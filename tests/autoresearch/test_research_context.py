import json
from pathlib import Path

from research.build_research_brief import (
    _change_details,
    _v4_evidence_lines,
    render_research_brief,
)
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


def test_v4_evidence_index_is_aggregate_and_excludes_selection_rationales():
    lines = _v4_evidence_lines(
        None,
        [
            {
                "index": 1,
                "requested_evaluations": [
                    {
                        "candidate": "checkpoint-100",
                        "instrument": "research_evaluation",
                        "model_fingerprint": "abcdef1234567890",
                        "metrics": {
                            "episodes": 20,
                            "seed": 7300,
                            "success_percent": 95.0,
                        },
                    }
                ],
                "candidate_selections": {
                    "checkpoint-100": "highest proxy",
                    "checkpoint-200": "final checkpoint",
                },
            }
        ],
    )

    rendered = "\n".join(lines)
    assert "1 measurements" in rendered
    assert "1 fingerprint-bound models" in rendered
    assert "episode counts 20" in rendered
    assert "seeds 7300" in rendered
    assert "success 95.00%" not in rendered
    assert "highest proxy" not in rendered


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
        "## Current lineages and scientific recipes"
    )
    assert rendered.index("## Current lineages and scientific recipes") < rendered.index(
        "## Working lineage"
    )
    assert rendered.index("## Working lineage") < rendered.index(
        "## Campaign experiment index"
    )
    assert rendered.index("## Development evidence index") < rendered.index(
        "## Provisional scientific synthesis"
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

    assert compact.count("1 measured checkpoint; 19 unmeasured checkpoints") == 25
    assert "research_evaluation/development-v1: 1 measurement" in compact
    assert "25 measurements" in compact
    assert "episode counts 20" in compact
    assert "seeds 0" in compact
    assert "experiment-25-0.json" in results_path.read_text(encoding="utf-8")
    assert "experiment-25-0.json" not in expanded
    assert "checkpoint-198" not in expanded
    assert "1250 measurements" in expanded
    assert "seeds 0-49 (50 distinct)" in expanded
    assert len(expanded) - len(compact) < 1000


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
        "## Current lineages and scientific recipes", 1
    )[0]

    assert latest.count("| `checkpoint-") == 1
    assert "| `checkpoint-10240` | 10,240 |" in latest
    assert "Unmeasured checkpoints: 23 of 24; steps 5,120-122,880" in latest
    assert "Training proxy observations" not in latest
    assert "Training facts" not in latest
    assert "training success" not in latest
    assert "reward 4" not in latest
    inventory = brief.split(
        "### Current experiment checkpoints available for measurement", 1
    )[1].split("## Working lineage", 1)[0]
    assert inventory.count("checkpoint-") == 24
    assert "Artifact base path: `research/checkpoints`" in inventory
    assert "24 checkpoints available for measurement; steps 5,120-122,880" in inventory
    assert "at most 3 distinct models" in inventory
    assert "local 10,240 steps; accumulated 10,240 steps" in inventory


def test_v4_brief_orders_checkpoint_inventory_numerically(monkeypatch, tmp_path):
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
                    "training_success": 0.9,
                    "ep_rew_mean": 100.0,
                    "artifact": f"research/checkpoints/checkpoint-{steps}",
                    "evaluations": [],
                }
                for steps in (100352, 10240, 105472, 120832, 5120)
            ],
        },
    }
    (research_dir / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)

    inventory = render_research_brief().split(
        "### Current experiment checkpoints available for measurement", 1
    )[1].split("## Working lineage", 1)[0]
    identifiers = next(
        line for line in inventory.splitlines() if line.startswith("- Identifiers:")
    )

    positions = [
        identifiers.index(f"`checkpoint-{steps}`")
        for steps in (5120, 10240, 100352, 105472, 120832)
    ]
    assert positions == sorted(positions)


def test_v4_brief_omits_training_proxies_without_hiding_checkpoint_inventory(
    monkeypatch, tmp_path
):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    proxies = {5120: 0.2, 10240: 1.0, 20480: 1.0, 30720: 1.0, 40960: 0.7}
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
                    "training_success": proxy,
                    "ep_rew_mean": 100.0,
                    "artifact": f"research/checkpoints/checkpoint-{steps}",
                    "evaluations": [],
                }
                for steps, proxy in proxies.items()
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
        "## Current lineages and scientific recipes", 1
    )[0]
    inventory = brief.split(
        "### Current experiment checkpoints available for measurement", 1
    )[1].split("## Working lineage", 1)[0]

    assert "training success" not in latest
    assert "episode reward" not in latest
    assert "checkpoint ranking" not in latest
    assert all(f"`checkpoint-{steps}`" in inventory for steps in proxies)
    assert "steps 5,120-40,960" in inventory


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


