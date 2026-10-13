"""Artifact-independent executable checks for the folded residual trace."""

import argparse
import json
from pathlib import Path

import numpy as np

from robot_learning.lab import folded_residual_trace as trace
from robot_learning.scenario.environment import TwoJointArmReachEnv


class _ControlledRuntime:
    def __init__(self, action_space):
        self.action_space = action_space
        self.observation_space = None
        self.reset_count = 0
        self.predict_count = 0

    def reset(self):
        self.reset_count += 1

    def predict(self, observation):
        del observation
        self.predict_count += 1
        if self.predict_count % 4 == 1:
            return np.array([2.0, -2.0])
        return np.array([0.25, 0.25])


class _ControlledEnv(TwoJointArmReachEnv):
    """Real scenario environment with deterministic, instrumented mj_step calls."""

    def __init__(self):
        super().__init__(frame_skip=10, max_episode_steps=4)
        self.hold_steps_required = 3
        self.reset_count = 0
        self._position = np.zeros(3, dtype=np.float64)
        self._total_substeps = 0

    def _end_effector_position(self):
        return self._position.copy()

    def _distance_to_target(self):
        return float(np.linalg.norm(self._position - self.data.mocap_pos[0]))

    def _observation(self):
        return np.zeros(self.observation_space.shape, dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        observation, info = super().reset(seed=seed, options=options)
        self.reset_count += 1
        self._position = np.asarray(self.data.mocap_pos[0], dtype=np.float64).copy()
        self._total_substeps = 0
        return observation, info

    def controlled_mj_step(self, data):
        substep = self._total_substeps % self.frame_skip
        control_step = self._total_substeps // self.frame_skip
        outside = (
            (self.reset_count == 1 and control_step == 0 and substep == 4)
            or (self.reset_count == 1 and control_step == 2)
        )
        offset = np.array([0.02, 0.0, 0.0]) if outside else np.zeros(3)
        self._position = np.asarray(self.data.mocap_pos[0], dtype=np.float64) + offset
        data.qpos[:] = 0.01 * (self._total_substeps + 1)
        data.qvel[:] = 0.1 * (self._total_substeps + 1)
        data.qacc[:] = 0.2 * (self._total_substeps + 1)
        if hasattr(data, "qfrc_actuator"):
            data.qfrc_actuator[:] = 0.3 * (self._total_substeps + 1)
        self._total_substeps += 1


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _run_controlled_check(*, episodes: int) -> dict:
    env = _ControlledEnv()
    runtime = _ControlledRuntime(env.action_space)
    runtime.observation_space = env.observation_space
    original_step = trace.mujoco.mj_step
    original_loader = trace.load_runtime
    original_factory = trace.make_evaluation_env
    original_classifier = trace.classify_target_ik_branches
    trace.mujoco.mj_step = lambda model, data: env.controlled_mj_step(data)
    trace.load_runtime = lambda model_path, algorithm=None: runtime
    trace.make_evaluation_env = lambda policy_runtime=None: env
    trace.classify_target_ik_branches = lambda model, target: {
        "open_legal": False,
        "folded_legal": True,
        "union": "folded_only",
    }
    try:
        panel = trace.collect_panel(
            Path("controlled-model"),
            episodes=episodes,
            seed=73,
        )
    finally:
        trace.mujoco.mj_step = original_step
        trace.load_runtime = original_loader
        trace.make_evaluation_env = original_factory
        trace.classify_target_ik_branches = original_classifier

    _assert(runtime.reset_count == episodes, "runtime reset was not repeated")
    _assert(runtime.predict_count >= 2, "fewer than two control steps were traced")
    _assert(panel["production_timing"]["frame_skip"] == 10, "frame skip changed")
    _assert(
        panel["schema"] == "folded_residual_trace"
        and panel["schema_version"] == 1,
        "trace schema/version is missing",
    )
    _assert(panel["selection"]["selected_episode_count"] >= 1, "no trace selected")
    selected = panel["detailed_traces"]
    all_frames = [frame for item in selected for frame in item["control_frames"]]
    _assert(all_frames, "selected trace is empty")
    hidden = next(
        (
            frame
            for frame in all_frames
            if frame["hidden_excursion_returned_inside"]
        ),
        None,
    )
    _assert(hidden is not None, "hidden substep excursion was not flagged")
    _assert(hidden["endpoint_in_tolerance"], "hidden excursion did not return inside")
    _assert(
        not hidden["endpoint_hold_interrupted"],
        "hidden excursion became an official interruption",
    )
    interrupted = next(
        (frame for frame in all_frames if frame["endpoint_hold_interrupted"]),
        None,
    )
    _assert(interrupted is not None, "endpoint hold interruption was not traced")
    _assert(
        interrupted["held_steps"] == 0,
        "interrupted endpoint did not reset the sampled hold",
    )
    saturated = next(
        (frame for frame in all_frames if frame["saturation_flag"]), None
    )
    _assert(saturated is not None, "clipping/saturation was not traced")
    _assert(
        saturated["applied_clipped_action"] != saturated["commanded_policy_action"],
        "applied action does not show clipping",
    )
    for frame in all_frames:
        _assert(len(frame["substeps"]) == 10, "substep count is not ten")
        _assert(
            [item["internal_substep"] for item in frame["substeps"]]
            == list(range(10)),
            "substep indices are not synchronized",
        )
        _assert(
            all("qacc" in item for item in frame["substeps"]),
            "qacc is absent from a substep",
        )
        _assert(
            all(
                "actuator_force_torque_available" in item
                and "qfrc_actuator" in item
                for item in frame["substeps"]
            ),
            "actuator availability or force field is absent",
        )
        _assert(
            len(frame["saturated_elements"])
            == len(frame["applied_clipped_action"]),
            "per-element saturation is absent",
        )
        _assert(
            "endpoint_outside_tolerance" in frame,
            "endpoint outside-tolerance flag is absent",
        )
    return {
        "observed": {
            "episodes": len(panel["episode_results"]),
            "runtime_reset_count": runtime.reset_count,
            "predict_count": runtime.predict_count,
            "selected_trace_count": len(selected),
            "frames_checked": len(all_frames),
            "substeps_per_frame": sorted(
                {len(frame["substeps"]) for frame in all_frames}
            ),
            "hidden_excursion_flagged": True,
            "hidden_excursion_official_interruption": False,
            "endpoint_interruption_flagged": True,
            "saturation_flagged": True,
            "qacc_present": True,
            "actuator_fields_present": True,
        },
        "expected": {
            "episodes": episodes,
            "repeated_runtime_resets": episodes,
            "minimum_predict_calls": 2,
            "substeps_per_frame": [10],
            "hidden_excursion_official_interruption": False,
            "endpoint_interruption_flagged": True,
            "saturation_flagged": True,
            "qacc_present": True,
            "actuator_fields_present": True,
        },
        "checked_scope": [
            "Repeated production-style resets and runtime reset calls.",
            "Two or more control frames with ten MuJoCo substeps each.",
            "Policy transformation, clipping, and per-element saturation.",
            "Endpoint sampled hold transitions and an endpoint interruption.",
            "Hidden outside-tolerance motion returning inside without an official interruption.",
            "qacc and qfrc_actuator schema fields on every retained substep.",
        ],
        "unchecked_scope": [
            "A saved policy runtime and model artifact are not loaded.",
            "The controlled mj_step replaces physical dynamics and does not validate them.",
            "The real target classifier is replaced with a folded_only fixture.",
        ],
    }


def run_check(output: Path, *, compatibility: bool = False) -> None:
    episodes = 1 if compatibility else 2
    try:
        payload = _run_controlled_check(episodes=episodes)
        payload.update(
            {
                "schema_version": 1,
                "mode": "compatibility" if compatibility else "behavioral",
                "status": "passed",
            }
        )
    except Exception as error:
        payload = {
            "schema_version": 1,
            "mode": "compatibility" if compatibility else "behavioral",
            "status": "failed",
            "error": str(error),
            "unchecked_scope": [
                "The controlled verification did not complete.",
            ],
        }
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        raise
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("behavioral", "compatibility"),
        default="behavioral",
    )
    args = parser.parse_args()
    run_check(args.output, compatibility=args.mode == "compatibility")


if __name__ == "__main__":
    main()
