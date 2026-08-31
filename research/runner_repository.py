"""Durable Runner persistence: campaign state, history, checkpoints and Git.

Every operation here is explicit and path-scoped. Nothing in this module makes
a protocol decision; it executes the ones the Runner already took.
"""

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from research import runner_paths as paths

# Detailed evidence belongs to the evaluation artifact, not to the compact
# history or the protocol state.
DETAILED_EVIDENCE_FIELDS = ("episode_results", "research_evidence")
# Transient Runner-owned control files: they carry a single phase handover and
# are discarded, never accumulated. They are Git-ignored and are never history.
RUNNER_CONTROL_PATHS = {
    "research/proposal.json",
    "research/evaluation_request.json",
}
# Durable Runner-owned campaign memory: the lifecycle state the Runner rewrites
# mid-experiment -- including the identity it allocates before validation --
# the campaign history, and the evidence and checkpoints operating the campaign
# produces. Operating the campaign is never a researcher intervention, so these
# leave the scientific change set and are committed on their own.
RUNNER_MEMORY_PATHS = {
    "research/research_state.json",
    "research/results.jsonl",
    "research/EXPERIMENTS.md",
    "research/postmortems.md",
    "research/BASELINE_PENDING",
}
RUNNER_MEMORY_PREFIXES = (
    "research/evaluations/",
    "research/checkpoints/accepted/",
    "research/checkpoints/retained/",
)
ARTIFACT_FILES = ("model.zip", "artifact.json")
OPTIONAL_ARTIFACT_FILES = ("vecnormalize.pkl", "replay_buffer.pkl")
EXPERIMENT_LOG_HEADER = (
    "# Experiment log\n"
    "\n"
    "| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |\n"
    "|---:|---|---|---|---:|---:|---|\n"
)


# --- Git -------------------------------------------------------------------


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=paths.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def status_paths(scope: tuple[str, ...]) -> list[str]:
    """Every path Git reports as changed, including both sides of a rename."""
    output = git(
        "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *scope
    )
    fields = [field for field in output.split("\0") if field]
    changed: list[str] = []
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        code, destination = entry[:2], entry[3:].strip()
        # `-z` reverses rename/copy entries: the origin follows in its own field.
        if code[:1] in {"R", "C"} and index < len(fields):
            origin = fields[index].strip()
            index += 1
            if origin:
                changed.append(origin)
        if destination:
            changed.append(destination)
    return changed


def is_runner_memory(path: str) -> bool:
    relative = path.replace("\\", "/")
    return relative in RUNNER_MEMORY_PATHS or relative.startswith(
        RUNNER_MEMORY_PREFIXES
    )


def is_runner_owned(path: str) -> bool:
    return path.replace("\\", "/") in RUNNER_CONTROL_PATHS or is_runner_memory(path)


def scientific_change_paths(changed: list[str]) -> list[str]:
    """The researcher intervention alone: campaign memory is not a change to it."""
    return [path for path in changed if not is_runner_owned(path)]


def assert_research_surface() -> list[str]:
    return scientific_change_paths(status_paths((".",)))


def changed_runner_memory() -> list[str]:
    return [path for path in status_paths((".",)) if is_runner_memory(path)]


def committed_change_paths(parent: str) -> list[str]:
    """Paths changed by commits since `parent`.

    Renames are reported as two independent sides so neither the vanished origin
    nor the new destination can be lost, exactly as the worktree scan does.
    """
    output = git("diff", "--name-only", "--no-renames", parent, "HEAD", "--")
    return [line.strip() for line in output.splitlines() if line.strip()]


def scientific_delta(parent: str) -> list[str]:
    """Every scientific path changed since the scientific parent.

    Committing a file does not remove it from the experiment that changed it, so
    the delta spans both the commits made since the parent and the working tree.
    """
    committed = committed_change_paths(parent) if parent else []
    return scientific_change_paths(
        list(dict.fromkeys([*committed, *status_paths((".",))]))
    )


def require_resolvable_commit(commit: str) -> None:
    """A rollback baseline that no longer exists must fail, never silently no-op."""
    try:
        git("cat-file", "-e", f"{commit}^{{commit}}")
    except RuntimeError as error:
        raise RuntimeError(
            f"the scientific parent {commit} no longer resolves to a commit; "
            "the code lineage decision cannot be applied safely"
        ) from error


def tracked_at_commit(commit: str, path: str) -> bool:
    """Whether `path` existed at `commit`, deciding restore versus removal."""
    return bool(git("ls-tree", "-r", "--name-only", commit, "--", path).strip())


def restore_paths(commit: str, restorable: list[str]) -> None:
    git("restore", "--source", commit, "--", *restorable)


def remove_created_path(created: Path) -> None:
    if created.is_dir():
        shutil.rmtree(created)
    else:
        created.unlink(missing_ok=True)


