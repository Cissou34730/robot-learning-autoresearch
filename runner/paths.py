"""Filesystem locations the Runner operates on.

Every Runner module reads these as attributes of this module rather than
importing the values, so redirecting the Runner at a sandbox is a single
rebinding here instead of one per module. The derived paths are independent
constants: rebinding `ROOT` alone does not recompute them.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_DIR = ROOT / "campaigns"
PI_WORKSPACE_DIR = ROOT / "pi_workspace"
RUNNER_STATE_DIR = ROOT / "runner" / "state"
RESEARCH_DIR = CAMPAIGNS_DIR
LOG_PATH = CAMPAIGNS_DIR / "EXPERIMENTS.md"
RESULTS_PATH = CAMPAIGNS_DIR / "results.jsonl"
OPERATION_REQUEST_PATH = PI_WORKSPACE_DIR / "operation_request.json"
STATE_PATH = RUNNER_STATE_DIR / "research_state.json"
TRAINING_LOG_DIR = CAMPAIGNS_DIR / "training_logs"
SCIENTIFIC_MODEL_PATH = PI_WORKSPACE_DIR / "scientific_model.md"
GOAL_PATH = RUNNER_STATE_DIR / "GOAL_REACHED"
RECOVERY_PENDING_PATH = RUNNER_STATE_DIR / "RECOVERY_PENDING"
RESTART_PENDING_PATH = RUNNER_STATE_DIR / "RESTART_PENDING"
CANDIDATE_ROOT = ROOT / "models" / "candidates"
# Completed measurements are research history: they outlive the checkpoints they
# describe, so they live outside the disposable candidate tree.
EVALUATION_DIR = CAMPAIGNS_DIR / "evaluations"


def training_log_path(operation_id: str, attempt: int, campaign_id: str) -> Path:
    filename = f"{operation_id.lower()}-attempt-{attempt}.log"
    return TRAINING_LOG_DIR / campaign_id / filename


def campaign_candidate_root(campaign_id: str) -> Path:
    """Candidate directory scoped to a specific campaign."""
    return CANDIDATE_ROOT / campaign_id


def campaign_checkpoint_root(campaign_id: str) -> Path:
    """Training candidate archive scoped to one campaign."""
    return EVALUATION_DIR.parent / "checkpoints" / "candidates" / campaign_id


def campaign_evaluation_dir(campaign_id: str) -> Path:
    """Evaluation artifacts directory scoped to a specific campaign."""
    return EVALUATION_DIR / campaign_id


def campaign_retained_root(campaign_id: str) -> Path:
    """Retained-lineage archive scoped to a specific campaign."""
    return EVALUATION_DIR.parent / "checkpoints" / "retained" / campaign_id
