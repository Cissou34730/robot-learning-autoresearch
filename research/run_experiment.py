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


# --- hypothesis phase ------------------------------------------------------


def begin_hypothesis_phase() -> int:
    """Anchor the parent before the researcher may change or commit any science."""
    state = repository.read_state()
    parent = repository.anchor_scientific_parent(state)
    repository.atomic_write_json(paths.STATE_PATH, state)
    console.announce(
        f"[runner] scientific parent of the next experiment: {parent[:12]}"
    )
    return 0


# --- non-mutating preflights -----------------------------------------------


def check_proposal() -> int:
    """Non-mutating orchestration preflight for researcher-produced proposals."""
    if not paths.PROPOSAL_PATH.exists():
        print("PROPOSAL_INVALID: research/proposal.json was not created")
        return 1
    try:
        proposal = json.loads(paths.PROPOSAL_PATH.read_text(encoding="utf-8"))
        contract = protocol.validate_proposal_against_state(
            proposal, repository.read_state()
        )
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
        protocol.validate_evaluation_request(request)
        experiment = int(pending["experiment"])
        if int(request.get("experiment", -1)) != experiment:
            raise ValueError(
                "evaluation request references the wrong experiment; "
                f"experiment {experiment} is awaiting evaluation"
            )
        available = protocol.available_evaluation_candidates(pending, state)
        protocol.planned_evaluations(request, available)
        protocol.planned_task_references(request, available)
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
    try:
        protocol.validate_postmortem_evidence(experiment, measured)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1
    return 0


# --- evaluation phase ------------------------------------------------------


