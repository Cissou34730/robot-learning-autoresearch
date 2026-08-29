"""Transactional autonomous-research runner for robot learning."""

import argparse
import hashlib
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
from typing import Any

from research.build_research_brief import write_training_summary
from robot_learning.scenario import (
    evaluate_final_model,
    render_scenario_evidence,
    render_training_progress_metric,
    summarize_research_evaluations,
)
from robot_learning.training.comparison import paired_comparison
from robot_learning.training.progress import (
    latest_training_record,
    parse_training_records,
)
from robot_learning.training.research_config import (
    RESEARCH_EVALUATION_EPISODES,
    RESEARCH_EVALUATION_SEED,
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
# Human-owned for the duration of this research problem: the enforcement
# mechanism, every file that can declare the objective reached, the official
# robot it measures, and the package files that resolve those imports.
PROTECTED_BENCHMARK_PATHS = {
    "research/run_experiment.py",
    "robot_learning/__init__.py",
    "robot_learning/benchmark/__init__.py",
    "robot_learning/benchmark/final_benchmark.py",
    "robot_learning/benchmark/final_contract.py",
    "robot_learning/robots/__init__.py",
    "robot_learning/robots/two_joint_arm.py",
    "robot_learning/robots/two_joint_arm.xml",
    "robot_learning/scenario/__init__.py",
    "robot_learning/scenario/final_benchmark.py",
}


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


# The runner formats facts the researcher already decided or the tools already
# measured. It never adds a scientific conclusion of its own.


def experiment_change_lines(result: dict) -> list[str]:
    changes = result.get("parameter_changes") or []
    if changes:
        return [
            f"{item['path']}: {item.get('before')} → {item.get('after')}"
            for item in changes
        ]
    return [str(result.get("change", "")).strip() or "-"]


def render_experiment_card(result: dict) -> str:
    budget = result.get("training_budget_steps")
    return "\n".join(
        [
            f"=== Research hypothesis · Experiment {result['index']} ===",
            "",
            "Hypothesis",
            str(result.get("hypothesis", "")).strip() or "-",
            "",
            "Experiment",
            *experiment_change_lines(result),
            "",
            f"Family : {result.get('family', '-')}",
            f"Parent : {result.get('training_parent', '-')}",
            f"Init   : {result.get('initialization', '-')}",
            f"Seed   : {result.get('training_seed', '-')}",
            f"Budget : {int(budget):,} steps" if budget else "Budget : -",
        ]
    )


def training_progress_suffix(record: dict[str, float] | None) -> str:
    """Append the rolling reward and the single scenario-owned live metric."""
    if not record:
        return ""
    parts: list[str] = []
    reward = record.get("ep_rew_mean")
    if reward is not None:
        parts.append(f"reward {float(reward):g}")
    scenario_fragment = render_training_progress_metric(record)
    if scenario_fragment:
        parts.append(scenario_fragment)
    return "".join(f" | {part}" for part in parts)


def _metric_transition(
    first: dict[str, float],
    final: dict[str, float],
    key: str,
) -> tuple[str, str] | None:
    before, after = first.get(key), final.get(key)
    if before is None or after is None:
        return None
    return f"{float(before):g}", f"{float(after):g}"


def _scenario_transition(
    first: dict[str, float],
    final: dict[str, float],
) -> tuple[str, str, str] | None:
    before = render_training_progress_metric(first)
    after = render_training_progress_metric(final)
    if not before or not after:
        return None
    before_label, _, before_value = before.partition(" ")
    after_label, _, after_value = after.partition(" ")
    if before_value and before_label == after_label:
        return before_label.capitalize(), before_value, after_value
    return "Scenario", before, after


def training_dynamics_rows(records: list[dict[str, float]]) -> list[str]:
    if not records:
        return []
    first, final = records[0], records[-1]
    rows: list[tuple[str, str, str]] = []
    reward = _metric_transition(first, final, "ep_rew_mean")
    if reward is not None:
        rows.append(("Reward mean", *reward))
    scenario = _scenario_transition(first, final)
    if scenario is not None:
        rows.append(scenario)
    for label, key in (
        ("Episode length", "ep_len_mean"),
        ("Policy std", "std"),
        ("Explained variance", "explained_variance"),
    ):
        transition = _metric_transition(first, final, key)
        if transition is not None:
            rows.append((label, *transition))
    if not rows:
        return []
    label_width = max(len(label) for label, _, _ in rows)
    value_width = max(len(before) for _, before, _ in rows)
    return [
        f"  {label:<{label_width}}  {before:>{value_width}} → {after}"
        for label, before, after in rows
    ]


def render_training_summary_card(
    result: dict,
    *,
    records: list[dict[str, float]],
    completed_steps: int,
    elapsed_seconds: float,
    candidate_names: list[str],
) -> str:
    budget = result.get("training_budget_steps")
    lines = [
        f"=== Training summary · Experiment {result['index']} ===",
        "",
        f"Hypothesis : {str(result.get('hypothesis', '')).strip() or '-'}",
        f"Change     : {'; '.join(experiment_change_lines(result))}",
        f"Family     : {result.get('family', '-')}",
        f"Parent     : {result.get('training_parent', '-')}",
        f"Init       : {result.get('initialization', '-')}",
        f"Seed       : {result.get('training_seed', '-')}",
        f"Budget     : {int(budget):,} steps" if budget else "Budget     : -",
        (
            f"Completed  : {completed_steps:,} steps in "
            f"{format_duration(elapsed_seconds)}"
        ),
    ]
    dynamics = training_dynamics_rows(records)
    if dynamics:
        lines.extend(["", "Training dynamics", *dynamics])
    lines.extend(["", "Candidates"])
    lines.extend(f"  {name}" for name in candidate_names)
    lines.extend(["", "Next", "  Researcher evaluation design"])
    return "\n".join(lines)


def evaluation_plan_rows(request: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for spec in request.get("evaluations") or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("label") or spec.get("candidate", "")).strip() or "-"
        try:
            detail = f"{int(spec['episodes'])} episodes · seed {int(spec['seed'])}"
        except (KeyError, TypeError, ValueError):
            detail = "episodes and seed pending validation"
        rows.append((name, detail))
    for comparison in request.get("paired_comparisons") or []:
        if not isinstance(comparison, dict):
            continue
        candidate = comparison.get("candidate", "?")
        reference = comparison.get("reference", "?")
        rows.append(("paired comparison", f"{candidate} vs {reference}"))
    return rows


def render_evaluation_plan(request: dict, experiment: int) -> str:
    lines = [f"=== Evaluation design · Experiment {experiment} ===", ""]
    question = str(request.get("question", "")).strip()
    if question:
        lines.extend(["Question", question, ""])
    rows = evaluation_plan_rows(request)
    if rows:
        width = max(len(name) for name, _ in rows)
        lines.append("Plan")
        lines.extend(f"  {name:<{width}}   {detail}" for name, detail in rows)
    reason = str(request.get("reason", "")).strip()
    if reason:
        lines.extend(["", "Reason", reason])
    return "\n".join(lines)


def summary_headline(summary: dict) -> str:
    success = summary.get("pooled_success_percent", summary.get("success_percent"))
    episodes = int(summary.get("episodes", 0))
    if success is None:
        return f"{episodes} episodes"
    return f"success {float(success):.1f}% · {episodes} episodes"


def render_evidence_card(
    experiment: int,
    candidates: list[dict],
    champion_summary: dict | None,
    comparisons: list[dict],
    next_phase: str,
) -> str:
    lines = [f"=== Evidence · Experiment {experiment} ===", ""]
    measured = [item for item in candidates if item.get("summary") is not None]
    if measured:
        width = max(len(str(item["name"])) for item in measured)
        lines.append("Candidate")
        lines.extend(
            f"  {item['name']!s:<{width}}   {summary_headline(item['summary'])}"
            for item in measured
        )
        lines.append("")
    if champion_summary is not None:
        lines.extend(["Champion", f"  {summary_headline(champion_summary)}", ""])
    for comparison in comparisons:
        delta = float(comparison["success_delta_percent"])
        lines.extend(
            [
                "Paired comparison",
                f"  {comparison['candidate']} vs {comparison['reference']}",
                f"  delta {delta:+.1f} pp",
                "",
            ]
        )
    if measured:
        evidence = render_scenario_evidence(measured[0]["summary"])
        lines.append("Scenario evidence")
        lines.extend(f"  {line}" if line else "" for line in evidence)
        lines.append("")
    lines.extend(["Next", f"  {next_phase}"])
    return "\n".join(lines)


def render_decision_card(plan: dict) -> str:
    pending = plan["pending"]
    retained = [
        f"  {retention['record']['id']} (from {retention['record']['candidate']})"
        for retention in plan["retentions"]
    ]
    lines = [
        f"=== Research decision · Experiment {int(pending['experiment'])} ===",
        "",
        "Continue from",
        plan["selected_name"],
        "",
        "Reason",
        str(plan["decision"]["reason"]).strip(),
        "",
        "Code",
        plan["code_action"],
        "",
        "Retained alternatives",
        *(retained or ["  none"]),
    ]
    if plan["removed_retained"]:
        lines.extend(
            [
                "",
                "Removed retained alternatives",
                *(f"  {lineage['id']}" for lineage in plan["removed_retained"]),
            ]
        )
    lines.extend(
        [
            "",
            "Final benchmark",
            "requested" if plan["request_final_benchmark"] else "not requested",
        ]
    )
    return "\n".join(lines)


def training_budget(
    standard_timesteps: int,
    _initialization: str,
    _baseline: bool,
    _accepted_training_steps: int,
) -> int:
    del _initialization, _baseline, _accepted_training_steps
    return standard_timesteps


def running_on_windows() -> bool:
    return platform.system() == "Windows"


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
    for attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


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
    return [path for path in changed if path.replace("\\", "/") not in control_files]


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


def evaluate_artifact(
    artifact_dir: Path,
    seed: int = RESEARCH_EVALUATION_SEED,
    label: str = "official evaluation",
    episodes: int = RESEARCH_EVALUATION_EPISODES,
    output_path: Path | None = None,
    official_benchmark: bool = False,
) -> dict:
    output_path = output_path or RESEARCH_DIR / "last_evaluation.json"
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
                    announce(
                        f"[eval] {label:<20} "
                        f"| {completed_episodes:>4} / {episodes} "
                        f"| {100 * completed_episodes // episodes:>3}% "
                        f"| {format_duration(time.monotonic() - started)}"
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
    stale_temporary_progress.unlink(missing_ok=True)
    if process.returncode != 0:
        raise RuntimeError(f"{label} failed:\n{stdout[-2000:]}\n{stderr[-2000:]}")
    metrics = json.loads(output_path.read_text(encoding="utf-8"))
    announce(
        f"[eval] {label:<20} "
        f"| {int(metrics['episodes']):>4} / {episodes} | 100% "
        f"| {format_duration(time.monotonic() - started)} "
        f"| success {metrics['success_percent']:.1f}%"
    )
    return metrics


def requested_paired_comparisons(
    request: dict,
    evaluations_by_candidate: dict[str, list[dict]],
) -> list[dict]:
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


def validate_evaluation_request(request: dict) -> None:
    """Require the researcher's scientific framing on a newly written request."""
    for field in ("question", "reason"):
        value = request.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"evaluation request requires a non-empty {field}")


def execute_pending_evaluations() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    pending = state.get("pending_evaluation_request")
    if not isinstance(pending, dict):
        raise TypeError("there is no trained experiment awaiting evaluation")
    if EVALUATION_REQUEST_PATH.exists():
        request = json.loads(EVALUATION_REQUEST_PATH.read_text(encoding="utf-8"))
        validate_evaluation_request(request)
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
    announce("\n" + render_evaluation_plan(request, experiment) + "\n")

    candidates = pending["candidates"]
    available = {item["name"]: item for item in candidates}
    if pending.get("champion_available"):
        available["champion"] = {
            "name": "champion",
            "artifact": state["accepted_artifact"],
            "evaluations": [],
        }

    executed: list[dict] = list(pending.get("partial_evaluations", []))
    # The persisted measurement ledger is the sole source of truth across
    # successive rounds and interrupted resumes.
    for contender in candidates:
        contender["evaluations"] = []
    for item in executed:
        contender = available.get(item["candidate"])
        if contender is not None:
            contender.setdefault("evaluations", []).append(item["metrics"])

    def request_key(name: str, episodes: int, seed: int) -> tuple[str, int, int]:
        return name, episodes, seed

    completed_keys = {
        request_key(
            item["candidate"],
            int(item["episodes"]),
            int(item["seed"]),
        )
        for item in executed
    }
    try:
        for number, spec in enumerate(requested, start=1):
            if not isinstance(spec, dict):
                raise TypeError("each requested evaluation must be an object")
            missing = [
                field
                for field in ("candidate", "episodes", "seed")
                if field not in spec
            ]
            if missing:
                raise ValueError(f"evaluation is missing required fields: {missing}")
            if "official_benchmark" in spec:
                raise ValueError(
                    "official_benchmark is not valid in a research evaluation request"
                )
            name = str(spec.get("candidate", "")).strip()
            contender = available.get(name)
            if contender is None:
                raise ValueError(
                    f"unknown evaluation candidate {name!r}; "
                    f"choose from {sorted(available)}"
                )
            episodes = int(spec["episodes"])
            seed = int(spec["seed"])
            if episodes < 1:
                raise ValueError("evaluation episodes must be positive")
            label = str(spec.get("label", f"requested evaluation {number}: {name}"))
            key = request_key(name, episodes, seed)
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
            summarize_research_evaluations(evaluations) if evaluations else None
        )

    champion_evaluations = available.get("champion", {}).get("evaluations", [])
    champion_summary = (
        summarize_research_evaluations(champion_evaluations)
        if champion_evaluations
        else None
    )

    comparison_inputs = {
        name: contender.get("evaluations", []) for name, contender in available.items()
    }
    comparisons = requested_paired_comparisons(request, comparison_inputs)
    result = pending["result"]
    result.update(
        {
            "status": "ok",
            "verdict": "measured as requested; awaiting researcher analysis",
            "decision_pending": True,
            "candidates": candidates,
            "requested_evaluations": executed,
            "paired_comparisons": comparisons,
        }
    )
    measured = [item for item in candidates if item.get("summary") is not None]
    if measured:
        primary = measured[0]["summary"]
        result["candidate_metrics"] = primary
        result["candidate_success_percent"] = primary["pooled_success_percent"]

    researcher_context = {
        "experiment": experiment,
        "candidates": candidates,
        "champion_available": bool(pending.get("champion_available")),
        "champion_summary": champion_summary,
        "champion_evaluations": champion_evaluations,
        "parameters": pending["parameters"],
        "initialization": pending["initialization"],
        "training_budget_steps": pending["training_budget_steps"],
        "parent_training_steps": pending["parent_training_steps"],
        "code_parent_commit": pending.get("code_parent_commit"),
        "research_change_paths": pending.get("research_change_paths", []),
    }
    more_evidence = bool(request.get("need_more_evidence", False))
    if more_evidence:
        pending["evaluation_plan"] = None
        pending["partial_evaluations"] = executed
        state["pending_evaluation_request"] = pending
        state["pending_researcher_decision"] = None
        state["last_verdict"] = (
            "measured; researcher requested another evaluation round"
        )
    else:
        state["pending_researcher_decision"] = researcher_context
        state["pending_evaluation_request"] = None
        state["last_verdict"] = result["verdict"]
    state["last_experiment"] = experiment
    if pending.get("baseline"):
        BASELINE_PENDING_PATH.unlink(missing_ok=True)
    atomic_write_json(STATE_PATH, state)
    EVALUATION_REQUEST_PATH.unlink(missing_ok=True)
    if not more_evidence:
        append_result(result)
    next_phase = (
        "Researcher evaluation design"
        if more_evidence
        else "Researcher lineage decision"
    )
    announce(
        "\n"
        + render_evidence_card(
            experiment,
            candidates,
            champion_summary,
            comparisons,
            next_phase,
        )
    )
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
) -> float:
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
    announce(f"[train] {label} | seed {seed} | {timesteps:,} steps")
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
                log_text = read_training_log(train_log, progress_offset)
                record = latest_training_record(log_text)
                steps = latest_step_count(log_text)
                if steps is None:
                    announce(f"[train] starting ({format_duration(elapsed)} elapsed)")
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
                        f"[train] {steps:,} / {progress_target:,} "
                        f"({progress:.0f}%) | {format_duration(elapsed)} | "
                        f"ETA ~{format_duration(eta)}"
                        + training_progress_suffix(record)
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
    return time.monotonic() - started


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
    seed: int,
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
        "seed": artifact.get("seed") == seed,
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


