"""Shared scenario mechanics for training and evaluation.

This module owns every behavior shared by training and evaluation: the MuJoCo
model, target sampling, success and hold semantics, observations and reward.
Training-only target construction lives in
`robot_learning/training/environment.py` so it can change without
altering how a saved policy is measured.

The benchmark constants are defaults, not a contract: research may train on a
different distribution, tolerance or horizon. The human-defined task is
enforced only by the protected benchmark in `benchmark/`.
"""

from typing import Any, ClassVar

import gymnasium as gym
import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.scenario.policy_io import make_policy_io
from robot_learning.training.reward import reach_reward


def _finite_vector(value: Any, shape: tuple[int, ...], *, context: str) -> np.ndarray:
    """Convert a diagnostic vector without accepting implicit reshaping."""
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be a numeric vector with shape {shape}") from exc
    if array.shape != shape:
        raise ValueError(f"{context} must have shape {shape}, got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{context} contains non-finite values")
    return array.copy()


class TwoJointArmReachEnv(gym.Env[np.ndarray, np.ndarray]):
    metadata: ClassVar[dict[str, Any]] = {"render_modes": []}

    def __init__(
        self,
        *,
        target_radius_range: tuple[float, float] = TARGET_RADIUS_RANGE,
        success_threshold: float = SUCCESS_THRESHOLD,
        hold_seconds: float = HOLD_SECONDS,
        frame_skip: int = FRAME_SKIP,
        max_episode_steps: int = MAX_EPISODE_STEPS,
        policy_runtime=None,
    ) -> None:
        super().__init__()
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.target_radius_range = target_radius_range
        self.policy_io = policy_runtime.io if policy_runtime else make_policy_io()

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)

        self.success_threshold = success_threshold
        control_dt = self.model.opt.timestep * self.frame_skip
        self.hold_steps_required = round(hold_seconds / control_dt)

        n_joints = 2
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(OBSERVATION_SIZE,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(n_joints,), dtype=np.float32
        )

        self._step_count = 0
        self._previous_distance = 0.0
        self._held_steps = 0
        self._outside_after_hold = False
        self._has_reached = False
        self._last_substep_trace: list[dict[str, Any]] = []

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

    def _distance_to_target(self) -> float:
        return float(
            np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0])
        )

    def _sample_target_position(self) -> None:
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(
            self.np_random.uniform(
                self.target_radius_range[0], self.target_radius_range[1]
            )
        )
        # The arm is planar but its plane sits above the world origin. Keep the
        # target in that same plane so the 3-D distance can genuinely reach zero.
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]

    def _observation(self) -> np.ndarray:
        return self.policy_io.observe(self.data)

    def _diagnostic_snapshot(self) -> dict[str, Any]:
        """Capture one simulator state using only public MuJoCo state fields."""
        qpos = _finite_vector(
            self.data.qpos, (self.model.nq,), context="MuJoCo qpos"
        )
        qvel = _finite_vector(
            self.data.qvel, (self.model.nv,), context="MuJoCo qvel"
        )
        ctrl = _finite_vector(
            self.data.ctrl, (self.model.nu,), context="MuJoCo ctrl"
        )
        joint_count = 2
        qpos_addresses = np.asarray(
            self.model.jnt_qposadr[:joint_count], dtype=np.int64
        )
        if qpos_addresses.shape != (joint_count,):
            raise ValueError("MuJoCo joint position addresses must describe two joints")
        if np.any(qpos_addresses < 0) or np.any(qpos_addresses >= self.model.nq):
            raise ValueError("MuJoCo joint position addresses are out of bounds")
        joint_qpos = qpos[qpos_addresses]
        _finite_vector(qvel[:joint_count], (joint_count,), context="MuJoCo joint qvel")

        joint_ranges = _finite_vector(
            self.model.jnt_range[:joint_count].reshape(-1),
            (joint_count * 2,),
            context="MuJoCo joint ranges",
        ).reshape(joint_count, 2)
        joint_limited = np.asarray(
            self.model.jnt_limited[:joint_count], dtype=bool
        )
        if joint_limited.shape != (joint_count,):
            raise ValueError("MuJoCo joint limit flags must describe two joints")
        distance_to_limit = np.minimum(
            joint_qpos - joint_ranges[:, 0], joint_ranges[:, 1] - joint_qpos
        )
        # The distance is retained in radians; the boolean proximity field uses
        # a fixed one-degree diagnostic band and does not affect the dynamics.
        proximity = joint_limited & (distance_to_limit <= np.deg2rad(1.0))
        active = joint_limited & (
            (joint_qpos <= joint_ranges[:, 0])
            | (joint_qpos >= joint_ranges[:, 1])
        )

        contact_pairs = [
            [int(self.data.contact[index].geom1), int(self.data.contact[index].geom2)]
            for index in range(int(self.data.ncon))
        ]
        distance = self._distance_to_target()
        if not np.isfinite(distance):
            raise ValueError("endpoint distance is non-finite")
        return {
            "qpos": qpos.tolist(),
            "qvel": qvel.tolist(),
            "ctrl": ctrl.tolist(),
            "endpoint_distance": float(distance),
            "contact_count": int(self.data.ncon),
            "contact_geom_pairs": contact_pairs,
            "joint_limit_distance": distance_to_limit.tolist(),
            "joint_limit_proximity": proximity.tolist(),
            "joint_limit_active": active.tolist(),
        }

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        del options
        super().reset(seed=seed)
        if self.policy_io.reset is not None:
            self.policy_io.reset()
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = 0.0
        self.data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self._sample_target_position()
        mujoco.mj_forward(self.model, self.data)

        self._step_count = 0
        self._previous_distance = self._distance_to_target()
        self._held_steps = 0
        self._outside_after_hold = False
        self._has_reached = False
        self._last_substep_trace = []
        return self._observation(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        try:
            supplied_action = np.asarray(action, dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise ValueError("action must be a numeric two-element vector") from exc
        if supplied_action.shape != self.action_space.shape:
            raise ValueError(
                f"action must have shape {self.action_space.shape}, "
                f"got {supplied_action.shape}"
            )
        if not np.all(np.isfinite(supplied_action)):
            raise ValueError("action contains non-finite values")
        try:
            post_policy_action = np.asarray(
                self.policy_io.action(action), dtype=np.float64
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "post-policy action must be a numeric two-element vector"
            ) from exc
        if post_policy_action.shape != self.action_space.shape:
            raise ValueError(
                "post-policy action must have shape "
                f"{self.action_space.shape}, got {post_policy_action.shape}"
            )
        if not np.all(np.isfinite(post_policy_action)):
            raise ValueError("post-policy action contains non-finite values")
        clipped_action = np.clip(
            post_policy_action, self.action_space.low, self.action_space.high
        )
        joint_saturation = (
            (post_policy_action < self.action_space.low)
            | (post_policy_action > self.action_space.high)
        )
        self.data.ctrl[:] = clipped_action
        substep_trace = []
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
            substep_trace.append(self._diagnostic_snapshot())

        post_control = self._diagnostic_snapshot()
        distance = float(post_control["endpoint_distance"])

        previous_held_steps = self._held_steps
        if distance <= self.success_threshold:
            self._held_steps += 1
            self._outside_after_hold = False
        else:
            if previous_held_steps > 0:
                self._outside_after_hold = True
            self._held_steps = 0

        reward = reach_reward(
            self._previous_distance,
            distance,
            self.success_threshold,
            clipped_action,
            held_steps=self._held_steps,
            previous_held_steps=previous_held_steps,
            hold_steps_required=self.hold_steps_required,
            penalize_outside=self._outside_after_hold,
        )
        self._previous_distance = distance

        first_reach = not self._has_reached and self._held_steps > 0
        if first_reach:
            self._has_reached = True
        hold_interrupted = previous_held_steps > 0 and self._held_steps == 0
        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        self._last_substep_trace = substep_trace
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            "first_reach": first_reach,
            "hold_interrupted": hold_interrupted,
            "post_policy_action": post_policy_action.tolist(),
            "clipped_action": clipped_action.tolist(),
            "joint_saturation": joint_saturation.tolist(),
            "action_saturated": bool(np.any(joint_saturation)),
            **post_control,
            "substep_trace": substep_trace,
            # Arbitrary scenario-owned attribution; the RL algorithm still only
            # ever sees `reward.total`.
            "reward_components": reward.components,
        }
        return self._observation(), float(reward.total), terminated, truncated, info


def make_evaluation_env(*, policy_runtime=None) -> gym.Env:
    """Build the fixed-distribution environment used by research evaluation."""
    env = TwoJointArmReachEnv(
        target_radius_range=TARGET_RADIUS_RANGE, policy_runtime=policy_runtime
    )
    if policy_runtime is not None:
        env.observation_space = policy_runtime.observation_space
    return env
