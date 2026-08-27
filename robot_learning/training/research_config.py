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
    "env": {
        "frame_skip",
        "max_episode_steps",
        "curriculum_stage_advance_success_rate",
        "curriculum_stage_advance_min_episodes",
    },
}

IMMUTABLE_INVARIANTS = {
    "success_threshold": 0.01,
    "hold_steps_required": 100,
    "target_radius_range": (0.06, 0.20),
    "max_episode_steps": 500,
}

# Fixed diagnostic ladder used by evaluation. This is deliberately separate
# from the training curriculum: researchers may change how the agent is taught,
# but not the ruler used to compare experiments.
EVALUATION_MILESTONES: tuple[tuple[float, float], ...] = (
    (0.03, 0.02),
    (0.02, 0.02),
    (0.01, 0.02),
    (0.01, 0.10),
    (0.01, 0.50),
    (0.01, 1.00),
    (0.01, 1.50),
    (0.01, 2.00),
)


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
    assert env.success_threshold == IMMUTABLE_INVARIANTS["success_threshold"]
    assert env.hold_steps_required == IMMUTABLE_INVARIANTS["hold_steps_required"]
    assert env.target_radius_range == IMMUTABLE_INVARIANTS["target_radius_range"]
    assert env.max_episode_steps == IMMUTABLE_INVARIANTS["max_episode_steps"]


def escalation_ladder() -> list[str]:
    return [
        "coefficient and hyperparameter tuning",
        "reward structure",
        "observation representation",
        "training curriculum",
        "policy architecture and training schedule",
        "learning algorithm (e.g. PPO vs SAC)",
        "broader goal-preserving training-method changes",
    ]
