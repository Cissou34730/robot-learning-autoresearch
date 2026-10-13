"""Executable laboratory check for velocity-aware stabilization shaping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.reward import reach_reward

SUCCESS_THRESHOLD = 0.01
EXPECTED_NEAR_BAND_WIDTH = 0.005
ZERO_ACTION = np.zeros(2, dtype=np.float32)


def _near_target_reward(distance: float, velocity: np.ndarray):
    return reach_reward(
        previous_distance=distance,
        current_distance=distance,
        success_threshold=SUCCESS_THRESHOLD,
        action=ZERO_ACTION,
        joint_velocities=velocity,
    )


def _prepare_near_target_state(
    env: TwoJointArmReachEnv, joint_velocities: np.ndarray
) -> None:
    env.data.mocap_pos[0] = env._end_effector_position()
    env.data.qvel[:] = joint_velocities
    mujoco.mj_forward(env.model, env.data)
    env._previous_distance = env._distance_to_target()


def _run_behavioral_check(output: Path) -> None:
    failures: list[str] = []
    observed: dict[str, object] = {}
    expected: dict[str, object] = {
        "zero_velocity_stabilization_penalty": 0.0,
        "higher_near_band_velocity_has_lower_total_reward": True,
        "outside_near_band_stabilization_penalty": 0.0,
        "reset_clears_step_hold_and_velocity_state": True,
        "production_step_wires_post_step_velocity": True,
    }

    zero = _near_target_reward(
        SUCCESS_THRESHOLD + 0.001, np.zeros(2, dtype=np.float64)
    )
    low = _near_target_reward(
        SUCCESS_THRESHOLD + 0.001, np.array([0.25, 0.0], dtype=np.float64)
    )
    high = _near_target_reward(
        SUCCESS_THRESHOLD + 0.001, np.array([0.75, 0.0], dtype=np.float64)
    )
    near_edge = _near_target_reward(
        SUCCESS_THRESHOLD + 0.75 * EXPECTED_NEAR_BAND_WIDTH,
        np.array([0.75, 0.0], dtype=np.float64),
    )
    outside_zero = _near_target_reward(
        SUCCESS_THRESHOLD + EXPECTED_NEAR_BAND_WIDTH + 0.001,
        np.zeros(2, dtype=np.float64),
    )
    outside_fast = _near_target_reward(
        SUCCESS_THRESHOLD + EXPECTED_NEAR_BAND_WIDTH + 0.001,
        np.array([2.0, -1.0], dtype=np.float64),
    )

    observed["controlled_rewards"] = {
        "zero_velocity": {
            "total": zero.total,
            "stabilization_penalty": zero.components["stabilization_penalty"],
        },
        "low_near_band_velocity": {
            "total": low.total,
            "stabilization_penalty": low.components["stabilization_penalty"],
        },
        "high_near_band_velocity": {
            "total": high.total,
            "stabilization_penalty": high.components["stabilization_penalty"],
        },
        "near_band_edge_velocity": {
            "total": near_edge.total,
            "stabilization_penalty": near_edge.components[
                "stabilization_penalty"
            ],
        },
        "outside_zero_velocity": {
            "total": outside_zero.total,
            "stabilization_penalty": outside_zero.components["stabilization_penalty"],
        },
        "outside_fast_velocity": {
            "total": outside_fast.total,
            "stabilization_penalty": outside_fast.components["stabilization_penalty"],
        },
    }
    if not np.isclose(zero.components["stabilization_penalty"], 0.0):
        failures.append("zero velocity did not receive zero stabilization penalty")
    if not (
        high.total < low.total < zero.total
        and high.components["stabilization_penalty"]
        < low.components["stabilization_penalty"]
        < 0.0
        and near_edge.components["stabilization_penalty"] < 0.0
    ):
        failures.append("increasing near-band velocity did not strictly lower reward")
    if not (
        np.isclose(outside_zero.components["stabilization_penalty"], 0.0)
        and np.isclose(outside_fast.components["stabilization_penalty"], 0.0)
        and np.isclose(outside_zero.total, outside_fast.total)
    ):
        failures.append("velocity was penalized outside the near-target band")

    env = TwoJointArmReachEnv()
    try:
        reset_states: list[dict[str, object]] = []
        for seed in (11, 12, 13):
            env.reset(seed=seed)
            env.step(ZERO_ACTION)
            env.reset(seed=seed + 100)
            reset_states.append(
                {
                    "seed": seed + 100,
                    "step_count": env._step_count,
                    "held_steps": env._held_steps,
                    "outside_after_hold": env._outside_after_hold,
                    "previous_distance_matches": bool(
                        np.isclose(
                            env._previous_distance, env._distance_to_target()
                        )
                    ),
                    "qvel_zero": bool(np.allclose(env.data.qvel, 0.0)),
                }
            )
        observed["repeated_reset_states"] = reset_states
        if any(
            state["step_count"] != 0
            or state["held_steps"] != 0
            or state["outside_after_hold"]
            or not state["previous_distance_matches"]
            or not state["qvel_zero"]
            for state in reset_states
        ):
            failures.append("reset retained step, hold, or velocity state")

        env.reset(seed=21)
        _prepare_near_target_state(env, np.array([0.75, 0.0], dtype=np.float64))
        _, _, _, _, info = env.step(ZERO_ACTION)
        production_components = info["reward_components"]
        production_penalty = production_components.get("stabilization_penalty", 0.0)
        observed["production_step"] = {
            "post_step_qvel": env.data.qvel[:2].tolist(),
            "distance": info["distance"],
            "stabilization_penalty": production_penalty,
        }
        if production_penalty >= 0.0:
            failures.append(
                "production environment did not pass near-target velocity to reward"
            )
    finally:
        env.close()

    artifact = {
        "check": "stabilization_reward_behavior",
        "status": "failed" if failures else "passed",
        "observed": observed,
        "expected": expected,
        "checked_scope": [
            "controlled reward behavior at zero, increasing near-band, and outside-band velocities",
            "repeated production-environment reset and step transitions",
            "post-step joint-velocity wiring from the environment into reward",
            "reset clearing simulator and environment episode state",
        ],
        "unchecked_scope": [
            "policy learning, convergence, and official evaluation outcomes",
            "the physical causal effect of the shaping term on hold success",
            "velocity behavior during internal MuJoCo substeps",
            "training recipe selection or coefficient optimality",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise AssertionError("; ".join(failures))


def _run_compatibility_check(output: Path) -> None:
    failures: list[str] = []
    observed: dict[str, object] = {}
    env = TwoJointArmReachEnv()
    try:
        env.reset(seed=31)
        first = env.step(ZERO_ACTION)
        env.reset(seed=32)
        _prepare_near_target_state(env, np.array([0.5, 0.0], dtype=np.float64))
        second = env.step(ZERO_ACTION)
        first_components = first[4]["reward_components"]
        second_components = second[4]["reward_components"]
        observed = {
            "first_step_reward": first[1],
            "second_step_reward": second[1],
            "first_step_components": first_components,
            "second_step_components": second_components,
            "reset_step_count": env._step_count,
        }
        if "stabilization_penalty" not in first_components:
            failures.append("changed reward path did not expose stabilization attribution")
        if not np.isfinite(first[1]) or not np.isfinite(second[1]):
            failures.append("production step returned a non-finite reward")
        if second_components.get("stabilization_penalty", 0.0) >= 0.0:
            failures.append("controlled near-target production step had no penalty")
    finally:
        env.close()

    artifact = {
        "check": "stabilization_reward_compatibility",
        "status": "failed" if failures else "passed",
        "observed": observed,
        "expected": {
            "production_reset_and_two_steps_complete": True,
            "stabilization_component_present": True,
            "controlled_near_target_step_penalized": True,
            "finite_rewards": True,
        },
        "checked_scope": [
            "actual TwoJointArmReachEnv reset and step production paths",
            "actual reward integration with controlled post-step velocity",
        ],
        "unchecked_scope": [
            "full behavioral boundary and monotonicity checks",
            "policy training and official evaluation",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise AssertionError("; ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("behavioral", "compatibility"), default="behavioral")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "compatibility":
        _run_compatibility_check(args.output)
    else:
        _run_behavioral_check(args.output)


if __name__ == "__main__":
    main()
