"""Researcher-owned tests for candidate checkpointing during training.

Checkpoint timing belongs to the current learning implementation: it waits for a
completed optimizer update before saving. A different algorithm may need a
different rule, and this file is expected to change with it.
"""

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
