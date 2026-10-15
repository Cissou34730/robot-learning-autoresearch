"""Candidate-independent measurements of the loaded two-joint MuJoCo model.

This is a diagnostic instrument, not an alternative environment.  It loads
the same XML path as the official scenario and reports finite-grid geometry,
compiled model quantities, and short deterministic control responses.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    MAX_REACH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import FRAME_SKIP, TARGET_RADIUS_RANGE


IK_RADIUS_COUNT = 15
IK_ANGLE_COUNT = 25
ROLLOUT_SUBSTEPS = FRAME_SKIP
ROLLOUT_TARGET = (0.15, 0.0, 0.02)
REPRESENTATIVE_CONFIGURATIONS: tuple[tuple[str, tuple[float, float]], ...] = (
    ("straight_outer", (0.0, 0.0)),
    ("moderate_folded", (0.0, math.pi / 2.0)),
    ("inward_folded", (0.0, math.radians(150.0))),
)
def _float_list(values: Any) -> list[float]:
    """Convert a MuJoCo or NumPy numeric array to JSON-compatible floats."""

    return [float(value) for value in np.asarray(values, dtype=np.float64).reshape(-1)]


def _float_matrix(values: Any) -> list[list[float]]:
    array = np.asarray(values, dtype=np.float64)
    return [[float(value) for value in row] for row in array]


def _named_objects(
    model: mujoco.MjModel, object_type: mujoco.mjtObj, count: int
) -> list[str]:
    names: list[str] = []
    for object_id in range(count):
        name = mujoco.mj_id2name(model, object_type, object_id)
        names.append(str(name) if name is not None else f"unnamed_{object_id}")
    return names


def _require_two_joint_model(model: mujoco.MjModel) -> None:
    if model.nq != 2 or model.nv != 2 or model.nu != 2 or model.njnt != 2:
        raise RuntimeError(
            "loaded XML is not the expected two-joint model: "
            f"nq={model.nq}, nv={model.nv}, nu={model.nu}, njnt={model.njnt}"
        )


def _joint_ranges(model: mujoco.MjModel) -> tuple[float, float, float, float]:
    ranges = np.asarray(model.jnt_range, dtype=np.float64)
    if ranges.shape != (2, 2):
        raise RuntimeError(f"unexpected joint-range shape: {ranges.shape}")
    return float(ranges[0, 0]), float(ranges[0, 1]), float(
        ranges[1, 0]
    ), float(ranges[1, 1])


def _best_equivalent_angle(
    angle: float, lower: float, upper: float
) -> tuple[float, float]:
    """Choose the periodic representation with the greatest limit margin."""

    period = 2.0 * math.pi
    midpoint = (lower + upper) / 2.0
    nearest_period = (midpoint - angle) / period
    lower_period = math.floor(nearest_period)
    candidates = (lower_period, lower_period + 1)

    def candidate_margin(period_count: int) -> float:
        candidate = angle + period_count * period
        return min(candidate - lower, upper - candidate)

    best_period = max(
        candidates,
        key=lambda period_count: (
            candidate_margin(period_count),
            -abs(period_count),
        ),
    )
    best_angle = angle + best_period * period
    return best_angle, candidate_margin(best_period)


def _ik_reachability(model: mujoco.MjModel) -> dict[str, Any]:
    """Evaluate both planar IK branches on a reported finite grid."""

    lower_shoulder, upper_shoulder, lower_elbow, upper_elbow = _joint_ranges(model)
    radii = [
        TARGET_RADIUS_RANGE[0]
        + index
        * (TARGET_RADIUS_RANGE[1] - TARGET_RADIUS_RANGE[0])
        / (IK_RADIUS_COUNT - 1)
        for index in range(IK_RADIUS_COUNT)
    ]
    angles = [
        -math.pi + index * (2.0 * math.pi) / (IK_ANGLE_COUNT - 1)
        for index in range(IK_ANGLE_COUNT)
    ]
    points: list[dict[str, Any]] = []
    feasible_count = 0
    infeasible_count = 0
    worst_feasible: dict[str, Any] | None = None
    minimum_feasible_margin: float | None = None

    for radius in radii:
        cosine_elbow = (
            radius * radius
            - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH
            - FOREARM_LENGTH * FOREARM_LENGTH
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        if not -1.0 <= cosine_elbow <= 1.0:
            raise RuntimeError(
                f"official radius grid is outside algebraic reach at radius {radius}"
            )
        elbow_magnitude = math.acos(max(-1.0, min(1.0, cosine_elbow)))
        for target_angle in angles:
            x = radius * math.cos(target_angle)
            y = radius * math.sin(target_angle)
            for branch_name, elbow_angle in (
                ("elbow_up", elbow_magnitude),
                ("elbow_down", -elbow_magnitude),
            ):
                shoulder_angle = math.atan2(y, x) - math.atan2(
                    FOREARM_LENGTH * math.sin(elbow_angle),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow_angle),
                )
                represented_shoulder, shoulder_margin = _best_equivalent_angle(
                    shoulder_angle, lower_shoulder, upper_shoulder
                )
                represented_elbow, elbow_margin = _best_equivalent_angle(
                    elbow_angle, lower_elbow, upper_elbow
                )
                joint_angles = (represented_shoulder, represented_elbow)
                margin = math.degrees(min(shoulder_margin, elbow_margin))
                feasible = (
                    shoulder_margin >= 0.0 and elbow_margin >= 0.0
                )
                point = {
                    "radius_m": float(radius),
                    "target_angle_rad": float(target_angle),
                    "target_angle_deg": float(math.degrees(target_angle)),
                    "branch": branch_name,
                    "raw_joint_angles_rad": [
                        float(shoulder_angle),
                        float(elbow_angle),
                    ],
                    "joint_angles_rad": [float(value) for value in joint_angles],
                    "joint_angles_deg": [
                        float(math.degrees(value)) for value in joint_angles
                    ],
                    "within_declared_joint_ranges": feasible,
                    "minimum_joint_limit_margin_deg": float(margin),
                }
                points.append(point)
                if feasible:
                    feasible_count += 1
                    if (
                        minimum_feasible_margin is None
                        or margin < minimum_feasible_margin
                    ):
                        minimum_feasible_margin = float(margin)
                        worst_feasible = {
                            "radius_m": float(radius),
                            "target_angle_rad": float(target_angle),
                            "target_angle_deg": float(math.degrees(target_angle)),
                            "branch": branch_name,
                            "joint_angles_rad": [
                                float(value) for value in joint_angles
                            ],
                            "minimum_joint_limit_margin_deg": float(margin),
                        }
                else:
                    infeasible_count += 1

    return {
        "grid_specification": {
            "radius_count": IK_RADIUS_COUNT,
            "angle_count": IK_ANGLE_COUNT,
            "branches_per_grid_point": 2,
            "radius_range_m": [
                float(TARGET_RADIUS_RANGE[0]),
                float(TARGET_RADIUS_RANGE[1]),
            ],
            "target_angle_range_rad": [-math.pi, math.pi],
            "target_angle_range_deg": [-180.0, 180.0],
            "radius_endpoints_included": True,
            "target_angle_endpoints_included": True,
            "branch_definition": {
                "elbow_up": "q2 = +acos(cos(q2))",
                "elbow_down": "q2 = -acos(cos(q2))",
            },
            "finite_grid_only": True,
            "continuous_reachability_not_claimed": True,
        },
        "joint_ranges_used_rad": _float_matrix(model.jnt_range),
        "joint_ranges_used_deg": _float_matrix(
            np.degrees(np.asarray(model.jnt_range, dtype=np.float64))
        ),
        "points": points,
        "feasible_count": feasible_count,
        "infeasible_count": infeasible_count,
        "minimum_feasible_margin_deg": minimum_feasible_margin,
        "worst_feasible_point": worst_feasible,
    }


def _reset_configuration(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: Sequence[float],
    control: Sequence[float],
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = np.asarray(qpos, dtype=np.float64)
    data.qvel[:] = 0.0
    data.ctrl[:] = np.asarray(control, dtype=np.float64)
    if data.mocap_pos.shape[0] < 1:
        raise RuntimeError("loaded XML has no mocap target for the diagnostic state")
    data.mocap_pos[0] = np.asarray(ROLLOUT_TARGET, dtype=np.float64)
    mujoco.mj_forward(model, data)


def _endpoint_snapshot(
    data: mujoco.MjData, previous_position: np.ndarray | None, timestep: float
) -> dict[str, Any]:
    position = np.asarray(data.site("end_effector").xpos, dtype=np.float64).copy()
    if previous_position is None:
        velocity = np.zeros(3, dtype=np.float64)
    else:
        velocity = (position - previous_position) / timestep
    target = np.asarray(ROLLOUT_TARGET, dtype=np.float64)
    return {
        "position_m": _float_list(position),
        "planar_radius_m": float(math.hypot(position[0], position[1])),
        "distance_to_target_m": float(np.linalg.norm(position - target)),
        "velocity_m_per_s": _float_list(velocity),
        "speed_m_per_s": float(np.linalg.norm(velocity)),
        "velocity_method": "position difference over one physics timestep",
    }


def _force_snapshot(data: mujoco.MjData) -> dict[str, list[float]]:
    return {
        "actuator_force_actuation_space": _float_list(data.actuator_force),
        "qfrc_actuator_joint_space": _float_list(data.qfrc_actuator),
        "qfrc_bias_joint_space": _float_list(data.qfrc_bias),
        "qfrc_passive_joint_space": _float_list(data.qfrc_passive),
        "qfrc_applied_joint_space": _float_list(data.qfrc_applied),
    }


def _state_snapshot(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    previous_position: np.ndarray | None,
) -> dict[str, Any]:
    return {
        "qpos_rad": _float_list(data.qpos),
        "qvel_rad_per_s": _float_list(data.qvel),
        "qacc_rad_per_s2": _float_list(data.qacc),
        "ctrl": _float_list(data.ctrl),
        "forces": _force_snapshot(data),
        "endpoint": _endpoint_snapshot(
            data, previous_position, float(model.opt.timestep)
        ),
    }


def _action_response(model: mujoco.MjModel) -> dict[str, Any]:
    data = mujoco.MjData(model)
    cases: list[dict[str, Any]] = []
    control_ranges = np.asarray(model.actuator_ctrlrange, dtype=np.float64)
    if control_ranges.shape != (2, 2):
        raise RuntimeError(
            f"unexpected actuator control-range shape: {control_ranges.shape}"
        )
    action_cases: tuple[tuple[str, tuple[float, float]], ...] = (
        ("zero", (0.0, 0.0)),
        (
            "saturated_positive",
            (float(control_ranges[0, 1]), float(control_ranges[1, 1])),
        ),
        (
            "saturated_negative",
            (float(control_ranges[0, 0]), float(control_ranges[1, 0])),
        ),
    )

    for configuration_name, qpos in REPRESENTATIVE_CONFIGURATIONS:
        for action_name, control in action_cases:
            _reset_configuration(model, data, qpos, control)
            initial_position = np.asarray(
                data.site("end_effector").xpos, dtype=np.float64
            ).copy()
            before = _state_snapshot(model, data, None)
            substeps: list[dict[str, Any]] = []
            previous_position = initial_position
            last_interval_start = initial_position
            for substep in range(1, ROLLOUT_SUBSTEPS + 1):
                last_interval_start = previous_position.copy()
                mujoco.mj_step(model, data)
                snapshot = _state_snapshot(model, data, previous_position)
                snapshot["substep"] = substep
                substeps.append(snapshot)
                previous_position = np.asarray(
                    data.site("end_effector").xpos, dtype=np.float64
                ).copy()
            after = _state_snapshot(model, data, last_interval_start)
            cases.append(
                {
                    "configuration": configuration_name,
                    "qpos_initial_rad": [float(value) for value in qpos],
                    "action_case": action_name,
                    "constant_control": [float(value) for value in control],
                    "state_before": before,
                    "substeps": substeps,
                    "state_after": after,
                }
            )

    return {
        "rollout_target_position_m": [float(value) for value in ROLLOUT_TARGET],
        "configuration_definitions": [
            {
                "name": name,
                "qpos_rad": [float(value) for value in qpos],
                "description": {
                    "straight_outer": "both links aligned",
                    "moderate_folded": "elbow at 90 degrees",
                    "inward_folded": "elbow at 150 degrees",
                }[name],
            }
            for name, qpos in REPRESENTATIVE_CONFIGURATIONS
        ],
        "action_definitions": [
            {
                "name": name,
                "constant_control": [float(value) for value in control],
                "control_is_at_declared_boundary": name
                in {"saturated_positive", "saturated_negative"},
            }
            for name, control in action_cases
        ],
        "physics_timestep_s": float(model.opt.timestep),
        "official_control_timestep_s": float(model.opt.timestep * FRAME_SKIP),
        "official_frame_skip_substeps": FRAME_SKIP,
        "probe_substeps_per_case": ROLLOUT_SUBSTEPS,
        "cases": cases,
    }


def _compiled_model(model: mujoco.MjModel) -> dict[str, Any]:
    data = mujoco.MjData(model)
    mass_matrices: list[dict[str, Any]] = []
    for configuration_name, qpos in REPRESENTATIVE_CONFIGURATIONS:
        _reset_configuration(model, data, qpos, (0.0, 0.0))
        mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
        mujoco.mj_fullM(model, data, mass_matrix)
        mass_matrices.append(
            {
                "configuration": configuration_name,
                "qpos_rad": [float(value) for value in qpos],
                "mass_matrix_kg_m2": _float_matrix(mass_matrix),
            }
        )

    return {
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "njnt": int(model.njnt),
            "nbody": int(model.nbody),
            "ngeom": int(model.ngeom),
            "nsite": int(model.nsite),
            "nmocap": int(model.nmocap),
        },
        "body_names": _named_objects(model, mujoco.mjtObj.mjOBJ_BODY, model.nbody),
        "body_mass_kg": _float_list(model.body_mass),
        "body_inertia_diagonal_kg_m2": _float_matrix(model.body_inertia),
        "joint_names": _named_objects(model, mujoco.mjtObj.mjOBJ_JOINT, model.njnt),
        "joint_ranges_rad": _float_matrix(model.jnt_range),
        "joint_ranges_deg": _float_matrix(
            np.degrees(np.asarray(model.jnt_range, dtype=np.float64))
        ),
        "actuator_names": _named_objects(
            model, mujoco.mjtObj.mjOBJ_ACTUATOR, model.nu
        ),
        "actuator_gear": _float_matrix(model.actuator_gear),
        "actuator_control_ranges": _float_matrix(model.actuator_ctrlrange),
        "actuator_control_range_units": "dimensionless control input",
        "actuator_gear_units": "loaded MuJoCo gear mapping",
        "mass_matrix_units": "kg*m^2 in generalized joint coordinates",
        "representative_configurations": mass_matrices,
    }


def _interpretation_inputs(
    ik_reachability: dict[str, Any], action_response: dict[str, Any]
) -> dict[str, Any]:
    max_speed_by_case: dict[str, float] = {}
    any_boundary_control = False
    for case in action_response["cases"]:
        case_key = f"{case['configuration']}:{case['action_case']}"
        max_speed = max(
            float(sample["endpoint"]["speed_m_per_s"])
            for sample in case["substeps"]
        )
        max_speed_by_case[case_key] = max_speed
        any_boundary_control = any_boundary_control or case["action_case"] in {
            "saturated_positive",
            "saturated_negative",
        }

    return {
        "measurement_label": "calculated measurements and flags; not conclusions",
        "finite_grid_contains_infeasible_branch_points": bool(
            ik_reachability["infeasible_count"] > 0
        ),
        "finite_grid_feasible_count": int(ik_reachability["feasible_count"]),
        "finite_grid_infeasible_count": int(ik_reachability["infeasible_count"]),
        "sampled_response_includes_declared_control_boundaries": bool(
            any_boundary_control
        ),
        "max_endpoint_speed_m_per_s_by_case": max_speed_by_case,
    }


def build_artifact() -> dict[str, Any]:
    """Load the official XML and construct the complete diagnostic artifact."""

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    _require_two_joint_model(model)
    ik_reachability = _ik_reachability(model)
    compiled_model = _compiled_model(model)
    action_response = _action_response(model)
    return {
        "schema_version": "initial_physics_probe.v1",
        "measurement_type": "candidate-independent loaded-model diagnostic",
        "model": {
            "identity": "two_joint_arm",
            "xml_path": str(TWO_JOINT_ARM_XML_PATH),
            "timestep_s": float(model.opt.timestep),
            "gravity_m_per_s2": _float_list(model.opt.gravity),
        },
        "official_constants": {
            "target_radius_range_m": [
                float(TARGET_RADIUS_RANGE[0]),
                float(TARGET_RADIUS_RANGE[1]),
            ],
            "upper_arm_length_m": float(UPPER_ARM_LENGTH),
            "forearm_length_m": float(FOREARM_LENGTH),
            "maximum_reach_m": float(MAX_REACH),
            "joint_ranges_deg": _float_matrix(
                np.degrees(np.asarray(model.jnt_range, dtype=np.float64))
            ),
            "control_range": _float_matrix(model.actuator_ctrlrange),
            "frame_skip": FRAME_SKIP,
        },
        "ik_reachability": ik_reachability,
        "compiled_model": compiled_model,
        "action_response": action_response,
        "interpretation_inputs": _interpretation_inputs(
            ik_reachability, action_response
        ),
    }


def _write_artifact(output_path: Path, artifact: dict[str, Any]) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact, stream, indent=2, sort_keys=False, allow_nan=False)
            stream.write("\n")
    except OSError as exc:
        raise RuntimeError(
            f"unable to write diagnostic artifact at {output_path}: {exc}"
        ) from exc


def _parse_output_path(argv: Sequence[str]) -> Path:
    if len(argv) != 2:
        raise ValueError(
            "invalid invocation: expected exactly one argument, <output_json>"
        )
    if argv[1] == "":
        raise ValueError("invalid invocation: output path is empty")
    return Path(argv[1])


def main(argv: Sequence[str] | None = None) -> None:
    arguments = sys.argv if argv is None else argv
    try:
        output_path = _parse_output_path(arguments)
    except ValueError as exc:
        raise SystemExit(f"initial_physics_probe failed: {exc}") from exc

    artifact = build_artifact()
    _write_artifact(output_path, artifact)


if __name__ == "__main__":
    main()
