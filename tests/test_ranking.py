from dataclasses import dataclass

from research_core.ranking import RankingConfig, evidence_rank_score, rank_candidates


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


def test_originating_query_does_not_make_irrelevant_result_look_exact():
    target = "11 kV 2000 A 25 kA switchgear price"
    candidates = [
        Candidate(
            "General electrical catalogue",
            "https://weak.example.com/catalogue",
            "Low voltage accessories and unrelated equipment.",
            query=target,
        ),
        Candidate(
            "11 kV switchgear import transaction",
            "https://trade.example.com/11kv-switchgear",
            "11 kV 2000 A 25 kA incomer panel transaction value USD 15,979.85.",
            query="11 kV 2000 A 25 kA switchgear import export customs",
        ),
    ]
    ranked = rank_candidates(
        candidates,
        target,
        title=lambda item: item.title,
        snippet=lambda item: item.snippet,
        url=lambda item: item.url,
        query=lambda item: item.query,
    )
    assert "trade.example.com" in ranked[0].url


def test_commercial_evidence_ranks_before_technical_only_when_pricing_requested():
    candidates = [
        Candidate(
            "11 kV 630 A 25 kA switchgear technical specification",
            "https://oem.example.com/spec",
            "IEC 62271-200 metal-clad switchgear, 11 kV, 630 A, 25 kA.",
        ),
        Candidate(
            "11 kV 630 A 25 kA tender award",
            "https://tender.example.com/award",
            "Winning bid INR 4,663,359 for seven 11 kV 630 A 25 kA panels.",
        ),
    ]
    ranked = rank_candidates(
        candidates,
        "11 kV 630 A 25 kA switchgear tender award price",
        title=lambda item: item.title,
        snippet=lambda item: item.snippet,
        url=lambda item: item.url,
    )
    assert "tender.example.com" in ranked[0].url


def test_evidence_rank_score_can_be_reused_before_an_app_fetch_shortlist():
    commercial = evidence_rank_score(
        "11 kV switchgear tender award",
        "BOQ unit price INR 402,543 for each 630 A VCB panel.",
        "https://procurement.example.com/award.pdf",
    )
    generic = evidence_rank_score(
        "11 kV switchgear overview",
        "General product marketing page with no commercial or technical evidence.",
        "https://example.com/switchgear",
    )
    weak = evidence_rank_score(
        "Top 10 switchgear reviews",
        "Forum review roundup.",
        "https://example.com/reviews",
    )

    assert commercial > generic
    assert generic > weak


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
