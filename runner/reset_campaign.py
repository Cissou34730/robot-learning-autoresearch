"""Human-only campaign reset implementation.

The PowerShell entry point owns cross-process exclusion. This module performs
read-only preflight before mutating the current branch. Campaign history is
recoverable through Git; no separate reset backup is kept.
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
import tempfile
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


def baseline_restore_paths(
    commit: str, candidate: dict, source_state: dict
) -> list[str]:
    artifact = validate_artifact_directory(str(candidate["artifact"]).rstrip("/"))
    evaluation_artifacts = [
        validate_evaluation_artifact_path(relative)
        for relative in candidate["evaluation_artifacts"]
    ]
    if not evaluation_artifacts:
        raise ValueError(
            "BaselineRef candidate requires at least one preserved evaluation artifact"
        )
    records_by_path: dict[str, list[dict]] = {}

    def collect_records(state: dict) -> None:
        missing = set(evaluation_artifacts) - records_by_path.keys()
        for event in state["operation_events"]:
            if event["kind"] != "measurement" or event["status"] != "completed":
                continue
            for measurement in event["result"]["measurements"]:
                metrics = measurement["metrics"]
                relative = metrics.get("evaluation_artifact")
                if (
                    measurement.get("candidate_id") == candidate["id"]
                    and relative in missing
                ):
                    records_by_path.setdefault(relative, []).append(metrics)

    collect_records(source_state)
    if len(records_by_path) != len(set(evaluation_artifacts)):
        revisions = str(
            git(
                "log",
                "--format=%H",
                "--all",
                "--diff-filter=AM",
                commit,
                "--",
                "runner/state/research_state.json",
            )
        ).splitlines()
        for revision in revisions:
            if revision == commit:
                continue
            historical_state = git_json(revision, "runner/state/research_state.json")
            if (
                historical_state.get("schema_version")
                != repository.STATE_SCHEMA_VERSION
            ):
                continue
            collect_records(historical_state)
            if len(records_by_path) == len(set(evaluation_artifacts)):
                break
    for relative in evaluation_artifacts:
        records = records_by_path.get(relative)
        if not records:
            raise ValueError(
                f"BaselineRef has no completed measurement record for {relative}"
            )
        artifact_path = safe_path(relative)
        if not artifact_path.is_file():
            raise ValueError(
                f"BaselineRef requires its preserved local measurement artifact: {relative}"
            )
        fingerprint = repository.file_fingerprint(artifact_path)
        if any(
            record["evaluation_artifact_fingerprint"] != fingerprint
            for record in records
        ):
            raise ValueError(
                f"BaselineRef local measurement fingerprint mismatch: {relative}"
            )
    source = commit_files(commit)
    required = {
        *(f"{artifact}/{name}" for name in repository.INFERENCE_ARTIFACT_FILES),
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
    restore = baseline_restore_paths(commit, candidate, state)
    actual_fingerprint = artifact_fingerprint_at_commit(
        commit, str(candidate["artifact"])
    )
    if actual_fingerprint != candidate["fingerprint"]:
        raise ValueError("BaselineRef model fingerprint does not match its role record")
    verify_task_compatibility(commit)
    return state, copy.deepcopy(candidate), restore, scientific_plan(scientific_commit)


def publish_reset_changes(
    message: str,
    scope: list[str],
    purpose: str,
) -> str | None:
    scope = [
        path for path in scope if not repository.is_local_measurement_artifact(path)
    ]
    forced = [
        path
        for path in scope
        if purpose == "campaign"
        and path.startswith(
            (
                "campaigns/checkpoints",
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
    repository.push_head()
    return commit


def path_is_covered(relative: str, targets: list[str]) -> bool:
    return any(
        relative == target or relative.startswith(f"{target}/") for target in targets
    )


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
    if not paths.locate("pyproject.toml").is_file():
        return
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(paths.locate("pyproject.toml").parent),
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
            "imported candidate requires at least one preserved evaluation artifact"
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


def reset_failure(original_head: str, error: Exception) -> RuntimeError:
    return RuntimeError(
        f"reset failed; the campaign started from commit {original_head}: {error}"
    )


def reset_fresh(recipe_ref: str | None) -> tuple[str, str | None]:
    source = resolve_commit(recipe_ref, "RecipeRef") if recipe_ref else None
    plan = scientific_plan(source) if source else None
    if source:
        verify_recipe_source(source)
    targets = validate_reset_targets(
        "fresh", [*CAMPAIGN_PATHS, *(plan_paths(plan) if plan else [])]
    )
    preflight_targets(targets)
    original_head = str(git("rev-parse", "HEAD")).strip()
    try:
        if plan:
            repository.apply_recipe_restore(plan)
            validate_restored_recipe()
            publish_reset_changes(
                f"restore scientific recipe from {source}",
                plan_paths(plan),
                "recipe",
            )
        state = write_fresh_campaign(source)
        publish_reset_changes(
            "reset research campaign state: fresh",
            list(CAMPAIGN_PATHS),
            "campaign",
        )
    except Exception as error:
        raise reset_failure(original_head, error) from error
    return str(state["campaign"]["id"]), source


def reset_baseline(reference: str) -> tuple[str, str]:
    source = resolve_commit(reference, "BaselineRef")
    source_state, candidate, restore, recipe_plan = verify_baseline_source(source)
    targets = validate_reset_targets(
        "baseline", sorted({*CAMPAIGN_PATHS, *restore, *plan_paths(recipe_plan)})
    )
    preflight_targets(targets)
    original_head = str(git("rev-parse", "HEAD")).strip()
    # Baseline measurement files are ignored by Git, so carry them across the
    # campaign cleanup in a temporary folder that is discarded afterwards.
    with tempfile.TemporaryDirectory(prefix="research-reset-") as staging:
        staged = Path(staging)
        for relative in candidate["evaluation_artifacts"]:
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_path(relative), destination)
        try:
            for relative in CAMPAIGN_PATHS:
                remove_path(relative)
            repository.apply_recipe_restore(recipe_plan)
            validate_restored_recipe()
            publish_reset_changes(
                f"restore scientific recipe from {candidate['scientific_commit']}",
                plan_paths(recipe_plan),
                "recipe",
            )
            apply_restore(source, restore)
            for relative in candidate["evaluation_artifacts"]:
                target = safe_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged / relative, target)
            state = baseline_state(
                source_state,
                candidate,
                base_commit=str(git("rev-parse", "HEAD")).strip(),
                recipe_source=str(candidate["scientific_commit"]),
            )
            write_campaign_memory(state)
            repository.validate_research_state(state, allow_missing_artifact=False)
            publish_reset_changes(
                f"reset research campaign state: prepared model {source}",
                list(dict.fromkeys([*CAMPAIGN_PATHS, *restore])),
                "campaign",
            )
        except Exception as error:
            raise reset_failure(original_head, error) from error
    return str(state["campaign"]["id"]), source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fresh", "baseline"), required=True)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--recipe-ref")
    parser.add_argument("--baseline-ref")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
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
            campaign_id, source = reset_fresh(args.recipe_ref)
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
            campaign_id, source = reset_baseline(str(baseline_source))
            print("=== Research state reset ===")
            print(f"Prepared model restored from {source}.")
            print(f"New campaign ID: {campaign_id}.")
        if str(git("status", "--porcelain", "--untracked-files=all")).strip():
            raise RuntimeError(
                "reset completed with an unexpectedly dirty working tree"
            )
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
