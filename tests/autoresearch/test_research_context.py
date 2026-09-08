import json
from pathlib import Path

from research.build_research_brief import _change_details, render_research_brief
from robot_learning.training.progress import parse_training_records

SAMPLE_LOG = """
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 400         |
|    ep_rew_mean          | 2.5         |
|    success_rate         | 0.25        |
| time/                   |             |
|    total_timesteps      | 1024        |
| train/                  |             |
|    explained_variance   | 0.4         |
|    std                  | 0.9         |
-----------------------------------------
| rollout/                |             |
|    ep_len_mean          | 500         |
|    ep_rew_mean          | 10          |
|    success_rate         | 0           |
| time/                   |             |
|    total_timesteps      | 2048        |
| train/                  |             |
|    explained_variance   | 0.8         |
|    std                  | 0.5         |
-----------------------------------------
Model saved to models/reach-example/model.zip
"""


def _checkpoint(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "model.zip").write_bytes(b"model")
    (path / "artifact.json").write_text("{}", encoding="utf-8")
    return path


def test_change_details_uses_structured_parameter_changes_only():
    result = {
        "change": "adjust rollout horizon",
        "hypothesis": "increasing the horizon from 10 to 20 should help",
        "parameter_changes": [
            {"path": "training.horizon", "before": 8, "after": 12}
        ],
    }

    details = _change_details(result)

    assert details == "training.horizon: 8 → 12"
    assert "10 → 20" not in details


def test_change_details_does_not_infer_values_from_hypothesis():
    result = {
        "change": "adjust rollout horizon",
        "hypothesis": "increasing the horizon from 10 to 20 should help",
    }

    assert _change_details(result) == "adjust rollout horizon"


def test_change_details_represents_recorded_code_changes():
    result = {
        "change": "adjust reward shaping",
        "hypothesis": "a change from 10 to 20 may help",
        "code_changes": ["robot_learning/rewards.py"],
    }

    assert _change_details(result) == (
        "adjust reward shaping; files: robot_learning/rewards.py"
    )


def test_training_log_parser_groups_metric_snapshots():
    records = parse_training_records(SAMPLE_LOG)

    assert len(records) == 2
    assert records[0]["success_rate"] == 0.25
    assert records[0]["total_timesteps"] == 1024
    assert records[1]["std"] == 0.5


