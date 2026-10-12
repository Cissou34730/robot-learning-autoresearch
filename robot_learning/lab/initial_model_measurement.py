"""Deterministic measurements of the compiled two-link physical model.

This module deliberately measures the model without importing a policy or an
environment wrapper.  The JSON schema is kept explicit because the output is
intended to be inspected as laboratory evidence, rather than consumed as a
training configuration.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import TARGET_RADIUS_RANGE


JOINT_NAMES = ("shoulder", "elbow")
GRID_RADIUS_COUNT = 25
GRID_ANGLE_COUNT = 72
CONTROL_STEPS = 10
FREE_DECAY_STEPS = 25
REPEATS_PER_CONTROL_TRIAL = 2
JOINT_LIMIT_DEGREES = 170.0


def _as_floats(values: object) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape(-1)]


def _as_matrix(values: object) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(values)]


def _enum_label(value: int, enum_type: object, labels: dict[str, str]) -> dict[str, object]:
    integer = int(value)
    for member_name, label in labels.items():
        if integer == int(getattr(enum_type, member_name)):
            return {"id": integer, "name": label}
    return {"id": integer, "name": "unknown"}


def _object_name(model: mujoco.MjModel, object_type: object, object_id: int) -> str | None:
    return mujoco.mj_id2name(model, object_type, int(object_id))


def _load_model_context() -> tuple[mujoco.MjModel, dict[str, object]]:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    joint_ids: dict[str, int] = {}
    qpos_addresses: list[int] = []
    dof_addresses: list[int] = []
    for name in JOINT_NAMES:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError(f"required joint is missing from compiled model: {name}")
        if int(model.jnt_type[joint_id]) != int(mujoco.mjtJoint.mjJNT_HINGE):
            raise RuntimeError(f"required joint is not a hinge: {name}")
        qpos_address = int(model.jnt_qposadr[joint_id])
        dof_address = int(model.jnt_dofadr[joint_id])
        if not 0 <= qpos_address < int(model.nq):
            raise RuntimeError(f"invalid qpos address for joint {name}: {qpos_address}")
        if not 0 <= dof_address < int(model.nv):
            raise RuntimeError(f"invalid dof address for joint {name}: {dof_address}")
        joint_ids[name] = joint_id
        qpos_addresses.append(qpos_address)
        dof_addresses.append(dof_address)

    if int(model.nq) != 2 or int(model.nv) != 2 or int(model.nu) != 2:
        raise RuntimeError(
            "compiled model dimensions must be nq=2, nv=2, nu=2; "
            f"got nq={model.nq}, nv={model.nv}, nu={model.nu}"
        )
    if len(set(qpos_addresses)) != 2 or len(set(dof_addresses)) != 2:
        raise RuntimeError("named joints do not have distinct generalized addresses")

    actuator_ids: list[int] = []
    for index, joint_name in enumerate(JOINT_NAMES):
        actuator_id = index
        transmission_joint = int(model.actuator_trnid[actuator_id, 0])
        if transmission_joint != joint_ids[joint_name]:
            raise RuntimeError(
                f"actuator {actuator_id} is not transmitted through {joint_name}"
            )
        actuator_ids.append(actuator_id)

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    if site_id < 0:
        raise RuntimeError("required site is missing from compiled model: end_effector")

    context = {
        "joint_ids": joint_ids,
        "qpos_addresses": qpos_addresses,
        "dof_addresses": dof_addresses,
        "actuator_ids": actuator_ids,
        "site_id": int(site_id),
    }
    return model, context


def _reset_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    context: dict[str, object],
    q: list[float],
    qvel: list[float] | None = None,
) -> None:
    mujoco.mj_resetData(model, data)
    qpos_addresses = context["qpos_addresses"]
    dof_addresses = context["dof_addresses"]
    assert isinstance(qpos_addresses, list)
    assert isinstance(dof_addresses, list)
    data.qpos[qpos_addresses] = np.asarray(q, dtype=float)
    if qvel is not None:
        data.qvel[dof_addresses] = np.asarray(qvel, dtype=float)
    mujoco.mj_forward(model, data)


def _snapshot(data: mujoco.MjData) -> dict[str, list[float]]:
    return {
        "qpos": _as_floats(data.qpos),
        "qvel": _as_floats(data.qvel),
        "qacc": _as_floats(data.qacc),
        "qfrc_actuator": _as_floats(data.qfrc_actuator),
    }


def _forward_kinematics(q: list[float]) -> np.ndarray:
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


def _analytic_jacobian(q: list[float]) -> np.ndarray:
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


def _compiled_planar_jacobian(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    context: dict[str, object],
) -> np.ndarray:
    jacp = np.zeros((3, int(model.nv)), dtype=float)
    jacr = np.zeros((3, int(model.nv)), dtype=float)
    mujoco.mj_jacSite(model, data, jacp, jacr, int(context["site_id"]))
    dof_addresses = context["dof_addresses"]
    assert isinstance(dof_addresses, list)
    return jacp[np.ix_([0, 1], dof_addresses)]


def _compiled_facts(model: mujoco.MjModel, context: dict[str, object]) -> dict[str, object]:
    joint_ids = context["joint_ids"]
    actuator_ids = context["actuator_ids"]
    qpos_addresses = context["qpos_addresses"]
    dof_addresses = context["dof_addresses"]
    assert isinstance(joint_ids, dict)
    assert isinstance(actuator_ids, list)
    assert isinstance(qpos_addresses, list)
    assert isinstance(dof_addresses, list)

    joints = []
    for name, qpos_address, dof_address in zip(
        JOINT_NAMES, qpos_addresses, dof_addresses
    ):
        joint_id = joint_ids[name]
        joints.append(
            {
                "name": name,
                "id": int(joint_id),
                "type": int(model.jnt_type[joint_id]),
                "qpos_address": int(qpos_address),
                "dof_address": int(dof_address),
                "range_rad": _as_floats(model.jnt_range[joint_id]),
                "damping_N_m_s": float(model.dof_damping[dof_address]),
                "armature_kg_m2": float(model.dof_armature[dof_address]),
            }
        )

    actuators = []
    for actuator_id in actuator_ids:
        transmitted_joint = int(model.actuator_trnid[actuator_id, 0])
        actuators.append(
            {
                "id": int(actuator_id),
                "name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
                ),
                "transmission_type": _enum_label(
                    int(model.actuator_trntype[actuator_id]),
                    mujoco.mjtTrn,
                    {"mjTRN_JOINT": "joint"},
                ),
                "transmission_joint": _object_name(
                    model, mujoco.mjtObj.mjOBJ_JOINT, transmitted_joint
                ),
                "transmission_joint_id": transmitted_joint,
                "gear": _as_floats(model.actuator_gear[actuator_id]),
                "control_range": _as_floats(model.actuator_ctrlrange[actuator_id]),
                "force_range": _as_floats(model.actuator_forcerange[actuator_id]),
            }
        )

    bodies = []
    for body_id in range(int(model.nbody)):
        bodies.append(
            {
                "id": body_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass_kg": float(model.body_mass[body_id]),
                "inertia_kg_m2": _as_floats(model.body_inertia[body_id]),
            }
        )

    return {
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "nbody": int(model.nbody),
            "njnt": int(model.njnt),
            "nsite": int(model.nsite),
        },
        "timestep_s": float(model.opt.timestep),
        "gravity_m_s2": _as_floats(model.opt.gravity),
        "integrator": _enum_label(
            int(model.opt.integrator),
            mujoco.mjtIntegrator,
            {
                "mjINT_EULER": "euler",
                "mjINT_RK4": "rk4",
                "mjINT_IMPLICIT": "implicit",
                "mjINT_IMPLICITFAST": "implicitfast",
            },
        ),
        "solver": _enum_label(
            int(model.opt.solver),
            mujoco.mjtSolver,
            {
                "mjSOL_PGS": "pgs",
                "mjSOL_CG": "cg",
                "mjSOL_NEWTON": "newton",
            },
        ),
        "solver_iterations": int(model.opt.iterations),
        "solver_tolerance": float(model.opt.tolerance),
        "bodies": bodies,
        "joints": joints,
        "actuators": actuators,
    }


def _ik_measurement(
    model: mujoco.MjModel, data: mujoco.MjData, context: dict[str, object]
) -> dict[str, object]:
    joint_ranges = []
    for joint in _compiled_facts(model, context)["joints"]:
        assert isinstance(joint, dict)
        joint_ranges.append(joint["range_rad"])

    radii = np.linspace(
        float(TARGET_RADIUS_RANGE[0]),
        float(TARGET_RADIUS_RANGE[1]),
        GRID_RADIUS_COUNT,
    )
    angles = [2.0 * math.pi * index / GRID_ANGLE_COUNT for index in range(GRID_ANGLE_COUNT)]
    records: list[dict[str, object]] = []
    feasible_by_branch = {"positive_elbow": 0, "negative_elbow": 0}
    max_analytic_residual = 0.0
    max_compiled_residual = 0.0

    for radius in radii:
        for angle in angles:
            target = np.asarray(
                [radius * math.cos(angle), radius * math.sin(angle), 0.02],
                dtype=float,
            )
            cosine = (
                radius * radius
                - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH
                - FOREARM_LENGTH * FOREARM_LENGTH
            ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
            cosine = min(1.0, max(-1.0, cosine))
            magnitude = math.acos(cosine)
            for branch, elbow in (
                ("positive_elbow", magnitude),
                ("negative_elbow", -magnitude),
            ):
                shoulder = math.atan2(float(target[1]), float(target[0])) - math.atan2(
                    FOREARM_LENGTH * math.sin(elbow),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
                )
                q = [shoulder, elbow]
                feasible = all(
                    float(bounds[0]) <= value <= float(bounds[1])
                    for bounds, value in zip(joint_ranges, q)
                )
                analytic_residual = float(np.linalg.norm(_forward_kinematics(q) - target))
                _reset_state(model, data, context, q)
                compiled_residual = float(
                    np.linalg.norm(data.site_xpos[int(context["site_id"])] - target)
                )
                margins = [
                    min(value - float(bounds[0]), float(bounds[1]) - value)
                    for bounds, value in zip(joint_ranges, q)
                ]
                if feasible:
                    feasible_by_branch[branch] += 1
                    max_analytic_residual = max(max_analytic_residual, analytic_residual)
                    max_compiled_residual = max(max_compiled_residual, compiled_residual)
                records.append(
                    {
                        "radius_m": float(radius),
                        "azimuth_rad": float(angle),
                        "branch": branch,
                        "target_xyz_m": _as_floats(target),
                        "q_rad": [float(value) for value in q],
                        "feasible": feasible,
                        "joint_limit_margin_rad": [float(value) for value in margins],
                        "analytic_fk_residual_m": analytic_residual,
                        "compiled_fk_residual_m": compiled_residual,
                    }
                )

    return {
        "link_lengths_m": {
            "upper_arm": float(UPPER_ARM_LENGTH),
            "forearm": float(FOREARM_LENGTH),
        },
        "radius_grid_m": _as_floats(radii),
        "azimuth_grid_rad": [float(value) for value in angles],
        "branch_definitions": {
            "positive_elbow": "+acos(c)",
            "negative_elbow": "-acos(c)",
        },
        "records": records,
        "summary": {
            "total_records": len(records),
            "feasible_records_by_branch": feasible_by_branch,
            "max_feasible_analytic_fk_residual_m": max_analytic_residual,
            "max_feasible_compiled_fk_residual_m": max_compiled_residual,
            "joint_limit_definition": "compiled joint ranges, radians",
        },
    }


def _jacobian_measurement(
    model: mujoco.MjModel, data: mujoco.MjData, context: dict[str, object]
) -> dict[str, object]:
    configurations = [
        ("reset", [0.0, 0.0]),
        ("bent_1", [0.55, -1.05]),
        ("bent_2", [-0.80, 0.90]),
    ]
    records = []
    for name, q in configurations:
        _reset_state(model, data, context, q)
        analytic = _analytic_jacobian(q)
        compiled = _compiled_planar_jacobian(model, data, context)
        singular_values = np.linalg.svd(analytic, compute_uv=False)
        smallest = float(singular_values[-1])
        condition = (
            float(singular_values[0] / smallest) if smallest > 1e-15 else None
        )
        records.append(
            {
                "name": name,
                "q_rad": [float(value) for value in q],
                "analytic_jacobian_m_per_rad": _as_matrix(analytic),
                "compiled_jacobian_m_per_rad": _as_matrix(compiled),
                "compiled_minus_analytic_max_abs_m_per_rad": float(
                    np.max(np.abs(compiled - analytic))
                ),
                "singular_values_m_per_rad": _as_floats(singular_values),
                "condition_number": condition,
                "condition_number_status": (
                    "finite" if condition is not None else "infinite_rank_deficient"
                ),
            }
        )
    return {
        "configuration_definition": (
            "reset is q=(0,0); bent configurations are fixed non-singular "
            "interior configurations in radians"
        ),
        "records": records,
        "summary": {
            "reset_smallest_singular_value_m_per_rad": records[0][
                "singular_values_m_per_rad"
            ][-1],
            "reset_condition_number": records[0]["condition_number"],
            "bent_smallest_singular_values_m_per_rad": [
                records[index]["singular_values_m_per_rad"][-1] for index in (1, 2)
            ],
        },
    }


def _controlled_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    context: dict[str, object],
    configuration_name: str,
    q: list[float],
    command: list[float],
    repeat_index: int,
) -> dict[str, object]:
    if any(value < -1.0 or value > 1.0 for value in command):
        raise RuntimeError(f"control command is outside [-1,1]: {command}")
    _reset_state(model, data, context, q)
    before = _snapshot(data)
    data.ctrl[:] = np.asarray(command, dtype=float)
    mujoco.mj_step(model, data, nstep=CONTROL_STEPS)
    after = _snapshot(data)
    return {
        "configuration": configuration_name,
        "q_initial_rad": [float(value) for value in q],
        "command": [float(value) for value in command],
        "repeat_index": int(repeat_index),
        "physics_steps": CONTROL_STEPS,
        "interval_s": float(CONTROL_STEPS * model.opt.timestep),
        "before": before,
        "after": after,
    }


def _dynamics_measurement(
    model: mujoco.MjModel, data: mujoco.MjData, context: dict[str, object]
) -> dict[str, object]:
    configurations = [
        ("reset", [0.0, 0.0]),
        ("bent_1", [0.55, -1.05]),
        ("bent_2", [-0.80, 0.90]),
    ]
    commands = [[1.0, 0.0], [0.0, 1.0], [0.5, -0.5], [0.0, 0.0]]
    trials = []
    for configuration_name, q in configurations:
        for command in commands:
            for repeat_index in range(REPEATS_PER_CONTROL_TRIAL):
                trials.append(
                    _controlled_trial(
                        model,
                        data,
                        context,
                        configuration_name,
                        q,
                        command,
                        repeat_index,
                    )
                )

    decay_q = [0.55, -1.05]
    decay_velocity = [0.35, -0.20]
    _reset_state(model, data, context, decay_q, decay_velocity)
    data.ctrl[:] = 0.0
    decay_states = [{"physics_step": 0, **_snapshot(data)}]
    for physics_step in range(1, FREE_DECAY_STEPS + 1):
        mujoco.mj_step(model, data)
        decay_states.append({"physics_step": physics_step, **_snapshot(data)})

    return {
        "control_interval_definition": (
            f"{CONTROL_STEPS} physics steps at the compiled timestep; "
            "commands are held constant"
        ),
        "controlled_trials": trials,
        "free_decay": {
            "configuration": "bent_1",
            "q_initial_rad": [float(value) for value in decay_q],
            "qvel_initial_rad_s": [float(value) for value in decay_velocity],
            "command": [0.0, 0.0],
            "physics_steps": FREE_DECAY_STEPS,
            "states": decay_states,
        },
        "summary": {
            "controlled_trial_count": len(trials),
            "repeats_per_configuration_command": REPEATS_PER_CONTROL_TRIAL,
            "free_decay_state_count": len(decay_states),
        },
    }


def compatibility_probe() -> dict[str, object]:
    """Exercise model loading, reset, forward dynamics, and a short step."""

    model, context = _load_model_context()
    data = mujoco.MjData(model)
    _reset_state(model, data, context, [0.0, 0.0])
    initial = _snapshot(data)
    command = [0.25, -0.25]
    data.ctrl[:] = np.asarray(command, dtype=float)
    mujoco.mj_step(model, data, nstep=3)
    return {
        "dimensions": {"nq": int(model.nq), "nv": int(model.nv), "nu": int(model.nu)},
        "command": command,
        "physics_steps": 3,
        "initial": initial,
        "after": _snapshot(data),
    }


def measure() -> dict[str, object]:
    model, context = _load_model_context()
    data = mujoco.MjData(model)
    compiled_model = _compiled_facts(model, context)
    kinematics = _ik_measurement(model, data, context)
    jacobian = _jacobian_measurement(model, data, context)
    dynamics = _dynamics_measurement(model, data, context)
    return {
        "schema_version": 1,
        "measurement": "initial_physical_model",
        "deterministic_design": {
            "model_source": "contracts/robots/two_joint_arm.xml",
            "radius_count": GRID_RADIUS_COUNT,
            "azimuth_count": GRID_ANGLE_COUNT,
            "controlled_trial_repeats": REPEATS_PER_CONTROL_TRIAL,
            "control_steps": CONTROL_STEPS,
            "free_decay_steps": FREE_DECAY_STEPS,
        },
        "units": {
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
        },
        "compiled_model": compiled_model,
        "kinematics": kinematics,
        "jacobian": jacobian,
        "dynamics": dynamics,
        "scope": {
            "purpose": (
                "discriminate compiled-plant and sampled-data uncertainty from "
                "the need to study learned-policy coverage"
            ),
            "learned_candidate_used": False,
            "protected_evaluator_semantics_resolved": False,
            "unchecked": [
                "protected evaluator hold semantics",
                "learned-policy coverage or performance",
            ],
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        required=True,
        type=Path,
        help="path of the deterministic JSON artifact to write",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = measure()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    with args.artifact.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
