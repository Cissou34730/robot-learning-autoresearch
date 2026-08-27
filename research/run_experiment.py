"""Transactional autonomous-research runner for the robot curriculum."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from research.build_research_brief import write_training_summary
from robot_learning.benchmark.spec import (
    EVALUATION_EPISODES,
    EVALUATION_SEED,
    FINAL_STAGE_INDEX,
    FINAL_SUCCESS_PERCENT,
    STAGE_PROMOTION_PERCENT,
    stage_spec,
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
STATE_PATH = RESEARCH_DIR / "research_state.json"
BASELINE_PENDING_PATH = RESEARCH_DIR / "BASELINE_PENDING"
RECOVERY_PENDING_PATH = RESEARCH_DIR / "RECOVERY_PENDING"
GOAL_PATH = RESEARCH_DIR / "GOAL_REACHED"
ACCEPTED_DIR = RESEARCH_DIR / "checkpoints" / "accepted"
STAGE_ARCHIVE_DIR = RESEARCH_DIR / "checkpoints" / "stages"
CANDIDATE_ROOT = ROOT / "models" / "candidates"

MUTABLE_PATHS = (
    "robot_learning/rewards",
    "robot_learning/train.py",
    "robot_learning/training/observations.py",
    "robot_learning/training/selection_callback.py",
    "tests/research",
)
IMMUTABLE_PATHS = (
    "robot_learning/benchmark",
    "robot_learning/environments/reach_env.py",
    "robot_learning/evaluate.py",
    "robot_learning/robots",
    "robot_learning/training/algorithms.py",
    "robot_learning/training/normalization.py",
    "robot_learning/training/research_config.py",
    "research/run_experiment.py",
    "tests/benchmark",
)

TIMESTEPS = 120_000
TRAIN_SEED = 0
TRAIN_TIMEOUT_SECONDS = 30 * 60
STATUS_INTERVAL_SECONDS = 15
INTERRUPT_GRACE_SECONDS = 30
CONFIRMATION_SEEDS = (3000, 5000)


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


def latest_training_steps(log_path: Path) -> int | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
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


def load_state(*, allow_unmeasured: bool = False) -> dict:
    if not STATE_PATH.exists():
        raise RuntimeError("research state is missing; refusing to run")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    required = {"schema_version", "current_stage", "accepted_artifact"}
    missing = required - set(state)
    if missing:
        raise RuntimeError(f"research state is incomplete: {sorted(missing)}")
    if state["schema_version"] != 2:
        raise RuntimeError("unsupported research state schema")
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


def path_is_within(path: str, roots: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        normalized == root or normalized.startswith(root.rstrip("/") + "/")
        for root in roots
    )


def assert_research_surface() -> list[str]:
    changed = status_paths((".",))
    allowed_control = {"research/proposal.json"}
    unexpected = [
        path
        for path in changed
        if path not in allowed_control and not path_is_within(path, MUTABLE_PATHS)
    ]
    if unexpected:
        raise ValueError(f"changes outside the research surface: {unexpected}")
    return [path for path in changed if path_is_within(path, MUTABLE_PATHS)]


def clean_mutable_changes() -> None:
    tracked = git("diff", "--name-only", "--", *MUTABLE_PATHS).splitlines()
    tracked += git("diff", "--cached", "--name-only", "--", *MUTABLE_PATHS).splitlines()
    if tracked:
        git("restore", "--staged", "--worktree", "--", *sorted(set(tracked)))
    untracked = git(
        "ls-files", "--others", "--exclude-standard", "--", *MUTABLE_PATHS
    ).splitlines()
    allowed_roots = [(ROOT / path).resolve() for path in MUTABLE_PATHS]
    for relative in untracked:
        target = (ROOT / relative).resolve()
        if not any(target == root or root in target.parents for root in allowed_roots):
            raise RuntimeError(f"refusing to remove unexpected path: {target}")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


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


def append_result(result: dict) -> None:
    with RESULTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")
    def cell(value: object) -> str:
        return " ".join(str(value).replace("|", "/").split())

    row = (
        f"| {result['index']} | {time.strftime('%Y-%m-%d')} | "
        f"{cell(result['change'])} | {cell(result['hypothesis'])} | "
        f"{cell(result.get('final_success_percent', '-'))} | "
        f"{cell(result.get('closest_distance_cm', '-'))} | "
        f"stage {cell(result.get('stage_index', '-'))} | "
        f"{cell(result['verdict'])} |"
    )
    text = LOG_PATH.read_text(encoding="utf-8").rstrip("\n") + "\n" + row + "\n"
    LOG_PATH.write_text(text, encoding="utf-8")


def evaluate_artifact(
    artifact_dir: Path,
    stage_index: int,
    seed: int = EVALUATION_SEED,
    label: str = "official evaluation",
) -> dict:
    output_path = RESEARCH_DIR / "last_evaluation.json"
    output_path.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "robot_learning.evaluate",
        "--model",
        str(artifact_dir / "model.zip"),
        "--stage-index",
        str(stage_index),
        "--episodes",
        str(EVALUATION_EPISODES),
        "--seed",
        str(seed),
        "--output-json",
        str(output_path),
    ]
    announce(
        f"[evaluation] {label} | {EVALUATION_EPISODES} episodes | seed {seed}"
    )
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
                announce(
                    f"[evaluation] {label} still running "
                    f"({format_duration(time.monotonic() - started)} elapsed)"
                )
                if time.monotonic() - started > 10 * 60:
                    stop_process(process, graceful=False)
                    raise TimeoutError(f"{label} exceeded the 10 minute safety limit")
    except KeyboardInterrupt:
        announce(f"\n[runner] Stopping {label}...")
        stop_process(process, graceful=True)
        raise
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{stdout[-2000:]}\n{stderr[-2000:]}")
    metrics = json.loads(output_path.read_text(encoding="utf-8"))
    announce(
        f"[evaluation] {label} complete in "
        f"{format_duration(time.monotonic() - started)} | "
        f"stage {stage_index}: {metrics['current_stage_success_percent']:.1f}% | "
        f"closest median: {metrics['closest_distance_cm']['median']:.2f} cm"
    )
    return metrics


def rank(metrics: dict, stage_index: int) -> tuple[float, float]:
    return (
        float(metrics["stage_success_percent"][stage_index]),
        -float(metrics["closest_distance_cm"]["median"]),
    )


def no_regression(candidate: dict, accepted: dict, stage_index: int) -> bool:
    return all(
        candidate["stage_success_percent"][index]
        >= accepted["stage_success_percent"][index]
        for index in range(stage_index)
    )


def train_candidate(
    output_dir: Path,
    stage_index: int,
    timesteps: int,
    seed: int,
    resume: Path | None,
    label: str = "candidate training",
) -> None:
    command = [
        sys.executable,
        "-m",
        "robot_learning.train",
        "--timesteps",
        str(timesteps),
        "--seed",
        str(seed),
        "--stage-index",
        str(stage_index),
        "--output-dir",
        str(output_dir),
    ]
    if resume is not None:
        command.extend(["--resume", str(resume)])
    train_log = RESEARCH_DIR / "last_train.log"
    started = time.monotonic()
    announce(
        f"[train] {label} | stage {stage_index} | seed {seed} | "
        f"{timesteps:,} steps"
    )
    with train_log.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            **process_group_options(),
        )
        last_selection: tuple[int, float, float] | None = None
        try:
            while process.poll() is None:
                try:
                    process.wait(timeout=STATUS_INTERVAL_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
                elapsed = time.monotonic() - started
                steps = latest_training_steps(train_log)
                if steps is None:
                    announce(
                        f"[train] starting ({format_duration(elapsed)} elapsed)"
                    )
                else:
                    progress = min(100.0, 100 * steps / timesteps)
                    eta = elapsed * max(timesteps - steps, 0) / steps if steps else 0
                    announce(
                        f"[train] {steps:,} / {timesteps:,} steps "
                        f"({progress:.0f}%) | {format_duration(elapsed)} elapsed | "
                        f"ETA ~{format_duration(eta)}"
                    )
                selection_path = output_dir / "best_selection.json"
                if selection_path.exists():
                    selection = json.loads(selection_path.read_text(encoding="utf-8"))
                    current_selection = (
                        int(selection["timesteps"]),
                        float(selection["success_percent"]),
                        float(selection["closest_distance_cm"]),
                    )
                    if current_selection != last_selection:
                        announce(
                            f"[selection] new best at {current_selection[0]:,} steps | "
                            f"stage {stage_index}: {current_selection[1]:.1f}% | "
                            f"closest median: {current_selection[2]:.2f} cm"
                        )
                        last_selection = current_selection
                if elapsed > TRAIN_TIMEOUT_SECONDS:
                    announce("[train] 30 minute safety limit reached; stopping.")
                    stop_process(process, graceful=False)
                    raise TimeoutError("training exceeded the 30 minute safety limit")
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


def validate_reusable_candidate(
    source: Path,
    *,
    stage_index: int,
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
        "stage": artifact.get("stage_index") == stage_index,
        "seed": artifact.get("seed") == TRAIN_SEED,
        "timesteps": artifact.get("timesteps") == timesteps,
        "n_envs": artifact.get("n_envs") == n_envs,
        "parameters": artifact.get("parameters") == expected_params,
        "policy": artifact.get("policy") == config["policy"],
        "resume checkpoint": actual_resume == expected_resume,
    }
    mismatches = [name for name, matches in checks.items() if not matches]
    if mismatches:
        raise ValueError(
            "reusable candidate does not match this experiment: "
            + ", ".join(mismatches)
        )


def confirm_promotion(artifact_dir: Path, stage_index: int) -> tuple[bool, list[dict]]:
    evaluations = [
        evaluate_artifact(
            artifact_dir,
            stage_index,
            seed,
            label=f"promotion confirmation {number}/{len(CONFIRMATION_SEEDS)}",
        )
        for number, seed in enumerate(CONFIRMATION_SEEDS, start=1)
    ]
    passed = all(
        result["current_stage_success_percent"] >= STAGE_PROMOTION_PERCENT
        for result in evaluations
    )
    return passed, evaluations


def commit_result(index: int, change: str) -> None:
    paths = [
        "research/EXPERIMENTS.md",
        "research/results.jsonl",
        "research/research_state.json",
        "research/current_params.json",
        "research/checkpoints",
    ]
    if BASELINE_PENDING_PATH.exists() or git("ls-files", "research/BASELINE_PENDING").strip():
        paths.append("research/BASELINE_PENDING")
    paths.extend(MUTABLE_PATHS)
    git("add", "-A", "--", *paths)
    if not git("diff", "--cached", "--name-only").strip():
        return
    git("commit", "-m", f"exp {index}: {change}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--reuse-candidate", type=Path, default=None)
    args = parser.parse_args()
    if not PROPOSAL_PATH.exists():
        print("ERROR: research/proposal.json not found.")
        return 1

    proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    change = str(proposal["change"]).strip()
    hypothesis = str(proposal["hypothesis"]).strip()
    parameter_overrides = proposal.get("params")
    baseline = bool(proposal.get("baseline", False))
    initialization = str(proposal.get("initialization", "transfer")).lower()
    index = next_index()
    state = load_state(allow_unmeasured=baseline)
    stage_index = int(state["current_stage"])
    accepted_dir = ROOT / state["accepted_artifact"]
    candidate_dir = CANDIDATE_ROOT / f"experiment-{index}"
    previous_config = load_experiment_config()
    config_written = False
    code_changes: list[str] = []

    target_m, hold_seconds = stage_spec(stage_index)
    announce(
        f"[runner] experiment {index} | stage {stage_index}: "
        f"reach {target_m * 100:.1f} cm and hold {hold_seconds:.2f} s"
    )
    announce(f"[runner] mode: {'baseline' if baseline else initialization}")

    result = {
        "schema_version": 1,
        "index": index,
        "change": change,
        "hypothesis": hypothesis,
        "stage_index": stage_index,
        "status": "error",
        "verdict": "error",
    }
    try:
        code_changes = assert_research_surface()
        if baseline and (parameter_overrides or code_changes):
            raise ValueError("baseline requires an unchanged research method")
        if parameter_overrides and code_changes:
            raise ValueError("use parameter mode or code mode, not both")
        if not baseline and not parameter_overrides and not code_changes:
            raise ValueError("experiment contains no research change")
        if initialization not in {"transfer", "fresh"}:
            raise ValueError("initialization must be transfer or fresh")
        if (
            initialization == "transfer"
            and parameter_overrides
            and parameter_overrides.get("policy")
        ):
            raise ValueError("policy architecture changes require fresh initialization")

        if parameter_overrides:
            announce("[checks] validating proposed parameters")
            validate_param_overrides(parameter_overrides)
            write_experiment_config(
                merge_param_overrides(previous_config, parameter_overrides)
            )
            config_written = True
        else:
            announce("[checks] running research-surface checks")
            run_module("ruff", "check", *MUTABLE_PATHS)
            run_module(
                "pytest",
                "-q",
                "--basetemp",
                str(ROOT / ".pytest-run-temp"),
            )
            announce("[checks] passed")

        accepted_metrics = state.get("accepted_metrics")
        if accepted_metrics is None:
            accepted_metrics = evaluate_artifact(
                accepted_dir, stage_index, label="accepted-policy baseline"
            )
            state["accepted_metrics"] = accepted_metrics
            state["accepted_parameters"] = previous_config

        resume = accepted_dir / "model.zip" if initialization == "transfer" else None
        if candidate_dir.exists():
            announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            remove_candidate_dir(candidate_dir)
        if args.reuse_candidate is not None:
            if not baseline:
                raise ValueError("candidate reuse is restricted to baseline recovery")
            reusable = args.reuse_candidate.resolve()
            validate_reusable_candidate(
                reusable,
                stage_index=stage_index,
                timesteps=args.timesteps,
                resume=resume,
                config=load_experiment_config(),
            )
            announce(f"[recovery] reusing completed candidate from {reusable}")
            copy_artifact(reusable, candidate_dir)
        else:
            train_candidate(
                candidate_dir,
                stage_index,
                args.timesteps,
                TRAIN_SEED,
                resume,
                label="baseline training" if baseline else "candidate training",
            )
        runtime_benchmark_changes = status_paths(IMMUTABLE_PATHS)
        if runtime_benchmark_changes:
            raise RuntimeError(
                "training modified protected benchmark files: "
                f"{runtime_benchmark_changes}"
            )
        candidate_metrics = evaluate_artifact(
            candidate_dir, stage_index, label="candidate evaluation"
        )
        improved = rank(candidate_metrics, stage_index) > rank(
            accepted_metrics, stage_index
        ) and no_regression(candidate_metrics, accepted_metrics, stage_index)

        active_dir = candidate_dir if improved else accepted_dir
        active_metrics = candidate_metrics if improved else accepted_metrics
        promoted = False
        confirmations: dict[str, list[dict]] = {"evaluation": []}
        if active_metrics["current_stage_success_percent"] >= STAGE_PROMOTION_PERCENT:
            announce("[confirmation] promotion threshold reached; confirming result")
            target_passed, confirmations["evaluation"] = confirm_promotion(
                active_dir, stage_index
            )
            promoted = target_passed

        if improved:
            copy_artifact(candidate_dir, ACCEPTED_DIR)
            state["accepted_artifact"] = str(ACCEPTED_DIR.relative_to(ROOT))
            state["accepted_metrics"] = candidate_metrics
            state["accepted_parameters"] = load_experiment_config()
            verdict = "kept"
        else:
            verdict = "reverted (no improvement)"
            if config_written:
                write_experiment_config(previous_config)
            if code_changes:
                clean_mutable_changes()

        active_dir = ACCEPTED_DIR if improved else accepted_dir
        if promoted:
            archive = STAGE_ARCHIVE_DIR / f"stage-{stage_index:02d}"
            copy_artifact(active_dir, archive)
            if stage_index < FINAL_STAGE_INDEX:
                state["current_stage"] = stage_index + 1
                verdict += f"; promoted to stage {stage_index + 1}"
            elif active_metrics["final_success_percent"] >= FINAL_SUCCESS_PERCENT:
                GOAL_PATH.write_text(
                    f"Goal reached at experiment {index}.\n", encoding="utf-8"
                )
                verdict += "; goal reached"

        state.update(
            {
                "last_experiment": index,
                "last_verdict": verdict,
                "last_metrics": candidate_metrics,
            }
        )
        result.update(
            {
                "status": "ok",
                "verdict": verdict,
                "accepted": improved,
                "promoted": promoted,
                "candidate_metrics": candidate_metrics,
                "confirmation_metrics": confirmations,
                "final_success_percent": candidate_metrics[
                    "final_success_percent"
                ],
                "current_stage_success_percent": candidate_metrics[
                    "current_stage_success_percent"
                ],
                "closest_distance_cm": candidate_metrics[
                    "closest_distance_cm"
                ]["median"],
            }
        )
        if baseline:
            BASELINE_PENDING_PATH.unlink(missing_ok=True)
            RECOVERY_PENDING_PATH.unlink(missing_ok=True)
        atomic_write_json(STATE_PATH, state)
        append_result(result)
        commit_result(index, change)
        announce(f"[decision] {verdict}")
    except KeyboardInterrupt:
        if config_written:
            write_experiment_config(previous_config)
        if code_changes:
            clean_mutable_changes()
        announce(
            "[runner] Interrupted by user. No candidate was accepted and the "
            "baseline remains pending."
        )
        return 130
    except Exception as error:  # noqa: BLE001
        if config_written:
            write_experiment_config(previous_config)
        if code_changes:
            clean_mutable_changes()
        result["error"] = str(error)[:500]
        result["verdict"] = f"error: {str(error)[:120]}"
        append_result(result)
        atomic_write_json(STATE_PATH, state)
        commit_result(index, change)
        print("SUMMARY: " + json.dumps(result))
        return 1
    finally:
        PROPOSAL_PATH.unlink(missing_ok=True)
        try:
            remove_candidate_dir(candidate_dir)
        except OSError as cleanup_error:
            announce(f"[runner] WARNING: candidate cleanup failed: {cleanup_error}")

    print("SUMMARY: " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
