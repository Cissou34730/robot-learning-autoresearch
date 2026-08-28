"""Transactional autonomous-research runner for robot learning."""

import argparse
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
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
from robot_learning.training.comparison import paired_comparison
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
CANDIDATE_ROOT = ROOT / "models" / "candidates"

MUTABLE_CODE_PATHS = (
    "robot_learning/rewards",
    "robot_learning/train.py",
    "robot_learning/training/observations.py",
    "robot_learning/training/comparison.py",
    "robot_learning/training/selection_callback.py",
    "tests/research",
)
MUTABLE_PATHS = ("research/current_params.json", *MUTABLE_CODE_PATHS)
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
CALIBRATION_TRAIN_SEEDS = (0, 1, 2)
TRAIN_TIMEOUT_SECONDS = 12 * 60 * 60
TRAIN_STALL_SECONDS = 30 * 60
STATUS_INTERVAL_SECONDS = 15
INTERRUPT_GRACE_SECONDS = 30
SELECTION_METHOD_VERSION = 4
# Development selection uses seed 2000 and the immutable reported benchmark uses
# EVALUATION_SEED (1000). Tournament data must be disjoint from both.
TOURNAMENT_SEEDS = (3000, 5000, 7000)
EXTENDED_TOURNAMENT_SEEDS = (9000, 11000)
PAIRED_SIGNIFICANCE_LEVEL = 0.05
SELECTION_SEED = 2000


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
    if initialization == "fresh" and not baseline:
        return max(standard_timesteps, accepted_training_steps)
    return standard_timesteps


