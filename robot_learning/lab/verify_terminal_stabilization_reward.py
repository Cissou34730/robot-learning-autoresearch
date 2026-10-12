"""Laboratory verification for terminal sampled-data stabilization shaping.

This is an executable check proposal, not a scientific validity claim.  It
uses an independent scalar reference for the new penalty and controlled
MuJoCo states to exercise the production reward and environment paths.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.reward import reach_reward


# Independent reference values for the supplied candidate intervention.
REFERENCE_TERMINAL_DISTANCE = 0.015
REFERENCE_SPEED_THRESHOLD = 1.0
REFERENCE_COEFFICIENT = 0.02


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_close(actual: float, expected: float, message: str) -> None:
    _assert(
        bool(np.isclose(actual, expected, rtol=1e-9, atol=1e-9)),
        f"{message}: observed {actual!r}, expected {expected!r}",
    )


def _set_target_at_end_effector(env: TwoJointArmReachEnv) -> None:
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    mujoco.mj_forward(env.model, env.data)


def _set_target_offset(env: TwoJointArmReachEnv, offset: np.ndarray) -> None:
    target = env.data.site("end_effector").xpos.copy()
    target[:2] += np.asarray(offset, dtype=np.float64)
    env.data.mocap_pos[0] = target
    mujoco.mj_forward(env.model, env.data)


def _set_joint_state(
    env: TwoJointArmReachEnv, qpos: np.ndarray, qvel: np.ndarray
) -> None:
    env.data.qpos[:] = 0.0
    env.data.qvel[:] = 0.0
    env.data.qpos[:2] = np.asarray(qpos, dtype=np.float64)
    env.data.qvel[:2] = np.asarray(qvel, dtype=np.float64)
    mujoco.mj_forward(env.model, env.data)


def _expect_value_error() -> None:
    for invalid in (np.zeros(1), np.asarray([np.nan, 0.0])):
        try:
            reach_reward(
                0.03,
                0.01,
                0.01,
                action=np.zeros(2),
                joint_velocities=invalid,
            )
        except ValueError:
            continue
        raise AssertionError("invalid joint velocity inputs must be rejected")


def _behavioral_check(output: Path) -> None:
    low_speed = np.asarray([0.6, 0.8], dtype=np.float64)
    high_speed = np.asarray([1.5, 2.0], dtype=np.float64)
    speed_norm = float(np.linalg.norm(high_speed))
    base_kwargs = {
        "previous_distance": 0.03,
        "success_threshold": 0.01,
        "action": np.zeros(2),
    }

    approach_low = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE + 1e-6,
        joint_velocities=low_speed,
    )
    approach_high = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE + 1e-6,
        joint_velocities=high_speed,
    )
    boundary_low = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
        joint_velocities=low_speed,
    )
    terminal_high = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
        joint_velocities=high_speed,
    )
    no_velocity = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
    )
    explicit_zero = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
        joint_velocities=np.zeros(2),
    )
    _assert(approach_low.components["terminal_stabilization"] == 0.0,
            "approach low speed must not be penalized")
    _assert(approach_high.components["terminal_stabilization"] == 0.0,
            "approach high speed must not be penalized")
    _assert(boundary_low.components["terminal_stabilization"] == 0.0,
            "speed at threshold must not be penalized")
    expected_penalty = -REFERENCE_COEFFICIENT * (
        speed_norm - REFERENCE_SPEED_THRESHOLD
    )
    _assert_close(
        terminal_high.components["terminal_stabilization"],
        expected_penalty,
        "terminal excess-speed penalty",
    )
    _assert(no_velocity.total == explicit_zero.total,
            "absent velocity must preserve the zero-speed reward")
    _assert(no_velocity.components["terminal_stabilization"] == 0.0,
            "absent velocity must have zero stabilization attribution")
    _assert(
        abs(terminal_high.components["terminal_stabilization"])
        <= 0.25 * abs(terminal_high.total),
        "controlled terminal penalty must remain bounded relative to reach reward",
    )
    just_outside = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE + 1e-9,
        joint_velocities=high_speed,
    )
    _assert(just_outside.components["terminal_stabilization"] == 0.0,
            "just outside terminal gate must be inactive")
    _expect_value_error()

    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        frame_skip=1,
        hold_seconds=0.06,
        max_episode_steps=12,
    )
    first_observation, _ = env.reset(seed=41)
    _assert(first_observation.shape == (11,), "reset observation shape changed")
    _set_joint_state(
        env,
        np.asarray([0.35, 0.75]),
        np.asarray([3.0, 0.0]),
    )
    _set_target_at_end_effector(env)
    env._previous_distance = env._distance_to_target()
    production_records = []
    for action in (
        np.asarray([2.0, -2.0]),
        np.asarray([0.0, 0.0]),
        np.asarray([-0.25, 0.25]),
    ):
        observation, reward, _, _, info = env.step(action)
        production_records.append(
            {
                "observation_shape": list(observation.shape),
                "reward": float(reward),
                "distance": float(info["distance"]),
                "held_steps": int(info["held_steps"]),
                "terminal_stabilization": float(
                    info["reward_components"]["terminal_stabilization"]
                ),
            }
        )
    _assert(np.isfinite([row["reward"] for row in production_records]).all(),
            "multiple production rewards must be finite")
    _assert(np.array_equal(env.data.ctrl, np.asarray([-0.25, 0.25])),
            "production action mapping must retain clipped controls")
    _assert(
        production_records[0]["distance"] <= REFERENCE_TERMINAL_DISTANCE,
        "controlled production transition must remain in terminal gate",
    )
    _assert(
        production_records[0]["terminal_stabilization"] < 0.0,
        "production wiring must pass post-transition velocity to reward",
    )

    hold_env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        frame_skip=1,
        hold_seconds=0.06,
        max_episode_steps=12,
    )
    hold_env.reset(seed=7)
    _set_target_at_end_effector(hold_env)
    hold_env._previous_distance = hold_env._distance_to_target()
    _, _, _, _, first_hold = hold_env.step(np.zeros(2))
    _, _, _, _, second_hold = hold_env.step(np.zeros(2))
    _set_target_offset(hold_env, np.asarray([0.05, 0.0]))
    _, _, terminated, _, interrupted_hold = hold_env.step(np.zeros(2))
    _assert(first_hold["held_steps"] == 1 and second_hold["held_steps"] == 2,
            "repeated in-gate transitions must advance the hold")
    _assert(interrupted_hold["held_steps"] == 0 and not terminated,
            "out-of-gate transition must interrupt the hold")
    _set_target_at_end_effector(hold_env)
    hold_env._previous_distance = hold_env._distance_to_target()
    _, _, _, _, resumed_hold = hold_env.step(np.zeros(2))
    _assert(resumed_hold["held_steps"] == 1,
            "in-gate transition must resume after interruption")
    reset_observation, _ = hold_env.reset(seed=7)
    repeated_reset_observation, _ = hold_env.reset(seed=7)
    _assert(np.array_equal(reset_observation, repeated_reset_observation),
            "seeded reset must remain deterministic")
    _assert(hold_env._held_steps == 0, "reset must clear hold state")

    artifact = {
        "check": "terminal_stabilization_reward",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "terminal_distance": REFERENCE_TERMINAL_DISTANCE,
            "speed_threshold": REFERENCE_SPEED_THRESHOLD,
            "coefficient": REFERENCE_COEFFICIENT,
            "approach_low_penalty": float(
                approach_low.components["terminal_stabilization"]
            ),
            "approach_high_penalty": float(
                approach_high.components["terminal_stabilization"]
            ),
            "terminal_high_penalty": float(
                terminal_high.components["terminal_stabilization"]
            ),
            "production_records": production_records,
            "hold_steps": [
                int(first_hold["held_steps"]),
                int(second_hold["held_steps"]),
                int(interrupted_hold["held_steps"]),
                int(resumed_hold["held_steps"]),
            ],
            "reset_held_steps": int(hold_env._held_steps),
        },
        "expected": {
            "approach_gate_zero_for_low_and_high_speed": True,
            "inclusive_terminal_gate_and_excess_speed_sign": True,
            "absent_velocity_preserves_reward": True,
            "finite_shape_validation": True,
            "production_velocity_wiring_active": True,
            "multiple_steps_and_action_clipping": True,
            "hold_interruption_and_resumption": True,
            "seeded_reset_clears_hold_state": True,
        },
        "checked_scope": [
            "direct reward behavior inside, outside, and on the terminal distance gate",
            "controlled low/high joint speeds and absent-velocity compatibility",
            "finite and shape validation for the new velocity input",
            "production reset, multiple steps, post-transition wiring, and clipping",
            "repeated hold transitions, interruption, resumption, and reset",
        ],
        "unchecked_scope": [
            "training exposure or learned-policy behavior",
            "official evaluation success and protected benchmark semantics",
            "continuous physics-step hold validity beyond exercised transitions",
            "scientific validity or causal benefit of the candidate intervention",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def _compatibility_check(output: Path) -> None:
    """Exercise changed reward/environment calls without a measurement artifact."""
    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        frame_skip=1,
        max_episode_steps=3,
    )
    observation, _ = env.reset(seed=19)
    _set_joint_state(
        env,
        np.asarray([0.35, 0.75]),
        np.asarray([2.0, 0.0]),
    )
    _set_target_at_end_effector(env)
    env._previous_distance = env._distance_to_target()
    next_observation, reward, _, _, info = env.step(np.asarray([2.0, -2.0]))
    components = info["reward_components"]
    _assert(observation.shape == (11,) and next_observation.shape == (11,),
            "production compatibility shapes must remain unchanged")
    _assert(np.isfinite(reward) and np.isfinite(next_observation).all(),
            "production compatibility outputs must be finite")
    _assert(np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0])),
            "production compatibility must retain action clipping")
    _assert("terminal_stabilization" in components,
            "production reward attribution must expose stabilization")
    _assert(
        info["distance"] <= REFERENCE_TERMINAL_DISTANCE
        and components["terminal_stabilization"] < 0.0,
        "production compatibility must pass active terminal velocity shaping",
    )

    direct = reach_reward(
        previous_distance=0.02,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
        success_threshold=0.01,
        action=np.zeros(2),
        joint_velocities=np.asarray([2.0, 0.0]),
    )
    _assert(direct.components["terminal_stabilization"] < 0.0,
            "direct changed reward call must activate the terminal penalty")
    artifact = {
        "check": "terminal_stabilization_reward_compatibility",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "observation_shape": list(observation.shape),
            "next_observation_shape": list(next_observation.shape),
            "finite_reward": bool(np.isfinite(reward)),
            "clipped_control": env.data.ctrl.tolist(),
            "production_distance": float(info["distance"]),
            "production_components": sorted(components),
            "production_terminal_stabilization": float(
                components["terminal_stabilization"]
            ),
            "direct_terminal_stabilization": float(
                direct.components["terminal_stabilization"]
            ),
        },
        "expected": {
            "production_path_executes": True,
            "observation_shapes_unchanged": True,
            "finite_outputs": True,
            "action_clipping_unchanged": True,
            "terminal_attribution_present_and_active": True,
        },
        "checked_scope": [
            "changed reward call with controlled finite velocity",
            "production environment reset and step wiring",
            "finite outputs, unchanged observation shape, and action clipping",
        ],
        "unchecked_scope": [
            "full behavioral hold/reset regression coverage",
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
