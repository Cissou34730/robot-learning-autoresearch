"""Protected task-reference evaluation.

An independent, human-owned execution of the original human-defined task,
reconstructed from the pre-research implementation and cross-checked against
`final_contract.py`. It measures a saved policy over the fixed development panel
of `reference_contract.py`, so models stay comparable on the original task while
research freely changes its own environment, sampling, reward, curriculum,
evaluation and instrumentation.

It shares no task mechanics with `robot_learning/scenario/`, and none with the
final benchmark either: the final benchmark is the existing trusted verdict path
and this development capability must not enlarge its regression surface. The
duplication below is deliberate, small, protected and stable.

This evaluation never declares the objective reached.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import gymnasium as gym
import mujoco
import numpy as np

from robot_learning.benchmark import final_contract, reference_contract
from robot_learning.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer

TASK_REFERENCE_EVALUATION_KIND = "task_reference"


def _policy_observation_contract() -> tuple[int, Callable[[Any], np.ndarray]]:
    """Resolved on use: the scenario package imports the panel built here."""
    from robot_learning.training.observations import (
        OBSERVATION_SIZE,
        reach_observation,
    )

    return OBSERVATION_SIZE, reach_observation


class TaskReferenceEnv(gym.Env[np.ndarray, np.ndarray]):
    """The original human-defined task, independent of research environments."""

    def __init__(self) -> None:
        super().__init__()
        observation_size, self._reach_observation = _policy_observation_contract()
        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self.success_threshold = final_contract.SUCCESS_THRESHOLD
        self.target_radius_range = final_contract.TARGET_RADIUS_RANGE
        self.frame_skip = final_contract.FRAME_SKIP
        self.max_episode_steps = final_contract.MAX_EPISODE_STEPS
        control_dt = self.model.opt.timestep * self.frame_skip
        self.hold_steps_required = max(
            round(final_contract.HOLD_SECONDS / control_dt), 1
        )
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(observation_size,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(2,), dtype=np.float32
        )
        self._step_count = 0
        self._held_steps = 0

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

    def _distance_to_target(self) -> float:
        return float(
            np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0])
        )

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
        # The arm is planar but its plane sits above the world origin.
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            float(self._end_effector_position()[2]),
        ]
        mujoco.mj_forward(self.model, self.data)
        self._step_count = 0
        self._held_steps = 0
        return self._reach_observation(self.data), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        self.data.ctrl[:] = np.clip(action, -1.0, 1.0)
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
        distance = self._distance_to_target()
        self._held_steps = (
            self._held_steps + 1 if distance <= self.success_threshold else 0
        )
        self._step_count += 1
        return (
            self._reach_observation(self.data),
            0.0,
            self._held_steps >= self.hold_steps_required,
            self._step_count >= self.max_episode_steps,
            {"distance": distance, "held_steps": self._held_steps},
        )


def task_reference_environment() -> TaskReferenceEnv:
    return TaskReferenceEnv()


def task_reference_panel() -> dict:
    """The protected panel identity, for orchestration and display only."""
    return {
        "panel": reference_contract.PANEL_ID,
        "panel_version": reference_contract.PANEL_VERSION,
        "episodes": reference_contract.EVALUATION_EPISODES,
        "seed": reference_contract.EVALUATION_SEED,
    }


def evaluate_task_reference_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Measure one model on the fixed task-reference panel."""
    panel = task_reference_panel()
    episodes = int(panel["episodes"])
    seed = int(panel["seed"])
    model = load_policy(model_path, algorithm)
    env = task_reference_environment()
    normalize_obs = load_observation_normalizer(model_path)

    episode_results: list[dict] = []
    for episode in range(episodes):
        episode_seed = seed + episode
        obs, _ = env.reset(seed=episode_seed)
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        steps = 0
        terminated = False
        truncated = False
        distance = float("nan")
        while not (terminated or truncated):
            normalized_obs = normalize_obs(obs) if normalize_obs is not None else obs
            action, _ = model.predict(normalized_obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            distance = float(info["distance"])
            steps += 1
        episode_results.append(
            {
                "episode": episode,
                "episode_seed": episode_seed,
                "target_radius_cm": float(np.hypot(target[0], target[1]) * 100.0),
                "target_angle_degrees": float(
                    np.degrees(np.arctan2(target[1], target[0]))
                ),
                # A complete hold is the task outcome, not Gymnasium termination.
                "success": bool(terminated),
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "final_distance_cm": 100.0 * distance,
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(item["success"] for item in episode_results)
    return {
        "schema_version": 1,
        "evaluation_kind": TASK_REFERENCE_EVALUATION_KIND,
        "model": str(model_path),
        "panel": panel["panel"],
        "panel_version": panel["panel_version"],
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100 * successes / episodes,
        "episode_results": episode_results,
    }
