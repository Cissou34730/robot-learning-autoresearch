import argparse
from pathlib import Path

from robot_learning.scenario.viewer import watch_scenario_policy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a trained agent in the scenario viewer"
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
    watch_scenario_policy(args.model, episodes=args.episodes, speed=args.speed)


if __name__ == "__main__":
    main()
