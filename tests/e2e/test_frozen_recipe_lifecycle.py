"""End-to-end tests of the frozen training operation over a real repository.

These tests build a throwaway Git repository, restore a frozen scientific
recipe from it, and drive a complete training operation with a stubbed trainer.
They are slow because they spawn real Git processes and let the runner execute
its own validation suites, so they live outside the campaign-time test domains.
"""

import json
import subprocess
from argparse import Namespace

import pytest

from research import runner_execution as execution
from research import runner_repository as repository


def _training_proposal() -> dict:
    return {
        "kind": "training",
        "family": "observation.representation",
        "hypothesis": "the current representation limits learning",
        "reasoning": {
            "evidence": [
                {"source": "evidence.txt", "observation": "Learning plateaus."}
            ],
            "alternative": "Insufficient training.",
            "expected_observation": "Progress resumes.",
            "contradicting_observation": "The plateau persists.",
            "initialization_reason": "Test the representation from initialization.",
            "strategy_link": "Determine whether representation limits progress.",
        },
        "change": "change the observation representation",
        "initialization": "fresh",
        "params": {"ppo": {"gamma": 0.99}},
    }


def _configure_recipe_repository(monkeypatch, tmp_path):
    research = tmp_path / "research"
    scenario = tmp_path / "robot_learning" / "scenario"
    training = tmp_path / "robot_learning" / "training"
    scenario_tests = tmp_path / "tests" / "scenario"
    for directory in (research, scenario, training, scenario_tests):
        directory.mkdir(parents=True, exist_ok=True)
    config_path = research / "current_params.json"
    scenario.joinpath("reward.py").write_text("RECIPE = 'A'\n", encoding="utf-8")
    training.joinpath("recipe_a.py").write_text("RECIPE = 'A'\n", encoding="utf-8")
    scenario_tests.joinpath("test_reward.py").write_text(
        "EXPECTED = 'A'\n", encoding="utf-8"
    )
    config_path.write_text(json.dumps({"recipe": "A"}), encoding="utf-8")
    tmp_path.joinpath("AGENTS.md").write_text("harness A\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "recipe A"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    recipe_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    scenario.joinpath("reward.py").write_text("RECIPE = 'B'\n", encoding="utf-8")
    training.joinpath("recipe_a.py").unlink()
    training.joinpath("recipe_b.py").write_text("RECIPE = 'B'\n", encoding="utf-8")
    scenario_tests.joinpath("test_reward.py").write_text(
        "EXPECTED = 'B'\n", encoding="utf-8"
    )
    config_path.write_text(json.dumps({"recipe": "B"}), encoding="utf-8")
    tmp_path.joinpath("AGENTS.md").write_text("harness B\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "recipe B"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    recipe_b = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    artifact = research / "checkpoints" / "retained" / "campaign" / "parent"
    artifact.mkdir(parents=True)
    artifact.joinpath("model.zip").write_bytes(b"parent model")
    artifact.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    artifact.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
    lineage = {
        "artifact": artifact.relative_to(tmp_path).as_posix(),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_experiment": 1,
        "candidate": "checkpoint-100352",
        "parameters": {"recipe": "A"},
        "scientific_commit": recipe_a,
        "training_steps": 100_352,
        "evaluation_artifacts": [],
        "reason": "Preserve recipe A.",
    }
    state_path = research / "research_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 4,
                "campaign": {
                    "id": "campaign",
                    "started_at": "now",
                    "base_commit": recipe_a,
                },
                "working_lineage": lineage,
                "best_known_lineage": None,
                "retained_lineages": [],
                "pending_scientific_parent": recipe_b,
            }
        ),
        encoding="utf-8",
    )
    path_values = {
        "research.runner_paths.ROOT": tmp_path,
        "research.runner_paths.RESEARCH_DIR": research,
        "research.runner_paths.STATE_PATH": state_path,
        "research.runner_paths.RESULTS_PATH": research / "results.jsonl",
        "research.runner_paths.LOG_PATH": research / "EXPERIMENTS.md",
        "research.runner_paths.POSTMORTEM_PATH": research / "postmortems.md",
        "research.runner_paths.PROPOSAL_PATH": research / "proposal.json",
        "research.runner_paths.CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "research.runner_paths.TRAINING_LOG_DIR": research / "training_logs",
        "research.runner_paths.RESTART_PENDING_PATH": research / "RESTART_PENDING",
        "research.runner_paths.RECOVERY_PENDING_PATH": research / "RECOVERY_PENDING",
        "robot_learning.training.research_config.CONFIG_PATH": config_path,
    }
    for target, value in path_values.items():
        monkeypatch.setattr(target, value)
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)
    return recipe_a, recipe_b, artifact, state_path