def test_brief_renders_checkpoint_aligned_facts_for_every_pending_candidate(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    _checkpoint(research_dir / "checkpoints" / "earlier")
    _checkpoint(research_dir / "checkpoints" / "later")
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "pending_evaluation_request": {
                    "experiment": 3,
                    "candidates": [
                        {
                            "name": "later",
                            "timesteps": 120,
                            "training_success": 0.0,
                            "ep_rew_mean": 0.0,
                            "artifact": "research/checkpoints/later",
                        },
                        {
                            "name": "earlier",
                            "timesteps": 20,
                            "training_success": None,
                            "ep_rew_mean": None,
                            "artifact": "research/checkpoints/earlier",
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()

    assert "| Candidate | Steps | Training success | Training reward | Artifact |" in brief
    assert "| `earlier` | 20 | unavailable | unavailable | `research/checkpoints/earlier` |" in brief
    assert "| `later` | 120 | 0 | 0 | `research/checkpoints/later` |" in brief
    assert brief.index("`earlier`") < brief.index("`later`")
    assert "Most recent training dynamics" not in brief


def test_brief_reports_the_measured_score_and_points_at_the_detail(
    monkeypatch, tmp_path
):
    summary = {
        "episodes": 4,
        "success_percent": 50.0,
        "pooled_success_percent": 50.0,
        "seed_count": 1,
    }
    research_dir = tmp_path / "research"
    _checkpoint(tmp_path / "accepted")
    evaluations_dir = research_dir / "evaluations"
    evaluations_dir.mkdir(parents=True)
    (evaluations_dir / "evaluation-experiment-3-champion-4ep-seed1000-ab.json").write_text(
        "{}", encoding="utf-8"
    )
    (evaluations_dir / "evaluation-experiment-4-1.json").write_text(
        "{}", encoding="utf-8"
    )
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "accepted_artifact": "accepted",
                "accepted_evaluations": [
                    "research/evaluations/evaluation-experiment-3-champion-4ep-seed1000-ab.json"
                ],
                "pending_researcher_decision": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "hold-focused",
                            "summary": summary,
                            "evaluations": [
                                {
                                    "episodes": 4,
                                    "seed": 3000,
                                    "success_percent": 50.0,
                                    "evaluation_artifact": (
                                        "research/evaluations/"
                                        "evaluation-experiment-4-1.json"
                                    ),
                                }
                            ],
                        }
                    ],
                    "champion_available": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()

    assert "hold-focused: pooled success 50.00%" in brief
    assert "4 episodes, seed 3000, success 50.00%" in brief
    assert "research/evaluations/evaluation-experiment-4-1.json" in brief
    assert (
        "Accepted evaluation detail: "
        "`research/evaluations/evaluation-experiment-3-champion-4ep-seed1000-ab.json`"
    ) in brief
    assert "summaries below as the normal evidence entry point" in brief
    assert "artifacts as needed to resolve the lineage decision" in brief
    assert "Open the detailed evaluation artifacts listed below" not in brief
    assert "Measured challenger diagnostics" not in brief
    assert "Observed failure diagnostics" not in brief


def test_brief_reports_missing_and_legacy_artifacts_as_unavailable(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    evaluations_dir = research_dir / "evaluations"
    evaluations_dir.mkdir(parents=True)
    _checkpoint(research_dir / "checkpoints" / "legacy")
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "accepted_artifact": "research\\checkpoints\\legacy",
                "accepted_evaluations": [
                    "research\\evaluations\\missing.json"
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()

    assert "Accepted checkpoint: `research/checkpoints/legacy`" in brief
    assert "Accepted evaluation detail: unavailable" in brief
    assert "research\\evaluations\\missing.json" not in brief


def test_brief_reports_an_incomplete_checkpoint_as_unavailable(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    incomplete = research_dir / "checkpoints" / "incomplete"
    incomplete.mkdir(parents=True)
    (incomplete / "model.zip").write_bytes(b"model")
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps({"accepted_artifact": "research/checkpoints/incomplete"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()

    assert "Accepted checkpoint: unavailable" in brief
    assert "`research/checkpoints/incomplete`" not in brief


def test_v4_brief_indexes_all_experiments_newest_first_without_candidate_metrics(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text(
        "## campaign / Scientific strategy\n\n**Direction:** Investigate updates.\n\n"
        "**Lessons and limits:** Only one run exists.\n\n**Open questions:** Why?\n\n"
        "**Conditional next steps:** Measure when needed.\n",
        encoding="utf-8",
    )
    results = [
        {
            "campaign_id": "campaign",
            "index": index,
            "kind": "training",
            "family": "method",
            "candidates": [],
            "hypothesis_assessment": f"Assessment {index}",
            "postmortem": "research/postmortems.md",
        }
        for index in range(1, 7)
    ]
    (research_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(result) for result in results) + "\n", encoding="utf-8"
    )
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
                "working_lineage": None,
                "best_known_lineage": None,
                "retained_lineages": [],
                "last_verdict": "awaiting analysis",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    rendered = render_research_brief()

    assert "## Current phase and latest event" in rendered
    assert "## Working lineage" in rendered
    assert "## Best-known model" in rendered
    assert "## Campaign experiment index" in rendered
    assert "| 6 |" in rendered and "| 1 |" in rendered
    assert rendered.index("| 6 |") < rendered.index("| 1 |")
    assert rendered.count("unmeasured") >= 6
    assert "candidate_metrics" not in rendered
    assert "- Hypothesis assessment: Assessment 6" in rendered
    assert "[postmortem](research/postmortems.md)" in rendered
    assert rendered.index("## Current phase and latest event") < rendered.index(
        "## Latest experiment"
    )
    assert rendered.index("## Latest experiment") < rendered.index(
        "## Current scientific direction"
    )
    assert rendered.index("## Current scientific direction") < rendered.index(
        "## Current lineages and scientific recipes"
    )
    assert rendered.index("## Current lineages and scientific recipes") < rendered.index(
        "## Working lineage"
    )
    assert rendered.index("## Working lineage") < rendered.index(
        "## Campaign experiment index"
    )


def test_v4_brief_groups_long_campaign_checkpoint_and_evidence_detail(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text(
        "## campaign / Scientific strategy\n\n**Direction:** Investigate updates.\n\n"
        "**Lessons and limits:** Evidence remains experiment-scoped.\n\n"
        "**Open questions:** Which update helps?\n\n"
        "**Conditional next steps:** Measure when needed.\n",
        encoding="utf-8",
    )

    def records(unmeasured: int, measurements: int) -> list[dict]:
        return [
            {
                "schema_version": 4,
                "campaign_id": "campaign",
                "index": index,
                "kind": "training",
                "family": "method",
                "candidates": [
                    {
                        "name": "measured",
                        "evaluations": [
                            {
                                "panel": "development-v1",
                                "seed": seed,
                                "episodes": 20,
                                "evaluation_artifact": (
                                    f"research/evaluations/experiment-{index}-{seed}.json"
                                ),
                            }
                            for seed in range(measurements)
                        ],
                    },
                    *[
                        {"name": f"checkpoint-{checkpoint}", "evaluations": []}
                        for checkpoint in range(unmeasured)
                    ],
                ],
                "hypothesis_assessment": f"Assessment {index}",
                "postmortem": "research/postmortems.md",
            }
            for index in range(1, 26)
        ]

    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "last_verdict": "awaiting proposal",
    }
    (research_dir / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    compact_records = records(19, 1)
    results_path = research_dir / "results.jsonl"
    results_path.write_text(
        "\n".join(json.dumps(record) for record in compact_records) + "\n",
        encoding="utf-8",
    )
    compact = render_research_brief()
    expanded_records = records(199, 50)
    results_path.write_text(
        "\n".join(json.dumps(record) for record in expanded_records) + "\n",
        encoding="utf-8",
    )
    expanded = render_research_brief()

    assert compact.count("1 measured checkpoint; 19 unmeasured checkpoints") == 50
    assert "research_evaluation/development-v1: 1 measurement" in compact
    assert "experiment-25-0.json" in results_path.read_text(encoding="utf-8")
    assert "experiment-25-0.json" not in expanded
    assert "checkpoint-198" not in expanded
    assert len(expanded) - len(compact) < 250


def test_v4_brief_compacts_unmeasured_checkpoints_and_keeps_measured_rows(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "pending_analysis": {
            "experiment": 3,
            "result": {"index": 3},
            "candidates": [
                {
                    "name": f"checkpoint-{steps}",
                    "timesteps": steps,
                    "training_success": value,
                    "ep_rew_mean": value * 10,
                    "artifact": f"research/checkpoints/checkpoint-{steps}",
                    "evaluations": (
                        [{"panel": "development", "episodes": 20}]
                        if steps == 10240
                        else []
                    ),
                }
                for index in range(24)
                for steps, value in [
                    (
                        (index + 1) * 5120,
                        {0: 0.1, 1: 0.4, 2: 0.3}.get(index, 0.2),
                    )
                ]
            ],
        },
    }
    (research_dir / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()
    latest = brief.split("## Latest experiment", 1)[1].split(
        "## Current scientific direction", 1
    )[0]

    assert latest.count("| `checkpoint-") == 1
    assert "| `checkpoint-10240` | 10,240 |" in latest
    assert "Unmeasured checkpoints: 23 of 24; steps 5,120-122,880" in latest
    assert "Training proxy trajectory: initial 0.1 at 5,120 steps; best 0.4 at 10,240 steps; final 0.2 at 122,880 steps (training success training proxy" in latest
    inventory = brief.split(
        "### Current experiment checkpoints available for measurement", 1
    )[1].split("## Working lineage", 1)[0]
    assert inventory.count("checkpoint-") == 24
    assert "Artifact base path: `research/checkpoints`" in inventory
    assert "24 checkpoints available for measurement; steps 5,120-122,880" in inventory


def test_v4_brief_reports_a_terminal_official_assessment(monkeypatch, tmp_path):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(
            {
                "schema_version": 4,
                "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
                "working_lineage": None,
                "best_known_lineage": None,
                "retained_lineages": [],
                "terminal_campaign_status": "goal_not_reached",
                "official_benchmark_model": {
                    "selected": "best_known",
                    "artifact": "research/checkpoints/best-known",
                },
                "official_benchmark_verdict": "goal_not_reached",
                "official_metrics": {"goal_reached": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    rendered = render_research_brief()

    assert "Current phase: terminal official assessment" in rendered
    assert "Available deliverables: none; the campaign is complete" in rendered
    assert "Model: best_known (research/checkpoints/best-known)" in rendered
    assert "Verdict: goal_not_reached" in rendered
    assert "Terminal assessment: goal_not_reached" in rendered


def test_brief_groups_original_and_replication_evidence(monkeypatch, tmp_path):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "index": index,
                    "verdict": "measured",
                    "hypothesis": "check spread",
                    "family": "method",
                    "training_seed": seed,
                    "candidate_metrics": {"success_percent": success},
                    **(
                        {"kind": "training", "change": "same method"}
                        if replication_of is None
                        else {"kind": "replication"}
                    ),
                    **(
                        {"replication_of": replication_of}
                        if replication_of is not None
                        else {}
                    ),
                }
            )
            for index, seed, success, replication_of in [
                (12, 1, 40.0, None),
                (15, 2, 60.0, 12),
                (16, 3, 50.0, 12),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "## Replication Evidence" in brief
    assert "`12`" in brief
    assert "seed 1" in brief and "seed 2" in brief and "seed 3" in brief
    assert "40.00-60.00%" in brief
    assert "Replicate the current method from fresh initialization" in brief


def test_brief_keeps_the_declared_family_without_deriving_a_taxonomy(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        json.dumps(
            {
                "index": 3,
                "verdict": "measured",
                "change": "increase the closeness reward",
                "hypothesis": "shaping",
                "family": "declared-family",
                "candidate_metrics": {"success_percent": 40.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "declared-family" in brief
    assert "## Tested hypothesis families" not in brief
    assert "reward.CLOSENESS_COEFFICIENT" not in brief


def test_lineage_orchestration_requires_markdown_postmortem():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")
    program = (root / "research" / "program.md").read_text(encoding="utf-8")

    assert "Test-LineageResearchMemory" in script
    assert "postmortems.md" in script
    assert "preserved candidate artifacts" not in script
    assert "preserve_candidates" not in script
    assert "previous_experiment_postmortem" not in program


def test_postmortems_are_presented_as_contestable_interpretations(
    monkeypatch, tmp_path
):
    root = Path(__file__).resolve().parents[2]
    for source in (root / "run_research.ps1", root / "research" / "program.md"):
        text = source.read_text(encoding="utf-8").lower()
        assert "do not retry" not in text
        assert "be retried" not in text

    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text(
        "## Experiment 1 - legacy entry\n\n"
        "**Result:** legacy result.\n\n"
        "**Observed behavior:** legacy behavior.\n\n"
        "**What was learned / do NOT retry:** legacy conclusion.\n\n"
        "## Experiment 2 - neutral entry\n\n"
        "**Result:** neutral result.\n\n"
        "**Observed behavior:** neutral behavior.\n\n"
        "**Interpretation:** neutral conclusion.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)
    brief = render_research_brief()

    assert "## Prior researcher interpretations" in brief
    assert "may be reconsidered when evidence" in brief
    # Both heading generations are readable and both render neutrally.
    assert "Interpretation: legacy conclusion." in brief
    assert "Interpretation: neutral conclusion." in brief
    assert "do NOT retry" not in brief


def test_unfamiliar_postmortem_heading_does_not_erase_the_experiment(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text(
        "## Experiment 3 - unfamiliar layout\n\n"
        "**Takeaway:** the arm stalls once the target moves outward.\n\n"
        "**Evidence inspected:** `research/evaluations/e3.json`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)
    brief = render_research_brief()

    assert "Experiment 3 - unfamiliar layout" in brief
    assert "the arm stalls once the target moves outward" in brief
    assert "Evidence inspected: unavailable" in brief
    assert "research/evaluations/e3.json" not in brief


def test_postmortem_evidence_normalizes_an_existing_legacy_path(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    evaluations_dir = research_dir / "evaluations"
    evaluations_dir.mkdir(parents=True)
    (evaluations_dir / "e3.json").write_text("{}", encoding="utf-8")
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text(
        "## Experiment 3\n\n"
        "**Result:** measured.\n\n"
        "**Evidence inspected:** `research\\evaluations\\e3.json`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    brief = render_research_brief()

    assert "Evidence inspected: `research/evaluations/e3.json`" in brief


def test_research_runtime_preflight_runs_before_any_researcher_session():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")
    lines = script.splitlines()

    guard = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "Assert-ResearchRuntime"
    )
    first_session = next(
        index for index, line in enumerate(lines) if "researcher_copilot.py" in line
    )
    first_runner = next(
        index
        for index, line in enumerate(lines)
        if "uv run python research/run_experiment.py" in line
    )

    assert "import robot_learning.train; import research.run_experiment" in script
    assert guard < first_session
    assert guard < first_runner
    assert "internally inconsistent" in script


def test_lineage_retry_gate_requires_attested_evidence():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")
    instruments = (root / "research" / "instruments.md").read_text(
        encoding="utf-8"
    )

    assert "--check-lineage-evidence" in script
    assert "LineageValidationFeedback" in script
    assert "failed validation: $lineageProblem" in script
    assert "Evidence inspected" in instruments


def test_research_contract_exposes_choices_and_exact_closure_conditions():
    root = Path(__file__).resolve().parents[2]
    program = (root / "research" / "program.md").read_text(encoding="utf-8")
    instruments = (root / "research" / "instruments.md").read_text(
        encoding="utf-8"
    )
    combined = f"{program}\n{instruments}".lower()

    for forbidden in (
        "this is the complete task",
        "bounded task",
        "five entries",
        "iterative optimization surface",
    ):
        assert forbidden not in combined
    assert "choose the operation that fits that question" in combined
    assert "continuation, replication, or\n   training" in combined
    assert "fresh training does not by itself establish" in combined
    assert "repeated evidence from that panel" in combined
    assert "best_known` requires exactly a" in combined
    assert "candidate string and reason string" in combined
    assert '"action": "<keep | revert | restore>"' in instruments
    assert "For `restore`, `code.lineage` is required" in instruments
    assert "omit `code.lineage`" in instruments
    assert "the Runner resolves that\nmodel's recorded measurements" in instruments
    assert "the researcher is responsible for judging whether the evidence backing a" in combined
    assert "assesses the frozen best-known" in instruments


def test_researcher_retries_resume_this_phase_own_session():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    # The v4 analysis phase joins the legacy compatibility phases, with one retry.
    assert script.count("Invoke-ResearcherSession -Prompt $") == 8
    assert script.count("-Continue") == 4
    # A retry resumes an identity this phase minted, not an implicit last session.
    assert "[guid]::NewGuid().ToString()" in script
    assert '$sessionArgs += "--resume"' in script
    assert "--continue" not in script


def test_researcher_prompts_leave_execution_to_the_launcher():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    assert script.count("invoke research/run_experiment.py") == 6
    assert "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py" in script
    assert "Experiment was already executed during the research session" not in script
    assert "The researcher executed an experiment during the new-hypothesis" in script


def test_v4_analysis_prompt_offers_measurement_or_closure_with_one_preflight():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    assert "pending_analysis" in script
    assert "--check-analysis-deliverable" in script
    assert "Choose exactly one outcome" in script
    assert "Candidate-only measurement and closure without new measurements are valid." in script
    assert "If best_known remains unchanged, omit the best_known field." in script
    assert "Do not restate or reselect it." in script
