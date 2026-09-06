import json
import subprocess
from argparse import Namespace
from pathlib import Path

from research import reset_campaign, run_experiment, runner_paths
from research import runner_execution as execution
from research import runner_protocol as protocol
from research import runner_repository as repository
from robot_learning.training import research_config


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(root: Path, relative: str, content: str) -> Path:
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")
    return destination


def redirect_paths(monkeypatch, root: Path) -> None:
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
        "ACCEPTED_DIR": research / "checkpoints" / "accepted",
        "CANDIDATE_ROOT": root / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in replacements.items():
        monkeypatch.setattr(runner_paths, name, value)
    monkeypatch.setattr(
        research_config, "CONFIG_PATH", research / "current_params.json"
    )
    monkeypatch.setattr(
        reset_campaign,
        "reset_backup_root",
        lambda: root / ".git" / "research-reset-backups",
    )


def reasoning() -> dict:
    return {
        "evidence": [{"source": "research/results.jsonl", "observation": "Measured."}],
        "alternative": "The observed behavior may not persist.",
        "expected_observation": "Continuation preserves the measured behavior.",
        "contradicting_observation": "Continuation loses the measured behavior.",
        "initialization_reason": "Continue the selected parent unchanged.",
        "strategy_link": "Test whether the established recipe benefits from continuation.",
    }