def test_continuation_restores_and_recovers_frozen_parent_recipe(monkeypatch, tmp_path):
    from research import run_experiment

    recipe_a, recipe_b, artifact, state_path = _configure_recipe_repository(
        monkeypatch, tmp_path
    )
    proposal = {
        "kind": "continuation",
        "family": "training.duration",
        "hypothesis": "The established recipe benefits from more training.",
        "reasoning": _training_proposal()["reasoning"],
        "initialization": "transfer",
        "training_parent": "working",
    }
    validation_calls = 0
    train_calls = []
    published_scopes = []

    def validate_restored_recipe():
        nonlocal validation_calls
        validation_calls += 1
        assert tmp_path.joinpath("robot_learning/scenario/reward.py").read_text() == (
            "RECIPE = 'A'\n"
        )
        assert tmp_path.joinpath("robot_learning/training/recipe_a.py").is_file()
        assert not tmp_path.joinpath("robot_learning/training/recipe_b.py").exists()
        assert tmp_path.joinpath("tests/scenario/test_reward.py").read_text() == (
            "EXPECTED = 'A'\n"
        )
        assert json.loads(
            tmp_path.joinpath("research/current_params.json").read_text()
        ) == {"recipe": "A"}
        assert tmp_path.joinpath("AGENTS.md").read_text() == "harness B\n"
        if validation_calls == 1:
            raise KeyboardInterrupt
        return {"recipe": "A"}

    def publish_recipe(experiment, scope):
        assert experiment == 1
        published_scopes.append(set(scope))
        return recipe_a

    def train_candidate(output_dir, timesteps, seed, resume, training_log, **kwargs):
        del seed, training_log, kwargs
        train_calls.append((timesteps, resume))
        assert resume == artifact / "model.zip"
        final = output_dir / "final_checkpoint"
        final.mkdir(parents=True)
        final.joinpath("model.zip").write_bytes(b"continued")
        final.joinpath("artifact.json").write_text(
            json.dumps({"timesteps": timesteps}), encoding="utf-8"
        )
        final.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
        return 0.0

    monkeypatch.setattr(
        execution, "validate_active_configuration", validate_restored_recipe
    )
    monkeypatch.setattr(repository, "publish_scientific_recipe", publish_recipe)
    monkeypatch.setattr(execution, "train_candidate", train_candidate)
    args = Namespace(timesteps=10, reuse_candidate=None)

    assert run_experiment.run_training_experiment(proposal, args) == 130
    interrupted = json.loads(state_path.read_text(encoding="utf-8"))
    frozen = interrupted["pending_training_operation"]["parent"]
    assert frozen["artifact"] == artifact.relative_to(tmp_path).as_posix()
    assert frozen["scientific_commit"] == recipe_a
    assert frozen["parameters"] == {"recipe": "A"}
    assert interrupted["pending_training_operation"]["code_parent_commit"] == recipe_b
    assert train_calls == []

    replacement = tmp_path / "research" / "checkpoints" / "retained" / "replacement"
    replacement.mkdir()
    replacement.joinpath("model.zip").write_bytes(b"replacement")
    replacement.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    replacement.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
    interrupted["working_lineage"]["artifact"] = replacement.relative_to(
        tmp_path
    ).as_posix()
    interrupted["working_lineage"]["fingerprint"] = repository.artifact_fingerprint(
        replacement
    )
    state_path.write_text(json.dumps(interrupted), encoding="utf-8")

    assert run_experiment.run_training_experiment(proposal, args) == 0
    assert train_calls == [(10, artifact / "model.zip")]
    assert published_scopes == [
        {
            "research/current_params.json",
            "robot_learning/scenario/reward.py",
            "robot_learning/training/recipe_a.py",
            "robot_learning/training/recipe_b.py",
            "tests/scenario/test_reward.py",
        }
    ]
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_training_operation"] is None
    assert persisted["pending_analysis"]["parameters"] == {"recipe": "A"}
    assert persisted["pending_analysis"]["parent_training_steps"] == 100_352
    assert persisted["pending_analysis"]["training_parent_lineage"] == frozen
    assert persisted["pending_analysis"]["result"]["training_parent_lineage"] == frozen


