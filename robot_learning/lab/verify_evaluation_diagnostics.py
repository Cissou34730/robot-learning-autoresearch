"""Runner-check proposal for research evaluation trajectory diagnostics.

This module is intentionally a small controlled kinematics check.  It does
not evaluate a learned policy or establish scientific validity.
"""

import argparse
import json
from pathlib import Path

import gymnasium as gym
import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario import evaluation as evaluation_module
from robot_learning.scenario.evaluation import build_step_diagnostic
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.scenario.policy_io import make_policy_io


def _reference_jacobian(qpos: np.ndarray) -> np.ndarray:
    q1, q2 = qpos
    q12 = q1 + q2
    return np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ],
        dtype=np.float64,
    )


def _assert_step_shape(step: dict) -> None:
    required = {
        "control_step",
        "distance_cm",
        "held_steps",
        "in_tolerance",
        "qpos_rad",
        "qvel_rad",
        "planar_ee_velocity_cm_s",
        "action",
        "jacobian_singular_values",
        "jacobian_condition_number",
        "joint_limit_margins_rad",
        "joint_limit_margin_rad",
        "elbow_branch",
    }
    missing = required.difference(step)
    assert not missing, f"missing trajectory diagnostic fields: {sorted(missing)}"
    assert len(step["qpos_rad"]) == 2
    assert len(step["qvel_rad"]) == 2
    assert len(step["planar_ee_velocity_cm_s"]) == 2
    assert len(step["action"]) == 2
    assert len(step["jacobian_singular_values"]) == 2
    assert len(step["joint_limit_margins_rad"]) == 2
    for field in (
        "distance_cm",
        "qpos_rad",
        "qvel_rad",
        "planar_ee_velocity_cm_s",
        "action",
        "jacobian_singular_values",
        "joint_limit_margins_rad",
        "joint_limit_margin_rad",
    ):
        assert np.all(np.isfinite(np.asarray(step[field], dtype=np.float64))), field
    condition_number = float(step["jacobian_condition_number"])
    assert np.isfinite(condition_number) or np.isposinf(condition_number)