def retained_lineage(state: dict, identifier: str) -> dict | None:
    return next(
        (
            lineage
            for lineage in state.get("retained_lineages", [])
            if lineage.get("id") == identifier
        ),
        None,
    )


def training_parent(
    proposal: dict, state: dict, initialization: str
) -> tuple[str, Path, int]:
    identifier = str(proposal.get("training_parent", "accepted")).strip()
    if initialization != "transfer":
        if identifier != "accepted":
            raise ValueError(
                "training_parent is only valid with transfer initialization"
            )
        return "fresh", Path(), 0
    if identifier == "accepted":
        return (
            "accepted",
            ROOT / state["accepted_artifact"],
            int(state.get("accepted_training_steps", 0)),
        )
    lineage = retained_lineage(state, identifier)
    if lineage is None:
        raise ValueError(f"unknown retained training parent {identifier!r}")
    artifact = ROOT / lineage["artifact"]
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        if not (artifact / filename).exists():
            raise ValueError(
                f"retained lineage {identifier!r} is incomplete: {filename}"
            )
    return identifier, artifact, int(lineage.get("training_steps", 0))


def validate_experiment_semantics(
    proposal: dict,
    experiment_kind: str,
    initialization: str,
    parameter_overrides: dict | None,
    code_changes: list[str],
    baseline: bool,
) -> None:
    if PROTECTED_BENCHMARK_PATHS & {path.replace("\\", "/") for path in code_changes}:
        raise ValueError(
            "the human-owned final benchmark, official robot and research "
            "protocol enforcement cannot be changed by a research proposal"
        )
    if baseline and (parameter_overrides or code_changes):
        raise ValueError("baseline requires an unchanged research method")
    if (
        not baseline
        and experiment_kind not in {"continuation", "replication"}
        and not parameter_overrides
        and not code_changes
    ):
        raise ValueError("experiment contains no research change")
    if initialization not in {"transfer", "fresh"}:
        raise ValueError("initialization must be transfer or fresh")
    if experiment_kind == "continuation" and initialization != "transfer":
        raise ValueError("continuation requires transfer initialization")
    if experiment_kind == "replication":
        if initialization != "fresh":
            raise ValueError("replication requires fresh initialization")
        if "training_seed" not in proposal:
            raise ValueError("replication requires an explicit training_seed")
        if parameter_overrides or code_changes:
            raise ValueError("replication requires an unchanged learning method")
        try:
            replicated_experiment = int(proposal["replication_of"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "replication requires an exact experiment number"
            ) from error
        if replicated_experiment < 1:
            raise ValueError("replication requires an exact experiment number")


def validate_training_proposal(proposal: dict, *, baseline: bool) -> None:
    if baseline:
        return
    forbidden = {
        "previous_result_decision",
        "previous_experiment_postmortem",
    } & set(proposal)
    if forbidden:
        raise ValueError(
            f"training proposal contains lineage-only fields: {sorted(forbidden)}"
        )
    required = {
        "kind",
        "family",
        "hypothesis",
        "change",
        "initialization",
        "training_parent",
        "training_seed",
        "params",
    }
    missing = sorted(field for field in required if field not in proposal)
    if missing:
        raise ValueError(f"training proposal is missing required fields: {missing}")
    if not str(proposal["family"]).strip():
        raise ValueError("training proposal family must be non-empty")
    if not str(proposal["training_parent"]).strip():
        raise ValueError("training proposal training_parent must be non-empty")


def remove_heavyweight_artifacts(artifact: Path) -> None:
    for filename in ("model.zip", "vecnormalize.pkl", "replay_buffer.pkl"):
        (artifact / filename).unlink(missing_ok=True)


def require_complete_artifact(artifact: Path, description: str) -> None:
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        if not (artifact / filename).is_file():
            raise ValueError(f"{description} is incomplete: {filename}")


def artifact_fingerprint(artifact: Path) -> str:
    digest = hashlib.sha256()
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        digest.update((artifact / filename).read_bytes())
    return digest.hexdigest()


def plan_code_lineage_decision(pending: dict, action: str) -> dict:
    if action == "keep":
        return {"restore": [], "remove_created": []}
    parent = str(pending.get("code_parent_commit", "")).strip()
    paths = [str(path) for path in pending.get("research_change_paths", [])]
    if not parent or not paths:
        return {"restore": [], "remove_created": []}
    restorable: list[str] = []
    created: list[Path] = []
    for path in paths:
        candidate = (ROOT / path).resolve()
        if ROOT.resolve() not in candidate.parents:
            raise RuntimeError(f"unsafe research change path: {path}")
        exists_at_parent = git(
            "ls-tree", "-r", "--name-only", parent, "--", path
        ).strip()
        if exists_at_parent:
            restorable.append(path)
        else:
            created.append(candidate)
    return {"restore": restorable, "remove_created": created}


def apply_code_lineage_decision(plan: dict) -> None:
    if plan["restore"]:
        git("restore", "--source", plan["parent"], "--", *plan["restore"])
    for created_path in plan["remove_created"]:
        if created_path.is_dir():
            shutil.rmtree(created_path)
        else:
            created_path.unlink(missing_ok=True)


def plan_previous_result_decision(proposal: dict, state: dict) -> dict:
    pending = state.get("pending_researcher_decision")
    if pending is None:
        raise ValueError("there is no researcher decision awaiting resolution")
    if set(proposal) != {"previous_result_decision"}:
        raise ValueError(
            "a lineage proposal must contain only previous_result_decision"
        )
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
    allowed = {
        "experiment",
        "continue_from",
        "reason",
        "code",
        "retain",
        "remove_retained",
        "request_final_benchmark",
    }
    extra = set(decision) - allowed
    if extra:
        raise ValueError(f"unsupported lineage decision fields: {sorted(extra)}")
    sources = {item["name"]: item for item in pending["candidates"]}
    if pending.get("champion_available"):
        sources["champion"] = {
            "name": "champion",
            "artifact": state["accepted_artifact"],
            "timesteps": int(state.get("accepted_training_steps", 0)),
            "summary": state.get("accepted_metrics"),
            "evaluations": pending.get("champion_evaluations", []),
            "parameters": state.get("accepted_parameters"),
        }
    if selected_name == "champion" and "champion" not in sources:
        raise ValueError("there is no existing champion to continue from")
    selected = sources.get(selected_name)
    if selected is None:
        raise ValueError(f"continue_from must be one of {sorted(sources)}")
    selected_artifact = ROOT / selected["artifact"]
    require_complete_artifact(selected_artifact, f"selected lineage {selected_name!r}")

    code_decision = decision.get("code")
    if not isinstance(code_decision, dict):
        raise TypeError(
            "previous_result_decision requires a code decision with action and reason"
        )
    if set(code_decision) != {"action", "reason"}:
        raise ValueError("code decision contains unsupported fields")
    code_action = str(code_decision.get("action", "")).strip().lower()
    code_reason = str(code_decision.get("reason", "")).strip()
    if code_action not in {"keep", "revert"} or not code_reason:
        raise ValueError("code decision must be keep or revert with a reason")
    code_plan = plan_code_lineage_decision(pending, code_action)
    code_plan["parent"] = str(pending.get("code_parent_commit", "")).strip()

    retained = list(state.get("retained_lineages", []))
    retained_by_id = {str(lineage.get("id")): lineage for lineage in retained}
    removal_ids = decision.get("remove_retained", [])
    if not isinstance(removal_ids, list) or any(
        not str(identifier).strip() for identifier in removal_ids
    ):
        raise ValueError("remove_retained must be a list of retained lineage IDs")
    removal_ids = [str(identifier).strip() for identifier in removal_ids]
    if len(set(removal_ids)) != len(removal_ids):
        raise ValueError("remove_retained contains duplicate IDs")
    missing = set(removal_ids) - set(retained_by_id)
    if missing:
        raise ValueError(f"unknown retained lineages: {sorted(missing)}")

    requested = decision.get("retain", [])
    if not isinstance(requested, list):
        raise TypeError("retain must be a list")
    retained_ids = set(retained_by_id)
    retention_plans: list[dict] = []
    for item in requested:
        if not isinstance(item, dict) or set(item) != {"candidate", "id", "reason"}:
            raise ValueError(
                "each retained lineage requires only candidate, id, and reason"
            )
        candidate_name = str(item["candidate"]).strip()
        identifier = str(item["id"]).strip()
        retention_reason = str(item["reason"]).strip()
        if (
            not identifier
            or Path(identifier).name != identifier
            or identifier in {".", ".."}
        ):
            raise ValueError(
                "retained lineage ID must be a stable file-name-safe identifier"
            )
        if not retention_reason or candidate_name not in sources:
            raise ValueError(
                "retained lineages require an available candidate, id, and reason"
            )
        if candidate_name == selected_name:
            raise ValueError("do not retain the lineage becoming active")
        if identifier in retained_ids or identifier in removal_ids:
            raise ValueError(f"conflicting retained lineage ID: {identifier}")
        source = sources[candidate_name]
        source_artifact = ROOT / source["artifact"]
        require_complete_artifact(source_artifact, f"retained lineage {identifier!r}")
        destination = RESEARCH_DIR / "checkpoints" / "retained" / identifier
        if destination.exists():
            raise ValueError(
                f"retained lineage destination already exists: {identifier}"
            )
        retention_plans.append(
            {
                "source": source_artifact,
                "destination": destination,
                "record": {
                    "id": identifier,
                    "artifact": str(destination.relative_to(ROOT)),
                    "origin_experiment": int(pending["experiment"]),
                    "candidate": candidate_name,
                    "reason": retention_reason,
                    "parameters": source.get("parameters", pending["parameters"]),
                    "training_steps": int(source["timesteps"]),
                },
            }
        )
        retained_ids.add(identifier)

    request_final = decision.get("request_final_benchmark", False)
    if not isinstance(request_final, bool):
        raise TypeError("request_final_benchmark must be true or false")
    selected_fingerprint = artifact_fingerprint(selected_artifact)
    if (
        request_final
        and state.get("official_benchmark_artifact") == selected_fingerprint
    ):
        raise ValueError(
            "the selected accepted artifact already received an official benchmark"
        )
    return {
        "pending": pending,
        "decision": decision,
        "selected": selected,
        "selected_name": selected_name,
        "selected_artifact": selected_artifact,
        "selected_fingerprint": selected_fingerprint,
        "code_action": code_action,
        "code_reason": code_reason,
        "code_plan": code_plan,
        "retained": [
            lineage for lineage in retained if lineage["id"] not in removal_ids
        ],
        "retentions": retention_plans,
        "removed_retained": [retained_by_id[identifier] for identifier in removal_ids],
        "request_final_benchmark": request_final,
    }


def apply_previous_result_decision(proposal: dict, state: dict) -> bool:
    plan = plan_previous_result_decision(proposal, state)
    pending = plan["pending"]
    selected = plan["selected"]
    selected_name = plan["selected_name"]
    # Copy alternatives first: a retained champion must survive replacement.
    for retention in plan["retentions"]:
        copy_artifact(retention["source"], retention["destination"])
    if selected_name != "champion":
        copy_artifact(plan["selected_artifact"], ACCEPTED_DIR)
        state["accepted_artifact"] = str(ACCEPTED_DIR.relative_to(ROOT))
        state["accepted_metrics"] = selected.get("summary")
        state["accepted_parameters"] = pending["parameters"]
        state["accepted_training_steps"] = (
            int(pending.get("parent_training_steps", 0))
            + int(pending["training_budget_steps"])
            if pending["initialization"] == "transfer"
            else int(pending["training_budget_steps"])
        )
        state["official_metrics"] = None
    else:
        state["accepted_metrics"] = selected.get("summary")
    apply_code_lineage_decision(plan["code_plan"])
    state["retained_lineages"] = plan["retained"] + [
        retention["record"] for retention in plan["retentions"]
    ]
    state["last_lineage_decision"] = {
        "experiment": int(pending["experiment"]),
        "continue_from": selected_name,
        "reason": plan["decision"]["reason"],
        "code": {"action": plan["code_action"], "reason": plan["code_reason"]},
        "code_parent_commit": pending.get("code_parent_commit"),
    }
    state["pending_researcher_decision"] = None
    state["last_verdict"] = f"researcher selected {selected_name}"
    atomic_write_json(STATE_PATH, state)
    # Retain compact challenger history while removing every duplicate reusable artifact.
    for candidate in pending["candidates"]:
        remove_heavyweight_artifacts(ROOT / candidate["artifact"])
    for lineage in plan["removed_retained"]:
        remove_heavyweight_artifacts(ROOT / lineage["artifact"])
    if plan["request_final_benchmark"]:
        state["pending_final_benchmark"] = {
            "experiment": int(pending["experiment"]),
            "selected": selected_name,
            "artifact": str(ACCEPTED_DIR.relative_to(ROOT)),
            "fingerprint": plan["selected_fingerprint"],
        }
        atomic_write_json(STATE_PATH, state)
    announce("\n" + render_decision_card(plan) + "\n")
    return False


def execute_pending_final_benchmark() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    pending = state.get("pending_final_benchmark")
    if not isinstance(pending, dict):
        raise TypeError(
            "there is no accepted lineage awaiting final benchmark evaluation"
        )
    artifact = str(pending.get("artifact", "")).strip()
    if artifact != state.get("accepted_artifact"):
        raise ValueError(
            "pending final benchmark does not identify the accepted artifact"
        )
    accepted_artifact = ROOT / artifact
    require_complete_artifact(accepted_artifact, "pending final benchmark artifact")
    fingerprint = str(pending.get("fingerprint", "")).strip()
    if not fingerprint or artifact_fingerprint(accepted_artifact) != fingerprint:
        raise ValueError(
            "pending final benchmark artifact fingerprint does not match accepted lineage"
        )
    if state.get("official_benchmark_artifact") == fingerprint:
        raise ValueError(
            "the selected accepted artifact already received an official benchmark"
        )

    official_metrics = evaluate_final_model(accepted_artifact / "model.zip")
    state["official_metrics"] = official_metrics
    state["official_benchmark_artifact"] = fingerprint
    state["pending_final_benchmark"] = None
    atomic_write_json(STATE_PATH, state)
    if bool(official_metrics["goal_reached"]):
        GOAL_PATH.write_text(
            f"Goal reached with {pending['selected']} from experiment {pending['experiment']}.\n",
            encoding="utf-8",
        )
    return 0


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
    commit_and_push(f"exp {index}: {change}")


def commit_lineage_decision(experiment: int, selected: str) -> None:
    control_files = {"research/proposal.json", "research/evaluation_request.json"}
    paths = [
        path
        for path in status_paths((".",))
        if path.replace("\\", "/") not in control_files
    ]
    stage_existing_or_tracked(paths)
    if git("diff", "--cached", "--name-only").strip():
        commit_and_push(f"select experiment {experiment} lineage: {selected}")


def commit_and_push(message: str) -> None:
    git("commit", "-m", message)
    try:
        git("push", "origin", "HEAD")
    except RuntimeError as error:
        raise RuntimeError(
            "commit created locally but push to origin failed; "
            "the research loop stopped to avoid unpublished history"
        ) from error


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
    parser.add_argument("--evaluate-pending-final", action="store_true")
    args = parser.parse_args()
    if args.evaluate_pending_final:
        return execute_pending_final_benchmark()
    if args.evaluate_pending:
        return execute_pending_evaluations()
    if not PROPOSAL_PATH.exists():
        print("ERROR: research/proposal.json not found.")
        return 1

    proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    raw_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    decision_pending = raw_state.get("pending_researcher_decision") is not None
    if decision_pending:
        state = load_state(allow_unmeasured=True, allow_missing_artifact=True)
        apply_previous_result_decision(proposal, state)
        pending_experiment = int(raw_state["pending_researcher_decision"]["experiment"])
        selected_lineage = str(proposal["previous_result_decision"]["continue_from"])
        commit_lineage_decision(pending_experiment, selected_lineage)
        PROPOSAL_PATH.unlink(missing_ok=True)
        return 0

    change = str(proposal["change"]).strip()
    hypothesis = str(proposal["hypothesis"]).strip()
    experiment_kind = str(proposal.get("kind", "training")).lower()
    parameter_overrides = proposal.get("params")
    if parameter_overrides is not None and not isinstance(parameter_overrides, dict):
        raise TypeError("proposal params must be an object")
    baseline = bool(proposal.get("baseline", False))
    validate_training_proposal(proposal, baseline=baseline)
    initialization = str(proposal.get("initialization", "transfer")).lower()
    index = next_index()
    fresh_baseline = baseline and initialization == "fresh"
    state = load_state(
        allow_unmeasured=True,
        allow_missing_artifact=fresh_baseline,
    )
    candidate_dir = CANDIDATE_ROOT / f"experiment-{index}"
    created_candidate_dirs: list[Path] = []
    previous_config = load_experiment_config()
    code_parent_commit = git("rev-parse", "HEAD").strip()
    code_changes: list[str] = []
    preserve_proposal = False
    reused_candidate: Path | None = None
    training_elapsed = 0.0
    parent_name, parent_artifact, parent_training_steps = training_parent(
        proposal, state, initialization
    )

    result: dict[str, Any] = {
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
        validate_experiment_semantics(
            proposal,
            experiment_kind,
            initialization,
            parameter_overrides,
            code_changes,
            baseline,
        )

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
                path
                for path in code_changes
                if path.endswith(".py") and (ROOT / path).exists()
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
        training_seed = int(proposal.get("training_seed", TRAIN_SEED))
        result["training_seed"] = training_seed
        result["training_parent"] = parent_name
        if experiment_kind == "replication":
            result["replication_of"] = str(
                proposal.get("replication_of", proposal.get("family", ""))
            ).strip()
        announce("\n" + render_experiment_card(result) + "\n")
        resume = parent_artifact / "model.zip" if initialization == "transfer" else None

        if candidate_dir.exists():
            announce(f"[cleanup] removing stale candidate {candidate_dir.name}")
            remove_candidate_dir(candidate_dir)
        if args.reuse_candidate is not None:
            reusable = args.reuse_candidate.resolve()
            reused_candidate = reusable
            validate_reusable_candidate(
                reusable,
                timesteps=effective_timesteps,
                seed=training_seed,
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
                remaining_timesteps = max(effective_timesteps - completed_timesteps, 0)
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
                    training_elapsed = train_candidate(
                        candidate_dir,
                        remaining_timesteps,
                        training_seed,
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
            training_elapsed = train_candidate(
                candidate_dir,
                effective_timesteps,
                training_seed,
                resume,
                label="baseline training" if baseline else "candidate training",
            )
        contenders = [
            {
                "name": path.name,
                "kind": "candidate",
                "path": path,
                "timesteps": int(
                    json.loads((path / "artifact.json").read_text(encoding="utf-8"))[
                        "timesteps"
                    ]
                ),
                "evaluations": [],
            }
            for path in candidate_directories(candidate_dir)
        ]
        archived_candidates = archive_candidates(index, contenders, effective_config)
        verdict = "trained; awaiting researcher evaluation request"
        records = parse_training_records(
            read_training_log(RESEARCH_DIR / "last_train.log")
        )
        completed_steps = max(
            (int(candidate["timesteps"]) for candidate in archived_candidates),
            default=0,
        )
        if records and "total_timesteps" in records[-1]:
            completed_steps = int(records[-1]["total_timesteps"])
        announce(
            "\n"
            + render_training_summary_card(
                result,
                records=records,
                completed_steps=completed_steps,
                elapsed_seconds=training_elapsed,
                candidate_names=[
                    str(candidate["name"]) for candidate in archived_candidates
                ],
            )
            + "\n"
        )

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
                    "parent_training_steps": int(parent_training_steps),
                    "baseline": baseline,
                    "code_parent_commit": code_parent_commit,
                    "research_change_paths": code_changes
                    + (["research/current_params.json"] if parameter_overrides else []),
                    "result": result,
                },
            }
        )
        result.update({"status": "trained", "verdict": verdict})
        if args.reuse_candidate is not None:
            RECOVERY_PENDING_PATH.unlink(missing_ok=True)
        RESTART_PENDING_PATH.unlink(missing_ok=True)
        atomic_write_json(STATE_PATH, state)
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
        announce(f"[error] experiment {index} invalid: {result['error']}")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
