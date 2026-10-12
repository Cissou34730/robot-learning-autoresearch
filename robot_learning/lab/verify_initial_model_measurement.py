"""Defect-sensitive verification for the initial physical-model artifact."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    UPPER_ARM_LENGTH,
)
from robot_learning.lab import initial_model_measurement


REQUIRED_SECTIONS = (
    "compiled_model",
    "kinematics",
    "jacobian",
    "dynamics",
)
EXPECTED_UNITS = {
    "time": "s",
    "length": "m",
    "angle": "rad",
    "angular_velocity": "rad/s",
    "angular_acceleration": "rad/s^2",
    "mass": "kg",
    "inertia": "kg*m^2",
    "damping": "N*m*s/rad",
    "torque": "N*m",
    "jacobian": "m/rad",
}


def _reference_fk(q: list[float]) -> np.ndarray:
    shoulder, elbow = q
    total = shoulder + elbow
    return np.asarray(
        [
            UPPER_ARM_LENGTH * math.cos(shoulder)
            + FOREARM_LENGTH * math.cos(total),
            UPPER_ARM_LENGTH * math.sin(shoulder)
            + FOREARM_LENGTH * math.sin(total),
            0.02,
        ],
        dtype=float,
    )


def _reference_jacobian(q: list[float]) -> np.ndarray:
    shoulder, elbow = q
    total = shoulder + elbow
    return np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * math.sin(shoulder)
                - FOREARM_LENGTH * math.sin(total),
                -FOREARM_LENGTH * math.sin(total),
            ],
            [
                UPPER_ARM_LENGTH * math.cos(shoulder)
                + FOREARM_LENGTH * math.cos(total),
                FOREARM_LENGTH * math.cos(total),
            ],
        ],
        dtype=float,
    )


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_close(actual: Any, expected: Any, message: str, tolerance: float = 1e-10) -> None:
    actual_array = np.asarray(actual, dtype=float)
    expected_array = np.asarray(expected, dtype=float)
    _assert(
        actual_array.shape == expected_array.shape
        and np.allclose(actual_array, expected_array, rtol=1e-10, atol=tolerance),
        f"{message}: observed={actual!r}, expected={expected!r}",
    )


def _assert_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        _assert(math.isfinite(value), f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{path}.{key}")
        return
    raise AssertionError(f"unsupported JSON value at {path}: {type(value)!r}")


def _load_json(path: Path) -> dict[str, Any]:
    def reject_nonstandard_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    with path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle, parse_constant=reject_nonstandard_constant)
    _assert(isinstance(artifact, dict), "artifact root must be an object")
    _assert_finite(artifact)
    return artifact


def _verify_structure(artifact: dict[str, Any]) -> dict[str, Any]:
    _assert(artifact.get("schema_version") == 1, "schema_version must be 1")
    _assert(artifact.get("measurement") == "initial_physical_model", "wrong measurement")
    units = artifact.get("units")
    _assert(isinstance(units, dict), "units section is missing")
    for key, value in EXPECTED_UNITS.items():
        _assert(units.get(key) == value, f"units.{key} is missing or incorrect")
    for section in REQUIRED_SECTIONS:
        _assert(isinstance(artifact.get(section), dict), f"missing section: {section}")
    scope = artifact.get("scope")
    _assert(isinstance(scope, dict), "scope section is missing")
    _assert(scope.get("learned_candidate_used") is False, "a learned candidate was used")
    _assert(
        scope.get("protected_evaluator_semantics_resolved") is False,
        "artifact must not claim protected evaluator semantics are resolved",
    )
    return {
        "schema_version": artifact["schema_version"],
        "required_sections": list(REQUIRED_SECTIONS),
        "unit_keys": sorted(EXPECTED_UNITS),
    }


def _verify_compiled_model(artifact: dict[str, Any]) -> dict[str, Any]:
    compiled = artifact["compiled_model"]
    dimensions = compiled.get("dimensions", {})
    _assert(
        dimensions.get("nq") == 2
        and dimensions.get("nv") == 2
        and dimensions.get("nu") == 2,
        f"unexpected compiled dimensions: {dimensions}",
    )
    joints = compiled.get("joints")
    actuators = compiled.get("actuators")
    _assert(isinstance(joints, list) and len(joints) == 2, "two compiled joints required")
    _assert(
        [joint.get("name") for joint in joints] == ["shoulder", "elbow"],
        "compiled joint names/order are incorrect",
    )
    for joint in joints:
        _assert_close(
            joint.get("range_rad"),
            [-math.radians(170.0), math.radians(170.0)],
            f"joint range for {joint.get('name')}",
            tolerance=1e-12,
        )
        _assert(isinstance(joint.get("qpos_address"), int), "qpos address missing")
        _assert(isinstance(joint.get("dof_address"), int), "dof address missing")
    _assert(
        isinstance(actuators, list) and len(actuators) == 2,
        "two compiled actuators required",
    )
    for index, actuator in enumerate(actuators):
        _assert_close(
            actuator.get("control_range"),
            [-1.0, 1.0],
            f"control range for actuator {index}",
            tolerance=1e-12,
        )
        _assert_close(
            actuator.get("gear")[:1],
            [5.0],
            f"gear for actuator {index}",
            tolerance=1e-12,
        )
        _assert(
            actuator.get("transmission_joint") in ("shoulder", "elbow"),
            f"missing actuator transmission for actuator {index}",
        )
    _assert_close(compiled.get("gravity_m_s2"), [0.0, 0.0, 0.0], "gravity", tolerance=1e-12)
    _assert_close(compiled.get("timestep_s"), 0.002, "timestep", tolerance=1e-12)
    return {
        "dimensions": dimensions,
        "joint_count": len(joints),
        "actuator_count": len(actuators),
        "timestep_s": compiled["timestep_s"],
    }


def _verify_ik(artifact: dict[str, Any]) -> dict[str, Any]:
    kinematics = artifact["kinematics"]
    records = kinematics.get("records")
    _assert(isinstance(records, list), "IK records are missing")
    _assert(
        len(records) == 25 * 72 * 2,
        f"unexpected IK record count: {len(records)}",
    )
    _assert(len(kinematics.get("radius_grid_m", [])) == 25, "radius grid is not 25 points")
    _assert(len(kinematics.get("azimuth_grid_rad", [])) == 72, "angle grid is not 72 points")
    feasible = 0
    branches: set[str] = set()
    maximum_residual = 0.0
    for index, record in enumerate(records):
        _assert(record.get("branch") in ("positive_elbow", "negative_elbow"), f"bad branch at {index}")
        branches.add(record["branch"])
        target = np.asarray(record.get("target_xyz_m"), dtype=float)
        q = [float(value) for value in record.get("q_rad", [])]
        _assert(target.shape == (3,) and len(q) == 2, f"malformed IK record at {index}")
        radius = math.hypot(float(target[0]), float(target[1]))
        _assert(0.06 - 1e-12 <= radius <= 0.20 + 1e-12, f"radius outside official domain at {index}")
        if record.get("feasible"):
            feasible += 1
            residual = float(np.linalg.norm(_reference_fk(q) - target))
            maximum_residual = max(maximum_residual, residual)
            _assert(residual <= 1e-8, f"independent IK residual is large at {index}: {residual}")
            _assert(
                -math.radians(170.0) - 1e-12 <= q[0] <= math.radians(170.0) + 1e-12
                and -math.radians(170.0) - 1e-12 <= q[1] <= math.radians(170.0) + 1e-12,
                f"feasible IK solution violates limits at {index}",
            )
            _assert(float(record.get("analytic_fk_residual_m")) <= 1e-8, "reported analytic residual is large")
            _assert(float(record.get("compiled_fk_residual_m")) <= 1e-8, "compiled FK residual is large")
    _assert(branches == {"positive_elbow", "negative_elbow"}, "both IK branches were not measured")
    _assert(feasible > 0, "no feasible IK solutions were reported")
    return {
        "record_count": len(records),
        "feasible_count": feasible,
        "branches": sorted(branches),
        "maximum_independent_residual_m": maximum_residual,
    }


def _verify_jacobians(artifact: dict[str, Any]) -> dict[str, Any]:
    records = artifact["jacobian"].get("records")
    _assert(isinstance(records, list) and len(records) >= 3, "Jacobian records are incomplete")
    by_name = {record.get("name"): record for record in records}
    _assert({"reset", "bent_1", "bent_2"} <= set(by_name), "required Jacobian configurations are missing")
    reset_smallest = None
    bent_smallest: list[float] = []
    for name, record in by_name.items():
        q = [float(value) for value in record.get("q_rad", [])]
        expected = _reference_jacobian(q)
        observed = np.asarray(record.get("analytic_jacobian_m_per_rad"), dtype=float)
        _assert(
            observed.shape == (2, 2) and np.allclose(observed, expected, atol=1e-10, rtol=1e-10),
            f"analytic Jacobian formula mismatch at {name}",
        )
        singular_values = np.linalg.svd(expected, compute_uv=False)
        _assert_close(
            record.get("singular_values_m_per_rad"),
            singular_values,
            f"singular values at {name}",
            tolerance=1e-10,
        )
        if name == "reset":
            reset_smallest = float(singular_values[-1])
        else:
            bent_smallest.append(float(singular_values[-1]))
    _assert(reset_smallest is not None and reset_smallest <= 1e-12, "reset is not singular")
    _assert(all(value > 1e-4 for value in bent_smallest), "bent configuration is singular")
    return {
        "reset_smallest_singular_value_m_per_rad": reset_smallest,
        "bent_smallest_singular_values_m_per_rad": bent_smallest,
        "checked_formula_independently": True,
    }


def _state_close(first: dict[str, Any], second: dict[str, Any], label: str) -> None:
    for field in ("qpos", "qvel", "qacc", "qfrc_actuator"):
        _assert_close(
            first.get(field),
            second.get(field),
            f"repeated trial {label} field {field}",
            tolerance=1e-12,
        )


def _verify_dynamics(artifact: dict[str, Any]) -> dict[str, Any]:
    compiled = artifact["compiled_model"]
    joints = compiled["joints"]
    actuators = compiled["actuators"]
    dof_by_joint = {joint["name"]: int(joint["dof_address"]) for joint in joints}
    trials = artifact["dynamics"].get("controlled_trials")
    _assert(isinstance(trials, list) and trials, "controlled dynamics trials are missing")
    groups: dict[tuple[str, tuple[float, ...]], list[dict[str, Any]]] = defaultdict(list)
    positive_force_checks = 0
    for trial in trials:
        _assert(trial.get("physics_steps") == 10, "controlled trial does not use ten physics steps")
        _assert_close(trial.get("interval_s"), 0.020, "controlled interval", tolerance=1e-12)
        command = tuple(float(value) for value in trial.get("command", []))
        _assert(len(command) == 2 and all(-1.0 <= value <= 1.0 for value in command), "bad control command")
        groups[(str(trial.get("configuration")), command)].append(trial)
        before = trial.get("before", {})
        after = trial.get("after", {})
        _assert(len(before.get("qpos", [])) == 2 and len(after.get("qpos", [])) == 2, "bad qpos snapshot")
        _assert(len(after.get("qfrc_actuator", [])) == 2, "bad actuator-force snapshot")
        for index, value in enumerate(command):
            if value > 0.0:
                actuator = actuators[index]
                joint_name = actuator["transmission_joint"]
                dof = dof_by_joint[joint_name]
                force = float(after["qfrc_actuator"][dof])
                gear = abs(float(actuator["gear"][0]))
                _assert(force > 0.0, f"positive command produced non-positive force at actuator {index}")
                _assert(
                    abs(force) <= gear * value + 1e-8,
                    f"positive actuator force exceeded bounded transmission at actuator {index}",
                )
                positive_force_checks += 1
    for key, group in groups.items():
        _assert(len(group) == 2, f"expected two repeated trials for {key}, got {len(group)}")
        _assert(
            {int(trial.get("repeat_index")) for trial in group} == {0, 1},
            f"repeat indices are incomplete for {key}",
        )
        _state_close(group[0]["before"], group[1]["before"], f"{key} before")
        _state_close(group[0]["after"], group[1]["after"], f"{key} after")
    _assert(positive_force_checks >= 2, "both positive actuator signs were not checked")

    free_decay = artifact["dynamics"].get("free_decay", {})
    states = free_decay.get("states")
    _assert(isinstance(states, list) and len(states) == 26, "free-decay trace is incomplete")
    _assert(free_decay.get("command") == [0.0, 0.0], "free decay is not zero-control")
    initial_qvel = states[0].get("qvel")
    _assert(
        isinstance(initial_qvel, list) and len(initial_qvel) == 2,
        "free-decay velocity snapshot has the wrong dimension",
    )
    _assert_close(
        [initial_qvel[dof_by_joint["shoulder"]], initial_qvel[dof_by_joint["elbow"]]],
        [0.35, -0.20],
        "known free-decay initial velocity",
        tolerance=1e-12,
    )
    maximum_speed = max(
        max(abs(float(value)) for value in state.get("qvel", [])) for state in states
    )
    _assert(maximum_speed < 10.0, "free-decay response is not bounded")
    return {
        "trial_group_count": len(groups),
        "positive_force_checks": positive_force_checks,
        "free_decay_state_count": len(states),
        "maximum_abs_qvel_rad_s": maximum_speed,
    }


def verify_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    structure = _verify_structure(artifact)
    compiled = _verify_compiled_model(artifact)
    ik = _verify_ik(artifact)
    jacobian = _verify_jacobians(artifact)
    dynamics = _verify_dynamics(artifact)
    return {
        "status": "passed",
        "observed": {
            "structure": structure,
            "compiled_model": compiled,
            "ik": ik,
            "jacobian": jacobian,
            "dynamics": dynamics,
        },
        "expected": {
            "independent_ik_residual_m": "<= 1e-8 for every feasible record",
            "reset_jacobian_smallest_singular_value_m_per_rad": "<= 1e-12",
            "bent_jacobian_smallest_singular_value_m_per_rad": "> 1e-4",
            "repeated_trials": "two equal reset/ten-step traces per configuration and command",
            "positive_actuator_force": "positive and no greater than gear times command",
            "json_values": "finite and JSON-serializable",
        },
        "checked_scope": [
            "compiled dimensions, timestep, gravity, joint limits, control ranges, and gears",
            "independent two-link IK forward residuals and joint-limit checks",
            "independent analytic Jacobian entries and singular-value consequences",
            "repeated reset/step determinism and positive actuator generalized-force sign",
            "bounded zero-control free-decay trace",
            "required sections, units, and finite JSON values",
        ],
        "unchecked_scope": [
            "protected evaluator hold semantics",
            "learned-policy coverage or performance",
            "scientific validity of default compiled inertial properties",
        ],
    }


def verify_compatibility() -> dict[str, Any]:
    observed = initial_model_measurement.compatibility_probe()
    dimensions = observed["dimensions"]
    _assert(dimensions == {"nq": 2, "nv": 2, "nu": 2}, f"unexpected dimensions: {dimensions}")
    command = observed["command"]
    after_force = observed["after"]["qfrc_actuator"]
    _assert(observed["physics_steps"] == 3, "compatibility probe did not take three steps")
    for index, value in enumerate(command):
        force = float(after_force[index])
        _assert(math.copysign(1.0, force) == math.copysign(1.0, value), "compatibility actuator sign mismatch")
        _assert(abs(force) <= 5.0 * abs(value) + 1e-8, "compatibility actuator force is unbounded")
    return {
        "status": "passed",
        "observed": observed,
        "expected": {
            "dimensions": {"nq": 2, "nv": 2, "nu": 2},
            "reset_then_step": "three controlled MuJoCo physics steps",
            "actuator_force": "same sign as command and bounded by 5|command| N*m",
        },
        "checked_scope": [
            "production model-loading and validation path",
            "production reset/forward path",
            "native MuJoCo controlled stepping and actuator-force sign",
        ],
        "unchecked_scope": [
            "full dense IK grid",
            "full ten-step repeated-trial artifact",
            "protected evaluator and learned-policy behavior",
        ],
    }


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, help="measurement artifact to verify")
    parser.add_argument("--output", type=Path, required=True, help="verification JSON to write")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the artifact-independent MuJoCo compatibility probe",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.compatibility:
            _assert(args.artifact is None, "--artifact is not used in compatibility mode")
            result = verify_compatibility()
        else:
            _assert(args.artifact is not None, "--artifact is required outside compatibility mode")
            result = verify_artifact(_load_json(args.artifact))
    except Exception as error:
        result = {
            "status": "failed",
            "observed": {"error": str(error)},
            "expected": {
                "status": "passed",
                "failure_sensitive_to": [
                    "swapped kinematics or Jacobian formulas",
                    "wrong actuator sign",
                    "missing reset between repeated trials",
                    "malformed or non-finite artifact",
                ],
            },
            "checked_scope": [],
            "unchecked_scope": [
                "checks after the reported failure",
                "protected evaluator and learned-policy behavior",
            ],
        }
        _write_result(args.output, result)
        return 1
    _write_result(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
