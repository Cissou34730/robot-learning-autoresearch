from typing import Any, ClassVar

import gymnasium as gym
import mujoco
import numpy as np

from robot_learning.rewards.reach_reward import reach_reward
from robot_learning.robots.two_joint_arm import MAX_REACH, TWO_JOINT_ARM_XML_PATH


class TwoJointArmReachEnv(gym.Env[np.ndarray, np.ndarray]):
    metadata: ClassVar[dict[str, Any]] = {"render_modes": []}

    def __init__(
        self,
        max_episode_steps: int = 200,
        frame_skip: int = 10,
        target_radius_range: tuple[float, float] = (0.06, 0.20),
        success_threshold: float = 0.03,
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

        n_joints = 2
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(2 * n_joints + 3,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(n_joints,), dtype=np.float32
        )

        self._step_count = 0
        self._previous_distance = 0.0

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
        return np.concatenate(
            [
                self.data.qpos,
                self.data.qvel,
                self._end_effector_position() - self.data.mocap_pos[0],
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
        reward = reach_reward(
            self._previous_distance, distance, self.success_threshold, action
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = distance <= self.success_threshold
        truncated = self._step_count >= self.max_episode_steps
        info = {"distance": distance, "is_success": terminated}
        return self._observation(), float(reward), terminated, truncated, info
