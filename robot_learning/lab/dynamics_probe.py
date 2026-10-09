"""Characterize the arm's compiled dynamics and initial control response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, TWO_JOINT_ARM_XML_PATH
from contracts.robots.two_joint_arm import UPPER_ARM_LENGTH

FRAME_SKIP = 10
CONTROL_DT = 0.02
RESPONSE_CONTROL_STEPS = 100
ACTION_PROBES = (
    ("shoulder_positive", (1.0, 0.0)),
    ("elbow_positive", (0.0, 1.0)),
    ("coupled_positive", (1.0, 1.0)),
    ("coupled_opposite", (1.0, -1.0)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def body_name(model: mujoco.MjModel, index: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, index) or str(index)


def joint_name(model: mujoco.MjModel, index: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, index) or str(index)


def actuator_name(model: mujoco.MjModel, index: int) -> str:
    return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index) or str(index)


def set_configuration(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: tuple[float, float],
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = qpos
    data.qvel[:2] = 0.0
    mujoco.mj_forward(model, data)


def end_effector_position(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    del model
    return data.site("end_effector").xpos.copy()


def jacobian_summary(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> dict:
    jacobian_position = np.zeros((3, model.nv))
    jacobian_rotation = np.zeros((3, model.nv))
    mujoco.mj_jacSite(
        model, data, jacobian_position, jacobian_rotation, site_id
    )
    planar_jacobian = jacobian_position[:2, :2]
    singular_values = np.linalg.svd(planar_jacobian, compute_uv=False)
    condition_number = (
        float(singular_values[0] / singular_values[-1])
        if singular_values[-1] > 1e-12
        else float("inf")
    )
    return {
        "planar_matrix": planar_jacobian.tolist(),
        "singular_values": singular_values.tolist(),
        "condition_number": condition_number,
    }


def target_configuration(radius: float) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = float(
        -np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return shoulder, elbow


def constrained_ik_summary() -> dict:
    joint_limit = np.deg2rad(170.0)
    radii = np.linspace(0.06, 0.20, 8)
    angles = np.linspace(-np.pi, np.pi, 73)[:-1]
    rows = []
    feasible_counts = {"open": 0, "folded": 0, "any": 0}
    for radius in radii:
        for angle in angles:
            cosine = (
                radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
            ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
            elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
            branch_results = {}
            for branch, elbow in (
                ("open", elbow_open),
                ("folded", -elbow_open),
            ):
                shoulder = float(
                    angle
                    - np.arctan2(
                        FOREARM_LENGTH * np.sin(elbow),
                        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
                    )
                )
                feasible = bool(
                    abs(shoulder) <= joint_limit and abs(elbow) <= joint_limit
                )
                branch_results[branch] = {
                    "shoulder_degrees": float(np.degrees(shoulder)),
                    "elbow_degrees": float(np.degrees(elbow)),
                    "feasible": feasible,
                }
                if feasible:
                    feasible_counts[branch] += 1
            any_feasible = any(
                branch_results[branch]["feasible"] for branch in ("open", "folded")
            )
            if any_feasible:
                feasible_counts["any"] += 1
            rows.append(
                {
                    "radius_m": float(radius),
                    "angle_degrees": float(np.degrees(angle)),
                    "branches": branch_results,
                }
            )
    total = len(rows)
    return {
        "sample_count": total,
        "feasible_counts": feasible_counts,
        "feasible_fractions": {
            key: value / total for key, value in feasible_counts.items()
        },
        "samples": rows,
    }


def response_probe(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: tuple[float, float],
    action_name: str,
    action: tuple[float, float],
    site_id: int,
) -> dict:
    set_configuration(model, data, qpos)
    initial_position = end_effector_position(model, data)
    initial_qpos = data.qpos[:2].copy()
    data.ctrl[:2] = action
    for _ in range(FRAME_SKIP):
        mujoco.mj_step(model, data)
    post_action_position = end_effector_position(model, data)
    post_action_qpos = data.qpos[:2].copy()
    post_action_qvel = data.qvel[:2].copy()
    post_action = {
        "qpos": post_action_qpos.tolist(),
        "qvel": post_action_qvel.tolist(),
        "endpoint_displacement_m": float(
            np.linalg.norm(post_action_position - initial_position)
        ),
        "endpoint_velocity_m_per_s": float(
            np.linalg.norm(post_action_position - initial_position) / CONTROL_DT
        ),
        "jacobian": jacobian_summary(model, data, site_id),
    }

    coast_trace = []
    peak_joint_speed = 0.0
    peak_endpoint_speed = 0.0
    settled_step = None
    previous_position = post_action_position
    data.ctrl[:2] = 0.0
    for control_step in range(1, RESPONSE_CONTROL_STEPS + 1):
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        position = end_effector_position(model, data)
        endpoint_speed = float(
            np.linalg.norm(position - previous_position) / CONTROL_DT
        )
        joint_speed = float(np.linalg.norm(data.qvel[:2]))
        peak_joint_speed = max(peak_joint_speed, joint_speed)
        peak_endpoint_speed = max(peak_endpoint_speed, endpoint_speed)
        if settled_step is None and joint_speed <= 0.01 and endpoint_speed <= 0.01:
            settled_step = control_step
        if control_step in (1, 5, 10, 25, 50, 100):
            coast_trace.append(
                {
                    "control_step": control_step,
                    "qpos": data.qpos[:2].tolist(),
                    "qvel": data.qvel[:2].tolist(),
                    "endpoint_speed_m_per_s": endpoint_speed,
                    "endpoint_displacement_from_start_m": float(
                        np.linalg.norm(position - initial_position)
                    ),
                }
            )
        previous_position = position
    return {
        "configuration_qpos": list(qpos),
        "action_name": action_name,
        "action": list(action),
        "initial_qpos": initial_qpos.tolist(),
        "post_action": post_action,
        "zero_input_response": {
            "peak_joint_speed_rad_per_s": peak_joint_speed,
            "peak_endpoint_speed_m_per_s": peak_endpoint_speed,
            "settled_by_control_step": settled_step,
            "trace": coast_trace,
        },
    }


def main() -> None:
    args = parse_args()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = model.site("end_effector").id

    configurations = {
        "reset_singularity": (0.0, 0.0),
        "representative_radius_0.08": target_configuration(0.08),
        "representative_radius_0.14": target_configuration(0.14),
        "representative_radius_0.20": target_configuration(0.20),
        "elbow_quarter_turn": (0.0, float(np.pi / 2.0)),
    }

    mass_matrix_by_configuration = {}
    jacobian_by_configuration = {}
    for name, qpos in configurations.items():
        set_configuration(model, data, qpos)
        mass_matrix = np.zeros((model.nv, model.nv))
        mujoco.mj_fullM(model, data, mass_matrix)
        mass_matrix_by_configuration[name] = mass_matrix.tolist()
        jacobian_by_configuration[name] = jacobian_summary(model, data, site_id)

    response_results = []
    for configuration_name in ("reset_singularity", "representative_radius_0.14"):
        qpos = configurations[configuration_name]
        for action_name, action in ACTION_PROBES:
            response_results.append(
                {
                    "configuration": configuration_name,
                    "response": response_probe(
                        model, data, qpos, action_name, action, site_id
                    ),
                }
            )

    artifact = {
        "schema_version": 1,
        "measurement": "compiled_dynamics_and_control_response",
        "model": {
            "timestep_s": float(model.opt.timestep),
            "control_period_s": float(model.opt.timestep * FRAME_SKIP),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "body_mass_kg": {
                body_name(model, index): float(model.body_mass[index])
                for index in range(model.nbody)
            },
            "body_inertia": {
                body_name(model, index): model.body_inertia[index].tolist()
                for index in range(model.nbody)
            },
            "joint_damping": {
                joint_name(model, index): float(model.dof_damping[model.jnt_dofadr[index]])
                for index in range(model.njnt)
            },
            "joint_armature": {
                joint_name(model, index): float(
                    model.dof_armature[model.jnt_dofadr[index]]
                )
                for index in range(model.njnt)
            },
            "actuator_gear": {
                actuator_name(model, index): model.actuator_gear[index].tolist()
                for index in range(model.nu)
            },
            "actuator_ctrlrange": {
                actuator_name(model, index): model.actuator_ctrlrange[index].tolist()
                for index in range(model.nu)
            },
        },
        "constrained_ik": constrained_ik_summary(),
        "configurations": {
            name: {"qpos": list(qpos)} for name, qpos in configurations.items()
        },
        "mass_matrix_by_configuration": mass_matrix_by_configuration,
        "jacobian_by_configuration": jacobian_by_configuration,
        "response_trials": response_results,
    }
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
