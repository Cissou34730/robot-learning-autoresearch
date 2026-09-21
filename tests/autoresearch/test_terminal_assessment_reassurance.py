"""Issue #59: reassure the Researcher about the irreversible terminal assessment.

The irreversibility is deliberate and is kept. These tests pin the reassuring
surface around it: a closure that requests the benchmark must state a non-empty
terminal reason, a pending request names the frozen best-known lineage in the
brief, and the brief states that both verdicts are legitimate outcomes.
"""

import pytest

from research import build_research_brief as brief
from research import run_experiment
from research.runner_protocol import plan_previous_result_decision
from robot_learning.scenario.evaluation import (
    summarize_research_evaluations as summarize_evaluations,
)


def _artifact(path):
    path.mkdir(parents=True, exist_ok=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (path / filename).write_bytes(b"artifact")
    return path


def _decision_state(candidate_artifact, measurements):
    return {
        "accepted_artifact": "accepted",
        "accepted_training_steps": 0,
        "pending_researcher_decision": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": candidate_artifact,
                    "timesteps": 120_000,
                    "evaluations": measurements,
                    "summary": summarize_evaluations(measurements),
                }
            ],
            "champion_available": False,
            "parameters": {"algorithm": {"name": "active-method"}},
            "initialization": "fresh",
            "training_budget_steps": 120_000,
        },
    }


def _evaluation(seed: int, outcomes: list[bool]) -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "steps": 100,
                "reward_total": 1.0,
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def _decision() -> dict:
    return {
        "previous_result_decision": {
            "experiment": 8,
            "continue_from": "candidate",
            "reason": "Measured policy is the useful parent.",
            "code": {"action": "keep", "reason": "Keep the measured method."},
        }
    }


def _best_known() -> dict:
    return {
        "artifact": "research/checkpoints/retained/campaign/e1",
        "fingerprint": "abc123",
        "candidate": "checkpoint-100352",
        "origin_experiment": 1,
        "training_steps": 100_352,
        "scientific_commit": "b35bd4b",
        "evaluation_artifacts": ["research/evaluations/panel.json"],
        "reason": "Highest measured task success in the campaign.",
    }


def test_a_terminal_request_requires_a_non_empty_reason(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    state = _decision_state("archive/candidate", [_evaluation(1000, [True, True])])

    without_reason = _decision()
    without_reason["previous_result_decision"]["request_final_benchmark"] = True
    with pytest.raises(ValueError, match="terminal_reason"):
        plan_previous_result_decision(without_reason, state)

    blank = _decision()
    blank["previous_result_decision"]["request_final_benchmark"] = True
    blank["previous_result_decision"]["terminal_reason"] = "   "
    with pytest.raises(ValueError, match="terminal_reason"):
        plan_previous_result_decision(blank, state)

    stated = _decision()
    stated["previous_result_decision"]["request_final_benchmark"] = True
    stated["previous_result_decision"]["terminal_reason"] = (
        "Repeated independent success above the goal."
    )
    plan = plan_previous_result_decision(stated, state)
    assert plan["terminal_reason"] == "Repeated independent success above the goal."


def test_a_non_terminal_closure_needs_no_terminal_reason(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    state = _decision_state("archive/candidate", [_evaluation(1000, [True, True])])

    plan = plan_previous_result_decision(_decision(), state)

    assert plan["request_final_benchmark"] is False
    assert plan["terminal_reason"] is None


def test_a_final_benchmark_conclusion_records_the_terminal_reason(monkeypatch):
    announced = []
    monkeypatch.setattr(run_experiment.console, "announce", announced.append)
    monkeypatch.setattr(run_experiment.repository, "write_state", lambda state: None)
    state = {
        "best_known_lineage": _best_known(),
        "last_experiment": 8,
    }

    run_experiment.apply_campaign_conclusion(
        {
            "action": "request_final_benchmark",
            "reason": "Repeated independent success above the goal.",
        },
        state,
    )

    pending = state["pending_final_benchmark"]
    assert pending["terminal_reason"] == "Repeated independent success above the goal."
    assert pending["best_known"]["candidate"] == "checkpoint-100352"
    assert any("Repeated independent success" in message for message in announced)


def test_the_serialized_closure_plan_carries_the_terminal_reason():
    plan = {
        "pending": {"experiment": 8},
        "decision": {"reason": "Selected the measured policy."},
        "working_name": "candidate",
        "working_record": {},
        "best_known_record": {},
        "best_known_name": "candidate",
        "code_action": "keep",
        "code_reason": "Keep the measured method.",
        "code_plan": {"parent": None, "restore": None, "remove_created": []},
        "retained": [],
        "removed_retained": [],
        "artifact_publications": [],
        "request_final_benchmark": True,
        "terminal_reason": "Repeated independent success above the goal.",
        "hypothesis_assessment": None,
        "designation_counter": 1,
    }

    serialized = run_experiment._serialize_closure_plan(
        plan, pending_field="pending_researcher_decision"
    )

    assert serialized["terminal_reason"] == "Repeated independent success above the goal."


def test_the_pending_terminal_assessment_names_the_frozen_model():
    state = {
        "pending_final_benchmark": {
            "selected": "best_known",
            "terminal_reason": "Repeated independent success above the goal.",
            "best_known": _best_known(),
        }
    }

    text = "\n".join(brief._v4_terminal_assessment_section(state))

    assert "## Pending terminal assessment" in text
    assert "`best_known`" in text
    assert "checkpoint-100352" in text
    assert "Origin experiment: 1" in text
    assert "Accumulated training steps: 100352" in text
    assert "research/checkpoints/retained/campaign/e1" in text
    assert "b35bd4b" in text
    assert "research/evaluations/panel.json" in text
    assert "Repeated independent success above the goal." in text


def test_the_pending_terminal_assessment_states_both_verdicts_are_legitimate():
    state = {
        "pending_final_benchmark": {
            "selected": "best_known",
            "terminal_reason": "Repeated independent success above the goal.",
            "best_known": _best_known(),
        }
    }

    text = "\n".join(brief._v4_terminal_assessment_section(state))

    assert "goal_not_reached" in text
    assert "legitimate campaign outcomes" in text
    assert "survives the verdict intact" in text
    # The mechanism is unchanged: the brief still states the irreversibility.
    assert "irreversible" in text


def test_the_pending_terminal_assessment_is_absent_without_a_request():
    assert brief._v4_terminal_assessment_section({}) == []
    assert (
        brief._v4_terminal_assessment_section({"pending_final_benchmark": None}) == []
    )


def test_the_terminal_reason_is_documented_in_the_request_contract():
    from pathlib import Path

    instruments = (
        Path(__file__).resolve().parents[2] / "research" / "instruments.md"
    ).read_text(encoding="utf-8")
    program = (
        Path(__file__).resolve().parents[2] / "research" / "program.md"
    ).read_text(encoding="utf-8")

    assert "terminal_reason" in instruments
    # The symmetric cost of waiting and the procedural decision rule are stated.
    assert "Deferring the request" in program
    assert "no longer describe an experiment whose outcome would" in program
    assert "not designed to\ndiagnose a policy" in program
    assert "legitimate campaign outcomes" in program
