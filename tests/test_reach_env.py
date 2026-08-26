import numpy as np
import pytest

from robot_learning.environments.reach_env import (
    CURRICULUM_STAGES,
    TwoJointArmReachEnv,
)
from robot_learning.rewards import reach_reward as reach_reward_module
from robot_learning.rewards.reach_reward import HOLD_COMPLETE_BONUS, reach_reward
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


def test_in_band_payment_is_flat_per_step():
    early = reach_reward(
        0.005, 0.005, success_threshold=0.01, held_steps=1, hold_steps_required=100
    )
    late = reach_reward(
        0.005, 0.005, success_threshold=0.01, held_steps=99, hold_steps_required=100
    )
    assert early == pytest.approx(late)
    assert late == pytest.approx(reach_reward_module.DWELL_BONUS_PER_STEP)


def test_out_of_band_step_pays_no_dwell():
    after_long_streak = reach_reward(
        0.02, 0.02, success_threshold=0.01, held_steps=50, hold_steps_required=100
    )
    fresh = reach_reward(
        0.02, 0.02, success_threshold=0.01, held_steps=0, hold_steps_required=100
    )
    assert after_long_streak == pytest.approx(fresh)


def test_hold_completion_adds_final_bonus():
    before = reach_reward(
        0.005, 0.005, success_threshold=0.01, held_steps=99, hold_steps_required=100
    )
    after = reach_reward(
        0.005, 0.005, success_threshold=0.01, held_steps=100, hold_steps_required=100
    )
    delta = after - before
    expected = HOLD_COMPLETE_BONUS
    assert delta == pytest.approx(expected)


def test_action_cost_penalizes_large_actions(monkeypatch):
    monkeypatch.setattr(reach_reward_module, "ACTION_COST_COEFFICIENT", 1.0)
    gentle = reach_reward(0.05, 0.04, success_threshold=0.03, action=np.full(2, 0.1))
    violent = reach_reward(0.05, 0.04, success_threshold=0.03, action=np.full(2, 1.0))
    assert violent < gentle


def test_invalid_target_radius_range_rejected():
    with pytest.raises(ValueError):
        TwoJointArmReachEnv(target_radius_range=(0.06, MAX_REACH + 0.1))


def test_holding_target_terminates_episode_after_required_steps():
    env = TwoJointArmReachEnv()
    env.reset(seed=0)
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    action = np.zeros(2)
    done = False
    steps = 0
    while not done:
        _, _, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        steps += 1
    assert terminated
    assert not truncated
    assert steps == env.hold_steps_required
    assert info["held_steps"] == env.hold_steps_required


def test_leaving_the_band_resets_the_hold_counter():
    env = TwoJointArmReachEnv()
    env.reset(seed=0)
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    for _ in range(20):
        _, _, _, _, info = env.step(np.zeros(2))
    assert info["held_steps"] == 20
    env.data.mocap_pos[0] = [0.30, 0.0, 0.0]
    _, _, _, _, info = env.step(np.zeros(2))
    assert info["held_steps"] == 0


def test_default_env_is_fixed_at_final_difficulty():
    env = TwoJointArmReachEnv()
    assert not env.curriculum_enabled
    assert env.success_threshold == pytest.approx(0.01)
    assert env.hold_steps_required == 100


def test_curriculum_tightens_precision_before_extending_the_hold():
    assert CURRICULUM_STAGES[:3] == ((0.03, 0.02), (0.02, 0.02), (0.01, 0.02))
    assert CURRICULUM_STAGES[-1] == (0.01, 2.00)
    assert all(seconds > 0 for _, seconds in CURRICULUM_STAGES)


def test_curriculum_env_starts_at_easiest_stage():
    env = TwoJointArmReachEnv(curriculum=True)
    env.reset(seed=0)
    assert env.success_threshold == pytest.approx(0.03)
    assert env.hold_steps_required == 1


def test_curriculum_advances_after_enough_successes():
    env = TwoJointArmReachEnv(curriculum=True)
    env.reset(seed=0)
    for _ in range(15):
        env._record_episode_outcome(True)
    assert env.success_threshold == pytest.approx(0.02)
    assert len(env._episode_outcomes) == 0
