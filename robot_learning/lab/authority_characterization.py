"""Characterize runtime dynamics and authority at staged-transfer residuals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.evaluation import evaluate_research_model


RESIDUAL_TARGETS = (
    {"band": "inner", "radius_cm": 10.657031564769065, "angle_degrees": -129.85988481026186},
    {"band": "outer", "radius_cm": 18.351506861749815, "angle_degrees": -150.61959017892283},
    {"band": "inner", "radius_cm": 10.853930142929325, "angle_degrees": -129.95065529343904},
    {"band": "outer", "radius_cm": 17.486787366282112, "angle_degrees": -148.37747616508878},
)
RESIDUAL_SEEDS = (4208, 4246, 4307, 4316)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Characterize authority at staged-transfer residual targets"
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    return parser.parse_args()


def target_position(radius_cm: float, angle_degrees: float) -> np.ndarray:
    angle = np.deg2rad(angle_degrees)
    return np.array(
        [radius_cm / 100.0 * np.cos(angle), radius_cm / 100.0 * np.sin(angle), 0.02],
        dtype=np.float64,
    )


def ik_solution(target: np.ndarray, elbow_sign: int) -> np.ndarray:
    radius = float(np.hypot(target[0], target[1]))
    cosine = (radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2) / (
        2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH
    )
    q2_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    q2 = elbow_sign * q2_magnitude
    q1 = float(
        np.arctan2(target[1], target[0])
        - np.arctan2(
            FOREARM_LENGTH * np.sin(q2),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(q2),
        )
    )
    return np.array([q1, q2], dtype=np.float64)


def jacobian(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    position = np.zeros((3, model.nv), dtype=np.float64)
    rotation = np.zeros((3, model.nv), dtype=np.float64)
    mujoco.mj_jacSite(model, data, position, rotation, data.site("end_effector").id)
    return position[:2, :2].copy()


def full_mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    mass = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, data, mass)
    return mass


def dynamics_snapshot(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target: np.ndarray,
    control: np.ndarray,
) -> dict:
    saved_qpos = data.qpos.copy()
    saved_qvel = data.qvel.copy()
    saved_mocap = data.mocap_pos.copy()
    saved_ctrl = data.ctrl.copy()

    data.mocap_pos[:] = target
    data.ctrl[:] = np.asarray(control, dtype=np.float64)
    mujoco.mj_forward(model, data)
    actual_qacc = data.qacc[:2].copy()
    actual_torque = data.qfrc_actuator[:2].copy()
    mass = full_mass_matrix(model, data)
    endpoint_jacobian = jacobian(model, data)
    data.ctrl[:] = np.zeros(model.nu, dtype=np.float64)
    mujoco.mj_forward(model, data)
    zero_torque = data.qfrc_actuator[:2].copy()
    torque_columns = []
    acceleration_columns = []
    for actuator_index in range(model.nu):
        probe = np.zeros(model.nu, dtype=np.float64)
        probe[actuator_index] = 1.0
        data.ctrl[:] = probe
        mujoco.mj_forward(model, data)
        torque_columns.append(data.qfrc_actuator[:2].copy() - zero_torque)
        acceleration_columns.append(np.zeros(2, dtype=np.float64))

    control_torque_map = np.column_stack(torque_columns)
    data.ctrl[:] = np.zeros(model.nu, dtype=np.float64)
    mujoco.mj_forward(model, data)
    zero_acceleration = data.qacc[:2].copy()
    for actuator_index in range(model.nu):
        probe = np.zeros(model.nu, dtype=np.float64)
        probe[actuator_index] = 1.0
        data.ctrl[:] = probe
        mujoco.mj_forward(model, data)
        acceleration_columns[actuator_index] = data.qacc[:2].copy() - zero_acceleration
    control_acceleration_map = np.column_stack(acceleration_columns)

    data.qpos[:] = saved_qpos
    data.qvel[:] = saved_qvel
    data.mocap_pos[:] = saved_mocap
    data.ctrl[:] = saved_ctrl
    mujoco.mj_forward(model, data)

    endpoint = data.site("end_effector").xpos[:2].copy()
    error = target[:2] - endpoint
    error_norm = float(np.linalg.norm(error))
    error_direction = error / error_norm if error_norm > 0.0 else np.zeros(2)
    target_direction = target[:2] / max(float(np.linalg.norm(target[:2])), 1e-12)
    tangent_direction = np.array([-target_direction[1], target_direction[0]])
    endpoint_acceleration_map = endpoint_jacobian @ np.linalg.solve(
        mass[:2, :2], control_torque_map
    )
    attainable_endpoint_acceleration = endpoint_jacobian @ np.linalg.solve(
        mass[:2, :2], control_acceleration_map
    )
    directional_columns = attainable_endpoint_acceleration.T @ error_direction
    directional_authority = float(np.sum(np.abs(directional_columns)))
    reserve = np.maximum(0.0, 1.0 - np.abs(control))

    return {
        "qpos_rad": saved_qpos[:2].tolist(),
        "qvel_rad_s": saved_qvel[:2].tolist(),
        "endpoint_error_cm": (100.0 * error).tolist(),
        "endpoint_error_norm_cm": 100.0 * error_norm,
        "actual_qacc_rad_s2": actual_qacc.tolist(),
        "actual_actuator_torque": actual_torque.tolist(),
        "control": np.asarray(control, dtype=np.float64).tolist(),
        "control_reserve": reserve.tolist(),
        "min_control_reserve": float(np.min(reserve)),
        "endpoint_acceleration_map": endpoint_acceleration_map.tolist(),
        "attainable_endpoint_acceleration_map": attainable_endpoint_acceleration.tolist(),
        "endpoint_acceleration_singular_values": np.linalg.svd(
            attainable_endpoint_acceleration, compute_uv=False
        ).tolist(),
        "directional_authority_m_s2": directional_authority,
        "radial_authority_m_s2": float(
            np.sum(np.abs(attainable_endpoint_acceleration.T @ target_direction))
        ),
        "tangential_authority_m_s2": float(
            np.sum(np.abs(attainable_endpoint_acceleration.T @ tangent_direction))
        ),
        "actual_endpoint_acceleration_from_jacobian_qacc_m_s2": (
            endpoint_jacobian @ actual_qacc
        ).tolist(),
        "mass_matrix": mass[:2, :2].tolist(),
        "endpoint_jacobian": endpoint_jacobian.tolist(),
        "jacobian_determinant_m2": float(
            UPPER_ARM_LENGTH * FOREARM_LENGTH * np.sin(saved_qpos[1])
        ),
    }


def runtime_model_summary(model: mujoco.MjModel) -> dict:
    body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_index)
        or str(body_index)
        for body_index in range(model.nbody)
    ]
    actuator_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_index)
        or str(actuator_index)
        for actuator_index in range(model.nu)
    ]
    return {
        "timestep_s": float(model.opt.timestep),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "body_names": body_names,
        "body_mass_kg": model.body_mass.tolist(),
        "body_inertia": model.body_inertia.tolist(),
        "dof_damping": model.dof_damping.tolist(),
        "dof_armature": model.dof_armature.tolist(),
        "actuator_names": actuator_names,
        "actuator_gear": model.actuator_gear.tolist(),
        "actuator_ctrlrange": model.actuator_ctrlrange.tolist(),
    }


def characterize_target(model: mujoco.MjModel, target_spec: dict, elbow_sign: int) -> dict:
    target = target_position(target_spec["radius_cm"], target_spec["angle_degrees"])
    data = mujoco.MjData(model)
    qpos = ik_solution(target, elbow_sign)
    data.qpos[:2] = qpos
    data.qvel[:] = 0.0
    data.mocap_pos[0] = target
    mujoco.mj_forward(model, data)
    snapshot = dynamics_snapshot(model, data, target, np.zeros(model.nu))
    snapshot.update(
        {
            "band": target_spec["band"],
            "target_radius_cm": target_spec["radius_cm"],
            "target_angle_degrees": target_spec["angle_degrees"],
            "target_position_m": target.tolist(),
            "ik_branch": "positive" if elbow_sign > 0 else "negative",
            "ik_qpos_rad": qpos.tolist(),
        }
    )
    return snapshot


def characterize_policy_episode(
    model: mujoco.MjModel,
    runtime,
    seed: int,
) -> dict:
    env = make_evaluation_env(policy_runtime=runtime)
    obs, _ = env.reset(seed=seed)
    runtime.reset()
    target = env.data.mocap_pos[0].copy()
    trajectory = []
    terminated = False
    truncated = False
    while not (terminated or truncated):
        action = np.asarray(runtime.predict(obs), dtype=np.float64).reshape(-1)
        applied_action = np.clip(action, -1.0, 1.0)
        endpoint_before = env.data.site("end_effector").xpos.copy()
        obs, _, terminated, truncated, info = env.step(action)
        endpoint_after = env.data.site("end_effector").xpos.copy()
        snapshot = dynamics_snapshot(env.model, env.data, target, applied_action)
        snapshot.update(
            {
                "step": len(trajectory) + 1,
                "distance_cm": 100.0 * float(info["distance"]),
                "endpoint_speed_m_s": float(
                    np.linalg.norm(endpoint_after - endpoint_before)
                    / (env.model.opt.timestep * env.frame_skip)
                ),
                "held_steps": int(info["held_steps"]),
                "saturated": bool(np.any(np.abs(applied_action) >= 1.0 - 1e-6)),
            }
        )
        trajectory.append(snapshot)

    return {
        "episode_seed": seed,
        "target_radius_cm": float(np.hypot(target[0], target[1]) * 100.0),
        "target_angle_degrees": float(np.degrees(np.arctan2(target[1], target[0]))),
        "success": bool(terminated and trajectory[-1]["held_steps"] >= 100),
        "steps": len(trajectory),
        "trajectory": trajectory,
    }


def main() -> None:
    args = parse_args()
    if args.episodes < 1:
        raise ValueError("episodes must be positive")

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    panel_evaluation = evaluate_research_model(
        args.model, episodes=args.episodes, seed=args.seed
    )
    runtime = load_runtime(args.model)
    policy_trajectories = [
        characterize_policy_episode(model, runtime, seed) for seed in RESIDUAL_SEEDS
    ]

    representative_configurations = [
        characterize_target(model, target_spec, elbow_sign)
        for target_spec in RESIDUAL_TARGETS
        for elbow_sign in (1, -1)
    ]
    artifact = {
        "schema_version": 1,
        "experiment": "staged_transfer_residual_authority_characterization",
        "model": str(args.model),
        "panel_evaluation": panel_evaluation,
        "runtime_model": runtime_model_summary(model),
        "representative_configurations": representative_configurations,
        "policy_trajectory_characterization": {
            "candidate": str(args.model),
            "episode_seeds": list(RESIDUAL_SEEDS),
            "episodes": policy_trajectories,
        },
        "interpretation_inputs": {
            "residual_target_source": "M4 T3:checkpoint-120832 no-first-entry rows",
            "trajectory_source": "replayed fixed development panel seeds",
            "authority_definition": (
                "Maximum instantaneous endpoint acceleration per normalized actuator "
                "command at the runtime state, with control reserve reported separately"
            ),
            "complete_hold_semantics": "100 consecutive 20 ms control samples",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