def _check() -> dict:
    env = make_evaluation_env()
    zero_action = np.zeros(env.action_space.shape, dtype=np.float32)

    first_obs, _ = env.reset(seed=31415)
    first_target = env.data.mocap_pos[0].copy()
    first_initial_state = (env.data.qpos.copy(), env.data.qvel.copy())
    second_obs, _ = env.reset(seed=31415)
    assert np.array_equal(first_obs, second_obs)
    assert np.array_equal(first_target, env.data.mocap_pos[0])
    assert all(
        np.array_equal(before, after)
        for before, after in zip(first_initial_state, (env.data.qpos, env.data.qvel))
    )

    trajectory = []
    for expected_step in range(1, 4):
        _, _, terminated, truncated, info = env.step(zero_action)
        assert not terminated and not truncated
        row = build_step_diagnostic(
            env.model,
            env.data,
            control_step=expected_step,
            distance_cm=100.0 * float(info["distance"]),
            held_steps=int(info["held_steps"]),
            action=env.data.ctrl.copy(),
            in_tolerance=bool(
                float(info["distance"]) <= env.success_threshold
            ),
        )
        _assert_step_shape(row)
        trajectory.append(row)
    assert [row["control_step"] for row in trajectory] == [1, 2, 3]
    assert all(row["action"] == [0.0, 0.0] for row in trajectory)

    qpos = np.asarray([0.35, 0.60], dtype=np.float64)
    qvel = np.asarray([0.20, -0.15], dtype=np.float64)
    env.data.qpos[:] = qpos
    env.data.qvel[:] = qvel
    mujoco.mj_forward(env.model, env.data)
    positive = build_step_diagnostic(
        env.model,
        env.data,
        control_step=4,
        distance_cm=0.0,
        held_steps=0,
        action=zero_action,
        in_tolerance=False,
    )
    _assert_step_shape(positive)
    reference_jacobian = _reference_jacobian(qpos)
    reference_singular_values = np.linalg.svd(
        reference_jacobian, compute_uv=False
    )
    np.testing.assert_allclose(
        positive["jacobian_singular_values"],
        reference_singular_values,
        rtol=1e-12,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        positive["planar_ee_velocity_cm_s"],
        reference_jacobian @ qvel * 100.0,
        rtol=1e-12,
        atol=1e-12,
    )
    expected_margins = np.minimum(
        qpos + np.deg2rad(170.0), np.deg2rad(170.0) - qpos
    )
    np.testing.assert_allclose(
        positive["joint_limit_margins_rad"], expected_margins, atol=1e-12
    )
    assert positive["elbow_branch"] == "open"
    assert np.isfinite(positive["jacobian_condition_number"])
    assert np.isclose(
        positive["jacobian_condition_number"],
        reference_singular_values[0] / reference_singular_values[-1],
        rtol=1e-12,
        atol=1e-12,
    )

    env.data.qpos[1] = -0.60
    mujoco.mj_forward(env.model, env.data)
    negative = build_step_diagnostic(
        env.model,
        env.data,
        control_step=5,
        distance_cm=0.0,
        held_steps=0,
        action=zero_action,
        in_tolerance=False,
    )
    assert negative["elbow_branch"] == "folded"
    env.data.qpos[1] = 0.0
    mujoco.mj_forward(env.model, env.data)
    zero_branch = build_step_diagnostic(
        env.model,
        env.data,
        control_step=6,
        distance_cm=0.0,
        held_steps=0,
        action=zero_action,
        in_tolerance=False,
    )
    assert zero_branch["elbow_branch"] == "open"

    env.data.qvel[:] = 0.0
    mujoco.mj_forward(env.model, env.data)
    rank_loss = build_step_diagnostic(
        env.model,
        env.data,
        control_step=7,
        distance_cm=0.0,
        held_steps=0,
        action=zero_action,
        in_tolerance=False,
    )
    assert rank_loss["jacobian_condition_number"] == float("inf")
    for invalid_condition_number in (float("nan"), float("-inf")):
        invalid_rank_loss = dict(rank_loss)
        invalid_rank_loss["jacobian_condition_number"] = invalid_condition_number
        try:
            _assert_step_shape(invalid_rank_loss)
        except AssertionError:
            pass
        else:
            raise AssertionError(
                "invalid Jacobian condition number was accepted: "
                f"{invalid_condition_number!r}"
            )

    class ZeroRuntime:
        def __init__(self) -> None:
            self.io = make_policy_io()
            self.observation_space = gym.spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(OBSERVATION_SIZE,),
                dtype=np.float32,
            )

        def reset(self) -> None:
            return None

        def predict(self, _obs: np.ndarray) -> np.ndarray:
            return np.zeros(2, dtype=np.float32)

    zero_runtime = ZeroRuntime()
    assert zero_runtime.observation_space.shape == (OBSERVATION_SIZE,)
    assert zero_runtime.observation_space.dtype == np.dtype(np.float32)
    assert np.all(np.isneginf(zero_runtime.observation_space.low))
    assert np.all(np.isposinf(zero_runtime.observation_space.high))
    original_loader = evaluation_module.load_runtime
    evaluation_module.load_runtime = lambda _path, _algorithm: zero_runtime
    try:
        evaluator_output = evaluation_module.evaluate_research_model(
            Path("controlled-policy"), episodes=1, seed=31415
        )
    finally:
        evaluation_module.load_runtime = original_loader
    evaluator_diagnostic = evaluator_output["research_evidence"][
        "episode_diagnostics"
    ][0]
    legacy_diagnostic_fields = {
        "episode",
        "episode_seed",
        "target_radius_cm",
        "target_angle_degrees",
        "min_distance_cm",
        "final_distance_cm",
        "first_reach_step",
        "max_held_steps",
        "in_tolerance_steps",
        "hold_interruptions",
    }
    assert legacy_diagnostic_fields.issubset(evaluator_diagnostic)
    assert evaluator_diagnostic["trajectory"]
    assert (
        len(evaluator_diagnostic["trajectory"])
        == evaluator_output["episode_results"][0]["steps"]
    )
    _assert_step_shape(evaluator_diagnostic["trajectory"][0])
    _assert_step_shape(evaluator_diagnostic["trajectory"][-1])
    assert evaluator_diagnostic["maximum_sampled_velocity_cm_s"] >= 0.0

    return {
        "observed": {
            "repeated_seed_resets": 2,
            "post_step_rows": len(trajectory),
            "trajectory_fields_checked": len(trajectory[0]),
            "evaluator_trajectory_rows": len(evaluator_diagnostic["trajectory"]),
            "posture_labels": [
                positive["elbow_branch"],
                negative["elbow_branch"],
                zero_branch["elbow_branch"],
            ],
            "rank_loss_condition_number": "inf",
            "invalid_condition_numbers_rejected": ["nan", "-inf"],
            "runtime_observation_space": {
                "shape": list(zero_runtime.observation_space.shape),
                "dtype": str(zero_runtime.observation_space.dtype),
                "unbounded": True,
            },
        },
        "expected": {
            "repeated_seed_resets": "identical initial state and target",
            "post_step_rows": 3,
            "posture_labels": ["open", "folded", "open"],
            "rank_loss_condition_number": "inf",
            "invalid_condition_numbers_rejected": ["nan", "-inf"],
            "runtime_observation_space": {
                "shape": [OBSERVATION_SIZE],
                "dtype": "float32",
                "unbounded": True,
            },
            "reference": "planar Jacobian singular values, velocity, and limits",
        },
        "checked_scope": [
            "official evaluation environment construction and seeded reset determinism",
            "controlled runtime observation space shape, dtype, and unbounded limits",
            "repeated zero-action post-step trajectory rows and field dimensions",
            "evaluator episode wiring retains a full trajectory and legacy fields",
            "planar Jacobian singular values and qvel-mapped cm/s velocity",
            "two-joint limit margins",
            "open/folded elbow labels, including q2 == 0 convention",
            "finite and positive-infinite Jacobian condition numbers",
            "rejection of NaN and negative-infinite condition numbers",
            "positive-infinite condition number at a rank-lost configuration",
        ],
        "unchecked_scope": [
            "learned-policy loading and policy runtime I/O",
            "long-horizon episode outcome semantics and 100-step holds",
            "between-control-step motion and scientific performance validity",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = _check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
