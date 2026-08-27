import json
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from robot_learning.benchmark.metrics import achieved_milestones
from robot_learning.benchmark.spec import FINAL_STAGE_INDEX
from robot_learning.environments.reach_env import TwoJointArmReachEnv


class StageSelectionCallback(BaseCallback):
    """Keep the best deterministic checkpoint seen inside one training run."""

    def __init__(
        self,
        output_dir: Path,
        stage_index: int,
        eval_every_steps: int,
        episodes: int,
        seed: int = 2000,
    ) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.stage_index = stage_index
        self.eval_every_steps = eval_every_steps
        self.episodes = episodes
        self.seed = seed
        self.next_evaluation = eval_every_steps
        self.best_rank = (-1.0, float("-inf"))

    def _normalize(self, obs: np.ndarray) -> np.ndarray:
        if hasattr(self.training_env, "normalize_obs"):
            return self.training_env.normalize_obs(obs[None, :])[0]
        return obs

    def _evaluate(self) -> tuple[float, float]:
        env = TwoJointArmReachEnv(stage_index=FINAL_STAGE_INDEX)
        successes = 0
        closest: list[float] = []
        control_dt = env.model.opt.timestep * env.frame_skip
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
            successes += achieved_milestones(distances, control_dt)[self.stage_index]
            closest.append(min(distances))
        return 100 * successes / self.episodes, float(np.median(closest) * 100)

    def _on_step(self) -> bool:
        if self.num_timesteps < self.next_evaluation:
            return True
        success, closest_cm = self._evaluate()
        rank = (success, -closest_cm)
        if rank > self.best_rank:
            self.best_rank = rank
            self.model.save(self.output_dir / "best_model")
            if hasattr(self.model, "save_replay_buffer"):
                self.model.save_replay_buffer(
                    self.output_dir / "best_replay_buffer.pkl"
                )
            if hasattr(self.training_env, "save"):
                self.training_env.save(str(self.output_dir / "best_vecnormalize.pkl"))
            (self.output_dir / "best_selection.json").write_text(
                json.dumps(
                    {
                        "stage_index": self.stage_index,
                        "success_percent": success,
                        "closest_distance_cm": closest_cm,
                        "timesteps": self.num_timesteps,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        self.next_evaluation += self.eval_every_steps
        return True
