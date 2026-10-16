"""Measure the compiled two-joint arm dynamics with deterministic controls.

This module is intentionally a physical response probe.  It does not load a
policy or evaluate the reach-and-hold task.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


TORQUE_CONTROLS = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
    (1.0, 1.0),
    (-1.0, -1.0),
)
ENVELOPE_CONTROLS = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
)
RESPONSE_SUBSTEPS = 100
ENVELOPE_SUBSTEPS = 200
RESPONSE_SAMPLES = frozenset((0, 10, 20, 50, 100))
ENVELOPE_SAMPLES = frozenset((0, 10, 20, 50, 100, 110, 120, 150, 200))


def _as_json_value(value: Any) -> Any:
    """Convert numpy values into ordinary JSON-compatible Python values."""

    if isinstance(value, np.ndarray):
        return [_as_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _as_json_value(value.item())
    if isinstance(value, dict):
        return {str(key): _as_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_json_value(item) for item in value]
    return value


def _object_name(
    model: mujoco.MjModel, object_type: Any, object_id: int
) -> str | None:
    name = mujoco.mj_id2name(model, object_type, int(object_id))
    return None if name is None else str(name)


def _required_object_id(
    model: mujoco.MjModel, object_type: Any, name: str
) -> int:
    object_id = int(mujoco.mj_name2id(model, object_type, name))
    if object_id < 0:
        raise RuntimeError(f"Required MuJoCo object is missing: {name}")
    return object_id


def _enum_identifier(
    enum_type: Any, value: Any, member_names: Iterable[str]
) -> dict[str, Any]:
    """Return an enum's numeric value and readable name when available."""

    numeric_value = int(value)
    identifier: dict[str, Any] = {"value": numeric_value}
    for member_name in member_names:
        member = getattr(enum_type, member_name, None)
        if member is not None and int(member) == numeric_value:
            identifier["name"] = member_name
            break
    return identifier


def _optional_force_quantities(data: mujoco.MjData) -> dict[str, Any]:
    """Collect public force arrays without assuming optional bindings."""

    quantities: dict[str, Any] = {}
    for field_name, output_name in (
        ("actuator_force", "actuator_force"),
        ("qfrc_actuator", "generalized_actuator_force"),
    ):
        field = getattr(data, field_name, None)
        if field is not None:
            quantities[output_name] = np.asarray(field, dtype=float).copy()
    return quantities


def _reset_zero_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    control: np.ndarray,
) -> np.ndarray:
    """Reset all simulation data, impose the exact zero joint state, and forward."""

    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = control
    mujoco.mj_forward(model, data)
    return np.asarray(data.site_xpos[site_id], dtype=float).copy()


def _snapshot(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    reset_site_position: np.ndarray,
    substep: int,
    control: np.ndarray,
    phase: str | None = None,
) -> dict[str, Any]:
    site_position = np.asarray(data.site_xpos[site_id], dtype=float).copy()
    qpos = np.asarray(data.qpos, dtype=float).copy()
    qvel = np.asarray(data.qvel, dtype=float).copy()
    distance = float(np.linalg.norm(site_position - reset_site_position))
    if not (
        np.all(np.isfinite(qpos))
        and np.all(np.isfinite(qvel))
        and np.all(np.isfinite(site_position))
        and np.isfinite(distance)
    ):
        raise FloatingPointError(
            f"Non-finite MuJoCo state encountered at substep {substep}"
        )

    snapshot: dict[str, Any] = {
        "substep": int(substep),
        "control": control.copy(),
        "qpos": qpos,
        "qvel": qvel,
        "end_effector_position": site_position,
        "distance_from_reset_end_effector": distance,
        "contact_count": int(data.ncon),
        "force_quantities": _optional_force_quantities(data),
    }
    if phase is not None:
        snapshot["phase"] = phase
    return snapshot


def _summary(
    snapshots: list[dict[str, Any]],
    maximum_joint_velocity: float,
    maximum_joint_displacement: float,
    maximum_end_effector_displacement: float,
    contact_occurred: bool,
) -> dict[str, Any]:
    """Build common trajectory summary fields for both probe types."""

    return {
        "maximum_absolute_joint_velocity": float(maximum_joint_velocity),
        "maximum_joint_displacement": float(maximum_joint_displacement),
        "maximum_end_effector_displacement": float(
            maximum_end_effector_displacement
        ),
        # The generic displacement is the maximum absolute joint displacement;
        # the end-effector displacement remains available separately.
        "maximum_displacement": float(maximum_joint_displacement),
        "contact_occurred": bool(contact_occurred),
        "samples": snapshots,
    }


