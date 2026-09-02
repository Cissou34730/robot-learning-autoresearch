"""Researcher-owned tests for candidate checkpointing during training.

Checkpoint timing belongs to the current learning implementation: it waits for a
completed optimizer update before saving. A different algorithm may need a
different rule, and this file is expected to change with it.
"""

from pathlib import Path

from robot_learning.training.candidate_checkpoint_callback import (
    CandidateCheckpointCallback,
)


def test_candidate_checkpoint_waits_for_a_completed_update(monkeypatch, tmp_path):
    callback = CandidateCheckpointCallback(output_dir=tmp_path, every_steps=20_000)
    checkpoints: list[int] = []

    def record_checkpoint():
        checkpoints.append(callback.num_timesteps)
        callback.last_checkpoint_steps = callback.num_timesteps

    monkeypatch.setattr(callback, "_save", record_checkpoint)

    callback.num_timesteps = 20_000
    assert callback._on_step()
    assert checkpoints == []

    callback.num_timesteps = 21_504
    callback._on_rollout_start()
    assert checkpoints == [21_504]
    assert callback.next_checkpoint == 40_000

    callback._on_training_end()
    assert checkpoints == [21_504]

    callback.num_timesteps = 24_576
    callback._on_training_end()
    assert checkpoints == [21_504, 24_576]


def test_candidate_checkpoint_records_rolling_metrics_at_save_time(tmp_path):
    class TrainingEnvironment:
        def save(self, path):
            Path(path).touch()

    class Model:
        ep_info_buffer = [{"r": 0.0}, {"r": 4.0}]
        ep_success_buffer = [0.0, 1.0]

        def get_env(self):
            return TrainingEnvironment()

        def save(self, path):
            Path(f"{path}.zip").touch()

    callback = CandidateCheckpointCallback(output_dir=tmp_path, every_steps=1)
    callback.init_callback(Model())
    callback.num_timesteps = 1

    callback._on_rollout_start()

    assert (tmp_path / "candidate_pool" / "checkpoint-1" / "training_metrics.json").read_text(
        encoding="utf-8"
    ) == '{\n  "success_rate": 0.5,\n  "ep_rew_mean": 2.0\n}\n'
