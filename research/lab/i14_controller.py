"""I14 full-distribution test of a fixed model-based stabilizing controller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

JOINT_LIMIT = np.deg2rad(170.0)
HOLD_STEPS_REQUIRED = 100
SETTLING_STEPS = 10
MAX_STEPS = 500
POSITION_GAIN = 36.0
VELOCITY_GAIN = 12.0
ACCELERATION_LIMIT = 160.0


def _wrap_to_pi(values: np.ndarray) -> np.ndarray:
    return (np.asarray(values) + np.pi) % (2.0 * np.pi) - np.pi


def _ik_branches(target_x: float, target_y: float) -> tuple[np.ndarray, np.ndarray]:
    radius_squared = target_x**2 + target_y**2
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    bearing = float(np.arctan2(target_y, target_x))
    branches = []
    for elbow_angle in (elbow, -elbow):
        shoulder = bearing - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow_angle),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow_angle),
        )
        branches.append(
            np.array(
                [_wrap_to_pi(np.array([shoulder]))[0], elbow_angle],
                dtype=np.float64,
            )
        )
    return branches[0], branches[1]


class ComputedTorqueController:
    """Choose a feasible IK branch and regulate its pose with known dynamics."""

    def __init__(self, env: TwoJointArmReachEnv) -> None:
        self.env = env
        self._target_q: np.ndarray | None = None
        self._gear = np.asarray(env.model.actuator_gear[:2, 0], dtype=np.float64)
        if np.any(self._gear <= 0.0):
            raise ValueError("controller requires positive actuator gear")

    def reset(self) -> None:
        target = np.asarray(self.env.data.mocap_pos[0], dtype=np.float64)
        branches = _ik_branches(float(target[0]), float(target[1]))
        feasible = [
            branch
            for branch in branches
            if np.all(np.abs(branch) <= JOINT_LIMIT + 1e-9)
        ]
        if not feasible:
            raise ValueError("target has no feasible inverse-kinematic branch")
        current_q = np.asarray(self.env.data.qpos[:2], dtype=np.float64)
        self._target_q = min(
            feasible,
            key=lambda branch: (
                -float(np.min(JOINT_LIMIT - np.abs(branch))),
                float(np.sum(np.square(_wrap_to_pi(branch - current_q)))),
            ),
        ).copy()

    def action(self) -> np.ndarray:
        if self._target_q is None:
            raise RuntimeError("controller action requested before reset")
        current_q = np.asarray(self.env.data.qpos[:2], dtype=np.float64)
        current_qvel = np.asarray(self.env.data.qvel[:2], dtype=np.float64)
        q_error = _wrap_to_pi(self._target_q - current_q)
        desired_acceleration = np.clip(
            POSITION_GAIN * q_error - VELOCITY_GAIN * current_qvel,
            -ACCELERATION_LIMIT,
            ACCELERATION_LIMIT,
        )

        mujoco.mj_forward(self.env.model, self.env.data)
        mass_matrix = np.zeros((2, 2), dtype=np.float64)
        mujoco.mj_fullM(self.env.model, mass_matrix, self.env.data.qM)
        torque = (
            mass_matrix @ desired_acceleration
            + np.asarray(self.env.data.qfrc_bias[:2], dtype=np.float64)
            - np.asarray(self.env.data.qfrc_passive[:2], dtype=np.float64)
        )
        return np.clip(torque / self._gear, -1.0, 1.0).astype(np.float32)


def _run_episode(env: TwoJointArmReachEnv, seed: int) -> dict:
    env.reset(seed=seed)
    controller = ComputedTorqueController(env)
    controller.reset()
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    first_entry_step: int | None = None
    settling_step: int | None = None
    longest_hold = 0
    current_hold = 0
    hold_interruptions = 0
    was_inside = False
    min_distance_cm = float("inf")
    final_distance_cm = float("nan")
    action_saturation_steps = 0
    action_norms: list[float] = []
    success = False
    steps = 0
    terminated = False
    truncated = False
    while not (terminated or truncated):
        action = controller.action()
        if np.any(np.abs(action) >= 1.0 - 1e-7):
            action_saturation_steps += 1
        action_sums = float(np.linalg.norm(action))
        action_norms.append(action_sums)
        _, _, terminated, truncated, info = env.step(action)
        steps += 1
        distance_cm = 100.0 * float(info["distance"])
        held_steps = int(info.get("held_steps", 0))
        min_distance_cm = min(min_distance_cm, distance_cm)
        final_distance_cm = distance_cm
        if held_steps > 0:
            current_hold += 1
            longest_hold = max(longest_hold, current_hold)
            if first_entry_step is None:
                first_entry_step = steps
            if settling_step is None and current_hold >= SETTLING_STEPS:
                settling_step = steps - SETTLING_STEPS + 1
        else:
            if was_inside:
                hold_interruptions += 1
            current_hold = 0
        was_inside = held_steps > 0
        success = bool(info.get("is_success", False))

    return {
        "episode_seed": seed,
        "target_radius_cm": float(np.hypot(target[0], target[1]) * 100.0),
        "target_angle_degrees": float(np.degrees(np.arctan2(target[1], target[0]))),
        "success": success,
        "steps": steps,
        "first_entry_step": first_entry_step,
        "settling_step": settling_step,
        "longest_uninterrupted_hold_steps": longest_hold,
        "hold_interruptions": hold_interruptions,
        "min_distance_cm": min_distance_cm,
        "timeout_distance_cm": final_distance_cm if truncated else None,
        "action_saturation_steps": action_saturation_steps,
        "mean_action_norm": float(np.mean(action_norms)),
    }


def _group(records: list[dict]) -> dict:
    successes = sum(bool(record["success"]) for record in records)
    return {
        "episodes": len(records),
        "successes": successes,
        "success_percent": 100.0 * successes / len(records),
        "approach_failures": sum(record["first_entry_step"] is None for record in records),
        "settling_failures": sum(
            record["first_entry_step"] is not None
            and record["settling_step"] is None
            for record in records
        ),
        "post_settling_hold_failures": sum(
            record["settling_step"] is not None and not record["success"]
            for record in records
        ),
        "mean_longest_uninterrupted_hold_steps": float(
            np.mean([record["longest_uninterrupted_hold_steps"] for record in records])
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes < 1 or args.seed < 0:
        raise ValueError("episodes must be positive and seed must be non-negative")

    env = TwoJointArmReachEnv(max_episode_steps=MAX_STEPS)
    records = [_run_episode(env, args.seed + episode) for episode in range(args.episodes)]
    artifact = {
        "schema_version": 1,
        "diagnostic": "I14 fixed computed-torque controller",
        "episodes": args.episodes,
        "seed": args.seed,
        "controller": {
            "position_gain": POSITION_GAIN,
            "velocity_gain": VELOCITY_GAIN,
            "acceleration_limit": ACCELERATION_LIMIT,
            "branch_rule": "feasible branch with maximum minimum joint-limit margin, then nearest from reset",
            "runtime_policy_assistance": False,
        },
        "summary": _group(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
