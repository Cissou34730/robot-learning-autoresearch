"""The generic research protocol: evidence, statistics, lineage and neutrality.

These tests are human-owned and immutable during a campaign. They describe how
the harness collects evidence and resolves lineage, never which learning method
produced it.
"""

import json
import re
from pathlib import Path

import pytest

from research.run_experiment import (
    apply_previous_result_decision,
    check_lineage_evidence,
    execute_pending_evaluations,
    execute_pending_final_benchmark,
)
from research.runner_execution import training_budget
from research.runner_protocol import (
    _evidence_records_compatible,
    evaluation_artifact_name,
    evaluation_semantics_fingerprint,
    evaluation_semantics_paths,
    experiment_family,
    is_protected_source,
    operation_description,
    parameter_change_records,
    plan_previous_result_decision,
    training_parent,
    validate_evaluation_request,
    validate_experiment_semantics,
    validate_proposal_against_state,
    validate_training_proposal,
)
from research.runner_repository import (
    artifact_fingerprint,
    compact_result_record,
    experiment_log_row,
    measurement_record,
    write_state,
)
from robot_learning.scenario.evaluation import (
    summarize_research_evaluations as summarize_evaluations,
)
from robot_learning.training.comparison import (
    exact_mcnemar_pvalue,
    paired_comparison,
)

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = (ROOT / "research" / "program.md").read_text(encoding="utf-8")
LOOP = (ROOT / "run_research.ps1").read_text(encoding="utf-8")

# Only used to assert that the protocol names *no* learning algorithm.
KNOWN_ALGORITHM_NAMES = ("ppo", "sac", "td3", "a2c", "ddpg")


@pytest.fixture(autouse=True)
def _allow_unchanged_research_delta(monkeypatch):
    """Ownership preflights are covered by the orchestration test modules."""
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta", lambda state: []
    )


def mentions(text: str, word: str) -> bool:
    return re.search(rf"\b{word}\b", text, flags=re.IGNORECASE) is not None


def test_the_copilot_adapter_is_a_protected_protocol_source():
    assert is_protected_source("researcher_copilot.py")


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        "research/program.md",
        "research/scenario.md",
        "research/instruments.md",
        "run_research.ps1",
        "researcher_session.ps1",
        "research/build_research_brief.py",
        "research/reset_campaign.py",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_researcher_cannot_modify_its_context_or_dependency_boundary(path):
    assert is_protected_source(path)
    with pytest.raises(ValueError, match="human-owned task, context, dependency"):
        validate_experiment_semantics({}, "training", "fresh", None, [path], False)


def test_new_hypothesis_boundary_uses_phase_aware_proposal_preflight():
    assert "--check-proposal" in LOOP
    assert "Current phase: prepare experiment $nextExperiment" in LOOP
    assert "write a lineage decision" in LOOP
    assert "failed validation: $proposalProblem" in LOOP
    assert "proposal valid for the current phase" in LOOP
    normalized_program = " ".join(PROGRAM.split())
    assert "The phase is incomplete until that deliverable exists" in normalized_program
    assert "one falsifiable hypothesis, a plausible alternative" in PROGRAM


def test_experiment_preparation_orders_question_operation_and_initialization():
    normalized_program = " ".join(PROGRAM.split())
    question = normalized_program.index("1. State the scientific question and how it serves the human objective.")
    operation = normalized_program.index("2. Choose the operation that fits that question")
    hypothesis = normalized_program.index(
        "3. State one falsifiable hypothesis, a plausible alternative"
    )
    initialization = normalized_program.index(
        "4. Justify the training parent and fresh-or-transfer initialization"
    )

    assert question < operation < hypothesis < initialization
    assert "Only after choosing the mechanism and intervention" not in PROGRAM
    assert "continuation, replication, or training with fresh or transfer" not in PROGRAM


def test_program_keeps_scientific_methods_subordinate_to_the_objective():
    normalized_program = " ".join(PROGRAM.split())

    assert "Your goal is a learned policy that satisfies the human-defined objective" in normalized_program
    assert "causal explanation and reproducibility are not prerequisites" in normalized_program
    assert "A coherent recipe may change several components" in normalized_program
    assert "All relevant evidence may inform the next investigation" in normalized_program
    assert "not a requirement to resolve every assumption before training" in normalized_program
    assert "An unsuccessful run does not automatically reject an intervention" in normalized_program
    assert "may be revised during preparation" in normalized_program
    for obsolete in (
        "Each intervention must manipulate one identifiable causal mechanism",
        "best serves the current investigation",
        "must first obtain that information",
        "measured policy behavior governs the choice of the next scientific problem",
    ):
        assert obsolete not in normalized_program


def evaluation(seed: int, outcomes: list[bool]) -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "steps": 100,
                "reward_total": 1.0,
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def test_paired_comparison_uses_identical_episode_outcomes():
    candidate = [evaluation(3000, [True, True, True, True, True, True])]
    champion = [evaluation(3000, [False, False, False, False, False, False])]

    comparison = paired_comparison(candidate, champion)

    assert comparison["candidate_wins"] == 6
    assert comparison["reference_wins"] == 0
    assert comparison["success_delta_percent"] == 100.0
    assert comparison["exact_p_value"] == pytest.approx(0.03125)


def test_paired_comparison_rejects_incompatible_episode_panels():
    with pytest.raises(ValueError, match="identical episodes"):
        paired_comparison(
            [evaluation(3000, [True, False])],
            [evaluation(4000, [True, False])],
        )


def test_evaluation_summary_consolidates_the_actual_panels():
    summary = summarize_evaluations(
        [evaluation(3000, [True, False]), evaluation(4000, [True] * 8)]
    )

    assert summary["episodes"] == 10
    assert summary["seed_count"] == 2
    assert summary["pooled_success_percent"] == pytest.approx(90.0)
    assert "failure_diagnostics" not in summary


def test_exact_p_value_is_one_without_discordant_episodes():
    assert exact_mcnemar_pvalue(0, 0) == 1.0


def test_requested_evaluations_resume_without_repeating_completed_work(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    baseline_path = tmp_path / "BASELINE_PENDING"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 4,
            "candidates": [
                {
                    "name": "checkpoint-100",
                    "artifact": "archive/checkpoint-100",
                    "timesteps": 100,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 100,
            "parent_training_steps": 0,
            "baseline": True,
            "result": {"index": 4, "change": "baseline", "hypothesis": "measure"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "question": "Is the baseline stable across two seed panels?",
                "reason": "Two panels bound seed variance before any comparison.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint-100",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first panel",
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint-100",
                        "episodes": 2,
                        "seed": 2000,
                        "label": "second panel",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    _artifact(tmp_path / "archive" / "checkpoint")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", tmp_path)
    monkeypatch.setattr("research.runner_paths.BASELINE_PENDING_PATH", baseline_path)

    def skip_result_recording(result):
        del result

    def skip_result_commit(index, change):
        del index, change

    monkeypatch.setattr(
        "research.runner_repository.append_result", skip_result_recording
    )
    monkeypatch.setattr("research.runner_repository.commit_result", skip_result_commit)

    calls: list[int] = []

    def interrupt_second(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", interrupt_second)
    assert execute_pending_evaluations() == 130
    assert calls == [1000, 2000]

    request_path.unlink()
    resumed_calls: list[int] = []

    def finish(artifact, seed, **kwargs):
        del artifact, kwargs
        resumed_calls.append(seed)
        return evaluation(seed, [True, True])

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", finish)
    assert execute_pending_evaluations() == 0
    assert resumed_calls == [2000]
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = final_state["pending_researcher_decision"]["candidates"][0]
    assert len(candidate["evaluations"]) == 2
    assert candidate["summary"]["episodes"] == 4


def test_evaluation_deduplication_ignores_label(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "checkpoint",
                            "artifact": "archive/checkpoint",
                            "timesteps": 100,
                            "evaluations": [],
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "fresh",
                    "training_budget_steps": 100,
                    "parent_training_steps": 0,
                    "baseline": True,
                    "result": {
                        "index": 4,
                        "change": "baseline",
                        "hypothesis": "measure",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "question": "Does relabelling a panel change the measurement?",
                "reason": "One panel is enough to check measurement identity.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first",
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "renamed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )

    def skip_result_recording(result):
        del result

    monkeypatch.setattr(
        "research.runner_repository.append_result", skip_result_recording
    )
    calls = []

    def record_evaluation(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        return evaluation(seed, [True, False])

    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", record_evaluation
    )

    assert execute_pending_evaluations() == 0
    assert calls == [1000]
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        len(final_state["pending_researcher_decision"]["candidates"][0]["evaluations"])
        == 1
    )


def test_researcher_can_request_evaluations_across_two_rounds(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "checkpoint",
                            "artifact": "archive/checkpoint",
                            "timesteps": 100,
                            "evaluations": [],
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "fresh",
                    "training_budget_steps": 100,
                    "parent_training_steps": 0,
                    "result": {"index": 4, "change": "measure", "hypothesis": "test"},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )
    monkeypatch.setattr("research.runner_repository.append_result", lambda result: None)

    calls: list[int] = []

    def record_evaluation(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        return evaluation(seed, [True, False])

    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", record_evaluation
    )
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "question": "Is one panel enough to judge the candidate?",
                "reason": "Start narrow and widen only if the evidence is unclear.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                    },
                ],
                "need_more_evidence": True,
            }
        ),
        encoding="utf-8",
    )

    assert execute_pending_evaluations() == 0
    first_round = json.loads(state_path.read_text(encoding="utf-8"))
    assert calls == [1000]
    assert first_round["pending_researcher_decision"] is None
    assert [
        item["seed"]
        for item in first_round["pending_evaluation_request"]["partial_evaluations"]
    ] == [1000]

    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "question": "Does a second seed panel confirm the first?",
                "reason": "The first round was too narrow to decide.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "reused A",
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 2000,
                        "label": "new B",
                    },
                ],
                "need_more_evidence": False,
            }
        ),
        encoding="utf-8",
    )

    assert execute_pending_evaluations() == 0
    second_round = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = second_round["pending_researcher_decision"]["candidates"][0]
    assert calls == [1000, 2000]
    assert [item["seed"] for item in candidate["evaluations"]] == [1000, 2000]
    assert candidate["summary"]["episodes"] == 4


