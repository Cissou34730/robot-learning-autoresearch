"""Durable Runner persistence, Git operations, and artifact integrity."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path, PureWindowsPath

from research import runner_paths as paths

STATE_SCHEMA_VERSION = 6
DEFAULT_MAX_INQUIRIES = 15

RUNNER_CONTROL_PATHS = {
    "research/operation_request.json",
    "research/RECOVERY_PENDING",
    "research/RESTART_PENDING",
}
RUNNER_MEMORY_PATHS = {
    "research/research_state.json",
    "research/results.jsonl",
    "research/EXPERIMENTS.md",
    "research/scientific_model.md",
}
RUNNER_MEMORY_PREFIXES = (
    "research/evaluations/",
    "research/checkpoints/candidates/",
    "research/checkpoints/retained/",
)

ARTIFACT_FILES = ("model.zip", "artifact.json")
INFERENCE_ARTIFACT_FILES = (*ARTIFACT_FILES, "policy_runtime.pkl")
OPTIONAL_ARTIFACT_FILES = (
    "vecnormalize.pkl",
    "replay_buffer.pkl",
    "policy_runtime.pkl",
)

STATE_FIELDS = {
    "schema_version",
    "campaign",
    "human_goal",
    "scientific_model",
    "active_inquiry",
    "pi_checkpoint",
    "scientific_session",
    "counters",
    "operation_events",
    "pending_operation",
    "model_roles",
    "candidates",
    "terminal_state",
    "official_assessment",
    "last_verdict",
}
CHECKPOINT_FIELDS = {
    "session_id",
    "inquiry_id",
    "human_goal_connection",
    "current_goal_gap",
    "current_synthesis",
    "evidence_references",
    "decision_frontier",
    "completed_operations",
    "candidates_and_roles",
    "next_direction_or_closure",
    "cumulative_resource_use",
    "scientific_commit",
}
CANDIDATE_FIELDS = {
    "id",
    "artifact",
    "fingerprint",
    "origin_operation",
    "name",
    "parameters",
    "scientific_commit",
    "training_steps",
    "evaluation_artifacts",
}
EVENT_FIELDS = {
    "id",
    "kind",
    "session_id",
    "inquiry_id",
    "request",
    "result",
    "status",
    "error",
    "supersedes",
    "superseded_by",
    "completed_at",
}
PENDING_FIELDS = {
    "id",
    "kind",
    "session_id",
    "inquiry_id",
    "request",
    "request_fingerprint",
    "progress",
    "failure",
    "supersedes",
    "data",
}
CAMPAIGN_FIELDS = {
    "id",
    "started_at",
    "base_commit",
    "recipe_source_commit",
    "max_inquiries",
}
OFFICIAL_ASSESSMENT_FIELDS = {"status", "model", "summary", "completed_at"}
OPERATION_KINDS = {
    "measurement",
    "training",
    "inquiry",
    "checkpoint",
    "model_role",
    "restore_recipe",
    "campaign_conclusion",
}
PENDING_DATA_FIELDS = {
    "measurement": {
        "measurements",
        "paired_comparisons",
        "evaluation_semantics",
        "task_reference_contract",
        "module_provenance",
        "partial_results",
        "result",
    },
    "training": {
        "parent",
        "code_parent_commit",
        "scientific_manifest",
        "scientific_paths",
        "scientific_commit",
        "effective_parameters",
        "candidate_dir",
        "archived_candidates",
        "result",
    },
    "inquiry": {"plan", "result"},
    "checkpoint": {
        "plan",
        "code_parent_commit",
        "scientific_manifest",
        "scientific_paths",
        "effective_parameters",
        "scientific_commit",
        "result",
    },
    "model_role": {"plan", "publication", "result"},
    "restore_recipe": {"plan", "pre_restore_manifest", "result"},
    "campaign_conclusion": {"plan", "result"},
}
PENDING_PROGRESS = {
    "measurement": {"accepted", "result_ready", "completed"},
    "training": {
        "accepted",
        "recipe_published",
        "training_dispatched",
        "training_completed",
        "candidates_archived",
        "result_ready",
        "completed",
    },
    "inquiry": {"accepted", "result_ready", "completed"},
    "checkpoint": {
        "accepted",
        "checkpoint_recipe_published",
        "result_ready",
        "completed",
    },
    "model_role": {
        "accepted",
        "publishing_artifact",
        "result_ready",
        "completed",
    },
    "restore_recipe": {"accepted", "restoring", "result_ready", "completed"},
    "campaign_conclusion": {"accepted", "result_ready", "completed"},
}


def repo_relative_path(path: Path) -> str:
    root = paths.ROOT.resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"path is outside the repository: {path}") from error


def resolve_repo_path(value: str) -> Path:
    normalized = str(value).replace("\\", "/")
    relative = Path(normalized)
    if not normalized or relative.is_absolute() or PureWindowsPath(normalized).drive:
        raise ValueError(f"repository path must be relative: {value}")
    root = paths.ROOT.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path is outside the repository: {value}")
    return resolved


def canonical_repo_path(value: str) -> str:
    return repo_relative_path(resolve_repo_path(value))


def git_process_group_options() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_git_process(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()


def git(*args: str) -> str:
    process = subprocess.Popen(
        ["git", *args],
        cwd=paths.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **git_process_group_options(),
    )
    try:
        stdout, stderr = process.communicate()
    except KeyboardInterrupt:
        stop_git_process(process)
        raise
    if process.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return stdout


def status_paths(scope: tuple[str, ...]) -> list[str]:
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
    relative = path.replace("\\", "/")
    return relative in RUNNER_CONTROL_PATHS or is_runner_memory(relative)


def scientific_change_paths(changed: list[str]) -> list[str]:
    from research import runner_protocol as protocol

    return [
        path
        for path in changed
        if not is_runner_owned(path) and not protocol.is_campaign_lab(path)
    ]


def researcher_change_paths(changed: list[str]) -> list[str]:
    return [path for path in changed if not is_runner_owned(path)]


def campaign_lab_change_paths(changed: list[str]) -> list[str]:
    from research import runner_protocol as protocol

    return [path for path in changed if protocol.is_campaign_lab(path)]


def committed_change_paths(parent: str) -> list[str]:
    output = git("diff", "--name-only", "--no-renames", parent, "HEAD", "--")
    return [line.strip() for line in output.splitlines() if line.strip()]


def scientific_delta(parent: str) -> list[str]:
    committed = committed_change_paths(parent) if parent else []
    return scientific_change_paths(
        list(dict.fromkeys([*committed, *status_paths((".",))]))
    )


def require_resolvable_commit(commit: str) -> None:
    try:
        git("cat-file", "-e", f"{commit}^{{commit}}")
    except RuntimeError as error:
        raise RuntimeError(f"scientific commit does not resolve: {commit}") from error


def tracked_at_commit(commit: str, path: str) -> bool:
    return bool(git("ls-tree", "-r", "--name-only", commit, "--", path).strip())


def restore_paths(commit: str, restorable: list[str]) -> None:
    if restorable:
        git("restore", "--source", commit, "--", *restorable)


def remove_created_path(created: Path) -> None:
    if created.is_dir():
        shutil.rmtree(created)
    else:
        created.unlink(missing_ok=True)


def apply_recipe_restore(plan: dict) -> None:
    restore_paths(str(plan["parent"]), list(plan["restore"]))
    for value in plan["remove_created"]:
        remove_created_path(resolve_repo_path(str(value)))


def recipe_paths_match_commit(plan: dict) -> bool:
    parent = str(plan["parent"])
    restored = [str(path) for path in plan["restore"]]
    if restored and git("diff", "--name-only", parent, "--", *restored).strip():
        return False
    return all(
        not resolve_repo_path(str(path)).exists() for path in plan["remove_created"]
    )


def stage_existing_or_tracked(candidates: list[str]) -> list[str]:
    stageable = [
        path
        for path in dict.fromkeys(candidates)
        if (paths.ROOT / path).exists() or git("ls-files", "--", path).strip()
    ]
    if stageable:
        git("add", "-A", "--", *stageable)
    return stageable


def push_head() -> None:
    try:
        git("push", "origin", "HEAD")
    except RuntimeError as error:
        raise RuntimeError(
            "local commits could not be pushed to origin; refusing unpublished state"
        ) from error


def campaign_commit_message(message: str) -> str:
    return f"camp: {message}"


def commit_and_push(message: str, scope: tuple[str, ...] = ()) -> None:
    git("commit", "-m", message, *(("--", *scope) if scope else ()))
    push_head()


def commit_paths(message: str, scope: list[str]) -> bool:
    stageable = stage_existing_or_tracked(scope)
    if not stageable:
        return False
    if not git("diff", "--cached", "--name-only", "--", *stageable).strip():
        return False
    commit_and_push(message, tuple(stageable))
    return True


def require_path_at_commit(commit: str, relative: str) -> None:
    path = canonical_repo_path(relative)
    if not resolve_repo_path(path).is_file():
        raise ValueError(f"committed path is missing from the worktree: {path}")
    worktree_blob = git("hash-object", "--", path).strip()
    try:
        committed_blob = git("rev-parse", f"{commit}:{path}").strip()
    except RuntimeError as error:
        raise ValueError(f"commit {commit} does not contain {path}") from error
    if committed_blob != worktree_blob:
        raise ValueError(f"commit {commit} does not contain the current {path}")


def publish_scientific_recipe(operation_id: str, scope: list[str]) -> str:
    if not commit_paths(
        campaign_commit_message(f"{operation_id} scientific recipe"), scope
    ):
        push_head()
    return git("rev-parse", "HEAD").strip()


def campaign_lab_manifest() -> list[dict]:
    tracked = [
        line.strip()
        for line in git("ls-files", "--", "research/lab").splitlines()
        if line.strip()
    ]
    changed = campaign_lab_change_paths(status_paths(("research/lab",)))
    manifest: list[dict] = []
    for relative in sorted({*tracked, *changed}):
        path = resolve_repo_path(relative)
        if path.is_file():
            manifest.append({"path": relative, "fingerprint": file_fingerprint(path)})
    return manifest


def publish_campaign_laboratory(operation_id: str) -> dict | None:
    """Publish PI-authored diagnostic tools independently from policy recipes."""
    changed = campaign_lab_change_paths(status_paths(("research/lab",)))
    if changed:
        from research import runner_execution as execution

        execution.validate_changed_sources(changed)
        commit_paths(
            campaign_commit_message(f"{operation_id} measurement tools"), changed
        )
    manifest = campaign_lab_manifest()
    if not manifest:
        return None
    commit = git("log", "-1", "--format=%H", "--", "research/lab").strip()
    if not commit:
        commit = git("rev-parse", "HEAD").strip()
    return {
        "commit": commit,
        "manifest": manifest,
        "fingerprint": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def changed_runner_memory() -> list[str]:
    return [path for path in status_paths((".",)) if is_runner_memory(path)]


def commit_runner_memory(message: str) -> bool:
    return commit_paths(campaign_commit_message(message), changed_runner_memory())


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _atomic_replace(temporary, path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    _atomic_replace(temporary, path)


def _nonempty(record: dict, field: str, description: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{description} must be a non-empty string")
    return value.strip()


def _positive_integer(
    value: object, description: str, *, allow_zero: bool = False
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{description} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ValueError(f"{description} must be at least {minimum}")
    return value


def canonicalize_candidate(candidate: dict) -> None:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_FIELDS:
        raise ValueError(f"candidate requires exactly {sorted(CANDIDATE_FIELDS)}")
    for field in ("id", "fingerprint", "origin_operation", "name"):
        _nonempty(candidate, field, f"candidate {field}")
    if not str(candidate["origin_operation"]).startswith("T"):
        raise ValueError("candidate origin_operation must be a training operation")
    candidate["artifact"] = canonical_repo_path(str(candidate["artifact"]))
    if not isinstance(candidate["parameters"], dict):
        raise TypeError("candidate parameters must be an object")
    _nonempty(candidate, "scientific_commit", "candidate scientific_commit")
    _positive_integer(
        candidate["training_steps"], "candidate training_steps", allow_zero=True
    )
    artifacts = candidate["evaluation_artifacts"]
    if not isinstance(artifacts, list) or not all(
        isinstance(item, str) and item.strip() for item in artifacts
    ):
        raise ValueError("candidate evaluation_artifacts must be a list of paths")
    candidate["evaluation_artifacts"] = [
        canonical_repo_path(item) for item in artifacts
    ]


def _validate_checkpoint(checkpoint: object, event_ids: set[str]) -> None:
    if checkpoint is None:
        return
    if not isinstance(checkpoint, dict) or set(checkpoint) != CHECKPOINT_FIELDS:
        raise ValueError(f"pi_checkpoint requires exactly {sorted(CHECKPOINT_FIELDS)}")
    _nonempty(checkpoint, "session_id", "pi_checkpoint session_id")
    inquiry_id = checkpoint["inquiry_id"]
    if inquiry_id is not None:
        _nonempty({"value": inquiry_id}, "value", "pi_checkpoint inquiry_id")
    for field in (
        "human_goal_connection",
        "current_goal_gap",
        "current_synthesis",
        "decision_frontier",
        "candidates_and_roles",
        "next_direction_or_closure",
        "cumulative_resource_use",
        "scientific_commit",
    ):
        _nonempty(checkpoint, field, f"pi_checkpoint {field}")
    evidence = checkpoint["evidence_references"]
    completed = checkpoint["completed_operations"]
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        raise ValueError("pi_checkpoint evidence_references must be a list of strings")
    if not isinstance(completed, list) or not all(
        isinstance(item, str) and item in event_ids for item in completed
    ):
        raise ValueError(
            "pi_checkpoint completed_operations must reference completed events"
        )


def _validate_active_inquiry(active: object) -> None:
    if active is None:
        return
    required = {
        "id",
        "question",
        "goal_connection",
        "closure_condition",
        "rationale",
        "opened_in_session",
        "reframes",
    }
    if not isinstance(active, dict) or set(active) != required:
        raise ValueError(f"active_inquiry requires exactly {sorted(required)}")
    if not str(active["id"]).startswith("I"):
        raise ValueError("active_inquiry id must use an I# identity")
    for field in (
        "question",
        "goal_connection",
        "closure_condition",
        "rationale",
        "opened_in_session",
    ):
        _nonempty(active, field, f"active_inquiry {field}")
    if not isinstance(active["reframes"], list):
        raise TypeError("active_inquiry reframes must be a list")
    for reframe in active["reframes"]:
        required_reframe = {
            "question",
            "goal_connection",
            "closure_condition",
            "rationale",
            "session_id",
        }
        if not isinstance(reframe, dict) or set(reframe) != required_reframe:
            raise ValueError(
                f"inquiry reframe requires exactly {sorted(required_reframe)}"
            )
        for field in required_reframe:
            _nonempty(reframe, field, f"inquiry reframe {field}")


def _validate_session(session: object, active_inquiry: object) -> None:
    if session is None:
        return
    required = {
        "id",
        "kind",
        "objective",
        "inquiry_id",
        "scientific_parent_commit",
        "operation_ids",
    }
    if not isinstance(session, dict) or set(session) != required:
        raise ValueError(f"scientific_session requires exactly {sorted(required)}")
    if not str(session["id"]).startswith("S"):
        raise ValueError("scientific_session id must use an S# identity")
    if session["kind"] not in {"goal_review", "inquiry"}:
        raise ValueError("scientific_session kind must be goal_review or inquiry")
    _nonempty(session, "objective", "scientific_session objective")
    _nonempty(
        session,
        "scientific_parent_commit",
        "scientific_session scientific_parent_commit",
    )
    operation_ids = session["operation_ids"]
    if not isinstance(operation_ids, list) or not all(
        isinstance(item, str) and item.strip() for item in operation_ids
    ):
        raise ValueError("scientific_session operation_ids must be a list of strings")
    if session["kind"] == "goal_review":
        if session["inquiry_id"] is not None:
            raise ValueError("goal_review session cannot carry an inquiry_id")
    else:
        if (
            isinstance(active_inquiry, dict)
            and session["inquiry_id"] != active_inquiry["id"]
        ):
            raise ValueError("inquiry session belongs to another inquiry")


def _require_exact_fields(value: object, fields: set[str], description: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{description} requires exactly {sorted(fields)}")
    return value


def _validate_operation_request_shape(kind: str, request: object) -> None:
    if not isinstance(request, dict):
        raise TypeError(f"{kind} request must be an object")
    if kind == "training":
        required = {"initialization", "seed", "steps", "description", "rationale"}
        allowed = required | {"parent"}
        if frozenset(request) not in {frozenset(required), frozenset(allowed)}:
            raise ValueError("training request fields are invalid")
        return
    if kind == "measurement":
        required = {"description", "rationale", "measurements"}
        allowed = required | {"paired_comparisons"}
        if frozenset(request) not in {frozenset(required), frozenset(allowed)}:
            raise ValueError("measurement request fields are invalid")
        measurements = request["measurements"]
        if not isinstance(measurements, list):
            raise TypeError("measurement request measurements must be a list")
        entry_fields = {
            "research_evaluation": {
                "instrument",
                "candidate",
                "episodes",
                "seed",
                "label",
            },
            "task_reference": {"instrument", "candidate", "label"},
            "python_module": {"instrument", "module", "args", "artifact", "label"},
        }
        for entry in measurements:
            if not isinstance(entry, dict) or entry.get("instrument") not in entry_fields:
                raise ValueError("measurement request has an invalid instrument")
            fields = entry_fields[entry["instrument"]]
            if frozenset(entry) not in {
                frozenset(fields),
                frozenset(fields - {"label"}),
            }:
                raise ValueError("measurement request entry fields are invalid")
        comparisons = request.get("paired_comparisons", [])
        if not isinstance(comparisons, list) or any(
            not isinstance(item, dict)
            or set(item) != {"candidate", "reference"}
            for item in comparisons
        ):
            raise ValueError("paired comparison fields are invalid")
        return
    if kind == "inquiry":
        action = request.get("action")
        fields = (
            {"action", "outcome", "reason"}
            if action == "close"
            else {
                "action",
                "question",
                "goal_connection",
                "closure_condition",
                "rationale",
            }
        )
    elif kind == "checkpoint":
        fields = CHECKPOINT_FIELDS - {"session_id", "inquiry_id", "scientific_commit"}
    elif kind == "model_role":
        fields = {"action", "candidate", "reason", "evidence"}
        if request.get("action") == "retain":
            fields.add("label")
    elif kind == "restore_recipe":
        fields = {"candidate", "reason"}
    else:
        fields = {"action", "reason"}
    _require_exact_fields(request, fields, f"{kind} request")


def _validate_manifest(value: object, description: str) -> None:
    if not isinstance(value, list):
        raise TypeError(f"{description} must be a list")
    for entry in value:
        _require_exact_fields(
            entry, {"path", "exists", "fingerprint"}, f"{description} entry"
        )


def _validate_pending_plan(kind: str, plan: object) -> None:
    if kind == "inquiry":
        if not isinstance(plan, dict):
            raise TypeError("pending inquiry plan must be an object")
        action = plan.get("action")
        if action == "open":
            _require_exact_fields(plan, {"action", "inquiry"}, "pending inquiry plan")
            _require_exact_fields(
                plan["inquiry"],
                {
                    "id",
                    "question",
                    "goal_connection",
                    "closure_condition",
                    "rationale",
                    "opened_in_session",
                    "reframes",
                },
                "pending inquiry",
            )
        elif action == "reframe":
            _require_exact_fields(
                plan,
                {"action", "inquiry_id", "reframe"},
                "pending inquiry plan",
            )
            _require_exact_fields(
                plan["reframe"],
                {
                    "question",
                    "goal_connection",
                    "closure_condition",
                    "rationale",
                    "session_id",
                },
                "pending inquiry reframe",
            )
        else:
            _require_exact_fields(
                plan,
                {"action", "inquiry_id", "outcome", "reason"},
                "pending inquiry plan",
            )
        return
    if kind == "checkpoint":
        _require_exact_fields(
            plan, CHECKPOINT_FIELDS - {"scientific_commit"}, "pending checkpoint plan"
        )
        return
    if kind == "model_role":
        fields = {"action", "candidate_id", "reason", "evidence"}
        if isinstance(plan, dict) and plan.get("action") == "retain":
            fields.add("label")
        _require_exact_fields(plan, fields, "pending model_role plan")
        return
    if kind == "restore_recipe":
        _require_exact_fields(
            plan,
            {
                "parent",
                "restore",
                "remove_created",
                "candidate_id",
                "parameters",
                "session_id",
            },
            "pending restore_recipe plan",
        )
        return
    _require_exact_fields(
        plan, {"status", "reason", "model"}, "pending campaign_conclusion plan"
    )


def _validate_pending_data(kind: str, data: object) -> None:
    data = _require_exact_fields(
        data, PENDING_DATA_FIELDS[kind], f"pending {kind} data"
    )
    if data["result"] is not None and not isinstance(data["result"], dict):
        raise TypeError(f"pending {kind} result must be an object or null")
    if kind == "training":
        _validate_manifest(data["scientific_manifest"], "training manifest")
        parent = data["parent"]
        if parent is not None:
            _require_exact_fields(
                parent,
                {
                    "id",
                    "artifact",
                    "fingerprint",
                    "scientific_commit",
                    "parameters",
                    "training_steps",
                },
                "pending training parent",
            )
        archived = data["archived_candidates"]
        if archived is not None:
            if not isinstance(archived, list):
                raise TypeError("pending archived_candidates must be a list or null")
            for candidate in archived:
                _require_exact_fields(
                    candidate,
                    {
                        "name",
                        "artifact",
                        "fingerprint",
                        "timesteps",
                        "training_success",
                        "ep_rew_mean",
                    },
                    "pending archived candidate",
                )
        return
    if kind == "measurement":
        if not isinstance(data["measurements"], list):
            raise TypeError("pending measurement measurements must be a list")
        planned_fields = {
            "research_evaluation": {
                "instrument",
                "candidate",
                "episodes",
                "seed",
                "label",
                "candidate_id",
                "artifact",
                "model_fingerprint",
            },
            "task_reference": {
                "instrument",
                "candidate",
                "label",
                "candidate_id",
                "artifact",
                "model_fingerprint",
            },
            "python_module": {"instrument", "module", "args", "artifact", "label"},
        }
        for entry in data["measurements"]:
            if not isinstance(entry, dict) or entry.get("instrument") not in planned_fields:
                raise ValueError("pending measurement has an invalid instrument")
            _require_exact_fields(
                entry,
                planned_fields[entry["instrument"]],
                "pending measurement entry",
            )
        comparison_fields = {
            "candidate",
            "reference",
            "candidate_model_fingerprint",
            "reference_model_fingerprint",
            "shared_episode_seeds",
            "candidate_measurement_indexes",
            "reference_measurement_indexes",
        }
        if not isinstance(data["paired_comparisons"], list):
            raise TypeError("pending paired_comparisons must be a list")
        for comparison in data["paired_comparisons"]:
            _require_exact_fields(
                comparison, comparison_fields, "pending paired comparison"
            )
        if not isinstance(data["partial_results"], list):
            raise TypeError("pending partial_results must be a list")
        for partial in data["partial_results"]:
            if not isinstance(partial, dict):
                raise TypeError("pending partial measurement must be an object")
            fields = (
                {"instrument", "module", "args", "label", "metrics"}
                if partial.get("instrument") == "python_module"
                else {"instrument", "candidate", "candidate_id", "label", "metrics"}
            )
            _require_exact_fields(partial, fields, "pending partial measurement")
            if not isinstance(partial["metrics"], dict):
                raise TypeError("pending partial measurement metrics must be an object")
        contract = data["task_reference_contract"]
        if contract is not None:
            _require_exact_fields(
                contract,
                {"panel", "panel_version", "episodes", "seed"},
                "pending task-reference contract",
            )
        provenance = data["module_provenance"]
        if provenance is not None:
            provenance = _require_exact_fields(
                provenance,
                {
                    "code_parent_commit",
                    "scientific_manifest",
                    "effective_parameters",
                    "module_paths",
                    "module_manifest",
                    "campaign_lab_manifest",
                    "campaign_lab_publication",
                },
                "pending module provenance",
            )
            _validate_manifest(
                provenance["scientific_manifest"], "module scientific manifest"
            )
            _validate_manifest(provenance["module_manifest"], "module manifest")
            publication = provenance["campaign_lab_publication"]
            if publication is not None:
                _require_exact_fields(
                    publication,
                    {"commit", "manifest", "fingerprint"},
                    "campaign laboratory publication",
                )
        return
    if kind == "checkpoint":
        _validate_manifest(data["scientific_manifest"], "checkpoint manifest")
    if kind == "model_role" and data["publication"] is not None:
        _require_exact_fields(
            data["publication"],
            {"source", "destination", "fingerprint"},
            "pending model_role publication",
        )
    if kind == "restore_recipe":
        _validate_manifest(data["pre_restore_manifest"], "pre-restore manifest")
    _validate_pending_plan(kind, data["plan"])


def _validate_completed_event_result(kind: str, result: dict) -> None:
    if kind == "measurement":
        fields = {"status", "measurements", "paired_comparisons", "tool_provenance"}
    elif kind == "training":
        fields = {
            "status",
            "initialization",
            "parent",
            "seed",
            "requested_steps",
            "completed_steps",
            "scientific_commit",
            "mechanical_provenance",
            "candidates",
            "learning_dynamics",
        }
    elif kind == "inquiry":
        fields = {"status", "action", "inquiry_id"}
        if result.get("action") == "close":
            fields |= {"outcome", "reason"}
    elif kind == "checkpoint":
        fields = {"status", "session_id"}
    elif kind == "model_role":
        fields = {"status", "action", "candidate", "evidence"}
    elif kind == "restore_recipe":
        fields = {"status", "candidate", "scientific_commit", "restored_paths"}
    else:
        fields = {"status", "model"}
    _require_exact_fields(result, fields, f"completed {kind} result")


def _validate_pending_operation(pending: object) -> None:
    pending = _require_exact_fields(
        pending, PENDING_FIELDS, "pending_operation"
    )
    kind = pending.get("kind")
    if kind not in OPERATION_KINDS:
        raise ValueError("pending_operation has an unsupported kind")
    for field in ("id", "session_id", "request_fingerprint", "progress"):
        _nonempty(pending, field, f"pending_operation {field}")
    if pending["inquiry_id"] is not None:
        _nonempty(
            {"value": pending["inquiry_id"]},
            "value",
            "pending_operation inquiry_id",
        )
    if pending["failure"] is not None:
        _nonempty({"value": pending["failure"]}, "value", "pending_operation failure")
    if pending["supersedes"] is not None:
        _nonempty(
            {"value": pending["supersedes"]},
            "value",
            "pending_operation supersedes",
        )
    request = _require_exact_fields(
        pending["request"], {kind}, "pending_operation request"
    )
    _validate_operation_request_shape(kind, request[kind])
    progress = pending["progress"]
    if kind == "measurement" and (
        match := re.fullmatch(r"measured_(\d+)_of_(\d+)", progress)
    ):
        completed, total = map(int, match.groups())
        if total != len(pending["data"]["measurements"]) or not 0 <= completed <= total:
            raise ValueError("pending measurement progress contradicts its plan")
    elif progress not in PENDING_PROGRESS[kind]:
        raise ValueError(f"pending {kind} has unsupported progress {progress!r}")
    _validate_pending_data(kind, pending["data"])


def _validate_operation_event(event: object) -> str:
    event = _require_exact_fields(event, EVENT_FIELDS, "operation event")
    identifier = _nonempty(event, "id", "operation event id")
    kind = event.get("kind")
    if kind not in OPERATION_KINDS:
        raise ValueError("operation event has an unsupported kind")
    _nonempty(event, "session_id", "operation event session_id")
    if event["inquiry_id"] is not None:
        _nonempty({"value": event["inquiry_id"]}, "value", "operation event inquiry_id")
    request = event["request"]
    _validate_operation_request_shape(kind, request)
    if event["status"] not in {"completed", "failed"}:
        raise ValueError("operation event status must be completed or failed")
    result = event["result"]
    if not isinstance(result, dict):
        raise TypeError("operation event result must be an object")
    if event["status"] == "failed":
        _require_exact_fields(result, {"status", "error"}, "failed operation result")
        if result["status"] != "failed" or result["error"] != event["error"]:
            raise ValueError("failed operation event provenance is inconsistent")
        _nonempty(event, "error", "operation event error")
        _nonempty(event, "superseded_by", "operation event superseded_by")
    elif event["error"] is not None or event["superseded_by"] is not None:
        raise ValueError("completed operation event cannot carry failure provenance")
    else:
        _validate_completed_event_result(kind, result)
    if event["supersedes"] is not None:
        _nonempty(event, "supersedes", "operation event supersedes")
    _nonempty(event, "completed_at", "operation event completed_at")
    return identifier


def validate_research_state(state: dict, *, allow_missing_artifact: bool) -> None:
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise RuntimeError("unsupported research state schema")
    missing = STATE_FIELDS - set(state)
    extra = set(state) - STATE_FIELDS
    if missing or extra:
        raise RuntimeError(
            "research state fields are invalid: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    campaign = _require_exact_fields(state["campaign"], CAMPAIGN_FIELDS, "campaign")
    for field in ("id", "started_at", "base_commit"):
        _nonempty(campaign, field, f"campaign {field}")
    if campaign["recipe_source_commit"] is not None:
        _nonempty(
            campaign, "recipe_source_commit", "campaign recipe_source_commit"
        )
    _positive_integer(campaign.get("max_inquiries"), "campaign max_inquiries")
    human_goal = state["human_goal"]
    if not isinstance(human_goal, dict) or set(human_goal) - {"source", "summary"}:
        raise ValueError("human_goal supports only source and optional summary")
    _nonempty(human_goal, "source", "human_goal source")
    if "summary" in human_goal:
        _nonempty(human_goal, "summary", "human_goal summary")
    model = state["scientific_model"]
    if not isinstance(model, dict) or set(model) != {"status", "path", "commit"}:
        raise ValueError("scientific_model requires status, path, and commit")
    if model["status"] not in {"pending", "ready"}:
        raise ValueError("scientific_model status must be pending or ready")
    _nonempty(model, "path", "scientific_model path")
    if model["path"] != "research/scientific_model.md":
        raise ValueError("scientific_model path is unsupported")
    if model["status"] == "ready":
        _nonempty(model, "commit", "scientific_model commit")
    elif model["commit"] is not None:
        raise ValueError("pending scientific_model cannot carry a commit")

    counters = state["counters"]
    expected_counters = {"inquiry", "session", "measurement", "training", "event"}
    if not isinstance(counters, dict) or set(counters) != expected_counters:
        raise ValueError(f"counters requires exactly {sorted(expected_counters)}")
    for field, value in counters.items():
        _positive_integer(value, f"counter {field}", allow_zero=True)

    events = state["operation_events"]
    if not isinstance(events, list):
        raise TypeError("operation_events must be a list")
    event_ids: set[str] = set()
    for event in events:
        identifier = _validate_operation_event(event)
        if identifier in event_ids:
            raise ValueError("operation event IDs must be unique")
        event_ids.add(identifier)

    _validate_active_inquiry(state["active_inquiry"])
    _validate_session(state["scientific_session"], state["active_inquiry"])
    _validate_checkpoint(state["pi_checkpoint"], event_ids)

    pending = state["pending_operation"]
    if pending is not None:
        _validate_pending_operation(pending)

    candidates = state["candidates"]
    if not isinstance(candidates, dict):
        raise TypeError("candidates must be an object keyed by candidate ID")
    for identifier, candidate in candidates.items():
        canonicalize_candidate(candidate)
        if identifier != candidate["id"]:
            raise ValueError("candidate map key must equal candidate id")
        if not allow_missing_artifact:
            artifact = resolve_repo_path(candidate["artifact"])
            require_complete_inference_artifact(artifact, f"candidate {identifier}")
            if artifact_fingerprint(artifact) != candidate["fingerprint"]:
                raise ValueError(f"candidate {identifier} fingerprint changed")

    roles = state["model_roles"]
    if not isinstance(roles, dict) or set(roles) != {
        "working",
        "best_known",
        "retained",
    }:
        raise ValueError("model_roles requires working, best_known, and retained")
    for role in ("working", "best_known"):
        candidate_id = roles[role]
        if candidate_id is not None and candidate_id not in candidates:
            raise ValueError(f"model role {role} names an unknown candidate")
    retained = roles["retained"]
    if not isinstance(retained, dict):
        raise TypeError("model_roles retained must be an object")
    for label, candidate_id in retained.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError("retained role labels must be non-empty")
        if candidate_id not in candidates:
            raise ValueError(f"retained role {label!r} names an unknown candidate")

    terminal = state["terminal_state"]
    if terminal is not None:
        if not isinstance(terminal, dict) or set(terminal) != {
            "status",
            "reason",
            "model",
        }:
            raise ValueError("terminal_state requires status, reason, and model")
        if terminal["status"] not in {
            "official_assessment_requested",
            "no_credible_route",
        }:
            raise ValueError("terminal_state status is unsupported")
        _nonempty(terminal, "reason", "terminal_state reason")
        if terminal["status"] == "official_assessment_requested":
            if terminal["model"] not in candidates:
                raise ValueError("terminal assessment names an unknown candidate")
        elif terminal["model"] is not None:
            raise ValueError("no_credible_route terminal state cannot name a model")
    assessment = state["official_assessment"]
    if assessment is not None:
        assessment = _require_exact_fields(
            assessment, OFFICIAL_ASSESSMENT_FIELDS, "official_assessment"
        )
        if (
            terminal is None
            or terminal["status"] != "official_assessment_requested"
        ):
            raise ValueError(
                "official_assessment requires an assessment-requested terminal state"
            )
        if assessment["status"] not in {"passed", "failed"}:
            raise ValueError("official_assessment status must be passed or failed")
        if assessment["model"] != terminal["model"]:
            raise ValueError("official_assessment model must match terminal state")
        _nonempty(assessment, "summary", "official_assessment summary")
        _nonempty(assessment, "completed_at", "official_assessment completed_at")


def write_state(state: dict) -> None:
    validate_research_state(state, allow_missing_artifact=True)
    atomic_write_json(paths.STATE_PATH, state)


def read_state() -> dict:
    return json.loads(paths.STATE_PATH.read_text(encoding="utf-8"))


def load_state(*, allow_missing_artifact: bool = False) -> dict:
    if not paths.STATE_PATH.exists():
        raise RuntimeError("research state is missing; refusing to run")
    state = read_state()
    validate_research_state(state, allow_missing_artifact=allow_missing_artifact)
    return state


def empty_campaign_state(
    *,
    campaign: dict,
    last_verdict: str,
    human_goal: dict | None = None,
) -> dict:
    campaign_copy = copy.deepcopy(campaign)
    campaign_id = str(campaign_copy.get("id") or "").strip()
    if not campaign_id:
        raise ValueError("fresh campaign state requires a campaign ID")
    campaign_copy.setdefault("max_inquiries", DEFAULT_MAX_INQUIRIES)
    campaign_copy.setdefault("recipe_source_commit", None)
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "campaign": campaign_copy,
        "human_goal": copy.deepcopy(human_goal or {"source": "research/scenario.md"}),
        "scientific_model": {
            "status": "pending",
            "path": "research/scientific_model.md",
            "commit": None,
        },
        "active_inquiry": None,
        "pi_checkpoint": None,
        "scientific_session": None,
        "counters": {
            "inquiry": 0,
            "session": 0,
            "measurement": 0,
            "training": 0,
            "event": 0,
        },
        "operation_events": [],
        "pending_operation": None,
        "model_roles": {
            "working": None,
            "best_known": None,
            "retained": {},
        },
        "candidates": {},
        "terminal_state": None,
        "official_assessment": None,
        "last_verdict": last_verdict,
    }
    validate_research_state(copy.deepcopy(state), allow_missing_artifact=True)
    return state


def current_campaign_id(state: dict) -> str:
    return str(state["campaign"]["id"])


def start_scientific_session(state: dict, *, kind: str, objective: str) -> dict:
    if state["terminal_state"] is not None:
        raise ValueError("a terminal campaign cannot start a scientific session")
    if state["scientific_model"]["status"] != "ready":
        raise ValueError("the scientific model must be ready before a PI session")
    if state["scientific_session"] is not None:
        raise ValueError("a scientific session is already active")
    if kind not in {"goal_review", "inquiry"}:
        raise ValueError("session kind must be goal_review or inquiry")
    active = state["active_inquiry"]
    if kind == "goal_review" and active is not None:
        raise ValueError("goal review requires no active inquiry")
    if kind == "inquiry" and active is None:
        raise ValueError("an inquiry session requires an active inquiry")
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("scientific session objective must be non-empty")
    state["counters"]["session"] += 1
    session = {
        "id": f"S{state['counters']['session']}",
        "kind": kind,
        "objective": objective.strip(),
        "inquiry_id": active["id"] if isinstance(active, dict) else None,
        "scientific_parent_commit": git("rev-parse", "HEAD").strip(),
        "operation_ids": [],
    }
    state["scientific_session"] = session
    return session


def require_scientific_model_publication_pending(state: dict) -> None:
    if state["scientific_model"] != {
        "status": "pending",
        "path": "research/scientific_model.md",
        "commit": None,
    }:
        raise ValueError("the scientific model can be published only once from pending")
    if (
        state["active_inquiry"] is not None
        or state["pi_checkpoint"] is not None
        or state["scientific_session"] is not None
        or state["operation_events"]
        or state["pending_operation"] is not None
        or any(state["counters"].values())
    ):
        raise ValueError(
            "the scientific model must be published before scientific sessions "
            "or operations"
        )


def mark_scientific_model_ready(state: dict, commit: str) -> None:
    require_scientific_model_publication_pending(state)
    require_resolvable_commit(commit)
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": commit,
    }


def measurement_evidence(record: dict) -> dict:
    artifact_value = _nonempty(
        record, "evaluation_artifact", "measurement evaluation_artifact"
    )
    expected = _nonempty(
        record,
        "evaluation_artifact_fingerprint",
        "measurement evaluation_artifact_fingerprint",
    )
    artifact = resolve_repo_path(artifact_value)
    if not artifact.is_file():
        raise ValueError(f"measurement artifact is missing: {artifact_value}")
    if file_fingerprint(artifact) != expected:
        raise ValueError("measurement artifact content changed after recording")
    evidence = json.loads(artifact.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise TypeError("measurement artifact must contain a JSON object")
    for field in ("episodes", "seed"):
        if field in record and evidence.get(field) != record[field]:
            raise ValueError(f"measurement artifact {field} differs from its record")
    return {**record, **evidence}


def measurement_record(metrics: dict) -> dict:
    record = {
        key: value
        for key, value in metrics.items()
        if key not in {"episode_results", "model", "research_evidence"}
    }
    episode_results = metrics.get("episode_results")
    if isinstance(episode_results, list) and episode_results:
        record["successes"] = sum(
            bool(item.get("success"))
            for item in episode_results
            if isinstance(item, dict)
        )
    return record


def history_records() -> list[dict]:
    if not paths.RESULTS_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in paths.RESULTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def render_operation_log(records: list[dict]) -> str:
    lines = [
        "# Campaign operation log",
        "",
        "| Operation | Kind | Inquiry | Result |",
        "|---|---|---|---|",
    ]
    for record in records:
        result = record.get("result") or {}
        summary = str(
            result.get("summary")
            or result.get("status")
            or result.get("outcome")
            or "completed"
        )
        summary = " ".join(summary.replace("|", "/").split())
        lines.append(
            f"| {record.get('id', '-')} | {record.get('kind', '-')} | "
            f"{record.get('inquiry_id') or '-'} | {summary} |"
        )
    return "\n".join(lines) + "\n"


def regenerate_operation_log() -> None:
    atomic_write_text(paths.LOG_PATH, render_operation_log(history_records()))


def synchronize_operation_log() -> None:
    expected = render_operation_log(history_records())
    if (
        not paths.LOG_PATH.exists()
        or paths.LOG_PATH.read_text(encoding="utf-8") != expected
    ):
        atomic_write_text(paths.LOG_PATH, expected)


def upsert_operation_event(event: dict) -> None:
    records = history_records()
    updated: list[dict] = []
    replaced = False
    for existing in records:
        if existing.get("campaign_id") == event.get("campaign_id") and existing.get(
            "id"
        ) == event.get("id"):
            if not replaced:
                updated.append(copy.deepcopy(event))
                replaced = True
            continue
        updated.append(existing)
    if not replaced:
        updated.append(copy.deepcopy(event))
    atomic_write_text(
        paths.RESULTS_PATH,
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in updated),
    )
    regenerate_operation_log()


def require_complete_artifact(artifact: Path, description: str) -> None:
    for filename in ARTIFACT_FILES:
        if not (artifact / filename).is_file():
            raise ValueError(f"{description} is incomplete: {filename}")


def require_complete_inference_artifact(artifact: Path, description: str) -> None:
    for filename in INFERENCE_ARTIFACT_FILES:
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


def file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def durable_artifact_destination(
    *, campaign_id: str, origin_operation: str, candidate: str, fingerprint: str
) -> Path:
    checkpoint = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:8]
    return paths.campaign_retained_root(campaign_id) / (
        f"{origin_operation.lower()}-c{checkpoint}-{fingerprint}"
    )


def publish_artifact(publication: dict) -> None:
    source = resolve_repo_path(str(publication["source"]))
    destination = resolve_repo_path(str(publication["destination"]))
    expected = str(publication["fingerprint"])
    require_complete_inference_artifact(source, "candidate source")
    if artifact_fingerprint(source) != expected:
        raise ValueError("candidate source fingerprint changed")
    if destination.exists():
        require_complete_inference_artifact(destination, "durable candidate")
        if artifact_fingerprint(destination) != expected:
            raise ValueError("durable candidate collides with a different artifact")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        if temporary.exists():
            shutil.rmtree(temporary)
        copy_artifact(source, temporary)
        require_complete_inference_artifact(temporary, "staged durable candidate")
        if artifact_fingerprint(temporary) != expected:
            raise ValueError("staged durable candidate fingerprint does not match")
        _atomic_replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def archive_candidates(
    operation_id: str,
    contenders: list[dict],
    config: dict,
    *,
    campaign_id: str,
) -> list[dict]:
    destination = paths.campaign_checkpoint_root(campaign_id) / operation_id.lower()
    inventory_path = destination / "inventory.json"
    parameters_path = destination / "parameters.json"
    if inventory_path.is_file() and parameters_path.is_file():
        archived = json.loads(inventory_path.read_text(encoding="utf-8"))["candidates"]
        if json.loads(parameters_path.read_text(encoding="utf-8")) != config:
            raise ValueError("archived candidate configuration changed")
        for item in archived:
            artifact = resolve_repo_path(item["artifact"])
            require_complete_inference_artifact(
                artifact, f"archived candidate {item['name']!r}"
            )
            if artifact_fingerprint(artifact) != item["fingerprint"]:
                raise ValueError("archived candidate fingerprint changed")
        return archived
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    archived: list[dict] = []
    for contender in contenders:
        name = str(contender["name"])
        artifact = destination / name
        copy_artifact(contender["path"], artifact)
        archived.append(
            {
                "name": name,
                "artifact": repo_relative_path(artifact),
                "fingerprint": artifact_fingerprint(artifact),
                "timesteps": int(contender["timesteps"]),
                "training_success": contender.get("training_success"),
                "ep_rew_mean": contender.get("ep_rew_mean"),
            }
        )
    atomic_write_json(parameters_path, config)
    atomic_write_json(
        inventory_path,
        {"schema_version": 1, "operation": operation_id, "candidates": archived},
    )
    return archived
