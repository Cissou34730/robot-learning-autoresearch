"""Strict goal-centered protocol validation for Runner operations."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from research import runner_paths as paths
from research import runner_repository as repository

PROTECTED_BENCHMARK_PATHS = {
    "robot_learning/policy_runtime.py",
    "research/run_experiment.py",
    "robot_learning/__init__.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/final_benchmark.py",
    "robot_learning/scenario/task_reference.py",
}
PROTECTED_BENCHMARK_PREFIXES = ("robot_learning/benchmark/",)
PROTECTED_RUNNER_PATHS = {
    "tools/campaign_report.py",
    "research/migrate_policy_runtime.py",
    "research/reset_campaign.py",
    "research/build_research_brief.py",
    "research/query_training_log.py",
    "researcher_session.ps1",
    "run_research.ps1",
    "researcher_mutex.ps1",
}
PROTECTED_RUNTIME_PATHS = {"researcher_copilot.py"}
PROTECTED_RUNTIME_PREFIXES = ("researcher_opencode/",)
PROTECTED_MEASUREMENT_PATHS = {"robot_learning/paired_evidence.py"}
PROTECTED_CONTEXT_PATHS = {
    "AGENTS.md",
    "research/instruments.md",
    "research/program.md",
    "research/scenario.md",
}
CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS = {"research/scientific_model.md"}
PROTECTED_RUNNER_PREFIXES = ("research/runner_",)
PROTECTED_TEST_PREFIXES = ("tests/",)
VALIDATED_TEST_PATHS = ("tests/benchmark", "tests/autoresearch")
AUTORESEARCH_BOUNDARY_TEST_PATHS = (
    "tests/autoresearch/test_ownership_registry.py",
    "tests/autoresearch/test_policy_runtime.py",
)
RESEARCHER_VALIDATED_TEST_PATHS = (*AUTORESEARCH_BOUNDARY_TEST_PATHS,)
RESEARCHER_OWNED_PREFIXES = (
    "robot_learning/scenario/",
    "robot_learning/training/",
)
CAMPAIGN_LAB_PREFIXES = ("research/lab/",)
RESEARCHER_OWNED_PATHS = {
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
}
PARAMETER_ONLY_PATHS = {"research/current_params.json"}
DEPENDENCY_METADATA_PATHS = {"pyproject.toml", "uv.lock"}
EVALUATION_SEMANTICS_ROOT = "robot_learning/scenario"
PRESENTATION_ONLY_PATHS = {
    "robot_learning/scenario/progress.py",
    "robot_learning/scenario/viewer.py",
}
TRAINING_ONLY_PATHS = {
    "robot_learning/scenario/reward.py",
    "robot_learning/scenario/training_environment.py",
}
MODEL_CONTAINED_RUNTIME_PATHS = {
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/policy_io.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
}
EVALUATION_RUNTIME_PATHS = (
    "robot_learning/policy_runtime.py",
    "robot_learning/evaluate.py",
    "robot_learning/benchmark/spec.py",
    "robot_learning/benchmark/metrics.py",
)
GENERATED_FILE_SUFFIXES = (".pyc", ".pyo", ".tmp")
GENERATED_DIRECTORY_NAMES = {"__pycache__"}
SUPPORTED_MEASUREMENT_INSTRUMENTS = {
    "python_module",
    "research_evaluation",
    "task_reference",
}
RESEARCH_EVALUATION_ENTRY_FIELDS = {
    "instrument",
    "candidate",
    "episodes",
    "seed",
    "label",
}
TASK_REFERENCE_ENTRY_FIELDS = {
    "instrument",
    "candidate",
    "label",
}
PYTHON_MODULE_ENTRY_FIELDS = {
    "instrument",
    "module",
    "args",
    "artifact",
    "label",
}
OPERATION_KEYS = {
    "inquiry",
    "measurement",
    "training",
    "checkpoint",
    "model_role",
    "restore_recipe",
    "campaign_conclusion",
}
SCIENTIFIC_OPERATION_KINDS = {
    "measurement",
    "training",
    "model_role",
    "restore_recipe",
}
SESSION_OPERATION_MATRIX = {
    "startup": {*SCIENTIFIC_OPERATION_KINDS, "checkpoint"},
    "goal_review": {"inquiry", "campaign_conclusion", "checkpoint"},
    "inquiry": {*SCIENTIFIC_OPERATION_KINDS, "inquiry", "checkpoint"},
}
TRUSTED_RUNTIME_PATHS = {
    "robot_learning/__init__.py",
    "robot_learning/policy_runtime.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
}
TASK_REFERENCE_ADAPTER_PATH = "robot_learning/scenario/task_reference.py"
OFFICIAL_ASSESSMENT_ADAPTER_PATH = "robot_learning/scenario/final_benchmark.py"


def is_protected_source(path: str) -> bool:
    relative = path.replace("\\", "/")
    return (
        relative in PROTECTED_BENCHMARK_PATHS
        or relative in PROTECTED_RUNNER_PATHS
        or relative in PROTECTED_RUNTIME_PATHS
        or relative in PROTECTED_MEASUREMENT_PATHS
        or relative in PROTECTED_CONTEXT_PATHS
        or relative in CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS
        or relative in DEPENDENCY_METADATA_PATHS
        or relative.startswith(PROTECTED_BENCHMARK_PREFIXES)
        or relative.startswith(PROTECTED_RUNNER_PREFIXES)
        or relative.startswith(PROTECTED_RUNTIME_PREFIXES)
    )


def is_human_owned(path: str) -> bool:
    relative = path.replace("\\", "/")
    return is_protected_source(relative) or relative.startswith(PROTECTED_TEST_PREFIXES)


def is_researcher_owned(path: str) -> bool:
    relative = path.replace("\\", "/")
    if is_human_owned(relative):
        return False
    return (
        relative in RESEARCHER_OWNED_PATHS
        or relative.startswith(RESEARCHER_OWNED_PREFIXES)
        or relative.startswith(CAMPAIGN_LAB_PREFIXES)
    )


def is_campaign_lab(path: str) -> bool:
    relative = path.replace("\\", "/")
    return not is_protected_source(relative) and relative.startswith(
        CAMPAIGN_LAB_PREFIXES
    )


def declared_paths_exist(root: Path | None = None) -> list[str]:
    base = root or paths.ROOT
    declared = {
        *PROTECTED_BENCHMARK_PATHS,
        *PROTECTED_RUNNER_PATHS,
        *PROTECTED_RUNTIME_PATHS,
        *PROTECTED_MEASUREMENT_PATHS,
        *PROTECTED_CONTEXT_PATHS,
        *DEPENDENCY_METADATA_PATHS,
        *RESEARCHER_OWNED_PATHS,
        *PARAMETER_ONLY_PATHS,
        *PRESENTATION_ONLY_PATHS,
        *TRAINING_ONLY_PATHS,
        *MODEL_CONTAINED_RUNTIME_PATHS,
        *EVALUATION_RUNTIME_PATHS,
    }
    missing = [relative for relative in declared if not (base / relative).is_file()]
    missing.extend(
        prefix
        for prefix in PROTECTED_BENCHMARK_PREFIXES
        if not (base / prefix).is_dir()
    )
    return sorted(missing)


def validation_test_paths(changed_paths: list[str]) -> tuple[str, ...]:
    sources = [
        path
        for path in changed_paths
        if path.replace("\\", "/") not in PARAMETER_ONLY_PATHS
    ]
    if not sources:
        return ()
    if all(is_researcher_owned(path) for path in sources):
        return RESEARCHER_VALIDATED_TEST_PATHS
    return VALIDATED_TEST_PATHS


TEST_SURFACE_REJECTION = "tests are human-owned and cannot be changed by the PI"
NOT_OWNED_PATHS_REMEDY = "remove those paths from the scientific operation"


def validate_research_delta_ownership(code_changes: list[str]) -> None:
    normalized = sorted({path.replace("\\", "/") for path in code_changes})
    protected_tests = sorted(
        path for path in normalized if path.startswith(PROTECTED_TEST_PREFIXES)
    )
    if protected_tests:
        raise ValueError(
            f"{TEST_SURFACE_REJECTION}: {protected_tests}; {NOT_OWNED_PATHS_REMEDY}"
        )
    rejected = sorted(
        path
        for path in normalized
        if not is_researcher_owned(path) and path not in PARAMETER_ONLY_PATHS
    )
    if rejected:
        raise ValueError(
            "scientific changes include human-owned or unclassified paths: "
            f"{rejected}; {NOT_OWNED_PATHS_REMEDY}"
        )


def validate_clean_human_owned_worktree() -> None:
    changed = repository.status_paths((".",))
    rejected = sorted(path for path in changed if is_human_owned(path))
    if rejected:
        raise ValueError(
            "protected or human-owned files have uncommitted changes: "
            f"{rejected}; restore them before protected assessment"
        )


def require_trusted_assessment_runtime(adapter_path: str) -> None:
    validate_clean_human_owned_worktree()
    trusted = [
        *TRUSTED_RUNTIME_PATHS,
        adapter_path,
        *repository.tracked_paths("robot_learning/benchmark"),
    ]
    repository.require_paths_at_head(trusted)


def scientific_strategy_section(text: str, campaign_id: str | None) -> str:
    """Return one campaign's PI-authored scientific-strategy section."""
    if not campaign_id:
        return ""
    match = re.search(
        rf"^## {re.escape(campaign_id)} / Scientific strategy\b.*?(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(0) if match else ""


def _nonempty(record: dict, field: str, description: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{description} must be a non-empty string")
    return value.strip()


def _integer(record: dict, field: str, description: str, *, minimum: int = 0) -> int:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{description} must be an integer")
    if value < minimum:
        raise ValueError(f"{description} must be at least {minimum}")
    return value


def require_active_session(state: dict) -> dict:
    session = state.get("scientific_session")
    if not isinstance(session, dict):
        raise TypeError("this operation requires an active scientific session")
    return session


def resolve_candidate(state: dict, identifier: str) -> dict:
    candidate_id = identifier.strip()
    roles = state["model_roles"]
    if candidate_id in {"working", "best_known"}:
        candidate_id = roles[candidate_id]
    elif candidate_id in roles["retained"]:
        candidate_id = roles["retained"][candidate_id]
    candidate = state["candidates"].get(candidate_id)
    if not isinstance(candidate, dict):
        raise KeyError(f"unknown model candidate {identifier!r}")
    artifact = repository.resolve_repo_path(candidate["artifact"])
    repository.require_complete_inference_artifact(
        artifact, f"model candidate {identifier!r}"
    )
    if repository.artifact_fingerprint(artifact) != candidate["fingerprint"]:
        raise ValueError(f"model candidate {identifier!r} fingerprint changed")
    return candidate


def validate_training_request(request: dict) -> None:
    required = {"initialization", "seed", "steps", "description", "rationale"}
    allowed = {*required, "parent"}
    missing = required - set(request)
    extra = set(request) - allowed
    if missing or extra:
        raise ValueError(
            "training request fields are invalid: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    initialization = request["initialization"]
    if initialization not in {"fresh", "transfer"}:
        raise ValueError("training initialization must be fresh or transfer")
    _integer(request, "seed", "training seed", minimum=0)
    _integer(request, "steps", "training steps", minimum=1)
    _nonempty(request, "description", "training description")
    _nonempty(request, "rationale", "training rationale")
    if initialization == "transfer":
        _nonempty(request, "parent", "transfer training parent")
    elif "parent" in request:
        raise ValueError("fresh training must not declare a parent")


def resolved_training_parent(request: dict, state: dict) -> dict | None:
    if request["initialization"] == "fresh":
        return None
    parent = resolve_candidate(state, str(request["parent"]))
    return {
        "id": parent["id"],
        "artifact": parent["artifact"],
        "fingerprint": parent["fingerprint"],
        "scientific_commit": parent["scientific_commit"],
        "parameters": parent["parameters"],
        "training_steps": parent["training_steps"],
    }


def requested_measurements(request: dict) -> list[dict]:
    measurements = request.get("measurements")
    if not isinstance(measurements, list):
        raise TypeError("measurement request measurements must be a list")
    if not measurements:
        raise ValueError("measurement request must contain at least one measurement")
    return measurements


def validate_measurement_request(request: dict) -> None:
    required = {"description", "rationale", "measurements"}
    allowed = {*required, "paired_comparisons"}
    missing = required - set(request)
    extra = set(request) - allowed
    if missing or extra:
        raise ValueError(
            "measurement request fields are invalid: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )
    _nonempty(request, "description", "measurement description")
    _nonempty(request, "rationale", "measurement rationale")
    for entry in requested_measurements(request):
        if not isinstance(entry, dict):
            raise TypeError("each measurement must be an object")
        instrument = entry.get("instrument")
        if instrument not in SUPPORTED_MEASUREMENT_INSTRUMENTS:
            raise ValueError(f"unknown measurement instrument {instrument!r}")
        if instrument == "research_evaluation":
            allowed_fields = RESEARCH_EVALUATION_ENTRY_FIELDS
        elif instrument == "task_reference":
            allowed_fields = TASK_REFERENCE_ENTRY_FIELDS
        else:
            allowed_fields = PYTHON_MODULE_ENTRY_FIELDS
        extra_fields = set(entry) - allowed_fields
        if extra_fields:
            raise ValueError(
                f"{instrument} measurement has unsupported fields "
                f"{sorted(extra_fields)}"
            )
        if "label" in entry and not isinstance(entry["label"], str):
            raise TypeError("measurement label must be a string")
        if instrument == "research_evaluation":
            _nonempty(entry, "candidate", "research_evaluation candidate")
            _integer(entry, "episodes", "research evaluation episodes", minimum=1)
            _integer(entry, "seed", "research evaluation seed", minimum=0)
        elif instrument == "task_reference":
            _nonempty(entry, "candidate", "task_reference candidate")
        else:
            module = _nonempty(entry, "module", "python_module module")
            if not module.startswith(("research.lab.", "robot_learning.scenario.")):
                raise ValueError(
                    "python_module must be under research.lab or "
                    "robot_learning.scenario"
                )
            arguments = entry.get("args")
            if not isinstance(arguments, list) or not all(
                isinstance(item, str) for item in arguments
            ):
                raise TypeError("python_module args must be a list of strings")
            artifact = repository.canonical_repo_path(
                _nonempty(entry, "artifact", "python_module artifact")
            )
            if not artifact.startswith("research/evaluations/"):
                raise ValueError(
                    "python_module artifact must be under research/evaluations"
                )
    comparisons = request.get("paired_comparisons", [])
    if not isinstance(comparisons, list):
        raise TypeError("paired_comparisons must be a list")
    for comparison in comparisons:
        if not isinstance(comparison, dict) or set(comparison) != {
            "candidate",
            "reference",
        }:
            raise ValueError(
                "paired comparison requires exactly candidate and reference"
            )
        _nonempty(comparison, "candidate", "paired comparison candidate")
        _nonempty(comparison, "reference", "paired comparison reference")


def planned_measurements(request: dict, state: dict) -> list[dict]:
    validate_measurement_request(request)
    planned: list[dict] = []
    for index, entry in enumerate(requested_measurements(request), start=1):
        if entry["instrument"] == "python_module":
            artifact = repository.canonical_repo_path(entry["artifact"])
            campaign_prefix = (
                repository.repo_relative_path(
                    paths.campaign_evaluation_dir(repository.current_campaign_id(state))
                )
                + "/"
            )
            if not artifact.startswith(campaign_prefix):
                raise ValueError(
                    "python_module artifact must be scoped to the current campaign"
                )
            planned.append(
                {
                    **entry,
                    "artifact": artifact,
                    "label": str(entry.get("label") or f"measurement {index}").strip(),
                }
            )
            continue
        candidate_name = str(entry["candidate"]).strip()
        candidate = resolve_candidate(state, candidate_name)
        planned.append(
            {
                **entry,
                "candidate": candidate["id"],
                "candidate_id": candidate["id"],
                "artifact": candidate["artifact"],
                "model_fingerprint": candidate["fingerprint"],
                "label": str(entry.get("label") or f"measurement {index}").strip(),
            }
        )
    return planned


def planned_paired_comparisons(
    request: dict, state: dict, measurements: list[dict]
) -> list[dict]:
    research_measurements: dict[str, list[tuple[int, dict]]] = {}
    for index, entry in enumerate(measurements):
        if entry["instrument"] == "research_evaluation":
            research_measurements.setdefault(entry["candidate_id"], []).append(
                (index, entry)
            )
    planned: list[dict] = []
    for comparison in request.get("paired_comparisons", []):
        candidate = resolve_candidate(state, str(comparison["candidate"]))
        reference = resolve_candidate(state, str(comparison["reference"]))
        for role, resolved in (("candidate", candidate), ("reference", reference)):
            if resolved["id"] not in research_measurements:
                raise ValueError(
                    f"paired comparison {role} {resolved['id']!r} must have a "
                    "planned research_evaluation measurement"
                )
        candidate_episodes = {
            seed
            for _, entry in research_measurements[candidate["id"]]
            for seed in range(
                int(entry["seed"]), int(entry["seed"]) + int(entry["episodes"])
            )
        }
        reference_episodes = {
            seed
            for _, entry in research_measurements[reference["id"]]
            for seed in range(
                int(entry["seed"]), int(entry["seed"]) + int(entry["episodes"])
            )
        }
        shared_episode_seeds = sorted(candidate_episodes & reference_episodes)
        if not shared_episode_seeds:
            raise ValueError(
                "paired comparison candidates have no shared planned episodes"
            )
        shared = set(shared_episode_seeds)
        candidate_measurement_indexes = [
            index
            for index, entry in research_measurements[candidate["id"]]
            if shared.intersection(
                range(
                    int(entry["seed"]),
                    int(entry["seed"]) + int(entry["episodes"]),
                )
            )
        ]
        reference_measurement_indexes = [
            index
            for index, entry in research_measurements[reference["id"]]
            if shared.intersection(
                range(
                    int(entry["seed"]),
                    int(entry["seed"]) + int(entry["episodes"]),
                )
            )
        ]
        planned.append(
            {
                "candidate": candidate["id"],
                "reference": reference["id"],
                "candidate_model_fingerprint": candidate["fingerprint"],
                "reference_model_fingerprint": reference["fingerprint"],
                "shared_episode_seeds": shared_episode_seeds,
                "candidate_measurement_indexes": candidate_measurement_indexes,
                "reference_measurement_indexes": reference_measurement_indexes,
            }
        )
    return planned


def validate_panel_independence(
    request: dict,
    *,
    protected_overlap=None,
) -> None:
    for entry in requested_measurements(request):
        if entry.get("instrument") != "research_evaluation":
            continue
        if protected_overlap is not None and protected_overlap(
            int(entry["seed"]), int(entry["episodes"])
        ):
            raise ValueError(
                "research evaluation panel overlaps protected benchmark evidence"
            )


def plan_inquiry_operation(request: dict, state: dict) -> dict:
    session = require_active_session(state)
    action = str(request.get("action", "")).strip()
    active = state.get("active_inquiry")
    if action == "open":
        expected = {
            "action",
            "question",
            "goal_connection",
            "closure_condition",
            "rationale",
        }
        if set(request) != expected:
            raise ValueError(f"inquiry open requires exactly {sorted(expected)}")
        if active is not None:
            raise ValueError("an inquiry is already active")
        if session["kind"] != "goal_review":
            raise ValueError("only a goal-review session may open an inquiry")
        if int(state["counters"]["inquiry"]) >= int(state["campaign"]["max_inquiries"]):
            raise ValueError("the unattended MaxInquiries creation cap is reached")
        for field in expected - {"action"}:
            _nonempty(request, field, f"inquiry {field}")
        next_index = int(state["counters"]["inquiry"]) + 1
        return {
            "action": "open",
            "inquiry": {
                "id": f"I{next_index}",
                "question": request["question"].strip(),
                "goal_connection": request["goal_connection"].strip(),
                "closure_condition": request["closure_condition"].strip(),
                "rationale": request["rationale"].strip(),
                "opened_in_session": session["id"],
                "reframes": [],
            },
        }
    if not isinstance(active, dict):
        raise TypeError("this inquiry operation requires an active inquiry")
    if session["kind"] != "inquiry" or session["inquiry_id"] != active["id"]:
        raise ValueError("inquiry changes require its active inquiry session")
    if action == "reframe":
        expected = {
            "action",
            "question",
            "goal_connection",
            "closure_condition",
            "rationale",
        }
        if set(request) != expected:
            raise ValueError(f"inquiry reframe requires exactly {sorted(expected)}")
        for field in expected - {"action"}:
            _nonempty(request, field, f"inquiry {field}")
        return {
            "action": "reframe",
            "inquiry_id": active["id"],
            "reframe": {
                "question": request["question"].strip(),
                "goal_connection": request["goal_connection"].strip(),
                "closure_condition": request["closure_condition"].strip(),
                "rationale": request["rationale"].strip(),
                "session_id": session["id"],
            },
        }
    if action != "close":
        raise ValueError("inquiry action must be open, reframe, or close")
    if set(request) != {"action", "outcome", "reason"}:
        raise ValueError("inquiry close requires action, outcome, and reason")
    _nonempty(request, "outcome", "inquiry outcome")
    _nonempty(request, "reason", "inquiry close reason")
    return {
        "action": "close",
        "inquiry_id": active["id"],
        "outcome": request["outcome"].strip(),
        "reason": request["reason"].strip(),
    }


def plan_checkpoint(request: dict, state: dict) -> dict:
    session = require_active_session(state)
    expected = repository.CHECKPOINT_FIELDS - {
        "session_id",
        "inquiry_id",
        "scientific_commit",
    }
    if set(request) != expected:
        raise ValueError(f"checkpoint requires exactly {sorted(expected)}")
    for field in expected - {"evidence_references", "completed_operations"}:
        _nonempty(request, field, f"checkpoint {field}")
    evidence = request["evidence_references"]
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) and item.strip() for item in evidence
    ):
        raise ValueError("checkpoint evidence_references must be a list of strings")
    completed_event_ids = {
        event["id"]
        for event in state["operation_events"]
        if event.get("status") == "completed"
    }
    for reference in evidence:
        if reference not in completed_event_ids:
            raise ValueError(
                "checkpoint evidence_references must name operation events "
                f"with status == completed: {reference}"
            )
    completed = request["completed_operations"]
    if completed != session["operation_ids"]:
        raise ValueError(
            "checkpoint completed_operations must exactly match this session"
        )
    return {
        "session_id": session["id"],
        "inquiry_id": session["inquiry_id"],
        **request,
    }


def plan_model_role(request: dict, state: dict) -> dict:
    require_active_session(state)
    action = str(request.get("action", "")).strip()
    allowed = {"action", "candidate", "reason", "evidence"}
    if action == "retain":
        allowed.add("label")
    if set(request) != allowed:
        raise ValueError(
            f"model_role {action or 'operation'} requires {sorted(allowed)}"
        )
    if action not in {"set_working", "set_best_known", "retain"}:
        raise ValueError(
            "model_role action must be set_working, set_best_known, or retain"
        )
    candidate = resolve_candidate(state, _nonempty(request, "candidate", "candidate"))
    _nonempty(request, "reason", "model role reason")
    evidence = request["evidence"]
    completed_event_ids = {
        event["id"]
        for event in state["operation_events"]
        if event.get("status") == "completed"
    }
    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise ValueError("model role evidence must name completed operations")
    if any(item not in completed_event_ids for item in evidence):
        raise ValueError(
            "model role evidence must name operation events with status == completed"
        )
    plan = {
        "action": action,
        "candidate_id": candidate["id"],
        "reason": request["reason"].strip(),
        "evidence": list(evidence),
    }
    if action == "retain":
        label = _nonempty(request, "label", "retained model label")
        if label in {"working", "best_known"}:
            raise ValueError("retained model label conflicts with a fixed role")
        plan["label"] = label
    return plan


def plan_recipe_paths(commit: str) -> dict:
    repository.require_resolvable_commit(commit)
    changed = [
        path
        for path in repository.scientific_delta(commit)
        if is_researcher_owned(path) or path.replace("\\", "/") in PARAMETER_ONLY_PATHS
    ]
    restore: list[str] = []
    remove_created: list[str] = []
    for relative in changed:
        if repository.tracked_at_commit(commit, relative):
            restore.append(relative)
        else:
            remove_created.append(relative)
    return {
        "parent": commit,
        "restore": restore,
        "remove_created": remove_created,
    }


def plan_recipe_restore(request: dict, state: dict) -> dict:
    session = require_active_session(state)
    if set(request) != {"candidate", "reason"}:
        raise ValueError("restore_recipe requires exactly candidate and reason")
    candidate = resolve_candidate(
        state, _nonempty(request, "candidate", "restore candidate")
    )
    _nonempty(request, "reason", "restore reason")
    plan = plan_recipe_paths(candidate["scientific_commit"])
    return {
        **plan,
        "candidate_id": candidate["id"],
        "parameters": candidate["parameters"],
        "session_id": session["id"],
    }


def plan_campaign_conclusion(request: dict, state: dict) -> dict:
    session = require_active_session(state)
    if session["kind"] != "goal_review":
        raise ValueError("campaign conclusion requires a goal-review session")
    if state["active_inquiry"] is not None:
        raise ValueError("close the active inquiry before concluding the campaign")
    if set(request) != {"action", "reason"}:
        raise ValueError("campaign_conclusion requires action and reason")
    action = str(request.get("action", "")).strip()
    if action not in {"request_official_assessment", "no_credible_route"}:
        raise ValueError(
            "campaign conclusion action must be request_official_assessment "
            "or no_credible_route"
        )
    reason = _nonempty(request, "reason", "campaign conclusion reason")
    model = None
    if action == "request_official_assessment":
        model = state["model_roles"]["best_known"]
        if model is None:
            raise ValueError(
                "official assessment requires an explicitly assigned best-known model"
            )
        resolve_candidate(state, model)
    status = (
        "official_assessment_requested"
        if action == "request_official_assessment"
        else action
    )
    return {"status": status, "reason": reason, "model": model}


def _latest_session_event(state: dict, session: dict) -> dict | None:
    operation_ids = session["operation_ids"]
    if not operation_ids:
        return None
    latest_id = operation_ids[-1]
    return next(
        (
            event
            for event in reversed(state["operation_events"])
            if event["id"] == latest_id
        ),
        None,
    )


def _validate_session_operation(
    kind: str,
    request: dict,
    state: dict,
    session: dict,
) -> None:
    session_kind = session["kind"]
    allowed = SESSION_OPERATION_MATRIX[session_kind]
    if kind not in allowed:
        raise ValueError(
            f"{kind} is not available in a {session_kind} scientific session"
        )
    if (
        session_kind == "goal_review"
        and kind == "inquiry"
        and request.get("action") != "open"
    ):
        raise ValueError("goal-review sessions may only open an inquiry")
    if (
        session_kind == "inquiry"
        and kind == "inquiry"
        and request.get("action") not in {"reframe", "close"}
    ):
        raise ValueError("inquiry sessions may only reframe or close their inquiry")
    latest = _latest_session_event(state, session)
    if (
        isinstance(latest, dict)
        and latest["kind"] == "inquiry"
        and latest["result"].get("action") == "reframe"
        and kind != "checkpoint"
    ):
        raise ValueError(
            "a reframed inquiry requires a checkpoint before further operation"
        )


def validate_operation_request(operation: dict, state: dict) -> str:
    if not isinstance(operation, dict):
        raise TypeError("operation request must be an object")
    if state["terminal_state"] is not None:
        raise ValueError("the campaign is terminal")
    pending = state["pending_operation"]
    if isinstance(pending, dict):
        if operation != pending["request"]:
            raise ValueError("a different Runner operation is already pending")
        return str(pending["kind"])
    keys = set(operation)
    if len(keys) != 1 or not keys <= OPERATION_KEYS:
        raise ValueError(
            f"operation request must contain one of {sorted(OPERATION_KEYS)}"
        )
    kind = next(iter(keys))
    request = operation[kind]
    if not isinstance(request, dict):
        raise TypeError(f"{kind} operation must be an object")
    session = require_active_session(state)
    _validate_session_operation(kind, request, state, session)
    if (
        state["active_inquiry"] is None
        and session["kind"] == "inquiry"
        and kind != "checkpoint"
    ):
        raise ValueError("a closed inquiry session must checkpoint before more work")
    if (
        state["active_inquiry"] is not None
        and session["kind"] == "goal_review"
        and kind != "checkpoint"
        and not (kind == "inquiry" and request.get("action") == "open")
    ):
        raise ValueError("an opened inquiry requires a checkpoint and fresh session")
    if kind == "training":
        validate_training_request(request)
        resolved_training_parent(request, state)
    elif kind == "measurement":
        validate_measurement_request(request)
        measurements = planned_measurements(request, state)
        planned_paired_comparisons(request, state, measurements)
    elif kind == "inquiry":
        plan_inquiry_operation(request, state)
    elif kind == "checkpoint":
        plan_checkpoint(request, state)
    elif kind == "model_role":
        plan_model_role(request, state)
    elif kind == "restore_recipe":
        plan_recipe_restore(request, state)
    else:
        plan_campaign_conclusion(request, state)
    return kind


def allocate_operation_id(kind: str, state: dict) -> str:
    if kind == "measurement":
        state["counters"]["measurement"] += 1
        return f"M{state['counters']['measurement']}"
    if kind == "training":
        state["counters"]["training"] += 1
        return f"T{state['counters']['training']}"
    state["counters"]["event"] += 1
    return f"E{state['counters']['event']}"


def is_generated_path(relative_parts: tuple[str, ...]) -> bool:
    *directories, name = relative_parts
    if any(
        part in GENERATED_DIRECTORY_NAMES or part.startswith(".")
        for part in directories
    ):
        return True
    return name.startswith(".") or name.endswith(GENERATED_FILE_SUFFIXES)


def evaluation_semantics_paths() -> list[str]:
    included = [
        relative
        for relative in EVALUATION_RUNTIME_PATHS
        if (paths.ROOT / relative).is_file()
    ]
    root = paths.ROOT / EVALUATION_SEMANTICS_ROOT
    if not root.is_dir():
        return sorted(included)
    for source in root.rglob("*"):
        if not source.is_file() or is_generated_path(source.relative_to(root).parts):
            continue
        relative = source.relative_to(paths.ROOT).as_posix()
        if (
            is_protected_source(relative)
            or relative in PRESENTATION_ONLY_PATHS
            or relative in TRAINING_ONLY_PATHS
            or relative in MODEL_CONTAINED_RUNTIME_PATHS
        ):
            continue
        included.append(relative)
    return sorted(included)


def evaluation_semantics_fingerprint() -> str:
    digest = hashlib.sha256()
    for relative in evaluation_semantics_paths():
        digest.update(relative.encode("utf-8"))
        digest.update((paths.ROOT / relative).read_bytes())
    return digest.hexdigest()[:12]


def evaluation_artifact_name(
    operation_id: str,
    candidate: str,
    episodes: int,
    seed: int,
    semantics: str,
    *,
    campaign_id: str,
) -> str:
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-") or "candidate"
    return (
        f"evaluation-{campaign_id}-{operation_id.lower()}-{label}-"
        f"{episodes}ep-seed{seed}-{semantics}.json"
    )


def task_reference_artifact_name(
    operation_id: str, candidate: str, panel: str, *, campaign_id: str
) -> str:
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-") or "candidate"
    return f"task-reference-{campaign_id}-{operation_id.lower()}-{label}-{panel}.json"
