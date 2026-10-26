"""Controller and process-boundary checks for the multi-campaign console.

Orchestration is validated with fake machinery and a discriminated fake
executor; the Windows containment boundary gets a small real-child smoke
test. No campaign is launched, reset, initialized, trained or assessed, and
no scientific code or state changes.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

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
    (harness / "reset_research.ps1").write_text("$args", encoding="utf-8")
    (harness / "run_research.ps1").write_text("$args", encoding="utf-8")
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

    # ProcessMachinery protocol -------------------------------------------
    def start(self, folder: Path, arguments: list[str]) -> FakeChild:
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


def test_parse_command_count_and_targets():
    assert control.parse_command("run 3") == ("run", [1, 2, 3])
    assert control.parse_command("stop 1") == ("stop", [1])
    assert control.parse_command("reset campaign-1 campaign-3") == ("reset", [1, 3])
    assert control.parse_command("start campaign-2 campaign-1") == ("start", [1, 2])


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
    assert "-Provider" not in settings.launcher_arguments()
    assert settings.launcher_arguments() == [
        "-Model",
        "gpt-6-luna",
        "-Reasoning",
        "high",
        "-MaxTimesteps",
        "360000",
        "-MaxInquiries",
        "15",
        "-StopTimeoutSeconds",
        "180",
    ]
    assert control.ResetConfig().arguments() == [
        "-Mode",
        "Fresh",
        "-RecipeRef",
        control.DEFAULT_RECIPE_REF,
        "-Clean",
        "-Force",
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
    assert [step.action for step in outcome.steps] == ["initialize"]
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
        if call[:2] != ["git", "-C"] and "reset_research.ps1" in " ".join(call)
    ]
    assert len(reset_arguments) == 1
    assert "-Clean" in reset_arguments[0]
    assert control.DEFAULT_RECIPE_REF in reset_arguments[0]
    started_folder, started_arguments = machinery.started[-1]
    assert started_folder == layout.folder(2)
    joined = " ".join(started_arguments)
    assert "-CampaignRoot" in joined
    assert "-StopRequestPath" in joined
    assert outcome.ok


def test_run_stops_batch_when_reset_fails(tmp_path):
    controller, machinery, *_ = _controller(tmp_path)
    # Slot 2 reset fails; slot 3 must not reset or launch.
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
    assert launch_3[0].status == control.SKIPPED
    assert machinery.started == []


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


def test_preflight_reports_dirty_harness_and_skips_batch(tmp_path):
    controller, machinery, *_ = _controller(
        tmp_path, harness_dirty=["M  main.py"]
    )
    outcome = controller.execute("run", [1], settings=control.LaunchSettings())
    assert outcome.steps[0].action == "launch"
    assert outcome.steps[0].status == control.SKIPPED
    assert "uncommitted" in outcome.steps[0].detail
    assert machinery.started == []


def test_stop_without_target_requires_selection(tmp_path):
    controller, *_ = _controller(tmp_path)
    with pytest.raises(control.CommandError):
        controller.execute("run", [], settings=control.LaunchSettings())


# -- Windows containment boundary (real child smoke checks) ------------------

requires_windows = pytest.mark.skipif(
    os.name != "nt", reason="Job Objects are Windows-only"
)


@requires_windows
def test_supervised_launcher_captures_output_and_reports_exit(tmp_path):
    from tui.process import LauncherBuilder

    script = tmp_path / "dummy.ps1"
    script.write_text("Write-Output 'child-alive'\nexit 3\n", encoding="utf-8")
    builder = LauncherBuilder(tmp_path)
    launcher = builder.start(script, [], tmp_path / "control")
    assert launcher.pid > 0
    assert launcher.poll() is False
    exit_code = launcher.wait(20.0)
    assert exit_code == 3
    assert launcher.poll() is True
    assert "child-alive" in (tmp_path / "control" / "console.out.log").read_text(
        encoding="utf-8", errors="replace"
    )
    assert launcher.job_process_ids() == []
    launcher.close()


@requires_windows
def test_force_stop_terminates_the_whole_contained_tree(tmp_path):
    from tui.process import LauncherBuilder

    script = tmp_path / "spawner.ps1"
    grandchild = tmp_path / "grandchild.ps1"
    grandchild.write_text("Start-Sleep -Seconds 60\n", encoding="utf-8")
    script.write_text(
        "Start-Process pwsh -ArgumentList '-NoProfile','-File','"
        + str(grandchild)
        + "'\nStart-Sleep -Seconds 60\n",
        encoding="utf-8",
    )
    builder = LauncherBuilder(tmp_path)
    launcher = builder.start(script, [], tmp_path / "control")
    time.sleep(0.5)  # allow the grandchild to spawn
    launcher.force_stop(timeout=10.0)
    assert launcher.poll() is True
    assert launcher.job_process_ids() == []
    assert launcher.exit_code != 0


@requires_windows
def test_instance_lock_entry_closes_on_release(tmp_path):
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    assert acquire_instance_lock(tmp_path) is None
    first.release()
    second = acquire_instance_lock(tmp_path)
    assert second is not None
    second.release()
