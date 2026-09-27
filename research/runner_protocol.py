"""Protocol decisions and validation for the Runner.

Everything here answers "is this admissible, and what would it mean?" without
performing the destructive part of the answer. The `plan_*` operations resolve
a complete decision that `run_experiment` and `runner_repository` then apply.
"""

import copy
import hashlib
import json
import re
from pathlib import Path

from research import runner_console as console
from research import runner_paths as paths
from research import runner_repository as repository

# Human-owned for the duration of this research problem: the enforcement
# mechanism, every file that can declare the objective reached, the human-owned
# task-reference panel, the official robot they measure, and the package files
# that resolve those imports.
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
# The whole benchmark package is human-owned: the task contract, the immutable
# constants that define the development evaluation and its frozen metrics.
# Protected by prefix so that adding a file under it never silently hands part of
# the task definition to the researcher.
PROTECTED_BENCHMARK_PREFIXES = ("robot_learning/benchmark/",)
# Additional Runner instruments are protected even when they do not belong to
# the official-task trust path.
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
# The researcher runtime boundary: it decides which tools and commands a
# research session may use, so a proposal must not be able to widen its own.
PROTECTED_RUNTIME_PATHS = {"researcher_copilot.py"}
# The optional OpenCode runtime is the same boundary expressed in another
# language. Protected by prefix so that adding a module, a manifest or a lockfile
# under it never silently hands part of the tool boundary to the researcher.
PROTECTED_RUNTIME_PREFIXES = ("researcher_opencode/",)
# Measurement-accounting invariants shared by the Runner and the research
# evaluator. Deterministic episode identity and conflict rejection are
# correctness properties, not scientific choices, so restoring a research recipe
# must never be able to revert them (issue #35).
PROTECTED_MEASUREMENT_PATHS = {
    "robot_learning/paired_evidence.py",
}
# Human-owned context defines the Researcher's protocol, permissions and task.
PROTECTED_CONTEXT_PATHS = {
    "AGENTS.md",
    "research/instruments.md",
    "research/program.md",
    "research/scenario.md",
}
# Produced at campaign start, so absent from the repository before the first campaign.
CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS = {
    "research/scientific_model.md",
}
# The rest of the enforcement mechanism, protected by prefix so that adding a
# Runner module never silently hands part of the protocol to the researcher.
PROTECTED_RUNNER_PREFIXES = ("research/runner_",)
# No test path belongs to the researcher's write surface. The whole tests/ tree
# is prefix-protected, so creating, renaming or deleting any test file -- in a
# human-owned domain or a retired researcher-test location -- is rejected.
PROTECTED_TEST_PREFIXES = ("tests/",)
VALIDATED_TEST_PATHS = (
    "tests/benchmark",
    "tests/autoresearch",
)
AUTORESEARCH_BOUNDARY_TEST_PATHS = (
    "tests/autoresearch/test_scenario_boundary.py",
    "tests/autoresearch/test_campaign_boundary.py",
)
# Researcher code changes retain only the human-owned architecture guards.
RESEARCHER_VALIDATED_TEST_PATHS = (*AUTORESEARCH_BOUNDARY_TEST_PATHS,)
FRESH_BASELINE_VALIDATED_TEST_PATHS = (
    "tests/benchmark",
    *RESEARCHER_VALIDATED_TEST_PATHS,
)
# The researcher-owned scientific surface, stated positively. Anything absent
# here is unclassified and validated completely, so a new or unfamiliar path is
# never assumed mutable.
RESEARCHER_OWNED_PREFIXES = (
    "robot_learning/scenario/",
    "robot_learning/training/",
)
# Campaign laboratory tooling is Researcher-owned, but it is not part of a
# policy's scientific recipe. It is published independently and never follows
# keep/revert/restore lineage decisions.
CAMPAIGN_LAB_PREFIXES = ("research/lab/",)
RESEARCHER_OWNED_PATHS = {
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
}
# Editing these carries no source change, so the test suites stay untouched.
PARAMETER_ONLY_PATHS = {"research/current_params.json"}
DEPENDENCY_METADATA_PATHS = {"pyproject.toml", "uv.lock"}
# The researcher-owned surface that materially defines what a research
# measurement means. The whole scenario package is scanned so new instrumentation
# modules or data files count without registering them here.
EVALUATION_SEMANTICS_ROOT = "robot_learning/scenario"
# Scenario files that only affect what a human sees, never how a saved policy is
# measured, so editing them must not invalidate completed measurements.
PRESENTATION_ONLY_PATHS = {
    "robot_learning/scenario/progress.py",
    "robot_learning/scenario/viewer.py",
}
# Researcher-owned files that shape training only. They determine neither how a
# saved policy is replayed nor whether an episode is a success, so editing them
# must not invalidate completed measurements.
TRAINING_ONLY_PATHS = {
    "robot_learning/scenario/reward.py",
    "robot_learning/scenario/training_environment.py",
}
# These sources are serialized into policy_runtime.pkl and therefore belong to
# model identity, not to the context in which that saved model is measured.
MODEL_CONTAINED_RUNTIME_PATHS = {
    "robot_learning/scenario/observations.py",
    "robot_learning/scenario/policy_io.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
}
# The files outside the scenario package that change how an already-trained
# policy is replayed, observed and turned into a research measurement. The
# benchmark constants and metrics are included because the development evaluation
# environment and its success criterion are built from them (issue #58).
EVALUATION_RUNTIME_PATHS = (
    "robot_learning/policy_runtime.py",
    "robot_learning/evaluate.py",
    "robot_learning/benchmark/spec.py",
    "robot_learning/benchmark/metrics.py",
)
GENERATED_FILE_SUFFIXES = (".pyc", ".pyo", ".tmp")
GENERATED_DIRECTORY_NAMES = {"__pycache__"}
# The one line a lineage decision must carry to name the evidence it relied on.
EVIDENCE_ATTESTATION_LABEL = "Evidence inspected"
HYPOTHESIS_ASSESSMENT_LABEL = "Hypothesis assessment"
# The researcher names the model; the panel behind this key is human-owned.
# `purpose` is not part of the accepted schema: a new request carrying it is
# rejected as unsupported, while historical records that contain it stay
# readable and are ignored when loaded.
RESEARCH_EVALUATION_ENTRY_FIELDS = {
    "instrument",
    "candidate",
    "episodes",
    "seed",
    "label",
    "selection",
    "omitted_alternative",
}
TASK_REFERENCE_ENTRY_FIELDS = {
    "instrument",
    "candidate",
    "label",
    "selection",
    "omitted_alternative",
}
SUPPORTED_MEASUREMENT_INSTRUMENTS = {
    "research_evaluation",
    "task_reference",
}
# A training operation states its scientific design without prescribing whether
# the method is an incumbent-local intervention or a new approach.
REQUIRED_INVESTIGATION_FIELDS = (
    "objective_link",
    "initialization_reason",
    "expected_observation",
    "rationale",
)
# --- ownership -------------------------------------------------------------


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
    """Protected paths lose first, so sharing a researcher prefix never frees them."""
    relative = path.replace("\\", "/")
    if is_protected_source(relative):
        return False
    if relative.startswith(PROTECTED_TEST_PREFIXES):
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
    """Every explicitly declared classification that is missing on disk.

    A declared-but-missing classification silently changes which files define
    evaluation semantics, so it must fail loudly instead of being ignored
    (issue #41).
    """
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
    # A prefix classification is a directory by construction; a missing package
    # must not silently drop its whole protected surface.
    missing.extend(
        prefix
        for prefix in PROTECTED_BENCHMARK_PREFIXES
        if not (base / prefix).is_dir()
    )
    return sorted(missing)


def validation_test_paths(
    changed_paths: list[str], *, fresh_baseline: bool
) -> tuple[str, ...]:
    """A fresh campaign validates the scientific and task surfaces before it
    consumes training compute, using targeted AutoResearch boundary checks.
    Afterwards the suites follow ownership: a change confined to the
    researcher's own scientific surface skips only the frozen task tests."""
    if fresh_baseline:
        return FRESH_BASELINE_VALIDATED_TEST_PATHS
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


# --- experiment identity ---------------------------------------------------


def allocated_experiment_index(state: dict, campaign_id: str | None = None) -> int:
    """The highest experiment identity the Runner has ever handed out.

    When campaign_id is provided, returns the highest index for that campaign only.
    `results.jsonl` and `EXPERIMENTS.md` are histories: they can be incomplete,
    regenerated or rolled back, so they never allocate identity. A state file
    written before allocation existed carries only the last experiment the
    Runner ran, which then seeds the counter.
    """
    if campaign_id is None:
        return max(
            int(state.get("last_allocated_experiment") or 0),
            int(state.get("last_experiment") or 0),
        )
    # Campaign-scoped: track per-campaign high index
    campaign_counters = state.get("campaign_experiment_counters", {})
    return int(campaign_counters.get(campaign_id, 0))


def experiment_working_paths(
    index: int, campaign_id: str | None = None
) -> tuple[Path, ...]:
    if campaign_id:
        root = paths.campaign_candidate_root(campaign_id)
    else:
        root = paths.CANDIDATE_ROOT
    return (
        root / f"experiment-{index}",
        root / f"recovery-experiment-{index}",
    )


def next_experiment_index(state: dict, campaign_id: str | None = None) -> int:
    """Allocate the next identity for a new experiment.

    When campaign_id is provided, allocates indices independently per campaign.
    An identity whose working directories already hold data is skipped, never
    reused: unexpected data is preserved and only costs a number.
    """
    index = allocated_experiment_index(state, campaign_id=campaign_id) + 1
    while any(
        path.exists()
        for path in experiment_working_paths(index, campaign_id=campaign_id)
    ):
        console.announce(
            f"[runner] WARNING: models/candidates already holds data for "
            f"experiment {index}; preserving it and skipping that identity"
        )
        index += 1
    # Update campaign counter if campaign_id provided
    if campaign_id:
        if "campaign_experiment_counters" not in state:
            state["campaign_experiment_counters"] = {}
        state["campaign_experiment_counters"][campaign_id] = index
    return index


def resumed_experiment_index(
    state: dict, reuse_candidate: Path | None, campaign_id: str | None = None
) -> int:
    """A preserved proposal keeps the identity its interrupted run allocated."""
    index = allocated_experiment_index(state, campaign_id=campaign_id)
    if reuse_candidate is not None:
        # Only load-bearing for a state file that predates allocated identity.
        match = re.fullmatch(r"recovery-experiment-(\d+)", reuse_candidate.name)
        if match:
            index = max(index, int(match.group(1)))
    return index


def allocated_inquiry_index(state: dict, campaign_id: str | None = None) -> int:
    """Highest inquiry identity allocated independently of experiments."""
    if campaign_id is None:
        return max(
            int(state.get("last_allocated_inquiry") or 0),
            int(state.get("last_inquiry") or 0),
        )
    return int((state.get("campaign_inquiry_counters") or {}).get(campaign_id, 0))


def require_active_inquiry(state: dict) -> dict:
    """Return the declared active inquiry."""
    active = state.get("active_inquiry")
    if not isinstance(active, dict):
        raise TypeError("this operation requires an active inquiry")
    return active


# --- experiment shape ------------------------------------------------------


def parameter_change_records(
    previous: dict,
    overrides: dict,
    prefix: str = "",
) -> list[dict]:
    """Describe only the leaves explicitly changed by a proposal."""
    changes: list[dict] = []
    for key, after in overrides.items():
        path = f"{prefix}.{key}" if prefix else key
        before = previous.get(key) if isinstance(previous, dict) else None
        if isinstance(after, dict):
            changes.extend(
                parameter_change_records(
                    before if isinstance(before, dict) else {},
                    after,
                    path,
                )
            )
        elif before != after:
            changes.append({"path": path, "before": before, "after": after})
    return changes


def extends_lineage(record: dict) -> bool:
    """Whether the record deliberately continues an existing lineage's training.

    ``continuation`` carries the relation implicitly. A changed recipe that
    still continues a lineage marks it explicitly with ``extends_lineage``.
    """
    if bool(record.get("extends_lineage")):
        return True
    return str(record.get("kind", "")).strip().lower() == "continuation"


def lineage_identity(lineage: dict | None, fallback: str = "") -> str:
    """Return the immutable identity of a frozen lineage.

    A lineage selected under a mutable role name such as ``working`` or
    ``best_known`` must keep its own identity when that role is later reassigned
    to a different lineage. The frozen ``candidate`` and ``origin_experiment``
    survive a reassignment; the role name does not.
    """
    if isinstance(lineage, dict):
        candidate = str(lineage.get("candidate") or "").strip()
        if candidate:
            origin = lineage.get("origin_experiment")
            return f"{candidate}@{origin}" if origin is not None else candidate
        identifier = str(lineage.get("identifier") or "").strip()
        if identifier:
            return identifier
    return fallback.strip()


def lineage_family(
    record: dict,
    parameter_paths: list[str],
    *,
    lineage: dict | None = None,
) -> str:
    """Name the extended lineage together with any adjusted parameter paths."""
    frozen = lineage if lineage is not None else record.get("training_parent_lineage")
    label = lineage_identity(frozen, str(record.get("training_parent", "")))
    base = f"lineage.{label}" if label else "lineage"
    if parameter_paths:
        return f"{base}+{'+'.join(parameter_paths)}"
    return base


def experiment_family(
    proposal: dict,
    experiment_kind: str,
    parameter_changes: list[dict],
    code_changes: list[str],
    *,
    training_parent_lineage: dict | None = None,
) -> str:
    if extends_lineage(proposal):
        return lineage_family(
            proposal,
            sorted({item["path"] for item in parameter_changes}),
            lineage=training_parent_lineage,
        )
    declared = str(proposal.get("family", "")).strip()
    if declared:
        return declared
    if experiment_kind == "calibration":
        return "research.training_seed_calibration"
    if proposal.get("baseline"):
        return "training.baseline"
    parameter_paths = sorted({item["path"] for item in parameter_changes})
    if parameter_paths:
        return "+".join(parameter_paths)
    if experiment_kind == "method":
        return "research.selection_method"
    if code_changes:
        normalized = re.sub(r"[^a-z0-9]+", "_", operation_description(proposal).lower())
        return f"code.{normalized.strip('_')[:80]}"
    return experiment_kind


