"""Adapter between the generic runner and the protected task-reference panel.

The protected implementation stays untouched in `robot_learning/benchmark/`.
This module exists only so the generic core keeps importing the scenario
boundary and never reaches into the benchmark package.
"""

from collections.abc import Callable
from pathlib import Path

from robot_learning.benchmark.reference_evaluation import (
    evaluate_task_reference_model as _protected_evaluate_task_reference_model,
)
from robot_learning.benchmark.reference_evaluation import (
    task_reference_panel as _protected_task_reference_panel,
)


def task_reference_panel() -> dict:
    return _protected_task_reference_panel()


def evaluate_task_reference_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    return _protected_evaluate_task_reference_model(
        model_path,
        algorithm=algorithm,
        progress_callback=progress_callback,
    )
