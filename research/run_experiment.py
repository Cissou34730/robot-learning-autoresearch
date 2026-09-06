"""Transactional autonomous-research runner for robot learning.

This module owns the Runner lifecycle: the CLI, which phase the persisted state
is in, and the order in which Runner operations happen. The implementation of
those operations lives in the `runner_*` modules:

  `runner_paths`       filesystem locations
  `runner_console`     what a human sees
  `runner_protocol`    what is admissible and what a decision means
  `runner_repository`  campaign state, history, checkpoints, Git
  `runner_execution`   subprocesses, training, measurement, timeouts
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from research import runner_console as console
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository
from robot_learning.training import research_config

TIMESTEPS = 120_000
TRAIN_SEED = 0

PROPOSAL_ERRORS = (
    json.JSONDecodeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def proposal_training_settings(
    proposal: dict,
) -> tuple[str, dict | None, bool, str]:
    """Resolve the training fields shared by preflight and execution."""
    return (
        str(proposal.get("kind", "training")).lower(),
        proposal.get("params"),
        bool(proposal.get("baseline", False)),
        str(proposal.get("initialization", "transfer")).lower(),
    )


def anchored_scientific_delta(raw_state: dict) -> list[str]:
    """Return the scientific delta from the parent anchored for this phase."""
    parent = str(raw_state.get("pending_scientific_parent") or "").strip()
    if not parent:
        raise ValueError(
            "research phase requires an existing pending scientific parent; "
            "run --begin-hypothesis before proposing an experiment"
        )
    repository.require_resolvable_commit(parent)
    return repository.scientific_delta(parent)


def validate_research_delta(raw_state: dict) -> list[str]:
    """Reject changes outside the researcher-owned scientific surface."""
    code_changes = anchored_scientific_delta(raw_state)
    protocol.validate_research_delta_ownership(code_changes)
    return code_changes


def validate_training_proposal_delta(proposal: dict, raw_state: dict) -> None:
    """Validate the proposal against the parent already anchored for this phase."""
    experiment_kind, parameter_overrides, baseline, initialization = (
        proposal_training_settings(proposal)
    )
    code_changes = validate_research_delta(raw_state)
    protocol.validate_experiment_semantics(
        proposal,
        experiment_kind,
        initialization,
        parameter_overrides,
        code_changes,
        baseline,
    )


# --- hypothesis phase ------------------------------------------------------


def begin_hypothesis_phase() -> int:
    """Anchor the parent before the researcher may change or commit any science."""
    state = repository.read_state()
    parent = repository.anchor_scientific_parent(state)
    repository.write_state(state)
    console.announce(
        f"[runner] scientific parent of the next experiment: {parent[:12]}"
    )
    return 0


def migrate_research_state() -> int:
    """Explicit human-only migration from the legacy v3 state schema."""
    try:
        changed = repository.migrate_research_state()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"RESEARCH_STATE_MIGRATION_INVALID: {error}")
        return 1
    print("RESEARCH_STATE_MIGRATED" if changed else "RESEARCH_STATE_ALREADY_CURRENT")
    return 0


# --- non-mutating preflights -----------------------------------------------


def check_proposal() -> int:
    """Non-mutating orchestration preflight for researcher-produced proposals."""
    if not paths.PROPOSAL_PATH.exists():
        print("PROPOSAL_INVALID: research/proposal.json was not created")
        return 1
    try:
        proposal = json.loads(paths.PROPOSAL_PATH.read_text(encoding="utf-8"))
        state = repository.read_state()
        contract = protocol.validate_proposal_against_state(proposal, state)
        if contract == "training":
            validate_training_proposal_delta(proposal, state)
        else:
            validate_research_delta(state)
    except PROPOSAL_ERRORS as error:
        print(f"PROPOSAL_INVALID: {error}")
        return 1
    print(f"PROPOSAL_VALID: {contract}")
    return 0


def check_evaluation_request() -> int:
    """Non-mutating preflight: is the researcher's request usable as written?

    It resolves the same plan execution will run, so a request that passes here
    fails afterwards only for a genuine Runner execution reason.
    """
    if not paths.EVALUATION_REQUEST_PATH.exists():
        print(
            "EVALUATION_REQUEST_INVALID: research/evaluation_request.json "
            "was not created"
        )
        return 1
    try:
        state = repository.read_state()
        pending = state.get("pending_evaluation_request")
        if not isinstance(pending, dict):
            raise TypeError("no experiment is awaiting a research evaluation")
        request = json.loads(paths.EVALUATION_REQUEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise TypeError("evaluation_request.json must contain a JSON object")
        protocol.validate_evaluation_request(
            request, allow_legacy_need_more_evidence=True
        )
        experiment = int(pending["experiment"])
        if int(request.get("experiment", -1)) != experiment:
            raise ValueError(
                "evaluation request references the wrong experiment; "
                f"experiment {experiment} is awaiting evaluation"
            )
        validate_research_delta(state)
        available = protocol.available_evaluation_candidates(pending, state)
        requested, _ = protocol.planned_measurements(
            request, available, allow_legacy_need_more_evidence=True
        )
        protocol.validate_paired_comparison_plan(request, pending, available, requested)
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"EVALUATION_REQUEST_INVALID: {error}")
        return 1
    print("EVALUATION_REQUEST_VALID")
    return 0


def check_analysis_deliverable() -> int:
    """Preflight the single actionable submission allowed during v4 analysis."""
    try:
        state = repository.read_state()
        pending = state.get("pending_analysis")
        if state.get("schema_version") != 4 or not isinstance(pending, dict):
            raise TypeError("no experiment is awaiting post-training analysis")
        measurement_valid = False
        closure_valid = False
        if paths.EVALUATION_REQUEST_PATH.exists():
            request = json.loads(
                paths.EVALUATION_REQUEST_PATH.read_text(encoding="utf-8")
            )
            if not isinstance(request, dict):
                raise TypeError("evaluation_request.json must contain a JSON object")
            if int(request.get("experiment", -1)) != int(pending["experiment"]):
                raise ValueError("evaluation request references the wrong experiment")
            available = protocol.available_evaluation_candidates(pending, state)
            requested, _ = protocol.planned_measurements(request, available)
            protocol.validate_paired_comparison_plan(
                request, pending, available, requested
            )
            validate_research_delta(state)
            measurement_valid = True
        if paths.PROPOSAL_PATH.exists():
            proposal = json.loads(paths.PROPOSAL_PATH.read_text(encoding="utf-8"))
            protocol.validate_proposal_against_state(proposal, state)
            validate_research_delta(state)
            closure_valid = True
        if measurement_valid and closure_valid:
            raise ValueError(
                "analysis has conflicting actionable measurement and closure deliverables"
            )
        if measurement_valid:
            print("ANALYSIS_DELIVERABLE_VALID: measurement")
            return 0
        if closure_valid:
            print("ANALYSIS_DELIVERABLE_VALID: closure")
            return 0
        raise ValueError("analysis requires evaluation_request.json or proposal.json")
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(f"ANALYSIS_DELIVERABLE_INVALID: {error}")
        return 1


def check_lineage_evidence(experiment: int) -> int:
    """Preflight for the loop: is the pending lineage decision attested yet?"""
    state = repository.read_state()
    pending = state.get("pending_researcher_decision")
    if not isinstance(pending, dict) or int(pending.get("experiment", -1)) != (
        experiment
    ):
        print(f"ERROR: experiment {experiment} is not awaiting a lineage decision.")
        return 1
    measured = protocol.pending_evaluation_artifacts(pending)
    if not measured:
        return 0
    campaign_id = repository.current_campaign_id(state)

    try:
        protocol.validate_postmortem_evidence(
            experiment,
            measured,
            campaign_id=campaign_id,
        )
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1
    return 0


# --- evaluation phase ------------------------------------------------------


def execute_pending_evaluations() -> int:
    from robot_learning.scenario.evaluation import summarize_research_evaluations
    from robot_learning.scenario.task_reference import task_reference_panel

    state = repository.read_state()
    campaign_id = repository.current_campaign_id(state)
    is_v4 = state.get("schema_version") == 4
    pending = (
        state.get("pending_analysis")
        if is_v4
        else state.get("pending_evaluation_request")
    )
    if not isinstance(pending, dict):
        raise TypeError("there is no trained experiment awaiting evaluation")
    validate_research_delta(state)
    if paths.EVALUATION_REQUEST_PATH.exists():
        request = json.loads(paths.EVALUATION_REQUEST_PATH.read_text(encoding="utf-8"))
        protocol.validate_evaluation_request(
            request, allow_legacy_need_more_evidence=not is_v4
        )
    else:
        request = pending.get("evaluation_plan")
        if not isinstance(request, dict):
            print("ERROR: research/evaluation_request.json not found.")
            return 1
    experiment = int(pending["experiment"])
    if int(request.get("experiment", -1)) != experiment:
        raise ValueError("evaluation request references the wrong experiment")
    candidates = pending["candidates"]
    available = protocol.available_evaluation_candidates(pending, state)
    # The whole plan is resolved first, so nothing is measured for a request
    # that a later entry would have invalidated.
    requested, requested_references = protocol.planned_measurements(
        request,
        available,
        allow_legacy_need_more_evidence=(
            not is_v4
            or (
                not paths.EVALUATION_REQUEST_PATH.exists()
                and "need_more_evidence" in request
            )
        ),
    )
    protocol.validate_paired_comparison_plan(request, pending, available, requested)
    resolved_models = (
        protocol.resolved_measurement_models(request, available) if is_v4 else {}
    )
    if paths.EVALUATION_REQUEST_PATH.exists():
        pending["evaluation_plan"] = request
        if is_v4:
            pending["evaluation_plan_models"] = resolved_models
        pending.setdefault("partial_evaluations", [])
        repository.write_state(state)
    elif is_v4:
        frozen_models = pending.get("evaluation_plan_models")
        if not isinstance(frozen_models, dict):
            raise ValueError("accepted measurement plan has no frozen model identities")
        if frozen_models != resolved_models:
            raise ValueError("accepted measurement plan model identity changed")
    console.announce("\n" + console.render_evaluation_plan(request, experiment) + "\n")

    executed: list[dict] = list(pending.get("partial_evaluations", []))
    reference_executed: list[dict] = list(
        pending.get("partial_task_reference_evaluations", [])
    )
    semantics = protocol.evaluation_semantics_fingerprint()
    panel = task_reference_panel()
    # The persisted measurement ledger is the sole source of truth across
    # successive rounds and interrupted resumes.
    for contender in candidates:
        contender["evaluations"] = []
    for item in executed:
        contender = available.get(item["candidate"])
        if contender is not None:
            contender.setdefault("evaluations", []).append(item["metrics"])

    def request_key(
        name: str, episodes: int, seed: int, fingerprint: str
    ) -> tuple[str, int, int, str]:
        return name, episodes, seed, fingerprint

    completed_keys = {
        request_key(
            item["candidate"],
            int(item["episodes"]),
            int(item["seed"]),
            str(item.get("evaluation_semantics", "")),
        )
        for item in executed
    }
    # A task-reference measurement is identified by the human-owned panel it ran,
    # never by researcher-owned evaluation semantics.
    completed_reference_keys = {
        (item["candidate"], str(item.get("panel", ""))) for item in reference_executed
    }
    try:
        for spec in requested:
            name = spec["candidate"]
            contender = available[name]
            episodes = spec["episodes"]
            seed = spec["seed"]
            label = spec["label"]
            key = request_key(name, episodes, seed, semantics)
            if key in completed_keys:
                console.announce(f"[evaluation] already complete; reusing {label}")
                continue
            eval_dir = paths.campaign_evaluation_dir(campaign_id)
            eval_dir.mkdir(parents=True, exist_ok=True)
            output_path = eval_dir / protocol.evaluation_artifact_name(
                experiment, name, episodes, seed, semantics, campaign_id=campaign_id
            )
            metrics = execution.evaluate_artifact(
                repository.resolve_repo_path(contender["artifact"]),
                seed,
                label=label,
                episodes=episodes,
                output_path=output_path,
            )
            # The artifact keeps the detail, including whatever researcher-owned
            # evidence the scenario emitted; state keeps only a reference to it.
            clean_metrics = repository.measurement_record(metrics)
            clean_metrics["evaluation_artifact"] = output_path.relative_to(
                paths.ROOT
            ).as_posix()
            clean_metrics["evaluation_semantics"] = semantics
            if is_v4:
                clean_metrics["model_fingerprint"] = resolved_models[name][
                    "fingerprint"
                ]
            contender.setdefault("evaluations", []).append(clean_metrics)
            executed.append(
                {
                    "candidate": name,
                    "episodes": episodes,
                    "seed": seed,
                    "label": label,
                    "evaluation_semantics": semantics,
                    "metrics": clean_metrics,
                    **(
                        {"model_fingerprint": resolved_models[name]["fingerprint"]}
                        if is_v4
                        else {}
                    ),
                }
            )
            completed_keys.add(key)
            pending["partial_evaluations"] = executed
            repository.write_state(state)

        for spec in requested_references:
            name = spec["candidate"]
            contender = available[name]
            label = spec["label"]
            reference_key = (name, panel["panel"])
            if reference_key in completed_reference_keys:
                console.announce(f"[task reference] already complete; reusing {label}")
                continue
            eval_dir = paths.campaign_evaluation_dir(campaign_id)
            eval_dir.mkdir(parents=True, exist_ok=True)
            output_path = eval_dir / protocol.task_reference_artifact_name(
                experiment, name, panel["panel"], campaign_id=campaign_id
            )
            metrics = execution.evaluate_artifact(
                repository.resolve_repo_path(contender["artifact"]),
                panel["seed"],
                label=label,
                episodes=panel["episodes"],
                output_path=output_path,
                task_reference=True,
            )
            reference_executed.append(
                {
                    "candidate": name,
                    "label": label,
                    "panel": str(metrics["panel"]),
                    "panel_version": int(metrics["panel_version"]),
                    "episodes": int(metrics["episodes"]),
                    "seed": int(metrics["seed"]),
                    "success_percent": float(metrics["success_percent"]),
                    "evaluation_artifact": output_path.relative_to(
                        paths.ROOT
                    ).as_posix(),
                    **(
                        {"model_fingerprint": resolved_models[name]["fingerprint"]}
                        if is_v4
                        else {}
                    ),
                }
            )
            completed_reference_keys.add(reference_key)
            pending["partial_task_reference_evaluations"] = reference_executed
            repository.write_state(state)
    except KeyboardInterrupt:
        console.announce(
            "[runner] Evaluation request paused. Completed measurements remain "
            "recorded in the pending request."
        )
        pending["partial_evaluations"] = executed
        pending["partial_task_reference_evaluations"] = reference_executed
        repository.write_state(state)
        return 130

    for candidate in candidates:
        evaluations = candidate.get("evaluations", [])
        candidate["summary"] = (
            summarize_research_evaluations(evaluations) if evaluations else None
        )

    champion_evaluations = available.get("champion", {}).get("evaluations", [])
    champion_summary = (
        summarize_research_evaluations(champion_evaluations)
        if champion_evaluations
        else None
    )

    comparison_inputs = {
        name: contender.get("evaluations", []) for name, contender in available.items()
    }
    comparisons = execution.requested_paired_comparisons(request, comparison_inputs)
    result = pending["result"]
    result.update(
        {
            "status": "ok",
            "verdict": "measured as requested; awaiting researcher analysis",
            "decision_pending": True,
            "candidates": candidates,
            "requested_evaluations": executed,
            # Measured on the human-owned panel; never pooled with the above.
            "task_reference_evaluations": reference_executed,
            "paired_comparisons": comparisons,
        }
    )
    measured = [item for item in candidates if item.get("summary") is not None]
    if measured and not is_v4:
        primary = measured[0]["summary"]
        result["candidate_metrics"] = primary
        result["candidate_success_percent"] = primary["pooled_success_percent"]

    researcher_context = {
        "experiment": experiment,
        "candidates": candidates,
        "champion_available": bool(pending.get("champion_available")),
        "champion_summary": champion_summary,
        "champion_evaluations": champion_evaluations,
        "task_reference_evaluations": reference_executed,
        "parameters": pending["parameters"],
        "initialization": pending["initialization"],
        "training_budget_steps": pending["training_budget_steps"],
        "parent_training_steps": pending["parent_training_steps"],
        "code_parent_commit": pending.get("code_parent_commit"),
        "research_change_paths": pending.get("research_change_paths", []),
    }
    more_evidence = bool(request.get("need_more_evidence", False)) and not is_v4
    if is_v4:
        pending["evaluation_plan"] = None
        pending["evaluation_plan_models"] = None
        pending["partial_evaluations"] = executed
        pending["partial_task_reference_evaluations"] = reference_executed
        state["pending_analysis"] = pending
        state["last_verdict"] = "measured as requested; awaiting researcher analysis"
    elif more_evidence:
        pending["evaluation_plan"] = None
        pending["partial_evaluations"] = executed
        pending["partial_task_reference_evaluations"] = reference_executed
        state["pending_evaluation_request"] = pending
        state["pending_researcher_decision"] = None
        state["last_verdict"] = (
            "measured; researcher requested another evaluation round"
        )
    else:
        state["pending_researcher_decision"] = researcher_context
        state["pending_evaluation_request"] = None
        state["last_verdict"] = result["verdict"]
    state["last_experiment"] = experiment
    if pending.get("baseline"):
        paths.BASELINE_PENDING_PATH.unlink(missing_ok=True)
    repository.write_state(state)
    paths.EVALUATION_REQUEST_PATH.unlink(missing_ok=True)
    if is_v4:
        repository.upsert_result(result)
    elif not more_evidence:
        repository.append_result(result)
    next_phase = (
        "Researcher post-training analysis"
        if is_v4 or more_evidence
        else "Researcher lineage decision"
    )
    console.announce(
        "\n"
        + console.render_evidence_card(
            experiment,
            candidates,
            champion_summary,
            comparisons,
            next_phase,
            task_reference_evaluations=reference_executed,
        )
    )
    return 0


# --- lineage phase ---------------------------------------------------------


def apply_previous_result_decision(proposal: dict, state: dict) -> bool:
    if state.get("schema_version") == 4 and isinstance(
        state.get("pending_closure_operation"), dict
    ):
        return apply_pending_v4_closure(state)
    plan = protocol.plan_previous_result_decision(proposal, state)
    if state.get("schema_version") == 4:
        return apply_v4_previous_result_decision(plan, state)
    pending = plan["pending"]
    selected = plan["selected"]
    selected_name = plan["selected_name"]
    # Copy alternatives first: a retained champion must survive replacement.
    for retention in plan["retentions"]:
        repository.copy_artifact(retention["source"], retention["destination"])
    if selected_name != "champion":
        repository.copy_artifact(plan["selected_artifact"], paths.ACCEPTED_DIR)
        state["accepted_artifact"] = repository.repo_relative_path(paths.ACCEPTED_DIR)
        state["accepted_metrics"] = selected.get("summary")
        state["accepted_parameters"] = pending["parameters"]
        state["accepted_training_steps"] = (
            int(pending.get("parent_training_steps", 0))
            + int(pending["training_budget_steps"])
            if pending["initialization"] == "transfer"
            else int(pending["training_budget_steps"])
        )
        state["official_metrics"] = None
    else:
        state["accepted_metrics"] = selected.get("summary")
        state["accepted_artifact"] = repository.repo_relative_path(
            repository.resolve_repo_path(state["accepted_artifact"])
        )
    state["accepted_evaluations"] = repository.evaluation_artifact_paths(
        selected.get("evaluations")
    )
    repository.apply_code_lineage_decision(plan["code_plan"])
    state["retained_lineages"] = plan["retained"] + [
        retention["record"] for retention in plan["retentions"]
    ]
    state["last_lineage_decision"] = {
        "experiment": int(pending["experiment"]),
        "continue_from": selected_name,
        "reason": plan["decision"]["reason"],
        "code": {"action": plan["code_action"], "reason": plan["code_reason"]},
        "code_parent_commit": pending.get("code_parent_commit"),
    }
    state["pending_researcher_decision"] = None
    state["last_verdict"] = f"researcher selected {selected_name}"
    repository.write_state(state)
    # Retain compact challenger history while removing every duplicate reusable artifact.
    for candidate in pending["candidates"]:
        repository.remove_heavyweight_artifacts(
            repository.resolve_repo_path(candidate["artifact"])
        )
    for lineage in plan["removed_retained"]:
        repository.remove_heavyweight_artifacts(
            repository.resolve_repo_path(lineage["artifact"])
        )
    # Completed evaluations are research history and survive their checkpoints.
    if plan["request_final_benchmark"]:
        state["pending_final_benchmark"] = {
            "experiment": int(pending["experiment"]),
            "selected": selected_name,
            "artifact": state["accepted_artifact"],
            "fingerprint": plan["selected_fingerprint"],
        }
        repository.write_state(state)
    console.announce("\n" + console.render_decision_card(plan) + "\n")
    return False


def apply_v4_previous_result_decision(plan: dict, state: dict) -> bool:
    operation = state.get("pending_closure_operation")
    if operation is None:
        pending_field = (
            "pending_analysis"
            if state.get("pending_analysis") is plan["pending"]
            else "pending_researcher_decision"
        )
        operation = {
            "experiment": int(plan["pending"]["experiment"]),
            "selected": plan["working_name"],
            "code_action": plan["code_action"],
            "plan": _serialize_closure_plan(plan, pending_field=pending_field),
            "progress": "planned",
        }
        state["pending_closure_operation"] = operation
        repository.write_state(state)
    return apply_pending_v4_closure(state)


def _serialize_closure_plan(plan: dict, *, pending_field: str) -> dict:
    code_plan = plan["code_plan"]
    return {
        "pending": plan["pending"],
        "pending_field": pending_field,
        "decision": plan["decision"],
        "working_name": plan["working_name"],
        "working_record": plan["working_record"],
        "best_known_record": plan["best_known_record"],
        "best_known_name": plan["best_known_name"],
        "code_action": plan["code_action"],
        "code_reason": plan["code_reason"],
        "code_plan": {
            "parent": code_plan["parent"],
            "restore": code_plan["restore"],
            "remove_created": [
                repository.repo_relative_path(path)
                for path in code_plan["remove_created"]
            ],
        },
        "retained": plan["retained"],
        "removed_retained": plan["removed_retained"],
        "artifact_publications": plan["artifact_publications"],
        "request_final_benchmark": plan["request_final_benchmark"],
    }


def apply_pending_v4_closure(state: dict) -> bool:
    operation = state.get("pending_closure_operation")
    if not isinstance(operation, dict):
        raise TypeError("there is no pending closure operation")
    plan = operation["plan"]
    pending = plan["pending"]
    pending_field = plan.get("pending_field")
    if pending_field not in {"pending_analysis", "pending_researcher_decision"}:
        pending_field = (
            "pending_analysis"
            if isinstance(state.get("pending_analysis"), dict)
            else "pending_researcher_decision"
        )
    progress = operation.get("progress")
    if progress not in {
        "planned",
        "copied",
        "code_applied",
        "role_result_written",
        "durable",
        "cleanup_complete",
    }:
        raise ValueError(f"unknown v4 closure progress: {progress!r}")
    if progress in {"durable", "cleanup_complete"}:
        return False
    if progress == "planned":
        for publication in plan.get("artifact_publications", []):
            repository.publish_artifact(publication)
        operation["progress"] = "copied"
        repository.write_state(state)
        progress = "copied"
    if progress == "copied":
        code_plan = dict(plan["code_plan"])
        code_plan["remove_created"] = [
            repository.resolve_repo_path(path) for path in code_plan["remove_created"]
        ]
        repository.apply_code_lineage_decision(code_plan)
        operation["progress"] = "code_applied"
        repository.write_state(state)
        progress = "code_applied"
    if progress not in {"code_applied", "role_result_written"}:
        raise RuntimeError(f"cannot write v4 closure roles from progress {progress!r}")
    state["working_lineage"] = plan["working_record"]
    state["best_known_lineage"] = plan["best_known_record"]
    state["retained_lineages"] = plan["retained"]
    state["last_lineage_decision"] = {
        "experiment": int(pending["experiment"]),
        "continue_from": plan["working_name"],
        "reason": plan["decision"]["reason"],
        "best_known": plan["best_known_name"],
        "code": {"action": plan["code_action"], "reason": plan["code_reason"]},
        "code_parent_commit": pending.get("code_parent_commit"),
    }
    state["last_verdict"] = f"researcher selected {plan['working_name']} as working"
    if plan["request_final_benchmark"]:
        best_known = plan["best_known_record"]
        state["pending_final_benchmark"] = {
            "experiment": int(pending["experiment"]),
            "selected": "best_known",
            "artifact": best_known["artifact"],
            "fingerprint": best_known["fingerprint"],
            "best_known": best_known,
        }
    if pending_field == "pending_analysis":
        result = pending["result"]
        result.update(
            {
                "status": "closed",
                "verdict": state["last_verdict"],
                "decision_pending": False,
                "closure_decision": plan["decision"],
                "postmortem": repository.repo_relative_path(paths.POSTMORTEM_PATH),
                "working_lineage": plan["working_record"],
                "best_known_lineage": plan["best_known_record"],
            }
        )
        repository.upsert_result(result)
        state["pending_analysis"] = None
    else:
        state["pending_researcher_decision"] = None
    operation["progress"] = "role_result_written"
    repository.write_state(state)
    operation["progress"] = "durable"
    repository.write_state(state)
    return False


def finalize_pending_v4_closure(state: dict) -> None:
    """Clean only after the scientific and campaign-memory commits are published."""
    operation = state.get("pending_closure_operation")
    if not isinstance(operation, dict):
        raise TypeError("there is no pending closure operation")
    if operation.get("progress") not in {"durable", "cleanup_complete"}:
        raise RuntimeError("cannot clean a v4 closure before durable publication")
    if operation.get("progress") == "cleanup_complete":
        return
    plan = operation["plan"]
    pending = plan["pending"]
    protected = repository.role_and_retention_artifacts(state)
    for candidate in pending["candidates"]:
        artifact = repository.resolve_repo_path(candidate["artifact"])
        if artifact not in protected:
            repository.remove_heavyweight_artifacts(artifact)
    for lineage in plan["removed_retained"]:
        artifact = repository.resolve_repo_path(lineage["artifact"])
        if artifact not in protected:
            repository.remove_heavyweight_artifacts(artifact)
    operation["progress"] = "cleanup_complete"
    repository.write_state(state)


def publish_v4_closure_completion(state: dict) -> None:
    """Publish cleanup and clear the operation without losing retry state."""
    operation = state.get("pending_closure_operation")
    if not isinstance(operation, dict):
        raise TypeError("there is no pending closure operation")
    experiment = int(operation["experiment"])
    finalize_pending_v4_closure(state)
    if not repository.commit_runner_memory(
        f"complete experiment {experiment} lineage cleanup"
    ):
        repository.push_head()
    try:
        state["pending_closure_operation"] = None
        repository.write_state(state)
        if not repository.commit_runner_memory(
            f"clear experiment {experiment} lineage operation"
        ):
            repository.push_head()
    except BaseException:
        state["pending_closure_operation"] = operation
        repository.write_state(state)
        raise


def resolve_pending_lineage(proposal: dict, raw_state: dict) -> int:
    state = repository.load_state(allow_unmeasured=True, allow_missing_artifact=True)
    apply_previous_result_decision(proposal, state)
    repository.commit_lineage_decision(
        int(
            (
                raw_state["pending_analysis"]
                if raw_state.get("schema_version") == 4
                else raw_state["pending_researcher_decision"]
            )["experiment"]
        ),
        str(proposal["previous_result_decision"]["continue_from"]),
        code_action=str(proposal["previous_result_decision"]["code"]["action"])
        .strip()
        .lower(),
        state=state,
    )
    paths.PROPOSAL_PATH.unlink(missing_ok=True)
    if state.get("schema_version") == 4:
        publish_v4_closure_completion(state)
    return 0


# --- final benchmark phase -------------------------------------------------


def execute_pending_final_benchmark() -> int:
    from robot_learning.scenario.final_benchmark import evaluate_final_model

    state = repository.read_state()
    pending = state.get("pending_final_benchmark")
    if not isinstance(pending, dict):
        raise TypeError(
            "there is no accepted lineage awaiting final benchmark evaluation"
        )
    if state.get("schema_version") == 4:
        best_known = state.get("best_known_lineage")
        frozen_best_known = pending.get("best_known")
        if not isinstance(best_known, dict) or not isinstance(frozen_best_known, dict):
            raise ValueError("pending final benchmark requires a v4 best-known lineage")
        if pending.get("selected") != "best_known":
            raise ValueError("pending final benchmark must target best_known")
        if (
            frozen_best_known.get("artifact") != best_known.get("artifact")
            or frozen_best_known.get("fingerprint") != best_known.get("fingerprint")
            or pending.get("artifact") != best_known.get("artifact")
            or pending.get("fingerprint") != best_known.get("fingerprint")
        ):
            raise ValueError(
                "pending final benchmark does not match the v4 best-known lineage"
            )
        artifact = str(best_known["artifact"])
        fingerprint = str(best_known["fingerprint"])
    else:
        artifact = str(pending.get("artifact", "")).strip()
        fingerprint = str(pending.get("fingerprint", "")).strip()
    if state.get("schema_version") != 4:
        accepted_reference = str(state.get("accepted_artifact", "")).strip()
        if repository.resolve_repo_path(artifact) != repository.resolve_repo_path(
            accepted_reference
        ):
            raise ValueError(
                "pending final benchmark does not identify the accepted artifact"
            )
    accepted_artifact = repository.resolve_repo_path(artifact)
    repository.require_complete_artifact(
        accepted_artifact, "pending final benchmark artifact"
    )
    if (
        not fingerprint
        or repository.artifact_fingerprint(accepted_artifact) != fingerprint
    ):
        raise ValueError(
            "pending final benchmark artifact fingerprint does not match accepted lineage"
        )
    if state.get("official_benchmark_artifact") == fingerprint:
        raise ValueError(
            "the selected accepted artifact already received an official benchmark"
        )

    official_metrics = evaluate_final_model(accepted_artifact / "model.zip")
    verdict = (
        "goal_reached" if bool(official_metrics["goal_reached"]) else "goal_not_reached"
    )
    state["official_metrics"] = official_metrics
    state["official_benchmark_artifact"] = fingerprint
    state["official_benchmark_model"] = {
        "selected": pending["selected"],
        "artifact": artifact,
        "fingerprint": fingerprint,
    }
    state["official_benchmark_verdict"] = verdict
    state["pending_final_benchmark"] = None
    state["terminal_campaign_status"] = verdict
    state["last_verdict"] = (
        "official benchmark reached the goal"
        if bool(official_metrics["goal_reached"])
        else "official benchmark did not reach the goal"
    )
    repository.write_state(state)
    if bool(official_metrics["goal_reached"]):
        paths.GOAL_PATH.write_text(
            f"Goal reached with {pending['selected']} from experiment {pending['experiment']}.\n",
            encoding="utf-8",
        )
    return 0


# --- training phase --------------------------------------------------------


def run_training_experiment(proposal: dict, args: argparse.Namespace) -> int:
    change = protocol.operation_description(proposal)
    hypothesis = str(proposal["hypothesis"]).strip()
    experiment_kind, parameter_overrides, baseline, initialization = (
        proposal_training_settings(proposal)
    )
    fresh_baseline = baseline and initialization == "fresh"
    state = repository.load_state(
        allow_unmeasured=True,
        allow_missing_artifact=fresh_baseline,
    )
    # Extract campaign ID early for use throughout the function
    campaign_id = repository.current_campaign_id(state)

    # A preserved proposal is the same experiment: recovery and restart reuse
    # the identity the interrupted run allocated instead of consuming a new one.
    resuming = args.reuse_candidate is not None or paths.RESTART_PENDING_PATH.exists()
    index = (
        protocol.resumed_experiment_index(
            state, args.reuse_candidate, campaign_id=campaign_id
        )
        if resuming
        else 0
    )
    if index < 1:
        index = protocol.next_experiment_index(state, campaign_id=campaign_id)
    state["last_allocated_experiment"] = index
    recoverable_continuation = args.reuse_candidate is not None
    # A fresh baseline has no hypothesis phase to anchor it, and a retry, restart
    # or recovery keeps the anchor the unfinished research already established.
    code_parent_commit = repository.anchor_scientific_parent(state)
    # Durable before validation or training can produce anything under this
    # identity, so a rejected, crashed or interrupted experiment consumes it.
    repository.write_state(state)
    candidate_dir = paths.campaign_candidate_root(campaign_id) / f"experiment-{index}"
    created_candidate_dirs: list[Path] = []
    previous_config = research_config.load_experiment_config()
    code_changes: list[str] = []
    preserve_proposal = False
    reused_candidate: Path | None = None
    training_elapsed = 0.0
    parent_name, parent_artifact, parent_training_steps = protocol.training_parent(
        proposal, state, initialization
    )

    result: dict[str, Any] = {
        "schema_version": 1,
        "index": index,
        "campaign_id": campaign_id,
        "change": change,
        "hypothesis": hypothesis,
        "kind": experiment_kind,
        "family": str(proposal.get("family", "")).strip() or experiment_kind,
        "initialization": initialization,
        "parameter_changes": [],
        "code_changes": [],
        "status": "error",
        "verdict": "error",
    }
    # Freeze the pre-training rationale: later revisions of scientific memory
    # must not retroactively change what this experiment was intended to test.
    if "reasoning" in proposal:
        result["reasoning"] = proposal["reasoning"]
        result["scientific_strategy"] = protocol.scientific_strategy_section(
            paths.POSTMORTEM_PATH.read_text(encoding="utf-8")
            if paths.POSTMORTEM_PATH.exists()
            else "",
            campaign_id,
        )
    result["proposal_snapshot"] = proposal
    try:
        code_changes = repository.scientific_delta(code_parent_commit)
        result["code_changes"] = code_changes
        protocol.validate_experiment_semantics(
            proposal,
            experiment_kind,
            initialization,
            parameter_overrides,
            code_changes,
            baseline,
        )

        if parameter_overrides:
            console.announce("[checks] validating proposed parameters")
            research_config.validate_param_overrides(parameter_overrides)
            result["parameter_changes"] = protocol.parameter_change_records(
                previous_config, parameter_overrides
            )
            research_config.write_experiment_config(
                research_config.merge_param_overrides(
                    previous_config, parameter_overrides
                )
            )
        result["family"] = protocol.experiment_family(
            proposal,
            experiment_kind,
            result["parameter_changes"],
            code_changes,
        )
        if code_changes:
            console.announce("[checks] validating changed files")
            execution.validate_changed_sources(code_changes)
        console.announce("[checks] resolving the effective training configuration")
        execution.validate_active_configuration()
        selected_tests = protocol.validation_test_paths(
            code_changes, fresh_baseline=fresh_baseline
        )
        if selected_tests:
            console.announce("[checks] running research-surface checks")
            if fresh_baseline:
                execution.validate_dependency_metadata()
            execution.run_validation_suites(selected_tests)
            console.announce("[checks] passed")

        effective_config = research_config.load_experiment_config()
        scientific_scope = repository.scientific_delta(code_parent_commit)
        state["pending_scientific_commit"] = {
            "experiment": index,
            "code_parent_commit": code_parent_commit,
            "scope": scientific_scope,
        }
        repository.write_state(state)
        scientific_commit = repository.publish_scientific_recipe(
            index,
            scientific_scope,
        )
        state["pending_scientific_commit"] = {
            "experiment": index,
            "code_parent_commit": code_parent_commit,
            "scientific_commit": scientific_commit,
        }
        repository.write_state(state)
        result["scientific_commit"] = scientific_commit
        effective_timesteps = execution.training_budget(
            args.timesteps,
            initialization,
            fresh_baseline,
            int(state.get("accepted_training_steps", args.timesteps)),
        )
        result["training_budget_steps"] = effective_timesteps
        training_seed = int(proposal.get("training_seed", TRAIN_SEED))
        result["training_seed"] = training_seed
        result["training_parent"] = parent_name
        if experiment_kind == "replication":
            result["replication_of"] = int(proposal["replication_of"])
        console.announce("\n" + console.render_experiment_card(result) + "\n")
        resume = parent_artifact / "model.zip" if initialization == "transfer" else None

        if resuming and candidate_dir.exists():
            # Only the experiment's own leftovers: a new identity that collided
            # with existing data was skipped rather than allocated.
            console.announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            execution.remove_candidate_dir(candidate_dir)

        def active_training_log() -> Path:
            attempt = execution.training_attempt(
                index,
                recoverable_continuation=recoverable_continuation,
                campaign_id=campaign_id,
            )
            return paths.training_log_path(index, attempt, campaign_id=campaign_id)

        if args.reuse_candidate is not None:
            reusable = args.reuse_candidate.resolve()
            reused_candidate = reusable
            execution.validate_reusable_candidate(
                reusable,
                timesteps=effective_timesteps,
                seed=training_seed,
                resume=resume,
                config=effective_config,
            )
            artifact = json.loads(
                (reusable / "artifact.json").read_text(encoding="utf-8")
            )
            completed_timesteps = int(artifact["timesteps"])
            if bool(artifact.get("completed", True)):
                console.announce(
                    f"[recovery] reusing completed candidate from {reusable}"
                )
                execution.copy_candidate_outputs(reusable, candidate_dir)
            else:
                remaining_timesteps = max(effective_timesteps - completed_timesteps, 0)
                if remaining_timesteps == 0:
                    console.announce(
                        "[recovery] interrupted training already reached its budget"
                    )
                    execution.copy_candidate_outputs(reusable, candidate_dir)
                else:
                    console.announce(
                        f"[recovery] resuming at {completed_timesteps:,} / "
                        f"{effective_timesteps:,} steps"
                    )
                    created_candidate_dirs.append(candidate_dir)
                    training_elapsed = execution.train_candidate(
                        candidate_dir,
                        remaining_timesteps,
                        training_seed,
                        reusable / "final_checkpoint" / "model.zip",
                        active_training_log(),
                        label=(
                            "resumed baseline training"
                            if baseline
                            else "resumed candidate training"
                        ),
                        continue_timesteps=True,
                        target_timesteps=effective_timesteps,
                    )
        else:
            created_candidate_dirs.append(candidate_dir)
            training_elapsed = execution.train_candidate(
                candidate_dir,
                effective_timesteps,
                training_seed,
                resume,
                active_training_log(),
                label="baseline training" if baseline else "candidate training",
            )
        contenders = [
            {**candidate, "kind": "candidate", "evaluations": []}
            for candidate in execution.candidate_directories(candidate_dir)
        ]
        archived_candidates = repository.archive_candidates(
            index, contenders, effective_config, campaign_id=campaign_id
        )
        for candidate in archived_candidates:
            candidate["scientific_commit"] = scientific_commit
        verdict = "trained; awaiting researcher analysis"
        completed_steps = max(
            (int(candidate["timesteps"]) for candidate in archived_candidates),
            default=0,
        )
        console.announce(
            "\n"
            + console.render_training_summary_card(
                result,
                completed_steps=completed_steps,
                elapsed_seconds=training_elapsed,
                candidates=archived_candidates,
            )
            + "\n"
        )

        pending = {
            "experiment": index,
            "candidates": archived_candidates,
            "champion_available": not fresh_baseline,
            "parameters": effective_config,
            "initialization": initialization,
            "training_budget_steps": effective_timesteps,
            "parent_training_steps": int(parent_training_steps),
            "baseline": baseline,
            "code_parent_commit": code_parent_commit,
            "scientific_commit": scientific_commit,
            "research_change_paths": code_changes
            + (["research/current_params.json"] if parameter_overrides else []),
            "result": result,
        }
        result["candidates"] = archived_candidates
        state.update({"last_experiment": index, "last_verdict": verdict})
        if state.get("schema_version") == 4:
            state["pending_analysis"] = pending
        else:
            state["pending_evaluation_request"] = pending
        result.update({"status": "trained", "verdict": verdict})
        if args.reuse_candidate is not None:
            paths.RECOVERY_PENDING_PATH.unlink(missing_ok=True)
        paths.RESTART_PENDING_PATH.unlink(missing_ok=True)
        repository.write_state(state)
        if state.get("schema_version") == 4:
            repository.upsert_result(result)
    except KeyboardInterrupt:
        recovery_dir = (
            paths.campaign_candidate_root(campaign_id) / f"recovery-experiment-{index}"
        )
        recoverable = all(
            (candidate_dir / filename).exists()
            for filename in repository.ARTIFACT_FILES
        )
        if recoverable:
            if recovery_dir.exists():
                execution.remove_candidate_dir(recovery_dir)
            candidate_dir.replace(recovery_dir)
            paths.RECOVERY_PENDING_PATH.write_text(
                repository.repo_relative_path(recovery_dir) + "\n", encoding="utf-8"
            )
            preserve_proposal = True
            console.announce(
                "[runner] Experiment paused. The latest complete training state "
                "was saved and will resume on the next launch."
            )
        else:
            preserve_proposal = True
            if reused_candidate is not None and paths.RECOVERY_PENDING_PATH.exists():
                console.announce(
                    "[runner] No newer complete state was produced; the previous "
                    "recovery checkpoint remains available for the next launch."
                )
            else:
                paths.RESTART_PENDING_PATH.write_text(
                    "Restart the preserved proposal from the beginning.\n",
                    encoding="utf-8",
                )
                console.announce(
                    "[runner] Experiment stopped before a recoverable training "
                    "state was produced; the same experiment will restart from "
                    "the beginning."
                )
        return 130
    except Exception as error:  # noqa: BLE001
        result["error"] = str(error)[:500]
        result["verdict"] = "invalid; researcher changes preserved"
        repository.append_result(result)
        repository.write_state(state)
        repository.commit_result(index, change)
        console.announce(f"[error] experiment {index} invalid: {result['error']}")
        return 1
    finally:
        if not preserve_proposal:
            paths.PROPOSAL_PATH.unlink(missing_ok=True)
        cleanup_targets = created_candidate_dirs or [candidate_dir]
        for cleanup_target in cleanup_targets:
            try:
                execution.remove_candidate_dir(cleanup_target)
            except OSError as cleanup_error:
                console.announce(
                    f"[runner] WARNING: candidate cleanup failed: {cleanup_error}"
                )
        if (
            reused_candidate is not None
            and not paths.RECOVERY_PENDING_PATH.exists()
            and reused_candidate.exists()
        ):
            execution.remove_candidate_dir(reused_candidate)

    return 0


# --- command dispatch ------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--reuse-candidate", type=Path, default=None)
    parser.add_argument("--evaluate-pending", action="store_true")
    parser.add_argument("--evaluate-pending-final", action="store_true")
    parser.add_argument("--check-lineage-evidence", type=int, default=None)
    parser.add_argument("--check-proposal", action="store_true")
    parser.add_argument("--check-evaluation-request", action="store_true")
    parser.add_argument("--check-analysis-deliverable", action="store_true")
    parser.add_argument("--begin-hypothesis", action="store_true")
    parser.add_argument("--migrate-research-state", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.migrate_research_state:
        migrated = migrate_research_state()
        print("RESEARCH_STATE_MIGRATED" if migrated else "RESEARCH_STATE_ALREADY_V4")
        return 0
    if args.begin_hypothesis:
        return begin_hypothesis_phase()
    if args.check_proposal:
        return check_proposal()
    if args.check_evaluation_request:
        return check_evaluation_request()
    if args.check_analysis_deliverable:
        return check_analysis_deliverable()
    if args.check_lineage_evidence is not None:
        return check_lineage_evidence(args.check_lineage_evidence)
    # Past this point the Runner may write history, so the derived human-readable
    # view is reconciled first: an interruption between the two writes is never
    # inherited as a second, competing history.
    repository.synchronize_experiment_log()
    if args.evaluate_pending_final:
        status = execute_pending_final_benchmark()
        if status == 0:
            # The official result may be the campaign's last transition, so it
            # is published now rather than by an experiment that may never run.
            repository.commit_runner_memory("record the official final benchmark")
        return status
    if args.evaluate_pending:
        return execute_pending_evaluations()
    if repository.read_state().get("pending_closure_operation"):
        state = repository.load_state(
            allow_unmeasured=True, allow_missing_artifact=True
        )
        operation = state["pending_closure_operation"]
        apply_pending_v4_closure(state)
        repository.commit_lineage_decision(
            int(operation["experiment"]),
            str(operation["selected"]),
            code_action=str(operation["code_action"]),
            state=state,
        )
        publish_v4_closure_completion(state)
        return 0
    if not paths.PROPOSAL_PATH.exists():
        print("ERROR: research/proposal.json not found.")
        return 1

    try:
        proposal = json.loads(paths.PROPOSAL_PATH.read_text(encoding="utf-8"))
        raw_state = repository.read_state()
        proposal_contract = protocol.validate_proposal_against_state(
            proposal, raw_state
        )
    except PROPOSAL_ERRORS as error:
        print(f"ERROR: invalid proposal for current phase: {error}")
        return 1
    if proposal_contract == "lineage":
        validate_research_delta(raw_state)
        return resolve_pending_lineage(proposal, raw_state)
    return run_training_experiment(proposal, args)


if __name__ == "__main__":
    sys.exit(main())