def operation_description(record: dict) -> str:
    """Return the stable human-readable operation description for a record.

    For a lineage extension the label comes from the frozen lineage identity,
    and the Researcher's raw ``change`` is read from ``researcher_change`` when
    the record stores the derived description in ``change``, so the lineage
    wording is applied exactly once.
    """
    kind = str(record.get("kind", "")).strip().lower()
    if kind == "replication":
        return "Replicate the current method from fresh initialization"
    if extends_lineage(record):
        label = (
            lineage_identity(
                record.get("training_parent_lineage"),
                str(record.get("training_parent", "")),
            )
            or "the selected parent"
        )
        if kind == "continuation":
            return f"Continue training lineage {label}"
        base = f"Continue training lineage {label} with a changed recipe"
        raw_change = record.get("researcher_change")
        if not (isinstance(raw_change, str) and raw_change.strip()):
            raw_change = record.get("change")
        if isinstance(raw_change, str) and raw_change.strip():
            return f"{base}: {raw_change.strip()}"
        return base
    value = record.get("change")
    return value.strip() if isinstance(value, str) else ""


def retained_lineage(state: dict, identifier: str) -> dict | None:
    return next(
        (
            lineage
            for lineage in state.get("retained_lineages", [])
            if lineage.get("id") == identifier
        ),
        None,
    )


def lineage_role(state: dict, identifier: str) -> dict | None:
    """Resolve a Researcher-facing lineage ID without changing its identity."""
    if identifier == "active_method":
        method = state.get("active_method")
        lineage = method.get("current_lineage") if isinstance(method, dict) else None
        return lineage if isinstance(lineage, dict) else None
    if identifier in {"working", "best_known"}:
        lineage = state.get(f"{identifier}_lineage")
        return lineage if isinstance(lineage, dict) else None
    lineage = retained_lineage(state, identifier)
    if lineage is not None:
        return lineage
    return None


def training_parent(
    proposal: dict, state: dict, initialization: str
) -> tuple[str, Path, int]:
    resolved = resolved_training_parent(proposal, state, initialization)
    if resolved is None:
        return "fresh", Path(), 0
    return (
        str(resolved["identifier"]),
        repository.resolve_repo_path(str(resolved["artifact"])),
        int(resolved["training_steps"]),
    )


def resolved_training_parent(
    proposal: dict, state: dict, initialization: str
) -> dict | None:
    """Freeze every model and recipe fact needed by training or recovery."""
    if initialization != "transfer":
        return None
    identifier = str(proposal["training_parent"]).strip()
    lineage = lineage_role(state, identifier)
    if lineage is None:
        raise ValueError(f"unknown training parent {identifier!r}")
    artifact = repository.resolve_repo_path(lineage["artifact"])
    for filename in repository.ARTIFACT_FILES:
        if not (artifact / filename).exists():
            raise ValueError(
                f"training parent {identifier!r} is incomplete: {filename}"
            )
    repository.require_complete_inference_artifact(
        artifact, f"training parent {identifier!r}"
    )
    fingerprint = str(lineage.get("fingerprint") or "").strip()
    if not fingerprint or repository.artifact_fingerprint(artifact) != fingerprint:
        raise ValueError(
            f"training parent {identifier!r} fingerprint does not match its artifact"
        )
    if str(proposal.get("kind", "training")).strip().lower() == "continuation":
        if not str(lineage.get("scientific_commit") or "").strip():
            raise ValueError(
                f"continuation parent {identifier!r} has no scientific_commit provenance"
            )
        if not isinstance(lineage.get("parameters"), dict):
            raise ValueError(
                f"continuation parent {identifier!r} has no effective parameters"
            )
    return {
        "identifier": identifier,
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": lineage.get("fingerprint"),
        "origin_experiment": lineage.get("origin_experiment"),
        "candidate": lineage.get("candidate", identifier),
        "parameters": lineage.get("parameters"),
        "scientific_commit": lineage.get("scientific_commit"),
        "training_steps": int(lineage.get("training_steps", 0)),
    }


# --- proposal validation ---------------------------------------------------


def _validate_investigation_statement(field: str, value: object) -> None:
    """Require an explicit statement. The check is explicitness, not merit."""
    if isinstance(value, str) and value.strip():
        return
    raise ValueError(f"investigation_design.{field} must be a non-empty string")


def validate_investigation_design(proposal: dict) -> None:
    """Check an explicit, method-neutral scientific design."""
    design = proposal.get("investigation_design")
    if not isinstance(design, dict):
        raise TypeError("proposal investigation_design must be an object")

    for field in REQUIRED_INVESTIGATION_FIELDS:
        _validate_investigation_statement(field, design.get(field))
    if "scientific_model" in design:
        scientific_model = design["scientific_model"]
        if not isinstance(scientific_model, dict):
            raise TypeError("investigation_design.scientific_model must be an object")
        if not scientific_model:
            raise ValueError("investigation_design.scientific_model must not be empty")
        for field, value in scientific_model.items():
            _validate_investigation_statement(f"scientific_model.{field}", value)
    predicted_path = design.get("predicted_behavioral_path")
    open_question = design.get("open_question")
    if not (isinstance(predicted_path, str) and predicted_path.strip()) and not (
        isinstance(open_question, str) and open_question.strip()
    ):
        raise ValueError(
            "investigation_design requires predicted_behavioral_path or open_question"
        )
    if predicted_path is not None and not (
        isinstance(predicted_path, str) and predicted_path.strip()
    ):
        raise ValueError(
            "investigation_design.predicted_behavioral_path must be non-empty"
        )
    if open_question is not None and not (
        isinstance(open_question, str) and open_question.strip()
    ):
        raise ValueError("investigation_design.open_question must be non-empty")
    evidence = design.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("investigation_design.evidence must be a non-empty list")
    for item in evidence:
        if not isinstance(item, dict):
            raise TypeError(
                "each investigation_design.evidence entry must be an object"
            )
        for field in ("source", "observation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(
                    f"investigation_design.evidence.{field} must be a non-empty string"
                )


def scientific_strategy_section(text: str, campaign_id: str | None) -> str:
    """Read only this campaign's revisable memory, separate from experiments."""
    if not campaign_id:
        return ""
    heading = rf"^## {re.escape(campaign_id)} / Scientific strategy[ \t]*\r?$"
    matches = list(
        re.finditer(
            heading + r".*?(?=^## |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
    )
    if len(matches) > 1:
        raise ValueError(
            "postmortems.md contains duplicate scientific strategy sections"
        )
    return matches[0].group(0).strip() if matches else ""


def validate_research_memory(proposal: dict, state: dict) -> None:
    """Validate references and the memory format without inventing conclusions."""
    for item in proposal["investigation_design"]["evidence"]:
        source = repository.resolve_repo_path(item["source"])
        if not source.is_file():
            raise ValueError(
                f"reasoning evidence source does not exist: {item['source']}"
            )
    text = (
        paths.POSTMORTEM_PATH.read_text(encoding="utf-8")
        if paths.POSTMORTEM_PATH.exists()
        else ""
    )
    section = scientific_strategy_section(text, repository.current_campaign_id(state))
    if not section:
        raise ValueError(
            "postmortems.md needs the current campaign's Scientific strategy section"
        )
    scientific_strategy_registers(section)


def _strategy_entry(section: str, *labels: str) -> str:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^\*\*(?:{alternatives}):\*\*[ \t]*(.*?)(?=^\*\*|\Z)",
        section,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def scientific_strategy_registers(section: str) -> dict[str, str]:
    """Return the causal research map, accepting the previous labels on read."""
    registers = {
        "current_synthesis": _strategy_entry(section, "Current synthesis", "Direction"),
        "lessons_and_limits": _strategy_entry(section, "Lessons and limits"),
        "competing_explanations": _strategy_entry(
            section, "Competing explanations", "Open questions"
        ),
        "decision_frontier": _strategy_entry(
            section, "Decision frontier", "Active inquiry"
        ),
    }
    labels = {
        "current_synthesis": "Current synthesis",
        "lessons_and_limits": "Lessons and limits",
        "competing_explanations": "Competing explanations",
        "decision_frontier": "Decision frontier",
    }
    for key, label in labels.items():
        if not registers[key]:
            raise ValueError(f"scientific strategy needs a non-empty '{label}' entry")
    return registers


# The Researcher owns science, not tests. Any test path in a proposal is a path
# the Researcher does not own, so the rejection names those paths and asks for
# them to be dropped from the proposal. It never asks the Researcher to edit,
# restore or otherwise modify a file it does not own.
TEST_SURFACE_REJECTION = (
    "tests are not part of the researcher's surface and cannot be changed by a "
    "research proposal"
)
NOT_OWNED_PATHS_REMEDY = (
    "drop those paths from the proposal, because they are not the researcher's "
    "changes to make"
)


def validate_research_delta_ownership(code_changes: list[str]) -> None:
    """Reject changes to every human-owned source and test surface.

    An unowned path is removed from the proposal, never repaired by the
    Researcher, so no rejection message prescribes an edit to it.
    """
    normalized = [path.replace("\\", "/") for path in code_changes]
    protected_sources = sorted(
        {path for path in normalized if is_protected_source(path)}
    )
    if protected_sources:
        raise ValueError(
            "human-owned task, context, dependency and protocol surfaces cannot "
            "be changed by a research proposal: "
            f"{protected_sources}; {NOT_OWNED_PATHS_REMEDY}"
        )
    protected_tests = sorted(
        path for path in normalized if path.startswith(PROTECTED_TEST_PREFIXES)
    )
    if protected_tests:
        raise ValueError(
            f"{TEST_SURFACE_REJECTION}: {protected_tests}; {NOT_OWNED_PATHS_REMEDY}"
        )


def validate_experiment_semantics(
    proposal: dict,
    experiment_kind: str,
    initialization: str,
    parameter_overrides: dict | None,
    code_changes: list[str],
    baseline: bool,
) -> None:
    validate_research_delta_ownership(code_changes)
    if baseline and (parameter_overrides or code_changes):
        raise ValueError("baseline requires an unchanged research method")
    if experiment_kind == "continuation" and code_changes:
        raise ValueError("continuation cannot change the scientific code surface")
    if (
        not baseline
        and experiment_kind not in {"continuation", "replication"}
        and not parameter_overrides
        and not code_changes
    ):
        raise ValueError("experiment contains no research change")
    if experiment_kind == "replication" and (parameter_overrides or code_changes):
        raise ValueError("replication requires an unchanged learning method")


def validate_training_proposal(proposal: dict, *, baseline: bool) -> None:
    def require_nonempty_string(field: str, description: str) -> None:
        value = proposal.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{description} must be a non-empty string")

    def require_integer(field: str, *, minimum: int | None = None) -> int:
        value = proposal.get(field)
        if type(value) is not int:
            raise ValueError(f"{field} must be an integer when supplied")
        if minimum is not None and value < minimum:
            qualifier = "non-negative" if minimum == 0 else "positive"
            raise ValueError(f"{field} must be a {qualifier} integer")
        return value

    if baseline:
        # A baseline is its own runner-generated contract, never a training kind.
        if "kind" in proposal:
            raise ValueError("baseline proposal must not declare kind")
        required = {"change", "hypothesis", "initialization"}
        missing = sorted(field for field in required if field not in proposal)
        if missing:
            raise ValueError(f"baseline proposal is missing required fields: {missing}")
        require_nonempty_string("hypothesis", "baseline proposal hypothesis")
        require_nonempty_string("change", "baseline proposal change")
        # A baseline measures the unchanged method from zero, never a lineage.
        if proposal["initialization"] != "fresh":
            raise ValueError("baseline proposal requires fresh initialization")
        return
    forbidden = {
        "previous_result_decision",
        "previous_experiment_postmortem",
        "reasoning",
    } & set(proposal)
    if forbidden:
        raise ValueError(
            f"training proposal contains lineage-only fields: {sorted(forbidden)}"
        )
    required = {
        "kind",
        "method_id",
        "initialization",
        "investigation_design",
    }
    missing = sorted(field for field in required if field not in proposal)
    if missing:
        raise ValueError(f"training proposal is missing required fields: {missing}")
    require_nonempty_string("method_id", "training proposal method_id")
    if "family" in proposal:
        require_nonempty_string("family", "training proposal family")
    kind = proposal["kind"]
    if kind not in {"training", "continuation", "replication"}:
        raise ValueError(
            "training proposal kind must be training, continuation or replication"
        )
    if kind == "training":
        if "change" not in proposal:
            raise ValueError("training proposal is missing required fields: ['change']")
        require_nonempty_string("change", "training proposal change")
    elif "change" in proposal:
        if kind == "continuation":
            reason = (
                "a continuation restores the frozen parent recipe and adjusts it "
                "only through params"
            )
        else:
            reason = "a replication starts from the unchanged method"
        raise ValueError(f"{kind} must omit change: {reason}")
    if proposal.get("params") is not None and not isinstance(proposal["params"], dict):
        raise TypeError("proposal params must be an object")
    if "training_seed" in proposal:
        require_integer("training_seed", minimum=0)
    initialization = proposal["initialization"]
    if initialization not in {"transfer", "fresh"}:
        raise ValueError("initialization must be transfer or fresh")
    if initialization == "transfer":
        if (
            not isinstance(proposal.get("training_parent"), str)
            or not proposal["training_parent"].strip()
        ):
            raise ValueError("transfer initialization requires training_parent")
    elif "training_parent" in proposal:
        raise ValueError("training_parent is only valid with transfer initialization")
    if kind == "continuation" and initialization != "transfer":
        raise ValueError("continuation requires transfer initialization")
    if kind == "replication":
        if initialization != "fresh":
            raise ValueError("replication requires fresh initialization")
        if "training_seed" not in proposal:
            raise ValueError("replication requires an explicit training_seed")
        require_integer("replication_of", minimum=1)
    relation = proposal.get("extends_lineage")
    if relation is not None and type(relation) is not bool:
        raise ValueError("extends_lineage must be a boolean")
    if relation:
        if kind != "training":
            raise ValueError("extends_lineage is only valid for a training proposal")
        if initialization != "transfer":
            raise ValueError("extends_lineage requires transfer initialization")
    validate_investigation_design(proposal)


def validate_proposal_phase(proposal: dict, state: dict) -> str:
    """Return the proposal contract expected by the persisted lifecycle state."""
    if not isinstance(proposal, dict):
        raise TypeError("proposal.json must contain a JSON object")
    pending_training = state.get("pending_training_operation")
    if isinstance(pending_training, dict):
        if proposal != pending_training.get("frozen_proposal"):
            raise ValueError(
                "proposal changed after the pending training operation was accepted"
            )
        return "training"
    if state.get("terminal_campaign_status") is not None:
        raise ValueError("the campaign has received its terminal official assessment")
    if state.get("pending_inquiry_operation") is not None:
        raise ValueError(
            "an inquiry operation is pending; resume it before submitting a proposal"
        )
    if (
        state.get("pending_baseline_decision") is not None
        or state.get("pending_method_decision") is not None
    ):
        raise ValueError(
            "a decision operation is pending; resume it before submitting a proposal"
        )
    if state.get("pending_final_benchmark") is not None:
        raise ValueError(
            "the final benchmark is pending; no research proposal is accepted"
        )
    if state.get("pending_analysis") is not None:
        pending = state["pending_analysis"]
        expected = "baseline_decision" if pending.get("baseline") else "method_decision"
        if set(proposal) != {expected}:
            raise ValueError(f"the current analysis phase requires only {expected}")
        return "baseline" if pending.get("baseline") else "method_decision"
    if state.get("pending_evaluation_request") is not None:
        raise ValueError(
            "research evaluation is pending; use evaluation_request.json, not "
            "proposal.json"
        )
    if "inquiry" in proposal:
        if set(proposal) != {"inquiry"}:
            raise ValueError("an inquiry operation must contain only inquiry")
        return "inquiry"
    if "method" in proposal:
        if set(proposal) != {"method"}:
            raise ValueError("a method operation must contain only method")
        return "method"
    if "method_decision" in proposal:
        if set(proposal) != {"method_decision"}:
            raise ValueError("a method decision must contain only method_decision")
        return "method_decision"
    if "campaign_conclusion" in proposal:
        if (
            state.get("pending_baseline_decision") is not None
            or state.get("pending_method_decision") is not None
        ):
            raise ValueError(
                "a campaign conclusion is not accepted while a decision operation "
                "is pending"
            )
        if set(proposal) != {"campaign_conclusion"}:
            raise ValueError(
                "a campaign conclusion must contain only campaign_conclusion"
            )
        return "conclusion"
    retired = {"previous_result_decision", "inquiry_decision"} & set(proposal)
    if retired:
        raise ValueError(
            f"retired proposal fields are not supported: {sorted(retired)}"
        )
    baseline = bool(proposal.get("baseline", False))
    validate_training_proposal(proposal, baseline=baseline)
    return "training"


def validate_proposal_against_state(
    proposal: dict,
    raw_state: dict,
    *,
    training_allocation_closed: bool = False,
) -> str:
    """Fully validate a proposal for its phase without mutating repository state."""
    contract = validate_proposal_phase(proposal, raw_state)
    if contract == "conclusion":
        plan_campaign_conclusion(proposal, raw_state)
    elif contract == "inquiry":
        plan_inquiry_operation(proposal, raw_state)
    elif contract == "method":
        plan_method_start(proposal, raw_state)
    elif contract == "method_decision":
        plan_method_decision(proposal, raw_state)
    elif contract == "baseline":
        state = repository.load_state(
            allow_unmeasured=True, allow_missing_artifact=True
        )
        plan_baseline_decision(proposal, state)
    elif proposal.get("kind") == "replication":
        campaign_id = repository.current_campaign_id(raw_state)
        recorded = (
            repository.result_records_for_campaign(campaign_id) if campaign_id else []
        )
        referenced = proposal["replication_of"]
        if not any(record.get("index") == referenced for record in recorded):
            raise ValueError(
                "replication_of must reference an existing experiment in the "
                "current campaign"
            )
    if (
        contract == "training"
        and proposal.get("baseline")
        and not isinstance(raw_state.get("pending_training_operation"), dict)
    ):
        campaign_id = repository.current_campaign_id(raw_state)
        counter = (
            raw_state.get("campaign_experiment_counters", {}).get(campaign_id, 0)
            if campaign_id
            else 0
        )
        inquiry_counter = (
            raw_state.get("campaign_inquiry_counters", {}).get(campaign_id, 0)
            if campaign_id
            else 0
        )
        occupied = any(
            raw_state.get(field) is not None
            for field in (
                "working_lineage",
                "best_known_lineage",
                "active_inquiry",
                "active_method",
                "inquiry_session",
            )
        ) or bool(raw_state.get("retained_lineages"))
        if (
            int(raw_state.get("last_experiment", 0)) != 0
            or int(raw_state.get("last_allocated_experiment", 0)) != 0
            or int(counter) != 0
            or int(raw_state.get("last_inquiry", 0)) != 0
            or int(raw_state.get("last_allocated_inquiry", 0)) != 0
            or int(inquiry_counter) != 0
            or occupied
            or not paths.BASELINE_PENDING_PATH.is_file()
        ):
            raise ValueError(
                "baseline is valid only for a true fresh campaign with zero "
                "experiment counters, no lineages or inquiry state, and "
                "BASELINE_PENDING"
            )
    if (
        contract == "training"
        and training_allocation_closed
        and not isinstance(raw_state.get("pending_training_operation"), dict)
    ):
        raise ValueError(
            "the training allocation cap is reached; choose a non-training "
            "inquiry operation or campaign conclusion"
        )
    if contract == "training" and not proposal.get("baseline"):
        active = raw_state.get("active_inquiry")
        method = raw_state.get("active_method")
        if not isinstance(active, dict):
            raise ValueError("non-baseline training requires an active inquiry")
        if not isinstance(method, dict):
            raise ValueError("non-baseline training requires a declared active_method")
        if method.get("lifecycle") not in {"concept", "development", "mature"}:
            raise ValueError("the active_method is not available for another iteration")
        if proposal.get("method_id") != method.get("id"):
            raise ValueError("training proposal method_id must match active_method.id")
        validate_research_memory(proposal, raw_state)
    return contract


def _inquiry_fields(operation: dict) -> dict:
    values = {}
    for field in ("question", "scope", "closure_condition"):
        value = operation.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"inquiry {field} must be a non-empty string")
        values[field] = value.strip()
    return values


