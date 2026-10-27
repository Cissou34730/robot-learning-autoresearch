"""Filesystem locations the Runner operates on.

Every Runner module reads these as attributes of this module rather than
importing the values, so redirecting the Runner at a sandbox is a single
rebinding here instead of one per module. The derived paths are independent
constants: rebinding `ROOT` alone does not recompute them.

`ROOT` is the campaign root: the repository holding PI-owned code and campaign
evidence, where the Runner commits. `HARNESS_ROOT` holds the harness itself.
`ROBOT_LEARNING_CAMPAIGN_ROOT` selects a separate campaign root; without it both
are the same folder. Repository-relative paths form one logical namespace that
`locate` maps to the owning root.
"""

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

CAMPAIGN_ROOT_ENV = "ROBOT_LEARNING_CAMPAIGN_ROOT"
HARNESS_ROOT = Path(__file__).resolve().parent.parent
ROOT = (
    Path(os.environ[CAMPAIGN_ROOT_ENV]).resolve()
    if os.environ.get(CAMPAIGN_ROOT_ENV)
    else HARNESS_ROOT
)
SPLIT = ROOT != HARNESS_ROOT
CAMPAIGN_OWNED_PREFIXES = (
    "robot_learning",
    "campaigns",
    "pi_workspace",
    "runner/state",
    "models",
    "reports",
    ".copilot",
)


def is_campaign_owned(relative: str | Path) -> bool:
    normalized = PurePosixPath(str(relative).replace("\\", "/")).as_posix()
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in CAMPAIGN_OWNED_PREFIXES
    )


# Harness files a running campaign loads; documents and tests never affect it.
HARNESS_RUNTIME_PREFIXES = ("benchmark/", "contracts/", "runner/", "tools/")
HARNESS_RUNTIME_FILES = frozenset({"pyproject.toml", "uv.lock"})


def is_harness_runtime(relative: str | Path) -> bool:
    normalized = str(relative).replace("\\", "/").lstrip("/").lower()
    return normalized in HARNESS_RUNTIME_FILES or normalized.startswith(
        HARNESS_RUNTIME_PREFIXES
    )


def locate(relative: str | Path) -> Path:
    """Physical location of a repository-relative logical path."""
    normalized = str(relative).replace("\\", "/")
    logical = PurePosixPath(normalized)
    if (
        not normalized
        or logical.is_absolute()
        or PureWindowsPath(normalized).drive
        or ".." in logical.parts
        or ":" in normalized
    ):
        raise ValueError(f"repository path must be relative: {relative}")
    relative = Path(*logical.parts)
    if SPLIT and not is_campaign_owned(relative):
        return HARNESS_ROOT / relative
    return ROOT / relative


def logical_path(path: Path) -> str:
    """Logical name of a physical file, rejecting files in the wrong root."""
    resolved = path.resolve()
    roots = (ROOT, HARNESS_ROOT) if SPLIT else (ROOT,)
    for root in roots:
        try:
            relative = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if locate(relative).resolve() == resolved:
            return relative
    raise ValueError(f"path is outside its owning repository: {path}")


def python_environment(campaign_root: Path | None = None) -> dict[str, str]:
    """Expose campaign science and harness packages to child interpreters."""
    environment = os.environ.copy()
    if SPLIT or campaign_root is not None:
        root = campaign_root or ROOT
        environment[CAMPAIGN_ROOT_ENV] = str(root)
        entries = [str(root), str(HARNESS_ROOT)]
        if environment.get("PYTHONPATH"):
            entries.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(entries)
    return environment


def git_admin_path(campaign_root: Path) -> Path:
    """Git administration directory: outside the worktree and publication."""
    admin = campaign_root / ".git"
    if admin.is_file():
        pointer = admin.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir:"):
            raise RuntimeError(f"Cannot locate Git administration for {campaign_root}.")
        admin = (campaign_root / pointer.split(":", 1)[1].strip()).resolve()
    return admin


def reset_marker_path(campaign_root: Path) -> Path:
    """Unfinished-reset record in Git administration, outside the worktree."""
    return git_admin_path(campaign_root) / "reset-incomplete.json"


def stop_request_path(campaign_root: Path) -> Path:
    """The one cooperative stop request of a campaign, whoever launched it."""
    return git_admin_path(campaign_root) / "stop-request"


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
