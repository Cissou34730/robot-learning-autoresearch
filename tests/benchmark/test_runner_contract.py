import json
from pathlib import Path

import pytest

from research.run_experiment import (
    PROTECTED_BENCHMARK_PATHS,
    append_result,
    assert_research_surface,
    candidate_directories,
    commit_and_push,
    execute_pending_final_benchmark,
    format_duration,
    latest_training_steps,
    load_state,
    main,
    validate_experiment_semantics,
    validate_reusable_candidate,
)
from robot_learning.evaluate import write_progress

OFFICIAL_TASK_PATHS = (
    "research/run_experiment.py",
    "robot_learning/__init__.py",
    "robot_learning/benchmark/__init__.py",
    "robot_learning/benchmark/final_benchmark.py",
    "robot_learning/benchmark/final_contract.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/final_benchmark.py",
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
    "research/build_research_brief.py",
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
    with pytest.raises(ValueError, match="human-owned final benchmark"):
        validate_experiment_semantics(
            {}, "training", "transfer", None, [protected_path], False
        )


@pytest.mark.parametrize("protected_path", OFFICIAL_TASK_PATHS)
def test_official_task_protection_ignores_path_separator(protected_path):
    with pytest.raises(ValueError, match="human-owned final benchmark"):
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
    with pytest.raises(ValueError, match="human-owned final benchmark"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            {"ppo": {"n_steps": 2048}},
            ["robot_learning/scenario/reward.py", "research/run_experiment.py"],
            False,
        )


def _pending_final_benchmark_state(monkeypatch, tmp_path):
    from research.run_experiment import artifact_fingerprint

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
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")
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


def test_research_surface_has_no_file_whitelist(monkeypatch):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda paths: (
            [
                "robot_learning/benchmark/spec.py",
                "robot_learning/evaluate.py",
                "research/run_experiment.py",
            ]
            if paths
            else []
        ),
    )

    assert assert_research_surface() == [
        "robot_learning/benchmark/spec.py",
        "robot_learning/evaluate.py",
        "research/run_experiment.py",
    ]


def test_direct_parameter_file_edit_is_a_research_change(monkeypatch):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda paths: ["research/current_params.json"] if paths else [],
    )

    assert assert_research_surface() == ["research/current_params.json"]


def test_training_progress_reads_latest_complete_snapshot(tmp_path):
    log = tmp_path / "train.log"
    log.write_text(
        "|    total_timesteps      | 1024        |\n"
        "|    total_timesteps      | 2048        |\n",
        encoding="utf-8",
    )
    assert latest_training_steps(log) == 2048


def test_duration_is_compact_and_human_readable():
    assert format_duration(15) == "15s"
    assert format_duration(125) == "2m05s"
    assert format_duration(3720) == "1h02m"


def test_evaluation_progress_is_best_effort(monkeypatch, tmp_path):
    progress = tmp_path / "evaluation.progress"
    assert write_progress(progress, 80, 200)
    assert json.loads(progress.read_text(encoding="utf-8")) == {
        "completed": 80,
        "total": 200,
    }

    def deny_write(path, *args, **kwargs):
        del path, args, kwargs
        raise PermissionError("simulated Windows reader lock")

    monkeypatch.setattr(Path, "write_text", deny_write)
    assert not write_progress(progress, 81, 200)


def test_automatic_commit_is_immediately_pushed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "research.run_experiment.git",
        lambda *args: calls.append(args) or "",
    )

    commit_and_push("record result")

    assert calls == [
        ("commit", "-m", "record result"),
        ("push", "origin", "HEAD"),
    ]


def test_fresh_baseline_can_start_without_an_accepted_artifact(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "missing-checkpoint",
                "accepted_metrics": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)

    state = load_state(allow_unmeasured=True, allow_missing_artifact=True)
    assert state["accepted_metrics"] is None
    with pytest.raises(RuntimeError, match="accepted artifact is incomplete"):
        load_state(allow_unmeasured=True)


def test_experiment_rows_remain_one_line(monkeypatch, tmp_path):
    log_path = tmp_path / "EXPERIMENTS.md"
    results_path = tmp_path / "results.jsonl"
    log_path.write_text("header\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.LOG_PATH", log_path)
    monkeypatch.setattr("research.run_experiment.RESULTS_PATH", results_path)

    append_result(
        {
            "index": 1,
            "change": "line one\nline two",
            "hypothesis": "safe | table",
            "verdict": "error:\ntraceback",
        }
    )

    assert log_path.read_text(encoding="utf-8").count("\n") == 2
    assert "line one line two" in log_path.read_text(encoding="utf-8")
    assert "safe / table" in log_path.read_text(encoding="utf-8")


