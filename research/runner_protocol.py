"""Protocol decisions and validation for the Runner.

Everything here answers "is this admissible, and what would it mean?" without
performing the destructive part of the answer. The `plan_*` operations resolve
a complete decision that `run_experiment` and `runner_repository` then apply.
"""

import hashlib
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
    "robot_learning/benchmark/__init__.py",
    "robot_learning/benchmark/final_benchmark.py",
    "robot_learning/benchmark/final_contract.py",
    "robot_learning/benchmark/reference_contract.py",
    "robot_learning/benchmark/reference_evaluation.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/final_benchmark.py",
    "robot_learning/scenario/task_reference.py",
}
# Additional Runner instruments are protected even when they do not belong to
# the official-task trust path.
PROTECTED_RUNNER_PATHS = {
    "research/migrate_policy_runtime.py",
    "research/build_research_brief.py",
    "research/query_training_log.py",
    "researcher_session.ps1",
    "run_research.ps1",
}
# The researcher runtime boundary: it decides which tools and commands a
# research session may use, so a proposal must not be able to widen its own.
PROTECTED_RUNTIME_PATHS = {"researcher_copilot.py"}
# Human-owned context defines the Researcher's protocol, permissions and task.
PROTECTED_CONTEXT_PATHS = {
    "AGENTS.md",
    "research/instruments.md",
    "research/program.md",
    "research/scenario.md",
}
# The rest of the enforcement mechanism, protected by prefix so that adding a
# Runner module never silently hands part of the protocol to the researcher.
PROTECTED_RUNNER_PREFIXES = ("research/runner_",)
# Human-owned test domains. Prefix-based so that creating, renaming or deleting
# a file underneath them is rejected just like modifying an existing one.
PROTECTED_TEST_PREFIXES = (
    "tests/benchmark/",
    "tests/autoresearch/",
)
VALIDATED_TEST_PATHS = (
    "tests/benchmark",
    "tests/autoresearch",
    "tests/scenario",
    "tests/training",
)
# A researcher code change cannot alter the frozen task, so `tests/benchmark`
# adds nothing; every other suite still guards code the researcher may rewrite.
RESEARCHER_VALIDATED_TEST_PATHS = (
    "tests/scenario",
    "tests/training",
    "tests/autoresearch/test_scenario_boundary.py",
    "tests/autoresearch/test_campaign_boundary.py",
)
# The researcher-owned scientific surface, stated positively. Anything absent
# here is unclassified and validated completely, so a new or unfamiliar path is
# never assumed mutable.
RESEARCHER_OWNED_PREFIXES = (
    "robot_learning/scenario/",
    "robot_learning/training/",
    "tests/scenario/",
    "tests/training/",
)
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
# The only files outside the scenario package that change how an already-trained
# policy is replayed, observed and turned into a research measurement.
EVALUATION_RUNTIME_PATHS = (
    "robot_learning/policy_runtime.py",
    "robot_learning/evaluate.py",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
)
GENERATED_FILE_SUFFIXES = (".pyc", ".pyo", ".tmp")
GENERATED_DIRECTORY_NAMES = {"__pycache__"}
# The one line a lineage decision must carry to name the evidence it relied on.
EVIDENCE_ATTESTATION_LABEL = "Evidence inspected"
# The researcher names the model; the panel behind this key is human-owned.
RESEARCH_EVALUATION_ENTRY_FIELDS = {
    "instrument",
    "candidate",
    "episodes",
    "seed",
    "label",
}
TASK_REFERENCE_ENTRY_FIELDS = {"instrument", "candidate", "label"}
SUPPORTED_MEASUREMENT_INSTRUMENTS = {
    "research_evaluation",
    "task_reference",
}


# --- ownership -------------------------------------------------------------


def is_protected_source(path: str) -> bool:
    relative = path.replace("\\", "/")
    return (
        relative in PROTECTED_BENCHMARK_PATHS
        or relative in PROTECTED_RUNNER_PATHS
        or relative in PROTECTED_RUNTIME_PATHS
        or relative in PROTECTED_CONTEXT_PATHS
        or relative in DEPENDENCY_METADATA_PATHS
        or relative.startswith(PROTECTED_RUNNER_PREFIXES)
    )


def is_researcher_owned(path: str) -> bool:
    """Protected paths lose first, so sharing a researcher prefix never frees them."""
    relative = path.replace("\\", "/")
    if is_protected_source(relative):
        return False
    if relative.startswith(PROTECTED_TEST_PREFIXES):
        return False
    return relative in RESEARCHER_OWNED_PATHS or relative.startswith(
        RESEARCHER_OWNED_PREFIXES
    )


