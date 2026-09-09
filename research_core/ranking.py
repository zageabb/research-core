from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, TypeVar
from urllib.parse import urlsplit

from .evidence import terms


T = TypeVar("T")

DEFAULT_EVIDENCE_SIGNALS = (
    "datasheet", "data sheet", "technical data", "technical catalogue", "catalogue",
    "manual", "product guide", "type designation", "specification", "iec", "ieee",
    "tender", "contract", "award", "framework", "schedule of rates", "purchase order",
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
    """Rank arbitrary app-specific search-result objects without taking ownership of their models."""
    cfg = config or RankingConfig()
    rows = list(candidates)
    if len(rows) < 2:
        return rows

    target_terms = terms(target_text)
    numeric_terms = {term for term in target_terms if any(char.isdigit() for char in term)}
    scored: list[tuple[float, int, T]] = []
    for index, item in enumerate(rows):
        item_title = str(title(item) or "").lower()
        item_snippet = str(snippet(item) or "").lower()
        item_url = str(url(item) or "")
        item_query = str(query(item) or "").lower() if query else ""
        haystack = f"{item_title} {item_snippet} {item_url.lower()} {item_query}"
        present = {term for term in target_terms if term in haystack}
        score = float(len(present))
        score += cfg.numeric_weight * len({term for term in numeric_terms if term in haystack})
        score += cfg.title_weight * len({term for term in target_terms if term in item_title})
        if item_url.split("?", 1)[0].lower().endswith(".pdf"):
            score += cfg.pdf_bonus
        score += sum(cfg.evidence_signal_bonus for signal in evidence_signals if signal.lower() in haystack)
        score -= sum(cfg.weak_signal_penalty for signal in weak_signals if signal.lower() in haystack)
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
