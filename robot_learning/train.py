import argparse
import json
import shutil
from pathlib import Path

import torch
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from robot_learning.scenario import make_training_env
from robot_learning.training.algorithms import algorithm_class, artifact_algorithm
from robot_learning.training.candidate_checkpoint_callback import (
    CandidateCheckpointCallback,
)
from robot_learning.training.research_config import load_experiment_config
from robot_learning.training.viewer_callback import LiveViewerCallback

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
    parser.add_argument("--algorithm", choices=("ppo", "sac"), default=None)
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
    algorithm = args.algorithm or str(config["algorithm"]["name"]).lower()
    n_envs = args.n_envs or int(config["training"]["n_envs"])
    if args.resume is not None:
        resume_algorithm = artifact_algorithm(args.resume)
        if resume_algorithm != algorithm:
            raise SystemExit(
                f"cannot resume {resume_algorithm} checkpoint as {algorithm}; "
                "use fresh initialization for an algorithm change"
            )

    args.output_dir.mkdir(parents=True, exist_ok=False)
    vec_env_cls = DummyVecEnv if n_envs == 1 else SubprocVecEnv
    venv = make_vec_env(
        make_training_env,
        n_envs=n_envs,
        seed=args.seed,
        vec_env_cls=vec_env_cls,
    )

    params = dict(config[algorithm])
    if algorithm == "ppo":
        params = parallel_ppo_params(params, n_envs)
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

    algorithm_type = algorithm_class(algorithm)
    tensorboard_log = str(args.output_dir / "tensorboard")
    if args.resume is not None:
        model = algorithm_type.load(
            args.resume,
            env=venv,
            seed=args.seed,
            tensorboard_log=tensorboard_log,
            **params,
        )
        replay_path = args.resume.parent / "replay_buffer.pkl"
        if algorithm == "sac" and replay_path.exists():
            model.load_replay_buffer(replay_path)
    else:
        model = algorithm_type(
            "MlpPolicy",
            venv,
            seed=args.seed,
            verbose=1,
            tensorboard_log=tensorboard_log,
            policy_kwargs=policy_kwargs,
            **params,
        )

    training = config["training"]
    callbacks = [
        CandidateCheckpointCallback(
            output_dir=args.output_dir,
            every_steps=int(training["checkpoint_every_steps"]),
        )
    ]
    if args.view:
        callbacks.append(LiveViewerCallback(speed=args.speed))

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
        if hasattr(model, "save_replay_buffer"):
            model.save_replay_buffer(args.output_dir / "last_replay_buffer.pkl")
        venv.save(str(args.output_dir / "last_vecnormalize.pkl"))
        artifact = {
            "schema_version": 1,
            "algorithm": algorithm,
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
        last_replay = args.output_dir / "last_replay_buffer.pkl"
        if last_replay.exists():
            shutil.copyfile(last_replay, final_checkpoint / "replay_buffer.pkl")
        shutil.copyfile(
            args.output_dir / "last_model.zip", args.output_dir / "model.zip"
        )
        shutil.copyfile(
            args.output_dir / "last_vecnormalize.pkl",
            args.output_dir / "vecnormalize.pkl",
        )
        if last_replay.exists():
            shutil.copyfile(last_replay, args.output_dir / "replay_buffer.pkl")

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