def _run_constant_control_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    control_values: tuple[float, float],
) -> dict[str, Any]:
    control = np.asarray(control_values, dtype=float)
    if control.shape != (model.nu,):
        raise ValueError(
            f"Control {control_values} does not match model.nu={model.nu}"
        )

    reset_site_position = _reset_zero_state(model, data, site_id, control)
    snapshots: list[dict[str, Any]] = []
    maximum_joint_velocity = 0.0
    maximum_joint_displacement = 0.0
    maximum_end_effector_displacement = 0.0
    contact_occurred = False

    for substep in range(RESPONSE_SUBSTEPS + 1):
        if substep in RESPONSE_SAMPLES:
            snapshots.append(
                _snapshot(
                    model,
                    data,
                    site_id,
                    reset_site_position,
                    substep,
                    control,
                )
            )
        maximum_joint_velocity = max(
            maximum_joint_velocity, float(np.max(np.abs(data.qvel)))
        )
        maximum_joint_displacement = max(
            maximum_joint_displacement,
            float(np.max(np.abs(np.asarray(data.qpos) - 0.0))),
        )
        maximum_end_effector_displacement = max(
            maximum_end_effector_displacement,
            float(
                np.linalg.norm(
                    np.asarray(data.site_xpos[site_id]) - reset_site_position
                )
            ),
        )
        contact_occurred = contact_occurred or data.ncon > 0
        if substep < RESPONSE_SUBSTEPS:
            mujoco.mj_step(model, data)
            # mj_step integrates qpos/qvel after its forward pass. Refresh
            # derived site, contact, and force quantities for the new state
            # before the next loop iteration reads them.
            mujoco.mj_forward(model, data)

    trial = {
        "control": control,
        "substeps": RESPONSE_SUBSTEPS,
        "duration_seconds": float(RESPONSE_SUBSTEPS * model.opt.timestep),
    }
    trial.update(
        _summary(
            snapshots,
            maximum_joint_velocity,
            maximum_joint_displacement,
            maximum_end_effector_displacement,
            contact_occurred,
        )
    )
    return trial


def _run_bang_bang_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    first_control_values: tuple[float, float],
) -> dict[str, Any]:
    first_control = np.asarray(first_control_values, dtype=float)
    second_control = -first_control
    if first_control.shape != (model.nu,):
        raise ValueError(
            f"Control {first_control_values} does not match model.nu={model.nu}"
        )

    reset_site_position = _reset_zero_state(model, data, site_id, first_control)
    snapshots: list[dict[str, Any]] = []
    maximum_joint_velocity = 0.0
    maximum_joint_displacement = 0.0
    maximum_end_effector_displacement = 0.0
    contact_occurred = False

    for substep in range(ENVELOPE_SUBSTEPS + 1):
        if substep <= RESPONSE_SUBSTEPS:
            applied_control = first_control
            phase = "first_control"
        else:
            applied_control = second_control
            phase = "reversed_control"

        if substep in ENVELOPE_SAMPLES:
            snapshots.append(
                _snapshot(
                    model,
                    data,
                    site_id,
                    reset_site_position,
                    substep,
                    applied_control,
                    phase,
                )
            )
        maximum_joint_velocity = max(
            maximum_joint_velocity, float(np.max(np.abs(data.qvel)))
        )
        maximum_joint_displacement = max(
            maximum_joint_displacement,
            float(np.max(np.abs(np.asarray(data.qpos) - 0.0))),
        )
        maximum_end_effector_displacement = max(
            maximum_end_effector_displacement,
            float(
                np.linalg.norm(
                    np.asarray(data.site_xpos[site_id]) - reset_site_position
                )
            ),
        )
        contact_occurred = contact_occurred or data.ncon > 0

        if substep < ENVELOPE_SUBSTEPS:
            if substep == RESPONSE_SUBSTEPS:
                data.ctrl[:] = second_control
            mujoco.mj_step(model, data)
            # Keep all state-derived measurements synchronized with the
            # post-integration qpos/qvel at the next sampled substep.
            mujoco.mj_forward(model, data)

    trial = {
        "initial_control": first_control,
        "reversed_control": second_control,
        "substeps_per_phase": RESPONSE_SUBSTEPS,
        "total_substeps": ENVELOPE_SUBSTEPS,
        "duration_seconds": float(ENVELOPE_SUBSTEPS * model.opt.timestep),
    }
    trial.update(
        _summary(
            snapshots,
            maximum_joint_velocity,
            maximum_joint_displacement,
            maximum_end_effector_displacement,
            contact_occurred,
        )
    )
    return trial


