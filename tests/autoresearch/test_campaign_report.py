"""Small in-memory report/accounting checks; no SDK, training, subprocesses or Git."""

import json
from types import SimpleNamespace

import researcher_copilot as adapter
from tools import campaign_report as report

CAMPAIGN = "045ec01f-613e-4cd7-9cac-4b3c512b0f94"


def test_usage_is_aggregate_only_and_missing_is_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "ROOT", tmp_path)
    args = SimpleNamespace(
        campaign_id=CAMPAIGN,
        experiment=2,
        phase="new hypothesis",
        attempt=1,
        session_id="session",
        model="gpt-5.6-luna",
        reasoning="high",
    )
    console = adapter.Console()
    console.tool("view", {"path": "secret-content.py"})
    adapter.record_usage(args, console, 3.2, adapter.EXIT_INTERRUPTED)
    row = json.loads(
        (tmp_path / "reports/session_usage" / f"{CAMPAIGN}.jsonl").read_text()
    )
    assert row["input_tokens"] is None
    assert row["aiu"] is None
    assert row["tool_calls"] == 1
    assert row["tools_by_name"] == {"view": 1}
    assert row["exit_code"] == 130
    assert "secret-content" not in json.dumps(row)


def test_main_records_runtime_failure_without_changing_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "ROOT", tmp_path)

    async def fail(args):
        raise RuntimeError("simulated")

    monkeypatch.setattr(adapter, "run", fail)
    code = adapter.main(
        ["prompt never stored", "--session-id", "s", "--campaign-id", CAMPAIGN]
    )
    assert code == adapter.EXIT_RUNTIME_FAILURE
    row = report.read_rows(tmp_path / "reports/session_usage" / f"{CAMPAIGN}.jsonl")[0]
    assert row["exit_code"] == code
    assert row["input_tokens"] is None
    assert "prompt never stored" not in json.dumps(row)


def test_usage_totals_count_retry_deltas_and_do_not_double_count_cache(tmp_path):
    campaign = {
        "repo": tmp_path,
        "id": CAMPAIGN,
        "state": {},
        "rows": [],
        "usage": [
            {
                "session_id": "same",
                "attempt": 1,
                "input_tokens": 100,
                "cache_read_tokens": 80,
                "output_tokens": 10,
            },
            {
                "session_id": "same",
                "attempt": 2,
                "input_tokens": 50,
                "cache_read_tokens": 40,
                "output_tokens": 5,
            },
        ],
    }
    metrics = report.comparison_metrics(campaign)
    assert metrics["Total tokens (input + output)"] == "165.00"
    assert metrics["New input tokens (input minus cache reads)"] == "30.00"
    assert metrics["AIU"] == "unavailable"
    assert (
        report.usage_total([{"aiu": 1}, {"aiu": None}], "aiu")
        == "1.00 (partial: 1/2 invocations)"
    )


def test_report_exposes_early_unmeasured_peak_and_selection_rationale(tmp_path):
    row = {
        "index": 2,
        "kind": "training",
        "initialization": "transfer",
        "family": "coverage",
        "candidates": [
            {"name": "checkpoint-20000", "timesteps": 20000, "training_success": 0.99},
            {
                "name": "checkpoint-100352",
                "timesteps": 100352,
                "training_success": 0.90,
            },
        ],
        "requested_evaluations": [
            {
                "candidate": "checkpoint-100352",
                "instrument": "research_evaluation",
                "episodes": 200,
                "seed": 0,
                "selection": "Historical matched position",
                "omitted_alternative": None,
                "metrics": {"success_percent": 90},
            }
        ],
    }
    campaign = {
        "repo": tmp_path,
        "id": CAMPAIGN,
        "state": {},
        "rows": [row],
        "usage": [],
    }
    text = report.render_report([campaign])
    assert "exact peak positions: 20000" in text
    assert "checkpoint-20000" in text
    assert "Historical matched position" in text
    assert "Historical consumption is unavailable, not zero" in text
    assert "not proof of a better model" in text


