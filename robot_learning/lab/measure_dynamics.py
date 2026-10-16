"""Measure isolated actuator pulses on the contract two-joint arm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv


SCHEMA_VERSION = "1.0"
DEFAULT_EPISODES = 4
DEFAULT_SEED = 0
DEFAULT_RECOVERY_FRAMES = 10

PROBE_ACTIONS = (
    ("shoulder_positive", (1.0, 0.0)),
    ("shoulder_negative", (-1.0, 0.0)),
    ("elbow_positive", (0.0, 1.0)),
    ("elbow_negative", (0.0, -1.0)),
)


def _json_vector(values: Iterable[Any]) -> list[float]:
    """Convert a numeric array to ordinary JSON number values."""
    return [float(value) for value in np.asarray(values).reshape(-1)]


def _model_name(model: mujoco.MjModel, object_name: str, index: int) -> str:
    addresses = getattr(model, f"name_{object_name}adr")
    address = int(addresses[index])
    names = bytes(model.names)
    return names[address:].split(b"\x00", 1)[0].decode("utf-8")


def _compiled_model_snapshot(model: mujoco.MjModel) -> dict[str, Any]:
    joints: list[dict[str, Any]] = []
    dofs: list[dict[str, Any]] = []
    for joint_id in range(int(model.njnt)):
        joint_name = _model_name(model, "jnt", joint_id)
        dof_address = int(model.jnt_dofadr[joint_id])
        joints.append(
            {
                "name": joint_name,
                "range": _json_vector(model.jnt_range[joint_id]),
                "qpos_address": int(model.jnt_qposadr[joint_id]),
                "dof_address": dof_address,
            }
        )
        dofs.append(
            {
                "joint_name": joint_name,
                "dof_address": dof_address,
                "damping": float(model.dof_damping[dof_address]),
                "armature": float(model.dof_armature[dof_address]),
            }
        )

    bodies = [
        {
            "name": _model_name(model, "body", body_id),
            "mass": float(model.body_mass[body_id]),
            "inertia": _json_vector(model.body_inertia[body_id]),
        }
        for body_id in range(int(model.nbody))
    ]

    actuators = []
    actuator_count = len(model.actuator_ctrlrange)
    for actuator_id in range(actuator_count):
        actuators.append(
            {
                "name": _model_name(model, "actuator", actuator_id),
                "ctrl_range": _json_vector(model.actuator_ctrlrange[actuator_id]),
                "ctrl_spec": _json_vector(model.actuator_ctrlspec[actuator_id]),
                "gear": _json_vector(model.actuator_gear[actuator_id]),
                "force_range": _json_vector(model.actuator_forcerange[actuator_id]),
                "ctrl_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "force_limited": bool(model.actuator_forcelimited[actuator_id]),
                "gain_type": int(model.actuator_gaintype[actuator_id]),
                "gain_parameters": _json_vector(
                    model.actuator_gainprm[actuator_id]
                ),
                "bias_type": int(model.actuator_biastype[actuator_id]),
                "bias_parameters": _json_vector(
                    model.actuator_biasprm[actuator_id]
                ),
                "dynamics_type": int(model.actuator_dyntype[actuator_id]),
                "dynamics_parameters": _json_vector(
                    model.actuator_dynprm[actuator_id]
                ),
            }
        )

    return {
        "name": "two_joint_arm",
        "timestep": float(model.opt.timestep),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "joints": joints,
        "dofs": dofs,
        "bodies": bodies,
        "actuators": actuators,
    }


def _target_components(
    target: np.ndarray,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    target_xy = np.asarray(target[:2], dtype=np.float64)
    radius = float(np.linalg.norm(target_xy))
    angle = float(np.arctan2(target_xy[1], target_xy[0]))
    radial_basis = target_xy / radius
    tangential_basis = np.array(
        [-radial_basis[1], radial_basis[0]], dtype=np.float64
    )
    return radius, angle, radial_basis, tangential_basis


def _site_velocity(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> np.ndarray:
    jacobian = np.zeros((3, int(model.nv)), dtype=np.float64)
    mujoco.mj_jacSite(model, data, jacobian, None, site_id)
    return jacobian @ np.asarray(data.qvel)


def _state_sample(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    target: np.ndarray,
    radial_basis: np.ndarray,
    tangential_basis: np.ndarray,
    control_frame_index: int,
    substep_index: int,
    control: np.ndarray,
    sample_index: int,
) -> dict[str, Any]:
    site_position = np.asarray(data.site_xpos[site_id]).copy()
    site_velocity = _site_velocity(model, data, site_id)
    target_distance = float(np.linalg.norm(site_position - target))
    radial_velocity = float(np.dot(site_velocity[:2], radial_basis))
    tangential_velocity = float(np.dot(site_velocity[:2], tangential_basis))
    return {
        "sample_index": sample_index,
        "time": float(data.time),
        "control_frame_index": control_frame_index,
        "substep_index": substep_index,
        "qpos": _json_vector(data.qpos),
        "qvel": _json_vector(data.qvel),
        "qacc": _json_vector(data.qacc),
        "qfrc_actuator": _json_vector(data.qfrc_actuator),
        "actuator_force": _json_vector(data.actuator_force),
        "end_effector_position": _json_vector(site_position),
        "end_effector_velocity": _json_vector(site_velocity),
        "target_distance": target_distance,
        "radial_velocity": radial_velocity,
        "tangential_velocity": tangential_velocity,
        "control": _json_vector(control),
    }


def _reset_values(
    data: mujoco.MjData, site_id: int, target: np.ndarray
) -> dict[str, Any]:
    return {
        "qpos": _json_vector(data.qpos),
        "qvel": _json_vector(data.qvel),
        "site_position": _json_vector(data.site_xpos[site_id]),
        "target_position": _json_vector(target),
    }


def _probe_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    first_sample = samples[0]
    final_sample = samples[-1]
    return {
        "first_pulse_actuator_force": first_sample["actuator_force"],
        "first_pulse_actuator_force_by_actuator": first_sample["actuator_force"],
        "first_pulse_qfrc_actuator": first_sample["qfrc_actuator"],
        "first_pulse_radial_velocity": first_sample["radial_velocity"],
        "first_pulse_tangential_velocity": first_sample["tangential_velocity"],
        "peak_abs_qvel": [
            max(abs(sample["qvel"][index]) for sample in samples)
            for index in range(len(first_sample["qvel"]))
        ],
        "peak_abs_qacc": [
            max(abs(sample["qacc"][index]) for sample in samples)
            for index in range(len(first_sample["qacc"]))
        ],
        "peak_abs_actuator_force": [
            max(abs(sample["actuator_force"][index]) for sample in samples)
            for index in range(len(first_sample["actuator_force"]))
        ],
        "peak_abs_qfrc_actuator": [
            max(abs(sample["qfrc_actuator"][index]) for sample in samples)
            for index in range(len(first_sample["qfrc_actuator"]))
        ],
        "minimum_target_distance": min(
            sample["target_distance"] for sample in samples
        ),
        "final_state": {
            "qpos": final_sample["qpos"],
            "qvel": final_sample["qvel"],
            "qacc": final_sample["qacc"],
            "qfrc_actuator": final_sample["qfrc_actuator"],
            "actuator_force": final_sample["actuator_force"],
            "end_effector_position": final_sample["end_effector_position"],
            "end_effector_velocity": final_sample["end_effector_velocity"],
            "target_distance": final_sample["target_distance"],
            "control": final_sample["control"],
        },
    }


def _run_probe(
    env: TwoJointArmReachEnv,
    episode_seed: int,
    action_name: str,
    action_values: tuple[float, float],
    recovery_frames: int,
    site_id: int,
) -> dict[str, Any]:
    _, _ = env.reset(seed=episode_seed)
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    reset = _reset_values(env.data, site_id, target)
    target_radius, target_angle, radial_basis, tangential_basis = _target_components(
        target
    )

    action = np.asarray(action_values, dtype=np.float64)
    zero_control = np.zeros_like(action)
    samples: list[dict[str, Any]] = []
    sample_index = 0
    for control_frame_index in range(recovery_frames + 1):
        control = action if control_frame_index == 0 else zero_control
        env.data.ctrl[:] = control
        # One policy control frame contains frame_skip separate MuJoCo substeps.
        for substep_index in range(env.frame_skip):
            mujoco.mj_step(env.model, env.data)
            # Recompute dynamics at the integrated endpoint so qacc and both
            # force spaces share the timestamped qpos and qvel below.
            mujoco.mj_forward(env.model, env.data)
            samples.append(
                _state_sample(
                    env.model,
                    env.data,
                    site_id,
                    target,
                    radial_basis,
                    tangential_basis,
                    control_frame_index,
                    substep_index,
                    control,
                    sample_index,
                )
            )
            sample_index += 1

    return {
        "name": action_name,
        "control": _json_vector(action),
        "reset": reset,
        "target_radius": target_radius,
        "target_angle": target_angle,
        "target_position": _json_vector(target),
        "samples": samples,
        "summary": _probe_summary(samples),
    }


def build_artifact(
    *,
    episodes: int = DEFAULT_EPISODES,
    seed: int = DEFAULT_SEED,
    recovery_frames: int = DEFAULT_RECOVERY_FRAMES,
) -> dict[str, Any]:
    """Run the deterministic pulse protocol and return its JSON-ready artifact."""
    if episodes <= 0:
        raise ValueError("episodes must be a positive integer")
    if recovery_frames < 0:
        raise ValueError("recovery_frames must be a non-negative integer")
    if seed < 0 or seed > np.iinfo(np.uint32).max:
        raise ValueError("seed must be in [0, 4294967295]")
    if episodes - 1 > np.iinfo(np.uint32).max - seed:
        raise ValueError("seed plus episode index exceeds the supported seed range")

    env = TwoJointArmReachEnv()
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise RuntimeError("compiled model is missing the end_effector site")
    if len(env.data.ctrl) != len(PROBE_ACTIONS[0][1]):
        raise RuntimeError("compiled model does not have the two expected controls")

    episode_records: list[dict[str, Any]] = []
    for episode_index in range(episodes):
        episode_seed = seed + episode_index
        probes = [
            _run_probe(
                env,
                episode_seed,
                action_name,
                action_values,
                recovery_frames,
                site_id,
            )
            for action_name, action_values in PROBE_ACTIONS
        ]
        first_probe = probes[0]
        episode_records.append(
            {
                "episode_index": episode_index,
                "seed": episode_seed,
                "target_radius": first_probe["target_radius"],
                "target_angle": first_probe["target_angle"],
                "target_position": first_probe["target_position"],
                "reset": first_probe["reset"],
                "probes": probes,
            }
        )

    model = env.model
    integration_timestep = float(model.opt.timestep)
    return {
        "protocol": {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "episode_count": episodes,
            "recovery_frames": recovery_frames,
            "integration_timestep": integration_timestep,
            "control_timestep": integration_timestep * env.frame_skip,
            "frame_skip": env.frame_skip,
            "pulse_duration": integration_timestep * env.frame_skip,
            "probe_action_set": [
                {"name": name, "control": list(control)}
                for name, control in PROBE_ACTIONS
            ],
            "velocity_basis": {
                "radial": "projection onto the target polar-radius direction from the base",
                "tangential": "projection onto the counter-clockwise target polar-angle direction",
            },
        },
        "compiled_model": _compiled_model_snapshot(model),
        "episodes": episode_records,
    }


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def _nonnegative_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def _seed_int(raw: str) -> int:
    value = _nonnegative_int(raw)
    if value > np.iinfo(np.uint32).max:
        raise argparse.ArgumentTypeError("must be at most 4294967295")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure isolated saturated pulses on the two-joint arm."
    )
    parser.add_argument("output_path", help="path for the JSON artifact")
    parser.add_argument(
        "--episodes", type=_positive_int, default=DEFAULT_EPISODES, metavar="N"
    )
    parser.add_argument(
        "--seed", type=_seed_int, default=DEFAULT_SEED, metavar="S"
    )
    parser.add_argument(
        "--recovery-frames",
        type=_nonnegative_int,
        default=DEFAULT_RECOVERY_FRAMES,
        metavar="N",
    )
    args = parser.parse_args(argv)
    if not args.output_path.strip():
        parser.error("output_path must not be empty")

    artifact = build_artifact(
        episodes=args.episodes,
        seed=args.seed,
        recovery_frames=args.recovery_frames,
    )
    output_path = Path(args.output_path)
    artifact_text = json.dumps(artifact, indent=2, allow_nan=False)
    output_path.write_text(artifact_text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
