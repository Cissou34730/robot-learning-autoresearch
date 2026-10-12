"""Executable, defect-sensitive checks for physical_characterization.

The default mode performs a small controlled measurement and writes observed
checks plus the measured artifact.  ``--compatibility`` is an artifact-
independent smoke path for the MuJoCo calls used by the measurement.
"""

from __future__ import annotations

import argparse
import math
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.lab.physical_characterization import (
    forward_kinematics,
    load_model,
    measure_physical_characterization,
    reset_simulation,
    run_response_sequence,
    solve_two_link_ik,
    target_position,
    write_json_artifact,
)


def _finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_finite(key) and _finite(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    return True


def _independent_planar_position(qpos: np.ndarray, z: float) -> np.ndarray:
    q1, q2 = (float(value) for value in qpos)
    return np.asarray(
        [
            UPPER_ARM_LENGTH * math.cos(q1)
            + FOREARM_LENGTH * math.cos(q1 + q2),
            UPPER_ARM_LENGTH * math.sin(q1)
            + FOREARM_LENGTH * math.sin(q1 + q2),
            z,
        ],
        dtype=np.float64,
    )


def _check(name: str, observed: Any, expected: Any, scope: str) -> dict[str, Any]:
    return {"name": name, "observed": observed, "expected": expected, "scope": scope}


def run_compatibility_check() -> dict[str, Any]:
    """Exercise production MuJoCo paths without requiring a full measurement."""
    model = load_model()
    data = mujoco.MjData(model)
    reset_simulation(model, data)
    zero_state = {
        "qpos": np.asarray(data.qpos, dtype=float).tolist(),
        "qvel": np.asarray(data.qvel, dtype=float).tolist(),
    }
    fk = forward_kinematics(model, data, (0.2, -0.25))
    sequence = run_response_sequence(model, data, (0.0, 0.0), response_steps=2)
    result = {
        "mode": "compatibility",
        "checks": [
            _check(
                "reset_zero_state",
                zero_state,
                {"qpos": [0.0, 0.0], "qvel": [0.0, 0.0]},
                "reset_simulation and compiled state arrays",
            ),
            _check(
                "forward_kinematics_finite",
                bool(_finite(fk["position"].tolist()) and _finite(fk["jacobian"].tolist())),
                True,
                "forward_kinematics and mj_jacSite",
            ),
            _check(
                "controlled_path_has_two_steps",
                len(sequence["steps"]),
                2,
                "run_response_sequence and repeated mj_step calls",
            ),
        ],
        "checked_scope": [
            "exact XML model loading",
            "zero reset through production reset_simulation",
            "forward kinematics and Jacobian on a controlled configuration",
            "two repeated control steps through production response path",
        ],
        "unchecked_scope": [
            "full radius-angle grid",
            "all representative configurations and response steps",
            "artifact schema completeness",
        ],
    }
    if zero_state != {"qpos": [0.0, 0.0], "qvel": [0.0, 0.0]}:
        raise AssertionError("compatibility reset did not return the zero state")
    if len(sequence["steps"]) != 2:
        raise AssertionError("compatibility response did not execute two control steps")
    return result


def run_behavioral_check() -> dict[str, Any]:
    model = load_model()
    data = mujoco.MjData(model)

    reset_simulation(model, data)
    reset_observed = {
        "qpos": np.asarray(data.qpos[:2], dtype=float).tolist(),
        "qvel": np.asarray(data.qvel[:2], dtype=float).tolist(),
    }

    target_a = target_position(0.12, 0.0)
    target_b = target_position(0.12, math.pi / 2.0)
    fk_a = forward_kinematics(model, data, (0.0, 0.0))
    fk_b = forward_kinematics(model, data, (0.45, -0.35))
    target_changed = float(np.linalg.norm(target_a - target_b))
    configuration_changed = float(np.linalg.norm(fk_a["position"] - fk_b["position"]))
    if target_changed <= 0.0 or configuration_changed <= 0.0:
        raise AssertionError("target or configuration change was not observable")

    ik_radius = 0.15
    ik_angle = 0.35
    ik_target = target_position(ik_radius, ik_angle, z=float(fk_a["position"][2]))
    ik_checks = []
    for branch, solution in solve_two_link_ik(ik_radius, ik_angle).items():
        if solution is None:
            raise AssertionError(f"{branch} unexpectedly has no analytical solution")
        fk = forward_kinematics(model, data, solution)
        independent = _independent_planar_position(solution, float(ik_target[2]))
        production_error = float(np.linalg.norm(fk["position"] - ik_target))
        independent_error = float(np.linalg.norm(independent - ik_target))
        ik_checks.append(
            _check(
                f"{branch}_reconstructs_target",
                {
                    "production_error_m": production_error,
                    "independent_formula_error_m": independent_error,
                },
                {"production_error_m_max": 1e-9, "independent_formula_error_m_max": 1e-12},
                "analytical two-link IK branch and MuJoCo forward kinematics",
            )
        )
        if production_error > 1e-9 or independent_error > 1e-12:
            raise AssertionError(f"{branch} failed target reconstruction")

    sequence = run_response_sequence(model, data, (0.0, 0.0), response_steps=6)
    steps = sequence["steps"]
    reversal_index = sequence["summary"]["reversal"]["step_index"]
    positive_step = steps[0]
    negative_step = steps[reversal_index]
    positive_projection = float(
        np.dot(
            np.asarray(positive_step["applied_control"], dtype=float),
            np.asarray(
                positive_step["finite_difference_acceleration_rad_per_s2"], dtype=float
            ),
        )
    )
    negative_projection = float(
        np.dot(
            np.asarray(negative_step["applied_control"], dtype=float),
            np.asarray(
                negative_step["finite_difference_acceleration_rad_per_s2"], dtype=float
            ),
        )
    )
    qpos_change = float(
        np.linalg.norm(
            np.asarray(steps[-1]["qpos_rad"], dtype=float)
            - np.asarray(steps[0]["qpos_before_rad"], dtype=float)
        )
    )
    qvel_peak = float(
        max(np.linalg.norm(np.asarray(step["qvel_rad_per_s"], dtype=float)) for step in steps)
    )
    if positive_projection <= 0.0 or negative_projection >= 0.0:
        raise AssertionError(
            "the +1/-1 control reversal did not reverse acceleration projection"
        )
    if qpos_change <= 0.0 or qvel_peak <= 0.0:
        raise AssertionError("repeated response steps did not update qpos and qvel")

    reset_simulation(model, data)
    reset_after_response = {
        "qpos": np.asarray(data.qpos[:2], dtype=float).tolist(),
        "qvel": np.asarray(data.qvel[:2], dtype=float).tolist(),
    }

    measurement = measure_physical_characterization(
        radius_count=2, angle_count=4, response_steps=6
    )
    facts = measurement["compiled_facts"]
    required_units = {
        "timestep": facts["timestep"]["unit"] == "s",
        "control_interval": facts["control_interval"]["unit"] == "s",
        "joint_ranges": all(
            joint["range"]["unit"] == "rad"
            and joint["damping"]["unit"]
            and joint["armature"]["unit"]
            for joint in facts["joints"]
        ),
        "actuator_ranges": all(
            actuator["gear"]["unit"] and actuator["control_range"]["unit"]
            for actuator in facts["actuators"]
        ),
        "body_mass_inertia": all(
            body["mass"]["unit"] == "kg" and body["inertia"]["unit"] == "kg m^2"
            for body in facts["bodies"]
        ),
        "response_units": all(
            measurement["controlled_responses"]["sampling"][key]
            for key in (
                "control_interval_unit",
                "qpos_unit",
                "qvel_unit",
                "finite_difference_acceleration_unit",
                "endpoint_speed_unit",
            )
        ),
    }
    if not all(required_units.values()):
        raise AssertionError(f"missing compiled fact units: {required_units}")

    grid = measurement["ik_jacobian_grid"]
    records = grid["records"]
    feasible_reconstructions = [
        record
        for record in records
        if record["range_feasible"]
        and record["endpoint_reconstruction_error_m"] is not None
    ]
    if not feasible_reconstructions or any(
        record["endpoint_reconstruction_error_m"] > 1e-9
        for record in feasible_reconstructions
    ):
        raise AssertionError("measured feasible IK records do not reconstruct targets")

    checks = [
        _check(
            "reset_returns_zero",
            reset_observed,
            {"qpos": [0.0, 0.0], "qvel": [0.0, 0.0]},
            "initial reset of production simulation state",
        ),
        _check(
            "target_and_configuration_changes_are_observable",
            {
                "target_change_m": target_changed,
                "configuration_forward_change_m": configuration_changed,
            },
            {"both_positive": True},
            "target construction and forward kinematics",
        ),
        *ik_checks,
        _check(
            "reversal_changes_acceleration_direction",
            {
                "positive_control_acceleration_projection": positive_projection,
                "negative_control_acceleration_projection": negative_projection,
            },
            {"positive_gt_zero_and_negative_lt_zero": True},
            "repeated control updates, transition, and finite-difference acceleration",
        ),
        _check(
            "repeated_steps_update_state",
            {"qpos_change_rad": qpos_change, "peak_qvel_rad_per_s": qvel_peak},
            {"both_positive": True},
            "control-step qpos/qvel records",
        ),
        _check(
            "reset_clears_response_state",
            reset_after_response,
            {"qpos": [0.0, 0.0], "qvel": [0.0, 0.0]},
            "reset after repeated updates and reversal",
        ),
        _check(
            "compiled_facts_have_units",
            required_units,
            {"all_true": True},
            "compiled model authority/timing facts and response sampling units",
        ),
        _check(
            "both_grid_branches_reconstruct",
            {
                "feasible_record_count": len(feasible_reconstructions),
                "maximum_error_m": max(
                    record["endpoint_reconstruction_error_m"]
                    for record in feasible_reconstructions
                ),
            },
            {"maximum_error_m": 1e-9, "strictly_below": True},
            "bounded radius-angle grid and range-feasible IK branches",
        ),
    ]
    return {
        "mode": "behavioral",
        "checks": checks,
        "measurement": measurement,
        "checked_scope": [
            "zero reset state before and after response",
            "target and configuration forward-kinematics consequences",
            "both analytical IK branches at an independent target",
            "repeated +1/-1 transition and finite-difference acceleration direction",
            "compiled authority/timing facts and explicit units",
            "small measured grid and response artifact records",
        ],
        "unchecked_scope": [
            "full default grid density beyond the controlled 2-by-4 verification grid",
            "scientific validity of the physical model or its interpretation",
            "policy success, training behavior, and official evaluation",
            "response behavior outside the measured bounded controls and configurations",
        ],
    }


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="output JSON verification artifact")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run only the small artifact-independent production-path check",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _argument_parser().parse_args(argv)
    result = (
        run_compatibility_check() if args.compatibility else run_behavioral_check()
    )
    write_json_artifact(result, args.artifact)


if __name__ == "__main__":
    main()
