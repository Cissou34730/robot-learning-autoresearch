"""Controlled-input verification for the branch/limit/trajectory intervention.

This module is an executable laboratory check, not a scientific validity
claim.  It uses the production environment and reward calls, while keeping
the expected kinematics and normalized-margin calculations independent of the
implementation helpers.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.reward import reach_reward


def _angle_in_range(angle: float, lower: float, upper: float) -> bool:
    turns = range(
        int(np.floor((lower - angle) / (2.0 * np.pi))) - 1,
        int(np.ceil((upper - angle) / (2.0 * np.pi))) + 2,
    )
    return any(
        lower <= angle + 2.0 * np.pi * turn <= upper for turn in turns
    )


def _reference_branch_flags(
    target_xy: np.ndarray, joint_ranges: np.ndarray
) -> np.ndarray:
    """Independent analytic-IK branch feasibility reference."""
    target_x, target_y = np.asarray(target_xy, dtype=np.float64)[:2]
    cosine = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 or cosine > 1.0:
        return np.zeros(2, dtype=np.float32)
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))
    flags = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        flags.append(
            float(
                _angle_in_range(
                    shoulder, float(joint_ranges[0, 0]), float(joint_ranges[0, 1])
                )
                and _angle_in_range(
                    elbow, float(joint_ranges[1, 0]), float(joint_ranges[1, 1])
                )
            )
        )
    return np.asarray(flags, dtype=np.float32)


def _reference_base_observation(data) -> np.ndarray:
    """Reconstruct the original eleven values without reading them from obs."""
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])

    def wrap(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    def shoulder(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    cosine = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    elbow_folded = -elbow_open
    residuals = [
        wrap(shoulder(elbow_open) - float(data.qpos[0])),
        wrap(elbow_open - float(data.qpos[1])),
        wrap(shoulder(elbow_folded) - float(data.qpos[0])),
        wrap(elbow_folded - float(data.qpos[1])),
    ]
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            data.site("end_effector").xpos - data.mocap_pos[0],
            residuals,
        ]
    ).astype(np.float32)


def _set_target(env: TwoJointArmReachEnv, target_xy: np.ndarray) -> None:
    target_z = float(env.data.site("end_effector").xpos[2])
    env.data.mocap_pos[0] = [
        float(target_xy[0]),
        float(target_xy[1]),
        target_z,
    ]
    mujoco.mj_forward(env.model, env.data)


def _joint_ranges(env: TwoJointArmReachEnv) -> np.ndarray:
    return np.asarray(env.model.jnt_range[:2], dtype=np.float64).copy()


def _joint_positions(env: TwoJointArmReachEnv, values: np.ndarray) -> None:
    for index in range(2):
        env.data.qpos[int(env.model.jnt_qposadr[index])] = float(values[index])
        env.data.qvel[int(env.model.jnt_dofadr[index])] = 0.0
    mujoco.mj_forward(env.model, env.data)


def _reference_margins(
    positions: np.ndarray, joint_ranges: np.ndarray
) -> np.ndarray:
    half_ranges = 0.5 * (joint_ranges[:, 1] - joint_ranges[:, 0])
    raw = np.minimum(
        positions - joint_ranges[:, 0], joint_ranges[:, 1] - positions
    )
    return np.clip(raw / half_ranges, -1.0, 1.0).astype(np.float32)


def _find_branch_targets(joint_ranges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    one_branch = None
    two_branches = None
    for radius in np.linspace(0.06, 0.20, 15):
        for angle in np.linspace(-np.pi, np.pi, 73):
            target = np.asarray(
                [radius * np.cos(angle), radius * np.sin(angle)],
                dtype=np.float64,
            )
            flags = _reference_branch_flags(target, joint_ranges)
            if int(np.sum(flags)) == 1 and one_branch is None:
                one_branch = target
            if int(np.sum(flags)) == 2 and two_branches is None:
                two_branches = target
            if one_branch is not None and two_branches is not None:
                return one_branch, two_branches
    raise AssertionError("the compiled model did not expose both branch cases")


def _behavioral_check(output: Path) -> None:
    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=20,
    )
    observations_a, _ = env.reset(seed=1729)
    target_a = env.data.mocap_pos[0].copy()
    observations_b, _ = env.reset(seed=1729)
    target_b = env.data.mocap_pos[0].copy()
    assert np.array_equal(observations_a, observations_b)
    assert np.array_equal(target_a, target_b)
    assert env.observation_space.shape == (15,)
    assert np.allclose(observations_b[:11], _reference_base_observation(env.data))

    joint_ranges = _joint_ranges(env)
    one_target, two_target = _find_branch_targets(joint_ranges)
    _set_target(env, one_target)
    one_observation = env._observation()
    _set_target(env, two_target)
    two_observation = env._observation()
    expected_one = _reference_branch_flags(one_target, joint_ranges)
    expected_two = _reference_branch_flags(two_target, joint_ranges)
    assert int(np.sum(expected_one)) == 1
    assert int(np.sum(expected_two)) == 2
    assert np.array_equal(one_observation[11:13], expected_one)
    assert np.array_equal(two_observation[11:13], expected_two)
    assert not np.array_equal(one_observation[11:13], two_observation[11:13])

    center = 0.5 * (joint_ranges[:, 0] + joint_ranges[:, 1])
    near_limit = joint_ranges[:, 0] + 0.10 * (
        joint_ranges[:, 1] - joint_ranges[:, 0]
    )
    _joint_positions(env, center)
    center_margins = env._observation()[13:15]
    _joint_positions(env, near_limit)
    near_margins = env._observation()[13:15]
    outside_limit = joint_ranges[:, 1] + 0.5 * (
        joint_ranges[:, 1] - joint_ranges[:, 0]
    )
    _joint_positions(env, outside_limit)
    outside_margins = env._observation()[13:15]
    assert np.allclose(center_margins, _reference_margins(center, joint_ranges))
    assert np.allclose(near_margins, _reference_margins(near_limit, joint_ranges))
    assert np.allclose(
        outside_margins, _reference_margins(outside_limit, joint_ranges)
    )
    assert np.all(near_margins < center_margins)
    assert np.all((near_margins >= -1.0) & (near_margins <= 1.0))
    assert np.array_equal(outside_margins, np.asarray([-1.0, -1.0], dtype=np.float32))

    safe_reward = reach_reward(
        0.10,
        0.09,
        0.01,
        np.zeros(2),
        joint_positions=center,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    near_limit_reward = reach_reward(
        0.10,
        0.09,
        0.01,
        np.zeros(2),
        joint_positions=near_limit,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    high_velocity_reward = reach_reward(
        0.10,
        0.09,
        0.01,
        np.zeros(2),
        joint_positions=center,
        joint_velocities=np.asarray([8.0, 0.0]),
        joint_ranges=joint_ranges,
    )
    assert np.isfinite(
        [safe_reward.total, near_limit_reward.total, high_velocity_reward.total]
    ).all()
    assert safe_reward.components["joint_limit"] == 0.0
    assert safe_reward.components["joint_speed"] == 0.0
    assert near_limit_reward.components["joint_limit"] < 0.0
    assert high_velocity_reward.components["joint_speed"] < 0.0
    assert near_limit_reward.total < safe_reward.total
    assert high_velocity_reward.total < safe_reward.total

    _, _, _, _, clipped_info = env.step(np.asarray([3.0, -3.0]))
    clipped_control = env.data.ctrl.copy()
    assert np.array_equal(clipped_control, np.asarray([1.0, -1.0]))
    assert np.isfinite(clipped_info["reward_components"]["joint_limit"])
    env.reset(seed=1730)
    _set_target(env, env.data.site("end_effector").xpos[:2].copy())
    env._previous_distance = env._distance_to_target()
    _, _, _, _, first_hold_info = env.step(np.zeros(2))
    _, _, _, _, second_hold_info = env.step(np.zeros(2))
    assert first_hold_info["held_steps"] == 1
    assert second_hold_info["held_steps"] == 2
    assert len(env.physics_step_distances) == env.frame_skip
    _set_target(
        env,
        env.data.site("end_effector").xpos[:2].copy() + np.asarray([0.10, 0.0]),
    )
    _, _, _, _, exited_hold_info = env.step(np.zeros(2))
    assert exited_hold_info["held_steps"] == 0

    artifact = {
        "check": "branch_limit_trajectory_intervention",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "observation_size": int(env.observation_space.shape[0]),
            "one_branch_flags": one_observation[11:13].tolist(),
            "two_branch_flags": two_observation[11:13].tolist(),
            "center_margins": center_margins.tolist(),
            "near_limit_margins": near_margins.tolist(),
            "outside_limit_margins": outside_margins.tolist(),
            "safe_reward": float(safe_reward.total),
            "near_limit_reward": float(near_limit_reward.total),
            "high_velocity_reward": float(high_velocity_reward.total),
            "clipped_control": clipped_control.tolist(),
            "hold_steps_before_exit": [
                int(first_hold_info["held_steps"]),
                int(second_hold_info["held_steps"]),
            ],
            "hold_steps_after_exit": int(exited_hold_info["held_steps"]),
        },
        "expected": {
            "observation_size": 15,
            "one_branch_count": 1,
            "two_branch_count": 2,
            "near_limit_margins_below_center": True,
            "outside_limit_margins_clipped": [-1.0, -1.0],
            "safe_shaping_components_zero": True,
            "near_limit_and_high_velocity_penalized": True,
            "clipped_control": [1.0, -1.0],
            "hold_steps_before_exit": [1, 2],
            "hold_steps_after_exit": 0,
        },
        "checked_scope": [
            "seeded reset determinism and preservation of the original eleven observation values",
            "analytic open/folded feasibility flags for one- and two-branch targets",
            "compiled-range margin normalization and clipping bounds",
            "bounded reward responses to near-limit and high-speed controlled states",
            "repeated physics-interval updates, action clipping, and hold exit",
        ],
        "unchecked_scope": [
            "learning performance or causal effect on a fresh training artifact",
            "official evaluation success and protected benchmark semantics",
            "continuous-hold behavior between the visible control boundaries",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def _compatibility_check(output: Path) -> None:
    """Exercise changed production paths with one artifact-independent step."""
    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=2,
    )
    observation, _ = env.reset(seed=19)
    next_observation, reward, _, _, info = env.step(np.asarray([2.0, -2.0]))
    assert observation.shape == (15,)
    assert next_observation.shape == (15,)
    assert np.isfinite(next_observation).all()
    assert np.isfinite(reward)
    assert np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0]))
    assert "joint_limit" in info["reward_components"]
    assert "joint_speed" in info["reward_components"]
    artifact = {
        "check": "branch_limit_trajectory_intervention_compatibility",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "reset_observation_shape": list(observation.shape),
            "step_observation_shape": list(next_observation.shape),
            "step_reward": float(reward),
            "clipped_control": env.data.ctrl.tolist(),
            "reward_component_keys": sorted(info["reward_components"]),
        },
        "expected": {
            "observation_shape": [15],
            "finite_reward_and_observation": True,
            "clipped_control": [1.0, -1.0],
            "integrated_shaping_components": ["joint_limit", "joint_speed"],
        },
        "checked_scope": [
            "production reset and step through the changed observation and reward paths",
            "finite integrated output and action clipping",
        ],
        "unchecked_scope": [
            "full branch and margin behavioral check",
            "training or evaluation artifact behavior",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    if args.compatibility:
        _compatibility_check(Path(args.output))
    else:
        _behavioral_check(Path(args.output))


if __name__ == "__main__":
    main()
