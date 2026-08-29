"""The scenario studied by this repository.

This package is the single, static boundary between the generic AutoResearch
machinery and everything specific to the current research problem. Generic code
imports these four functions and nothing else below this package.

Replacing the research problem means replacing this package (and, when the task
itself changes, the protected benchmark and physics assets). It must not require
redesigning the runner, training, lineage, or benchmark lifecycle.
"""

from robot_learning.scenario.brief import render_scenario_evidence
from robot_learning.scenario.environment import make_training_env
from robot_learning.scenario.evaluation import evaluate_research_model
from robot_learning.scenario.final_benchmark import evaluate_final_model

__all__ = [
    "evaluate_final_model",
    "evaluate_research_model",
    "make_training_env",
    "render_scenario_evidence",
]