def apply_code_lineage_decision(plan: dict) -> None:
    if plan["restore"]:
        restore_paths(plan["parent"], plan["restore"])
    for created_path in plan["remove_created"]:
        remove_created_path(created_path)


def stage_existing_or_tracked(candidates: list[str]) -> list[str]:
    stageable = [
        path
        for path in dict.fromkeys(candidates)
        if (paths.ROOT / path).exists() or git("ls-files", "--", path).strip()
    ]
    if stageable:
        git("add", "-A", "--", *stageable)
    return stageable


def commit_and_push(message: str, scope: tuple[str, ...] = ()) -> None:
    git("commit", "-m", message, *(("--", *scope) if scope else ()))
    try:
        git("push", "origin", "HEAD")
    except RuntimeError as error:
        raise RuntimeError(
            "commit created locally but push to origin failed; "
            "the research loop stopped to avoid unpublished history"
        ) from error


def commit_paths(message: str, scope: list[str]) -> bool:
    """Commit exactly these paths; every other worktree or index entry is left alone."""
    stageable = stage_existing_or_tracked(scope)
    if not stageable:
        return False
    if not git("diff", "--cached", "--name-only", "--", *stageable).strip():
        return False
    commit_and_push(message, tuple(stageable))
    return True


def commit_runner_memory(message: str) -> bool:
    return commit_paths(message, changed_runner_memory())


def commit_result(index: int, change: str) -> None:
    """An invalid experiment is already finished, so its memory is durable now."""
    commit_runner_memory(f"exp {index}: {change}")


def commit_lineage_decision(
    experiment: int,
    selected: str,
    *,
    code_action: str = "keep",
    state: dict | None = None,
) -> None:
    # Two owners, two commits: the surviving science first, then the campaign
    # memory that must outlive it whatever the next lineage decision does.
    reverted = code_action == "revert"
    commit_paths(
        f"experiment {experiment} code reverted to its scientific parent"
        if reverted
        else f"experiment {experiment} code retained for {selected}",
        assert_research_surface(),
    )
    if state is not None:
        # Only durable science closes the lineage: until the commit above has
        # been published, the rollback anchor must stay recoverable.
        state["pending_scientific_parent"] = None
        atomic_write_json(paths.STATE_PATH, state)
    commit_runner_memory(f"select experiment {experiment} lineage: {selected}")


# --- campaign state --------------------------------------------------------


def _atomic_replace(temporary: Path, destination: Path) -> None:
    for attempt in range(20):
        try:
            temporary.replace(destination)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def atomic_write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _atomic_replace(temporary, path)


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    _atomic_replace(temporary, path)


def read_state() -> dict:
    """The persisted lifecycle state exactly as written, without any contract check."""
    return json.loads(paths.STATE_PATH.read_text(encoding="utf-8"))


def load_state(
    *,
    allow_unmeasured: bool = False,
    allow_missing_artifact: bool = False,
) -> dict:
    if not paths.STATE_PATH.exists():
        raise RuntimeError("research state is missing; refusing to run")
    state = read_state()
    required = {"schema_version", "accepted_artifact"}
    missing = required - set(state)
    if missing:
        raise RuntimeError(f"research state is incomplete: {sorted(missing)}")
    if state["schema_version"] != 2:
        raise RuntimeError("unsupported research state schema")
    if not allow_missing_artifact:
        artifact = paths.ROOT / state["accepted_artifact"]
        for filename in ARTIFACT_FILES:
            if not (artifact / filename).exists():
                raise RuntimeError(f"accepted artifact is incomplete: {filename}")
    if not allow_unmeasured and state.get("accepted_metrics") is None:
        raise RuntimeError("accepted checkpoint has no baseline metrics")
    return state


def anchor_scientific_parent(state: dict) -> str:
    """The scientific state the currently unfinished research originates from.

    Captured once and then preserved across researcher retries, launcher
    restarts, training recovery, evaluation rounds and invalid experiments, so a
    rejection returns to the last closed lineage rather than to whatever HEAD
    happens to be when the runner next looks. Only a completed lineage decision
    clears it.
    """
    parent = str(state.get("pending_scientific_parent") or "").strip()
    if not parent:
        parent = git("rev-parse", "HEAD").strip()
    state["pending_scientific_parent"] = parent
    return parent


# --- campaign history ------------------------------------------------------


def evaluation_reference(evaluation: dict) -> dict:
    """Everything except the detail the evaluation artifact already holds."""
    return {
        key: value
        for key, value in evaluation.items()
        if key not in DETAILED_EVIDENCE_FIELDS
    }


def measurement_record(metrics: dict) -> dict:
    """State keeps the episode outcomes paired comparison needs, nothing more.

    Researcher-defined evidence stays in the artifact so the protocol state
    never becomes a second, opaque evidence store.
    """
    return {
        key: value
        for key, value in metrics.items()
        if key not in ("model", "research_evidence")
    }


