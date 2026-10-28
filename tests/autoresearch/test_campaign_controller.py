"""Controller and process-boundary checks for the multi-campaign console.

Orchestration is validated with fake machinery and a discriminated fake
executor; the Windows containment boundary gets a small real-child smoke
test. No campaign is launched, reset, initialized, trained or assessed, and
no scientific code or state changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tui import controller as control
from tui.process import acquire_instance_lock


def _layout(tmp_path: Path) -> control.WorkspaceLayout:
    root = tmp_path / "robot-learning-campaigns"
    root.mkdir()
    for slot in (1, 2, 3):
        campaign = root / f"campaign-{slot}"
        campaign.mkdir()
        (campaign / ".git").mkdir()
    harness = tmp_path / "harness"
    harness.mkdir()
    return control.WorkspaceLayout(harness, root)


class FakeChild:
    def __init__(self, exit_code: int = 0, pending_stop: bool = False) -> None:
        self.exit_code = exit_code
        self.pending_stop = pending_stop
        self.forced = False
        self.stop_requests = 0
        self.wait_calls: list[float] = []

    def poll(self) -> bool:
        return self.pending_stop is False or self.forced

    def exit_code_value(self) -> int:
        if self.forced:
            return 0x2DF  # TerminatedJobObject sentinel used in tests
        return self.exit_code

    def wait(self, seconds: float) -> int | None:
        self.wait_calls.append(seconds)
        return None


class FakeMachinery:
    """Records controller calls without touching processes."""

    def __init__(self) -> None:
        self.children: dict[Path, FakeChild] = {}
        self.started: list[tuple[Path, list[str]]] = []
        self.forced: list[FakeChild] = []
        self.force_timeout: float | None = None
        self.next_exit_code = 0
        self.wait_exit_code: int | None = 130  # cooperative stop succeeds by default
        self.fail_start: str | None = None
        self.reason = ""

    # ProcessMachinery protocol -------------------------------------------
    def start(
        self, folder: Path, arguments: list[str], control_directory: Path
    ) -> FakeChild:
        if self.fail_start:
            raise RuntimeError(self.fail_start)
        child = FakeChild(exit_code=self.next_exit_code)
        child.pending_stop = True  # appears running to the poller
        self.children[folder] = child
        self.started.append((folder, list(arguments)))
        return child

    def poll(self, child: FakeChild) -> bool:
        return not child.pending_stop or child.forced

    def exit_code(self, child: FakeChild) -> int | None:
        if child.forced:
            return 0x2DF  # TerminatedJobObject sentinel used in tests
        return self.next_exit_code

    def wait(self, child: FakeChild, seconds: float) -> int | None:
        child.wait_calls.append(seconds)
        if self.wait_exit_code is not None:
            self.next_exit_code = self.wait_exit_code
            child.pending_stop = False
        return self.wait_exit_code

    def request_stop(self, child: FakeChild) -> bool:
        child.stop_requests += 1
        if child.stop_requests == 1:
            child.pending_stop = False
            return True
        return False

    def force_stop(self, child: FakeChild, timeout: float | None = None) -> None:
        child.forced = True
        self.forced.append(child)
        self.force_timeout = timeout

    def finish(self, child: FakeChild) -> None:
        pass

    def failure_reason(self, child: FakeChild) -> str:
        return self.reason


def _machine(tmp_path: Path) -> FakeMachinery:
    return FakeMachinery()


def _controller(
    tmp_path: Path,
    machinery: FakeMachinery | None = None,
    harness_dirty: list[str] | None = None,
):
    layout = _layout(tmp_path)
    machinery = machinery or FakeMachinery()

    class Runner:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def __call__(self, arguments: list[str]):
            self.calls.append(list(arguments))
            if "tools.initialize_campaign" in arguments:
                destination = Path(arguments[arguments.index("--campaign-root") + 1])
                (destination / ".git").mkdir(parents=True)
            dirty = "\n".join(harness_dirty or [])
            if arguments[:2] == ["git", "-C"]:
                return subprocess.CompletedProcess(
                    arguments, 0, stdout=dirty, stderr=""
                )
            return subprocess.CompletedProcess(
                arguments, 0, stdout="reset ok", stderr=""
            )

    runner = Runner()
    controller = control.CampaignController(layout, machinery, runner=runner)
    controller._preflight = control.HarnessPreflight(
        layout.harness_root,
        lambda arguments: subprocess.CompletedProcess(
            arguments,
            0,
            stdout="\n".join(harness_dirty or []),
            stderr="",
        ),
    )
    return controller, machinery, layout, runner


def test_parse_command_numbers_ranges_and_targets():
    assert control.parse_command("run 3") == ("run", [3])
    assert control.parse_command("stop 1") == ("stop", [1])
    assert control.parse_command("reset campaign-1 campaign-3") == ("reset", [1, 3])
    assert control.parse_command("start campaign-2 campaign-1") == ("start", [1, 2])


@pytest.mark.parametrize("verb", ["start", "run", "reset", "stop"])
def test_numeric_targets_always_mean_identities_and_ranges_are_inclusive(verb):
    assert control.parse_command(f"{verb} 2") == (verb, [2])
    assert control.parse_command(f"{verb} 1-2") == (verb, [1, 2])
    assert control.parse_command(f"{verb} 2-3") == (verb, [2, 3])
    assert control.parse_command(f"{verb} 1-5") == (verb, [1, 2, 3, 4, 5])
    assert control.parse_command(f"{verb} 1 3") == (verb, [1, 3])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "deploy 2",
        "run 0",
        "run 6",
        "run campaign-0",
        "run campaign-2 campaign-2",
        "reset foo",
        "start 3-2",
        "run 0-2",
        "reset 1-6",
        "stop 1-2-3",
        "start 1-3 2",
        "start 2 campaign-2",
    ],
)
def test_parse_command_rejects_invalid(text):
    with pytest.raises(control.CommandError):
        control.parse_command(text)


def test_settings_preserve_omitted_arguments():
    assert control.LaunchSettings().launcher_arguments() == []
    settings = control.LaunchSettings(
        model="gpt-6-luna",
        provider=None,
        reasoning="high",
        timesteps=None,
        max_timesteps=360000,
        max_inquiries=15,
        stop_timeout_seconds=180,
    )
    assert "--provider" not in settings.launcher_arguments()
    assert settings.launcher_arguments() == [
        "--model",
        "gpt-6-luna",
        "--reasoning",
        "high",
        "--max-timesteps",
        "360000",
        "--max-inquiries",
        "15",
        "--stop-timeout-seconds",
        "180",
    ]
    assert control.ResetConfig().arguments() == [
        "--mode",
        "fresh",
        "--recipe-ref",
        control.DEFAULT_RECIPE_REF,
        "--clean",
        "--force",
    ]
    with pytest.raises(control.ControllerError):
        control.ResetConfig(mode="Baseline").arguments()


def test_run_initializes_missing_folder_then_reset_and_launch(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    # Slot 4 does not exist: the run command creates it from the recipe
    # with the existing initializer and continues into reset and launch.
    outcome = controller.execute("run", [4], settings=control.LaunchSettings())
    statuses = [(step.action, step.status) for step in outcome.steps]
    assert statuses[0] == ("initialize", control.SUCCESS)
    assert ("reset", control.SUCCESS) in statuses
    assert ("launch", control.SUCCESS) in statuses
    assert outcome.ok
    started_folder, _started_arguments = machinery.started[-1]
    assert started_folder == layout.folder(4)


def test_run_without_any_repository_reports_setup_error(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    controller._layout = control.WorkspaceLayout(
        layout.harness_root, layout.campaigns_root / "empty"
    )
    outcome = controller.execute("run", [1], settings=control.LaunchSettings())
    assert outcome.steps[0].action == "initialize"
    assert all(s.status == control.SKIPPED for s in outcome.steps[1:])
    assert outcome.steps[0].status == control.FAILED
    assert "no existing campaign repository" in outcome.steps[0].detail
    assert machinery.started == []


def test_run_executes_reset_then_launch(tmp_path):
    controller, machinery, layout, runner = _controller(tmp_path)
    outcome = controller.execute("run", [2], settings=control.LaunchSettings())
    statuses = [(step.action, step.status) for step in outcome.steps]
    assert ("initialize", control.SKIPPED) in statuses
    assert ("reset", control.SUCCESS) in statuses
    assert ("launch", control.SUCCESS) in statuses
    reset_arguments = [
        call
        for call in runner.calls
        if call[:2] != ["git", "-C"] and "runner.launcher.reset" in call
    ]
    assert len(reset_arguments) == 1
    assert "--clean" in reset_arguments[0]
    assert control.DEFAULT_RECIPE_REF in reset_arguments[0]
    started_folder, started_arguments = machinery.started[-1]
    assert started_folder == layout.folder(2)
    assert started_arguments[:2] == ["--campaign-root", str(layout.folder(2))]
    assert outcome.ok


def test_run_resets_stopped_campaign_before_launching_again(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller.execute("run", [1], settings=control.LaunchSettings())
    controller.execute("stop", [1], settings=control.LaunchSettings())
    controller.settle("campaign-1", 1)
    outcome = controller.execute("run", [1], settings=control.LaunchSettings())
    assert [(s.action, s.status) for s in outcome.steps] == [
        ("initialize", control.SKIPPED),
        ("reset", control.SUCCESS),
        ("launch", control.SUCCESS),
    ]
    assert len(machinery.started) == 2


def test_batch_reset_failure_blocks_only_that_campaign(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    original = controller._runner

    def run(arguments):
        if str(layout.folder(2)) in arguments and "--mode" in arguments:
            return subprocess.CompletedProcess(
                arguments, 1, stdout="", stderr="reset failed"
            )
        return original(arguments)

    controller._runner = run
    outcome = controller.execute("run", [1, 2, 3], settings=control.LaunchSettings())
    assert [(s.target, s.status) for s in outcome.steps if s.action == "reset"] == [
        ("campaign-1", control.SUCCESS),
        ("campaign-2", control.FAILED),
        ("campaign-3", control.SUCCESS),
    ]
    assert [(s.target, s.status) for s in outcome.steps if s.action == "launch"] == [
        ("campaign-1", control.SUCCESS),
        ("campaign-2", control.SKIPPED),
        ("campaign-3", control.SUCCESS),
    ]
    assert controller.state("campaign-2").stage == "failed"
    assert [folder for folder, _ in machinery.started] == [
        layout.folder(1),
        layout.folder(3),
    ]


@pytest.mark.parametrize(
    "status,launch",
    [
        ("official_assessment_requested", True),
        ("official_assessment_passed", False),
        ("official_assessment_failed", False),
        ("no_credible_route", False),
    ],
)
def test_start_preserves_terminal_outcomes_but_resumes_pending_assessment(
    tmp_path, status, launch
):
    controller, machinery, layout, _ = _controller(tmp_path)
    path = layout.folder(1) / "runner/state/research_state.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"terminal_state": {"status": status}}), encoding="utf-8"
    )
    outcome = controller.execute("start", [1], settings=control.LaunchSettings())
    assert bool(machinery.started) is launch
    assert outcome.ok


@pytest.mark.parametrize(
    "status",
    [
        "official_assessment_passed",
        "official_assessment_failed",
        "no_credible_route",
        "official_assessment_requested",
    ],
)
def test_normal_exit_classifies_recorded_completion_immediately(tmp_path, status):
    controller, machinery, layout, _ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    state_file = layout.folder(1) / "runner/state/research_state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({"terminal_state": {"status": status}}), encoding="utf-8"
    )
    machinery.children[layout.folder(1)].pending_stop = False
    state = controller.reap("campaign-1")
    assert state.stage == (
        "stopped" if status == "official_assessment_requested" else "completed"
    )
    assert state.child is None


@pytest.mark.parametrize("git_file", [False, True])
def test_unfinished_reset_record_blocks_start_in_a_new_controller(tmp_path, git_file):
    _, machinery, layout, _ = _controller(tmp_path)
    if git_file:
        admin = tmp_path / "git-admin"
        admin.mkdir()
        git_path = layout.folder(1) / ".git"
        git_path.rmdir()
        git_path.write_text(f"gitdir: {admin.as_posix()}\n", encoding="utf-8")
    marker = control.reset_marker_path(layout.folder(1))
    marker.write_text("{}", encoding="utf-8")

    fresh = control.CampaignController(
        layout,
        machinery,
        runner=lambda args: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )
    assert fresh.state("campaign-1").stage == "failed"
    refused = fresh.execute("start", [1], settings=control.LaunchSettings())
    assert not refused.ok and not machinery.started
    marker.unlink()
    assert fresh.execute("start", [1], settings=control.LaunchSettings()).ok
    assert len(machinery.started) == 1


def test_refused_reset_without_a_record_does_not_block_start(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller._runner = lambda args: subprocess.CompletedProcess(
        args, 1, stdout="", stderr="another loop or reset is already running"
    )
    assert not controller.execute("reset", [1], settings=control.LaunchSettings()).ok
    assert controller.execute("start", [1], settings=control.LaunchSettings()).ok
    assert len(machinery.started) == 1


def test_one_failed_forced_cleanup_does_not_skip_other_launchers(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    controller.execute("start", [1, 2], settings=control.LaunchSettings())
    first = machinery.children[layout.folder(1)]
    original = machinery.force_stop

    def force(child, timeout=None):
        if child is first:
            raise TimeoutError("stuck first child")
        original(child, timeout)

    machinery.force_stop = force
    with pytest.raises(RuntimeError):
        controller.force_all()
    assert machinery.children[layout.folder(2)].forced
    assert controller.state("campaign-2").child is None


def test_run_reset_failure_does_not_block_other_campaigns(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    # Slot 2 reset fails; slot 3 still resets and launches.
    original = controller._reset_one

    def failing_reset(outcome, target, reset_config):
        if target.slot == 2:
            target.stage = "failed"
            target.detail = "boom"
            outcome.record("reset", target.label, control.FAILED, "boom")
            return
        original(outcome, target, reset_config)

    controller._reset_one = failing_reset
    outcome = controller.execute("run", [2, 3], settings=control.LaunchSettings())
    actions = [step for step in outcome.steps if step.action in {"reset", "launch"}]
    reset_2 = next(
        step
        for step in actions
        if step.target == "campaign-2" and step.action == "reset"
    )
    assert reset_2.status == control.FAILED
    launch_3 = [
        step
        for step in actions
        if step.target == "campaign-3" and step.action == "launch"
    ]
    assert len(launch_3) == 1
    assert launch_3[0].status == control.SUCCESS
    assert len(machinery.started) == 1


def test_reset_refused_while_running(tmp_path):
    controller, _machinery, _layout, _ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    with pytest.raises(control.ControllerError):
        controller.execute("reset", [1], settings=control.LaunchSettings())
    assert controller.state("campaign-1").stage == "running"


def test_duplicate_command_submission_refused(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    with pytest.raises(control.ControllerError):
        controller.execute("start", [1], settings=control.LaunchSettings())
    assert len(machinery.started) == 1


def test_start_2_does_not_retarget_or_interrupt_running_campaign_1(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    first = machinery.children[layout.folder(1)]
    verb, slots = control.parse_command("start 2")
    outcome = controller.execute(verb, slots, settings=control.LaunchSettings())
    assert outcome.ok
    assert [folder for folder, _ in machinery.started] == [
        layout.folder(1),
        layout.folder(2),
    ]
    assert first.stop_requests == 0
    assert not first.forced


def test_stop_sends_request_and_marks_stopping(tmp_path):
    controller, machinery, layout, _ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    child = machinery.children[layout.folder(1)]
    outcome = controller.execute("stop", [1], settings=control.LaunchSettings())
    assert child.stop_requests == 1
    assert controller.state("campaign-1").stage == "stopping"
    assert outcome.ok
    again = controller.execute("stop", [1], settings=control.LaunchSettings())
    assert again.steps[0].status == control.SKIPPED
    assert child.stop_requests == 1  # never a second overwrite


@pytest.mark.parametrize("existing", [False, True])
def test_launcher_stop_request_reports_creation_and_is_sent_once(tmp_path, existing):
    from tui.process import SupervisedLauncher

    request = tmp_path / "stop-request"
    if existing:
        request.write_text("earlier request", encoding="utf-8")
        os.utime(request, (0, 0))
    child = SupervisedLauncher(
        pid=0,
        job=None,
        _process=None,
        _thread=None,
        _log=None,
        stop_request=request,
    )
    assert child.request_stop() is (not existing)
    assert child.stop_requested
    # A request left by an earlier run is refreshed so the launcher honours it.
    assert request.stat().st_mtime > 0
    request.write_text("do not overwrite", encoding="utf-8")
    assert child.request_stop() is False
    assert request.read_text(encoding="utf-8") == "do not overwrite"


def test_reap_classifies_exit_codes(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller.execute("run", [1], settings=control.LaunchSettings())
    state = controller.state("campaign-1")
    machinery.children[state.folder].pending_stop = False

    machinery.next_exit_code = 130
    controller.reap(state.label)
    assert state.stage == "stopped"
    assert "cooperative stop request" in state.detail

    controller.execute("start", [2], settings=control.LaunchSettings())
    second = controller.state("campaign-2")
    machinery.children[second.folder].pending_stop = False
    machinery.next_exit_code = 0
    controller.reap(second.label)
    assert "durable state" in second.detail

    controller.execute("start", [3], settings=control.LaunchSettings())
    third = controller.state("campaign-3")
    machinery.children[third.folder].pending_stop = False
    machinery.next_exit_code = 7
    controller.reap(third.label)
    assert third.stage == "failed"
    assert "code 7" in third.detail
    assert third.detail == "launcher exited with code 7"


def test_a_failed_launcher_reports_why_it_stopped(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    machinery.reason = "Copilot bounded session failed: files changed"
    controller.execute("start", [1], settings=control.LaunchSettings())
    state = controller.state("campaign-1")
    machinery.children[state.folder].pending_stop = False
    machinery.next_exit_code = 1
    controller.reap(state.label)
    assert state.stage == "failed"
    assert state.detail == (
        "launcher exited with code 1: Copilot bounded session failed: files changed"
    )


def test_settle_escalates_to_forced_stop(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    machinery.wait_exit_code = None  # the launcher misses the cooperative deadline
    controller.execute("start", [1], settings=control.LaunchSettings())
    state = controller.state("campaign-1")
    controller.execute("stop", [1], settings=control.LaunchSettings())
    child = machinery.children[state.folder]
    child.wait_calls.append(180.0)
    controller.settle(state.label, timeout=0.1)
    child.forced = True
    state = controller.reap(state.label)
    assert machinery.forced == [child]
    assert state.stage == "failed"


def test_stop_returns_cooperatively_without_forced_termination(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    controller.execute("stop", [1], settings=control.LaunchSettings())
    state = controller.settle("campaign-1", 185)
    assert state.stage == "stopped"
    assert state.exit_code == 130
    assert machinery.forced == []


def test_ordinary_stop_uses_invocation_deadline_plus_five_seconds(
    tmp_path, monkeypatch
):
    controller, machinery, *_ = _controller(tmp_path)
    clock = [100.0]
    monkeypatch.setattr(control.time, "monotonic", lambda: clock[0])
    machinery.wait_exit_code = None
    controller.execute(
        "start", [1], settings=control.LaunchSettings(stop_timeout_seconds=7)
    )
    controller.execute(
        "stop", [1], settings=control.LaunchSettings(stop_timeout_seconds=1)
    )
    child = machinery.started and next(iter(machinery.children.values()))
    child.pending_stop = True
    clock[0] = 111.9
    assert controller.reap("campaign-1").stage == "stopping"
    assert machinery.forced == []
    clock[0] = 112.0
    assert controller.reap("campaign-1").stage == "failed"
    assert machinery.forced == [child]


def test_shutdown_latch_blocks_new_actions_and_stops_all(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    controller.execute("start", [1], settings=control.LaunchSettings())
    controller.execute("start", [2], settings=control.LaunchSettings())
    controller.latch_shutdown()
    assert controller.shutting_down
    with pytest.raises(control.ControllerError):
        controller.execute("run", [3], settings=control.LaunchSettings())
    children = list(machinery.children.values())
    assert all(child.stop_requests == 1 for child in children)
    for label in ("campaign-1", "campaign-2"):
        controller.settle(label, timeout=0.05)
        state = controller.state(label)
        assert state.stage == "stopped"


def test_shutdown_during_reset_never_launches_the_batch(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    calls = []

    def run(arguments):
        calls.append(arguments)
        controller.latch_shutdown()
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    controller._runner = run
    outcome = controller.execute("run", [1, 2], settings=control.LaunchSettings())
    assert len(calls) == 1
    assert machinery.started == []
    assert all(
        s.status == control.SKIPPED for s in outcome.steps if s.action == "launch"
    )


def test_preflight_reports_dirty_harness_and_skips_batch(tmp_path):
    controller, machinery, *_ = _controller(tmp_path, harness_dirty=["M  main.py"])
    outcome = controller.execute("run", [1], settings=control.LaunchSettings())
    assert outcome.steps[0].action == "preflight"
    assert outcome.steps[0].status == control.FAILED
    assert "uncommitted" in outcome.steps[0].detail
    assert machinery.started == []


def test_unavailable_contained_runtime_refuses_before_any_reset(tmp_path):
    controller, machinery, _layout, runner = _controller(tmp_path)

    def missing():
        raise RuntimeError("PowerShell 7 required")

    machinery.preflight = missing
    outcome = controller.execute("run", [1, 2], settings=control.LaunchSettings())
    assert not outcome.ok
    assert all(
        s.action == "preflight" and s.status == control.FAILED for s in outcome.steps
    )
    assert runner.calls == []
    assert machinery.started == []


def test_stop_without_target_requires_selection(tmp_path):
    controller, *_ = _controller(tmp_path)
    with pytest.raises(control.CommandError):
        controller.execute("run", [], settings=control.LaunchSettings())


# -- Windows containment boundary (real child smoke checks) ------------------

requires_windows = pytest.mark.skipif(
    os.name != "nt", reason="Job Objects are Windows-only"
)


@pytest.fixture(params=["installed", "windows-powershell"])
def native_shell(request):
    """A shell that runs dummy scripts: installed PS 7 and unpackaged PS 5.1.

    The scripts only exercise the Windows creation and containment policy.
    """
    import shutil

    if request.param == "installed":
        executable = shutil.which("pwsh")
        if executable is None:
            pytest.skip("PowerShell 7 is not installed")
        return executable
    return str(
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )


def _script(shell: str, script: Path) -> list[str]:
    return [shell, "-NoProfile", "-NonInteractive", "-File", str(script)]


@requires_windows
def test_supervised_launcher_captures_output_and_reports_exit(tmp_path, native_shell):
    from tui.process import LauncherBuilder

    script = tmp_path / "dummy.ps1"
    script.write_text(
        "Write-Output 'child-alive'\n"
        "[Console]::Error.WriteLine('first')\n"
        "[Console]::Error.WriteLine('the reason it stopped')\n"
        "exit 3\n",
        encoding="utf-8",
    )
    builder = LauncherBuilder(tmp_path)
    launcher = builder.start_command(
        _script(native_shell, script), tmp_path / "control"
    )
    assert launcher.pid > 0
    assert launcher.poll() is False
    exit_code = launcher.wait(20.0)
    assert exit_code == 3
    assert launcher.poll() is True
    assert launcher.last_error_line() == "the reason it stopped"
    assert "child-alive" in (tmp_path / "control" / "console.out.log").read_text(
        encoding="utf-8", errors="replace"
    )
    assert launcher.job_process_ids() == []
    launcher.close()


@requires_windows
def test_assignment_failure_does_not_run_the_suspended_child(
    tmp_path, monkeypatch, native_shell
):
    from tui.process import LauncherBuilder, kernel32

    marker = tmp_path / "should-not-run"
    script = tmp_path / "dummy.ps1"
    script.write_text(
        f"Set-Content -LiteralPath '{marker}' -Value 'ran'", encoding="utf-8"
    )
    monkeypatch.setattr(kernel32, "AssignProcessToJobObject", lambda *_: False)
    with pytest.raises(OSError, match="assigning"):
        LauncherBuilder(tmp_path).start_command(
            _script(native_shell, script), tmp_path / "control"
        )
    assert not marker.exists()
    # Cleanup also releases every diagnostic handle on partial startup failure.
    (tmp_path / "control/console.out.log").unlink()
    (tmp_path / "control/console.err.log").unlink()


@requires_windows
def test_packaged_creation_policy_failure_never_runs_the_child(
    tmp_path, monkeypatch, native_shell
):
    from tui.process import LauncherBuilder, kernel32

    marker = tmp_path / "should-not-run"
    script = tmp_path / "dummy.ps1"
    script.write_text(
        f"Set-Content -LiteralPath '{marker}' -Value 'ran'", encoding="utf-8"
    )
    monkeypatch.setattr(kernel32, "UpdateProcThreadAttribute", lambda *_: False)
    with pytest.raises(OSError, match="disabling packaged process-tree breakaway"):
        LauncherBuilder(tmp_path).start_command(
            _script(native_shell, script), tmp_path / "control"
        )
    assert not marker.exists()
    (tmp_path / "control/console.out.log").unlink()
    (tmp_path / "control/console.err.log").unlink()


@requires_windows
def test_uv_python_chain_stops_cooperatively(tmp_path):
    from tui.process import LauncherBuilder, _uv_executable

    harness = Path(__file__).resolve().parents[2]
    pidfile = tmp_path / "worker.pid"
    request = tmp_path / "stop-request"
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import os, sys, time\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "while not Path(sys.argv[2]).exists(): time.sleep(.05)\n"
        "raise SystemExit(130)\n",
        encoding="utf-8",
    )
    child = LauncherBuilder(harness).start_command(
        [
            _uv_executable(),
            "run",
            "--no-sync",
            "--project",
            str(harness),
            "python",
            str(worker),
            str(pidfile),
            str(request),
        ],
        tmp_path / "control",
    )
    child.stop_request = request
    try:
        deadline = time.monotonic() + 20
        while not pidfile.exists() and not child.poll() and time.monotonic() < deadline:
            time.sleep(0.05)
        worker_pid = int(pidfile.read_text(encoding="utf-8"))
        assert {child.pid, worker_pid}.issubset(child.job_process_ids())
        assert child.request_stop()
        assert child.wait(20) == 130
        assert child.job_process_ids() == []
    finally:
        child.close()


@requires_windows
def test_force_stop_terminates_the_whole_contained_tree(tmp_path, native_shell):
    from tui.process import LauncherBuilder

    script = tmp_path / "spawner.ps1"
    pidfile = tmp_path / "child.pid"
    script.write_text(
        "$p = Start-Process ping.exe -ArgumentList '-n','60','127.0.0.1' -PassThru\n"
        f"$p.Id | Set-Content -LiteralPath '{pidfile}'\nStart-Sleep -Seconds 60\n",
        encoding="utf-8",
    )
    builder = LauncherBuilder(tmp_path)
    launcher = builder.start_command(
        _script(native_shell, script), tmp_path / "control"
    )
    try:
        deadline = time.monotonic() + 15
        while (
            not pidfile.exists() or not pidfile.read_text(encoding="utf-8-sig").strip()
        ) and time.monotonic() < deadline:
            time.sleep(0.05)
        descendant = int(pidfile.read_text(encoding="utf-8-sig").strip())
        assert {launcher.pid, descendant}.issubset(launcher.job_process_ids())
        launcher.force_stop(timeout=10.0)
        assert launcher.poll() is True
        assert launcher.job_process_ids() == []
        assert launcher.exit_code != 0
    finally:
        launcher.close()


@requires_windows
def test_kill_on_close_contains_native_descendants_after_owner_crash(
    tmp_path, native_shell
):
    import ctypes
    import sys

    from tui.process import _WAIT_OBJECT_0, kernel32

    script = tmp_path / "spawner.ps1"
    pidfile = tmp_path / "child.pid"
    script.write_text(
        "$p = Start-Process ping.exe -ArgumentList '-n','60','127.0.0.1' -PassThru\n"
        f"$p.Id | Set-Content -LiteralPath '{pidfile}'\nStart-Sleep 60\n",
        encoding="utf-8",
    )
    owner_code = (
        "import os,time; from pathlib import Path; "
        "from tui.process import LauncherBuilder; "
        f"child=LauncherBuilder(Path({str(tmp_path)!r})).start_command({_script(native_shell, script)!r},Path({str(tmp_path / 'control')!r})); "
        "print(child.pid,flush=True); input(); os._exit(0)"
    )
    owner = subprocess.Popen(
        [sys.executable, "-c", owner_code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    handles = []
    try:
        launcher_pid = int(owner.stdout.readline())
        deadline = time.monotonic() + 15
        while (
            not pidfile.exists() or not pidfile.read_text(encoding="utf-8-sig").strip()
        ) and time.monotonic() < deadline:
            time.sleep(0.05)
        descendant = int(pidfile.read_text(encoding="utf-8-sig").strip())
        for pid in (launcher_pid, descendant):
            handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            assert handle
            handles.append(handle)
        owner.communicate("crash\n", timeout=10)
        assert owner.returncode == 0
        for handle in handles:
            assert kernel32.WaitForSingleObject(handle, 10000) == _WAIT_OBJECT_0
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.communicate(timeout=10)
        for handle in handles:
            kernel32.CloseHandle(handle)


@requires_windows
def test_instance_lock_entry_closes_on_release(tmp_path):
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    assert acquire_instance_lock(tmp_path) is None
    first.release()
    second = acquire_instance_lock(tmp_path)
    assert second is not None
    second.release()


@requires_windows
@pytest.mark.parametrize("cached_error", [0, 183])
def test_instance_lock_uses_the_ctypes_saved_error_not_raw_get_last_error(
    tmp_path, monkeypatch, cached_error
):
    import ctypes

    from tui import process

    closed = []

    def create(*args):
        ctypes.set_last_error(cached_error)
        return 123

    monkeypatch.setattr(process.kernel32, "CreateMutexW", create)
    monkeypatch.setattr(process.kernel32, "CloseHandle", closed.append)
    monkeypatch.setattr(
        process.kernel32, "GetLastError", lambda: pytest.fail("raw error slot used")
    )
    lock = process.acquire_instance_lock(tmp_path)
    if cached_error:
        assert lock is None and closed == [123]
    else:
        assert lock is not None
        lock.release()
        assert closed == [123]


def test_helper_shutdown_attempts_every_helper_before_reporting_failure():
    from tui.process import LauncherMachinery

    calls = []

    def first():
        calls.append(1)
        raise TimeoutError("first helper stuck")

    machinery = object.__new__(LauncherMachinery)
    machinery._helper_lock = threading.Lock()
    machinery._helpers = [
        SimpleNamespace(force_stop=first),
        SimpleNamespace(force_stop=lambda: calls.append(2)),
    ]
    machinery._closing = False
    with pytest.raises(RuntimeError):
        machinery.stop_helpers()
    assert calls == [1, 2]
    assert machinery._closing


@requires_windows
def test_owned_launch_has_a_private_hidden_console_not_the_owners_console(tmp_path):
    import sys

    harness = Path(__file__).resolve().parents[2]
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import ctypes,json\n"
        "k=ctypes.WinDLL('kernel32',use_last_error=True)\n"
        "k.GetConsoleWindow.restype=ctypes.c_void_p\n"
        "u=ctypes.WinDLL('user32'); u.IsWindowVisible.argtypes=[ctypes.c_void_p]\n"
        "window=k.GetConsoleWindow()\n"
        "print(json.dumps({'window':window,'visible':bool(u.IsWindowVisible(window)),'codepage':k.GetConsoleCP()}))\n",
        encoding="utf-8",
    )
    owner = tmp_path / "owner.py"
    owner.write_text(
        "import ctypes,json\nfrom pathlib import Path\nfrom tui.process import LauncherBuilder\n"
        "k=ctypes.WinDLL('kernel32'); k.GetConsoleWindow.restype=ctypes.c_void_p\n"
        "window=k.GetConsoleWindow(); assert window and k.GetConsoleCP()\n"
        f"child=LauncherBuilder(Path({str(harness)!r})).start_command([{sys.executable!r},{str(worker)!r}],Path({str(tmp_path / 'control')!r}))\n"
        "try:\n"
        " assert child.wait(20)==0\n"
        " result=json.loads(child._log.stdout_path.read_text(encoding='utf-8-sig'))\n"
        " assert result['window'] and result['window'] != window\n"
        " assert result['codepage'] and not result['visible']\n"
        "finally: child.close()\n",
        encoding="utf-8",
    )
    hidden = subprocess.STARTUPINFO()
    hidden.dwFlags = subprocess.STARTF_USESHOWWINDOW
    hidden.wShowWindow = 0
    completed = subprocess.run(
        [sys.executable, str(owner)],
        cwd=harness,
        env={**os.environ, "PYTHONPATH": str(harness)},
        startupinfo=hidden,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
