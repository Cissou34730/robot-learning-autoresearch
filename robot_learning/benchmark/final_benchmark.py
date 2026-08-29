"""Protected execution of the human-owned final benchmark."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import gymnasium as gym
import mujoco
import numpy as np

from robot_learning.benchmark import final_contract
from robot_learning.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer
from robot_learning.training.observations import OBSERVATION_SIZE, reach_observation


class FinalBenchmarkEnv(gym.Env[np.ndarray, np.ndarray]):
    """Fixed final task, deliberately separate from research environment defaults."""

    def __init__(self) -> None:
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self.success_threshold = final_contract.SUCCESS_THRESHOLD
        self.target_radius_range = final_contract.TARGET_RADIUS_RANGE
        self.frame_skip = final_contract.FRAME_SKIP
        self.max_episode_steps = final_contract.MAX_EPISODE_STEPS
        control_dt = self.model.opt.timestep * self.frame_skip
        self.hold_steps_required = max(round(final_contract.HOLD_SECONDS / control_dt), 1)
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBSERVATION_SIZE,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(2,), dtype=np.float32
        )
        self._step_count = 0
        self._held_steps = 0

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

    def _distance_to_target(self) -> float:
        return float(np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0]))

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict]:
        del options
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = 0.0
        self.data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(self.np_random.uniform(*self.target_radius_range))
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            float(self._end_effector_position()[2]),
        ]
        mujoco.mj_forward(self.model, self.data)
        self._step_count = 0
        self._held_steps = 0
        return reach_observation(self.data), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        self.data.ctrl[:] = np.clip(action, -1.0, 1.0)
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
        distance = self._distance_to_target()
        self._held_steps = self._held_steps + 1 if distance <= self.success_threshold else 0
        self._step_count += 1
        return (
            reach_observation(self.data),
            0.0,
            self._held_steps >= self.hold_steps_required,
            self._step_count >= self.max_episode_steps,
            {"distance": distance},
        )


def official_environment() -> FinalBenchmarkEnv:
    return FinalBenchmarkEnv()


def _hold_progress(distances: list[float], required_steps: int) -> dict:
    longest = 0
    current = 0
    best_inside = 0
    best_excess_cm = float("inf")
    threshold = final_contract.SUCCESS_THRESHOLD
    for distance in distances:
        current = current + 1 if distance <= threshold else 0
        longest = max(longest, current)
    for start in range(max(len(distances) - required_steps + 1, 1)):
        window = distances[start : start + required_steps]
        inside = sum(distance <= threshold for distance in window)
        excess_cm = 100 * sum(max(distance - threshold, 0.0) for distance in window)
        if (inside, -excess_cm) > (best_inside, -best_excess_cm):
            best_inside = inside
            best_excess_cm = excess_cm
    return {
        "success": longest >= required_steps,
        "longest_consecutive_steps": min(longest, required_steps),
        "best_window_inside_steps": best_inside,
        "best_window_excess_cm": best_excess_cm,
    }


def evaluate_final_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Evaluate one artifact with the fixed final contract only."""
    model = load_policy(model_path, algorithm)
    env = official_environment()
    normalize_obs = load_observation_normalizer(model_path) or (lambda obs: obs)
    control_dt = env.model.opt.timestep * final_contract.FRAME_SKIP
    required_steps = max(round(final_contract.HOLD_SECONDS / control_dt), 1)
    successes = 0
    final_distances: list[float] = []

    for episode in range(final_contract.EVALUATION_EPISODES):
        obs, _ = env.reset(seed=final_contract.EVALUATION_SEED + episode)
        distances: list[float] = []
        done = False
        while not done:
            action, _ = model.predict(normalize_obs(obs), deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(float(info["distance"]))
            done = terminated or truncated
        progress = _hold_progress(distances, required_steps)
        successes += int(progress["success"])
        final_distances.append(distances[-1])
        if progress_callback is not None:
            progress_callback(episode + 1, final_contract.EVALUATION_EPISODES)

    return {
        "schema_version": 1,
        "episodes": final_contract.EVALUATION_EPISODES,
        "seed": final_contract.EVALUATION_SEED,
        "success_percent": 100 * successes / final_contract.EVALUATION_EPISODES,
        "final_distance_cm": {
            "mean": float(np.mean(final_distances) * 100),
            "median": float(np.median(final_distances) * 100),
            "worst": float(np.max(final_distances) * 100),
        },
    }