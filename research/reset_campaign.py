"""Human-only campaign reset implementation.

The PowerShell entry point owns cross-process exclusion. This module performs
read-only preflight before creating a recoverable backup and mutating the current
branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository

EPHEMERAL_PATHS = (
    "research/GOAL_REACHED",
    "research/RECOVERY_PENDING",
    "research/RESTART_PENDING",
    "research/proposal.json",
    "research/evaluation_request.json",
    "research/training_logs",
    "research/evaluations",
    "research/last_train_summary.md",
    "research/last_evaluation.json",
    "research/brief.md",
    "models/candidates",
)
CAMPAIGN_PATHS = (
    "research/EXPERIMENTS.md",
    "research/results.jsonl",
    "research/postmortems.md",
    "research/archive.md",
    "research/research_state.json",
    "research/BASELINE_PENDING",
    "research/checkpoints",
    *EPHEMERAL_PATHS,
)
TASK_COMPATIBILITY_PATHS = (
    "robot_learning/benchmark/final_contract.py",
    "robot_learning/benchmark/reference_contract.py",
    "robot_learning/benchmark/spec.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
)
RESET_OPERATION_VERSION = 1


def git(*arguments: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=paths.ROOT,
        check=False,
        capture_output=True,
        text=text,
    )
    if result.returncode:
        error = (
            result.stderr.strip() if text else result.stderr.decode(errors="replace")
        )
        raise RuntimeError(f"git {' '.join(arguments)} failed: {error}")
    return result.stdout


def resolve_commit(reference: str, description: str) -> str:
    if not reference.strip():
        raise ValueError(f"{description} is required")
    return str(
        git("rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}")
    ).strip()


def reset_backup_root() -> Path:
    backup = Path(
        str(
            git(
                "rev-parse",
                "--path-format=absolute",
                "--git-path",
                "research-reset-backups",
            )
        ).strip()
    ).resolve()
    administrative_roots = {
        Path(
            str(git("rev-parse", "--path-format=absolute", option)).strip()
        ).resolve()
        for option in ("--git-dir", "--git-common-dir")
    }
    if backup.name != "research-reset-backups" or backup.parent not in administrative_roots:
        raise RuntimeError(
            f"Git resolved an unsafe reset-maintenance path: {backup}"
        )
    return backup


def git_administrative_path(option: str) -> Path:
    return Path(
        str(git("rev-parse", "--path-format=absolute", option)).strip()
    ).resolve()


def repository_identity() -> dict[str, str]:
    return {
        "root": str(paths.ROOT.resolve()),
        "git_dir": str(git_administrative_path("--git-dir")),
        "git_common_dir": str(git_administrative_path("--git-common-dir")),
        "branch": str(git("symbolic-ref", "--quiet", "--short", "HEAD")).strip(),
    }


def path_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        raise RuntimeError(f"reset cannot fingerprint unsupported path: {path}")
    digest.update(b"directory\0")
    for item in sorted(
        path.rglob("*"), key=lambda value: value.relative_to(path).as_posix()
    ):
        relative = item.relative_to(path).as_posix().encode()
        if item.is_dir():
            digest.update(b"directory\0" + relative + b"\0")
        elif item.is_file():
            digest.update(b"file\0" + relative + b"\0")
            digest.update(item.read_bytes())
        else:
            raise RuntimeError(f"reset cannot fingerprint unsupported path: {item}")
    return digest.hexdigest()


def normalize_targets(relative_paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for relative in dict.fromkeys(relative_paths):
        target = safe_path(relative)
        normalized.append(target.relative_to(paths.ROOT.resolve()).as_posix())
    return normalized


def new_operation(mode: str, source: str | None, targets: list[str]) -> dict:
    operation = {
        "schema_version": RESET_OPERATION_VERSION,
        "mode": mode,
        "source_commit": source,
        "original_head": str(git("rev-parse", "HEAD")).strip(),
        "repository": repository_identity(),
        "targeted_paths": normalize_targets(targets),
        "pre_reset": [],
        "commits": [],
        "progress": "planned",
    }
    if mode == "fresh":
        operation["recipe_source_commit"] = source
    else:
        operation["baseline_source_commit"] = source
    return operation


def commit_files(commit: str) -> set[str]:
    return {
        line.strip()
        for line in str(git("ls-tree", "-r", "--name-only", commit)).splitlines()
        if line.strip()
    }


def git_json(commit: str, relative: str) -> dict:
    try:
        value = git("show", f"{commit}:{relative}")
        parsed = json.loads(str(value))
    except (RuntimeError, json.JSONDecodeError) as error:
        raise ValueError(f"{relative} is missing or invalid at {commit}") from error
    if not isinstance(parsed, dict):
        raise TypeError(f"{relative} must contain a JSON object at {commit}")
    return parsed


def git_bytes(commit: str, relative: str) -> bytes:
    return bytes(git("show", f"{commit}:{relative}", text=False))


def ensure_clean_repository() -> None:
    git("symbolic-ref", "--quiet", "--short", "HEAD")
    git("remote", "get-url", "origin")
    if str(git("status", "--porcelain", "--untracked-files=all")).strip():
        raise RuntimeError(
            "the working tree is not clean; commit or resolve its changes before resetting research"
        )


def safe_path(relative: str) -> Path:
    normalized = str(relative).replace("\\", "/")
    requested = Path(normalized)
    if (
        not normalized
        or requested.is_absolute()
        or PureWindowsPath(normalized).drive
        or ".." in requested.parts
    ):
        raise ValueError(f"repository path must be relative: {relative}")
    root = paths.ROOT.resolve()
    candidate = root / requested
    cursor = candidate
    while cursor != root:
        if cursor.exists() and cursor.is_symlink():
            raise RuntimeError(f"reset refuses linked paths: {cursor}")
        if os.name == "nt" and cursor.exists():
            try:
                import ctypes

                attributes = ctypes.windll.kernel32.GetFileAttributesW(str(cursor))
                if attributes != -1 and attributes & 0x400:
                    raise RuntimeError(f"reset refuses linked paths: {cursor}")
            except AttributeError:
                pass
        cursor = cursor.parent
    return candidate.resolve()


def require_unlocked(path: Path) -> None:
    if not path.is_file() or os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(str(path), 0x80000000, 0, None, 3, 0x80, None)
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        raise RuntimeError(f"reset target is locked: {path}")
    ctypes.windll.kernel32.CloseHandle(handle)


def preflight_targets(relative_paths: list[str]) -> None:
    for relative in dict.fromkeys(relative_paths):
        target = safe_path(relative)
        if not target.exists():
            continue
        items = [target]
        if target.is_dir():
            items.extend(target.rglob("*"))
        for item in items:
            safe_path(item.relative_to(paths.ROOT).as_posix())
            require_unlocked(item)


def scientific_plan(commit: str) -> dict:
    return protocol.plan_lineage_restore({"scientific_commit": commit})


def plan_paths(plan: dict) -> list[str]:
    return [
        *plan["restore"],
        *(repository.repo_relative_path(path) for path in plan["remove_created"]),
    ]


def verify_task_compatibility(commit: str) -> None:
    changed = str(
        git("diff", "--name-only", commit, "HEAD", "--", *TASK_COMPATIBILITY_PATHS)
    ).strip()
    if changed:
        raise ValueError(
            "the human-defined task differs from the requested source revision: "
            + ", ".join(changed.splitlines())
        )


def verify_recipe_source(commit: str) -> None:
    files = commit_files(commit)
    if "research/current_params.json" not in files:
        raise ValueError("recipe source is missing research/current_params.json")
    git_json(commit, "research/current_params.json")
    verify_task_compatibility(commit)


def artifact_fingerprint_at_commit(commit: str, artifact: str) -> str:
    digest = hashlib.sha256()
    for name in (*repository.ARTIFACT_FILES, *repository.OPTIONAL_ARTIFACT_FILES):
        relative = f"{artifact.rstrip('/')}/{name}"
        try:
            content = git_bytes(commit, relative)
        except RuntimeError:
            if name in repository.ARTIFACT_FILES:
                raise ValueError(
                    f"baseline artifact is missing required file: {relative}"
                ) from None
            continue
        digest.update(content)
    return digest.hexdigest()


def baseline_restore_paths(commit: str, state: dict) -> list[str]:
    source = commit_files(commit)
    current = commit_files("HEAD")
    campaign_id = str(state["campaign"]["id"])
    prefixes = (
        "research/checkpoints/",
        f"research/evaluations/{campaign_id}/",
        f"research/training_logs/{campaign_id}/",
    )
    fixed = {
        "research/research_state.json",
        "research/results.jsonl",
        "research/postmortems.md",
        "research/archive.md",
    }
    return sorted(
        path for path in source | current if path in fixed or path.startswith(prefixes)
    )


def verify_baseline_source(commit: str) -> tuple[dict, list[dict], list[str]]:
    state = git_json(commit, "research/research_state.json")
    if state.get("schema_version") != 4:
        raise ValueError(
            "BaselineRef does not contain a current campaign state"
        )
    repository.validate_state(state, allow_missing_artifact=True)
    working = state.get("working_lineage")
    best = state.get("best_known_lineage")
    pending_fields = (
        "pending_analysis",
        "pending_training_operation",
        "pending_closure_operation",
        "pending_scientific_parent",
        "pending_final_benchmark",
        "terminal_campaign_status",
        "official_metrics",
    )
    if (
        not isinstance(working, dict)
        or not isinstance(best, dict)
        or working.get("fingerprint") != best.get("fingerprint")
        or int(state.get("last_experiment", -1)) != 1
        or int(state.get("last_allocated_experiment", -1)) != 1
        or state.get("retained_lineages")
        or any(state.get(field) is not None for field in pending_fields)
    ):
        raise ValueError(
            "BaselineRef must be a closed measured experiment 1 with matching working and best-known roles"
        )
    scientific_commit = str(working.get("scientific_commit") or "")
    resolve_commit(scientific_commit, "BaselineRef scientific_commit")
    verify_task_compatibility(scientific_commit)
    campaign_id = str(state["campaign"]["id"])
    uuid.UUID(campaign_id)
    evaluations = working.get("evaluation_artifacts") or []
    if not evaluations:
        raise ValueError("BaselineRef has no completed development evidence")
    files = commit_files(commit)
    artifact = str(working["artifact"])
    required = {
        f"{artifact}/model.zip",
        f"{artifact}/artifact.json",
        f"{artifact}/policy_runtime.pkl",
        f"{artifact}/vecnormalize.pkl",
        *evaluations,
        "research/results.jsonl",
        "research/postmortems.md",
    }
    missing = sorted(required - files)
    if missing:
        raise ValueError(f"BaselineRef is missing required artifacts: {missing}")
    actual_fingerprint = artifact_fingerprint_at_commit(commit, artifact)
    if actual_fingerprint != working["fingerprint"]:
        raise ValueError("BaselineRef model fingerprint does not match its role record")
    metadata = git_json(commit, f"{artifact}/artifact.json")
    actual_steps = metadata.get("timesteps", metadata.get("training_steps"))
    if actual_steps is None or int(actual_steps) != int(working["training_steps"]):
        raise ValueError(
            "BaselineRef role training steps do not match artifact metadata"
        )
    raw_results = str(git("show", f"{commit}:research/results.jsonl"))
    try:
        records = [
            json.loads(line) for line in raw_results.splitlines() if line.strip()
        ]
    except json.JSONDecodeError as error:
        raise ValueError("BaselineRef results.jsonl is invalid") from error
    matching = [
        record
        for record in records
        if record.get("campaign_id") == campaign_id and record.get("index") == 1
    ]
    if len(matching) != 1:
        raise ValueError("BaselineRef history must contain exactly its experiment 1")
    record = matching[0]
    candidates = [
        candidate
        for candidate in record.get("candidates") or []
        if isinstance(candidate, dict) and candidate.get("name") == working["candidate"]
    ]
    if len(candidates) != 1 or int(candidates[0].get("timesteps", -1)) != int(
        working["training_steps"]
    ):
        raise ValueError(
            "BaselineRef history does not identify the selected checkpoint"
        )
    measurements = {
        item.get("evaluation_artifact"): item
        for item in candidates[0].get("evaluations") or []
        if isinstance(item, dict)
    }
    postmortem = str(git("show", f"{commit}:research/postmortems.md"))
    for evidence in evaluations:
        measurement = measurements.get(evidence)
        if (
            measurement is None
            or measurement.get("model_fingerprint") != working["fingerprint"]
            or measurement.get("evaluation_artifact_fingerprint")
            != hashlib.sha256(git_bytes(commit, evidence)).hexdigest()
            or evidence not in postmortem
        ):
            raise ValueError(
                f"BaselineRef cannot bind model identity to evidence {evidence}"
            )
    closure = record.get("closure_decision") or {}
    best_decision = closure.get("best_known") or {}
    if (
        record.get("status") != "closed"
        or closure.get("continue_from") != working["candidate"]
        or best_decision.get("candidate") != best["candidate"]
    ):
        raise ValueError(
            "BaselineRef history does not contain the recorded designation"
        )
    verify_task_compatibility(commit)
    return state, matching, baseline_restore_paths(commit, state)


def create_backup(relative_paths: list[str], operation: dict) -> Path:
    backup_root = reset_backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"{int(time.time())}-{uuid.uuid4()}"
    files = backup / "files"
    files.mkdir(parents=True)
    manifest: list[str] = []
    pre_reset: list[dict] = []
    for relative in operation["targeted_paths"]:
        source = safe_path(relative)
        if not source.exists():
            pre_reset.append({"path": relative, "exists": False})
            continue
        destination = files / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
            kind = "directory"
        else:
            shutil.copy2(source, destination)
            kind = "file"
        manifest.append(relative)
        pre_reset.append(
            {
                "path": relative,
                "exists": True,
                "kind": kind,
                "fingerprint": path_fingerprint(source),
            }
        )
    operation.update(
        progress="backed_up",
        backup=str(backup.resolve()),
        backed_up=manifest,
        pre_reset=pre_reset,
    )
    repository.atomic_write_json(backup / "operation.json", operation)
    return backup


def update_operation(backup: Path, operation: dict, progress: str) -> None:
    operation["progress"] = progress
    repository.atomic_write_json(backup / "operation.json", operation)


def publish_reset_changes(
    backup: Path,
    operation: dict,
    message: str,
    scope: list[str],
    purpose: str,
    force_add: list[str] | None = None,
) -> str | None:
    forced = list(dict.fromkeys(force_add or []))
    ordinary = [path for path in scope if path not in forced]
    stageable = repository.stage_existing_or_tracked(ordinary)
    if forced:
        git("add", "-f", "--", *forced)
        stageable.extend(forced)
    if not stageable or not str(
        git("diff", "--cached", "--name-only", "--", *stageable)
    ).strip():
        return None
    git("commit", "-m", message, "--", *stageable)
    commit = str(git("rev-parse", "HEAD")).strip()
    operation["commits"].append(
        {"purpose": purpose, "commit": commit, "pushed": False}
    )
    update_operation(backup, operation, f"{purpose}_committed")
    repository.push_head()
    operation["commits"][-1]["pushed"] = True
    update_operation(backup, operation, f"{purpose}_published")
    return commit


def path_is_covered(relative: str, targets: list[str]) -> bool:
    return any(
        relative == target or relative.startswith(f"{target}/")
        for target in targets
    )


def validate_recovery_operation(operation_path: str) -> tuple[Path, dict]:
    backup_root = reset_backup_root().resolve()
    candidate = Path(operation_path)
    if candidate.is_dir():
        candidate = candidate / "operation.json"
    candidate = candidate.resolve()
    if candidate.name != "operation.json" or candidate.parent.parent != backup_root:
        raise ValueError(
            f"recovery operation must be directly below {backup_root}"
        )
    try:
        operation = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid reset recovery operation: {candidate}") from error
    if (
        not isinstance(operation, dict)
        or operation.get("schema_version") != RESET_OPERATION_VERSION
    ):
        raise ValueError("unsupported reset recovery operation schema")
    if operation.get("repository") != repository_identity():
        raise ValueError(
            "reset recovery operation belongs to a different repository/worktree"
        )
    targets = operation.get("targeted_paths")
    entries = operation.get("pre_reset")
    commits = operation.get("commits")
    if (
        operation.get("mode") not in {"fresh", "baseline"}
        or not isinstance(targets, list)
        or not targets
        or len(targets) != len(set(targets))
        or not isinstance(entries, list)
        or [entry.get("path") for entry in entries if isinstance(entry, dict)]
        != targets
        or not isinstance(commits, list)
        or any(
            not isinstance(record, dict)
            or record.get("purpose") not in {"recipe", "campaign"}
            or not isinstance(record.get("commit"), str)
            or not record["commit"]
            or not isinstance(record.get("pushed"), bool)
            for record in commits
        )
    ):
        raise ValueError("reset recovery operation has an invalid target manifest")
    for relative in targets:
        safe_path(relative)
        if not (
            path_is_covered(relative, list(CAMPAIGN_PATHS))
            or protocol.is_researcher_owned(relative)
            or relative in protocol.PARAMETER_ONLY_PATHS
        ):
            raise ValueError(
                f"reset recovery operation contains an unsafe target: {relative}"
            )
    backup_files = candidate.parent / "files"
    for entry in entries:
        backup_path = backup_files / entry["path"]
        if not entry.get("exists"):
            if backup_path.exists():
                raise ValueError(f"unexpected backup content for {entry['path']}")
            continue
        if (
            entry.get("kind") not in {"file", "directory"}
            or not backup_path.exists()
        ):
            raise ValueError(f"reset backup is incomplete for {entry['path']}")
        if path_fingerprint(backup_path) != entry.get("fingerprint"):
            raise ValueError(
                f"reset backup fingerprint mismatch for {entry['path']}"
            )
    return candidate, operation


def changed_worktree_paths() -> set[str]:
    changed = set(str(git("diff", "--name-only")).splitlines())
    changed.update(str(git("diff", "--cached", "--name-only")).splitlines())
    changed.update(
        str(git("ls-files", "--others", "--exclude-standard")).splitlines()
    )
    return {path for path in changed if path}


def restore_backup_files(operation_path: Path, operation: dict) -> None:
    targets = operation["targeted_paths"]
    unrelated = sorted(
        path
        for path in changed_worktree_paths()
        if not path_is_covered(path, targets)
    )
    if unrelated:
        raise RuntimeError(
            "recovery refuses unrelated working-tree changes: " + ", ".join(unrelated)
        )
    staged = str(git("diff", "--cached", "--name-only")).splitlines()
    if staged:
        git("restore", "--staged", "--source", "HEAD", "--", *staged)
    backup_files = operation_path.parent / "files"
    for entry in operation["pre_reset"]:
        relative = entry["path"]
        target = safe_path(relative)
        remove_path(relative)
        if not entry.get("exists"):
            continue
        source = backup_files / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["kind"] == "directory":
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    for entry in operation["pre_reset"]:
        target = safe_path(entry["path"])
        if bool(entry.get("exists")) != target.exists():
            raise RuntimeError(f"recovery existence mismatch for {entry['path']}")
        if entry.get("exists") and path_fingerprint(target) != entry["fingerprint"]:
            raise RuntimeError(f"recovery fingerprint mismatch for {entry['path']}")


def tracked_recovery_paths(operation: dict) -> list[str]:
    targets = operation["targeted_paths"]
    tracked = commit_files(operation["original_head"]) | commit_files("HEAD")
    return sorted(path for path in tracked if path_is_covered(path, targets))


def recover_reset(operation_path: str) -> tuple[Path, str | None, bool]:
    manifest_path, operation = validate_recovery_operation(operation_path)
    if operation.get("progress") == "recovered":
        return manifest_path.parent, operation.get("recovery_commit"), True
    recovery_commit = operation.get("recovery_commit")
    if recovery_commit:
        if str(git("rev-parse", "HEAD")).strip() != recovery_commit:
            raise RuntimeError("recorded local recovery commit is not the current HEAD")
    else:
        commits = operation.get("commits")
        expected_head = commits[-1]["commit"] if commits else operation["original_head"]
        if str(git("rev-parse", "HEAD")).strip() != expected_head:
            raise RuntimeError("current HEAD does not match the failed reset operation")
        restore_backup_files(manifest_path, operation)
        if commits:
            stageable = tracked_recovery_paths(operation)
            if stageable:
                git("add", "-f", "-A", "--", *stageable)
            git(
                "commit",
                "-m",
                f"recover failed research reset {manifest_path.parent.name}",
                "--",
                *stageable,
            )
            recovery_commit = str(git("rev-parse", "HEAD")).strip()
            operation["recovery_commit"] = recovery_commit
            operation["recovery_pushed"] = False
            update_operation(manifest_path.parent, operation, "recovery_committed")
        elif changed_worktree_paths():
            raise RuntimeError(
                "recovery restored files but the original worktree is not clean"
            )
    if recovery_commit and not operation.get("recovery_pushed"):
        try:
            repository.push_head()
        except RuntimeError as error:
            update_operation(
                manifest_path.parent, operation, "recovery_local_unpublished"
            )
            raise RuntimeError(
                f"recovery commit {recovery_commit} is complete locally but not pushed"
            ) from error
        operation["recovery_pushed"] = True
    if changed_worktree_paths():
        raise RuntimeError("recovery completed with an unexpectedly dirty working tree")
    update_operation(manifest_path.parent, operation, "recovered")
    return manifest_path.parent, recovery_commit, True


def remove_path(relative: str) -> None:
    target = safe_path(relative)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)


def apply_restore(commit: str, relative_paths: list[str]) -> None:
    source = commit_files(commit)
    restore = [path for path in relative_paths if path in source]
    remove = [path for path in relative_paths if path not in source]
    if restore:
        repository.restore_paths(commit, restore)
    for relative in remove:
        remove_path(relative)


def validate_restored_recipe() -> None:
    if not (paths.ROOT / "pyproject.toml").is_file():
        return
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "import robot_learning.train; import robot_learning.scenario.environment",
        ],
        cwd=paths.ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"restored scientific recipe failed import validation: {result.stderr.strip()}"
        )


def empty_state(base_commit: str, recipe_source: str | None) -> dict:
    campaign_id = str(uuid.uuid4())
    return repository.empty_campaign_state(
        campaign={
            "id": campaign_id,
            "started_at": datetime.now(UTC).isoformat(),
            "base_commit": base_commit,
            "recipe_source_commit": recipe_source,
        },
        last_verdict="fresh baseline pending after research reset",
    )


def write_fresh_campaign(recipe_source: str | None) -> dict:
    for relative in CAMPAIGN_PATHS:
        remove_path(relative)
    base_commit = str(git("rev-parse", "HEAD")).strip()
    state = empty_state(base_commit, recipe_source)
    paths.RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    repository.write_state(state)
    repository.atomic_write_text(paths.RESULTS_PATH, "")
    repository.atomic_write_text(paths.LOG_PATH, repository.render_experiment_log([]))
    repository.atomic_write_text(
        paths.POSTMORTEM_PATH, "# Research postmortems\n\nNo experiments recorded.\n"
    )
    repository.atomic_write_text(
        paths.RESEARCH_DIR / "archive.md",
        "# Research archive\n\nNo archived experiments.\n",
    )
    paths.BASELINE_PENDING_PATH.write_text(
        "Fresh baseline pending after explicit research reset.\n", encoding="utf-8"
    )
    return state


def copy_external_logs(source_root: Path, campaign_id: str) -> list[str]:
    source = source_root / "research" / "training_logs" / campaign_id
    if not source.is_dir():
        raise ValueError(f"baseline training logs are missing from {source}")
    target = paths.TRAINING_LOG_DIR / campaign_id
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for log in source.glob("experiment-1-attempt-*.log"):
        destination = target / log.name
        shutil.copy2(log, destination)
        if repository.file_fingerprint(log) != repository.file_fingerprint(destination):
            raise RuntimeError(f"baseline training log changed while copying: {log}")
        copied.append(repository.repo_relative_path(destination))
    if not copied:
        raise ValueError(f"baseline training logs are missing from {source}")
    return copied


def baseline_log_source(commit: str, state: dict, requested: str | None) -> Path | None:
    campaign_id = str(state["campaign"]["id"])
    prefix = f"research/training_logs/{campaign_id}/"
    if any(path.startswith(prefix) for path in commit_files(commit)):
        return None
    if not requested:
        raise ValueError(
            "BaselineRef has no durable training log and no TrainingLogSource was supplied"
        )
    source = Path(requested).resolve()
    logs = source / "research" / "training_logs" / campaign_id
    if not logs.is_dir() or not any(logs.glob("experiment-1-attempt-*.log")):
        raise ValueError(f"baseline training logs are missing from {logs}")
    return source


def reset_fresh(recipe_ref: str | None) -> tuple[str, str | None, Path]:
    source = resolve_commit(recipe_ref, "RecipeRef") if recipe_ref else None
    plan = scientific_plan(source) if source else None
    if source:
        verify_recipe_source(source)
    targets = [*CAMPAIGN_PATHS, *(plan_paths(plan) if plan else [])]
    preflight_targets(targets)
    operation = new_operation("fresh", source, targets)
    backup = create_backup(targets, operation)
    try:
        if plan:
            repository.apply_code_lineage_decision(plan)
            validate_restored_recipe()
            update_operation(backup, operation, "recipe_restored")
            publish_reset_changes(
                backup,
                operation,
                f"restore scientific recipe from {source}",
                plan_paths(plan),
                "recipe",
            )
        state = write_fresh_campaign(source)
        update_operation(backup, operation, "campaign_initialized")
        publish_reset_changes(
            backup,
            operation,
            "reset research experiment state: fresh",
            list(CAMPAIGN_PATHS),
            "campaign",
        )
        update_operation(backup, operation, "complete")
    except Exception as error:
        operation["error"] = str(error)
        repository.atomic_write_json(backup / "operation.json", operation)
        command = f'.\\reset_research.ps1 -Recover "{backup / "operation.json"}" -Force'
        raise RuntimeError(f"reset failed; run {command}: {error}") from error
    return str(state["campaign"]["id"]), source, backup


def reset_baseline(
    reference: str, training_log_source: str | None
) -> tuple[str, str, Path]:
    source = resolve_commit(reference, "BaselineRef")
    state, records, restore = verify_baseline_source(source)
    recipe_plan = scientific_plan(str(state["working_lineage"]["scientific_commit"]))
    external_logs = baseline_log_source(source, state, training_log_source)
    targets = sorted({*CAMPAIGN_PATHS, *restore, *plan_paths(recipe_plan)})
    preflight_targets(targets)
    operation = new_operation("baseline", source, targets)
    backup = create_backup(targets, operation)
    try:
        for relative in CAMPAIGN_PATHS:
            remove_path(relative)
        repository.apply_code_lineage_decision(recipe_plan)
        validate_restored_recipe()
        apply_restore(source, restore)
        campaign_id = str(state["campaign"]["id"])
        tracked_logs = [
            path
            for path in commit_files(source)
            if path.startswith(f"research/training_logs/{campaign_id}/")
        ]
        if not tracked_logs:
            if external_logs is None:
                raise RuntimeError("baseline training-log preflight was inconsistent")
            log_source = external_logs
            if log_source == paths.ROOT.resolve():
                log_source = backup / "files"
            tracked_logs = copy_external_logs(log_source, campaign_id)
        repository.validate_state(state, allow_missing_artifact=False)
        repository.atomic_write_text(
            paths.LOG_PATH, repository.render_experiment_log(records)
        )
        update_operation(backup, operation, "baseline_restored")
        publication_scope = list(
            dict.fromkeys([*repository.status_paths((".",)), *tracked_logs])
        )
        if str(git("status", "--porcelain", "--untracked-files=all")).strip():
            publish_reset_changes(
                backup,
                operation,
                f"reset research experiment state: baseline {source}",
                publication_scope,
                "campaign",
                force_add=tracked_logs,
            )
        else:
            repository.push_head()
        update_operation(backup, operation, "complete")
    except Exception as error:
        operation["error"] = str(error)
        repository.atomic_write_json(backup / "operation.json", operation)
        command = f'.\\reset_research.ps1 -Recover "{backup / "operation.json"}" -Force'
        raise RuntimeError(f"reset failed; run {command}: {error}") from error
    return str(state["campaign"]["id"]), source, backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--mode", choices=("fresh", "baseline"))
    operation.add_argument("--recover")
    parser.add_argument("--recipe-ref")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--training-log-source")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.recover:
            if args.recipe_ref or args.baseline_ref or args.training_log_source:
                raise ValueError("recovery accepts --recover only")
            backup, commit, _ = recover_reset(args.recover)
            print("=== Research reset recovered ===")
            print(f"Operation: {backup / 'operation.json'}")
            print(f"Recovery commit: {commit or 'none required'}")
            return 0
        ensure_clean_repository()
        if args.mode == "fresh":
            if args.baseline_ref or args.training_log_source:
                raise ValueError("fresh accepts --recipe-ref only")
            campaign_id, source, backup = reset_fresh(args.recipe_ref)
            print("=== Research state reset ===")
            print(
                f"Source recipe revision: {source or 'current HEAD (science preserved)'}"
            )
            print(f"New campaign ID: {campaign_id}")
            print(
                "Fresh baseline pending; the next normal launch allocates experiment 1."
            )
            print(
                "No trained model, score, evidence, or prior designation was imported."
            )
        else:
            if not args.baseline_ref or args.recipe_ref:
                raise ValueError(
                    "baseline requires --baseline-ref and rejects --recipe-ref"
                )
            campaign_id, source, backup = reset_baseline(
                args.baseline_ref, args.training_log_source
            )
            print("=== Research state reset ===")
            print(f"Prepared baseline restored from {source}.")
            print(f"Campaign ID: {campaign_id}; next experiment: 2.")
        if str(git("status", "--porcelain", "--untracked-files=all")).strip():
            raise RuntimeError(
                "reset completed with an unexpectedly dirty working tree"
            )
        print(f"Recovery backup: {backup}")
        print("No training was launched.")
        return 0
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
