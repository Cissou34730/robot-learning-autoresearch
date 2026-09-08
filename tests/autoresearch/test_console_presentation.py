"""The AutoResearch console must read as a research loop of existing facts."""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from research import run_experiment, runner_console
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

ROOT = Path(__file__).resolve().parents[2]


def test_runner_timestamp_uses_local_time(monkeypatch, capsys):
    class FixedLocalDateTime:
        @classmethod
        def now(cls, timezone=None):
            assert timezone is None
            return datetime(2026, 9, 7, 0, 12, 34)  # noqa: DTZ001

    monkeypatch.setattr(runner_console, "datetime", FixedLocalDateTime)

    runner_console.announce("[checks] passed")

    assert capsys.readouterr().out == "[00:12:34] [checks] passed\n"


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


def test_v4_training_summary_advances_to_post_training_analysis():
    result = experiment_result()
    result["schema_version"] = 4

    card = render_training_summary_card(
        result, completed_steps=1, elapsed_seconds=1, candidates=[]
    )

    assert "Next\n  Researcher post-training analysis" in card


def test_v4_replication_brief_reports_result_level_measurements(monkeypatch, tmp_path):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "campaign": {"id": "campaign", "base_commit": "base"},
                "last_verdict": "awaiting analysis",
            }
        ),
        encoding="utf-8",
    )
    results = [
        {
            "index": 1,
            "replication_of": None,
            "training_seed": 10,
            "requested_evaluations": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "checkpoint-a",
                    "metrics": {"episodes": 20, "seed": 100, "success_percent": 55.0},
                }
            ],
        },
        {
            "index": 2,
            "replication_of": 1,
            "training_seed": 11,
            "task_reference_evaluations": [
                {
                    "instrument": "task_reference",
                    "candidate": "checkpoint-b",
                    "panel": "held-out",
                    "episodes": 30,
                    "seed": 200,
                    "success_percent": 65.0,
                }
            ],
        },
        {
            "index": 3,
            "replication_of": 1,
            "training_seed": 12,
            "requested_evaluations": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "checkpoint-c",
                    "metrics": {"success_percent": 75.0},
                }
            ],
        },
        {"index": 4, "replication_of": 1, "training_seed": 13},
    ]
    for result in results:
        result["campaign_id"] = "campaign"
    (research_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(result) for result in results) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    rendered = render_research_brief()

    assert "experiment 1, seed 10, checkpoint-a, research_evaluation, 20 episodes, seed 100, success 55.00%" in rendered
    assert "experiment 2, seed 11, checkpoint-b, task_reference/held-out, 30 episodes, seed 200, success 65.00%" in rendered
    assert "experiment 3, seed 12, checkpoint-c, research_evaluation, success 75.00%" in rendered
    assert "experiment 4, seed 13, unmeasured" in rendered


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
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": "checkpoint-120832",
                "episodes": 200,
                "seed": 2000,
                "label": "checkpoint-120832",
            },
            {
                "instrument": "research_evaluation",
                "candidate": "champion",
                "episodes": 200,
                "seed": 2000,
            },
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
    assert "Scientific recipe\nkeep" in card
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


def test_v4_decision_card_keeps_working_and_best_known_distinct():
    card = render_decision_card(
        {
            "pending": {"experiment": 2},
            "decision": {"reason": "Keep exploring this checkpoint."},
            "working_name": "checkpoint-120832",
            "best_known_name": "baseline",
            "code_action": "keep",
            "request_final_benchmark": False,
            "hypothesis_assessment": (
                "The predicted behavior improved, with only one panel measured."
            ),
        }
    )

    assert "Working lineage\ncheckpoint-120832" in card
    assert "Best-known model\nbaseline" in card
    assert "Hypothesis assessment\nThe predicted behavior improved" in card


