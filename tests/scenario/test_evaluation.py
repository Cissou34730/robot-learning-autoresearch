"""Researcher-owned tests for the scenario research evaluation.

The scenario owns which diagnostics survive into the summary that the brief and
the runner present. Changing those diagnostics is a normal research change.
"""

import pytest

from robot_learning.scenario import (
    render_scenario_evidence,
    summarize_research_evaluations,
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


def test_evaluation_summary_keeps_failed_target_diagnostics():
    summary = summarize_research_evaluations([evaluation(3000, [True, False])])

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


def test_evaluation_summary_pools_seed_panels():
    summary = summarize_research_evaluations(
        [evaluation(3000, [True, False]), evaluation(4000, [True, True])]
    )

    assert summary["episodes"] == 4
    assert summary["seed_count"] == 2
    assert summary["pooled_success_percent"] == pytest.approx(75.0)


def test_scenario_evidence_is_rendered_from_the_summary():
    evidence = render_scenario_evidence(
        summarize_research_evaluations([evaluation(3000, [True, False])])
    )

    assert evidence
    assert all(isinstance(line, str) for line in evidence)
