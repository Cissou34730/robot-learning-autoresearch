"""Multi-campaign launch/stop/reset control for the operator console.

Terminal-free by design: orchestration, state machines and outcome records
live here so they can be exercised with fake executors before any Textual
rendering (issue #68). Logic never edits campaign state directly; every
lifecycle action delegates to the existing initialize/reset/launcher entry
points, to the per-campaign launcher mutex, and to the cooperative
stop-request contract in ``docs/external-campaign-stop.md``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

DEFAULT_RECIPE_REF = "baseline-distinct-episodes-v3-robot"
DEFAULT_STOP_TIMEOUT = 180
MAX_SLOTS = 5

SUCCESS = "success"
FAILED = "failed"
SKIPPED = "skipped"

# Terminal-durable campaign outcomes (from research_state.json), kept apart
# from process outcomes such as launcher exit codes.
TERMINAL_OUTCOMES = (
    "official_assessment_passed",
    "official_assessment_failed",
    "no_credible_route",
)


def default_campaigns_root(harness_root: Path) -> Path:
    return harness_root.parent / "robot-learning-campaigns"


def campaigns_root(harness_root: Path) -> Path:
    configured = os.environ.get("ROBOT_LEARNING_CAMPAIGNS")
    return Path(configured) if configured else default_campaigns_root(harness_root)


class CommandError(ValueError):
    """Invalid command text; the operator sees the message."""


class ControllerError(RuntimeError):
    """A broken precondition or failed command; reported to the operator."""


class CampaignFolderError(ControllerError):
    """A selected standard campaign folder does not exist."""


@dataclass
class LaunchSettings:
    """Shared launcher parameters for one batch.

    ``None`` preserves the existing distinction between an omitted argument
    and an explicitly provided one; passing an explicit launcher default is
    not always equivalent to letting the launcher resolve it.
    """

    model: str | None = None
    provider: str | None = None
    reasoning: str | None = None
    timesteps: int | None = None
    max_timesteps: int | None = None
    max_inquiries: int | None = None
    stop_timeout_seconds: int | None = None

    def launcher_arguments(self) -> list[str]:
        if self.provider is not None and self.provider not in {
            "github-copilot",
            "opencode",
            "opencode-go",
        }:
            raise CommandError(
                "Provider must be github-copilot, opencode or opencode-go."
            )
        if self.reasoning is not None and self.reasoning not in {
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        }:
            raise CommandError("Reasoning must be low, medium, high, xhigh or max.")
        for name, value, maximum in (
            ("Timesteps", self.timesteps, 2147483647),
            ("MaxTimesteps", self.max_timesteps, 2147483647),
            ("MaxInquiries", self.max_inquiries, 2147483647),
            ("StopTimeoutSeconds", self.stop_timeout_seconds, 3600),
        ):
            if value is not None and not 1 <= value <= maximum:
                raise CommandError(f"{name} must be between 1 and {maximum}.")
        arguments: list[str] = []
        if self.model:
            arguments += ["-Model", self.model]
        if self.provider:
            arguments += ["-Provider", self.provider]
        if self.reasoning:
            arguments += ["-Reasoning", self.reasoning]
        if self.timesteps is not None:
            arguments += ["-Timesteps", str(self.timesteps)]
        if self.max_timesteps is not None:
            arguments += ["-MaxTimesteps", str(self.max_timesteps)]
        if self.max_inquiries is not None:
            arguments += ["-MaxInquiries", str(self.max_inquiries)]
        if self.stop_timeout_seconds is not None:
            arguments += ["-StopTimeoutSeconds", str(self.stop_timeout_seconds)]
        return arguments


@dataclass(frozen=True)
class ResetConfig:
    """What is destroyed before a run; see ``docs/reset-research.md``."""

    mode: str = "Fresh"
    clean: bool = True
    recipe_ref: str | None = DEFAULT_RECIPE_REF
    baseline_ref: str | None = None

    def arguments(self) -> list[str]:
        if self.mode not in {"Fresh", "Baseline"}:
            raise CommandError("Reset mode must be Fresh or Baseline.")
        if self.mode == "Fresh" and self.baseline_ref:
            raise CommandError("Fresh reset does not accept a baseline ref.")
        arguments = ["-Mode", self.mode]
        if self.mode == "Baseline":
            if not self.baseline_ref:
                raise ControllerError("Baseline reset requires a baseline ref.")
            arguments += ["-BaselineRef", self.baseline_ref]
        elif self.recipe_ref:
            arguments += ["-RecipeRef", self.recipe_ref]
        if self.clean:
            arguments.append("-Clean")
        arguments.append("-Force")
        return arguments


@dataclass
class StepRecord:
    action: str
    target: str
    status: str
    detail: str = ""


@dataclass
class BatchOutcome:
    """One submitted command's step records. Batches are not transactions:
    earlier successes are never rolled back, and a failed step stops every
    step that has not run yet."""

    action: str
    steps: list[StepRecord] = field(default_factory=list)

    def record(
        self, action: str, target: str, status: str, detail: str = ""
    ) -> StepRecord:
        record = StepRecord(action=action, target=target, status=status, detail=detail)
        self.steps.append(record)
        return record

    @property
    def ok(self) -> bool:
        return all(step.status != FAILED for step in self.steps)

    @property
    def ran(self) -> bool:
        return bool(self.steps)

    def summary(self) -> str:
        if not self.steps:
            return f"{self.action}: nothing to do"
        return "; ".join(
            f"{step.action} {step.target}: {step.status}" for step in self.steps
        )


def parse_command(text: str) -> tuple[str, list[int]]:
    """Parse one command line into ``(verb, slots)``.

    A bare number selects that campaign; ``1-3`` selects an inclusive range.
    ``campaign-k`` tokens also select explicit folders. Campaign actions without a target are allowed only
    inside a campaign tab, where the caller supplies that campaign.
    """
    tokens = text.strip().split()
    if not tokens:
        raise CommandError("Empty command.")
    verb = tokens[0].lower()
    if verb not in {"run", "start", "reset", "stop", "help", "models", "diagnostics"}:
        raise CommandError(f"Unknown command: {tokens[0]!r}")
    if len(tokens) == 1:
        return verb, []
    selection = tokens[1:]
    if selection == ["all"]:
        if verb != "stop":
            raise CommandError(
                "Use campaign numbers, ranges or folder names; all is stop-only."
            )
        return verb, list(range(1, MAX_SLOTS + 1))
    slots: list[int] = []
    for token in selection:
        lowered = token.lower()
        if lowered.startswith("campaign-"):
            identity = lowered[len("campaign-") :]
            if identity not in {str(slot) for slot in range(1, MAX_SLOTS + 1)}:
                raise CommandError(f"Invalid campaign folder: {token!r}")
            selected = [int(identity)]
        else:
            match = re.fullmatch(r"([1-5])(?:-([1-5]))?", lowered)
            if match is None:
                raise CommandError(
                    f"Invalid target {token!r}; use a campaign number 1–5, a range such as 1-3, or a folder name."
                )
            first = int(match[1])
            last = int(match[2] or match[1])
            if first > last:
                raise CommandError(f"Invalid descending range: {token!r}")
            selected = range(first, last + 1)
        for slot in selected:
            if slot in slots:
                raise CommandError(f"Duplicate target: campaign-{slot}")
            slots.append(slot)
    return verb, sorted(slots)


class WorkspaceLayout:
    """Resolves the five standard campaign folders beside the harness."""

    def __init__(
        self, harness_root: Path, campaigns_root_path: Path | None = None
    ) -> None:
        self.harness_root = Path(harness_root)
        self.campaigns_root = Path(campaigns_root_path or campaigns_root(harness_root))

    @classmethod
    def discover(cls, harness_root: Path) -> WorkspaceLayout:
        return cls(harness_root)

    def folder(self, slot: int) -> Path:
        if not 1 <= slot <= MAX_SLOTS:
            raise CommandError(f"Campaign slot must be between 1 and {MAX_SLOTS}.")
        return self.campaigns_root / f"campaign-{slot}"

    def label(self, slot: int) -> str:
        return f"campaign-{slot}"

    def slot_for(self, label: str) -> int:
        token = label.lower()
        if not token.startswith("campaign-") or not token[len("campaign-") :].isdigit():
            raise CommandError(f"Invalid campaign label: {label}")
        slot = int(token[len("campaign-") :])
        if not 1 <= slot <= MAX_SLOTS:
            raise CommandError(f"Campaign slot must be between 1 and {MAX_SLOTS}.")
        return slot

    def is_installed(self, slot: int) -> bool:
        return (self.folder(slot) / ".git").exists()

    def installed(self) -> list[str]:
        return [
            self.label(slot)
            for slot in range(1, MAX_SLOTS + 1)
            if self.is_installed(slot)
        ]


@dataclass
class CampaignFolderState:
    """Mutable controller state for one installed campaign repository."""

    label: str
    slot: int
    folder: Path
    stage: str = "idle"  # idle|resetting|launching|running|stopping|stopped|failed
    detail: str = ""
    child: object | None = None
    stop_requested: bool = False
    campaign_id: str | None = None
    exit_code: int | None = None
    stop_timeout: float = DEFAULT_STOP_TIMEOUT
    stop_started: float | None = None
    control_directory: Path | None = None
    cleanup_lock: object = field(default_factory=threading.RLock, repr=False)

    @property
    def busy(self) -> bool:
        return self.stage in {"resetting", "launching", "running", "stopping"}

    @property
    def owned(self) -> bool:
        return self.child is not None


class ProcessMachinery(Protocol):
    """The Windows boundary the controller needs; injected for tests."""

    def start(self, folder: Path, arguments: list[str]) -> object:
        """Create, contain, and run one launcher invocation."""
        ...

    def poll(self, child: object) -> bool: ...

    def exit_code(self, child: object) -> int | None: ...

    def wait(self, child: object, seconds: float) -> int | None: ...

    def request_stop(self, child: object) -> bool: ...

    def force_stop(self, child: object, timeout: float | None = None) -> None: ...

    def finish(self, child: object) -> None: ...


class ResetError(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class LauncherError(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)


def _environment_for_launch() -> dict[str, str]:
    """Child environment: presentation overrides must not redirect the
    campaign's own observation feeds."""
    env = dict(os.environ)
    env.pop("TUI_OBSERVATIONS", None)
    env.pop("TUI_TYPED_EVENTS", None)
    env.pop("ROBOT_LEARNING_CAMPAIGN_ROOT", None)
    return env


