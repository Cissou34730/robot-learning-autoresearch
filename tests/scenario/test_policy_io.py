import numpy as np

from robot_learning.scenario.environment import make_training_env
from robot_learning.scenario.policy_io import make_policy_io


def test_action_mapping_smooths_command_changes():
    policy_io = make_policy_io()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.75, -0.75])


def test_action_mapping_reset_clears_previous_command():
    policy_io = make_policy_io()
    policy_io.action(np.array([1.0, -1.0]))

    assert policy_io.reset is not None
    policy_io.reset()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])


def test_observation_exposes_applied_command_and_reset_clears_it():
    env = make_training_env()
    observation, _ = env.reset(seed=0)

    assert observation.shape == (13,)
    np.testing.assert_allclose(observation[-2:], [0.0, 0.0])

    observation, _, _, _, _ = env.step(np.array([1.0, -1.0]))
    np.testing.assert_allclose(observation[-2:], [0.5, -0.5])

    observation, _ = env.reset(seed=1)
    np.testing.assert_allclose(observation[-2:], [0.0, 0.0])