def _single_panel_evaluation_fixture(monkeypatch, tmp_path):
    """A pending experiment with one candidate and one requested panel."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    evaluations_dir = tmp_path / "research" / "evaluations"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 9,
                    "candidates": [
                        {
                            "name": "checkpoint",
                            "artifact": "archive/checkpoint",
                            "timesteps": 100,
                            "evaluations": [],
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "fresh",
                    "training_budget_steps": 100,
                    "parent_training_steps": 0,
                    "result": {
                        "index": 9,
                        "change": "instrumented",
                        "hypothesis": "measure",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    request_path.write_text(
        json.dumps(
            {
                "experiment": 9,
                "question": "What does the saved policy actually do?",
                "reason": "One panel under the current instrumentation.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", evaluations_dir)
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )
    return state_path, request_path, evaluations_dir


def _recording_evaluator(monkeypatch, payload_for):
    """Stand in for the evaluator subprocess: write the artifact, return it."""
    calls: list[int] = []

    def evaluate(artifact, seed, output_path=None, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        payload = payload_for(seed)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)
    return calls


# Deliberately meaningless: the runner must never learn what these mean.
ARBITRARY_EVIDENCE = {
    "zorble_index": {"quux": [1, 2, 3], "frobnitz": {"nested": [{"deep": True}]}},
    "wibble": 4.25,
    "flumps": ["a", "b"],
}


def test_researcher_evidence_reaches_the_artifact_and_stays_out_of_state(
    monkeypatch, tmp_path
):
    state_path, _, evaluations_dir = _single_panel_evaluation_fixture(
        monkeypatch, tmp_path
    )
    recorded: list[dict] = []
    monkeypatch.setattr("research.runner_repository.append_result", recorded.append)

    def payload(seed):
        measurement = evaluation(seed, [True, False])
        measurement["research_evidence"] = ARBITRARY_EVIDENCE
        return measurement

    _recording_evaluator(monkeypatch, payload)

    assert execute_pending_evaluations() == 0

    artifacts = sorted(evaluations_dir.glob("*.json"))
    assert len(artifacts) == 1
    stored = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert stored["research_evidence"] == ARBITRARY_EVIDENCE

    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = final_state["pending_researcher_decision"]["candidates"][0]
    measurement = candidate["evaluations"][0]
    assert "research_evidence" not in measurement
    assert measurement["evaluation_artifact"] == (
        artifacts[0].relative_to(tmp_path).as_posix()
    )
    # Paired comparison still needs episode outcomes; the evidence blob does not.
    assert [item["episode"] for item in measurement["episode_results"]] == [0, 1]
    assert "research_evidence" not in json.dumps(final_state)


def test_recorded_history_keeps_references_not_detailed_evidence(monkeypatch, tmp_path):
    _single_panel_evaluation_fixture(monkeypatch, tmp_path)
    recorded: list[dict] = []
    monkeypatch.setattr(
        "research.runner_repository.append_result",
        lambda result: recorded.append(compact_result_record(result)),
    )

    def payload(seed):
        measurement = evaluation(seed, [True, False])
        measurement["research_evidence"] = ARBITRARY_EVIDENCE
        return measurement

    _recording_evaluator(monkeypatch, payload)

    assert execute_pending_evaluations() == 0

    history = recorded[0]
    serialized = json.dumps(history)
    assert "research_evidence" not in serialized
    assert "episode_results" not in serialized
    assert "zorble_index" not in serialized
    measurement = history["candidates"][0]["evaluations"][0]
    assert measurement["evaluation_artifact"].endswith(".json")
    assert measurement["success_percent"] == 50.0


def test_pending_evaluation_transition_rewrites_legacy_artifact_paths(
    monkeypatch, tmp_path
):
    state_path, _, _ = _single_panel_evaluation_fixture(monkeypatch, tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pending_evaluation_request"]["candidates"][0]["artifact"] = (
        "archive\\checkpoint"
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    results_path = tmp_path / "results.jsonl"
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", results_path)
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "EXPERIMENTS.md")
    _recording_evaluator(monkeypatch, lambda seed: evaluation(seed, [True]))

    assert execute_pending_evaluations() == 0

    persisted_state = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = persisted_state["pending_researcher_decision"]["candidates"][0]
    assert candidate["artifact"] == "archive/checkpoint"
    result = json.loads(results_path.read_text(encoding="utf-8"))
    assert result["candidates"][0]["artifact"] == "archive/checkpoint"


def test_changed_evaluation_semantics_force_a_new_measurement(monkeypatch, tmp_path):
    _, request_path, evaluations_dir = _single_panel_evaluation_fixture(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr("research.runner_repository.append_result", lambda result: None)
    calls = _recording_evaluator(monkeypatch, lambda seed: evaluation(seed, [True]))

    def request_same_panel(more_evidence: bool) -> None:
        request_path.write_text(
            json.dumps(
                {
                    "experiment": 9,
                    "question": "What does this panel show now?",
                    "reason": "Measurement identity is what is under test.",
                    "measurements": [
                        {
                            "instrument": "research_evaluation",
                            "candidate": "checkpoint",
                            "episodes": 2,
                            "seed": 1000,
                        }
                    ],
                    "need_more_evidence": more_evidence,
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "research.runner_protocol.evaluation_semantics_fingerprint", lambda: "before"
    )
    request_same_panel(True)
    assert execute_pending_evaluations() == 0
    assert calls == [1000]

    # Unchanged semantics: the completed identical measurement is reused.
    request_same_panel(True)
    assert execute_pending_evaluations() == 0
    assert calls == [1000]

    # Re-instrumented: the same candidate, episodes and seed is a new fact.
    monkeypatch.setattr(
        "research.runner_protocol.evaluation_semantics_fingerprint", lambda: "after"
    )
    request_same_panel(False)
    assert execute_pending_evaluations() == 0
    assert calls == [1000, 1000]
    assert len(sorted(evaluations_dir.glob("*.json"))) == 2


def _semantics_tree(tmp_path):
    """A miniature repository holding the measurement-relevant surface."""
    scenario = tmp_path / "robot_learning" / "scenario"
    scenario.mkdir(parents=True)
    for name in (
        "__init__.py",
        "environment.py",
        "evaluation.py",
        "final_benchmark.py",
        "observations.py",
        "policy_io.py",
        "progress.py",
        "reward.py",
        "training_environment.py",
        "viewer.py",
    ):
        content = "original\n"
        (scenario / name).write_text(content, encoding="utf-8")
    training = tmp_path / "robot_learning" / "training"
    training.mkdir(parents=True)
    for name in ("algorithms.py", "normalization.py"):
        (training / name).write_text("original\n", encoding="utf-8")
    (tmp_path / "robot_learning" / "evaluate.py").write_text(
        "original\n", encoding="utf-8"
    )
    (tmp_path / "robot_learning" / "policy_runtime.py").write_text(
        "original\n", encoding="utf-8"
    )
    research = tmp_path / "research"
    research.mkdir(parents=True)
    (research / "build_research_brief.py").write_text("original\n", encoding="utf-8")
    (tmp_path / "run_research.ps1").write_text("original\n", encoding="utf-8")
    return scenario


def test_evaluation_semantics_fingerprint_covers_researcher_measurement_state(
    monkeypatch, tmp_path
):
    scenario = _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    assert evaluation_semantics_paths() == [
        "robot_learning/evaluate.py",
        "robot_learning/policy_runtime.py",
        "robot_learning/scenario/environment.py",
        "robot_learning/scenario/evaluation.py",
    ]

    original = evaluation_semantics_fingerprint()
    assert original == evaluation_semantics_fingerprint()

    # Editing an existing researcher-owned module changes measurement identity.
    (scenario / "evaluation.py").write_text("instrumented\n", encoding="utf-8")
    edited = evaluation_semantics_fingerprint()
    assert edited != original

    # So does adding one, even before anything imports it.
    (scenario / "instrumentation.py").write_text("probe\n", encoding="utf-8")
    extended = evaluation_semantics_fingerprint()
    assert extended != edited

    # Renaming it changes identity even though the contents are unchanged.
    (scenario / "instrumentation.py").rename(scenario / "analysis.py")
    assert evaluation_semantics_fingerprint() != extended

    # Removing it returns to the previous identity.
    (scenario / "analysis.py").unlink()
    assert evaluation_semantics_fingerprint() == edited

    # Researcher-owned measurement data counts as much as researcher-owned code.
    config = scenario / "measurement_config.json"
    config.write_text('{"window": 1}', encoding="utf-8")
    with_data = evaluation_semantics_fingerprint()
    assert with_data != edited
    config.write_text('{"window": 2}', encoding="utf-8")
    assert evaluation_semantics_fingerprint() != with_data


def test_evaluation_semantics_fingerprint_excludes_training_only_reward(
    monkeypatch, tmp_path
):
    scenario = _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    original = evaluation_semantics_fingerprint()
    (scenario / "reward.py").write_text("changed reward\n", encoding="utf-8")
    assert evaluation_semantics_fingerprint() == original
    (scenario / "training_environment.py").write_text(
        "changed training environment\n", encoding="utf-8"
    )
    assert evaluation_semantics_fingerprint() == original

    (scenario / "evaluation.py").write_text("changed evaluator\n", encoding="utf-8")
    assert evaluation_semantics_fingerprint() != original


def _comparison_record(
    evaluation_semantics: str,
    *,
    episodes: int = 200,
    seed: int = 10,
    episode_identities: list[tuple[int, int]] | None = None,
) -> dict:
    record = {
        "instrument": "research_evaluation",
        "settings": (
            "research_evaluation",
            episodes,
            seed,
            evaluation_semantics,
        )
    }
    if episode_identities is not None:
        record["episode_identities"] = episode_identities
    return record


@pytest.mark.parametrize(
    ("candidate", "reference", "compatible"),
    [
        (
            _comparison_record("same-semantics"),
            _comparison_record("same-semantics"),
            True,
        ),
        (
            _comparison_record("semantics-a"),
            _comparison_record("semantics-b"),
            False,
        ),
        (
            _comparison_record("legacy", episode_identities=[(0, 10)]),
            _comparison_record(
                "legacy", episode_identities=[(0, 10)],
            ),
            True,
        ),
        (
            _comparison_record("legacy-a"),
            _comparison_record("legacy-b"),
            False,
        ),
        (
            _comparison_record("same", episodes=100),
            _comparison_record("same", episodes=200),
            False,
        ),
        (
            _comparison_record("same", seed=10),
            _comparison_record("same", seed=11),
            False,
        ),
        (
            _comparison_record("same", episode_identities=[(0, 10)]),
            _comparison_record("same", episode_identities=[(0, 11)]),
            False,
        ),
    ],
)
def test_evaluation_semantics_are_the_compatibility_identity(
    candidate, reference, compatible
):
    assert _evidence_records_compatible(candidate, reference) is compatible


@pytest.mark.parametrize(
    "relative",
    [
        "robot_learning/evaluate.py",
        "robot_learning/policy_runtime.py",
    ],
)
def test_non_scenario_evaluation_dependencies_change_measurement_identity(
    monkeypatch, tmp_path, relative
):
    _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    original = evaluation_semantics_fingerprint()
    (tmp_path / relative).write_text("changed\n", encoding="utf-8")

    assert evaluation_semantics_fingerprint() != original


@pytest.mark.parametrize(
    "relative",
    [
        "robot_learning/scenario/policy_io.py",
        "robot_learning/scenario/observations.py",
        "robot_learning/training/algorithms.py",
        "robot_learning/training/normalization.py",
    ],
)
def test_model_contained_sources_do_not_change_measurement_identity(
    monkeypatch, tmp_path, relative
):
    _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    original = evaluation_semantics_fingerprint()
    (tmp_path / relative).write_text("changed\n", encoding="utf-8")

    assert evaluation_semantics_fingerprint() == original


def test_presentation_and_generated_files_stay_out_of_measurement_identity(
    monkeypatch, tmp_path
):
    scenario = _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    original = evaluation_semantics_fingerprint()

    # Presentation-only scenario code never changes what was measured.
    for name in ("progress.py", "viewer.py"):
        (scenario / name).write_text("restyled\n", encoding="utf-8")
    assert evaluation_semantics_fingerprint() == original

    # Neither do the loop or the compact-context builder.
    (tmp_path / "research" / "build_research_brief.py").write_text(
        "restyled\n", encoding="utf-8"
    )
    (tmp_path / "run_research.ps1").write_text("restyled\n", encoding="utf-8")
    assert evaluation_semantics_fingerprint() == original

    # Neither do build or scratch products under the scenario package.
    cache = scenario / "__pycache__"
    cache.mkdir()
    (cache / "evaluation.cpython-313.pyc").write_bytes(b"\x00compiled")
    tool_cache = scenario / ".mypy_cache" / "3.13"
    tool_cache.mkdir(parents=True)
    (tool_cache / "evaluation.data.json").write_text("{}", encoding="utf-8")
    (scenario / "evaluation.py.tmp").write_text("scratch\n", encoding="utf-8")
    (scenario / ".DS_Store").write_bytes(b"junk")
    assert evaluation_semantics_fingerprint() == original


def test_protected_scenario_files_stay_out_of_measurement_identity(
    monkeypatch, tmp_path
):
    scenario = _semantics_tree(tmp_path)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)

    original = evaluation_semantics_fingerprint()
    for name in ("__init__.py", "final_benchmark.py"):
        (scenario / name).write_text("changed\n", encoding="utf-8")

    assert evaluation_semantics_fingerprint() == original


def test_pending_result_requires_an_explicit_researcher_decision():
    state = {
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [],
            "champion_available": True,
        }
    }

    with pytest.raises(ValueError, match="previous_result_decision"):
        apply_previous_result_decision({}, state)


def _attested_lineage_state(monkeypatch, tmp_path):
    """A pending decision whose experiment produced one detailed artifact."""
    _artifact(tmp_path / "archive" / "candidate")
    artifacts = tmp_path / "research" / "evaluations"
    artifacts.mkdir(parents=True)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", artifacts)
    state = _decision_state(
        "archive/candidate", _measured(tmp_path, "candidate", artifacts)
    )
    return (
        state,
        "research/evaluations/evaluation-experiment-8-candidate-2ep-seed44-ab.json",
    )


def test_lineage_decision_requires_attested_current_experiment_evidence(
    monkeypatch, tmp_path
):
    state, artifact = _attested_lineage_state(monkeypatch, tmp_path)
    _attest(monkeypatch, tmp_path, 8, [artifact])

    assert not apply_previous_result_decision(_lineage_decision(), state)


@pytest.mark.parametrize(
    ("paths", "label", "message"),
    [
        # No attestation line at all.
        ([], "Notes", "Evidence inspected"),
        # Names an artifact that was never written.
        (
            ["research/evaluations/evaluation-experiment-8-ghost-2ep-seed44-ab.json"],
            "Evidence inspected",
            "at least one detailed source",
        ),
        # Names a real artifact belonging to a different experiment.
        (
            ["research/evaluations/evaluation-experiment-2-other-2ep-seed44-ab.json"],
            "Evidence inspected",
            "at least one detailed source",
        ),
    ],
)
def test_unattested_lineage_decision_is_rejected(
    monkeypatch, tmp_path, paths, label, message
):
    state, _ = _attested_lineage_state(monkeypatch, tmp_path)
    (
        tmp_path
        / "research"
        / "evaluations"
        / "evaluation-experiment-2-other-2ep-seed44-ab.json"
    ).write_text("{}", encoding="utf-8")
    _attest(monkeypatch, tmp_path, 8, paths or ["none"], label=label)

    with pytest.raises(ValueError, match=message):
        apply_previous_result_decision(_lineage_decision(), state)


def test_attested_artifact_must_exist_on_disk(monkeypatch, tmp_path):
    state, artifact = _attested_lineage_state(monkeypatch, tmp_path)
    _attest(monkeypatch, tmp_path, 8, [artifact])
    (tmp_path / artifact).unlink()

    with pytest.raises(ValueError, match="do not exist"):
        apply_previous_result_decision(_lineage_decision(), state)


def test_lineage_evidence_preflight_matches_the_runner_decision(monkeypatch, tmp_path):
    state, artifact = _attested_lineage_state(monkeypatch, tmp_path)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    _attest(monkeypatch, tmp_path, 8, ["research/evaluations/absent.json"])
    assert check_lineage_evidence(8) == 1

    _attest(monkeypatch, tmp_path, 8, [artifact])
    assert check_lineage_evidence(8) == 0
    # A lineage decision is only checkable for the experiment actually pending.
    assert check_lineage_evidence(9) == 1


class UninspectableEvidence:
    """Fails loudly if generic code looks inside the researcher's channel."""

    def __getattr__(self, name):
        raise AssertionError(f"generic code read research_evidence.{name}")

    def __getitem__(self, key):
        raise AssertionError(f"generic code read research_evidence[{key!r}]")

    def __iter__(self):
        raise AssertionError("generic code iterated research_evidence")

    def __len__(self):
        raise AssertionError("generic code sized research_evidence")


