"""The human-owned task-reference panel.

These tests protect a development measurement of the original human-defined
task: stable across experiments, independent of researcher-owned task mechanics,
and never an objective verdict. They also protect the fact that adding this
capability leaves the final benchmark untouched. They are immutable during a
research campaign and stay independent of any concrete learning method.
"""

import ast
from pathlib import Path

import numpy as np
import pytest

from research.runner_protocol import (
    TASK_REFERENCE_ENTRY_FIELDS,
    task_reference_artifact_name,
    validate_evaluation_request,
    validate_experiment_semantics,
)
from robot_learning.benchmark import final_contract, reference_contract
from robot_learning.benchmark.reference_evaluation import (
    TaskReferenceEnv,
    evaluate_task_reference_model,
    task_reference_panel,
)

ROOT = Path(__file__).resolve().parents[2]

PROTECTED_REFERENCE_PATHS = (
    "robot_learning/benchmark/reference_contract.py",
    "robot_learning/benchmark/reference_evaluation.py",
    "robot_learning/scenario/task_reference.py",
)


class StillPolicy:
    """A policy that never moves, so panels can be compared without training."""

    def predict(self, observation, deterministic=True):
        del observation, deterministic
        return np.zeros(2), None


def panel_targets(episodes: int, seed: int) -> list[tuple[float, float]]:
    env = TaskReferenceEnv()
    targets = []
    for episode in range(episodes):
        env.reset(seed=seed + episode)
        position = env.data.mocap_pos[0]
        targets.append((float(position[0]), float(position[1])))
    return targets


def stub_policy_loading(monkeypatch) -> None:
    monkeypatch.setattr(
        "robot_learning.benchmark.reference_evaluation.load_policy",
        lambda model_path, algorithm=None: StillPolicy(),
    )
    monkeypatch.setattr(
        "robot_learning.benchmark.reference_evaluation.load_observation_normalizer",
        lambda model_path: None,
    )


def test_reference_panel_is_fixed_and_human_owned():
    panel = task_reference_panel()

    assert panel["panel"] == reference_contract.PANEL_ID
    assert panel["panel_version"] == reference_contract.PANEL_VERSION
    assert panel["episodes"] == reference_contract.EVALUATION_EPISODES
    assert panel["seed"] == reference_contract.EVALUATION_SEED
    assert panel["episodes"] > 0


def test_reference_panel_is_not_the_final_benchmark_panel():
    assert reference_contract.EVALUATION_SEED != final_contract.EVALUATION_SEED
    assert panel_targets(16, reference_contract.EVALUATION_SEED) != panel_targets(
        16, final_contract.EVALUATION_SEED
    )


def test_reference_task_matches_the_protected_task_definition():
    env = TaskReferenceEnv()
    control_dt = env.model.opt.timestep * env.frame_skip

    assert env.success_threshold == pytest.approx(final_contract.SUCCESS_THRESHOLD)
    assert env.target_radius_range == final_contract.TARGET_RADIUS_RANGE
    assert env.frame_skip == final_contract.FRAME_SKIP
    assert env.max_episode_steps == final_contract.MAX_EPISODE_STEPS
    assert env.hold_steps_required == round(final_contract.HOLD_SECONDS / control_dt)
    assert np.array_equal(env.action_space.low, -np.ones(2))
    assert np.array_equal(env.action_space.high, np.ones(2))


def test_reference_reset_restores_the_original_initial_state():
    env = TaskReferenceEnv()
    env.reset(seed=reference_contract.EVALUATION_SEED)
    env.step(np.ones(2))
    env.reset(seed=reference_contract.EVALUATION_SEED)

    assert np.allclose(env.data.qpos, 0.0)
    assert np.allclose(env.data.qvel, 0.0)
    # The planar arm and its target must share a plane for the distance to reach 0.
    assert env.data.mocap_pos[0][2] == pytest.approx(
        float(env.data.site("end_effector").xpos[2])
    )


def test_reference_hold_requires_the_complete_uninterrupted_hold():
    env = TaskReferenceEnv()
    env.reset(seed=reference_contract.EVALUATION_SEED)
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()

    for step in range(env.hold_steps_required):
        _, _, terminated, truncated, _ = env.step(np.zeros(2))
        assert not truncated
        assert terminated is (step == env.hold_steps_required - 1)


def test_reference_hold_restarts_after_leaving_tolerance():
    env = TaskReferenceEnv()
    env.reset(seed=reference_contract.EVALUATION_SEED)
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    for _ in range(env.hold_steps_required - 1):
        env.step(np.zeros(2))

    env.data.mocap_pos[0] = env.data.mocap_pos[0] + np.array([0.05, 0.0, 0.0])
    _, _, terminated, _, info = env.step(np.zeros(2))

    assert terminated is False
    assert info["held_steps"] == 0


def test_reference_truncates_at_the_original_horizon(monkeypatch):
    env = TaskReferenceEnv()
    env.reset(seed=reference_contract.EVALUATION_SEED)
    monkeypatch.setattr(env, "_distance_to_target", lambda: 1.0)

    for step in range(env.max_episode_steps):
        _, _, terminated, truncated, _ = env.step(np.zeros(2))
        assert not terminated
        assert truncated is (step == env.max_episode_steps - 1)


def test_reference_panel_keeps_the_original_uniform_radius_semantics():
    low, high = final_contract.TARGET_RADIUS_RANGE
    radii = [
        float(np.hypot(x, y))
        for x, y in panel_targets(
            reference_contract.EVALUATION_EPISODES, reference_contract.EVALUATION_SEED
        )
    ]

    assert all(low <= radius <= high for radius in radii)
    assert float(np.mean(radii)) == pytest.approx((low + high) / 2, abs=0.01)