def comparison_label(entry: dict) -> str:
    comparison = entry.get("paired_vs_reference")
    if comparison is None:
        return "time-diverse"
    if comparison["exact_p_value"] > PAIRED_SIGNIFICANCE_LEVEL:
        return "equivalent"
    return "better" if comparison["net_wins"] > 0 else "worse"


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
    ]
    announce(
        f"[evaluation] {label} | {episodes} episodes | seed {seed}"
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


def summarize_tournament(
    evaluations: list[dict],
    selection_method_version: int = SELECTION_METHOD_VERSION,
) -> dict:
    if not evaluations:
        raise ValueError("a tournament summary requires at least one evaluation")
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
        "selection_method_version": selection_method_version,
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


def summarize_noise_floor(replicates: list[dict]) -> dict:
    scores = [float(item["summary"]["pooled_success_percent"]) for item in replicates]
    if len(scores) < 2:
        raise ValueError("noise calibration requires at least two training replicates")
    return {
        "training_seeds": [int(item["training_seed"]) for item in replicates],
        "pooled_success_percent": scores,
        "pooled_success_mean_percent": statistics.mean(scores),
        "pooled_success_std_pp": statistics.stdev(scores),
        "pooled_success_range_pp": max(scores) - min(scores),
    }


def rank(metrics: dict) -> tuple[float, float, float, float, float, float]:
    progress = metrics["failed_episode_progress"]
    return (
        float(metrics["seeds_passing_98_percent"]),
        float(metrics["worst_seed_success_percent"]),
        float(metrics["pooled_success_percent"]),
        float(progress["longest_consecutive_steps_mean"]),
        float(progress["best_window_inside_steps_mean"]),
        -float(progress["best_window_excess_cm_mean"]),
    )


def tournament_result_is_close(first: dict, second: dict) -> bool:
    return (
        first["seeds_passing_98_percent"]
        == second["seeds_passing_98_percent"]
        and abs(
            first["worst_seed_success_percent"]
            - second["worst_seed_success_percent"]
        )
        <= 0.5
        and abs(first["pooled_success_percent"] - second["pooled_success_percent"])
        <= 0.5
    )


def finalist_directories(candidate_dir: Path) -> list[Path]:
    manifest_path = candidate_dir / "selection_manifest.json"
    if not manifest_path.exists():
        return [candidate_dir]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    finalists = [candidate_dir / item["path"] for item in manifest["finalists"]]
    if not 1 <= len(finalists) <= 3:
        raise RuntimeError("training must produce between one and three finalists")
    for finalist in finalists:
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            if not (finalist / filename).exists():
                raise RuntimeError(f"finalist is incomplete: {finalist / filename}")
    return finalists


def select_tournament_winner(
    contenders: list[dict], noise_floor_pp: float = 0.0
) -> dict:
    champion = next(
        (item for item in contenders if item["kind"] == "champion"), None
    )
    if champion is None:
        return max(contenders, key=lambda item: rank(item["summary"]))

    eligible = [
        item
        for item in contenders
        if item["kind"] == "candidate"
        and item.get("paired_vs_champion", {}).get("net_wins", 0) > 0
        and item["paired_vs_champion"]["success_delta_percent"] > noise_floor_pp
        and item["paired_vs_champion"]["exact_p_value"]
        <= PAIRED_SIGNIFICANCE_LEVEL
    ]
    if not eligible:
        return champion
    return max(
        eligible,
        key=lambda item: (
            item["paired_vs_champion"]["net_wins"],
            rank(item["summary"]),
        ),
    )


def evaluate_tournament(
    contenders: list[dict],
    selection_method_version: int,
    noise_floor_pp: float = 0.0,
    *,
    extend_close: bool = True,
) -> tuple[list[dict], dict]:
    seeds = list(TOURNAMENT_SEEDS)

    def evaluate_missing(active_seeds: list[int]) -> None:
        for contender in contenders:
            completed = {item["seed"] for item in contender["evaluations"]}
            for seed in active_seeds:
                if seed not in completed:
                    contender["evaluations"].append(
                        evaluate_artifact(
                            contender["path"],
                            seed,
                            label=f"tournament {contender['name']} seed {seed}",
                        )
                    )
            contender["summary"] = summarize_tournament(
                contender["evaluations"], selection_method_version
            )

    def attach_pairing() -> None:
        champion = next(
            (item for item in contenders if item["kind"] == "champion"), None
        )
        if champion is None:
            return
        for contender in contenders:
            if contender["kind"] == "candidate":
                contender["paired_vs_champion"] = paired_comparison(
                    contender["evaluations"], champion["evaluations"]
                )

    evaluate_missing(seeds)
    attach_pairing()
    ordered = sorted(contenders, key=lambda item: rank(item["summary"]), reverse=True)
    positive_but_uncertain = any(
        item.get("paired_vs_champion", {}).get("net_wins", 0) > 0
        and item["paired_vs_champion"]["exact_p_value"]
        > PAIRED_SIGNIFICANCE_LEVEL
        for item in contenders
    )
    if extend_close and len(ordered) > 1 and (
        tournament_result_is_close(ordered[0]["summary"], ordered[1]["summary"])
        or positive_but_uncertain
    ):
        announce("[tournament] leading models are close; extending evaluation")
        seeds.extend(EXTENDED_TOURNAMENT_SEEDS)
        evaluate_missing(seeds)
        attach_pairing()

    winner = select_tournament_winner(contenders, noise_floor_pp)
    return contenders, winner


def archive_candidate(
    index: int,
    contender: dict,
    config: dict,
    tournament: list[dict],
) -> Path:
    destination = RESEARCH_DIR / "checkpoints" / "challengers" / f"experiment-{index}"
    if destination.exists():
        raise RuntimeError(f"challenger archive already exists: {destination}")
    copy_artifact(contender["path"], destination)
    atomic_write_json(destination / "parameters.json", config)
    atomic_write_json(
        destination / "tournament.json",
        {
            "schema_version": 1,
            "selection_method_version": contender["summary"][
                "selection_method_version"
            ],
            "selected_candidate": contender["name"],
            "summary": contender["summary"],
            "contenders": [
                {
                    "name": item["name"],
                    "kind": item["kind"],
                    "summary": item["summary"],
                    "paired_vs_champion": item.get("paired_vs_champion"),
                }
                for item in tournament
            ],
        },
    )
    return destination


def archive_calibration(index: int, replicates: list[dict], noise_floor: dict) -> Path:
    destination = RESEARCH_DIR / "checkpoints" / "calibrations" / f"experiment-{index}"
    if destination.exists():
        raise RuntimeError(f"calibration archive already exists: {destination}")
    destination.mkdir(parents=True)
    for replicate in replicates:
        copy_artifact(
            replicate["path"], destination / f"seed-{replicate['training_seed']}"
        )
    atomic_write_json(
        destination / "calibration.json",
        {
            "schema_version": 1,
            "noise_floor": noise_floor,
            "replicates": [
                {
                    "training_seed": item["training_seed"],
                    "summary": item["summary"],
                }
                for item in replicates
            ],
        },
    )
    return destination


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
    selection_reference_path: Path | None = None,
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
        "--output-dir",
        str(output_dir),
    ]
    if resume is not None:
        command.extend(["--resume", str(resume)])
    if selection_reference_path is not None:
        command.extend(
            ["--selection-reference-json", str(selection_reference_path)]
        )
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
        last_selection: tuple | None = None
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
                    progress = min(100.0, 100 * steps / timesteps)
                    eta = elapsed * max(timesteps - steps, 0) / steps if steps else 0
                    announce(
                        f"[train] {steps:,} / {timesteps:,} steps "
                        f"({progress:.0f}%) | {format_duration(elapsed)} elapsed | "
                        f"ETA ~{format_duration(eta)}"
                    )
                selection_path = output_dir / "selection_update.json"
                if selection_path.exists():
                    selection = json.loads(selection_path.read_text(encoding="utf-8"))
                    selection_metrics = selection["metrics"]
                    failure_progress = selection_metrics["failed_episode_progress"]
                    paired = selection.get("paired_vs_reference")
                    current_selection = (
                        int(selection["timesteps"]),
                        str(selection["status"]),
                        float(selection_metrics["success_percent"]),
                        int(failure_progress["failed_episodes"]),
                        int(paired["candidate_wins"]) if paired else 0,
                        int(paired["reference_wins"]) if paired else 0,
                        float(paired["exact_p_value"]) if paired else 1.0,
                    )
                    if current_selection != last_selection:
                        announce(
                            f"[selection] {current_selection[0]:,} steps | "
                            f"{current_selection[1]} | "
                            f"success: {current_selection[2]:.1f}% | "
                            f"failures: {current_selection[3]} | "
                            f"paired wins candidate/reference: "
                            f"{current_selection[4]}/{current_selection[5]} | "
                            f"p={current_selection[6]:.3f}"
                        )
                        last_selection = current_selection
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
    manifest_path = output_dir / "selection_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        finalists = ", ".join(
            f"{item['timesteps']:,} ({comparison_label(item)})"
            for item in manifest["finalists"]
        )
        announce(f"[selection] final tournament checkpoints: {finalists}")
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
    manifest_path = source / "selection_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    shutil.copyfile(manifest_path, destination / "selection_manifest.json")
    for finalist in manifest["finalists"]:
        relative = Path(finalist["path"])
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