def test_generic_compaction_never_inspects_the_evidence_channel():
    opaque = UninspectableEvidence()
    metrics = {
        "episodes": 2,
        "seed": 44,
        "success_percent": 50.0,
        "model": "models/candidates/x/model.zip",
        "episode_results": [{"episode": 0, "success": True}],
        "research_evidence": opaque,
    }

    state_record = measurement_record(metrics)
    assert "research_evidence" not in state_record
    assert state_record["episode_results"] == metrics["episode_results"]
    json.dumps(state_record, sort_keys=True)

    history = compact_result_record(
        {
            "index": 4,
            "candidates": [{"name": "c", "evaluations": [dict(metrics)]}],
            "requested_evaluations": [{"candidate": "c", "metrics": dict(metrics)}],
        }
    )
    serialized = json.dumps(history, sort_keys=True)
    assert "research_evidence" not in serialized
    assert "episode_results" not in serialized


def test_result_persistence_canonicalizes_legacy_artifact_references(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    result = {
        "candidates": [
            {
                "artifact": "research\\checkpoints\\candidate",
                "evaluations": [
                    {"evaluation_artifact": ("research\\evaluations\\candidate.json")}
                ],
            }
        ],
        "task_reference_evaluations": [
            {"evaluation_artifact": "research\\evaluations\\reference.json"}
        ],
    }

    history = compact_result_record(result)

    assert history["candidates"][0]["artifact"] == ("research/checkpoints/candidate")
    assert (
        history["candidates"][0]["evaluations"][0]["evaluation_artifact"]
        == "research/evaluations/candidate.json"
    )
    assert history["task_reference_evaluations"][0]["evaluation_artifact"] == (
        "research/evaluations/reference.json"
    )
    assert result["task_reference_evaluations"][0]["evaluation_artifact"] == (
        "research\\evaluations\\reference.json"
    )


def test_state_persistence_canonicalizes_known_legacy_artifact_references(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "research_state.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    for index in range(6):
        _artifact(tmp_path / "archive" / f"model-{index}")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    state = {
        "accepted_artifact": "research\\checkpoints\\accepted",
        "accepted_evaluations": ["research\\evaluations\\accepted.json"],
        "retained_lineages": [
            {
                "artifact": "research\\checkpoints\\retained",
                "evaluation_artifacts": ["research\\evaluations\\retained.json"],
            }
        ],
        "pending_evaluation_request": {
            "candidates": [{"artifact": "research\\checkpoints\\candidate"}]
        },
    }

    write_state(state)

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["accepted_artifact"] == "research/checkpoints/accepted"
    assert persisted["accepted_evaluations"] == ["research/evaluations/accepted.json"]
    assert persisted["retained_lineages"][0]["artifact"] == (
        "research/checkpoints/retained"
    )
    assert persisted["retained_lineages"][0]["evaluation_artifacts"] == [
        "research/evaluations/retained.json"
    ]
    assert (
        persisted["pending_evaluation_request"]["candidates"][0]["artifact"]
        == "research/checkpoints/candidate"
    )


def test_opaque_evidence_survives_the_whole_execution_path(monkeypatch, tmp_path):
    state_path, _, _ = _single_panel_evaluation_fixture(monkeypatch, tmp_path)
    recorded: list[dict] = []
    monkeypatch.setattr(
        "research.runner_repository.append_result",
        lambda result: recorded.append(compact_result_record(result)),
    )

    def payload(seed):
        measurement = evaluation(seed, [True, False])
        measurement["research_evidence"] = UninspectableEvidence()
        return measurement

    def evaluate(artifact, seed, output_path=None, **kwargs):
        del artifact, kwargs
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("{}", encoding="utf-8")
        return payload(seed)

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)

    # Any generic read of the channel would raise before this returns.
    assert execute_pending_evaluations() == 0
    assert "research_evidence" not in state_path.read_text(encoding="utf-8")
    assert "research_evidence" not in json.dumps(recorded[0], sort_keys=True)


def test_researcher_can_select_an_archived_candidate_as_next_lineage(
    monkeypatch, tmp_path
):
    candidate = tmp_path / "archive" / "candidate-2"
    candidate.mkdir(parents=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (candidate / filename).write_bytes(b"artifact")
    summary = summarize_evaluations([evaluation(3000, [True, False])])
    state = {
        "accepted_artifact": "accepted",
        "accepted_training_steps": 0,
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [
                {
                    "name": "candidate-2",
                    "artifact": "archive/candidate-2",
                    "summary": summary,
                }
            ],
            "champion_available": False,
            "parameters": {"algorithm": {"name": "active-method"}},
            "initialization": "fresh",
            "training_budget_steps": 120_000,
        },
    }
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr(
        "research.runner_paths.STATE_PATH", tmp_path / "research_state.json"
    )
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    reached = apply_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 7,
                "continue_from": "candidate-2",
                "reason": "It is the most useful measured lineage.",
                "code": {
                    "action": "keep",
                    "reason": "The learning change remains the useful parent.",
                },
            }
        },
        state,
    )

    assert not reached
    assert (tmp_path / "accepted" / "model.zip").read_bytes() == b"artifact"
    assert state["accepted_metrics"] == summary
    assert state["accepted_training_steps"] == 120_000
    assert state["pending_researcher_decision"] is None