def test_reusable_candidate_must_match_experiment(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "model.zip").touch()
    (candidate / "vecnormalize.pkl").touch()
    (candidate / "artifact.json").write_text(
        '{"algorithm":"ppo","seed":0,"timesteps":1000,'
        '"n_envs":1,"parameters":{"n_steps":1024},"policy":{},'
        '"resumed_from":null}',
        encoding="utf-8",
    )
    config = {
        "algorithm": {"name": "ppo"},
        "training": {"n_envs": 1},
        "ppo": {"n_steps": 1024},
        "policy": {},
    }

    with pytest.raises(ValueError, match="timesteps"):
        validate_reusable_candidate(
            candidate,
            timesteps=120_000,
            seed=0,
            resume=None,
            config=config,
        )


def test_interrupted_candidate_can_resume_its_remaining_budget(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for filename in ("model.zip", "vecnormalize.pkl"):
        (candidate / filename).touch()
    (candidate / "artifact.json").write_text(
        '{"algorithm":"ppo","seed":0,"timesteps":50000,'
        '"requested_timesteps":120000,"completed":false,'
        '"n_envs":1,"parameters":{"n_steps":1024},"policy":{},'
        '"resumed_from":"a prior recovery checkpoint"}',
        encoding="utf-8",
    )
    config = {
        "algorithm": {"name": "ppo"},
        "training": {"n_envs": 1},
        "ppo": {"n_steps": 1024},
        "policy": {},
    }

    validate_reusable_candidate(
        candidate,
        timesteps=120_000,
        seed=0,
        resume=None,
        config=config,
    )


def test_candidate_manifest_exposes_all_complete_artifacts(tmp_path):
    finalists = []
    for number in range(3):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "candidate_manifest.json").write_text(
        json.dumps({"candidates": finalists}), encoding="utf-8"
    )

    assert candidate_directories(tmp_path) == [
        tmp_path / item["path"] for item in finalists
    ]


def test_candidate_manifest_is_not_limited_to_three_artifacts(tmp_path):
    finalists = []
    for number in range(5):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "candidate_manifest.json").write_text(
        json.dumps({"candidates": finalists}), encoding="utf-8"
    )

    assert len(candidate_directories(tmp_path)) == 5


def test_lineage_resolution_finishes_before_next_experiment_training(
    monkeypatch, tmp_path
):
    candidate = tmp_path / "archive" / "candidate"
    candidate.mkdir(parents=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (candidate / filename).write_bytes(b"artifact")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "accepted_metrics": None,
                "pending_researcher_decision": {
                    "experiment": 3,
                    "candidates": [
                        {
                            "name": "candidate",
                            "artifact": "archive/candidate",
                            "timesteps": 10,
                            "evaluations": [],
                            "summary": None,
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "fresh",
                    "training_budget_steps": 10,
                },
            }
        ),
        encoding="utf-8",
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps(
            {
                "previous_result_decision": {
                    "experiment": 3,
                    "continue_from": "candidate",
                    "reason": "Selected measured lineage.",
                    "code": {"action": "keep", "reason": "Keep this parent."},
                    "request_final_benchmark": True,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")
    committed = []

    def record_lineage_commit(*args):
        committed.append(args)

    monkeypatch.setattr(
        "research.run_experiment.commit_lineage_decision", record_lineage_commit
    )

    def fail_if_training_starts(*args, **kwargs):
        del args, kwargs
        pytest.fail("next experiment trained too early")

    monkeypatch.setattr(
        "research.run_experiment.train_candidate",
        fail_if_training_starts,
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    assert main() == 0
    assert not proposal_path.exists()
    resolved = json.loads(state_path.read_text(encoding="utf-8"))
    assert committed == [(3, "candidate")]
    assert resolved["pending_researcher_decision"] is None
    assert resolved["pending_final_benchmark"]["selected"] == "candidate"

    def evaluate_after_commit(model):
        assert committed == [(3, "candidate")]
        assert model == tmp_path / "accepted" / "model.zip"
        return {
            "episodes": 200,
            "seed": 1000,
            "success_percent": 100.0,
            "goal_reached": True,
        }

    monkeypatch.setattr(
        "research.run_experiment.evaluate_final_model", evaluate_after_commit
    )
    assert execute_pending_final_benchmark() == 0
