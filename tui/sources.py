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
