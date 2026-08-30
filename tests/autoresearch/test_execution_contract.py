"""Human-owned tests of the generic AutoResearch execution machinery.

The runner executes and records researcher decisions. These tests describe its
lifecycle, persistence, protected surfaces and validation timing. They stay
method-neutral: they never name or import a concrete learning algorithm.
"""

import json
from pathlib import Path

import pytest

from research.run_experiment import (
    PROTECTED_TEST_PREFIXES,
    append_result,
    assert_research_surface,
    candidate_directories,
    check_proposal,
    commit_and_push,
    dependency_metadata_changed,
    format_duration,
    latest_training_steps,
    load_state,
    main,
    requires_full_validation,
    validate_changed_sources,
    validate_experiment_semantics,
    validate_proposal_phase,
    validate_reusable_candidate,
    validate_training_proposal,
)
from robot_learning.evaluate import write_progress
from robot_learning.train import effective_training_config
from robot_learning.training.research_config import load_experiment_config

PROTECTED_TEST_PATHS = (
    "tests/benchmark/test_task_contract.py",
    "tests/benchmark/test_benchmark_trust_path.py",
    "tests/autoresearch/test_execution_contract.py",
    "tests/autoresearch/test_research_protocol.py",
)

RESEARCHER_OWNED_TEST_PATHS = (
    "tests/scenario/test_reward.py",
    "tests/scenario/test_environment.py",
    "tests/training/test_active_learning_method.py",
    "tests/training/test_checkpointing.py",
)


def active_effective_config() -> tuple[dict, dict]:
    """The current runtime configuration and the trainer's resolved view of it."""
    config = load_experiment_config()
    return config, effective_training_config(config)


# --- research surface ------------------------------------------------------


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


# --- protected test domains ------------------------------------------------


def renamed(origin: str, destination: str) -> tuple[str, str]:
    """A staged rename as `-z` reports it: destination first, origin after."""
    return (f"R  {destination}", origin)


def worktree_changes(monkeypatch, *entries: str | tuple[str, ...]) -> list[str]:
    fields: list[str] = []
    for entry in entries:
        fields.extend((entry,) if isinstance(entry, str) else entry)
    monkeypatch.setattr(
        "research.run_experiment.git",
        lambda *args: "".join(f"{field}\0" for field in fields),
    )
    return assert_research_surface()


def validate_worktree(monkeypatch, *entries: str | tuple[str, ...]) -> list[str]:
    changes = worktree_changes(monkeypatch, *entries)
    validate_experiment_semantics({}, "training", "transfer", None, changes, False)
    return changes


def test_protected_test_directories_are_prefix_based():
    assert PROTECTED_TEST_PREFIXES == ("tests/benchmark/", "tests/autoresearch/")


@pytest.mark.parametrize("protected_path", PROTECTED_TEST_PATHS)
def test_modifying_a_protected_test_is_rejected(monkeypatch, protected_path):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, f" M {protected_path}")


@pytest.mark.parametrize("protected_path", PROTECTED_TEST_PATHS)
def test_deleting_a_protected_test_is_rejected(monkeypatch, protected_path):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, f" D {protected_path}")


def test_status_reports_both_sides_of_a_rename(monkeypatch):
    assert worktree_changes(
        monkeypatch,
        renamed("tests/scenario/test_reward.py", "tests/scenario/test_shaping.py"),
    ) == ["tests/scenario/test_reward.py", "tests/scenario/test_shaping.py"]


def test_status_keeps_unquoted_paths_containing_spaces(monkeypatch):
    assert worktree_changes(monkeypatch, " M research/a note.md") == [
        "research/a note.md"
    ]


def test_renaming_a_protected_test_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(
            monkeypatch,
            renamed(
                "tests/benchmark/test_task_contract.py",
                "tests/benchmark/renamed.py",
            ),
        )


@pytest.mark.parametrize(
    ("origin", "destination"),
    [
        (
            "tests/training/test_active_learning_method.py",
            "tests/autoresearch/test_smuggled_rule.py",
        ),
        (
            "tests/scenario/test_reward.py",
            "tests/benchmark/test_smuggled_contract.py",
        ),
    ],
)
def test_renaming_a_researcher_test_into_a_protected_domain_is_rejected(
    monkeypatch, origin, destination
):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, renamed(origin, destination))


