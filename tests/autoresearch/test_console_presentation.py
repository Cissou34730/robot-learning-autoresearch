"""The AutoResearch console must read as a research loop of existing facts."""

import json

import pytest

from research import run_experiment
from research.build_research_brief import render_research_brief
from research.runner_console import (
    render_decision_card,
    render_evaluation_plan,
    render_evidence_card,
    render_experiment_card,
    render_training_summary_card,
    training_progress_suffix,
)
from research.runner_protocol import validate_evaluation_request
from robot_learning.training.progress import (
    latest_training_record,
    parse_training_records,
)

TRAINING_LOG = """
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 487         |
|    ep_rew_mean          | -42.1       |
|    success_rate         | 0.18        |
| time/                   |             |
|    total_timesteps      | 20480       |
| train/                  |             |
|    explained_variance   | 0.4         |
|    std                  | 0.57        |
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 400         |
|    ep_rew_mean          | -19.7       |
| time/                   |             |
|    total_timesteps      | 61440       |
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 326         |
|    ep_rew_mean          | -6.9        |
|    success_rate         | 0.61        |
| time/                   |             |
|    total_timesteps      | 120832      |
| train/                  |             |
|    explained_variance   | 0.9         |
|    std                  | 0.46        |
-----------------------------------------
Model saved to models/candidates/experiment-2/model.zip
"""


def test_extracted_parser_reads_every_snapshot():
    records = parse_training_records(TRAINING_LOG)

    assert len(records) == 3
    assert records[0]["total_timesteps"] == 20480
    assert records[0]["success_rate"] == 0.18
    assert records[-1]["std"] == 0.46


def test_extracted_parser_tolerates_missing_fields():
    records = parse_training_records(TRAINING_LOG)

    assert "success_rate" not in records[1]
    assert "std" not in records[1]


def test_latest_snapshot_skips_a_block_without_a_step_counter():
    partial = TRAINING_LOG + "| rollout/                |             |\n"

    assert latest_training_record(partial)["total_timesteps"] == 120832
    assert latest_training_record("no metrics here") is None


def test_live_progress_shows_reward_and_one_scenario_metric():
    suffix = training_progress_suffix({"ep_rew_mean": -6.9, "success_rate": 0.61})

    assert suffix == " | -6.9 | 61%"
    assert suffix.count("|") == 2


def test_live_progress_omits_each_missing_metric():
    assert training_progress_suffix({"ep_rew_mean": -6.9}) == " | -6.9"
    assert training_progress_suffix({"success_rate": 0.61}) == " | 61%"
    assert training_progress_suffix({"ep_len_mean": 400}) == ""
    assert training_progress_suffix(None) == ""


def experiment_result() -> dict:
    return {
        "index": 2,
        "hypothesis": "The closeness potential decays too quickly at long range.",
        "change": "widen the closeness length scale",
        "family": "reward.long_range_shaping",
        "initialization": "transfer",
        "training_parent": "accepted",
        "training_seed": 0,
        "training_budget_steps": 120_000,
        "parameter_changes": [
            {"path": "reward.CLOSENESS_LENGTH_SCALE", "before": 0.05, "after": 0.10}
        ],
    }


def test_experiment_card_leads_with_the_hypothesis_and_the_mutation():
    card = render_experiment_card(experiment_result())

    assert card.startswith("=== Research hypothesis · Experiment 2 ===")
    assert "The closeness potential decays too quickly at long range." in card
    assert "reward.CLOSENESS_LENGTH_SCALE: 0.05 → 0.1" in card
    assert "Family : reward.long_range_shaping" in card
    assert "Parent : accepted" in card
    assert "Init   : transfer" in card
    assert "Seed   : 0" in card
    assert "Budget : 120,000 steps" in card


def test_experiment_card_falls_back_to_the_code_change_description():
    result = experiment_result()
    result["parameter_changes"] = []

    assert "widen the closeness length scale" in render_experiment_card(result)


