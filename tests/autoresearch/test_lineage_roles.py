import json
from pathlib import Path

from research import runner_protocol as protocol


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode("ascii"))
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
    )
    return path


def _lineage(path: Path, *, steps: int) -> dict:
    return {
        "artifact": path.name,
        "fingerprint": f"fingerprint-{path.name}",
        "origin_experiment": 1,
        "candidate": path.name,
        "parameters": {"algorithm": {"name": path.name}},
        "scientific_commit": "a" * 40,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "reason": f"Preserve {path.name}.",
    }


def test_v4_lineage_roles_are_independent_training_parents(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    best_known = _artifact(tmp_path / "best-known-checkpoint", "best-known")
    retained = _artifact(tmp_path / "retained-checkpoint", "retained")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": _lineage(best_known, steps=80_000),
        "retained_lineages": [
            {"id": "alternative", **_lineage(retained, steps=60_000)}
        ],
    }

    working_parent = protocol.training_parent(
        {"training_parent": "working"}, state, "transfer"
    )
    best_parent = protocol.training_parent(
        {"training_parent": "best_known"}, state, "transfer"
    )
    retained_parent = protocol.training_parent(
        {"training_parent": "alternative"}, state, "transfer"
    )

    assert working_parent == ("working", working, 120_000)
    assert best_parent == ("best_known", best_known, 80_000)
    assert retained_parent == ("alternative", retained, 60_000)
    assert working.joinpath("model.zip").read_bytes() == b"working"
    assert best_known.joinpath("model.zip").read_bytes() == b"best-known"


def test_v4_measurement_catalog_exposes_roles_and_retained(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    best_known = _artifact(tmp_path / "best-known-checkpoint", "best-known")
    retained = _artifact(tmp_path / "retained-checkpoint", "retained")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": _lineage(best_known, steps=80_000),
        "retained_lineages": [
            {"id": "alternative", **_lineage(retained, steps=60_000)}
        ],
    }
    pending = {
        "candidates": [
            {
                "name": "checkpoint-40k",
                "artifact": "current-checkpoint",
                "evaluations": [],
            }
        ]
    }

    available = protocol.available_evaluation_candidates(pending, state)

    assert set(available) == {
        "checkpoint-40k",
        "working",
        "best_known",
        "alternative",
    }
    assert available["working"]["artifact"] == working.name
    assert available["best_known"]["artifact"] == best_known.name
    assert available["alternative"]["artifact"] == retained.name


def test_v4_rejects_legacy_role_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": None,
        "retained_lineages": [],
    }

    for identifier in ("accepted", "champion"):
        try:
            protocol.training_parent(
                {"training_parent": identifier}, state, "transfer"
            )
        except ValueError as error:
            assert str(error) == f"unknown training parent {identifier!r}"
        else:
            raise AssertionError(f"legacy role {identifier!r} was accepted")