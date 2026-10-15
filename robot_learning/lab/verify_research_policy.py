"""Focused laboratory checks for the I1 training exposure and diagnostics."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.evaluation import (
    failure_attribution,
    ik_branch_proximities,
    selected_ik_branch,
)
from robot_learning.train import effective_training_config
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
    training_exposure_metadata,
)
from robot_learning.training.research_config import load_experiment_config


def _write_result(path: Path, checks: list[str], *, compatibility: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compatibility": compatibility,
                "checks": checks,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def check_research_policy_contract(artifact: Path) -> None:
    """Check changed constants, metadata, and pure diagnostic invariants."""
    expected_range = tuple(float(value) for value in TARGET_RADIUS_RANGE)
    if tuple(TRAINING_TARGET_RADIUS_RANGE) != expected_range:
        raise AssertionError("training radius range is not the official interval")

    exposure = training_exposure_metadata()
    if exposure["radius_range_m"] != list(expected_range):
        raise AssertionError("training metadata does not record the radius range")
    if exposure["radius_law"] != "uniform":
        raise AssertionError("training metadata does not record uniform radii")
    if exposure["angle_law"] != "uniform_full_circle":
        raise AssertionError(
            "training metadata does not record full-angle sampling"
        )
    if exposure["angle_range_radians"] != [-math.pi, math.pi]:
        raise AssertionError("training metadata has the wrong angle interval")

    effective_config = effective_training_config(load_experiment_config())
    if effective_config["training_exposure"] != exposure:
        raise AssertionError(
            "effective training configuration lost the exposure metadata"
        )

    open_observation = np.zeros(11, dtype=np.float64)
    open_observation[7:9] = [0.1, 0.2]
    open_observation[9:11] = [0.8, 0.9]
    open_distance, folded_distance = ik_branch_proximities(open_observation)
    if not math.isclose(open_distance, math.sqrt(0.05)):
        raise AssertionError("open IK proximity uses the wrong observation slice")
    if not math.isclose(folded_distance, math.sqrt(1.45)):
        raise AssertionError("folded IK proximity uses the wrong observation slice")
    if selected_ik_branch(open_distance, folded_distance) != "open":
        raise AssertionError("closer open IK branch was not selected")

    folded_observation = np.zeros(11, dtype=np.float64)
    folded_observation[7:9] = [0.8, 0.9]
    folded_observation[9:11] = [0.1, 0.2]
    open_distance, folded_distance = ik_branch_proximities(folded_observation)
    if selected_ik_branch(open_distance, folded_distance) != "folded":
        raise AssertionError("closer folded IK branch was not selected")

    if failure_attribution(False, None) != "approach_failure":
        raise AssertionError("missing first entry was not attributed to approach")
    if failure_attribution(False, 3) != "hold_failure":
        raise AssertionError("unfinished hold was not attributed to hold")
    if failure_attribution(True, 3) != "success":
        raise AssertionError("completed episode was not attributed to success")

    _write_result(
        artifact,
        [
            "official training radius interval is exposed",
            "full-angle uniform sampling is recorded",
            "effective training configuration preserves exposure metadata",
            "open and folded IK branch diagnostics select the closer branch",
            "failure attribution helpers obey approach, hold, and success invariants",
        ],
        compatibility=False,
    )


def check_production_compatibility(artifact: Path) -> None:
    """Exercise the real training environment without a saved policy artifact."""
    env = make_training_env()
    try:
        observation, _ = env.reset(seed=I1_COMPATIBILITY_SEED)
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        radius = float(np.hypot(target[0], target[1]))
        lower, upper = TRAINING_TARGET_RADIUS_RANGE
        if not lower <= radius <= upper:
            raise AssertionError(
                "production training reset sampled outside its range"
            )
        if observation.shape != (11,):
            raise AssertionError("production training observation changed shape")

        next_observation, _, _, _, _ = env.step(
            np.asarray([2.0, -2.0], dtype=np.float32)
        )
        actual = np.asarray(env.data.ctrl, dtype=np.float64)
        if next_observation.shape != (11,):
            raise AssertionError(
                "production training step changed observation shape"
            )
        if not np.all(np.isfinite(actual)):
            raise AssertionError("production action command is not finite")
        if not np.all(actual >= env.action_space.low) or not np.all(
            actual <= env.action_space.high
        ):
            raise AssertionError("production action command escaped clipping bounds")
    finally:
        env.close()

    _write_result(
        artifact,
        [
            "production training environment reset sampled the declared radius law",
            "production training step retained the 11-value observation",
            "production applied control remained finite and clipped",
        ],
        compatibility=True,
    )


I1_COMPATIBILITY_SEED = 17


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    if args.compatibility:
        check_production_compatibility(args.artifact)
    else:
        check_research_policy_contract(args.artifact)


if __name__ == "__main__":
    main()
