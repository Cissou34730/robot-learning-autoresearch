import numpy as np
import pytest

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.rewards.reach_reward import SUCCESS_BONUS, reach_reward
from robot_learning.robots.two_joint_arm import MAX_REACH


def test_reset_returns_observation_of_expected_shape():
    env = TwoJointArmReachEnv()
    obs, _ = env.reset(seed=0)
    assert obs.shape == env.observation_space.shape
    assert env.observation_space.contains(obs)


def test_step_outputs_match_spaces_and_are_finite():
    env = TwoJointArmReachEnv()
    obs, _ = env.reset(seed=1)
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
    assert obs.shape == env.observation_space.shape
    assert np.isfinite(reward)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert np.isfinite(info["distance"])


def test_seed_produces_reproducible_targets():
    env_a, env_b = TwoJointArmReachEnv(), TwoJointArmReachEnv()
    env_a.reset(seed=42)
    env_b.reset(seed=42)
    assert np.allclose(env_a.data.mocap_pos[0], env_b.data.mocap_pos[0])


def test_target_is_always_within_arm_reach():
    env = TwoJointArmReachEnv()
    for _ in range(50):
        env.reset(seed=None)
        radius = float(np.linalg.norm(env.data.mocap_pos[0]))
        assert 0 < radius <= MAX_REACH


def test_truncation_after_max_steps():
    env = TwoJointArmReachEnv(max_episode_steps=5)
    env.reset(seed=3)
    action = np.zeros(2)
    truncated = False
    for _ in range(5):
        _, _, _, truncated, _ = env.step(action)
    assert truncated


def test_reward_is_positive_when_closer_and_negative_when_farther():
    assert (
        reach_reward(
            previous_distance=0.10, current_distance=0.08, success_threshold=0.03
        )
        > 0
    )
    assert (
        reach_reward(
            previous_distance=0.08, current_distance=0.10, success_threshold=0.03
        )
        < 0
    )


def test_success_bonus_added_when_threshold_met():
    just_above = reach_reward(0.05, 0.03 + 1e-9, success_threshold=0.03)
    just_below = reach_reward(0.05, 0.03 - 1e-9, success_threshold=0.03)
    assert just_below - just_above == pytest.approx(SUCCESS_BONUS)


def test_invalid_target_radius_range_rejected():
    with pytest.raises(ValueError):
        TwoJointArmReachEnv(target_radius_range=(0.06, MAX_REACH + 0.1))
