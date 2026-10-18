"""Record control-step trajectories for a saved policy on a reference panel.

This is a research characterization instrument. Its control-step samples do
not establish protected within-step occupancy or official task success.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.environment import make_evaluation_env


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _nonnegative_scalar(value: Any, label: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise ValueError(f"{label} must be a finite nonnegative scalar")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{label} must be a finite nonnegative scalar")
    return number


def _read_reference(path: Path, *, seed: int, episodes: int) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as handle:
            reference = json.load(
                handle,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid reference JSON in {path}: {exc}") from exc

    reference = _mapping(reference, "reference artifact")
    if _integer(reference.get("schema_version"), "reference schema_version") != 5:
        raise ValueError("reference artifact must use research-evaluation schema 5")
    if _integer(reference.get("seed"), "reference seed", minimum=0) != seed:
        raise ValueError("reference seed does not match the requested seed")
    if (
        _integer(reference.get("episodes"), "reference episodes", minimum=1)
        != episodes
    ):
        raise ValueError("reference episode count does not match the requested count")
    if reference.get("official_benchmark") is not False:
        raise ValueError("reference artifact must be a research evaluation")

    research_evidence = _mapping(
        reference.get("research_evidence"), "reference research_evidence"
    )
    units = _mapping(research_evidence.get("units"), "reference units")
    if units.get("distance") != "cm" or units.get("time") != "control_steps":
        raise ValueError("reference target diagnostics must use cm and control_steps")

    results = _array(reference.get("episode_results"), "reference episode_results")
    diagnostics = _array(
        research_evidence.get("episode_diagnostics"),
        "reference episode_diagnostics",
    )
    if len(results) != episodes or len(diagnostics) != episodes:
        raise ValueError("reference episode rows do not match the requested count")

    target_min_cm = 100.0 * TARGET_RADIUS_RANGE[0]
    target_max_cm = 100.0 * TARGET_RADIUS_RANGE[1]
    rows = []
    for episode in range(episodes):
        expected_seed = seed + episode
        result = _mapping(results[episode], f"reference result {episode}")
        diagnostic = _mapping(diagnostics[episode], f"reference diagnostic {episode}")
        for row, label in (
            (result, "result"),
            (diagnostic, "diagnostic"),
        ):
            if _integer(row.get("episode"), f"reference {label} episode") != episode:
                raise ValueError(f"reference {label} episode index is inconsistent")
            if (
                _integer(row.get("episode_seed"), f"reference {label} episode_seed")
                != expected_seed
            ):
                raise ValueError(f"reference {label} seed is inconsistent")

        success = result.get("success")
        if not isinstance(success, bool):
            raise ValueError(f"reference result {episode} success must be boolean")
        steps = _integer(
            result.get("steps"), f"reference result {episode} steps", minimum=1
        )
        if steps > MAX_EPISODE_STEPS:
            raise ValueError(f"reference result {episode} exceeds the episode limit")
        terminated = result.get("terminated")
        truncated = result.get("truncated")
        if not isinstance(terminated, bool) or not isinstance(truncated, bool):
            raise ValueError(
                f"reference result {episode} termination flags must be boolean"
            )
        if success is not terminated:
            raise ValueError(
                f"reference result {episode} success and termination disagree"
            )
        if truncated is not (steps == MAX_EPISODE_STEPS):
            raise ValueError(
                f"reference result {episode} truncation flag and step count disagree"
            )
        if not (terminated or truncated):
            raise ValueError(f"reference result {episode} has no terminal condition")

        radius_cm = _finite_number(
            diagnostic.get("target_radius_cm"),
            f"reference diagnostic {episode} target_radius_cm",
        )
        if not target_min_cm <= radius_cm <= target_max_cm:
            raise ValueError(f"reference target radius for episode {episode} is invalid")
        angle_degrees = _finite_number(
            diagnostic.get("target_angle_degrees"),
            f"reference diagnostic {episode} target_angle_degrees",
        )
        if not -180.0 <= angle_degrees <= 180.0:
            raise ValueError(f"reference target angle for episode {episode} is invalid")
        first_reach_step = diagnostic.get("first_reach_step")
        if first_reach_step is not None:
            first_reach_step = _integer(
                first_reach_step,
                f"reference diagnostic {episode} first_reach_step",
                minimum=1,
            )
            if first_reach_step > steps:
                raise ValueError(
                    f"reference first-reach step exceeds episode {episode} length"
                )
        if success and first_reach_step is None:
            raise ValueError(
                f"successful reference episode {episode} has no first-reach step"
            )
        rows.append(
            {
                "episode_seed": expected_seed,
                "target_radius_cm": radius_cm,
                "target_angle_degrees": angle_degrees,
                "success": success,
                "first_reach_step": first_reach_step,
                "steps": steps,
                "terminated": terminated,
                "truncated": truncated,
            }
        )
    return rows


def _named_id(model: mujoco.MjModel, object_type: Any, name: str) -> int:
    object_id = mujoco.mj_name2id(model, object_type, name)
    if object_id < 0:
        raise ValueError(f"required MuJoCo model object is missing: {name}")
    return int(object_id)


def _model_layout(env) -> dict[str, Any]:
    model = env.model
    joint_names = ("shoulder", "elbow")
    joint_ids = np.array(
        [
            _named_id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
            for name in joint_names
        ],
        dtype=np.intp,
    )
    if model.nq != 2 or model.nv != 2 or model.nu != 2:
        raise ValueError("the trace instrument requires the two-joint arm model")
    if not np.all(model.jnt_type[joint_ids] == mujoco.mjtJoint.mjJNT_HINGE):
        raise ValueError("the arm joints must be hinges")

    qpos_indices = np.asarray(model.jnt_qposadr[joint_ids], dtype=np.intp)
    dof_indices = np.asarray(model.jnt_dofadr[joint_ids], dtype=np.intp)
    joint_ranges = np.asarray(model.jnt_range[joint_ids], dtype=np.float64)
    if not np.all(model.jnt_limited[joint_ids]) or not np.isfinite(joint_ranges).all():
        raise ValueError("both arm joints must have finite declared limits")
    if np.any(joint_ranges[:, 0] >= joint_ranges[:, 1]):
        raise ValueError("arm joint limits are inconsistent")
    axes = np.asarray(model.jnt_axis[joint_ids], dtype=np.float64)
    if not np.allclose(axes, [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]):
        raise ValueError("the arm IK trace requires both joints to rotate about z")
    if not np.allclose(model.jnt_pos[joint_ids], 0.0):
        raise ValueError("the arm IK trace requires joints at their body origins")

    shoulder_body = int(model.jnt_bodyid[joint_ids[0]])
    elbow_body = int(model.jnt_bodyid[joint_ids[1]])
    if int(model.body_parentid[elbow_body]) != shoulder_body:
        raise ValueError("the elbow body must be directly attached to the shoulder body")
    shoulder_offset = np.asarray(model.body_pos[shoulder_body], dtype=np.float64)
    if not np.allclose(shoulder_offset[:2], 0.0):
        raise ValueError("the shoulder joint must lie above the arm base origin")
    base_body = int(model.body_parentid[shoulder_body])
    base_offset = np.asarray(model.body_pos[base_body], dtype=np.float64)
    if int(model.body_parentid[base_body]) != 0 or not np.allclose(
        base_offset[:2], 0.0
    ):
        raise ValueError("the arm base must be rooted at the target coordinate origin")
    site_id = _named_id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    if int(model.site_bodyid[site_id]) != elbow_body:
        raise ValueError("the end-effector site must be attached to the elbow body")

    forearm_offset = np.asarray(model.body_pos[elbow_body], dtype=np.float64)
    site_offset = np.asarray(model.site_pos[site_id], dtype=np.float64)
    if (
        not np.allclose(forearm_offset[1:], 0.0)
        or not np.allclose(site_offset[1:], 0.0)
        or forearm_offset[0] <= 0.0
        or site_offset[0] <= 0.0
    ):
        raise ValueError("the arm links must lie along their local positive x axes")
    identity_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
    if not np.allclose(
        model.body_quat[[base_body, shoulder_body, elbow_body]], identity_quaternion
    ):
        raise ValueError("the arm IK trace requires unrotated base and arm bodies")

    if not np.all(model.actuator_trntype == mujoco.mjtTrn.mjTRN_JOINT):
        raise ValueError("both arm actuators must use direct joint transmissions")
    if not np.array_equal(model.actuator_trnid[:, 0], joint_ids):
        raise ValueError("actuators must follow shoulder, elbow order")
    gear = np.asarray(model.actuator_gear[:, 0], dtype=np.float64)
    if not np.isfinite(gear).all():
        raise ValueError("actuator gear values must be finite")

    return {
        "joint_names": joint_names,
        "joint_ids": joint_ids,
        "qpos_indices": qpos_indices,
        "dof_indices": dof_indices,
        "joint_ranges": joint_ranges,
        "link_lengths": np.array([forearm_offset[0], site_offset[0]]),
        "gear": gear,
    }


def _finite_array(values: Any, label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError(f"{label} contains a non-finite value")
    return array


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_joint_errors(
    target_position: np.ndarray, q: np.ndarray, link_lengths: np.ndarray
) -> dict[str, list[float]]:
    target_x, target_y = target_position[:2]
    upper_length, forearm_length = link_lengths
    cos_elbow = (
        target_x**2
        + target_y**2
        - upper_length**2
        - forearm_length**2
    ) / (2.0 * upper_length * forearm_length)
    if cos_elbow < -1.0 - 1e-12 or cos_elbow > 1.0 + 1e-12:
        raise ValueError("sampled target is outside the two-link arm workspace")
    elbow_magnitude = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))
    result = {}
    for branch, elbow in (
        ("elbow_positive", elbow_magnitude),
        ("elbow_negative", -elbow_magnitude),
    ):
        shoulder = target_angle - np.arctan2(
            forearm_length * np.sin(elbow),
            upper_length + forearm_length * np.cos(elbow),
        )
        result[branch] = [
            _wrap_to_pi(float(shoulder - q[0])),
            _wrap_to_pi(float(elbow - q[1])),
        ]
    return result


def _sample(
    env,
    layout: dict[str, Any],
    target_position: np.ndarray,
    *,
    control_step: int,
    held_steps: int,
    has_control_sample: bool,
    environment_reported_distance: Any = None,
) -> dict[str, Any]:
    if has_control_sample:
        # mj_step integrates qpos after its forward pass; refresh kinematics
        # at the sampled state without advancing or otherwise stepping physics.
        mujoco.mj_kinematics(env.model, env.data)

    q = _finite_array(
        env.data.qpos[layout["qpos_indices"]], "joint position"
    )
    qdot = _finite_array(env.data.qvel[layout["dof_indices"]], "joint velocity")
    endpoint = _finite_array(
        env.data.site("end_effector").xpos, "end-effector position"
    )
    error = endpoint - target_position
    distance = float(np.linalg.norm(error))
    if not math.isfinite(distance):
        raise ValueError("endpoint error norm is not finite")
    if control_step == 0:
        reported_distance = distance
    else:
        reported_distance = _nonnegative_scalar(
            environment_reported_distance, "environment-reported distance"
        )

    margins = {}
    for index, name in enumerate(layout["joint_names"]):
        lower, upper = layout["joint_ranges"][index]
        margins[name] = {
            "to_lower_limit_rad": float(q[index] - lower),
            "to_upper_limit_rad": float(upper - q[index]),
        }

    if has_control_sample:
        command = _finite_array(env.data.ctrl, "clipped applied command")
        nominal_torque = command * layout["gear"]
        measured_torque = _finite_array(
            env.data.qfrc_actuator[layout["dof_indices"]],
            "measured generalized actuator torque",
        )
        command_value = command.tolist()
        nominal_torque_value = _finite_array(
            nominal_torque, "nominal command-times-gear torque"
        ).tolist()
        measured_torque_value = measured_torque.tolist()
    else:
        command_value = None
        nominal_torque_value = None
        measured_torque_value = None

    return {
        "control_step": control_step,
        "q_rad": q.tolist(),
        "qdot_rad_s": qdot.tolist(),
        "endpoint_minus_target_m": error.tolist(),
        "endpoint_error_norm_m": distance,
        "environment_reported_distance_m": reported_distance,
        "ik_branch_joint_errors_rad": _ik_joint_errors(
            target_position, q, layout["link_lengths"]
        ),
        "joint_limit_margins_rad": margins,
        "clipped_applied_command": command_value,
        "nominal_command_times_gear_torque_nm": nominal_torque_value,
        "measured_generalized_applied_joint_torque_nm": measured_torque_value,
        "held_steps": held_steps,
    }


def _record_episode(
    runtime,
    env,
    layout: dict[str, Any],
    *,
    episode: int,
    episode_seed: int,
) -> dict[str, Any]:
    observation, _ = env.reset(seed=episode_seed)
    runtime.reset()
    target_position = _finite_array(env.data.mocap_pos[0], "sampled target")
    target_radius = float(np.hypot(target_position[0], target_position[1]))
    target_angle = float(np.degrees(np.arctan2(target_position[1], target_position[0])))
    if not math.isfinite(target_radius) or not math.isfinite(target_angle):
        raise ValueError(f"episode {episode} sampled an invalid target")

    held_steps = 0
    trace = [
        _sample(
            env,
            layout,
            target_position,
            control_step=0,
            held_steps=held_steps,
            has_control_sample=False,
        )
    ]
    first_reach_step = None
    terminated = False
    truncated = False
    step_count = 0
    success = False
    while not (terminated or truncated):
        action = runtime.predict(observation)
        observation, _, terminated, truncated, info = env.step(action)
        step_count += 1
        if step_count > env.max_episode_steps:
            raise ValueError(f"episode {episode} exceeded its configured step limit")
        held_steps = _integer(info.get("held_steps"), "environment held_steps", minimum=0)
        if held_steps > 0 and first_reach_step is None:
            first_reach_step = step_count
        success_value = info.get("is_success")
        if not isinstance(success_value, bool):
            raise ValueError("environment is_success must be boolean")
        success = success_value
        trace.append(
            _sample(
                env,
                layout,
                target_position,
                control_step=step_count,
                held_steps=held_steps,
                has_control_sample=True,
                environment_reported_distance=info["distance"],
            )
        )

    if not trace or trace[-1]["control_step"] != step_count:
        raise ValueError(f"episode {episode} trace does not include its final step")
    if success:
        if not terminated or held_steps != env.hold_steps_required:
            raise ValueError(f"episode {episode} success state is inconsistent")
        final_hold = [
            sample["held_steps"] for sample in trace[-env.hold_steps_required :]
        ]
        if final_hold != list(range(1, env.hold_steps_required + 1)):
            raise ValueError(f"episode {episode} is missing samples from its full hold")
        outcome = "success"
    elif first_reach_step is None:
        outcome = "no_reach_failure"
    else:
        outcome = "post_reach_failure"

    return {
        "episode": episode,
        "episode_seed": episode_seed,
        "target_radius_m": target_radius,
        "target_angle_degrees": target_angle,
        "outcome": outcome,
        "success": success,
        "first_reach_step": first_reach_step,
        "steps": step_count,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "trajectory": trace,
    }


def _validate_against_reference(
    rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]]
) -> None:
    for episode, (row, reference) in enumerate(zip(rows, reference_rows, strict=True)):
        if row["episode_seed"] != reference["episode_seed"]:
            raise ValueError(f"episode {episode} seed does not match the reference")
        if not math.isclose(
            row["target_radius_m"] * 100.0,
            reference["target_radius_cm"],
            rel_tol=1e-10,
            abs_tol=1e-9,
        ):
            raise ValueError(f"episode {episode} target radius does not match reference")
        if not math.isclose(
            row["target_angle_degrees"],
            reference["target_angle_degrees"],
            rel_tol=1e-10,
            abs_tol=1e-9,
        ):
            raise ValueError(f"episode {episode} target angle does not match reference")
        if row["success"] is not reference["success"]:
            raise ValueError(f"episode {episode} success label does not match reference")
        if row["first_reach_step"] != reference["first_reach_step"]:
            raise ValueError(
                f"episode {episode} first-reach step does not match reference"
            )
        if row["steps"] != reference["steps"]:
            raise ValueError(f"episode {episode} episode length does not match reference")
        if row["terminated"] is not reference["terminated"]:
            raise ValueError(
                f"episode {episode} termination flag does not match reference"
            )
        if row["truncated"] is not reference["truncated"]:
            raise ValueError(
                f"episode {episode} truncation flag does not match reference"
            )


def _run(
    *,
    model_path: Path,
    seed: int,
    episodes: int,
    reference_path: Path,
    output_path: Path,
) -> None:
    reference_rows = _read_reference(reference_path, seed=seed, episodes=episodes)
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    try:
        layout = _model_layout(env)
        if env.frame_skip != FRAME_SKIP:
            raise ValueError("research environment control sampling is not 10 substeps")
        control_substeps = int(env.frame_skip)
        control_dt = float(env.model.opt.timestep * env.frame_skip)
        hold_steps_required = round(HOLD_SECONDS / control_dt)
        if hold_steps_required != 100 or hold_steps_required != env.hold_steps_required:
            raise ValueError("research environment hold-step semantics are inconsistent")

        rows = [
            _record_episode(
                runtime,
                env,
                layout,
                episode=episode,
                episode_seed=seed + episode,
            )
            for episode in range(episodes)
        ]
        _validate_against_reference(rows, reference_rows)
    finally:
        env.close()

    result = {
        "schema_version": 1,
        "model": str(model_path),
        "reference_evaluation": str(reference_path),
        "seed": seed,
        "episodes": episodes,
        "metadata": {
            "units": {
                "joint_position": "rad",
                "joint_velocity": "rad/s",
                "endpoint_error": "m",
                "environment_reported_distance": "m",
                "joint_limit_margin": "rad",
                "command": "normalized actuator command",
                "torque": "N m",
                "target_radius": "m",
                "target_angle": "degrees",
            },
            "joint_order": ["shoulder", "elbow"],
            "control_substeps": control_substeps,
            "control_sampling": "10 MuJoCo substeps per control step",
            "control_timestep_seconds": control_dt,
            "hold_steps_required": hold_steps_required,
            "torque_sampling": "control-step endpoint",
            "distance_semantics": (
                "Outcome and first-reach labels use environment-reported distance. "
                "The endpoint error is recomputed from sampled q after forward "
                "kinematics; paired values expose any one-substep "
                "state/kinematics discrepancy."
            ),
            "reset_sample": (
                "Step 0 has no applied command or torque; those fields are null."
            ),
            "scope": (
                "Research control-step trace; cannot establish protected "
                "within-step occupancy or official success."
            ),
        },
        "episode_rows": rows,
    }
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _nonnegative_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _positive_integer(value: str) -> int:
    parsed = _nonnegative_integer(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trace saved-policy episodes and validate them against research evaluation."
    )
    parser.add_argument("--candidate-model", type=Path, required=True)
    parser.add_argument("--seed", type=_nonnegative_integer, required=True)
    parser.add_argument("--episodes", type=_positive_integer, required=True)
    parser.add_argument("--reference-evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        model_path = args.candidate_model.expanduser().resolve(strict=True)
        reference_path = args.reference_evaluation.expanduser().resolve(strict=True)
        output_path = args.output.expanduser().resolve()
        if not model_path.is_file():
            raise ValueError(f"candidate model is not a file: {model_path}")
        if not reference_path.is_file():
            raise ValueError(f"reference evaluation is not a file: {reference_path}")
        if output_path in {model_path, reference_path}:
            raise ValueError("output path must not overwrite an input artifact")
        if not output_path.parent.is_dir():
            raise ValueError(f"output directory does not exist: {output_path.parent}")
        if output_path.exists():
            raise ValueError(f"output file already exists: {output_path}")
        _run(
            model_path=model_path,
            seed=args.seed,
            episodes=args.episodes,
            reference_path=reference_path,
            output_path=output_path,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