def test_runner_uses_the_human_defined_budget_for_all_initializations():
    assert training_budget(120_000, "transfer", False, 720_000) == 120_000
    assert training_budget(120_000, "fresh", False, 720_000) == 120_000
    assert training_budget(120_000, "fresh", True, 720_000) == 120_000


def test_experiment_card_records_exact_nested_parameter_changes():
    previous = {"method": {"rollout_steps": 4096, "learning_rate": 5e-5}}
    overrides = {"method": {"rollout_steps": 16384}}

    changes = parameter_change_records(previous, overrides)

    assert changes == [{"path": "method.rollout_steps", "before": 4096, "after": 16384}]
    assert experiment_family({}, "training", changes, []) == "method.rollout_steps"


def test_declared_code_family_is_stable_across_numeric_variants():
    proposal = {"family": "reward.outside_boundary_penalty"}

    assert (
        experiment_family(
            proposal,
            "training",
            [],
            ["robot_learning/rewards/reach_reward.py"],
        )
        == "reward.outside_boundary_penalty"
    )


def _artifact(path):
    path.mkdir(parents=True, exist_ok=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (path / filename).write_bytes(b"artifact")
    return path


def _decision_state(candidate_artifact, measurements):
    return {
        "accepted_artifact": "accepted",
        "accepted_training_steps": 0,
        "pending_researcher_decision": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": candidate_artifact,
                    "timesteps": 120_000,
                    "evaluations": measurements,
                    "summary": summarize_evaluations(measurements),
                }
            ],
            "champion_available": False,
            "parameters": {"algorithm": {"name": "active-method"}},
            "initialization": "fresh",
            "training_budget_steps": 120_000,
        },
    }


def _lineage_decision():
    return {
        "previous_result_decision": {
            "experiment": 8,
            "continue_from": "candidate",
            "reason": "Measured policy is the useful parent.",
            "code": {"action": "keep", "reason": "Keep the measured method."},
        }
    }


def test_final_benchmark_runs_after_separate_lineage_resolution(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")

    state = _decision_state("archive/candidate", [evaluation(1000, [True] * 2)])
    request = _lineage_decision()
    request["previous_result_decision"]["request_final_benchmark"] = True
    calls = []
    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark.evaluate_final_model",
        lambda model: (
            calls.append(model)
            or {
                "episodes": 200,
                "seed": 1000,
                "success_percent": 100.0,
                "goal_reached": True,
            }
        ),
    )
    assert not apply_previous_result_decision(request, state)
    assert calls == []
    assert state["pending_researcher_decision"] is None
    assert state["pending_final_benchmark"]["artifact"] == "accepted"
    assert not (tmp_path / "GOAL_REACHED").exists()

    assert execute_pending_final_benchmark() == 0
    assert calls == [tmp_path / "accepted" / "model.zip"]
    persisted = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert persisted["official_metrics"]["success_percent"] == 100.0
    assert persisted["pending_final_benchmark"] is None
    assert persisted["official_benchmark_verdict"] == "goal_reached"
    assert persisted["terminal_campaign_status"] == "goal_reached"
    assert (tmp_path / "GOAL_REACHED").exists()


def test_legacy_champion_path_is_canonicalized_before_final_benchmark(
    monkeypatch, tmp_path
):
    accepted = _artifact(tmp_path / "research" / "checkpoints" / "accepted")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", accepted)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    state = {
        "accepted_artifact": "research\\checkpoints\\accepted",
        "accepted_metrics": {"success_percent": 50.0},
        "accepted_parameters": {},
        "accepted_training_steps": 100,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 8,
            "candidates": [],
            "champion_available": True,
            "champion_evaluations": [],
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 100,
        },
    }
    decision = {
        "previous_result_decision": {
            "experiment": 8,
            "continue_from": "champion",
            "reason": "Keep the accepted lineage.",
            "code": {"action": "keep", "reason": "Keep the accepted code."},
            "request_final_benchmark": True,
        }
    }
    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark.evaluate_final_model",
        lambda model: {
            "episodes": 1,
            "seed": 1000,
            "success_percent": 50.0,
            "goal_reached": False,
        },
    )

    assert not apply_previous_result_decision(decision, state)
    assert state["accepted_artifact"] == "research/checkpoints/accepted"
    assert state["pending_final_benchmark"]["artifact"] == state["accepted_artifact"]
    assert execute_pending_final_benchmark() == 0


def test_pending_final_benchmark_survives_failure_and_failed_result(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    state = _decision_state("archive/candidate", [evaluation(1000, [True] * 2)])
    request = _lineage_decision()
    request["previous_result_decision"]["request_final_benchmark"] = True
    assert not apply_previous_result_decision(request, state)

    def failed_benchmark(model):
        del model
        raise RuntimeError("benchmark crashed")

    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark.evaluate_final_model", failed_benchmark
    )
    with pytest.raises(RuntimeError, match="benchmark crashed"):
        execute_pending_final_benchmark()
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        persisted["pending_final_benchmark"]["fingerprint"]
        == state["pending_final_benchmark"]["fingerprint"]
    )
    assert persisted["official_metrics"] is None

    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark.evaluate_final_model",
        lambda model: {
            "episodes": 200,
            "seed": 1000,
            "success_percent": 97.5,
            "goal_reached": False,
        },
    )
    assert execute_pending_final_benchmark() == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_final_benchmark"] is None
    assert persisted["official_metrics"]["success_percent"] == 97.5
    assert not (tmp_path / "GOAL_REACHED").exists()


