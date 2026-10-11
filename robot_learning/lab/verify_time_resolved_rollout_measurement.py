"""Independent structural and physics check for the time-resolved artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, TWO_JOINT_ARM_XML_PATH, UPPER_ARM_LENGTH
from contracts.task_spec import MAX_EPISODE_STEPS, SUCCESS_THRESHOLD


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FAILURE_SEEDS = {
    4201,
    4208,
    4225,
    4226,
    4228,
    4243,
    4244,
    4246,
    4307,
    4316,
}
EXPECTED_CONTROL_SEEDS = {
    4211,
    4214,
    4236,
    4264,
    4286,
    4297,
    4337,
    4347,
    4349,
    4355,
}
BRANCH_NEAR_TOLERANCE_RAD = 0.10
JOINT_LIMIT_TOLERANCE_RAD = 1e-10
NUMERICAL_TOLERANCE = 2e-7


class VerificationError(ValueError):
    """A defect-sensitive artifact check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _array(value: Any, shape: tuple[int, ...], field: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    _require(result.shape == shape, f"{field} has shape {result.shape}, expected {shape}")
    _require(bool(np.all(np.isfinite(result))), f"{field} contains a non-finite value")
    return result


def _finite(value: Any, field: str) -> float:
    result = float(value)
    _require(bool(np.isfinite(result)), f"{field} is not finite")
    return result


def _close(actual: Any, expected: Any, field: str, tolerance: float = NUMERICAL_TOLERANCE) -> None:
    _require(
        bool(np.allclose(np.asarray(actual), np.asarray(expected), rtol=tolerance, atol=tolerance)),
        f"{field} disagrees with its independent reference",
    )


def _wrap(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _reference_ik(target: np.ndarray, model: mujoco.MjModel, qpos: np.ndarray) -> dict[str, Any]:
    cosine = (
        target[0] ** 2
        + target[1] ** 2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    _require(-1.0 - 1e-10 <= cosine <= 1.0 + 1e-10, "target is outside independent IK domain")
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    branches = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = np.arctan2(target[1], target[0]) - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        solution = np.array([_wrap(shoulder), elbow])
        feasible = bool(
            np.all(solution >= model.jnt_range[:2, 0] - JOINT_LIMIT_TOLERANCE_RAD)
            and np.all(solution <= model.jnt_range[:2, 1] + JOINT_LIMIT_TOLERANCE_RAD)
        )
        error = float(
            np.linalg.norm([_wrap(qpos[0] - solution[0]), qpos[1] - solution[1]])
        )
        branches[name] = {"solution": solution, "feasible": feasible, "error": error}
    near = [
        name
        for name, branch in branches.items()
        if branch["feasible"] and branch["error"] <= BRANCH_NEAR_TOLERANCE_RAD
    ]
    occupancy = (
        "ambiguous"
        if not near
        else min(near, key=lambda name: branches[name]["error"])
    )
    branches["occupancy"] = occupancy
    return branches


def _check_trace(
    rollout: dict[str, Any],
    model: mujoco.MjModel,
    data: mujoco.MjData,
) -> dict[str, Any]:
    target = _array(rollout["target"]["position_m"], (3,), "target")
    target_radius = float(np.hypot(target[0], target[1]))
    _close(rollout["target"]["radius_m"], target_radius, "target radius")
    _close(rollout["target"]["radius_cm"], 100.0 * target_radius, "target radius in centimeters")
    _close(
        rollout["target"]["angle_degrees"],
        np.degrees(np.arctan2(target[1], target[0])),
        "target angle",
    )
    trace = rollout["trace"]
    _require(isinstance(trace, list) and len(trace) > 0, "rollout has no time-resolved trace")
    initial_qpos = _array(rollout["initial_state"]["qpos_rad"], (2,), "initial qpos")
    initial_qvel = _array(rollout["initial_state"]["qvel_rad_s"], (2,), "initial qvel")
    _close(initial_qpos, np.zeros(2), "initial qpos reset", tolerance=0.0)
    _close(initial_qvel, np.zeros(2), "initial qvel reset", tolerance=0.0)
    previous_qpos = initial_qpos
    previous_qvel = initial_qvel
    previous_held = 0
    interruptions = 0
    first_reach = None
    max_held = 0
    for expected_step, record in enumerate(trace, start=1):
        _require(record["control_step"] == expected_step, "trace control steps are not consecutive")
        qpos_before = _array(record["qpos_before_rad"], (2,), "qpos_before")
        qvel_before = _array(record["qvel_before_rad_s"], (2,), "qvel_before")
        qpos_after = _array(record["qpos_after_rad"], (2,), "qpos_after")
        qvel_after = _array(record["qvel_after_rad_s"], (2,), "qvel_after")
        _close(qpos_before, previous_qpos, "repeated qpos state")
        _close(qvel_before, previous_qvel, "repeated qvel state")
        endpoint = _array(record["endpoint_position_m"], (3,), "endpoint position")
        endpoint_velocity = _array(record["endpoint_velocity_m_s"], (3,), "endpoint velocity")
        _array(record["target_position_m"], (3,), "trace target")
        _close(record["target_position_m"], target, "stable target")
        _array(record["policy_action"], (2,), "policy action")
        applied = _array(record["applied_clipped_control"], (2,), "applied control")
        _require(bool(np.all(applied >= -1.0)) and bool(np.all(applied <= 1.0)), "control is not clipped")
        _array(record["actuator_force"], (2,), "actuator force")
        _array(record["joint_actuator_torque_Nm"], (2,), "joint actuator torque")

        data.qpos[:] = qpos_after
        data.qvel[:] = qvel_after
        mujoco.mj_forward(model, data)
        _close(endpoint, data.site("end_effector").xpos, "endpoint forward kinematics")
        distance = float(np.linalg.norm(endpoint - target))
        _close(record["distance_m"], distance, "distance")
        _close(record["distance_cm"], 100.0 * distance, "distance in centimeters")
        in_tolerance = distance <= SUCCESS_THRESHOLD
        _require(record["in_tolerance"] is in_tolerance, "tolerance flag disagrees with distance")
        held = int(record["held_steps"])
        expected_held = previous_held + 1 if in_tolerance else 0
        _require(held == expected_held, "held_steps violates the tolerance transition rule")
        _require(int(record["previous_held_steps"]) == previous_held, "previous hold counter is wrong")
        interruption = previous_held > 0 and not in_tolerance
        _require(record["interruption"] is interruption, "interruption flag is wrong")
        if interruption:
            interruptions += 1
        expected_transition = (
            "entered"
            if in_tolerance and previous_held == 0
            else "continued"
            if in_tolerance
            else "interrupted"
            if interruption
            else "outside"
        )
        _require(record["hold_counter_transition"] == expected_transition, "hold transition label is wrong")
        _require(int(record["cumulative_interruptions"]) == interruptions, "cumulative interruptions are wrong")
        if in_tolerance and first_reach is None:
            first_reach = expected_step
        max_held = max(max_held, held)

        branches = _reference_ik(target, model, qpos_after)
        for name in ("open", "folded"):
            observed = record["ik"][name]
            _array(observed["qpos_rad"], (2,), f"{name} IK solution")
            _close(observed["qpos_rad"], branches[name]["solution"], f"{name} IK solution")
            _require(bool(observed["feasible"]) is branches[name]["feasible"], f"{name} feasibility is wrong")
            _close(observed["error_rad"], branches[name]["error"], f"{name} branch error")
        _require(record["ik"]["occupancy"] == branches["occupancy"], "branch occupancy is wrong")

        dynamics = record["dynamics"]
        _close(dynamics["elbow_angle_rad"], qpos_after[1], "elbow angle")
        _close(dynamics["sin_elbow"], np.sin(qpos_after[1]), "sin elbow")
        _close(dynamics["joint_velocity_norm_rad_s"], np.linalg.norm(qvel_after), "joint velocity norm")
        _close(dynamics["endpoint_velocity_norm_m_s"], np.linalg.norm(endpoint_velocity), "endpoint velocity norm")
        radial_norm = float(np.hypot(endpoint[0], endpoint[1]))
        if radial_norm <= 1e-15:
            _require(
                dynamics["radial_endpoint_velocity_m_s"] is None
                and dynamics["tangential_endpoint_velocity_m_s"] is None,
                "unavailable radial quantities must be null",
            )
        else:
            radial_unit = endpoint[:2] / radial_norm
            tangential_unit = np.array([-radial_unit[1], radial_unit[0]])
            _close(
                dynamics["radial_endpoint_velocity_m_s"],
                np.dot(endpoint_velocity[:2], radial_unit),
                "radial endpoint velocity",
            )
            _close(
                dynamics["tangential_endpoint_velocity_m_s"],
                np.dot(endpoint_velocity[:2], tangential_unit),
                "tangential endpoint velocity",
            )

        contact = record["contact"]
        count = int(contact["count"])
        _require(count >= 0 and len(contact["events"]) == count, "contact record is incomplete")
        for event in contact["events"]:
            _require(isinstance(event["geom1"], int) and isinstance(event["geom2"], int), "contact IDs are not integers")
            _finite(event["distance_m"], "contact distance")
        _require(bool(record["terminated"]) == (held >= 100), "termination disagrees with hold counter")
        _require(bool(record["truncated"]) == (expected_step >= MAX_EPISODE_STEPS), "truncation disagrees with horizon")
        if expected_step < len(trace):
            _require(
                not record["terminated"] and not record["truncated"],
                "trace continues after termination or truncation",
            )
        previous_qpos, previous_qvel, previous_held = qpos_after, qvel_after, held

    outcome = rollout["outcome"]
    _require(trace[-1]["terminated"] or trace[-1]["truncated"], "trace does not end in termination or truncation")
    _require(int(outcome["steps"]) == len(trace), "outcome step count is wrong")
    expected_success = rollout["role"] == "control"
    _require(bool(outcome["success"]) is expected_success, "role outcome is wrong")
    _require(bool(outcome["success"]) is bool(trace[-1]["terminated"]), "outcome success is wrong")
    _require(bool(outcome["terminated"]) is bool(trace[-1]["terminated"]), "outcome termination is wrong")
    _require(bool(outcome["truncated"]) is bool(trace[-1]["truncated"]), "outcome truncation is wrong")
    _require(int(outcome["first_reach_step"]) == first_reach if first_reach is not None else outcome["first_reach_step"] is None, "first reach is wrong")
    _require(int(outcome["max_held_steps"]) == max_held, "maximum hold is wrong")
    _require(int(outcome["hold_interruptions"]) == interruptions, "outcome interruptions are wrong")
    final_branch = rollout["mechanism_diagnostics"]
    _require(final_branch["final_branch_occupancy"] == trace[-1]["ik"]["occupancy"], "final branch label is missing or wrong")
    for name in ("open", "folded"):
        _close(
            final_branch["final_branch_errors_rad"][name],
            trace[-1]["ik"][name]["error_rad"],
            f"final {name} branch error",
        )
    summary = rollout["contact_summary"]
    counts = [int(record["contact"]["count"]) for record in trace]
    _require(int(summary["samples"]) == len(trace), "contact summary samples are wrong")
    _require(int(summary["maximum_contact_count"]) == max(counts), "contact summary maximum is wrong")
    _require(int(summary["nonzero_contact_samples"]) == sum(count > 0 for count in counts), "contact summary nonzero count is wrong")
    return {"first_reach_step": first_reach, "interruptions": interruptions}


def verify_artifact(artifact_path: Path) -> dict[str, Any]:
    path = artifact_path if artifact_path.is_absolute() else REPOSITORY_ROOT / artifact_path
    with path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    _require(artifact["schema_version"] == 1, "unsupported artifact schema")
    _require(artifact["measurement"] == "time_resolved_rollout_mechanism_discrimination", "wrong measurement")
    requested = artifact["requested_rollouts"]
    failure_seeds = requested["failure_seeds"]
    control_seeds = requested["control_seeds"]
    _require(set(failure_seeds) == EXPECTED_FAILURE_SEEDS and len(failure_seeds) == 10, "failure seed panel is wrong")
    _require(set(control_seeds) == EXPECTED_CONTROL_SEEDS and len(control_seeds) == 10, "control seed panel is wrong")
    _require(requested["total"] == 20, "requested rollout count is wrong")
    semantics = artifact["evaluation_semantics"]
    _require(semantics["frame_skip"] == 10 and semantics["simulator_substeps_per_action"] == 10, "substep semantics are missing")
    _require(semantics["hold_steps_required"] == 100 and semantics["max_control_steps"] == 500, "hold or horizon semantics are missing")
    _require(bool(artifact["reset_evidence"]["each_rollout_reset_with_its_seed"]), "reset evidence is missing")
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    _require(model.nq == 2 and model.nv == 2 and model.nu == 2, "compiled model dimensions are unexpected")
    rollouts = artifact["rollouts"]
    _require(len(rollouts) == 20, "artifact does not contain exactly 20 rollouts")
    seen = set()
    checked = []
    for rollout in rollouts:
        seed = int(rollout["seed"])
        _require(seed not in seen, "duplicate rollout seed")
        seen.add(seed)
        expected_role = "failure" if seed in EXPECTED_FAILURE_SEEDS else "control" if seed in EXPECTED_CONTROL_SEEDS else None
        _require(expected_role is not None and rollout["role"] == expected_role, "rollout role is wrong")
        _require(bool(rollout["expected_success"]) is (expected_role == "control"), "expected role outcome is wrong")
        checked.append(_check_trace(rollout, model, data))
    _require(seen == EXPECTED_FAILURE_SEEDS | EXPECTED_CONTROL_SEEDS, "requested seeds are not all represented")
    failures = [item for rollout, item in zip(rollouts, checked, strict=True) if rollout["role"] == "failure"]
    _require(any(item["interruptions"] > 0 for item in failures), "no failure exercises a hold interruption")
    _require(any(item["first_reach_step"] is None for item in failures), "no failure exercises the no-first-reach transition")
    return {
        "checked_rollouts": len(rollouts),
        "checked_steps": sum(len(rollout["trace"]) for rollout in rollouts),
        "failure_with_interruption": True,
        "failure_without_first_reach": True,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify a time-resolved rollout artifact.")
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else REPOSITORY_ROOT / args.output
    try:
        observed = verify_artifact(args.artifact)
        result = {
            "schema_version": 1,
            "passed": True,
            "observed_vs_expected": observed,
            "checked_scope": [
                "20 exact M9 seeds and role outcomes",
                "reset state and repeated qpos/qvel transitions",
                "forward-kinematics endpoint and geometry distances",
                "hold transitions, interruption classes, contacts, and branch IK",
            ],
            "unchecked_scope": [
                "scientific validity of the mechanism interpretation",
                "policy provenance beyond the artifact runtime metadata",
            ],
        }
        exit_code = 0
    except (VerificationError, KeyError, IndexError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": 1,
            "passed": False,
            "error": str(exc),
            "observed_vs_expected": {},
            "checked_scope": [],
            "unchecked_scope": ["The artifact was not fully checked after this defect."],
        }
        exit_code = 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
