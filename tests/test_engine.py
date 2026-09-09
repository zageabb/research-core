from dataclasses import dataclass

from research_core.depth import DynamicResearchConfig, DynamicResearchController
from research_core.engine import CoverageAssessment, OperationResult, ResearchEngine


@dataclass
class Candidate:
    url: str


def test_engine_stops_when_domain_assessment_is_complete():
    controller = DynamicResearchController(DynamicResearchConfig(initial_batch=2, later_batch=2, hard_page_cap=10))
    engine = ResearchEngine(controller)

    def search(queries, seen):
        items = [Candidate("https://example.com/a"), Candidate("https://example.com/b")]
        seen.update(item.url for item in items)
        return OperationResult(items=items)

    def rank(items, _target):
        return OperationResult(items=items)

    def read(items, source_id):
        return OperationResult(items=[{"source_id": source_id + index, "url": item.url} for index, item in enumerate(items)])

    def review(items):
        return OperationResult(items=items)

    def assess(evidence):
        return CoverageAssessment(complete=len(evidence) >= 2, summary="Enough evidence")

    result = engine.run(
        initial_queries=["test"],
        target_text="test",
        search=search,
        rank=rank,
        read=read,
        review=review,
        assess=assess,
        candidate_key=lambda item: item.url,
    )

    assert result.pages_attempted == 2
    assert len(result.evidence) == 2
    assert "sufficient" in result.stop_reason.lower()
