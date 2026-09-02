import json
from pathlib import Path

from research.build_research_brief import render_research_brief
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


def test_training_log_parser_groups_metric_snapshots():
    records = parse_training_records(SAMPLE_LOG)

    assert len(records) == 2
    assert records[0]["success_rate"] == 0.25
    assert records[0]["total_timesteps"] == 1024
    assert records[1]["std"] == 0.5


def test_brief_renders_checkpoint_aligned_facts_for_every_pending_candidate(
    monkeypatch, tmp_path
):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
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
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "`earlier` — 20;unavailable;unavailable;`research/checkpoints/earlier`" in brief
    assert "`later` — 120;0;0;`research/checkpoints/later`" in brief
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
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
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
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    brief = render_research_brief()

    assert "hold-focused: pooled success 50.00%" in brief
    assert "4 episodes, seed 3000, success 50.00%" in brief
    assert "research/evaluations/evaluation-experiment-4-1.json" in brief
    assert (
        "Accepted evaluation detail: "
        "`research/evaluations/evaluation-experiment-3-champion-4ep-seed1000-ab.json`"
    ) in brief
    assert "Open the detailed evaluation artifacts listed below" in brief
    assert "Measured challenger diagnostics" not in brief
    assert "Observed failure diagnostics" not in brief


def test_brief_groups_original_and_exact_replications(monkeypatch, tmp_path):
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "research_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "index": index,
                    "verdict": "measured",
                    "change": "same method",
                    "hypothesis": "check spread",
                    "family": "method",
                    "training_seed": seed,
                    "candidate_metrics": {"success_percent": success},
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
    program = (root / "research" / "program.md").read_text(encoding="utf-8")

    assert "--check-lineage-evidence" in script
    assert "LineageValidationFeedback" in script
    assert "failed validation: $lineageProblem" in script
    assert "Evidence inspected" in program


def test_researcher_retries_resume_this_phase_own_session():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    # One process boundary, three bounded phases, one retry each.
    assert script.count("Invoke-ResearcherSession -Prompt $") == 6
    assert script.count("-Continue") == 3
    # A retry resumes an identity this phase minted, not an implicit last session.
    assert "[guid]::NewGuid().ToString()" in script
    assert '$sessionArgs += "--resume"' in script
    assert "--continue" not in script


def test_researcher_prompts_leave_execution_to_the_launcher():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    assert script.count("invoke research/run_experiment.py") == 6
    assert "Experiment was already executed during the research session" not in script
    assert "The researcher executed an experiment during the new-hypothesis" in script
