"""Adapter between the generic runner and the protected final benchmark.

The protected implementation stays untouched in `robot_learning/benchmark/`.
Only this module translates its result into the single boolean the generic
AutoResearch lifecycle needs.
"""

from collections.abc import Callable
from pathlib import Path

from robot_learning.benchmark.final_benchmark import (
    evaluate_final_model as _protected_evaluate_final_model,
)
from robot_learning.benchmark.final_contract import FINAL_SUCCESS_PERCENT


def evaluate_final_model(
    model_path: Path,
    *,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    metrics = _protected_evaluate_final_model(
        model_path,
        algorithm=algorithm,
        progress_callback=progress_callback,
    )
    return {
        **metrics,
        "goal_reached": float(metrics["success_percent"]) >= FINAL_SUCCESS_PERCENT,
    }
