"""Execution mechanics for the Runner.

Subprocesses, training, research evaluations, timeouts, interruption handling
and the candidate artifacts they produce. The training and physics stack is
imported inside the execution paths that need it, so validation-only commands
never pay for it.
"""

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from research import runner_console as console
from research import runner_paths as paths
from research import runner_repository as repository
from robot_learning.training.research_config import (
    RESEARCH_EVALUATION_EPISODES,
    RESEARCH_EVALUATION_SEED,
)

TRAIN_TIMEOUT_SECONDS = 12 * 60 * 60
TRAIN_STALL_SECONDS = 30 * 60
STATUS_INTERVAL_SECONDS = 15
INTERRUPT_GRACE_SECONDS = 30
EVALUATION_TIMEOUT_SECONDS = 12 * 60 * 60
EVALUATION_STALL_SECONDS = 30 * 60


# --- process mechanics -----------------------------------------------------


def running_on_windows() -> bool:
    return platform.system() == "Windows"


def process_group_options() -> dict:
    if running_on_windows():
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_process(process: subprocess.Popen, *, graceful: bool) -> None:
    if process.poll() is not None:
        return
    if running_on_windows():
        if graceful:
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                process.wait(timeout=INTERRUPT_GRACE_SECONDS)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return
    if graceful:
        kill_process_group = getattr(os, "killpg", None)
        if kill_process_group is not None:
            try:
                kill_process_group(process.pid, signal.SIGINT)
                process.wait(timeout=INTERRUPT_GRACE_SECONDS)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_module(module: str, *args: str, timeout: int | None = None) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=paths.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{module} failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return result.stdout


