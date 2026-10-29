"""Bounded campaign shutdown coordination, independent of dialogs."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Thread

from tui.controller import CampaignController


@dataclass(frozen=True)
class ShutdownOutcome:
    detached: tuple[str, ...] = ()
    complete: bool = True


class ShutdownCoordinator:
    def __init__(
        self,
        controller: CampaignController,
        report: Callable[[str], None],
        choose: Callable[[list[str]], str],
    ) -> None:
        self.controller = controller
        self.report = report
        self.choose = choose

    def wait(self, labels: list[str], seconds: float) -> list[str]:
        if not labels:
            return []
        with ThreadPoolExecutor(max_workers=len(labels)) as pool:
            futures = {
                label: pool.submit(self.controller.wait_stopped, label, seconds)
                for label in labels
            }
        still_running = []
        for label, future in futures.items():
            try:
                stopped = future.result()
            except (OSError, RuntimeError) as error:
                self.report(f"Campaign cleanup failed: {label}: {error}")
                continue
            if not stopped:
                still_running.append(label)
        return still_running

    def stop(
        self,
        command_thread: Thread | None,
        *,
        helper_grace: float,
        prompt_seconds: float,
        wait_more_seconds: float,
    ) -> ShutdownOutcome:
        cleanup_failed = False
        if command_thread is not None:
            command_thread.join(helper_grace)
            if command_thread.is_alive():
                try:
                    self.controller.stop_helpers()
                except (OSError, RuntimeError) as error:
                    cleanup_failed = True
                    self.report(f"Helper cleanup failed: {error}")
                command_thread.join(5)
        stuck = self.wait(
            [
                state.label
                for state in self.controller.folder_states()
                if state.child is not None
            ],
            prompt_seconds,
        )
        while stuck:
            choice = self.choose(stuck)
            if choice == "kill":
                self.controller.force_all(timeout=15.0)
                break
            if choice == "leave":
                return ShutdownOutcome(tuple(self.controller.detach_all()))
            stuck = self.wait(stuck, wait_more_seconds)
        return ShutdownOutcome(complete=not cleanup_failed)
