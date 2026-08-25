"""Deterministic experiment runner for the autoresearch loop.

The research agent writes `research/proposal.json` and edits the allowed code
files. This script does everything else: verifies the diff, runs checks,
trains, evaluates, appends the results row, applies the ratchet, updates the
best-so-far marker, and manages the GOAL_REACHED / STAGNATED sentinels.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "research" / "EXPERIMENTS.md"
PROPOSAL_PATH = ROOT / "research" / "proposal.json"
SENTINEL_DIR = ROOT / "research"
CODE_DIR = "robot_learning"

TIMESTEPS = 60000
EVAL_EPISODES = 200
TRAIN_SEED = 0
GOAL_PERCENT = 98.0
STAGNATION_WINDOW = 5


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def run_module(module: str, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{module} failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    return result.stdout


def next_index(log_text: str) -> int:
    indices = [int(m) for m in re.findall(r"^\| (\d+) \|", log_text, flags=re.MULTILINE)]
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


def recent_verdicts(log_text: str, window: int) -> list[str]:
    rows = re.findall(r"^\| \d+ \|.+\|$", log_text, flags=re.MULTILINE)
    verdicts = []
    for row_text in rows[-window:]:
        cells = [c.strip() for c in row_text.split("|")]
        verdicts.append(cells[-2] if len(cells) >= 2 else "")
    return verdicts


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

    log_text = LOG_PATH.read_text(encoding="utf-8")
    index = next_index(log_text)
    best_before = current_best(log_text)
    model_dir: Path | None = None

    try:
        diff = git("diff", "--stat", CODE_DIR)
        if not diff.strip():
            print("ERROR: no code diff in robot_learning/ — nothing to test.")
            return 1

        print("Running checks (ruff, pytest)...")
        run_module("ruff", "check", ".")
        checks = run_module("pytest", "-q")
        if "failed" in checks:
            raise RuntimeError("pytest reported failures")

        print(f"Training ({args.timesteps} steps, seed {TRAIN_SEED})...")
        train_out = run_module(
            "robot_learning.train",
            "--timesteps", str(args.timesteps),
            "--seed", str(TRAIN_SEED),
        )
        match = re.search(r"Model saved to (.+)model\.zip", train_out)
        if not match:
            raise RuntimeError("could not locate saved model path in trainer output")
        model_dir = Path(match.group(1))
        model_zip = f"{match.group(1)}model.zip"

        print(f"Evaluating ({EVAL_EPISODES} episodes)...")
        eval_out = run_module(
            "robot_learning.evaluate",
            "--model", model_zip,
            "--episodes", str(EVAL_EPISODES),
        )
        rate = re.search(r"Success rate: \d+/\d+ \((\d+(?:\.\d+)?)%\)", eval_out)
        dists = re.search(
            r"mean (\d+(?:\.\d+)?), median (\d+(?:\.\d+)?)", eval_out
        )
        if not rate or not dists:
            raise RuntimeError("could not parse evaluation output")

        success = float(rate.group(1))
        mean_dist = dists.group(1)
        median_dist = dists.group(2)

    except Exception as error:  # noqa: BLE001
        git("checkout", "--", CODE_DIR)
        row = (
            f"| {index} | {time.strftime('%Y-%m-%d')} | {change} | {hypothesis} "
            f"| - | - | - | error ({str(error)[:80]}) |"
        )
        LOG_PATH.write_text(append_row(log_text, row), encoding="utf-8")
        PROPOSAL_PATH.unlink(missing_ok=True)
        print(f"SUMMARY: {{\"status\": \"error\", \"index\": {index}}}")
        return 1

    improved = success > best_before
    equal = success == best_before
    if improved:
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

    if improved:
        git("add", CODE_DIR, "research/EXPERIMENTS.md")
        git("commit", "-m", f"exp {index}: {change} -> {success:g}%")
    else:
        git("checkout", "--", CODE_DIR)
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

    verdicts = recent_verdicts(LOG_PATH.read_text(encoding="utf-8"), STAGNATION_WINDOW)
    completed_recent = [v for v in verdicts if v and not v.startswith("error")]
    if (
        len(completed_recent) == STAGNATION_WINDOW
        and all(v.startswith("reverted") for v in completed_recent)
        and not (SENTINEL_DIR / "STAGNATED").exists()
    ):
        (SENTINEL_DIR / "STAGNATED").write_text(
            f"{STAGNATION_WINDOW} consecutive experiments without improvement "
            f"(best remains {best_before:g}%). Recommend revisiting budget, task "
            f"definition, or observation design.\n",
            encoding="utf-8",
        )
        summary["sentinel"] = "STAGNATED"

    print("SUMMARY: " + json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
