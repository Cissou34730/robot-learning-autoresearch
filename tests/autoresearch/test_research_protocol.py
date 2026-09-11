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
    reference = [evaluation(3000, [False, False, False, False, False, False])]

    comparison = paired_comparison(candidate, reference)

    assert comparison["candidate_wins"] == 6
    assert comparison["reference_wins"] == 0
    assert comparison["success_delta_percent"] == 100.0
    assert comparison["exact_p_value"] == pytest.approx(0.03125)


def test_paired_comparison_rejects_panels_without_shared_episodes():
    with pytest.raises(ValueError, match="do not cover identical episodes"):
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
        ),
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
                "legacy",
                episode_identities=[(0, 10)],
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
            True,
        ),
        (
            _comparison_record("same", seed=10),
            _comparison_record("same", seed=11),
            True,
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


def test_runner_uses_the_human_defined_budget_for_all_initializations():
    assert training_budget(120_000, "transfer", False) == 120_000
    assert training_budget(120_000, "fresh", False) == 120_000
    assert training_budget(120_000, "fresh", True) == 120_000


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
                "best_known_lineage": {
                    "artifact": "archive/best",
                    "fingerprint": "best",
                },
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

    with pytest.raises(ValueError, match="does not match the best-known lineage"):
        execute_pending_final_benchmark()


def test_terminal_campaign_rejects_new_proposals():
    with pytest.raises(ValueError, match="terminal official assessment"):
        validate_proposal_against_state(
            {"hypothesis": "another run"},
            {"terminal_campaign_status": "goal_not_reached"},
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


@pytest.mark.parametrize("selection", [None, "", "   ", 7])
def test_each_measurement_requires_a_selection_justification(selection):
    entry = {
        "instrument": "research_evaluation",
        "candidate": "candidate",
        "episodes": 2,
        "seed": 1000,
    }
    if selection is not None:
        entry["selection"] = selection
    with pytest.raises(
        ValueError,
        match="requires a non-empty selection stating why this model is useful",
    ):
        validate_evaluation_request(
            {
                "question": "question",
                "reason": "reason",
                "measurements": [entry],
            }
        )


def test_measurements_for_one_candidate_may_have_distinct_selections():
    validate_evaluation_request(
        {
            "question": "question",
            "reason": "reason",
            "measurements": [
                {
                    "instrument": "task_reference",
                    "candidate": "candidate",
                    "selection": "measure behavior on the protected panel",
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": "candidate",
                    "episodes": 2,
                    "seed": 1000,
                    "selection": "inspect researcher-owned diagnostics",
                },
            ],
        }
    )


def test_continuation_and_replication_allow_unchanged_methods(scientific_reasoning):
    validate_experiment_semantics({}, "continuation", "transfer", None, [], False)
    invalid_continuation = {
        "kind": "continuation",
        "family": "x",
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
        "hypothesis": "check additional training",
        "initialization": "transfer",
        "training_parent": "accepted",
    }
    validate_training_proposal(continuation_without_change, baseline=False)

    replication_without_change = {
        "reasoning": scientific_reasoning,
        "kind": "replication",
        "family": "method",
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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
        "investigation_type": "confirmatory",
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


def test_evaluation_artifacts_are_named_per_measured_panel():
    first = evaluation_artifact_name(
        8, "checkpoint-120832", 200, 1000, "aaaa", campaign_id="campaign"
    )
    second = evaluation_artifact_name(
        8, "checkpoint-120832", 200, 2000, "aaaa", campaign_id="campaign"
    )
    reinstrumented = evaluation_artifact_name(
        8, "checkpoint-120832", 200, 1000, "bbbb", campaign_id="campaign"
    )

    assert first != second
    assert first != reinstrumented
    assert first == evaluation_artifact_name(
        8, "checkpoint-120832", 200, 1000, "aaaa", campaign_id="campaign"
    )


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
