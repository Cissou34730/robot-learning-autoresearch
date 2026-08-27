import argparse
import time
from pathlib import Path

import mujoco
import mujoco.viewer

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a trained agent in the MuJoCo viewer"
    )
    parser.add_argument(
        "--model", type=Path, required=True, help="path to a trained model.zip"
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument(
        "--speed", type=float, default=1.0, help="playback speed multiplier"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = TwoJointArmReachEnv()
    model = load_policy(args.model)
    normalize_obs = load_observation_normalizer(args.model)
    if normalize_obs is None:
        normalize_obs = lambda obs: obs
    control_dt = env.model.opt.timestep * env.frame_skip

    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        for _ in range(args.episodes):
            obs, _ = env.reset()
            episode_reward = 0.0
            done = False
            while not done and viewer.is_running():
                action, _ = model.predict(normalize_obs(obs), deterministic=True)
                obs, reward, terminated, truncated, info = env.step(action)
                episode_reward += reward
                done = terminated or truncated
                viewer.sync()
                time.sleep(control_dt / max(args.speed, 1e-6))
            print(
                f"episode finished: reward={episode_reward:.2f} success={info['is_success']}"
            )
            if not viewer.is_running():
                break


if __name__ == "__main__":
    main()
