"""Candidate-free plant and kinematic characterization for the arm task."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import FRAME_SKIP


def _shoulder_for_elbow(target_angle: float, elbow: float) -> float:
    return float(
        target_angle
        - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )


def _ik_solution(radius: float, target_angle: float, branch: str) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    elbow = elbow_magnitude if branch == "open" else -elbow_magnitude
    return _shoulder_for_elbow(target_angle, elbow), elbow


def _forward_kinematics(qpos: np.ndarray) -> np.ndarray:
    q1, q2 = qpos
    return np.array(
        [
            UPPER_ARM_LENGTH * np.cos(q1)
            + FOREARM_LENGTH * np.cos(q1 + q2),
            UPPER_ARM_LENGTH * np.sin(q1)
            + FOREARM_LENGTH * np.sin(q1 + q2),
        ],
        dtype=np.float64,
    )


def _joint_limit_margin(model: mujoco.MjModel, qpos: np.ndarray) -> float:
    margins = np.minimum(
        qpos - model.jnt_range[:2, 0],
        model.jnt_range[:2, 1] - qpos,
    )
    return float(np.min(margins))


def _branch_catalog(model: mujoco.MjModel) -> list[dict]:
    records = []
    radii = np.linspace(0.06, 0.20, 8)
    angles = np.linspace(-np.pi, np.pi, 17)[:-1]
    for radius in radii:
        for angle in angles:
            target = radius * np.array([np.cos(angle), np.sin(angle)])
            for branch in ("open", "folded"):
                qpos = np.asarray(_ik_solution(float(radius), float(angle), branch))
                residual = float(np.linalg.norm(_forward_kinematics(qpos) - target))
                jacobian = np.array(
                    [
                        [
                            -UPPER_ARM_LENGTH * np.sin(qpos[0])
                            - FOREARM_LENGTH * np.sin(qpos.sum()),
                            -FOREARM_LENGTH * np.sin(qpos.sum()),
                        ],
                        [
                            UPPER_ARM_LENGTH * np.cos(qpos[0])
                            + FOREARM_LENGTH * np.cos(qpos.sum()),
                            FOREARM_LENGTH * np.cos(qpos.sum()),
                        ],
                    ]
                )
                records.append(
                    {
                        "radius_m": float(radius),
                        "target_angle_degrees": float(np.degrees(angle)),
                        "branch": branch,
                        "qpos_radians": qpos.tolist(),
                        "residual_m": residual,
                        "minimum_joint_limit_margin_degrees": float(
                            np.degrees(_joint_limit_margin(model, qpos))
                        ),
                        "jacobian_singular_values": np.linalg.svd(
                            jacobian, compute_uv=False
                        ).tolist(),
                    }
                )
    return records


def _model_summary(model: mujoco.MjModel) -> dict:
    body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, index)
        for index in range(model.nbody)
    ]
    return {
        "timestep_s": float(model.opt.timestep),
        "frame_skip": FRAME_SKIP,
        "control_period_s": float(model.opt.timestep * FRAME_SKIP),
        "integrator": int(model.opt.integrator),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "body_names": body_names,
        "body_mass_kg": model.body_mass.tolist(),
        "body_inertia": model.body_inertia.tolist(),
        "joint_damping": model.dof_damping[:2].tolist(),
        "joint_armature": model.dof_armature[:2].tolist(),
        "joint_ranges_radians": model.jnt_range[:2].tolist(),
        "actuator_gear": model.actuator_gear.tolist(),
        "actuator_ctrlrange": model.actuator_ctrlrange.tolist(),
    }


def _end_effector_speed(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    jacobian_position = np.zeros((3, model.nv))
    jacobian_rotation = np.zeros((3, model.nv))
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    mujoco.mj_jacSite(
        model, data, jacobian_position, jacobian_rotation, site_id
    )
    return float(np.linalg.norm(jacobian_position @ data.qvel))


def _pulse_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    joint: int,
    sign: int,
    pulse_control_steps: int,
    release_control_steps: int,
) -> dict:
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    initial_ee = data.site("end_effector").xpos[:2].copy()
    control_dt = model.opt.timestep * FRAME_SKIP
    trace = []

    for control_step in range(pulse_control_steps + release_control_steps):
        data.ctrl[:] = 0.0
        if control_step < pulse_control_steps:
            data.ctrl[joint] = float(sign)
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        ee_position = data.site("end_effector").xpos[:2].copy()
        trace.append(
            {
                "control_step": control_step + 1,
                "phase": "pulse" if control_step < pulse_control_steps else "release",
                "qpos_radians": data.qpos[:2].tolist(),
                "qvel_radians_per_s": data.qvel[:2].tolist(),
                "ee_position_m": ee_position.tolist(),
                "ee_speed_m_per_s": _end_effector_speed(model, data),
            }
        )

    pulse_end = np.asarray(trace[pulse_control_steps - 1]["ee_position_m"])
    final_position = np.asarray(trace[-1]["ee_position_m"])
    release_positions = np.asarray(
        [entry["ee_position_m"] for entry in trace[pulse_control_steps:]]
    )
    return {
        "joint": joint,
        "sign": sign,
        "pulse_control_steps": pulse_control_steps,
        "release_control_steps": release_control_steps,
        "initial_qpos_radians": qpos.tolist(),
        "initial_ee_position_m": initial_ee.tolist(),
        "estimated_mean_acceleration_radians_per_s2": (
            np.asarray(trace[0]["qvel_radians_per_s"]) / control_dt
        ).tolist(),
        "peak_abs_joint_velocity_radians_per_s": float(
            np.max(
                np.abs(
                    np.asarray(
                        [entry["qvel_radians_per_s"] for entry in trace]
                    )
                )
            )
        ),
        "peak_ee_speed_m_per_s": float(
            max(entry["ee_speed_m_per_s"] for entry in trace)
        ),
        "post_pulse_ee_travel_m": float(
            np.max(np.linalg.norm(release_positions - pulse_end, axis=1))
        ),
        "post_pulse_final_qvel_radians_per_s": trace[-1][
            "qvel_radians_per_s"
        ],
        "post_pulse_final_ee_displacement_m": float(
            np.linalg.norm(final_position - pulse_end)
        ),
        "trace": trace,
    }


def measure(
    *,
    pulse_control_steps: int = 1,
    release_control_steps: int = 20,
) -> dict:
    if pulse_control_steps < 1 or release_control_steps < 1:
        raise ValueError("pulse and release durations must be positive")

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    configurations = [
        {"label": "straight_reset", "qpos_radians": [0.0, 0.0]},
    ]
    for radius in (0.06, 0.13, 0.20):
        for branch in ("open", "folded"):
            qpos = _ik_solution(radius, 0.0, branch)
            configurations.append(
                {
                    "label": f"radius_{radius:.2f}_{branch}",
                    "radius_m": radius,
                    "branch": branch,
                    "qpos_radians": list(qpos),
                }
            )

    pulse_results = []
    for configuration in configurations:
        qpos = np.asarray(configuration["qpos_radians"], dtype=np.float64)
        for joint in range(2):
            for sign in (-1, 1):
                pulse_results.append(
                    {
                        "configuration": configuration,
                        "response": _pulse_trial(
                            model,
                            data,
                            qpos,
                            joint,
                            sign,
                            pulse_control_steps,
                            release_control_steps,
                        ),
                    }
                )

    return {
        "schema_version": 1,
        "measurement": "two_joint_arm_plant_dynamics_and_kinematics",
        "protocol": {
            "kinematic_radii_m": [0.06, 0.20],
            "kinematic_angle_samples": 16,
            "pulse_command": "one actuator at signed full control, then zero",
            "pulse_control_steps": pulse_control_steps,
            "release_control_steps": release_control_steps,
            "sample_period_s": float(model.opt.timestep * FRAME_SKIP),
        },
        "model": _model_summary(model),
        "kinematic_branch_catalog": _branch_catalog(model),
        "pulse_responses": pulse_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--pulse-control-steps", type=int, default=1)
    parser.add_argument("--release-control-steps", type=int, default=20)
    args = parser.parse_args()

    result = measure(
        pulse_control_steps=args.pulse_control_steps,
        release_control_steps=args.release_control_steps,
    )
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
