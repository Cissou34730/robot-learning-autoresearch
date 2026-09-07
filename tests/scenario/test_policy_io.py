"""Tests for the scenario policy input and physical-action mapping."""

import numpy as np

from robot_learning.scenario.environment import make_training_env


def test_target_conditioned_action_mapping_guides_zero_command():
    env = make_training_env()
    env.reset(seed=0)

    action = env.policy_io.action(np.zeros(2))

    assert action.shape == (2,)
    assert np.all(np.abs(action) <= 1.0)
    assert not np.allclose(action, 0.0)

    env.close()
