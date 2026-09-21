"""Issue #53: the candidate inventory must not offer only training proxies.

The post-training brief forces a choice among many checkpoints, but the old
inventory exposed only ``training_success`` and ``ep_rew_mean`` as per-candidate
discriminators, so those proxies became the de facto selection criterion. These
tests pin that the inventory also carries non-proxy descriptors derived from the
preserved raw training records (position in the run, trajectory direction,
variability and location), that missing raw context is labelled honestly, that
location labels are tie-aware, that the display order is still a
metric-independent permutation, and that only the current candidates' actual
measured training parent is surfaced as an ancestor.
"""

import json
from pathlib import Path

from research.build_research_brief import render_research_brief

ROOT = Path(__file__).resolve().parents[2]


def _candidate(name, *, success, reward, evaluations=None):
    steps = int(name.split("-")[-1])
    return {
        "name": name,
        "timesteps": steps,
        "training_success": success,
        "ep_rew_mean": reward,
        "artifact": f"research/checkpoints/{name}",
        "evaluations": evaluations or [],
    }


def _log_text(records):
    lines = []
    for record in records:
        lines.append("| rollout/           |")
        for key in ("ep_rew_mean", "success_rate"):
            if key in record:
                lines.append(f"|    {key}     | {record[key]} |")
        lines.append("| time/              |")
        lines.append(f"|    total_timesteps | {record['total_timesteps']} |")
    return "\n".join(lines) + "\n"


def _render_inventory(
    monkeypatch,
    tmp_path,
    candidates,
    *,
    experiment=3,
    records=None,
    training_parent_lineage=None,
    state_extra=None,
):
    research_dir = tmp_path / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    if records is not None:
        log_dir = research_dir / "training_logs" / "campaign"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"experiment-{experiment}-attempt-1.log").write_text(
            _log_text(records), encoding="utf-8"
        )
    pending = {
        "experiment": experiment,
        "result": {"index": experiment},
        "candidates": candidates,
    }
    if training_parent_lineage is not None:
        pending["training_parent_lineage"] = training_parent_lineage
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "pending_analysis": pending,
    }
    if state_extra:
        state.update(state_extra)
    (research_dir / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)
    text = render_research_brief()
    return text.split("### Current experiment candidate inventory", 1)[1].split(
        "## Working lineage", 1
    )[0]


def _lineage(label, artifact, *, origin=2, evidence=()):
    return {
        "candidate": label,
        "origin_experiment": origin,
        "training_steps": 2000,
        "artifact": f"research/checkpoints/{label}",
        "fingerprint": f"{label}-fingerprint",
        "scientific_commit": f"{label}-commit",
        "parameters": {},
        "evaluation_artifacts": list(evidence),
        "reason": f"Reason for {label}.",
    }


_VARYING_RAW_RECORDS = [
    {"total_timesteps": 5120, "success_rate": 0.1, "ep_rew_mean": 1.0},
    {"total_timesteps": 10240, "success_rate": 0.4, "ep_rew_mean": 2.0},
    {"total_timesteps": 20480, "success_rate": 0.6, "ep_rew_mean": 3.0},
    {"total_timesteps": 30720, "success_rate": 0.2, "ep_rew_mean": 1.5},
    {"total_timesteps": 40960, "success_rate": 0.3, "ep_rew_mean": 2.5},
]


def test_inventory_exposes_raw_derived_non_proxy_discriminators(monkeypatch, tmp_path):
    # Endpoint proxies rise monotonically, so any turning point must come from
    # the raw training records rather than the checkpoint endpoint values.
    candidates = [
        _candidate(f"checkpoint-{step}", success=0.1 * (index + 1), reward=float(index))
        for index, step in enumerate((5120, 10240, 20480, 30720, 40960))
    ]
    inventory = _render_inventory(
        monkeypatch, tmp_path, candidates, records=_VARYING_RAW_RECORDS
    )

    header = next(
        line for line in inventory.splitlines() if line.startswith("| Candidate |")
    )
    # At least one discriminator that is neither of the two training proxies.
    assert "Run position" in header
    assert "location and shape" in header
    # The shape comes from the raw records, not the monotone endpoint proxies.
    assert "local max" in inventory
    assert "local min" in inventory
    assert "local spread" in inventory
    # Distributional context, not only bare endpoint values.
    assert "Training-record spread across this run" in inventory
    assert "Q1-Q3" in inventory
    # The disclaimer is a positive instruction, not only a negation.
    assert "not task measurements" in inventory
    assert "weak strategy" in inventory
    assert "spans the question you are asking" in inventory


def test_missing_raw_log_context_is_labelled_unavailable(monkeypatch, tmp_path):
    candidates = [_candidate("checkpoint-5120", success=0.9, reward=9.0)]
    inventory = _render_inventory(monkeypatch, tmp_path, candidates)

    # The endpoint proxies are high, but no raw context exists to describe shape.
    assert "raw log unavailable" in inventory
    assert "Raw training records are unavailable" in inventory
    assert "local max" not in inventory
    assert "local spread" not in inventory


