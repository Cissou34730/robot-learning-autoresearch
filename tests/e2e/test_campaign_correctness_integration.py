"""Schema-6 lifecycle persistence through a clean clone."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _append_marker(root: Path, relative: str, marker: str) -> None:
    path = root / relative
    path.write_text(
        path.read_text(encoding="utf-8") + f"\n# E2E_RECIPE_MARKER={marker}\n",
        encoding="utf-8",
    )


def _write_campaign_debris(root: Path, marker: str) -> None:
    debris = {
        "research/research_state.json": json.dumps(
            {"schema_version": 5, "campaign": marker}
        ),
        "research/results.jsonl": json.dumps({"legacy": marker}) + "\n",
        "research/EXPERIMENTS.md": f"# {marker} history\n",
        "research/scientific_model.md": f"# {marker} scientific model\n",
        "research/postmortems.md": f"# {marker} postmortem\n",
        "research/brief.md": f"# {marker} brief\n",
        "research/operation_request.json": '{"training":{}}\n',
        "research/GOAL_REACHED": f"{marker} goal marker\n",
        "research/RECOVERY_PENDING": f"{marker} recovery marker\n",
        "research/RESTART_PENDING": f"{marker} restart marker\n",
        "research/BASELINE_PENDING": f"{marker} baseline marker\n",
        "research/evaluations/old/evidence.json": json.dumps({"marker": marker}),
        "research/checkpoints/candidates/old/model.zip": f"{marker} model",
        "research/checkpoints/candidates/old/artifact.json": "{}",
        "research/checkpoints/candidates/old/policy_runtime.pkl": f"{marker} runtime",
        "models/candidates/old/model.zip": f"{marker} disposable model",
        "research/lab/old_diagnostic.py": f"MARKER = {marker!r}\n",
    }
    for relative, content in debris.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _assert_fresh_recipe_reset(root: Path, source: str, old_campaign_id: str) -> str:
    state = json.loads(
        root.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    assert state["schema_version"] == 6
    assert state["campaign"]["id"] != old_campaign_id
    assert state["campaign"]["recipe_source_commit"] == source
    assert state["counters"] == {
        "inquiry": 0,
        "session": 0,
        "measurement": 0,
        "training": 0,
        "event": 0,
    }
    assert state["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }
    for field in (
        "active_inquiry",
        "pi_checkpoint",
        "scientific_session",
        "pending_operation",
        "terminal_state",
        "official_assessment",
    ):
        assert state[field] is None
    assert state["operation_events"] == []
    assert state["candidates"] == {}
    assert state["scientific_model"] == {
        "status": "pending",
        "path": "research/scientific_model.md",
        "commit": None,
    }
    assert root.joinpath("research/results.jsonl").read_text(encoding="utf-8") == ""
    assert root.joinpath("research/EXPERIMENTS.md").read_text(encoding="utf-8") == (
        "# Campaign operation log\n\n"
        "| Operation | Kind | Inquiry | Result |\n"
        "|---|---|---|---|\n"
    )
    for relative in (
        "research/scientific_model.md",
        "research/postmortems.md",
        "research/brief.md",
        "research/operation_request.json",
        "research/GOAL_REACHED",
        "research/RECOVERY_PENDING",
        "research/RESTART_PENDING",
        "research/BASELINE_PENDING",
        "research/evaluations",
        "research/checkpoints",
        "models/candidates",
        "research/lab",
    ):
        assert not root.joinpath(relative).exists()
    return state["campaign"]["id"]


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


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_fresh_recipe_ref_restores_only_the_schema6_scientific_recipe(tmp_path):
    root = tmp_path / "repository"
    remote = tmp_path / "remote.git"
    clone = tmp_path / "clean-clone"
    subprocess.run(
        ["git", "clone", "--no-local", str(ROOT), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(root, "config", "user.name", "Test Runner")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "remote", "remove", "origin")
    _git(tmp_path, "init", "--bare", str(remote))
    _git(root, "remote", "add", "origin", str(remote))

    recipe_paths = (
        "robot_learning/scenario/reward.py",
        "robot_learning/scenario/observations.py",
        "robot_learning/training/algorithms.py",
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
    )
    for relative in recipe_paths:
        _append_marker(root, relative, "source")
    params_path = root / "research" / "current_params.json"
    source_params = json.loads(params_path.read_text(encoding="utf-8"))
    source_params["ppo"]["gamma"] = 0.98
    params_path.write_text(json.dumps(source_params, indent=2) + "\n", encoding="utf-8")
    source_only = root / "robot_learning" / "scenario" / "source_only.py"
    source_only.write_text("RECIPE_SOURCE_ONLY = True\n", encoding="utf-8")
    _append_marker(root, "run_research.ps1", "protected-source")
    protected_test = root / "tests" / "e2e_recipe_reset_marker.txt"
    protected_test.write_text("protected source\n", encoding="utf-8")
    _write_campaign_debris(root, "source")
    _git(root, "add", "-A")
    _git(root, "add", "-f", "models/candidates/old/model.zip")
    _git(root, "commit", "-m", "schema-6 reset source fixture")
    source = _git(root, "rev-parse", "HEAD")

    for relative in recipe_paths:
        _append_marker(root, relative, "later")
    later_params = json.loads(params_path.read_text(encoding="utf-8"))
    later_params["ppo"]["gamma"] = 0.97
    params_path.write_text(json.dumps(later_params, indent=2) + "\n", encoding="utf-8")
    source_only.unlink()
    later_only = root / "robot_learning" / "scenario" / "later_only.py"
    later_only.write_text("RECIPE_LATER_ONLY = True\n", encoding="utf-8")
    _append_marker(root, "run_research.ps1", "protected-current")
    protected_test.write_text("protected current\n", encoding="utf-8")
    _write_campaign_debris(root, "current")
    old_campaign_id = "22222222-2222-2222-2222-222222222222"
    root.joinpath("research/research_state.json").write_text(
        json.dumps({"schema_version": 5, "campaign": {"id": old_campaign_id}}),
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "add", "-f", "models/candidates/old/model.zip")
    _git(root, "commit", "-m", "later science and current protected surface")
    branch = _git(root, "branch", "--show-current")
    _git(root, "push", "-u", "origin", f"HEAD:{branch}")
    _git(remote, "symbolic-ref", "HEAD", f"refs/heads/{branch}")

    reset = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / "reset_research.ps1"),
            "-Mode",
            "Fresh",
            "-RecipeRef",
            source,
            "-Force",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert reset.returncode == 0, reset.stderr

    new_campaign_id = _assert_fresh_recipe_reset(root, source, old_campaign_id)
    for relative in recipe_paths:
        text = root.joinpath(relative).read_text(encoding="utf-8")
        assert "E2E_RECIPE_MARKER=source" in text
        assert "E2E_RECIPE_MARKER=later" not in text
    restored_params = json.loads(params_path.read_text(encoding="utf-8"))
    assert restored_params["ppo"]["gamma"] == 0.98
    assert source_only.read_text(encoding="utf-8") == "RECIPE_SOURCE_ONLY = True\n"
    assert not later_only.exists()
    assert "E2E_RECIPE_MARKER=protected-current" in root.joinpath(
        "run_research.ps1"
    ).read_text(encoding="utf-8")
    assert protected_test.read_text(encoding="utf-8") == "protected current\n"
    assert _git(root, "status", "--porcelain") == ""

    _git(tmp_path, "-c", "core.longpaths=true", "clone", str(remote), str(clone))
    assert _assert_fresh_recipe_reset(clone, source, old_campaign_id) == new_campaign_id
    assert (
        json.loads(
            clone.joinpath("research/current_params.json").read_text(encoding="utf-8")
        )["ppo"]["gamma"]
        == 0.98
    )
    assert clone.joinpath("robot_learning/scenario/source_only.py").is_file()
    assert not clone.joinpath("robot_learning/scenario/later_only.py").exists()
    assert "E2E_RECIPE_MARKER=protected-current" in clone.joinpath(
        "run_research.ps1"
    ).read_text(encoding="utf-8")
    assert (
        clone.joinpath("tests/e2e_recipe_reset_marker.txt").read_text(encoding="utf-8")
        == "protected current\n"
    )
    assert _git(clone, "status", "--porcelain") == ""
