from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "where", "which", "who",
    "why", "will", "with", "you", "your",
}

COMMERCIAL_QUERY_TERMS = {
    "price", "prices", "pricing", "cost", "costs", "quote", "quotation", "commercial", "tender", "award",
    "procurement", "boq", "invoice", "transaction", "customs", "import", "export", "purchase", "contract",
    "rate", "rates", "budget", "estimate", "market",
}
COMMERCIAL_EVIDENCE_PHRASES = (
    "unit price", "unit rate", "award value", "winning bid", "contract value", "estimated value",
    "schedule of rates", "bill of quantities", "boq", "purchase order", "commercial offer", "quotation",
    "invoice", "customs", "import", "export", "transaction value", "tender award",
)
PRICE_SIGNAL_RE = re.compile(
    r"(?:GBP|USD|EUR|JPY|INR|CNY|AUD|CAD|CHF|BDT|NPR|NGN|£|€|\$|₹|¥|৳)\s*"
    r"\d[\d,.]*(?:\s*(?:million|billion|thousand|[kmb]))?|"
    r"\d[\d,.]*(?:\s*(?:million|billion|thousand|[kmb]))?\s*"
    r"(?:GBP|USD|EUR|JPY|INR|CNY|AUD|CAD|CHF|BDT|NPR|NGN)",
    re.I,
)
SPEC_SIGNAL_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kV|V|kA|A|MVA|kVA|MW|kW|Hz|mm|cm|m|kg|GB|TB)\b",
    re.I,
)


class SourceQuality(str, Enum):
    STRONG = "strong"
    USEFUL = "useful"
    WEAK = "weak"
    REJECT = "reject"


@dataclass
class EvidenceRecord:
    source_id: int
    title: str
    url: str
    query: str = ""
    text: str = ""
    claims: list[str] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)
    quality: SourceQuality | str = SourceQuality.USEFUL
    published_at: str = ""
    obtained_at: str = ""
    metadata: dict = field(default_factory=dict)


def terms(value: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9][a-z0-9_.+/-]{1,}", str(value).lower())
        if word not in STOP_WORDS
    }


def commercial_evidence_score(value: str, *, query_is_commercial: bool = True) -> float:
    """Return a small generic bonus for passages that contain observable commercial evidence."""
    text = str(value or "")
    lower = text.lower()
    score = 0.0
    if PRICE_SIGNAL_RE.search(text):
        score += 1.0 if query_is_commercial else 0.2
    phrase_hits = sum(1 for phrase in COMMERCIAL_EVIDENCE_PHRASES if phrase in lower)
    score += min(0.75, phrase_hits * (0.25 if query_is_commercial else 0.1))
    return score


def best_passages(content: str, query: str, limit: int = 5, max_chars: int = 9_000) -> list[str]:
    """Return query-relevant passages while preserving useful numeric and commercial evidence."""
    target = terms(query)
    numeric_target = {term for term in target if any(char.isdigit() for char in term)}
    query_is_commercial = bool(target & COMMERCIAL_QUERY_TERMS)
    raw = [
        " ".join(part.split())
        for part in re.split(r"\n{1,}|(?<=[.!?])\s+(?=[A-Z0-9])", str(content))
    ]
    passages = [part for part in raw if 40 <= len(part) <= 2_500]
    if not passages:
        compact = " ".join(str(content).split())[:max_chars]
        return [compact] if compact else []

    scored: list[tuple[float, int, str, set[str], bool]] = []
    for index, passage in enumerate(passages):
        passage_terms = terms(passage)
        overlap = target & passage_terms
        coverage = len(overlap) / max(1, len(target))
        density = len(overlap) / max(1, len(passage_terms))
        numeric_overlap = len(numeric_target & passage_terms) / max(1, len(numeric_target)) if numeric_target else 0.0
        number_bonus = 0.08 if re.search(r"\b\d[\d,.%]*\b", passage) else 0.0
        spec_bonus = 0.3 if numeric_target and SPEC_SIGNAL_RE.search(passage) else 0.0
        commercial_bonus = commercial_evidence_score(passage, query_is_commercial=query_is_commercial)
        price_bearing = bool(PRICE_SIGNAL_RE.search(passage))
        score = coverage * 3 + density + numeric_overlap * 1.5 + number_bonus + spec_bonus + commercial_bonus
        scored.append((score, index, passage, passage_terms, price_bearing))

    selected: list[tuple[int, str]] = []
    selected_terms: list[set[str]] = []
    size = 0
    ordered = sorted(scored, key=lambda row: (-row[0], row[1]))
    for _score, index, passage, passage_terms, _price_bearing in ordered:
        if any(
            len(passage_terms & prior) / max(1, len(passage_terms | prior)) > 0.82
            for prior in selected_terms
        ):
            continue
        if size + len(passage) > max_chars and selected:
            continue
        selected.append((index, passage))
        selected_terms.append(passage_terms)
        size += len(passage)
        if len(selected) >= limit:
            break

    # For commercial research, do not let a price/award passage disappear merely
    # because a descriptive passage has slightly better lexical overlap. Reserve
    # one slot when a concrete price signal exists and the caller requested >1 passage.
    if query_is_commercial and limit > 1 and not any(PRICE_SIGNAL_RE.search(passage) for _, passage in selected):
        priced = next((row for row in ordered if row[4]), None)
        if priced:
            _score, index, passage, passage_terms, _ = priced
            if len(passage) <= max_chars:
                if len(selected) >= limit:
                    selected.pop()
                    selected_terms.pop()
                selected.append((index, passage))

    return [passage for _index, passage in sorted(selected)]


def normalise_quality(value: SourceQuality | str | None, default: SourceQuality = SourceQuality.WEAK) -> SourceQuality:
    try:
        return value if isinstance(value, SourceQuality) else SourceQuality(str(value or "").strip().lower())
    except ValueError:
        return default


def evidence_ledger(records: list[EvidenceRecord]) -> str:
    rows: list[str] = []
    for item in records:
        quality = normalise_quality(item.quality).value
        claims = "\n".join(f"- {claim}" for claim in item.claims) or "- No claims pre-extracted"
        passages = "\n\n".join(
            f"Passage {index}: {passage}" for index, passage in enumerate(item.passages, 1)
        )
        published = f"\nPublished: {item.published_at}" if item.published_at else ""
        obtained = item.obtained_at or date.today().isoformat()
        rows.append(
            f"[{item.source_id}] {item.title}\nURL: {item.url}\nFound via: {item.query}"
            f"{published}\nObtained: {obtained}\nQuality: {quality}\n"
            f"Extracted claims:\n{claims}\nRelevant passages:\n{passages or item.text}"
        )
    return "\n\n---\n\n".join(rows)