def validation_test_paths(
    changed_paths: list[str], *, fresh_baseline: bool
) -> tuple[str, ...]:
    """A fresh campaign baseline is validated completely before it consumes
    training compute, even when the committed worktree carries no research
    change. Afterwards the suites follow ownership: a change confined to the
    researcher's own scientific surface skips only the frozen task tests."""
    if fresh_baseline:
        return VALIDATED_TEST_PATHS
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
        # Backward compat: global fallback for legacy code paths
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


def experiment_family(
    proposal: dict,
    experiment_kind: str,
    parameter_changes: list[dict],
    code_changes: list[str],
) -> str:
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
    """Return the stable human-readable operation description for a record."""
    kind = str(record.get("kind", "")).strip().lower()
    if kind == "continuation":
        return "Continue training the unchanged method"
    if kind == "replication":
        return "Replicate the current method from fresh initialization"
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


def training_parent(
    proposal: dict, state: dict, initialization: str
) -> tuple[str, Path, int]:
    if initialization != "transfer":
        return "fresh", Path(), 0
    identifier = str(proposal["training_parent"]).strip()
    if identifier == "accepted":
        return (
            "accepted",
            repository.resolve_repo_path(state["accepted_artifact"]),
            int(state.get("accepted_training_steps", 0)),
        )
    lineage = retained_lineage(state, identifier)
    if lineage is None:
        raise ValueError(f"unknown retained training parent {identifier!r}")
    artifact = repository.resolve_repo_path(lineage["artifact"])
    for filename in repository.ARTIFACT_FILES:
        if not (artifact / filename).exists():
            raise ValueError(
                f"retained lineage {identifier!r} is incomplete: {filename}"
            )
    return identifier, artifact, int(lineage.get("training_steps", 0))


# --- proposal validation ---------------------------------------------------