def _compiled_model_description(model: mujoco.MjModel) -> dict[str, Any]:
    bodies: list[dict[str, Any]] = []
    for body_id in range(model.nbody):
        name = _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        if name is not None:
            bodies.append(
                {
                    "name": name,
                    "mass": model.body_mass[body_id],
                    "inertia": model.body_inertia[body_id],
                }
            )

    joints: list[dict[str, Any]] = []
    for joint_id in range(model.njnt):
        name = _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        if name is None:
            name = f"joint_{joint_id}"
        dof_id = int(model.jnt_dofadr[joint_id])
        joints.append(
            {
                "name": name,
                "qpos_address": model.jnt_qposadr[joint_id],
                "dof_address": dof_id,
                "dof_damping": model.dof_damping[dof_id],
                "dof_armature": model.dof_armature[dof_id],
            }
        )

    actuators: list[dict[str, Any]] = []
    for actuator_id in range(model.nu):
        actuators.append(
            {
                "name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
                ),
                "index": actuator_id,
                "gear": model.actuator_gear[actuator_id],
                "ctrlrange": model.actuator_ctrlrange[actuator_id],
            }
        )

    geoms: list[dict[str, Any]] = []
    for geom_id in range(model.ngeom):
        geoms.append(
            {
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id),
                "index": geom_id,
                "contype": model.geom_contype[geom_id],
                "conaffinity": model.geom_conaffinity[geom_id],
            }
        )

    return {
        "bodies": bodies,
        "joints": joints,
        "actuators": actuators,
        "geoms": geoms,
    }


def _runtime_description(model: mujoco.MjModel) -> dict[str, Any]:
    runtime: dict[str, Any] = {
        "mujoco_version": getattr(mujoco, "__version__", None),
        "model_timestep": model.opt.timestep,
        "nq": model.nq,
        "nv": model.nv,
        "nu": model.nu,
    }
    for field_name, enum_type, member_names in (
        (
            "integrator",
            mujoco.mjtIntegrator,
            (
                "mjINT_EULER",
                "mjINT_RK4",
                "mjINT_IMPLICIT",
                "mjINT_IMPLICITFAST",
            ),
        ),
        (
            "solver",
            mujoco.mjtSolver,
            ("mjSOL_PGS", "mjSOL_CG", "mjSOL_NEWTON"),
        ),
    ):
        value = getattr(model.opt, field_name, None)
        if value is not None:
            runtime[field_name] = _enum_identifier(
                enum_type, value, member_names
            )
    return runtime


def _reset_state_and_inertia(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    zero_control = np.zeros(model.nu, dtype=float)
    reset_site_position = _reset_zero_state(model, data, site_id, zero_control)
    dense_inertia = np.zeros((model.nv, model.nv), dtype=float)
    mujoco.mj_fullM(model, data, dense_inertia)
    condition_number = float(np.linalg.cond(dense_inertia))
    return (
        {
            "qpos": np.asarray(data.qpos, dtype=float).copy(),
            "qvel": np.asarray(data.qvel, dtype=float).copy(),
            "site_name": "end_effector",
            "site_position": reset_site_position,
        },
        {
            "dense_generalized_inertia": dense_inertia,
            "condition_number": condition_number,
        },
    )


def _build_artifact() -> dict[str, Any]:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = _required_object_id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    reset_state, inertia_at_reset = _reset_state_and_inertia(
        model, data, site_id
    )

    torque_trials = [
        _run_constant_control_trial(model, data, site_id, control)
        for control in TORQUE_CONTROLS
    ]
    envelope_trials = [
        _run_bang_bang_trial(model, data, site_id, control)
        for control in ENVELOPE_CONTROLS
    ]

    return {
        "schema_version": 1,
        "interpretation_scope": (
            "Physical response probe only; this is not a policy evaluation "
            "and does not measure reach-and-hold success."
        ),
        "runtime": _runtime_description(model),
        "compiled_model": _compiled_model_description(model),
        "reset_state": reset_state,
        "inertia_at_reset": inertia_at_reset,
        "torque_response": {
            "substeps_per_trial": RESPONSE_SUBSTEPS,
            "duration_seconds": float(RESPONSE_SUBSTEPS * model.opt.timestep),
            "sample_substeps": sorted(RESPONSE_SAMPLES),
            "trials": torque_trials,
            "finite_time_envelope": {
                "substeps_per_phase": RESPONSE_SUBSTEPS,
                "total_substeps": ENVELOPE_SUBSTEPS,
                "duration_seconds": float(
                    ENVELOPE_SUBSTEPS * model.opt.timestep
                ),
                "sample_substeps": sorted(ENVELOPE_SAMPLES),
                "trials": envelope_trials,
            },
        },
    }


def _write_artifact(output_argument: str, artifact: dict[str, Any]) -> None:
    if not output_argument.strip():
        raise ValueError("The output path must be a non-empty literal path")
    output_path = Path(output_argument)
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_argument}")
    if not output_path.parent.exists():
        raise FileNotFoundError(
            f"Output parent directory does not exist: {output_path.parent}"
        )
    if not output_path.parent.is_dir():
        raise NotADirectoryError(
            f"Output parent is not a directory: {output_path.parent}"
        )

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(
            _as_json_value(artifact),
            output_file,
            allow_nan=False,
            indent=2,
        )
        output_file.write("\n")


def main() -> None:
    if len(sys.argv) != 2:
        raise ValueError(
            "Usage: uv run -m robot_learning.lab.compiled_dynamics_probe "
            "OUTPUT_JSON"
        )
    _write_artifact(sys.argv[1], _build_artifact())


if __name__ == "__main__":
    main()
