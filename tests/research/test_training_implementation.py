"""The current training implementation is PPO, and only PPO.

These tests pin the *current* method and the protocol's neutrality towards it.
They must not be read as forbidding a future researcher-owned replacement of
the learning algorithm.
"""

import json
import re
from pathlib import Path

import pytest
from stable_baselines3 import PPO

from research.build_research_brief import render_research_brief
from robot_learning import train as train_module
from robot_learning.scenario import make_training_env
from robot_learning.training import algorithms
from robot_learning.training.research_config import (
    load_experiment_config,
    merge_param_overrides,
)

ROOT = Path(__file__).resolve().parents[2]
TRAIN_SOURCE = (ROOT / "robot_learning" / "train.py").read_text(encoding="utf-8")
ALGORITHMS_SOURCE = (ROOT / "robot_learning" / "training" / "algorithms.py").read_text(
    encoding="utf-8"
)
PROGRAM = (ROOT / "research" / "program.md").read_text(encoding="utf-8")
SCENARIO = (ROOT / "research" / "scenario.md").read_text(encoding="utf-8")
LOOP = (ROOT / "run_research.ps1").read_text(encoding="utf-8")

BUILT_IN_TRAINING_SOURCES = (TRAIN_SOURCE, ALGORITHMS_SOURCE)


def mentions(text: str, word: str) -> bool:
    return re.search(rf"\b{word}\b", text, flags=re.IGNORECASE) is not None


# --- current implementation ------------------------------------------------


def test_training_entry_point_uses_ppo_directly():
    assert train_module.PPO is PPO
    assert train_module.ALGORITHM_NAME == "ppo"
    assert "PPO(" in TRAIN_SOURCE
    assert "PPO.load(" in TRAIN_SOURCE


def test_active_configuration_constructs_ppo():
    config = load_experiment_config()
    model = PPO(
        "MlpPolicy",
        make_training_env(),
        policy_kwargs=train_module.build_policy_kwargs(config["policy"]),
        **train_module.parallel_ppo_params(config["ppo"], 1),
    )

    assert isinstance(model, PPO)


def test_built_in_training_implementation_does_not_know_about_sac():
    for source in BUILT_IN_TRAINING_SOURCES:
        assert not mentions(source, "sac"), source[:80]


def test_there_is_no_built_in_algorithm_registry():
    assert not hasattr(algorithms, "ALGORITHMS")
    assert not hasattr(algorithms, "algorithm_class")
    assert "--algorithm" not in TRAIN_SOURCE


def test_replay_buffer_handling_was_removed_with_sac():
    assert "replay_buffer" not in TRAIN_SOURCE


def test_no_multi_algorithm_framework_replaced_the_branching():
    training_package = {
        path.name for path in (ROOT / "robot_learning" / "training").glob("*.py")
    }

    assert training_package == {
        "__init__.py",
        "algorithms.py",
        "candidate_checkpoint_callback.py",
        "comparison.py",
        "normalization.py",
        "observations.py",
        "progress.py",
        "research_config.py",
    }
    for forbidden in (
        "supported_algorithms.json",
        "algorithm_catalog.json",
        "algorithm_registry.py",
        "algorithm_capabilities.json",
    ):
        assert not (ROOT / "research" / forbidden).exists()
        assert not (ROOT / "robot_learning" / "training" / forbidden).exists()


def test_policy_loading_serves_the_current_method_only():
    assert algorithms.load_policy.__module__ == "robot_learning.training.algorithms"
    with pytest.raises(ValueError, match="unsupported algorithm"):
        algorithms.load_policy(Path("missing.zip"), "sac")


# --- current_params.json ---------------------------------------------------


def test_current_params_describes_only_the_active_method():
    config = load_experiment_config()

    assert config["algorithm"]["name"] == "ppo"
    assert config["ppo"]["n_steps"] > 0
    assert set(config) == {"algorithm", "ppo", "policy", "training"}