@pytest.mark.parametrize(
    ("origin", "destination"),
    [
        (
            "tests/autoresearch/test_execution_contract.py",
            "tests/training/test_execution_contract.py",
        ),
        (
            "tests/benchmark/test_task_contract.py",
            "tests/scenario/test_task_contract.py",
        ),
    ],
)
def test_renaming_a_protected_test_out_of_its_domain_is_rejected(
    monkeypatch, origin, destination
):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, renamed(origin, destination))


def test_renaming_between_researcher_owned_domains_is_allowed(monkeypatch):
    assert validate_worktree(
        monkeypatch,
        renamed(
            "tests/scenario/test_reward.py",
            "tests/training/test_reward_shaping.py",
        ),
    ) == [
        "tests/scenario/test_reward.py",
        "tests/training/test_reward_shaping.py",
    ]


def test_creating_a_new_protected_test_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, "?? tests/autoresearch/test_invented_rule.py")

    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, "?? tests/benchmark/test_invented_rule.py")


def test_protected_test_protection_ignores_path_separator(monkeypatch):
    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, "?? tests\\autoresearch\\test_invented.py")

    with pytest.raises(ValueError, match="human-owned .* tests"):
        validate_worktree(monkeypatch, " M tests\\benchmark\\test_task_contract.py")


@pytest.mark.parametrize("research_test_path", RESEARCHER_OWNED_TEST_PATHS)
def test_researcher_owned_tests_remain_changeable(monkeypatch, research_test_path):
    assert validate_worktree(monkeypatch, f" M {research_test_path}") == [
        research_test_path
    ]
    assert validate_worktree(monkeypatch, f"?? {research_test_path}") == [
        research_test_path
    ]
    assert validate_worktree(monkeypatch, f" D {research_test_path}") == [
        research_test_path
    ]


def test_researcher_owned_tests_are_ordinary_code_changes(monkeypatch):
    changes = validate_worktree(
        monkeypatch,
        " M robot_learning/scenario/reward.py",
        " M tests/scenario/test_reward.py",
    )

    assert changes == [
        "robot_learning/scenario/reward.py",
        "tests/scenario/test_reward.py",
    ]


def test_researcher_owned_tests_follow_the_code_lineage(monkeypatch):
    from research import run_experiment

    root = Path(__file__).resolve().parents[2]
    created = "tests/training/test_invented_by_this_experiment.py"

    def tracked_at_parent(*args: str) -> str:
        path = args[-1]
        return "" if path == created else f"{path}\n"

    monkeypatch.setattr(run_experiment, "ROOT", root)
    monkeypatch.setattr(run_experiment, "git", tracked_at_parent)

    plan = run_experiment.plan_code_lineage_decision(
        {
            "code_parent_commit": "abc123",
            "research_change_paths": [
                "robot_learning/scenario/reward.py",
                "tests/scenario/test_reward.py",
                created,
            ],
        },
        "revert",
    )

    assert plan["restore"] == [
        "robot_learning/scenario/reward.py",
        "tests/scenario/test_reward.py",
    ]
    assert plan["remove_created"] == [(root / created).resolve()]


def test_renamed_researcher_tests_travel_with_the_code_lineage(monkeypatch):
    from research import run_experiment

    root = Path(__file__).resolve().parents[2]
    origin = "tests/scenario/test_reward.py"
    destination = "tests/scenario/test_shaping.py"

    def tracked_at_parent(*args: str) -> str:
        path = args[-1]
        return "" if path == destination else f"{path}\n"

    monkeypatch.setattr(run_experiment, "ROOT", root)
    monkeypatch.setattr(run_experiment, "git", tracked_at_parent)

    plan = run_experiment.plan_code_lineage_decision(
        {
            "code_parent_commit": "abc123",
            "research_change_paths": [origin, destination],
        },
        "revert",
    )

    assert plan["restore"] == [origin]
    assert plan["remove_created"] == [(root / destination).resolve()]


# --- validation timing -----------------------------------------------------


def test_fresh_campaign_baseline_is_validated_without_worktree_changes():
    assert requires_full_validation([], fresh_baseline=True)


def test_unchanged_continuation_or_evaluation_skips_the_test_suites():
    assert not requires_full_validation([], fresh_baseline=False)