def test_quartile_labels_are_tie_aware_for_constant_and_tied_values(
    monkeypatch, tmp_path
):
    constant_records = [
        {"total_timesteps": step, "success_rate": 0.5, "ep_rew_mean": 4.0}
        for step in (5120, 10240, 20480, 30720, 40960)
    ]
    candidates = [
        _candidate(f"checkpoint-{step}", success=0.5, reward=4.0)
        for step in (5120, 10240, 20480, 30720, 40960)
    ]
    inventory = _render_inventory(
        monkeypatch, tmp_path, candidates, records=constant_records
    )

    # A constant distribution centres at the median quarter, never Q4 for all.
    assert "Q2" in inventory
    assert "Q4" not in inventory
    assert "flat" in inventory

    tied_records = [
        {"total_timesteps": 5120, "success_rate": 0.5, "ep_rew_mean": 4.0},
        {"total_timesteps": 10240, "success_rate": 0.5, "ep_rew_mean": 4.0},
        {"total_timesteps": 20480, "success_rate": 0.9, "ep_rew_mean": 9.0},
    ]
    tied_candidates = [
        _candidate("checkpoint-5120", success=0.5, reward=4.0),
        _candidate("checkpoint-10240", success=0.5, reward=4.0),
        _candidate("checkpoint-20480", success=0.9, reward=9.0),
    ]
    tied = _render_inventory(
        monkeypatch, tmp_path, tied_candidates, records=tied_records
    )
    # The two tied low values share one location; the single high value is Q4.
    # Both the success and reward contexts carry the same tie.
    assert tied.count("Q2") == 4
    assert tied.count("Q4") == 2


def test_fresh_initialization_has_no_ancestor_measurement_claim(monkeypatch, tmp_path):
    candidates = [_candidate("checkpoint-5120", success=0.5, reward=5.0)]
    inventory = _render_inventory(
        monkeypatch,
        tmp_path,
        candidates,
        state_extra={
            "working_lineage": _lineage(
                "working", "working", evidence=["research/evaluations/working.json"]
            ),
            "best_known_lineage": _lineage(
                "best", "best", evidence=["research/evaluations/best.json"]
            ),
            "retained_lineages": [
                {
                    **_lineage(
                        "alternate",
                        "alternate",
                        evidence=["research/evaluations/alternate.json"],
                    ),
                    "id": "alternate",
                }
            ],
        },
    )

    # No training parent exists, so no ancestor measurement may be claimed.
    assert "Task-level measurement recorded" not in inventory
    assert "working.json" not in inventory
    assert "best.json" not in inventory
    assert "alternate.json" not in inventory


def test_only_the_actual_training_parent_measurement_is_surfaced(monkeypatch, tmp_path):
    candidates = [_candidate("checkpoint-5120", success=0.5, reward=5.0)]
    parent = _lineage(
        "checkpoint-parent",
        "parent",
        origin=7,
        evidence=["research/evaluations/parent.json"],
    )
    inventory = _render_inventory(
        monkeypatch,
        tmp_path,
        candidates,
        training_parent_lineage=parent,
        state_extra={
            "working_lineage": _lineage(
                "working", "working", evidence=["research/evaluations/working.json"]
            ),
            "best_known_lineage": _lineage(
                "best", "best", evidence=["research/evaluations/best.json"]
            ),
            "retained_lineages": [
                {
                    **_lineage(
                        "alternate",
                        "alternate",
                        evidence=["research/evaluations/alternate.json"],
                    ),
                    "id": "alternate",
                }
            ],
        },
    )

    assert "Task-level measurement recorded for the frozen training parent" in inventory
    assert "`checkpoint-parent`" in inventory
    assert "origin experiment 7" in inventory
    assert "`research/evaluations/parent.json`" in inventory
    # Unrelated saved lineages are not ancestors and must be excluded.
    assert "working.json" not in inventory
    assert "best.json" not in inventory
    assert "alternate.json" not in inventory


def test_inventory_order_is_not_a_training_metric_sort(monkeypatch, tmp_path):
    names = [
        "checkpoint-5120",
        "checkpoint-10240",
        "checkpoint-20480",
        "checkpoint-30720",
        "checkpoint-40960",
    ]

    def order_for(values):
        candidates = [
            _candidate(name, success=values[name], reward=values[name] * 10)
            for name in names
        ]
        inventory = _render_inventory(
            monkeypatch,
            tmp_path,
            candidates,
            records=_VARYING_RAW_RECORDS,
        )
        return [
            line.split("|")[1].strip()
            for line in inventory.splitlines()
            if line.startswith("| `checkpoint-")
        ]

    ascending = {name: index for index, name in enumerate(names)}
    descending = {name: -index for index, name in enumerate(names)}
    ascending_order = order_for(ascending)
    descending_order = order_for(descending)

    # Reversing the proxy values cannot reorder the rows ...
    assert ascending_order == descending_order
    # ... and the order is not the metric order or the step order either.
    assert ascending_order != [f"`{name}`" for name in names]
    assert len(ascending_order) == len(names)


def test_launcher_excludes_training_proxies_as_sufficient_reasons():
    launcher = " ".join((ROOT / "run_research.ps1").read_text(encoding="utf-8").split())

    assert "Training-time proxy values" in launcher
    assert (
        "are not task measurements and are not sufficient reasons on their own"
        in launcher
    )
