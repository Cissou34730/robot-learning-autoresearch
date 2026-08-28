import json

import pytest

from research.run_experiment import (
    record_previous_postmortem,
    select_tournament_winner,
    summarize_noise_floor,
    summarize_tournament,
    training_budget,
)
from robot_learning.training.comparison import (
    exact_mcnemar_pvalue,
    paired_comparison,
)


def evaluation(seed: int, outcomes: list[bool]) -> dict:
    failures = outcomes.count(False)
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "failed_episode_progress": {
            "failed_episodes": failures,
            "longest_consecutive_steps_mean": 99.0 if failures else 100.0,
            "best_window_inside_steps_mean": 99.0 if failures else 100.0,
            "best_window_excess_cm_mean": 0.01 if failures else 0.0,
            "required_steps": 100,
        },
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "target_radius_cm": 10.0,
                "target_angle_degrees": 0.0,
                "longest_consecutive_steps": 100 if outcome else 99,
                "best_window_inside_steps": 100 if outcome else 99,
                "best_window_excess_cm": 0.0 if outcome else 0.01,
                "final_distance_cm": 0.5,
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def test_paired_comparison_uses_identical_episode_outcomes():
    candidate = [evaluation(3000, [True, True, True, True, True, True])]
    champion = [evaluation(3000, [False, False, False, False, False, False])]

    comparison = paired_comparison(candidate, champion)

    assert comparison["candidate_wins"] == 6
    assert comparison["reference_wins"] == 0
    assert comparison["success_delta_percent"] == 100.0
    assert comparison["exact_p_value"] == pytest.approx(0.03125)


def test_tournament_summary_keeps_failed_target_diagnostics():
    summary = summarize_tournament([evaluation(3000, [True, False])])

    assert summary["failure_diagnostics"] == [
        {
            "episode": 1,
            "episode_seed": 3001,
            "success": False,
            "target_radius_cm": 10.0,
            "target_angle_degrees": 0.0,
            "longest_consecutive_steps": 99,
            "best_window_inside_steps": 99,
            "best_window_excess_cm": 0.01,
            "final_distance_cm": 0.5,
        }
    ]


def test_paired_promotion_requires_significance_and_noise_margin():
    candidate_summary = summarize_tournament(
        [evaluation(3000, [True, True, True, True, True, True])]
    )
    champion_summary = summarize_tournament(
        [evaluation(3000, [False, False, False, False, False, False])]
    )
    candidate = {
        "name": "candidate",
        "kind": "candidate",
        "summary": candidate_summary,
        "paired_vs_champion": paired_comparison(
            [evaluation(3000, [True] * 6)],
            [evaluation(3000, [False] * 6)],
        ),
    }
    champion = {"name": "champion", "kind": "champion", "summary": champion_summary}

    assert select_tournament_winner([candidate, champion], 10.0) is candidate
    assert select_tournament_winner([candidate, champion], 100.0) is champion


def test_exact_p_value_is_one_without_discordant_episodes():
    assert exact_mcnemar_pvalue(0, 0) == 1.0


def test_noise_floor_comes_from_independent_training_replicates():
    floor = summarize_noise_floor(
        [
            {"training_seed": 0, "summary": {"pooled_success_percent": 97.0}},
            {"training_seed": 1, "summary": {"pooled_success_percent": 98.0}},
            {"training_seed": 2, "summary": {"pooled_success_percent": 99.0}},
        ]
    )

    assert floor["pooled_success_range_pp"] == 2.0
    assert floor["pooled_success_std_pp"] == 1.0


def test_fresh_challenger_receives_runner_owned_compute_matching():
    assert training_budget(120_000, "transfer", False, 720_000) == 120_000
    assert training_budget(120_000, "fresh", False, 720_000) == 720_000
    assert training_budget(120_000, "fresh", True, 720_000) == 120_000


def test_previous_postmortem_is_required_and_recorded(monkeypatch, tmp_path):
    results = tmp_path / "results.jsonl"
    postmortems = tmp_path / "postmortems.md"
    results.write_text(json.dumps({"index": 7}) + "\n", encoding="utf-8")
    postmortems.write_text("# Research postmortems\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.RESULTS_PATH", results)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path)

    with pytest.raises(TypeError, match="previous_experiment_postmortem"):
        record_previous_postmortem({}, baseline=False)

    record_previous_postmortem(
        {
            "previous_experiment_postmortem": {
                "experiment": 7,
                "result": "No promotion.",
                "behavior": "Candidate tied the champion.",
                "learned": "Do not repeat the same optimizer change.",
                "next_class": "Inspect failure geometry.",
            }
        },
        baseline=False,
    )

    memory = postmortems.read_text(encoding="utf-8")
    assert "## Experiment 7" in memory
    assert "Inspect failure geometry" in memory
