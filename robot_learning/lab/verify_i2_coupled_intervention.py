"""Defect-sensitive laboratory check for the I2 coupled intervention.

This module is an executable proposal, not a scientific validation.  It uses
controlled MuJoCo states, repeated reward transitions, the production training
environment, and the production evaluator with a bounded fake runtime.  The
check has not been executed by the author.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    UPPER_ARM_LENGTH,
)
from robot_learning.scenario import evaluation
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.training.environment import make_training_env
from robot_learning.training.reward import reach_reward

_UNCHECKED_SCOPE = [
    "policy quality or scientific validity",
    "long-horizon training and stabilization performance",
    "official benchmark or panel acceptance",
]
_JOINT_NAMES = ("shoulder", "elbow")
_IK_TOLERANCE = 1e-9


class _BoundedRuntime:
    def __init__(self, observation_space) -> None:
        self.observation_space = observation_space
        self.reset_count = 0
        self.predict_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def predict(self, observation) -> np.ndarray:
        self.predict_count += 1
        if np.asarray(observation).shape != (OBSERVATION_SIZE,):
            raise AssertionError("runtime received the wrong observation shape")
        return np.zeros(2, dtype=np.float32)


class _TrackedEnvironment(TwoJointArmReachEnv):
    def __init__(self) -> None:
        super().__init__(
            target_radius_range=(0.06, 0.20),
            max_episode_steps=3,
            hold_seconds=1000.0,
        )
        self.reset_count = 0
        self.step_count = 0
        self.observation_shapes: list[tuple[int, ...]] = []
        self.reward_components: list[dict[str, float]] = []

    def reset(self, **kwargs):
        self.reset_count += 1
        observation, info = super().reset(**kwargs)
        self.observation_shapes.append(tuple(observation.shape))
        return observation, info

    def step(self, action):
        self.step_count += 1
        observation, reward, terminated, truncated, info = super().step(action)
        self.observation_shapes.append(tuple(observation.shape))
        self.reward_components.append(dict(info["reward_components"]))
        return observation, reward, terminated, truncated, info


def _set_target(env: TwoJointArmReachEnv, target: tuple[float, float, float]) -> None:
    env.data.mocap_pos[0] = np.asarray(target, dtype=np.float64)
    mujoco.mj_forward(env.model, env.data)


def _legacy_observation_reference(data) -> np.ndarray:
    """Recompute the retained eleven values without using reach_observation."""
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cosine = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    def wrap(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    elbow_folded = -elbow_open
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            data.site("end_effector").xpos.copy() - data.mocap_pos[0],
            [
                wrap(shoulder_for_elbow(elbow_open) - float(data.qpos[0])),
                wrap(elbow_open - float(data.qpos[1])),
                wrap(shoulder_for_elbow(elbow_folded) - float(data.qpos[0])),
                wrap(elbow_folded - float(data.qpos[1])),
            ],
        ]
    )


def _reference_branch_features(model, target: tuple[float, float, float]) -> list[float]:
    """Calculate expected indicators and normalized margins independently."""
    radius = float(np.hypot(target[0], target[1]))
    target_angle = float(np.arctan2(target[1], target[0]))
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    ids = [
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        for name in _JOINT_NAMES
    ]
    ranges = [
        (float(model.jnt_range[joint_id][0]), float(model.jnt_range[joint_id][1]))
        for joint_id in ids
    ]
    if not -1.0 - _IK_TOLERANCE <= cosine <= 1.0 + _IK_TOLERANCE:
        return [0.0, 0.0, 0.0, 0.0]

    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    expected: list[float] = []
    for sign in (1.0, -1.0):
        elbow = sign * elbow_magnitude
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        angles = []
        for angle, (lower, upper) in zip((shoulder, elbow), ranges):
            candidates = [angle + 2.0 * np.pi * turns for turns in range(-2, 3)]
            in_range = [
                candidate
                for candidate in candidates
                if lower - _IK_TOLERANCE <= candidate <= upper + _IK_TOLERANCE
            ]
            angles.append(
                min(in_range, key=lambda candidate: abs(candidate - angle))
                if in_range
                else (angle + np.pi) % (2.0 * np.pi) - np.pi
            )
        feasible = all(
            lower - _IK_TOLERANCE <= angle <= upper + _IK_TOLERANCE
            for angle, (lower, upper) in zip(angles, ranges)
        )
        margin = (
            min(
                min(angle - lower, upper - angle) / (upper - lower)
                for angle, (lower, upper) in zip(angles, ranges)
            )
            if feasible
            else 0.0
        )
        expected.extend([float(feasible), float(np.clip(margin, 0.0, 0.5))])
    return expected


def _check_observations() -> dict:
    env = TwoJointArmReachEnv(max_episode_steps=2)
    try:
        env.reset(seed=3)
        env.data.qpos[:] = [0.1, -0.2]
        env.data.qvel[:] = [0.3, -0.4]
        mujoco.mj_forward(env.model, env.data)

        reachable = (0.15, 0.0, 0.02)
        _set_target(env, reachable)
        observed_reachable = env._observation()
        expected_reachable = _reference_branch_features(env.model, reachable)
        retained = _legacy_observation_reference(env.data)
        if observed_reachable.shape != (OBSERVATION_SIZE,):
            raise AssertionError(f"observation shape {observed_reachable.shape}")
        if observed_reachable.dtype != np.float32:
            raise AssertionError(f"observation dtype {observed_reachable.dtype}")
        if not np.allclose(observed_reachable[:11], retained, atol=1e-6):
            raise AssertionError("the retained eleven observation values changed")
        if not np.allclose(
            observed_reachable[11:], expected_reachable, atol=1e-6
        ):
            raise AssertionError(
                f"reachable branch features {observed_reachable[11:].tolist()!r}"
                f" != {expected_reachable!r}"
            )
        if observed_reachable[11] != 1.0 or observed_reachable[13] != 1.0:
            raise AssertionError("reachable target did not expose both branches")
        if not 0.0 < observed_reachable[12] <= 0.5 or not 0.0 < observed_reachable[
            14
        ] <= 0.5:
            raise AssertionError("reachable branch margins were not bounded positive")

        # This target is inside the unconstrained workspace but both branches
        # place the shoulder beyond the compiled +/-170 degree range.
        range_infeasible = (-0.219, 0.0, 0.02)
        _set_target(env, range_infeasible)
        observed_infeasible = env._observation()
        expected_infeasible = _reference_branch_features(env.model, range_infeasible)
        if not np.allclose(
            observed_infeasible[11:], expected_infeasible, atol=1e-6
        ):
            raise AssertionError(
                f"infeasible branch features {observed_infeasible[11:].tolist()!r}"
            )
        if observed_infeasible[11:].tolist() != [0.0, 0.0, 0.0, 0.0]:
            raise AssertionError("infeasible branches lacked the zero sentinel")
        if not np.allclose(
            observed_infeasible[:11],
            _legacy_observation_reference(env.data),
            atol=1e-6,
        ):
            raise AssertionError("range classification changed retained features")
        return {
            "shape": list(observed_reachable.shape),
            "dtype": str(observed_reachable.dtype),
            "reachable_features": observed_reachable[11:].tolist(),
            "reachable_expected": expected_reachable,
            "range_infeasible_features": observed_infeasible[11:].tolist(),
            "range_infeasible_expected": expected_infeasible,
        }
    finally:
        env.close()


def _assert_components_sum(result) -> None:
    if not np.isclose(result.total, sum(result.components.values())):
        raise AssertionError("reward components do not attribute the scalar total")


def _check_reward_transitions() -> dict:
    fast_endpoint = np.asarray([0.20, 0.0, 0.0], dtype=np.float64)
    fast_joints = np.asarray([0.8, -0.6], dtype=np.float64)
    far = reach_reward(
        0.21,
        0.20,
        0.01,
        held_steps=0,
        previous_held_steps=0,
        endpoint_velocity=fast_endpoint,
        joint_velocity=fast_joints,
    )
    far_stationary = reach_reward(
        0.21,
        0.20,
        0.01,
        held_steps=0,
        previous_held_steps=0,
        endpoint_velocity=np.zeros(3),
        joint_velocity=np.zeros(2),
    )
    near = reach_reward(
        0.02,
        0.009,
        0.01,
        held_steps=1,
        previous_held_steps=0,
        endpoint_velocity=fast_endpoint,
        joint_velocity=fast_joints,
    )
    outside = reach_reward(
        0.009,
        0.015,
        0.01,
        held_steps=0,
        previous_held_steps=1,
        penalize_outside=True,
        endpoint_velocity=fast_endpoint,
        joint_velocity=fast_joints,
    )
    for result in (far, far_stationary, near, outside):
        _assert_components_sum(result)
    if far.components["speed_penalty"] >= 0.0:
        raise AssertionError("far speed penalty was not sign-correct")
    if far_stationary.components["speed_penalty"] != 0.0:
        raise AssertionError("stationary speed penalty was not zero")
    if abs(far.components["speed_penalty"]) >= 0.05 * abs(
        near.components["speed_penalty"]
    ):
        raise AssertionError("far speed penalty was not weakly gated")
    if near.components["speed_penalty"] >= 0.0:
        raise AssertionError("near speed penalty was not negative")
    if outside.components["speed_penalty"] >= 0.0:
        raise AssertionError("outside-band speed penalty was not negative")
    if outside.components["outside_band"] >= 0.0:
        raise AssertionError("outside-band transition lost its existing penalty")

    hold_entry = reach_reward(
        0.02,
        0.009,
        0.01,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=3,
        endpoint_velocity=np.zeros(3),
        joint_velocity=np.zeros(2),
    )
    hold_exit = reach_reward(
        0.009,
        0.015,
        0.01,
        held_steps=0,
        previous_held_steps=1,
        hold_steps_required=3,
        penalize_outside=True,
        endpoint_velocity=np.zeros(3),
        joint_velocity=np.zeros(2),
    )
    hold_complete = reach_reward(
        0.009,
        0.009,
        0.01,
        held_steps=3,
        previous_held_steps=2,
        hold_steps_required=3,
        endpoint_velocity=np.zeros(3),
        joint_velocity=np.zeros(2),
    )
    for result in (hold_entry, hold_exit, hold_complete):
        _assert_components_sum(result)
    if hold_entry.components["hold_progress"] <= 0.0:
        raise AssertionError("hold entry no longer advances hold progress")
    if hold_exit.components["hold_progress"] != 0.0:
        raise AssertionError("hold exit changed the existing forfeiture behavior")
    if hold_complete.components["hold_complete"] <= 0.0:
        raise AssertionError("hold completion transition no longer completes")
    return {
        "far_speed_penalty": far.components["speed_penalty"],
        "far_stationary_speed_penalty": far_stationary.components["speed_penalty"],
        "near_speed_penalty": near.components["speed_penalty"],
        "outside_speed_penalty": outside.components["speed_penalty"],
        "outside_band_penalty": outside.components["outside_band"],
        "hold_entry": hold_entry.components,
        "hold_exit": hold_exit.components,
        "hold_complete": hold_complete.components,
    }


def _run_controlled_evaluation(
    episodes: int,
) -> tuple[dict, _TrackedEnvironment, _BoundedRuntime]:
    controlled_env = _TrackedEnvironment()
    runtime = _BoundedRuntime(controlled_env.observation_space)
    original_loader = evaluation.load_runtime
    original_factory = evaluation.make_evaluation_env
    evaluation.load_runtime = lambda _path, _algorithm: runtime
    evaluation.make_evaluation_env = lambda policy_runtime=None: controlled_env
    try:
        result = evaluation.evaluate_research_model(
            Path("controlled-policy.zip"), episodes=episodes, seed=17
        )
    finally:
        evaluation.load_runtime = original_loader
        evaluation.make_evaluation_env = original_factory
        controlled_env.close()
    return result, controlled_env, runtime


def _check_production_training_environment() -> dict:
    env = make_training_env()
    try:
        observations = []
        rewards = []
        for seed in (5, 6):
            observation, _ = env.reset(seed=seed)
            observations.append(tuple(observation.shape))
            observation, reward, _, _, info = env.step(np.zeros(2, dtype=np.float32))
            observations.append(tuple(observation.shape))
            rewards.append(float(reward))
            if "speed_penalty" not in info["reward_components"]:
                raise AssertionError("training path omitted speed_penalty attribution")
    finally:
        env.close()
    if any(shape != (OBSERVATION_SIZE,) for shape in observations):
        raise AssertionError(f"training observation shapes {observations!r}")
    return {
        "resets": 2,
        "steps": 2,
        "observation_shapes": observations,
        "rewards": rewards,
    }


def _check_production_evaluator(episodes: int) -> dict:
    result, environment, runtime = _run_controlled_evaluation(episodes)
    if any(shape != (OBSERVATION_SIZE,) for shape in environment.observation_shapes):
        raise AssertionError(
            f"evaluator observation shapes {environment.observation_shapes!r}"
        )
    if not environment.reward_components:
        raise AssertionError("evaluator did not produce reward component attribution")
    required = {
        "speed_penalty",
        "endpoint_speed_penalty",
        "joint_speed_penalty",
    }
    for components in environment.reward_components:
        if not required.issubset(components):
            raise AssertionError(f"missing speed components: {components!r}")
    if environment.reset_count != episodes or runtime.reset_count != episodes:
        raise AssertionError("repeated evaluator resets were not exercised")
    if runtime.predict_count != environment.step_count:
        raise AssertionError("bounded runtime predictions did not follow steps")
    if any(not item["truncated"] for item in result["episode_results"]):
        raise AssertionError("bounded evaluator episodes did not truncate")
    return {
        "episodes": episodes,
        "resets": environment.reset_count,
        "steps": environment.step_count,
        "runtime_resets": runtime.reset_count,
        "runtime_predictions": runtime.predict_count,
        "observation_shapes": [
            list(shape) for shape in environment.observation_shapes
        ],
        "reward_component_keys": sorted(environment.reward_components[0]),
    }


def _run_check(compatibility: bool) -> dict:
    if compatibility:
        evaluator = _check_production_evaluator(episodes=1)
        return {
            "checked_scope": [
                "one short production evaluator episode",
                "production observation shape and reward attribution",
            ],
            "observed": {"evaluator": evaluator},
            "expected": {
                "one_episode": True,
                "observation_shape": [OBSERVATION_SIZE],
                "speed_penalty_component": True,
            },
        }
    observations = _check_observations()
    reward = _check_reward_transitions()
    training = _check_production_training_environment()
    evaluator = _check_production_evaluator(episodes=2)
    return {
        "checked_scope": [
            "retained observation values and float32 shape",
            "reachable both-branch IK features",
            "compiled-range-infeasible branch sentinel",
            "far, near, and outside-band speed gating",
            "repeated hold-entry, hold-exit, and completion transitions",
            "repeated production training resets and steps",
            "repeated production evaluator resets, steps, and bounded runtime",
        ],
        "observed": {
            "observations": observations,
            "reward": reward,
            "training": training,
            "evaluator": evaluator,
        },
        "expected": {
            "observation_shape": [OBSERVATION_SIZE],
            "observation_dtype": "float32",
            "infeasible_margin_sentinel": 0.0,
            "far_speed_penalty_weak_and_negative": True,
            "near_and_outside_speed_penalty_negative": True,
            "hold_transitions_preserved": True,
            "production_paths_exercised": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    try:
        payload = {
            "status": "passed",
            "unchecked_scope": _UNCHECKED_SCOPE,
            **_run_check(compatibility=args.compatibility),
        }
    except Exception as error:
        payload = {
            "status": "failed",
            "checked_scope": ["I2 coupled intervention verification"],
            "unchecked_scope": _UNCHECKED_SCOPE,
            "error": f"{type(error).__name__}: {error}",
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        raise
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