def test_reference_angles_cover_the_original_full_range():
    angles = [
        float(np.arctan2(y, x))
        for x, y in panel_targets(
            reference_contract.EVALUATION_EPISODES, reference_contract.EVALUATION_SEED
        )
    ]

    assert min(angles) < -np.pi / 2
    assert max(angles) > np.pi / 2


def test_reference_panel_is_deterministic():
    assert panel_targets(16, reference_contract.EVALUATION_SEED) == panel_targets(
        16, reference_contract.EVALUATION_SEED
    )


def test_candidate_and_champion_run_the_same_cases(monkeypatch, tmp_path):
    monkeypatch.setattr(reference_contract, "EVALUATION_EPISODES", 3)
    stub_policy_loading(monkeypatch)
    candidate = tmp_path / "candidate.zip"
    champion = tmp_path / "champion.zip"
    candidate.write_bytes(b"candidate")
    champion.write_bytes(b"champion")

    def cases(model_path):
        return [
            (
                item["episode_seed"],
                item["target_radius_cm"],
                item["target_angle_degrees"],
            )
            for item in evaluate_task_reference_model(model_path)["episode_results"]
        ]

    assert cases(candidate) == cases(champion)


def test_reference_evaluation_is_factual_and_declares_no_success(monkeypatch, tmp_path):
    monkeypatch.setattr(reference_contract, "EVALUATION_EPISODES", 2)
    stub_policy_loading(monkeypatch)
    model_path = tmp_path / "model.zip"
    model_path.write_bytes(b"model")

    result = evaluate_task_reference_model(model_path)

    assert result["evaluation_kind"] == "task_reference"
    assert result["official_benchmark"] is False
    assert "goal_reached" not in result
    assert "research_evidence" not in result
    assert result["panel"] == reference_contract.PANEL_ID
    assert result["seed"] == reference_contract.EVALUATION_SEED
    assert result["episodes"] == 2
    assert [item["episode_seed"] for item in result["episode_results"]] == [
        reference_contract.EVALUATION_SEED,
        reference_contract.EVALUATION_SEED + 1,
    ]
    for episode in result["episode_results"]:
        assert set(episode) == {
            "episode",
            "episode_seed",
            "target_radius_cm",
            "target_angle_degrees",
            "success",
            "steps",
            "terminated",
            "truncated",
            "final_distance_cm",
        }


def test_reference_evaluation_is_independent_of_researcher_task_code():
    relative = "robot_learning/benchmark/reference_evaluation.py"
    source = (ROOT / relative).read_text(encoding="utf-8")
    imported = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]

    assert "make_training_env" not in source
    for module in imported:
        assert module not in (
            "robot_learning.scenario",
            "robot_learning.scenario.environment",
            "robot_learning.scenario.evaluation",
            "robot_learning.scenario.reward",
        ), f"{relative} imports researcher-owned task mechanics via {module}"


def test_final_benchmark_does_not_depend_on_the_task_reference():
    source = (ROOT / "robot_learning/benchmark/final_benchmark.py").read_text(
        encoding="utf-8"
    )

    assert "reference_contract" not in source
    assert "reference_evaluation" not in source


@pytest.mark.parametrize("protected_path", PROTECTED_REFERENCE_PATHS)
def test_research_proposal_cannot_change_the_task_reference(protected_path):
    with pytest.raises(ValueError, match="human-owned final benchmark"):
        validate_experiment_semantics(
            {}, "training", "transfer", None, [protected_path], False
        )


def _request(**overrides) -> dict:
    request = {
        "experiment": 3,
        "question": "Does the candidate hold as well as the champion?",
        "reason": "A stable comparison decides the lineage question.",
    }
    request.update(overrides)
    return request


def test_request_accepts_research_only_reference_only_and_both():
    research = [{"candidate": "checkpoint-1", "episodes": 10, "seed": 5}]
    reference = [{"candidate": "champion"}]

    validate_evaluation_request(_request(evaluations=research))
    validate_evaluation_request(_request(task_reference_evaluations=reference))
    validate_evaluation_request(
        _request(evaluations=research, task_reference_evaluations=reference)
    )


def test_request_must_ask_for_at_least_one_measurement():
    with pytest.raises(ValueError, match="at least one research or"):
        validate_evaluation_request(_request(evaluations=[]))


@pytest.mark.parametrize(
    "entry",
    [
        {"candidate": "champion", "episodes": 10},
        {"candidate": "champion", "seed": 4},
        {"candidate": "champion", "panel": "custom"},
        {"candidate": "champion", "official_benchmark": True},
    ],
)
def test_request_rejects_researcher_owned_reference_panel_parameters(entry):
    with pytest.raises(ValueError, match="human-owned"):
        validate_evaluation_request(_request(task_reference_evaluations=[entry]))


@pytest.mark.parametrize("entry", [{}, {"candidate": "   "}])
def test_request_rejects_a_reference_evaluation_without_a_model(entry):
    with pytest.raises(ValueError, match="requires a candidate"):
        validate_evaluation_request(_request(task_reference_evaluations=[entry]))


def test_request_rejects_a_malformed_reference_list():
    with pytest.raises(TypeError, match="must be a list"):
        validate_evaluation_request(_request(task_reference_evaluations={}))
    with pytest.raises(TypeError, match="must be an object"):
        validate_evaluation_request(_request(task_reference_evaluations=["champion"]))


def test_reference_entry_fields_stay_minimal():
    assert TASK_REFERENCE_ENTRY_FIELDS == {"candidate", "label"}


def test_reference_artifacts_cannot_collide_with_research_artifacts():
    name = task_reference_artifact_name(3, "champion", "task-reference-v1")

    assert name.startswith("task-reference-experiment-3-champion-")
    assert not name.startswith("evaluation-experiment-")
