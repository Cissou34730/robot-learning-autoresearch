from types import SimpleNamespace

import numpy as np

from robot_learning.scenario.policy_io import make_policy_io


def observation_data(target_distance):
    target = np.array([0.1, 0.0, 0.0])
    site = SimpleNamespace(xpos=target + np.array([target_distance, 0.0, 0.0]))
    return SimpleNamespace(
        qpos=np.zeros(2),
        qvel=np.zeros(2),
        mocap_pos=np.array([target]),
        site=lambda name: site,
    )


def test_action_mapping_smooths_command_changes():
    policy_io = make_policy_io()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.75, -0.75])


def test_action_mapping_is_more_responsive_during_approach():
    policy_io = make_policy_io()
    policy_io.observe(observation_data(0.10))

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.75, -0.75])


def test_action_mapping_retains_incumbent_smoothing_near_target():
    policy_io = make_policy_io()
    policy_io.observe(observation_data(0.01))

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])


def test_action_mapping_reset_clears_previous_command():
    policy_io = make_policy_io()
    policy_io.action(np.array([1.0, -1.0]))

    assert policy_io.reset is not None
    policy_io.reset()

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
