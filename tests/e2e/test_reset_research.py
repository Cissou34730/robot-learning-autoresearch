import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from research import reset_campaign, runner_paths

ROOT = Path(__file__).resolve().parents[2]
RESET_FILES = (
    "research/reset_campaign.py",
    "research/runner_console.py",
    "research/runner_paths.py",
    "research/runner_protocol.py",
    "research/runner_repository.py",
)


def copy_reset_implementation(root):
    shutil.copy2(ROOT / "reset_research.ps1", root / "reset_research.ps1")
    for relative in RESET_FILES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def test_reset_persists_a_canonical_accepted_artifact(tmp_path):
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    root = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    research_dir = root / "research"
    research_dir.mkdir(parents=True)
    copy_reset_implementation(root)
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
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
    assert state["schema_version"] == 4
    assert state["working_lineage"] is None
    assert state["best_known_lineage"] is None


def test_fresh_reset_uses_linked_worktree_git_directory(tmp_path):
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell is unavailable")
    primary = tmp_path / "primary"
    linked = tmp_path / "linked"
    remote = tmp_path / "remote.git"
    primary.mkdir()
    git(tmp_path, "init", "--bare", str(remote))
    git(primary, "init", "-b", "primary")
    git(primary, "config", "user.name", "Test Runner")
    git(primary, "config", "user.email", "test@example.invalid")
    git(primary, "config", "core.autocrlf", "false")
    git(primary, "config", "core.longpaths", "true")
    git(primary, "remote", "add", "origin", str(remote))
    copy_reset_implementation(primary)
    write(primary, ".gitignore", "__pycache__/\n*.pyc\n")
    write(primary, "research/current_params.json", '{"seed": 0}\n')
    git(primary, "add", ".")
    git(primary, "commit", "-m", "seed")
    git(primary, "push", "-u", "origin", "primary")
    git(primary, "worktree", "add", "-b", "linked", str(linked), "HEAD")

    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(linked / "reset_research.ps1"),
            "-Mode",
            "Fresh",
            "-Force",
        ],
        cwd=linked,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (linked / ".git").is_file()
    backup_root = Path(
        git(
            linked,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "research-reset-backups",
        )
    )
    assert len(list(backup_root.glob("*/operation.json"))) == 1
    assert not (linked / ".git/research-reset-backups").exists()
    assert not git(linked, "status", "--porcelain", "--untracked-files=all")
    assert git(linked, "rev-parse", "HEAD") == git(
        linked, "rev-parse", "origin/linked"
    )


SCRIPT = ROOT / "reset_research.ps1"
HELPER = ROOT / "research" / "reset_campaign.py"
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