def test_evaluation_plan_is_printed_before_any_evaluation_runs(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                    "pending_scientific_parent": "test-parent",
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
    request["measurements"] = [
        {
            "instrument": "research_evaluation",
            "candidate": "checkpoint-120832",
            "episodes": 2,
            "seed": 2000,
        }
    ]
    request["paired_comparisons"] = []
    request_path.write_text(json.dumps(request), encoding="utf-8")

    checkpoint = tmp_path / "archive" / "checkpoint-120832"
    checkpoint.mkdir(parents=True)
    checkpoint.joinpath("model.zip").write_bytes(b"model")
    checkpoint.joinpath("artifact.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", tmp_path)
    monkeypatch.setattr(
        "research.runner_repository.require_resolvable_commit", lambda _: None
    )
    monkeypatch.setattr("research.runner_repository.scientific_delta", lambda _: [])
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


def test_v4_brief_exposes_authoritative_lineages_recipes_and_checkpoints(
    monkeypatch, tmp_path
):
    current_params = {
        "algorithm": {"name": "ppo"},
        "ppo": {"learning_rate": 0.0003},
    }
    working = {
        "candidate": "checkpoint-working",
        "origin_experiment": 2,
        "training_steps": 2000,
        "artifact": "research/checkpoints/working",
        "fingerprint": "working-fingerprint",
        "scientific_commit": "working-commit",
        "parameters": {
            "algorithm": {"name": "ppo"},
            "ppo": {"learning_rate": 0.0001},
        },
        "evaluation_artifacts": ["research/evaluations/working.json"],
        "reason": "Continue the current line of research.",
    }
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "working_lineage": working,
        "best_known_lineage": {
            "candidate": "checkpoint-best",
            "origin_experiment": 1,
            "training_steps": 1000,
            "artifact": "research/checkpoints/best",
            "fingerprint": "best-fingerprint",
            "scientific_commit": "best-commit",
            "parameters": current_params,
            "evaluation_artifacts": ["research/evaluations/best.json"],
            "reason": "Best measured primary outcome.",
        },
        "retained_lineages": [
            {
                "id": "alternate",
                "candidate": "checkpoint-alternate",
                "origin_experiment": 1,
                "training_steps": 800,
                "artifact": "research/checkpoints/alternate",
                "fingerprint": "alternate-fingerprint",
                "scientific_commit": "alternate-commit",
                "parameters": current_params,
                "evaluation_artifacts": ["research/evaluations/alternate.json"],
            }
        ],
        "pending_analysis": {
            "experiment": 3,
            "result": {"index": 3},
            "candidates": [
                {
                    "name": "checkpoint-current",
                    "timesteps": 3000,
                    "artifact": "models/candidates/current",
                }
            ],
        },
    }
    (tmp_path / "current_params.json").write_text(
        json.dumps(current_params), encoding="utf-8"
    )
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    section = brief.split("## Current lineages and scientific recipes", 1)[1].split(
        "## Working lineage", 1
    )[0]
    assert "Valid `training_parent` identifiers: `working`, `best_known`, `alternate`" in section
    assert "`checkpoint-current`" not in section.split(
        "### Current experiment checkpoints available for measurement", 1
    )[0]
    for expected in (
        "Candidate: checkpoint-working",
        "Origin experiment: 2",
        "Accumulated training steps: 2000",
        "Artifact: `research/checkpoints/working`",
        "Model fingerprint: working-fingerprint",
        "Scientific commit: working-commit",
        'Effective parameters: {"algorithm":{"name":"ppo"},"ppo":{"learning_rate":0.0001}}',
        "Recorded evaluation artifacts: `research/evaluations/working.json`",
        "Researcher reason: Continue the current line of research.",
        "Researcher reason: Best measured primary outcome.",
        "`alternate`",
        "`ppo.learning_rate`: lineage 0.0001; current 0.0003",
        "Parameter differences from `best_known`: none",
        "- Artifact base path: `models/candidates`",
        "1 checkpoints available for measurement; steps 3,000-3,000",
        "- Identifiers: `checkpoint-current` (3,000 steps)",
    ):
        assert expected in section
    assert section.count("Candidate: checkpoint-working") == 1
    assert section.count("Candidate: checkpoint-best") == 1
    assert "- See `working` under **Current lineages and scientific recipes**." in brief
    assert "- See `best_known` under **Current lineages and scientific recipes**." in brief
    assert brief.index("## Latest experiment") < brief.index(
        "## Current scientific direction"
    )
    assert brief.index("## Current scientific direction") < brief.index(
        "## Current lineages and scientific recipes"
    )