def commit_result(index: int, change: str) -> None:
    paths = [
        "research/EXPERIMENTS.md",
        "research/results.jsonl",
        "research/research_state.json",
        "research/current_params.json",
        "research/postmortems.md",
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
    experiment_kind = str(proposal.get("kind", "training")).lower()
    parameter_overrides = proposal.get("params")
    baseline = bool(proposal.get("baseline", False))
    initialization = str(proposal.get("initialization", "transfer")).lower()
    index = next_index()
    fresh_baseline = baseline and initialization == "fresh"
    state = load_state(
        allow_unmeasured=baseline,
        allow_missing_artifact=fresh_baseline,
    )
    accepted_dir = ROOT / state["accepted_artifact"]
    candidate_dir = CANDIDATE_ROOT / f"experiment-{index}"
    created_candidate_dirs: list[Path] = []
    previous_config = load_experiment_config()
    selection_reference_path: Path | None = None
    config_written = False
    code_changes: list[str] = []

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
        "status": "error",
        "verdict": "error",
    }
    try:
        code_changes = assert_research_surface()
        if experiment_kind not in {"training", "method", "calibration"}:
            raise ValueError("experiment kind must be training, method, or calibration")
        if baseline and experiment_kind != "training":
            raise ValueError("a baseline must be a training experiment")
        if experiment_kind == "calibration" and (parameter_overrides or code_changes):
            raise ValueError("A/A calibration requires an unchanged training recipe")
        if baseline and (parameter_overrides or code_changes):
            raise ValueError("baseline requires an unchanged research method")
        if (
            not baseline
            and experiment_kind != "calibration"
            and not parameter_overrides
            and not code_changes
        ):
            raise ValueError("experiment contains no research change")
        if initialization not in {"transfer", "fresh"}:
            raise ValueError("initialization must be transfer or fresh")
        if (
            initialization == "transfer"
            and parameter_overrides
            and parameter_overrides.get("policy")
        ):
            raise ValueError("policy architecture changes require fresh initialization")

        record_previous_postmortem(proposal, baseline=baseline)
        if (
            experiment_kind == "training"
            and not baseline
            and state.get("noise_floor") is None
        ):
            raise ValueError(
                "training-seed noise floor is not calibrated; the next proposal "
                "must be an unchanged kind=calibration A/A experiment"
            )

        if parameter_overrides:
            announce("[checks] validating proposed parameters")
            validate_param_overrides(parameter_overrides)
            write_experiment_config(
                merge_param_overrides(previous_config, parameter_overrides)
            )
            config_written = True
        if code_changes:
            announce("[checks] running research-surface checks")
            run_module("ruff", "check", *MUTABLE_CODE_PATHS)
            run_module(
                "pytest",
                "-q",
                "--basetemp",
                str(ROOT / ".pytest-run-temp"),
            )
            announce("[checks] passed")

        if experiment_kind == "method":
            method_version = int(
                state.get("selection_method_version", SELECTION_METHOD_VERSION)
            ) + 1
            verdict = "method adopted"
            state.update(
                {
                    "selection_method_version": method_version,
                    "last_experiment": index,
                    "last_verdict": verdict,
                }
            )
            result.update(
                {
                    "status": "ok",
                    "verdict": verdict,
                    "selection_method_version": method_version,
                }
            )
            atomic_write_json(STATE_PATH, state)
            append_result(result)
            commit_result(index, change)
            announce(f"[decision] {verdict} as selection method v{method_version}")
            return 0

        accepted_metrics = state.get("accepted_metrics")
        if accepted_metrics is None and not fresh_baseline:
            accepted_metrics = evaluate_artifact(
                accepted_dir, label="accepted-policy baseline"
            )
            state["accepted_metrics"] = accepted_metrics
            state["accepted_parameters"] = previous_config

        effective_config = load_experiment_config()
        effective_timesteps = training_budget(
            args.timesteps,
            initialization,
            fresh_baseline,
            int(state.get("accepted_training_steps", args.timesteps)),
        )
        if initialization == "fresh" and not fresh_baseline:
            announce(
                "[training plan] fresh initialization receives the fixed "
                f"compute-matched budget: {effective_timesteps:,} steps"
            )
        else:
            announce(f"[training plan] {effective_timesteps:,} steps")
        resume = accepted_dir / "model.zip" if initialization == "transfer" else None
        if not fresh_baseline:
            selection_reference_path = (
                CANDIDATE_ROOT / f"selection-reference-experiment-{index}.json"
            )
            selection_reference_path.unlink(missing_ok=True)
            evaluate_artifact(
                accepted_dir,
                SELECTION_SEED,
                label="development-panel champion reference",
                episodes=int(effective_config["training"]["selection_eval_episodes"]),
                output_path=selection_reference_path,
            )

        if experiment_kind == "calibration":
            if initialization != "transfer":
                raise ValueError("A/A calibration must start each replicate from the champion")
            replicates: list[dict] = []
            for training_seed in CALIBRATION_TRAIN_SEEDS:
                replicate_dir = CANDIDATE_ROOT / (
                    f"experiment-{index}-calibration-seed-{training_seed}"
                )
                if replicate_dir.exists():
                    remove_candidate_dir(replicate_dir)
                created_candidate_dirs.append(replicate_dir)
                train_candidate(
                    replicate_dir,
                    effective_timesteps,
                    training_seed,
                    resume,
                    selection_reference_path,
                    label=f"A/A replicate {training_seed + 1}/{len(CALIBRATION_TRAIN_SEEDS)}",
                )
                replicates.append(
                    {
                        "name": f"training-seed-{training_seed}",
                        "kind": "calibration",
                        "training_seed": training_seed,
                        "path": replicate_dir / "final_checkpoint",
                        "evaluations": [],
                    }
                )
            calibration_tournament, _ = evaluate_tournament(
                replicates,
                int(state.get("selection_method_version", SELECTION_METHOD_VERSION)),
                extend_close=False,
            )
            noise_floor = summarize_noise_floor(calibration_tournament)
            calibration_archive = archive_calibration(
                index, calibration_tournament, noise_floor
            )
            verdict = "calibration recorded"
            state.update(
                {
                    "noise_floor": noise_floor,
                    "last_experiment": index,
                    "last_verdict": verdict,
                }
            )
            result.update(
                {
                    "status": "ok",
                    "verdict": verdict,
                    "noise_floor": noise_floor,
                    "calibration_archive": str(calibration_archive.relative_to(ROOT)),
                }
            )
            atomic_write_json(STATE_PATH, state)
            append_result(result)
            commit_result(index, change)
            announce(
                "[calibration] training-seed noise floor: "
                f"std {noise_floor['pooled_success_std_pp']:.3f} pp | "
                f"range {noise_floor['pooled_success_range_pp']:.3f} pp"
            )
            return 0

        if candidate_dir.exists():
            announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            remove_candidate_dir(candidate_dir)
        if args.reuse_candidate is not None:
            if not baseline:
                raise ValueError("candidate reuse is restricted to baseline recovery")
            reusable = args.reuse_candidate.resolve()
            validate_reusable_candidate(
                reusable,
                timesteps=args.timesteps,
                resume=resume,
                config=effective_config,
            )
            announce(f"[recovery] reusing completed candidate from {reusable}")
            copy_candidate_outputs(reusable, candidate_dir)
        else:
            created_candidate_dirs.append(candidate_dir)
            train_candidate(
                candidate_dir,
                effective_timesteps,
                TRAIN_SEED,
                resume,
                selection_reference_path,
                label="baseline training" if baseline else "candidate training",
            )
        runtime_benchmark_changes = status_paths(IMMUTABLE_PATHS)
        if runtime_benchmark_changes:
            raise RuntimeError(
                "training modified protected benchmark files: "
                f"{runtime_benchmark_changes}"
            )
        contenders = [
            {
                "name": f"candidate-{number}",
                "kind": "candidate",
                "path": path,
                "evaluations": [],
            }
            for number, path in enumerate(finalist_directories(candidate_dir), start=1)
        ]
        if not fresh_baseline:
            contenders.append(
                {
                    "name": "champion",
                    "kind": "champion",
                    "path": accepted_dir,
                    "evaluations": [],
                }
            )
        selection_method_version = int(
            state.get("selection_method_version", SELECTION_METHOD_VERSION)
        )
        noise_floor_pp = float(
            (state.get("noise_floor") or {}).get("pooled_success_std_pp", 0.0)
        )
        tournament, winner = evaluate_tournament(
            contenders, selection_method_version, noise_floor_pp
        )
        candidate_winner = max(
            (item for item in tournament if item["kind"] == "candidate"),
            key=lambda item: rank(item["summary"]),
        )
        challenger_archive = archive_candidate(
            index, candidate_winner, effective_config, tournament
        )
        promoted = winner["kind"] == "candidate"
        official_metrics = evaluate_artifact(
            winner["path"], EVALUATION_SEED, label="fixed reported benchmark"
        )
        goal_reached = (
            winner["summary"]["seeds_passing_98_percent"]
            == winner["summary"]["seed_count"]
            and official_metrics["success_percent"] >= FINAL_SUCCESS_PERCENT
        )

        if promoted:
            copy_artifact(winner["path"], ACCEPTED_DIR)
            state["accepted_artifact"] = str(ACCEPTED_DIR.relative_to(ROOT))
            state["accepted_metrics"] = winner["summary"]
            state["accepted_parameters"] = load_experiment_config()
            if initialization == "transfer":
                state["accepted_training_steps"] = int(
                    state.get("accepted_training_steps", 0)
                ) + effective_timesteps
            else:
                state["accepted_training_steps"] = effective_timesteps
            verdict = "promoted"
        else:
            state["accepted_metrics"] = winner["summary"]
            verdict = "champion retained"
            if config_written:
                write_experiment_config(previous_config)
            if code_changes:
                clean_mutable_changes()

        if goal_reached:
            GOAL_PATH.write_text(
                f"Goal reached at experiment {index}.\n", encoding="utf-8"
            )
            verdict += "; goal reached"

        tournament_result = [
            {
                "name": item["name"],
                "kind": item["kind"],
                "summary": item["summary"],
                "paired_vs_champion": item.get("paired_vs_champion"),
                "evaluations": metrics_without_artifact_path(item["evaluations"]),
            }
            for item in tournament
        ]

        state.update(
            {
                "selection_method_version": selection_method_version,
                "last_experiment": index,
                "last_verdict": verdict,
                "last_metrics": candidate_winner["summary"],
                "official_metrics": metrics_without_artifact_path(
                    [official_metrics]
                )[0],
                "accepted_tournament": metrics_without_artifact_path(
                    winner["evaluations"]
                ),
            }
        )
        result.update(
            {
                "status": "ok",
                "verdict": verdict,
                "accepted": promoted,
                "promoted": promoted,
                "goal_reached": goal_reached,
                "selection_method_version": selection_method_version,
                "candidate_metrics": candidate_winner["summary"],
                "candidate_success_percent": candidate_winner["summary"][
                    "pooled_success_percent"
                ],
                "candidate_seeds_passed": (
                    f"{candidate_winner['summary']['seeds_passing_98_percent']}/"
                    f"{candidate_winner['summary']['seed_count']}"
                ),
                "challenger_archive": str(challenger_archive.relative_to(ROOT)),
                "winner": winner["name"],
                "official_metrics": metrics_without_artifact_path(
                    [official_metrics]
                )[0],
                "noise_floor_pp": noise_floor_pp,
                "tournament": tournament_result,
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
        if code_changes or status_paths(MUTABLE_PATHS):
            clean_mutable_changes()
        if baseline:
            announce(
                "[runner] Baseline interrupted by user. It remains pending and "
                "will restart from the beginning next time."
            )
        else:
            announce(
                "[runner] Experiment interrupted by user. The candidate was "
                "discarded and the accepted checkpoint is unchanged."
            )
        return 130
    except Exception as error:  # noqa: BLE001
        if config_written:
            write_experiment_config(previous_config)
        if code_changes or status_paths(MUTABLE_PATHS):
            clean_mutable_changes()
        result["error"] = str(error)[:500]
        if experiment_kind == "method":
            result["verdict"] = "method rejected"
        else:
            result["verdict"] = "invalid"
        append_result(result)
        atomic_write_json(STATE_PATH, state)
        commit_result(index, change)
        print("SUMMARY: " + json.dumps(result))
        return 1
    finally:
        PROPOSAL_PATH.unlink(missing_ok=True)
        cleanup_targets = created_candidate_dirs or [candidate_dir]
        for cleanup_target in cleanup_targets:
            try:
                remove_candidate_dir(cleanup_target)
            except OSError as cleanup_error:
                announce(f"[runner] WARNING: candidate cleanup failed: {cleanup_error}")
        if selection_reference_path is not None:
            selection_reference_path.unlink(missing_ok=True)

    print("SUMMARY: " + json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