def test_researcher_retries_resume_this_phase_own_session():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    assert script.count("Invoke-ResearcherSession -Prompt $") == 4
    assert script.count("-Continue") == 2
    # A retry resumes an identity this phase minted, not an implicit last session.
    assert "[guid]::NewGuid().ToString()" in script
    assert '$sessionArgs += "--resume"' in script
    assert "--continue" not in script


def test_researcher_prompts_leave_execution_to_the_launcher():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")

    assert script.count("invoke research/run_experiment.py") == 2
    assert "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py" in script
    assert "Experiment was already executed during the research session" not in script
    assert "The researcher executed an experiment during the new-hypothesis" in script


def test_researcher_prompts_are_objective_first_and_direction_neutral():
    root = Path(__file__).resolve().parents[2]
    script = (root / "run_research.ps1").read_text(encoding="utf-8")
    policy = (root / "researcher_copilot.py").read_text(encoding="utf-8")

    objective = "Assess progress toward a learned policy satisfying the human objective."
    interpretation = "Relate findings to the proposal's type-specific question"
    assert script.count(objective) >= 1
    assert script.index(objective) < script.index(interpretation)
    assert "prescribes no next action" in script
    assert "Conditional next steps" not in script
    assert "most informative to measure rather than the alternatives" not in script
    assert "chosen over the other available checkpoints" not in script
    assert "Context efficiency does not determine which" in policy


def test_researcher_contract_preserves_investigative_freedom_across_layers():
    root = Path(__file__).resolve().parents[2]
    program = (root / "research" / "program.md").read_text(encoding="utf-8")
    instruments = (root / "research" / "instruments.md").read_text(
        encoding="utf-8"
    )
    launcher = (root / "run_research.ps1").read_text(encoding="utf-8")
    brief_builder = (root / "research" / "build_research_brief.py").read_text(
        encoding="utf-8"
    )
    protocol = (root / "research" / "runner_protocol.py").read_text(
        encoding="utf-8"
    )
    combined = f"{program}\n{instruments}\n{launcher}\n{brief_builder}\n{protocol}".lower()
    normalized_program = " ".join(program.lower().split())
    normalized_instruments = " ".join(instruments.lower().split())
    normalized_brief_builder = " ".join(brief_builder.lower().split())
    normalized_protocol = " ".join(protocol.lower().split())

    for scientific_preference in (
        "use additional diagnosis, measurement, or replication only when",
        "prefer the simplest evidence sufficient",
        "training proxy is the only signal",
        "chosen over the other available checkpoints",
        "most informative to measure rather than the alternatives",
        "choose the question that advances the current research direction",
        "single strongest development experiment",
        "no supported material opportunity",
        "reuse compatible evidence when it answers the question",
        "already expected to satisfy",
        "not a way to resolve development uncertainty",
        "does not imply the campaign is ending",
    ):
        assert scientific_preference not in combined

    assert "assess progress toward a learned policy satisfying the human objective" in launcher.lower()
    assert "`current synthesis`: the present interpretation" in normalized_program
    assert "the synthesis records no required next action" in normalized_program
    assert "an exploratory investigation states the question, the uncertainty" in normalized_program
    assert "does not by itself reject a useful saved policy" in normalized_program
    assert "another useful investigation does not prohibit stopping" in normalized_program
    assert "`current synthesis`: the present interpretation" in normalized_program
    assert "`conditional next steps`" not in normalized_program
    assert "the researcher determines the amount and type of evidence appropriate" in normalized_program
    assert "why measuring that model is useful for the scientific question" in normalized_instruments
    assert "harness" not in normalized_program
    assert "harness" not in normalized_instruments
    for scientific_instruction in (
        "start with `research/brief.md`",
        "choose the form that supports the investigation",
        "the intended basis for deciding which checkpoints to measure",
        "when it may help explain a result or generate a useful hypothesis",
        "not a recommendation about which models are informative",
    ):
        assert scientific_instruction not in normalized_instruments
    assert "provisional scientific synthesis" in normalized_brief_builder
    assert "training proxy observations" not in normalized_brief_builder
    assert "model is useful for the current scientific question" in normalized_protocol