def test_v4_final_benchmark_freezes_best_known_and_records_terminal_failure(
    monkeypatch, tmp_path
):
    artifact = _artifact(tmp_path / "archive" / "best-known")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    fingerprint = artifact_fingerprint(artifact)
    best_known = {
        "artifact": "archive/best-known",
        "fingerprint": fingerprint,
        "origin_experiment": 8,
        "candidate": "candidate",
        "parameters": {},
        "scientific_commit": "abc123",
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Measured model selected for official assessment.",
    }
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": best_known.copy(),
        "best_known_lineage": best_known.copy(),
        "retained_lineages": [],
        "pending_final_benchmark": {
            "experiment": 8,
            "selected": "best_known",
            "artifact": best_known["artifact"],
            "fingerprint": fingerprint,
            "best_known": best_known.copy(),
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(
        "robot_learning.scenario.final_benchmark.evaluate_final_model",
        lambda model: {"goal_reached": False, "model": str(model)},
    )

    assert execute_pending_final_benchmark() == 0

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_final_benchmark"] is None
    assert persisted["official_benchmark_artifact"] == fingerprint
    assert persisted["official_benchmark_model"] == {
        "selected": "best_known",
        "artifact": "archive/best-known",
        "fingerprint": fingerprint,
    }
    assert persisted["official_benchmark_verdict"] == "goal_not_reached"
    assert persisted["terminal_campaign_status"] == "goal_not_reached"
    assert not (tmp_path / "GOAL_REACHED").exists()


def test_v4_final_benchmark_rejects_a_pending_request_that_does_not_match_best_known(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 4,
                "best_known_lineage": {"artifact": "archive/best", "fingerprint": "best"},
                "pending_final_benchmark": {
                    "selected": "best_known",
                    "artifact": "archive/other",
                    "fingerprint": "other",
                    "best_known": {"artifact": "archive/other", "fingerprint": "other"},
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match the v4 best-known"):
        execute_pending_final_benchmark()


def test_terminal_campaign_rejects_new_proposals():
    with pytest.raises(ValueError, match="terminal official assessment"):
        validate_proposal_against_state(
            {"hypothesis": "another run"},
            {"terminal_campaign_status": "goal_not_reached"},
        )


def test_identical_artifact_cannot_repeat_final_benchmark(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    decision = _lineage_decision()
    decision["previous_result_decision"]["request_final_benchmark"] = True
    fingerprint = plan_previous_result_decision(decision, state)["selected_fingerprint"]
    state["official_benchmark_artifact"] = fingerprint

    with pytest.raises(ValueError, match="already received"):
        plan_previous_result_decision(decision, state)


def test_research_evaluation_request_rejects_official_benchmark(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": "archive/candidate",
                    "timesteps": 1,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Can the official benchmark decide this lineage?",
                "reason": "It must not; the request has to be rejected.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "candidate",
                        "episodes": 200,
                        "seed": 1000,
                        "official_benchmark": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    with pytest.raises(ValueError, match="unsupported fields"):
        execute_pending_evaluations()


@pytest.mark.parametrize("distinct_count", [1, 2, 3])
def test_evaluation_request_accepts_up_to_three_distinct_models(
    distinct_count, monkeypatch, tmp_path
):
    """Requests with 1-3 distinct models are accepted."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": f"model-{i}",
                    "artifact": f"archive/model-{i}",
                    "timesteps": 1,
                    "evaluations": [],
                }
                for i in range(distinct_count)
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": f"model-{i}",
                        "episodes": 2,
                        "seed": 1000,
                    }
                    for i in range(distinct_count)
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    # Should not raise; validation passes.
    from research.runner_protocol import validate_evaluation_request

    request = json.loads(request_path.read_text(encoding="utf-8"))
    validate_evaluation_request(request)


def test_evaluation_request_rejects_more_than_three_distinct_models(
    monkeypatch, tmp_path
):
    """Requests with 4+ distinct models are rejected during validation."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": f"model-{i}",
                    "artifact": f"archive/model-{i}",
                    "timesteps": 1,
                    "evaluations": [],
                }
                for i in range(4)
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": f"model-{i}",
                        "episodes": 2,
                        "seed": 1000,
                    }
                    for i in range(4)
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    with pytest.raises(ValueError, match="at most 3 distinct models.*4 requested"):
        execute_pending_evaluations()


def test_repeated_measurements_of_same_model_count_once(monkeypatch, tmp_path):
    """Multiple measurements of the same model count as one toward the limit."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "single-model",
                    "artifact": "archive/single-model",
                    "timesteps": 1,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "single-model",
                        "episodes": 2,
                        "seed": 1000,
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "single-model",
                        "episodes": 2,
                        "seed": 2000,
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "single-model",
                        "episodes": 4,
                        "seed": 3000,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    # Should not raise; counts as 1 distinct model.
    from research.runner_protocol import validate_evaluation_request

    request = json.loads(request_path.read_text(encoding="utf-8"))
    validate_evaluation_request(request)


def test_different_instruments_same_model_count_once(monkeypatch, tmp_path):
    """Different instruments for the same model count as one toward the limit."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": "archive/candidate",
                    "timesteps": 1,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "candidate",
                        "episodes": 2,
                        "seed": 1000,
                    },
                    {"instrument": "task_reference", "candidate": "candidate"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    # Should not raise; counts as 1 distinct model.
    from research.runner_protocol import validate_evaluation_request

    request = json.loads(request_path.read_text(encoding="utf-8"))
    validate_evaluation_request(request)


def test_paired_comparisons_excluded_from_model_count(monkeypatch, tmp_path):
    """Paired comparisons do not count toward the three-model limit."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "model-a",
                    "artifact": "archive/model-a",
                    "timesteps": 1,
                    "evaluations": [],
                },
                {
                    "name": "model-b",
                    "artifact": "archive/model-b",
                    "timesteps": 1,
                    "evaluations": [],
                },
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "model-a",
                        "episodes": 2,
                        "seed": 1000,
                    },
                    {
                        "instrument": "research_evaluation",
                        "candidate": "model-b",
                        "episodes": 2,
                        "seed": 1000,
                    },
                ],
                "paired_comparisons": [
                    {"candidate": "model-a", "reference": "model-b"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    # Should not raise; paired comparisons are ignored in the count.
    request = json.loads(request_path.read_text(encoding="utf-8"))
    validate_evaluation_request(request)


def test_evaluation_request_allows_omitted_need_more_evidence():
    validate_evaluation_request(
        {
            "question": "question",
            "reason": "reason",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "candidate",
                    "episodes": 2,
                    "seed": 1000,
                }
            ],
        }
    )


@pytest.mark.parametrize("obsolete_value", [True, False, "true", 0, None])
def test_new_evaluation_request_rejects_obsolete_need_more_evidence(obsolete_value):
    with pytest.raises(ValueError, match="need_more_evidence is obsolete"):
        validate_evaluation_request(
            {
                "question": "question",
                "reason": "reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "candidate",
                        "episodes": 2,
                        "seed": 1000,
                    }
                ],
                "need_more_evidence": obsolete_value,
            }
        )


def test_evaluation_request_still_requires_a_measurement():
    with pytest.raises(ValueError, match="at least one measurement"):
        validate_evaluation_request(
            {
                "question": "question",
                "reason": "reason",
                "measurements": [],
            }
        )


def test_rejection_before_any_execution_on_exceeding_limit(monkeypatch, tmp_path):
    """When limit is exceeded, no evaluations or comparisons are executed."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": f"model-{i}",
                    "artifact": f"archive/model-{i}",
                    "timesteps": 1,
                    "evaluations": [],
                }
                for i in range(4)
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Test question",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": f"model-{i}",
                        "episodes": 2,
                        "seed": 1000,
                    }
                    for i in range(4)
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_DIR", tmp_path / "evaluations"
    )
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )

    calls = []

    def track_evaluator(artifact, seed, **kwargs):
        calls.append(("eval", artifact, seed))
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", track_evaluator)
    monkeypatch.setattr("research.runner_repository.append_result", lambda result: None)

    # Should reject before any evaluation is attempted.
    with pytest.raises(ValueError, match="at most 3 distinct models"):
        execute_pending_evaluations()

    # Verify no evaluations were executed.
    assert calls == []
    # Verify state was not mutated.
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert final_state == state


def test_multiple_rounds_each_have_independent_three_model_limit(monkeypatch, tmp_path):
    """Each additional evaluation round has its own independent limit."""
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"

    # First round: measure 3 distinct models
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": f"model-{i}",
                    "artifact": f"archive/model-{i}",
                    "timesteps": 1,
                    "evaluations": [],
                }
                for i in range(3)
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "First round",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": f"model-{i}",
                        "episodes": 2,
                        "seed": 1000,
                    }
                    for i in range(3)
                ],
                "need_more_evidence": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_DIR", tmp_path / "evaluations"
    )
    monkeypatch.setattr(
        "research.runner_paths.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )
    monkeypatch.setattr("research.runner_repository.append_result", lambda result: None)

    def evaluator(artifact, seed, **kwargs):
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluator)

    execute_pending_evaluations()

    # Reload state after first round
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending_evaluation_request"]["partial_evaluations"] is not None
    assert len(state["pending_evaluation_request"]["partial_evaluations"]) == 3

    # Second round: measure 3 more distinct models (different from first round).
    # This should be allowed since each round has its own limit.
    state["pending_evaluation_request"]["candidates"] = [
        {
            "name": f"model-{i}",
            "artifact": f"archive/model-{i}",
            "timesteps": 1,
            "evaluations": [],
        }
        for i in range(3, 6)
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")

    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "question": "Second round",
                "reason": "Test reason",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": f"model-{i}",
                        "episodes": 2,
                        "seed": 2000,
                    }
                    for i in range(3, 6)
                ],
                "need_more_evidence": False,
            }
        ),
        encoding="utf-8",
    )

    # Should succeed without raising.
    execute_pending_evaluations()

    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert final_state["pending_researcher_decision"] is not None


