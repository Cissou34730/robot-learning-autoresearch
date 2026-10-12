"""Independent verifier for the paired T7/T4 rollout artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import MAX_EPISODE_STEPS, SUCCESS_THRESHOLD


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SEEDS = [
    4200,
    4201,
    4202,
    4203,
    4204,
    4205,
    4206,
    4207,
    4208,
    4209,
    4210,
    4261,
]
HOLD_STEPS_REQUIRED = 100
BRANCH_NEAR_TOLERANCE_RAD = 0.10
JOINT_LIMIT_TOLERANCE_RAD = 1e-10
NUMERICAL_TOLERANCE = 2e-7


class VerificationError(ValueError):
    """An artifact does not satisfy the paired measurement contract."""


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


def _close(
    actual: Any,
    expected: Any,
    field: str,
    tolerance: float = NUMERICAL_TOLERANCE,
) -> None:
    actual_array = np.asarray(actual)
    expected_array = np.asarray(expected)
    if not bool(np.allclose(actual_array, expected_array, rtol=tolerance, atol=tolerance)):
        raise VerificationError(
            f"{field} disagrees with its independent reference: "
            f"actual={actual_array}, expected={expected_array}"
        )


def _wrap(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _reference_ik(
    target: np.ndarray, model: mujoco.MjModel, qpos: np.ndarray
) -> dict[str, Any]:
    cosine = (
        target[0] ** 2
        + target[1] ** 2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    _require(
        -1.0 - 1e-10 <= cosine <= 1.0 + 1e-10,
        "target is outside the independent IK domain",
    )
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    branches: dict[str, Any] = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = np.arctan2(target[1], target[0]) - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        solution = np.array([_wrap(shoulder), elbow])
        feasible = bool(
            np.all(
                solution >= model.jnt_range[:2, 0] - JOINT_LIMIT_TOLERANCE_RAD
            )
            and np.all(
                solution <= model.jnt_range[:2, 1] + JOINT_LIMIT_TOLERANCE_RAD
            )
        )
        error = float(
            np.linalg.norm([_wrap(qpos[0] - solution[0]), qpos[1] - solution[1]])
        )
        branches[name] = {
            "solution": solution,
            "feasible": feasible,
            "error": error,
        }
    near = [
        name
        for name, branch in branches.items()
        if branch["feasible"] and branch["error"] <= BRANCH_NEAR_TOLERANCE_RAD
    ]
    branches["occupancy"] = (
        "ambiguous"
        if not near
        else min(near, key=lambda name: branches[name]["error"])
    )
    return branches


def _check_rollout(
    rollout: dict[str, Any],
    model: mujoco.MjModel,
    data: mujoco.MjData,
) -> dict[str, Any]:
    target = _array(rollout["target"]["position_m"], (3,), "target")
    radius = float(np.hypot(target[0], target[1]))
    _close(rollout["target"]["radius_m"], radius, "target radius")
    _close(rollout["target"]["radius_cm"], 100.0 * radius, "target radius cm")
    _close(
        rollout["target"]["angle_degrees"],
        np.degrees(np.arctan2(target[1], target[0])),
        "target angle",
    )
    initial_qpos = _array(rollout["initial_state"]["qpos_rad"], (2,), "initial qpos")
    initial_qvel = _array(
        rollout["initial_state"]["qvel_rad_s"], (2,), "initial qvel"
    )
    _close(initial_qpos, np.zeros(2), "reset qpos", tolerance=0.0)
    _close(initial_qvel, np.zeros(2), "reset qvel", tolerance=0.0)
    trace = rollout["trace"]
    _require(isinstance(trace, list) and trace, "rollout has no trace")
    _require(len(trace) <= MAX_EPISODE_STEPS, "rollout exceeds the 500-step horizon")
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    _require(site_id >= 0, "official XML has no end_effector site")

    previous_qpos = initial_qpos
    previous_qvel = initial_qvel
    previous_held = 0
    interruptions = 0
    first_reach = None
    max_held = 0
    saw_continued = False
    for expected_step, record in enumerate(trace, start=1):
        _require(
            int(record["control_step"]) == expected_step,
            "trace control steps are not consecutive",
        )
        qpos_before = _array(record["qpos_before_rad"], (2,), "qpos before")
        qvel_before = _array(record["qvel_before_rad_s"], (2,), "qvel before")
        qpos_after = _array(record["qpos_after_rad"], (2,), "qpos after")
        qvel_after = _array(record["qvel_after_rad_s"], (2,), "qvel after")
        _close(qpos_before, previous_qpos, "repeated qpos transition")
        _close(qvel_before, previous_qvel, "repeated qvel transition")
        endpoint = _array(record["endpoint_position_m"], (3,), "live endpoint")
        endpoint_velocity = _array(
            record["endpoint_velocity_m_s"], (3,), "live endpoint velocity"
        )
        _close(record["target_position_m"], target, "stable target")
        _array(record["policy_action"], (2,), "policy action")
        applied = _array(record["applied_clipped_control"], (2,), "clipped control")
        _require(
            bool(np.all(applied >= -1.0)) and bool(np.all(applied <= 1.0)),
            "applied control is outside [-1, 1]",
        )
        _array(record["actuator_force"], (2,), "actuator force")
        _array(record["joint_actuator_torque_Nm"], (2,), "joint actuator torque")

        mujoco.mj_resetData(model, data)
        data.qpos[:] = qpos_after
        data.qvel[:] = qvel_after
        mujoco.mj_forward(model, data)
        reference_endpoint = np.asarray(
            data.site("end_effector").xpos, dtype=np.float64
        ).copy()
        jacobian_position = np.empty((3, model.nv), dtype=np.float64)
        jacobian_rotation = np.empty((3, model.nv), dtype=np.float64)
        mujoco.mj_jacSite(
            model, data, jacobian_position, jacobian_rotation, site_id
        )
        reference_velocity = jacobian_position @ qvel_after
        reference = record["kinematic_reference"]
        _close(
            reference["endpoint_position_m"],
            reference_endpoint,
            "forward-kinematic endpoint reference",
        )
        _close(
            reference["endpoint_velocity_m_s"],
            reference_velocity,
            "Jacobian-times-qvel endpoint reference",
        )
        position_error = _finite(
            reference["position_error_m"], "position reference error"
        )
        velocity_error = _finite(
            reference["velocity_error_m_s"], "velocity reference error"
        )
        _require(position_error >= 0.0 and velocity_error >= 0.0, "negative reference error")
        _close(position_error, np.linalg.norm(endpoint - reference_endpoint), "position error")
        _close(velocity_error, np.linalg.norm(endpoint_velocity - reference_velocity), "velocity error")
        _close(
            endpoint,
            reference_endpoint,
            "live endpoint versus independent forward kinematics",
        )
        _close(
            endpoint_velocity,
            reference_velocity,
            "live endpoint velocity versus independent Jacobian",
        )

        distance = float(np.linalg.norm(endpoint - target))
        _close(record["distance_m"], distance, "live distance")
        _close(record["distance_cm"], 100.0 * distance, "distance cm")
        in_tolerance = distance <= SUCCESS_THRESHOLD
        _require(record["in_tolerance"] is in_tolerance, "in-tolerance flag is stale")
        held = int(record["held_steps"])
        _require(
            held == (previous_held + 1 if in_tolerance else 0),
            "held counter violates the environment transition",
        )
        _require(
            int(record["previous_held_steps"]) == previous_held,
            "previous held counter is wrong",
        )
        interruption = previous_held > 0 and not in_tolerance
        _require(record["interruption"] is interruption, "interruption flag is stale")
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
        _require(
            record["hold_counter_transition"] == expected_transition,
            "hold transition label is stale",
        )
        _require(
            int(record["cumulative_interruptions"]) == interruptions,
            "cumulative interruption count is wrong",
        )
        if expected_transition == "continued":
            saw_continued = True
        if in_tolerance and first_reach is None:
            first_reach = expected_step
        max_held = max(max_held, held)

        branches = _reference_ik(target, model, qpos_after)
        for name in ("open", "folded"):
            observed = record["ik"][name]
            _array(observed["qpos_rad"], (2,), f"{name} IK solution")
            _close(observed["qpos_rad"], branches[name]["solution"], f"{name} IK solution")
            _require(
                bool(observed["feasible"]) is branches[name]["feasible"],
                f"{name} IK feasibility is wrong",
            )
            _close(observed["error_rad"], branches[name]["error"], f"{name} IK error")
        _require(
            record["ik"]["occupancy"] == branches["occupancy"],
            "IK branch occupancy is wrong",
        )

        dynamics = record["dynamics"]
        _close(dynamics["elbow_angle_rad"], qpos_after[1], "elbow angle")
        _close(dynamics["sin_elbow"], np.sin(qpos_after[1]), "sin elbow")
        _close(
            dynamics["joint_velocity_norm_rad_s"],
            np.linalg.norm(qvel_after),
            "joint velocity norm",
        )
        _close(
            dynamics["endpoint_velocity_norm_m_s"],
            np.linalg.norm(endpoint_velocity),
            "endpoint velocity norm",
        )
        planar_radius = float(np.hypot(endpoint[0], endpoint[1]))
        if planar_radius <= 1e-15:
            _require(
                dynamics["radial_endpoint_velocity_m_s"] is None
                and dynamics["tangential_endpoint_velocity_m_s"] is None,
                "radial quantities must be null at zero radius",
            )
        else:
            radial_unit = endpoint[:2] / planar_radius
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
        _require(int(contact["count"]) >= 0, "contact count is negative")
        _require(
            len(contact["events"]) == int(contact["count"]),
            "contact events do not match contact count",
        )
        for event in contact["events"]:
            _require(
                isinstance(event["geom1"], int) and isinstance(event["geom2"], int),
                "contact geometry IDs are not integers",
            )
            _finite(event["distance_m"], "contact distance")
        _require(
            bool(record["terminated"]) is (held >= HOLD_STEPS_REQUIRED),
            "termination does not implement the 100-step hold",
        )
        _require(
            bool(record["truncated"]) is (expected_step >= MAX_EPISODE_STEPS),
            "truncation does not implement the 500-step horizon",
        )
        if expected_step < len(trace):
            _require(
                not record["terminated"] and not record["truncated"],
                "trace continues after termination or truncation",
            )
        previous_qpos, previous_qvel, previous_held = qpos_after, qvel_after, held

    final = trace[-1]
    outcome = rollout["outcome"]
    _require(
        bool(final["terminated"]) or bool(final["truncated"]),
        "trace does not end at termination or truncation",
    )
    _require(int(outcome["steps"]) == len(trace), "outcome step count is wrong")
    _require(
        bool(outcome["success"]) is bool(outcome["terminated"]),
        "actual success and termination disagree",
    )
    _require(bool(outcome["terminated"]) is bool(final["terminated"]), "outcome termination is wrong")
    _require(bool(outcome["truncated"]) is bool(final["truncated"]), "outcome truncation is wrong")
    _require(
        outcome["first_reach_step"] == first_reach,
        "outcome first-reach field is stale",
    )
    _require(int(outcome["max_held_steps"]) == max_held, "outcome maximum hold is wrong")
    _require(
        int(outcome["hold_interruptions"]) == interruptions,
        "outcome interruption count is wrong",
    )
    _require(
        int(rollout["contact_summary"]["samples"]) == len(trace),
        "contact summary sample count is wrong",
    )
    counts = [int(record["contact"]["count"]) for record in trace]
    _require(
        int(rollout["contact_summary"]["maximum_contact_count"]) == max(counts),
        "contact summary maximum is wrong",
    )
    _require(
        int(rollout["contact_summary"]["nonzero_contact_samples"])
        == sum(count > 0 for count in counts),
        "contact summary nonzero count is wrong",
    )
    return {
        "seed": int(rollout["seed"]),
        "first_reach_step": first_reach,
        "interruptions": interruptions,
        "max_held_steps": max_held,
        "saw_continued": saw_continued,
        "steps": len(trace),
    }


def _trace_signature(rollout: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        (
            tuple(record["policy_action"]),
            tuple(record["applied_clipped_control"]),
            tuple(record["qpos_after_rad"]),
            tuple(record["qvel_after_rad_s"]),
        )
        for record in rollout["trace"]
    )


def verify_artifact(artifact_path: Path) -> dict[str, Any]:
    path = artifact_path if artifact_path.is_absolute() else REPOSITORY_ROOT / artifact_path
    with path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    _require(artifact["schema_version"] == 1, "unsupported artifact schema")
    _require(
        artifact["measurement"]
        == "paired_time_resolved_rollout_mechanism_discrimination",
        "wrong measurement",
    )
    _require(
        artifact["requested_probe_seeds"] == EXPECTED_SEEDS,
        "probe seeds are not the exact I10 seed list",
    )
    semantics = artifact["evaluation_semantics"]
    _require(
        semantics["frame_skip"] == 10
        and semantics["simulator_substeps_per_action"] == 10
        and semantics["hold_steps_required"] == HOLD_STEPS_REQUIRED
        and semantics["max_control_steps"] == MAX_EPISODE_STEPS,
        "evaluation timing or hold semantics are wrong",
    )
    _require(
        bool(semantics["reset_each_episode_with_seed"])
        and bool(semantics["runtime_reset_each_episode"])
        and bool(semantics["candidate_environments_are_independent"])
        and bool(semantics["outcomes_are_actual_environment_outcomes"]),
        "reset, independence, or actual-outcome evidence is missing",
    )
    measurement_semantics = artifact["measurement_semantics"]
    required_live_fields = {
        "endpoint_position_m",
        "endpoint_velocity_m_s",
        "distance_m",
        "in_tolerance",
        "previous_held_steps",
        "held_steps",
        "hold_counter_transition",
        "interruption",
    }
    _require(
        required_live_fields.issubset(set(measurement_semantics["live_environment_fields"])),
        "live environment field metadata is incomplete",
    )
    _require(
        "live MuJoCo data" in measurement_semantics["live_environment_source"]
        and "live environment" in measurement_semantics["live_environment_source"],
        "live environment source metadata is missing",
    )
    _require(
        "does not replace" in measurement_semantics["kinematic_reference"]["role"],
        "kinematic reference is not separated from live fields",
    )
    reset_evidence = artifact["reset_evidence"]
    _require(
        bool(reset_evidence["each_candidate_and_seed_reset_independently"])
        and bool(reset_evidence["runtime_reset_before_each_rollout"])
        and bool(reset_evidence["trace_contains_before_and_after_each_update"]),
        "repeated reset evidence is missing",
    )

    candidates = artifact["candidates"]
    _require(isinstance(candidates, list) and len(candidates) == 2, "two candidate records are required")
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    _require(set(by_id) == {"t7", "t4"}, "candidate IDs are not exactly t7 and t4")
    model_fingerprints = {candidate["model"]["sha256"] for candidate in candidates}
    _require(len(model_fingerprints) == 2, "candidate model fingerprints are not distinct")
    for candidate in candidates:
        _require(
            isinstance(candidate["runtime"]["sha256"], str)
            and len(candidate["runtime"]["sha256"]) == 64,
            "candidate runtime fingerprint is missing",
        )

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    _require(model.nq == 2 and model.nv == 2 and model.nu == 2, "official XML dimensions are unexpected")
    checked: dict[str, list[dict[str, Any]]] = {}
    rollouts_by_seed: dict[str, dict[int, dict[str, Any]]] = {}
    for candidate_id in ("t7", "t4"):
        candidate = by_id[candidate_id]
        rollouts = candidate["rollouts"]
        _require(
            [int(rollout["seed"]) for rollout in rollouts] == EXPECTED_SEEDS,
            f"{candidate_id} rollouts do not preserve the exact seed order",
        )
        candidate_checked = []
        rollouts_by_seed[candidate_id] = {}
        for rollout in rollouts:
            seed = int(rollout["seed"])
            rollouts_by_seed[candidate_id][seed] = rollout
            candidate_checked.append(_check_rollout(rollout, model, data))
        summary = candidate["outcome_summary"]
        successes = sum(bool(rollout["outcome"]["success"]) for rollout in rollouts)
        _require(int(summary["episodes"]) == len(rollouts), f"{candidate_id} episode summary is wrong")
        _require(int(summary["successes"]) == successes, f"{candidate_id} success summary is wrong")
        _require(int(summary["failures"]) == len(rollouts) - successes, f"{candidate_id} failure summary is wrong")
        checked[candidate_id] = candidate_checked

    pairing = artifact["target_pairing"]
    _require(bool(pairing["exact_match_all_seeds"]), "target pairing evidence is false")
    _require([int(item["seed"]) for item in pairing["by_seed"]] == EXPECTED_SEEDS, "target pairing seed list is wrong")
    for seed in EXPECTED_SEEDS:
        t7_target = rollouts_by_seed["t7"][seed]["target"]["position_m"]
        t4_target = rollouts_by_seed["t4"][seed]["target"]["position_m"]
        _require(t7_target == t4_target, f"target geometry differs at seed {seed}")
        pair = next(item for item in pairing["by_seed"] if int(item["seed"]) == seed)
        _require(bool(pair["exact_match"]), f"target pairing flag is false at seed {seed}")
        _require(pair["t7_target_position_m"] == t7_target, f"T7 pairing evidence is stale at seed {seed}")
        _require(pair["t4_target_position_m"] == t4_target, f"T4 pairing evidence is stale at seed {seed}")

    differences = []
    for seed in EXPECTED_SEEDS:
        t7_signature = _trace_signature(rollouts_by_seed["t7"][seed])
        t4_signature = _trace_signature(rollouts_by_seed["t4"][seed])
        if t7_signature != t4_signature:
            differences.append(seed)
    _require(differences, "T7 and T4 traces appear silently substituted")

    t7_checked = checked["t7"]
    _require(
        any(item["first_reach_step"] is None for item in t7_checked),
        "T7 has no no-first-reach probe",
    )
    _require(
        any(
            item["first_reach_step"] is not None and item["interruptions"] > 0
            for item in t7_checked
        ),
        "T7 has no reach-then-interrupt probe",
    )
    _require(
        any(item["saw_continued"] for items in checked.values() for item in items),
        "traces do not exercise repeated in-tolerance updates",
    )
    _require(
        any(item["interruptions"] > 0 for item in t7_checked),
        "traces do not exercise a hold interruption",
    )
    return {
        "checked_candidates": ["t7", "t4"],
        "checked_seeds": EXPECTED_SEEDS,
        "checked_rollouts": 2 * len(EXPECTED_SEEDS),
        "checked_steps": sum(
            item["steps"] for items in checked.values() for item in items
        ),
        "target_pairing_checked": True,
        "distinct_model_fingerprints": True,
        "runtime_fingerprints_recorded": True,
        "trace_difference_seeds": differences,
        "t7_no_first_reach_seeds": sorted(
            item["seed"] for item in t7_checked if item["first_reach_step"] is None
        ),
        "t7_reach_then_interrupt_seeds": sorted(
            item["seed"]
            for item in t7_checked
            if item["first_reach_step"] is not None and item["interruptions"] > 0
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Verify a paired time-resolved T7/T4 rollout artifact."
    )
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
                "exact I10 probe seeds and both independent candidate records",
                "candidate/model/runtime fingerprints and non-substituted traces",
                "per-candidate reset evidence and repeated qpos/qvel transitions",
                "official MuJoCo forward kinematics and translational Jacobian-times-qvel endpoint velocity",
                "live endpoint, distance, tolerance, hold, interruption, and termination semantics",
                "clipped controls, actuator/contact records, bounded IK, and dynamics quantities",
                "paired target geometry and T7 no-first-reach plus reach-then-interrupt behavior",
            ],
            "unchecked_scope": [
                "scientific validity of the proposed mechanism interpretation",
                "policy provenance beyond the recorded fingerprints and loader metadata",
                "causal attribution between plant, timing, saturation, and policy/runtime mechanisms",
            ],
        }
        exit_code = 0
    except (
        VerificationError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
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
