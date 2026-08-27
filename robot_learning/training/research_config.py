"""Single source of truth for experiment parameters.

All tunable parameters live in `research/current_params.json`. Nothing else in
the codebase may define parameter defaults: this module loads and validates the
file, and every consumer (training, evaluation, runner) reads it through here.

Machine-enforced boundaries live in IMMUTABLE_INVARIANTS and
assert_immutable_invariants(): these properties define the task and may never
be modified by experiments.
"""

import json
from pathlib import Path

from robot_learning.benchmark.spec import FINAL_STAGE_INDEX

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "research" / "current_params.json"

PARAM_WHITELIST: dict[str, set[str]] = {
    "reward": {
        "PROGRESS_COEFFICIENT",
        "CLOSENESS_COEFFICIENT",
        "CLOSENESS_LENGTH_SCALE",
        "ACTION_COST_COEFFICIENT",
        "DWELL_BONUS_PER_STEP",
        "HOLD_COMPLETE_BONUS",
    },
    "ppo": {
        "learning_rate",
        "gamma",
        "gae_lambda",
        "n_steps",
        "batch_size",
        "n_epochs",
        "clip_range",
        "ent_coef",
        "vf_coef",
        "max_grad_norm",
        "target_kl",
        "use_sde",
        "sde_sample_freq",
        "normalize_advantage",
        "ortho_init",
    },
    "policy": {
        "net_arch",
        "activation",
        "log_std_init",
        "share_features_extractor",
    },
    "algorithm": {"name"},
    "training": {
        "n_envs",
        "checkpoint_every_steps",
        "selection_eval_every_steps",
        "selection_eval_episodes",
    },
    "curriculum": {"segments"},
    "sac": {
        "learning_rate",
        "buffer_size",
        "learning_starts",
        "batch_size",
        "tau",
        "gamma",
        "train_freq",
        "gradient_steps",
        "ent_coef",
    },
}


def resolve_training_curriculum(
    config: dict, *, current_stage: int, total_timesteps: int
) -> list[tuple[int, int]]:
    raw_segments = config["curriculum"]["segments"]
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError("curriculum.segments must be a non-empty list")
    parsed: list[tuple[int, float]] = []
    for number, segment in enumerate(raw_segments, start=1):
        if not isinstance(segment, dict) or set(segment) != {"stage_index", "fraction"}:
            raise ValueError(
                f"curriculum segment {number} requires stage_index and fraction"
            )
        raw_stage = segment["stage_index"]
        stage_index = current_stage if raw_stage == "current" else int(raw_stage)
        if not 0 <= stage_index <= FINAL_STAGE_INDEX:
            raise ValueError(f"invalid curriculum stage: {stage_index}")
        fraction = float(segment["fraction"])
        if fraction <= 0:
            raise ValueError("curriculum fractions must be positive")
        parsed.append((stage_index, fraction))
    total_fraction = sum(fraction for _, fraction in parsed)
    if abs(total_fraction - 1.0) > 1e-9:
        raise ValueError("curriculum fractions must sum to 1.0")

    remaining = total_timesteps
    resolved: list[tuple[int, int]] = []
    for number, (stage_index, fraction) in enumerate(parsed):
        steps = (
            remaining
            if number == len(parsed) - 1
            else round(total_timesteps * fraction)
        )
        if steps < 1:
            raise ValueError("every curriculum segment needs at least one timestep")
        resolved.append((stage_index, steps))
        remaining -= steps
    return resolved


def validate_param_overrides(overrides: dict) -> None:
    unknown_sections = set(overrides) - set(PARAM_WHITELIST)
    if unknown_sections:
        raise ValueError(f"unknown parameter sections: {sorted(unknown_sections)}")
    for section, values in overrides.items():
        invalid = set(values) - PARAM_WHITELIST[section]
        if invalid:
            raise ValueError(f"unknown {section} parameters: {sorted(invalid)}")


def merge_param_overrides(current: dict, overrides: dict) -> dict:
    effective = {section: dict(values) for section, values in current.items()}
    for section, values in overrides.items():
        effective.setdefault(section, {}).update(values)
    return effective


def load_experiment_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} is missing - it is the single source of truth for "
            "experiment parameters and must exist."
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    missing_sections = set(PARAM_WHITELIST) - set(config)
    if missing_sections:
        raise ValueError(
            f"{CONFIG_PATH} is missing required sections: {sorted(missing_sections)}"
        )
    validate_param_overrides(config)
    return config


def write_experiment_config(config: dict) -> None:
    validate_param_overrides(config)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def assert_immutable_invariants(env) -> None:
    from robot_learning.benchmark.spec import (
        FINAL_STAGE_INDEX,
        FRAME_SKIP,
        MAX_EPISODE_STEPS,
        TARGET_RADIUS_RANGE,
        stage_spec,
    )

    threshold, hold_seconds = stage_spec(FINAL_STAGE_INDEX)
    control_dt = env.model.opt.timestep * env.frame_skip
    assert env.success_threshold == threshold
    assert env.hold_steps_required == round(hold_seconds / control_dt)
    assert env.target_radius_range == TARGET_RADIUS_RANGE
    assert env.max_episode_steps == MAX_EPISODE_STEPS
    assert env.frame_skip == FRAME_SKIP
