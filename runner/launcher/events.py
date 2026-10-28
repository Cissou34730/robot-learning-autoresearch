"""Launcher observations for the TUI: one-way, best effort, never control."""

from __future__ import annotations

from pathlib import Path

from runner import typed_events
from runner.event_contract import JOURNAL_SUFFIX
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
        typed_events.configure(directory / f"{campaign_id}{JOURNAL_SUFFIX}")
        return True

    def observe(
        self,
        kind: str,
        *,
        scope: str = "",
        text: str = "",
        fields: dict | None = None,
        session_id: str = "",
        attempt: str = "",
        actor: str = "launcher",
    ) -> None:
        """Identities come from the arguments, then ``fields``, then the context."""
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
                session_id=session_id or str(fields.get("session_id") or ""),
                inquiry_id=str(fields.get("inquiry_id") or ""),
                attempt=attempt,
                actor=actor,
            )
        except Exception:  # noqa: BLE001 - presenting must never alter launcher behavior
            return

    def status(
        self, message: str, *, scope: str = "info", session_id: str = ""
    ) -> None:
        self.observe("notice", scope=scope, text=message, session_id=session_id)

    def card(
        self,
        title: str,
        *,
        scope: str,
        lines: tuple[str, ...] = (),
        session_id: str = "",
    ) -> None:
        self.observe(
            "notice",
            scope=scope,
            fields={"title": title, "body": list(lines)},
            session_id=session_id,
        )
