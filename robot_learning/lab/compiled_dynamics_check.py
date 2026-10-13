"""Executable, defect-sensitive verification proposal for compiled dynamics.

The check calls the characterization's production path with controlled
inputs, then writes a compact result artifact.  It is intended for the
repository's ``python_module`` instrument and is not executed here.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from contracts.robots.two_joint_arm import MAX_REACH
from contracts.task_spec import FRAME_SKIP
from robot_learning.lab.compiled_dynamics import characterize


def _finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(item) for item in value)
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return True


def _check_normal(result: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    context = result.get("compiled_context", {})
    geometry = result.get("geometry", {})
    actuators = result.get("actuators", [])
    branches = result.get("ik_branch_feasibility", {})
    trajectories = result.get("control_trajectories", [])
    substep = result.get("substep_trace", {})

    if abs(context.get("timestep_seconds", -1.0) - 0.002) > 1e-12:
        errors.append("compiled timestep is not the official 0.002 seconds")
    if context.get("frame_skip") != FRAME_SKIP:
        errors.append("compiled characterization omitted or changed frame skip")
    if not geometry.get("bodies") or not geometry.get("geoms"):
        errors.append("compiled geometry summary is missing")
    if not actuators:
        errors.append("compiled actuator summary is missing")
    required_actuator_fields = {
        "transmission_type",
        "transmission_id",
        "control_range",
        "gain_parameters",
        "force_range",
        "gear",
    }
    for actuator in actuators:
        if not required_actuator_fields.issubset(actuator):
            errors.append("actuator transmission/control/gain/force fields are incomplete")
            break

    initial = np.asarray(geometry.get("initial_end_effector_position", []), dtype=float)
    expected_initial_x = MAX_REACH
    if initial.shape != (3,) or not np.isfinite(initial).all():
        errors.append("compiled initial end-effector geometry is not finite")
    elif abs(float(initial[0]) - expected_initial_x) > 1e-10:
        errors.append("compiled zero-pose end-effector geometry disagrees with link lengths")

    for branch_name in ("open", "folded"):
        branch = branches.get(branch_name)
        if not isinstance(branch, dict):
            errors.append(f"IK branch feasibility summary missing: {branch_name}")
            continue
        if branch.get("evaluated_samples") != 29 * 360:
            errors.append(f"IK branch grid is not the required dense official grid: {branch_name}")
        if branch.get("limit_feasible_samples", 0) <= 0:
            errors.append(f"IK branch has no legal configurations: {branch_name}")
        if branch.get("jacobian_condition_min") is None:
            errors.append(f"Jacobian conditioning summary missing: {branch_name}")

    if not isinstance(trajectories, list) or len(trajectories) != 3:
        errors.append("zero, saturated, and braking trajectories are not all present")
    total_resets = 0
    synchronized_steps = 0
    zero_poses = 0
    saturated_motion = False
    opposing_controls = False
    for trajectory in trajectories:
        replicates = trajectory.get("replicates", [])
        if len(replicates) != 2:
            errors.append(f"trajectory lacks repeated reset replicate: {trajectory.get('name')}")
        for replicate in replicates:
            total_resets += 1
            initial_state = replicate.get("initial", {})
            qpos = np.asarray(initial_state.get("qpos", []), dtype=float)
            qvel = np.asarray(initial_state.get("qvel", []), dtype=float)
            if qpos.shape == (2,) and qvel.shape == (2,) and np.max(
                np.abs(np.concatenate((qpos, qvel)))
            ) < 1e-10:
                zero_poses += 1
            else:
                errors.append("a repeated reset did not return to zero qpos/qvel")
            if not np.isfinite(qpos).all() or not np.isfinite(qvel).all():
                errors.append("a repeated reset produced non-finite qpos/qvel")
            steps = replicate.get("steps", [])
            if not steps:
                errors.append("a controlled trajectory has no repeated updates")
            for step in steps:
                fields = (
                    "qpos",
                    "qvel",
                    "qacc",
                    "ctrl",
                    "actuator_force",
                    "actuator_torque",
                )
                if not all(field in step for field in fields):
                    errors.append("synchronized qpos/qvel/qacc/control/force fields are incomplete")
                    continue
                arrays = [np.asarray(step[field], dtype=float) for field in fields]
                if not all(np.isfinite(array).all() for array in arrays):
                    errors.append("a repeated transition produced a non-finite diagnostic")
                if any(array.shape != (2,) for array in arrays):
                    errors.append("joint diagnostic dimensions are not synchronized")
                synchronized_steps += 1
                if trajectory.get("name") == "zero" and np.max(
                    np.abs(arrays[0]) + np.abs(arrays[1])
                ) > 1e-10:
                    errors.append("zero-action transition did not preserve the zero state")
                if trajectory.get("name") == "single_joint_saturated" and not np.allclose(
                    arrays[3], [1.0, 0.0], atol=1e-12
                ):
                    errors.append("single-joint saturated control was not preserved")
                if trajectory.get("name") == "single_joint_saturated" and np.max(
                    np.abs(arrays[0]) + np.abs(arrays[1])
                ) > 1e-9:
                    saturated_motion = True
                if trajectory.get("name") == "braking_opposing":
                    if arrays[3][0] < 0.0:
                        opposing_controls = True
                    if len(steps) >= 5 and step is steps[-1] and not np.allclose(
                        arrays[3], [-1.0, 0.0], atol=1e-12
                    ):
                        errors.append("braking control was not preserved")
            if len(replicates) == 2:
                first_steps = replicates[0].get("steps", [])
                second_steps = replicates[1].get("steps", [])
                if len(first_steps) != len(second_steps):
                    errors.append("repeated reset replicates have different step counts")
                else:
                    for first, second in zip(first_steps, second_steps):
                        for field in (
                            "qpos",
                            "qvel",
                            "qacc",
                            "ctrl",
                            "actuator_force",
                            "actuator_torque",
                        ):
                            first_array = np.asarray(first.get(field, []), dtype=float)
                            second_array = np.asarray(second.get(field, []), dtype=float)
                            if first_array.shape != second_array.shape or not np.allclose(
                                first_array,
                                second_array,
                                atol=1e-12,
                                rtol=1e-12,
                            ):
                                errors.append(
                                    f"repeated reset replicates diverged for {trajectory.get('name')} {field}"
                                )
                                break
    if total_resets < 6 or zero_poses != total_resets:
        errors.append("repeated reset coverage is incomplete")
    if synchronized_steps == 0:
        errors.append("no synchronized repeated step transitions were checked")
    if not saturated_motion:
        errors.append("single-joint saturation did not cause a controlled transition")
    if not opposing_controls:
        errors.append("braking trajectory omitted an opposing control transition")

    distances = substep.get("internal_substep_distances_m", [])
    if (
        len(distances) != FRAME_SKIP
        or "sampled_endpoint_distance_m" not in substep
        or "internal_distance_max_m" not in substep
        or "internal_minus_endpoint_max_abs_m" not in substep
    ):
        errors.append("substep-versus-endpoint distance comparison is missing")
    elif not _finite(substep):
        errors.append("substep-versus-endpoint comparison is non-finite")
    elif abs(float(distances[-1]) - float(substep["sampled_endpoint_distance_m"])) > 1e-12:
        errors.append("substep trace does not identify its sampled endpoint")

    observations = {
        "reset_count": total_resets,
        "synchronized_step_count": synchronized_steps,
        "zero_pose_resets": zero_poses,
        "trajectory_names": [item.get("name") for item in trajectories],
        "branch_names": sorted(branches),
        "substep_count": len(substep.get("internal_substep_distances_m", [])),
    }
    return errors, observations


def _check_compatibility(result: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    transition = result.get("compatibility_transition", {})
    trace = result.get("compatibility_substep_trace", {})
    if not result.get("compatibility_mode"):
        errors.append("compatibility mode did not mark its result")
    if not result.get("geometry", {}).get("geoms"):
        errors.append("compatibility path did not compile geometry")
    if not result.get("actuators"):
        errors.append("compatibility path did not expose actuators")
    if len(transition.get("steps", [])) != 5:
        errors.append("compatibility path did not perform controlled repeated steps")
    if len(trace.get("internal_substep_distances_m", [])) != FRAME_SKIP:
        errors.append("compatibility path did not exercise internal substeps")
    if not _finite(result):
        errors.append("compatibility production path produced non-finite values")
    return errors, {
        "transition_step_count": len(transition.get("steps", [])),
        "substep_count": len(trace.get("internal_substep_distances_m", [])),
        "geometry_count": len(result.get("geometry", {}).get("geoms", [])),
        "actuator_count": len(result.get("actuators", [])),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="small JSON check artifact path")
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args(argv)

    result = characterize(compatibility=args.compatibility)
    if args.compatibility:
        errors, observations = _check_compatibility(result)
        mode = "compatibility"
    else:
        errors, observations = _check_normal(result)
        mode = "behavioral"
    artifact = {
        "check": "compiled_dynamics_check",
        "mode": mode,
        "passed": not errors,
        "observed": observations,
        "expected": {
            "finite_synchronized_repeated_transitions": True,
            "compiled_geometry_and_actuator_summaries": True,
            "both_ik_branch_feasibility_summaries": not args.compatibility,
            "substep_endpoint_comparison": True,
        },
        "errors": errors,
        "checked_scope": [
            "compiled model summaries",
            "repeated resets and controlled transitions",
            "synchronized state/control/actuator diagnostics",
            "IK branch feasibility and Jacobian conditioning",
            "internal substep versus sampled endpoint distances",
        ],
        "unchecked_scope": [
            "policy learning or policy performance",
            "official evaluation success rate",
            "contact behavior outside the controlled traces",
            "continuous-time behavior between recorded MuJoCo substeps",
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    if errors:
        raise AssertionError("; ".join(errors))


if __name__ == "__main__":
    main()
