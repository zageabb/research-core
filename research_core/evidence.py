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


def best_passages(content: str, query: str, limit: int = 5, max_chars: int = 9_000) -> list[str]:
    """Return query-relevant, de-duplicated passages instead of sending a whole page to an LLM."""
    target = terms(query)
    raw = [
        " ".join(part.split())
        for part in re.split(r"\n{1,}|(?<=[.!?])\s+(?=[A-Z0-9])", str(content))
    ]
    passages = [part for part in raw if 40 <= len(part) <= 2_500]
    if not passages:
        compact = " ".join(str(content).split())[:max_chars]
        return [compact] if compact else []

    scored: list[tuple[float, int, str, set[str]]] = []
    for index, passage in enumerate(passages):
        passage_terms = terms(passage)
        coverage = len(target & passage_terms) / max(1, len(target))
        density = len(target & passage_terms) / max(1, len(passage_terms))
        number_bonus = 0.08 if re.search(r"\b\d[\d,.%]*\b", passage) else 0.0
        scored.append((coverage * 3 + density + number_bonus, index, passage, passage_terms))

    selected: list[tuple[int, str]] = []
    selected_terms: list[set[str]] = []
    size = 0
    for _score, index, passage, passage_terms in sorted(scored, key=lambda row: (-row[0], row[1])):
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
