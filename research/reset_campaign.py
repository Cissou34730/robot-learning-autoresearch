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

BACKUP_ROOT = paths.ROOT / ".git" / "research-reset-backups"
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
            "BaselineRef must use schema v4; unverifiable legacy baselines must be migrated before reset"
        )
    repository.validate_v4_state(state, allow_missing_artifact=True)
    working = state.get("working_lineage")
    best = state.get("best_known_lineage")
    pending_fields = (
        "pending_analysis",
        "pending_training_operation",
        "pending_evaluation_request",
        "pending_researcher_decision",
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
            "BaselineRef history does not contain the recorded v4 designation"
        )
    verify_task_compatibility(commit)
    return state, matching, baseline_restore_paths(commit, state)


def create_backup(relative_paths: list[str], operation: dict) -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_ROOT / f"{int(time.time())}-{uuid.uuid4()}"
    files = backup / "files"
    files.mkdir(parents=True)
    manifest: list[str] = []
    for relative in dict.fromkeys(relative_paths):
        source = safe_path(relative)
        if not source.exists():
            continue
        destination = files / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        manifest.append(relative)
    operation.update(progress="backed_up", backup=str(backup), backed_up=manifest)
    repository.atomic_write_json(backup / "operation.json", operation)
    return backup


def update_operation(backup: Path, operation: dict, progress: str) -> None:
    operation["progress"] = progress
    repository.atomic_write_json(backup / "operation.json", operation)


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
    return repository.empty_v4_campaign_state(
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
    operation = {"mode": "fresh", "recipe_source_commit": source, "progress": "planned"}
    backup = create_backup(targets, operation)
    try:
        if plan:
            repository.apply_code_lineage_decision(plan)
            validate_restored_recipe()
            update_operation(backup, operation, "recipe_restored")
            repository.commit_paths(
                f"restore scientific recipe from {source}", plan_paths(plan)
            )
            update_operation(backup, operation, "recipe_published")
        state = write_fresh_campaign(source)
        update_operation(backup, operation, "campaign_initialized")
        repository.commit_paths(
            "reset research experiment state: fresh",
            list(CAMPAIGN_PATHS),
        )
        update_operation(backup, operation, "complete")
    except Exception as error:
        operation["error"] = str(error)
        repository.atomic_write_json(backup / "operation.json", operation)
        raise RuntimeError(f"reset failed; recover from {backup}: {error}") from error
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
    operation = {
        "mode": "baseline",
        "baseline_source_commit": source,
        "progress": "planned",
    }
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
        repository.validate_v4_state(state, allow_missing_artifact=False)
        repository.atomic_write_text(
            paths.LOG_PATH, repository.render_experiment_log(records)
        )
        update_operation(backup, operation, "baseline_restored")
        publication_scope = list(
            dict.fromkeys([*repository.status_paths((".",)), *tracked_logs])
        )
        ordinary_scope = [
            path for path in publication_scope if path not in tracked_logs
        ]
        repository.stage_existing_or_tracked(ordinary_scope)
        git("add", "-f", "--", *tracked_logs)
        if str(git("diff", "--cached", "--name-only")).strip():
            repository.commit_and_push(
                f"reset research experiment state: baseline {source}"
            )
        else:
            repository.push_head()
        update_operation(backup, operation, "complete")
    except Exception as error:
        operation["error"] = str(error)
        repository.atomic_write_json(backup / "operation.json", operation)
        raise RuntimeError(f"reset failed; recover from {backup}: {error}") from error
    return str(state["campaign"]["id"]), source, backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fresh", "baseline"), required=True)
    parser.add_argument("--recipe-ref")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--training-log-source")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
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
