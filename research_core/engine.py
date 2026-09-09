from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Iterable, TypeVar

from .depth import DynamicResearchController


CandidateT = TypeVar("CandidateT")
EvidenceT = TypeVar("EvidenceT")


@dataclass
class OperationResult(Generic[CandidateT]):
    items: list[CandidateT] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class CoverageAssessment:
    complete: bool = False
    follow_up_queries: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ResearchRun(Generic[EvidenceT]):
    evidence: list[EvidenceT]
    pages_attempted: int
    rounds_completed: int
    stop_reason: str
    diagnostics: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


class ResearchEngine(Generic[CandidateT, EvidenceT]):
    """Application-neutral, quality-led research loop.

    Applications keep ownership of search providers, page readers, prompts, source review,
    evidence models and domain sufficiency rules. The core owns candidate pooling, batching,
    dynamic-depth control, stagnation handling and the stop/continue lifecycle.
    """

    def __init__(self, controller: DynamicResearchController | None = None) -> None:
        self.controller = controller or DynamicResearchController()

    def run(
        self,
        *,
        initial_queries: list[str],
        target_text: str,
        search: Callable[[list[str], set[str]], OperationResult[CandidateT]],
        rank: Callable[[list[CandidateT], str], OperationResult[CandidateT]],
        read: Callable[[list[CandidateT], int], OperationResult[EvidenceT]],
        review: Callable[[list[EvidenceT]], OperationResult[EvidenceT]],
        assess: Callable[[list[EvidenceT]], CoverageAssessment],
        candidate_key: Callable[[CandidateT], str],
        progress: Callable[[dict], None] | None = None,
    ) -> ResearchRun[EvidenceT]:
        progress = progress or (lambda _event: None)
        evidence: list[EvidenceT] = []
        candidate_pool: list[CandidateT] = []
        seen_urls: set[str] = set()
        consumed_urls: set[str] = set()
        diagnostics: list[str] = []
        steps: list[str] = []
        active_queries = list(initial_queries)
        pages_attempted = 0
        next_source_id = 1
        stagnant_rounds = 0
        rounds_completed = 0
        stop_reason = "Research completed."

        for round_number in range(1, self.controller.config.hard_round_cap + 1):
            rounds_completed = round_number
            progress({"kind": "phase", "round": round_number, "status": "running"})

            new_candidates: list[CandidateT] = []
            if active_queries:
                searched = search(active_queries, seen_urls)
                new_candidates = searched.items
                diagnostics.extend(searched.diagnostics)
                candidate_pool.extend(new_candidates)

            unread = [item for item in candidate_pool if candidate_key(item) not in consumed_urls]
            ranked_result = rank(unread, target_text)
            diagnostics.extend(ranked_result.diagnostics)
            ranked = ranked_result.items

            batch_size = self.controller.batch_size(round_number, pages_attempted)
            batch = ranked[:batch_size]
            for item in batch:
                consumed_urls.add(candidate_key(item))

            opened = OperationResult[EvidenceT]()
            if batch:
                opened = read(batch, next_source_id)
                diagnostics.extend(opened.diagnostics)
                pages_attempted += len(batch)
                next_source_id += len(batch)

            reviewed = review(opened.items)
            diagnostics.extend(reviewed.diagnostics)
            evidence.extend(reviewed.items)
            stagnant_rounds = 0 if reviewed.items else stagnant_rounds + 1

            assessment = assess(evidence)
            if assessment.summary:
                steps.append(assessment.summary)
            active_queries = list(assessment.follow_up_queries)

            unread_remaining = any(candidate_key(item) not in consumed_urls for item in candidate_pool)
            decision = self.controller.evaluate(
                round_number=round_number,
                pages_attempted=pages_attempted,
                stagnant_rounds=stagnant_rounds,
                domain_complete=assessment.complete,
                has_follow_up_queries=bool(active_queries),
                has_unread_candidates=unread_remaining,
            )
            round_summary = (
                f"Research round {round_number}: {len(new_candidates)} new candidate(s), "
                f"{len(batch)} page attempt(s), {len(reviewed.items)} evidence source(s) retained; "
                f"{len(evidence)} retained in total."
            )
            steps.append(round_summary)
            progress({
                "kind": "round",
                "round": round_number,
                "status": "returned",
                "summary": round_summary,
                "assessment": assessment.summary,
            })
            if decision.stop:
                stop_reason = decision.reason
                break

        return ResearchRun(
            evidence=evidence,
            pages_attempted=pages_attempted,
            rounds_completed=rounds_completed,
            stop_reason=stop_reason,
            diagnostics=diagnostics,
            steps=steps,
        )
