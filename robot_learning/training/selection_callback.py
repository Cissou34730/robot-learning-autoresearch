import json
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from robot_learning.benchmark.metrics import (
    evaluation_rank,
    maximum_consecutive_hold_steps,
    milestone_steps,
    summarize_consecutive_hold_steps,
)
from robot_learning.benchmark.spec import HOLD_SECONDS
from robot_learning.environments.reach_env import TwoJointArmReachEnv


class SelectionCallback(BaseCallback):
    """Keep the best deterministic checkpoint seen inside one training run."""

    def __init__(
        self,
        output_dir: Path,
        eval_every_steps: int,
        episodes: int,
        seed: int = 2000,
    ) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.eval_every_steps = eval_every_steps
        self.episodes = episodes
        self.seed = seed
        self.next_evaluation = eval_every_steps
        self.last_evaluation_steps: int | None = None
        self.best_rank = (
            float("-inf"),
            float("-inf"),
            float("-inf"),
            float("-inf"),
        )

    def _normalize(self, obs: np.ndarray) -> np.ndarray:
        if hasattr(self.training_env, "normalize_obs"):
            return self.training_env.normalize_obs(obs[None, :])[0]
        return obs

    def _evaluate(self) -> dict:
        env = TwoJointArmReachEnv()
        successes = 0
        hold_steps: list[int] = []
        closest: list[float] = []
        control_dt = env.model.opt.timestep * env.frame_skip
        required_hold_steps = milestone_steps(HOLD_SECONDS, control_dt)
        for episode in range(self.episodes):
            obs, _ = env.reset(seed=self.seed + episode)
            distances: list[float] = []
            done = False
            while not done:
                action, _ = self.model.predict(
                    self._normalize(obs), deterministic=True
                )
                obs, _, terminated, truncated, info = env.step(action)
                distances.append(float(info["distance"]))
                done = terminated or truncated
            maximum_hold = maximum_consecutive_hold_steps(distances)
            successes += maximum_hold >= required_hold_steps
            hold_steps.append(maximum_hold)
            closest.append(min(distances))
        return {
            "success_percent": 100 * successes / self.episodes,
            "consecutive_hold_steps": summarize_consecutive_hold_steps(
                hold_steps, required_hold_steps
            ),
            "closest_distance_cm": {
                "median": float(np.median(closest) * 100),
            },
            "timesteps": self.num_timesteps,
        }

    def _on_step(self) -> bool:
        return True

    def _evaluate_and_save(self) -> None:
        metrics = self._evaluate()
        self.last_evaluation_steps = self.num_timesteps
        current_rank = evaluation_rank(metrics)
        if current_rank <= self.best_rank:
            return
        self.best_rank = current_rank
        self.model.save(self.output_dir / "best_model")
        if hasattr(self.model, "save_replay_buffer"):
            self.model.save_replay_buffer(
                self.output_dir / "best_replay_buffer.pkl"
            )
        if hasattr(self.training_env, "save"):
            self.training_env.save(str(self.output_dir / "best_vecnormalize.pkl"))
        (self.output_dir / "best_selection.json").write_text(
            json.dumps(metrics, indent=2),
            encoding="utf-8",
        )

    def _on_rollout_start(self) -> None:
        if self.num_timesteps < self.next_evaluation:
            return
        self._evaluate_and_save()
        while self.next_evaluation <= self.num_timesteps:
            self.next_evaluation += self.eval_every_steps

    def _on_training_end(self) -> None:
        if self.last_evaluation_steps != self.num_timesteps:
            self._evaluate_and_save()
