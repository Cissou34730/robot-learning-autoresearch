"""Read a range of preserved raw training records for one experiment."""

from __future__ import annotations

import argparse
import re
import sys

from research import runner_paths as paths
from robot_learning.training.progress import parse_training_records


def experiment_log_paths(experiment: int) -> list[tuple[int, object]]:
    pattern = re.compile(rf"^experiment-{experiment}-attempt-(\d+)\.log$")
    logs = []
    for log_path in paths.TRAINING_LOG_DIR.glob(f"experiment-{experiment}-attempt-*.log"):
        match = pattern.match(log_path.name)
        if match is not None:
            logs.append((int(match.group(1)), log_path))
    return sorted(logs)


def selected_records(
    experiment: int, first_step: int, last_step: int
) -> list[tuple[int, dict[str, float]]]:
    records = []
    for attempt, log_path in experiment_log_paths(experiment):
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for record in parse_training_records(text):
            timestep = record.get("total_timesteps")
            if timestep is not None and first_step <= timestep <= last_step:
                records.append((attempt, record))
    return records


def render_markdown(records: list[tuple[int, dict[str, float]]]) -> str:
    metric_names = sorted(
        {metric for _, record in records for metric in record if metric != "total_timesteps"}
    )
    columns = ["attempt", "total_timesteps", *metric_names]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for attempt, record in records:
        values = [str(attempt), f"{record['total_timesteps']:g}"]
        values.extend(
            "" if metric not in record else f"{record[metric]:g}"
            for metric in metric_names
        )
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=int)
    parser.add_argument("--from-step", required=True, type=int)
    parser.add_argument("--to-step", required=True, type=int)
    arguments = parser.parse_args(argv)
    if arguments.experiment < 1:
        parser.error("--experiment must be a positive integer")
    if arguments.from_step < 0 or arguments.from_step > arguments.to_step:
        parser.error("timestep bounds must satisfy 0 <= --from-step <= --to-step")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    if not experiment_log_paths(arguments.experiment):
        print(
            f"no training logs found for experiment {arguments.experiment}",
            file=sys.stderr,
        )
        return 1
    print(render_markdown(selected_records(
        arguments.experiment, arguments.from_step, arguments.to_step
    )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())