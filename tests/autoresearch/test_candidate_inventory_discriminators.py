"""Issue #53: the candidate inventory must not offer only training proxies.

The post-training brief forces a choice among many checkpoints, but the old
inventory exposed only ``training_success`` and ``ep_rew_mean`` as per-candidate
discriminators, so those proxies became the de facto selection criterion. These
tests pin that the inventory also carries non-proxy descriptors (position in the
run, trajectory location and shape), that the distributional context is present,
that the display order is still a metric-independent permutation, and that
recorded task-level measurements of lineage ancestors are surfaced.
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


def _render_inventory(monkeypatch, tmp_path, candidates, *, state_extra=None):
    research_dir = tmp_path / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "pending_analysis": {
            "experiment": 3,
            "result": {"index": 3},
            "candidates": candidates,
        },
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


def test_inventory_exposes_non_proxy_discriminators_and_positive_guidance(
    monkeypatch, tmp_path
):
    candidates = [
        _candidate("checkpoint-5120", success=0.1, reward=1.0),
        _candidate("checkpoint-10240", success=0.4, reward=2.0),
        _candidate("checkpoint-20480", success=0.6, reward=3.0),
        _candidate("checkpoint-30720", success=0.2, reward=1.5),
        _candidate("checkpoint-40960", success=0.3, reward=2.5),
    ]
    inventory = _render_inventory(monkeypatch, tmp_path, candidates)

    header = next(
        line for line in inventory.splitlines() if line.startswith("| Candidate |")
    )
    # At least one discriminator that is neither of the two training proxies.
    assert "Run position" in header
    assert "location and shape" in header
    # The trajectory shape describes behaviour, not just the endpoint score.
    assert "local max" in inventory  # success and reward both peak at 20480
    assert "local min" in inventory  # success troughs at 30720
    assert "rising" in inventory or "falling" in inventory
    assert "local spread" in inventory
    # Distributional context, not only bare endpoint values.
    assert "spread across this run" in inventory
    assert "Q1-Q3" in inventory
    # The disclaimer is a positive instruction, not only a negation.
    assert "not task measurements" in inventory
    assert "weak strategy" in inventory
    assert "spans the question you are asking" in inventory


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
        inventory = _render_inventory(monkeypatch, tmp_path, candidates)
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


def test_inventory_surfaces_task_level_ancestor_measurements(monkeypatch, tmp_path):
    candidates = [_candidate("checkpoint-5120", success=0.5, reward=5.0)]
    working = {
        "candidate": "checkpoint-working",
        "origin_experiment": 2,
        "training_steps": 2000,
        "artifact": "research/checkpoints/working",
        "fingerprint": "working-fingerprint",
        "scientific_commit": "working-commit",
        "parameters": {},
        "evaluation_artifacts": ["research/evaluations/working.json"],
        "reason": "Continue the current line of research.",
    }
    inventory = _render_inventory(
        monkeypatch,
        tmp_path,
        candidates,
        state_extra={"working_lineage": working},
    )

    assert "lineage ancestors" in inventory
    assert "`working`" in inventory
    assert "`research/evaluations/working.json`" in inventory


def test_launcher_excludes_training_proxies_as_sufficient_reasons():
    launcher = " ".join((ROOT / "run_research.ps1").read_text(encoding="utf-8").split())

    assert "Training-time proxy values" in launcher
    assert (
        "are not task measurements and are not sufficient reasons on their own"
        in launcher
    )