def compact_result_record(result: dict) -> dict:
    """History keeps identity, score and artifact references, never the evidence."""
    record = dict(result)
    candidates = record.get("candidates")
    if isinstance(candidates, list):
        record["candidates"] = [
            {
                **candidate,
                "evaluations": [
                    evaluation_reference(item)
                    for item in candidate.get("evaluations") or []
                ],
            }
            if isinstance(candidate, dict)
            else candidate
            for candidate in candidates
        ]
    requested = record.get("requested_evaluations")
    if isinstance(requested, list):
        record["requested_evaluations"] = [
            {**item, "metrics": evaluation_reference(item.get("metrics") or {})}
            if isinstance(item, dict)
            else item
            for item in requested
        ]
    return record


def result_records() -> list[dict]:
    """The authoritative experiment history, oldest first."""
    if not paths.RESULTS_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in paths.RESULTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def latest_recorded_experiment() -> int | None:
    records = result_records()
    return int(records[-1]["index"]) if records else None


def experiment_log_row(record: dict) -> str:
    def cell(value: object) -> str:
        return " ".join(str(value).replace("|", "/").split())

    return (
        f"| {record['index']} | {cell(record.get('recorded_at', '-'))} | "
        f"{cell(record.get('change', '-'))} | {cell(record.get('hypothesis', '-'))} | "
        f"{cell(record.get('candidate_success_percent', '-'))} | "
        f"{cell(record.get('candidate_seeds_passed', '-'))} | "
        f"{cell(record.get('verdict', '-'))} |"
    )


def render_experiment_log(records: list[dict]) -> str:
    return EXPERIMENT_LOG_HEADER + "".join(
        experiment_log_row(record) + "\n" for record in records
    )


def regenerate_experiment_log() -> None:
    """Rewrite the human-readable view from the authoritative history.

    Written atomically so an interruption leaves either the previous derived
    view or the current one, never a partial second history.
    """
    atomic_write_text(paths.LOG_PATH, render_experiment_log(result_records()))


def synchronize_experiment_log() -> None:
    """Recover the derived view if a crash landed between append and regeneration."""
    if not paths.LOG_PATH.exists():
        regenerate_experiment_log()
        return
    expected = render_experiment_log(result_records())
    if paths.LOG_PATH.read_text(encoding="utf-8") != expected:
        atomic_write_text(paths.LOG_PATH, expected)


def append_result(result: dict) -> None:
    """Record one experiment in the authoritative history, then derive the view."""
    record = compact_result_record(result)
    record.setdefault("recorded_at", time.strftime("%Y-%m-%d"))
    with paths.RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    regenerate_experiment_log()


# --- checkpoints and artifacts ---------------------------------------------


def require_complete_artifact(artifact: Path, description: str) -> None:
    for filename in ARTIFACT_FILES:
        if not (artifact / filename).is_file():
            raise ValueError(f"{description} is incomplete: {filename}")


def artifact_fingerprint(artifact: Path) -> str:
    digest = hashlib.sha256()

    for filename in ARTIFACT_FILES:
        digest.update((artifact / filename).read_bytes())

    for filename in OPTIONAL_ARTIFACT_FILES:
        path = artifact / filename
        if path.is_file():
            digest.update(path.read_bytes())

    return digest.hexdigest()


def copy_artifact(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    for filename in ARTIFACT_FILES:
        shutil.copyfile(source / filename, destination / filename)

    for filename in OPTIONAL_ARTIFACT_FILES:
        source_file = source / filename
        destination_file = destination / filename

        if source_file.is_file():
            shutil.copyfile(source_file, destination_file)
        else:
            destination_file.unlink(missing_ok=True)


def remove_heavyweight_artifacts(artifact: Path) -> None:
    for filename in ("model.zip", "vecnormalize.pkl", "replay_buffer.pkl"):
        (artifact / filename).unlink(missing_ok=True)


def evaluation_artifact_paths(evaluations: list[dict] | None) -> list[str]:
    return [
        str(item["evaluation_artifact"])
        for item in evaluations or []
        if item.get("evaluation_artifact")
    ]


def archive_candidates(
    index: int,
    contenders: list[dict],
    config: dict,
) -> list[dict]:
    destination = (
        paths.RESEARCH_DIR / "checkpoints" / "challengers" / f"experiment-{index}"
    )
    if destination.exists():
        raise RuntimeError(f"challenger archive already exists: {destination}")
    destination.mkdir(parents=True)
    archived: list[dict] = []
    for contender in contenders:
        if contender["kind"] != "candidate":
            continue
        artifact = destination / contender["name"]
        copy_artifact(contender["path"], artifact)
        archived.append(
            {
                "name": contender["name"],
                "artifact": str(artifact.relative_to(paths.ROOT)),
                "timesteps": int(contender["timesteps"]),
                "evaluations": [],
            }
        )
    atomic_write_json(destination / "parameters.json", config)
    atomic_write_json(
        destination / "inventory.json",
        {
            "schema_version": 1,
            "candidates": archived,
        },
    )
    return archived
