"""Trust boundary for the Runner-owned official assessment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.adapters import final_benchmark as scenario_final_benchmark
from runner import assessment, paths, protocol, repository, run_experiment

OFFICIAL_TASK_PATHS = (
    "contracts/policy_runtime.py",
    "runner/run_experiment.py",
    "runner/assessment.py",
    "robot_learning/__init__.py",
    "benchmark/__init__.py",
    "benchmark/final_benchmark.py",
    "benchmark/final_contract.py",
    "benchmark/reference_contract.py",
    "benchmark/reference_evaluation.py",
    "contracts/robots/__init__.py",
    "contracts/robots/two_joint_arm.py",
    "contracts/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "benchmark/adapters/final_benchmark.py",
    "benchmark/adapters/task_reference.py",
)

PI_OWNED_PATHS = (
    "robot_learning/training/reward.py",
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/environment.py",
    "robot_learning/scenario/evaluation.py",
    "robot_learning/scenario/viewer.py",
    "robot_learning/train.py",
    "robot_learning/evaluate.py",
    "robot_learning/training/algorithms.py",
)


def test_protected_surface_covers_the_whole_benchmark_package():
    root = Path(__file__).resolve().parents[2]
    package_files = [
        path.relative_to(root).as_posix()
        for path in (root / "benchmark").rglob("*")
        if path.is_file()
    ]

    assert package_files
    assert all(protocol.is_protected_source(path) for path in package_files)
    assert not any(protocol.is_researcher_owned(path) for path in package_files)


@pytest.mark.parametrize("protected_path", OFFICIAL_TASK_PATHS)
def test_pi_delta_cannot_change_the_official_task(protected_path):
    with pytest.raises(ValueError, match="human-owned"):
        protocol.validate_research_delta_ownership([protected_path])
    with pytest.raises(ValueError, match="human-owned"):
        protocol.validate_research_delta_ownership([protected_path.replace("/", "\\")])


@pytest.mark.parametrize("pi_path", PI_OWNED_PATHS)
def test_pi_owned_scientific_files_remain_changeable(pi_path):
    protocol.validate_research_delta_ownership([pi_path])


def test_runner_assessment_is_the_trusted_official_entry(monkeypatch, tmp_path):
    observed: dict[str, object] = {}

    def trust(adapter_path):
        observed["adapter"] = adapter_path

    def protected(model_path, algorithm=None, progress_callback=None):
        observed["model"] = model_path
        observed["algorithm"] = algorithm
        observed["progress"] = progress_callback
        return {"goal_reached": True}

    monkeypatch.setattr(
        assessment.protocol, "require_trusted_assessment_runtime", trust
    )
    monkeypatch.setattr(
        "benchmark.adapters.final_benchmark.evaluate_final_model", protected
    )
    callback = lambda _completed, _total: None

    assert assessment.evaluate_official_model(
        tmp_path / "model.zip",
        algorithm="ppo",
        progress_callback=callback,
    ) == {"goal_reached": True}
    assert observed == {
        "adapter": protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH,
        "model": tmp_path / "model.zip",
        "algorithm": "ppo",
        "progress": callback,
    }


@pytest.mark.parametrize(
    ("success_percent", "goal_reached"),
    [(97.9, False), (98.0, True)],
)
def test_protected_scenario_adapter_applies_the_official_threshold(
    monkeypatch, tmp_path, success_percent, goal_reached
):
    observed: dict[str, object] = {}
    callback = lambda _completed, _total: None

    def protected(model_path, algorithm=None, progress_callback=None):
        observed.update(
            model=model_path,
            algorithm=algorithm,
            progress_callback=progress_callback,
        )
        return {
            "episodes": 200,
            "seed": 10_000,
            "success_percent": success_percent,
        }

    monkeypatch.setattr(
        scenario_final_benchmark,
        "_protected_evaluate_final_model",
        protected,
    )

    result = scenario_final_benchmark.evaluate_final_model(
        tmp_path / "model.zip",
        algorithm="ppo",
        progress_callback=callback,
    )

    assert result["success_percent"] == success_percent
    assert result["goal_reached"] is goal_reached
    assert observed == {
        "model": tmp_path / "model.zip",
        "algorithm": "ppo",
        "progress_callback": callback,
    }


def _requested_assessment_state(monkeypatch, tmp_path):
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "STATE_PATH": tmp_path / "runner" / "state" / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": tmp_path / "pi_workspace" / "operation_request.json",
        "GOAL_PATH": tmp_path / "runner" / "state" / "GOAL_REACHED",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)

    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    for name in repository.INFERENCE_ARTIFACT_FILES:
        artifact.joinpath(name).write_bytes(name.encode())
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="ready for goal review",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    repository.start_scientific_session(
        state,
        kind="goal_review",
        objective="Decide whether to request the official assessment.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The explicitly selected model is ready.",
        }
    }
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    return candidate, artifact


@pytest.mark.parametrize(
    ("goal_reached", "expected_status"),
    [(True, "passed"), (False, "failed")],
)
def test_goal_verdict_follows_only_runner_owned_official_assessment(
    monkeypatch, tmp_path, goal_reached, expected_status
):
    candidate, artifact = _requested_assessment_state(monkeypatch, tmp_path)
    monkeypatch.setattr(
        run_experiment.assessment,
        "evaluate_official_model",
        lambda *_args, **_kwargs: {
            "goal_reached": goal_reached,
            "success_percent": 98.0 if goal_reached else 97.9,
            "episodes": 200,
        },
    )

    assert run_experiment.run_official_assessment() == 0

    persisted = json.loads(paths.STATE_PATH.read_text(encoding="utf-8"))
    assert persisted["terminal_state"]["status"] == (
        f"official_assessment_{expected_status}"
    )
    assert persisted["official_assessment"]["model"] == candidate["id"]
    assert persisted["official_assessment"]["artifact"] == candidate["artifact"]
    assert (artifact / "model.zip").is_file()
    assert paths.GOAL_PATH.exists() is goal_reached
