import argparse
import json
from pathlib import Path

from robot_learning.scenario import evaluate_final_model, evaluate_research_model
from robot_learning.training.research_config import (
    RESEARCH_EVALUATION_EPISODES,
    RESEARCH_EVALUATION_SEED,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained robot policy")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--episodes", type=int, default=RESEARCH_EVALUATION_EPISODES)
    parser.add_argument("--seed", type=int, default=RESEARCH_EVALUATION_SEED)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--progress-json", type=Path, default=None)
    parser.add_argument("--official-benchmark", action="store_true")
    return parser.parse_args()


def write_progress(path: Path, completed: int, total: int) -> bool:
    """Write best-effort telemetry without risking the evaluation itself."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"completed": completed, "total": total}) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # Progress is only a heartbeat. The final evaluation result remains the
        # authoritative output and must not fail because Windows briefly locks
        # this file while the parent process reads it.
        return False
    return True


def main() -> None:
    args = parse_args()

    def report_progress(completed: int, total: int) -> None:
        if args.progress_json is None:
            return
        write_progress(args.progress_json, completed, total)

    result = (
        evaluate_final_model(
            args.model,
            algorithm=args.algorithm,
            progress_callback=report_progress,
        )
        if args.official_benchmark
        else evaluate_research_model(
            args.model,
            episodes=args.episodes,
            seed=args.seed,
            algorithm=args.algorithm,
            progress_callback=report_progress,
        )
    )
    output = json.dumps(result, indent=2)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