def test_parameter_only_experiment_skips_the_test_suites():
    assert not requires_full_validation(
        ["research/current_params.json"], fresh_baseline=False
    )
    assert not requires_full_validation(
        ["research\\current_params.json"], fresh_baseline=False
    )


def test_active_configuration_is_resolved_through_the_trainer():
    from research import run_experiment

    config, effective = active_effective_config()

    assert run_experiment.validate_active_configuration() == effective
    assert config == load_experiment_config()


def test_incomplete_active_configuration_is_rejected(monkeypatch):
    from research import run_experiment

    monkeypatch.setattr(
        run_experiment, "load_experiment_config", lambda: {"training": {}}
    )

    with pytest.raises(RuntimeError, match="active training configuration is invalid"):
        run_experiment.validate_active_configuration()


def test_parameter_only_experiment_still_validates_the_configuration(
    monkeypatch, tmp_path
):
    from research import run_experiment

    accepted = tmp_path / "accepted"
    accepted.mkdir()
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (accepted / filename).write_bytes(b"artifact")
    (tmp_path / "research_state.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "accepted_metrics": None,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "EXPERIMENTS.md").write_text("header\n", encoding="utf-8")
    (tmp_path / "proposal.json").write_text(
        json.dumps(
            {
                "kind": "training",
                "family": "method.rollout_steps",
                "hypothesis": "a longer rollout stabilizes the update",
                "change": "lengthen the rollout",
                "initialization": "transfer",
                "training_parent": "accepted",
                "params": {"training": {"n_envs": 1}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_experiment, "ROOT", tmp_path)
    monkeypatch.setattr(run_experiment, "ACCEPTED_DIR", accepted)
    monkeypatch.setattr(run_experiment, "STATE_PATH", tmp_path / "research_state.json")
    monkeypatch.setattr(run_experiment, "PROPOSAL_PATH", tmp_path / "proposal.json")
    monkeypatch.setattr(run_experiment, "LOG_PATH", tmp_path / "EXPERIMENTS.md")
    monkeypatch.setattr(run_experiment, "RESULTS_PATH", tmp_path / "results.jsonl")
    monkeypatch.setattr(run_experiment, "CANDIDATE_ROOT", tmp_path / "candidates")
    monkeypatch.setattr(run_experiment, "git", lambda *args: "")
    monkeypatch.setattr(run_experiment, "announce", lambda message: None)
    monkeypatch.setattr(run_experiment, "load_experiment_config", dict)
    monkeypatch.setattr(run_experiment, "write_experiment_config", lambda config: None)
    monkeypatch.setattr(
        run_experiment,
        "run_module",
        lambda *args, **kwargs: pytest.fail("a parameter-only experiment ran pytest"),
    )
    monkeypatch.setattr(
        run_experiment,
        "train_candidate",
        lambda *args, **kwargs: pytest.fail("training started on an invalid config"),
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    assert run_experiment.main() == 1

    recorded = json.loads(
        (tmp_path / "results.jsonl").read_text(encoding="utf-8").strip()
    )
    assert "active training configuration is invalid" in recorded["error"]


@pytest.mark.parametrize(
    "changed_path",
    [
        "robot_learning/scenario/reward.py",
        "robot_learning/train.py",
        "tests/scenario/test_reward.py",
        "tests/training/test_active_learning_method.py",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_code_changing_experiment_is_fully_validated(changed_path):
    assert requires_full_validation([changed_path], fresh_baseline=False)


def test_dependency_metadata_is_only_checked_when_it_changes():
    assert dependency_metadata_changed(["pyproject.toml"])
    assert dependency_metadata_changed(["uv.lock"])
    assert not dependency_metadata_changed(["robot_learning/train.py"])


def test_changed_python_files_are_syntax_checked(monkeypatch, tmp_path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.run_module",
        lambda *args, **kwargs: pytest.fail("linting ran on unparsable source"),
    )

    with pytest.raises(RuntimeError, match="broken.py"):
        validate_changed_sources(["broken.py"])


def test_changed_json_files_must_parse(monkeypatch, tmp_path):
    (tmp_path / "good.json").write_text("{}", encoding="utf-8")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        '{"index": 1}\n{"index": 2}\n', encoding="utf-8"
    )
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)

    validate_changed_sources(["good.json", "results.jsonl"])
    with pytest.raises(RuntimeError, match="broken.json"):
        validate_changed_sources(["broken.json"])


def test_changed_python_files_are_linted_individually(monkeypatch, tmp_path):
    (tmp_path / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "research.run_experiment.run_module",
        lambda *args, **kwargs: calls.append(args) or "",
    )

    validate_changed_sources(["clean.py", "notes.md", "absent.py"])

    assert calls == [("ruff", "check", "clean.py")]


def test_dependency_check_never_rewrites_the_lockfile(monkeypatch):
    from research import run_experiment

    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        run_experiment, "run_command", lambda *args, **kwargs: calls.append(args) or ""
    )

    run_experiment.validate_dependency_metadata()

    assert calls == [("uv", "lock", "--check")]


def test_validated_test_paths_are_the_four_repository_domains():
    from research import run_experiment

    assert run_experiment.VALIDATED_TEST_PATHS == (
        "tests/benchmark",
        "tests/autoresearch",
        "tests/scenario",
        "tests/training",
    )
    root = Path(__file__).resolve().parents[2]
    for relative in run_experiment.VALIDATED_TEST_PATHS:
        assert (root / relative).is_dir(), relative


# --- execution lifecycle ---------------------------------------------------


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


# --- artifact reuse --------------------------------------------------------


def test_reusable_candidate_must_match_experiment(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "model.zip").touch()
    (candidate / "vecnormalize.pkl").touch()
    config, effective = active_effective_config()
    (candidate / "artifact.json").write_text(
        json.dumps(
            {
                "seed": 0,
                "timesteps": 1000,
                "effective_config": effective,
                "resumed_from": None,
            }
        ),
        encoding="utf-8",
    )

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
    config, effective = active_effective_config()
    (candidate / "artifact.json").write_text(
        json.dumps(
            {
                "seed": 0,
                "timesteps": 50_000,
                "requested_timesteps": 120_000,
                "completed": False,
                "effective_config": effective,
                "resumed_from": "a prior recovery checkpoint",
            }
        ),
        encoding="utf-8",
    )

    validate_reusable_candidate(
        candidate,
        timesteps=120_000,
        seed=0,
        resume=None,
        config=config,
    )


def test_reusable_candidate_compares_effective_configuration_opaquely(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for filename in ("model.zip", "vecnormalize.pkl"):
        (candidate / filename).touch()
    config, effective = active_effective_config()
    artifact = {
        "seed": 0,
        "timesteps": 120_000,
        "requested_timesteps": 120_000,
        "effective_config": effective,
        "resumed_from": None,
    }
    (candidate / "artifact.json").write_text(json.dumps(artifact), encoding="utf-8")

    validate_reusable_candidate(
        candidate, timesteps=120_000, seed=0, resume=None, config=config
    )

    # The runner only compares the trainer's own description for equality.
    artifact["effective_config"] = {"a different training configuration": True}
    (candidate / "artifact.json").write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="effective configuration"):
        validate_reusable_candidate(
            candidate, timesteps=120_000, seed=0, resume=None, config=config
        )

    artifact["effective_config"] = effective
    artifact["seed"] = 1
    (candidate / "artifact.json").write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="seed"):
        validate_reusable_candidate(
            candidate, timesteps=120_000, seed=0, resume=None, config=config
        )


def test_runner_does_not_interpret_effective_configuration():
    source = (Path(__file__).parents[2] / "research" / "run_experiment.py").read_text(
        encoding="utf-8"
    )
    validation = source.split("def validate_reusable_candidate", 1)[1].split(
        "def retained_lineage", 1
    )[0]

    for forbidden in ("ppo", "n_steps", "policy", "parameters", "n_envs"):
        assert forbidden not in validation


# --- proposal validation ---------------------------------------------------


def test_training_proposal_requires_only_its_scientific_shape():
    proposal = {
        "kind": "training",
        "family": "observation.representation",
        "hypothesis": "the observation hides information needed by the policy",
        "change": "change the observation representation",
        "initialization": "fresh",
    }

    validate_training_proposal(proposal, baseline=False)
    validate_experiment_semantics(
        proposal,
        "training",
        "fresh",
        None,
        ["robot_learning/scenario/observations.py"],
        False,
    )


def test_transfer_proposal_requires_a_training_parent():
    proposal = {
        "kind": "training",
        "family": "x",
        "hypothesis": "x",
        "change": "x",
        "initialization": "transfer",
    }

    with pytest.raises(ValueError, match="requires training_parent"):
        validate_training_proposal(proposal, baseline=False)

    proposal["training_parent"] = "accepted"
    validate_training_proposal(proposal, baseline=False)


def test_fresh_proposal_rejects_a_training_parent():
    proposal = {
        "kind": "training",
        "family": "x",
        "hypothesis": "x",
        "change": "x",
        "initialization": "fresh",
        "training_parent": "accepted",
    }

    with pytest.raises(ValueError, match="only valid with transfer"):
        validate_training_proposal(proposal, baseline=False)


def test_baseline_proposal_requires_fields_consumed_by_execution():
    with pytest.raises(ValueError, match="baseline proposal is missing"):
        validate_training_proposal({"baseline": True}, baseline=True)


def _training_proposal() -> dict:
    return {
        "kind": "training",
        "family": "observation.representation",
        "hypothesis": "the current representation limits learning",
        "change": "change the observation representation",
        "initialization": "fresh",
    }


def test_current_phase_accepts_a_training_proposal_when_no_decision_is_pending():
    state = {
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_final_benchmark": None,
    }

    assert validate_proposal_phase(_training_proposal(), state) == "training"


def test_proposal_preflight_accepts_a_valid_training_proposal(
    monkeypatch, tmp_path, capsys
):
    proposal_path = tmp_path / "proposal.json"
    state_path = tmp_path / "research_state.json"
    proposal_path.write_text(json.dumps(_training_proposal()), encoding="utf-8")
    state_path.write_text(
        json.dumps(
            {
                "pending_evaluation_request": None,
                "pending_researcher_decision": None,
                "pending_final_benchmark": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)

    assert check_proposal() == 0
    assert "PROPOSAL_VALID: training" in capsys.readouterr().out


def test_current_phase_rejects_redundant_lineage_before_training_fields():
    state = {
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_final_benchmark": None,
    }
    residue = {"previous_result_decision": {"experiment": 1}}

    with pytest.raises(ValueError, match="lineage is already resolved"):
        validate_proposal_phase(residue, state)


def test_lineage_phase_accepts_only_the_lineage_proposal_shape():
    state = {"pending_researcher_decision": {"experiment": 1}}

    assert (
        validate_proposal_phase(
            {"previous_result_decision": {"experiment": 1}}, state
        )
        == "lineage"
    )
    with pytest.raises(ValueError, match="requires a lineage proposal"):
        validate_proposal_phase(_training_proposal(), state)


def test_proposal_preflight_rejects_incident_residue_without_mutation(
    monkeypatch, tmp_path, capsys
):
    proposal_path = tmp_path / "proposal.json"
    state_path = tmp_path / "research_state.json"
    accepted = tmp_path / "accepted" / "model.zip"
    accepted.parent.mkdir()
    accepted.write_bytes(b"accepted-lineage")
    proposal_path.write_text(
        json.dumps({"previous_result_decision": {"experiment": 1}}),
        encoding="utf-8",
    )
    state = {
        "last_experiment": 1,
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_final_benchmark": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    original_state = state_path.read_bytes()
    original_proposal = proposal_path.read_bytes()
    monkeypatch.setattr("research.run_experiment.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)

    assert check_proposal() == 1
    assert "lineage is already resolved" in capsys.readouterr().out

    def fail_if_training_starts(*args, **kwargs):
        del args, kwargs
        pytest.fail("training started for a phase-incompatible proposal")

    monkeypatch.setattr("research.run_experiment.train_candidate", fail_if_training_starts)
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])
    assert main() == 1
    assert "invalid proposal for current phase" in capsys.readouterr().out
    assert state_path.read_bytes() == original_state
    assert proposal_path.read_bytes() == original_proposal
    assert accepted.read_bytes() == b"accepted-lineage"


# --- candidate manifest ----------------------------------------------------


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


# --- lineage ---------------------------------------------------------------


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
    from research.run_experiment import execute_pending_final_benchmark

    assert execute_pending_final_benchmark() == 0
