from research_core.evidence import EvidenceRecord, SourceQuality, best_passages, evidence_ledger


def test_best_passages_prefers_query_terms_and_numbers():
    content = (
        "This generic company paragraph describes products and services without technical detail.\n"
        "The NX-12 switchgear is rated 12 kV, 3150 A and 31.5 kA to IEC 62271-200.\n"
        "Contact our sales team for further information about unrelated products."
    )
    passages = best_passages(content, "NX-12 12 kV 3150 A 31.5 kA IEC 62271-200", limit=1)
    assert len(passages) == 1
    assert "3150 A" in passages[0]


def test_evidence_ledger_preserves_quality():
    ledger = evidence_ledger([
        EvidenceRecord(
            source_id=1,
            title="OEM datasheet",
            url="https://example.com/spec.pdf",
            query="NX-12 datasheet",
            quality=SourceQuality.STRONG,
            claims=["Rated 12 kV"],
            passages=["NX-12 is rated 12 kV."],
            obtained_at="2026-09-09",
        )
    ])
    assert "Quality: strong" in ledger
    assert "[1] OEM datasheet" in ledger
