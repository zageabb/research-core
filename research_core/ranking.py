from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar
from urllib.parse import urlsplit

from .evidence import COMMERCIAL_QUERY_TERMS, commercial_evidence_score, terms


T = TypeVar("T")

DEFAULT_EVIDENCE_SIGNALS = (
    "datasheet", "data sheet", "technical data", "technical catalogue", "catalogue",
    "manual", "product guide", "type designation", "specification", "iec", "ieee",
    "tender", "contract", "award", "framework", "schedule of rates", "purchase order",
    "bill of quantities", "boq", "quotation", "commercial offer", "invoice", "customs",
    "import", "export", "transaction",
)
DEFAULT_WEAK_SIGNALS = (
    "review", "best of", "top 10", "forum", "reddit", "quora", "pinterest",
)


@dataclass(frozen=True)
class RankingConfig:
    numeric_weight: float = 2.5
    title_weight: float = 0.75
    pdf_bonus: float = 3.0
    evidence_signal_bonus: float = 1.2
    commercial_evidence_weight: float = 1.5
    weak_signal_penalty: float = 1.5
    embedding_weight: float = 5.0
    max_per_domain: int = 3
    embedding_shortlist: int = 60


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def evidence_rank_score(
    title: str,
    snippet: str,
    url: str = "",
    *,
    query_is_commercial: bool = True,
    evidence_signals: Sequence[str] = DEFAULT_EVIDENCE_SIGNALS,
    weak_signals: Sequence[str] = DEFAULT_WEAK_SIGNALS,
    config: RankingConfig | None = None,
) -> float:
    """Score generic evidence quality signals independently from subject relevance.

    Applications that keep their own subject-specific ranking can add this score before
    cutting a fetch shortlist. The same evidence behaviour is therefore reusable without
    forcing consumers to replace their existing candidate models or relevance policy.
    """
    cfg = config or RankingConfig()
    item_title = str(title or "")
    item_snippet = str(snippet or "")
    item_url = str(url or "")
    corpus = f"{item_title} {item_snippet} {item_url}"
    lower_corpus = corpus.lower()

    score = 0.0
    if item_url.split("?", 1)[0].lower().endswith(".pdf"):
        score += cfg.pdf_bonus
    score += sum(cfg.evidence_signal_bonus for signal in evidence_signals if signal.lower() in lower_corpus)
    score += cfg.commercial_evidence_weight * commercial_evidence_score(
        corpus, query_is_commercial=query_is_commercial
    )
    score -= sum(cfg.weak_signal_penalty for signal in weak_signals if signal.lower() in lower_corpus)
    return score


def rank_candidates(
    candidates: Iterable[T],
    target_text: str,
    *,
    title: Callable[[T], str],
    snippet: Callable[[T], str],
    url: Callable[[T], str],
    query: Callable[[T], str] | None = None,
    embedding_vectors: dict[str, Sequence[float]] | None = None,
    target_vector: Sequence[float] | None = None,
    evidence_signals: Sequence[str] = DEFAULT_EVIDENCE_SIGNALS,
    weak_signals: Sequence[str] = DEFAULT_WEAK_SIGNALS,
    config: RankingConfig | None = None,
) -> list[T]:
    """Rank arbitrary app-specific search-result objects without taking ownership of their models.

    Candidate relevance is derived from the returned title/snippet/URL, not from the
    search query that produced the candidate. Including the originating query in the
    match corpus makes every result appear to contain the requested terms and flattens
    ranking quality, so query provenance is deliberately excluded from direct scoring.
    """
    cfg = config or RankingConfig()
    rows = list(candidates)
    if len(rows) < 2:
        return rows

    target_terms = terms(target_text)
    numeric_terms = {term for term in target_terms if any(char.isdigit() for char in term)}
    query_is_commercial = bool(target_terms & COMMERCIAL_QUERY_TERMS)
    scored: list[tuple[float, int, T]] = []
    for index, item in enumerate(rows):
        item_title = str(title(item) or "")
        item_snippet = str(snippet(item) or "")
        item_url = str(url(item) or "")
        item_query = str(query(item) or "") if query else ""

        # The originating query is useful provenance, but not evidence that the
        # result itself matches. Score only what the search engine returned.
        corpus = f"{item_title} {item_snippet} {item_url}"
        corpus_terms = terms(corpus)
        title_terms = terms(item_title)
        present = target_terms & corpus_terms
        numeric_present = numeric_terms & corpus_terms

        score = float(len(present))
        score += cfg.numeric_weight * len(numeric_present)
        score += cfg.title_weight * len(target_terms & title_terms)
        score += evidence_rank_score(
            item_title,
            item_snippet,
            item_url,
            query_is_commercial=query_is_commercial,
            evidence_signals=evidence_signals,
            weak_signals=weak_signals,
            config=cfg,
        )

        # A result returned by a complementary query gets no free relevance points,
        # but a query whose terms are visibly reflected in the result gets a small
        # provenance bonus. This rewards productive query variants without masking
        # irrelevant search-engine hits.
        if item_query:
            productive_terms = terms(item_query) & corpus_terms
            score += min(1.0, len(productive_terms) * 0.08)

        if target_vector is not None and embedding_vectors:
            vector = embedding_vectors.get(normalise_url(item_url))
            if vector is not None:
                score += cfg.embedding_weight * cosine_similarity(target_vector, vector)
        scored.append((score, index, item))

    ordered = [item for _score, _index, item in sorted(scored, key=lambda row: (-row[0], row[1]))]
    return diversify_domains(ordered, url=url, max_per_domain=cfg.max_per_domain)


def diversify_domains(candidates: Iterable[T], *, url: Callable[[T], str], max_per_domain: int = 3) -> list[T]:
    """Prefer source diversity while preserving all candidates as deferred fallbacks."""
    primary: list[T] = []
    deferred: list[T] = []
    counts: dict[str, int] = {}
    for item in candidates:
        host = hostname(url(item))
        if host and counts.get(host, 0) >= max_per_domain:
            deferred.append(item)
            continue
        if host:
            counts[host] = counts.get(host, 0) + 1
        primary.append(item)
    return [*primary, *deferred]


def hostname(value: str) -> str:
    try:
        return (urlsplit(str(value)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def normalise_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value).strip())
    except ValueError:
        return str(value).strip()
    scheme = parsed.scheme.lower() or "https"
    host = (parsed.hostname or "").lower().removeprefix("www.")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/") or "/"
    return f"{scheme}://{host}{port}{path}" + (f"?{parsed.query}" if parsed.query else "")