def run_command(*command: str, timeout: int | None = None) -> str:
    result = subprocess.run(
        list(command),
        cwd=paths.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed:\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return result.stdout


# --- research-surface checks -----------------------------------------------


def validate_changed_sources(changed_paths: list[str]) -> None:
    python_changes: list[str] = []
    for path in changed_paths:
        absolute = paths.ROOT / path
        if not absolute.is_file():
            continue
        if path.endswith(".py"):
            try:
                compile(absolute.read_text(encoding="utf-8"), path, "exec")
            except SyntaxError as error:
                message = f"{path} has invalid Python syntax: {error}"
                raise RuntimeError(message) from error
            python_changes.append(path)
        elif path.endswith(".json"):
            try:
                json.loads(absolute.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise RuntimeError(f"{path} is not valid JSON: {error}") from error
    if python_changes:
        run_module("ruff", "check", *python_changes)


def validate_dependency_metadata() -> None:
    """Check the lockfile against the project metadata without rewriting it."""
    run_command("uv", "lock", "--check")


def effective_config(config: dict) -> dict:
    """The trainer's own view of a configuration, resolved through the trainer."""
    from robot_learning.train import effective_training_config

    return effective_training_config(config)


def validate_active_configuration() -> dict:
    """Resolve the active configuration through the trainer's own view of it."""
    from robot_learning.training import research_config

    config = research_config.load_experiment_config()
    research_config.validate_param_overrides(config)
    try:
        return effective_config(config)
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"the active training configuration is invalid: {error}"
        ) from error


def run_validation_suites(selected_tests: tuple[str, ...]) -> None:
    run_module(
        "pytest",
        "-q",
        *selected_tests,
        "--basetemp",
        str(paths.ROOT / ".pytest-run-temp"),
    )


# --- training --------------------------------------------------------------


def read_training_log(log_path: Path, after_offset: int = 0) -> str:
    if not log_path.exists():
        return ""
    with log_path.open(encoding="utf-8", errors="replace") as handle:
        handle.seek(after_offset)
        return handle.read()


def latest_step_count(text: str) -> int | None:
    matches = re.findall(r"\|\s+total_timesteps\s+\|\s+(\d+)\s+\|", text)
    return int(matches[-1]) if matches else None


def latest_training_steps(log_path: Path, *, after_offset: int = 0) -> int | None:
    return latest_step_count(read_training_log(log_path, after_offset))


def training_log_attempts(experiment: int) -> list[int]:
    pattern = re.compile(rf"^experiment-{experiment}-attempt-(\d+)\.log$")
    attempts = [
        int(match.group(1))
        for log_path in paths.TRAINING_LOG_DIR.glob(f"experiment-{experiment}-attempt-*.log")
        if (match := pattern.match(log_path.name)) is not None
    ]
    return sorted(attempts)


def training_log_path(experiment: int, attempt: int) -> Path:
    return paths.training_log_path(experiment, attempt)


def training_attempt(experiment: int, *, recoverable_continuation: bool) -> int:
    attempts = training_log_attempts(experiment)
    if recoverable_continuation:
        if not attempts:
            raise RuntimeError(
                f"no training log exists for recoverable experiment {experiment}"
            )
        return attempts[-1]
    return attempts[-1] + 1 if attempts else 1


def training_records(experiment: int, attempt: int) -> list[dict[str, float]]:
    from robot_learning.training.progress import parse_training_records

    return parse_training_records(read_training_log(training_log_path(experiment, attempt)))


def training_budget(
    standard_timesteps: int,
    _initialization: str,
    _baseline: bool,
    _accepted_training_steps: int,
) -> int:
    del _initialization, _baseline, _accepted_training_steps
    return standard_timesteps


def train_candidate(
    output_dir: Path,
    timesteps: int,
    seed: int,
    resume: Path | None,
    training_log: Path,
    label: str = "candidate training",
    continue_timesteps: bool = False,
    target_timesteps: int | None = None,
) -> float:
    from robot_learning.training.progress import latest_training_record

    command = [
        sys.executable,
        "-m",
        "robot_learning.train",
        "--timesteps",
        str(timesteps),
        "--seed",
        str(seed),
        "--output-dir",
        str(output_dir),
    ]
    if resume is not None:
        command.extend(["--resume", str(resume)])
    if continue_timesteps:
        command.append("--continue-timesteps")
    if target_timesteps is not None:
        command.extend(["--target-timesteps", str(target_timesteps)])
    train_log = training_log
    started = time.monotonic()
    console.announce(f"[train] {label} | seed {seed} | {timesteps:,} steps")
    train_log.parent.mkdir(parents=True, exist_ok=True)
    with train_log.open("a" if continue_timesteps else "w", encoding="utf-8") as log_file:
        log_file.write(f"\n=== {label} ===\n")
        log_file.flush()
        progress_offset = log_file.tell()
        process = subprocess.Popen(
            command,
            cwd=paths.ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            **process_group_options(),
        )
        last_steps: int | None = None
        last_progress_at = started
        try:
            while process.poll() is None:
                try:
                    process.wait(timeout=STATUS_INTERVAL_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
                elapsed = time.monotonic() - started
                log_text = read_training_log(train_log, progress_offset)
                record = latest_training_record(log_text)
                steps = latest_step_count(log_text)
                if steps is None:
                    console.announce(
                        f"[train] starting ({console.format_duration(elapsed)} elapsed)"
                    )
                else:
                    if steps != last_steps:
                        last_steps = steps
                        last_progress_at = time.monotonic()
                    progress_target = target_timesteps or timesteps
                    progress = min(100.0, 100 * steps / progress_target)
                    completed_this_run = (
                        steps
                        if not continue_timesteps
                        else max(steps - (progress_target - timesteps), 0)
                    )
                    eta = (
                        elapsed * max(progress_target - steps, 0) / completed_this_run
                        if completed_this_run
                        else 0
                    )
                    console.announce(
                        f"[train] {steps:,} / {progress_target:,} "
                        f"({progress:.0f}%) | {console.format_duration(elapsed)} | "
                        f"ETA ~{console.format_duration(eta)}"
                        + console.training_progress_suffix(record)
                    )
                stalled_for = time.monotonic() - last_progress_at
                if stalled_for > TRAIN_STALL_SECONDS:
                    console.announce("[train] no progress for 30 minutes; stopping.")
                    stop_process(process, graceful=False)
                    raise TimeoutError("training made no progress for 30 minutes")
                if elapsed > TRAIN_TIMEOUT_SECONDS:
                    console.announce("[train] 12 hour safety limit reached; stopping.")
                    stop_process(process, graceful=False)
                    raise TimeoutError("training exceeded the 12 hour safety limit")
        except KeyboardInterrupt:
            console.announce(
                "\n[runner] Stopping training and waiting for it to close..."
            )
            stop_process(process, graceful=True)
            raise
    if process.returncode != 0:
        tail = train_log.read_text(encoding="utf-8").splitlines()[-15:]
        raise RuntimeError("training failed:\n" + "\n".join(tail))
    for filename in repository.ARTIFACT_FILES:
        if not (output_dir / filename).exists():
            raise RuntimeError(f"training output is incomplete: {filename}")
    return time.monotonic() - started


# --- candidate artifacts ---------------------------------------------------


def remove_candidate_dir(path: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved.parent != paths.CANDIDATE_ROOT.resolve():
        raise RuntimeError(f"refusing to remove non-candidate directory: {resolved}")
    for attempt in range(20):
        try:
            shutil.rmtree(resolved)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.25)


def candidate_directories(candidate_dir: Path) -> list[Path]:
    manifest_path = candidate_dir / "candidate_manifest.json"
    if not manifest_path.exists():
        return [candidate_dir / "final_checkpoint"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = [candidate_dir / item["path"] for item in manifest["candidates"]]
    if not candidates:
        raise RuntimeError("training must produce at least one candidate")
    for candidate in candidates:
        for filename in repository.ARTIFACT_FILES:
            if not (candidate / filename).exists():
                raise RuntimeError(f"candidate is incomplete: {candidate / filename}")
    return candidates


def copy_candidate_outputs(source: Path, destination: Path) -> None:
    repository.copy_artifact(source, destination)
    final_checkpoint = source / "final_checkpoint"
    if final_checkpoint.exists():
        repository.copy_artifact(final_checkpoint, destination / "final_checkpoint")
    manifest_path = source / "candidate_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shutil.copyfile(manifest_path, destination / "candidate_manifest.json")
    for candidate in manifest["candidates"]:
        relative = Path(candidate["path"])
        if relative == Path("final_checkpoint"):
            continue
        shutil.copytree(source / relative, destination / relative)


def validate_reusable_candidate(
    source: Path,
    *,
    timesteps: int,
    seed: int,
    resume: Path | None,
    config: dict,
) -> None:
    for filename in repository.ARTIFACT_FILES:
        if not (source / filename).exists():
            raise ValueError(f"reusable candidate is incomplete: {filename}")
    artifact = json.loads((source / "artifact.json").read_text(encoding="utf-8"))
    expected_effective_config = effective_config(config)
    expected_resume = resume.resolve() if resume is not None else None
    actual_resume = (
        Path(artifact["resumed_from"]).resolve()
        if artifact.get("resumed_from") is not None
        else None
    )
    checks = {
        "seed": artifact.get("seed") == seed,
        "requested timesteps": int(
            artifact.get("requested_timesteps", artifact.get("timesteps", -1))
        )
        == timesteps,
        "effective configuration": artifact.get("effective_config")
        == expected_effective_config,
        "resume checkpoint": (
            not bool(artifact.get("completed", True))
            or actual_resume == expected_resume
        ),
    }
    mismatches = [name for name, matches in checks.items() if not matches]
    if mismatches:
        raise ValueError(
            "reusable candidate does not match this experiment: "
            + ", ".join(mismatches)
        )


# --- measurement -----------------------------------------------------------


def evaluate_artifact(
    artifact_dir: Path,
    seed: int = RESEARCH_EVALUATION_SEED,
    label: str = "official evaluation",
    episodes: int = RESEARCH_EVALUATION_EPISODES,
    output_path: Path | None = None,
    official_benchmark: bool = False,
    task_reference: bool = False,
) -> dict:
    output_path = output_path or paths.RESEARCH_DIR / "last_evaluation.json"
    output_path.unlink(missing_ok=True)
    progress_path = output_path.with_suffix(output_path.suffix + ".progress")
    stale_temporary_progress = progress_path.with_suffix(progress_path.suffix + ".tmp")
    progress_path.unlink(missing_ok=True)
    stale_temporary_progress.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "robot_learning.evaluate",
        "--model",
        str(artifact_dir / "model.zip"),
        "--episodes",
        str(episodes),
        "--seed",
        str(seed),
        "--output-json",
        str(output_path),
        "--progress-json",
        str(progress_path),
    ]
    if official_benchmark:
        command.append("--official-benchmark")
    if task_reference:
        command.append("--task-reference")
    progress_label = f"{artifact_dir.name} {label}"
    started = time.monotonic()
    last_progress_at = started
    completed_episodes = 0
    # The evaluator can emit large episode-level diagnostics. File-backed streams
    # avoid filling a Windows pipe while this process waits and prints heartbeats.
    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            command,
            cwd=paths.ROOT,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            **process_group_options(),
        )
        try:
            while True:
                try:
                    process.wait(timeout=STATUS_INTERVAL_SECONDS)
                    break
                except subprocess.TimeoutExpired:
                    try:
                        progress = json.loads(progress_path.read_text(encoding="utf-8"))
                        current_completed = int(progress["completed"])
                    except (
                        FileNotFoundError,
                        json.JSONDecodeError,
                        KeyError,
                        ValueError,
                    ):
                        current_completed = completed_episodes
                    if current_completed > completed_episodes:
                        completed_episodes = current_completed
                        last_progress_at = time.monotonic()
                    console.announce(
                        f"[eval] {progress_label:<20} "
                        f"| {completed_episodes:>4} / {episodes} "
                        f"| {100 * completed_episodes // episodes:>3}% "
                        f"| {console.format_duration(time.monotonic() - started)}"
                    )
                    if time.monotonic() - last_progress_at > EVALUATION_STALL_SECONDS:
                        stop_process(process, graceful=False)
                        raise TimeoutError(
                            f"{label} made no episode progress for "
                            f"{console.format_duration(EVALUATION_STALL_SECONDS)} "
                            f"({completed_episodes}/{episodes} complete)"
                        )
                    if time.monotonic() - started > EVALUATION_TIMEOUT_SECONDS:
                        stop_process(process, graceful=False)
                        raise TimeoutError(
                            f"{label} exceeded the "
                            f"{console.format_duration(EVALUATION_TIMEOUT_SECONDS)} total limit "
                            f"({completed_episodes}/{episodes} complete)"
                        )
        except KeyboardInterrupt:
            console.announce(f"\n[runner] Stopping {label}...")
            stop_process(process, graceful=True)
            raise
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    progress_path.unlink(missing_ok=True)
    stale_temporary_progress.unlink(missing_ok=True)
    if process.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{stdout[-2000:]}\n{stderr[-2000:]}")
    metrics = json.loads(output_path.read_text(encoding="utf-8"))
    console.announce(
        f"[eval] {progress_label:<20} "
        f"| {int(metrics['episodes']):>4} / {episodes} | 100% "
        f"| {console.format_duration(time.monotonic() - started)} "
        f"| success {metrics['success_percent']:.1f}%"
    )
    return metrics


def requested_paired_comparisons(
    request: dict,
    evaluations_by_candidate: dict[str, list[dict]],
) -> list[dict]:
    from robot_learning.training.comparison import paired_comparison

    comparisons = request.get("paired_comparisons", [])
    if not isinstance(comparisons, list):
        raise TypeError("paired_comparisons must be a list")
    results: list[dict] = []
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise TypeError("each paired comparison must be an object")
        candidate_name = str(comparison.get("candidate", "")).strip()
        reference_name = str(comparison.get("reference", "")).strip()
        if candidate_name not in evaluations_by_candidate:
            raise ValueError(f"unknown paired comparison candidate {candidate_name!r}")
        if reference_name not in evaluations_by_candidate:
            raise ValueError(f"unknown paired comparison reference {reference_name!r}")
        try:
            result = paired_comparison(
                evaluations_by_candidate[candidate_name],
                evaluations_by_candidate[reference_name],
            )
        except ValueError as error:
            raise ValueError(
                f"paired comparison {candidate_name!r} vs {reference_name!r}: {error}"
            ) from error
        results.append(
            {
                "candidate": candidate_name,
                "reference": reference_name,
                **result,
            }
        )
    return results
