"""Researcher-owned tests for the current scenario reward.

They describe the behavior of the reward as implemented today, expressed
through its active coefficients rather than historical numeric snapshots. A
reward experiment is expected to update them alongside the reward itself.
"""

import numpy as np
import pytest

from robot_learning.scenario import reward as reward_module
from robot_learning.scenario.reward import HOLD_COMPLETE_BONUS, reach_reward


def test_reward_encourages_progress():
    assert reach_reward(0.10, 0.08, 0.03).total > 0
    assert reach_reward(0.08, 0.10, 0.03).total < 0


def test_linear_hold_progress_reward_pays_completion():
    early = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=100,
    ).total
    late = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=99,
        previous_held_steps=98,
        hold_steps_required=100,
    ).total
    done = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=100,
        previous_held_steps=99,
        hold_steps_required=100,
    ).total
    assert early == pytest.approx(late)
    assert early > 0
    assert done - late == pytest.approx(HOLD_COMPLETE_BONUS)


def test_losing_hold_progress_applies_the_configured_forfeit(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "OUTSIDE_BAND_PENALTY", 0.0)
    reward = reach_reward(
        0.005,
        0.0101,
        0.01,
        held_steps=0,
        previous_held_steps=90,
        hold_steps_required=100,
        penalize_outside=True,
    ).total

    expected_forfeit = -(
        reward_module.HOLD_EXIT_FORFEIT_FRACTION
        * reward_module.HOLD_PROGRESS_BONUS
        * 0.9**reward_module.HOLD_PROGRESS_EXPONENT
    )
    assert reward == pytest.approx(expected_forfeit)


def test_outside_penalty_accumulates_and_is_bounded(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    just_outside = reach_reward(0.0105, 0.0105, 0.01, penalize_outside=True).total
    far_outside = reach_reward(0.10, 0.10, 0.01, penalize_outside=True).total

    assert just_outside == pytest.approx(
        -reward_module.OUTSIDE_BAND_PENALTY * 0.0005 / reward_module.OUTSIDE_BAND_WIDTH
    )
    assert far_outside == pytest.approx(-reward_module.OUTSIDE_BAND_PENALTY)


def test_outside_penalty_is_steady_while_the_lost_hold_stays_outside(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    expected = -(
        reward_module.OUTSIDE_BAND_PENALTY * 0.0001 / reward_module.OUTSIDE_BAND_WIDTH
    )
    exiting = reach_reward(
        0.005,
        0.0101,
        0.01,
        held_steps=0,
        previous_held_steps=0,
        hold_steps_required=100,
        penalize_outside=True,
    ).total
    still_outside = reach_reward(
        0.0101,
        0.0101,
        0.01,
        held_steps=0,
        previous_held_steps=0,
        hold_steps_required=100,
        penalize_outside=True,
    ).total

    assert exiting == pytest.approx(expected)
    assert still_outside == pytest.approx(expected)


def test_reward_components_are_free_form_and_sum_to_the_scalar():
    result = reach_reward(
        0.05,
        0.04,
        0.01,
        action=np.full(2, 0.3),
        held_steps=0,
        previous_held_steps=5,
        hold_steps_required=100,
        penalize_outside=True,
    )

    assert isinstance(result.components, dict)
    assert all(isinstance(value, float) for value in result.components.values())
    assert sum(result.components.values()) == pytest.approx(result.total)


def test_action_cost_penalizes_large_actions(monkeypatch):
    monkeypatch.setattr(reward_module, "ACTION_COST_COEFFICIENT", 1.0)
    gentle = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 0.1)).total
    violent = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 1.0)).total
    assert violent < gentle