def plan_inquiry_operation(proposal: dict, state: dict) -> dict:
    """Validate opening, reframing, or closing one bounded inquiry."""
    if any(
        state.get(field) is not None
        for field in (
            "pending_analysis",
            "pending_evaluation_request",
            "pending_baseline_decision",
            "pending_method_decision",
            "pending_final_benchmark",
            "pending_campaign_conclusion",
        )
    ):
        raise ValueError("the current pending operation must be resolved first")
    operation = proposal.get("inquiry")
    if not isinstance(operation, dict):
        raise TypeError("inquiry must be an object")
    action = str(operation.get("action", "")).strip()
    active = state.get("active_inquiry")
    session = state.get("inquiry_session")
    if action == "open":
        if isinstance(active, dict):
            raise ValueError("an inquiry is already active")
        if not isinstance(session, dict):
            raise ValueError("opening an inquiry requires its allocated session")
        expected = {"action", "question", "scope", "closure_condition"}
        if set(operation) != expected:
            raise ValueError(
                "opening an inquiry requires exactly action, question, scope, "
                "and closure_condition"
            )
        return {
            "action": "open",
            "inquiry_id": int(session["inquiry_id"]),
            "session_id": str(session["id"]),
            **_inquiry_fields(operation),
        }
    if not isinstance(active, dict):
        raise TypeError(f"inquiry {action or 'operation'} requires an active inquiry")
    if action == "reframe":
        expected = {
            "action",
            "question",
            "scope",
            "closure_condition",
            "rationale",
        }
        if set(operation) != expected:
            raise ValueError(
                "reframing an inquiry requires exactly action, question, scope, "
                "closure_condition, and rationale"
            )
        rationale = str(operation.get("rationale", "")).strip()
        if not rationale:
            raise ValueError("inquiry reframe rationale must be non-empty")
        return {
            "action": "reframe",
            "inquiry_id": int(active["id"]),
            "rationale": rationale,
            **_inquiry_fields(operation),
        }
    if action != "close":
        raise ValueError("inquiry action must be open, reframe, or close")
    if set(operation) != {"action", "outcome"}:
        raise ValueError("closing an inquiry requires exactly action and outcome")
    outcome = str(operation.get("outcome", "")).strip()
    if not outcome:
        raise ValueError("inquiry outcome must be non-empty")
    method = state.get("active_method")
    if isinstance(method, dict) and method.get("lifecycle") not in {
        "promoted",
        "retained",
        "abandoned",
    }:
        raise ValueError(
            "close the active method by promoting, retaining, or abandoning it "
            "before closing the inquiry"
        )
    section = scientific_strategy_section(
        paths.POSTMORTEM_PATH.read_text(encoding="utf-8")
        if paths.POSTMORTEM_PATH.exists()
        else "",
        repository.current_campaign_id(state),
    )
    if not section:
        raise ValueError(
            "postmortems.md needs the current campaign's Scientific strategy section"
        )
    scientific_strategy_registers(section)
    return {
        "action": "close",
        "outcome": outcome,
        "inquiry_id": int(active["id"]),
        "active_method": copy.deepcopy(method),
    }


def plan_method_start(proposal: dict, state: dict) -> dict:
    """Validate a first-class method declaration before any method training."""
    active = require_active_inquiry(state)
    if state.get("active_method") is not None:
        raise ValueError("the active inquiry already has an active_method")
    operation = proposal.get("method")
    if not isinstance(operation, dict):
        raise TypeError("method must be an object")
    expected = {
        "action",
        "id",
        "scientific_question",
        "rationale",
        "lifecycle",
    }
    if set(operation) != expected or operation.get("action") != "start":
        raise ValueError(
            "method start requires exactly action=start, id, scientific_question, "
            "rationale, and lifecycle"
        )
    identifier = str(operation.get("id", "")).strip()
    if (
        not identifier
        or Path(identifier).name != identifier
        or identifier in {".", ".."}
    ):
        raise ValueError("method id must be non-empty and file-name-safe")
    for field in ("scientific_question", "rationale"):
        if not isinstance(operation.get(field), str) or not operation[field].strip():
            raise ValueError(f"method {field} must be a non-empty string")
    lifecycle = str(operation.get("lifecycle", "")).strip()
    if lifecycle not in {"concept", "development"}:
        raise ValueError("a new method lifecycle must be concept or development")
    base_scientific_commit = str(state.get("pending_scientific_parent") or "").strip()
    if not base_scientific_commit:
        raise ValueError(
            "method start requires the anchored pre-method scientific parent"
        )
    return {
        "action": "start",
        "method": {
            "id": identifier,
            "inquiry_id": int(active["id"]),
            "scientific_question": operation["scientific_question"].strip(),
            "rationale": operation["rationale"].strip(),
            "lifecycle": lifecycle,
            "base_scientific_commit": base_scientific_commit,
            "current_lineage": None,
            "iterations": [],
            "resolution": None,
        },
    }


def _method_inquiry_context(state: dict, method: dict) -> dict:
    """Expose inquiry measurements through the method-decision evidence machinery."""
    lineage = method.get("current_lineage")
    active = require_active_inquiry(state)
    ledger = state.get("preparation_measurement")
    if not (isinstance(ledger, dict) and ledger.get("inquiry_id") == active.get("id")):
        ledger = {}
    return {
        "experiment": (
            int(lineage["origin_experiment"])
            if isinstance(lineage, dict)
            else int(state.get("last_experiment", 0))
        ),
        "inquiry_id": int(active["id"]),
        "method_id": str(method["id"]),
        "candidates": [],
        "parameters": copy.deepcopy(lineage.get("parameters", {}))
        if isinstance(lineage, dict)
        else {},
        "code_parent_commit": str(method["base_scientific_commit"]),
        "preparation_evaluations": copy.deepcopy(
            ledger.get("partial_evaluations") or []
        ),
        "preparation_task_reference_evaluations": copy.deepcopy(
            ledger.get("partial_task_reference_evaluations") or []
        ),
    }


