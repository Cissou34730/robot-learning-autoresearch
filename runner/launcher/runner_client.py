"""Runner and helper invocations from the launcher, with structured results."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from runner.launcher.child import ChildRunner
from runner.launcher.trust import TrustGuard

PUBLICATION_FAILURE_EXIT_CODE = 3


class LauncherError(RuntimeError):
    """A launcher-level failure; its message is reported verbatim."""


@dataclass(frozen=True)
class RunnerOutcome:
    exit_code: int
    result: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[str]:
        return [
            str(error)
            for error in self.result.get("errors") or []
            if str(error).strip()
        ]

    @property
    def validation_message(self) -> str:
        validation = self.result.get("validation")
        if isinstance(validation, dict) and validation.get("message"):
            return str(validation["message"]).strip()
        return "\n".join(self.errors).strip()

    def submission_error(self) -> str:
        if self.errors:
            return os.linesep.join(self.errors).strip()
        return "Runner failed without an error message; transaction state is preserved."


def uv_executable() -> str:
    found = shutil.which("uv")
    if not found:
        raise LauncherError(
            "uv is not on PATH; the launcher needs it to start children."
        )
    return found


class RunnerClient:
    """Runs harness Python children for one campaign under the trust gate."""

    def __init__(
        self,
        *,
        harness_root: Path,
        children: ChildRunner,
        trust: TrustGuard,
        timesteps: int,
        max_timesteps: int,
    ) -> None:
        self._harness = harness_root
        self._children = children
        self._trust = trust
        self._timesteps = timesteps
        self._max_timesteps = max_timesteps
        self._results = Path(tempfile.mkdtemp(prefix="robot-learning-launcher-"))
        self._count = 0

    def _python(self, *arguments: str, group: str | None = None) -> list[str]:
        command = [uv_executable(), "run", "--project", str(self._harness)]
        if group:
            command += ["--group", group]
        return [*command, "python", *arguments]

    def runner(
        self, *arguments: str, input_text: str | None = None, refresh_trust: bool = True
    ) -> RunnerOutcome:
        """One Runner invocation; the trust snapshot is checked before it runs."""
        self._trust.verify()
        self._count += 1
        result_path = self._results / f"result-{self._count}.json"
        command = self._python(
            "-m",
            "runner.run_experiment",
            "--timesteps",
            str(self._timesteps),
            "--max-timesteps",
            str(self._max_timesteps),
            *arguments,
            "--result-path",
            str(result_path),
        )
        exit_code = self._children.run(
            command, operation="research runner", input_text=input_text
        )
        if refresh_trust:
            self._trust.refresh()
        return RunnerOutcome(exit_code, _read_result(result_path))

    def build_brief(self) -> None:
        self._trust.verify()
        if self._children.run(
            self._python("-m", "runner.build_brief"), operation="research brief"
        ):
            raise LauncherError("Could not build the compact PI research brief.")

    def require_runtime(self) -> None:
        if self._children.run(
            self._python("-c", "import runner.run_experiment"),
            operation="runtime check",
        ):
            raise LauncherError(
                "The research runtime is internally inconsistent. No PI session or "
                "Runner operation was started."
            )

    def adapter_command(self, *arguments: str) -> list[str]:
        return self._python(
            "-m", "runner.copilot.copilot_adapter", *arguments, group="researcher"
        )

    def close(self) -> None:
        shutil.rmtree(self._results, ignore_errors=True)


def _read_result(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    finally:
        path.unlink(missing_ok=True)
    return value if isinstance(value, dict) else {}