def test_training_summary_reports_checkpoint_aligned_candidate_facts():
    card = render_training_summary_card(
        experiment_result(),
        completed_steps=120_832,
        elapsed_seconds=534,
        candidates=[
            {
                "name": "checkpoint-120832",
                "timesteps": 120_832,
                "training_success": 0.0,
                "ep_rew_mean": -6.9,
            },
            {
                "name": "checkpoint-30720",
                "timesteps": 30_720,
                "training_success": None,
                "ep_rew_mean": 0.0,
            },
        ],
    )

    assert "=== Training summary · Experiment 2 ===" in card
    assert "Hypothesis : The closeness potential decays too quickly" in card
    assert "Change     : reward.CLOSENESS_LENGTH_SCALE: 0.05 → 0.1" in card
    assert "Family     : reward.long_range_shaping" in card
    assert "Parent     : accepted" in card
    assert "Init       : transfer" in card
    assert "Seed       : 0" in card
    assert "Budget     : 120,000 steps" in card
    assert "Completed  : 120,832 steps in 8m54s" in card
    assert "Training dynamics" not in card
    assert "Episode length" not in card
    assert "Candidate | Steps | Training success | Training reward" in card
    assert "checkpoint-30720 | 30,720 | unavailable | 0" in card
    assert "checkpoint-120832 | 120,832 | 0% | -6.9" in card
    assert card.index("checkpoint-30720") < card.index("checkpoint-120832")
    assert "Next\n  Researcher evaluation design" in card


def test_training_summary_keeps_missing_checkpoint_metrics_distinct_from_zero():
    card = render_training_summary_card(
        experiment_result(),
        completed_steps=1024,
        elapsed_seconds=12,
        candidates=[
            {
                "name": "checkpoint-1024",
                "timesteps": 1024,
                "training_success": None,
                "ep_rew_mean": 0.0,
            }
        ],
    )

    assert "checkpoint-1024 | 1,024 | unavailable | 0" in card


def test_runner_no_longer_dumps_the_structured_result_to_the_console():
    source = run_experiment.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()

    assert "SUMMARY: " not in text
    assert "append_result(result)" in text


def evaluation_request() -> dict:
    return {
        "experiment": 2,
        "question": "Did the longer-range shaping improve acquisition?",
        "reason": "A matched panel directly tests the hypothesis.",
        "evaluations": [
            {
                "candidate": "checkpoint-120832",
                "episodes": 200,
                "seed": 2000,
                "label": "checkpoint-120832",
            },
            {"candidate": "champion", "episodes": 200, "seed": 2000},
        ],
        "paired_comparisons": [
            {"candidate": "checkpoint-120832", "reference": "champion"}
        ],
    }


@pytest.mark.parametrize("field", ["question", "reason"])
@pytest.mark.parametrize("value", [None, "", "   ", 7])
def test_evaluation_request_requires_the_scientific_framing(field, value):
    request = evaluation_request()
    if value is None:
        del request[field]
    else:
        request[field] = value

    with pytest.raises(ValueError, match=f"non-empty {field}"):
        validate_evaluation_request(request)


def test_valid_evaluation_request_passes_validation():
    validate_evaluation_request(evaluation_request())


def test_evaluation_plan_shows_the_question_panel_and_reason():
    plan = render_evaluation_plan(evaluation_request(), 2)

    assert plan.startswith("=== Evaluation design · Experiment 2 ===")
    assert "Did the longer-range shaping improve acquisition?" in plan
    assert "checkpoint-120832   200 episodes · seed 2000" in plan
    assert "champion" in plan
    assert "paired comparison   checkpoint-120832 vs champion" in plan
    assert "A matched panel directly tests the hypothesis." in plan
    for interpretation in ("supported", "rejected", "significant", "better"):
        assert interpretation not in plan


def test_evaluation_plan_survives_a_recovered_request_without_framing():
    request = evaluation_request()
    del request["question"]
    del request["reason"]

    plan = render_evaluation_plan(request, 2)

    assert "Question" not in plan
    assert "Reason" not in plan
    assert "checkpoint-120832   200 episodes · seed 2000" in plan


def measured_summary(success: float) -> dict:
    return {
        "episodes": 200,
        "seed_count": 1,
        "pooled_success_percent": success,
        "success_percent": success,
    }


