from dataclasses import dataclass

from research_core.ranking import RankingConfig, rank_candidates


@dataclass
class Candidate:
    title: str
    url: str
    snippet: str
    query: str = ""


def test_matching_datasheet_ranks_before_generic_result():
    candidates = [
        Candidate(
            "Switchgear accessories and reviews",
            "https://example.com/reviews/switchgear",
            "Generic accessory overview and review page.",
        ),
        Candidate(
            "NX-12 Technical Datasheet 12 kV 3150 A 31.5 kA IEC 62271-200",
            "https://oem.example.com/nx12-datasheet.pdf",
            "NX-12 metal enclosed switchgear technical data.",
        ),
    ]
    ranked = rank_candidates(
        candidates,
        "NX-12 12 kV 3150 A 31.5 kA IEC 62271-200",
        title=lambda item: item.title,
        snippet=lambda item: item.snippet,
        url=lambda item: item.url,
        query=lambda item: item.query,
    )
    assert ranked[0].url.endswith("nx12-datasheet.pdf")


def test_domain_diversity_defers_excess_results():
    candidates = [
        Candidate(f"Exact datasheet {index}", f"https://same.example.com/p{index}.pdf", "12 kV 3150 A")
        for index in range(4)
    ] + [Candidate("Alternate OEM", "https://other.example.com/spec.pdf", "12 kV 3150 A")]
    ranked = rank_candidates(
        candidates,
        "12 kV 3150 A",
        title=lambda item: item.title,
        snippet=lambda item: item.snippet,
        url=lambda item: item.url,
        config=RankingConfig(max_per_domain=2),
    )
    assert ranked.index(next(item for item in ranked if "other.example.com" in item.url)) < 4
