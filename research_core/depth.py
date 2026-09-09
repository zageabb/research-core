from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DynamicResearchConfig:
    """Quality-led research budget with hard safety ceilings."""

    initial_batch: int = 8
    later_batch: int = 6
    hard_page_cap: int = 200
    hard_round_cap: int = 8
    stagnant_round_limit: int = 2

    def __post_init__(self) -> None:
        if self.initial_batch < 1 or self.later_batch < 1:
            raise ValueError("Research batch sizes must be at least 1.")
        if self.hard_page_cap < max(self.initial_batch, self.later_batch):
            raise ValueError("hard_page_cap must be at least as large as the batch sizes.")
        if self.hard_round_cap < 1:
            raise ValueError("hard_round_cap must be at least 1.")
        if self.stagnant_round_limit < 1:
            raise ValueError("stagnant_round_limit must be at least 1.")


@dataclass(frozen=True)
class ResearchStopDecision:
    stop: bool
    reason: str = ""


class DynamicResearchController:
    """Centralises stop/continue decisions without knowing the application's domain rules."""

    def __init__(self, config: DynamicResearchConfig | None = None) -> None:
        self.config = config or DynamicResearchConfig()

    def batch_size(self, round_number: int, pages_attempted: int) -> int:
        if round_number < 1:
            raise ValueError("round_number must start at 1.")
        remaining = max(0, self.config.hard_page_cap - max(0, pages_attempted))
        target = self.config.initial_batch if round_number == 1 else self.config.later_batch
        return min(target, remaining)

    def evaluate(
        self,
        *,
        round_number: int,
        pages_attempted: int,
        stagnant_rounds: int,
        domain_complete: bool,
        has_follow_up_queries: bool,
        has_unread_candidates: bool,
    ) -> ResearchStopDecision:
        if domain_complete:
            return ResearchStopDecision(True, "Evidence coverage is sufficient.")
        if pages_attempted >= self.config.hard_page_cap:
            return ResearchStopDecision(
                True,
                f"Research safety ceiling reached after {pages_attempted} page attempts.",
            )
        if stagnant_rounds >= self.config.stagnant_round_limit:
            return ResearchStopDecision(
                True,
                f"Research stopped after {stagnant_rounds} stagnant round(s).",
            )
        if not has_follow_up_queries and not has_unread_candidates:
            return ResearchStopDecision(
                True,
                "No productive follow-up search or unread candidate evidence remained.",
            )
        if round_number >= self.config.hard_round_cap:
            return ResearchStopDecision(
                True,
                f"Research safety round ceiling reached after {self.config.hard_round_cap} rounds.",
            )
        return ResearchStopDecision(False, "")