def plan_method_decision(proposal: dict, state: dict) -> dict:
    """Plan one method transition from analysis or directly from inquiry."""
    active = require_active_inquiry(state)
    if any(
        state.get(field) is not None
        for field in (
            "pending_evaluation_request",
            "pending_baseline_decision",
            "pending_method_decision",
            "pending_final_benchmark",
            "pending_campaign_conclusion",
        )
    ):
        raise ValueError("the current pending operation must be resolved first")
    method = state.get("active_method")
    if not isinstance(method, dict):
        raise TypeError("method decision requires an active_method")
    lifecycle = str(method.get("lifecycle", ""))
    if lifecycle in {"promoted", "retained", "abandoned"}:
        raise ValueError("the active_method is already resolved")
    analysis = state.get("pending_analysis")
    if isinstance(analysis, dict) and analysis.get("baseline"):
        raise ValueError("baseline analysis requires baseline_decision")
    has_pending_analysis = isinstance(analysis, dict)
    pending = (
        copy.deepcopy(analysis)
        if has_pending_analysis
        else _method_inquiry_context(state, method)
    )
    if has_pending_analysis and pending.get("method_id") != method.get("id"):
        raise ValueError("pending training does not belong to active_method")
    decision = proposal.get("method_decision")
    if not isinstance(decision, dict):
        raise TypeError("method_decision must be an object")
    allowed = {
        "experiment",
        "action",
        "outcome",
        "reason",
        "candidate",
        "code",
        "retained_id",
        "best_known",
    }
    extra = set(decision) - allowed
    if extra:
        raise ValueError(f"unsupported method_decision fields: {sorted(extra)}")
    action = str(decision.get("action", "")).strip()
    if action not in {
        "continue",
        "refine",
        "mature",
        "promote",
        "retain",
        "abandon",
    }:
        raise ValueError(
            "method_decision action must be continue, refine, mature, promote, "
            "retain, or abandon"
        )
    outcome = str(decision.get("outcome", "")).strip()
    reason = str(decision.get("reason", "")).strip()
    if not outcome or not reason:
        raise ValueError("method_decision requires non-empty outcome and reason")
    if has_pending_analysis:
        if int(decision.get("experiment", -1)) != int(pending["experiment"]):
            raise ValueError("method_decision references the wrong experiment")
        assessment = validate_postmortem_evidence(
            int(pending["experiment"]),
            pending_evaluation_artifacts(pending),
            campaign_id=repository.current_campaign_id(state),
            pending=pending,
            require_hypothesis_assessment=True,
        )
    else:
        if "experiment" in decision:
            raise ValueError(
                "an inquiry method_decision must not allocate or reference an experiment"
            )
        if action in {"continue", "refine", "mature"}:
            raise ValueError(
                f"method action {action} requires pending post-training analysis"
            )
        assessment = None

    sources = _lineage_sources(pending, state)
    code_context = copy.deepcopy(pending)
    if action == "abandon" or not has_pending_analysis:
        code_context["code_parent_commit"] = str(method["base_scientific_commit"])
    code_action, code_reason, code_plan = _code_decision_plan(
        decision, code_context, state, sources
    )
    if action == "abandon":
        if code_action == "keep":
            raise ValueError("abandoning a method requires explicit revert or restore")
        if (
            code_action == "restore"
            and decision["code"].get("lineage") == "active_method"
        ):
            raise ValueError(
                "abandoning a method cannot restore its own scientific recipe"
            )

    previous_lineage = copy.deepcopy(method.get("current_lineage"))
    selected_name = str(decision.get("candidate", "")).strip()
    selected_record = None
    if action in {"continue", "refine", "mature"}:
        if not selected_name and isinstance(previous_lineage, dict):
            selected_name = "active_method"
        if not selected_name:
            raise ValueError(f"method action {action} requires a selectable lineage")
        selected_record = _selected_record(
            name=selected_name,
            reason=outcome,
            sources=sources,
            pending=pending,
            description="selected method lineage",
        )
    elif action in {"promote", "retain"}:
        if not isinstance(previous_lineage, dict):
            raise ValueError(f"method action {action} requires a current lineage")
        if selected_name and selected_name != "active_method":
            raise ValueError(
                f"method action {action} operates on the current active_method lineage"
            )
        selected_name = "active_method"
        selected_record = _selected_record(
            name=selected_name,
            reason=outcome,
            sources=sources,
            pending=pending,
            description="current method lineage",
        )
    elif "candidate" in decision:
        raise ValueError("abandon must not select a candidate")

    next_method = copy.deepcopy(method)
    if selected_record is not None:
        next_method["current_lineage"] = copy.deepcopy(selected_record)
    if has_pending_analysis:
        iteration = next(
            (
                item
                for item in next_method["iterations"]
                if item.get("experiment") == int(pending["experiment"])
            ),
            None,
        )
        if iteration is None:
            raise ValueError("active_method has no record of this training iteration")
        iteration.update(
            status=action,
            outcome=outcome,
            candidate=selected_name or None,
        )
    resolution = {
        "action": action,
        "outcome": outcome,
        "reason": reason,
        "inquiry_id": int(active["id"]),
    }
    if has_pending_analysis:
        resolution["experiment"] = int(pending["experiment"])
    working = copy.deepcopy(state.get("working_lineage"))
    best = copy.deepcopy(state.get("best_known_lineage"))
    prior_working = copy.deepcopy(working)
    prior_best = copy.deepcopy(best)
    retained = [copy.deepcopy(item) for item in state.get("retained_lineages", [])]
    designation_counter = designation_counter_for(state)
    best_name = None

    if action in {"continue", "refine"}:
        next_method.update(lifecycle="development", resolution=None)
    elif action == "mature":
        next_method.update(lifecycle="mature", resolution=None)
    elif action == "promote":
        if lifecycle != "mature":
            raise ValueError("promotion requires a method already marked mature")
        _require_measured_designation(
            selected_record, pending, state, "promoted method lineage"
        )
        _require_paired_promotion_evidence(
            "active_method", selected_record, pending, state
        )
        next_method.update(
            lifecycle="promoted",
            current_lineage=copy.deepcopy(selected_record),
            resolution=resolution,
        )
        working = copy.deepcopy(selected_record)
        working["reason"] = outcome
        best_decision = decision.get("best_known")
        if best_decision is not None:
            if not isinstance(best_decision, dict) or set(best_decision) != {
                "candidate",
                "reason",
            }:
                raise ValueError("best_known requires exactly candidate and reason")
            if best_decision.get("candidate") != "active_method":
                raise ValueError(
                    "method promotion can designate only active_method as best_known"
                )
            best = copy.deepcopy(selected_record)
            best["reason"] = str(best_decision.get("reason", "")).strip()
            if not best["reason"]:
                raise ValueError("best_known reason must be non-empty")
            _require_measured_designation(
                best, pending, state, "best-known designation"
            )
            designation_counter = next_designation_ordinal(
                state.get("best_known_lineage"),
                str(best["fingerprint"]),
                designation_counter,
            )
            best["designation_ordinal"] = designation_counter
            best_name = "active_method"
    elif action == "retain":
        identifier = str(decision.get("retained_id", "")).strip()
        known = {str(item.get("id")) for item in retained}
        if (
            not identifier
            or Path(identifier).name != identifier
            or identifier in {".", ".."}
            or identifier in known
        ):
            raise ValueError(
                "retained_id must be unique, non-empty, and file-name-safe"
            )
        retained.append({"id": identifier, **copy.deepcopy(selected_record)})
        resolution["retained_id"] = identifier
        next_method.update(
            lifecycle="retained",
            current_lineage=copy.deepcopy(selected_record),
            resolution=resolution,
        )
    else:
        if "retained_id" in decision or "best_known" in decision:
            raise ValueError("abandon cannot retain or designate the method")
        next_method.update(
            lifecycle="abandoned",
            current_lineage=None,
            resolution=resolution,
        )
    if action != "retain" and "retained_id" in decision:
        raise ValueError("retained_id is valid only for retain")
    if action != "promote" and "best_known" in decision:
        raise ValueError("best_known is valid only for promote")

    publications = _artifact_publications(
        state,
        working,
        best,
        retained,
        next_method.get("current_lineage"),
    )
    if action != "promote":
        working = prior_working
    if best_name is None:
        best = prior_best
    released = (
        previous_lineage
        if isinstance(previous_lineage, dict)
        and (
            next_method.get("current_lineage") is None
            or next_method["current_lineage"].get("fingerprint")
            != previous_lineage.get("fingerprint")
        )
        else None
    )
    return {
        "kind": "method_decision",
        "inquiry_id": int(active["id"]),
        "method_id": str(method["id"]),
        "pending": pending,
        "updates_experiment": has_pending_analysis,
        "decision": copy.deepcopy(decision),
        "method_action": action,
        "method_candidate": selected_name or None,
        "working_name": "active_method" if action == "promote" else "working",
        "working_record": working,
        "best_known_name": best_name,
        "best_known_record": best,
        "active_method": next_method,
        "released_method_lineage": released,
        "retained": retained,
        "removed_retained": [],
        "artifact_publications": publications,
        "code_action": code_action,
        "code_reason": code_reason,
        "code_plan": code_plan,
        "hypothesis_assessment": assessment,
        "designation_counter": designation_counter,
    }


def plan_campaign_conclusion(proposal: dict, state: dict) -> dict:
    """Validate a preparation-phase decision that ends without a new experiment.

    Preparation historically required a training proposal. A campaign conclusion
    is the second legal exit: it either submits the standing best-known lineage
    for the official final assessment or records that no further experiment is
    warranted. Neither outcome creates an experiment record.

    Preparation measurements inform this decision without committing the phase
    to training. After any number of saved-lineage measurement rounds, the
    Researcher may request another round, prepare an experiment, request the
    official assessment, or conclude that no further experiment is warranted.
    """
    if (
        state.get("pending_baseline_decision") is not None
        or state.get("pending_method_decision") is not None
    ):
        raise ValueError(
            "a campaign conclusion is not accepted while a decision operation is pending"
        )
    if state.get("active_inquiry") is not None:
        raise ValueError("close the active inquiry before concluding the campaign")
    if set(proposal) != {"campaign_conclusion"}:
        raise ValueError("a campaign conclusion must contain only campaign_conclusion")
    conclusion = proposal["campaign_conclusion"]
    if not isinstance(conclusion, dict):
        raise TypeError("campaign_conclusion must be an object")
    extra = set(conclusion) - {"action", "reason"}
    if extra:
        raise ValueError(f"unsupported campaign_conclusion fields: {sorted(extra)}")
    action = str(conclusion.get("action", "")).strip()
    reason = str(conclusion.get("reason", "")).strip()
    if action not in {"request_final_benchmark", "no_further_experiment"}:
        raise ValueError(
            "campaign_conclusion action must be request_final_benchmark or "
            "no_further_experiment"
        )
    if not reason:
        raise ValueError("campaign_conclusion requires a non-empty reason")
    best_known = state.get("best_known_lineage")
    if action == "request_final_benchmark":
        if not isinstance(best_known, dict):
            raise ValueError("a final benchmark requires a designated best-known model")
        artifact = repository.resolve_repo_path(best_known["artifact"])
        repository.require_complete_artifact(artifact, "best-known lineage")
        if state.get("official_benchmark_artifact") == best_known.get("fingerprint"):
            raise ValueError(
                "the designated best-known model already received an official benchmark"
            )
    return {
        "action": action,
        "reason": reason,
        "campaign_conclusion": conclusion,
        "best_known": best_known if action == "request_final_benchmark" else None,
    }


# --- evaluation requests ---------------------------------------------------


def requested_measurements(request: dict) -> list[dict]:
    measurements = request.get("measurements")
    if not isinstance(measurements, list):
        raise TypeError("measurements must be a list")
    if not measurements:
        raise ValueError("an evaluation request must contain at least one measurement")
    return measurements


def validate_evaluation_request(request: dict) -> None:
    """Require the researcher's scientific framing on a newly written request."""
    for field in ("question", "reason"):
        value = request.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"evaluation request requires a non-empty {field}")
    for field in ("evaluations", "task_reference_evaluations"):
        if field in request:
            raise ValueError(
                f"{field} is obsolete; submit measurements through measurements"
            )
    if "need_more_evidence" in request:
        raise ValueError(
            "need_more_evidence is retired; submit another measurement request "
            "or a method-iteration decision"
        )
    comparisons = request.get("paired_comparisons", [])
    if not isinstance(comparisons, list):
        raise TypeError("paired_comparisons must be a list")
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise TypeError("each paired comparison must be an object")
        unsupported = sorted(set(comparison) - {"candidate", "reference"})
        if unsupported:
            raise ValueError(
                f"paired comparison cannot set unsupported fields {unsupported}"
            )
        for field in ("candidate", "reference"):
            value = comparison.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"paired comparison requires a non-empty {field}")
    # Collect distinct candidates before detailed validation.
    distinct_candidates = set()
    for entry in requested_measurements(request):
        if not isinstance(entry, dict):
            raise TypeError("each measurement must be an object")
        instrument = entry.get("instrument")
        if instrument not in SUPPORTED_MEASUREMENT_INSTRUMENTS:
            raise ValueError(f"unknown measurement instrument {instrument!r}")
        candidate = entry.get("candidate")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"{instrument} requires a non-empty candidate")
        distinct_candidates.add(candidate.strip())
        allowed_fields = (
            RESEARCH_EVALUATION_ENTRY_FIELDS
            if instrument == "research_evaluation"
            else TASK_REFERENCE_ENTRY_FIELDS
        )
        unknown = sorted(set(entry) - allowed_fields)
        if unknown:
            raise ValueError(
                f"{instrument} measurement cannot set unsupported fields {unknown}"
            )
        if "label" in entry and not isinstance(entry["label"], str):
            raise ValueError("measurement label must be a string")
        # Record scientific usefulness without asking the Runner to rank candidates.
        selection = entry.get("selection")
        if not isinstance(selection, str) or not selection.strip():
            raise ValueError(
                f"{instrument} requires a non-empty selection stating why this "
                "model is useful for the current scientific question"
            )
        # ``omitted_alternative`` stays accepted for historical records but is no
        # longer required: naming a model left out of a request produced
        # administrative counterfactuals, not new scientific information.
        omitted_alternative = entry.get("omitted_alternative")
        if omitted_alternative is not None and (
            not isinstance(omitted_alternative, str) or not omitted_alternative.strip()
        ):
            raise ValueError("omitted_alternative must be a non-empty string or null")
        if instrument == "research_evaluation":
            missing = [field for field in ("episodes", "seed") if field not in entry]
            if missing:
                raise ValueError(
                    f"research_evaluation is missing required fields: {missing}"
                )
            if not isinstance(entry["episodes"], int) or isinstance(
                entry["episodes"], bool
            ):
                raise ValueError("research_evaluation episodes must be an integer")
            if entry["episodes"] < 1:
                raise ValueError("research_evaluation episodes must be positive")
            if not isinstance(entry["seed"], int) or isinstance(entry["seed"], bool):
                raise ValueError("research_evaluation seed must be an integer")
    # Enforce the three-model limit per evaluation round.
    if len(distinct_candidates) > 3:
        raise ValueError(
            f"an evaluation request may measure at most 3 distinct models; "
            f"{len(distinct_candidates)} requested: {sorted(distinct_candidates)}"
        )


