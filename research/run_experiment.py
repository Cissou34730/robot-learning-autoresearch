"""Transactional autonomous-research runner for robot learning."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from research.build_research_brief import write_training_summary
from robot_learning.benchmark.spec import (
    EVALUATION_EPISODES,
    EVALUATION_SEED,
    FINAL_SUCCESS_PERCENT,
    HOLD_SECONDS,
    SUCCESS_THRESHOLD,
)
from robot_learning.training.research_config import (
    load_experiment_config,
    merge_param_overrides,
    validate_param_overrides,
    write_experiment_config,
)

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
LOG_PATH = RESEARCH_DIR / "EXPERIMENTS.md"
RESULTS_PATH = RESEARCH_DIR / "results.jsonl"
PROPOSAL_PATH = RESEARCH_DIR / "proposal.json"
EVALUATION_REQUEST_PATH = RESEARCH_DIR / "evaluation_request.json"
STATE_PATH = RESEARCH_DIR / "research_state.json"
BASELINE_PENDING_PATH = RESEARCH_DIR / "BASELINE_PENDING"
RECOVERY_PENDING_PATH = RESEARCH_DIR / "RECOVERY_PENDING"
RESTART_PENDING_PATH = RESEARCH_DIR / "RESTART_PENDING"
GOAL_PATH = RESEARCH_DIR / "GOAL_REACHED"
ACCEPTED_DIR = RESEARCH_DIR / "checkpoints" / "accepted"
CANDIDATE_ROOT = ROOT / "models" / "candidates"

TIMESTEPS = 120_000
TRAIN_SEED = 0
TRAIN_TIMEOUT_SECONDS = 12 * 60 * 60
TRAIN_STALL_SECONDS = 30 * 60
STATUS_INTERVAL_SECONDS = 15
INTERRUPT_GRACE_SECONDS = 30
EVALUATION_TIMEOUT_SECONDS = 12 * 60 * 60
EVALUATION_STALL_SECONDS = 30 * 60
EVALUATION_SUMMARY_VERSION = 1


def announce(message: str) -> None:
    print(message, flush=True)


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def training_budget(
    standard_timesteps: int,
    initialization: str,
    baseline: bool,
    accepted_training_steps: int,
) -> int:
    return standard_timesteps


def latest_training_steps(log_path: Path, *, after_offset: int = 0) -> int | None:
    if not log_path.exists():
        return None
    with log_path.open(encoding="utf-8", errors="replace") as handle:
        handle.seek(after_offset)
        text = handle.read()
    matches = re.findall(r"\|\s+total_timesteps\s+\|\s+(\d+)\s+\|", text)
    return int(matches[-1]) if matches else None


def process_group_options() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_process(process: subprocess.Popen, *, graceful: bool) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
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
        try:
            os.killpg(process.pid, signal.SIGINT)
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


def remove_candidate_dir(path: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    if resolved.parent != CANDIDATE_ROOT.resolve():
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


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def atomic_write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_state(
    *,
    allow_unmeasured: bool = False,
    allow_missing_artifact: bool = False,
) -> dict:
    if not STATE_PATH.exists():
        raise RuntimeError("research state is missing; refusing to run")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    required = {"schema_version", "accepted_artifact"}
    missing = required - set(state)
    if missing:
        raise RuntimeError(f"research state is incomplete: {sorted(missing)}")
    if state["schema_version"] != 2:
        raise RuntimeError("unsupported research state schema")
    if not allow_missing_artifact:
        artifact = ROOT / state["accepted_artifact"]
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            if not (artifact / filename).exists():
                raise RuntimeError(f"accepted artifact is incomplete: {filename}")
    if not allow_unmeasured and state.get("accepted_metrics") is None:
        raise RuntimeError("accepted checkpoint has no baseline metrics")
    return state


def status_paths(paths: tuple[str, ...]) -> list[str]:
    output = git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    return [line[3:].strip().strip('"') for line in output.splitlines() if line]


def assert_research_surface() -> list[str]:
    changed = status_paths((".",))
    control_files = {
        "research/proposal.json",
        "research/evaluation_request.json",
    }
    return [
        path
        for path in changed
        if path.replace("\\", "/") not in control_files
    ]


def run_module(module: str, *args: str, timeout: int | None = None) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
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


def next_index() -> int:
    indices: list[int] = []
    if RESULTS_PATH.exists():
        for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                indices.append(int(json.loads(line)["index"]))
    if not indices and LOG_PATH.exists():
        indices = [
            int(value)
            for value in re.findall(
                r"^\| (\d+) \|", LOG_PATH.read_text(encoding="utf-8"), re.MULTILINE
            )
        ]
    return max(indices, default=0) + 1


def parameter_change_records(
    previous: dict,
    overrides: dict,
    prefix: str = "",
) -> list[dict]:
    """Describe only the leaves explicitly changed by a proposal."""
    changes: list[dict] = []
    for key, after in overrides.items():
        path = f"{prefix}.{key}" if prefix else key
        before = previous.get(key) if isinstance(previous, dict) else None
        if isinstance(after, dict):
            changes.extend(
                parameter_change_records(
                    before if isinstance(before, dict) else {},
                    after,
                    path,
                )
            )
        elif before != after:
            changes.append({"path": path, "before": before, "after": after})
    return changes


def experiment_family(
    proposal: dict,
    experiment_kind: str,
    parameter_changes: list[dict],
    code_changes: list[str],
) -> str:
    declared = str(proposal.get("family", "")).strip()
    if declared:
        return declared
    if experiment_kind == "calibration":
        return "research.training_seed_calibration"
    if proposal.get("baseline"):
        return "training.baseline"
    parameter_paths = sorted({item["path"] for item in parameter_changes})
    if parameter_paths:
        return "+".join(parameter_paths)
    if experiment_kind == "method":
        return "research.selection_method"
    if code_changes:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(proposal["change"]).lower())
        return f"code.{normalized.strip('_')[:80]}"
    return experiment_kind


def append_result(result: dict) -> None:
    with RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")
    def cell(value: object) -> str:
        return " ".join(str(value).replace("|", "/").split())

    row = (
        f"| {result['index']} | {time.strftime('%Y-%m-%d')} | "
        f"{cell(result['change'])} | {cell(result['hypothesis'])} | "
        f"{cell(result.get('candidate_success_percent', '-'))} | "
        f"{cell(result.get('candidate_seeds_passed', '-'))} | "
        f"{cell(result['verdict'])} |"
    )
    text = LOG_PATH.read_text(encoding="utf-8").rstrip("\n") + "\n" + row + "\n"
    LOG_PATH.write_text(text, encoding="utf-8")


def latest_recorded_experiment() -> int | None:
    if not RESULTS_PATH.exists():
        return None
    records = [
        json.loads(line)
        for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return int(records[-1]["index"]) if records else None


def record_previous_postmortem(proposal: dict, *, baseline: bool) -> None:
    previous_index = latest_recorded_experiment()
    if baseline or previous_index is None:
        return
    memory = proposal.get("previous_experiment_postmortem")
    if not isinstance(memory, dict):
        raise TypeError(
            "proposal must include previous_experiment_postmortem for experiment "
            f"{previous_index}"
        )
    if int(memory.get("experiment", -1)) != previous_index:
        raise ValueError(
            "previous_experiment_postmortem must describe experiment "
            f"{previous_index}"
        )
    fields = {
        "result": "Result",
        "behavior": "Observed behavior",
        "learned": "What was learned / do NOT retry",
        "next_class": "Recommended next experiment class",
    }
    missing = [key for key in fields if not str(memory.get(key, "")).strip()]
    if missing:
        raise ValueError(f"postmortem fields are missing: {missing}")
    path = RESEARCH_DIR / "postmortems.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research postmortems\n"
    if re.search(rf"^## Experiment {previous_index}\b", text, re.MULTILINE):
        return
    lines = ["", f"## Experiment {previous_index}", ""]
    for key, label in fields.items():
        value = " ".join(str(memory[key]).split())
        lines.append(f"**{label}:** {value}")
        lines.append("")
    path.write_text(text.rstrip() + "\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def evaluate_artifact(
    artifact_dir: Path,
    seed: int = EVALUATION_SEED,
    label: str = "official evaluation",
    episodes: int = EVALUATION_EPISODES,
    output_path: Path | None = None,
) -> dict:
    output_path = output_path or RESEARCH_DIR / "last_evaluation.json"
    output_path.unlink(missing_ok=True)
    progress_path = output_path.with_suffix(output_path.suffix + ".progress")
    progress_path.unlink(missing_ok=True)
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
    announce(
        f"[evaluation] {label} | {episodes} episodes | seed {seed}"
    )
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
            cwd=ROOT,
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
                    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
                        current_completed = completed_episodes
                    if current_completed > completed_episodes:
                        completed_episodes = current_completed
                        last_progress_at = time.monotonic()
                    announce(
                        f"[evaluation] {label} still running "
                        f"| {completed_episodes}/{episodes} episodes "
                        f"({format_duration(time.monotonic() - started)} elapsed)"
                    )
                    if time.monotonic() - last_progress_at > EVALUATION_STALL_SECONDS:
                        stop_process(process, graceful=False)
                        raise TimeoutError(
                            f"{label} made no episode progress for "
                            f"{format_duration(EVALUATION_STALL_SECONDS)} "
                            f"({completed_episodes}/{episodes} complete)"
                        )
                    if time.monotonic() - started > EVALUATION_TIMEOUT_SECONDS:
                        stop_process(process, graceful=False)
                        raise TimeoutError(
                            f"{label} exceeded the "
                            f"{format_duration(EVALUATION_TIMEOUT_SECONDS)} total limit "
                            f"({completed_episodes}/{episodes} complete)"
                        )
        except KeyboardInterrupt:
            announce(f"\n[runner] Stopping {label}...")
            stop_process(process, graceful=True)
            raise
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    progress_path.unlink(missing_ok=True)
    if process.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{stdout[-2000:]}\n{stderr[-2000:]}")
    metrics = json.loads(output_path.read_text(encoding="utf-8"))
    announce(
        f"[evaluation] {label} complete in "
        f"{format_duration(time.monotonic() - started)} | "
        f"success: {metrics['success_percent']:.1f}% | "
        f"failed episodes: {metrics['failed_episode_progress']['failed_episodes']} | "
        f"failed hold: "
        f"{metrics['failed_episode_progress']['longest_consecutive_steps_mean']:.1f}/"
        f"{metrics['failed_episode_progress']['required_steps']} | "
        f"best window: "
        f"{metrics['failed_episode_progress']['best_window_inside_steps_mean']:.1f}/"
        f"{metrics['failed_episode_progress']['required_steps']}"
    )
    return metrics


def summarize_evaluations(
    evaluations: list[dict],
    summary_version: int = EVALUATION_SUMMARY_VERSION,
) -> dict:
    if not evaluations:
        raise ValueError("an evaluation summary requires at least one evaluation")
    total_episodes = sum(int(item["episodes"]) for item in evaluations)
    total_successes = sum(
        float(item["success_percent"]) * int(item["episodes"]) / 100
        for item in evaluations
    )
    total_failures = sum(
        int(item["failed_episode_progress"]["failed_episodes"])
        for item in evaluations
    )
    required = int(evaluations[0]["failed_episode_progress"]["required_steps"])

    def failure_weighted_mean(field: str, perfect: float) -> float:
        if not total_failures:
            return perfect
        return sum(
            float(item["failed_episode_progress"][field])
            * int(item["failed_episode_progress"]["failed_episodes"])
            for item in evaluations
        ) / total_failures

    seed_success = {
        str(item["seed"]): float(item["success_percent"]) for item in evaluations
    }
    failed_diagnostics = [
        {
            key: value
            for key, value in episode.items()
            if key != "distance_trace_cm"
        }
        for evaluation in evaluations
        for episode in evaluation.get("episode_results", [])
        if not episode["success"]
    ]
    failed_diagnostics.sort(
        key=lambda item: (
            item["longest_consecutive_steps"],
            item["best_window_inside_steps"],
            -item["best_window_excess_cm"],
        )
    )
    pooled_success = 100 * total_successes / total_episodes
    return {
        "schema_version": 1,
        "evaluation_summary_version": summary_version,
        "episodes": total_episodes,
        "seed_count": len(evaluations),
        "seed_success_percent": seed_success,
        "seeds_passing_98_percent": sum(
            success >= FINAL_SUCCESS_PERCENT for success in seed_success.values()
        ),
        "worst_seed_success_percent": min(seed_success.values()),
        "pooled_success_percent": pooled_success,
        "success_percent": pooled_success,
        "failed_episode_progress": {
            "failed_episodes": total_failures,
            "longest_consecutive_steps_mean": failure_weighted_mean(
                "longest_consecutive_steps_mean", float(required)
            ),
            "best_window_inside_steps_mean": failure_weighted_mean(
                "best_window_inside_steps_mean", float(required)
            ),
            "best_window_excess_cm_mean": failure_weighted_mean(
                "best_window_excess_cm_mean", 0.0
            ),
            "required_steps": required,
        },
        "failure_diagnostics": failed_diagnostics,
    }


def candidate_directories(candidate_dir: Path) -> list[Path]:
    manifest_path = candidate_dir / "candidate_manifest.json"
    if not manifest_path.exists():
        return [candidate_dir / "final_checkpoint"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = [candidate_dir / item["path"] for item in manifest["candidates"]]
    if not candidates:
        raise RuntimeError("training must produce at least one candidate")
    for candidate in candidates:
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            if not (candidate / filename).exists():
                raise RuntimeError(f"candidate is incomplete: {candidate / filename}")
    return candidates


def archive_candidates(
    index: int,
    contenders: list[dict],
    config: dict,
) -> list[dict]:
    destination = RESEARCH_DIR / "checkpoints" / "challengers" / f"experiment-{index}"
    if destination.exists():
        raise RuntimeError(f"challenger archive already exists: {destination}")
    destination.mkdir(parents=True)
    archived: list[dict] = []
    for contender in contenders:
        if contender["kind"] != "candidate":
            continue
        artifact = destination / contender["name"]
        copy_artifact(contender["path"], artifact)
        archived.append(
            {
                "name": contender["name"],
                "artifact": str(artifact.relative_to(ROOT)),
                "timesteps": int(contender["timesteps"]),
                "evaluations": [],
            }
        )
    atomic_write_json(destination / "parameters.json", config)
    atomic_write_json(
        destination / "inventory.json",
        {
            "schema_version": 1,
            "candidates": archived,
        },
    )
    return archived


def execute_pending_evaluations() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    pending = state.get("pending_evaluation_request")
    if not isinstance(pending, dict):
        raise TypeError("there is no trained experiment awaiting evaluation")
    if EVALUATION_REQUEST_PATH.exists():
        request = json.loads(EVALUATION_REQUEST_PATH.read_text(encoding="utf-8"))
        pending["evaluation_plan"] = request
        pending.setdefault("partial_evaluations", [])
        atomic_write_json(STATE_PATH, state)
    else:
        request = pending.get("evaluation_plan")
        if not isinstance(request, dict):
            print("ERROR: research/evaluation_request.json not found.")
            return 1
    experiment = int(pending["experiment"])
    if int(request.get("experiment", -1)) != experiment:
        raise ValueError("evaluation request references the wrong experiment")
    requested = request.get("evaluations")
    if not isinstance(requested, list):
        raise TypeError("evaluation request requires an evaluations list")

    candidates = pending["candidates"]
    for candidate in candidates:
        candidate["evaluations"] = []
    available = {item["name"]: item for item in candidates}
    if pending.get("champion_available"):
        available["champion"] = {
            "name": "champion",
            "artifact": state["accepted_artifact"],
            "evaluations": [],
        }

    executed: list[dict] = list(pending.get("partial_evaluations", []))
    for item in executed:
        contender = available.get(item["candidate"])
        if contender is not None:
            contender.setdefault("evaluations", []).append(item["metrics"])

    def request_key(name: str, episodes: int, seed: int, label: str) -> tuple:
        return name, episodes, seed, label

    completed_keys = {
        request_key(
            item["candidate"],
            int(item["episodes"]),
            int(item["seed"]),
            item["label"],
        )
        for item in executed
    }
    try:
        for number, spec in enumerate(requested, start=1):
            if not isinstance(spec, dict):
                raise TypeError("each requested evaluation must be an object")
            name = str(spec.get("candidate", "")).strip()
            contender = available.get(name)
            if contender is None:
                raise ValueError(
                    f"unknown evaluation candidate {name!r}; "
                    f"choose from {sorted(available)}"
                )
            episodes = int(spec.get("episodes", EVALUATION_EPISODES))
            seed = int(spec.get("seed", EVALUATION_SEED))
            if episodes < 1:
                raise ValueError("evaluation episodes must be positive")
            label = str(spec.get("label", f"requested evaluation {number}: {name}"))
            key = request_key(name, episodes, seed, label)
            if key in completed_keys:
                announce(f"[evaluation] already complete; reusing {label}")
                continue
            output_path = CANDIDATE_ROOT / (
                f"evaluation-experiment-{experiment}-{number}.json"
            )
            metrics = evaluate_artifact(
                ROOT / contender["artifact"],
                seed,
                label=label,
                episodes=episodes,
                output_path=output_path,
            )
            output_path.unlink(missing_ok=True)
            clean_metrics = metrics_without_artifact_path([metrics])[0]
            contender.setdefault("evaluations", []).append(clean_metrics)
            executed.append(
                {
                    "candidate": name,
                    "episodes": episodes,
                    "seed": seed,
                    "label": label,
                    "metrics": clean_metrics,
                }
            )
            completed_keys.add(key)
            pending["partial_evaluations"] = executed
            atomic_write_json(STATE_PATH, state)
    except KeyboardInterrupt:
        announce(
            "[runner] Evaluation request paused. Completed measurements remain "
            "recorded in the pending request."
        )
        pending["partial_evaluations"] = executed
        atomic_write_json(STATE_PATH, state)
        return 130

    for candidate in candidates:
        evaluations = candidate.get("evaluations", [])
        candidate["summary"] = (
            summarize_evaluations(evaluations)
            if evaluations
            else None
        )

    champion_evaluations = available.get("champion", {}).get("evaluations", [])
    champion_summary = (
        summarize_evaluations(champion_evaluations)
        if champion_evaluations
        else None
    )

    result = pending["result"]
    result.update(
        {
            "status": "ok",
            "verdict": "measured as requested; awaiting researcher analysis",
            "decision_pending": True,
            "candidates": candidates,
            "requested_evaluations": executed,
        }
    )
    measured = [item for item in candidates if item.get("summary") is not None]
    if measured:
        primary = measured[0]["summary"]
        result["candidate_metrics"] = primary
        result["candidate_success_percent"] = primary["pooled_success_percent"]

    state["pending_researcher_decision"] = {
        "experiment": experiment,
        "candidates": candidates,
        "champion_available": bool(pending.get("champion_available")),
        "champion_summary": champion_summary,
        "parameters": pending["parameters"],
        "initialization": pending["initialization"],
        "training_budget_steps": pending["training_budget_steps"],
        "parent_training_steps": pending["parent_training_steps"],
        "code_parent_commit": pending.get("code_parent_commit"),
    }
    state["pending_evaluation_request"] = None
    state["last_experiment"] = experiment
    state["last_verdict"] = result["verdict"]
    if pending.get("baseline"):
        BASELINE_PENDING_PATH.unlink(missing_ok=True)
    atomic_write_json(STATE_PATH, state)
    append_result(result)
    EVALUATION_REQUEST_PATH.unlink(missing_ok=True)
    commit_result(experiment, str(result["change"]))
    announce("[result] requested evaluations complete; researcher analysis required")
    return 0


def metrics_without_artifact_path(evaluations: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in evaluation.items() if key != "model"}
        for evaluation in evaluations
    ]


def train_candidate(
    output_dir: Path,
    timesteps: int,
    seed: int,
    resume: Path | None,
    label: str = "candidate training",
    continue_timesteps: bool = False,
    target_timesteps: int | None = None,
) -> None:
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
    train_log = RESEARCH_DIR / "last_train.log"
    started = time.monotonic()
    announce(
        f"[train] {label} | seed {seed} | {timesteps:,} steps"
    )
    with train_log.open("w", encoding="utf-8") as log_file:
        log_file.write(f"\n=== {label} ===\n")
        log_file.flush()
        progress_offset = log_file.tell()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
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
                steps = latest_training_steps(
                    train_log, after_offset=progress_offset
                )
                if steps is None:
                    announce(
                        f"[train] starting ({format_duration(elapsed)} elapsed)"
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
                    announce(
                        f"[train] {steps:,} / {progress_target:,} steps "
                        f"({progress:.0f}%) | {format_duration(elapsed)} elapsed | "
                        f"ETA ~{format_duration(eta)}"
                    )
                stalled_for = time.monotonic() - last_progress_at
                if stalled_for > TRAIN_STALL_SECONDS:
                    announce("[train] no progress for 30 minutes; stopping.")
                    stop_process(process, graceful=False)
                    raise TimeoutError("training made no progress for 30 minutes")
                if elapsed > TRAIN_TIMEOUT_SECONDS:
                    announce("[train] 12 hour safety limit reached; stopping.")
                    stop_process(process, graceful=False)
                    raise TimeoutError("training exceeded the 12 hour safety limit")
        except KeyboardInterrupt:
            announce("\n[runner] Stopping training and waiting for it to close...")
            stop_process(process, graceful=True)
            raise
    write_training_summary()
    if process.returncode != 0:
        tail = train_log.read_text(encoding="utf-8").splitlines()[-15:]
        raise RuntimeError("training failed:\n" + "\n".join(tail))
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        if not (output_dir / filename).exists():
            raise RuntimeError(f"training output is incomplete: {filename}")
    announce(
        f"[train] {label} complete in {format_duration(time.monotonic() - started)}"
    )


def copy_artifact(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        shutil.copyfile(source / filename, destination / filename)
    replay_buffer = source / "replay_buffer.pkl"
    destination_replay = destination / "replay_buffer.pkl"
    if replay_buffer.exists():
        shutil.copyfile(replay_buffer, destination_replay)
    elif destination_replay.exists():
        destination_replay.unlink()


def copy_candidate_outputs(source: Path, destination: Path) -> None:
    copy_artifact(source, destination)
    final_checkpoint = source / "final_checkpoint"
    if final_checkpoint.exists():
        copy_artifact(final_checkpoint, destination / "final_checkpoint")
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
    resume: Path | None,
    config: dict,
) -> None:
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        if not (source / filename).exists():
            raise ValueError(f"reusable candidate is incomplete: {filename}")
    artifact = json.loads((source / "artifact.json").read_text(encoding="utf-8"))
    algorithm = str(config["algorithm"]["name"]).lower()
    n_envs = int(config["training"]["n_envs"])
    expected_params = dict(config[algorithm])
    if algorithm == "ppo":
        expected_params["n_steps"] = int(expected_params["n_steps"]) // n_envs
    expected_resume = resume.resolve() if resume is not None else None
    actual_resume = (
        Path(artifact["resumed_from"]).resolve()
        if artifact.get("resumed_from") is not None
        else None
    )
    checks = {
        "algorithm": artifact.get("algorithm") == algorithm,
        "seed": artifact.get("seed") == TRAIN_SEED,
        "requested timesteps": int(
            artifact.get("requested_timesteps", artifact.get("timesteps", -1))
        )
        == timesteps,
        "n_envs": artifact.get("n_envs") == n_envs,
        "parameters": artifact.get("parameters") == expected_params,
        "policy": artifact.get("policy") == config["policy"],
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


def apply_previous_result_decision(proposal: dict, state: dict) -> bool:
    pending = state.get("pending_researcher_decision")
    if pending is None:
        return False
    decision = proposal.get("previous_result_decision")
    if not isinstance(decision, dict):
        raise TypeError(
            "the previous experiment is awaiting a researcher decision; add "
            "previous_result_decision to the proposal"
        )
    if int(decision.get("experiment", -1)) != int(pending["experiment"]):
        raise ValueError("previous_result_decision references the wrong experiment")
    selected_name = str(decision.get("continue_from", "")).strip()
    reason = str(decision.get("reason", "")).strip()
    if not reason:
        raise ValueError("previous_result_decision requires a reason")

    selected_summary: dict | None = None
    if selected_name == "champion":
        artifact = ROOT / state["accepted_artifact"]
        if not artifact.exists():
            raise ValueError("there is no existing champion to continue from")
        selected_summary = state.get("accepted_metrics")
    else:
        selected = next(
            (
                item
                for item in pending["candidates"]
                if item["name"] == selected_name
            ),
            None,
        )
        if selected is None:
            choices = [item["name"] for item in pending["candidates"]]
            if pending.get("champion_available"):
                choices.append("champion")
            raise ValueError(f"continue_from must be one of {choices}")
        artifact = ROOT / selected["artifact"]
        copy_artifact(artifact, ACCEPTED_DIR)
        state["accepted_artifact"] = str(ACCEPTED_DIR.relative_to(ROOT))
        selected_summary = selected.get("summary")
        state["accepted_metrics"] = selected_summary
        state["accepted_parameters"] = pending["parameters"]
        if pending["initialization"] == "transfer":
            state["accepted_training_steps"] = int(
                pending.get("parent_training_steps", 0)
            ) + int(pending["training_budget_steps"])
        else:
            state["accepted_training_steps"] = int(pending["training_budget_steps"])

    code_decision = decision.get("code")
    if not isinstance(code_decision, dict):
        raise TypeError(
            "previous_result_decision requires a code decision with action and reason"
        )
    code_action = str(code_decision.get("action", "")).strip().lower()
    code_reason = str(code_decision.get("reason", "")).strip()
    if code_action not in {"keep", "revert", "revise"} or not code_reason:
        raise ValueError("code decision must be keep, revert, or revise with a reason")
    state["official_metrics"] = selected_summary
    state["last_lineage_decision"] = {
        "experiment": int(pending["experiment"]),
        "continue_from": selected_name,
        "reason": reason,
        "code": {"action": code_action, "reason": code_reason},
        "code_parent_commit": pending.get("code_parent_commit"),
    }
    state["pending_researcher_decision"] = None
    state["last_verdict"] = f"researcher selected {selected_name}"
    goal_reached = bool(
        selected_summary
        and int(selected_summary.get("episodes", 0)) >= EVALUATION_EPISODES
        and float(selected_summary.get("pooled_success_percent", 0.0))
        >= FINAL_SUCCESS_PERCENT
    )
    if goal_reached:
        GOAL_PATH.write_text(
            f"Goal reached with {selected_name} from experiment {pending['experiment']}.\n",
            encoding="utf-8",
        )
    atomic_write_json(STATE_PATH, state)
    announce(
        f"[researcher decision] continuing from {selected_name}: {reason}"
    )
    return goal_reached


def commit_result(index: int, change: str) -> None:
    control_files = {
        "research/proposal.json",
        "research/evaluation_request.json",
    }
    paths = [
        path
        for path in status_paths((".",))
        if path.replace("\\", "/") not in control_files
    ]
    stage_existing_or_tracked(paths)
    for control_file in control_files:
        git("reset", "--", control_file)
    if not git("diff", "--cached", "--name-only").strip():
        return
    git("commit", "-m", f"exp {index}: {change}")


def commit_lineage_decision(experiment: int, selected: str) -> None:
    paths = [
        "research/research_state.json",
        "research/checkpoints/accepted",
        "research/GOAL_REACHED",
    ]
    stage_existing_or_tracked(paths)
    if git("diff", "--cached", "--name-only").strip():
        git("commit", "-m", f"select experiment {experiment} lineage: {selected}")


def stage_existing_or_tracked(paths: list[str]) -> None:
    stageable = [
        path
        for path in dict.fromkeys(paths)
        if (ROOT / path).exists() or git("ls-files", "--", path).strip()
    ]
    if stageable:
        git("add", "-A", "--", *stageable)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--reuse-candidate", type=Path, default=None)
    parser.add_argument("--evaluate-pending", action="store_true")
    args = parser.parse_args()
    if args.evaluate_pending:
        return execute_pending_evaluations()
    if not PROPOSAL_PATH.exists():
        print("ERROR: research/proposal.json not found.")
        return 1

    proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    change = str(proposal["change"]).strip()
    hypothesis = str(proposal["hypothesis"]).strip()
    experiment_kind = str(proposal.get("kind", "training")).lower()
    parameter_overrides = proposal.get("params")
    baseline = bool(proposal.get("baseline", False))
    initialization = str(proposal.get("initialization", "transfer")).lower()
    index = next_index()
    fresh_baseline = baseline and initialization == "fresh"
    raw_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    decision_pending = raw_state.get("pending_researcher_decision") is not None
    state = load_state(
        allow_unmeasured=True,
        allow_missing_artifact=fresh_baseline or decision_pending,
    )
    if decision_pending:
        goal_reached = apply_previous_result_decision(proposal, state)
        pending_experiment = int(raw_state["pending_researcher_decision"]["experiment"])
        selected_lineage = str(
            proposal["previous_result_decision"]["continue_from"]
        )
        commit_lineage_decision(pending_experiment, selected_lineage)
        if goal_reached:
            PROPOSAL_PATH.unlink(missing_ok=True)
            return 0
    accepted_dir = ROOT / state["accepted_artifact"]
    candidate_dir = CANDIDATE_ROOT / f"experiment-{index}"
    created_candidate_dirs: list[Path] = []
    previous_config = load_experiment_config()
    code_parent_commit = git("rev-parse", "HEAD").strip()
    code_changes: list[str] = []
    preserve_proposal = False
    reused_candidate: Path | None = None

    announce(
        f"[runner] experiment {index} | goal: reach "
        f"{SUCCESS_THRESHOLD * 100:.1f} cm and hold {HOLD_SECONDS:.2f} s"
    )
    announce(f"[runner] mode: {'baseline' if baseline else initialization}")

    result = {
        "schema_version": 1,
        "index": index,
        "change": change,
        "hypothesis": hypothesis,
        "kind": experiment_kind,
        "family": str(proposal.get("family", "")).strip() or experiment_kind,
        "initialization": initialization,
        "parameter_changes": [],
        "code_changes": [],
        "status": "error",
        "verdict": "error",
    }
    try:
        code_changes = assert_research_surface()
        result["code_changes"] = code_changes
        if baseline and (parameter_overrides or code_changes):
            raise ValueError("baseline requires an unchanged research method")
        if not baseline and not parameter_overrides and not code_changes:
            raise ValueError("experiment contains no research change")
        if initialization not in {"transfer", "fresh"}:
            raise ValueError("initialization must be transfer or fresh")

        record_previous_postmortem(proposal, baseline=baseline)
        if parameter_overrides:
            announce("[checks] validating proposed parameters")
            validate_param_overrides(parameter_overrides)
            result["parameter_changes"] = parameter_change_records(
                previous_config, parameter_overrides
            )
            write_experiment_config(
                merge_param_overrides(previous_config, parameter_overrides)
            )
        result["family"] = experiment_family(
            proposal,
            experiment_kind,
            result["parameter_changes"],
            code_changes,
        )
        if code_changes:
            announce("[checks] running research-surface checks")
            python_changes = [
                path for path in code_changes if path.endswith(".py") and (ROOT / path).exists()
            ]
            if python_changes:
                run_module("ruff", "check", *python_changes)
            run_module(
                "pytest",
                "-q",
                "--basetemp",
                str(ROOT / ".pytest-run-temp"),
            )
            announce("[checks] passed")

        effective_config = load_experiment_config()
        effective_timesteps = training_budget(
            args.timesteps,
            initialization,
            fresh_baseline,
            int(state.get("accepted_training_steps", args.timesteps)),
        )
        result["training_budget_steps"] = effective_timesteps
        announce(f"[training plan] {effective_timesteps:,} steps")
        resume = accepted_dir / "model.zip" if initialization == "transfer" else None

        if candidate_dir.exists():
            announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            remove_candidate_dir(candidate_dir)
        if args.reuse_candidate is not None:
            reusable = args.reuse_candidate.resolve()
            reused_candidate = reusable
            validate_reusable_candidate(
                reusable,
                timesteps=effective_timesteps,
                resume=resume,
                config=effective_config,
            )
            artifact = json.loads(
                (reusable / "artifact.json").read_text(encoding="utf-8")
            )
            completed_timesteps = int(artifact["timesteps"])
            if bool(artifact.get("completed", True)):
                announce(f"[recovery] reusing completed candidate from {reusable}")
                copy_candidate_outputs(reusable, candidate_dir)
            else:
                remaining_timesteps = max(
                    effective_timesteps - completed_timesteps, 0
                )
                if remaining_timesteps == 0:
                    announce(
                        "[recovery] interrupted training already reached its budget"
                    )
                    copy_candidate_outputs(reusable, candidate_dir)
                else:
                    announce(
                        f"[recovery] resuming at {completed_timesteps:,} / "
                        f"{effective_timesteps:,} steps"
                    )
                    created_candidate_dirs.append(candidate_dir)
                    train_candidate(
                        candidate_dir,
                        remaining_timesteps,
                        TRAIN_SEED,
                        reusable / "final_checkpoint" / "model.zip",
                        label=(
                            "resumed baseline training"
                            if baseline
                            else "resumed candidate training"
                        ),
                        continue_timesteps=True,
                        target_timesteps=effective_timesteps,
                    )
        else:
            created_candidate_dirs.append(candidate_dir)
            train_candidate(
                candidate_dir,
                effective_timesteps,
                TRAIN_SEED,
                resume,
                label="baseline training" if baseline else "candidate training",
            )
        contenders = [
            {
                "name": path.name,
                "kind": "candidate",
                "path": path,
                "timesteps": int(
                    json.loads(
                        (path / "artifact.json").read_text(encoding="utf-8")
                    )["timesteps"]
                ),
                "evaluations": [],
            }
            for path in candidate_directories(candidate_dir)
        ]
        archived_candidates = archive_candidates(
            index, contenders, effective_config
        )
        verdict = "trained; awaiting researcher evaluation request"

        state.update(
            {
                "last_experiment": index,
                "last_verdict": verdict,
                "pending_evaluation_request": {
                    "experiment": index,
                    "candidates": archived_candidates,
                    "champion_available": not fresh_baseline,
                    "parameters": effective_config,
                    "initialization": initialization,
                    "training_budget_steps": effective_timesteps,
                    "parent_training_steps": int(
                        state.get("accepted_training_steps", 0)
                    ),
                    "baseline": baseline,
                    "code_parent_commit": code_parent_commit,
                    "result": result,
                },
            }
        )
        result.update({"status": "trained", "verdict": verdict})
        if args.reuse_candidate is not None:
            RECOVERY_PENDING_PATH.unlink(missing_ok=True)
        RESTART_PENDING_PATH.unlink(missing_ok=True)
        atomic_write_json(STATE_PATH, state)
        commit_result(index, change)
        announce(f"[result] {verdict}")
    except KeyboardInterrupt:
        recovery_dir = CANDIDATE_ROOT / f"recovery-experiment-{index}"
        recoverable = all(
            (candidate_dir / filename).exists()
            for filename in ("model.zip", "vecnormalize.pkl", "artifact.json")
        )
        if recoverable:
            if recovery_dir.exists():
                remove_candidate_dir(recovery_dir)
            candidate_dir.replace(recovery_dir)
            RECOVERY_PENDING_PATH.write_text(
                str(recovery_dir.relative_to(ROOT)) + "\n", encoding="utf-8"
            )
            preserve_proposal = True
            announce(
                "[runner] Experiment paused. The latest complete training state "
                "was saved and will resume on the next launch."
            )
        else:
            preserve_proposal = True
            if reused_candidate is not None and RECOVERY_PENDING_PATH.exists():
                announce(
                    "[runner] No newer complete state was produced; the previous "
                    "recovery checkpoint remains available for the next launch."
                )
            else:
                RESTART_PENDING_PATH.write_text(
                    "Restart the preserved proposal from the beginning.\n",
                    encoding="utf-8",
                )
                announce(
                    "[runner] Experiment stopped before a recoverable training "
                    "state was produced; the same experiment will restart from "
                    "the beginning."
                )
        return 130
    except Exception as error:  # noqa: BLE001
        result["error"] = str(error)[:500]
        result["verdict"] = "invalid; researcher changes preserved"
        append_result(result)
        atomic_write_json(STATE_PATH, state)
        commit_result(index, change)
        print("SUMMARY: " + json.dumps(result))
        return 1
    finally:
        if not preserve_proposal:
            PROPOSAL_PATH.unlink(missing_ok=True)
        cleanup_targets = created_candidate_dirs or [candidate_dir]
        for cleanup_target in cleanup_targets:
            try:
                remove_candidate_dir(cleanup_target)
            except OSError as cleanup_error:
                announce(f"[runner] WARNING: candidate cleanup failed: {cleanup_error}")
        if (
            reused_candidate is not None
            and not RECOVERY_PENDING_PATH.exists()
            and reused_candidate.exists()
        ):
            remove_candidate_dir(reused_candidate)

    print("SUMMARY: " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
