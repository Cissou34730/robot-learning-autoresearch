"""Structured result of one Runner invocation for the launcher.

The launcher passes ``--result-path``; the Runner writes one JSON object there
when it exits. Standard output and error are diagnostics only and are never
parsed as data or forwarded to the PI.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

_path: Path | None = None
_record: dict = {"errors": []}


def configure(path: Path | None) -> None:
    global _path
    _path = path
    _record.clear()
    _record["errors"] = []


def put(key: str, value: object) -> None:
    _record[key] = value


def add_error(message: str) -> None:
    _record["errors"].append(str(message))


def add_exception(error: BaseException) -> None:
    add_error("".join(traceback.format_exception(error)).rstrip())


def write(exit_code: int) -> None:
    if _path is None:
        return
    temporary = _path.with_name(_path.name + ".tmp")
    temporary.write_text(
        json.dumps({"exit_code": exit_code, **_record}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary, _path)