def _research_panel(entry: dict) -> tuple[int, int] | None:
    """The evaluated episode interval ``(seed, episodes)`` of one measurement."""
    seed = entry.get("seed")
    episodes = entry.get("episodes")
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        return None
    return seed, episodes


def _panels_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    """Whether two half-open episode intervals share any episode seed."""
    left_start, left_count = left
    right_start, right_count = right
    return max(left_start, right_start) < min(
        left_start + left_count, right_start + right_count
    )


def recorded_research_panels(
    state: dict, pending: dict | None
) -> list[tuple[int, int]]:
    """Panels already recorded for this campaign's research evaluations."""
    campaign_id = repository.current_campaign_id(state)
    sources = (
        list(repository.history_records_for_campaign(campaign_id))
        if campaign_id
        else []
    )
    if isinstance(pending, dict):
        sources.append(pending)
    panels: list[tuple[int, int]] = []
    for source in sources:
        for entry in [
            *(source.get("requested_evaluations") or []),
            *(source.get("partial_evaluations") or []),
            *(source.get("preparation_evaluations") or []),
        ]:
            if not isinstance(entry, dict):
                continue
            if entry.get("instrument", "research_evaluation") != "research_evaluation":
                continue
            metrics = entry.get("metrics") or {}
            panel = _research_panel({**metrics, **entry})
            if panel is not None:
                panels.append(panel)
    return panels


def validate_panel_independence(
    request: dict,
    prior_panels: list[tuple[int, int]] | None = None,
    *,
    protected_overlap=None,
) -> None:
    """Reject research-evaluation panels that partially overlap other panels.

    An identical panel is allowed for deliberate reuse, and a disjoint panel is
    always allowed; only partial overlap is rejected. ``protected_overlap`` is a
    predicate supplied by the scenario boundary that reports whether a panel
    overlaps the protected benchmark episodes; the generic Runner never reads the
    protected range, and the error never names it.
    """
    seen: list[tuple[int, int]] = []
    for entry in requested_measurements(request):
        if not isinstance(entry, dict):
            continue
        if entry.get("instrument") != "research_evaluation":
            continue
        panel = _research_panel(entry)
        if panel is None:
            continue
        if protected_overlap is not None and protected_overlap(*panel):
            raise ValueError(
                "research_evaluation panel overlaps protected benchmark evidence; "
                "choose a panel disjoint from the protected episode range"
            )
        for other in seen:
            if other != panel and _panels_overlap(panel, other):
                raise ValueError(
                    "research_evaluation panels within one request partially "
                    "overlap; use an identical panel or disjoint panels"
                )
        for other in prior_panels or []:
            if other != panel and _panels_overlap(panel, other):
                raise ValueError(
                    "research_evaluation panel partially overlaps a previously "
                    "recorded research panel; reuse the identical panel or choose "
                    "a disjoint panel"
                )
        seen.append(panel)


def available_evaluation_candidates(pending: dict, state: dict) -> dict:
    """Models a request may name, including independent reusable lineage roles."""
    available = {item["name"]: item for item in pending["candidates"]}
    identifiers = ["working", "best_known", "active_method"]
    identifiers.extend(
        str(lineage.get("id"))
        for lineage in state.get("retained_lineages", [])
        if str(lineage.get("id", "")).strip()
    )
    for identifier in identifiers:
        lineage = lineage_role(state, identifier)
        if lineage is None:
            continue
        available[identifier] = {
            **lineage,
            "name": identifier,
            "evaluations": list(lineage.get("evaluations", [])),
        }
    return available


def upcoming_experiment_index(state: dict) -> int:
    """The identity the launcher's next preparation phase will allocate.

    This is a read-only forecast. Unlike ``next_experiment_index`` it never
    mutates the campaign counter, so forecasting a preparation measurement does
    not consume or skip the experiment a later training proposal allocates.
    """
    campaign_id = repository.current_campaign_id(state)
    return (
        max(
            allocated_experiment_index(state, campaign_id),
            int(state.get("last_allocated_experiment") or 0),
            int(state.get("last_experiment") or 0),
        )
        + 1
    )


def preparation_ledger(state: dict) -> dict | None:
    """The accumulated preparation ledger for the active inquiry, if any.

    Ledgers carry an inquiry identity so repeated rounds remain associated even
    when no training experiment is allocated.
    """
    ledger = state.get("preparation_measurement")
    if not isinstance(ledger, dict):
        return None
    inquiry_id = ledger.get("inquiry_id")
    if not isinstance(inquiry_id, int) or isinstance(inquiry_id, bool):
        return None
    return ledger


def _current_lineage_fingerprints(state: dict) -> dict[str, str]:
    """The currently resolved fingerprint of every requestable saved lineage."""
    fingerprints: dict[str, str] = {}
    for identifier in ("working", "best_known", "active_method"):
        lineage = lineage_role(state, identifier)
        if isinstance(lineage, dict):
            fingerprints[identifier] = str(lineage.get("fingerprint") or "")
    for lineage in state.get("retained_lineages", []):
        if isinstance(lineage, dict) and str(lineage.get("id", "")).strip():
            fingerprints[str(lineage["id"])] = str(lineage.get("fingerprint") or "")
    return fingerprints


def _preparation_entry_matches(entry: dict, fingerprints: dict[str, str]) -> bool:
    """Whether a recorded preparation measurement still describes its lineage.

    A saved-lineage alias can be repointed at a different artifact. Reusing an
    old measurement then would silently misattribute it, so the recorded model
    fingerprint must equal the currently resolved one.
    """
    name = str(entry.get("candidate", "")).strip()
    recorded = entry.get("model_fingerprint")
    if not isinstance(recorded, str) or not recorded:
        metrics = entry.get("metrics")
        recorded = (
            metrics.get("model_fingerprint") if isinstance(metrics, dict) else None
        )
    current = fingerprints.get(name)
    return bool(current) and recorded == current


def preparation_measurement_context(state: dict) -> dict:
    """A lineage-only pending context for a preparation-phase measurement.

    Preparation has no trained experiment, so the requestable models are exactly
    the eligible saved lineages. The context carries the upcoming experiment
    identity so artifact names and recorded rounds stay under it, and an empty
    candidate list so a not-yet-run experiment's candidates cannot be named. The
    accumulated ledger for the same inquiry seeds the round numbers and partial
    ledger so a repeated panel is reused rather than re-executed, but only while
    every recorded model still matches its current lineage.
    """
    experiment = upcoming_experiment_index(state)
    active = require_active_inquiry(state)
    inquiry_id = int(active["id"])
    ledger = preparation_ledger(state)
    rounds: list[dict] = []
    partials: list[dict] = []
    references: list[dict] = []
    ledger_inquiry = int(ledger["inquiry_id"]) if ledger is not None else -1
    if ledger is not None and ledger_inquiry == inquiry_id:
        rounds = [dict(record) for record in ledger.get("rounds") or []]
        fingerprints = _current_lineage_fingerprints(state)
        recorded_partials = list(ledger.get("partial_evaluations") or [])
        recorded_references = list(
            ledger.get("partial_task_reference_evaluations") or []
        )
        partials = [
            entry
            for entry in recorded_partials
            if _preparation_entry_matches(entry, fingerprints)
        ]
        references = [
            entry
            for entry in recorded_references
            if _preparation_entry_matches(entry, fingerprints)
        ]
    return {
        "experiment": experiment,
        "inquiry_id": inquiry_id,
        "candidates": [],
        "champion_available": False,
        "parameters": {},
        "initialization": "fresh",
        "training_budget_steps": 0,
        "parent_training_steps": 0,
        "preparation": True,
        "evaluation_rounds": rounds,
        "partial_evaluations": partials,
        "partial_task_reference_evaluations": references,
        "result": {
            "status": "pending",
            "verdict": "preparation measurement",
            "decision_pending": True,
        },
    }


def planned_measurements(
    request: dict, available: dict
) -> tuple[list[dict], list[dict]]:
    """Resolve all typed measurements before either evaluator starts."""
    validate_evaluation_request(request)
    requested_names = {
        str(spec["candidate"]).strip() for spec in requested_measurements(request)
    }
    omitted_names = set(available) - requested_names
    evaluations: list[dict] = []
    references: list[dict] = []
    for spec in requested_measurements(request):
        name = spec["candidate"].strip()
        if name not in available:
            raise ValueError(
                f"unknown measurement candidate {name!r}; choose from {sorted(available)}"
            )
        omitted_alternative = spec.get("omitted_alternative")
        if omitted_alternative is not None:
            omitted_alternative = omitted_alternative.strip()
            if omitted_alternative not in available:
                raise ValueError(
                    f"unknown omitted_alternative {omitted_alternative!r}; choose "
                    f"from {sorted(omitted_names)}"
                )
            if omitted_alternative in requested_names:
                raise ValueError(
                    f"omitted_alternative {omitted_alternative!r} is also measured "
                    "in this request"
                )
        if spec["instrument"] == "research_evaluation":
            evaluations.append(
                {
                    "candidate": name,
                    "episodes": spec["episodes"],
                    "seed": spec["seed"],
                    "selection": spec["selection"].strip(),
                    "omitted_alternative": omitted_alternative,
                    "label": spec.get(
                        "label", f"requested evaluation {len(evaluations) + 1}: {name}"
                    ),
                }
            )
        else:
            references.append(
                {
                    "candidate": name,
                    "selection": spec["selection"].strip(),
                    "omitted_alternative": omitted_alternative,
                    "label": spec.get(
                        "label", f"task reference {len(references) + 1}: {name}"
                    ),
                }
            )
    return evaluations, references


def resolved_measurement_models(request: dict, available: dict) -> dict[str, dict]:
    """Freeze each requested model name to one artifact and fingerprint."""
    resolved: dict[str, dict] = {}
    names = [
        str(measurement["candidate"]).strip()
        for measurement in requested_measurements(request)
    ]
    for comparison in request.get("paired_comparisons", []):
        names.extend(
            (
                str(comparison["candidate"]).strip(),
                str(comparison["reference"]).strip(),
            )
        )
    for name in names:
        if name in resolved:
            continue
        if name not in available:
            raise ValueError(
                f"unknown measurement model {name!r}; choose from {sorted(available)}"
            )
        contender = available[name]
        artifact = repository.resolve_repo_path(contender["artifact"])
        repository.require_complete_artifact(artifact, f"measurement model {name!r}")
        resolved[name] = {
            "artifact": repository.repo_relative_path(artifact),
            "fingerprint": repository.artifact_fingerprint(artifact),
        }
    return resolved


def validate_paired_comparison_plan(
    request: dict,
    pending: dict,
    available: dict,
    requested: list[dict],
    *,
    state: dict | None = None,
    resolved_models: dict[str, dict] | None = None,
) -> list[dict]:
    """Validate comparison identities that will exist after this request."""
    if state is None:
        raise ValueError("paired comparison validation requires campaign state")
    if resolved_models is None:
        resolved_models = resolved_measurement_models(request, available)
    return _resolved_paired_evidence_plan(
        request, pending, state, requested, resolved_models
    )


def validate_preparation_evaluation_request(
    request: dict,
    state: dict,
    *,
    protected_overlap=None,
) -> dict:
    """Validate a preparation request that may name saved lineages only.

    Preparation has no pending experiment, so the requestable models are the
    eligible saved lineages (``working``, ``best_known``, ``active_method`` or a
    retained ID).
    Naming an experiment's candidate fails as an unknown candidate. The returned
    synthetic context is what execution resolves the request against.
    """
    require_active_inquiry(state)
    if state.get("pending_analysis") is not None:
        raise ValueError(
            "post-training analysis is pending; submit its deliverable instead"
        )
    if state.get("pending_evaluation_request") is not None:
        raise ValueError("a measurement request is already pending")
    if (
        state.get("pending_baseline_decision") is not None
        or state.get("pending_method_decision") is not None
    ):
        raise ValueError("a decision operation is pending; no measurement is accepted")
    if state.get("pending_final_benchmark") is not None:
        raise ValueError("the final benchmark is pending; no measurement is accepted")
    if state.get("pending_inquiry_operation") is not None:
        raise ValueError("an inquiry operation is pending; no measurement is accepted")
    if "experiment" in request:
        raise ValueError(
            "a preparation measurement must omit experiment; it names saved "
            "lineages, not a trained experiment"
        )
    validate_evaluation_request(request)
    pending = preparation_measurement_context(state)
    available = available_evaluation_candidates(pending, state)
    if not available:
        raise ValueError("there are no saved lineages available to measure")
    requested, _ = planned_measurements(request, available)
    resolved_models = resolved_measurement_models(request, available)
    validate_panel_independence(
        request,
        recorded_research_panels(state, pending),
        protected_overlap=protected_overlap,
    )
    validate_paired_comparison_plan(
        request,
        pending,
        available,
        requested,
        state=state,
        resolved_models=resolved_models,
    )
    return pending


# --- measurement identity --------------------------------------------------


