"""Architecture guards for the static scenario boundary.

The generic AutoResearch core must depend on `robot_learning.scenario` and
nothing else that is specific to the current research problem. These guards are
human-owned and stay independent of whichever learning method is active.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from research.build_research_brief import render_research_brief
from robot_learning import scenario
from robot_learning.scenario.evaluation import summarize_research_evaluations
from robot_learning.training import research_config
from robot_learning.training.research_config import load_experiment_config

ROOT = Path(__file__).resolve().parents[2]

# Derived, never listed: a guard must follow the Runner when a responsibility
# moves into a new module instead of silently guarding nothing.
RUNNER_MODULES = (
    "research/run_experiment.py",
    *sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "research").glob("runner_*.py")
    ),
)


def runner_sources() -> dict[str, str]:
    return {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in RUNNER_MODULES
    }


SCENARIO_EVALUATION_FIELDS = (
    "failed_episode_progress",
    "failure_diagnostics",
    "longest_consecutive_steps",
    "best_window_inside_steps",
    "best_window_excess_cm",
    "distance_trace_cm",
    "target_radius_cm",
    "target_angle_degrees",
    "required_steps",
    "reward_components",
    "held_steps",
    # Current reward component names; none of them is a generic contract.
    "closeness",
    "hold_progress",
    "outside_band",
    "hold_complete",
    "action_cost",
)

# Every place a standard research evaluation panel could be re-declared.
RESEARCH_EVALUATION_PANEL_MODULES = (
    "robot_learning/evaluate.py",
    "robot_learning/scenario/evaluation.py",
    "research/build_research_brief.py",
    *RUNNER_MODULES,
)

SCENARIO_WORDING = (
    "physical reachability",
    "reach the target",
    "reaching and holding",
    "hold-duration",
    "hold-stability",
    "target-entry",
    "target geometry",
    "target distribution",
    "near the target",
    "subset of targets",
    "tolerance",
    "end effector",
    "two-joint",
    "mujoco",
)

GENERIC_CORE_MODULES = (
    "robot_learning/train.py",
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/candidate_checkpoint_callback.py",
    "robot_learning/training/comparison.py",
    "robot_learning/training/normalization.py",
    "robot_learning/training/progress.py",
    "robot_learning/training/research_config.py",
    "research/build_research_brief.py",
    *RUNNER_MODULES,
)

FORBIDDEN_MODULES = frozenset(
    {
        "robot_learning.environments.reach_env",
        "robot_learning.rewards.reach_reward",
        "robot_learning.training.observations",
        "robot_learning.robots.two_joint_arm",
        "robot_learning.benchmark",
        "robot_learning.benchmark.final_benchmark",
        "robot_learning.benchmark.final_contract",
        "robot_learning.benchmark.metrics",
        "robot_learning.benchmark.reference_contract",
        "robot_learning.benchmark.reference_evaluation",
        "robot_learning.benchmark.spec",
    }
)
SCENARIO_OWNING_MODULES = frozenset(
    {
        "robot_learning.scenario.environment",
        "robot_learning.scenario.evaluation",
        "robot_learning.scenario.final_benchmark",
        "robot_learning.scenario.progress",
        "robot_learning.scenario.task_reference",
        "robot_learning.scenario.viewer",
    }
)

# Only used to assert that generic surfaces name *no* learning algorithm.
KNOWN_ALGORITHM_NAMES = ("ppo", "sac", "td3", "a2c", "ddpg")

# The scenario package and the protected benchmark import each other through the
# shared observation contract; each must be a valid first import.
IMPORT_CYCLE_ENTRY_POINTS = (
    "robot_learning.benchmark.final_benchmark",
    "robot_learning.benchmark.reference_evaluation",
    "robot_learning.scenario",
    "robot_learning.scenario.final_benchmark",
    "robot_learning.training.observations",
)


def mentions(text: str, word: str) -> bool:
    return re.search(rf"\b{word}\b", text, flags=re.IGNORECASE) is not None


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules.append(node.module)
    return modules


def module_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules.append(node.module)
    return modules


def test_scenario_initializer_exposes_no_scientific_or_protected_api():
    assert not hasattr(scenario, "__all__")
    assert not any(
        name
        in {
            "evaluate_final_model",
            "evaluate_research_model",
            "evaluate_task_reference_model",
            "make_training_env",
            "make_training_viewer_callback",
            "render_training_progress_metric",
            "summarize_research_evaluations",
            "task_reference_panel",
            "watch_scenario_policy",
        }
        for name in vars(scenario)
    )


@pytest.mark.parametrize("relative_path", GENERIC_CORE_MODULES)
def test_generic_core_has_no_scenario_specific_imports(relative_path):
    for module in imported_modules(ROOT / relative_path):
        assert module not in FORBIDDEN_MODULES, (
            f"{relative_path} imports scenario-specific module {module}"
        )
        if module.startswith("robot_learning.scenario"):
            assert module in SCENARIO_OWNING_MODULES, (
                f"{relative_path} uses an unknown scenario import {module}"
            )


@pytest.mark.parametrize("relative_path", GENERIC_CORE_MODULES)
def test_generic_core_has_no_physics_engine_imports(relative_path):
    for module in imported_modules(ROOT / relative_path):
        assert module != "mujoco" and not module.startswith("mujoco."), (
            f"{relative_path} depends on the scenario physics engine via {module}"
        )


def test_generic_core_may_only_use_the_scenario_package():
    users = [
        path
        for path in GENERIC_CORE_MODULES
        if any(
            module.startswith("robot_learning.scenario")
            for module in imported_modules(ROOT / path)
        )
    ]
    assert set(users) == {
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        "research/run_experiment.py",
        "research/runner_console.py",
    }
    for relative_path in users:
        assert all(
            module in SCENARIO_OWNING_MODULES
            for module in imported_modules(ROOT / relative_path)
            if module.startswith("robot_learning.scenario")
        )
    # The compact-context builder needs no scenario code at all.
    assert "research/build_research_brief.py" not in users


def test_every_researcher_session_loads_the_authoritative_context():
    script = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
    program_lines = [
        line for line in script.splitlines() if "research/program.md" in line
    ]
    assert len(program_lines) == 6
    for line in program_lines:
        for context in (
            "AGENTS.md",
            "research/scenario.md",
            "research/instruments.md",
            "research/brief.md",
        ):
            assert context in line, line


def test_scenario_document_defines_the_current_problem():
    scenario_text = (ROOT / "research" / "scenario.md").read_text(encoding="utf-8")
    program_text = (ROOT / "research" / "program.md").read_text(encoding="utf-8")
    instruments_text = (ROOT / "research" / "instruments.md").read_text(
        encoding="utf-8"
    )

    assert "research/scenario.md" in program_text
    for scenario_fact in ("6–20 cm", "1 cm", "2 seconds", "98%"):
        assert scenario_fact in scenario_text
        assert scenario_fact not in program_text
        assert scenario_fact not in instruments_text
    for repository_path in ("research/run_experiment.py", "tests/benchmark/"):
        assert repository_path not in scenario_text


def test_protocol_uses_scenario_independent_wording():
    program_text = (
        (ROOT / "research" / "program.md").read_text(encoding="utf-8").lower()
    )

    for wording in SCENARIO_WORDING:
        assert wording not in program_text, f"program.md still says {wording!r}"


def test_the_repository_has_a_single_research_brief():
    assert not (ROOT / "robot_learning" / "scenario" / "brief.py").exists()
    assert (ROOT / "robot_learning" / "scenario" / "progress.py").exists()


def test_research_evaluation_panel_is_a_single_orchestration_setting():
    literal = re.compile(rf"\b{research_config.RESEARCH_EVALUATION_EPISODES}\b")
    for relative_path in RESEARCH_EVALUATION_PANEL_MODULES:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert not literal.search(source), (
            f"{relative_path} duplicates the standard evaluation panel size"
        )

    assert "default=RESEARCH_EVALUATION_EPISODES" in (
        ROOT / "robot_learning" / "evaluate.py"
    ).read_text(encoding="utf-8")
    assert any(
        "episodes: int = RESEARCH_EVALUATION_EPISODES" in source
        for source in runner_sources().values()
    )


def test_the_brief_imposes_no_hypothesis_taxonomy():
    import research.build_research_brief as brief_builder

    assert not hasattr(brief_builder, "_legacy_family")
    source = (ROOT / "research" / "build_research_brief.py").read_text(encoding="utf-8")
    assert "Tested hypothesis families" not in source
    assert "failure diagnostics" not in source.lower()


def test_runner_reads_the_live_training_metric_only_through_the_boundary():
    sources = runner_sources()

    assert any(
        "render_training_progress_metric" in source for source in sources.values()
    )
    for relative, source in sources.items():
        assert "success_rate" not in source, relative


def test_another_scenario_metric_needs_no_generic_change(monkeypatch):
    from research import runner_console

    monkeypatch.setattr(
        "robot_learning.scenario.progress.render_training_progress_metric",
        lambda metrics: "completion 74%",
    )

    assert runner_console.training_progress_suffix({"ep_rew_mean": -6.9}) == (
        " | -6.9 | 74%"
    )


def test_researcher_runtime_output_is_never_parsed():
    script = (ROOT / "run_research.ps1").read_text(encoding="utf-8")

    assert "uv run --group researcher python researcher_copilot.py" in script
    assert "--format json" not in script
    for forbidden in ("ConvertFrom-Json $researcher", "Select-String", "Tee-Object"):
        assert forbidden not in script
    # The Runner may name the adapter as a path it protects, but must never
    # import it, drive it, or read what it printed.
    for relative, source in runner_sources().items():
        assert "subprocess" not in source or "researcher_copilot" not in source, (
            relative
        )
        for module in imported_modules(ROOT / relative):
            assert module != "researcher_copilot", relative
            assert module != "copilot" and not module.startswith("copilot."), relative


def test_normalization_never_reaches_for_the_scenario():
    normalization = ROOT / "robot_learning" / "training" / "normalization.py"
    scenario_evaluation = ROOT / "robot_learning" / "scenario" / "evaluation.py"

    # The scenario depends on this helper, so any import back would cycle.
    assert "robot_learning.policy_runtime" in module_level_imports(scenario_evaluation)
    assert "robot_learning.scenario" not in imported_modules(normalization)
    # Rebuilding policy preprocessing must not construct the training environment.
    assert "make_training_env" not in normalization.read_text(encoding="utf-8")


@pytest.mark.parametrize("module_name", IMPORT_CYCLE_ENTRY_POINTS)
def test_scenario_and_benchmark_import_in_any_order(module_name):
    """A fresh interpreter, so no suite may depend on pytest collection order."""
    completed = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr[-2000:]


@pytest.mark.parametrize("relative_path", GENERIC_CORE_MODULES)
def test_generic_core_does_not_interpret_scenario_evaluation_fields(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    for field in SCENARIO_EVALUATION_FIELDS:
        assert field not in source, f"{relative_path} interprets {field}"


def test_scenario_owns_the_evaluation_summary():
    sources = runner_sources()
    scenario_source = (
        ROOT / "robot_learning" / "scenario" / "evaluation.py"
    ).read_text(encoding="utf-8")

    assert any(
        "summarize_research_evaluations" in source for source in sources.values()
    )
    assert "def summarize_research_evaluations" in scenario_source
    for relative, source in sources.items():
        assert "def summarize_evaluations" not in source, relative


def test_task_success_threshold_is_not_generic_configuration():
    config_source = (
        ROOT / "robot_learning" / "training" / "research_config.py"
    ).read_text(encoding="utf-8")

    assert "98" not in config_source
    assert "SUCCESS_TARGET" not in config_source
    for relative, source in runner_sources().items():
        assert "98" not in source, relative
    assert not hasattr(research_config, "RESEARCH_SUCCESS_TARGET_PERCENT")


def test_ordinary_research_evaluation_ignores_the_final_threshold():
    import robot_learning.scenario.evaluation as scenario_evaluation
    from robot_learning.benchmark import final_contract

    assert final_contract.FINAL_SUCCESS_PERCENT == 98.0
    assert not hasattr(scenario_evaluation, "FINAL_SUCCESS_PERCENT")
    for module in imported_modules(
        ROOT / "robot_learning" / "scenario" / "evaluation.py"
    ):
        assert not module.startswith("robot_learning.benchmark"), module

    summary = summarize_research_evaluations(
        [
            {"episodes": 1, "seed": 1, "success_percent": 98.0},
            {"episodes": 1, "seed": 2, "success_percent": 97.9},
        ]
    )

    assert "seeds_passing_98_percent" not in summary
    assert summary["worst_seed_success_percent"] == 97.9


def test_compact_context_states_no_final_threshold(monkeypatch, tmp_path):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps(
            {
                "accepted_artifact": "accepted",
                "accepted_metrics": {
                    "episodes": 400,
                    "seed_count": 2,
                    "success_percent": 99.0,
                    "pooled_success_percent": 99.0,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "Accepted seed panels: 2" in brief
    assert "Accepted success: 99%" in brief
    assert "seeds passing" not in brief.lower()
    # The compact context reports the measured result, not a derived failure count.
    assert "failed episodes" not in brief.lower()


def test_training_environment_carries_no_official_task_enforcement():
    import robot_learning.scenario.environment

    assert not hasattr(
        robot_learning.scenario.environment, "assert_immutable_invariants"
    )

    source = (ROOT / "robot_learning" / "scenario" / "environment.py").read_text(
        encoding="utf-8"
    )
    assert "final_contract" not in source


def test_runtime_configuration_carries_no_reward():
    config = load_experiment_config()
    assert "reward" not in config

    persisted = json.loads(
        (ROOT / "research" / "current_params.json").read_text(encoding="utf-8")
    )
    assert persisted == config


def test_scenario_reward_is_code_not_configuration():
    source = (ROOT / "robot_learning" / "scenario" / "reward.py").read_text(
        encoding="utf-8"
    )

    assert "current_params" not in source
    assert "load_experiment_config" not in source
    assert "research_config" not in source


def test_scenario_definition_stays_algorithm_independent():
    scenario_text = (ROOT / "research" / "scenario.md").read_text(encoding="utf-8")

    for algorithm_name in KNOWN_ALGORITHM_NAMES:
        assert not mentions(scenario_text, algorithm_name), algorithm_name
    for path in (ROOT / "robot_learning" / "scenario").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for algorithm_name in KNOWN_ALGORITHM_NAMES:
            assert not mentions(source, algorithm_name), path.name


def test_every_runner_module_is_human_owned():
    """Splitting the enforcement mechanism must never hand a piece of it away."""
    from research import runner_protocol

    for relative in RUNNER_MODULES:
        assert runner_protocol.is_protected_source(relative), relative
        assert not runner_protocol.is_researcher_owned(relative), relative


def test_scenario_files_participate_in_normal_code_lineage(monkeypatch):
    from research import runner_protocol

    monkeypatch.setattr("research.runner_paths.ROOT", ROOT)
    monkeypatch.setattr(
        "research.runner_repository.git",
        lambda *args: "robot_learning/scenario/reward.py\n",
    )

    plan = runner_protocol.plan_code_lineage_decision(
        {
            "code_parent_commit": "abc123",
            "research_change_paths": [
                "robot_learning/scenario/reward.py",
                "robot_learning/scenario/observations.py",
            ],
        },
        "revert",
    )

    assert plan["restore"] == [
        "robot_learning/scenario/reward.py",
        "robot_learning/scenario/observations.py",
    ]
    assert plan["remove_created"] == []
