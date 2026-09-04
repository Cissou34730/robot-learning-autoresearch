import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_reset_persists_a_canonical_accepted_artifact(tmp_path):
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    root = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    research_dir = root / "research"
    research_dir.mkdir(parents=True)
    shutil.copy2(
        Path(__file__).resolve().parents[2] / "reset_research.ps1",
        root / "reset_research.ps1",
    )
    (research_dir / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "test", str(root)], check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=root, check=True
    )

    subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(root / "reset_research.ps1"),
            "-Mode",
            "Fresh",
            "-Force",
        ],
        cwd=root,
        check=True,
    )

    state = json.loads(
        (research_dir / "research_state.json").read_text(encoding="utf-8-sig")
    )
    assert state["accepted_artifact"] == "research/checkpoints/accepted"


SCRIPT = Path(__file__).resolve().parents[2] / "reset_research.ps1"
CAMPAIGN = "d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f"
EVALUATION = f"research/evaluations/{CAMPAIGN}/baseline.json"
LOG = f"research/training_logs/{CAMPAIGN}/experiment-1-attempt-1.log"


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


@pytest.fixture(scope="module")
def reset_template(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("reset-template")
    root = tmp_path / "repo with spaces"
    root.mkdir()
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(root, "init", "-b", "development")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "remote", "add", "origin", str(remote))
    shutil.copy2(SCRIPT, root / SCRIPT.name)
    state = {
        "schema_version": 3,
        "last_experiment": 1,
        "last_allocated_experiment": 1,
        "campaign": {"id": CAMPAIGN},
        "accepted_artifact": "research/checkpoints/accepted",
        "accepted_metrics": {"success_percent": 66},
        "accepted_evaluations": [EVALUATION],
        "retained_lineages": [],
    }
    write(root, "research/research_state.json", json.dumps(state))
    write(root, "research/checkpoints/accepted/artifact.json", '{"completed": true}')
    write(root, "research/current_params.json", '{"seed": 0}')
    write(
        root,
        "research/results.jsonl",
        json.dumps({"campaign_id": CAMPAIGN, "index": 1}) + "\n",
    )
    for name in (
        "robot_learning/scenario/reward.py",
        "robot_learning/scenario/policy_io.py",
        "robot_learning/training/checkpoint.py",
        "robot_learning/train.py",
        "tests/scenario/test_reward.py",
        "tests/training/test_policy.py",
        "research/scenario.md",
        "research/postmortems.md",
        "research/EXPERIMENTS.md",
        "research/checkpoints/accepted/model.zip",
        "research/checkpoints/accepted/vecnormalize.pkl",
        "research/checkpoints/accepted/policy_runtime.pkl",
        EVALUATION,
    ):
        write(root, name, "baseline\n")
    for name in (
        "research/program.md",
        "research/instruments.md",
        "research/runner_execution.py",
        "robot_learning/policy_runtime.py",
        "robot_learning/benchmark/final_benchmark.py",
        "robot_learning/scenario/__init__.py",
        "tests/benchmark/test_contract.py",
    ):
        write(root, name, "old harness\n")
    write(root, "robot_learning/benchmark/final_contract.py", "fixed task\n")
    write(
        root,
        ".gitignore",
        "research/training_logs/\nmodels/\nresearch/brief.md\nresearch/last_train_summary.md\nresearch/proposal.json\n",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "prepared baseline")
    baseline = git(root, "rev-parse", "HEAD")
    write(root, LOG, "baseline raw training log\n")
    for name in (
        "research/program.md",
        "research/instruments.md",
        "research/runner_execution.py",
        "robot_learning/policy_runtime.py",
        "robot_learning/benchmark/final_benchmark.py",
        "robot_learning/scenario/__init__.py",
        "tests/benchmark/test_contract.py",
    ):
        write(root, name, "current harness\n")
    for name in (
        "robot_learning/scenario/reward.py",
        "tests/scenario/test_reward.py",
        "robot_learning/scenario/later.py",
        "tests/training/later.py",
        "research/evaluations/later.json",
        "research/checkpoints/retained/later/model.zip",
        "research/BASELINE_PENDING",
    ):
        write(root, name, "later science\n")
    state.update(last_experiment=5, last_allocated_experiment=5)
    write(root, "research/research_state.json", json.dumps(state))
    git(root, "add", ".")
    git(root, "commit", "-m", "later campaign and harness")
    write(root, "research/proposal.json", "stale ignored control\n")
    write(root, "research/brief.md", "stale brief\n")
    write(root, "research/last_train_summary.md", "stale summary\n")
    write(root, "models/candidates/later/model.zip", "disposable\n")
    return root, baseline


