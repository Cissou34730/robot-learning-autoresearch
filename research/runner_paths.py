"""Filesystem locations the Runner operates on.

Every Runner module reads these as attributes of this module rather than
importing the values, so redirecting the Runner at a sandbox is a single
rebinding here instead of one per module. The derived paths are independent
constants: rebinding `ROOT` alone does not recompute them.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
LOG_PATH = RESEARCH_DIR / "EXPERIMENTS.md"
RESULTS_PATH = RESEARCH_DIR / "results.jsonl"
PROPOSAL_PATH = RESEARCH_DIR / "proposal.json"
POSTMORTEM_PATH = RESEARCH_DIR / "postmortems.md"
EVALUATION_REQUEST_PATH = RESEARCH_DIR / "evaluation_request.json"
STATE_PATH = RESEARCH_DIR / "research_state.json"
TRAINING_LOG_DIR = RESEARCH_DIR / "training_logs"
BASELINE_PENDING_PATH = RESEARCH_DIR / "BASELINE_PENDING"
RECOVERY_PENDING_PATH = RESEARCH_DIR / "RECOVERY_PENDING"
RESTART_PENDING_PATH = RESEARCH_DIR / "RESTART_PENDING"
GOAL_PATH = RESEARCH_DIR / "GOAL_REACHED"
ACCEPTED_DIR = RESEARCH_DIR / "checkpoints" / "accepted"
CANDIDATE_ROOT = ROOT / "models" / "candidates"
# Completed measurements are research history: they outlive the checkpoints they
# describe, so they live outside the disposable candidate tree.
EVALUATION_DIR = RESEARCH_DIR / "evaluations"


def training_log_path(experiment: int, attempt: int, campaign_id: str | None = None) -> Path:
	if campaign_id:
		return TRAINING_LOG_DIR / campaign_id / f"experiment-{experiment}-attempt-{attempt}.log"
	return TRAINING_LOG_DIR / f"experiment-{experiment}-attempt-{attempt}.log"


def campaign_candidate_root(campaign_id: str | None) -> Path:
	"""Candidate directory scoped to a specific campaign, or legacy CANDIDATE_ROOT if campaign_id is None."""
	if campaign_id is None:
		return CANDIDATE_ROOT
	return CANDIDATE_ROOT / campaign_id


def campaign_checkpoint_root(campaign_id: str | None) -> Path:
	"""Challenger checkpoint archive scoped to a specific campaign, or legacy path if campaign_id is None."""
	if campaign_id is None:
		return RESEARCH_DIR / "checkpoints" / "challengers"
	return RESEARCH_DIR / "checkpoints" / "challengers" / campaign_id


def campaign_evaluation_dir(campaign_id: str | None) -> Path:
	"""Evaluation artifacts directory scoped to a specific campaign, or legacy EVALUATION_DIR if campaign_id is None."""
	if campaign_id is None:
		return EVALUATION_DIR
	return EVALUATION_DIR / campaign_id