def test_continuation_and_replication_allow_unchanged_methods(scientific_reasoning):
    validate_experiment_semantics({}, "continuation", "transfer", None, [], False)
    invalid_continuation = {
        "kind": "continuation",
        "family": "x",
        "hypothesis": "x",
        "initialization": "fresh",
    }
    with pytest.raises(ValueError, match="continuation requires transfer"):
        validate_training_proposal(invalid_continuation, baseline=False)

    validate_experiment_semantics(
        {"training_seed": 19, "replication_of": 12},
        "replication",
        "fresh",
        None,
        [],
        False,
    )
    invalid_replication = {
        "kind": "replication",
        "family": "x",
        "hypothesis": "x",
        "initialization": "fresh",
        "replication_of": 12,
    }
    with pytest.raises(ValueError, match="explicit training_seed"):
        validate_training_proposal(invalid_replication, baseline=False)

    continuation_without_change = {
        "reasoning": scientific_reasoning,
        "kind": "continuation",
        "family": "method",
        "hypothesis": "check additional training",
        "initialization": "transfer",
        "training_parent": "accepted",
    }
    validate_training_proposal(continuation_without_change, baseline=False)

    replication_without_change = {
        "reasoning": scientific_reasoning,
        "kind": "replication",
        "family": "method",
        "hypothesis": "check outcome spread",
        "initialization": "fresh",
        "training_seed": 19,
        "replication_of": 12,
    }
    validate_training_proposal(replication_without_change, baseline=False)

    with pytest.raises(ValueError, match="human-owned task, context"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            {"training": {"n_envs": 2}},
            ["robot_learning/benchmark/final_contract.py"],
            False,
        )


@pytest.mark.parametrize("field", ["replication_of", "training_seed"])
@pytest.mark.parametrize("invalid_value", [True, 12.5, "12", None])
def test_replication_rejects_non_integer_numeric_fields(field, invalid_value):
    proposal = {
        "kind": "replication",
        "family": "method",
        "hypothesis": "check outcome spread",
        "initialization": "fresh",
        "training_seed": 19,
        "replication_of": 12,
    }
    proposal[field] = invalid_value

    with pytest.raises(ValueError, match=f"{field} must be an integer"):
        validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize(
    ("kind", "initialization", "extra_fields"),
    [
        ("training", "fresh", {"change": "test", "training_seed": 0}),
        (
            "continuation",
            "transfer",
            {"training_parent": "accepted", "training_seed": 7},
        ),
        (
            "replication",
            "fresh",
            {"training_seed": 19, "replication_of": 12},
        ),
    ],
)
def test_training_numeric_fields_accept_valid_integers(
    kind, initialization, extra_fields, scientific_reasoning
):
    proposal = {
        "kind": kind,
        "family": "method",
        "hypothesis": "check numeric contract",
        "initialization": initialization,
        **extra_fields,
        "reasoning": scientific_reasoning,
    }

    validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize("kind", ["training", "continuation", "replication"])
def test_training_proposal_rejects_negative_seed_for_every_operation(kind):
    proposal = {
        "kind": kind,
        "family": "method",
        "hypothesis": "check seed contract",
        "initialization": "fresh",
        "training_seed": -1,
    }
    if kind == "training":
        proposal["change"] = "change method"
    elif kind == "continuation":
        proposal.update(initialization="transfer", training_parent="accepted")
    else:
        proposal["replication_of"] = 12

    with pytest.raises(
        ValueError, match="training_seed must be a non-negative integer"
    ):
        validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize("kind", ["continuation", "replication"])
def test_unchanged_operations_reject_change(kind):
    proposal = {
        "kind": kind,
        "family": "method",
        "hypothesis": "check unchanged operation",
        "change": "operation note",
        "initialization": "transfer" if kind == "continuation" else "fresh",
    }
    if kind == "continuation":
        proposal["training_parent"] = "accepted"
    else:
        proposal.update(training_seed=1, replication_of=12)

    with pytest.raises(ValueError, match=f"{kind} must omit change"):
        validate_training_proposal(proposal, baseline=False)


def test_replication_reference_must_exist_in_current_campaign(
    monkeypatch, scientific_reasoning, scientific_memory
):
    proposal = {
        "kind": "replication",
        "family": "method",
        "hypothesis": "check outcome spread",
        "reasoning": scientific_reasoning,
        "initialization": "fresh",
        "training_seed": 19,
        "replication_of": 12,
    }
    state = {
        "campaign": {"id": "current"},
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_final_benchmark": None,
    }
    records = {
        "current": [{"campaign_id": "current", "index": 12}],
        "previous": [{"campaign_id": "previous", "index": 12}],
    }
    monkeypatch.setattr(
        "research.runner_repository.result_records_for_campaign",
        lambda campaign_id: records.get(campaign_id, []),
    )

    assert validate_proposal_against_state(proposal, state) == "training"
    records["current"] = []
    with pytest.raises(ValueError, match="existing experiment in the current campaign"):
        validate_proposal_against_state(proposal, state)

    state["campaign"]["id"] = "previous"
    assert validate_proposal_against_state(proposal, state) == "training"


def test_unchanged_operation_history_uses_neutral_text():
    result = {
        "index": 15,
        "kind": "replication",
        "hypothesis": "check outcome spread",
        "replication_of": 12,
    }

    assert operation_description(result) == (
        "Replicate the current method from fresh initialization"
    )
    assert "Replicate the current method from fresh initialization" in (
        experiment_log_row(result)
    )
    assert compact_result_record({"replication_of": "12"})["replication_of"] == 12


def test_v4_history_keeps_distinct_checkpoint_panels_and_closure_decisions():
    row = experiment_log_row(
        {
            "schema_version": 4,
            "index": 3,
            "kind": "continuation",
            "training_parent": "working",
            "candidates": [
                {
                    "name": "checkpoint-20",
                    "evaluations": [
                        {
                            "instrument": "research_evaluation",
                            "panel": "development-v1",
                            "seed": 4,
                            "episodes": 20,
                            "success_percent": 65.0,
                        }
                    ],
                },
                {"name": "checkpoint-40", "evaluations": []},
            ],
            "task_reference_evaluations": [
                {
                    "candidate": "checkpoint-20",
                    "instrument": "task_reference",
                    "panel": "reference-v1",
                    "episodes": 10,
                    "success_percent": 70.0,
                }
            ],
            "hypothesis_assessment": "The prediction is partly supported.",
            "closure_decision": {
                "continue_from": "checkpoint-20",
                "best_known": {"candidate": "checkpoint-20"},
                "code": {"action": "keep"},
            },
            "verdict": "stale awaiting analysis",
        }
    )

    assert "1 measured checkpoint; 1 unmeasured checkpoint" in row
    assert "research_evaluation/development-v1: 1 measurement" in row
    assert "task_reference/reference-v1: 1 measurement" in row
    assert "checkpoint-40" not in row
    assert "working checkpoint-20; best known checkpoint-20; code keep" in row
    assert "The prediction is partly supported." in row
    assert "stale awaiting analysis" not in row


def test_training_proposal_has_no_postmortem_or_lineage_payload(scientific_reasoning):
    proposal = {
        "kind": "training",
        "family": "reward.hold",
        "reasoning": scientific_reasoning,
        "hypothesis": "test",
        "change": "test",
        "initialization": "transfer",
        "training_parent": "accepted",
        "training_seed": 0,
        "params": {},
    }
    validate_training_proposal(proposal, baseline=False)
    proposal["previous_experiment_postmortem"] = {}
    with pytest.raises(ValueError, match="lineage-only"):
        validate_training_proposal(proposal, baseline=False)


def test_champion_can_be_retained_before_replacement(monkeypatch, tmp_path):
    champion = _artifact(tmp_path / "accepted")
    challenger = _artifact(tmp_path / "archive" / "candidate")
    challenger_model = challenger.joinpath("model.zip").read_bytes()
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state.update(
        {
            "accepted_artifact": "accepted",
            "accepted_training_steps": 55,
            "accepted_parameters": {"algorithm": {"name": "active-method"}},
        }
    )
    state["pending_researcher_decision"]["champion_available"] = True
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {
            "candidate": "champion",
            "id": "pre-change-policy",
            "reason": "Useful contrast.",
        }
    ]
    assert not apply_previous_result_decision(decision, state)
    retained = state["retained_lineages"][0]
    assert retained["id"] == "pre-change-policy"
    assert (
        tmp_path / retained["artifact"] / "model.zip"
    ).read_bytes() == champion.joinpath("model.zip").read_bytes()
    assert (tmp_path / "accepted" / "model.zip").read_bytes() == challenger_model
    identifier, parent, steps = training_parent(
        {"training_parent": "pre-change-policy"}, state, "transfer"
    )
    assert (identifier, parent, steps) == (
        "pre-change-policy",
        tmp_path / retained["artifact"],
        55,
    )


def _measured(tmp_path, name, artifacts):
    """One completed evaluation panel plus the JSON artifact it produced."""
    relative = f"research/evaluations/evaluation-experiment-8-{name}-2ep-seed44-ab.json"
    (artifacts / Path(relative).name).write_text("{}", encoding="utf-8")
    record = evaluation(44, [True, False])
    record["evaluation_artifact"] = relative
    return [record]


