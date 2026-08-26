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

from robot_learning.training.research_config import (
    assert_immutable_invariants,
    escalation_ladder,
    load_experiment_config,
    merge_param_overrides,
    validate_param_overrides,
    write_experiment_config,
)

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "research" / "EXPERIMENTS.md"
PROPOSAL_PATH = ROOT / "research" / "proposal.json"
STATE_PATH = ROOT / "research" / "research_state.json"
ESCALATION_PATH = ROOT / "research" / "ESCALATION_REQUEST"
SENTINEL_DIR = ROOT / "research"
CODE_DIR = "robot_learning"
MODELS_DIR = ROOT / "models"
ALLOWED_CODE_FILES = {
    "robot_learning/rewards/reach_reward.py",
    "robot_learning/environments/reach_env.py",
    "tests/test_reach_env.py",
}

TIMESTEPS = 120000
EVAL_EPISODES = 200
TRAIN_SEED = 0
GOAL_PERCENT = 98.0
STAGNATION_WINDOW = 5

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
    param_overrides = proposal.get("params")

    log_text = LOG_PATH.read_text(encoding="utf-8")
    index = next_index(log_text)
    best_before = current_best(log_text)
    model_dir: Path | None = None

    try:
        code_diff = git("diff", "--stat", CODE_DIR).strip()
        if param_overrides and code_diff:
            raise ValueError(
                "proposal contains both params and a code edit - use one or the other"
            )
        if not param_overrides and not code_diff:
            print("ERROR: no parameter overrides and no code diff - nothing to test.")
            return 1

        hypothesis_class = str(proposal.get("class", "")).strip().lower()
        if not hypothesis_class:
            raise ValueError(
                "proposal must include a 'class' field naming the ladder level "
                "(e.g. 'reward structure')"
            )

        if code_diff:
            changed_files = {
                line.split("|")[0].strip()
                for line in git("diff", "--name-only", CODE_DIR).splitlines()
                if line.strip()
            }
            outside = changed_files - ALLOWED_CODE_FILES
            if outside:
                raise ValueError(
                    f"edits touch files outside the allowed research surface: "
                    f"{sorted(outside)}"
                )

        previous_config = load_experiment_config()
        effective_params = merge_param_overrides(previous_config, param_overrides or {})
        config_written = False

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
        with train_log.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "robot_learning.train",
                    "--timesteps",
                    str(args.timesteps),
                    "--seed",
                    str(TRAIN_SEED),
                ],
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
        git("checkout", "--", CODE_DIR)
        if config_written:
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

    if improved and param_overrides:
        write_experiment_config(effective_params)

    files_to_commit = ["research/EXPERIMENTS.md", "research/current_params.json"]
    if improved and code_diff:
        files_to_commit.append(CODE_DIR)

    if improved:
        git("add", *files_to_commit)
        git("commit", "-m", f"exp {index}: {change} -> {success:g}%")
    else:
        if config_written:
            write_experiment_config(previous_config)
        if code_diff:
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

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if improved:
        state["consecutive_failures"] = 0
    else:
        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
    if hypothesis_class:
        state["hypothesis_class"] = hypothesis_class
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    verdicts = recent_verdicts(LOG_PATH.read_text(encoding="utf-8"), STAGNATION_WINDOW)
    completed_recent = [v for v in verdicts if v and not v.startswith("error")]
    exhausted = (
        len(completed_recent) == STAGNATION_WINDOW
        and all(v.startswith("reverted") for v in completed_recent)
        and not (SENTINEL_DIR / "ESCALATION_REQUEST").exists()
    )
    if exhausted:
        ladder = escalation_ladder()
        current_class = state.get("hypothesis_class", ladder[0])
        if current_class in ladder:
            next_index_in_ladder = min(
                ladder.index(current_class) + 1, len(ladder) - 1
            )
        else:
            next_index_in_ladder = 1
        next_class = ladder[next_index_in_ladder]
        (SENTINEL_DIR / "ESCALATION_REQUEST").write_text(
            f"{STAGNATION_WINDOW} consecutive experiments in class "
            f"'{current_class}' produced no improvement (best remains "
            f"{best_before:g}%).\n\n"
            f"ESCALATION: the next researcher must stop tuning '{current_class}' "
            f"and propose experiments from the next ladder class:\n"
            f"  >>> {next_class} <<<\n\n"
            f"Read the postmortems in research/postmortems.md first, analyse the "
            f"accumulated evidence, and form a coherent hypothesis in the new "
            f"class.\n",
            encoding="utf-8",
        )
        summary["escalation"] = next_class
        state["hypothesis_class"] = next_class
        state["consecutive_failures"] = 0
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
