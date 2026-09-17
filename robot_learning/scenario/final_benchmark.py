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


def research_panel_overlaps_protected(seed: int, episodes: int) -> bool:
    """Whether a research episode panel ``[seed, seed + episodes)`` overlaps the
    protected benchmark episodes.

    The protected seed range stays inside this adapter; the generic Runner never
    reads it and the validation error never names it.
    """
    from robot_learning.benchmark import final_contract

    research_start = seed
    research_stop = seed + episodes
    protected_start = final_contract.EVALUATION_SEED
    protected_stop = final_contract.EVALUATION_SEED + final_contract.EVALUATION_EPISODES
    return max(research_start, protected_start) < min(research_stop, protected_stop)


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
