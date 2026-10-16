"""Deterministic, candidate-independent dynamics measurement for the arm.

This module deliberately uses the human-authored MuJoCo XML and only records
diagnostic physics quantities.  It does not construct an environment or call
the official task evaluator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from contracts.task_spec import FRAME_SKIP


SCHEMA_VERSION = "1.0"
DEFAULT_OUTER_BLOCKS = 20
EXPECTED_PHYSICS_TIMESTEP = 0.002
EXPECTED_FRAME_SKIP = 10
MODEL_UNIT_CONVENTION = (
    "Declared SI-style interpretation for this artifact: length in m, mass in "
    "kg, time in s, and hinge angles in rad. MuJoCo does not enforce units; "
    "the XML contains no unit declaration. The actuator control-to-torque "
    "mapping is unresolved because the task contract does not define it."
)
ACTION = np.array([0.5, -0.5], dtype=np.float64)
CONFIGURATIONS: tuple[tuple[str, tuple[float, float]], ...] = (
    ("reset", (0.0, 0.0)),
    ("open_bent", (0.0, float(np.pi / 2.0))),
    ("folded_bent", (0.0, float(-np.pi / 2.0))),
)


def _finite_array(value: Any, label: str) -> np.ndarray:
    """Return a copied numeric array, rejecting non-finite values explicitly."""

    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{label} contains a non-finite numeric value")
    return array.copy()


def _finite_float(value: Any, label: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{label} is non-finite")
    return number


def _json_array(value: Any, label: str) -> list[Any]:
    """Convert a finite NumPy value to JSON-native lists."""

    array = _finite_array(value, label)
    return array.tolist()


def _object_name(
    model: mujoco.MjModel, object_type: Any, object_id: int, label: str
) -> str:
    name = mujoco.mj_id2name(model, object_type, object_id)
    if name is None or not str(name):
        raise ValueError(f"{label} has no compiled MuJoCo name")
    return str(name)


def _dense_mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    matrix = np.empty((int(model.nv), int(model.nv)), dtype=np.float64)
    mujoco.mj_fullM(model, data, matrix)
    return _finite_array(matrix, "mass matrix")


def _reset_data(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: Iterable[float]
) -> np.ndarray:
    requested_qpos = _finite_array(tuple(qpos), "configuration qpos")
    if requested_qpos.shape != (int(model.nq),):
        raise ValueError(
            f"configuration qpos has shape {requested_qpos.shape}, "
            f"expected {(int(model.nq),)}"
        )

    mujoco.mj_resetData(model, data)
    data.qpos[:] = requested_qpos
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    _finite_array(data.qpos, "reset qpos")
    _finite_array(data.qvel, "reset qvel")
    return requested_qpos


def _model_facts(model: mujoco.MjModel) -> dict[str, Any]:
    body_names = [
        _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id, f"body {body_id}")
        for body_id in range(int(model.nbody))
    ]
    joint_names = [
        _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id, f"joint {joint_id}")
        for joint_id in range(int(model.njnt))
    ]
    actuator_names = [
        _object_name(
            model,
            mujoco.mjtObj.mjOBJ_ACTUATOR,
            actuator_id,
            f"actuator {actuator_id}",
        )
        for actuator_id in range(int(model.nu))
    ]

    joints: list[dict[str, Any]] = []
    dofs: list[dict[str, Any]] = []
    for joint_id, joint_name in enumerate(joint_names):
        dof_id = int(model.jnt_dofadr[joint_id])
        if dof_id < 0 or dof_id >= int(model.nv):
            raise ValueError(f"joint {joint_name} has invalid dof address {dof_id}")
        damping = _finite_float(
            model.dof_damping[dof_id], f"damping for joint {joint_name}"
        )
        armature = _finite_float(
            model.dof_armature[dof_id], f"armature for joint {joint_name}"
        )
        joints.append(
            {
                "name": joint_name,
                "qpos_address": int(model.jnt_qposadr[joint_id]),
                "dof_address": dof_id,
                "damping": damping,
                "armature": armature,
                "damping_source": "compiled model.dof_damping",
                "armature_source": "compiled model.dof_armature",
            }
        )
        dofs.append(
            {
                "address": dof_id,
                "joint_name": joint_name,
                "damping": damping,
                "armature": armature,
            }
        )

    actuators: list[dict[str, Any]] = []
    for actuator_id, actuator_name in enumerate(actuator_names):
        transmission_ids = np.asarray(
            model.actuator_trnid[actuator_id], dtype=np.int64
        )
        if transmission_ids.shape != (2,):
            raise ValueError(
                f"transmission ids for actuator {actuator_name} have "
                f"unexpected shape {transmission_ids.shape}"
            )
        transmission_type = int(model.actuator_trntype[actuator_id])
        primary_target_name: str | None = None
        # The supplied XML uses joint transmissions.  Preserve the raw public
        # type and ids even if a future XML uses another transmission kind.
        if transmission_type == int(mujoco.mjtTrn.mjTRN_JOINT):
            target_id = int(transmission_ids[0])
            if 0 <= target_id < int(model.njnt):
                primary_target_name = joint_names[target_id]
        actuators.append(
            {
                "name": actuator_name,
                "gear": _json_array(
                    model.actuator_gear[actuator_id],
                    f"gear for actuator {actuator_name}",
                ),
                "control_range": _json_array(
                    model.actuator_ctrlrange[actuator_id],
                    f"control range for actuator {actuator_name}",
                ),
                "transmission_type_code": transmission_type,
                "transmission_type_enum": (
                    "mjTRN_JOINT"
                    if transmission_type == int(mujoco.mjtTrn.mjTRN_JOINT)
                    else "unmapped_public_mjTRN_value"
                ),
                "transmission_ids": transmission_ids.tolist(),
                "primary_joint_name": primary_target_name,
            }
        )

    return {
        "dimensions": {
            "nbody": int(model.nbody),
            "njnt": int(model.njnt),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
        },
        "units": {
            "convention": MODEL_UNIT_CONVENTION,
            "timestep_seconds": "s",
            "gravity": "m/s^2",
            "body_mass": "kg",
            "body_inertia_diagonal": "kg*m^2",
            "joint_damping": "N*m*s/rad",
            "dof_damping": "N*m*s/rad",
            "joint_armature": "kg*m^2",
            "dof_armature": "kg*m^2",
            "actuator_gear": (
                "transmission coefficient; physical units unresolved because "
                "the control-to-torque convention is unspecified"
            ),
            "actuator_control_range": (
                "bounded actuator command; physical units unresolved because "
                "the control-to-torque convention is unspecified"
            ),
            "mass_matrix": "kg*m^2/rad^2 for the revolute generalized coordinates",
        },
        "options": {
            "timestep_seconds": _finite_float(
                model.opt.timestep, "compiled timestep"
            ),
            "gravity": _json_array(model.opt.gravity, "compiled gravity"),
        },
        "bodies": [
            {
                "id": body_id,
                "name": body_names[body_id],
                "mass": _finite_float(model.body_mass[body_id], f"mass for body {body_id}"),
                "inertia_diagonal": _json_array(
                    model.body_inertia[body_id], f"inertia for body {body_id}"
                ),
            }
            for body_id in range(int(model.nbody))
        ],
        "joints": joints,
        "dofs": dofs,
        "actuators": actuators,
    }


def _site_quantities(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    position = _finite_array(data.site_xpos[site_id], "end-effector position")
    jacobian = np.zeros((3, int(model.nv)), dtype=np.float64)
    mujoco.mj_jacSite(model, data, jacobian, None, site_id)
    jacobian = _finite_array(jacobian, "end-effector Jacobian")
    velocity = _finite_array(jacobian @ data.qvel, "end-effector velocity")
    if jacobian.shape[1] < 2:
        raise ValueError("end-effector Jacobian does not have two planar columns")
    determinant = _finite_float(
        np.linalg.det(jacobian[:2, :2]), "planar Jacobian determinant"
    )
    return position, velocity, determinant


def _state_record(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    target: np.ndarray,
    phase: str,
    outer_step: int,
    substep: int,
    held_action: np.ndarray,
) -> dict[str, Any]:
    qpos = _finite_array(data.qpos, "trace qpos")
    qvel = _finite_array(data.qvel, "trace qvel")
    qacc = _finite_array(data.qacc, "trace qacc")
    position, velocity, jacobian_determinant = _site_quantities(model, data, site_id)
    distance = _finite_float(
        np.linalg.norm(position - target), "diagnostic target distance"
    )
    mass_matrix = _dense_mass_matrix(model, data)
    kinetic_energy = _finite_float(
        0.5 * qvel @ mass_matrix @ qvel, "kinetic energy"
    )
    return {
        "phase": phase,
        "outer_step": outer_step,
        "substep": substep,
        "held_action": _json_array(held_action, "held action"),
        "qpos": qpos.tolist(),
        "qvel": qvel.tolist(),
        "qacc": qacc.tolist(),
        "end_effector_position": position.tolist(),
        "end_effector_velocity": velocity.tolist(),
        "distance_to_diagnostic_target": distance,
        "planar_jacobian_determinant": jacobian_determinant,
        "kinetic_energy": kinetic_energy,
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot summarize an empty trace")

    def peak(field: str) -> float:
        return max(_finite_float(record[field], field) for record in records)

    def speed(record: dict[str, Any], field: str) -> float:
        return _finite_float(np.linalg.norm(record[field]), field)

    peak_joint_speed = max(speed(record, "qvel") for record in records)
    peak_end_effector_speed = max(
        speed(record, "end_effector_velocity") for record in records
    )
    reversal_records = [
        record for record in records if record["phase"] == "sign_reversal"
    ]
    if not reversal_records:
        raise ValueError("trace has no sign-reversal records")
    first_reversal = reversal_records[0]
    post_reversal_extrema = {
        "minimum_distance": min(
            _finite_float(record["distance_to_diagnostic_target"], "distance")
            for record in reversal_records
        ),
        "maximum_distance": max(
            _finite_float(record["distance_to_diagnostic_target"], "distance")
            for record in reversal_records
        ),
        "peak_joint_speed": max(speed(record, "qvel") for record in reversal_records),
        "peak_end_effector_speed": max(
            speed(record, "end_effector_velocity") for record in reversal_records
        ),
    }
    phase_summaries: dict[str, dict[str, float]] = {}
    for phase in ("constant_action", "sign_reversal"):
        phase_records = [record for record in records if record["phase"] == phase]
        if phase_records:
            phase_summaries[phase] = {
                "peak_joint_speed": max(speed(record, "qvel") for record in phase_records),
                "peak_end_effector_speed": max(
                    speed(record, "end_effector_velocity")
                    for record in phase_records
                ),
                "peak_distance": max(
                    _finite_float(
                        record["distance_to_diagnostic_target"], "distance"
                    )
                    for record in phase_records
                ),
            }

    final_record = records[-1]
    final_state = {
        "phase": final_record["phase"],
        "outer_step": final_record["outer_step"],
        "substep": final_record["substep"],
        "qpos": final_record["qpos"],
        "qvel": final_record["qvel"],
        "end_effector_position": final_record["end_effector_position"],
        "end_effector_velocity": final_record["end_effector_velocity"],
        "distance_to_diagnostic_target": final_record[
            "distance_to_diagnostic_target"
        ],
        "kinetic_energy": final_record["kinetic_energy"],
    }
    return {
        "peak_joint_speed": peak_joint_speed,
        "peak_end_effector_speed": peak_end_effector_speed,
        "peak_distance": peak("distance_to_diagnostic_target"),
        "first_reversal": {
            "outer_step": first_reversal["outer_step"],
            "substep": first_reversal["substep"],
            "qpos": first_reversal["qpos"],
            "qvel": first_reversal["qvel"],
            "distance_to_diagnostic_target": first_reversal[
                "distance_to_diagnostic_target"
            ],
        },
        "post_reversal_extrema": post_reversal_extrema,
        "by_phase": phase_summaries,
        "final_state": final_state,
    }


def measure_dynamics(*, outer_blocks: int = DEFAULT_OUTER_BLOCKS) -> dict[str, Any]:
    """Run the fixed diagnostic schedule and return one JSON-compatible object."""

    if isinstance(outer_blocks, bool) or not isinstance(outer_blocks, int):
        raise ValueError("outer_blocks must be an integer")
    if outer_blocks <= 0:
        raise ValueError("outer_blocks must be positive")

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    if (int(model.nq), int(model.nv), int(model.nu)) != (2, 2, 2):
        raise ValueError(
            "compiled arm dimensions changed; expected nq=2, nv=2, and nu=2"
        )
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    if site_id < 0:
        raise ValueError("compiled model has no end_effector site")

    timestep = _finite_float(model.opt.timestep, "compiled timestep")
    if not np.isclose(timestep, EXPECTED_PHYSICS_TIMESTEP, rtol=0.0, atol=1e-15):
        raise ValueError(
            f"compiled timestep is {timestep}, expected {EXPECTED_PHYSICS_TIMESTEP}"
        )
    if FRAME_SKIP != EXPECTED_FRAME_SKIP:
        raise ValueError(
            f"task frame skip is {FRAME_SKIP}, expected {EXPECTED_FRAME_SKIP}"
        )
    _reset_data(model, data, (0.0, 0.0))
    target_position, _, _ = _site_quantities(model, data, site_id)
    diagnostic_target = np.array(
        [0.15, 0.0, target_position[2]], dtype=np.float64
    )
    _finite_array(diagnostic_target, "diagnostic target")

    mass_matrices: list[dict[str, Any]] = []
    for name, qpos in CONFIGURATIONS:
        reset_qpos = _reset_data(model, data, qpos)
        mass_matrices.append(
            {
                "configuration": name,
                "qpos": reset_qpos.tolist(),
                "qvel": _json_array(data.qvel, f"{name} reset qvel"),
                "matrix_units": (
                    "kg*m^2/rad^2 under the declared SI-style convention"
                ),
                "matrix": _dense_mass_matrix(model, data).tolist(),
            }
        )

    control_ranges = _finite_array(model.actuator_ctrlrange, "actuator control ranges")
    if control_ranges.shape != (2, 2):
        raise ValueError(f"expected two actuator control ranges, got {control_ranges.shape}")
    if np.any(ACTION < control_ranges[:, 0]) or np.any(ACTION > control_ranges[:, 1]):
        raise ValueError("constant diagnostic action is outside compiled control ranges")
    reverse_action = -ACTION
    if np.any(reverse_action < control_ranges[:, 0]) or np.any(
        reverse_action > control_ranges[:, 1]
    ):
        raise ValueError("reversed diagnostic action is outside compiled control ranges")

    traces: list[dict[str, Any]] = []
    for configuration, qpos in CONFIGURATIONS:
        initial_qpos = _reset_data(model, data, qpos)
        records: list[dict[str, Any]] = []
        for phase, action in (
            ("constant_action", ACTION),
            ("sign_reversal", reverse_action),
        ):
            for outer_step in range(outer_blocks):
                data.ctrl[:] = action
                for substep in range(FRAME_SKIP):
                    mujoco.mj_step(model, data)
                    # mj_step has advanced qpos/qvel, while qacc and
                    # position-dependent quantities were computed for the
                    # integration state. Recompute forward dynamics so every
                    # field below describes the same post-step state.
                    mujoco.mj_forward(model, data)
                    records.append(
                        _state_record(
                            model,
                            data,
                            site_id,
                            diagnostic_target,
                            phase,
                            outer_step,
                            substep,
                            action,
                        )
                    )
        traces.append(
            {
                "configuration": configuration,
                "initial_qpos": initial_qpos.tolist(),
                "initial_qvel": [0.0, 0.0],
                "records": records,
                "summary": _summary(records),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "measurement": {
            "name": "two_joint_arm_dynamics",
            "deterministic": True,
            "model_source": "contracts/robots/two_joint_arm.xml via TWO_JOINT_ARM_XML_PATH",
            "official_task_evaluated": False,
            "official_evaluator_called": False,
            "diagnostic_only": True,
            "unit_convention": MODEL_UNIT_CONVENTION,
            "units": {
                "time": "s",
                "qpos": "rad",
                "qvel": "rad/s",
                "qacc": "rad/s^2",
                "position": "m",
                "velocity": "m/s",
                "distance": "m",
                "jacobian_determinant": "m^2 per rad^2",
                "kinetic_energy": "kg*m^2/s^2 (J) under the declared convention",
                "actuator_control": (
                    "physical units unresolved; bounded command only"
                ),
                "actuator_gear": (
                    "physical units unresolved; transmission coefficient only"
                ),
            },
        },
        "compiled_model": _model_facts(model),
        "schedule": {
            "physics_timestep_seconds": timestep,
            "outer_control_block_size": FRAME_SKIP,
            "outer_control_block_statement": (
                "each held_action is written to model.ctrl and held over "
                f"{FRAME_SKIP} consecutive mj_step calls"
            ),
            "outer_step_indexing": "zero-based within each phase",
            "substep_indexing": "zero-based within each outer control block",
            "outer_blocks_per_phase": outer_blocks,
            "phase_order": ["constant_action", "sign_reversal"],
            "constant_action": _json_array(ACTION, "constant action"),
            "sign_reversed_action": _json_array(reverse_action, "reversed action"),
            "action_units": (
                "bounded actuator command; physical units unresolved because "
                "the control-to-torque convention is unspecified"
            ),
            "diagnostic_target": diagnostic_target.tolist(),
            "diagnostic_target_description": (
                "[0.15, 0.0, end_effector_z] fixed from the reset geometry"
            ),
        },
        "mass_matrices": mass_matrices,
        "traces": traces,
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a deterministic MuJoCo two-joint-arm dynamics artifact."
    )
    parser.add_argument("output_json", type=Path, help="required output JSON path")
    parser.add_argument(
        "--outer-blocks",
        type=int,
        default=DEFAULT_OUTER_BLOCKS,
        help=f"positive outer blocks per action phase (default: {DEFAULT_OUTER_BLOCKS})",
    )
    args = parser.parse_args(argv)
    if args.outer_blocks <= 0:
        parser.error("--outer-blocks must be positive")
    if args.output_json.name in {"", ".", ".."}:
        parser.error("output JSON path must name a file")
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    output_path = args.output_json
    if output_path.exists() and output_path.is_dir():
        raise SystemExit(f"measure_dynamics: output path is a directory: {output_path}")
    if not output_path.parent.is_dir():
        raise SystemExit(
            f"measure_dynamics: output parent directory does not exist: "
            f"{output_path.parent}"
        )
    try:
        artifact = measure_dynamics(outer_blocks=args.outer_blocks)
        with output_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"measure_dynamics: {exc}") from exc


if __name__ == "__main__":
    main()
