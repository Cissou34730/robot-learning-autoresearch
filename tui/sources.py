"""Resilient read-only access to campaign files.

Campaign files are rewritten atomically by the Runner, and JSONL stores are
upserted in place. A read can observe a partial write, a short-lived empty
file or a record appended between reads. These helpers never raise for a
transient condition and never write anything.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from runner import paths
from tui.development import freeze

_RETRY_ATTEMPTS = 5
_RETRY_PAUSE = 0.02


def modified_ns(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def is_recent(path: Path | None, max_age_seconds: float) -> bool:
    stamp = modified_ns(path)
    if stamp is None:
        return False
    age = time.time() - stamp / 1_000_000_000
    return age <= max_age_seconds


def read_json(path: Path | None) -> dict | None:
    """Return parsed JSON, tolerating atomic replacement mid-read."""
    if path is None:
        return None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            parsed = json.loads(text)
        except ValueError:
            if attempt + 1 < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_PAUSE)
                continue
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def read_jsonl(path: Path | None) -> list[dict]:
    """Return parsed JSONL records, skipping torn or malformed tail lines."""
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    records: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


@dataclass(frozen=True)
class DevelopmentSourcesSnapshot:
    """Worker-readable data only; never a controller or command destination."""

    campaign_id: str | None
    current_state: Mapping | None
    state: Mapping | None
    records: tuple[Mapping, ...]
    usage: tuple[Mapping, ...]
    archived: bool
    source_available: bool
    explanation: str | None
    delivery_stage: str | None
    last_known: bool
    training_metrics: Mapping
    stamp: tuple


def _file_stamp(path: Path) -> tuple:
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_size
    except OSError:
        return str(path), None, None


def _development_files(root: Path, campaign_id: str | None) -> tuple[Path, ...]:
    files = (
        root / "runner/state/research_state.json",
        root / "campaigns/results.jsonl",
    )
    return (
        (*files, root / f"reports/session_usage/{campaign_id}.jsonl")
        if campaign_id
        else files
    )


def _campaign_identity(state: Mapping | None) -> str | None:
    campaign = (state or {}).get("campaign")
    identity = campaign.get("id") if isinstance(campaign, Mapping) else None
    return (
        identity
        if isinstance(identity, str)
        and identity
        and not any(part in identity for part in ("/", "\\", ":"))
        and identity not in {".", ".."}
        else None
    )


def _has_development(state: Mapping | None) -> bool:
    state = state or {}
    session = state.get("scientific_session")
    return (
        bool(state.get("recipe_development"))
        or state.get("campaign_phase") == "recipe_development"
        or isinstance(session, Mapping)
        and session.get("kind") == "recipe_development"
    )


def _immutable(value: Mapping | None) -> Mapping | None:
    return cast(Mapping, freeze(value)) if value is not None else None


class CampaignSources:
    """Reads the durable campaign files selected by the campaign root."""

    def __init__(self, campaign_root: Path | None = None) -> None:
        self._campaign_root = Path(campaign_root) if campaign_root else None
        self._usage_path: Path | None = None
        self._development_root: Path | None = None
        self._development_id: str | None = None
        self._development_cache: DevelopmentSourcesSnapshot | None = None
        self._development_metric_paths: tuple[Path, ...] = ()

    def _locations(self) -> tuple[Path, Path, Path]:
        if self._campaign_root is not None:
            # Explicit per-campaign root (operator console tabs): frozen at
            # construction, never rebound through runner.paths globals.
            root = self._campaign_root
            return (
                root / "runner" / "state" / "research_state.json",
                root / "campaigns" / "results.jsonl",
                root / "reports" / "session_usage",
            )
        return (
            paths.STATE_PATH,
            paths.RESULTS_PATH,
            paths.ROOT / "reports" / "session_usage",
        )

    def stamp(self) -> tuple:
        """Changes whenever any durable source file is rewritten."""
        state_path, results_path, _ = self._locations()
        return (
            modified_ns(state_path),
            modified_ns(results_path),
            modified_ns(self._usage_path),
        )

    def campaign_id(self) -> str | None:
        """The campaign this folder holds now; reads the state file only."""
        state = self.campaign_state()
        value = ((state or {}).get("campaign") or {}).get("id")
        return str(value) if value else None

    def campaign_state(self) -> dict | None:
        return read_json(self._locations()[0])

    def read(self) -> tuple[dict | None, list[dict], list[dict]]:
        state_path, results_path, usage_dir = self._locations()
        state = read_json(state_path)
        records = read_jsonl(results_path)
        usage_rows = []
        campaign_id = (state or {}).get("campaign", {}).get("id")
        self._usage_path = None
        if campaign_id:
            self._usage_path = usage_dir / f"{campaign_id}.jsonl"
            usage_rows = read_jsonl(self._usage_path)
        return state, records, usage_rows

    def development_stamp(self) -> tuple:
        """Cheap metadata check covering public, archive, marker and bound metrics."""
        root = (self._campaign_root or paths.ROOT).resolve()
        identity = self._development_id if root == self._development_root else None
        files = list(_development_files(root, identity))
        files.append(paths.recipe_handoff_directory(root) / "handoff.json")
        if identity:
            files.extend(
                _development_files(
                    paths.recipe_development_archive(root, identity), identity
                )
            )
        if root == self._development_root:
            files.extend(self._development_metric_paths)
        return tuple(_file_stamp(path) for path in files)

    @staticmethod
    def _training_metrics(root: Path, state: Mapping) -> tuple[dict, tuple[Path, ...]]:
        candidates = state.get("candidates") or {}
        candidates = dict(candidates) if isinstance(candidates, Mapping) else {}
        pending = state.get("pending_operation") or {}
        if isinstance(pending, Mapping):
            data = pending.get("data") or {}
            archived = (
                data.get("archived_candidates") if isinstance(data, Mapping) else None
            )
            for item in archived or ():
                if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                    candidates[f"{pending.get('id')}:{item['name']}"] = item
        bound = []
        metrics = {}
        for identity, candidate in candidates.items():
            artifact = (
                candidate.get("artifact") if isinstance(candidate, Mapping) else None
            )
            if not isinstance(artifact, str) or not artifact:
                continue
            relative = Path(artifact)
            if (
                relative.is_absolute()
                or relative.drive
                or ".git" in relative.parts
                or ".." in relative.parts
                or ":" in artifact
            ):
                continue
            try:
                target = (root / relative / "training_metrics.json").resolve()
                if not target.is_relative_to(root):
                    continue
            except (OSError, ValueError):
                continue
            bound.append(target)
            packet = read_json(target)
            if packet is not None:
                metrics[identity] = packet
        return metrics, tuple(bound)

    def read_development(self) -> DevelopmentSourcesSnapshot:
        """Read development independently of the public campaign report.

        Keep the first current state separate so the UI can confirm delivery.
        A missing root during a swap may use the same identity's last valid data.
        """
        root = (self._campaign_root or paths.ROOT).resolve()
        if root != self._development_root:
            self._development_root = root
            self._development_id = None
            self._development_cache = None
            self._development_metric_paths = ()
        stamp = self.development_stamp()
        cached = self._development_cache
        if cached is not None and stamp == cached.stamp:
            return cached
        public_stamp = _file_stamp(root / "runner/state/research_state.json")
        current = read_json(root / "runner/state/research_state.json")
        identity = _campaign_identity(current)
        marker = read_json(paths.recipe_handoff_directory(root) / "handoff.json") or {}
        if marker.get("root") != str(root) or marker.get("version") != 1:
            marker = {}
        if current is None:
            identity = self._development_id
            if (
                identity is None
                and not root.exists()
                and marker.get("stage") == "ready"
            ):
                value = marker.get("campaign_id")
                identity = value if isinstance(value, str) and value else None
        if identity != self._development_id:
            cached = None
            self._development_cache = None
            self._development_metric_paths = ()
        self._development_id = identity
        read_stamp = self.development_stamp()
        stage = marker.get("stage") if marker.get("campaign_id") == identity else None
        stage = stage if isinstance(stage, str) else None
        source_root = root
        state = current if _has_development(current) else None
        archived = False
        explanation = None
        if state is None and identity:
            source_root = paths.recipe_development_archive(root, identity)
            archived_state = read_json(source_root / "runner/state/research_state.json")
            if _campaign_identity(archived_state) == identity and _has_development(
                archived_state
            ):
                state = archived_state
                archived = True
                if current is None:
                    explanation = (
                        "Public campaign state is unavailable during delivery."
                    )
        if (
            state is None
            and cached is not None
            and cached.source_available
            and (
                current is None
                or stage in {"preparing", "ready", "awaiting_session_end"}
            )
        ):
            bundle = replace(
                cached,
                current_state=_immutable(current),
                delivery_stage=stage,
                last_known=True,
                explanation="Development source is temporarily unavailable; showing last known data.",
                stamp=self.development_stamp(),
            )
            self._development_cache = bundle
            return bundle
        records = (
            read_jsonl(source_root / "campaigns/results.jsonl")
            if state is not None
            else []
        )
        usage = (
            read_jsonl(source_root / f"reports/session_usage/{identity}.jsonl")
            if state is not None and identity
            else []
        )
        metrics, self._development_metric_paths = (
            self._training_metrics(source_root, state)
            if state is not None
            else ({}, ())
        )
        final_stamp = self.development_stamp()
        final_files = {item[0]: item for item in final_stamp}
        stable = public_stamp == final_files.get(public_stamp[0]) and all(
            final_files.get(item[0]) == item for item in read_stamp
        )
        bundle = DevelopmentSourcesSnapshot(
            identity,
            _immutable(current),
            _immutable(state),
            tuple(cast(Mapping, freeze(record)) for record in records),
            tuple(cast(Mapping, freeze(row)) for row in usage),
            archived,
            state is not None,
            explanation
            if state is not None
            else "No recorded development source is available for this campaign.",
            stage,
            False,
            cast(Mapping, freeze(metrics)),
            final_stamp if stable else (),
        )
        self._development_cache = bundle
        return bundle