def validate_scientific_reasoning(proposal: dict) -> None:
    """Check explicit reasoning, not its scientific merit or truthfulness."""
    reasoning = proposal.get("reasoning")
    if not isinstance(reasoning, dict):
        raise TypeError("proposal reasoning must be an object")
    for field in (
        "alternative",
        "expected_observation",
        "contradicting_observation",
        "initialization_reason",
        "strategy_link",
    ):
        value = reasoning.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"reasoning.{field} must be a non-empty string")
    evidence = reasoning.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("reasoning.evidence must be a non-empty list")
    for item in evidence:
        if not isinstance(item, dict):
            raise TypeError("each reasoning.evidence entry must be an object")
        for field in ("source", "observation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(
                    f"reasoning.evidence.{field} must be a non-empty string"
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
    for item in proposal["reasoning"]["evidence"]:
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
    for label in (
        "Direction",
        "Lessons and limits",
        "Open questions",
        "Conditional next steps",
        "Reconsider when",
    ):
        match = re.search(
            rf"^\*\*{re.escape(label)}:\*\*[ \t]*(.*?)(?=^\*\*|\Z)",
            section,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match or not match.group(1).strip():
            raise ValueError(f"scientific strategy needs a non-empty '{label}' entry")


def validate_research_delta_ownership(code_changes: list[str]) -> None:
    """Reject changes to every human-owned source and test surface."""
    normalized = [path.replace("\\", "/") for path in code_changes]
    protected_sources = sorted(
        {path for path in normalized if is_protected_source(path)}
    )
    if protected_sources:
        raise ValueError(
            "human-owned task, context, dependency and protocol surfaces cannot "
            "be changed by a research proposal: "
            f"{protected_sources}; restore them to their content at the "
            "scientific parent before proposing another experiment"
        )
    protected_tests = sorted(
        path for path in normalized if path.startswith(PROTECTED_TEST_PREFIXES)
    )
    if protected_tests:
        raise ValueError(
            "the human-owned benchmark and AutoResearch tests cannot be changed "
            f"by a research proposal: {protected_tests}; restore them to their "
            "content at the scientific parent before proposing another experiment"
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
    if experiment_kind == "continuation" and (parameter_overrides or code_changes):
        raise ValueError("continuation requires an unchanged learning method")
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
    } & set(proposal)
    if forbidden:
        raise ValueError(
            f"training proposal contains lineage-only fields: {sorted(forbidden)}"
        )
    required = {
        "kind",
        "family",
        "hypothesis",
        "initialization",
    }
    missing = sorted(field for field in required if field not in proposal)
    if missing:
        raise ValueError(f"training proposal is missing required fields: {missing}")
    require_nonempty_string("family", "training proposal family")
    require_nonempty_string("hypothesis", "training proposal hypothesis")
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
        raise ValueError(
            f"{kind} must omit change because it uses the unchanged learning method"
        )
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
    validate_scientific_reasoning(proposal)


def validate_proposal_phase(proposal: dict, state: dict) -> str:
    """Return the proposal contract expected by the persisted lifecycle state."""
    if not isinstance(proposal, dict):
        raise TypeError("proposal.json must contain a JSON object")
    if state.get("pending_final_benchmark") is not None:
        raise ValueError(
            "the final benchmark is pending; no research proposal is accepted"
        )
    if state.get("pending_evaluation_request") is not None:
        raise ValueError(
            "research evaluation is pending; use evaluation_request.json, not "
            "proposal.json"
        )
    if state.get("pending_researcher_decision") is not None:
        if set(proposal) != {"previous_result_decision"}:
            raise ValueError(
                "the current phase requires a lineage proposal containing only "
                "previous_result_decision"
            )
        return "lineage"
    if "previous_result_decision" in proposal:
        raise ValueError(
            "the previous experiment lineage is already resolved; the current "
            "phase requires a new training proposal without previous_result_decision"
        )
    baseline = bool(proposal.get("baseline", False))
    validate_training_proposal(proposal, baseline=baseline)
    return "training"


def validate_proposal_against_state(proposal: dict, raw_state: dict) -> str:
    """Fully validate a proposal for its phase without mutating repository state."""
    contract = validate_proposal_phase(proposal, raw_state)
    if contract == "lineage":
        state = repository.load_state(
            allow_unmeasured=True, allow_missing_artifact=True
        )
        plan_previous_result_decision(proposal, state)
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
    if contract == "training" and not proposal.get("baseline"):
        validate_research_memory(proposal, raw_state)
    return contract


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
    if (
        "need_more_evidence" in request
        and type(request["need_more_evidence"]) is not bool
    ):
        raise ValueError("need_more_evidence must be true or false")
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


def available_evaluation_candidates(pending: dict, state: dict) -> dict:
    """The models a request may name: this experiment's candidates and the champion."""
    available = {item["name"]: item for item in pending["candidates"]}
    if pending.get("champion_available"):
        available["champion"] = {
            "name": "champion",
            "artifact": state["accepted_artifact"],
            "evaluations": [],
        }
    return available


def planned_measurements(
    request: dict, available: dict
) -> tuple[list[dict], list[dict]]:
    """Resolve all typed measurements before either evaluator starts."""
    validate_evaluation_request(request)
    evaluations: list[dict] = []
    references: list[dict] = []
    for spec in requested_measurements(request):
        name = spec["candidate"].strip()
        if name not in available:
            raise ValueError(
                f"unknown measurement candidate {name!r}; choose from {sorted(available)}"
            )
        if spec["instrument"] == "research_evaluation":
            evaluations.append(
                {
                    "candidate": name,
                    "episodes": spec["episodes"],
                    "seed": spec["seed"],
                    "label": spec.get(
                        "label", f"requested evaluation {len(evaluations) + 1}: {name}"
                    ),
                }
            )
        else:
            references.append(
                {
                    "candidate": name,
                    "label": spec.get(
                        "label", f"task reference {len(references) + 1}: {name}"
                    ),
                }
            )
    return evaluations, references


def validate_paired_comparison_plan(
    request: dict,
    pending: dict,
    available: dict,
    requested: list[dict],
) -> None:
    """Validate comparison identities that will exist after this request."""
    expected_panels: dict[str, set[tuple[int, int]]] = {
        name: set() for name in available
    }
    for item in pending.get("partial_evaluations", []) or []:
        name = str(item.get("candidate", "")).strip()
        if name in expected_panels:
            expected_panels[name].add((int(item["seed"]), int(item["episodes"])))
    for item in requested:
        expected_panels[item["candidate"]].add((item["seed"], item["episodes"]))

    for comparison in request.get("paired_comparisons", []):
        candidate = comparison["candidate"].strip()
        reference = comparison["reference"].strip()
        if candidate not in available:
            raise ValueError(f"unknown paired comparison candidate {candidate!r}")
        if reference not in available:
            raise ValueError(f"unknown paired comparison reference {reference!r}")
        candidate_panels = expected_panels[candidate]
        reference_panels = expected_panels[reference]
        if not candidate_panels or not reference_panels:
            raise ValueError(
                f"paired comparison {candidate!r} vs {reference!r} requires "
                "research-evaluation data for both models"
            )
        if candidate_panels != reference_panels:
            raise ValueError(
                f"paired comparison {candidate!r} vs {reference!r} requires "
                "identical (seed, episodes) panels"
            )


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
    """Every researcher-owned file that can change how a saved policy is measured.

    Any file type counts, so researcher-authored instrumentation modules and
    measurement data files are covered without a registry.
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
        if is_protected_source(relative) or relative in PRESENTATION_ONLY_PATHS:
            continue
        included.append(relative)
    return sorted(included)


def evaluation_semantics_fingerprint() -> str:
    """Identify the researcher-owned state that defines what a measurement means.

    Paths are hashed with their contents so an added, renamed or deleted file
    changes measurement identity just like an edited one.
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


def validate_postmortem_evidence(
    experiment: int,
    measured: list[str],
    *,
    campaign_id: str | None = None,
) -> None:
    """Require the decision to name existing evidence of this experiment.

    This shows only that the researcher session identified real artifacts of the
    experiment it is resolving; it cannot show that they were understood.
    """
    section = postmortem_section(experiment, campaign_id)
    if not section.strip():
        identity = (
            f"{campaign_id} / Experiment {experiment}"
            if campaign_id
            else f"Experiment {experiment}"
        )
        raise ValueError(f"postmortems.md has no entry for {identity}")
    attested = attested_evidence_paths(section)
    if not attested:
        raise ValueError(
            f"the experiment {experiment} postmortem needs an "
            f"'{EVIDENCE_ATTESTATION_LABEL}:' line listing the detailed "
            "evaluation artifacts the decision relied on"
        )
    owned = {path.replace("\\", "/") for path in measured}
    matched = [path for path in attested if path.replace("\\", "/") in owned]
    if not matched:
        raise ValueError(
            f"{EVIDENCE_ATTESTATION_LABEL} must name at least one detailed "
            f"evaluation artifact measured for experiment {experiment}: "
            f"{sorted(owned)}"
        )
    missing = sorted(
        path for path in matched if not repository.resolve_repo_path(path).is_file()
    )
    if missing:
        raise ValueError(f"attested evaluation artifacts do not exist: {missing}")


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
    changed = repository.scientific_change_paths(
        list(
            dict.fromkeys(
                [
                    *(str(path) for path in pending.get("research_change_paths", [])),
                    *(current_paths or []),
                ]
            )
        )
    )
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


def plan_previous_result_decision(proposal: dict, state: dict) -> dict:
    pending = state.get("pending_researcher_decision")
    if pending is None:
        raise ValueError("there is no researcher decision awaiting resolution")
    if set(proposal) != {"previous_result_decision"}:
        raise ValueError(
            "a lineage proposal must contain only previous_result_decision"
        )
    decision = proposal.get("previous_result_decision")
    if not isinstance(decision, dict):
        raise TypeError(
            "the previous experiment is awaiting a researcher decision; add "
            "previous_result_decision to the proposal"
        )
    if int(decision.get("experiment", -1)) != int(pending["experiment"]):
        raise ValueError("previous_result_decision references the wrong experiment")
    measured_evidence = pending_evaluation_artifacts(pending)
    if measured_evidence:
        validate_postmortem_evidence(
            int(pending["experiment"]),
            measured_evidence,
            campaign_id=repository.current_campaign_id(state),
        )
    selected_name = str(decision.get("continue_from", "")).strip()
    reason = str(decision.get("reason", "")).strip()
    if not reason:
        raise ValueError("previous_result_decision requires a reason")
    allowed = {
        "experiment",
        "continue_from",
        "reason",
        "code",
        "retain",
        "remove_retained",
        "request_final_benchmark",
    }
    extra = set(decision) - allowed
    if extra:
        raise ValueError(f"unsupported lineage decision fields: {sorted(extra)}")
    sources = {item["name"]: item for item in pending["candidates"]}
    if pending.get("champion_available"):
        sources["champion"] = {
            "name": "champion",
            "artifact": state["accepted_artifact"],
            "timesteps": int(state.get("accepted_training_steps", 0)),
            "summary": state.get("accepted_metrics"),
            "evaluations": pending.get("champion_evaluations", []),
            "parameters": state.get("accepted_parameters"),
        }
    if selected_name == "champion" and "champion" not in sources:
        raise ValueError("there is no existing champion to continue from")
    selected = sources.get(selected_name)
    if selected is None:
        raise ValueError(f"continue_from must be one of {sorted(sources)}")
    selected_artifact = repository.resolve_repo_path(selected["artifact"])
    repository.require_complete_artifact(
        selected_artifact, f"selected lineage {selected_name!r}"
    )

    code_decision = decision.get("code")
    if not isinstance(code_decision, dict):
        raise TypeError(
            "previous_result_decision requires a code decision with action and reason"
        )
    if set(code_decision) != {"action", "reason"}:
        raise ValueError("code decision contains unsupported fields")
    code_action = str(code_decision.get("action", "")).strip().lower()
    code_reason = str(code_decision.get("reason", "")).strip()
    if code_action not in {"keep", "revert"} or not code_reason:
        raise ValueError("code decision must be keep or revert with a reason")
    parent = str(pending.get("code_parent_commit", "")).strip()
    # The frozen change set describes the intervention that trained; the science
    # that must be undone is whatever stands against the parent now.
    code_plan = plan_code_lineage_decision(
        pending,
        code_action,
        current_paths=(
            repository.scientific_delta(parent)
            if parent and code_action == "revert"
            else None
        ),
    )
    code_plan["parent"] = parent

    retained = list(state.get("retained_lineages", []))
    retained_by_id = {str(lineage.get("id")): lineage for lineage in retained}
    removal_ids = decision.get("remove_retained", [])
    if not isinstance(removal_ids, list) or any(
        not str(identifier).strip() for identifier in removal_ids
    ):
        raise ValueError("remove_retained must be a list of retained lineage IDs")
    removal_ids = [str(identifier).strip() for identifier in removal_ids]
    if len(set(removal_ids)) != len(removal_ids):
        raise ValueError("remove_retained contains duplicate IDs")
    missing = set(removal_ids) - set(retained_by_id)
    if missing:
        raise ValueError(f"unknown retained lineages: {sorted(missing)}")

    requested = decision.get("retain", [])
    if not isinstance(requested, list):
        raise TypeError("retain must be a list")
    retained_ids = set(retained_by_id)
    retention_plans: list[dict] = []
    for item in requested:
        if not isinstance(item, dict) or set(item) != {"candidate", "id", "reason"}:
            raise ValueError(
                "each retained lineage requires only candidate, id, and reason"
            )
        candidate_name = str(item["candidate"]).strip()
        identifier = str(item["id"]).strip()
        retention_reason = str(item["reason"]).strip()
        if (
            not identifier
            or Path(identifier).name != identifier
            or identifier in {".", ".."}
        ):
            raise ValueError(
                "retained lineage ID must be a stable file-name-safe identifier"
            )
        if not retention_reason or candidate_name not in sources:
            raise ValueError(
                "retained lineages require an available candidate, id, and reason"
            )
        if candidate_name == selected_name:
            raise ValueError("do not retain the lineage becoming active")
        if identifier in retained_ids or identifier in removal_ids:
            raise ValueError(f"conflicting retained lineage ID: {identifier}")
        source = sources[candidate_name]
        source_artifact = repository.resolve_repo_path(source["artifact"])
        repository.require_complete_artifact(
            source_artifact, f"retained lineage {identifier!r}"
        )
        campaign_id = repository.current_campaign_id(state)
        destination = paths.campaign_retained_root(campaign_id) / identifier
        if destination.exists():
            raise ValueError(
                f"retained lineage destination already exists: {identifier}"
            )
        retention_plans.append(
            {
                "source": source_artifact,
                "destination": destination,
                "record": {
                    "id": identifier,
                    "artifact": repository.repo_relative_path(destination),
                    "origin_experiment": int(pending["experiment"]),
                    "campaign_id": campaign_id,
                    "candidate": candidate_name,
                    "reason": retention_reason,
                    "parameters": source.get("parameters", pending["parameters"]),
                    "training_steps": int(source["timesteps"]),
                    "evaluation_artifacts": repository.evaluation_artifact_paths(
                        source.get("evaluations")
                    ),
                },
            }
        )
        retained_ids.add(identifier)

    request_final = decision.get("request_final_benchmark", False)
    if not isinstance(request_final, bool):
        raise TypeError("request_final_benchmark must be true or false")
    selected_fingerprint = repository.artifact_fingerprint(selected_artifact)
    if (
        request_final
        and state.get("official_benchmark_artifact") == selected_fingerprint
    ):
        raise ValueError(
            "the selected accepted artifact already received an official benchmark"
        )
    return {
        "pending": pending,
        "decision": decision,
        "selected": selected,
        "selected_name": selected_name,
        "selected_artifact": selected_artifact,
        "selected_fingerprint": selected_fingerprint,
        "code_action": code_action,
        "code_reason": code_reason,
        "code_plan": code_plan,
        "retained": [
            lineage for lineage in retained if lineage["id"] not in removal_ids
        ],
        "retentions": retention_plans,
        "removed_retained": [retained_by_id[identifier] for identifier in removal_ids],
        "request_final_benchmark": request_final,
    }
