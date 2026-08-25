from typing import Any, ClassVar

import gymnasium as gym
import mujoco
import numpy as np

from robot_learning.rewards.reach_reward import reach_reward
from robot_learning.robots.two_joint_arm import (
    FOREARM_LENGTH,
    MAX_REACH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)


class TwoJointArmReachEnv(gym.Env[np.ndarray, np.ndarray]):
    metadata: ClassVar[dict[str, Any]] = {"render_modes": []}

    def __init__(
        self,
        max_episode_steps: int = 500,
        frame_skip: int = 10,
        target_radius_range: tuple[float, float] = (0.06, 0.20),
        success_threshold: float = 0.01,
        hold_seconds: float = 2.0,
    ) -> None:
        super().__init__()
        if not 0 < target_radius_range[1] <= MAX_REACH:
            raise ValueError(
                f"target radius must stay within the arm reach ({MAX_REACH} m)"
            )

        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.target_radius_range = target_radius_range
        self.success_threshold = success_threshold

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        control_dt = self.model.opt.timestep * self.frame_skip
        self.hold_steps_required = round(hold_seconds / control_dt)

        n_joints = 2
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(2 * n_joints + 3 + 4 + 1,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(n_joints,), dtype=np.float32
        )

        self._step_count = 0
        self._previous_distance = 0.0
        self._held_steps = 0

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
        self.data.mocap_pos[0] = [radius * np.cos(angle), radius * np.sin(angle), 0.0]

    def _observation(self) -> np.ndarray:
        def wrap_to_pi(angle: float) -> float:
            return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

        def shoulder_for_elbow(elbow: float) -> float:
            return float(
                np.arctan2(target_y, target_x)
                - np.arctan2(
                    FOREARM_LENGTH * np.sin(elbow),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
                )
            )

        target_x = float(self.data.mocap_pos[0][0])
        target_y = float(self.data.mocap_pos[0][1])
        cos_elbow = (
            target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
        shoulder_open = shoulder_for_elbow(elbow_open)
        elbow_folded = -elbow_open
        shoulder_folded = shoulder_for_elbow(elbow_folded)
        ik_deltas = [
            wrap_to_pi(shoulder_open - float(self.data.qpos[0])),
            wrap_to_pi(elbow_open - float(self.data.qpos[1])),
            wrap_to_pi(shoulder_folded - float(self.data.qpos[0])),
            wrap_to_pi(elbow_folded - float(self.data.qpos[1])),
        ]
        return np.concatenate(
            [
                self.data.qpos,
                self.data.qvel,
                self._end_effector_position() - self.data.mocap_pos[0],
                ik_deltas,
                [self._held_steps / self.hold_steps_required],
            ]
        ).astype(np.float32)

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = 0.0
        self.data.qvel[:] = 0.0
        self._sample_target_position()
        mujoco.mj_forward(self.model, self.data)

        self._step_count = 0
        self._previous_distance = self._distance_to_target()
        self._held_steps = 0
        return self._observation(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action = np.clip(
            np.asarray(action, dtype=np.float64),
            self.action_space.low,
            self.action_space.high,
        )
        self.data.ctrl[:] = action
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)

        distance = self._distance_to_target()

        if distance <= self.success_threshold:
            self._held_steps += 1
        else:
            self._held_steps = 0

        reward = reach_reward(
            self._previous_distance,
            distance,
            self.success_threshold,
            action,
            held_steps=self._held_steps,
            hold_steps_required=self.hold_steps_required,
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
        }
        return self._observation(), float(reward), terminated, truncated, info
