import json
import shutil
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from robot_learning.benchmark.metrics import (
    episode_hold_progress,
    evaluation_rank,
    milestone_steps,
    summarize_hold_progress,
)
from robot_learning.benchmark.spec import HOLD_SECONDS
from robot_learning.environments.reach_env import TwoJointArmReachEnv


def select_top_finalists(entries: list[dict], top_k: int) -> list[dict]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    return sorted(
        entries,
        key=lambda item: (tuple(item["rank"]), -int(item["timesteps"])),
        reverse=True,
    )[:top_k]


class SelectionCallback(BaseCallback):
    """Keep the top deterministic checkpoints seen inside one training run."""

    def __init__(
        self,
        output_dir: Path,
        eval_every_steps: int,
        episodes: int,
        top_k: int,
        seed: int = 2000,
    ) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.eval_every_steps = eval_every_steps
        self.episodes = episodes
        self.top_k = top_k
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        self.seed = seed
        self.next_evaluation = eval_every_steps
        self.last_evaluation_steps: int | None = None
        self.finalists: list[dict] = []

    def _normalize(self, obs: np.ndarray) -> np.ndarray:
        if hasattr(self.training_env, "normalize_obs"):
            return self.training_env.normalize_obs(obs[None, :])[0]
        return obs

    def _evaluate(self) -> dict:
        env = TwoJointArmReachEnv()
        successes = 0
        episode_progress: list[dict] = []
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
            progress = episode_hold_progress(distances, required_hold_steps)
            successes += progress["success"]
            episode_progress.append(progress)
        return {
            "success_percent": 100 * successes / self.episodes,
            "failed_episode_progress": summarize_hold_progress(
                episode_progress, required_hold_steps
            ),
            "timesteps": self.num_timesteps,
        }

    def _on_step(self) -> bool:
        return True

    def _evaluate_and_save(self) -> None:
        metrics = self._evaluate()
        self.last_evaluation_steps = self.num_timesteps
        current_rank = evaluation_rank(metrics)
        if len(self.finalists) >= self.top_k and current_rank <= tuple(
            self.finalists[-1]["rank"]
        ):
            return

        relative_path = Path("finalists") / f"checkpoint-{self.num_timesteps}"
        checkpoint_dir = self.output_dir / relative_path
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        self.model.save(checkpoint_dir / "model")
        if hasattr(self.model, "save_replay_buffer"):
            self.model.save_replay_buffer(checkpoint_dir / "replay_buffer.pkl")
        if hasattr(self.training_env, "save"):
            self.training_env.save(str(checkpoint_dir / "vecnormalize.pkl"))
        (checkpoint_dir / "selection.json").write_text(
            json.dumps(metrics, indent=2),
            encoding="utf-8",
        )
        entry = {
            "timesteps": self.num_timesteps,
            "rank": list(current_rank),
            "path": relative_path.as_posix(),
            "metrics": metrics,
        }
        self.finalists.append(entry)
        selected = select_top_finalists(self.finalists, self.top_k)
        selected_paths = {item["path"] for item in selected}
        removed = [
            item for item in self.finalists if item["path"] not in selected_paths
        ]
        self.finalists = selected
        for discarded in removed:
            shutil.rmtree(self.output_dir / discarded["path"])

        manifest = {
            "schema_version": 1,
            "top_k": self.top_k,
            "finalists": self.finalists,
        }
        (self.output_dir / "selection_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        if entry in self.finalists:
            update = {
                "position": self.finalists.index(entry) + 1,
                **entry,
            }
            (self.output_dir / "selection_update.json").write_text(
                json.dumps(update, indent=2), encoding="utf-8"
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
