import argparse
import copy
import json
import shutil
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from robot_learning.policy_runtime import frozen_scientific_modules
from robot_learning.scenario.teacher import DampedIKTeacher
from robot_learning.scenario.training_environment import make_training_env
from robot_learning.scenario.viewer import make_training_viewer_callback
from robot_learning.training.candidate_checkpoint_callback import (
    CandidateCheckpointCallback,
)
from robot_learning.training.checkpoint import export_runtime
from robot_learning.training.research_config import load_experiment_config

# The current learning method. Replacing it is a normal research change.
ALGORITHM_NAME = "ppo"

ACTIVATION_FUNCTIONS = {
    "tanh": torch.nn.Tanh,
    "relu": torch.nn.ReLU,
    "elu": torch.nn.ELU,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a robot policy")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", type=Path, default=None)
    parser.add_argument("--continue-timesteps", action="store_true")
    parser.add_argument("--target-timesteps", type=int, default=None)
    parser.add_argument("--n-envs", type=int, default=None)
    parser.add_argument("--view", action="store_true")
    parser.add_argument("--speed", type=float, default=1.0)
    return parser.parse_args()


def build_policy_kwargs(policy_config: dict) -> dict:
    activation_name = str(policy_config["activation"]).lower()
    if activation_name not in ACTIVATION_FUNCTIONS:
        raise ValueError(f"unknown activation: {activation_name}")
    result = {
        "net_arch": list(policy_config["net_arch"]),
        "activation_fn": ACTIVATION_FUNCTIONS[activation_name],
    }
    if "log_std_init" in policy_config:
        result["log_std_init"] = policy_config["log_std_init"]
    return result


def parallel_ppo_params(ppo_params: dict, n_envs: int) -> dict:
    if n_envs < 1:
        raise ValueError("n_envs must be at least 1")
    rollout_size = int(ppo_params["n_steps"])
    if rollout_size % n_envs:
        raise ValueError(
            f"n_steps ({rollout_size}) must be divisible by n_envs ({n_envs})"
        )
    result = dict(ppo_params)
    result["n_steps"] = rollout_size // n_envs
    return result


def effective_training_config(config: dict) -> dict:
    """Describe the concrete runtime configuration used by this trainer."""
    n_envs = int(config["training"]["n_envs"])
    return {
        "runtime_config": copy.deepcopy(config),
        "n_envs": n_envs,
        "model_parameters": parallel_ppo_params(config["ppo"], n_envs),
        "policy": copy.deepcopy(config["policy"]),
    }


def initialize_with_teacher(model, venv, teacher_config: dict) -> None:
    """Fit the actor mean to teacher actions before ordinary PPO updates."""
    if int(venv.num_envs) != 1:
        raise ValueError("teacher initialization currently requires one environment")

    sample_count = int(teacher_config["samples"])
    epochs = int(teacher_config["epochs"])
    batch_size = int(teacher_config["batch_size"])
    learning_rate = float(teacher_config["learning_rate"])
    if sample_count < 1 or epochs < 1 or batch_size < 1 or learning_rate <= 0.0:
        raise ValueError("teacher initialization parameters must be positive")

    teacher = DampedIKTeacher(
        position_gain=float(teacher_config["position_gain"]),
        velocity_damping=float(teacher_config["velocity_damping"]),
    )
    observations: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    venv.reset()
    raw_observation = venv.get_original_obs().copy()
    env = venv.venv.envs[0].unwrapped
    teacher.reset(env)
    while len(observations) < sample_count:
        observations.append(raw_observation[0].copy())
        action = teacher.action(env)
        actions.append(action.copy())
        _, _, done, _ = venv.step(action.reshape(1, -1))
        raw_observation = venv.get_original_obs().copy()
        if bool(done[0]):
            teacher.reset(env)

    raw_observations = np.asarray(observations, dtype=np.float32)
    normalized_observations = venv.normalize_obs(raw_observations)
    observation_tensor = torch.as_tensor(
        normalized_observations, dtype=torch.float32, device=model.device
    )
    action_tensor = torch.as_tensor(
        np.asarray(actions, dtype=np.float32),
        dtype=torch.float32,
        device=model.device,
    )

    optimizer = torch.optim.Adam(model.policy.parameters(), lr=learning_rate)
    model.policy.set_training_mode(True)
    for _ in range(epochs):
        permutation = torch.randperm(sample_count, device=model.device)
        for start in range(0, sample_count, batch_size):
            indices = permutation[start : start + batch_size]
            distribution = model.policy.get_distribution(observation_tensor[indices])
            mean = distribution.distribution.mean
            loss = torch.nn.functional.mse_loss(mean, action_tensor[indices])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    optimizer_defaults = dict(model.policy.optimizer.defaults)
    optimizer_defaults.pop("lr", None)
    model.policy.optimizer = torch.optim.Adam(
        model.policy.parameters(),
        lr=float(model.learning_rate),
        **optimizer_defaults,
    )