def test_transfer_intervention_keeps_current_recipe(monkeypatch, tmp_path):
    from research import run_experiment

    _, recipe_b, artifact, state_path = _configure_recipe_repository(
        monkeypatch, tmp_path
    )
    reward = tmp_path / "robot_learning" / "scenario" / "reward.py"
    reward.write_text("RECIPE = 'B intervention'\n", encoding="utf-8")
    proposal = {
        "kind": "training",
        "family": "reward.intervention",
        "hypothesis": "The current reward intervention improves learning.",
        "reasoning": _training_proposal()["reasoning"],
        "change": "Keep the current reward intervention.",
        "initialization": "transfer",
        "training_parent": "working",
    }

    def validate_current_recipe():
        assert reward.read_text() == "RECIPE = 'B intervention'\n"
        assert json.loads(
            tmp_path.joinpath("research/current_params.json").read_text()
        ) == {"recipe": "B"}
        return {"recipe": "B"}

    def stop_at_training(output_dir, timesteps, seed, resume, training_log, **kwargs):
        del output_dir, timesteps, seed, training_log, kwargs
        assert resume == artifact / "model.zip"
        assert reward.read_text() == "RECIPE = 'B intervention'\n"
        raise KeyboardInterrupt

    monkeypatch.setattr(execution, "validate_changed_sources", lambda paths: None)
    monkeypatch.setattr(execution, "run_validation_suites", lambda paths: None)
    monkeypatch.setattr(
        execution, "validate_active_configuration", validate_current_recipe
    )
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *args: recipe_b)
    monkeypatch.setattr(execution, "train_candidate", stop_at_training)

    assert (
        run_experiment.run_training_experiment(
            proposal, Namespace(timesteps=10, reuse_candidate=None)
        )
        == 130
    )
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_training_operation"]["recipe_restore"] is None
    assert reward.read_text() == "RECIPE = 'B intervention'\n"


