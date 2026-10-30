"""Strict goal-centered protocol validation for Runner operations."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath

from runner import paths, repository

PROTECTED_BENCHMARK_PATHS = {
    "robot_learning/__init__.py",
    "robot_learning/scenario/__init__.py",
}
PROTECTED_BENCHMARK_PREFIXES = ("benchmark/", "contracts/")
PROTECTED_RUNNER_PATHS = {
    "tools/campaign_report.py",
    "runner/migrate_policy_runtime.py",
    "runner/reset_campaign.py",
    "runner/build_brief.py",
    "runner/query_training_log.py",
    "researcher_session.ps1",
    "run_research.ps1",
    "researcher_mutex.ps1",
}
PROTECTED_RUNTIME_PATHS = {"runner/copilot/copilot_adapter.py"}
PROTECTED_RUNTIME_PREFIXES = ("runner/", "tools/")
PROTECTED_MEASUREMENT_PATHS = {"benchmark/paired_evidence.py"}
PROTECTED_CONTEXT_PATHS = {
    "AGENTS.md",
    "contracts/authority.md",
    "contracts/glossary.md",
    "contracts/instruments.md",
    "contracts/instruments/coding.md",
    "contracts/instruments/inquiry.md",
    "contracts/instruments/measurement.md",
    "contracts/instruments/readers.md",
    "contracts/instruments/scientific-model.md",
    "contracts/instruments/training.md",
    "contracts/program.md",
    "contracts/scenario.md",
}
CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS = {"pi_workspace/scientific_model.md"}
PROTECTED_RUNNER_PREFIXES = ("runner/",)
PROTECTED_TEST_PREFIXES = ("tests/",)
HUMAN_OWNED_PREFIXES = (
    "benchmark/",
    "campaigns/",
    "contracts/",
    "docs/",
    "runner/",
    "tools/",
    *PROTECTED_TEST_PREFIXES,
)
VALIDATED_TEST_PATHS = ("tests/benchmark", "tests/autoresearch")
AUTORESEARCH_BOUNDARY_TEST_PATHS = (
    "tests/autoresearch/test_ownership_registry.py",
    "tests/autoresearch/test_policy_runtime.py",
)
RESEARCHER_VALIDATED_TEST_PATHS = (*AUTORESEARCH_BOUNDARY_TEST_PATHS,)
RESEARCHER_OWNED_PREFIXES = (
    "robot_learning/scenario/",
    "robot_learning/training/",
    "robot_learning/lab/",
)
CAMPAIGN_LAB_PREFIXES = ("robot_learning/lab/",)
RESEARCHER_OWNED_PATHS = {
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
}
PARAMETER_ONLY_PATHS = {"robot_learning/training/current_params.json"}
DEPENDENCY_METADATA_PATHS = {"pyproject.toml", "uv.lock"}
EVALUATION_SEMANTICS_ROOT = "robot_learning/scenario"
PRESENTATION_ONLY_PATHS = {
    "robot_learning/scenario/progress.py",
    "robot_learning/scenario/viewer.py",
}
TRAINING_ONLY_PATHS = {
    "robot_learning/training/reward.py",
    "robot_learning/training/environment.py",
}
MODEL_CONTAINED_RUNTIME_PATHS = {
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/policy_io.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
}
EVALUATION_RUNTIME_PATHS = (
    "contracts/policy_runtime.py",
    "robot_learning/evaluate.py",
    "contracts/task_spec.py",
    "benchmark/metrics.py",
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
    "inputs",
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
    "recipe_development": {*SCIENTIFIC_OPERATION_KINDS, "checkpoint"},
    "startup": {*SCIENTIFIC_OPERATION_KINDS, "checkpoint"},
    "goal_review": {
        "measurement",
        "model_role",
        "inquiry",
        "campaign_conclusion",
        "checkpoint",
    },
    "inquiry": {*SCIENTIFIC_OPERATION_KINDS, "inquiry", "checkpoint"},
}
TRUSTED_RUNTIME_PATHS = {
    "robot_learning/__init__.py",
    "contracts/policy_runtime.py",
    "contracts/robots/__init__.py",
    "contracts/robots/robot.py",
    "contracts/robots/robot.xml",
    "robot_learning/scenario/__init__.py",
}
TASK_REFERENCE_ADAPTER_PATH = "benchmark/adapters/task_reference.py"
OFFICIAL_ASSESSMENT_ADAPTER_PATH = "benchmark/adapters/final_benchmark.py"


def _scientific_base_path(path: str) -> str | None:
    relative = path.replace("\\", "/")
    parts = relative.split("/")
    if (
        PureWindowsPath(relative).drive
        or ":" in relative
        or any(part in {"", ".", ".."} for part in parts)
    ):
        return None
    if [part.casefold() for part in parts[:2]] == ["robot_learning", "variants"]:
        if len(parts) < 4 or not TRAINING_VARIANT_LABEL.fullmatch(parts[2]):
            return None
        return "/".join(("robot_learning", *parts[3:])).casefold()
    return relative.casefold()


def is_protected_source(path: str) -> bool:
    relative = _scientific_base_path(path)
    if relative is None:
        return True
    return any(
        relative == protected.casefold()
        for protected in (
            *PROTECTED_BENCHMARK_PATHS,
            *PROTECTED_RUNNER_PATHS,
            *PROTECTED_RUNTIME_PATHS,
            *PROTECTED_MEASUREMENT_PATHS,
            *PROTECTED_CONTEXT_PATHS,
            *CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS,
            *DEPENDENCY_METADATA_PATHS,
        )
    ) or relative.startswith(
        tuple(
            prefix.casefold()
            for prefix in (
                *PROTECTED_BENCHMARK_PREFIXES,
                *PROTECTED_RUNNER_PREFIXES,
                *PROTECTED_RUNTIME_PREFIXES,
            )
        )
    )


def is_human_owned(path: str) -> bool:
    relative = path.replace("\\", "/")
    return is_protected_source(relative) or relative.startswith(HUMAN_OWNED_PREFIXES)


def is_researcher_owned(path: str) -> bool:
    relative = _scientific_base_path(path)
    if relative is None or relative.startswith("robot_learning/variants/"):
        return False
    if is_human_owned(relative):
        return False
    return (
        relative in RESEARCHER_OWNED_PATHS
        or relative.startswith(RESEARCHER_OWNED_PREFIXES)
        or relative.startswith(CAMPAIGN_LAB_PREFIXES)
        or relative == "pi_workspace/operation_request.json"
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
    missing = [
        relative
        for relative in declared
        if not (base / relative if root else paths.locate(relative)).is_file()
    ]
    missing.extend(
        prefix
        for prefix in PROTECTED_BENCHMARK_PREFIXES
        if not (base / prefix if root else paths.locate(prefix)).is_dir()
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
    harness_changed = []
    if paths.SPLIT:
        harness_changed = sorted(
            path
            for path in repository.status_paths((".",), harness=True)
            if paths.is_harness_runtime(path)
            and is_human_owned(path)
            and not repository.is_runner_owned(path)
        )
    rejected = sorted(
        path
        for path in changed
        if is_human_owned(path) and not repository.is_runner_owned(path)
    )
    problems = []
    if harness_changed:
        print(
            f"Harness runtime files have uncommitted changes: {harness_changed}",
            file=sys.stderr,
        )
        problems.append(
            "the Runner files contain uncommitted changes that you cannot restore"
        )
    if rejected:
        problems.append(
            f"protected or human-owned campaign files have uncommitted changes: "
            f"{rejected}; restore them"
        )
    if problems:
        raise ValueError(
            "; ".join(problems) + ". A research evaluation, a task-reference "
            "evaluation or the official assessment cannot run until these files "
            "are restored"
        )


def require_trusted_assessment_runtime(adapter_path: str) -> None:
    validate_clean_human_owned_worktree()
    trusted = [
        *TRUSTED_RUNTIME_PATHS,
        adapter_path,
        *repository.tracked_paths("benchmark"),
        *repository.tracked_paths("contracts"),
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
        raise TypeError("this operation requires an active session")
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
        raise KeyError(f"unknown candidate {identifier!r}")
    artifact = repository.resolve_repo_path(candidate["artifact"])
    repository.require_complete_inference_artifact(
        artifact, f"candidate {identifier!r}"
    )
    if repository.artifact_fingerprint(artifact) != candidate["fingerprint"]:
        raise ValueError(f"candidate {identifier!r} fingerprint changed")
    return candidate


def validate_training_request(request: dict) -> None:
    required = {"initialization", "seed", "steps", "description", "rationale"}
    allowed = {*required, "parent", "variants"}
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
    if initialization == "fresh" and "parent" in request:
        raise ValueError("fresh training must not declare a parent")
    if "variants" in request:
        _validate_training_variants(request["variants"])
    if initialization == "transfer" and (
        "parent" in request or "variants" not in request
    ):
        _nonempty(request, "parent", "transfer training parent")
    for variant in request.get("variants", []):
        if initialization == "fresh" and "parent" in variant:
            raise ValueError("fresh training variants must not declare a parent")
        if "parent" in variant:
            _nonempty(variant, "parent", "transfer training variant parent")
        elif initialization == "transfer" and "parent" not in request:
            raise ValueError("each transfer training variant requires a parent")


TRAINING_VARIANT_LABEL = re.compile(r"[a-z][a-z0-9_]{0,15}")
MIN_TRAINING_VARIANTS = 2
MAX_TRAINING_VARIANTS = 4


def _validate_training_variants(variants: object) -> None:
    if not isinstance(variants, list) or not (
        MIN_TRAINING_VARIANTS <= len(variants) <= MAX_TRAINING_VARIANTS
    ):
        raise ValueError(
            f"training variants must be a list of {MIN_TRAINING_VARIANTS} to "
            f"{MAX_TRAINING_VARIANTS} variants"
        )
    labels: set[str] = set()
    for variant in variants:
        if (
            not isinstance(variant, dict)
            or "label" not in variant
            or not set(variant) <= {"label", "parameters", "parent"}
        ):
            raise ValueError(
                "each training variant requires label and allows parameters and parent"
            )
        label = variant["label"]
        if not isinstance(label, str) or not TRAINING_VARIANT_LABEL.fullmatch(label):
            raise ValueError(
                "a training variant label must start with a lowercase letter and "
                "contain only lowercase letters, digits and underscores, at most "
                "16 characters"
            )
        if label in labels:
            raise ValueError(f"training variant label {label!r} is not unique")
        labels.add(label)
        if not isinstance(variant.get("parameters", {}), dict):
            raise TypeError("training variant parameters must be an object")


def resolved_training_parent(request: dict, state: dict) -> dict | None:
    if request["initialization"] == "fresh" or "parent" not in request:
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
            if not module.startswith(
                (
                    "robot_learning.lab.",
                    "robot_learning.scenario.",
                    "robot_learning.training.",
                )
            ):
                raise ValueError(
                    "python_module must be under robot_learning.lab, "
                    "robot_learning.scenario, or robot_learning.training"
                )
            arguments = entry.get("args")
            if not isinstance(arguments, list) or not all(
                isinstance(item, str) for item in arguments
            ):
                raise TypeError("python_module args must be a list of strings")
            validate_measurement_inputs(entry)
            artifact = repository.canonical_repo_path(
                _nonempty(entry, "artifact", "python_module artifact")
            )
            evaluation_prefix = (
                repository.repo_relative_path(paths.EVALUATION_DIR) + "/"
            )
            if not artifact.startswith(evaluation_prefix):
                raise ValueError(
                    f"python_module artifact must be under {evaluation_prefix.rstrip('/')}"
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


def validate_measurement_inputs(entry: dict) -> None:
    from runner.artifact_evidence_query import ArtifactReference

    inputs = entry.get("inputs", {})
    if not isinstance(inputs, dict):
        raise TypeError("python_module inputs must be a named reference object")
    for name, reference in inputs.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError("python_module input names must be identifiers")
        if isinstance(reference, dict) and set(reference) == {"candidate"}:
            _nonempty(reference, "candidate", f"python_module input '{name}' candidate")
        else:
            ArtifactReference.model_validate(reference)
    used_inputs = set()
    for argument in entry["args"]:
        matches = list(re.finditer(r"\{input:([^{}]+)\}", argument))
        remainder = re.sub(r"\{input:([^{}]+)\}", "", argument)
        if "{input:" in remainder:
            raise ValueError("Malformed python_module input placeholder")
        used_inputs.update(match[1] for match in matches)
    if used_inputs != set(inputs):
        raise ValueError(
            "python_module input placeholders must match declared inputs: "
            f"undeclared={sorted(used_inputs - set(inputs))}, "
            f"unused={sorted(set(inputs) - used_inputs)}"
        )


def planned_measurements(request: dict, state: dict) -> list[dict]:
    validate_measurement_request(request)
    planned: list[dict] = []
    panels: dict[tuple, int] = {}
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
                    "python_module artifact must be scoped to the current campaign "
                    f"and start with {campaign_prefix}"
                )
            spec = {
                **entry,
                "artifact": artifact,
                "label": str(entry.get("label") or f"measurement {index}").strip(),
            }
            if "inputs" in entry:
                spec["input_artifacts"] = resolved_measurement_inputs(entry, state)
                for name, binding in spec["input_artifacts"].items():
                    if binding["artifact_path"] == artifact:
                        raise ValueError(
                            f"python_module output artifact would overwrite input '{name}'"
                        )
                spec["args"] = [
                    re.sub(
                        r"\{input:([^{}]+)\}",
                        lambda match, inputs=spec["input_artifacts"]: inputs[match[1]][
                            "artifact_path"
                        ],
                        argument,
                    )
                    for argument in entry["args"]
                ]
            planned.append(spec)
            continue
        candidate_name = str(entry["candidate"]).strip()
        candidate = resolve_candidate(state, candidate_name)
        panel = (
            entry["instrument"],
            candidate["id"],
            entry.get("seed"),
            entry.get("episodes"),
        )
        if panel in panels:
            raise ValueError(
                f"measurement {index} repeats measurement {panels[panel]}: "
                f"{entry['instrument']} of {candidate['id']}"
                + (
                    f" with seed {entry['seed']} and {entry['episodes']} episodes"
                    if entry["instrument"] == "research_evaluation"
                    else ""
                )
                + "; each panel may appear once per request"
            )
        panels[panel] = index
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


def resolved_measurement_inputs(spec: dict, state: dict) -> dict:
    from runner.artifact_evidence_query import (
        ArtifactUnavailableError,
        FingerprintMismatchError,
        resolve_artifact_reference,
    )

    resolved = {}
    for name, reference in spec.get("inputs", {}).items():
        try:
            if set(reference) == {"candidate"}:
                candidate = resolve_candidate(state, str(reference["candidate"]))
                resolved[name] = {
                    "candidate": candidate["id"],
                    "artifact_path": f"{candidate['artifact']}/model.zip",
                    "model_fingerprint": candidate["fingerprint"],
                }
            else:
                resolved[name] = resolve_artifact_reference(state, reference)
        except (
            ArtifactUnavailableError,
            FingerprintMismatchError,
            KeyError,
            OSError,
            ValueError,
        ) as error:
            raise ValueError(
                f"python_module input '{name}' could not be resolved: {error}"
            ) from error
    return resolved


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
        if candidate["id"] not in research_measurements:
            raise ValueError(
                f"paired comparison candidate {candidate['id']!r} must have a "
                "planned research_evaluation measurement"
            )
        candidate_episodes = {
            seed
            for _, entry in research_measurements[candidate["id"]]
            for seed in range(
                int(entry["seed"]), int(entry["seed"]) + int(entry["episodes"])
            )
        }
        stored: list[dict] = []
        if reference["id"] in research_measurements:
            reference_episodes = {
                seed
                for _, entry in research_measurements[reference["id"]]
                for seed in range(
                    int(entry["seed"]), int(entry["seed"]) + int(entry["episodes"])
                )
            }
        else:
            stored, reference_episodes = _stored_reference_measurements(
                state, reference, candidate_episodes
            )
            if not stored:
                raise ValueError(
                    f"paired comparison reference {reference['id']!r} must have a "
                    "planned research_evaluation measurement or an earlier completed "
                    "research_evaluation of the same candidate with the same "
                    "fingerprint on shared episode seeds under the current "
                    "evaluation semantics"
                )
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
            for index, entry in research_measurements.get(reference["id"], [])
            if shared.intersection(
                range(
                    int(entry["seed"]),
                    int(entry["seed"]) + int(entry["episodes"]),
                )
            )
        ]
        plan = {
            "candidate": candidate["id"],
            "reference": reference["id"],
            "candidate_model_fingerprint": candidate["fingerprint"],
            "reference_model_fingerprint": reference["fingerprint"],
            "shared_episode_seeds": shared_episode_seeds,
            "candidate_measurement_indexes": candidate_measurement_indexes,
            "reference_measurement_indexes": reference_measurement_indexes,
        }
        if stored:
            plan[STORED_REFERENCE_FIELD] = stored
        planned.append(plan)
    return planned


STORED_REFERENCE_FIELD = "reference_stored_measurements"
STORED_MEASUREMENT_FIELDS = (
    "evaluation_artifact",
    "evaluation_artifact_fingerprint",
    "evaluation_semantics",
    "model_fingerprint",
    "seed",
    "episodes",
)


def _stored_reference_measurements(
    state: dict, reference: dict, seeds: set[int]
) -> tuple[list[dict], set[int]]:
    """Earlier research evaluations of the same saved artifact covering `seeds`."""
    semantics = evaluation_semantics_fingerprint()
    stored: list[dict] = []
    covered: set[int] = set()
    for event in state.get("operation_events", []):
        if event.get("kind") != "measurement" or event.get("status") != "completed":
            continue
        for item in (event.get("result") or {}).get("measurements", []):
            metrics = item.get("metrics") or {}
            if (
                item.get("instrument") != "research_evaluation"
                or item.get("candidate_id") != reference["id"]
                or metrics.get("model_fingerprint") != reference["fingerprint"]
                or metrics.get("evaluation_semantics") != semantics
            ):
                continue
            panel = set(
                range(
                    int(metrics["seed"]),
                    int(metrics["seed"]) + int(metrics["episodes"]),
                )
            )
            new = (panel & seeds) - covered
            if new:
                stored.append(
                    {
                        "operation_id": event["id"],
                        "metrics": {
                            field: metrics[field] for field in STORED_MEASUREMENT_FIELDS
                        },
                    }
                )
                covered |= new
    return stored, covered


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
            raise ValueError("inquiry open is not available in this session")
        for field in expected - {"action"}:
            _nonempty(request, field, f"inquiry {field}")
        checkpoint = state.get("pi_checkpoint")
        if not isinstance(checkpoint, dict):
            raise ValueError(
                "inquiry open requires the session record of the previous session"
            )
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
                "handoff_conclusion": checkpoint["current_synthesis"],
                "handoff_question": request["question"].strip(),
                "handoff_source_session_id": checkpoint["session_id"],
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
    if session["kind"] == "goal_review":
        active = state["active_inquiry"]
        if (
            not isinstance(active, dict)
            or active.get("opened_in_session") != session["id"]
        ):
            raise ValueError(
                "the checkpoint operation of a goal-review session requires an "
                "inquiry opened in this session"
            )
    expected = repository.CHECKPOINT_FIELDS - {
        "session_id",
        "inquiry_id",
        "scientific_commit",
    }
    if set(request) != expected:
        raise ValueError(f"checkpoint requires exactly {sorted(expected)}")
    for field in expected - {"evidence_references", "completed_operations"}:
        _nonempty(request, field, f"checkpoint {field}")
    if (
        session["kind"] == "goal_review"
        and request["next_question"].strip() != state["active_inquiry"]["question"]
    ):
        raise ValueError(
            "in a goal-review session, checkpoint next_question must match the "
            "question of the opened inquiry"
        )
    if (
        session["kind"] == "inquiry"
        and isinstance(state["active_inquiry"], dict)
        and request["next_question"].strip() != state["active_inquiry"]["question"]
    ):
        raise ValueError(
            "in an inquiry session with an active inquiry, checkpoint next_question "
            "must match the question of the active inquiry"
        )
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
            f"checkpoint completed_operations mismatch in session {session['id']}. "
            f"Expected {json.dumps(session['operation_ids'])}. "
            f"Submitted {json.dumps(completed)}. "
            "The session remains active until the Runner accepts its checkpoint "
            "operation."
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
    _nonempty(request, "reason", "model_role reason")
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
        raise ValueError("model_role evidence must name completed operations")
    if any(item not in completed_event_ids for item in evidence):
        raise ValueError(
            "model_role evidence must name operation events with status == completed"
        )
    plan = {
        "action": action,
        "candidate_id": candidate["id"],
        "reason": request["reason"].strip(),
        "evidence": list(evidence),
    }
    if action == "retain":
        label = _nonempty(request, "label", "retained role label")
        if label in {"working", "best_known"}:
            raise ValueError("retained role label conflicts with a fixed role")
        plan["label"] = label
    return plan


def plan_recipe_paths(commit: str, selected_paths: list[str] | None = None) -> dict:
    repository.require_resolvable_commit(commit)
    changed = (
        selected_paths
        if selected_paths is not None
        else [
            path
            for path in repository.scientific_delta(commit)
            if is_researcher_owned(path)
            or path.replace("\\", "/") in PARAMETER_ONLY_PATHS
        ]
    )
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
    if set(request) != {"candidate", "reason", "paths"}:
        raise ValueError(
            "restore_recipe requires candidate, reason and explicit paths; "
            "unselected measurement sources are preserved"
        )
    candidate = resolve_candidate(
        state, _nonempty(request, "candidate", "restore candidate")
    )
    _nonempty(request, "reason", "restore reason")
    requested_paths = request["paths"]
    if not isinstance(requested_paths, list) or not requested_paths:
        raise ValueError("restore_recipe paths must be a nonempty exact-file list")
    selected = []
    for path in requested_paths:
        if not isinstance(path, str):
            raise TypeError("restore_recipe paths must be strings")
        relative = repository.canonical_repo_path(path)
        if (
            not is_researcher_owned(relative)
            or is_campaign_lab(relative)
            or relative == "pi_workspace/operation_request.json"
        ):
            raise ValueError(
                f"restore_recipe path is not a learning-recipe source: {relative}"
            )
        current = repository.resolve_repo_path(relative)
        historical = repository.tracked_at_commit(
            candidate["scientific_commit"], relative
        )
        if current.is_dir() or (not historical and not current.is_file()):
            raise ValueError(
                f"restore_recipe requires an existing or recorded file: {relative}"
            )
        if relative in selected:
            raise ValueError(f"restore_recipe paths contains duplicate: {relative}")
        selected.append(relative)
    if "robot_learning/training/current_params.json" not in selected:
        raise ValueError(
            "restore_recipe paths must include robot_learning/training/current_params.json "
            "to restore the candidate's recorded parameters"
        )
    plan = plan_recipe_paths(candidate["scientific_commit"], selected)
    return {
        **plan,
        "candidate_id": candidate["id"],
        "parameters": candidate["parameters"],
        "session_id": session["id"],
    }


def plan_campaign_conclusion(request: dict, state: dict) -> dict:
    session = require_active_session(state)
    if session["kind"] != "goal_review":
        raise ValueError("campaign_conclusion requires a goal-review session")
    if state["active_inquiry"] is not None:
        raise ValueError("close the active inquiry before concluding the campaign")
    if set(request) != {"action", "reason"}:
        raise ValueError("campaign_conclusion requires action and reason")
    action = str(request.get("action", "")).strip()
    if action != "request_official_assessment":
        raise ValueError(
            "campaign_conclusion action must be request_official_assessment"
        )
    reason = _nonempty(request, "reason", "campaign_conclusion reason")
    model = state["model_roles"]["best_known"]
    if model is None:
        raise ValueError(
            "official assessment requires an explicitly assigned best-known candidate"
        )
    resolve_candidate(state, model)
    return {"status": "official_assessment_requested", "reason": reason, "model": model}


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


def session_operation_availability(state: dict) -> dict:
    session = state.get("scientific_session")
    result = {
        "allowed_operations": [],
        "checkpoint_required": False,
        "checkpoint_reason": None,
        "next_question": None,
    }
    if not isinstance(session, dict) or state.get("terminal_state"):
        return result
    pending = state.get("pending_operation")
    if isinstance(pending, dict) and (
        not pending.get("failure")
        or pending["progress"] in {"result_ready", "completed"}
    ):
        return result
    active = state.get("active_inquiry")
    allowed = set(SESSION_OPERATION_MATRIX[session["kind"]])
    latest = _latest_session_event(state, session)
    reason = None
    if session["kind"] == "goal_review":
        if isinstance(active, dict) and active["opened_in_session"] == session["id"]:
            reason = (
                f"Inquiry {active['id']} was opened. Submit the checkpoint "
                "operation for this goal-review session."
            )
        else:
            allowed.discard("checkpoint")
    elif session["kind"] == "inquiry":
        if active is None:
            reason = (
                "The inquiry is closed. Submit the checkpoint operation for this "
                "inquiry session."
            )
        elif (
            isinstance(latest, dict)
            and latest["kind"] == "inquiry"
            and latest["result"].get("action") == "reframe"
        ):
            reason = (
                f"Inquiry {active['id']} was reframed. Submit the checkpoint "
                "operation for this inquiry session."
            )
    if reason:
        allowed = {"checkpoint"}
        result.update(
            checkpoint_required=True,
            checkpoint_reason=reason,
            next_question=active["question"] if isinstance(active, dict) else None,
        )
    result["allowed_operations"] = sorted(allowed)
    return result


def _validate_session_operation(
    kind: str,
    request: dict,
    state: dict,
    session: dict,
) -> None:
    session_kind = session["kind"]
    availability = session_operation_availability(state)
    allowed = availability["allowed_operations"]
    if kind not in allowed:
        if availability["checkpoint_required"]:
            raise ValueError(
                "the current session requires a checkpoint operation before any "
                "other operation. " + availability["checkpoint_reason"]
            )
        if kind == "checkpoint" and session_kind == "goal_review" and allowed:
            raise ValueError(
                "the checkpoint operation of a goal-review session requires an "
                "inquiry opened in this session"
            )
        raise ValueError(
            f"{kind} is not available in the current {session_kind} session"
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


def operation_envelope_schema() -> dict:
    return {
        "oneOf": [
            {
                "type": "object",
                "properties": {kind: operation_body_schema(kind)},
                "required": [kind],
                "additionalProperties": False,
            }
            for kind in sorted(OPERATION_KEYS)
        ]
    }


def operation_body_schema(kind: str) -> dict:
    text = {"type": "string", "minLength": 1}
    strings = {"type": "array", "items": text}

    def body(properties: dict, optional: tuple[str, ...] = ()) -> dict:
        return {
            "type": "object",
            "properties": properties,
            "required": sorted(set(properties) - set(optional)),
            "additionalProperties": False,
        }

    if kind == "training":
        common: dict = {
            "seed": {"type": "integer", "minimum": 0},
            "steps": {"type": "integer", "minimum": 1},
            "description": text,
            "rationale": text,
            "variants": {
                "type": "array",
                "minItems": MIN_TRAINING_VARIANTS,
                "maxItems": MAX_TRAINING_VARIANTS,
                "items": body(
                    {
                        "label": {
                            "type": "string",
                            "pattern": f"^{TRAINING_VARIANT_LABEL.pattern}$",
                        },
                        "parameters": {"type": "object"},
                    },
                    optional=("parameters",),
                ),
            },
        }
        schema = {
            "oneOf": [
                body(
                    {**common, "initialization": {"const": "fresh", "type": "string"}},
                    optional=("variants",),
                ),
                body(
                    {
                        **common,
                        "variants": {
                            **common["variants"],
                            "items": body(
                                {
                                    **common["variants"]["items"]["properties"],
                                    "parent": text,
                                },
                                optional=("parameters", "parent"),
                            ),
                        },
                        "initialization": {"const": "transfer", "type": "string"},
                        "parent": text,
                    },
                    optional=("variants", "parent"),
                ),
            ]
        }
        schema["oneOf"][1]["anyOf"] = [
            {"required": ["parent"]},
            {
                "required": ["variants"],
                "properties": {"variants": {"items": {"required": ["parent"]}}},
            },
        ]
        return schema
    if kind == "measurement":
        entries = [
            body(
                {
                    "instrument": {"const": "research_evaluation", "type": "string"},
                    "candidate": text,
                    "episodes": {"type": "integer", "minimum": 1},
                    "seed": {"type": "integer", "minimum": 0},
                    "label": {"type": "string"},
                },
                ("label",),
            ),
            body(
                {
                    "instrument": {"const": "task_reference", "type": "string"},
                    "candidate": text,
                    "label": {"type": "string"},
                },
                ("label",),
            ),
            body(
                {
                    "instrument": {"const": "python_module", "type": "string"},
                    "module": text,
                    "args": {
                        "type": "array",
                        "description": (
                            "One string per literal module argument. Do not include "
                            "the module name or a command prefix such as `python -m`. "
                            "Use concrete output paths."
                        ),
                        "items": {"type": "string"},
                    },
                    "artifact": text,
                    "label": {"type": "string"},
                    "inputs": {
                        "type": "object",
                        "additionalProperties": {
                            "oneOf": [
                                body(
                                    {
                                        "operation_id": text,
                                        "artifact_index": {
                                            "type": "integer",
                                            "minimum": 0,
                                        },
                                    }
                                ),
                                body({"candidate": text}),
                            ]
                        },
                    },
                },
                ("label", "inputs"),
            ),
        ]
        return body(
            {
                "description": text,
                "rationale": text,
                "measurements": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"oneOf": entries},
                },
                "paired_comparisons": {
                    "type": "array",
                    "items": body({"candidate": text, "reference": text}),
                },
            },
            ("paired_comparisons",),
        )
    if kind == "inquiry":
        common = {
            "question": text,
            "goal_connection": text,
            "closure_condition": text,
            "rationale": text,
        }
        return {
            "oneOf": [
                body({**common, "action": {"const": action, "type": "string"}})
                for action in ("open", "reframe")
            ]
            + [
                body(
                    {
                        "action": {"const": "close", "type": "string"},
                        "outcome": text,
                        "reason": text,
                    }
                )
            ]
        }
    if kind == "checkpoint":
        fields = repository.CHECKPOINT_FIELDS - {
            "session_id",
            "inquiry_id",
            "scientific_commit",
        }
        return body(
            {
                field: strings
                if field in {"evidence_references", "completed_operations"}
                else text
                for field in sorted(fields)
            }
        )
    if kind == "model_role":
        common = {
            "candidate": text,
            "reason": text,
            "evidence": {**strings, "minItems": 1},
        }
        return {
            "oneOf": [
                body({**common, "action": {"const": action, "type": "string"}})
                for action in ("set_working", "set_best_known")
            ]
            + [
                body(
                    {
                        **common,
                        "action": {"const": "retain", "type": "string"},
                        "label": text,
                    }
                )
            ]
        }
    if kind == "restore_recipe":
        return body(
            {
                "candidate": text,
                "reason": text,
                "paths": {**strings, "minItems": 1},
            }
        )
    if kind == "campaign_conclusion":
        return body(
            {
                "action": {"const": "request_official_assessment", "type": "string"},
                "reason": text,
            }
        )
    raise ValueError(f"unknown operation kind {kind!r}")


def validate_operation_shape(kind: str, request: object) -> None:
    """Check request structure without resolving state or executing a planner."""
    schema = operation_body_schema(kind)

    def variant(spec: dict, record: dict, selector: str) -> dict:
        if "oneOf" not in spec:
            return spec
        selected = next(
            (
                item
                for item in spec["oneOf"]
                if item["properties"][selector]["const"] == record.get(selector)
            ),
            None,
        )
        if selected is None:
            raise ValueError(f"{kind} {selector} is invalid: {record.get(selector)!r}")
        return selected

    def fields(record: object, spec: dict, description: str) -> None:
        if not isinstance(record, dict):
            raise TypeError(f"{description} must be an object")
        missing = set(spec["required"]) - set(record)
        extra = set(record) - set(spec["properties"])
        if missing or extra:
            raise ValueError(
                f"{description} fields are invalid: "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        for name, value in record.items():
            field = spec["properties"][name]
            expected = field["type"]
            if expected == "string":
                if "minLength" in field:
                    _nonempty(record, name, f"{description} {name}")
                elif not isinstance(value, str):
                    raise TypeError(f"{description} {name} must be a string")
                if "const" in field and value != field["const"]:
                    raise ValueError(f"{description} {name} must be {field['const']!r}")
            elif expected == "integer":
                _integer(
                    record, name, f"{description} {name}", minimum=field["minimum"]
                )
            elif expected == "object" and not isinstance(value, dict):
                raise TypeError(f"{description} {name} must be an object")
            elif expected == "array":
                if not isinstance(value, list):
                    raise TypeError(f"{description} {name} must be a list")
                if len(value) < field.get("minItems", 0):
                    raise ValueError(f"{description} {name} must not be empty")
                if field["items"].get("type") == "string" and any(
                    not isinstance(item, str)
                    or ("minLength" in field["items"] and not item.strip())
                    for item in value
                ):
                    raise TypeError(f"{description} {name} must be a list of strings")

    if not isinstance(request, dict):
        raise TypeError(f"{kind} request must be an object")
    selector = "initialization" if kind == "training" else "action"
    schema = variant(schema, request, selector)
    fields(request, schema, f"{kind} request")
    if kind == "training":
        validate_training_request(request)
    if kind != "measurement":
        return
    entry_schema = schema["properties"]["measurements"]["items"]
    for index, entry in enumerate(request["measurements"]):
        if not isinstance(entry, dict):
            raise TypeError(f"measurement {index} must be an object")
        fields(
            entry, variant(entry_schema, entry, "instrument"), f"measurement {index}"
        )
        if entry["instrument"] == "python_module":
            validate_measurement_inputs(entry)
    comparison_schema = schema["properties"]["paired_comparisons"]["items"]
    for index, comparison in enumerate(request.get("paired_comparisons", [])):
        fields(comparison, comparison_schema, f"paired comparison {index}")


def validate_operation_submission(operation: dict) -> str:
    kind = validate_operation_envelope(operation)
    validate_operation_shape(kind, operation[kind])
    if kind == "measurement":
        for index, entry in enumerate(operation[kind]["measurements"]):
            if entry["instrument"] == "python_module" and any(
                "{artifact}" in argument for argument in entry["args"]
            ):
                raise ValueError(
                    f"measurement {index} args contains unresolved '{{artifact}}'; "
                    "supply the concrete output path in the module arguments"
                )
    return kind


def validate_operation_envelope(operation: dict) -> str:
    if not isinstance(operation, dict):
        raise TypeError("operation request must be an object")
    keys = set(operation)
    wrappers = keys & OPERATION_KEYS
    if not wrappers:
        intended = operation.get("kind")
        hint = (
            f"Put the operation body inside '{intended}', not a 'kind' field."
            if isinstance(intended, str) and intended in OPERATION_KEYS
            else "Put the operation body inside one operation-named object."
        )
        raise ValueError(
            "Missing operation wrapper. "
            f"{hint} Allowed wrappers: {sorted(OPERATION_KEYS)}. "
            f"Received top-level fields: {sorted(map(str, keys))}."
        )
    if len(wrappers) != 1:
        raise ValueError(
            "An operation request must contain exactly one wrapper; "
            f"received {sorted(wrappers)}."
        )
    kind = next(iter(wrappers))
    if extra := keys - wrappers:
        raise ValueError(
            f"Unexpected top-level fields: {sorted(map(str, extra))}. "
            f"Keep only '{kind}' at the top level; put its body fields inside it."
        )
    if not isinstance(operation[kind], dict):
        raise TypeError(f"'{kind}' operation body must be an object")
    return kind


def validate_operation_request(operation: dict, state: dict) -> str:
    if not isinstance(operation, dict):
        raise TypeError("operation request must be an object")
    if state["terminal_state"] is not None:
        raise ValueError("the campaign is terminal")
    kind = validate_operation_submission(operation)
    pending = state["pending_operation"]
    if isinstance(pending, dict):
        if operation != pending["request"]:
            raise ValueError("a different Runner operation is already pending")
        return str(pending["kind"])
    request = operation[kind]
    session = require_active_session(state)
    _validate_session_operation(kind, request, state, session)
    if (
        state["active_inquiry"] is None
        and session["kind"] == "inquiry"
        and kind != "checkpoint"
    ):
        raise ValueError(
            "an inquiry session whose inquiry is closed requires a checkpoint "
            "operation before any other operation"
        )
    if (
        state["active_inquiry"] is not None
        and session["kind"] == "goal_review"
        and kind != "checkpoint"
        and not (kind == "inquiry" and request.get("action") == "open")
    ):
        raise ValueError(
            "an opened inquiry requires a checkpoint operation and a new session"
        )
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
        if paths.locate(relative).is_file()
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
        digest.update(paths.locate(relative).read_bytes())
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