def test_comparison_keeps_campaigns_separate_and_deduplicates_artifacts(tmp_path):
    m = {
        "candidate": "checkpoint-100352",
        "instrument": "task_reference",
        "evaluation_artifact": "one.json",
        "episodes": 200,
        "success_percent": 98,
    }
    row = {"index": 1, "requested_evaluations": [m], "task_reference_evaluations": [m]}
    assert len(report.measurements(row)) == 1
    first = {"repo": tmp_path, "id": "first", "state": {}, "rows": [row], "usage": []}
    second = {"repo": tmp_path, "id": "second", "state": {}, "rows": [], "usage": []}
    text = report.render_report([first, second])
    assert "| Recorded experiments | 1 | 0 |" in text
    assert "| Instruments | task_reference: 1 | unavailable |" in text


def test_loading_and_generation_do_not_mutate_campaign_sources(tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    state = research / "research_state.json"
    history = research / "results.jsonl"
    state.write_text(json.dumps({"campaign": {"id": CAMPAIGN}}))
    history.write_text(json.dumps({"index": 1, "campaign_id": "other"}) + "\n")
    before = (state.read_bytes(), history.read_bytes())
    output = tmp_path / "reports/report.md"
    assert report.main(["--repo", str(tmp_path), "--output", str(output)]) == 0
    assert (state.read_bytes(), history.read_bytes()) == before
    assert "Recorded experiments | 0" in output.read_text()


def test_checkpoint_frequency_counts_experiments_not_instruments(tmp_path):
    row = {
        "index": 1,
        "requested_evaluations": [
            {"candidate": "checkpoint-100352", "instrument": "research_evaluation"},
            {"candidate": "checkpoint-100352", "instrument": "task_reference"},
        ],
    }
    metrics = report.comparison_metrics({"repo": tmp_path, "rows": [row], "usage": []})
    assert (
        metrics["Experiments selecting each checkpoint position"]
        == "checkpoint-100352: 1"
    )
    assert metrics["Measurement executions"] == "2"


def test_display_order_mirrors_the_brief_metric_independent_order():
    from research import build_research_brief as brief

    candidates = [
        {"name": "checkpoint-100", "artifact": "research/checkpoints/a"},
        {"name": "checkpoint-200", "artifact": "research/checkpoints/b"},
        {"name": "checkpoint-300", "artifact": "research/checkpoints/c"},
    ]
    assert [c["name"] for c in report.display_order(candidates)] == [
        c["name"] for c in brief.candidate_display_order(candidates)
    ]


def test_selection_diagnostics_expose_presentation_and_ranks(tmp_path):
    row = {
        "index": 3,
        "candidates": [
            {
                "name": "checkpoint-100",
                "timesteps": 100,
                "training_success": 0.1,
                "artifact": "research/checkpoints/checkpoint-100",
            },
            {
                "name": "checkpoint-200",
                "timesteps": 200,
                "training_success": 0.9,
                "artifact": "research/checkpoints/checkpoint-200",
            },
        ],
        "requested_evaluations": [
            {
                "candidate": "checkpoint-100",
                "instrument": "research_evaluation",
                "episodes": 10,
                "seed": 0,
                "selection": "explicit uncertainty",
                "metrics": {"success_percent": 50},
            }
        ],
    }
    diagnostics = report.selection_diagnostics([row])
    assert len(diagnostics) == 1
    experiment, name, displayed, proxy_rank, timestep_rank, endpoint = diagnostics[0]
    assert experiment == 3
    assert name == "checkpoint-100"
    assert displayed in (1, 2)
    assert proxy_rank == 2
    assert timestep_rank == "1/2"
    assert endpoint == "no"

    campaign = {
        "repo": tmp_path,
        "id": CAMPAIGN,
        "state": {},
        "rows": [row],
        "usage": [],
    }
    text = report.render_report([campaign])
    assert "### Selection diagnostics" in text
    assert "| Proxy rank |" in text
    assert "| 3 | checkpoint-100 |" in text


def test_accounting_failure_does_not_fail_a_successful_invocation(monkeypatch, capsys):
    async def succeed(args):
        return adapter.EXIT_OK

    def fail_record(*args):
        raise OSError("simulated accounting failure")

    monkeypatch.setattr(adapter, "run", succeed)
    monkeypatch.setattr(adapter, "record_usage", fail_record)
    assert adapter.main(["prompt", "--session-id", "s"]) == adapter.EXIT_OK
    assert "Session usage could not be recorded" in capsys.readouterr().err