def test_runtime_overrides_still_merge():
    config = load_experiment_config()
    merged = merge_param_overrides(config, {"ppo": {"learning_rate": 0.0001}})

    assert merged["ppo"]["learning_rate"] == 0.0001
    assert merged["ppo"]["n_steps"] == config["ppo"]["n_steps"]
    assert config["ppo"]["learning_rate"] != 0.0001


# --- default researcher context --------------------------------------------


def test_no_researcher_prompt_forces_the_configuration_into_context():
    assert "research/current_params.json" not in LOOP
    for expected in (
        "research/program.md",
        "research/scenario.md",
        "research/brief.md",
        "research/last_train_summary.md",
    ):
        assert expected in LOOP


def test_protocol_default_context_excludes_the_configuration():
    context_block = PROGRAM.split("## Working context", 1)[1].split("##", 1)[0]
    start_with = context_block.split("Start with:", 1)[1].split("Use this", 1)[0]

    assert "`research/current_params.json`" not in start_with
    assert "`research/last_train_summary.md`" in start_with
    # It stays available on demand, just not pushed into every session.
    assert "`research/current_params.json`" in context_block


# --- research brief --------------------------------------------------------


def test_brief_names_the_method_without_dumping_its_configuration(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text(
        json.dumps(
            {
                "algorithm": {"name": "ppo"},
                "ppo": {"learning_rate": 0.0003, "ent_coef": 0.01},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)
    monkeypatch.setattr(
        "research.build_research_brief.TRAIN_SUMMARY_PATH", tmp_path / "absent.md"
    )

    brief = render_research_brief()

    assert "Current learning method: PPO" in brief
    assert "## Current parameters" not in brief
    assert "learning_rate" not in brief
    assert "ent_coef" not in brief


# --- protocol --------------------------------------------------------------


def test_protocol_treats_the_implementation_as_a_starting_point():
    for statement in (
        "It is a starting point, not part of the problem definition",
        "modify or replace the learning algorithm",
        "is not the set of algorithms you are allowed to consider",
    ):
        assert statement in PROGRAM


def test_protocol_requires_a_mechanism_before_changing_method():
    assert "Poor performance alone is not sufficient evidence" in PROGRAM
    assert "must not be treated as a menu of preferred interventions" in PROGRAM


def test_protocol_offers_no_alternative_algorithm_menu():
    for algorithm_name in ("ppo", "sac", "td3", "a2c", "ddpg"):
        assert not mentions(PROGRAM, algorithm_name), algorithm_name


def test_protocol_no_longer_enumerates_the_configuration_surface():
    assert "overrides to the currently active runtime configuration" in PROGRAM
    assert "`algorithm`, `ppo`, `sac`, `policy`, `training`" not in PROGRAM


def test_protocol_example_is_a_minimal_structural_proposal():
    proposal_example = PROGRAM.split("### Standard training proposal", 1)[1].split(
        "Required:", 1
    )[0]

    assert '"initialization": "fresh"' in proposal_example
    assert "training_parent" not in proposal_example
    assert "training_seed" not in proposal_example
    assert '"params"' not in proposal_example
    for field in ("training_parent", "training_seed", "params"):
        assert field in PROGRAM


# --- scenario --------------------------------------------------------------


def test_scenario_definition_stays_algorithm_independent():
    for algorithm_name in ("ppo", "sac"):
        assert not mentions(SCENARIO, algorithm_name), algorithm_name
    for path in (ROOT / "robot_learning" / "scenario").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for algorithm_name in ("ppo", "sac"):
            assert not mentions(source, algorithm_name), path.name


# --- baseline --------------------------------------------------------------


def test_baseline_protocol_wording_is_algorithm_neutral():
    assert 'change = "Fresh baseline"' in LOOP
    assert not mentions(LOOP, "ppo")
    assert "trains the repository's current unchanged learning method" in PROGRAM
