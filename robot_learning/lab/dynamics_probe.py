"""Deterministic MuJoCo measurements for the two-link arm.

This is a laboratory measurement, not an environment or a controller.  It
records short, independently reset trajectories so that compiled dynamics,
actuator authority, coupling, and limit behavior can be inspected before
training a policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


DEFAULT_SUBSTEPS = 10
DEFAULT_DECAY_SUBSTEPS = 20
DEFAULT_PULSE_CONTROL = 1.0
DEFAULT_SEED = 0
FIXED_TARGET_XY = np.array([0.10, 0.0], dtype=np.float64)


def _name(model: mujoco.MjModel, obj: Any, index: int) -> str:
    value = mujoco.mj_id2name(model, obj, index)
    return value if value is not None else f"unnamed_{index}"


def _finite_array(values: Any, label: str) -> list[Any]:
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{label} contains a non-finite value")
    return array.tolist()


def _finite_scalar(value: Any, label: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{label} is non-finite")
    return number


def _enum_name(value: int, names: dict[int, str]) -> str:
    return names.get(int(value), f"unknown_{int(value)}")


def _model_facts(model: mujoco.MjModel) -> dict[str, Any]:
    if (model.nq, model.nv, model.nu) != (2, 2, 2):
        raise ValueError(
            "the authoritative two_joint_arm model must have nq=2, nv=2, nu=2"
        )
    if model.njnt != 2:
        raise ValueError("the authoritative model must have exactly two joints")

    joint_facts: list[dict[str, Any]] = []
    for joint_id in range(model.njnt):
        if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_HINGE):
            raise ValueError(f"joint {joint_id} is not a hinge")
        qpos_address = int(model.jnt_qposadr[joint_id])
        dof_address = int(model.jnt_dofadr[joint_id])
        joint_facts.append(
            {
                "id": joint_id,
                "name": _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "range_rad": _finite_array(
                    model.jnt_range[joint_id], f"joint_range_{joint_id}"
                ),
                "limited": bool(model.jnt_limited[joint_id]),
                "qpos_address": qpos_address,
                "dof_address": dof_address,
                "damping": _finite_scalar(
                    model.dof_damping[dof_address], f"joint_damping_{joint_id}"
                ),
                "armature": _finite_scalar(
                    model.dof_armature[dof_address], f"joint_armature_{joint_id}"
                ),
            }
        )

    actuator_facts: list[dict[str, Any]] = []
    for actuator_id in range(model.nu):
        actuator_facts.append(
            {
                "id": actuator_id,
                "name": _name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id),
                "gear": _finite_array(
                    model.actuator_gear[actuator_id], f"actuator_gear_{actuator_id}"
                ),
                "ctrl_range": _finite_array(
                    model.actuator_ctrlrange[actuator_id],
                    f"actuator_ctrlrange_{actuator_id}",
                ),
                "force_range": _finite_array(
                    model.actuator_forcerange[actuator_id],
                    f"actuator_forcerange_{actuator_id}",
                ),
                "ctrl_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "force_limited": bool(model.actuator_forcelimited[actuator_id]),
            }
        )

    integrator_names = {
        int(mujoco.mjtIntegrator.mjINT_EULER): "mjINT_EULER",
        int(mujoco.mjtIntegrator.mjINT_RK4): "mjINT_RK4",
        int(mujoco.mjtIntegrator.mjINT_IMPLICIT): "mjINT_IMPLICIT",
        int(mujoco.mjtIntegrator.mjINT_IMPLICITFAST): "mjINT_IMPLICITFAST",
    }
    solver_names = {
        int(mujoco.mjtSolver.mjSOL_PGS): "mjSOL_PGS",
        int(mujoco.mjtSolver.mjSOL_CG): "mjSOL_CG",
        int(mujoco.mjtSolver.mjSOL_NEWTON): "mjSOL_NEWTON",
    }

    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "nbody": int(model.nbody),
        "njnt": int(model.njnt),
        "timestep_s": _finite_scalar(model.opt.timestep, "timestep"),
        "integrator": {
            "id": int(model.opt.integrator),
            "name": _enum_name(int(model.opt.integrator), integrator_names),
        },
        "solver": {
            "id": int(model.opt.solver),
            "name": _enum_name(int(model.opt.solver), solver_names),
            "iterations": int(model.opt.iterations),
        },
        "joints": joint_facts,
        "bodies": [
            {
                "id": body_id,
                "name": _name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass": _finite_scalar(model.body_mass[body_id], f"body_mass_{body_id}"),
                "inertia": _finite_array(
                    model.body_inertia[body_id], f"body_inertia_{body_id}"
                ),
            }
            for body_id in range(model.nbody)
        ],
        "actuators": actuator_facts,
        "dof_damping": _finite_array(model.dof_damping, "dof_damping"),
        "dof_armature": _finite_array(model.dof_armature, "dof_armature"),
    }


def _available_state_fields(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, list[str]]:
    model_candidates = (
        "jnt_limited",
        "jnt_range",
        "actuator_ctrllimited",
        "actuator_ctrlrange",
        "actuator_forcelimited",
        "actuator_forcerange",
    )
    data_candidates = ("ctrl", "actuator_force", "efc_type", "efc_id", "nefc")
    model_fields = [field for field in model_candidates if hasattr(model, field)]
    data_fields = [field for field in data_candidates if hasattr(data, field)]
    return {
        "model_fields": model_fields,
        "data_fields": data_fields,
        "unavailable_model_fields": [
            field for field in model_candidates if field not in model_fields
        ],
        "unavailable_data_fields": [
            field for field in data_candidates if field not in data_fields
        ],
    }


def _joint_limit_margins(
    model: mujoco.MjModel, data: mujoco.MjData
) -> list[dict[str, float | int | str]]:
    margins: list[dict[str, float | int | str]] = []
    for joint_id in range(model.njnt):
        qpos_address = int(model.jnt_qposadr[joint_id])
        lower, upper = (
            float(model.jnt_range[joint_id, 0]),
            float(model.jnt_range[joint_id, 1]),
        )
        qpos = _finite_scalar(data.qpos[qpos_address], f"qpos_{joint_id}")
        lower_margin = _finite_scalar(qpos - lower, f"lower_margin_{joint_id}")
        upper_margin = _finite_scalar(upper - qpos, f"upper_margin_{joint_id}")
        margins.append(
            {
                "joint_id": joint_id,
                "joint_name": _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "lower_margin_rad": lower_margin,
                "upper_margin_rad": upper_margin,
                "minimum_margin_rad": min(lower_margin, upper_margin),
            }
        )
    return margins


def _limit_state(
    model: mujoco.MjModel, data: mujoco.MjData, available: dict[str, list[str]]
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "joint_limit_margins": _joint_limit_margins(model, data),
        "joint_limit_constraint_ids": None,
        "joint_limit_constraint_active": None,
        "control_saturated": None,
        "force_saturated": None,
    }

    if all(
        field in available["data_fields"] for field in ("efc_type", "efc_id", "nefc")
    ):
        limit_type = int(mujoco.mjtConstraint.mjCNSTR_LIMIT_JOINT)
        ids: list[int] = []
        for constraint_id in range(int(data.nefc)):
            if int(data.efc_type[constraint_id]) == limit_type:
                ids.append(int(data.efc_id[constraint_id]))
        state["joint_limit_constraint_ids"] = ids
        state["joint_limit_constraint_active"] = bool(ids)

    if "ctrl" in available["data_fields"] and "actuator_ctrllimited" in available["model_fields"]:
        saturated: list[bool] = []
        for actuator_id in range(model.nu):
            if not bool(model.actuator_ctrllimited[actuator_id]):
                saturated.append(False)
                continue
            low, high = model.actuator_ctrlrange[actuator_id]
            value = float(data.ctrl[actuator_id])
            saturated.append(bool(np.isclose(value, low) or np.isclose(value, high)))
        state["control_saturated"] = saturated

    if (
        "actuator_force" in available["data_fields"]
        and "actuator_forcelimited" in available["model_fields"]
    ):
        saturated_force: list[bool] = []
        for actuator_id in range(model.nu):
            if not bool(model.actuator_forcelimited[actuator_id]):
                saturated_force.append(False)
                continue
            low, high = model.actuator_forcerange[actuator_id]
            value = float(data.actuator_force[actuator_id])
            saturated_force.append(bool(np.isclose(value, low) or np.isclose(value, high)))
        state["force_saturated"] = saturated_force

    return state


def _sample(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    fixed_target_xy: np.ndarray,
    available_fields: dict[str, list[str]],
    *,
    step_index: int,
    phase: str,
) -> dict[str, Any]:
    qpos = _finite_array(data.qpos, "qpos")
    qvel = _finite_array(data.qvel, "qvel")
    qacc = _finite_array(data.qacc, "qacc")
    ctrl = _finite_array(data.ctrl, "ctrl")
    xy = _finite_array(data.site_xpos[site_id, :2], "end_effector_xy")
    site_velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        model,
        data,
        mujoco.mjtObj.mjOBJ_SITE,
        site_id,
        site_velocity,
        0,
    )
    # mj_objectVelocity returns [angular xyz, translational xyz].  With
    # flg_local=0 these are world-frame components, so [3:5] is xy.
    site_velocity = np.asarray(
        _finite_array(site_velocity, "end_effector_site_velocity"),
        dtype=np.float64,
    )
    xy_velocity = _finite_array(
        site_velocity[3:5], "end_effector_xy_velocity"
    )
    distance = _finite_scalar(
        np.linalg.norm(np.asarray(xy, dtype=np.float64) - fixed_target_xy),
        "distance_to_fixed_target",
    )
    return {
        "step_index": int(step_index),
        "phase": phase,
        "qpos_rad": qpos,
        "qvel_rad_s": qvel,
        "qacc_rad_s2": qacc,
        "applied_ctrl": ctrl,
        "end_effector_xy_m": xy,
        "end_effector_xy_velocity_m_s": xy_velocity,
        "distance_to_fixed_target_m": distance,
        "limit_and_saturation": _limit_state(model, data, available_fields),
    }


def _reset_state(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int, fixed_target_xy: np.ndarray
) -> dict[str, Any]:
    qpos = _finite_array(data.qpos, "initial qpos")
    qvel = _finite_array(data.qvel, "initial qvel")
    if not np.allclose(qvel, 0.0):
        raise ValueError("independent probe reset did not produce zero velocity")
    xy = _finite_array(data.site_xpos[site_id, :2], "initial end_effector_xy")
    return {
        "qpos_rad": qpos,
        "qvel_rad_s": qvel,
        "end_effector_xy_m": xy,
        "end_effector_radius_m": _finite_scalar(np.linalg.norm(xy), "initial radius"),
        "distance_to_fixed_target_m": _finite_scalar(
            np.linalg.norm(np.asarray(xy, dtype=np.float64) - fixed_target_xy),
            "initial distance",
        ),
    }


def _run_schedule(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    fixed_target_xy: np.ndarray,
    available_fields: dict[str, list[str]],
    qpos: Iterable[float],
    schedule: list[tuple[str, np.ndarray]],
) -> dict[str, Any]:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = np.asarray(list(qpos), dtype=np.float64)
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    initial_state = _reset_state(model, data, site_id, fixed_target_xy)

    samples: list[dict[str, Any]] = []
    requested_controls: list[list[float]] = []
    for step_index, (phase, control) in enumerate(schedule, start=1):
        control_array = np.asarray(control, dtype=np.float64)
        if control_array.shape != (model.nu,) or not np.all(np.isfinite(control_array)):
            raise ValueError(f"invalid control at schedule step {step_index}")
        requested_controls.append(_finite_array(control_array, "requested control"))
        data.ctrl[:] = control_array
        mujoco.mj_step(model, data)
        samples.append(
            _sample(
                model,
                data,
                site_id,
                fixed_target_xy,
                available_fields,
                step_index=step_index,
                phase=phase,
            )
        )

    if len(samples) != len(schedule):
        raise RuntimeError("probe schedule and recorded sample lengths differ")
    return {
        "declared_substeps": len(schedule),
        "initial_state": initial_state,
        "requested_ctrl": requested_controls,
        "samples": samples,
    }


def _configuration_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "reset_fully_extended",
            "qpos_rad": [0.0, 0.0],
            "description": "authoritative reset posture; both links point along +x",
        },
        {
            "name": "orthogonal_elbow",
            "qpos_rad": [0.0, float(np.pi / 2.0)],
            "description": "non-singular posture with an approximately orthogonal elbow",
        },
        {
            "name": "folded_inner_positive",
            "qpos_rad": [0.0, 2.2],
            "description": "folded posture near the inner official radial regime",
        },
        {
            "name": "folded_inner_negative",
            "qpos_rad": [0.0, -2.2],
            "description": "opposite folded branch near the inner official radial regime",
        },
    ]


def _validate_settings(substeps: int, decay_substeps: int, pulse_control: float, seed: int) -> None:
    if substeps <= 0 or decay_substeps <= 0:
        raise ValueError("substeps and decay_substeps must be positive")
    if not np.isfinite(pulse_control) or not 0.0 < pulse_control <= 1.0:
        raise ValueError("pulse_control must be finite and in (0, 1]")
    if seed < 0:
        raise ValueError("seed must be non-negative")


def collect_probe(
    *,
    substeps: int = DEFAULT_SUBSTEPS,
    decay_substeps: int = DEFAULT_DECAY_SUBSTEPS,
    pulse_control: float = DEFAULT_PULSE_CONTROL,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Compile the authoritative model and return a JSON-compatible probe."""

    _validate_settings(substeps, decay_substeps, pulse_control, seed)
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = int(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"))
    if site_id < 0:
        raise ValueError("authoritative model has no end_effector site")

    model_facts = _model_facts(model)
    available_fields = _available_state_fields(model, data)
    fixed_target = FIXED_TARGET_XY.copy()
    configurations: list[dict[str, Any]] = []
    total_resets = 0

    for definition in _configuration_definitions():
        qpos = np.asarray(definition["qpos_rad"], dtype=np.float64)
        if qpos.shape != (model.nq,) or not np.all(np.isfinite(qpos)):
            raise ValueError(f"invalid configuration {definition['name']}")
        for joint_id in range(model.njnt):
            address = int(model.jnt_qposadr[joint_id])
            low, high = model.jnt_range[joint_id]
            if not low <= qpos[address] <= high:
                raise ValueError(f"configuration {definition['name']} exceeds joint range")

        probes: dict[str, Any] = {}
        for joint_id in range(model.nu):
            for direction_name, direction in (("positive", 1.0), ("negative", -1.0)):
                control = np.zeros(model.nu, dtype=np.float64)
                control[joint_id] = direction * pulse_control
                schedule = [
                    (f"single_joint_{direction_name}", control.copy())
                    for _ in range(substeps)
                ]
                probes[f"joint_{joint_id}_{direction_name}"] = _run_schedule(
                    model,
                    data,
                    site_id,
                    fixed_target,
                    available_fields,
                    qpos,
                    schedule,
                )
                total_resets += 1

            positive = np.zeros(model.nu, dtype=np.float64)
            negative = np.zeros(model.nu, dtype=np.float64)
            positive[joint_id] = pulse_control
            negative[joint_id] = -pulse_control
            reversal_schedule = [
                ("positive_pulse", positive.copy()) for _ in range(substeps)
            ] + [("negative_reversal", negative.copy()) for _ in range(substeps)]
            probes[f"joint_{joint_id}_reversal"] = _run_schedule(
                model,
                data,
                site_id,
                fixed_target,
                available_fields,
                qpos,
                reversal_schedule,
            )
            total_resets += 1

        pulse = np.zeros(model.nu, dtype=np.float64)
        pulse[0] = pulse_control
        decay_schedule = [
            ("nonzero_pulse", pulse.copy()) for _ in range(substeps)
        ] + [
            ("zero_control_decay", np.zeros(model.nu, dtype=np.float64))
            for _ in range(decay_substeps)
        ]
        probes["zero_control_decay"] = _run_schedule(
            model,
            data,
            site_id,
            fixed_target,
            available_fields,
            qpos,
            decay_schedule,
        )
        total_resets += 1
        configurations.append(
            {
                "name": definition["name"],
                "description": definition["description"],
                "qpos_rad": _finite_array(qpos, f"configuration_{definition['name']}"),
                "probes": probes,
            }
        )

    return {
        "schema_version": 1,
        "measurement": "two_joint_arm_dynamics_probe",
        "metadata": {
            "deterministic_seed": int(seed),
            "seed_use": "recorded for reproducibility; probe controls and configurations are fixed",
            "settings": {
                "single_action_substeps": int(substeps),
                "decay_zero_control_substeps": int(decay_substeps),
                "pulse_control_magnitude": _finite_scalar(
                    pulse_control, "pulse_control"
                ),
            },
            "units": {
                "time": "s",
                "qpos": "rad",
                "qvel": "rad/s",
                "qacc": "rad/s^2",
                "control": "dimensionless MuJoCo actuator control",
                "end_effector_xy": "m",
                "end_effector_xy_velocity": "m/s",
                "end_effector_xy_velocity_source": "mujoco.mj_objectVelocity site result[3:5] with flg_local=0 (world-frame translational xy)",
                "joint_limit_margin": "rad",
            },
            "probe_definitions": {
                "single_joint": "one actuator direction held for the declared environment substep count",
                "reversal": "positive pulse for the declared count followed by an equal negative pulse",
                "zero_control_decay": "positive joint-0 pulse followed by zero control",
                "fixed_target_xy_m": _finite_array(fixed_target, "fixed target"),
                "target_role": "auxiliary distance diagnostic; it is not written into model mocap state",
                "configurations": [
                    {
                        "name": item["name"],
                        "qpos_rad": item["qpos_rad"],
                        "description": item["description"],
                    }
                    for item in _configuration_definitions()
                ],
            },
            "independent_reset_count": int(total_resets),
            "state_field_availability": available_fields,
        },
        "compiled_model": model_facts,
        "configurations": configurations,
    }


def _assert_json_finite(value: Any, path: str = "artifact") -> None:
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError(f"{path} contains a non-finite float")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_json_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_json_finite(child, f"{path}[{index}]")


def write_probe_artifact(output_path: str | Path, **settings: Any) -> dict[str, Any]:
    artifact = collect_probe(**settings)
    _assert_json_finite(artifact)
    path = Path(output_path)
    path.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="JSON artifact path")
    parser.add_argument("--substeps", type=int, default=DEFAULT_SUBSTEPS)
    parser.add_argument("--decay-substeps", type=int, default=DEFAULT_DECAY_SUBSTEPS)
    parser.add_argument("--pulse-control", type=float, default=DEFAULT_PULSE_CONTROL)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    write_probe_artifact(
        args.output,
        substeps=args.substeps,
        decay_substeps=args.decay_substeps,
        pulse_control=args.pulse_control,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
