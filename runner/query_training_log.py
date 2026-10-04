"""Read a range of preserved raw training records for one schema-6 operation."""

from __future__ import annotations

import argparse
import re
import sys

from robot_learning.training.progress import parse_training_records
from runner import paths, repository


def training_log_paths(operation_id: str) -> list[tuple[int, object]]:
    state = repository.load_state(allow_missing_artifact=True)
    campaign_id = repository.current_campaign_id(state)
    directory = (
        paths.TRAINING_LOG_DIR / campaign_id if campaign_id else paths.TRAINING_LOG_DIR
    )
    stem = operation_id.lower()
    pattern = re.compile(rf"^{re.escape(stem)}-attempt-(\d+)\.log$")
    logs = []
    for log_path in directory.glob(f"{stem}-attempt-*.log"):
        match = pattern.match(log_path.name)
        if match is not None:
            logs.append((int(match.group(1)), log_path))
    return sorted(logs)


def selected_records(
    operation_id: str, first_step: int, last_step: int
) -> list[tuple[int, dict[str, float]]]:
    records = []
    for attempt, log_path in training_log_paths(operation_id):
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for record in parse_training_records(text):
            timestep = record.get("total_timesteps")
            if timestep is not None and first_step <= timestep <= last_step:
                records.append((attempt, record))
    return records


def render_markdown(records: list[tuple[int, dict[str, float]]]) -> str:
    metric_names = sorted(
        {
            metric
            for _, record in records
            for metric in record
            if metric != "total_timesteps"
        }
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
    parser.add_argument("--operation", required=True)
    parser.add_argument("--from-step", required=True, type=int)
    parser.add_argument("--to-step", required=True, type=int)
    arguments = parser.parse_args(argv)
    if re.fullmatch(r"T[1-9]\d*", arguments.operation) is None:
        parser.error("--operation must be a training operation ID such as T1")
    if arguments.from_step < 0 or arguments.from_step > arguments.to_step:
        parser.error("timestep bounds must satisfy 0 <= --from-step <= --to-step")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    if not training_log_paths(arguments.operation):
        print(
            f"no training logs found for operation {arguments.operation}",
            file=sys.stderr,
        )
        return 1
    print(
        render_markdown(
            selected_records(
                arguments.operation, arguments.from_step, arguments.to_step
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
