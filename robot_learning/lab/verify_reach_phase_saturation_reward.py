"""Laboratory verification for reach-phase saturation-aware reward shaping.

This is an executable check proposal, not a scientific validity claim.  It
uses an independent scalar reference for the two new terms and controlled
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
REFERENCE_ACTION_THRESHOLD = 0.8
REFERENCE_ACTION_COEFFICIENT = 0.05
REFERENCE_ACTION_EXCESS_CAP = 0.2
REFERENCE_SPEED_THRESHOLD = 2.0
REFERENCE_SPEED_COEFFICIENT = 0.01
REFERENCE_SPEED_EXCESS_CAP = 5.0


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


def _expect_value_errors() -> None:
    invalid_inputs = (
        {"action": np.zeros(1), "joint_velocities": np.zeros(2)},
        {"action": np.asarray([np.nan, 0.0]), "joint_velocities": np.zeros(2)},
        {"action": np.zeros(2), "joint_velocities": np.asarray([np.inf, 0.0])},
    )
    for invalid in invalid_inputs:
        try:
            reach_reward(
                0.04,
                0.03,
                0.01,
                action=invalid["action"],
                joint_velocities=invalid["joint_velocities"],
            )
        except ValueError:
            continue
        raise AssertionError("non-finite and malformed inputs must be rejected")


def _behavioral_check(output: Path) -> None:
    benign_action = np.asarray([0.4, -0.4], dtype=np.float64)
    stressed_action = np.asarray([1.0, -1.0], dtype=np.float64)
    benign_speed = np.asarray([1.0, 1.0], dtype=np.float64)
    stressed_speed = np.asarray([3.0, 4.0], dtype=np.float64)
    stressed_speed_norm = float(np.linalg.norm(stressed_speed))
    base_kwargs = {
        "previous_distance": 0.04,
        "success_threshold": 0.01,
    }

    benign = reach_reward(
        **base_kwargs,
        current_distance=0.03,
        action=benign_action,
        joint_velocities=benign_speed,
    )
    stressed = reach_reward(
        **base_kwargs,
        current_distance=0.03,
        action=stressed_action,
        joint_velocities=stressed_speed,
    )
    just_outside = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE + 1e-9,
        action=stressed_action,
        joint_velocities=stressed_speed,
    )
    terminal = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE,
        action=stressed_action,
        joint_velocities=stressed_speed,
    )
    inside_terminal = reach_reward(
        **base_kwargs,
        current_distance=REFERENCE_TERMINAL_DISTANCE - 1e-9,
        action=stressed_action,
        joint_velocities=stressed_speed,
    )

    expected_action_penalty = -REFERENCE_ACTION_COEFFICIENT * min(
        max(
            float(np.max(np.abs(stressed_action))) - REFERENCE_ACTION_THRESHOLD,
            0.0,
        ),
        REFERENCE_ACTION_EXCESS_CAP,
    )
    expected_speed_penalty = -REFERENCE_SPEED_COEFFICIENT * min(
        max(stressed_speed_norm - REFERENCE_SPEED_THRESHOLD, 0.0),
        REFERENCE_SPEED_EXCESS_CAP,
    )
    expected_terminal_stabilization = -0.02 * (stressed_speed_norm - 1.0)

    for name in ("reach_phase_action_saturation", "reach_phase_joint_speed"):
        _assert(name in stressed.components, f"missing reward attribution: {name}")
        _assert(name in benign.components, f"missing benign attribution: {name}")
        _assert(name in terminal.components, f"missing terminal attribution: {name}")
    _assert(
        benign.components["reach_phase_action_saturation"] == 0.0
        and benign.components["reach_phase_joint_speed"] == 0.0,
        "below-threshold pre-entry inputs must have zero new terms",
    )
    _assert_close(
        stressed.components["reach_phase_action_saturation"],
        expected_action_penalty,
        "independent action-saturation reference",
    )
    _assert_close(
        stressed.components["reach_phase_joint_speed"],
        expected_speed_penalty,
        "independent joint-speed reference",
    )
    _assert(
        stressed.components["reach_phase_action_saturation"] < 0.0
        and stressed.components["reach_phase_joint_speed"] < 0.0,
        "stressed pre-entry shaping must be negative",
    )
    _assert(
        abs(stressed.components["reach_phase_action_saturation"])
        <= REFERENCE_ACTION_COEFFICIENT * REFERENCE_ACTION_EXCESS_CAP
        and abs(stressed.components["reach_phase_joint_speed"])
        <= REFERENCE_SPEED_COEFFICIENT * REFERENCE_SPEED_EXCESS_CAP,
        "both new penalties must remain bounded",
    )
    _assert(
        just_outside.components["reach_phase_action_saturation"] < 0.0
        and just_outside.components["reach_phase_joint_speed"] < 0.0,
        "the new terms must use the outside-of-terminal gate",
    )
    for result in (terminal, inside_terminal):
        _assert(
            result.components["reach_phase_action_saturation"] == 0.0
            and result.components["reach_phase_joint_speed"] == 0.0,
            "new reach-phase terms must be inactive in the terminal neighborhood",
        )
    _assert_close(
        terminal.components["terminal_stabilization"],
        expected_terminal_stabilization,
        "terminal stabilization must remain active",
    )
    _assert(
        terminal.components["terminal_stabilization"] < 0.0,
        "terminal stabilization sign must remain negative",
    )
    _assert(
        np.isfinite(
            [stressed.total, *stressed.components.values(), terminal.total]
        ).all(),
        "controlled reward totals and attributions must be finite",
    )
    _expect_value_errors()

    env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        frame_skip=1,
        hold_seconds=2.0,
        max_episode_steps=8,
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
        components = info["reward_components"]
        _assert(observation.shape == (11,), "step observation shape changed")
        _assert(np.isfinite(reward), "production reward must be finite")
        _assert(
            np.isfinite(observation).all(),
            "production observation must remain finite",
        )
        _assert(
            np.isfinite(list(components.values())).all(),
            "production attribution must remain finite",
        )
        production_records.append(
            {
                "observation_shape": list(observation.shape),
                "reward": float(reward),
                "distance": float(info["distance"]),
                "held_steps": int(info["held_steps"]),
                "action_saturation": float(
                    components["reach_phase_action_saturation"]
                ),
                "joint_speed": float(components["reach_phase_joint_speed"]),
                "terminal_stabilization": float(
                    components["terminal_stabilization"]
                ),
            }
        )
        if len(production_records) == 1:
            _assert(
                np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0])),
                "production action clipping must map saturation inputs to bounds",
            )
    _assert(
        np.array_equal(env.data.ctrl, np.asarray([-0.25, 0.25])),
        "production action mapping must retain clipped controls",
    )
    _assert(
        production_records[0]["terminal_stabilization"] < 0.0,
        "production wiring must retain terminal velocity shaping",
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
    _assert(
        first_hold["held_steps"] == 1 and second_hold["held_steps"] == 2,
        "repeated in-gate transitions must advance the hold",
    )
    _assert(
        interrupted_hold["held_steps"] == 0 and not terminated,
        "out-of-gate transition must interrupt the hold",
    )
    _set_target_at_end_effector(hold_env)
    hold_env._previous_distance = hold_env._distance_to_target()
    _, _, _, _, resumed_hold = hold_env.step(np.zeros(2))
    _assert(
        resumed_hold["held_steps"] == 1,
        "in-gate transition must resume after interruption",
    )

    reset_observation, _ = hold_env.reset(seed=7)
    isolated_env = TwoJointArmReachEnv(
        target_radius_range=(0.10, 0.10),
        frame_skip=1,
        hold_seconds=0.06,
        max_episode_steps=12,
    )
    isolated_observation, _ = isolated_env.reset(seed=7)
    _assert(
        np.array_equal(reset_observation, isolated_observation),
        "seeded reset must isolate prior transition state",
    )
    _assert(hold_env._held_steps == 0, "reset must clear hold state")

    artifact = {
        "check": "reach_phase_saturation_reward",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "reference": {
                "terminal_distance": REFERENCE_TERMINAL_DISTANCE,
                "action_threshold": REFERENCE_ACTION_THRESHOLD,
                "action_coefficient": REFERENCE_ACTION_COEFFICIENT,
                "speed_threshold": REFERENCE_SPEED_THRESHOLD,
                "speed_coefficient": REFERENCE_SPEED_COEFFICIENT,
            },
            "benign_components": benign.components,
            "stressed_components": stressed.components,
            "terminal_components": terminal.components,
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
            "independent_reference_matches_both_new_terms": True,
            "benign_pre_entry_terms_zero": True,
            "stressed_pre_entry_terms_negative_and_finite": True,
            "terminal_gate_disables_new_terms": True,
            "terminal_stabilization_retained": True,
            "finite_and_shape_validation": True,
            "attribution_keys_present": True,
            "observation_shape_and_action_clipping_unchanged": True,
            "hold_interruption_resumption_and_reset_unchanged": True,
        },
        "checked_scope": [
            "independent action saturation and joint-speed references",
            "pre-entry, boundary, and terminal-neighborhood gating",
            "sign, boundedness, finite outputs, and attribution keys",
            "production reset, repeated steps, observation shape, and clipping",
            "repeated hold transitions, interruption, resumption, and seeded reset isolation",
        ],
        "unchecked_scope": [
            "training exposure, convergence, or learned-policy behavior",
            "official evaluation success and protected evaluator validity",
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
        max_episode_steps=4,
    )
    observation, _ = env.reset(seed=19)
    _set_joint_state(
        env,
        np.asarray([0.35, 0.75]),
        np.asarray([3.0, 0.0]),
    )
    _set_target_at_end_effector(env)
    env._previous_distance = env._distance_to_target()
    records = []
    for action in (np.asarray([2.0, -2.0]), np.zeros(2)):
        next_observation, reward, _, _, info = env.step(action)
        components = info["reward_components"]
        _assert(observation.shape == (11,), "compatibility observation shape changed")
        _assert(next_observation.shape == (11,), "compatibility step shape changed")
        _assert(np.isfinite(reward) and np.isfinite(next_observation).all(),
                "compatibility outputs must be finite")
        _assert(
            "reach_phase_action_saturation" in components
            and "reach_phase_joint_speed" in components,
            "compatibility attribution must expose both new terms",
        )
        records.append(
            {
                "reward": float(reward),
                "observation_shape": list(next_observation.shape),
                "clipped_control": env.data.ctrl.tolist(),
                "distance": float(info["distance"]),
                "new_terms": {
                    "action": float(components["reach_phase_action_saturation"]),
                    "speed": float(components["reach_phase_joint_speed"]),
                },
            }
        )
        if len(records) == 1:
            _assert(
                np.array_equal(env.data.ctrl, np.asarray([1.0, -1.0])),
                "compatibility action clipping must map inputs to bounds",
            )
        observation = next_observation
    _assert(
        np.array_equal(env.data.ctrl, np.asarray([0.0, 0.0])),
        "compatibility path must retain action clipping and assignment",
    )

    direct = reach_reward(
        previous_distance=0.04,
        current_distance=0.03,
        success_threshold=0.01,
        action=np.asarray([1.0, -1.0]),
        joint_velocities=np.asarray([3.0, 4.0]),
    )
    _assert(
        direct.components["reach_phase_action_saturation"] < 0.0
        and direct.components["reach_phase_joint_speed"] < 0.0,
        "direct changed reward call must activate both pre-entry terms",
    )
    artifact = {
        "check": "reach_phase_saturation_reward_compatibility",
        "execution_note": "The author did not execute this verification.",
        "observed": {
            "production_records": records,
            "direct_new_terms": {
                "action": direct.components["reach_phase_action_saturation"],
                "speed": direct.components["reach_phase_joint_speed"],
            },
            "production_component_keys": sorted(
                env.step(np.zeros(2))[4]["reward_components"]
            ),
        },
        "expected": {
            "production_path_executes": True,
            "observation_shapes_unchanged": True,
            "finite_outputs": True,
            "action_clipping_unchanged": True,
            "both_new_attribution_keys_present": True,
            "both_new_terms_activate_pre_entry": True,
        },
        "checked_scope": [
            "changed direct reward call with controlled finite action and velocity",
            "production environment reset and repeated step wiring",
            "finite outputs, unchanged observation shape, and action clipping",
        ],
        "unchecked_scope": [
            "full behavioral gate and hold/reset regression coverage",
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
