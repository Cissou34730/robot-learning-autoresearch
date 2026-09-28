"""Behavioral launcher-to-Runner coverage for the schema-6 lifecycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from research import run_experiment
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_repository as repository


def _configure(monkeypatch, tmp_path: Path) -> dict:
    research = tmp_path / "research"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "SCIENTIFIC_MODEL_PATH": research / "scientific_model.md",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
        "GOAL_PATH": research / "GOAL_REACHED",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(repository, "campaign_lab_manifest", list)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "b" * 40
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    monkeypatch.setattr(
        run_experiment, "_protected_panel_overlap", lambda *_args: False
    )
    monkeypatch.setattr(
        run_experiment.protocol, "evaluation_semantics_fingerprint", lambda: "semantics"
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "research/scenario.md",
            "summary": "Reach the protected task objective.",
        },
        last_verdict="fresh campaign",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.write_state(state)
    return state


def _run(monkeypatch, *arguments: str) -> int:
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", *arguments])
    return run_experiment.main()


def _start(monkeypatch, kind: str, objective: str, backend_id: str) -> None:
    assert (
        _run(
            monkeypatch,
            "--start-session",
            kind,
            "--session-objective",
            objective,
            "--backend-session-id",
            backend_id,
            "--backend-adapter",
            "copilot",
            "--backend-model",
            "gpt-5.6-luna",
            "--backend-reasoning",
            "high",
        )
        == 0
    )


def _submit(monkeypatch, request: dict) -> dict:
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    assert _run(monkeypatch) == 0
    return repository.read_state()


def _checkpoint(state: dict, *, next_step: str) -> dict:
    session = state["scientific_session"]
    completed = list(session["operation_ids"])
    return {
        "checkpoint": {
            "human_goal_connection": "The bounded work informs the human goal.",
            "current_goal_gap": "The protected objective is not yet established.",
            "current_synthesis": "The recorded operations provide the current facts.",
            "evidence_references": completed,
            "decision_frontier": "Choose the next goal-directed transition.",
            "completed_operations": completed,
            "candidates_and_roles": "Candidate and role state remain explicit.",
            "next_direction_or_closure": next_step,
            "cumulative_resource_use": "Only mocked lightweight operations ran.",
        }
    }


def test_launcher_runner_flow_uses_peer_operations_and_no_post_training_gate(
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)

    _start(monkeypatch, "startup", "Prepare the campaign for goal review.", "backend-1")
    state = _submit(
        monkeypatch,
        _checkpoint(repository.read_state(), next_step="Review the human goal."),
    )
    assert state["scientific_session"] is None

    _start(monkeypatch, "goal_review", "Choose the obstacle to resolve.", "backend-2")
    state = _submit(
        monkeypatch,
        {
            "inquiry": {
                "action": "open",
                "question": "What blocks reliable task completion?",
                "goal_connection": "The blocking behavior prevents the human goal.",
                "closure_condition": "Measure a candidate and decide its role.",
                "rationale": "Resolving this obstacle determines the next route.",
            }
        },
    )
    assert state["active_inquiry"]["id"] == "I1"
    state = _submit(
        monkeypatch,
        _checkpoint(state, next_step="Start a bounded inquiry session."),
    )
    assert state["scientific_session"] is None

    _start(monkeypatch, "inquiry", "Resolve the active obstacle.", "backend-3")
    archived_artifact = tmp_path / "archive" / "checkpoint-10"
    archived_artifact.mkdir(parents=True)
    archived_artifact.joinpath("model.zip").write_bytes(b"model")
    archived_artifact.joinpath("artifact.json").write_text(
        '{"timesteps": 10, "completed": true}', encoding="utf-8"
    )
    archived_artifact.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
    archived = [
        {
            "name": "checkpoint-10",
            "artifact": repository.repo_relative_path(archived_artifact),
            "fingerprint": repository.artifact_fingerprint(archived_artifact),
            "timesteps": 10,
            "training_success": 0.5,
            "ep_rew_mean": 1.0,
        }
    ]
    monkeypatch.setattr(execution, "validate_active_configuration", dict)
    monkeypatch.setattr(execution, "train_candidate", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda _path: [
            {"name": "checkpoint-10", "path": archived_artifact, "timesteps": 10}
        ],
    )
    monkeypatch.setattr(
        repository, "archive_candidates", lambda *_args, **_kwargs: archived
    )
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda _path: None)
    state = _submit(
        monkeypatch,
        {
            "training": {
                "initialization": "fresh",
                "seed": 7,
                "steps": 10,
                "description": "Train the current scientific recipe.",
                "rationale": "The learning dynamics inform the inquiry.",
            }
        },
    )
    bounded_session_id = state["scientific_session"]["id"]
    assert state["scientific_session"]["operation_ids"] == ["T1"]
    assert state["pending_operation"] is None
    assert state["terminal_state"] is None
    assert state["model_roles"]["working"] is None
    assert state["model_roles"]["best_known"] is None

    candidate_id = "T1:checkpoint-10"

    def evaluate(_artifact, seed, *, episodes, output_path, **_kwargs):
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 100.0,
            "episode_results": [
                {"episode": index, "episode_seed": seed + index, "success": True}
                for index in range(episodes)
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)
    state = _submit(
        monkeypatch,
        {
            "measurement": {
                "description": "Measure the trained candidate.",
                "rationale": "The factual result decides whether to designate it.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate_id,
                        "episodes": 2,
                        "seed": 100,
                    }
                ],
            }
        },
    )
    assert state["scientific_session"]["id"] == bounded_session_id
    assert state["scientific_session"]["operation_ids"] == ["T1", "M1"]

    state = _submit(
        monkeypatch,
        {
            "model_role": {
                "action": "set_best_known",
                "candidate": candidate_id,
                "reason": "The completed measurement supports this designation.",
                "evidence": ["M1"],
            }
        },
    )
    assert state["model_roles"]["best_known"] == candidate_id
    state = _submit(
        monkeypatch,
        {
            "inquiry": {
                "action": "close",
                "outcome": "The candidate is ready for official assessment.",
                "reason": "The inquiry closure condition is met.",
            }
        },
    )
    assert state["active_inquiry"] is None
    state = _submit(
        monkeypatch,
        _checkpoint(state, next_step="Request the official assessment."),
    )
    assert state["scientific_session"] is None

    _start(monkeypatch, "goal_review", "Choose the terminal goal action.", "backend-4")
    state = _submit(
        monkeypatch,
        {
            "campaign_conclusion": {
                "action": "request_official_assessment",
                "reason": "Completed evidence supports the explicit best-known model.",
            }
        },
    )
    assert state["terminal_state"]["status"] == "official_assessment_requested"
    monkeypatch.setattr(
        run_experiment.assessment,
        "evaluate_official_model",
        lambda *_args, **_kwargs: {
            "goal_reached": True,
            "success_percent": 100.0,
            "episodes": 200,
        },
    )
    assert _run(monkeypatch, "--run-official-assessment") == 0

    final = repository.read_state()
    assert final["terminal_state"]["status"] == "official_assessment_passed"
    assert final["scientific_session"] is None
    assert final["pending_operation"] is None
    assert [event["kind"] for event in final["operation_events"]] == [
        "checkpoint",
        "inquiry",
        "checkpoint",
        "training",
        "measurement",
        "model_role",
        "inquiry",
        "checkpoint",
        "campaign_conclusion",
    ]