def test_v4_brief_renders_best_known_as_an_alias_of_identical_working_recipe(
    monkeypatch, tmp_path
):
    lineage = {
        "candidate": "checkpoint-shared",
        "origin_experiment": 2,
        "training_steps": 2000,
        "artifact": "research/checkpoints/shared",
        "fingerprint": "shared-fingerprint",
        "scientific_commit": "shared-commit",
        "parameters": {"algorithm": {"name": "ppo"}},
        "evaluation_artifacts": ["research/evaluations/shared.json"],
    }
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "working_lineage": {**lineage, "reason": "Continue training this lineage."},
        "best_known_lineage": {**lineage, "reason": "Best measured outcome."},
        "retained_lineages": [],
    }
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()
    section = brief.split("## Current lineages and scientific recipes", 1)[1].split(
        "## Working lineage", 1
    )[0]

    assert "Valid `training_parent` identifiers: `working`, `best_known`" in section
    assert "- `best_known`: alias of `working`" in section
    assert section.count("Artifact: `research/checkpoints/shared`") == 1
    assert section.count('Effective parameters: {"algorithm":{"name":"ppo"}}') == 1
    assert "Researcher reason: Continue training this lineage." in section
    assert "Researcher reason: Best measured outcome." in section


def test_v4_brief_renders_absent_lineage_facts_as_not_recorded(
    monkeypatch, tmp_path
):
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "working_lineage": {"candidate": "checkpoint-working"},
    }
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    section = brief.split("## Current lineages and scientific recipes", 1)[1].split(
        "## Working lineage", 1
    )[0]
    assert "Valid `training_parent` identifiers: `working`" in section
    assert "Origin experiment: not recorded" in section
    assert "Artifact: not recorded" in section
    assert "Model fingerprint: not recorded" in section
    assert "Scientific commit: not recorded" in section
    assert "Effective parameters: not recorded" in section
    assert "Recorded evaluation artifacts: not recorded" in section
    assert "Parameter differences from `working`: not recorded" in section
    assert "Parameter differences from `best_known`: not recorded" in section
    assert "No current experiment checkpoints are recorded." in section


def test_same_session_retries_reuse_context_while_initial_prompts_stay_grounded():
    launcher = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
    grounding = (
        "Read AGENTS.md, research/program.md, research/scenario.md, "
        "research/instruments.md, and research/brief.md."
    )

    def prompt_block(name: str) -> str:
        match = re.search(rf"\${name}\s*=\s*@\((.*?)\)\s*-join", launcher, re.DOTALL)
        assert match is not None
        return match.group(1)

    for name in ("analysisPrompt", "evaluationPrompt", "decisionPrompt", "researchPrompt"):
        assert grounding in prompt_block(name)

    retry_deliverables = {
        "analysisRetryPrompt": "research/evaluation_request.json",
        "evaluationRetryPrompt": "research/evaluation_request.json",
        "decisionRetryPrompt": "research/proposal.json",
        "retryPrompt": "research/proposal.json",
    }
    for name, deliverable in retry_deliverables.items():
        block = prompt_block(name)
        assert grounding not in block
        assert "same Researcher session context remains available" in block
        assert "failed validation:" in block
        assert "Correct only the invalid or missing" in block
        assert deliverable in block
        assert "Reread" in block
        assert "contract" in block and "state" in block


def test_retries_allow_enough_context_to_resolve_the_validation_error():
    launcher = (ROOT / "run_research.ps1").read_text(encoding="utf-8")

    for name in ("analysisRetryPrompt",):
        match = re.search(rf"\${name}\s*=\s*@\((.*?)\)\s*-join", launcher, re.DOTALL)
        assert match is not None
        block = match.group(1)
        assert "Reread relevant contract and state files as needed" in block
        assert "reuse the existing context for everything else" in block
        assert "Reread one" not in block
