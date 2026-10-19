"""Trusted entry points for protected task-reference and official assessment."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from runner import protocol


def task_reference_contract() -> dict:
    protocol.require_trusted_assessment_runtime(protocol.TASK_REFERENCE_ADAPTER_PATH)
    from benchmark.adapters.task_reference import task_reference_panel

    return task_reference_panel()


def evaluate_task_reference_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    protocol.require_trusted_assessment_runtime(protocol.TASK_REFERENCE_ADAPTER_PATH)
    from benchmark.adapters.task_reference import evaluate_task_reference_model

    kwargs = {"progress_callback": progress_callback}
    if algorithm is not None:
        kwargs["algorithm"] = algorithm
    return evaluate_task_reference_model(
        model_path,
        **kwargs,
    )


def evaluate_official_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    protocol.require_trusted_assessment_runtime(
        protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH
    )
    from benchmark.adapters.final_benchmark import evaluate_final_model

    kwargs = {"progress_callback": progress_callback}
    if algorithm is not None:
        kwargs["algorithm"] = algorithm
    return evaluate_final_model(
        model_path,
        **kwargs,
    )


def _write_progress(path: Path, completed: int, total: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"completed": completed, "total": total}) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-reference", action="store_true", required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--episodes")
    parser.add_argument("--seed")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--progress-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    def report_progress(completed: int, total: int) -> None:
        if args.progress_json is not None:
            _write_progress(args.progress_json, completed, total)

    result = evaluate_task_reference_model(
        args.model,
        algorithm=args.algorithm,
        progress_callback=report_progress,
    )
    output = json.dumps(result, indent=2)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