def _attest(
    monkeypatch,
    tmp_path,
    experiment,
    paths,
    label="Evidence inspected",
    campaign_id=None,
):
    """Write the postmortem a lineage decision must carry to be accepted."""
    postmortem = tmp_path / "postmortems.md"
    heading = (
        f"## {campaign_id} / Experiment {experiment} - measured"
        if campaign_id
        else f"## Experiment {experiment} - measured"
    )
    postmortem.write_text(
        f"{heading}\n\n"
        "**Result:** measured.\n\n"
        "**Observed behavior:** recorded.\n\n"
        "**Hypothesis assessment:** The prediction is partly supported, with "
        "limited evidence from this panel.\n\n"
        "**Interpretation:** the candidate is the useful parent.\n\n"
        f"**{label}:** " + ", ".join(f"`{path}`" for path in paths) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", postmortem)
    return postmortem


def _evaluation_lifecycle_state(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    _artifact(tmp_path / "archive" / "runner-up")
    artifacts = tmp_path / "research" / "evaluations"
    artifacts.mkdir(parents=True)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(
        "research.runner_paths.CANDIDATE_ROOT", tmp_path / "models" / "candidates"
    )
    monkeypatch.setattr("research.runner_paths.EVALUATION_DIR", artifacts)
    _attest(
        monkeypatch,
        tmp_path,
        8,
        ["research/evaluations/evaluation-experiment-8-candidate-2ep-seed44-ab.json"],
    )

    state = _decision_state(
        "archive/candidate", _measured(tmp_path, "candidate", artifacts)
    )
    runner_up = _measured(tmp_path, "runner-up", artifacts)
    state["pending_researcher_decision"]["candidates"].append(
        {
            "name": "runner-up",
            "artifact": "archive/runner-up",
            "timesteps": 120_000,
            "evaluations": runner_up,
            "summary": summarize_evaluations(runner_up),
        }
    )
    return state, artifacts


def test_evaluation_artifacts_are_named_per_measured_panel():
    first = evaluation_artifact_name(8, "checkpoint-120832", 200, 1000, "aaaa")
    second = evaluation_artifact_name(8, "checkpoint-120832", 200, 2000, "aaaa")
    reinstrumented = evaluation_artifact_name(8, "checkpoint-120832", 200, 1000, "bbbb")

    assert first != second
    assert first != reinstrumented
    assert first == evaluation_artifact_name(8, "checkpoint-120832", 200, 1000, "aaaa")


def test_discarded_candidate_keeps_its_completed_evaluation_evidence(
    monkeypatch, tmp_path
):
    state, artifacts = _evaluation_lifecycle_state(monkeypatch, tmp_path)

    assert not apply_previous_result_decision(_lineage_decision(), state)

    # The runner-up checkpoint is discarded; its completed measurement is not.
    assert not (tmp_path / "archive" / "runner-up" / "model.zip").exists()
    assert (artifacts / "evaluation-experiment-8-candidate-2ep-seed44-ab.json").exists()
    assert (artifacts / "evaluation-experiment-8-runner-up-2ep-seed44-ab.json").exists()
    assert state["accepted_evaluations"] == [
        "research/evaluations/evaluation-experiment-8-candidate-2ep-seed44-ab.json"
    ]
    assert state["pending_researcher_decision"] is None


def test_retained_lineage_keeps_its_evaluation_evidence(monkeypatch, tmp_path):
    state, artifacts = _evaluation_lifecycle_state(monkeypatch, tmp_path)
    obsolete = (
        "research/evaluations/evaluation-experiment-2-obsolete-2ep-seed44-ab.json"
    )
    (artifacts / Path(obsolete).name).write_text("{}", encoding="utf-8")
    _artifact(tmp_path / "research" / "checkpoints" / "retained" / "obsolete")
    state["retained_lineages"] = [
        {
            "id": "obsolete",
            "artifact": "research/checkpoints/retained/obsolete",
            "origin_experiment": 2,
            "evaluation_artifacts": [obsolete],
        }
    ]
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {"candidate": "runner-up", "id": "alternative", "reason": "Useful contrast."}
    ]
    decision["previous_result_decision"]["remove_retained"] = ["obsolete"]

    assert not apply_previous_result_decision(decision, state)

    retained = state["retained_lineages"][0]
    assert retained["id"] == "alternative"
    assert retained["evaluation_artifacts"] == [
        "research/evaluations/evaluation-experiment-8-runner-up-2ep-seed44-ab.json"
    ]
    assert (artifacts / "evaluation-experiment-8-runner-up-2ep-seed44-ab.json").exists()
    # Removing a retained lineage drops its checkpoint, never its measurements.
    assert (artifacts / Path(obsolete).name).exists()


def test_retained_lineage_is_scoped_to_the_active_campaign(monkeypatch, tmp_path):
    state, _ = _evaluation_lifecycle_state(monkeypatch, tmp_path)
    campaign_id = "550e8400-e29b-41d4-a716-446655440000"
    state["campaign"] = {
        "id": campaign_id,
        "started_at": "2026-01-01T00:00:00Z",
        "base_commit": "abc123",
    }
    # The lifecycle fixture attests a campaign-less postmortem heading; re-attest
    # it under the campaign-scoped heading the plan now looks up.
    _attest(
        monkeypatch,
        tmp_path,
        8,
        ["research/evaluations/evaluation-experiment-8-candidate-2ep-seed44-ab.json"],
        campaign_id=campaign_id,
    )
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {"candidate": "runner-up", "id": "alternative", "reason": "Useful contrast."}
    ]

    assert not apply_previous_result_decision(decision, state)

    retained = state["retained_lineages"][0]
    assert retained["campaign_id"] == campaign_id
    assert retained["artifact"] == (
        f"research/checkpoints/retained/{campaign_id}/alternative"
    )
    assert (
        tmp_path / "research" / "checkpoints" / "retained" / campaign_id / "alternative"
    ).exists()


def test_removing_retained_lineage_keeps_history_but_removes_artifact(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "candidate")
    retained = _artifact(
        tmp_path / "research" / "checkpoints" / "retained" / "obsolete"
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = [
        {
            "id": "obsolete",
            "artifact": "research/checkpoints/retained/obsolete",
            "origin_experiment": 2,
        }
    ]
    decision = _lineage_decision()
    decision["previous_result_decision"]["remove_retained"] = ["obsolete"]
    assert not apply_previous_result_decision(decision, state)
    assert state["retained_lineages"] == []
    assert retained.joinpath("artifact.json").exists()
    assert not retained.joinpath("model.zip").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda decision: decision["previous_result_decision"].update(
            {"continue_from": "missing"}
        ),
        lambda decision: decision["previous_result_decision"]["code"].update(
            {"action": "revise"}
        ),
        lambda decision: decision["previous_result_decision"].update(
            {"retain": [{"candidate": "missing", "id": "alternative", "reason": "bad"}]}
        ),
        lambda decision: decision["previous_result_decision"].update(
            {"remove_retained": ["missing"]}
        ),
    ],
)
def test_invalid_lineage_decisions_mutate_nothing(monkeypatch, tmp_path, mutate):
    candidate = _artifact(tmp_path / "archive" / "candidate")
    accepted = _artifact(tmp_path / "accepted")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", accepted)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = []
    before_state = json.dumps(state, sort_keys=True)
    before_accepted = accepted.joinpath("model.zip").read_bytes()
    before_candidate = candidate.joinpath("model.zip").read_bytes()
    decision = _lineage_decision()
    mutate(decision)
    with pytest.raises((TypeError, ValueError)):
        apply_previous_result_decision(decision, state)
    assert json.dumps(state, sort_keys=True) == before_state
    assert accepted.joinpath("model.zip").read_bytes() == before_accepted
    assert candidate.joinpath("model.zip").read_bytes() == before_candidate


def test_conflicting_retention_is_rejected_before_mutation(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    accepted = _artifact(tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", accepted)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = [
        {"id": "alternative", "artifact": "old", "origin_experiment": 1}
    ]
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {"candidate": "candidate", "id": "alternative", "reason": "bad"}
    ]
    with pytest.raises(ValueError, match="do not retain|conflicting"):
        plan_previous_result_decision(decision, state)
    assert accepted.joinpath("model.zip").exists()


def test_discarded_candidates_keep_history_but_lose_heavyweight_files(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "selected")
    discarded = _artifact(tmp_path / "archive" / "discarded")
    (discarded / "replay_buffer.pkl").write_bytes(b"large")
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("research.runner_paths.GOAL_PATH", tmp_path / "GOAL_REACHED")
    measurements = [evaluation(44, [True, False])]
    state = _decision_state("archive/selected", measurements)
    state["pending_researcher_decision"]["candidates"].append(
        {
            "name": "discarded",
            "artifact": "archive/discarded",
            "timesteps": 120_000,
            "evaluations": measurements,
            "summary": summarize_evaluations(measurements),
        }
    )
    assert not apply_previous_result_decision(_lineage_decision(), state)
    assert (discarded / "artifact.json").exists()
    assert not (discarded / "model.zip").exists()
    assert not (discarded / "vecnormalize.pkl").exists()
    assert not (discarded / "replay_buffer.pkl").exists()


# --- method neutrality of the protocol -------------------------------------


def test_protocol_defines_a_method_neutral_researcher_within_the_fixed_stack():
    normalized_program = " ".join(PROGRAM.split())
    for expertise in (
        "robot-learning",
        "reinforcement learning",
        "robotics simulation",
        "experimental measurement",
        "scientific software",
    ):
        assert expertise in normalized_program
    assert "current implementation is a starting point" in PROGRAM
    assert "within the installed stack" in PROGRAM
    assert "does not install packages" in PROGRAM


def test_protocol_offers_no_alternative_algorithm_menu():
    for algorithm_name in KNOWN_ALGORITHM_NAMES:
        assert not mentions(PROGRAM, algorithm_name), algorithm_name


def test_protocol_does_not_enumerate_the_configuration_surface():
    assert "`algorithm`" not in PROGRAM


def test_protocol_delegates_request_schemas_to_the_instrument_catalog():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")

    assert "```json" not in PROGRAM
    assert "request contract" in PROGRAM
    for field in ("training_parent", "training_seed", "params"):
        assert f'"{field}"' not in PROGRAM
        assert f'"{field}"' in instruments


