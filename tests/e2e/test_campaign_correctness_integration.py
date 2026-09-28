"""Schema-6 lifecycle persistence through a clean clone."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from research import run_experiment
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_repository as repository


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _start(monkeypatch, kind: str, objective: str, backend_id: str) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiment.py",
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
        ],
    )
    assert run_experiment.main() == 0


def _submit(monkeypatch, request: dict) -> dict:
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    assert run_experiment.main() == 0
    return repository.read_state()


def _checkpoint(state: dict, next_step: str) -> dict:
    completed = list(state["scientific_session"]["operation_ids"])
    return {
        "checkpoint": {
            "human_goal_connection": "The session advances the protected objective.",
            "current_goal_gap": "The objective is not yet established.",
            "current_synthesis": "The operation history contains the current facts.",
            "evidence_references": completed,
            "decision_frontier": "Choose the next goal-directed transition.",
            "completed_operations": completed,
            "candidates_and_roles": "Candidate identities and roles remain explicit.",
            "next_direction_or_closure": next_step,
            "cumulative_resource_use": "One bounded mocked session.",
        }
    }


def test_schema6_goal_flow_survives_clean_clone(monkeypatch, tmp_path):
    root = tmp_path / "repository"
    remote = tmp_path / "remote.git"
    research = root / "research"
    research.mkdir(parents=True)
    root.joinpath("README.md").write_text("fixture\n", encoding="utf-8")
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test Runner")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    base = _git(root, "rev-parse", "HEAD")
    _git(tmp_path, "init", "--bare", str(remote))
    _git(root, "remote", "add", "origin", str(remote))

    for name, value in {
        "ROOT": root,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "SCIENTIFIC_MODEL_PATH": research / "scientific_model.md",
        "EVALUATION_DIR": research / "evaluations",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *_args: base)
    monkeypatch.setattr(
        run_experiment, "_protected_panel_overlap", lambda *_args: False
    )
    monkeypatch.setattr(
        run_experiment.protocol, "evaluation_semantics_fingerprint", lambda: "semantics"
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)

    artifact = root / "research" / "checkpoints" / "candidates" / "seed"
    artifact.mkdir(parents=True)
    artifact.joinpath("model.zip").write_bytes(b"model")
    artifact.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    artifact.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T0:seed",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T0",
        "name": "seed",
        "parameters": {},
        "scientific_commit": base,
        "training_steps": 0,
        "evaluation_artifacts": [],
    }
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": base},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": base,
    }
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)

    _start(monkeypatch, "startup", "Prepare for goal review.", "backend-1")
    state = _submit(
        monkeypatch, _checkpoint(repository.read_state(), "Review the goal.")
    )
    _start(monkeypatch, "goal_review", "Open the most useful inquiry.", "backend-2")
    state = _submit(
        monkeypatch,
        {
            "inquiry": {
                "action": "open",
                "question": "Does the seed candidate satisfy the task reference?",
                "goal_connection": "The result determines whether this route is viable.",
                "closure_condition": "Measure the candidate and decide the route.",
                "rationale": "The bounded measurement can change the goal decision.",
            }
        },
    )
    state = _submit(monkeypatch, _checkpoint(state, "Measure inside the inquiry."))
    _start(monkeypatch, "inquiry", "Measure the seed candidate.", "backend-3")

    def evaluate(_artifact, seed, *, episodes, output_path, **_kwargs):
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 0.0,
            "episode_results": [
                {"episode": index, "episode_seed": seed + index, "success": False}
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
                "description": "Measure the seed candidate.",
                "rationale": "The factual result resolves the bounded question.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "episodes": 2,
                        "seed": 100,
                    }
                ],
            }
        },
    )
    state = _submit(
        monkeypatch,
        {
            "inquiry": {
                "action": "close",
                "outcome": "The seed route does not meet the objective.",
                "reason": "The bounded measurement satisfies the closure condition.",
            }
        },
    )
    state = _submit(monkeypatch, _checkpoint(state, "Return to goal review."))
    _start(monkeypatch, "goal_review", "Choose the campaign conclusion.", "backend-4")
    state = _submit(
        monkeypatch,
        {
            "campaign_conclusion": {
                "action": "no_credible_route",
                "reason": "The bounded evidence leaves no credible route.",
            }
        },
    )
    assert state["terminal_state"]["status"] == "no_credible_route"
    assert state["scientific_session"] is None
    assert state["pending_operation"] is None

    _git(root, "add", ".")
    _git(root, "commit", "-m", "persist schema-6 campaign")
    _git(root, "push", "-u", "origin", "HEAD")
    clone = tmp_path / "clone"
    _git(tmp_path, "-c", "core.longpaths=true", "clone", str(remote), str(clone))
    cloned = json.loads(
        clone.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(paths, "ROOT", clone)
    repository.validate_research_state(cloned, allow_missing_artifact=True)
    cloned_candidate = cloned["candidates"][candidate["id"]]
    cloned_artifact = clone / cloned_candidate["artifact"]
    repository.require_complete_inference_artifact(
        cloned_artifact, "cloned schema-6 candidate"
    )
    assert (
        repository.artifact_fingerprint(cloned_artifact)
        == (cloned_candidate["fingerprint"])
    )
    assert cloned["terminal_state"]["status"] == "no_credible_route"
    assert [event["kind"] for event in cloned["operation_events"]] == [
        "checkpoint",
        "inquiry",
        "checkpoint",
        "measurement",
        "inquiry",
        "checkpoint",
        "campaign_conclusion",
    ]
