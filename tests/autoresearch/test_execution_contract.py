"""Human-owned tests of the generic AutoResearch execution machinery.

The runner executes and records researcher decisions. These tests describe its
lifecycle, persistence, protected surfaces and validation timing. They stay
method-neutral: they never name or import a concrete learning algorithm.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from research import runner_execution as execution
from research import runner_protocol as protocol
from research.run_experiment import (
    apply_previous_result_decision,
    begin_hypothesis_phase,
    check_proposal,
    main,
)
from research.runner_console import format_duration
from research.runner_execution import (
    candidate_directories,
    latest_training_steps,
    validate_changed_sources,
    validate_reusable_candidate,
)
from research.runner_protocol import (
    PROTECTED_TEST_PREFIXES,
    allocated_experiment_index,
    next_experiment_index,
    plan_code_lineage_decision,
    plan_previous_result_decision,
    resumed_experiment_index,
    validate_experiment_semantics,
    validate_proposal_phase,
    validate_training_proposal,
    validation_test_paths,
)
from research.runner_repository import (
    RUNNER_CONTROL_PATHS,
    anchor_scientific_parent,
    append_result,
    apply_code_lineage_decision,
    assert_research_surface,
    commit_and_push,
    commit_lineage_decision,
    commit_result,
    commit_runner_memory,
    copy_artifact,
    is_runner_memory,
    load_state,
    repo_relative_path,
    require_complete_artifact,
    resolve_repo_path,
    scientific_delta,
    synchronize_experiment_log,
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


RUNTIME_STACK_MODULES = (
    "mujoco",
    "torch",
    "gymnasium",
    "stable_baselines3",
    "robot_learning.scenario",
)

VALIDATION_ONLY_COMMANDS = (
    "--check-proposal",
    "--check-evaluation-request",
    "--check-lineage-evidence",
    "--begin-hypothesis",
)


def test_the_runner_loads_without_the_training_runtime():
    """A control command must not pay for the training and physics stack."""
    probe = (
        "import sys, json\n"
        "from research import run_experiment\n"
        f"loaded = [m for m in {RUNTIME_STACK_MODULES!r} if m in sys.modules]\n"
        "print(json.dumps(loaded))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr[-2000:]
    assert json.loads(completed.stdout.strip()) == []


def test_validation_only_commands_stay_in_the_dispatcher():
    """Every control command returns before the Runner may write anything."""
    source = (Path(__file__).parents[2] / "research" / "run_experiment.py").read_text(
        encoding="utf-8"
    )
    dispatch = source.split("def main()", 1)[1]
    before_mutation, _, _ = dispatch.partition("synchronize_experiment_log")

    assert _
    for flag in VALIDATION_ONLY_COMMANDS:
        attribute = flag.removeprefix("--").replace("-", "_")
        assert attribute in before_mutation, flag


def test_research_surface_has_no_file_whitelist(monkeypatch):
    monkeypatch.setattr(
        "research.runner_repository.status_paths",
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
        "research.runner_repository.status_paths",
        lambda paths: ["research/current_params.json"] if paths else [],
    )

    assert assert_research_surface() == ["research/current_params.json"]


# --- runner memory versus scientific change --------------------------------

SCIENTIFIC_CHANGE = "robot_learning/scenario/reward.py"
RUNNER_MEMORY_WORKTREE = [
    "research/results.jsonl",
    "research/EXPERIMENTS.md",
    "research/research_state.json",
    "research/postmortems.md",
    "research/BASELINE_PENDING",
    "research/evaluations/evaluation-experiment-3-champion-200ep-seed1000-abc.json",
    "research/checkpoints/accepted/model.zip",
    "research/checkpoints/retained/alternative-3/model.zip",
]


def record_git(monkeypatch, changed: list[str]) -> list[tuple[str, ...]]:
    """Record every git invocation over a worktree Git reports as `changed`."""
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        if args[0] == "ls-files":
            return args[-1] + "\n"
        if args[0] == "diff":
            return "\n".join(args[args.index("--") + 1 :]) + "\n"
        return ""

    monkeypatch.setattr(
        "research.runner_repository.status_paths",
        lambda paths: list(changed) if paths else [],
    )
    monkeypatch.setattr("research.runner_repository.git", fake_git)
    return calls


def commits_of(calls: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return [call for call in calls if call[0] == "commit"]


def committed_paths(commit: tuple[str, ...]) -> list[str]:
    return list(commit[commit.index("--") + 1 :])


def test_dirty_runner_memory_is_never_a_scientific_change(monkeypatch):
    monkeypatch.setattr(
        "research.runner_repository.status_paths",
        lambda paths: [SCIENTIFIC_CHANGE, *RUNNER_MEMORY_WORKTREE] if paths else [],
    )

    assert assert_research_surface() == [SCIENTIFIC_CHANGE]


def test_a_runner_memory_commit_cannot_capture_scientific_changes(monkeypatch):
    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, *RUNNER_MEMORY_WORKTREE])

    assert commit_runner_memory("record campaign memory")

    commits = commits_of(calls)
    assert len(commits) == 1
    assert set(committed_paths(commits[0])) == set(RUNNER_MEMORY_WORKTREE)
    assert SCIENTIFIC_CHANGE not in committed_paths(commits[0])
    # Nothing staged, unstaged, reset or restored the scientific modification.
    assert not [
        call for call in calls if call[0] in {"reset", "restore", "checkout", "stash"}
    ]
    assert SCIENTIFIC_CHANGE not in {
        argument for call in calls if call[0] == "add" for argument in call
    }
    assert assert_research_surface() == [SCIENTIFIC_CHANGE]


def test_invalid_experiment_memory_is_persisted_without_its_science(monkeypatch):
    history = [
        "research/results.jsonl",
        "research/EXPERIMENTS.md",
        "research/research_state.json",
    ]
    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, *history])

    commit_result(3, "Reshape the shaping term")

    commits = commits_of(calls)
    assert len(commits) == 1
    assert commits[0][2] == "exp 3: Reshape the shaping term"
    assert set(committed_paths(commits[0])) == set(history)
    assert calls[-1] == ("push", "origin", "HEAD")
    assert assert_research_surface() == [SCIENTIFIC_CHANGE]


def test_lineage_closure_separates_the_science_from_the_memory_commit(monkeypatch):
    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, *RUNNER_MEMORY_WORKTREE])

    commit_lineage_decision(4, "checkpoint-120832")

    science, memory = commits_of(calls)
    assert committed_paths(science) == [SCIENTIFIC_CHANGE]
    assert set(committed_paths(memory)) == set(RUNNER_MEMORY_WORKTREE)
    assert memory[2] == "select experiment 4 lineage: checkpoint-120832"


def test_evaluation_artifacts_are_evidence_and_never_restorable_science(monkeypatch):
    artifact = "research/evaluations/evaluation-experiment-4-champion.json"
    monkeypatch.setattr(
        "research.runner_repository.status_paths",
        lambda paths: [SCIENTIFIC_CHANGE, artifact] if paths else [],
    )

    assert assert_research_surface() == [SCIENTIFIC_CHANGE]
    # A campaign recorded before this boundary existed still cannot lose evidence.
    assert plan_code_lineage_decision(
        {"code_parent_commit": "0" * 40, "research_change_paths": [artifact]},
        "revert",
    ) == {"restore": [], "remove_created": []}

    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, artifact])
    assert commit_runner_memory("record measured evidence")
    assert committed_paths(commits_of(calls)[0]) == [artifact]


def test_the_official_final_benchmark_is_persisted_immediately(monkeypatch):
    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, "research/research_state.json"])
    monkeypatch.setattr(
        "research.run_experiment.execute_pending_final_benchmark", lambda: 0
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py", "--evaluate-pending-final"])

    assert main() == 0

    commits = commits_of(calls)
    assert len(commits) == 1
    assert committed_paths(commits[0]) == ["research/research_state.json"]


def test_transient_controls_never_become_durable_campaign_memory(monkeypatch):
    assert RUNNER_CONTROL_PATHS == {
        "research/proposal.json",
        "research/evaluation_request.json",
    }
    assert not any(is_runner_memory(control) for control in RUNNER_CONTROL_PATHS)

    calls = record_git(monkeypatch, [SCIENTIFIC_CHANGE, *sorted(RUNNER_CONTROL_PATHS)])

    assert assert_research_surface() == [SCIENTIFIC_CHANGE]
    assert not commit_runner_memory("record campaign memory")
    assert calls == []


# --- protected test domains ------------------------------------------------


def renamed(origin: str, destination: str) -> tuple[str, str]:
    """A staged rename as `-z` reports it: destination first, origin after."""
    return (f"R  {destination}", origin)


def worktree_changes(monkeypatch, *entries: str | tuple[str, ...]) -> list[str]:
    fields: list[str] = []
    for entry in entries:
        fields.extend((entry,) if isinstance(entry, str) else entry)
    monkeypatch.setattr(
        "research.runner_repository.git",
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

    root = Path(__file__).resolve().parents[2]
    created = "tests/training/test_invented_by_this_experiment.py"

    def tracked_at_parent(*args: str) -> str:
        path = args[-1]
        return "" if path == created else f"{path}\n"

    monkeypatch.setattr("research.runner_paths.ROOT", root)
    monkeypatch.setattr("research.runner_repository.git", tracked_at_parent)

    plan = protocol.plan_code_lineage_decision(
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

    root = Path(__file__).resolve().parents[2]
    origin = "tests/scenario/test_reward.py"
    destination = "tests/scenario/test_shaping.py"

    def tracked_at_parent(*args: str) -> str:
        path = args[-1]
        return "" if path == destination else f"{path}\n"

    monkeypatch.setattr("research.runner_paths.ROOT", root)
    monkeypatch.setattr("research.runner_repository.git", tracked_at_parent)

    plan = protocol.plan_code_lineage_decision(
        {
            "code_parent_commit": "abc123",
            "research_change_paths": [origin, destination],
        },
        "revert",
    )

    assert plan["restore"] == [origin]
    assert plan["remove_created"] == [(root / destination).resolve()]


# --- validation timing -----------------------------------------------------

ALL_SUITES = (
    "tests/benchmark",
    "tests/autoresearch",
    "tests/scenario",
    "tests/training",
)
RESEARCHER_SUITES = (
    "tests/scenario",
    "tests/training",
    "tests/autoresearch/test_scenario_boundary.py",
    "tests/autoresearch/test_campaign_boundary.py",
)


def test_fresh_campaign_baseline_runs_every_suite():
    assert validation_test_paths([], fresh_baseline=True) == ALL_SUITES
    assert (
        validation_test_paths(
            ["robot_learning/scenario/reward.py"], fresh_baseline=True
        )
        == ALL_SUITES
    )


def test_unchanged_continuation_or_evaluation_skips_the_test_suites():
    assert validation_test_paths([], fresh_baseline=False) == ()


def test_parameter_only_experiment_skips_the_test_suites():
    assert (
        validation_test_paths(["research/current_params.json"], fresh_baseline=False)
        == ()
    )
    assert (
        validation_test_paths(["research\\current_params.json"], fresh_baseline=False)
        == ()
    )


def test_active_configuration_is_resolved_through_the_trainer():

    config, effective = active_effective_config()

    assert execution.validate_active_configuration() == effective
    assert config == load_experiment_config()


def test_incomplete_active_configuration_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "robot_learning.training.research_config.load_experiment_config",
        lambda: {"training": {}},
    )

    with pytest.raises(RuntimeError, match="active training configuration is invalid"):
        execution.validate_active_configuration()


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
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", accepted)
    monkeypatch.setattr(
        "research.runner_paths.STATE_PATH", tmp_path / "research_state.json"
    )
    monkeypatch.setattr(
        "research.runner_paths.PROPOSAL_PATH", tmp_path / "proposal.json"
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "EXPERIMENTS.md")
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl"
    )
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path / "candidates")
    monkeypatch.setattr("research.runner_repository.git", lambda *args: "")
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)
    monkeypatch.setattr(
        "robot_learning.training.research_config.load_experiment_config", dict
    )
    monkeypatch.setattr(
        "robot_learning.training.research_config.write_experiment_config",
        lambda config: None,
    )
    monkeypatch.setattr(
        "research.runner_execution.run_module",
        lambda *args, **kwargs: pytest.fail("a parameter-only experiment ran pytest"),
    )
    monkeypatch.setattr(
        "research.runner_execution.train_candidate",
        lambda *args, **kwargs: pytest.fail("training started on an invalid config"),
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    assert run_experiment.main() == 1

    recorded = json.loads(
        (tmp_path / "results.jsonl").read_text(encoding="utf-8").strip()
    )
    assert "active training configuration is invalid" in recorded["error"]


@pytest.mark.parametrize(
    "changed_paths",
    [
        ["robot_learning/scenario/reward.py"],
        ["robot_learning/scenario/observations.py"],
        ["robot_learning/training/algorithms.py"],
        ["robot_learning/train.py"],
        ["robot_learning/evaluate.py"],
        ["robot_learning/play.py"],
        ["tests/scenario/test_reward.py"],
        ["tests/training/test_active_learning_method.py"],
        ["robot_learning\\scenario\\reward.py"],
        # Mixed researcher-owned surfaces, and researcher code beside a
        # parameter-only edit, stay a researcher-only change.
        [
            "robot_learning/scenario/environment.py",
            "robot_learning/training/normalization.py",
            "tests/scenario/test_environment.py",
            "tests/training/test_checkpointing.py",
        ],
        ["robot_learning/scenario/reward.py", "research/current_params.json"],
    ],
)
def test_researcher_owned_change_skips_only_the_frozen_task_suite(changed_paths):
    assert (
        validation_test_paths(changed_paths, fresh_baseline=False) == RESEARCHER_SUITES
    )


@pytest.mark.parametrize(
    "changed_path",
    [
        # Human-owned paths are validated completely if inspected directly.
        "research/build_research_brief.py",
        "run_research.ps1",
        "research/program.md",
        "robot_learning/environments/reach_env.py",
        "robot_learning/rewards/reach_reward.py",
        "robot_learning/benchmark/metrics.py",
        "pyproject.toml",
        "uv.lock",
        "main.py",
        # Protected paths never become researcher-owned by sharing a prefix.
        "robot_learning/scenario/__init__.py",
        "robot_learning/scenario/final_benchmark.py",
        "robot_learning/scenario/task_reference.py",
        "tests/benchmark/test_task_contract.py",
        "tests/autoresearch/test_execution_contract.py",
    ],
)
def test_change_outside_the_researcher_surface_runs_every_suite(changed_path):
    assert validation_test_paths([changed_path], fresh_baseline=False) == ALL_SUITES


def test_one_unclassified_path_pulls_the_whole_experiment_to_full_validation():
    assert (
        validation_test_paths(
            ["robot_learning/scenario/reward.py", "research/build_research_brief.py"],
            fresh_baseline=False,
        )
        == ALL_SUITES
    )


@pytest.mark.parametrize(
    "protected_path",
    [
        "AGENTS.md",
        "research/program.md",
        "research/scenario.md",
        "research/instruments.md",
        "run_research.ps1",
        "researcher_session.ps1",
        "research/build_research_brief.py",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_context_runtime_and_dependency_metadata_are_protected(protected_path):
    assert protocol.is_protected_source(protected_path)
    assert not protocol.is_researcher_owned(protected_path)


def test_changed_python_files_are_syntax_checked(monkeypatch, tmp_path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_execution.run_module",
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
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    validate_changed_sources(["good.json", "results.jsonl"])
    with pytest.raises(RuntimeError, match="broken.json"):
        validate_changed_sources(["broken.json"])


def test_changed_python_files_are_linted_individually(monkeypatch, tmp_path):
    (tmp_path / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "research.runner_execution.run_module",
        lambda *args, **kwargs: calls.append(args) or "",
    )

    validate_changed_sources(["clean.py", "notes.md", "absent.py"])

    assert calls == [("ruff", "check", "clean.py")]


def test_dependency_check_never_rewrites_the_lockfile(monkeypatch):
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "research.runner_execution.run_command",
        lambda *args, **kwargs: calls.append(args) or "",
    )

    execution.validate_dependency_metadata()

    assert calls == [("uv", "lock", "--check")]


def test_validated_test_paths_are_the_four_repository_domains():

    assert protocol.VALIDATED_TEST_PATHS == (
        "tests/benchmark",
        "tests/autoresearch",
        "tests/scenario",
        "tests/training",
    )
    assert protocol.RESEARCHER_VALIDATED_TEST_PATHS == (
        "tests/scenario",
        "tests/training",
        "tests/autoresearch/test_scenario_boundary.py",
        "tests/autoresearch/test_campaign_boundary.py",
    )
    root = Path(__file__).resolve().parents[2]
    for relative in protocol.VALIDATED_TEST_PATHS:
        assert (root / relative).is_dir(), relative


def test_researcher_owned_surface_is_declared_positively_and_exists():

    root = Path(__file__).resolve().parents[2]
    for prefix in protocol.RESEARCHER_OWNED_PREFIXES:
        assert (root / prefix).is_dir(), prefix
    for relative in protocol.RESEARCHER_OWNED_PATHS:
        assert (root / relative).is_file(), relative


def test_protected_paths_are_never_researcher_owned():

    for relative in protocol.PROTECTED_BENCHMARK_PATHS:
        assert not protocol.is_researcher_owned(relative), relative
    for prefix in protocol.PROTECTED_TEST_PREFIXES:
        assert not protocol.is_researcher_owned(f"{prefix}test_anything.py")


def test_a_proposal_touching_protected_tests_is_rejected_before_selection():
    for relative in (
        "tests/benchmark/test_task_contract.py",
        "tests/autoresearch/test_execution_contract.py",
        "tests/benchmark/test_newly_invented.py",
    ):
        with pytest.raises(ValueError, match="cannot be changed"):
            validate_experiment_semantics(
                {}, "training", "transfer", None, [relative], False
            )


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
        "research.runner_repository.git",
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
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_repository.git", lambda *args: "base-commit\n"
    )

    state = load_state(allow_unmeasured=True, allow_missing_artifact=True)
    assert state["accepted_metrics"] is None
    with pytest.raises(RuntimeError, match="accepted artifact is incomplete"):
        load_state(allow_unmeasured=True)


def test_repo_paths_use_forward_slashes_and_resolve_legacy_separators(
    monkeypatch, tmp_path
):
    root = tmp_path / "repo"
    nested = root / "research" / "checkpoints" / "accepted"
    monkeypatch.setattr("research.runner_paths.ROOT", root)

    assert repo_relative_path(nested) == "research/checkpoints/accepted"
    assert resolve_repo_path("research\\checkpoints\\accepted") == nested
    assert resolve_repo_path("research/checkpoints/accepted") == nested


@pytest.mark.parametrize(
    "persisted",
    ["../outside", "/absolute/path", "C:\\absolute\\path"],
)
def test_resolve_repo_path_rejects_non_repository_paths(
    monkeypatch, tmp_path, persisted
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path / "repo")

    with pytest.raises(ValueError, match="repository|outside"):
        resolve_repo_path(persisted)


def test_load_state_resolves_legacy_windows_artifact_path(monkeypatch, tmp_path):
    accepted = tmp_path / "research" / "checkpoints" / "accepted"
    accepted.mkdir(parents=True)
    (accepted / "model.zip").write_bytes(b"model")
    (accepted / "artifact.json").write_text("{}", encoding="utf-8")
    state_path = tmp_path / "research_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "accepted_artifact": "research\\checkpoints\\accepted",
                "accepted_metrics": {"success_percent": 50.0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)

    assert load_state()["accepted_artifact"] == "research\\checkpoints\\accepted"


def test_experiment_rows_remain_one_line(monkeypatch, tmp_path):
    log_path = tmp_path / "EXPERIMENTS.md"
    results_path = tmp_path / "results.jsonl"
    log_path.write_text("header\n", encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", log_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", results_path)

    append_result(
        {
            "index": 1,
            "change": "line one\nline two",
            "hypothesis": "safe | table",
            "verdict": "error:\ntraceback",
        }
    )

    rows = [
        line
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("| 1 |")
    ]
    assert len(rows) == 1
    assert "line one line two" in rows[0]
    assert "safe / table" in rows[0]
    assert "error: traceback" in rows[0]


def test_the_markdown_log_is_derived_from_the_authoritative_history(
    monkeypatch, tmp_path
):
    """`results.jsonl` is the history; the Markdown view is only rendered from it."""
    log_path = tmp_path / "EXPERIMENTS.md"
    results_path = tmp_path / "results.jsonl"
    monkeypatch.setattr("research.runner_paths.LOG_PATH", log_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", results_path)

    for index in (1, 2):
        append_result(
            {
                "index": index,
                "change": f"change {index}",
                "hypothesis": f"hypothesis {index}",
                "verdict": "trained",
            }
        )

    records = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record["index"] for record in records] == [1, 2]
    assert all(record["recorded_at"] for record in records)

    rendered = log_path.read_text(encoding="utf-8")
    assert rendered.startswith("# Experiment log\n")
    assert rendered.count("| change 1 |") == 1
    assert rendered.count("| change 2 |") == 1

    # A Markdown view damaged by an interruption is rebuilt, never trusted.
    log_path.write_text("# Experiment log\n\ncorrupted\n", encoding="utf-8")
    synchronize_experiment_log()

    assert log_path.read_text(encoding="utf-8") == rendered


def test_a_legacy_record_without_a_date_still_renders(monkeypatch, tmp_path):
    log_path = tmp_path / "EXPERIMENTS.md"
    results_path = tmp_path / "results.jsonl"
    results_path.write_text(
        json.dumps({"index": 7, "change": "legacy", "verdict": "ok"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", log_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", results_path)

    synchronize_experiment_log()

    assert "| 7 | - | legacy |" in log_path.read_text(encoding="utf-8")


# --- artifact reuse --------------------------------------------------------


def test_artifact_without_optional_training_state_promotes_cleanly(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    (source / "model.zip").write_bytes(b"new model")
    (source / "artifact.json").write_text("{}", encoding="utf-8")
    (destination / "model.zip").write_bytes(b"old model")
    (destination / "artifact.json").write_text("{}", encoding="utf-8")
    (destination / "vecnormalize.pkl").write_bytes(b"stale normalization")
    (destination / "replay_buffer.pkl").write_bytes(b"stale replay")

    require_complete_artifact(source, "candidate")
    copy_artifact(source, destination)

    assert (destination / "model.zip").read_bytes() == b"new model"
    assert not (destination / "vecnormalize.pkl").exists()
    assert not (destination / "replay_buffer.pkl").exists()


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
    source = (Path(__file__).parents[2] / "research" / "runner_execution.py").read_text(
        encoding="utf-8"
    )
    validation = source.split("def validate_reusable_candidate", 1)[1].split(
        "def evaluate_artifact", 1
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("family", "   "),
        ("hypothesis", ""),
        ("change", "\t"),
    ],
)
def test_training_proposal_rejects_empty_scientific_text(field, value):
    proposal = _training_proposal()
    proposal[field] = value

    with pytest.raises(ValueError, match="non-empty string"):
        validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize("initialization", ["resume", "FRESH", 7, None])
def test_training_proposal_rejects_unknown_initialization(initialization):
    proposal = _training_proposal()
    proposal["initialization"] = initialization

    with pytest.raises(ValueError, match="initialization must be transfer or fresh"):
        validate_training_proposal(proposal, baseline=False)


def test_training_proposal_rejects_unknown_kind():
    proposal = _training_proposal()
    proposal["kind"] = "banana"

    with pytest.raises(ValueError, match="kind must be training"):
        validate_training_proposal(proposal, baseline=False)


def test_training_proposal_accepts_the_valid_training_kinds():
    validate_training_proposal(_training_proposal(), baseline=False)

    transfer = _training_proposal()
    transfer.update(initialization="transfer", training_parent="accepted")
    validate_training_proposal(transfer, baseline=False)

    continuation = dict(transfer, kind="continuation")
    validate_training_proposal(continuation, baseline=False)

    replication = dict(
        _training_proposal(),
        kind="replication",
        training_seed=19,
        replication_of=12,
    )
    validate_training_proposal(replication, baseline=False)


def test_baseline_proposal_requires_fields_consumed_by_execution():
    with pytest.raises(ValueError, match="baseline proposal is missing"):
        validate_training_proposal({"baseline": True}, baseline=True)


@pytest.mark.parametrize(("field", "value"), [("hypothesis", ""), ("change", " ")])
def test_baseline_proposal_rejects_empty_required_text(field, value):
    proposal = {
        "baseline": True,
        "hypothesis": "measure the starting method",
        "change": "run the unchanged starting method",
        "initialization": "fresh",
    }
    proposal[field] = value

    with pytest.raises(ValueError, match="non-empty string"):
        validate_training_proposal(proposal, baseline=True)


def test_baseline_proposal_accepts_nonempty_required_text():
    validate_training_proposal(
        {
            "baseline": True,
            "hypothesis": "measure the starting method",
            "change": "run the unchanged starting method",
            "initialization": "fresh",
        },
        baseline=True,
    )


def _baseline_proposal() -> dict:
    """The shape run_research.ps1 generates for a pending baseline."""
    return {
        "baseline": True,
        "change": "Fresh baseline",
        "hypothesis": "Establish the initial baseline for the human-defined objective.",
        "class": "baseline",
        "initialization": "fresh",
    }


@pytest.mark.parametrize(
    "kind", ["training", "continuation", "replication", "banana", None]
)
def test_baseline_proposal_must_not_declare_a_kind(kind):
    proposal = dict(_baseline_proposal(), kind=kind)

    with pytest.raises(ValueError, match="baseline proposal must not declare kind"):
        validate_training_proposal(proposal, baseline=True)


def test_runner_generated_baseline_remains_valid():
    validate_training_proposal(_baseline_proposal(), baseline=True)


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
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)

    assert check_proposal() == 0
    assert "PROPOSAL_VALID: training" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("initialization", "resume", "initialization must be transfer or fresh"),
        ("kind", "banana", "kind must be training"),
        ("hypothesis", "", "hypothesis must be a non-empty string"),
    ],
)
def test_proposal_preflight_rejects_static_training_contract_errors(
    monkeypatch, tmp_path, capsys, field, value, message
):
    proposal_path = tmp_path / "proposal.json"
    state_path = tmp_path / "research_state.json"
    proposal = _training_proposal()
    proposal[field] = value
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
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
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)

    assert check_proposal() == 1
    assert message in capsys.readouterr().out


def _write_preflight_files(monkeypatch, tmp_path, proposal: dict) -> None:
    proposal_path = tmp_path / "proposal.json"
    state_path = tmp_path / "research_state.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
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
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)


@pytest.mark.parametrize("kind", ["training", "replication", "banana"])
def test_proposal_preflight_rejects_a_baseline_declaring_a_kind(
    monkeypatch, tmp_path, capsys, kind
):
    _write_preflight_files(monkeypatch, tmp_path, dict(_baseline_proposal(), kind=kind))

    assert check_proposal() == 1
    assert "baseline proposal must not declare kind" in capsys.readouterr().out


def test_proposal_preflight_accepts_the_runner_generated_baseline(
    monkeypatch, tmp_path, capsys
):
    _write_preflight_files(monkeypatch, tmp_path, _baseline_proposal())

    assert check_proposal() == 0
    assert "PROPOSAL_VALID: training" in capsys.readouterr().out


@pytest.mark.parametrize("initialization", ["transfer", "resume", ""])
def test_proposal_preflight_rejects_a_baseline_that_is_not_fresh(
    monkeypatch, tmp_path, capsys, initialization
):
    _write_preflight_files(
        monkeypatch,
        tmp_path,
        dict(_baseline_proposal(), initialization=initialization),
    )

    assert check_proposal() == 1
    assert "baseline proposal requires fresh initialization" in capsys.readouterr().out


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
        validate_proposal_phase({"previous_result_decision": {"experiment": 1}}, state)
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
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)

    assert check_proposal() == 1
    assert "lineage is already resolved" in capsys.readouterr().out

    def fail_if_training_starts(*args, **kwargs):
        del args, kwargs
        pytest.fail("training started for a phase-incompatible proposal")

    monkeypatch.setattr(
        "research.runner_execution.train_candidate", fail_if_training_starts
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])
    assert main() == 1
    assert "invalid proposal for current phase" in capsys.readouterr().out
    assert state_path.read_bytes() == original_state
    assert proposal_path.read_bytes() == original_proposal
    assert accepted.read_bytes() == b"accepted-lineage"


# --- experiment identity ---------------------------------------------------


def _allocation_campaign(monkeypatch, tmp_path, state: dict) -> Path:
    """The smallest on-disk campaign the training path of main() can run."""
    accepted = tmp_path / "accepted"
    accepted.mkdir(exist_ok=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (accepted / filename).touch()
    state_path = tmp_path / "research_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "accepted_metrics": None,
                **state,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "EXPERIMENTS.md").write_text("| # | Date |\n", encoding="utf-8")

    def fail_if_training_starts(*args, **kwargs):
        del args, kwargs
        pytest.fail("training started for an experiment that never validated")

    for target, value in {
        "research.runner_paths.ROOT": tmp_path,
        "research.runner_paths.STATE_PATH": state_path,
        "research.runner_paths.LOG_PATH": tmp_path / "EXPERIMENTS.md",
        "research.runner_paths.RESULTS_PATH": tmp_path / "results.jsonl",
        "research.runner_paths.PROPOSAL_PATH": tmp_path / "proposal.json",
        "research.runner_paths.CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "research.runner_paths.RESTART_PENDING_PATH": tmp_path / "RESTART_PENDING",
        "research.runner_paths.RECOVERY_PENDING_PATH": tmp_path / "RECOVERY_PENDING",
        "research.runner_repository.git": (
            lambda *args: "0" * 40 + "\n" if args[0] == "rev-parse" else ""
        ),
        "research.runner_repository.status_paths": lambda paths: [],
        "research.runner_execution.train_candidate": fail_if_training_starts,
    }.items():
        monkeypatch.setattr(target, value)
    return state_path


def _rejected_proposal() -> dict:
    """Shape-valid, but carries no research change, so execution rejects it."""
    return {
        "kind": "training",
        "family": "identity.allocation",
        "hypothesis": "An experiment number is spent even when nothing trains.",
        "change": "No researcher change at all.",
        "initialization": "fresh",
    }


def _allocated(state_path: Path) -> int | None:
    return json.loads(state_path.read_text(encoding="utf-8")).get(
        "last_allocated_experiment"
    )


def test_runner_state_outranks_an_incomplete_history(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path / "candidates")
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", tmp_path / "results")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "log")
    (tmp_path / "results").write_text('{"index": 1}\n{"index": 2}\n', encoding="utf-8")
    (tmp_path / "log").write_text("| 1 | a |\n| 2 | b |\n", encoding="utf-8")

    assert next_experiment_index({"last_allocated_experiment": 4}) == 5


def test_a_state_file_without_allocation_seeds_it_from_the_runner_state():
    assert allocated_experiment_index({"last_experiment": 4}) == 4
    assert allocated_experiment_index({}) == 0


def test_a_fresh_campaign_allocates_the_first_experiment(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path / "candidates")

    assert next_experiment_index({"last_experiment": 0}) == 1


@pytest.mark.parametrize("existing", ["experiment-5", "recovery-experiment-5"])
def test_unexpected_experiment_data_is_preserved_and_its_identity_skipped(
    monkeypatch, tmp_path, capsys, existing
):
    candidates = tmp_path / "candidates"
    (candidates / existing).mkdir(parents=True)
    (candidates / existing / "model.zip").write_bytes(b"earlier experiment")
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", candidates)

    assert next_experiment_index({"last_allocated_experiment": 4}) == 6
    assert (candidates / existing / "model.zip").read_bytes() == b"earlier experiment"
    assert "skipping that identity" in capsys.readouterr().out


def test_recovery_keeps_the_identity_its_interrupted_run_allocated(tmp_path):
    state = {"last_experiment": 4, "last_allocated_experiment": 5}

    assert resumed_experiment_index(state, tmp_path / "recovery-experiment-5") == 5
    assert resumed_experiment_index(state, None) == 5
    # A state file written before allocation existed still recovers experiment 5.
    assert (
        resumed_experiment_index(
            {"last_experiment": 4}, tmp_path / "recovery-experiment-5"
        )
        == 5
    )


def test_an_invalid_experiment_consumes_its_identity(monkeypatch, tmp_path, capsys):
    state_path = _allocation_campaign(monkeypatch, tmp_path, {"last_experiment": 4})
    proposal_path = tmp_path / "proposal.json"
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    proposal_path.write_text(json.dumps(_rejected_proposal()), encoding="utf-8")
    assert main() == 1
    assert "experiment 5 invalid" in capsys.readouterr().out
    assert _allocated(state_path) == 5

    # A fresh Runner invocation reloads the persisted state; 5 is spent for good.
    proposal_path.write_text(json.dumps(_rejected_proposal()), encoding="utf-8")
    assert main() == 1
    assert "experiment 6 invalid" in capsys.readouterr().out
    assert _allocated(state_path) == 6
    recorded = [
        json.loads(line)["index"]
        for line in (tmp_path / "results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert recorded == [5, 6]


@pytest.mark.parametrize("mechanism", ["restart", "recovery"])
def test_a_resumed_experiment_reuses_its_allocated_identity(
    monkeypatch, tmp_path, capsys, mechanism
):
    state_path = _allocation_campaign(
        monkeypatch,
        tmp_path,
        {"last_experiment": 4, "last_allocated_experiment": 5},
    )
    (tmp_path / "proposal.json").write_text(
        json.dumps(_rejected_proposal()), encoding="utf-8"
    )
    argv = ["run_experiment.py"]
    if mechanism == "restart":
        (tmp_path / "RESTART_PENDING").write_text("restart\n", encoding="utf-8")
    else:
        recovery = tmp_path / "models" / "candidates" / "recovery-experiment-5"
        recovery.mkdir(parents=True)
        argv += ["--reuse-candidate", str(recovery)]
    monkeypatch.setattr("sys.argv", argv)

    assert main() == 1
    assert "experiment 5 invalid" in capsys.readouterr().out
    assert _allocated(state_path) == 5


def test_a_pending_phase_proposal_allocates_no_identity(monkeypatch, tmp_path, capsys):
    state_path = _allocation_campaign(
        monkeypatch,
        tmp_path,
        {"last_experiment": 4, "pending_evaluation_request": {"experiment": 4}},
    )
    (tmp_path / "proposal.json").write_text(
        json.dumps(_rejected_proposal()), encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    assert main() == 1
    assert "invalid proposal for current phase" in capsys.readouterr().out
    assert _allocated(state_path) is None


def test_runner_state_is_never_a_researcher_change(monkeypatch):
    monkeypatch.setattr(
        "research.runner_repository.status_paths",
        lambda paths: (
            [
                "research/research_state.json",
                "robot_learning/scenario/reward.py",
            ]
            if paths
            else []
        ),
    )

    assert assert_research_surface() == ["robot_learning/scenario/reward.py"]


# --- candidate manifest ----------------------------------------------------


def test_candidate_manifest_preserves_identity_and_complete_artifacts(tmp_path):
    finalists = []
    for number in range(3):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append(
            {
                "name": f"candidate-{number}",
                "timesteps": number * 100,
                "path": relative,
                "training_success": 0.0,
                "ep_rew_mean": 1.0,
            }
        )
    (tmp_path / "candidate_manifest.json").write_text(
        json.dumps({"candidates": finalists}), encoding="utf-8"
    )

    candidates = candidate_directories(tmp_path)

    assert [item["name"] for item in candidates] == [
        "candidate-0",
        "candidate-1",
        "candidate-2",
    ]
    assert [item["timesteps"] for item in candidates] == [0, 100, 200]
    assert [item["path"] for item in candidates] == [
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
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    monkeypatch.setattr(
        "research.runner_repository.git", lambda *args: "base-commit\n"
    )
    committed = []

    def record_lineage_commit(*args, **kwargs):
        del kwargs
        committed.append(args)

    monkeypatch.setattr(
        "research.runner_repository.commit_lineage_decision", record_lineage_commit
    )

    def fail_if_training_starts(*args, **kwargs):
        del args, kwargs
        pytest.fail("next experiment trained too early")

    monkeypatch.setattr(
        "research.runner_execution.train_candidate",
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
        "robot_learning.scenario.evaluate_final_model", evaluate_after_commit
    )
    from research.run_experiment import execute_pending_final_benchmark

    assert execute_pending_final_benchmark() == 0


# --- scientific parent and path-scoped rollback ----------------------------

SCIENCE = "robot_learning/scenario/reward.py"
OTHER_SCIENCE = "robot_learning/training/normalization.py"
MEMORY = "research/results.jsonl"
PARAMS = "research/current_params.json"


def _git(work: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=work, capture_output=True, text=True, check=True
    ).stdout


def _write(work: Path, path: str, text: str) -> None:
    target = work / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit(work: Path, message: str) -> str:
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", message)
    return _head(work)


def _head(work: Path) -> str:
    return _git(work, "rev-parse", "HEAD").strip()


def _subjects(work: Path) -> list[str]:
    return _git(work, "log", "--format=%s").splitlines()


def _files_of(work: Path, revision: str) -> list[str]:
    return _git(work, "show", "--name-only", "--format=", revision).split()


def _anchored_parent(work: Path) -> str | None:
    state = json.loads(
        (work / "research" / "research_state.json").read_text(encoding="utf-8")
    )
    return state.get("pending_scientific_parent")


@pytest.fixture
def science_repo(monkeypatch, tmp_path):
    """A real repository with an origin, so rollback is exercised, not simulated."""

    subprocess.run(
        ["git", "init", "--bare", "-q", str(tmp_path / "origin.git")], check=True
    )
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "runner@example.invalid")
    _git(work, "config", "user.name", "runner")
    _git(work, "remote", "add", "origin", str(tmp_path / "origin.git"))
    _write(work, ".gitignore", "archive/\nmodels/\n")
    _write(work, SCIENCE, "parent reward\n")
    _write(work, PARAMS, '{"method": {"rate": 1}}\n')
    _write(work, MEMORY, '{"index": 1}\n')
    _write(work, "research/research_state.json", json.dumps({"schema_version": 2}))
    _commit(work, "accepted science")
    _git(work, "push", "-q", "-u", "origin", "main")
    monkeypatch.setattr("research.runner_paths.ROOT", work)
    monkeypatch.setattr(
        "research.runner_paths.STATE_PATH", work / "research" / "research_state.json"
    )
    return work


def test_the_scientific_parent_predates_every_researcher_commit(science_repo):
    accepted = _head(science_repo)

    assert begin_hypothesis_phase() == 0
    _write(science_repo, SCIENCE, "researcher commit B\n")

    assert _commit(science_repo, "researcher commit B") != accepted
    assert _anchored_parent(science_repo) == accepted


def test_an_unfinished_researcher_phase_keeps_its_scientific_parent(science_repo):
    accepted = _head(science_repo)
    begin_hypothesis_phase()
    _write(science_repo, SCIENCE, "first attempt\n")
    _commit(science_repo, "researcher commit B")

    # A retry, a launcher restart and the experiment itself all re-enter the
    # same unfinished phase, and none of them recaptures HEAD.
    begin_hypothesis_phase()
    begin_hypothesis_phase()
    state = json.loads(
        (science_repo / "research" / "research_state.json").read_text(encoding="utf-8")
    )

    assert _anchored_parent(science_repo) == accepted
    assert anchor_scientific_parent(state) == accepted


def test_a_rejected_experiment_leaves_its_science_in_the_next_delta(science_repo):
    accepted = _head(science_repo)
    begin_hypothesis_phase()
    _write(science_repo, SCIENCE, "preserved after rejection\n")
    _commit(science_repo, "researcher commit B")
    state = json.loads(
        (science_repo / "research" / "research_state.json").read_text(encoding="utf-8")
    )

    assert anchor_scientific_parent(state) == accepted
    assert scientific_delta(accepted) == [SCIENCE]


def test_committed_researcher_changes_stay_in_the_experiment_delta(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, SCIENCE, "committed change\n")
    _commit(science_repo, "researcher commit B")

    assert _git(science_repo, "status", "--porcelain").strip() == ""
    assert scientific_delta(accepted) == [SCIENCE]


def test_several_researcher_commits_form_one_experiment_delta(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, SCIENCE, "first\n")
    _commit(science_repo, "researcher commit B")
    _write(science_repo, "robot_learning/scenario/observations.py", "second\n")
    _commit(science_repo, "researcher commit C")
    _write(science_repo, OTHER_SCIENCE, "still dirty\n")

    assert sorted(scientific_delta(accepted)) == [
        "robot_learning/scenario/observations.py",
        SCIENCE,
        OTHER_SCIENCE,
    ]


def test_a_committed_protected_change_cannot_bypass_validation(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, "robot_learning/robots/two_joint_arm.xml", "<mujoco/>\n")
    _commit(science_repo, "researcher commit touching the official robot")
    delta = scientific_delta(accepted)

    assert _git(science_repo, "status", "--porcelain").strip() == ""
    with pytest.raises(ValueError, match="human-owned task, context") as rejection:
        validate_experiment_semantics({}, "training", "transfer", None, delta, False)
    assert "robot_learning/robots/two_joint_arm.xml" in str(rejection.value)
    assert "scientific parent" in str(rejection.value)


def test_a_committed_protected_test_cannot_bypass_validation(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, "tests/autoresearch/test_smuggled_rule.py", "assert True\n")
    _commit(science_repo, "researcher commit inventing a protocol rule")
    delta = scientific_delta(accepted)

    with pytest.raises(ValueError, match="human-owned .* tests") as rejection:
        validate_experiment_semantics({}, "training", "transfer", None, delta, False)
    assert "tests/autoresearch/test_smuggled_rule.py" in str(rejection.value)
    assert "scientific parent" in str(rejection.value)


def test_keep_preserves_every_researcher_commit_and_commits_what_is_left(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, SCIENCE, "commit B reward\n")
    first = _commit(science_repo, "researcher commit B")
    _write(science_repo, "robot_learning/scenario/observations.py", "commit C\n")
    second = _commit(science_repo, "researcher commit C")
    _write(science_repo, OTHER_SCIENCE, "final adjustment\n")
    _write(science_repo, MEMORY, '{"index": 1}\n{"index": 2}\n')

    plan = plan_code_lineage_decision(
        {"code_parent_commit": accepted, "research_change_paths": [SCIENCE]}, "keep"
    )
    apply_code_lineage_decision({**plan, "parent": accepted})
    commit_lineage_decision(4, "checkpoint-1", code_action="keep")

    history = _git(science_repo, "log", "--format=%H").split()
    assert history[-3:] == [second, first, accepted]
    assert (science_repo / SCIENCE).read_text(encoding="utf-8") == "commit B reward\n"
    assert (science_repo / OTHER_SCIENCE).read_text(encoding="utf-8") == (
        "final adjustment\n"
    )
    assert _subjects(science_repo)[:2] == [
        "select experiment 4 lineage: checkpoint-1",
        "experiment 4 code retained for checkpoint-1",
    ]
    assert _files_of(science_repo, "HEAD~1") == [OTHER_SCIENCE]
    assert _files_of(science_repo, "HEAD") == [MEMORY]


def test_revert_restores_committed_and_uncommitted_science_of_every_kind(science_repo):
    _write(science_repo, "robot_learning/scenario/observations.py", "parent view\n")
    _write(science_repo, "robot_learning/scenario/legacy.py", "parent legacy\n")
    accepted = _commit(science_repo, "more accepted science")
    _write(science_repo, SCIENCE, "experiment reward\n")
    _write(science_repo, "robot_learning/scenario/created.py", "created here\n")
    _commit(science_repo, "researcher commit B")
    (science_repo / "robot_learning" / "scenario" / "observations.py").unlink()
    _git(
        science_repo,
        "mv",
        "robot_learning/scenario/legacy.py",
        "robot_learning/scenario/renamed.py",
    )
    _commit(science_repo, "researcher commit C")
    _write(science_repo, OTHER_SCIENCE, "dirty and uncommitted\n")
    _write(science_repo, PARAMS, '{"method": {"rate": 2}}\n')

    plan = plan_code_lineage_decision(
        {"code_parent_commit": accepted, "research_change_paths": []},
        "revert",
        current_paths=scientific_delta(accepted),
    )
    apply_code_lineage_decision({**plan, "parent": accepted})

    def content(path: str) -> str:
        return (science_repo / path).read_text(encoding="utf-8")

    assert content(SCIENCE) == "parent reward\n"
    assert content("robot_learning/scenario/observations.py") == "parent view\n"
    assert content("robot_learning/scenario/legacy.py") == "parent legacy\n"
    assert json.loads(content(PARAMS)) == {"method": {"rate": 1}}
    for absent in (
        "robot_learning/scenario/renamed.py",
        "robot_learning/scenario/created.py",
        OTHER_SCIENCE,
    ):
        assert not (science_repo / absent).exists()


def test_a_scientific_revert_moves_history_forward_and_spares_runner_memory(
    science_repo,
):
    accepted = _head(science_repo)
    _write(science_repo, SCIENCE, "experiment reward\n")
    science_commit = _commit(science_repo, "researcher commit B")
    _write(science_repo, MEMORY, '{"index": 1}\n{"index": 2}\n')
    _write(science_repo, "research/evaluations/evaluation-experiment-2.json", "{}\n")
    memory_commit = _commit(science_repo, "exp 2: record campaign memory")
    _write(science_repo, SCIENCE, "later adjustment\n")
    _write(science_repo, "research/postmortems.md", "## Experiment 2\n")

    plan = plan_code_lineage_decision(
        {"code_parent_commit": accepted, "research_change_paths": [SCIENCE, MEMORY]},
        "revert",
        current_paths=scientific_delta(accepted),
    )
    apply_code_lineage_decision({**plan, "parent": accepted})
    commit_lineage_decision(2, "champion", code_action="revert")

    assert plan["restore"] == [SCIENCE]
    assert plan["remove_created"] == []
    assert (science_repo / SCIENCE).read_text(encoding="utf-8") == "parent reward\n"
    # The memory written before, during and after the reverted science survives.
    assert (science_repo / MEMORY).read_text(encoding="utf-8") == (
        '{"index": 1}\n{"index": 2}\n'
    )
    assert (
        science_repo / "research" / "evaluations" / "evaluation-experiment-2.json"
    ).exists()
    assert (science_repo / "research" / "postmortems.md").read_text(
        encoding="utf-8"
    ) == "## Experiment 2\n"
    history = _git(science_repo, "log", "--format=%H").split()
    assert history[-3:] == [memory_commit, science_commit, accepted]
    assert _subjects(science_repo)[:2] == [
        "select experiment 2 lineage: champion",
        "experiment 2 code reverted to its scientific parent",
    ]
    assert _files_of(science_repo, "HEAD~1") == [SCIENCE]
    assert MEMORY not in _files_of(science_repo, "HEAD~1")


def test_parameter_configuration_follows_the_scientific_rollback(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, PARAMS, '{"method": {"rate": 2}}\n')
    _commit(science_repo, "researcher commit tuning the active method")
    pending = {"code_parent_commit": accepted, "research_change_paths": [PARAMS]}

    assert scientific_delta(accepted) == [PARAMS]
    apply_code_lineage_decision(
        {**plan_code_lineage_decision(pending, "keep"), "parent": accepted}
    )
    assert json.loads((science_repo / PARAMS).read_text(encoding="utf-8")) == {
        "method": {"rate": 2}
    }

    apply_code_lineage_decision(
        {**plan_code_lineage_decision(pending, "revert"), "parent": accepted}
    )
    assert json.loads((science_repo / PARAMS).read_text(encoding="utf-8")) == {
        "method": {"rate": 1}
    }


def test_an_unresolvable_scientific_parent_stops_the_rollback(science_repo):
    with pytest.raises(RuntimeError, match="no longer resolves"):
        plan_code_lineage_decision(
            {"code_parent_commit": "0" * 40, "research_change_paths": [SCIENCE]},
            "revert",
        )


def test_a_closed_lineage_releases_the_scientific_parent(monkeypatch, science_repo):

    candidate = science_repo / "archive" / "candidate-1"
    candidate.mkdir(parents=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (candidate / filename).write_bytes(b"artifact")
    monkeypatch.setattr(
        "research.runner_paths.ACCEPTED_DIR",
        science_repo / "research" / "checkpoints" / "accepted",
    )
    monkeypatch.setattr(
        "research.runner_paths.GOAL_PATH", science_repo / "GOAL_REACHED"
    )
    accepted = _head(science_repo)
    begin_hypothesis_phase()
    _write(science_repo, SCIENCE, "experiment reward\n")
    _commit(science_repo, "researcher commit B")
    state = json.loads(
        (science_repo / "research" / "research_state.json").read_text(encoding="utf-8")
    )
    state.update(
        {
            "accepted_artifact": "accepted",
            "accepted_training_steps": 0,
            "pending_researcher_decision": {
                "experiment": 7,
                "candidates": [
                    {
                        "name": "candidate-1",
                        "artifact": "archive/candidate-1",
                        "summary": None,
                    }
                ],
                "champion_available": False,
                "parameters": {},
                "initialization": "fresh",
                "training_budget_steps": 100,
                # The runner recomputes the delta, so the frozen list is stale.
                "code_parent_commit": accepted,
                "research_change_paths": [],
            },
        }
    )

    assert not apply_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 7,
                "continue_from": "candidate-1",
                "reason": "The measured lineage is the useful one.",
                "code": {
                    "action": "revert",
                    "reason": "The intervention did not earn its complexity.",
                },
            }
        },
        state,
    )

    assert (science_repo / SCIENCE).read_text(encoding="utf-8") == "parent reward\n"
    # Changing the working tree is not closing the lineage: the anchor survives
    # until the restored science is committed and published.
    assert state["pending_scientific_parent"] == accepted
    assert _anchored_parent(science_repo) == accepted

    commit_lineage_decision(7, "candidate-1", code_action="revert", state=state)

    assert state["pending_scientific_parent"] is None
    assert _anchored_parent(science_repo) is None
    assert _files_of(science_repo, "HEAD~1") == [SCIENCE]


def test_an_unpublished_scientific_commit_keeps_the_scientific_parent(
    monkeypatch, science_repo
):

    accepted = _head(science_repo)
    begin_hypothesis_phase()
    _write(science_repo, SCIENCE, "experiment reward\n")
    state = json.loads(
        (science_repo / "research" / "research_state.json").read_text(encoding="utf-8")
    )

    def unpublishable(message, paths=()):
        del message, paths
        raise RuntimeError("commit created locally but push to origin failed")

    monkeypatch.setattr("research.runner_repository.commit_and_push", unpublishable)

    with pytest.raises(RuntimeError, match="push to origin failed"):
        commit_lineage_decision(7, "candidate-1", code_action="keep", state=state)

    # The experiment stays recoverable: its rollback baseline never moved.
    assert state["pending_scientific_parent"] == accepted
    assert _anchored_parent(science_repo) == accepted


def test_a_keep_decision_never_plans_a_restoration(science_repo):
    accepted = _head(science_repo)
    _write(science_repo, SCIENCE, "experiment reward\n")
    _commit(science_repo, "researcher commit B")
    state = {
        "accepted_artifact": "accepted",
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [{"name": "candidate-1", "artifact": "archive/candidate-1"}],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 100,
            "code_parent_commit": accepted,
            "research_change_paths": [SCIENCE],
        },
    }
    candidate = science_repo / "archive" / "candidate-1"
    candidate.mkdir(parents=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (candidate / filename).write_bytes(b"artifact")

    plan = plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 7,
                "continue_from": "candidate-1",
                "reason": "The measured lineage is the useful one.",
                "code": {"action": "keep", "reason": "The mechanism earned its place."},
            }
        },
        state,
    )

    assert plan["code_plan"] == {
        "restore": [],
        "remove_created": [],
        "parent": accepted,
    }
    assert (science_repo / SCIENCE).read_text(encoding="utf-8") == "experiment reward\n"
