from research_core.depth import DynamicResearchConfig, DynamicResearchController


def test_dynamic_batches_expand_until_safety_cap():
    controller = DynamicResearchController(DynamicResearchConfig(
        initial_batch=8, later_batch=6, hard_page_cap=20, hard_round_cap=8,
    ))
    assert controller.batch_size(1, 0) == 8
    assert controller.batch_size(2, 8) == 6
    assert controller.batch_size(3, 14) == 6
    assert controller.batch_size(4, 20) == 0


def test_domain_completion_stops_immediately():
    controller = DynamicResearchController()
    decision = controller.evaluate(
        round_number=1,
        pages_attempted=4,
        stagnant_rounds=0,
        domain_complete=True,
        has_follow_up_queries=True,
        has_unread_candidates=True,
    )
    assert decision.stop is True
    assert "sufficient" in decision.reason.lower()


def test_stagnation_stops_before_hard_cap():
    controller = DynamicResearchController(DynamicResearchConfig(stagnant_round_limit=2))
    decision = controller.evaluate(
        round_number=3,
        pages_attempted=12,
        stagnant_rounds=2,
        domain_complete=False,
        has_follow_up_queries=True,
        has_unread_candidates=True,
    )
    assert decision.stop is True
    assert "stagnant" in decision.reason.lower()
