"""Controlled laboratory check for the I1 candidate preparation.

This is a defect-sensitive executable check, not a scientific validation.  It
uses the real training environment and the real research evaluator with a
short, deterministic bounded-action runtime.  The evaluator's loader and
factory are replaced only inside the check so no model artifact is required.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from robot_learning.scenario import evaluation
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.policy_io import make_policy_io
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

_UNCHECKED_SCOPE = [
    "policy quality or scientific validity",
    "long-horizon candidate evaluation",
    "official benchmark acceptance",
    "continuous within-frame-skip motion",
]


class _BoundedRuntime:
    def __init__(self, observation_space) -> None:
        self.io = make_policy_io()
        self.observation_space = observation_space
        self.reset_count = 0
        self.predict_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def predict(self, _observation) -> np.ndarray:
        self.predict_count += 1
        return np.asarray([1.0, -1.0], dtype=np.float32)


class _TrackedEnvironment(TwoJointArmReachEnv):
    def __init__(self) -> None:
        super().__init__(
            target_radius_range=(0.06, 0.20),
            max_episode_steps=3,
            hold_seconds=1000.0,
        )
        self.reset_count = 0
        self.step_count = 0

    def reset(self, **kwargs):
        self.reset_count += 1
        return super().reset(**kwargs)

    def step(self, action):
        self.step_count += 1
        return super().step(action)


def _run_controlled_evaluation(episodes: int) -> tuple[dict, _TrackedEnvironment, _BoundedRuntime]:
    controlled_env = _TrackedEnvironment()
    runtime = _BoundedRuntime(controlled_env.observation_space)

    original_loader = evaluation.load_runtime
    original_factory = evaluation.make_evaluation_env
    evaluation.load_runtime = lambda _path, _algorithm: runtime
    evaluation.make_evaluation_env = lambda policy_runtime=None: controlled_env
    try:
        result = evaluation.evaluate_research_model(
            Path("controlled-policy.zip"),
            episodes=episodes,
            seed=17,
        )
    finally:
        evaluation.load_runtime = original_loader
        evaluation.make_evaluation_env = original_factory
        controlled_env.close()
    return result, controlled_env, runtime


def _check_training_range() -> dict:
    expected = [0.06, 0.20]
    exposed = [float(value) for value in TRAINING_TARGET_RADIUS_RANGE]
    if exposed != expected:
        raise AssertionError(f"training range {exposed!r} != {expected!r}")
    environment = make_training_env()
    try:
        observed = [float(value) for value in environment.target_radius_range]
        if observed != expected:
            raise AssertionError(
                f"constructed training range {observed!r} != {expected!r}"
            )
        environment.reset(seed=3)
        environment.reset(seed=4)
    finally:
        environment.close()
    return {"expected_m": expected, "constant_m": exposed, "constructed_m": observed}


def _check_geometry_classification() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    reachable = evaluation._geometry_diagnostics(
        model, np.asarray([0.15, 0.0, 0.02], dtype=np.float64)
    )
    if reachable["range_stratum"] != "both_branches_feasible":
        raise AssertionError(f"reachable stratum: {reachable['range_stratum']}")
    if reachable["branch_feasibility"] != {"open": True, "folded": True}:
        raise AssertionError(f"reachable branches: {reachable['branch_feasibility']}")
    open_q = np.asarray(reachable["branches"]["open"]["joint_angles_rad"])
    label = evaluation._trajectory_branch_label(reachable, open_q, model)
    if label != "open":
        raise AssertionError(f"measured open branch classified as {label!r}")

    range_infeasible = evaluation._geometry_diagnostics(
        model, np.asarray([-0.22, 0.0, 0.02], dtype=np.float64)
    )
    if range_infeasible["range_stratum"] != "range_infeasible":
        raise AssertionError(
            f"limit-infeasible stratum: {range_infeasible['range_stratum']}"
        )
    if any(range_infeasible["branch_feasibility"].values()):
        raise AssertionError("limit-infeasible target has a feasible branch")
    if evaluation._trajectory_branch_label(
        range_infeasible, np.zeros(2, dtype=np.float64), model
    ) != "unavailable":
        raise AssertionError("unavailable branches received a trajectory label")
    return {
        "reachable": reachable,
        "reachable_measured_label": label,
        "limit_infeasible": range_infeasible,
    }


def _check_behavior() -> dict:
    result, controlled_env, runtime = _run_controlled_evaluation(episodes=2)
    diagnostics = result["research_evidence"]["episode_diagnostics"]
    required = {
        "target_radius_cm",
        "target_angle_degrees",
        "min_distance_cm",
        "peak_distance_cm",
        "final_distance_cm",
        "first_reach_step",
        "max_held_steps",
        "in_tolerance_steps",
        "hold_interruptions",
        "endpoint_velocity",
        "joint_velocity",
        "action_saturation",
        "branch_feasibility",
        "range_stratum",
        "trajectory_branch_label",
        "ik_branches",
    }
    for item in diagnostics:
        missing = required.difference(item)
        if missing:
            raise AssertionError(f"diagnostic keys missing: {sorted(missing)}")
        if item["action_saturation"]["any"] is not True:
            raise AssertionError("the bounded action was not marked saturated")
        if item["action_saturation"]["steps"] != item["steps"]:
            raise AssertionError("saturation step count did not follow transitions")
        if item["endpoint_velocity"]["final_m_per_s"] < 0.0:
            raise AssertionError("endpoint velocity has an invalid sign")
        if item["joint_velocity"]["final_rad_per_s"] < 0.0:
            raise AssertionError("joint velocity has an invalid sign")
    units = result["research_evidence"]["units"]
    expected_units = {
        "distance": "cm",
        "target_radius": "cm",
        "target_angle": "degrees",
        "time": "control_steps",
        "endpoint_velocity": "m_per_s",
        "joint_velocity": "rad_per_s",
        "joint_angles": "rad",
        "range_margin": "rad",
        "action": "normalized_control",
    }
    if units != expected_units:
        raise AssertionError(f"units {units!r} != {expected_units!r}")
    if controlled_env.reset_count != 2 or controlled_env.step_count != 6:
        raise AssertionError("repeated reset/update transitions were not exercised")
    if runtime.reset_count != 2 or runtime.predict_count != 6:
        raise AssertionError("runtime reset or repeated prediction was not exercised")
    if any(not episode["truncated"] for episode in result["episode_results"]):
        raise AssertionError("controlled episodes did not exercise truncation")
    return {
        "episodes": len(diagnostics),
        "resets": controlled_env.reset_count,
        "steps": controlled_env.step_count,
        "runtime_resets": runtime.reset_count,
        "runtime_predictions": runtime.predict_count,
        "diagnostics": diagnostics,
        "units": units,
    }


def _run_check(compatibility: bool) -> dict:
    training = _check_training_range()
    if compatibility:
        result, _, runtime = _run_controlled_evaluation(episodes=1)
        diagnostics = result["research_evidence"]["episode_diagnostics"]
        if len(diagnostics) != 1 or not diagnostics[0]["action_saturation"]["any"]:
            raise AssertionError("production evaluator compatibility path failed")
        return {
            "checked_scope": [
                "training range construction",
                "one controlled production evaluator episode",
            ],
            "observed": {"training": training, "runtime_resets": runtime.reset_count},
            "expected": {
                "training_range_m": [0.06, 0.20],
                "one_episode_diagnostic": True,
            },
        }
    geometry = _check_geometry_classification()
    behavior = _check_behavior()
    return {
        "checked_scope": [
            "official training range exposed and constructed",
            "repeated evaluator updates, transitions, and resets",
            "required diagnostic keys and explicit units",
            "bounded-action saturation detection",
            "reachable and compiled-range-infeasible IK strata",
        ],
        "observed": {
            "training": training,
            "geometry": geometry,
            "behavior": behavior,
        },
        "expected": {
            "training_range_m": [0.06, 0.20],
            "diagnostics_for_each_episode": True,
            "bounded_action_saturated": True,
            "reachable_and_infeasible_strata_distinct": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    try:
        payload = {
            "status": "passed",
            "unchecked_scope": _UNCHECKED_SCOPE,
            **_run_check(compatibility=args.compatibility),
        }
    except Exception as error:
        payload = {
            "status": "failed",
            "checked_scope": ["candidate diagnostics preparation"],
            "unchecked_scope": _UNCHECKED_SCOPE,
            "error": f"{type(error).__name__}: {error}",
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        raise
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