def test_baseline_protocol_wording_is_algorithm_neutral():
    assert 'change = "Fresh baseline"' in LOOP
    for algorithm_name in KNOWN_ALGORITHM_NAMES:
        assert not mentions(LOOP, algorithm_name), algorithm_name
    assert "current implementation is a starting point" in PROGRAM


def test_no_researcher_prompt_forces_the_configuration_into_context():
    assert "research/current_params.json" not in LOOP
    for expected in (
        "AGENTS.md",
        "research/program.md",
        "research/scenario.md",
        "research/instruments.md",
        "research/brief.md",
    ):
        assert expected in LOOP
    assert "research/last_train_summary.md" not in LOOP


def test_researcher_guidance_keeps_git_out_of_the_scientific_evidence_surface():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    normalized_agents = " ".join(agents.split())

    assert "authoritative sources of scientific evidence" in normalized_agents
    assert "code provenance and code inspection" in normalized_agents
    assert "routine workspace-discovery mechanism" in normalized_agents
    assert "inspect files and Git history" not in normalized_agents

    assert LOOP.count("evaluation design normally requires no Git inspection") == 1
    assert LOOP.count("current experiment's scientific recipe delta") == 1
    assert LOOP.count("requires understanding the current code state or delta") == 1
    for routine_command in ("git log", "git show", "git blame"):
        assert routine_command not in LOOP.lower()


def test_evidence_inspection_is_brief_first_and_targeted():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized = " ".join(instruments.split())

    assert "Start with `research/brief.md`" in normalized
    assert "only when additional detail is needed" in normalized
    assert "targeted extraction" in normalized
    assert "uv run --group researcher jello '_.metrics'" in normalized
    assert "relative to the repository" in normalized
    assert "Do not inspect instrument or Runner implementation" in normalized
    assert "every JSON or JSONL artifact" not in normalized
    assert (
        """Detailed artifacts remain valid sources of scientific evidence, including for
unsuccessful experiments. Inspect episode-level behavior, distributions,
failure modes, or any other detail when it may help explain a result or generate
a useful hypothesis.

When querying structured artifacts, prefer queries that answer a scientific
question over queries that only rediscover the artifact schema or reconfirm
summary values already available in `research/brief.md`. Schema inspection is
appropriate when needed to understand an unfamiliar artifact; once the relevant
structure is known, proceed directly to the scientific analysis rather than
repeatedly rediscovering it."""
        in instruments
    )

    assert LOOP.count("Start from the brief and instrument contract") == 1
    assert LOOP.count("as needed to support the postmortem") == 1
    assert "Read the detailed evaluation artifacts" not in LOOP


def test_experiment_preparation_retry_avoids_vague_repository_discovery():
    assert "inspect the relevant repository state" not in LOOP
    assert LOOP.count("requires understanding the current code state or delta") == 1


def test_post_training_refinement_is_optional_and_scoped_to_current_experiment():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_instruments = " ".join(instruments.split())

    assert "initial post-training analysis for trained experiment" in LOOP
    assert "New measurement results are available" in LOOP
    assert (
        "State the question or uncertainty, then select measurements "
        "proportionate to the uncertainty and their cost"
    ) in LOOP
    assert "eligible saved lineages can be remeasured" in LOOP
    assert (
        "If the relevant quantity is not currently emitted, you may modify "
        "researcher-owned measurement instrumentation before requesting it."
    ) in LOOP
    assert "only in this post-training phase" in LOOP
    assert "Closure without new measurements is valid" in PROGRAM
    assert "through `research/evaluation_request.json`" in PROGRAM
    assert (
        "No diagnostic code change or particular instrument is required"
        in normalized_instruments
    )
    assert "mechanism_evaluation_request" not in PROGRAM + instruments + LOOP


def test_post_training_reasoning_requires_a_revisable_investigation_interpretation():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_program = " ".join(PROGRAM.split())
    normalized_instruments = " ".join(instruments.split())

    assert "assess the question actually tested" in LOOP
    assert "Scope causal claims to the evidence" in LOOP
    assert "That direction may replace the current investigation" in LOOP
    assert "That operational boundary does not prescribe the scientific decision." in normalized_program
    assert "An unsuccessful run does not automatically reject an intervention" in normalized_program
    assert "The `reasoning` object contains the fields shown in the schema." in normalized_instruments
    assert "Their scientific use is defined in `research/program.md`." in normalized_instruments
    assert "measured behavioral gap" not in normalized_instruments
    assert "broader causal mechanism" not in normalized_instruments
    assert "next_if_expected" not in PROGRAM + instruments + LOOP
    assert "next_if_contradicted" not in PROGRAM + instruments + LOOP


def test_evaluation_requests_support_the_model_decision_and_next_direction():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_program = " ".join(PROGRAM.split())
    normalized_instruments = " ".join(instruments.split())

    assert "State the question or uncertainty, then choose" in normalized_program
    assert "expected contribution to that objective" in normalized_program
    assert "may advance, revise, or reject the current investigation" in normalized_program
    assert "useful, proportionate measurement scope" in normalized_program
    assert "Reuse compatible evidence when it answers the question" in normalized_program
    sufficiency_rule = (
        "Close when the evidence supports a lineage decision and a reasoned next action, "
        "without requiring a complete explanation of the outcome."
    )
    assert sufficiency_rule in normalized_program
    assert sufficiency_rule not in normalized_instruments
    assert "No comparison, replication, task-reference panel, diagnostic, or additional round is mandatory or preferred" in normalized_program
    assert "`question` and `reason` are non-empty strings" in normalized_instruments
    assert "the revisable question or approach that best serves the human objective" in normalized_program
    evaluation_design_prompt = LOOP.split(
        "Current phase: design the research evaluation", 1
    )[1].split("Do not start training or evaluation", 1)[0]
    assert "measurements are useful and proportionate to the uncertainty" in evaluation_design_prompt
    assert "every listed measurement is needed" not in evaluation_design_prompt
    assert "best_known" not in evaluation_design_prompt.lower()
    assert "best_known" not in LOOP.split("$analysisPrompt = @(", 1)[0]
    new_hypothesis_prompt = LOOP.split(
        "Current phase: prepare experiment", 1
    )[1].split("Do not exit after analysis or diagnosis", 1)[0]
    assert "best_known" not in new_hypothesis_prompt.lower()
    assert "same development panel" not in LOOP.lower()
    assert "smallest sufficient set" not in LOOP
    assert "minimum measurement" not in LOOP.lower()
    assert "exploratory characterization when useful" in LOOP.lower()
    assert "campaign objective and current scientific strategy and available evidence" in LOOP.lower()
    assert LOOP.count("Comparison and task-reference measurement are optional") == 2
    assert (
        '"strategy_link": "<how this experiment advances, revises, or rejects '
        'the current investigation>"'
    ) in instruments
    assert '"measurements": [' in instruments
    assert '"paired_comparisons": [' in instruments
    assert "decision_relevant_measurements" not in PROGRAM + instruments + LOOP
    assert "Measured task behavior governs claims of policy progress" in normalized_program
    assert "All relevant evidence may inform the next investigation" in normalized_program
    assert (
        "not a commitment to the current investigation or incumbent policy"
    ) in normalized_program

    with pytest.raises(ValueError, match="unsupported fields.*reason"):
        validate_evaluation_request(
            {
                "question": "Does the candidate preserve primary success?",
                "reason": "The requested panel answers the stated question.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "candidate",
                        "episodes": 2,
                        "seed": 1000,
                        "reason": "Unsupported per-measurement reason.",
                    }
                ],
            }
        )


def test_experiment_preparation_uses_the_question_and_operation_before_initialization():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_program = " ".join(PROGRAM.split())
    normalized_instruments = " ".join(instruments.split())

    assert "State the scientific question, then choose the fitting operation" in LOOP
    assert "Only then justify the parent and fresh-or-transfer initialization" in LOOP
    assert "1. State the scientific question and how it serves the human objective." in normalized_program
    assert "2. Choose the operation that fits that question" in normalized_program
    assert "3. State one falsifiable hypothesis" in normalized_program
    assert "4. Justify the training parent and fresh-or-transfer initialization" in normalized_program
    assert "Only after choosing the mechanism and intervention" not in LOOP + PROGRAM
    assert "Unchanged tensor dimensions alone do not establish semantic compatibility" in normalized_program
    assert "Choose the mechanism and intervention before initialization." not in normalized_instruments
    assert "semantic compatibility" not in normalized_instruments


def test_terminal_assessment_uses_information_value_without_becoming_feedback():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_program = " ".join(PROGRAM.split())
    normalized_instruments = " ".join(instruments.split())
    combined = " ".join((PROGRAM + "\n" + LOOP).split())

    assert "terminal assessment" in combined
    assert "highest-value next action" in combined
    assert "more valuable now than further research" in combined
    assert "ends the campaign after either verdict" in combined
    assert "highest-value next action" not in normalized_instruments
    assert "The scientific decision rule for requesting assessment is defined in `research/program.md`." in normalized_instruments
    assert "considering available compute, evidence of task performance, uncertainty" in normalized_program
    assert "no next experiment is intended" not in combined
    assert "no scientifically useful path remains" not in combined
    assert "when a scientifically useful next experiment remains" not in combined


def test_protocol_default_context_names_only_authoritative_context():
    opening = PROGRAM.split("## Roles", 1)[0]

    for expected in (
        "`AGENTS.md`",
        "`research/scenario.md`",
        "`research/instruments.md`",
        "`research/brief.md`",
    ):
        assert expected in opening
    assert "`research/current_params.json`" not in opening
    assert "`research/last_train_summary.md`" not in PROGRAM
