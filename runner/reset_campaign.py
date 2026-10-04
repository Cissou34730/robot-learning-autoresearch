"""Human-only campaign reset implementation.

The PowerShell entry point owns cross-process exclusion. This module performs
read-only preflight before creating a recoverable backup and mutating the current
branch.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner import paths, protocol, repository

EPHEMERAL_PATHS = (
    "pi_workspace/operation_request.json",
    "runner/state/GOAL_REACHED",
    "runner/state/RECOVERY_PENDING",
    "runner/state/RESTART_PENDING",
    "runner/state/proposal.json",
    "runner/state/evaluation_request.json",
    "campaigns/training_logs",
    "campaigns/evaluations",
    "runner/state/last_train_summary.md",
    "runner/state/last_evaluation.json",
    "campaigns/brief.md",
    "models/candidates",
)
CAMPAIGN_PATHS = (
    "robot_learning/lab",
    "campaigns/EXPERIMENTS.md",
    "campaigns/results.jsonl",
    "runner/state/research_state.json",
    "pi_workspace/scientific_model.md",
    "campaigns/checkpoints",
    "campaigns/postmortems.md",
    "campaigns/archive.md",
    "runner/state/BASELINE_PENDING",
    *EPHEMERAL_PATHS,
)
TASK_COMPATIBILITY_PATHS = (
    "benchmark/final_contract.py",
    "benchmark/reference_contract.py",
    "contracts/task_spec.py",
    "contracts/robots/two_joint_arm.py",
    "contracts/robots/two_joint_arm.xml",
)
RESET_OPERATION_VERSION = 1
BASELINE_ARTIFACT_ROOTS = (
    "campaigns/checkpoints/candidates",
    "campaigns/checkpoints/retained",
)
BASELINE_EVALUATION_ROOT = "campaigns/evaluations"


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
        Path(str(git("rev-parse", "--path-format=absolute", option)).strip()).resolve()
        for option in ("--git-dir", "--git-common-dir")
    }
    if (
        backup.name != "research-reset-backups"
        or backup.parent not in administrative_roots
    ):
        raise RuntimeError(f"Git resolved an unsafe reset-maintenance path: {backup}")
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


def canonical_import_path(relative: str, description: str) -> str:
    try:
        normalized = repository.canonical_repo_path(relative)
    except ValueError as error:
        raise ValueError(f"{description} is invalid: {relative}") from error
    safe_path(normalized)
    return normalized


def path_is_below(relative: str, root: str) -> bool:
    return relative.startswith(f"{root}/") and relative != root


def validate_scientific_restore_path(relative: str) -> str:
    normalized = canonical_import_path(relative, "scientific recipe path")
    if protocol.is_campaign_lab(normalized) or not (
        protocol.is_researcher_owned(normalized)
        or normalized in protocol.PARAMETER_ONLY_PATHS
    ):
        raise ValueError(
            f"scientific recipe path is outside the permitted surface: {normalized}"
        )
    return normalized


def validate_artifact_directory(relative: str) -> str:
    normalized = canonical_import_path(relative, "baseline artifact path")
    if not any(path_is_below(normalized, root) for root in BASELINE_ARTIFACT_ROOTS):
        raise ValueError(
            "baseline artifact path must be below an approved checkpoint archive "
            f"root: {normalized}"
        )
    return normalized


def validate_evaluation_artifact_path(relative: str) -> str:
    normalized = canonical_import_path(relative, "baseline evaluation artifact path")
    if not path_is_below(normalized, BASELINE_EVALUATION_ROOT):
        raise ValueError(
            "baseline evaluation artifact must be below campaigns/evaluations: "
            f"{normalized}"
        )
    return normalized


def is_baseline_artifact_file(relative: str) -> bool:
    names = {
        *repository.ARTIFACT_FILES,
        *repository.INFERENCE_ARTIFACT_FILES,
        *repository.OPTIONAL_ARTIFACT_FILES,
    }
    return Path(relative).name in names and any(
        path_is_below(str(Path(relative).parent).replace("\\", "/"), root)
        for root in BASELINE_ARTIFACT_ROOTS
    )


def validate_reset_targets(mode: str, relative_paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for relative in dict.fromkeys(relative_paths):
        target = canonical_import_path(relative, "reset target")
        allowed = target in CAMPAIGN_PATHS
        if not allowed:
            try:
                allowed = validate_scientific_restore_path(target) == target
            except ValueError:
                allowed = False
        if mode == "baseline" and not allowed:
            allowed = is_baseline_artifact_file(target) or path_is_below(
                target, BASELINE_EVALUATION_ROOT
            )
        if not allowed:
            raise ValueError(f"reset target is outside the permitted scope: {target}")
        normalized.append(target)
    return normalized


def new_operation(mode: str, source: str | None, targets: list[str]) -> dict:
    operation = {
        "schema_version": RESET_OPERATION_VERSION,
        "mode": mode,
        "source_commit": source,
        "original_head": str(git("rev-parse", "HEAD")).strip(),
        "repository": repository_identity(),
        "targeted_paths": validate_reset_targets(mode, targets),
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


def clean_campaign_changes(*, recipe_ref: str | None = None) -> None:
    if recipe_ref:
        verify_recipe_source(resolve_commit(recipe_ref, "RecipeRef"))
    changed = set()
    for arguments in (
        ("diff", "--name-only", "--no-renames", "-z"),
        ("diff", "--cached", "--name-only", "--no-renames", "-z"),
    ):
        changed.update(path for path in str(git(*arguments)).split("\0") if path)
    untracked = {
        path
        for path in str(git("ls-files", "--others", "--exclude-standard", "-z")).split(
            "\0"
        )
        if path
    }

    def permitted(path: str) -> bool:
        return path_is_covered(path, list(CAMPAIGN_PATHS)) or bool(
            recipe_ref
            and (
                protocol.is_researcher_owned(path)
                or path in protocol.PARAMETER_ONLY_PATHS
            )
        )

    unrelated = sorted(path for path in changed | untracked if not permitted(path))
    if unrelated:
        raise RuntimeError(
            "clean reset refuses changes outside campaign paths: "
            + ", ".join(unrelated)
        )
    if changed:
        git(
            "restore", "--source=HEAD", "--staged", "--worktree", "--", *sorted(changed)
        )
    if untracked:
        git("clean", "-fd", "--", *sorted(untracked))


def ensure_clean_repository(
    *, clean: bool = False, recipe_ref: str | None = None
) -> None:
    git("symbolic-ref", "--quiet", "--short", "HEAD")
    git("remote", "get-url", "origin")
    if clean:
        clean_campaign_changes(recipe_ref=recipe_ref)
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
    plan = protocol.plan_recipe_paths(commit)
    restore: list[str] = []
    remove_created: list[str] = []
    for field, destination in (
        ("restore", restore),
        ("remove_created", remove_created),
    ):
        for relative in plan[field]:
            if protocol.is_campaign_lab(relative):
                continue
            try:
                destination.append(validate_scientific_restore_path(relative))
            except ValueError as error:
                raise RuntimeError(
                    f"recipe plan contains a non-scientific path: {relative}"
                ) from error
    return {
        "parent": plan["parent"],
        "restore": restore,
        "remove_created": remove_created,
    }


def plan_paths(plan: dict) -> list[str]:
    return [*plan["restore"], *plan["remove_created"]]


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
    if "robot_learning/training/current_params.json" not in files:
        raise ValueError(
            "recipe source is missing robot_learning/training/current_params.json"
        )
    git_json(commit, "robot_learning/training/current_params.json")
    verify_task_compatibility(commit)


def artifact_fingerprint_at_commit(commit: str, artifact: str) -> str:
    artifact = validate_artifact_directory(artifact)
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


def baseline_restore_paths(commit: str, candidate: dict) -> list[str]:
    artifact = validate_artifact_directory(str(candidate["artifact"]).rstrip("/"))
    evaluation_artifacts = [
        validate_evaluation_artifact_path(relative)
        for relative in candidate["evaluation_artifacts"]
    ]
    if not evaluation_artifacts:
        raise ValueError(
            "BaselineRef candidate requires at least one committed evaluation artifact"
        )
    source = commit_files(commit)
    required = {
        *(f"{artifact}/{name}" for name in repository.INFERENCE_ARTIFACT_FILES),
        *evaluation_artifacts,
        "pi_workspace/scientific_model.md",
    }
    missing = sorted(required - source)
    if missing:
        raise ValueError(f"BaselineRef is missing required artifacts: {missing}")
    optional = {
        f"{artifact}/{name}"
        for name in repository.OPTIONAL_ARTIFACT_FILES
        if f"{artifact}/{name}" in source
    }
    return sorted(required | optional)


def verify_baseline_source(commit: str) -> tuple[dict, dict, list[str], dict]:
    state = git_json(commit, "runner/state/research_state.json")
    if state.get("schema_version") != repository.STATE_SCHEMA_VERSION:
        raise ValueError("BaselineRef must use schema 6")
    repository.validate_research_state(state, allow_missing_artifact=True)
    roles = state["model_roles"]
    candidate_id = roles["working"]
    if candidate_id is None or candidate_id != roles["best_known"]:
        raise ValueError(
            "BaselineRef must designate one prepared candidate as both working "
            "and best-known"
        )
    candidate = state["candidates"].get(candidate_id)
    if not isinstance(candidate, dict):
        raise TypeError("BaselineRef model roles name an unknown candidate")
    if state["scientific_model"]["status"] != "ready":
        raise ValueError("BaselineRef must contain a ready scientific model")
    model_commit = str(state["scientific_model"]["commit"])
    resolve_commit(model_commit, "BaselineRef scientific model commit")
    if git_bytes(model_commit, "pi_workspace/scientific_model.md") != git_bytes(
        commit, "pi_workspace/scientific_model.md"
    ):
        raise ValueError(
            "BaselineRef scientific model differs from its recorded commit"
        )
    scientific_commit = str(candidate["scientific_commit"])
    resolve_commit(scientific_commit, "BaselineRef scientific_commit")
    verify_task_compatibility(scientific_commit)
    restore = baseline_restore_paths(commit, candidate)
    actual_fingerprint = artifact_fingerprint_at_commit(
        commit, str(candidate["artifact"])
    )
    if actual_fingerprint != candidate["fingerprint"]:
        raise ValueError("BaselineRef model fingerprint does not match its role record")
    verify_task_compatibility(commit)
    return state, copy.deepcopy(candidate), restore, scientific_plan(scientific_commit)


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
) -> str | None:
    forced = [
        path
        for path in scope
        if purpose == "campaign"
        and path.startswith(
            (
                "campaigns/checkpoints",
                "campaigns/evaluations",
                "campaigns/training_logs",
                "models/",
            )
        )
        and (
            (paths.ROOT / path).exists()
            or git("--literal-pathspecs", "ls-files", "--", path).strip()
        )
    ]
    ordinary = [path for path in scope if path not in forced]
    stageable = repository.stage_existing_or_tracked(ordinary)
    if forced:
        git("add", "-f", "-A", "--", *forced)
        stageable.extend(forced)
    if (
        not stageable
        or not str(git("diff", "--cached", "--name-only", "--", *stageable)).strip()
    ):
        return None
    git(
        "commit",
        "-m",
        repository.campaign_commit_message(message),
        "--",
        *stageable,
    )
    commit = str(git("rev-parse", "HEAD")).strip()
    operation["commits"].append({"purpose": purpose, "commit": commit, "pushed": False})
    update_operation(backup, operation, f"{purpose}_committed")
    repository.push_head()
    operation["commits"][-1]["pushed"] = True
    update_operation(backup, operation, f"{purpose}_published")
    return commit


def path_is_covered(relative: str, targets: list[str]) -> bool:
    return any(
        relative == target or relative.startswith(f"{target}/") for target in targets
    )


def validate_recovery_operation(operation_path: str) -> tuple[Path, dict]:
    backup_root = reset_backup_root().resolve()
    candidate = Path(operation_path)
    if candidate.is_dir():
        candidate = candidate / "operation.json"
    candidate = candidate.resolve()
    if candidate.name != "operation.json" or candidate.parent.parent != backup_root:
        raise ValueError(f"recovery operation must be directly below {backup_root}")
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
    try:
        if validate_reset_targets(operation["mode"], targets) != targets:
            raise ValueError
    except ValueError as error:
        raise ValueError(
            "reset recovery operation contains an unsafe target"
        ) from error
    backup_files = candidate.parent / "files"
    for entry in entries:
        backup_path = backup_files / entry["path"]
        if not entry.get("exists"):
            if backup_path.exists():
                raise ValueError(f"unexpected backup content for {entry['path']}")
            continue
        if entry.get("kind") not in {"file", "directory"} or not backup_path.exists():
            raise ValueError(f"reset backup is incomplete for {entry['path']}")
        if path_fingerprint(backup_path) != entry.get("fingerprint"):
            raise ValueError(f"reset backup fingerprint mismatch for {entry['path']}")
    return candidate, operation


def changed_worktree_paths() -> set[str]:
    changed = set(str(git("diff", "--name-only")).splitlines())
    changed.update(str(git("diff", "--cached", "--name-only")).splitlines())
    changed.update(str(git("ls-files", "--others", "--exclude-standard")).splitlines())
    return {path for path in changed if path}


def restore_backup_files(operation_path: Path, operation: dict) -> None:
    targets = operation["targeted_paths"]
    unrelated = sorted(
        path for path in changed_worktree_paths() if not path_is_covered(path, targets)
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
        last_verdict="fresh campaign initialized; scientific model pending",
    )


def write_campaign_memory(state: dict) -> None:
    repository.write_state(state)
    repository.atomic_write_text(paths.RESULTS_PATH, "")
    repository.atomic_write_text(paths.LOG_PATH, repository.render_operation_log([]))


def write_fresh_campaign(recipe_source: str | None) -> dict:
    for relative in CAMPAIGN_PATHS:
        remove_path(relative)
    base_commit = str(git("rev-parse", "HEAD")).strip()
    state = empty_state(base_commit, recipe_source)
    paths.CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    paths.PI_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    paths.RUNNER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    write_campaign_memory(state)
    return state


def baseline_state(
    source_state: dict,
    candidate: dict,
    *,
    base_commit: str,
    recipe_source: str,
) -> dict:
    if not candidate["evaluation_artifacts"]:
        raise ValueError(
            "imported candidate requires at least one committed evaluation artifact"
        )
    state = empty_state(base_commit, recipe_source)
    candidate_id = str(candidate["id"])
    origin = re.fullmatch(r"T([1-9]\d*)", str(candidate["origin_operation"]))
    if origin is None:
        raise ValueError(
            "imported candidate origin_operation must be a strict training operation ID"
        )
    state["scientific_model"] = copy.deepcopy(source_state["scientific_model"])
    state["counters"]["measurement"] = source_state["counters"]["measurement"]
    state["counters"]["training"] = max(
        source_state["counters"]["training"],
        int(origin.group(1)),
    )
    state["candidates"] = {candidate_id: copy.deepcopy(candidate)}
    state["model_roles"] = {
        "working": candidate_id,
        "best_known": candidate_id,
        "retained": {},
    }
    state["last_verdict"] = "prepared model restored by human maintenance operation"
    repository.validate_research_state(state, allow_missing_artifact=True)
    return state


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
            repository.apply_recipe_restore(plan)
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
            "reset research campaign state: fresh",
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


def reset_baseline(reference: str) -> tuple[str, str, Path]:
    source = resolve_commit(reference, "BaselineRef")
    source_state, candidate, restore, recipe_plan = verify_baseline_source(source)
    targets = sorted({*CAMPAIGN_PATHS, *restore, *plan_paths(recipe_plan)})
    preflight_targets(targets)
    operation = new_operation("baseline", source, targets)
    backup = create_backup(targets, operation)
    try:
        for relative in CAMPAIGN_PATHS:
            remove_path(relative)
        repository.apply_recipe_restore(recipe_plan)
        validate_restored_recipe()
        update_operation(backup, operation, "recipe_restored")
        publish_reset_changes(
            backup,
            operation,
            f"restore scientific recipe from {candidate['scientific_commit']}",
            plan_paths(recipe_plan),
            "recipe",
        )
        apply_restore(source, restore)
        state = baseline_state(
            source_state,
            candidate,
            base_commit=str(git("rev-parse", "HEAD")).strip(),
            recipe_source=str(candidate["scientific_commit"]),
        )
        write_campaign_memory(state)
        repository.validate_research_state(state, allow_missing_artifact=False)
        update_operation(backup, operation, "baseline_restored")
        publish_reset_changes(
            backup,
            operation,
            f"reset research campaign state: prepared model {source}",
            list(dict.fromkeys([*CAMPAIGN_PATHS, *restore])),
            "campaign",
        )
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
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--recipe-ref")
    parser.add_argument("--baseline-ref")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.recover:
            if args.recipe_ref or args.baseline_ref or args.clean:
                raise ValueError("recovery accepts --recover only, without --clean")
            backup, commit, _ = recover_reset(args.recover)
            print("=== Research reset recovered ===")
            print(f"Operation: {backup / 'operation.json'}")
            print(f"Recovery commit: {commit or 'none required'}")
            return 0
        if args.mode == "fresh":
            if args.baseline_ref:
                raise ValueError("fresh accepts --recipe-ref only")
        elif not args.baseline_ref or args.recipe_ref:
            raise ValueError(
                "baseline requires --baseline-ref and rejects --recipe-ref"
            )
        baseline_source = None
        if args.mode == "baseline":
            baseline_source = resolve_commit(args.baseline_ref, "BaselineRef")
            verify_baseline_source(baseline_source)
        ensure_clean_repository(
            clean=args.clean,
            recipe_ref=args.recipe_ref if args.mode == "fresh" else None,
        )
        if args.mode == "fresh":
            campaign_id, source, backup = reset_fresh(args.recipe_ref)
            print("=== Research state reset ===")
            print(
                f"Source recipe revision: {source or 'current HEAD (science preserved)'}"
            )
            print(f"New campaign ID: {campaign_id}")
            print("Scientific model pending; the launcher publishes it before PI work.")
            print(
                "No trained model, score, evidence, or prior designation was imported."
            )
        else:
            campaign_id, source, backup = reset_baseline(str(baseline_source))
            print("=== Research state reset ===")
            print(f"Prepared model restored from {source}.")
            print(f"New campaign ID: {campaign_id}.")
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
