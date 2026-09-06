import numpy as np

from robot_learning.scenario.policy_io import make_policy_io


def test_action_smoothing_is_reset_between_episodes():
    policy_io = make_policy_io()

    np.testing.assert_allclose(policy_io.action([1.0, -1.0]), [0.5, -0.5])
    np.testing.assert_allclose(policy_io.action([1.0, -1.0]), [0.75, -0.75])

    assert policy_io.reset is not None
    policy_io.reset()
    np.testing.assert_allclose(policy_io.action([1.0, -1.0]), [0.5, -0.5])
