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
from robot_learning.training.comparison import paired_comparison

SELECTION_SIGNIFICANCE_LEVEL = 0.05


def _time_diverse(entries: list[dict], count: int) -> list[dict]:
    ordered = sorted(entries, key=lambda item: int(item["timesteps"]))
    if count <= 0:
        return []
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]

    first = int(ordered[0]["timesteps"])
    last = int(ordered[-1]["timesteps"])
    selected: list[dict] = []
    for position in range(count):
        target = first + (last - first) * position / (count - 1)
        available = [item for item in ordered if item not in selected]
        selected.append(
            min(
                available,
                key=lambda item: (
                    abs(int(item["timesteps"]) - target),
                    int(item["timesteps"]),
                ),
            )
        )
    return selected


def comparison_status(entry: dict) -> str:
    comparison = entry.get("paired_vs_reference")
    if comparison is None or comparison["exact_p_value"] > SELECTION_SIGNIFICANCE_LEVEL:
        return "equivalent"
    if comparison["net_wins"] > 0:
        return "meaningfully better"
    if comparison["net_wins"] < 0:
        return "meaningfully worse"
    return "equivalent"


def select_top_finalists(entries: list[dict], top_k: int) -> list[dict]:
    """Prefer evidence, then preserve training-time diversity under equivalence."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if not entries:
        return []
    if not any("paired_vs_reference" in item for item in entries):
        return sorted(
            entries,
            key=lambda item: (tuple(item["rank"]), -int(item["timesteps"])),
            reverse=True,
        )[:top_k]

    better = sorted(
        [item for item in entries if comparison_status(item) == "meaningfully better"],
        key=lambda item: (
            item["paired_vs_reference"]["net_wins"],
            tuple(item["rank"]),
        ),
        reverse=True,
    )
    selected = better[:top_k]
    remaining_slots = top_k - len(selected)
    equivalent = [
        item
        for item in entries
        if comparison_status(item) == "equivalent" and item not in selected
    ]
    selected.extend(_time_diverse(equivalent, remaining_slots))
    remaining_slots = top_k - len(selected)
    if remaining_slots:
        worse = sorted(
            [item for item in entries if item not in selected],
            key=lambda item: (
                item.get("paired_vs_reference", {}).get("net_wins", 0),
                tuple(item["rank"]),
            ),
            reverse=True,
        )
        selected.extend(worse[:remaining_slots])
    return selected


class SelectionCallback(BaseCallback):
    """Keep meaningful or time-diverse deterministic checkpoints from one run."""

    def __init__(
        self,
        output_dir: Path,
        eval_every_steps: int,
        episodes: int,
        top_k: int,
        seed: int = 2000,
        reference_metrics_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.eval_every_steps = eval_every_steps
        self.episodes = episodes
        self.top_k = top_k
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        self.seed = seed
        self.reference_metrics = (
            json.loads(reference_metrics_path.read_text(encoding="utf-8"))
            if reference_metrics_path is not None
            else None
        )
        if self.reference_metrics is not None:
            if int(self.reference_metrics["seed"]) != seed:
                raise ValueError("selection reference uses a different seed")
            if int(self.reference_metrics["episodes"]) != episodes:
                raise ValueError("selection reference uses a different episode count")
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
        episode_results: list[dict] = []
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
            episode_results.append(
                {
                    "episode": episode,
                    "episode_seed": self.seed + episode,
                    "success": bool(progress["success"]),
                    "longest_consecutive_steps": progress[
                        "longest_consecutive_steps"
                    ],
                    "best_window_inside_steps": progress["best_window_inside_steps"],
                    "best_window_excess_cm": progress["best_window_excess_cm"],
                }
            )
        return {
            "schema_version": 3,
            "episodes": self.episodes,
            "seed": self.seed,
            "success_percent": 100 * successes / self.episodes,
            "failed_episode_progress": summarize_hold_progress(
                episode_progress, required_hold_steps
            ),
            "episode_results": episode_results,
            "timesteps": self.num_timesteps,
        }

    def _on_step(self) -> bool:
        return True

    def _evaluate_and_save(self) -> None:
        metrics = self._evaluate()
        self.last_evaluation_steps = self.num_timesteps
        current_rank = evaluation_rank(metrics)
        comparison = None
        if self.reference_metrics is not None:
            comparison = paired_comparison([metrics], [self.reference_metrics])

        relative_path = Path("selection_pool") / f"checkpoint-{self.num_timesteps}"
        checkpoint_dir = self.output_dir / relative_path
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        self.model.save(checkpoint_dir / "model")
        if hasattr(self.model, "save_replay_buffer"):
            self.model.save_replay_buffer(checkpoint_dir / "replay_buffer.pkl")
        if hasattr(self.training_env, "save"):
            self.training_env.save(str(checkpoint_dir / "vecnormalize.pkl"))
        (checkpoint_dir / "selection.json").write_text(
            json.dumps(metrics, indent=2), encoding="utf-8"
        )
        entry = {
            "timesteps": self.num_timesteps,
            "rank": list(current_rank),
            "path": relative_path.as_posix(),
            "metrics": metrics,
        }
        if comparison is not None:
            entry["paired_vs_reference"] = comparison
        self.finalists.append(entry)
        update = {
            "status": (
                comparison_status(entry)
                if comparison is not None
                else "unreferenced checkpoint pool"
            ),
            **entry,
        }
        (self.output_dir / "selection_update.json").write_text(
            json.dumps(update, indent=2), encoding="utf-8"
        )

    def _finalize_selection(self) -> None:
        selected = select_top_finalists(self.finalists, self.top_k)
        selected_paths = {item["path"] for item in selected}
        for discarded in self.finalists:
            if discarded["path"] in selected_paths:
                continue
            path = self.output_dir / discarded["path"]
            if path.exists():
                shutil.rmtree(path)
        self.finalists = selected
        manifest = {
            "schema_version": 2,
            "top_k": self.top_k,
            "selection_basis": "paired evidence, then training-time diversity",
            "finalists": self.finalists,
        }
        (self.output_dir / "selection_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
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
        self._finalize_selection()
