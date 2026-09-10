from .depth import DynamicResearchConfig, DynamicResearchController, ResearchStopDecision
from .engine import CoverageAssessment, OperationResult, ResearchEngine, ResearchRun
from .evidence import EvidenceRecord, SourceQuality, best_passages, evidence_ledger
from .ranking import RankingConfig, rank_candidates

__all__ = [
    "DynamicResearchConfig",
    "DynamicResearchController",
    "ResearchStopDecision",
    "CoverageAssessment",
    "OperationResult",
    "ResearchEngine",
    "ResearchRun",
    "EvidenceRecord",
    "SourceQuality",
    "best_passages",
    "evidence_ledger",
    "RankingConfig",
    "rank_candidates",
]

__version__ = "0.2.0"
