"""Deterministic experiment runner for the autoresearch loop.

The research agent writes `research/proposal.json` (and, in code mode, edits
the allowed files). This script does everything else: validates input against
machine-enforced boundaries, runs gates when needed, trains, evaluates,
appends the results row, applies the ratchet, updates best-so-far, escalates
between hypothesis classes, and writes GOAL_REACHED on success.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from research.build_research_brief import write_training_summary
from robot_learning.training.research_config import (
    assert_immutable_invariants,
    load_experiment_config,
    merge_param_overrides,
    validate_param_overrides,
    write_experiment_config,
)

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "research" / "EXPERIMENTS.md"
PROPOSAL_PATH = ROOT / "research" / "proposal.json"
STATE_PATH = ROOT / "research" / "research_state.json"
BASELINE_PENDING_PATH = ROOT / "research" / "BASELINE_PENDING"
SENTINEL_DIR = ROOT / "research"
CODE_DIR = "robot_learning"
MODELS_DIR = ROOT / "models"
BASELINE_MODEL_PATH = MODELS_DIR / "reach-exp19" / "model.zip"
BASE_ALLOWED_CODE_FILES = {
    "robot_learning/rewards/reach_reward.py",
    "robot_learning/environments/reach_env.py",
    "tests/test_reach_env.py",
}
ALGORITHM_CODE_FILES = {
    "robot_learning/train.py",
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
}
RESEARCH_DIFF_PATHS = (CODE_DIR, "tests/test_reach_env.py")

TIMESTEPS = 120000
EVAL_EPISODES = 200
TRAIN_SEED = 0
GOAL_PERCENT = 98.0

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


def run_module(module: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{module} failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return result.stdout


def next_index(log_text: str) -> int:
    indices = [
        int(m) for m in re.findall(r"^\| (\d+) \|", log_text, flags=re.MULTILINE)
    ]
    return max(indices, default=0) + 1


def current_best(log_text: str) -> float:
    match = re.search(r"\*\*Best so far:\*\* (\d+(?:\.\d+)?)%", log_text)
    return float(match.group(1)) if match else 0.0


def set_best_line(log_text: str, percent: float, index: int) -> str:
    replacement = f"**Best so far:** {percent:g}% (experiment {index})"
    updated, count = re.subn(r"\*\*Best so far:\*\*.*", replacement, log_text, count=1)
    if count == 0:
        updated = replacement + "\n\n" + log_text
    return updated


def append_row(log_text: str, row: str) -> str:
    return log_text.rstrip("\n") + "\n" + row + "\n"



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    args = parser.parse_args()

    if not PROPOSAL_PATH.exists():
        print("ERROR: research/proposal.json not found.")
        return 1
    proposal = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    change = str(proposal["change"]).strip()
    hypothesis = str(proposal["hypothesis"]).strip()
    param_overrides = proposal.get("params")
    hypothesis_class = str(proposal.get("class", "unclassified")).strip().lower()
    initialization = str(proposal.get("initialization", "transfer")).strip().lower()
    baseline = bool(proposal.get("baseline", False))

    log_text = LOG_PATH.read_text(encoding="utf-8")
    index = next_index(log_text)
    best_before = current_best(log_text)
    model_dir: Path | None = None
    code_diff = ""
    previous_config: dict | None = None
    config_written = False

    try:
        if initialization not in {"transfer", "fresh"}:
            raise ValueError("initialization must be 'transfer' or 'fresh'")
        if baseline and initialization != "transfer":
            raise ValueError("the baseline must use transfer initialization")
        if baseline and not BASELINE_PENDING_PATH.exists():
            raise ValueError("baseline requested but research/BASELINE_PENDING is absent")

        immutable_env_overrides = {"max_episode_steps", "frame_skip"} & set(
            (param_overrides or {}).get("env", {})
        )
        if immutable_env_overrides:
            raise ValueError(
                f"immutable environment parameters cannot be changed: "
                f"{sorted(immutable_env_overrides)}"
            )
        code_diff = git("diff", "--stat", *RESEARCH_DIFF_PATHS).strip()
        if baseline and (param_overrides or code_diff):
            raise ValueError("baseline requires no parameter overrides or code edits")
        if param_overrides and code_diff:
            raise ValueError(
                "proposal contains both params and a code edit - use one or the other"
            )
        if not baseline and not param_overrides and not code_diff:
            print("ERROR: no parameter overrides and no code diff - nothing to test.")
            return 1
        if initialization == "transfer" and param_overrides and param_overrides.get(
            "policy"
        ):
            raise ValueError(
                "policy changes require initialization='fresh' because checkpoint "
                "tensor shapes may be incompatible"
            )

        if code_diff:
            changed_files = {
                line.strip()
                for line in git("diff", "--name-only", *RESEARCH_DIFF_PATHS).splitlines()
                if line.strip()
            }
            allowed_code_files = set(BASE_ALLOWED_CODE_FILES)
            if "learning algorithm" in hypothesis_class or "broader" in hypothesis_class:
                allowed_code_files.update(ALGORITHM_CODE_FILES)
            outside = changed_files - allowed_code_files
            if outside:
                raise ValueError(
                    f"edits touch files outside the allowed research surface: "
                    f"{sorted(outside)}"
                )

        previous_config = load_experiment_config()
        effective_params = merge_param_overrides(previous_config, param_overrides or {})

        if param_overrides:
            validate_param_overrides(param_overrides)
            write_experiment_config(effective_params)
            config_written = True
            print(f"[runner] parameter mode: applying {param_overrides}")
        else:
            print("[runner] code mode: running checks (ruff, pytest)...")
            run_module("ruff", "check", ".")
            checks = run_module("pytest", "-q")
            if "failed" in checks:
                raise RuntimeError("pytest reported failures")
            from robot_learning.environments.reach_env import TwoJointArmReachEnv

            probe_env = TwoJointArmReachEnv()
            assert_immutable_invariants(probe_env)
            print("[runner] immutable invariants verified")

        print(f"[runner] training started: {args.timesteps} steps, seed {TRAIN_SEED}")
        print("[runner] progress updates every 15 s (checkpoints every 5k steps)")
        started = time.time()
        train_log = ROOT / "research" / "last_train.log"
        train_command = [
            sys.executable,
            "-m",
            "robot_learning.train",
            "--timesteps",
            str(args.timesteps),
            "--seed",
            str(TRAIN_SEED),
        ]
        if initialization == "transfer":
            if not BASELINE_MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"baseline model not found: {BASELINE_MODEL_PATH}"
                )
            train_command.extend(["--resume", str(BASELINE_MODEL_PATH)])

        with train_log.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                train_command,
                cwd=ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
            last_reported = -1
            while process.poll() is None:
                time.sleep(15)
                candidates = [
                    p
                    for p in MODELS_DIR.glob("*/checkpoints/reach_*_steps.zip")
                    if p.stat().st_mtime >= started
                ]
                if candidates:
                    latest = max(
                        int(re.search(r"_(\d+)_steps\.zip$", p.name).group(1))
                        for p in candidates
                    )
                    if latest > last_reported:
                        elapsed = time.time() - started
                        print(
                            f"[train] {latest} / {args.timesteps} steps "
                            f"({elapsed:.0f}s elapsed)"
                        )
                        last_reported = latest
        write_training_summary()
        if process.returncode != 0:
            tail = train_log.read_text(encoding="utf-8").splitlines()[-15:]
            raise RuntimeError("training failed:\n" + "\n".join(tail))

        run_dirs = sorted(MODELS_DIR.glob("reach-*"), key=lambda p: p.stat().st_mtime)
        model_dir = run_dirs[-1]
        model_zip = str(model_dir / "model.zip")
        print(f"[runner] training done in {time.time() - started:.0f}s")

        print(f"[runner] evaluating on {EVAL_EPISODES} fresh episodes (~1-2 min)...")
        eval_started = time.time()
        eval_out = run_module(
            "robot_learning.evaluate",
            "--model",
            model_zip,
            "--episodes",
            str(EVAL_EPISODES),
        )
        rate = re.search(r"Success rate: (\d+)/(\d+) \((\d+(?:\.\d+)?)%\)", eval_out)
        dists = re.search(r"mean (\d+(?:\.\d+)?), median (\d+(?:\.\d+)?)", eval_out)
        if not rate or not dists:
            raise RuntimeError("could not parse evaluation output")

        success = float(rate.group(3))
        mean_dist = dists.group(1)
        median_dist = dists.group(2)
        print(
            f"[runner] evaluation done in {time.time() - eval_started:.0f}s: "
            f"{success:g}% success"
        )

    except Exception as error:  # noqa: BLE001
        if code_diff and not param_overrides:
            git("checkout", "--", *RESEARCH_DIFF_PATHS)
        if config_written and previous_config is not None:
            write_experiment_config(previous_config)
        row = (
            f"| {index} | {time.strftime('%Y-%m-%d')} | {change} | {hypothesis} "
            f"| - | - | - | error ({str(error)[:80]}) |"
        )
        LOG_PATH.write_text(append_row(log_text, row), encoding="utf-8")
        PROPOSAL_PATH.unlink(missing_ok=True)
        print(
            "SUMMARY: "
            + json.dumps(
                {"status": "error", "index": index, "error": str(error)[:300]}
            )
        )
        return 1

    improved = baseline or success > best_before
    equal = success == best_before
    if baseline:
        verdict = "kept (baseline)"
    elif improved:
        verdict = "kept"
    elif equal:
        verdict = "reverted (equal)"
    else:
        verdict = "reverted (worse)"

    row = (
        f"| {index} | {time.strftime('%Y-%m-%d')} | {change} | {hypothesis} "
        f"| {success:g} | {mean_dist} | {median_dist} | {verdict} |"
    )
    log_text = append_row(log_text, row)
    if improved:
        log_text = set_best_line(log_text, success, index)
    LOG_PATH.write_text(log_text, encoding="utf-8")

    if improved and param_overrides:
        write_experiment_config(effective_params)

    files_to_commit = ["research/EXPERIMENTS.md", "research/current_params.json"]
    if improved and code_diff:
        files_to_commit.extend(RESEARCH_DIFF_PATHS)
    if baseline:
        BASELINE_PENDING_PATH.unlink(missing_ok=True)
        files_to_commit.append("research/BASELINE_PENDING")

    if improved:
        git("add", *files_to_commit)
        git("commit", "-m", f"exp {index}: {change} -> {success:g}%")
    else:
        if config_written:
            write_experiment_config(previous_config)
        if code_diff:
            git("checkout", "--", *RESEARCH_DIFF_PATHS)
        if model_dir is not None and model_dir.exists():
            shutil.rmtree(model_dir, ignore_errors=True)
    PROPOSAL_PATH.unlink(missing_ok=True)

    summary = {
        "status": "ok",
        "index": index,
        "change": change,
        "success_percent": success,
        "best_before": best_before,
        "improved": improved,
        "verdict": verdict,
    }

    if improved and success >= GOAL_PERCENT:
        (SENTINEL_DIR / "GOAL_REACHED").write_text(
            f"Goal reached at experiment {index}: {success:g}%.\n", encoding="utf-8"
        )
        summary["sentinel"] = "GOAL_REACHED"

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["last_experiment"] = index
    state["last_class"] = hypothesis_class
    state["last_verdict"] = verdict
    if baseline:
        state["baseline_experiment"] = index
        state["baseline_success_percent"] = success
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print("=" * 60)
    print(
        f"Experiment {index} finished: {success:g}% success "
        f"(previous best {best_before:g}%)"
    )
    print(f"Change tested : {change}")
    print(f"Verdict       : {verdict}" + ("  -> committed to git" if improved else ""))
    if "sentinel" in summary:
        print(f"Loop outcome  : {summary['sentinel']}")
    print("=" * 60)
    print("SUMMARY: " + json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
