import hashlib

import numpy as np
import pytest

from robot_learning.benchmark import final_contract
from robot_learning.benchmark.final_benchmark import official_environment
from robot_learning.benchmark.metrics import (
    achieved_goal,
    episode_hold_progress,
    maximum_consecutive_hold_steps,
    summarize_hold_progress,
)
from robot_learning.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


def test_robot_physics_asset_is_frozen():
    digest = hashlib.sha256(TWO_JOINT_ARM_XML_PATH.read_bytes()).hexdigest()
    assert digest == "6ccb918656b92a931927e2bfd90378d915da009b741155c7cafc5913b9f87f62"


def test_final_task_contract_is_fixed():
    env = official_environment()
    control_dt = env.model.opt.timestep * env.frame_skip
    assert env.success_threshold == pytest.approx(final_contract.SUCCESS_THRESHOLD)
    assert env.hold_steps_required == round(final_contract.HOLD_SECONDS / control_dt)
    assert env.target_radius_range == final_contract.TARGET_RADIUS_RANGE
    assert env.frame_skip == final_contract.FRAME_SKIP
    assert env.max_episode_steps == final_contract.MAX_EPISODE_STEPS
    assert final_contract.FINAL_SUCCESS_PERCENT == 98.0
    assert final_contract.EVALUATION_EPISODES == 200
    assert final_contract.EVALUATION_SEED == 1000


def test_official_environment_uses_final_contract_not_research_defaults(monkeypatch):
    monkeypatch.setattr("robot_learning.benchmark.spec.HOLD_SECONDS", 0.5)
    monkeypatch.setattr("robot_learning.benchmark.spec.SUCCESS_THRESHOLD", 0.2)

    env = official_environment()
    control_dt = env.model.opt.timestep * env.frame_skip

    assert env.success_threshold == pytest.approx(0.01)
    assert env.hold_steps_required == round(2.0 / control_dt)


def test_seed_produces_reproducible_fixed_distribution():
    env_a, env_b = official_environment(), official_environment()
    env_a.reset(seed=42)
    env_b.reset(seed=42)
    assert np.allclose(env_a.data.mocap_pos[0], env_b.data.mocap_pos[0])
    radius = float(np.linalg.norm(env_a.data.mocap_pos[0][:2]))
    low, high = final_contract.TARGET_RADIUS_RANGE
    assert low <= radius <= high


def test_final_hold_requires_100_consecutive_steps():
    env = official_environment()
    env.reset(seed=0)
    assert env.hold_steps_required == 100
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    for step in range(100):
        _, _, terminated, truncated, _ = env.step(np.zeros(2))
        assert not truncated
        assert terminated is (step == 99)


def test_fixed_metric_requires_the_complete_hold():
    assert not achieved_goal([0.005] * 99, control_dt=0.02)
    assert achieved_goal([0.005] * 100, control_dt=0.02)


def test_fixed_metric_measures_the_longest_unbroken_hold():
    distances = [0.005] * 40 + [0.02] + [0.005] * 75 + [0.02] + [0.005] * 60
    assert maximum_consecutive_hold_steps(distances) == 75


def test_failed_episode_progress_rewards_task_aligned_near_success():
    almost = episode_hold_progress([0.005] * 99 + [0.0101], required=100)
    intermittent = episode_hold_progress(
        [0.005] * 70 + [0.02] + [0.005] * 29,
        required=100,
    )

    assert almost["longest_consecutive_steps"] == 99
    assert almost["best_window_inside_steps"] == 99
    assert almost["best_window_excess_cm"] == pytest.approx(0.01)
    assert intermittent["longest_consecutive_steps"] == 70
    assert intermittent["best_window_inside_steps"] == 99


def test_progress_summary_uses_failed_episodes_only():
    episodes = [
        episode_hold_progress([0.005] * 100, required=100),
        episode_hold_progress([0.005] * 80 + [0.02] * 20, required=100),
    ]

    summary = summarize_hold_progress(episodes, required=100)
    assert summary["failed_episodes"] == 1
    assert summary["longest_consecutive_steps_mean"] == 80
    assert summary["best_window_inside_steps_mean"] == 80
    assert summary["best_window_excess_cm_mean"] == pytest.approx(20.0)