def main() -> None:
    args = parse_args()
    config = load_experiment_config()
    effective_config = effective_training_config(config)
    n_envs = args.n_envs or effective_config["n_envs"]
    if args.n_envs is not None:
        effective_config["n_envs"] = n_envs
        effective_config["model_parameters"] = parallel_ppo_params(
            config["ppo"], n_envs
        )

    args.output_dir.mkdir(parents=True, exist_ok=False)
    vec_env_cls = DummyVecEnv if n_envs == 1 else SubprocVecEnv
    venv = make_vec_env(
        make_training_env,
        n_envs=n_envs,
        seed=args.seed,
        vec_env_cls=vec_env_cls,
    )

    params = effective_config["model_parameters"]
    policy_kwargs = build_policy_kwargs(effective_config["policy"])
    if args.resume is not None:
        stats_path = args.resume.parent / "vecnormalize.pkl"
        if not stats_path.exists():
            raise SystemExit(f"normalization statistics missing: {stats_path}")
        venv = VecNormalize.load(str(stats_path), venv)
    else:
        venv = VecNormalize(
            venv,
            norm_obs=True,
            norm_reward=False,
            gamma=float(params["gamma"]),
        )

    tensorboard_log = str(args.output_dir / "tensorboard")
    if args.resume is not None:
        model = PPO.load(
            args.resume,
            env=venv,
            seed=args.seed,
            tensorboard_log=tensorboard_log,
            **params,
        )
    else:
        model = PPO(
            "MlpPolicy",
            venv,
            seed=args.seed,
            verbose=1,
            tensorboard_log=tensorboard_log,
            policy_kwargs=policy_kwargs,
            **params,
        )

    teacher_config = config.get("teacher_initialization")
    if teacher_config is not None:
        initialize_with_teacher(model, venv, teacher_config)

    training = config["training"]
    checkpoint_callback = CandidateCheckpointCallback(
        output_dir=args.output_dir,
        every_steps=int(training["checkpoint_every_steps"]),
    )
    callbacks: list[BaseCallback] = [checkpoint_callback]
    if args.view:
        callbacks.append(make_training_viewer_callback(speed=args.speed))

    interrupted = False
    try:
        model.learn(
            total_timesteps=args.timesteps,
            reset_num_timesteps=not args.continue_timesteps,
            callback=callbacks,
        )
    except KeyboardInterrupt:
        interrupted = True
        print("\nTraining interrupted - saving the best available policy.")
    finally:
        with frozen_scientific_modules():
            model.save(args.output_dir / "last_model")
        venv.save(str(args.output_dir / "last_vecnormalize.pkl"))
        checkpoint_callback.save_terminal_checkpoint()
        artifact = {
            "schema_version": 1,
            "algorithm": ALGORITHM_NAME,
            "seed": args.seed,
            "timesteps": int(model.num_timesteps),
            "requested_timesteps": args.target_timesteps or args.timesteps,
            "completed": not interrupted,
            "resumed_from": str(args.resume) if args.resume else None,
            "effective_config": effective_config,
        }
        (args.output_dir / "artifact.json").write_text(
            json.dumps(artifact, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        shutil.copyfile(
            args.output_dir / "last_model.zip", args.output_dir / "model.zip"
        )
        shutil.copyfile(
            args.output_dir / "last_vecnormalize.pkl",
            args.output_dir / "vecnormalize.pkl",
        )
        export_runtime(args.output_dir, stats_path=args.output_dir / "vecnormalize.pkl")

        candidates: list[dict] = []
        pool_dir = args.output_dir / "candidate_pool"
        for candidate_dir in sorted(pool_dir.glob("checkpoint-*")):
            try:
                steps = int(candidate_dir.name.removeprefix("checkpoint-"))
            except ValueError:
                continue
            if not all(
                (candidate_dir / filename).exists()
                for filename in ("model.zip", "vecnormalize.pkl")
            ):
                continue
            metrics_path = candidate_dir / "training_metrics.json"
            training_metrics = (
                json.loads(metrics_path.read_text(encoding="utf-8"))
                if metrics_path.exists()
                else {"success_rate": None, "ep_rew_mean": None}
            )
            candidate_metrics = {
                "training_success": training_metrics["success_rate"],
                "ep_rew_mean": training_metrics["ep_rew_mean"],
            }
            candidate_artifact = {
                **artifact,
                "timesteps": steps,
                "completed": True,
                **candidate_metrics,
            }
            (candidate_dir / "artifact.json").write_text(
                json.dumps(candidate_artifact, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            candidates.append(
                {
                    "name": f"checkpoint-{steps}",
                    "timesteps": steps,
                    "path": candidate_dir.relative_to(args.output_dir).as_posix(),
                    **candidate_metrics,
                }
            )

        (args.output_dir / "candidate_manifest.json").write_text(
            json.dumps({"schema_version": 1, "candidates": candidates}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"ARTIFACT_DIR: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