def test_continuation_restoration_failure_keeps_frozen_operation(monkeypatch, tmp_path):
    from research import run_experiment

    recipe_a, _, artifact, state_path = _configure_recipe_repository(
        monkeypatch, tmp_path
    )
    proposal = {
        "kind": "continuation",
        "family": "training.duration",
        "hypothesis": "The established recipe benefits from more training.",
        "reasoning": _training_proposal()["reasoning"],
        "initialization": "transfer",
        "training_parent": "working",
    }
    original_apply = repository.apply_code_lineage_decision
    failed = False

    def fail_after_restore(plan):
        nonlocal failed
        original_apply(plan)
        if not failed:
            failed = True
            raise OSError("injected restoration failure")

    monkeypatch.setattr(repository, "apply_code_lineage_decision", fail_after_restore)
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *args, **kwargs: pytest.fail("training started before recovery"),
    )
    args = Namespace(timesteps=10, reuse_candidate=None)

    assert run_experiment.run_training_experiment(proposal, args) == 1
    interrupted = json.loads(state_path.read_text(encoding="utf-8"))
    operation = interrupted["pending_training_operation"]
    assert operation["progress"] == "parent_frozen"
    assert operation["parent"]["artifact"] == artifact.relative_to(tmp_path).as_posix()
    assert operation["parent"]["scientific_commit"] == recipe_a
    assert "injected restoration failure" in operation["last_error"]

    monkeypatch.setattr(repository, "apply_code_lineage_decision", original_apply)
    monkeypatch.setattr(
        execution,
        "validate_active_configuration",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    assert run_experiment.run_training_experiment(proposal, args) == 130
    recovered = json.loads(state_path.read_text(encoding="utf-8"))
    assert recovered["pending_training_operation"]["progress"] == "recipe_restored"
    assert recovered["pending_training_operation"]["parent"] == operation["parent"]


@pytest.mark.parametrize(
    ("crashed_completed", "expected_training_steps"),
    [(True, [10]), (False, [10, 6])],
)
def test_continuation_recovers_candidate_after_process_crash(
    monkeypatch, tmp_path, crashed_completed, expected_training_steps
):
    from research import run_experiment

    recipe_a, _, artifact, state_path = _configure_recipe_repository(
        monkeypatch, tmp_path
    )
    proposal = {
        "kind": "continuation",
        "family": "training.duration",
        "hypothesis": "The established recipe benefits from more training.",
        "reasoning": _training_proposal()["reasoning"],
        "initialization": "transfer",
        "training_parent": "working",
    }
    train_calls = []

    def write_complete_candidate(
        output_dir, timesteps, seed, resume, training_log, **kwargs
    ):
        del training_log, kwargs
        train_calls.append(timesteps)
        first_attempt = len(train_calls) == 1
        completed = crashed_completed if first_attempt else True
        completed_steps = 10 if completed else 4
        metadata = {
            "seed": seed,
            "timesteps": completed_steps,
            "requested_timesteps": 10,
            "effective_config": {"recipe": "A"},
            "resumed_from": str(resume),
            "completed": completed,
        }
        for destination in (output_dir, output_dir / "final_checkpoint"):
            destination.mkdir(parents=True, exist_ok=True)
            destination.joinpath("model.zip").write_bytes(b"continued")
            destination.joinpath("artifact.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
            destination.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
        return 0.0

    monkeypatch.setattr(
        execution, "validate_active_configuration", lambda: {"recipe": "A"}
    )
    monkeypatch.setattr(execution, "effective_config", lambda config: config)
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *args: recipe_a)
    monkeypatch.setattr(execution, "train_candidate", write_complete_candidate)
    original_write = repository.write_state
    crashed = False

    def crash_before_completion_write(value):
        nonlocal crashed
        operation = value.get("pending_training_operation")
        if (
            isinstance(operation, dict)
            and operation.get("progress") == "training_completed"
            and not crashed
        ):
            crashed = True
            raise SystemExit("simulated process death")
        original_write(value)

    monkeypatch.setattr(repository, "write_state", crash_before_completion_write)
    original_remove = execution.remove_candidate_dir
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda path: None)
    args = Namespace(timesteps=10, reuse_candidate=None)

    with pytest.raises(SystemExit, match="process death"):
        run_experiment.run_training_experiment(proposal, args)

    crashed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        crashed_state["pending_training_operation"]["progress"] == "training_dispatched"
    )
    candidate = tmp_path / "models" / "candidates" / "campaign" / "experiment-1"
    assert candidate.joinpath("final_checkpoint/model.zip").is_file()

    monkeypatch.setattr(repository, "write_state", original_write)
    monkeypatch.setattr(execution, "remove_candidate_dir", original_remove)
    assert run_experiment.run_training_experiment(proposal, args) == 0
    assert train_calls == expected_training_steps
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_training_operation"] is None
    assert persisted["pending_analysis"]["training_parent_lineage"]["artifact"] == (
        artifact.relative_to(tmp_path).as_posix()
    )