def evaluation_artifact_name(
    experiment: int,
    candidate: str,
    episodes: int,
    seed: int,
    semantics: str,
    campaign_id: str | None = None,
) -> str:
    """One stable file per measured panel, so repeated rounds never collide.

    When campaign_id is provided, includes it in the filename to isolate
    artifacts per campaign.
    """
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-") or "candidate"
    if campaign_id:
        return (
            f"evaluation-{campaign_id}-experiment-{experiment}-{label}-"
            f"{episodes}ep-seed{seed}-{semantics}.json"
        )
    return (
        f"evaluation-experiment-{experiment}-{label}-"
        f"{episodes}ep-seed{seed}-{semantics}.json"
    )


def task_reference_artifact_name(
    experiment: int, candidate: str, panel: str, campaign_id: str | None = None
) -> str:
    """Task-reference identity is the model and the human-owned panel, nothing else.

    When campaign_id is provided, includes it in the filename to isolate
    artifacts per campaign.
    """
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", candidate).strip("-") or "candidate"
    if campaign_id:
        return (
            f"task-reference-{campaign_id}-experiment-{experiment}-{label}-{panel}.json"
        )
    return f"task-reference-experiment-{experiment}-{label}-{panel}.json"


def is_generated_path(relative_parts: tuple[str, ...]) -> bool:
    """Tool caches and scratch files are not researcher-owned measurement state."""
    *directories, name = relative_parts
    if any(
        part in GENERATED_DIRECTORY_NAMES or part.startswith(".")
        for part in directories
    ):
        return True
    return name.startswith(".") or name.endswith(GENERATED_FILE_SUFFIXES)


def evaluation_semantics_paths() -> list[str]:
    """Every file that can change how a saved policy is measured.

    The scenario package is scanned in full, so researcher-authored
    instrumentation modules and measurement data files are covered without a
    registry; the protected benchmark constants and metrics are named explicitly
    because they define the success criterion outside that package.
    """
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
    """Identify the files that define what a research measurement means.

    The hashed set is two unions. The non-scenario paths in
    ``EVALUATION_RUNTIME_PATHS`` are mixed-ownership: the researcher-owned
    evaluator alongside protected human-owned inputs such as the policy runtime
    and the benchmark constants and metrics that fix the development success
    criterion and episode geometry. The scenario package is scanned except for
    the files filtered out there - protected, presentation-only, training-only
    and model-contained paths. Paths are hashed with their contents so an added,
    renamed or deleted file changes measurement identity just like an edited
    one.
    """
    digest = hashlib.sha256()
    for relative in evaluation_semantics_paths():
        digest.update(relative.encode("utf-8"))
        digest.update((paths.ROOT / relative).read_bytes())
    return digest.hexdigest()[:12]


# --- lineage evidence ------------------------------------------------------


def pending_evaluation_artifacts(pending: dict) -> list[str]:
    """Every detailed artifact measured for the experiment being resolved."""
    collected: list[str] = []
    for candidate in pending.get("candidates") or []:
        if isinstance(candidate, dict):
            collected.extend(
                repository.evaluation_artifact_paths(candidate.get("evaluations"))
            )
    collected.extend(
        repository.evaluation_artifact_paths(pending.get("champion_evaluations"))
    )
    collected.extend(
        repository.evaluation_artifact_paths(pending.get("task_reference_evaluations"))
    )
    return list(dict.fromkeys(collected))


