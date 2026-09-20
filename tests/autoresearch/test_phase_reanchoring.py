"""Every research phase adopts commits made since the previous anchor.

Issue #30: a campaign stopped after a human-owned harness fix was committed
resumed with a scientific parent anchored before that fix, so the proposal's
delta contained the human commit and the ownership validator attributed it to
the researcher. A phase must re-anchor the scientific parent to the current
HEAD before it reads or validates its delta; only what is still uncommitted
remains the researcher's change.
"""

import json
import subprocess
from pathlib import Path

from research import run_experiment
from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository

HUMAN_TEST_PATH = "tests/autoresearch/test_scenario_boundary.py"
RESEARCHER_PATH = "robot_learning/scenario/reward.py"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "researcher@example.com")
    _git(repo, "config", "user.name", "Researcher Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _scientific_memory(campaign_id: str) -> str:
    return (
        f"## {campaign_id} / Scientific strategy\n\n"
        "**Current synthesis:** Investigate the plateau.\n\n"
        "**Lessons and limits:** Progress slows; evidence.txt; one training seed.\n\n"
        "**Open questions:** Optimization or insufficient budget?\n\n"
        "**Reconsider when:** No progress after the additional training.\n"
    )


def _training_proposal() -> dict:
    return {
        "kind": "training",
        "family": "observation.representation",
        "investigation_type": "confirmatory",
        "hypothesis": "the current representation limits learning",
        "reasoning": {
            "evidence": [
                {"source": "evidence.txt", "observation": "Learning plateaus."}
            ],
            "alternative": "Insufficient training.",
            "expected_observation": "Progress resumes.",
            "contradicting_observation": "The plateau persists.",
            "initialization_reason": "Test the representation from initialization.",
            "objective_link": "Determine whether representation limits objective progress.",
        },
        "change": "change the observation representation",
        "initialization": "fresh",
        "params": {"ppo": {"gamma": 0.99}},
    }


def _evaluation_state(commit: str) -> dict:
    return {
        "accepted_artifact": "research/checkpoints/accepted",
        "pending_scientific_parent": commit,
        "pending_evaluation_request": {
            "experiment": 3,
            "champion_available": True,
            "candidates": [
                {
                    "name": "experiment-3",
                    "artifact": "models/candidates/experiment-3",
                }
            ],
        },
    }


def _evaluation_request() -> dict:
    return {
        "experiment": 3,
        "question": "does the intervention change the outcome",
        "reason": "the candidate must be measured before the next decision",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": "experiment-3",
                "episodes": 200,
                "seed": 1000,
                "selection": "the only model the hypothesis is about",
                "omitted_alternative": None,
            }
        ],
    }


def _capture_ownership(monkeypatch) -> list[list[str]]:
    seen: list[list[str]] = []
    original = protocol.validate_research_delta_ownership

    def spy(code_changes):
        seen.append(list(code_changes))
        return original(code_changes)

    monkeypatch.setattr(protocol, "validate_research_delta_ownership", spy)
    return seen


def test_hypothesis_phase_reanchors_to_head_after_a_human_commit(
    monkeypatch, tmp_path, capsys
):
    repo = tmp_path / "repo"
    _init_repo(repo)
    reward = repo / RESEARCHER_PATH
    boundary = repo / HUMAN_TEST_PATH
    _write(reward, "# researcher-owned scenario code\n")
    _write(boundary, "# human-owned environment boundary tests\n")
    _write(repo / "evidence.txt", "Measured progression\n")
    postmortem = repo / "research" / "postmortems.md"
    _write(postmortem, _scientific_memory("current"))
    commit_a = _commit(repo, "scientific parent")

    state_path = repo / "research" / "research_state.json"
    state = repository.empty_v4_campaign_state(
        campaign={
            "id": "current",
            "started_at": "2026-01-01T00:00:00Z",
            "base_commit": commit_a,
        },
        last_verdict="fresh baseline pending",
    )
    state["pending_scientific_parent"] = commit_a
    state_path.write_text(json.dumps(state), encoding="utf-8")

    # A human commit changes a human-owned test path after the anchor.
    _write(boundary, "# human-owned environment boundary tests\n# fixed\n")
    commit_b = _commit(repo, "human harness fix")

    # The researcher's live change is on a researcher-owned path.
    _write(reward, "# researcher-owned scenario code\n# intervention\n")

    monkeypatch.setattr(paths, "ROOT", repo)
    monkeypatch.setattr(paths, "STATE_PATH", state_path)
    proposal_path = repo / "research" / "proposal.json"
    monkeypatch.setattr(paths, "PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(paths, "POSTMORTEM_PATH", postmortem)

    # Before re-anchoring, the human commit is part of the phase's delta.
    assert HUMAN_TEST_PATH in repository.scientific_delta(commit_a)

    assert run_experiment.begin_hypothesis_phase() == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_scientific_parent"] == commit_b

    proposal_path.write_text(json.dumps(_training_proposal()), encoding="utf-8")
    seen = _capture_ownership(monkeypatch)

    assert run_experiment.check_proposal() == 0
    assert "PROPOSAL_VALID: training" in capsys.readouterr().out
    # Only the uncommitted researcher change is attributed to the proposal.
    assert seen
    assert all(entry == [RESEARCHER_PATH] for entry in seen)


def test_non_hypothesis_phase_reanchors_to_head_after_a_human_commit(
    monkeypatch, tmp_path, capsys
):
    repo = tmp_path / "repo"
    _init_repo(repo)
    reward = repo / RESEARCHER_PATH
    boundary = repo / HUMAN_TEST_PATH
    accepted = repo / "research" / "checkpoints" / "accepted"
    _write(reward, "# researcher-owned scenario code\n")
    _write(boundary, "# human-owned environment boundary tests\n")
    _write(accepted / "model.zip", "model\n")
    _write(accepted / "artifact.json", "{}\n")
    commit_a = _commit(repo, "scientific parent")

    state_path = repo / "research" / "research_state.json"
    state_path.write_text(json.dumps(_evaluation_state(commit_a)), encoding="utf-8")

    # A human commit changes a human-owned test path after the anchor.
    _write(boundary, "# human-owned environment boundary tests\n# fixed\n")
    commit_b = _commit(repo, "human harness fix")

    # The researcher's live change is on a researcher-owned path.
    _write(reward, "# researcher-owned scenario code\n# intervention\n")

    request_path = repo / "research" / "evaluation_request.json"
    request_path.write_text(json.dumps(_evaluation_request()), encoding="utf-8")

    monkeypatch.setattr(paths, "ROOT", repo)
    monkeypatch.setattr(paths, "STATE_PATH", state_path)
    monkeypatch.setattr(paths, "EVALUATION_REQUEST_PATH", request_path)

    assert HUMAN_TEST_PATH in repository.scientific_delta(commit_a)
    assert repository.scientific_delta(commit_b) == [RESEARCHER_PATH]

    original_state = state_path.read_bytes()
    seen = _capture_ownership(monkeypatch)

    # The evaluation-request phase re-anchors before validating its delta.
    assert run_experiment.check_evaluation_request() == 0
    assert "EVALUATION_REQUEST_VALID" in capsys.readouterr().out
    assert seen == [[RESEARCHER_PATH]]
    # A validation-only phase never rewrites the persisted anchor.
    assert state_path.read_bytes() == original_state