@pytest.fixture
def baseline_repository(reset_template, tmp_path):
    # The immutable fixture history is built once. Each test gets its own full
    # copy and bare remote; no campaign or Git state is shared between resets.
    template, baseline = reset_template
    root = tmp_path / "repo with spaces"
    shutil.copytree(template, root)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(root, "remote", "set-url", "origin", str(remote))
    return root, baseline


def reset(root, *arguments):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell is unavailable")
    return subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(root / SCRIPT.name),
            *arguments,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_baseline_restores_science_and_evidence_in_current_branch(baseline_repository):
    root, baseline = baseline_repository
    branch = git(root, "branch", "--show-current")
    worktrees = git(root, "worktree", "list", "--porcelain")
    result = reset(root, "-Mode", "Baseline", "-BaselineRef", baseline, "-Force")
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(root, "branch", "--show-current") == branch
    assert git(root, "worktree", "list", "--porcelain").count(
        "worktree "
    ) == worktrees.count("worktree ")
    assert git(root, "status", "--porcelain") == ""
    assert git(root, "rev-parse", "HEAD") == git(
        root, "rev-parse", "origin/development"
    )
    for name in (
        "robot_learning/scenario/reward.py",
        "tests/scenario/test_reward.py",
        "robot_learning/training/checkpoint.py",
        "tests/training/test_policy.py",
        "research/checkpoints/accepted/model.zip",
        "research/checkpoints/accepted/vecnormalize.pkl",
        "research/checkpoints/accepted/policy_runtime.pkl",
        EVALUATION,
    ):
        assert (root / name).read_bytes() == b"baseline\n"
    for name in (
        "research/program.md",
        "research/instruments.md",
        "research/runner_execution.py",
        "robot_learning/policy_runtime.py",
        "robot_learning/benchmark/final_benchmark.py",
        "robot_learning/scenario/__init__.py",
        "tests/benchmark/test_contract.py",
    ):
        assert (root / name).read_bytes() == b"current harness\n"
    for name in (
        "robot_learning/scenario/later.py",
        "tests/training/later.py",
        "research/BASELINE_PENDING",
        "research/proposal.json",
        "research/brief.md",
        "research/last_train_summary.md",
        "research/evaluations/later.json",
        "research/checkpoints/retained",
        "models/candidates",
    ):
        assert not (root / name).exists()
    state = json.loads((root / "research/research_state.json").read_text())
    assert state["last_experiment"] == state["last_allocated_experiment"] == 1
    assert state["campaign"]["id"] == CAMPAIGN
    assert git(root, "ls-files", "--", LOG) == LOG
    assert (root / LOG).read_text() == "baseline raw training log\n"
    # Replay from the new commit needs no external source for ignored logs.
    prepared = git(root, "rev-parse", "HEAD")
    result = reset(
        root,
        "-Mode",
        "Baseline",
        "-BaselineRef",
        prepared,
        "-TrainingLogSource",
        str(root / "nonexistent"),
        "-Force",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(root, "rev-parse", "HEAD") == prepared


def test_fresh_clears_campaign_but_keeps_current_science(baseline_repository):
    root, _ = baseline_repository
    result = reset(root, "-Mode", "Fresh", "-Force")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "robot_learning/scenario/reward.py").read_text() == "later science\n"
    assert (root / "tests/scenario/test_reward.py").read_text() == "later science\n"
    assert (root / "research/BASELINE_PENDING").exists()
    assert not (root / "research/checkpoints").exists()
    assert not (root / "research/evaluations").exists()
    assert not (root / "research/training_logs").exists()
    assert not (root / "research/last_train_summary.md").exists()
    state = json.loads(
        (root / "research/research_state.json").read_text(encoding="utf-8-sig")
    )
    assert state["last_experiment"] == 0
    assert state["campaign"]["id"] != CAMPAIGN
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "problem",
    [
        "missing_mode",
        "missing_ref",
        "fresh_with_ref",
        "dirty",
        "unfinished",
        "missing_logs",
        "missing_runtime",
        "missing_evidence",
        "changed_task",
    ],
)
def test_refuses_before_mutation(baseline_repository, problem):
    root, baseline = baseline_repository
    args = ["-Mode", "Baseline", "-BaselineRef", baseline, "-Force"]
    if problem == "missing_mode":
        args = ["-Force"]
    elif problem == "missing_ref":
        args = ["-Mode", "Baseline", "-Force"]
    elif problem == "fresh_with_ref":
        args[1] = "Fresh"
    elif problem == "dirty":
        write(root, "research/program.md", "uncommitted development\n")
    elif problem == "unfinished":
        args[3] = "HEAD"
    elif problem == "missing_logs":
        (root / LOG).unlink()
    elif problem in {"missing_runtime", "missing_evidence"}:
        # Build an incomplete baseline commit without moving the active branch.
        git(root, "checkout", "--detach", baseline)
        missing = (
            "research/checkpoints/accepted/policy_runtime.pkl"
            if problem == "missing_runtime"
            else EVALUATION
        )
        git(root, "rm", "--", missing)
        git(root, "commit", "-m", "incomplete fixture")
        args[3] = git(root, "rev-parse", "HEAD")
        git(root, "checkout", "development")
    elif problem == "changed_task":
        write(root, "robot_learning/benchmark/final_contract.py", "different task\n")
        git(root, "add", ".")
        git(root, "commit", "-m", "different task")
    head = git(root, "rev-parse", "HEAD")
    status = git(root, "status", "--porcelain")
    candidate = (root / "models/candidates/later/model.zip").read_bytes()
    result = reset(root, *args)
    assert result.returncode != 0
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == status
    assert (root / "models/candidates/later/model.zip").read_bytes() == candidate
    assert (root / "research/brief.md").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing regression")
def test_locked_history_is_detected_before_deleting_candidates(baseline_repository):
    root, _ = baseline_repository
    head = git(root, "rev-parse", "HEAD")
    with (root / "research/results.jsonl").open("rb"):
        result = reset(root, "-Mode", "Fresh", "-Force")
    assert result.returncode != 0
    assert git(root, "rev-parse", "HEAD") == head
    assert (root / "models/candidates/later/model.zip").exists()
    assert (root / "research/checkpoints/accepted/model.zip").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
def test_cleanup_refuses_a_junction_to_another_directory(baseline_repository, tmp_path):
    import _winapi

    root, _ = baseline_repository
    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside, "keep.txt", "must survive")
    junction = root / "models/candidates/linked"
    _winapi.CreateJunction(str(outside), str(junction))
    try:
        head = git(root, "rev-parse", "HEAD")
        result = reset(root, "-Mode", "Fresh", "-Force")
        assert result.returncode != 0
        assert "linked paths" in result.stderr
        assert git(root, "rev-parse", "HEAD") == head
        assert (outside / "keep.txt").read_text() == "must survive"
    finally:
        # Remove the junction itself, not the outside directory it points at.
        junction.rmdir()
