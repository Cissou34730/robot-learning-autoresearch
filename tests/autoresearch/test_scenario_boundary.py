"""Architecture guards for the static scenario boundary.

The generic AutoResearch core must depend on `robot_learning.scenario` and
nothing else that is specific to the current research problem. These guards are
human-owned and stay independent of whichever learning method is active.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from research.build_research_brief import render_research_brief
from robot_learning import scenario
from robot_learning.scenario import summarize_research_evaluations
from robot_learning.training import research_config
from robot_learning.training.research_config import load_experiment_config

ROOT = Path(__file__).resolve().parents[2]

SCENARIO_BOUNDARY = (
    "evaluate_final_model",
    "evaluate_research_model",
    "make_training_env",
    "make_training_viewer_callback",
    "render_scenario_evidence",
    "render_training_progress_metric",
    "summarize_research_evaluations",
    "watch_scenario_policy",
)

SCENARIO_EVALUATION_FIELDS = (
    "failed_episode_progress",
    "longest_consecutive_steps",
    "best_window_inside_steps",
    "best_window_excess_cm",
    "distance_trace_cm",
    "target_radius_cm",
    "target_angle_degrees",
    "required_steps",
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
    "research/run_experiment.py",
    "research/build_research_brief.py",
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
        "robot_learning.benchmark.spec",
    }
)

# Only used to assert that generic surfaces name *no* learning algorithm.
KNOWN_ALGORITHM_NAMES = ("ppo", "sac", "td3", "a2c", "ddpg")


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


def test_scenario_exposes_exactly_the_static_boundary():
    assert tuple(sorted(scenario.__all__)) == SCENARIO_BOUNDARY
    exported = {
        name
        for name in vars(scenario)
        if not name.startswith("_") and callable(getattr(scenario, name))
    }
    assert exported == set(SCENARIO_BOUNDARY)


@pytest.mark.parametrize("relative_path", GENERIC_CORE_MODULES)
def test_generic_core_has_no_scenario_specific_imports(relative_path):
    for module in imported_modules(ROOT / relative_path):
        assert module not in FORBIDDEN_MODULES, (
            f"{relative_path} imports scenario-specific module {module}"
        )
        assert not module.startswith("robot_learning.scenario."), (
            f"{relative_path} reaches past the scenario boundary via {module}"
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
            module == "robot_learning.scenario"
            for module in imported_modules(ROOT / path)
        )
    ]
    assert "robot_learning/train.py" in users
    assert "robot_learning/evaluate.py" in users
    assert "research/run_experiment.py" in users
    assert "research/build_research_brief.py" in users


def test_researcher_context_always_includes_both_protocol_and_scenario():
    script = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
    program_lines = [
        line for line in script.splitlines() if "research/program.md" in line
    ]
    assert program_lines
    for line in program_lines:
        assert "research/scenario.md" in line, line


def test_scenario_document_defines_the_current_problem():
    scenario_text = (ROOT / "research" / "scenario.md").read_text(encoding="utf-8")
    program_text = (ROOT / "research" / "program.md").read_text(encoding="utf-8")

    assert "robot_learning/scenario/" in scenario_text
    assert "research/scenario.md" in program_text
    for scenario_fact in ("6–20 cm", "1 cm", "2 seconds", "98%"):
        assert scenario_fact in scenario_text
        assert scenario_fact not in program_text


def test_protocol_uses_scenario_independent_wording():
    program_text = (
        (ROOT / "research" / "program.md").read_text(encoding="utf-8").lower()
    )

    for wording in SCENARIO_WORDING:
        assert wording not in program_text, f"program.md still says {wording!r}"


def test_historical_reward_families_remain_resolvable():
    from research.build_research_brief import _legacy_family

    assert (
        _legacy_family({"change": "increase the closeness reward"})
        == "reward.CLOSENESS_COEFFICIENT"
    )
    assert (
        _legacy_family({"change": "raise the completion bonus"})
        == "reward.HOLD_COMPLETE_BONUS"
    )
    assert (
        _legacy_family({"change": "reduce the action cost"})
        == "reward.ACTION_COST_COEFFICIENT"
    )


def test_live_training_metric_is_owned_by_the_scenario():
    assert scenario.render_training_progress_metric({"success_rate": 0.61}) == (
        "success 61%"
    )
    assert scenario.render_training_progress_metric({"ep_rew_mean": -6.9}) is None


def test_runner_reads_the_live_training_metric_only_through_the_boundary():
    source = (ROOT / "research" / "run_experiment.py").read_text(encoding="utf-8")

    assert "render_training_progress_metric" in source
    assert "success_rate" not in source


def test_another_scenario_metric_needs_no_generic_change(monkeypatch):
    from research import run_experiment

    monkeypatch.setattr(
        run_experiment,
        "render_training_progress_metric",
        lambda metrics: "completion 74%",
    )

    assert run_experiment.training_progress_suffix({"ep_rew_mean": -6.9}) == (
        " | reward -6.9 | completion 74%"
    )


def test_researcher_runtime_output_is_never_parsed():
    script = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
    runner = (ROOT / "research" / "run_experiment.py").read_text(encoding="utf-8")

    assert "opencode run --model $model --variant $reasoning" in script
    assert "--format json" not in script
    for forbidden in ("ConvertFrom-Json $opencode", "Select-String", "Tee-Object"):
        assert forbidden not in script
    assert "opencode" not in runner


def test_compatibility_reexports_alias_the_scenario_implementation():
    from robot_learning.environments.reach_env import TwoJointArmReachEnv
    from robot_learning.rewards.reach_reward import reach_reward
    from robot_learning.scenario import environment, observations, reward
    from robot_learning.training.observations import (
        OBSERVATION_SIZE,
        reach_observation,
    )

    assert TwoJointArmReachEnv is environment.TwoJointArmReachEnv
    assert reach_reward is reward.reach_reward
    assert reach_observation is observations.reach_observation
    assert OBSERVATION_SIZE == observations.OBSERVATION_SIZE


def test_normalization_keeps_its_scenario_import_lazy():
    normalization = ROOT / "robot_learning" / "training" / "normalization.py"
    scenario_evaluation = ROOT / "robot_learning" / "scenario" / "evaluation.py"

    # The scenario depends on this helper, so a module-level import would cycle.
    assert "robot_learning.training.normalization" in module_level_imports(
        scenario_evaluation
    )
    assert "robot_learning.scenario" not in module_level_imports(normalization)
    assert "robot_learning.scenario" in imported_modules(normalization)


@pytest.mark.parametrize("relative_path", GENERIC_CORE_MODULES)
def test_generic_core_does_not_interpret_scenario_evaluation_fields(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    for field in SCENARIO_EVALUATION_FIELDS:
        assert field not in source, f"{relative_path} interprets {field}"


def test_scenario_owns_the_evaluation_summary():
    runner_source = (ROOT / "research" / "run_experiment.py").read_text(
        encoding="utf-8"
    )
    scenario_source = (
        ROOT / "robot_learning" / "scenario" / "evaluation.py"
    ).read_text(encoding="utf-8")

    assert "summarize_research_evaluations" in runner_source
    assert "def summarize_research_evaluations" in scenario_source
    assert "def summarize_evaluations" not in runner_source


def test_task_success_threshold_is_not_generic_configuration():
    config_source = (
        ROOT / "robot_learning" / "training" / "research_config.py"
    ).read_text(encoding="utf-8")
    runner_source = (ROOT / "research" / "run_experiment.py").read_text(
        encoding="utf-8"
    )

    assert "98" not in config_source
    assert "SUCCESS_TARGET" not in config_source
    assert "98" not in runner_source
    assert not hasattr(research_config, "RESEARCH_SUCCESS_TARGET_PERCENT")


def test_scenario_owns_the_current_success_target():
    from robot_learning.benchmark import final_contract
    from robot_learning.scenario import evaluation as scenario_evaluation

    assert scenario_evaluation.FINAL_SUCCESS_PERCENT == 98.0
    assert final_contract.FINAL_SUCCESS_PERCENT == 98.0

    summary = summarize_research_evaluations(
        [
            {
                "episodes": 1,
                "seed": 1,
                "success_percent": 98.0,
                "failed_episode_progress": {
                    "failed_episodes": 0,
                    "longest_consecutive_steps_mean": 100.0,
                    "best_window_inside_steps_mean": 100.0,
                    "best_window_excess_cm_mean": 0.0,
                    "required_steps": 100,
                },
                "episode_results": [],
            },
            {
                "episodes": 1,
                "seed": 2,
                "success_percent": 97.9,
                "failed_episode_progress": {
                    "failed_episodes": 0,
                    "longest_consecutive_steps_mean": 100.0,
                    "best_window_inside_steps_mean": 100.0,
                    "best_window_excess_cm_mean": 0.0,
                    "required_steps": 100,
                },
                "episode_results": [],
            },
        ]
    )

    assert summary["seeds_passing_98_percent"] == 1


def test_persisted_seed_pass_field_stays_readable(monkeypatch, tmp_path):
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
                    "seeds_passing_98_percent": 2,
                    "success_percent": 99.0,
                    "pooled_success_percent": 99.0,
                    "failed_episode_progress": {
                        "failed_episodes": 4,
                        "longest_consecutive_steps_mean": 91.0,
                        "best_window_inside_steps_mean": 95.0,
                        "best_window_excess_cm_mean": 0.1,
                        "required_steps": 100,
                    },
                    "failure_diagnostics": [],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "Accepted seeds passing 98%: 2/2" in brief
    assert "Accepted failed episodes: 4" in brief


def test_scenario_owns_rendering():
    assert not (ROOT / "robot_learning" / "training" / "viewer_callback.py").exists()

    play_source = (ROOT / "robot_learning" / "play.py").read_text(encoding="utf-8")
    train_source = (ROOT / "robot_learning" / "train.py").read_text(encoding="utf-8")
    viewer_source = (ROOT / "robot_learning" / "scenario" / "viewer.py").read_text(
        encoding="utf-8"
    )

    assert "viewer.launch_passive" not in play_source
    assert "viewer.launch_passive" not in train_source
    assert "viewer.launch_passive" in viewer_source
    assert scenario.make_training_viewer_callback(speed=2.0).speed == 2.0


def test_training_environment_carries_no_official_task_enforcement():
    from robot_learning.scenario import environment

    assert not hasattr(environment, "assert_immutable_invariants")

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


def test_scenario_files_participate_in_normal_code_lineage(monkeypatch):
    from research import run_experiment

    monkeypatch.setattr(run_experiment, "ROOT", ROOT)
    monkeypatch.setattr(
        run_experiment, "git", lambda *args: "robot_learning/scenario/reward.py\n"
    )

    plan = run_experiment.plan_code_lineage_decision(
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
