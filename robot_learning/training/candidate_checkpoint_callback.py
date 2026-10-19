import json
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback

from robot_learning.training.checkpoint import save_checkpoint


class CandidateCheckpointCallback(BaseCallback):
    """Save neutral candidates only after completed learning updates."""

    def __init__(self, output_dir: Path, every_steps: int) -> None:
        super().__init__()
        if every_steps < 1:
            raise ValueError("checkpoint cadence must be positive")
        self.output_dir = output_dir
        self.every_steps = every_steps
        self.next_checkpoint = every_steps

    def _on_step(self) -> bool:
        return True

    def _checkpoint_dir(self, timesteps: int) -> Path:
        return self.output_dir / "candidate_pool" / f"checkpoint-{timesteps}"

    def _save(self) -> None:
        checkpoint_dir = self._checkpoint_dir(self.num_timesteps)
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        save_checkpoint(self.model, self.training_env, checkpoint_dir)
        rewards = [
            float(episode["r"])
            for episode in self.model.ep_info_buffer
            if "r" in episode
        ]
        successes = [float(success) for success in self.model.ep_success_buffer]
        (checkpoint_dir / "training_metrics.json").write_text(
            json.dumps(
                {
                    "success_rate": sum(successes) / len(successes)
                    if successes
                    else None,
                    "ep_rew_mean": sum(rewards) / len(rewards) if rewards else None,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _on_rollout_start(self) -> None:
        if self.num_timesteps < self.next_checkpoint:
            return
        self._save()
        while self.next_checkpoint <= self.num_timesteps:
            self.next_checkpoint += self.every_steps

    def save_terminal_checkpoint(self) -> None:
        """Save the run's actual final steps as an ordinary candidate.

        Cadence alone can leave the run's true last steps unrepresented in the
        candidate pool; this saves it like any other checkpoint, unless
        cadence already covered the same step count.
        """
        if self._checkpoint_dir(self.num_timesteps).exists():
            return
        self._save()
