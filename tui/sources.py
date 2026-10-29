"""Resilient read-only access to campaign files.

Campaign files are rewritten atomically by the Runner, and JSONL stores are
upserted in place. A read can observe a partial write, a short-lived empty
file or a record appended between reads. These helpers never raise for a
transient condition and never write anything.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from runner import paths

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


class CampaignSources:
    """Reads the durable campaign files selected by the campaign root."""

    def __init__(self, campaign_root: Path | None = None) -> None:
        self._campaign_root = Path(campaign_root) if campaign_root else None
        self._usage_path: Path | None = None

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
        state = read_json(self._locations()[0])
        value = ((state or {}).get("campaign") or {}).get("id")
        return str(value) if value else None

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
