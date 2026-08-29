import argparse
import json
import shutil
from pathlib import Path

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from robot_learning.scenario import make_training_env, make_training_viewer_callback
from robot_learning.training.candidate_checkpoint_callback import (
    CandidateCheckpointCallback,
)
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


def main() -> None:
    args = parse_args()
    config = load_experiment_config()
    n_envs = args.n_envs or int(config["training"]["n_envs"])

    args.output_dir.mkdir(parents=True, exist_ok=False)
    vec_env_cls = DummyVecEnv if n_envs == 1 else SubprocVecEnv
    venv = make_vec_env(
        make_training_env,
        n_envs=n_envs,
        seed=args.seed,
        vec_env_cls=vec_env_cls,
    )

    params = parallel_ppo_params(config["ppo"], n_envs)
    policy_kwargs = build_policy_kwargs(config["policy"])
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

    training = config["training"]
    callbacks: list[BaseCallback] = [
        CandidateCheckpointCallback(
            output_dir=args.output_dir,
            every_steps=int(training["checkpoint_every_steps"]),
        )
    ]
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
        model.save(args.output_dir / "last_model")
        venv.save(str(args.output_dir / "last_vecnormalize.pkl"))
        artifact = {
            "schema_version": 1,
            "algorithm": ALGORITHM_NAME,
            "seed": args.seed,
            "timesteps": int(model.num_timesteps),
            "requested_timesteps": args.target_timesteps or args.timesteps,
            "completed": not interrupted,
            "resumed_from": str(args.resume) if args.resume else None,
            "n_envs": n_envs,
            "parameters": params,
            "policy": config["policy"],
        }
        (args.output_dir / "artifact.json").write_text(
            json.dumps(artifact, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        final_checkpoint = args.output_dir / "final_checkpoint"
        final_checkpoint.mkdir()
        shutil.copyfile(
            args.output_dir / "last_model.zip", final_checkpoint / "model.zip"
        )
        shutil.copyfile(
            args.output_dir / "last_vecnormalize.pkl",
            final_checkpoint / "vecnormalize.pkl",
        )
        (final_checkpoint / "artifact.json").write_text(
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
            candidate_artifact = {**artifact, "timesteps": steps, "completed": True}
            (candidate_dir / "artifact.json").write_text(
                json.dumps(candidate_artifact, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            candidates.append(
                {
                    "name": f"checkpoint-{steps}",
                    "timesteps": steps,
                    "path": candidate_dir.relative_to(args.output_dir).as_posix(),
                }
            )

        final_steps = int(model.num_timesteps)
        if not any(item["timesteps"] == final_steps for item in candidates):
            candidates.append(
                {
                    "name": "final",
                    "timesteps": final_steps,
                    "path": "final_checkpoint",
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