def test_evidence_card_reports_only_measured_facts():
    card = render_evidence_card(
        2,
        [{"name": "checkpoint-120832", "summary": measured_summary(64.0)}],
        measured_summary(59.0),
        [
            {
                "candidate": "checkpoint-120832",
                "reference": "champion",
                "success_delta_percent": 5.0,
            }
        ],
        "Researcher lineage decision",
    )

    assert card.startswith("=== Evidence · Experiment 2 ===")
    assert "checkpoint-120832   success 64.0% · 200 episodes" in card
    assert "Champion\n  success 59.0% · 200 episodes" in card
    assert "checkpoint-120832 vs champion" in card
    assert "delta +5.0 pp" in card
    assert "Next\n  Researcher lineage decision" in card


def test_evidence_card_adds_no_scenario_interpretation():
    card = render_evidence_card(
        2,
        [{"name": "checkpoint", "summary": measured_summary(64.0)}],
        None,
        [],
        "Researcher evaluation design",
    )

    assert "Scenario evidence" not in card
    assert "Champion" not in card
    assert "Paired comparison" not in card


def lineage_plan() -> dict:
    return {
        "pending": {"experiment": 2},
        "decision": {
            "reason": "The candidate improves the measured behavior sufficiently.",
        },
        "selected_name": "checkpoint-120832",
        "code_action": "keep",
        "retentions": [],
        "removed_retained": [],
        "request_final_benchmark": False,
    }


def test_decision_card_shows_the_researcher_decision_only():
    card = render_decision_card(lineage_plan())

    assert card.startswith("=== Research decision · Experiment 2 ===")
    assert "Continue from\ncheckpoint-120832" in card
    assert "The candidate improves the measured behavior sufficiently." in card
    assert "Code\nkeep" in card
    assert "Retained alternatives\n  none" in card
    assert "Final benchmark\nnot requested" in card
    assert "Hypothesis supported" not in card
    assert "Hypothesis rejected" not in card


def test_decision_card_lists_retained_and_removed_alternatives():
    plan = lineage_plan()
    plan["retentions"] = [
        {"record": {"id": "wide-shaping", "candidate": "checkpoint-120832"}}
    ]
    plan["removed_retained"] = [{"id": "old-branch"}]
    plan["request_final_benchmark"] = True

    card = render_decision_card(plan)

    assert "  wide-shaping (from checkpoint-120832)" in card
    assert "Removed retained alternatives\n  old-branch" in card
    assert "Final benchmark\nrequested" in card


def test_evaluation_plan_is_printed_before_any_evaluation_runs(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 2,
                    "candidates": [
                        {
                            "name": "checkpoint-120832",
                            "artifact": "archive/checkpoint-120832",
                            "timesteps": 120832,
                            "evaluations": [],
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "transfer",
                    "training_budget_steps": 120_000,
                    "parent_training_steps": 0,
                    "result": {"index": 2, "change": "widen", "hypothesis": "decay"},
                },
            }
        ),
        encoding="utf-8",
    )
    request = evaluation_request()
    request["evaluations"] = [
        {"candidate": "checkpoint-120832", "episodes": 2, "seed": 2000}
    ]
    request["paired_comparisons"] = []
    request_path.write_text(json.dumps(request), encoding="utf-8")

    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )
    monkeypatch.setattr("research.runner_repository.append_result", lambda result: None)

    printed: list[str] = []
    monkeypatch.setattr("research.runner_console.announce", printed.append)
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact",
        lambda artifact, seed, **kwargs: {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        },
    )

    assert run_experiment.execute_pending_evaluations() == 0
    assert "=== Evaluation design · Experiment 2 ===" in printed[0]
    assert "=== Evidence · Experiment 2 ===" in printed[-1]


def test_brief_names_the_active_method_without_dumping_its_configuration(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text(
        json.dumps(
            {
                "algorithm": {"name": "active-method"},
                "active-method": {
                    "learning_rate": 0.0003,
                    "exploration_bonus": 0.01,
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)
    brief = render_research_brief()

    assert "Current learning method: ACTIVE-METHOD" in brief
    assert "## Current parameters" not in brief
    assert "learning_rate" not in brief
    assert "exploration_bonus" not in brief