class HarnessPreflight:
    """Runs the launcher's own cheap refusals before expensive steps."""

    def __init__(
        self,
        harness_root: Path,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self._harness_root = harness_root
        self._runner = runner or _run_git

    def status(self) -> StepRecord:
        try:
            result = self._runner(
                [
                    "git",
                    "-C",
                    str(self._harness_root),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ]
            )
        except OSError as error:
            return StepRecord("preflight", "harness", FAILED, str(error))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "git status failed"
            return StepRecord("preflight", "harness", FAILED, detail)
        if result.stdout.strip():
            names = result.stdout.strip().splitlines()
            return StepRecord(
                "preflight",
                "harness",
                FAILED,
                "harness worktree has uncommitted changes: " + ", ".join(names[:6]),
            )
        return StepRecord("preflight", "harness", SUCCESS)

    def check(self) -> None:
        record = self.status()
        if record.status == FAILED:
            raise ControllerError(record.detail)


def _run_git(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments, capture_output=True, text=True, shell=False, check=False
    )


class CampaignController:
    """Orchestrates initialize/reset/launch/stop over standard folders."""

    def __init__(
        self,
        layout: WorkspaceLayout,
        machinery: ProcessMachinery,
        *,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
        control_directory_factory: Callable[[], Path] | None = None,
        campaign_id_reader: Callable[[Path], str | None] | None = None,
    ) -> None:
        self._layout = layout
        self._machinery = machinery
        self._runner = runner or getattr(machinery, "run", _run_git)
        self._control_directory_factory = (
            control_directory_factory or _default_control_directory
        )
        self._campaign_id_reader = campaign_id_reader or _read_campaign_id
        self._preflight = HarnessPreflight(layout.harness_root, runner)
        self._folders: dict[str, CampaignFolderState] = {}
        self._shutdown: bool = False
        self._launch_lock = threading.Lock()
        self._outcomes: list[BatchOutcome] = []

    # -- Application view --------------------------------------------------
    def labels(self) -> list[str]:
        return self._layout.installed()

    def folder_states(self) -> list[CampaignFolderState]:
        return [
            self._folders[label]
            for label in self._layout.installed()
            if label in self._folders
        ]

    def state(self, label: str) -> CampaignFolderState:
        slot = self._layout.slot_for(label)
        folder = self._folders.get(label)
        if folder is None:
            folder = CampaignFolderState(
                label=label, slot=slot, folder=self._layout.folder(slot)
            )
            self._folders[label] = folder
        return folder

    def outcomes(self) -> list[BatchOutcome]:
        return list(self._outcomes)

    @property
    def shutting_down(self) -> bool:
        return self._shutdown

    # -- Helpers -----------------------------------------------------------
    def _targets(
        self, slots: list[int], *, allow_missing: bool = False
    ) -> list[CampaignFolderState]:
        """Resolve shared (registered) state machines for the selection.

        States are reused across commands so the controller never forgets a
        campaign is running, failed, or stopped.
        """
        states: list[CampaignFolderState] = []
        for slot in slots:
            installed = self._layout.is_installed(slot)
            if not installed and not allow_missing:
                raise CampaignFolderError(
                    f"campaign-{slot} is not initialized. `run` can create it from the recipe."
                )
            state = self.state(self._layout.label(slot))
            if not installed and state.stage == "idle":
                state.stage = "pending"
            states.append(state)
        return states

    def _refuse_busy(self, target: CampaignFolderState, action: str) -> None:
        if self._shutdown:
            raise ControllerError("The console is shutting down; no new actions.")
        if target.busy or target.owned:
            raise ControllerError(
                f"{target.label} is {target.stage}; {action} refused."
            )

    def _record(
        self,
        outcome: BatchOutcome,
        action: str,
        target: str,
        status: str,
        detail: str = "",
    ) -> StepRecord:
        record = outcome.record(action, target, status, detail)
        return record

    # -- Command surface ---------------------------------------------------
    def execute(
        self,
        verb: str,
        slots: list[int],
        *,
        settings: LaunchSettings,
        reset: ResetConfig | None = None,
        external_target: str | None = None,
    ) -> BatchOutcome:
        """Run one parsed command synchronously. A campaign tab supplies
        ``external_target`` for its untargeted commands."""
        if external_target is not None:
            slot = self._layout.slot_for(external_target)
            slots = [slot]
        if not slots:
            raise CommandError(
                f"{verb} requires a campaign number, range or folder name."
            )
        if len(set(slots)) != len(slots):
            raise CommandError("Duplicate campaign targets.")
        if verb not in {"start", "stop", "reset", "run"}:
            raise CommandError(f"Unknown command: {verb!r}")
        settings.launcher_arguments()
        reset = reset or ResetConfig()
        if verb in {"run", "reset"}:
            reset.arguments()
        outcome = BatchOutcome(action=verb)
        self._outcomes.append(outcome)
        targets = self._targets(slots, allow_missing=verb in {"run", "stop"})
        if verb != "stop":
            # Stopping a busy campaign is the point of `stop`; every other
            # action refuses to touch a busy target.
            for target in targets:
                self._refuse_busy(target, verb)
        if verb == "stop":
            for target in targets:
                self._stop_one(outcome, target)
            return outcome
        check_runtime = getattr(self._machinery, "preflight", None)
        if check_runtime is not None:
            try:
                check_runtime()
            except (OSError, RuntimeError) as error:
                for target in targets:
                    target.stage = "failed"
                    target.detail = str(error)
                    outcome.record("preflight", target.label, FAILED, str(error))
                return outcome
        if verb in {"start", "run"}:
            try:
                self._preflight.check()
            except ControllerError as error:
                for target in targets:
                    target.stage = "failed"
                    target.detail = str(error)
                    outcome.record("preflight", target.label, FAILED, str(error))
                return outcome
        if verb == "run":
            for target in targets:
                if not outcome.ok or self._shutdown:
                    outcome.record(
                        "initialize",
                        target.label,
                        SKIPPED,
                        "blocked by an earlier failure or shutdown",
                    )
                    continue
                if not self._layout.is_installed(target.slot):
                    self._initialize_one(outcome, target, reset)
                else:
                    outcome.record(
                        "initialize",
                        target.label,
                        SKIPPED,
                        "campaign repository already exists",
                    )
        if verb in {"reset", "run"}:
            for target in targets:
                if not outcome.ok or self._shutdown:
                    outcome.record(
                        "reset",
                        target.label,
                        SKIPPED,
                        "blocked by a failed earlier step",
                    )
                    continue
                self._reset_one(outcome, target, reset)
        if verb in {"run", "start"}:
            preparation_failed = not outcome.ok
            for target in targets:
                if preparation_failed:
                    outcome.record(
                        "launch",
                        target.label,
                        SKIPPED,
                        "blocked by a failed earlier step",
                    )
                    continue
                with self._launch_lock:
                    self._launch_one(outcome, target, settings)
        return outcome

    # -- Steps -------------------------------------------------------------
    def _initialize_one(
        self, outcome: BatchOutcome, target: CampaignFolderState, reset: ResetConfig
    ) -> None:
        """Create a missing standard folder with the existing initializer."""
        if target.busy or self._shutdown:
            self._record(
                outcome, "initialize", target.label, SKIPPED, "campaign is not idle"
            )
            return
        source = self._first_installed()
        if source is None:
            target.stage = "failed"
            target.detail = "no existing campaign repository to copy the recipe from"
            self._record(
                outcome,
                "initialize",
                target.label,
                FAILED,
                "no existing campaign repository to copy the recipe from",
            )
            return
        completed = self._runner(
            [
                "uv",
                "run",
                "--project",
                str(self._layout.harness_root),
                "python",
                "-m",
                "tools.initialize_campaign",
                "--campaign-root",
                str(target.folder),
                "--source-repository",
                str(self._layout.folder(self._layout.slot_for(source))),
                "--recipe-ref",
                reset.baseline_ref
                if reset.mode == "Baseline"
                else (reset.recipe_ref or DEFAULT_RECIPE_REF),
            ]
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            target.stage = "failed"
            target.detail = (
                detail[-1200:]
                or f"initialization failed with exit code {completed.returncode}"
            )
            self._record(outcome, "initialize", target.label, FAILED, target.detail)
            return
        target.stage = "idle"
        self._record(outcome, "initialize", target.label, SUCCESS)

    def _first_installed(self) -> str | None:
        installed = self._layout.installed()
        return installed[0] if installed else None

    def _reset_one(
        self, outcome: BatchOutcome, target: CampaignFolderState, reset: ResetConfig
    ) -> None:
        if self._shutdown:
            self._record(
                outcome, "reset", target.label, SKIPPED, "the console is shutting down"
            )
            return
        if target.busy:
            self._record(
                outcome, "reset", target.label, SKIPPED, f"campaign is {target.stage}"
            )
            return
        target.stage = "resetting"
        target.detail = ""
        try:
            completed = self._runner(
                [
                    "pwsh",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(self._layout.harness_root / "reset_research.ps1"),
                    "-CampaignRoot",
                    str(target.folder),
                    *reset.arguments(),
                ]
            )
        except (OSError, RuntimeError) as error:
            target.stage = "failed"
            target.detail = str(error)
            self._record(outcome, "reset", target.label, FAILED, str(error))
            return
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            tail = detail[-1200:]
            target.stage = "failed"
            target.detail = (
                tail or f"reset failed with exit code {completed.returncode}"
            )
            self._record(outcome, "reset", target.label, FAILED, target.detail)
            return
        target.stage = "stopped"
        target.detail = ""
        target.campaign_id = self._campaign_id_reader(target.folder)
        self._record(outcome, "reset", target.label, SUCCESS)

    def _launch_one(
        self,
        outcome: BatchOutcome,
        target: CampaignFolderState,
        settings: LaunchSettings,
    ) -> None:
        if self._shutdown:
            self._record(
                outcome, "launch", target.label, SKIPPED, "the console is shutting down"
            )
            return
        if target.busy:
            self._record(
                outcome, "launch", target.label, SKIPPED, f"campaign is {target.stage}"
            )
            return
        state_file = target.folder / "runner/state/research_state.json"
        if state_file.is_file():
            try:
                durable = json.loads(state_file.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as error:
                target.stage = "failed"
                target.detail = f"Cannot read campaign state: {error}"
                self._record(outcome, "launch", target.label, FAILED, target.detail)
                return
            terminal = durable.get("terminal_state") or {}
            if terminal.get("status") in TERMINAL_OUTCOMES:
                target.stage = "completed"
                target.detail = terminal["status"]
                self._record(
                    outcome,
                    "launch",
                    target.label,
                    SKIPPED,
                    f"Recorded outcome: {target.detail}; use reset or run for a new campaign.",
                )
                return
        control_directory = self._control_directory_factory()
        target.control_directory = control_directory
        target.stop_timeout = settings.stop_timeout_seconds or DEFAULT_STOP_TIMEOUT
        target.stop_started = None
        arguments = [
            "-CampaignRoot",
            str(target.folder),
            *settings.launcher_arguments(),
            "-StopRequestPath",
            str(control_directory / "stop.request"),
        ]
        target.stage = "launching"
        target.detail = ""
        try:
            child = self._machinery.start(target.folder, arguments)
        except Exception as error:  # noqa: BLE001 - reported verbatim to the operator
            target.stage = "failed"
            target.detail = str(error)
            target.child = None
            self._record(outcome, "launch", target.label, FAILED, str(error))
            return
        target.child = child
        target.stop_requested = False
        target.stage = "running"
        target.campaign_id = self._campaign_id_reader(target.folder)
        self._record(outcome, "launch", target.label, SUCCESS)

    def _stop_one(self, outcome: BatchOutcome, target: CampaignFolderState) -> None:
        if target.child is None or target.stage not in {"running", "launching"}:
            self._record(
                outcome, "stop", target.label, SKIPPED, f"campaign is {target.stage}"
            )
            return
        created = self._machinery.request_stop(target.child)
        target.stop_requested = True
        target.stop_started = time.monotonic()
        target.stage = "stopping"
        self._record(
            outcome,
            "stop",
            target.label,
            SUCCESS if created else SKIPPED,
            "" if created else "a stop request already exists",
        )

    # -- Shutdown ----------------------------------------------------------
    def latch_shutdown(self) -> None:
        """Stop accepting new actions; send stop requests everywhere."""
        with self._launch_lock:
            self._shutdown = True
        for label in self._layout.installed():
            target = self._folders.get(label)
            if target is None or not target.busy:
                continue
            if target.child is not None and target.stage == "running":
                self._stop_one(BatchOutcome("shutdown"), target)

    def reap(self, label: str) -> CampaignFolderState:
        """Poll one child; classify its exit and end its state machine."""
        with self.state(label).cleanup_lock:
            return self._reap(label)

    def _reap(self, label: str) -> CampaignFolderState:
        target = self._folders[label]
        if target.child is None:
            return target
        if not self._machinery.poll(target.child):
            if (
                target.stop_started is not None
                and time.monotonic() >= target.stop_started + target.stop_timeout + 5
            ):
                return self.settle(label, 0)
            return target
        code = self._machinery.exit_code(target.child)
        if code == 124:
            self._machinery.force_stop(target.child)
            target.stage = "failed"
            target.detail = (
                "cooperative stop timed out; the process tree was terminated"
            )
        elif code == 130:
            target.stage = "stopped"
            target.detail = "stopped by the cooperative stop request"
        elif code == 0:
            target.stage = "stopped"
            target.detail = (
                "launcher returned normally; inspect durable state before resuming"
            )
        else:
            target.stage = "failed"
            target.detail = f"launcher exited with code {code}"
        self._machinery.finish(target.child)
        target.exit_code = code
        target.child = None
        return target

    def reap_all(self) -> None:
        for label in self._layout.installed():
            if label in self._folders:
                self.reap(label)

    def settle(self, label: str, timeout: float) -> CampaignFolderState:
        """Wait for one stopping launcher; escalate if it misses the bound."""
        with self.state(label).cleanup_lock:
            return self._settle(label, timeout)

    def _settle(self, label: str, timeout: float) -> CampaignFolderState:
        target = self._folders[label]
        if target.child is None:
            return target
        code = self._machinery.wait(target.child, timeout)
        if code is None:
            self._machinery.force_stop(target.child)
            self._machinery.finish(target.child)
            target.stage = "failed"
            target.detail = (
                "cooperative stop timed out; the process tree was terminated"
            )
            target.child = None
            return target
        return self.reap(label)

    def force_all(self, timeout: float | None = None) -> None:
        for label in self._layout.installed():
            target = self._folders.get(label)
            if target is not None:
                with target.cleanup_lock:
                    if target.child is not None:
                        self._machinery.force_stop(target.child, timeout)
                        self._machinery.finish(target.child)
                        target.stage = "failed"
                        target.detail = "forced termination (console shutdown)"
                        target.child = None

    def stop_helpers(self) -> None:
        stop = getattr(self._machinery, "stop_helpers", None)
        if stop is not None:
            stop()


def _default_control_directory() -> Path:
    from tui.process import control_root, new_control_directory

    return new_control_directory(control_root())


def _read_campaign_id(folder: Path) -> str | None:
    """Read the current campaign identity without touching state."""
    state = folder / "runner" / "state" / "research_state.json"
    try:
        import json

        payload = json.loads(state.read_text(encoding="utf-8-sig"))
        identifier = payload.get("campaign", {}).get("id")
        return str(identifier) if identifier else None
    except (OSError, ValueError):
        return None


def campaign_short_id(campaign_id: str | None) -> str:
    return (campaign_id or "")[:8] or "unavailable"


def run_id() -> str:
    return uuid.uuid4().hex


def monotonic() -> float:
    return time.monotonic()


__all__ = [
    "DEFAULT_RECIPE_REF",
    "DEFAULT_STOP_TIMEOUT",
    "TERMINAL_OUTCOMES",
    "BatchOutcome",
    "CampaignController",
    "CampaignFolderError",
    "CampaignFolderState",
    "CommandError",
    "ControllerError",
    "HarnessPreflight",
    "LaunchSettings",
    "LauncherError",
    "ProcessMachinery",
    "ResetConfig",
    "ResetError",
    "StepRecord",
    "WorkspaceLayout",
    "campaign_short_id",
    "campaigns_root",
    "default_campaigns_root",
    "monotonic",
    "parse_command",
    "run_id",
]
