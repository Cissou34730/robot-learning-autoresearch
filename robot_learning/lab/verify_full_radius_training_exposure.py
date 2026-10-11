"""Verify the training radius exposure and preserve official hold semantics.

This is a laboratory check for the I2 construction change. It samples targets
after constructing the training environment, and uses controlled target
placements to exercise the official environment's contiguous hold behavior.
It does not measure policy performance or scientific validity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)


EXPECTED_TRAINING_RADIUS_RANGE = (0.06, 0.20)
EXPECTED_OFFICIAL_RADIUS_RANGE = (0.06, 0.20)
EXPECTED_HOLD_STEPS = 100
EXPECTED_SUCCESS_THRESHOLD = 0.01
EXPECTED_FRAME_SKIP = 10

UNCHECKED_SCOPE = [
    "whether full-radius exposure improves acquisition or official success",
    "PPO settings, policy architecture, and learned behavior",
    "compiled dynamics beyond the transitions exercised by this check",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _radius(env: TwoJointArmReachEnv) -> float:
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    return float(np.linalg.norm(target[:2]))


def _place_target_at_end_effector(env: TwoJointArmReachEnv) -> None:
    env.data.mocap_pos[0] = env.data.site("end_effector").xpos.copy()
    mujoco.mj_forward(env.model, env.data)


def _run_check(observed: dict[str, Any]) -> None:
    training_env = make_training_env()
    try:
        observed["training_constant"] = list(TRAINING_TARGET_RADIUS_RANGE)
        observed["training_constructed_range"] = list(
            training_env.target_radius_range
        )
        _require(
            tuple(TRAINING_TARGET_RADIUS_RANGE) == EXPECTED_TRAINING_RADIUS_RANGE,
            "training radius constant is not exactly (0.06, 0.20)",
        )
        _require(
            tuple(training_env.target_radius_range)
            == EXPECTED_TRAINING_RADIUS_RANGE,
            "constructed training environment does not carry (0.06, 0.20)",
        )

        training_samples: list[dict[str, Any]] = []
        for seed in (11, 23, 37):
            training_env.reset(seed=seed)
            sampled_radius = _radius(training_env)
            _require(
                EXPECTED_TRAINING_RADIUS_RANGE[0]
                <= sampled_radius
                <= EXPECTED_TRAINING_RADIUS_RANGE[1],
                f"training reset sampled radius outside full range: {sampled_radius}",
            )
            transition = training_env.step(np.zeros(2, dtype=np.float32))
            _require(
                len(transition) == 5,
                "training environment transition did not retain the Gymnasium API",
            )
            training_samples.append(
                {"seed": seed, "sampled_radius": sampled_radius}
            )
        observed["training_reset_samples"] = training_samples
    finally:
        training_env.close()

    official_env = TwoJointArmReachEnv()
    try:
        observed["official_default_range"] = list(official_env.target_radius_range)
        observed["official_hold_steps_required"] = official_env.hold_steps_required
        observed["official_success_threshold"] = official_env.success_threshold
        observed["official_frame_skip"] = official_env.frame_skip
        _require(
            tuple(official_env.target_radius_range)
            == EXPECTED_OFFICIAL_RADIUS_RANGE,
            "official scenario default radius range changed",
        )
        _require(
            official_env.hold_steps_required == EXPECTED_HOLD_STEPS,
            "official scenario hold length changed from 100 control steps",
        )
        _require(
            official_env.success_threshold == EXPECTED_SUCCESS_THRESHOLD,
            "official scenario success threshold changed",
        )
        _require(
            official_env.frame_skip == EXPECTED_FRAME_SKIP,
            "official scenario frame skip changed",
        )

        zero_action = np.zeros(2, dtype=np.float32)
        official_env.reset(seed=101)
        _place_target_at_end_effector(official_env)
        first_transition = official_env.step(zero_action)
        first_info = first_transition[4]
        _require(
            first_info["held_steps"] == 1 and not first_transition[2],
            "an in-tolerance transition did not start a contiguous hold",
        )

        for _ in range(EXPECTED_HOLD_STEPS - 3):
            official_env.step(zero_action)
        penultimate_transition = official_env.step(zero_action)
        _require(
            penultimate_transition[4]["held_steps"] == EXPECTED_HOLD_STEPS - 1
            and not penultimate_transition[2],
            "hold terminated before 100 uninterrupted control steps",
        )
        final_transition = official_env.step(zero_action)
        _require(
            final_transition[4]["held_steps"] == EXPECTED_HOLD_STEPS
            and final_transition[2],
            "100th uninterrupted in-tolerance step did not terminate successfully",
        )

        official_env.reset(seed=102)
        _place_target_at_end_effector(official_env)
        official_env.step(zero_action)
        official_env.data.mocap_pos[0] = (
            official_env.data.site("end_effector").xpos
            + np.array([0.05, 0.0, 0.0])
        )
        mujoco.mj_forward(official_env.model, official_env.data)
        interrupted_transition = official_env.step(zero_action)
        _require(
            interrupted_transition[4]["held_steps"] == 0
            and not interrupted_transition[2],
            "leaving tolerance did not reset the contiguous hold",
        )
        observed["official_hold_trace"] = {
            "first_held_steps": first_info["held_steps"],
            "penultimate_held_steps": penultimate_transition[4]["held_steps"],
            "final_held_steps": final_transition[4]["held_steps"],
            "interrupted_held_steps": interrupted_transition[4]["held_steps"],
        }
    finally:
        official_env.close()


def _write_artifact(path: Path, report: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as artifact:
        json.dump(report, artifact, indent=2, sort_keys=True)
        artifact.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="path for the JSON verification artifact")
    args = parser.parse_args(argv)

    observed: dict[str, Any] = {}
    report: dict[str, Any] = {
        "status": "passed",
        "observed": observed,
        "expected": {
            "training_radius_range": list(EXPECTED_TRAINING_RADIUS_RANGE),
            "official_radius_range": list(EXPECTED_OFFICIAL_RADIUS_RANGE),
            "hold_steps": EXPECTED_HOLD_STEPS,
            "success_threshold": EXPECTED_SUCCESS_THRESHOLD,
            "frame_skip": EXPECTED_FRAME_SKIP,
        },
        "checked_scope": [
            "training constant and constructed environment radius range",
            "repeated training resets, sampled radii, and Gymnasium transitions",
            "official default radius range and hold configuration",
            "official contiguous hold completion and interruption reset",
        ],
        "unchecked_scope": UNCHECKED_SCOPE,
    }
    try:
        _run_check(observed)
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        _write_artifact(Path(args.output), report)
        raise

    _write_artifact(Path(args.output), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
