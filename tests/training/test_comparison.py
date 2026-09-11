import pytest

from robot_learning.training.comparison import episode_outcomes, paired_comparison


def evaluation(seed: int, outcomes: list[bool], semantics: str = "current") -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "evaluation_semantics": semantics,
        "episode_results": [
            {"episode": index, "episode_seed": seed + index, "success": success}
            for index, success in enumerate(outcomes)
        ],
    }


def test_overlapping_panels_do_not_duplicate_paired_wins():
    candidate = [evaluation(0, [True, True]), evaluation(1, [True, False])]
    reference = [evaluation(0, [True, False]), evaluation(1, [False, False])]

    comparison = paired_comparison(candidate, reference)

    assert comparison["episodes"] == 3
    assert comparison["candidate_wins"] == 1
    assert comparison["reference_wins"] == 0
    assert comparison["success_delta_percent"] == pytest.approx(100 / 3)
    assert comparison["exact_p_value"] == 1.0


def test_repeated_identical_panel_does_not_change_comparison():
    candidate = evaluation(10, [True, True])
    reference = evaluation(10, [True, False])

    assert paired_comparison([candidate, candidate], [reference, reference]) == (
        paired_comparison([candidate], [reference])
    )


def test_overlapping_conflicting_outcomes_are_rejected():
    with pytest.raises(ValueError, match="conflicting deterministic measurements"):
        episode_outcomes([evaluation(0, [True, False]), evaluation(1, [True])])


def test_recorded_identity_not_panel_offset_controls_comparison():
    candidate = evaluation(0, [True])
    reference = evaluation(0, [False])
    reference["episode_results"][0]["episode_seed"] = 42

    with pytest.raises(ValueError, match="do not share any episodes"):
        paired_comparison([candidate], [reference])


def test_partial_panel_overlap_reports_shared_and_source_coverage():
    candidate = evaluation(10, [True] * 200)
    reference = evaluation(10, [False] * 1000)

    comparison = paired_comparison([candidate], [reference])

    assert comparison["episodes"] == 200
    assert comparison["shared_episodes"] == 200
    assert comparison["candidate_episode_coverage"] == 200
    assert comparison["reference_episode_coverage"] == 1000
    assert comparison["candidate_wins"] == 200


def test_different_evaluation_semantics_do_not_collapse():
    outcomes = episode_outcomes(
        [evaluation(0, [True], "old"), evaluation(0, [False], "new")]
    )

    assert len(outcomes) == 2


def test_compact_metrics_cannot_claim_distinct_episode_coverage():
    with pytest.raises(ValueError, match="complete detailed episode outcomes"):
        episode_outcomes([{"episodes": 100, "seed": 0, "success_percent": 98}])