def test_reset_entry_point_exposes_fresh_recipe_restoration():
    wrapper = SCRIPT.read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")

    assert "[string]$RecipeRef" in wrapper
    assert '"Local\\RobotLearningAutoresearch"' in wrapper
    assert "uv run python research/reset_campaign.py" in wrapper
    assert 'parser.add_argument("--recipe-ref")' in helper
    assert '[Parameter(Mandatory, ParameterSetName = "Recover")]' in wrapper
    assert 'operation.add_argument("--recover")' in helper


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
    copy_reset_implementation(root)
    write(root, "research/current_params.json", '{"seed": 0}')
    for name in (
        "robot_learning/scenario/reward.py",
        "robot_learning/scenario/policy_io.py",
        "robot_learning/training/checkpoint.py",
        "robot_learning/train.py",
        "tests/scenario/test_reward.py",
        "tests/training/test_policy.py",
        "research/scenario.md",
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
        "__pycache__/\n*.pyc\nresearch/training_logs/\nmodels/\nresearch/brief.md\nresearch/last_train_summary.md\nresearch/proposal.json\n",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline scientific recipe")
    recipe = git(root, "rev-parse", "HEAD")
    artifact_json = json.dumps({"completed": True, "timesteps": 100_352})
    write(root, "research/checkpoints/accepted/artifact.json", artifact_json)
    for name in (
        "research/checkpoints/accepted/model.zip",
        "research/checkpoints/accepted/vecnormalize.pkl",
        "research/checkpoints/accepted/policy_runtime.pkl",
    ):
        write(root, name, "baseline\n")
    write(root, EVALUATION, "baseline\n")
    fingerprint = hashlib.sha256(
        b"baseline\n" + artifact_json.encode() + b"baseline\n" + b"baseline\n"
    ).hexdigest()
    evidence_fingerprint = hashlib.sha256(b"baseline\n").hexdigest()
    lineage = {
        "artifact": "research/checkpoints/accepted",
        "fingerprint": fingerprint,
        "origin_experiment": 1,
        "candidate": "checkpoint-100",
        "parameters": {"seed": 0},
        "scientific_commit": recipe,
        "training_steps": 100_352,
        "evaluation_artifacts": [EVALUATION],
        "reason": "Strongest measured baseline.",
    }
    decision = {
        "experiment": 1,
        "continue_from": "checkpoint-100",
        "best_known": {
            "action": "designate",
            "candidate": "checkpoint-100",
            "reason": "Strongest measured baseline.",
        },
        "reason": "Strongest measured baseline.",
        "code": {"action": "keep", "reason": "No scientific change."},
    }
    state = {
        "schema_version": 4,
        "last_experiment": 1,
        "last_allocated_experiment": 1,
        "campaign": {
            "id": CAMPAIGN,
            "started_at": "2026-01-01T00:00:00Z",
            "base_commit": recipe,
        },
        "campaign_experiment_counters": {CAMPAIGN: 1},
        "working_lineage": lineage,
        "best_known_lineage": dict(lineage),
        "retained_lineages": [],
        "pending_analysis": None,
        "pending_training_operation": None,
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_closure_operation": None,
        "pending_scientific_parent": None,
        "pending_final_benchmark": None,
        "terminal_campaign_status": None,
        "official_metrics": None,
        "last_lineage_decision": decision,
        "last_verdict": "researcher selected checkpoint-100",
    }
    record = {
        "schema_version": 4,
        "campaign_id": CAMPAIGN,
        "index": 1,
        "kind": "training",
        "change": "Fresh baseline",
        "hypothesis": "Measure the baseline.",
        "hypothesis_assessment": "The baseline reached 66%.",
        "candidates": [
            {
                "name": "checkpoint-100",
                "timesteps": 100_352,
                "evaluations": [
                    {
                        "evaluation_artifact": EVALUATION,
                        "evaluation_artifact_fingerprint": evidence_fingerprint,
                        "model_fingerprint": fingerprint,
                        "episodes": 200,
                        "seed": 1,
                        "success_percent": 66,
                    }
                ],
            }
        ],
        "status": "closed",
        "decision_pending": False,
        "verdict": "researcher selected checkpoint-100",
        "closure_decision": decision,
        "postmortem": "research/postmortems.md",
    }
    write(root, "research/research_state.json", json.dumps(state))
    write(root, "research/results.jsonl", json.dumps(record) + "\n")
    write(root, "research/EXPERIMENTS.md", "baseline derived history\n")
    write(
        root,
        "research/postmortems.md",
        f"# Research postmortems\n\n## {CAMPAIGN} / Experiment 1\n\n"
        f"**Evidence inspected:** `{EVALUATION}`\n",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "prepared v4 baseline")
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
        timeout=120,
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
    assert state["schema_version"] == 4
    assert state["working_lineage"]["artifact"] == "research/checkpoints/accepted"
    assert state["working_lineage"]["candidate"] == "checkpoint-100"
    expected_fingerprint = hashlib.sha256(
        b"".join(
            (root / "research/checkpoints/accepted" / name).read_bytes()
            for name in (
                "model.zip",
                "artifact.json",
                "vecnormalize.pkl",
                "policy_runtime.pkl",
            )
        )
    ).hexdigest()
    assert state["working_lineage"]["fingerprint"] == expected_fingerprint
    assert state["best_known_lineage"]["fingerprint"] == expected_fingerprint
    recipe = state["working_lineage"]["scientific_commit"]
    assert git(root, "cat-file", "-t", recipe) == "commit"
    record = json.loads((root / "research/results.jsonl").read_text())
    assert record["schema_version"] == 4
    assert record["status"] == "closed"
    assert record["decision_pending"] is False
    assert record["closure_decision"] == state["last_lineage_decision"]
    assert record["postmortem"] == "research/postmortems.md"
    experiment_log = (root / "research/EXPERIMENTS.md").read_text()
    assert "working checkpoint-100; best known checkpoint-100" in experiment_log
    assert "awaiting researcher analysis" not in experiment_log
    assert (
        f"## {CAMPAIGN} / Experiment 1"
        in (root / "research/postmortems.md").read_text()
    )
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
    replayed = json.loads((root / "research/research_state.json").read_text())
    assert replayed["schema_version"] == 4
    assert replayed["working_lineage"]["scientific_commit"] == recipe
    assert replayed["best_known_lineage"]["scientific_commit"] == recipe


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
    assert state["schema_version"] == 4
    assert state["working_lineage"] is None
    assert state["best_known_lineage"] is None
    assert git(root, "status", "--porcelain") == ""


def test_fresh_recipe_restores_science_without_importing_baseline_evidence(
    baseline_repository,
):
    root, baseline = baseline_repository
    source_state = json.loads(
        git(root, "show", f"{baseline}:research/research_state.json")
    )
    recipe = source_state["working_lineage"]["scientific_commit"]
    old_head = git(root, "rev-parse", "HEAD")

    result = reset(
        root,
        "-Mode",
        "Fresh",
        "-RecipeRef",
        recipe,
        "-Force",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert recipe in result.stdout
    assert "No trained model, score, evidence" in result.stdout
    assert (root / "robot_learning/scenario/reward.py").read_text() == "baseline\n"
    assert (root / "tests/scenario/test_reward.py").read_text() == "baseline\n"
    assert not (root / "robot_learning/scenario/later.py").exists()
    assert not (root / "tests/training/later.py").exists()
    assert (root / "research/program.md").read_text() == "current harness\n"
    assert (
        root / "robot_learning/policy_runtime.py"
    ).read_text() == "current harness\n"
    assert not (root / "research/checkpoints").exists()
    assert not (root / "research/evaluations").exists()
    state = json.loads((root / "research/research_state.json").read_text())
    assert state["campaign"]["recipe_source_commit"] == recipe
    assert state["campaign"]["id"] != CAMPAIGN
    assert state["campaign_experiment_counters"] == {state["campaign"]["id"]: 0}
    assert state["last_experiment"] == state["last_allocated_experiment"] == 0
    assert state["working_lineage"] is None
    assert state["best_known_lineage"] is None
    assert state["retained_lineages"] == []
    assert (root / "research/BASELINE_PENDING").exists()
    assert (root / "research/results.jsonl").read_text() == ""
    assert git(root, "rev-list", "--count", f"{old_head}..HEAD") == "2"
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.parametrize("problem", ["missing_ref", "invalid_json", "changed_task"])
def test_recipe_ref_refuses_invalid_sources_before_mutation(
    baseline_repository, problem
):
    root, baseline = baseline_repository
    source_state = json.loads(
        git(root, "show", f"{baseline}:research/research_state.json")
    )
    recipe = source_state["working_lineage"]["scientific_commit"]
    if problem == "missing_ref":
        recipe = "missing-recipe"
    else:
        git(root, "checkout", "--detach", recipe)
        if problem == "invalid_json":
            write(root, "research/current_params.json", "not json\n")
        else:
            write(
                root, "robot_learning/benchmark/final_contract.py", "different task\n"
            )
        git(root, "add", ".")
        git(root, "commit", "-m", f"invalid recipe: {problem}")
        recipe = git(root, "rev-parse", "HEAD")
        git(root, "checkout", "development")
    head = git(root, "rev-parse", "HEAD")
    candidate = (root / "models/candidates/later/model.zip").read_bytes()

    result = reset(root, "-Mode", "Fresh", "-RecipeRef", recipe, "-Force")

    assert result.returncode != 0
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == ""
    assert (root / "models/candidates/later/model.zip").read_bytes() == candidate


def test_reset_refuses_while_campaign_mutex_is_held(baseline_repository):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell is unavailable")
    root, _ = baseline_repository
    holder = subprocess.Popen(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$created=$false; "
                "$mutex=[Threading.Mutex]::new($true,'Local\\RobotLearningAutoresearch',[ref]$created); "
                "[Console]::Out.WriteLine('READY'); [Console]::Out.Flush(); "
                "[Console]::In.ReadLine() | Out-Null; $mutex.ReleaseMutex(); $mutex.Dispose()"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "READY"
        head = git(root, "rev-parse", "HEAD")
        result = reset(root, "-Mode", "Fresh", "-Force")
        assert result.returncode != 0
        assert "already running" in result.stderr
        assert git(root, "rev-parse", "HEAD") == head
    finally:
        if holder.stdin is not None:
            holder.stdin.write("\n")
            holder.stdin.flush()
        holder.wait(timeout=30)


def test_push_failure_keeps_recovery_backup_and_never_reports_success(
    baseline_repository,
):
    root, baseline = baseline_repository
    source_state = json.loads(
        git(root, "show", f"{baseline}:research/research_state.json")
    )
    recipe = source_state["working_lineage"]["scientific_commit"]
    git(root, "remote", "set-url", "origin", str(root / "missing-remote.git"))

    result = reset(root, "-Mode", "Fresh", "-RecipeRef", recipe, "-Force")

    assert result.returncode != 0
    assert "reset_research.ps1 -Recover" in result.stderr
    assert "New campaign ID" not in result.stdout
    backups = list((root / ".git/research-reset-backups").glob("*/operation.json"))
    assert len(backups) == 1
    operation = json.loads(backups[0].read_text())
    assert operation["mode"] == "fresh"
    assert operation["recipe_source_commit"] == recipe
    assert operation["backed_up"]
    assert "error" in operation
    assert (backups[0].parent / "files/research/research_state.json").is_file()


def redirect_reset_paths(monkeypatch, root):
    research = root / "research"
    replacements = {
        "ROOT": root,
        "RESEARCH_DIR": research,
        "LOG_PATH": research / "EXPERIMENTS.md",
        "RESULTS_PATH": research / "results.jsonl",
        "PROPOSAL_PATH": research / "proposal.json",
        "POSTMORTEM_PATH": research / "postmortems.md",
        "EVALUATION_REQUEST_PATH": research / "evaluation_request.json",
        "STATE_PATH": research / "research_state.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "BASELINE_PENDING_PATH": research / "BASELINE_PENDING",
        "RECOVERY_PENDING_PATH": research / "RECOVERY_PENDING",
        "RESTART_PENDING_PATH": research / "RESTART_PENDING",
        "GOAL_PATH": research / "GOAL_REACHED",
        "ACCEPTED_DIR": research / "checkpoints/accepted",
        "CANDIDATE_ROOT": root / "models/candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in replacements.items():
        monkeypatch.setattr(runner_paths, name, value)
    monkeypatch.setattr(
        reset_campaign,
        "reset_backup_root",
        lambda: root / ".git/research-reset-backups",
    )


@pytest.mark.parametrize("phase", ["restoration", "state", "commit"])
def test_internal_failure_keeps_recovery_backup(
    baseline_repository, monkeypatch, phase
):
    root, baseline = baseline_repository
    redirect_reset_paths(monkeypatch, root)
    source_state = json.loads(
        git(root, "show", f"{baseline}:research/research_state.json")
    )
    recipe = source_state["working_lineage"]["scientific_commit"]

    def fail(*_args, **_kwargs):
        raise RuntimeError(f"simulated {phase} failure")

    if phase == "restoration":
        monkeypatch.setattr(
            reset_campaign.repository, "apply_code_lineage_decision", fail
        )
        recipe_ref = recipe
    elif phase == "state":
        monkeypatch.setattr(reset_campaign.repository, "write_state", fail)
        recipe_ref = None
    else:
        monkeypatch.setattr(reset_campaign.repository, "commit_paths", fail)
        recipe_ref = None

    with pytest.raises(RuntimeError, match=r"reset_research\.ps1 -Recover"):
        reset_campaign.reset_fresh(recipe_ref)

    backups = list((root / ".git/research-reset-backups").glob("*/operation.json"))
    assert len(backups) == 1
    operation = json.loads(backups[0].read_text())
    assert operation["progress"] in {
        "backed_up",
        "campaign_initialized",
        "recipe_restored",
    }
    assert operation["error"] == f"simulated {phase} failure"
    assert (backups[0].parent / "files/research/research_state.json").is_file()


def test_baseline_accepts_measured_v4_roles(baseline_repository):
    root, baseline = baseline_repository
    state_path = root / "research/research_state.json"
    result = reset(root, "-Mode", "Baseline", "-BaselineRef", baseline, "-Force")

    assert result.returncode == 0, result.stdout + result.stderr
    restored = json.loads(state_path.read_text())
    assert restored["schema_version"] == 4
    assert restored["working_lineage"]["artifact"] == "research/checkpoints/accepted"
    assert restored["working_lineage"]["training_steps"] == 100_352
    assert restored["working_lineage"] == restored["best_known_lineage"]


def test_baseline_accepts_v4_retained(baseline_repository):
    root, baseline = baseline_repository
    git(root, "checkout", "--detach", baseline)
    retained = f"research/checkpoints/retained/{CAMPAIGN}/p"
    (root / retained).parent.mkdir(parents=True)
    shutil.move(root / "research/checkpoints/accepted", root / retained)
    state_path = root / "research/research_state.json"
    state = json.loads(state_path.read_text())
    state["working_lineage"]["artifact"] = retained
    state["best_known_lineage"]["artifact"] = retained
    write(root, "research/research_state.json", json.dumps(state))
    git(root, "add", "-A", "research/checkpoints", "research/research_state.json")
    git(root, "commit", "-m", "publish durable v4 baseline role")
    retained_baseline = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "development")

    result = reset(
        root,
        "-Mode",
        "Baseline",
        "-BaselineRef",
        retained_baseline,
        "-Force",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    restored = json.loads(state_path.read_text())
    assert restored["working_lineage"]["artifact"] == retained
    assert restored["best_known_lineage"]["artifact"] == retained
    for filename in (
        "model.zip",
        "artifact.json",
        "vecnormalize.pkl",
        "policy_runtime.pkl",
    ):
        assert (root / retained / filename).is_file()
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
        "mismatched_history",
        "mismatched_result_evidence",
        "mismatched_postmortem",
        "changed_task",
        "legacy",
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
    elif problem in {
        "mismatched_history",
        "mismatched_result_evidence",
        "mismatched_postmortem",
    }:
        git(root, "checkout", "--detach", baseline)
        if problem == "mismatched_history":
            write(
                root,
                "research/results.jsonl",
                json.dumps({"campaign_id": "another-campaign", "index": 1}) + "\n",
            )
        elif problem == "mismatched_result_evidence":
            record = json.loads((root / "research/results.jsonl").read_text())
            record["candidates"][0]["evaluations"] = []
            write(root, "research/results.jsonl", json.dumps(record) + "\n")
        else:
            write(
                root,
                "research/postmortems.md",
                f"## {CAMPAIGN} / Experiment 1\n\n"
                "**Evidence inspected:** research/evaluations/unrelated.json\n",
            )
        git(root, "add", "research")
        git(root, "commit", "-m", "incompatible scientific record")
        args[3] = git(root, "rev-parse", "HEAD")
        git(root, "checkout", "development")
    elif problem == "changed_task":
        write(root, "robot_learning/benchmark/final_contract.py", "different task\n")
        git(root, "add", ".")
        git(root, "commit", "-m", "different task")
    elif problem == "legacy":
        git(root, "checkout", "--detach", baseline)
        state = json.loads((root / "research/research_state.json").read_text())
        state["schema_version"] = 3
        write(root, "research/research_state.json", json.dumps(state))
        git(root, "add", "research/research_state.json")
        git(root, "commit", "-m", "unverifiable legacy fixture")
        args[3] = git(root, "rev-parse", "HEAD")
        git(root, "checkout", "development")
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