def execute_pending_evaluations() -> int:
    from robot_learning.scenario import (
        summarize_research_evaluations,
        task_reference_panel,
    )

    state = repository.read_state()
    pending = state.get("pending_evaluation_request")
    if not isinstance(pending, dict):
        raise TypeError("there is no trained experiment awaiting evaluation")
    if paths.EVALUATION_REQUEST_PATH.exists():
        request = json.loads(paths.EVALUATION_REQUEST_PATH.read_text(encoding="utf-8"))
        protocol.validate_evaluation_request(request)
        pending["evaluation_plan"] = request
        pending.setdefault("partial_evaluations", [])
        repository.atomic_write_json(paths.STATE_PATH, state)
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
    requested = protocol.planned_evaluations(request, available)
    requested_references = protocol.planned_task_references(request, available)
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
            paths.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
            output_path = paths.EVALUATION_DIR / protocol.evaluation_artifact_name(
                experiment, name, episodes, seed, semantics
            )
            metrics = execution.evaluate_artifact(
                paths.ROOT / contender["artifact"],
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
            contender.setdefault("evaluations", []).append(clean_metrics)
            executed.append(
                {
                    "candidate": name,
                    "episodes": episodes,
                    "seed": seed,
                    "label": label,
                    "evaluation_semantics": semantics,
                    "metrics": clean_metrics,
                }
            )
            completed_keys.add(key)
            pending["partial_evaluations"] = executed
            repository.atomic_write_json(paths.STATE_PATH, state)

        for spec in requested_references:
            name = spec["candidate"]
            contender = available[name]
            label = spec["label"]
            reference_key = (name, panel["panel"])
            if reference_key in completed_reference_keys:
                console.announce(f"[task reference] already complete; reusing {label}")
                continue
            paths.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
            output_path = paths.EVALUATION_DIR / protocol.task_reference_artifact_name(
                experiment, name, panel["panel"]
            )
            metrics = execution.evaluate_artifact(
                paths.ROOT / contender["artifact"],
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
                }
            )
            completed_reference_keys.add(reference_key)
            pending["partial_task_reference_evaluations"] = reference_executed
            repository.atomic_write_json(paths.STATE_PATH, state)
    except KeyboardInterrupt:
        console.announce(
            "[runner] Evaluation request paused. Completed measurements remain "
            "recorded in the pending request."
        )
        pending["partial_evaluations"] = executed
        pending["partial_task_reference_evaluations"] = reference_executed
        repository.atomic_write_json(paths.STATE_PATH, state)
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
    if measured:
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
    more_evidence = bool(request.get("need_more_evidence", False))
    if more_evidence:
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
    repository.atomic_write_json(paths.STATE_PATH, state)
    paths.EVALUATION_REQUEST_PATH.unlink(missing_ok=True)
    if not more_evidence:
        repository.append_result(result)
    next_phase = (
        "Researcher evaluation design"
        if more_evidence
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
    plan = protocol.plan_previous_result_decision(proposal, state)
    pending = plan["pending"]
    selected = plan["selected"]
    selected_name = plan["selected_name"]
    # Copy alternatives first: a retained champion must survive replacement.
    for retention in plan["retentions"]:
        repository.copy_artifact(retention["source"], retention["destination"])
    if selected_name != "champion":
        repository.copy_artifact(plan["selected_artifact"], paths.ACCEPTED_DIR)
        state["accepted_artifact"] = str(paths.ACCEPTED_DIR.relative_to(paths.ROOT))
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
    repository.atomic_write_json(paths.STATE_PATH, state)
    # Retain compact challenger history while removing every duplicate reusable artifact.
    for candidate in pending["candidates"]:
        repository.remove_heavyweight_artifacts(paths.ROOT / candidate["artifact"])
    for lineage in plan["removed_retained"]:
        repository.remove_heavyweight_artifacts(paths.ROOT / lineage["artifact"])
    # Completed evaluations are research history and survive their checkpoints.
    if plan["request_final_benchmark"]:
        state["pending_final_benchmark"] = {
            "experiment": int(pending["experiment"]),
            "selected": selected_name,
            "artifact": str(paths.ACCEPTED_DIR.relative_to(paths.ROOT)),
            "fingerprint": plan["selected_fingerprint"],
        }
        repository.atomic_write_json(paths.STATE_PATH, state)
    console.announce("\n" + console.render_decision_card(plan) + "\n")
    return False


def resolve_pending_lineage(proposal: dict, raw_state: dict) -> int:
    state = repository.load_state(allow_unmeasured=True, allow_missing_artifact=True)
    apply_previous_result_decision(proposal, state)
    repository.commit_lineage_decision(
        int(raw_state["pending_researcher_decision"]["experiment"]),
        str(proposal["previous_result_decision"]["continue_from"]),
        code_action=str(proposal["previous_result_decision"]["code"]["action"])
        .strip()
        .lower(),
        state=state,
    )
    paths.PROPOSAL_PATH.unlink(missing_ok=True)
    return 0


# --- final benchmark phase -------------------------------------------------


def execute_pending_final_benchmark() -> int:
    from robot_learning.scenario import evaluate_final_model

    state = repository.read_state()
    pending = state.get("pending_final_benchmark")
    if not isinstance(pending, dict):
        raise TypeError(
            "there is no accepted lineage awaiting final benchmark evaluation"
        )
    artifact = str(pending.get("artifact", "")).strip()
    if artifact != state.get("accepted_artifact"):
        raise ValueError(
            "pending final benchmark does not identify the accepted artifact"
        )
    accepted_artifact = paths.ROOT / artifact
    repository.require_complete_artifact(
        accepted_artifact, "pending final benchmark artifact"
    )
    fingerprint = str(pending.get("fingerprint", "")).strip()
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
    state["official_metrics"] = official_metrics
    state["official_benchmark_artifact"] = fingerprint
    state["pending_final_benchmark"] = None
    repository.atomic_write_json(paths.STATE_PATH, state)
    if bool(official_metrics["goal_reached"]):
        paths.GOAL_PATH.write_text(
            f"Goal reached with {pending['selected']} from experiment {pending['experiment']}.\n",
            encoding="utf-8",
        )
    return 0


# --- training phase --------------------------------------------------------


def run_training_experiment(proposal: dict, args: argparse.Namespace) -> int:
    change = str(proposal["change"]).strip()
    hypothesis = str(proposal["hypothesis"]).strip()
    experiment_kind = str(proposal.get("kind", "training")).lower()
    parameter_overrides = proposal.get("params")
    baseline = bool(proposal.get("baseline", False))
    initialization = str(proposal.get("initialization", "transfer")).lower()
    fresh_baseline = baseline and initialization == "fresh"
    state = repository.load_state(
        allow_unmeasured=True,
        allow_missing_artifact=fresh_baseline,
    )
    # A preserved proposal is the same experiment: recovery and restart reuse
    # the identity the interrupted run allocated instead of consuming a new one.
    resuming = args.reuse_candidate is not None or paths.RESTART_PENDING_PATH.exists()
    index = (
        protocol.resumed_experiment_index(state, args.reuse_candidate)
        if resuming
        else 0
    )
    if index < 1:
        index = protocol.next_experiment_index(state)
    state["last_allocated_experiment"] = index
    recoverable_continuation = args.reuse_candidate is not None
    # A fresh baseline has no hypothesis phase to anchor it, and a retry, restart
    # or recovery keeps the anchor the unfinished research already established.
    code_parent_commit = repository.anchor_scientific_parent(state)
    # Durable before validation or training can produce anything under this
    # identity, so a rejected, crashed or interrupted experiment consumes it.
    repository.atomic_write_json(paths.STATE_PATH, state)
    candidate_dir = paths.CANDIDATE_ROOT / f"experiment-{index}"
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
            if fresh_baseline or protocol.dependency_metadata_changed(code_changes):
                execution.validate_dependency_metadata()
            execution.run_validation_suites(selected_tests)
            console.announce("[checks] passed")

        effective_config = research_config.load_experiment_config()
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
            result["replication_of"] = str(
                proposal.get("replication_of", proposal.get("family", ""))
            ).strip()
        console.announce("\n" + console.render_experiment_card(result) + "\n")
        resume = parent_artifact / "model.zip" if initialization == "transfer" else None

        if resuming and candidate_dir.exists():
            # Only the experiment's own leftovers: a new identity that collided
            # with existing data was skipped rather than allocated.
            console.announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            execution.remove_candidate_dir(candidate_dir)

        def active_training_log() -> Path:
            attempt = execution.training_attempt(
                index, recoverable_continuation=recoverable_continuation
            )
            return paths.training_log_path(index, attempt)

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
            {
                "name": path.name,
                "kind": "candidate",
                "path": path,
                **json.loads((path / "artifact.json").read_text(encoding="utf-8")),
                "evaluations": [],
            }
            for path in execution.candidate_directories(candidate_dir)
        ]
        archived_candidates = repository.archive_candidates(
            index, contenders, effective_config
        )
        verdict = "trained; awaiting researcher evaluation request"
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

        state.update(
            {
                "last_experiment": index,
                "last_verdict": verdict,
                "pending_evaluation_request": {
                    "experiment": index,
                    "candidates": archived_candidates,
                    "champion_available": not fresh_baseline,
                    "parameters": effective_config,
                    "initialization": initialization,
                    "training_budget_steps": effective_timesteps,
                    "parent_training_steps": int(parent_training_steps),
                    "baseline": baseline,
                    "code_parent_commit": code_parent_commit,
                    "research_change_paths": code_changes
                    + (["research/current_params.json"] if parameter_overrides else []),
                    "result": result,
                },
            }
        )
        result.update({"status": "trained", "verdict": verdict})
        if args.reuse_candidate is not None:
            paths.RECOVERY_PENDING_PATH.unlink(missing_ok=True)
        paths.RESTART_PENDING_PATH.unlink(missing_ok=True)
        repository.atomic_write_json(paths.STATE_PATH, state)
    except KeyboardInterrupt:
        recovery_dir = paths.CANDIDATE_ROOT / f"recovery-experiment-{index}"
        recoverable = all(
            (candidate_dir / filename).exists()
            for filename in repository.ARTIFACT_FILES
        )
        if recoverable:
            if recovery_dir.exists():
                execution.remove_candidate_dir(recovery_dir)
            candidate_dir.replace(recovery_dir)
            paths.RECOVERY_PENDING_PATH.write_text(
                str(recovery_dir.relative_to(paths.ROOT)) + "\n", encoding="utf-8"
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
        repository.atomic_write_json(paths.STATE_PATH, state)
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
    parser.add_argument("--begin-hypothesis", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.begin_hypothesis:
        return begin_hypothesis_phase()
    if args.check_proposal:
        return check_proposal()
    if args.check_evaluation_request:
        return check_evaluation_request()
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
        return resolve_pending_lineage(proposal, raw_state)
    return run_training_experiment(proposal, args)


if __name__ == "__main__":
    sys.exit(main())
