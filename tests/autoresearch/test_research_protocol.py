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
    evaluation_artifact_name,
    evaluation_semantics_fingerprint,
    evaluation_semantics_paths,
    experiment_family,
    is_protected_source,
    parameter_change_records,
    plan_previous_result_decision,
    training_parent,
    validate_experiment_semantics,
    validate_training_proposal,
)
from research.runner_repository import (
    compact_result_record,
    measurement_record,
)
from robot_learning.scenario import (
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


def mentions(text: str, word: str) -> bool:
    return re.search(rf"\b{word}\b", text, flags=re.IGNORECASE) is not None


def test_the_copilot_adapter_is_a_protected_protocol_source():
    assert is_protected_source("researcher_copilot.py")


def test_new_hypothesis_boundary_uses_phase_aware_proposal_preflight():
    assert "--check-proposal" in LOOP
    assert "Current phase: prepare experiment $nextExperiment" in LOOP
    assert "write a lineage decision" in LOOP
    assert "failed validation: $proposalProblem" in LOOP
    assert "proposal valid for the current phase" in LOOP
    assert "preliminary diagnosis is not completion" in PROGRAM
    assert (
        "chosen one falsifiable hypothesis and its corresponding intervention"
        in PROGRAM
    )


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
                "evaluations": [
                    {
                        "candidate": "checkpoint-100",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first panel",
                    },
                    {
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
                "evaluations": [
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first",
                    },
                    {
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
                "evaluations": [
                    {"candidate": "checkpoint", "episodes": 2, "seed": 1000},
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
                "evaluations": [
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "reused A",
                    },
                    {
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
                "evaluations": [
                    {"candidate": "checkpoint", "episodes": 2, "seed": 1000}
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
                    "evaluations": [
                        {"candidate": "checkpoint", "episodes": 2, "seed": 1000}
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
        "progress.py",
        "reward.py",
        "viewer.py",
    ):
        (scenario / name).write_text("original\n", encoding="utf-8")
    training = tmp_path / "robot_learning" / "training"
    training.mkdir(parents=True)
    for name in ("algorithms.py", "normalization.py"):
        (training / name).write_text("original\n", encoding="utf-8")
    (tmp_path / "robot_learning" / "evaluate.py").write_text(
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
        "robot_learning/scenario/environment.py",
        "robot_learning/scenario/evaluation.py",
        "robot_learning/scenario/observations.py",
        "robot_learning/scenario/reward.py",
        "robot_learning/training/algorithms.py",
        "robot_learning/training/normalization.py",
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


@pytest.mark.parametrize(
    "relative",
    [
        "robot_learning/evaluate.py",
        "robot_learning/training/algorithms.py",
        "robot_learning/training/normalization.py",
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
            "at least one detailed evaluation artifact",
        ),
        # Names a real artifact belonging to a different experiment.
        (
            ["research/evaluations/evaluation-experiment-2-other-2ep-seed44-ab.json"],
            "Evidence inspected",
            "at least one detailed evaluation artifact",
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
        "robot_learning.scenario.evaluate_final_model",
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
    assert (tmp_path / "GOAL_REACHED").exists()


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
        "robot_learning.scenario.evaluate_final_model", failed_benchmark
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
        "robot_learning.scenario.evaluate_final_model",
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
                "evaluations": [
                    {
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
    with pytest.raises(ValueError, match="not valid"):
        execute_pending_evaluations()


def test_continuation_and_replication_allow_unchanged_methods():
    validate_experiment_semantics({}, "continuation", "transfer", None, [], False)
    invalid_continuation = {
        "kind": "continuation",
        "family": "x",
        "hypothesis": "x",
        "change": "x",
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
        "change": "x",
        "initialization": "fresh",
        "replication_of": 12,
    }
    with pytest.raises(ValueError, match="explicit training_seed"):
        validate_training_proposal(invalid_replication, baseline=False)

    with pytest.raises(ValueError, match="human-owned final benchmark"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            {"training": {"n_envs": 2}},
            ["robot_learning/benchmark/final_contract.py"],
            False,
        )


def test_training_proposal_has_no_postmortem_or_lineage_payload():
    proposal = {
        "kind": "training",
        "family": "reward.hold",
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


def _attest(monkeypatch, tmp_path, experiment, paths, label="Evidence inspected"):
    """Write the postmortem a lineage decision must carry to be accepted."""
    postmortem = tmp_path / "postmortems.md"
    postmortem.write_text(
        f"## Experiment {experiment} - measured\n\n"
        "**Result:** measured.\n\n"
        "**Observed behavior:** recorded.\n\n"
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


def test_protocol_treats_the_implementation_as_a_starting_point():
    for statement in (
        "It is a starting point, not part of the problem definition",
        "modify or replace the learning algorithm",
        "is not the set of algorithms you are allowed to consider",
    ):
        assert statement in PROGRAM


def test_protocol_requires_a_mechanism_before_changing_method():
    assert "Poor performance alone is not sufficient evidence" in PROGRAM
    assert "must not be treated as a menu of preferred interventions" in PROGRAM


def test_protocol_offers_no_alternative_algorithm_menu():
    for algorithm_name in KNOWN_ALGORITHM_NAMES:
        assert not mentions(PROGRAM, algorithm_name), algorithm_name


def test_protocol_does_not_enumerate_the_configuration_surface():
    assert "overrides to the currently active runtime configuration" in PROGRAM
    assert "`algorithm`" not in PROGRAM


def test_protocol_example_is_a_minimal_structural_proposal():
    proposal_example = PROGRAM.split("### Standard training proposal", 1)[1].split(
        "Required:", 1
    )[0]

    assert '"initialization": "<fresh|transfer>"' in proposal_example
    assert '"initialization": "fresh"' not in proposal_example
    assert '"initialization": "transfer"' not in proposal_example
    assert "training_parent" not in proposal_example
    assert "training_seed" not in proposal_example
    assert '"params"' not in proposal_example
    for field in ("training_parent", "training_seed", "params"):
        assert field in PROGRAM


def test_baseline_protocol_wording_is_algorithm_neutral():
    assert 'change = "Fresh baseline"' in LOOP
    for algorithm_name in KNOWN_ALGORITHM_NAMES:
        assert not mentions(LOOP, algorithm_name), algorithm_name
    assert "trains the repository's current unchanged learning method" in PROGRAM


def test_no_researcher_prompt_forces_the_configuration_into_context():
    assert "research/current_params.json" not in LOOP
    for expected in (
        "research/program.md",
        "research/scenario.md",
        "research/brief.md",
    ):
        assert expected in LOOP
    assert "research/last_train_summary.md" not in LOOP


def test_protocol_default_context_excludes_the_configuration():
    context_block = PROGRAM.split("## Working context", 1)[1].split("##", 1)[0]
    start_with = context_block.split("Start with:", 1)[1].split("Use this", 1)[0]

    assert "`research/current_params.json`" not in start_with
    assert "`research/last_train_summary.md`" not in context_block
    # It stays available on demand, just not pushed into every session.
    assert "`research/current_params.json`" in context_block
