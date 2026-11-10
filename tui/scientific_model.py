"""Read-only view of a campaign's published scientific model."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static
from textual.worker import get_current_worker

from tui.sources import CampaignSources

MODEL_PATH = "pi_workspace/scientific_model.md"


@dataclass(frozen=True)
class ScientificModelView:
    status: str  # ready, pending, missing or error
    message: str
    commit: str | None = None
    text: str = ""


def model_status(state: dict | None) -> str | None:
    model = (state or {}).get("scientific_model")
    status = model.get("status") if isinstance(model, dict) else None
    return status if status in {"pending", "ready"} else None


def load_scientific_model(folder: Path) -> ScientificModelView:
    """The committed model recorded in the campaign state; reads only."""
    if not (folder / ".git").exists():
        return ScientificModelView("missing", "This campaign folder is not set up.")
    state = CampaignSources(folder).campaign_state()
    if state is None:
        return ScientificModelView("missing", "The campaign state is not available.")
    model = state.get("scientific_model")
    if not isinstance(model, dict):
        return ScientificModelView(
            "missing", "This campaign records no scientific model."
        )
    if model.get("status") == "pending":
        return ScientificModelView(
            "pending", "The analysis has not published the scientific model yet."
        )
    commit, path = model.get("commit"), model.get("path")
    if model.get("status") != "ready" or not commit or path != MODEL_PATH:
        return ScientificModelView(
            "error", "The scientific model record in the campaign state is not valid."
        )
    result = subprocess.run(
        ["git", "-C", str(folder), "show", f"{commit}:{path}"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git exit code {result.returncode}"
        return ScientificModelView(
            "error", f"Cannot read the published model: {detail}", commit
        )
    return ScientificModelView("ready", "", commit, result.stdout)


class ScientificModelReader(ModalScreen):
    """The published scientific model of one campaign. Esc closes."""

    BINDINGS: ClassVar[list] = [("escape", "dismiss", "Close")]
    CSS = """
    ScientificModelReader { align: center middle; }
    #model-frame {
        width: 100%; max-width: 110; height: 100%;
        padding: 0 1; background: $surface;
    }
    #model-title { text-style: bold; }
    #model-identity, #model-hint { color: $text-muted; }
    #model-status { margin-top: 1; }
    #model-scroll { height: 1fr; }
    """

    def __init__(self, label: str, folder: Path) -> None:
        super().__init__()
        self.label = label
        self.folder = folder
        self.model_view: ScientificModelView | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="model-frame"):
            yield Static(
                f"Scientific model · {self.label}", id="model-title", markup=False
            )
            yield Static(
                str(self.folder / MODEL_PATH), id="model-identity", markup=False
            )
            yield Static("Loading...", id="model-status", markup=False)
            with VerticalScroll(id="model-scroll"):
                yield Markdown(id="model-body")
            yield Static(
                "Read only · Up/Down/PgUp/PgDn scroll · Esc close", id="model-hint"
            )

    def on_mount(self) -> None:
        self.query_one("#model-body").display = False
        self._load()

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _load(self) -> None:
        worker = get_current_worker()
        try:
            view = load_scientific_model(self.folder)
        except OSError as error:
            view = ScientificModelView("error", f"Cannot read the campaign: {error}")
        if not worker.is_cancelled:
            self.app.call_from_thread(self._show, view)

    async def _show(self, view: ScientificModelView) -> None:
        self.model_view = view
        status = self.query_one("#model-status", Static)
        if view.commit:
            self.query_one("#model-identity", Static).update(
                f"{MODEL_PATH} @ {view.commit[:12]}"
            )
        if view.status != "ready":
            status.update(view.message)
            return
        status.display = False
        body = self.query_one("#model-body", Markdown)
        body.display = True
        await body.update(view.text)
        self.query_one("#model-scroll").focus()