def test_campaign_lifecycle_survives_recipe_restore_and_clean_clone(
    monkeypatch, tmp_path
):
    root = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    root.mkdir()
    git(tmp_path, "init", "--bare", str(remote))
    git(root, "init", "-b", "master")
    git(root, "config", "user.name", "Test Runner")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "core.longpaths", "true")
    git(root, "remote", "add", "origin", str(remote))
    redirect_paths(monkeypatch, root)
    write(
        root,
        ".gitignore",
        "__pycache__/\n*.pyc\nmodels/\nresearch/checkpoints/challengers/\n"
        "research/training_logs/\nresearch/proposal.json\n"
        "research/evaluation_request.json\n",
    )
    write(root, "robot_learning/benchmark/final_contract.py", "TASK = 'fixed'\n")
    write(root, "robot_learning/scenario/reward.py", "RECIPE = 'A'\n")
    write(root, "research/current_params.json", '{"recipe": "A"}\n')
    write(root, "tests/scenario/test_reward.py", "EXPECTED = 'A'\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "recipe A")
    recipe_a = git(root, "rev-parse", "HEAD")

    write(root, "robot_learning/scenario/reward.py", "RECIPE = 'B'\n")
    write(root, "research/current_params.json", '{"recipe": "B"}\n')
    write(root, "robot_learning/scenario/recipe_b_only.py", "ACTIVE = True\n")
    old_state = repository.empty_v4_campaign_state(
        campaign={"id": "old-campaign", "started_at": "then", "base_commit": recipe_a},
        last_verdict="old campaign",
    )
    repository.write_state(old_state)
    write(root, "research/results.jsonl", "")
    write(root, "research/EXPERIMENTS.md", "old history\n")
    write(root, "research/postmortems.md", "old analysis\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "recipe B and old campaign")
    git(root, "push", "origin", "HEAD")

    campaign_id, source, _ = reset_campaign.reset_fresh(recipe_a)

    assert source == recipe_a
    assert (root / "robot_learning/scenario/reward.py").read_text() == "RECIPE = 'A'\n"
    assert json.loads((root / "research/current_params.json").read_text()) == {
        "recipe": "A"
    }
    assert not (root / "robot_learning/scenario/recipe_b_only.py").exists()
    reset_state = repository.read_state()
    assert reset_state["campaign"]["recipe_source_commit"] == recipe_a
    assert reset_state["campaign_experiment_counters"] == {campaign_id: 0}
    assert reset_state["working_lineage"] is None
    assert reset_state["best_known_lineage"] is None

    validated_recipes: list[str] = []
    training_calls: list[tuple[int, int, Path | None, str]] = []
    evaluation_calls: list[bytes] = []

    def validate_configuration():
        recipe = json.loads(research_config.CONFIG_PATH.read_text())["recipe"]
        assert (root / "robot_learning/scenario/reward.py").read_text() == (
            f"RECIPE = '{recipe}'\n"
        )
        validated_recipes.append(recipe)

    def train_candidate(output_dir, timesteps, seed, resume, training_log, **kwargs):
        del training_log
        marker = f"experiment-{len(training_calls) + 1}".encode()
        training_calls.append((timesteps, seed, resume, kwargs["label"]))
        artifact = output_dir / "final_checkpoint"
        artifact.mkdir(parents=True)
        artifact.joinpath("model.zip").write_bytes(marker)
        artifact.joinpath("artifact.json").write_text(
            json.dumps({"completed": True, "timesteps": timesteps}),
            encoding="utf-8",
        )
        artifact.joinpath("policy_runtime.pkl").write_bytes(b"runtime:" + marker)
        return 0.0

    def evaluate_artifact(artifact, seed, output_path, **kwargs):
        del kwargs
        model = Path(artifact).joinpath("model.zip").read_bytes()
        evaluation_calls.append(model)
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0 if model == b"experiment-1" else 100.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {
                    "episode": 1,
                    "episode_seed": seed + 1,
                    "success": model == b"experiment-2",
                },
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(
        execution, "validate_active_configuration", validate_configuration
    )
    monkeypatch.setattr(execution, "validate_dependency_metadata", lambda: None)
    monkeypatch.setattr(execution, "run_validation_suites", lambda paths: None)
    monkeypatch.setattr(execution, "train_candidate", train_candidate)
    monkeypatch.setattr(execution, "evaluate_artifact", evaluate_artifact)
    monkeypatch.setattr(protocol, "evaluation_semantics_fingerprint", lambda: "test")
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    baseline = {
        "baseline": True,
        "change": "Fresh baseline",
        "hypothesis": "Establish the initial baseline.",
        "class": "baseline",
        "initialization": "fresh",
    }
    assert (
        run_experiment.run_training_experiment(
            baseline, Namespace(timesteps=100, reuse_candidate=None)
        )
        == 0
    )
    assert training_calls == [(100, 0, None, "baseline training")]
    first = repository.read_state()["pending_analysis"]
    first_candidate = first["candidates"][0]["name"]
    runner_paths.EVALUATION_REQUEST_PATH.write_text(
        json.dumps(
            {
                "experiment": 1,
                "question": "How does the baseline behave?",
                "reason": "Establish reusable development evidence.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": first_candidate,
                        "episodes": 2,
                        "seed": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert run_experiment.execute_pending_evaluations() == 0
    first = repository.read_state()["pending_analysis"]
    first_evidence = first["candidates"][0]["evaluations"][0]["evaluation_artifact"]
    runner_paths.POSTMORTEM_PATH.write_text(
        f"## {campaign_id} / Experiment 1\n\n"
        "**Hypothesis assessment:** The baseline establishes measured behavior.\n\n"
        f"**Evidence inspected:** `{first_evidence}`\n",
        encoding="utf-8",
    )
    first_decision = {
        "previous_result_decision": {
            "experiment": 1,
            "continue_from": first_candidate,
            "reason": "Continue the measured baseline.",
            "best_known": {
                "candidate": first_candidate,
                "reason": "It is the only measured model.",
                "evidence": [first_evidence],
            },
            "code": {"action": "keep", "reason": "Keep recipe A."},
        }
    }
    assert (
        run_experiment.resolve_pending_lineage(first_decision, repository.read_state())
        == 0
    )
    first_closed = repository.read_state()
    first_working = first_closed["working_lineage"]
    assert (
        first_working["fingerprint"]
        == first_closed["best_known_lineage"]["fingerprint"]
    )
    assert first_working["artifact"] == first_closed["best_known_lineage"]["artifact"]
    assert first_working["artifact"].startswith("research/checkpoints/retained/")

    write(root, "robot_learning/scenario/reward.py", "RECIPE = 'B'\n")
    write(root, "research/current_params.json", '{"recipe": "B"}\n')
    write(root, "robot_learning/scenario/recipe_b_only.py", "ACTIVE = True\n")
    git(root, "add", "robot_learning/scenario", "research/current_params.json")
    git(root, "commit", "-m", "change to recipe B")
    git(root, "push", "origin", "HEAD")

    continuation = {
        "kind": "continuation",
        "family": "training.duration",
        "hypothesis": "Recipe A benefits from more training.",
        "reasoning": reasoning(),
        "initialization": "transfer",
        "training_parent": "working",
    }
    assert (
        run_experiment.run_training_experiment(
            continuation, Namespace(timesteps=100, reuse_candidate=None)
        )
        == 0
    )
    assert validated_recipes == ["A", "A"]
    assert not (root / "robot_learning/scenario/recipe_b_only.py").exists()
    assert training_calls[1][0:2] == (100, 0)
    assert training_calls[1][2] == root / first_working["artifact"] / "model.zip"
    second = repository.read_state()["pending_analysis"]
    second_candidate = second["candidates"][0]["name"]
    runner_paths.EVALUATION_REQUEST_PATH.write_text(
        json.dumps(
            {
                "experiment": 2,
                "question": "Did continuation improve on identical episodes?",
                "reason": "Compare against the reusable baseline panel.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": second_candidate,
                        "episodes": 2,
                        "seed": 10,
                    }
                ],
                "paired_comparisons": [
                    {"candidate": second_candidate, "reference": "working"}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert run_experiment.execute_pending_evaluations() == 0
    assert evaluation_calls == [b"experiment-1", b"experiment-2"]
    second = repository.read_state()["pending_analysis"]
    comparison = second["result"]["paired_comparisons"][0]
    assert comparison["source_artifacts"][1] == first_evidence
    second_evidence = second["candidates"][0]["evaluations"][0]["evaluation_artifact"]
    runner_paths.POSTMORTEM_PATH.write_text(
        f"## {campaign_id} / Experiment 2\n\n"
        "**Hypothesis assessment:** The continuation improved on the reused panel.\n\n"
        f"**Evidence inspected:** `{second_evidence}`, `{first_evidence}`\n",
        encoding="utf-8",
    )
    second_decision = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": second_candidate,
            "reason": "Continue the improved trajectory.",
            "code": {"action": "keep", "reason": "Keep restored recipe A."},
        }
    }
    assert (
        run_experiment.resolve_pending_lineage(second_decision, repository.read_state())
        == 0
    )

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "clone", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    cloned_state = json.loads(
        clone.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    cloned_results = [
        json.loads(line)
        for line in clone.joinpath("research/results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert [record["status"] for record in cloned_results] == ["closed", "closed"]
    assert cloned_results[1]["paired_comparisons"][0]["source_artifacts"][1] == (
        first_evidence
    )
    assert cloned_state["pending_closure_operation"] is None
    assert cloned_state["working_lineage"]["training_steps"] == 200
    assert (
        cloned_state["best_known_lineage"]["fingerprint"]
        == first_working["fingerprint"]
    )
    assert clone.joinpath("robot_learning/scenario/reward.py").read_text() == (
        "RECIPE = 'A'\n"
    )
    assert not clone.joinpath("robot_learning/scenario/recipe_b_only.py").exists()
    for role in ("working_lineage", "best_known_lineage"):
        artifact = clone / cloned_state[role]["artifact"]
        for filename in ("model.zip", "artifact.json", "policy_runtime.pkl"):
            assert artifact.joinpath(filename).is_file()
        assert (
            repository.artifact_fingerprint(artifact)
            == cloned_state[role]["fingerprint"]
        )
