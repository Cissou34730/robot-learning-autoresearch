"""The scenario studied by this repository.

This package is the single, static boundary between the generic AutoResearch
machinery and everything specific to the current research problem. Generic code
imports only the functions explicitly exported here and never reaches into
scenario submodules.

Replacing the research problem means replacing this package (and, when the task
itself changes, the protected benchmark and physics assets). It must not require
redesigning the runner, training, lineage, or benchmark lifecycle.
"""

from robot_learning.scenario.brief import render_scenario_evidence
from robot_learning.scenario.environment import make_training_env
from robot_learning.scenario.evaluation import (
    evaluate_research_model,
    summarize_research_evaluations,
)
from robot_learning.scenario.final_benchmark import evaluate_final_model
from robot_learning.scenario.viewer import (
    make_training_viewer_callback,
    watch_scenario_policy,
)

__all__ = [
    "evaluate_final_model",
    "evaluate_research_model",
    "make_training_env",
    "make_training_viewer_callback",
    "render_scenario_evidence",
    "summarize_research_evaluations",
    "watch_scenario_policy",
]
