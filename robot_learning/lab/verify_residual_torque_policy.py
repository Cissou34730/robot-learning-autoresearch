"""Defect-sensitive checks for the residual-torque control profile.

This module is intended for the ``python_module`` instrument.  Its reference
controller is written independently of the scenario implementation so that
the checks exercise the saved control contract, repeated state updates, and
the direct-control regression path rather than checking source structure.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.policy_io import (
    DIRECT_CONTROL_PROFILE,
    RESIDUAL_TORQUE_PROFILE,
    make_policy_io,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training.environment import make_training_env
from robot_learning.training.reward import TARGETED_REGULATION_PROFILE


L1 = 0.12
L2 = 0.10
JOINT_ATTRACTION_GAIN = 0.65
JOINT_ERROR_SCALE = 0.70
JOINT_VELOCITY_DAMPING_GAIN = 0.18
JOINT_VELOCITY_SCALE = 2.0
ENDPOINT_ERROR_GAIN = 0.80
ENDPOINT_ERROR_SCALE = 0.025
ENDPOINT_VELOCITY_DAMPING_GAIN = 0.28
ENDPOINT_VELOCITY_SCALE = 0.50
ENDPOINT_BOUNDARY_OUTER_DISTANCE = 0.05
JOINT_LIMIT_RADIANS = np.deg2rad(170.0)
JOINT_LIMIT_MARGIN = np.deg2rad(20.0)
JOINT_LIMIT_REPULSION_GAIN = 0.25
SINGULAR_ELBOW_THRESHOLD = 0.12
SINGULAR_ELBOW_ESCAPE_GAIN = 0.08
RESIDUAL_ACTION_SCALE = 0.35
SUCCESS_THRESHOLD = 0.01


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _reference_ik(target: np.ndarray) -> tuple[list[np.ndarray], int]:
    target_x, target_y = float(target[0]), float(target[1])
    target_angle = float(np.arctan2(target_y, target_x))
    cosine_elbow = (
        target_x**2 + target_y**2 - L1**2 - L2**2
    ) / (2.0 * L1 * L2)
    elbow_magnitude = float(np.arccos(np.clip(cosine_elbow, -1.0, 1.0)))
    branches = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = target_angle - np.arctan2(
            L2 * np.sin(elbow),
            L1 + L2 * np.cos(elbow),
        )
        branches.append(np.array([shoulder, elbow], dtype=np.float64))

    return branches, 0


def _reference_action(
    learned_action: np.ndarray,
    q: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, int, dict[str, np.ndarray | float]]:
    branches, _ = _reference_ik(target)
    errors = [
        np.array(
            [
                _wrap_to_pi(float(branch[0] - q[0])),
                _wrap_to_pi(float(branch[1] - q[1])),
            ],
            dtype=np.float64,
        )
        for branch in branches
    ]
    branch_index = int(np.argmin([np.linalg.norm(error) for error in errors]))
    joint_error = errors[branch_index]

    joint_attraction = JOINT_ATTRACTION_GAIN * np.tanh(
        joint_error / JOINT_ERROR_SCALE
    )
    joint_damping = JOINT_VELOCITY_DAMPING_GAIN * np.tanh(
        qvel / JOINT_VELOCITY_SCALE
    )
    nominal_torque = np.clip(joint_attraction - joint_damping, -1.0, 1.0)

    q1, q2 = float(q[0]), float(q[1])
    distal_angle = q1 + q2
    endpoint = np.array(
        [
            L1 * np.cos(q1) + L2 * np.cos(distal_angle),
            L1 * np.sin(q1) + L2 * np.sin(distal_angle),
        ],
        dtype=np.float64,
    )
    jacobian = np.array(
        [
            [
                -L1 * np.sin(q1) - L2 * np.sin(distal_angle),
                -L2 * np.sin(distal_angle),
            ],
            [
                L1 * np.cos(q1) + L2 * np.cos(distal_angle),
                L2 * np.cos(distal_angle),
            ],
        ],
        dtype=np.float64,
    )
    endpoint_error = target[:2] - endpoint
    endpoint_term = ENDPOINT_ERROR_GAIN * np.tanh(
        (jacobian.T @ endpoint_error) / ENDPOINT_ERROR_SCALE
    )

    endpoint_velocity = jacobian @ qvel
    distance = float(np.linalg.norm(endpoint_error))
    boundary_weight = np.clip(
        (ENDPOINT_BOUNDARY_OUTER_DISTANCE - distance)
        / (ENDPOINT_BOUNDARY_OUTER_DISTANCE - SUCCESS_THRESHOLD),
        0.0,
        1.0,
    )
    endpoint_velocity_term = -(
        ENDPOINT_VELOCITY_DAMPING_GAIN
        * boundary_weight
        * np.tanh((jacobian.T @ endpoint_velocity) / ENDPOINT_VELOCITY_SCALE)
    )

    limit_term = np.zeros(2, dtype=np.float64)
    for index, joint in enumerate(q):
        lower_distance = float(joint + JOINT_LIMIT_RADIANS)
        upper_distance = float(JOINT_LIMIT_RADIANS - joint)
        if lower_distance < JOINT_LIMIT_MARGIN:
            limit_term[index] += JOINT_LIMIT_REPULSION_GAIN * np.clip(
                1.0 - lower_distance / JOINT_LIMIT_MARGIN,
                0.0,
                1.0,
            )
        if upper_distance < JOINT_LIMIT_MARGIN:
            limit_term[index] -= JOINT_LIMIT_REPULSION_GAIN * np.clip(
                1.0 - upper_distance / JOINT_LIMIT_MARGIN,
                0.0,
                1.0,
            )

    singular_term = np.zeros(2, dtype=np.float64)
    if abs(float(q[1])) < SINGULAR_ELBOW_THRESHOLD:
        target_angle = float(np.arctan2(target[1], target[0]))
        singular_term[1] = SINGULAR_ELBOW_ESCAPE_GAIN * (
            1.0 if target_angle >= 0.0 else -1.0
        )

    clipped_learned_action = np.clip(learned_action, -1.0, 1.0)
    result = np.clip(
        nominal_torque
        + endpoint_term
        + endpoint_velocity_term
        + limit_term
        + singular_term
        + RESIDUAL_ACTION_SCALE * clipped_learned_action,
        -1.0,
        1.0,
    )
    terms = {
        "nominal_torque": nominal_torque,
        "endpoint_term": endpoint_term,
        "endpoint_velocity_term": endpoint_velocity_term,
        "limit_term": limit_term,
        "singular_term": singular_term,
        "selected_branch": branches[branch_index],
    }
    return result, branch_index, terms


def _set_state(
    env: TwoJointArmReachEnv,
    q: np.ndarray,
    qvel: np.ndarray,
    radius: float,
    angle: float,
) -> np.ndarray:
    env.data.qpos[:2] = q
    env.data.qvel[:2] = qvel
    env.data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        0.02,
    ]
    mujoco.mj_forward(env.model, env.data)
    return env.data.mocap_pos[0].copy()


def _close_enough(
    observed: np.ndarray, expected: np.ndarray, label: str
) -> dict[str, object]:
    observed = np.asarray(observed, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    error = float(np.max(np.abs(observed - expected)))
    if error > 1.0e-9:
        raise AssertionError(f"{label} differs by {error}")
    return {
        "label": label,
        "observed": observed.tolist(),
        "expected": expected.tolist(),
        "max_abs_error": error,
    }


def _control_profile_checks(observations: list[dict[str, object]]) -> None:
    try:
        make_policy_io(control_profile="unknown_profile")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown policy profile was accepted")
    try:
        TwoJointArmReachEnv(control_profile="unknown_profile")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown environment profile was accepted")

    training_env = make_training_env()
    try:
        if training_env.target_radius_range != (0.06, 0.20):
            raise AssertionError(
                f"training radius range is {training_env.target_radius_range}"
            )
        if training_env.control_profile != RESIDUAL_TORQUE_PROFILE:
            raise AssertionError("training environment is not residual torque")
        if training_env.reward_profile != TARGETED_REGULATION_PROFILE:
            raise AssertionError("training reward is not targeted regulation")
        observations.append(
            {
                "label": "training_profile",
                "observed": {
                    "target_radius_range": list(training_env.target_radius_range),
                    "control_profile": training_env.control_profile,
                    "reward_profile": training_env.reward_profile,
                },
                "expected": {
                    "target_radius_range": [0.06, 0.20],
                    "control_profile": RESIDUAL_TORQUE_PROFILE,
                    "reward_profile": TARGETED_REGULATION_PROFILE,
                },
            }
        )
    finally:
        training_env.close()

    evaluation_env = make_evaluation_env()
    try:
        if evaluation_env.control_profile != DIRECT_CONTROL_PROFILE:
            raise AssertionError("evaluation without a runtime is not direct")
        observations.append(
            {
                "label": "evaluation_default_profile",
                "observed": evaluation_env.control_profile,
                "expected": DIRECT_CONTROL_PROFILE,
            }
        )
    finally:
        evaluation_env.close()

    marked_runtime = SimpleNamespace(
        io=make_policy_io(control_profile=RESIDUAL_TORQUE_PROFILE)
    )
    marked_evaluation_env = TwoJointArmReachEnv(policy_runtime=marked_runtime)
    try:
        if marked_evaluation_env.control_profile != RESIDUAL_TORQUE_PROFILE:
            raise AssertionError("saved PolicyIO marker was not respected")
        observations.append(
            {
                "label": "saved_policy_io_marker",
                "observed": marked_evaluation_env.control_profile,
                "expected": RESIDUAL_TORQUE_PROFILE,
            }
        )
    finally:
        marked_evaluation_env.close()


def _residual_control_checks(observations: list[dict[str, object]]) -> None:
    env = TwoJointArmReachEnv(
        frame_skip=1,
        control_profile=RESIDUAL_TORQUE_PROFILE,
    )
    try:
        reset_observation, _ = env.reset(seed=17)
        if reset_observation.shape != (11,):
            raise AssertionError("reset did not return the physical observation")
        if not np.allclose(env.data.qpos[:2], 0.0) or not np.allclose(
            env.data.qvel[:2], 0.0
        ):
            raise AssertionError("reset-like state was not restored")

        cases = [
            (
                "negative_angle",
                np.array([0.35, -0.20]),
                np.array([0.40, -0.30]),
                0.12,
                -2.20,
                np.array([1.40, -0.80]),
            ),
            (
                "singular_reset_like",
                np.array([0.0, 0.0]),
                np.array([0.0, 0.0]),
                0.18,
                -1.10,
                np.array([-0.40, 0.20]),
            ),
            (
                "near_upper_joint_limit",
                np.array([np.deg2rad(165.0), -0.35]),
                np.array([1.10, -0.90]),
                0.10,
                -2.50,
                np.array([-1.20, 1.30]),
            ),
            (
                "repeated_regulation_update",
                np.array([-0.80, 0.80]),
                np.array([-0.25, 0.60]),
                0.16,
                0.70,
                np.array([0.30, -0.45]),
            ),
        ]
        for label, q, qvel, radius, angle, learned_action in cases:
            target = _set_state(env, q, qvel, radius, angle)
            expected, branch_index, terms = _reference_action(
                learned_action,
                q,
                qvel,
                target,
            )
            env.step(learned_action)
            observations.append(
                {
                    "label": label,
                    "branch_index": branch_index,
                    "selected_branch": terms["selected_branch"].tolist(),
                    "terms": {
                        key: value.tolist()
                        for key, value in terms.items()
                        if key != "selected_branch"
                    },
                    "comparison": _close_enough(
                        env.data.ctrl.copy(), expected, label
                    ),
                }
            )

        env.reset(seed=23)
        if not np.allclose(env.data.qpos[:2], 0.0) or not np.allclose(
            env.data.qvel[:2], 0.0
        ):
            raise AssertionError("second reset did not restore the arm")
        observations.append(
            {
                "label": "repeated_reset",
                "observed": {
                    "qpos": env.data.qpos[:2].tolist(),
                    "qvel": env.data.qvel[:2].tolist(),
                    "held_steps": env._held_steps,
                },
                "expected": {
                    "qpos": [0.0, 0.0],
                    "qvel": [0.0, 0.0],
                    "held_steps": 0,
                },
            }
        )
    finally:
        env.close()


def _direct_control_check(observations: list[dict[str, object]]) -> None:
    env = TwoJointArmReachEnv(frame_skip=1)
    try:
        env.reset(seed=29)
        learned_action = np.array([0.35, -1.70])
        env.step(learned_action)
        expected = np.array([0.35, -1.0])
        if env.control_profile != DIRECT_CONTROL_PROFILE:
            raise AssertionError("default control profile is not direct")
        observations.append(
            {
                "label": "direct_control_regression",
                "comparison": _close_enough(
                    env.data.ctrl.copy(), expected, "direct_control"
                ),
            }
        )
    finally:
        env.close()

    legacy_io = make_policy_io()
    object.__delattr__(legacy_io, "control_profile")
    legacy_env = TwoJointArmReachEnv(
        frame_skip=1,
        policy_runtime=SimpleNamespace(io=legacy_io),
    )
    try:
        legacy_env.reset(seed=31)
        learned_action = np.array([-0.45, 1.60])
        legacy_env.step(learned_action)
        observations.append(
            {
                "label": "legacy_runtime_without_marker",
                "comparison": _close_enough(
                    legacy_env.data.ctrl.copy(),
                    np.array([-0.45, 1.0]),
                    "legacy_direct_control",
                ),
            }
        )
    finally:
        legacy_env.close()


def _export_persistence_check(observations: list[dict[str, object]]) -> None:
    from robot_learning.training import checkpoint

    captured: dict[str, object] = {}

    def capture_save_runtime(model_path, **kwargs):
        del model_path
        captured.update(kwargs)

    original_save_runtime = checkpoint.save_runtime
    checkpoint.save_runtime = capture_save_runtime
    try:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint.export_runtime(Path(directory), stats_path=None)
    finally:
        checkpoint.save_runtime = original_save_runtime

    policy_io = captured.get("policy_io")
    observed_profile = getattr(policy_io, "control_profile", None)
    if observed_profile != RESIDUAL_TORQUE_PROFILE:
        raise AssertionError(
            f"exported profile is {observed_profile!r}, not residual torque"
        )
    observations.append(
        {
            "label": "checkpoint_profile_persistence",
            "observed": observed_profile,
            "expected": RESIDUAL_TORQUE_PROFILE,
        }
    )


def run_checks() -> dict[str, object]:
    observations: list[dict[str, object]] = []
    _control_profile_checks(observations)
    _residual_control_checks(observations)
    _direct_control_check(observations)
    _export_persistence_check(observations)
    return {
        "passed": True,
        "checked_scope": [
            "independent two-branch planar IK and wrapped-error branch selection",
            "bounded nominal attraction and joint-velocity damping",
            "Jacobian-transpose endpoint error and boundary-weighted endpoint damping",
            "joint-limit repulsion and deterministic singular-elbow escape",
            "residual clipping across repeated changed states and negative target angle",
            "reset transitions and direct-control action identity",
            "training/evaluation profiles, injected marker, and export persistence",
        ],
        "observed_vs_expected": observations,
        "unchecked_scope": [
            "long-horizon learning performance and matched-panel capability",
            "MuJoCo trajectory quality beyond the controlled action comparisons",
            "official no-first-reach failure counts and scientific validity",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact")
    args = parser.parse_args()
    try:
        result = run_checks()
    except Exception as error:
        result = {
            "passed": False,
            "checked_scope": [
                "residual-torque profile laboratory checks up to the failing check"
            ],
            "observed_vs_expected": {
                "error_type": type(error).__name__,
                "error": str(error),
            },
            "unchecked_scope": [
                "checks after the first failure",
                "long-horizon learning performance and matched-panel capability",
                "official no-first-reach failure counts and scientific validity",
            ],
        }
    Path(args.artifact).write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
