import numpy as np

from robot_learning.scenario.policy_io import make_policy_io


class _FakeData:
    def __init__(self, angle):
        self.mocap_pos = np.array([[np.cos(angle), np.sin(angle), 0.0]])
        self.qpos = np.zeros(2)
        self.qvel = np.zeros(2)

    def site(self, name):
        assert name == "end_effector"
        return type("Site", (), {"xpos": np.zeros(3)})()


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


def test_action_mapping_reduces_lag_in_residual_target_sector():
    policy_io = make_policy_io()
    policy_io.observe(_FakeData(np.deg2rad(-130.0)))

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.75, -0.75])


def test_action_mapping_keeps_baseline_smoothing_outside_residual_sector():
    policy_io = make_policy_io()
    policy_io.observe(_FakeData(np.deg2rad(30.0)))

    np.testing.assert_allclose(policy_io.action(np.array([1.0, -1.0])), [0.5, -0.5])