def postmortem_section(
    experiment: int,
    campaign_id: str | None = None,
) -> str:
    """Return one experiment postmortem within the requested campaign."""
    if not paths.POSTMORTEM_PATH.exists():
        return ""

    heading = (
        rf"^## {re.escape(campaign_id)} / Experiment {experiment}\b"
        if campaign_id
        else rf"^## Experiment {experiment}\b"
    )

    match = re.search(
        heading + r".*?(?=^## |\Z)",
        paths.POSTMORTEM_PATH.read_text(encoding="utf-8"),
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(0) if match else ""


def attested_evidence_paths(section: str) -> list[str]:
    """Artifact paths the researcher recorded as the basis for the decision."""
    listed_paths: list[str] = []
    for line in section.splitlines():
        cleaned = line.replace("*", "").strip().lstrip("-").strip()
        if not cleaned.lower().startswith(EVIDENCE_ATTESTATION_LABEL.lower()):
            continue
        _, _, listed = cleaned.partition(":")
        listed_paths.extend(
            token.strip("`\"',;()[] ")
            for token in re.split(r"[\s,]+", listed)
            if token.strip("`\"',;()[] ")
        )
    return list(dict.fromkeys(listed_paths))


def postmortem_field(section: str, label: str) -> str | None:
    """Return one Researcher-authored labeled field without interpreting it."""
    match = re.search(
        rf"^\*\*{re.escape(label)}:\*\*[ \t]*(.*?)"
        r"(?=^\*\*[^\r\n]+:\*\*|\Z)",
        section,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def validate_postmortem_evidence(
    experiment: int,
    measured: list[str],
    *,
    campaign_id: str | None = None,
    pending: dict | None = None,
    require_hypothesis_assessment: bool = False,
) -> str | None:
    """Require the experiment postmortem and return its hypothesis assessment."""
    section = postmortem_section(experiment, campaign_id)
    if not section.strip():
        identity = (
            f"{campaign_id} / Experiment {experiment}"
            if campaign_id
            else f"Experiment {experiment}"
        )
        raise ValueError(f"postmortems.md has no entry for {identity}")
    assessment = postmortem_field(section, HYPOTHESIS_ASSESSMENT_LABEL)
    if require_hypothesis_assessment and assessment is None:
        raise ValueError(
            f"the experiment {experiment} postmortem needs a non-empty "
            f"'{HYPOTHESIS_ASSESSMENT_LABEL}:' field"
        )
    return assessment


# --- lineage decisions -----------------------------------------------------


def plan_code_lineage_decision(
    pending: dict, action: str, *, current_paths: list[str] | None = None
) -> dict:
    if action == "keep":
        return {"restore": [], "remove_created": []}
    parent = str(pending.get("code_parent_commit", "")).strip()
    if not parent:
        # State written before an experiment recorded a scientific parent.
        return {"restore": [], "remove_created": []}
    # The intervention that was validated and trained, plus everything scientific
    # that happened afterwards. Campaign memory recorded in either set before
    # this boundary existed can still be listed, and rejecting science must never
    # restore history to an older version.
    changed = [
        path
        for path in repository.scientific_change_paths(
            list(
                dict.fromkeys(
                    [
                        *(
                            str(path)
                            for path in pending.get("research_change_paths", [])
                        ),
                        *(current_paths or []),
                    ]
                )
            )
        )
        if is_researcher_owned(path) or path.replace("\\", "/") in PARAMETER_ONLY_PATHS
    ]
    if not changed:
        return {"restore": [], "remove_created": []}
    repository.require_resolvable_commit(parent)
    restorable: list[str] = []
    created: list[Path] = []
    for path in changed:
        candidate = (paths.ROOT / path).resolve()
        if paths.ROOT.resolve() not in candidate.parents:
            raise RuntimeError(f"unsafe research change path: {path}")
        if repository.tracked_at_commit(parent, path):
            restorable.append(path)
        else:
            created.append(candidate)
    return {"restore": restorable, "remove_created": created}


def plan_lineage_restore(lineage: dict) -> dict:
    """Restore all researcher-owned changes between a lineage recipe and now."""
    commit = str(lineage.get("scientific_commit") or "").strip()
    if not commit:
        raise ValueError("restore lineage has no scientific_commit provenance")
    repository.require_resolvable_commit(commit)
    changed = [
        path
        for path in repository.scientific_delta(commit)
        if is_researcher_owned(path) or path.replace("\\", "/") in PARAMETER_ONLY_PATHS
    ]
    restorable: list[str] = []
    created: list[Path] = []
    for path in changed:
        candidate = (paths.ROOT / path).resolve()
        if repository.tracked_at_commit(commit, path):
            restorable.append(path)
        else:
            created.append(candidate)
    return {"parent": commit, "restore": restorable, "remove_created": created}


def next_designation_ordinal(
    existing_best: dict | None, fingerprint: str, counter: int
) -> int:
    """The designation ordinal for a best-known fingerprint.

    Idempotently naming the current fingerprint preserves the ordinal. Any other
    designation, including a return to an earlier fingerprint, starts a new
    tenure and a new ordinal.
    """
    if (
        isinstance(existing_best, dict)
        and existing_best.get("fingerprint") == fingerprint
        and isinstance(existing_best.get("designation_ordinal"), int)
    ):
        return int(existing_best["designation_ordinal"])
    return int(counter) + 1


def designation_counter_for(state: dict) -> int:
    """The highest designation ordinal this campaign has already issued.

    Falls back to the current best-known ordinal so a campaign whose counter was
    never persisted does not reissue ordinal 1 for a new designation.
    """
    existing = state.get("best_known_lineage")
    ordinal = (
        existing.get("designation_ordinal") if isinstance(existing, dict) else None
    )
    recorded = int(state.get("best_known_designation_counter", 0) or 0)
    if isinstance(ordinal, int) and not isinstance(ordinal, bool):
        return max(recorded, ordinal)
    return recorded


def _lineage_sources(pending: dict, state: dict) -> dict[str, dict]:
    sources = {
        item["name"]: {**item, "_current_candidate": True}
        for item in pending["candidates"]
    }
    for identifier in ("working", "best_known", "active_method"):
        lineage = lineage_role(state, identifier)
        if lineage is not None:
            sources[identifier] = {**lineage, "name": identifier}
    for lineage in state.get("retained_lineages", []):
        sources[str(lineage["id"])] = {**lineage, "name": str(lineage["id"])}
    return sources


def _selection_panel_identity(entry: dict, instrument: str) -> dict | None:
    """The instrument-preserving identity of a panel a model was measured on."""
    if instrument == "task_reference":
        panel = entry.get("panel")
        if not isinstance(panel, str) or not panel.strip():
            return None
        identity: dict = {"instrument": "task_reference", "panel": panel}
        for field in ("panel_version", "seed", "episodes"):
            value = entry.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                identity[field] = value
        return identity
    seed = entry.get("seed")
    episodes = entry.get("episodes")
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        return None
    return {"instrument": "research_evaluation", "seed": seed, "episodes": episodes}


def _selection_panel_key(identity: dict) -> tuple:
    return tuple(sorted(identity.items()))


def _normalized_selection_panel(item: object) -> dict | None:
    """Accept an instrument-preserving panel identity object."""
    if isinstance(item, dict):
        instrument = item.get("instrument")
        if instrument == "task_reference":
            panel = item.get("panel")
            if not isinstance(panel, str) or not panel.strip():
                return None
            identity: dict = {"instrument": "task_reference", "panel": panel}
            for field in ("panel_version", "seed", "episodes"):
                value = item.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    identity[field] = value
            return identity
        if instrument == "research_evaluation":
            seed = item.get("seed")
            episodes = item.get("episodes")
            if isinstance(seed, bool) or not isinstance(seed, int):
                return None
            if isinstance(episodes, bool) or not isinstance(episodes, int):
                return None
            return {
                "instrument": "research_evaluation",
                "seed": seed,
                "episodes": episodes,
            }
    return None


def _selection_panels_for(source: dict, pending: dict, fingerprint: str) -> list[dict]:
    """The panels a newly selected lineage was measured on.

    Issue #57: a lineage selected on a panel's episodes is not independently
    confirmed by re-measuring those same episodes. The identity of every panel the
    model was measured on in this experiment is recorded on the lineage so the
    brief can surface its selection exposure. Both instruments covered by the
    contract are recorded, and the representation preserves the instrument and the
    panel identity. Panels already recorded on a carried-over lineage are
    preserved.
    """
    panels: list[dict] = []
    seen: set[tuple] = set()
    for item in source.get("selected_panels") or []:
        normalized = _normalized_selection_panel(item)
        if normalized is None:
            continue
        key = _selection_panel_key(normalized)
        if key not in seen:
            seen.add(key)
            panels.append(normalized)
    for instrument, keys in (
        (
            "research_evaluation",
            (
                "requested_evaluations",
                "partial_evaluations",
                "preparation_evaluations",
            ),
        ),
        (
            "task_reference",
            (
                "task_reference_evaluations",
                "partial_task_reference_evaluations",
                "preparation_task_reference_evaluations",
            ),
        ),
    ):
        for key in keys:
            for entry in pending.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                if entry.get("instrument", instrument) != instrument:
                    continue
                metrics = (
                    entry.get("metrics")
                    if isinstance(entry.get("metrics"), dict)
                    else {}
                )
                merged = {**metrics, **entry}
                entry_fingerprint = merged.get("model_fingerprint")
                if (
                    fingerprint
                    and entry_fingerprint
                    and str(entry_fingerprint) != str(fingerprint)
                ):
                    continue
                identity = _selection_panel_identity(merged, instrument)
                if identity is None:
                    continue
                identity_key = _selection_panel_key(identity)
                if identity_key in seen:
                    continue
                seen.add(identity_key)
                panels.append(identity)
    return panels


def _lineage_record(source: dict, pending: dict, artifact: Path, reason: str) -> dict:
    current = bool(source.get("_current_candidate"))
    checkpoint_steps = int(source.get("timesteps", source.get("training_steps", 0)))
    steps = (
        int(pending.get("parent_training_steps", 0)) + checkpoint_steps
        if current and pending.get("initialization") == "transfer"
        else checkpoint_steps
    )
    fingerprint = repository.artifact_fingerprint(artifact)
    return {
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": fingerprint,
        "origin_experiment": int(pending["experiment"])
        if current
        else int(source["origin_experiment"]),
        "candidate": str(
            source.get("candidate")
            if not current and source.get("candidate") is not None
            else source.get("name", source.get("candidate"))
        ),
        "parameters": source.get("parameters", pending["parameters"]),
        "scientific_commit": source.get("scientific_commit")
        or pending.get("scientific_commit"),
        "training_steps": steps,
        "evaluation_artifacts": repository.evaluation_artifact_paths(
            source.get("evaluations")
        )
        if current
        else list(source.get("evaluation_artifacts", [])),
        "selected_panels": _selection_panels_for(source, pending, fingerprint),
        "reason": reason,
    }


def _artifact_publications(
    state: dict,
    working_record: dict | None,
    best_known_record: dict | None,
    retained: list[dict],
    method_record: dict | None = None,
) -> list[dict]:
    """Freeze complete durable-artifact work before closure mutation begins."""
    campaign_id = repository.current_campaign_id(state)
    records = []
    if working_record is not None:
        records.append(("working", working_record))
    if best_known_record is not None:
        records.append(("best_known", best_known_record))
    if method_record is not None:
        records.append(("active_method", method_record))
    records.extend((f"retained:{item['id']}", item) for item in retained)
    grouped: dict[str, list[tuple[str, dict, Path]]] = {}
    for role, record in records:
        source = repository.resolve_repo_path(record["artifact"])
        fingerprint = str(record["fingerprint"])
        repository.require_complete_inference_artifact(source, f"{role} lineage")
        if repository.artifact_fingerprint(source) != fingerprint:
            raise ValueError(f"{role} lineage fingerprint does not match its artifact")
        grouped.setdefault(fingerprint, []).append((role, record, source))

    publications: list[dict] = []
    for fingerprint, aliases in grouped.items():
        durable_alias = next(
            (
                alias
                for alias in aliases
                if repository.repo_relative_path(alias[2]).startswith(
                    (
                        "research/checkpoints/accepted/",
                        "research/checkpoints/retained/",
                    )
                )
            ),
            None,
        )
        if durable_alias is not None:
            destination = repository.repo_relative_path(durable_alias[2])
            for _, record, _ in aliases:
                record["artifact"] = destination
            continue

        _, source_record, source = aliases[0]
        destination = repository.durable_artifact_destination(
            campaign_id=campaign_id,
            origin_experiment=int(source_record["origin_experiment"]),
            candidate=str(source_record["candidate"]),
            fingerprint=fingerprint,
        )
        publication = {
            "source": repository.repo_relative_path(source),
            "destination": repository.repo_relative_path(destination),
            "fingerprint": fingerprint,
            "resulting_records": {},
        }
        for role, record, _ in aliases:
            record["artifact"] = publication["destination"]
            publication["resulting_records"][role] = record
        repository.validate_artifact_publication(publication)
        publications.append(publication)
    return publications


def _development_evidence_catalog(pending: dict, state: dict) -> dict[str, dict]:
    catalog: dict[str, dict] = {}

    def add(path: str, record: dict) -> None:
        canonical_path = repository.canonical_repo_path(path)
        record["evaluation_artifact"] = canonical_path
        existing = catalog.get(canonical_path)
        if existing is not None and existing != record:
            raise ValueError(
                f"conflicting measurement metadata for evidence artifact: "
                f"{canonical_path}"
            )
        catalog[canonical_path] = record

    campaign_id = repository.current_campaign_id(state)
    sources = [
        *repository.history_records_for_campaign(campaign_id),
        pending,
    ]
    for source in sources:
        research_evaluations = [
            *(source.get("requested_evaluations") or []),
            *(source.get("partial_evaluations") or []),
            *(source.get("preparation_evaluations") or []),
        ]
        for evaluation in research_evaluations:
            if not isinstance(evaluation, dict):
                continue
            metrics = evaluation.get("metrics")
            if not isinstance(metrics, dict):
                metrics = evaluation
            path = metrics.get("evaluation_artifact")
            if not isinstance(path, str) or not path.strip():
                continue
            add(
                path,
                {
                    "instrument": "research_evaluation",
                    "model_fingerprint": evaluation.get("model_fingerprint")
                    or metrics.get("model_fingerprint"),
                    "evaluation_artifact_fingerprint": evaluation.get(
                        "evaluation_artifact_fingerprint"
                    )
                    or metrics.get("evaluation_artifact_fingerprint"),
                    "settings": (
                        "research_evaluation",
                        int(evaluation.get("episodes", metrics.get("episodes", -1))),
                        int(evaluation.get("seed", metrics.get("seed", -1))),
                        str(
                            evaluation.get(
                                "evaluation_semantics",
                                metrics.get("evaluation_semantics", ""),
                            )
                        ),
                    ),
                },
            )
        reference_evaluations = [
            *(source.get("task_reference_evaluations") or []),
            *(source.get("partial_task_reference_evaluations") or []),
            *(source.get("preparation_task_reference_evaluations") or []),
        ]
        for evaluation in reference_evaluations:
            if not isinstance(evaluation, dict):
                continue
            path = evaluation.get("evaluation_artifact")
            if not isinstance(path, str) or not path.strip():
                continue
            add(
                path,
                {
                    "instrument": "task_reference",
                    "model_fingerprint": evaluation.get("model_fingerprint"),
                    "evaluation_artifact_fingerprint": evaluation.get(
                        "evaluation_artifact_fingerprint"
                    ),
                    "settings": (
                        "task_reference",
                        str(evaluation.get("panel", "")),
                        int(evaluation.get("panel_version", -1)),
                        int(evaluation.get("episodes", -1)),
                        int(evaluation.get("seed", -1)),
                    ),
                },
            )
    return catalog


def _validated_historical_panel_records(
    records: list[dict], settings: tuple
) -> list[dict]:
    """Validate detailed historical panels and collapse byte-identical copies."""
    validated: list[dict] = []
    fingerprints: set[str] = set()
    expected_outcomes: dict[tuple[int, int], bool] | None = None
    for record in records:
        if record.get("planned"):
            validated.append(record)
            continue
        path = record["evaluation_artifact"]
        artifact = repository.resolve_repo_path(path)
        content_fingerprint = repository.file_fingerprint(artifact)
        frozen_fingerprint = record.get("evaluation_artifact_fingerprint")
        if frozen_fingerprint and frozen_fingerprint != content_fingerprint:
            raise ValueError(
                f"historical evidence content changed after measurement: {path}"
            )
        try:
            measurement = json.loads(artifact.read_text(encoding="utf-8"))
            episode_results = measurement["episode_results"]
            identified_outcomes = [
                (
                    (int(item["episode"]), int(item["episode_seed"])),
                    bool(item["success"]),
                )
                for item in episode_results
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"historical evidence has invalid detailed episode identities: {path}"
            ) from error
        outcomes = dict(identified_outcomes)
        if len(outcomes) != len(identified_outcomes):
            raise ValueError(f"historical evidence repeats an episode identity: {path}")
        if (
            int(measurement.get("episodes", -1)) != int(settings[1])
            or int(measurement.get("seed", -1)) != int(settings[2])
            or len(outcomes) != int(settings[1])
        ):
            raise ValueError(
                f"historical evidence panel metadata is inconsistent: {path}"
            )
        if expected_outcomes is not None and outcomes != expected_outcomes:
            raise ValueError(
                f"conflicting deterministic measurements for historical panel "
                f"seed {settings[2]}: {[item['evaluation_artifact'] for item in records]}"
            )
        expected_outcomes = outcomes
        if content_fingerprint in fingerprints:
            continue
        fingerprints.add(content_fingerprint)
        validated.append(
            {
                **record,
                "content_fingerprint": content_fingerprint,
                "episode_identities": sorted(outcomes),
            }
        )
    return validated


def _evidence_records_compatible(candidate: dict, reference: dict) -> bool:
    if candidate["instrument"] != reference["instrument"]:
        return False
    candidate_settings = candidate["settings"]
    reference_settings = reference["settings"]
    if candidate["instrument"] == "task_reference":
        return candidate_settings == reference_settings
    if candidate["instrument"] != "research_evaluation":
        return False
    if candidate_settings[3] != reference_settings[3]:
        return False
    return bool(_record_episode_seeds(candidate) & _record_episode_seeds(reference))


def _record_episode_seeds(record: dict) -> set[int]:
    identities = record.get("episode_identities")
    if identities is not None:
        return {int(identity[1]) for identity in identities}
    _, episodes, seed, _ = record["settings"]
    return set(range(int(seed), int(seed) + int(episodes)))


def _compatible_primary_panels(
    candidate_records: list[dict], reference_records: list[dict]
) -> list[tuple[tuple[tuple, tuple], list[dict], list[dict]]]:
    candidate_groups: dict[tuple, list[dict]] = {}
    reference_groups: dict[tuple, list[dict]] = {}
    for record in candidate_records:
        candidate_groups.setdefault(record["settings"], []).append(record)
    for record in reference_records:
        reference_groups.setdefault(record["settings"], []).append(record)
    panels = []
    for candidate_settings, candidate_panel in candidate_groups.items():
        for reference_settings, reference_panel in reference_groups.items():
            if not _evidence_records_compatible(candidate_panel[0], reference_panel[0]):
                continue
            panels.append(
                (
                    (candidate_settings, reference_settings),
                    candidate_panel,
                    reference_panel,
                )
            )
    return sorted(panels, key=lambda item: str(item[0]))


def _resolved_paired_evidence_plan(
    request: dict,
    pending: dict,
    state: dict,
    requested: list[dict],
    resolved_models: dict[str, dict],
) -> list[dict]:
    """Resolve comparisons to immutable models and exact evidence artifacts."""
    catalog = _development_evidence_catalog(pending, state)
    semantics = evaluation_semantics_fingerprint()
    campaign_id = repository.current_campaign_id(state)
    experiment = int(pending["experiment"])
    for measurement in requested:
        name = measurement["candidate"]
        path = paths.campaign_evaluation_dir(campaign_id) / evaluation_artifact_name(
            experiment,
            name,
            measurement["episodes"],
            measurement["seed"],
            semantics,
            campaign_id=campaign_id,
        )
        canonical_path = repository.repo_relative_path(path)
        planned_record = {
            "instrument": "research_evaluation",
            "model_fingerprint": resolved_models[name]["fingerprint"],
            "evaluation_artifact": canonical_path,
            "planned": True,
            "settings": (
                "research_evaluation",
                int(measurement["episodes"]),
                int(measurement["seed"]),
                semantics,
            ),
            "episode_identities": [
                (episode, int(measurement["seed"]) + episode)
                for episode in range(int(measurement["episodes"]))
            ],
        }
        existing = catalog.get(canonical_path)
        if existing is None:
            catalog[canonical_path] = planned_record
        elif any(
            existing[key] != planned_record[key]
            for key in ("instrument", "model_fingerprint", "settings")
        ):
            raise ValueError(
                f"planned measurement conflicts with existing evidence metadata: "
                f"{canonical_path}"
            )

    plan: list[dict] = []
    for comparison in request.get("paired_comparisons", []):
        candidate = str(comparison["candidate"]).strip()
        reference = str(comparison["reference"]).strip()
        candidate_fingerprint = resolved_models[candidate]["fingerprint"]
        reference_fingerprint = resolved_models[reference]["fingerprint"]
        candidate_records = [
            record
            for record in catalog.values()
            if record["instrument"] == "research_evaluation"
            and record["model_fingerprint"] == candidate_fingerprint
        ]
        reference_records = [
            record
            for record in catalog.values()
            if record["instrument"] == "research_evaluation"
            and record["model_fingerprint"] == reference_fingerprint
        ]
        for record in [*candidate_records, *reference_records]:
            if (
                not record.get("planned")
                and not repository.resolve_repo_path(
                    record["evaluation_artifact"]
                ).is_file()
            ):
                raise ValueError(
                    "paired comparison evidence artifact does not exist: "
                    f"{record['evaluation_artifact']}"
                )
        if not candidate_records or not reference_records:
            missing = candidate if not candidate_records else reference
            missing_fingerprint = (
                candidate_fingerprint
                if not candidate_records
                else reference_fingerprint
            )
            missing_source = available_evaluation_candidates(pending, state)[missing]
            associated_paths = set(
                repository.evaluation_artifact_paths(missing_source.get("evaluations"))
            ) | {
                repository.canonical_repo_path(str(path))
                for path in missing_source.get("evaluation_artifacts", [])
            }
            associated_records = [
                catalog[path]
                for path in associated_paths
                if path in catalog
                and catalog[path]["instrument"] == "research_evaluation"
            ]
            unverifiable = [
                record["evaluation_artifact"]
                for record in associated_records
                if not record["model_fingerprint"]
            ]
            mismatched = [
                (
                    record["evaluation_artifact"],
                    record["model_fingerprint"],
                )
                for record in associated_records
                if record["model_fingerprint"]
                and record["model_fingerprint"] != missing_fingerprint
            ]
            if unverifiable:
                raise ValueError(
                    f"paired comparison evidence for {missing!r} lacks model "
                    f"identity metadata: {sorted(unverifiable)}"
                )
            if mismatched:
                raise ValueError(
                    f"paired comparison evidence for {missing!r} has a true "
                    f"fingerprint mismatch; expected {missing_fingerprint}, "
                    f"found {sorted(mismatched)}"
                )
            raise ValueError(
                f"paired comparison {candidate!r} vs {reference!r} has no "
                f"fingerprint-bound research-evaluation evidence for {missing!r}"
            )
        compatible_panels = _compatible_primary_panels(
            candidate_records, reference_records
        )
        if not compatible_panels:
            candidate_contexts = sorted(
                (record["evaluation_artifact"], record["settings"])
                for record in candidate_records
            )
            reference_contexts = sorted(
                (record["evaluation_artifact"], record["settings"])
                for record in reference_records
            )
            raise ValueError(
                f"paired comparison {candidate!r} vs {reference!r} has no compatible "
                "research-evaluation semantics and panel settings; "
                f"candidate contexts: {candidate_contexts}; "
                f"reference contexts: {reference_contexts}"
            )
        panels = []
        for settings, candidate_panel, reference_panel in compatible_panels:
            candidate_settings, reference_settings = settings
            panel_candidate_records = _validated_historical_panel_records(
                candidate_panel,
                candidate_settings[:3],
            )
            panel_reference_records = _validated_historical_panel_records(
                reference_panel,
                reference_settings[:3],
            )
            candidate_episode_seeds = set.intersection(
                *(_record_episode_seeds(record) for record in panel_candidate_records)
            )
            reference_episode_seeds = set.intersection(
                *(_record_episode_seeds(record) for record in panel_reference_records)
            )
            shared_episode_seeds = sorted(
                candidate_episode_seeds & reference_episode_seeds
            )
            if not shared_episode_seeds:
                raise ValueError(
                    f"paired comparison {candidate!r} vs {reference!r} has "
                    "no shared historical episode identities"
                )
            candidate_paths = sorted(
                record["evaluation_artifact"] for record in panel_candidate_records
            )
            reference_paths = sorted(
                record["evaluation_artifact"] for record in panel_reference_records
            )
            panels.append(
                {
                    "instrument": candidate_settings[0],
                    "episodes": len(shared_episode_seeds),
                    "seed": candidate_settings[2],
                    "evaluation_semantics": candidate_settings[3],
                    "candidate_episodes": candidate_settings[1],
                    "candidate_seed": candidate_settings[2],
                    "reference_episodes": reference_settings[1],
                    "reference_seed": reference_settings[2],
                    "shared_episode_seeds": shared_episode_seeds,
                    "candidate_artifacts": candidate_paths,
                    "candidate_artifact_fingerprints": {
                        path: repository.file_fingerprint(
                            repository.resolve_repo_path(path)
                        )
                        for path in candidate_paths
                        if repository.resolve_repo_path(path).is_file()
                    },
                    "reference_artifacts": reference_paths,
                    "reference_artifact_fingerprints": {
                        path: repository.file_fingerprint(
                            repository.resolve_repo_path(path)
                        )
                        for path in reference_paths
                        if repository.resolve_repo_path(path).is_file()
                    },
                }
            )
        plan.append(
            {
                "candidate": candidate,
                "reference": reference,
                "candidate_model_fingerprint": candidate_fingerprint,
                "reference_model_fingerprint": reference_fingerprint,
                "panels": panels,
            }
        )
    return plan


def _fully_frozen_paired_panel(panel: dict) -> bool:
    for side in ("candidate", "reference"):
        artifacts = panel.get(f"{side}_artifacts")
        fingerprints = panel.get(f"{side}_artifact_fingerprints")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        if not isinstance(fingerprints, dict) or any(
            path not in fingerprints for path in artifacts
        ):
            return False
    return True


def refresh_repaired_paired_evidence_plan(
    request: dict,
    pending: dict,
    state: dict,
    requested: list[dict],
    resolved_models: dict[str, dict],
    evidence_plan: list[dict],
) -> list[dict]:
    """Rebind only provisional panels after repaired evaluation semantics change."""
    current_semantics = evaluation_semantics_fingerprint()
    stale = any(
        not _fully_frozen_paired_panel(panel)
        and panel.get("evaluation_semantics") != current_semantics
        for comparison in evidence_plan
        for panel in comparison.get("panels", [])
    )
    if not stale:
        return evidence_plan

    campaign_id = repository.current_campaign_id(state)
    experiment = int(pending["experiment"])
    expected_paths = {
        (
            measurement["candidate"],
            int(measurement["episodes"]),
            int(measurement["seed"]),
        ): repository.repo_relative_path(
            paths.campaign_evaluation_dir(campaign_id)
            / evaluation_artifact_name(
                experiment,
                measurement["candidate"],
                measurement["episodes"],
                measurement["seed"],
                current_semantics,
                campaign_id=campaign_id,
            )
        )
        for measurement in requested
    }
    refreshed = _resolved_paired_evidence_plan(
        request, pending, state, requested, resolved_models
    )
    refreshed_by_identity = {
        (comparison["candidate"], comparison["reference"]): comparison
        for comparison in refreshed
    }
    rebound_plan: list[dict] = []
    for comparison in evidence_plan:
        identity = (comparison["candidate"], comparison["reference"])
        replacement = refreshed_by_identity.get(identity)
        if replacement is None:
            raise ValueError(
                "implementation repair left an accepted paired comparison "
                f"without executable evidence: {identity[0]!r} vs {identity[1]!r}"
            )
        for key in ("candidate_model_fingerprint", "reference_model_fingerprint"):
            if comparison.get(key) != replacement.get(key):
                raise ValueError(
                    "implementation repair changed a paired comparison model identity"
                )
        panels: list[dict] = []
        replacement_panels = replacement.get("panels", [])
        for panel in comparison.get("panels", []):
            if _fully_frozen_paired_panel(panel):
                panels.append(copy.deepcopy(panel))
                continue
            matched = next(
                (
                    candidate
                    for candidate in replacement_panels
                    if candidate.get("instrument") == panel.get("instrument")
                    and candidate.get("seed") == panel.get("seed")
                    and candidate.get("candidate_episodes")
                    == panel.get("candidate_episodes")
                    and candidate.get("candidate_seed") == panel.get("candidate_seed")
                    and candidate.get("reference_episodes")
                    == panel.get("reference_episodes")
                    and candidate.get("reference_seed") == panel.get("reference_seed")
                    and candidate.get("evaluation_semantics") == current_semantics
                ),
                None,
            )
            if matched is None:
                raise ValueError(
                    "implementation repair changed evaluation semantics, but the "
                    "accepted request cannot recreate both sides of paired panel "
                    f"seed {panel.get('seed')}"
                )
            candidate_path = expected_paths.get(
                (
                    identity[0],
                    int(panel.get("candidate_episodes", -1)),
                    int(panel.get("candidate_seed", -1)),
                )
            )
            reference_path = expected_paths.get(
                (
                    identity[1],
                    int(panel.get("reference_episodes", -1)),
                    int(panel.get("reference_seed", -1)),
                )
            )
            if candidate_path not in matched.get(
                "candidate_artifacts", []
            ) or reference_path not in matched.get("reference_artifacts", []):
                raise ValueError(
                    "implementation repair changed evaluation semantics, but the "
                    "accepted request does not measure both sides of paired panel "
                    f"seed {panel.get('seed')}"
                )
            rebound_panel = copy.deepcopy(matched)
            for side, path in (
                ("candidate", candidate_path),
                ("reference", reference_path),
            ):
                fingerprints = matched.get(f"{side}_artifact_fingerprints", {})
                rebound_panel[f"{side}_artifacts"] = [path]
                rebound_panel[f"{side}_artifact_fingerprints"] = (
                    {path: fingerprints[path]} if path in fingerprints else {}
                )
            panels.append(rebound_panel)
        rebound = copy.deepcopy(comparison)
        rebound["panels"] = panels
        rebound_plan.append(rebound)
    return rebound_plan


def _validated_designation_evidence(
    paths: set[str],
    *,
    expected_fingerprint: str,
    catalog: dict[str, dict],
    description: str,
) -> list[dict]:
    records: list[dict] = []
    for path in paths:
        record = catalog.get(path)
        if record is None:
            raise ValueError(
                f"{description} evidence has unavailable measurement provenance: {path}"
            )
        if not record["model_fingerprint"]:
            raise ValueError(
                f"{description} evidence lacks model identity metadata: {path}"
            )
        if record["model_fingerprint"] != expected_fingerprint:
            raise ValueError(
                f"{description} evidence fingerprint does not match the selected "
                f"model: {path}"
            )
        artifact = repository.resolve_repo_path(path)
        if not artifact.is_file():
            raise ValueError(f"{description} evidence does not exist: {path}")
        evidence_fingerprint = record.get("evaluation_artifact_fingerprint")
        if not evidence_fingerprint:
            raise ValueError(
                f"{description} evidence lacks immutable file identity: {path}"
            )
        if repository.file_fingerprint(artifact) != evidence_fingerprint:
            raise ValueError(
                f"{description} evidence content changed after measurement: {path}"
            )
        settings = record["settings"]
        if (
            record["instrument"] == "research_evaluation"
            and (settings[1] < 1 or settings[2] < 0 or not settings[3])
        ) or (
            record["instrument"] == "task_reference"
            and (
                not settings[1] or settings[2] < 1 or settings[3] < 1 or settings[4] < 0
            )
        ):
            raise ValueError(
                f"{description} evidence has incomplete panel metadata: {path}"
            )
        records.append(record)
    return records


def _code_decision_plan(
    decision: dict, pending: dict, state: dict, sources: dict[str, dict]
) -> tuple[str, str, dict]:
    code = decision.get("code")
    if not isinstance(code, dict):
        raise TypeError("code decision requires action and reason")
    action = str(code.get("action", "")).strip().lower()
    reason = str(code.get("reason", "")).strip()
    allowed = (
        {"action", "reason", "lineage"}
        if action == "restore"
        else {
            "action",
            "reason",
        }
    )
    if (
        action not in {"keep", "revert", "restore"}
        or not reason
        or set(code) != allowed
    ):
        raise ValueError(
            "code decision must be keep or revert with action and reason, or "
            "restore with action, reason, and lineage"
        )
    parent = str(pending.get("code_parent_commit", "")).strip()
    if action == "restore":
        lineage_name = str(code.get("lineage", "")).strip()
        source = sources.get(lineage_name)
        if source is None:
            raise ValueError(f"code restore lineage must be one of {sorted(sources)}")
        plan = plan_lineage_restore(source)
        plan["lineage"] = lineage_name
    else:
        plan = plan_code_lineage_decision(
            pending,
            action,
            current_paths=(
                repository.scientific_delta(parent)
                if parent and action == "revert"
                else None
            ),
        )
        plan["parent"] = parent
    return action, reason, plan


def _selected_record(
    *,
    name: str,
    reason: str,
    sources: dict[str, dict],
    pending: dict,
    description: str,
) -> dict:
    if name not in sources or not reason:
        raise ValueError(
            f"{description} must name one of {sorted(sources)} with a reason"
        )
    source = sources[name]
    artifact = repository.resolve_repo_path(source["artifact"])
    repository.require_complete_inference_artifact(artifact, description)
    return _lineage_record(source, pending, artifact, reason)


def _require_measured_designation(
    record: dict, pending: dict, state: dict, description: str
) -> None:
    catalog = _development_evidence_catalog(pending, state)
    fingerprint = str(record["fingerprint"])
    matching = {
        path
        for path, evidence in catalog.items()
        if evidence["model_fingerprint"] == fingerprint
    }
    if not matching:
        raise ValueError(f"{description} has no recorded campaign measurement")
    validated = _validated_designation_evidence(
        matching,
        expected_fingerprint=fingerprint,
        catalog=catalog,
        description=description,
    )
    record["evaluation_artifacts"] = sorted(
        set(record["evaluation_artifacts"])
        | {item["evaluation_artifact"] for item in validated}
    )


def _require_paired_promotion_evidence(
    selected_name: str,
    selected_record: dict,
    pending: dict,
    state: dict,
) -> None:
    working = state.get("working_lineage")
    if not isinstance(working, dict):
        raise TypeError("method promotion requires a current working lineage")
    if selected_record["fingerprint"] == working.get("fingerprint"):
        raise ValueError(
            "method promotion must compare a distinct model against working"
        )
    request = {
        "paired_comparisons": [{"candidate": selected_name, "reference": "working"}]
    }
    available = available_evaluation_candidates(pending, state)
    resolved = {}
    for name in (selected_name, "working"):
        source = available[name]
        artifact = repository.resolve_repo_path(source["artifact"])
        repository.require_complete_artifact(
            artifact, f"promotion evidence model {name!r}"
        )
        resolved[name] = {
            "artifact": repository.repo_relative_path(artifact),
            "fingerprint": repository.artifact_fingerprint(artifact),
        }
    if resolved[selected_name]["fingerprint"] != selected_record["fingerprint"]:
        raise ValueError("promoted method candidate identity changed")
    plan = validate_paired_comparison_plan(
        request,
        pending,
        available,
        [],
        state=state,
        resolved_models=resolved,
    )
    if not plan:
        raise ValueError(
            "method promotion requires compatible paired evidence against working"
        )


def plan_baseline_decision(proposal: dict, state: dict) -> dict:
    """Select the measured baseline before the first inquiry can open."""
    pending = state.get("pending_analysis")
    if not isinstance(pending, dict) or not pending.get("baseline"):
        raise ValueError("there is no baseline awaiting selection")
    decision = proposal.get("baseline_decision")
    if not isinstance(decision, dict):
        raise TypeError("baseline_decision must be an object")
    if set(decision) != {"experiment", "candidate", "reason"}:
        raise ValueError(
            "baseline_decision requires exactly experiment, candidate, and reason"
        )
    if int(decision.get("experiment", -1)) != int(pending["experiment"]):
        raise ValueError("baseline_decision references the wrong experiment")
    sources = {
        item["name"]: {**item, "_current_candidate": True}
        for item in pending["candidates"]
    }
    candidate = str(decision.get("candidate", "")).strip()
    reason = str(decision.get("reason", "")).strip()
    record = _selected_record(
        name=candidate,
        reason=reason,
        sources=sources,
        pending=pending,
        description="selected baseline",
    )
    _require_measured_designation(record, pending, state, "selected baseline")
    record["designation_ordinal"] = 1
    publications = _artifact_publications(
        state,
        record,
        copy.deepcopy(record),
        list(state.get("retained_lineages", [])),
    )
    return {
        "kind": "baseline",
        "pending": pending,
        "decision": decision,
        "working_name": candidate,
        "working_record": record,
        "best_known_name": candidate,
        "best_known_record": copy.deepcopy(record),
        "active_method": None,
        "released_method_lineage": None,
        "retained": list(state.get("retained_lineages", [])),
        "removed_retained": [],
        "artifact_publications": publications,
        "code_action": "keep",
        "code_reason": "Preserve the unchanged baseline recipe.",
        "code_plan": {
            "parent": str(pending.get("code_parent_commit", "")).strip(),
            "restore": [],
            "remove_created": [],
        },
        "designation_counter": 1,
    }
