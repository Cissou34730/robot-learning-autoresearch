"""Laboratory check for velocity-aware braking and robust hold shaping.

This module uses controlled reward inputs rather than a learned policy.  It
checks directional consequences that should remain true independently of the
chosen coefficients: braking is gated away from the target, fast motion near
the target is penalized more, deeper holds receive more margin reward, and an
interrupted hold forfeits prior progress.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.training.reward import reach_reward


SUCCESS_THRESHOLD = 0.01
HOLD_STEPS_REQUIRED = 100


def _as_json_value(value: Any) -> Any:
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _write_artifact(
    output: Path,
    *,
    status: str,
    observations: list[dict[str, Any]],
    failure: str | None = None,
) -> None:
    artifact: dict[str, Any] = {
        "check": "velocity_hold_reward",
        "status": status,
        "observations": observations,
        "checked_scope": [
            "reward updates during far transit and near-target motion",
            "repeated in-margin hold updates",
            "in-tolerance to out-of-tolerance hold interruption",
            "fresh reset-equivalent hold sequence",
            "finite scalar totals and braking/hold-margin attribution",
        ],
        "unchecked_scope": [
            "learned-policy behavior and training convergence",
            "task-level reach or complete-hold rates",
            "MuJoCo dynamics and evaluator outcomes",
            "coefficient optimality or causal isolation of the intervention",
        ],
    }
    if failure is not None:
        artifact["failure"] = failure
    output.write_text(
        json.dumps(artifact, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _record(
    observations: list[dict[str, Any]],
    *,
    name: str,
    observed: Any,
    expected: str,
    scope: str,
    condition: bool,
) -> None:
    observation = {
        "name": name,
        "observed": _as_json_value(observed),
        "expected": expected,
        "scope": scope,
    }
    observations.append(observation)
    if not condition:
        raise AssertionError(f"{name}: observed {observed!r}; expected {expected}")


def run_check(output: Path) -> None:
    observations: list[dict[str, Any]] = []
    try:
        far_transit = reach_reward(
            previous_distance=0.15,
            current_distance=0.12,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=0,
            previous_held_steps=0,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.array([20.0, -20.0]),
        )
        _record(
            observations,
            name="far_high_velocity_has_no_braking_penalty",
            observed=far_transit.components["braking"],
            expected="exactly zero outside the smooth near-target gate",
            scope="far transit with high joint velocity",
            condition=far_transit.components["braking"] == 0.0,
        )

        near_high_velocity = reach_reward(
            previous_distance=0.02,
            current_distance=0.008,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=1,
            previous_held_steps=0,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.array([1.0, 0.5]),
        )
        near_low_velocity = reach_reward(
            previous_distance=0.02,
            current_distance=0.008,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=1,
            previous_held_steps=0,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.array([0.1, 0.05]),
        )
        _record(
            observations,
            name="near_target_high_velocity_is_penalized_more",
            observed={
                "high_velocity_braking": near_high_velocity.components["braking"],
                "low_velocity_braking": near_low_velocity.components["braking"],
            },
            expected="high-velocity braking contribution is more negative",
            scope="same near-target transition with two controlled velocities",
            condition=(
                near_high_velocity.components["braking"]
                < near_low_velocity.components["braking"]
            ),
        )

        shallow_hold = reach_reward(
            previous_distance=0.009,
            current_distance=0.009,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=2,
            previous_held_steps=1,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.zeros(2),
        )
        deep_hold = reach_reward(
            previous_distance=0.002,
            current_distance=0.002,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=2,
            previous_held_steps=1,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.zeros(2),
        )
        _record(
            observations,
            name="deeper_inner_hold_margin_is_rewarded",
            observed={
                "shallow_margin": shallow_hold.components["hold_margin"],
                "deep_margin": deep_hold.components["hold_margin"],
            },
            expected=(
                "deeper in-ball position has a larger margin, while the "
                "boundary-skimming point has none"
            ),
            scope="boundary-skimming versus inner-margin held step",
            condition=(
                deep_hold.components["hold_margin"]
                > shallow_hold.components["hold_margin"]
                and shallow_hold.components["hold_margin"] == 0.0
                and deep_hold.components["hold_margin"] > 0.0
            ),
        )

        repeated_hold = [
            reach_reward(
                previous_distance=0.002,
                current_distance=0.002,
                success_threshold=SUCCESS_THRESHOLD,
                held_steps=held,
                previous_held_steps=held - 1,
                hold_steps_required=HOLD_STEPS_REQUIRED,
                qvel=np.zeros(2),
            )
            for held in (2, 3, 4)
        ]
        repeated_totals = [result.total for result in repeated_hold]
        repeated_margins = [
            result.components["hold_margin"] for result in repeated_hold
        ]
        _record(
            observations,
            name="repeated_inner_hold_updates_remain_finite_and_rewarded",
            observed={
                "totals": repeated_totals,
                "margins": repeated_margins,
            },
            expected="all totals are finite and every held step has positive margin",
            scope="three consecutive controlled in-margin hold updates",
            condition=(
                all(np.isfinite(total) for total in repeated_totals)
                and all(margin > 0.0 for margin in repeated_margins)
            ),
        )

        interrupted_hold = reach_reward(
            previous_distance=0.004,
            current_distance=0.015,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=0,
            previous_held_steps=3,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            penalize_outside=True,
            qvel=np.zeros(2),
        )
        _record(
            observations,
            name="hold_interruption_forfeits_prior_progress",
            observed=interrupted_hold.components["hold_progress"],
            expected="negative hold-progress contribution after exiting the ball",
            scope="in-tolerance hold followed by an outside transition",
            condition=interrupted_hold.components["hold_progress"] < 0.0,
        )

        fresh_sequence = reach_reward(
            previous_distance=0.15,
            current_distance=0.004,
            success_threshold=SUCCESS_THRESHOLD,
            held_steps=1,
            previous_held_steps=0,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            qvel=np.zeros(2),
        )
        fresh_components = fresh_sequence.components
        _record(
            observations,
            name="fresh_sequence_has_no_stale_exit_forfeit",
            observed={
                "hold_progress": fresh_components["hold_progress"],
                "hold_margin": fresh_components["hold_margin"],
                "braking": fresh_components["braking"],
            },
            expected="a fresh held step has positive progress and margin, with no braking",
            scope="reset-equivalent first held update after interruption scenario",
            condition=(
                fresh_components["hold_progress"] > 0.0
                and fresh_components["hold_margin"] > 0.0
                and fresh_components["braking"] == 0.0
            ),
        )

        names = set(fresh_components)
        _record(
            observations,
            name="new_reward_components_are_attributed",
            observed=sorted(names),
            expected="component attribution includes braking and hold_margin",
            scope="reward result attribution",
            condition={"braking", "hold_margin"}.issubset(names),
        )
        all_finite = all(
            np.isfinite(value)
            for result in (
                far_transit,
                near_high_velocity,
                near_low_velocity,
                shallow_hold,
                deep_hold,
                *repeated_hold,
                interrupted_hold,
                fresh_sequence,
            )
            for value in [result.total, *result.components.values()]
        )
        _record(
            observations,
            name="controlled_reward_outputs_are_finite",
            observed=all_finite,
            expected="all checked scalar totals and components are finite",
            scope="representative far, near, hold, interruption, and fresh updates",
            condition=all_finite,
        )
    except Exception as error:
        _write_artifact(
            output,
            status="failed",
            observations=observations,
            failure=str(error),
        )
        raise

    _write_artifact(output, status="passed", observations=observations)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run_check(args.output)


if __name__ == "__main__":
    main()
