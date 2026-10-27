"""Launcher observations for the TUI: one-way, best effort, never control."""

from __future__ import annotations

from pathlib import Path

from runner import typed_events
from runner.launcher.summaries import load_state

_SEVERITY = {"error": "error", "warning": "warning"}


class LauncherEvents:
    """Writes the launcher's facts into the campaign's typed event feed."""

    def __init__(self, campaign_root: Path) -> None:
        self._campaign_root = campaign_root
        self._campaign_id: str | None = None

    def _bind(self) -> bool:
        if self._campaign_id:
            return True
        try:
            campaign_id = str(load_state(self._campaign_root)["campaign"]["id"] or "")
        except (OSError, ValueError, KeyError, TypeError):
            return False
        if not campaign_id:
            return False
        self._campaign_id = campaign_id
        directory = self._campaign_root / "reports" / "tui_observations"
        typed_events.set_campaign(campaign_id)
        typed_events.configure(directory / f"{campaign_id}.events.jsonl")
        return True

    def observe(
        self, kind: str, *, scope: str = "", text: str = "", fields: dict | None = None
    ) -> None:
        try:
            if not self._bind():
                return
            fields = dict(fields or {})
            payload = {
                **({"text": text} if text else {}),
                **({"scope": scope} if scope else {}),
                **fields,
            }
            typed_events.emit(
                kind,
                payload,
                scope=scope,
                severity=_SEVERITY.get(scope, "info"),
                operation_id=str(fields.get("operation_id") or ""),
                session_id=str(fields.get("session_id") or ""),
                inquiry_id=str(fields.get("inquiry_id") or ""),
            )
        except Exception:  # noqa: BLE001 - presenting must never alter launcher behavior
            return

    def status(self, message: str, *, scope: str = "info") -> None:
        self.observe("notice", scope=scope, text=message)

    def card(self, title: str, *, scope: str, lines: tuple[str, ...] = ()) -> None:
        self.observe(
            "notice", scope=scope, fields={"title": title, "body": list(lines)}
        )
