import argparse
import json
import time
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.viewer_callback import LiveViewerCallback

MODELS_DIR = Path("models")
CHECKPOINT_EVERY_STEPS = 5000

ENVIRONMENTS = {"reach": TwoJointArmReachEnv}

PPO_HYPERPARAMETERS = {
    "n_steps": 1024,
    "batch_size": 64,
    "gamma": 0.99,
    "learning_rate": 3e-4,
    "gae_lambda": 0.95,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a PPO agent")
    parser.add_argument("--env", default="reach", choices=sorted(ENVIRONMENTS))
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--view", action="store_true", help="open a live MuJoCo viewer during training"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="playback speed of the live viewer (2.0 = twice real time)",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="path to an existing model.zip to continue training from",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    save_dir = MODELS_DIR / (
        f"{args.env}-resume-{time.strftime('%Y%m%d-%H%M%S')}"
        if args.resume is not None
        else f"{args.env}-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    tensorboard_log = str(save_dir / "tensorboard")

    venv = DummyVecEnv([lambda: Monitor(ENVIRONMENTS[args.env]())])
    if args.resume is not None:
        stats_path = args.resume.parent / "vecnormalize.pkl"
        if stats_path.exists():
            venv = VecNormalize.load(str(stats_path), venv)
            print(f"Loaded observation statistics from {stats_path}")
        else:
            raise SystemExit(
                f"No vecnormalize.pkl next to {args.resume} — this model was trained "
                "without normalization and cannot be resumed into a normalized run."
            )
    else:
        venv = VecNormalize(
            venv,
            norm_obs=True,
            norm_reward=False,
            gamma=PPO_HYPERPARAMETERS["gamma"],
        )

    callbacks = []
    if args.view:
        callbacks.append(LiveViewerCallback(speed=args.speed))

    if args.resume is not None:
        model = PPO.load(
            args.resume, env=venv, seed=args.seed, tensorboard_log=tensorboard_log
        )
    else:
        model = PPO(
            "MlpPolicy",
            venv,
            seed=args.seed,
            verbose=1,
            tensorboard_log=tensorboard_log,
            **PPO_HYPERPARAMETERS,
        )

    callbacks.append(
        CheckpointCallback(
            save_freq=CHECKPOINT_EVERY_STEPS,
            save_path=str(save_dir / "checkpoints"),
            name_prefix=args.env,
            save_vecnormalize=True,
        )
    )

    save_dir.mkdir(parents=True, exist_ok=False)

    try:
        model.learn(
            total_timesteps=args.timesteps,
            reset_num_timesteps=args.resume is None,
            callback=callbacks,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted — saving current policy before exit.")
    finally:
        model.save(save_dir / "model")
        venv.save(str(save_dir / "vecnormalize.pkl"))
        (save_dir / "run_config.json").write_text(
            json.dumps(
                {
                    "env": args.env,
                    "timesteps": args.timesteps,
                    "seed": args.seed,
                    "resumed_from": str(args.resume) if args.resume else None,
                    "hyperparameters": PPO_HYPERPARAMETERS,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Model saved to {save_dir / 'model.zip'}")
        print(f"Metrics: uv run tensorboard --logdir {MODELS_DIR}")


if __name__ == "__main__":
    main()
