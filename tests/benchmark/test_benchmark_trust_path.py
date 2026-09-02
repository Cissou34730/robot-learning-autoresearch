"""The human-owned trust path between the runner and the official benchmark.

These tests protect the objective, the official robot, the benchmark contract
and the final goal verdict. They are immutable during a research campaign and
must stay independent of any concrete learning method.
"""

import json
from pathlib import Path

import pytest

from research.run_experiment import execute_pending_final_benchmark
from research.runner_protocol import (
    PROTECTED_BENCHMARK_PATHS,
    validate_experiment_semantics,
)

OFFICIAL_TASK_PATHS = (
    "research/run_experiment.py",
    "robot_learning/__init__.py",
    "robot_learning/benchmark/__init__.py",
    "robot_learning/benchmark/final_benchmark.py",
    "robot_learning/benchmark/final_contract.py",
    "robot_learning/benchmark/reference_contract.py",
    "robot_learning/benchmark/reference_evaluation.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/final_benchmark.py",
    "robot_learning/scenario/task_reference.py",
)

RESEARCHER_OWNED_PATHS = (
    "robot_learning/scenario/reward.py",
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/environment.py",
    "robot_learning/scenario/evaluation.py",
    "robot_learning/scenario/brief.py",
    "robot_learning/scenario/viewer.py",
    "robot_learning/train.py",
    "robot_learning/evaluate.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/research_config.py",
    "research/current_params.json",
)


def test_protected_surface_covers_the_whole_goal_reached_path():
    assert PROTECTED_BENCHMARK_PATHS == set(OFFICIAL_TASK_PATHS)


def test_protected_surface_covers_every_import_routing_file_on_the_trust_path():
    from robot_learning.benchmark import final_benchmark, final_contract
    from robot_learning.robots import two_joint_arm
    from robot_learning.scenario import final_benchmark as adapter

    packages: set[str] = set()
    for module in (adapter, final_benchmark, final_contract, two_joint_arm):
        parts = module.__name__.split(".")[:-1]
        for depth in range(1, len(parts) + 1):
            packages.add(".".join(parts[:depth]))

    assert packages == {
        "robot_learning",
        "robot_learning.benchmark",
        "robot_learning.robots",
        "robot_learning.scenario",
    }
    for package in packages:
        init_path = f"{package.replace('.', '/')}/__init__.py"
        assert init_path in PROTECTED_BENCHMARK_PATHS, init_path


@pytest.mark.parametrize("protected_path", OFFICIAL_TASK_PATHS)
def test_research_proposal_cannot_change_the_official_task(protected_path):
    with pytest.raises(ValueError, match="human-owned task, context"):
        validate_experiment_semantics(
            {}, "training", "transfer", None, [protected_path], False
        )


@pytest.mark.parametrize("protected_path", OFFICIAL_TASK_PATHS)
def test_official_task_protection_ignores_path_separator(protected_path):
    with pytest.raises(ValueError, match="human-owned task, context"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            None,
            [protected_path.replace("/", "\\")],
            False,
        )


@pytest.mark.parametrize("research_path", RESEARCHER_OWNED_PATHS)
def test_researcher_owned_files_remain_changeable(research_path):
    validate_experiment_semantics(
        {}, "training", "transfer", None, [research_path], False
    )


def test_scenario_adapter_cannot_bypass_the_protected_benchmark():
    from robot_learning.benchmark import final_benchmark as protected
    from robot_learning.scenario import final_benchmark as adapter

    assert adapter._protected_evaluate_final_model is protected.evaluate_final_model
    assert adapter.FINAL_SUCCESS_PERCENT == 98.0


def test_protected_task_files_exist_at_their_protected_paths():
    root = Path(__file__).resolve().parent.parent.parent

    for protected_path in OFFICIAL_TASK_PATHS:
        assert (root / protected_path).is_file(), protected_path


def test_researcher_cannot_change_the_enforcement_mechanism():
    with pytest.raises(ValueError, match="human-owned task, context"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            {"training": {"n_envs": 2}},
            ["robot_learning/scenario/reward.py", "research/run_experiment.py"],
            False,
        )


def _pending_final_benchmark_state(monkeypatch, tmp_path):
    from research.runner_repository import artifact_fingerprint

    accepted = tmp_path / "accepted"
    accepted.mkdir()
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (accepted / filename).write_bytes(b"artifact")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "accepted_metrics": None,
                "official_metrics": None,
                "pending_final_benchmark": {
                    "experiment": 9,
                    "selected": "candidate",
                    "artifact": "accepted",
                    "fingerprint": artifact_fingerprint(accepted),
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    return state_path


@pytest.mark.parametrize(
    ("official_success_percent", "goal_reached"), [(98.0, True), (97.9, False)]
)
def test_goal_reached_follows_only_the_protected_benchmark(
    monkeypatch, tmp_path, official_success_percent, goal_reached
):
    state_path = _pending_final_benchmark_state(monkeypatch, tmp_path)

    def protected_benchmark(model_path, algorithm=None, progress_callback=None):
        del model_path, algorithm, progress_callback
        return {
            "schema_version": 1,
            "episodes": 200,
            "seed": 1000,
            "success_percent": official_success_percent,
        }

    # Only the protected evaluator is stubbed: the real adapter derives the verdict.
    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark._protected_evaluate_final_model",
        protected_benchmark,
    )

    assert execute_pending_final_benchmark() == 0

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["official_metrics"]["goal_reached"] is goal_reached
    assert (tmp_path / "GOAL_REACHED").exists() is goal_reached
