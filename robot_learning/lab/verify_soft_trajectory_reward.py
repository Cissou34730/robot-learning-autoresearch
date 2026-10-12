"""Laboratory verification for the T2-compatible soft reward intervention.

This is an executable check proposal, not a scientific validity claim.  It
reconstructs the original observation independently, then drives the real
environment and reward with controlled states so that a representation-only
regression or an over-strong shaping change is detected.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.reward import (
    TERMINAL_SHAPING_DISTANCE,
    reach_reward,
)


def _reference_observation(data) -> np.ndarray:
    """Reconstruct the original eleven values without reading an observation."""
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
    residuals = [
        wrap(shoulder(elbow_open) - float(data.qpos[0])),
        wrap(elbow_open - float(data.qpos[1])),
        wrap(shoulder(-elbow_open) - float(data.qpos[0])),
        wrap(-elbow_open - float(data.qpos[1])),
    ]
    return np.concatenate(
        [
            np.asarray(data.qpos),
            np.asarray(data.qvel),
            data.site("end_effector").xpos - data.mocap_pos[0],
            residuals,
        ]
    ).astype(np.float32)


def _set_target_at_end_effector(env: TwoJointArmReachEnv) -> None:
    position = env.data.site("end_effector").xpos.copy()
    env.data.mocap_pos[0] = position
    mujoco.mj_forward(env.model, env.data)


def _set_target_offset(env: TwoJointArmReachEnv, offset: np.ndarray) -> None:
    position = env.data.site("end_effector").xpos.copy()
    position[:2] += np.asarray(offset, dtype=np.float64)
    env.data.mocap_pos[0] = position
    mujoco.mj_forward(env.model, env.data)


def _joint_ranges(env: TwoJointArmReachEnv) -> np.ndarray:
    return np.asarray(env.model.jnt_range[:2], dtype=np.float64).copy()


def _expect_value_error() -> None:
    try:
        reach_reward(
            0.10,
            0.09,
            0.01,
            joint_positions=np.zeros(2),
        )
    except ValueError:
        return
    raise AssertionError("partial joint-shaping inputs must remain invalid")


def _behavioral_check(output: Path) -> None:
    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=20,
    )
    first_observation, _ = env.reset(seed=1729)
    first_target = env.data.mocap_pos[0].copy()
    second_observation, _ = env.reset(seed=1729)
    second_target = env.data.mocap_pos[0].copy()
    assert np.array_equal(first_observation, second_observation)
    assert np.array_equal(first_target, second_target)
    assert env.observation_space.shape == (11,)
    assert first_observation.shape == (11,)
    assert np.allclose(
        second_observation, _reference_observation(env.data), atol=1e-7
    )

    transition_observations = []
    transition_rewards = []
    transition_components = []
    for action in (
        np.asarray([0.25, -0.25]),
        np.asarray([-0.50, 0.10]),
        np.asarray([3.0, -3.0]),
    ):
        observation, reward, _, _, info = env.step(action)
        transition_observations.append(observation)
        transition_rewards.append(reward)
        transition_components.append(info["reward_components"])
    assert all(observation.shape == (11,) for observation in transition_observations)
    assert np.isfinite(transition_rewards).all()
    assert len(env.physics_step_distances) == env.frame_skip
    assert np.isfinite(env.physics_step_distances).all()
    assert np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0]))

    joint_ranges = _joint_ranges(env)
    center = 0.5 * (joint_ranges[:, 0] + joint_ranges[:, 1])
    near_limit = joint_ranges[:, 0] + 0.02 * (
        joint_ranges[:, 1] - joint_ranges[:, 0]
    )
    approach_kwargs = {
        "previous_distance": 0.10,
        "current_distance": 0.09,
        "success_threshold": 0.01,
        "action": np.zeros(2),
    }
    approach_reward = reach_reward(**approach_kwargs)
    approach_near_limit_reward = reach_reward(
        **approach_kwargs,
        joint_positions=near_limit,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    approach_high_speed_reward = reach_reward(
        **approach_kwargs,
        joint_positions=center,
        joint_velocities=np.asarray([8.0, 0.0]),
        joint_ranges=joint_ranges,
    )
    terminal_kwargs = {
        "previous_distance": 0.03,
        "current_distance": 0.015,
        "success_threshold": 0.01,
        "action": np.zeros(2),
    }
    terminal_reward = reach_reward(**terminal_kwargs)
    terminal_near_limit_reward = reach_reward(
        **terminal_kwargs,
        joint_positions=near_limit,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    terminal_high_speed_reward = reach_reward(
        **terminal_kwargs,
        joint_positions=center,
        joint_velocities=np.asarray([8.0, 0.0]),
        joint_ranges=joint_ranges,
    )
    terminal_boundary_reward = reach_reward(
        previous_distance=0.03,
        current_distance=TERMINAL_SHAPING_DISTANCE,
        success_threshold=0.01,
        action=np.zeros(2),
        joint_positions=near_limit,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    just_outside_terminal_reward = reach_reward(
        previous_distance=0.03,
        current_distance=TERMINAL_SHAPING_DISTANCE + 1e-6,
        success_threshold=0.01,
        action=np.zeros(2),
        joint_positions=near_limit,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    safe_reward = reach_reward(
        **approach_kwargs,
        joint_positions=center,
        joint_velocities=np.zeros(2),
        joint_ranges=joint_ranges,
    )
    assert np.isfinite(
        [
            approach_reward.total,
            approach_near_limit_reward.total,
            approach_high_speed_reward.total,
            terminal_reward.total,
            terminal_near_limit_reward.total,
            terminal_high_speed_reward.total,
            terminal_boundary_reward.total,
            just_outside_terminal_reward.total,
            safe_reward.total,
        ]
    ).all()
    assert TERMINAL_SHAPING_DISTANCE > 0.0
    assert safe_reward.components["joint_limit"] == 0.0
    assert safe_reward.components["joint_speed"] == 0.0
    assert approach_near_limit_reward.components["joint_limit"] == 0.0
    assert approach_high_speed_reward.components["joint_speed"] == 0.0
    assert approach_near_limit_reward.total == approach_reward.total
    assert approach_high_speed_reward.total == approach_reward.total
    assert terminal_near_limit_reward.components["joint_limit"] < 0.0
    assert terminal_high_speed_reward.components["joint_speed"] < 0.0
    assert terminal_boundary_reward.components["joint_limit"] < 0.0
    assert just_outside_terminal_reward.components["joint_limit"] == 0.0
    assert terminal_near_limit_reward.total < terminal_reward.total
    assert terminal_high_speed_reward.total < terminal_reward.total
    assert abs(terminal_near_limit_reward.components["joint_limit"]) <= 0.25 * abs(
        terminal_reward.total
    )
    assert abs(terminal_high_speed_reward.components["joint_speed"]) <= 0.25 * abs(
        terminal_reward.total
    )
    assert set(safe_reward.components) == {
        "progress",
        "closeness",
        "hold_progress",
        "outside_band",
        "hold_complete",
        "action_cost",
        "joint_limit",
        "joint_speed",
    }
    _expect_value_error()

    hold_env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        hold_seconds=0.06,
        max_episode_steps=10,
    )
    hold_env.reset(seed=7)
    _set_target_at_end_effector(hold_env)
    hold_env._previous_distance = hold_env._distance_to_target()
    _, _, _, _, first_hold = hold_env.step(np.zeros(2))
    _, _, _, _, second_hold = hold_env.step(np.zeros(2))
    _set_target_offset(hold_env, np.asarray([0.10, 0.0]))
    _, _, terminated, _, interrupted_hold = hold_env.step(np.zeros(2))
    assert first_hold["held_steps"] == 1
    assert second_hold["held_steps"] == 2
    assert interrupted_hold["held_steps"] == 0
    assert not terminated
    _set_target_at_end_effector(hold_env)
    hold_env._previous_distance = hold_env._distance_to_target()
    _, _, _, _, resumed_hold = hold_env.step(np.zeros(2))
    assert resumed_hold["held_steps"] == 1

    reset_observation, _ = hold_env.reset(seed=7)
    repeated_reset_observation, _ = hold_env.reset(seed=7)
    assert np.array_equal(reset_observation, repeated_reset_observation)
    assert hold_env._held_steps == 0

    artifact = {
        "check": "soft_trajectory_reward",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "observation_size": int(env.observation_space.shape[0]),
            "reference_observation_match": True,
            "transition_count": len(transition_observations),
            "physics_step_count": len(env.physics_step_distances),
            "clipped_control": env.data.ctrl.tolist(),
            "terminal_shaping_distance": TERMINAL_SHAPING_DISTANCE,
            "approach_reward": float(approach_reward.total),
            "approach_stress_shaping": {
                "joint_limit": float(
                    approach_near_limit_reward.components["joint_limit"]
                ),
                "joint_speed": float(
                    approach_high_speed_reward.components["joint_speed"]
                ),
            },
            "safe_shaping": {
                "joint_limit": float(safe_reward.components["joint_limit"]),
                "joint_speed": float(safe_reward.components["joint_speed"]),
            },
            "terminal_shaping": {
                "joint_limit": float(
                    terminal_near_limit_reward.components["joint_limit"]
                ),
                "joint_speed": float(
                    terminal_high_speed_reward.components["joint_speed"]
                ),
                "boundary_joint_limit": float(
                    terminal_boundary_reward.components["joint_limit"]
                ),
                "just_outside_joint_limit": float(
                    just_outside_terminal_reward.components["joint_limit"]
                ),
            },
            "hold_steps": [
                int(first_hold["held_steps"]),
                int(second_hold["held_steps"]),
                int(interrupted_hold["held_steps"]),
                int(resumed_hold["held_steps"]),
            ],
            "reset_held_steps": int(hold_env._held_steps),
            "reward_component_keys": sorted(safe_reward.components),
        },
        "expected": {
            "observation_size": 11,
            "reference_observation_match": True,
            "multiple_transitions_finite": True,
            "physics_step_count_equals_frame_skip": True,
            "clipped_control": [1.0, -1.0],
            "safe_shaping_components_zero": True,
            "approach_stress_components_zero": True,
            "terminal_near_limit_and_high_speed_penalized": True,
            "terminal_boundary_active_and_just_outside_inactive": True,
            "terminal_penalties_bounded_relative_to_reach": True,
            "hold_steps": [1, 2, 0, 1],
            "reset_held_steps": 0,
        },
        "checked_scope": [
            "T2 eleven-value observation reconstructed independently from production MuJoCo state",
            "repeated seeded resets and several production transitions",
            "approach shaping suppression and terminal-gated near-limit/high-speed penalties",
            "inclusive terminal gate boundary and just-outside inactivity",
            "public reward attribution keys and partial-input validation",
            "action clipping, physics-step telemetry, hold interruption, resumption, and reset",
        ],
        "unchecked_scope": [
            "learning performance or causal effect on a training artifact",
            "official evaluation success and protected benchmark semantics",
            "continuous-hold behavior between visible control boundaries",
            "policy normalization behavior outside the restored observation shape",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def _compatibility_check(output: Path) -> None:
    """Exercise the changed production paths with controlled inputs only."""
    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        max_episode_steps=2,
    )
    observation, _ = env.reset(seed=19)
    next_observation, reward, _, _, info = env.step(np.asarray([2.0, -2.0]))
    assert observation.shape == (11,)
    assert next_observation.shape == (11,)
    assert np.isfinite(next_observation).all()
    assert np.isfinite(reward)
    assert np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0]))
    assert set(info["reward_components"]) == {
        "progress",
        "closeness",
        "hold_progress",
        "outside_band",
        "hold_complete",
        "action_cost",
        "joint_limit",
        "joint_speed",
    }

    joint_ranges = _joint_ranges(env)
    near_limit = joint_ranges[:, 0] + 0.02 * (
        joint_ranges[:, 1] - joint_ranges[:, 0]
    )
    approach = reach_reward(
        previous_distance=0.03,
        current_distance=TERMINAL_SHAPING_DISTANCE + 0.005,
        success_threshold=0.01,
        action=np.zeros(2),
        joint_positions=near_limit,
        joint_velocities=np.asarray([8.0, 0.0]),
        joint_ranges=joint_ranges,
    )
    terminal = reach_reward(
        previous_distance=0.03,
        current_distance=TERMINAL_SHAPING_DISTANCE * 0.5,
        success_threshold=0.01,
        action=np.zeros(2),
        joint_positions=near_limit,
        joint_velocities=np.asarray([8.0, 0.0]),
        joint_ranges=joint_ranges,
    )
    assert approach.components["joint_limit"] == 0.0
    assert approach.components["joint_speed"] == 0.0
    assert terminal.components["joint_limit"] < 0.0
    assert terminal.components["joint_speed"] < 0.0

    env.reset(seed=23)
    env.data.qpos[:2] = near_limit
    env.data.qvel[:2] = 0.0
    mujoco.mj_forward(env.model, env.data)
    _set_target_at_end_effector(env)
    env._previous_distance = env._distance_to_target()
    _, _, _, _, terminal_info = env.step(np.zeros(2))
    assert terminal_info["distance"] <= TERMINAL_SHAPING_DISTANCE
    assert terminal_info["reward_components"]["joint_limit"] < 0.0

    env.reset(seed=23)
    env.data.qpos[:2] = near_limit
    env.data.qvel[:2] = 0.0
    mujoco.mj_forward(env.model, env.data)
    _set_target_at_end_effector(env)
    _set_target_offset(env, np.asarray([0.05, 0.0]))
    env._previous_distance = env._distance_to_target()
    _, _, _, _, approach_info = env.step(np.zeros(2))
    assert approach_info["distance"] > TERMINAL_SHAPING_DISTANCE
    assert approach_info["reward_components"]["joint_limit"] == 0.0
    assert approach_info["reward_components"]["joint_speed"] == 0.0

    artifact = {
        "check": "soft_trajectory_reward_compatibility",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "observation_space_shape": list(env.observation_space.shape),
            "reset_observation_shape": list(observation.shape),
            "step_observation_shape": list(next_observation.shape),
            "step_reward": float(reward),
            "clipped_control": env.data.ctrl.tolist(),
            "reward_component_keys": sorted(info["reward_components"]),
            "terminal_shaping_distance": TERMINAL_SHAPING_DISTANCE,
            "direct_approach_shaping": {
                "joint_limit": float(approach.components["joint_limit"]),
                "joint_speed": float(approach.components["joint_speed"]),
            },
            "direct_terminal_shaping": {
                "joint_limit": float(terminal.components["joint_limit"]),
                "joint_speed": float(terminal.components["joint_speed"]),
            },
            "production_terminal_distance": float(terminal_info["distance"]),
            "production_approach_distance": float(approach_info["distance"]),
            "production_terminal_joint_limit": float(
                terminal_info["reward_components"]["joint_limit"]
            ),
            "production_approach_joint_limit": float(
                approach_info["reward_components"]["joint_limit"]
            ),
        },
        "expected": {
            "observation_space_shape": [11],
            "reset_observation_shape": [11],
            "step_observation_shape": [11],
            "finite_step_reward_and_observation": True,
            "clipped_control": [1.0, -1.0],
            "stable_reward_component_keys": True,
            "direct_approach_shaping_zero": True,
            "direct_terminal_shaping_active": True,
            "production_terminal_shaping_active": True,
            "production_approach_shaping_zero": True,
        },
        "checked_scope": [
            "production reset and step through the restored observation path",
            "production reward call with controlled clipped action",
            "direct reward gate outside and inside the terminal neighborhood",
            "integrated production reward gate at a controlled joint-limit state",
            "finite integrated outputs and stable attribution keys",
        ],
        "unchecked_scope": [
            "full behavioral shaping and hold check",
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
