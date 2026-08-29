from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback


class CandidateCheckpointCallback(BaseCallback):
    """Save neutral candidates only after completed learning updates."""

    def __init__(self, output_dir: Path, every_steps: int) -> None:
        super().__init__()
        if every_steps < 1:
            raise ValueError("checkpoint cadence must be positive")
        self.output_dir = output_dir
        self.every_steps = every_steps
        self.next_checkpoint = every_steps
        self.last_checkpoint_steps: int | None = None

    def _on_step(self) -> bool:
        return True

    def _save(self) -> None:
        checkpoint_dir = (
            self.output_dir / "candidate_pool" / f"checkpoint-{self.num_timesteps}"
        )
        checkpoint_dir.mkdir(parents=True, exist_ok=False)
        self.model.save(checkpoint_dir / "model")
        if hasattr(self.model, "save_replay_buffer"):
            self.model.save_replay_buffer(checkpoint_dir / "replay_buffer.pkl")
        if hasattr(self.training_env, "save"):
            self.training_env.save(str(checkpoint_dir / "vecnormalize.pkl"))
        self.last_checkpoint_steps = self.num_timesteps

    def _on_rollout_start(self) -> None:
        if self.num_timesteps < self.next_checkpoint:
            return
        self._save()
        while self.next_checkpoint <= self.num_timesteps:
            self.next_checkpoint += self.every_steps

    def _on_training_end(self) -> None:
        if self.last_checkpoint_steps != self.num_timesteps:
            self._save()
