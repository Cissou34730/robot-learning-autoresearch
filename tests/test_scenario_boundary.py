"""Architecture guards for the static scenario boundary.

The generic AutoResearch core must depend on `robot_learning.scenario` and
nothing else that is specific to the current research problem.
"""

import ast
import json
from pathlib import Path

import pytest

from robot_learning import scenario
from robot_learning.training.research_config import load_experiment_config

ROOT = Path(__file__).resolve().parent.parent

SCENARIO_BOUNDARY = (
    "evaluate_final_model",
    "evaluate_research_model",
    "make_training_env",
    "render_scenario_evidence",
)

GENERIC_CORE_MODULES = (
    "robot_learning/train.py",
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/candidate_checkpoint_callback.py",
    "robot_learning/training/comparison.py",
    "robot_learning/training/normalization.py",
    "robot_learning/training/research_config.py",
    "robot_learning/training/viewer_callback.py",
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

GENERIC_CONFIG_SECTIONS = frozenset({"algorithm", "ppo", "sac", "policy", "training"})


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
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


def test_runtime_configuration_carries_no_reward():
    config = load_experiment_config()
    assert "reward" not in config
    assert set(config) <= GENERIC_CONFIG_SECTIONS

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
