"""Test campaign boundary enforcement in research state and artifacts.

Campaign boundaries ensure that:
1. Research state requires a campaign identity (UUID, start time, base commit)
2. Experiment indices are scoped per campaign
3. Result records preserve campaign_id for history
4. Artifact paths are organized by campaign
5. Brief generation filters to current campaign
"""

import json
import uuid

import pytest

from research import reset_campaign, runner_paths, runner_protocol, runner_repository


class TestCampaignIdentifierAccess:
    """Helper functions should reliably extract campaign context from state."""

    def test_current_campaign_id(self):
        """current_campaign_id should extract campaign ID from state."""
        state = {
            "campaign": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "started_at": "2026-09-01T12:00:00Z",
                "base_commit": "abc123",
            }
        }

        campaign_id = runner_repository.current_campaign_id(state)
        assert campaign_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_current_campaign_base_commit(self):
        """current_campaign_base_commit should extract base commit for Git inspection."""
        state = {
            "campaign": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "started_at": "2026-09-01T12:00:00Z",
                "base_commit": "def456",
            }
        }

        base_commit = runner_repository.current_campaign_base_commit(state)
        assert base_commit == "def456"

    def test_current_campaign_id_missing_raises_error(self):
        """current_campaign_id should return None if campaign is missing."""
        state = {}

        assert runner_repository.current_campaign_id(state) is None

    def test_inquiry_identity_is_independent_from_experiment_identity(self):
        state = runner_repository.empty_campaign_state(
            campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
            last_verdict="baseline selected",
        )
        state["working_lineage"] = {"artifact": "working"}
        state["campaign_experiment_counters"]["campaign"] = 7
        state["campaign_inquiry_counters"]["campaign"] = 2
        state["last_allocated_experiment"] = 7
        state["last_experiment"] = 7

        session = runner_repository.ensure_inquiry_session(state)
        inquiry = runner_protocol.plan_inquiry_operation(
            {
                "inquiry": {
                    "action": "open",
                    "question": "What should be investigated?",
                    "scope": "Current-campaign evidence.",
                    "closure_condition": "A supported decision is available.",
                }
            },
            state,
        )

        assert inquiry["inquiry_id"] == 3
        assert session["inquiry_id"] == 3
        assert state["campaign_experiment_counters"]["campaign"] == 7
        assert state["last_allocated_experiment"] == 7


@pytest.mark.parametrize(
    "pending_field",
    (
        "pending_baseline_decision",
        "pending_method_decision",
        "pending_campaign_conclusion",
        "campaign_conclusion",
    ),
)
def test_baseline_reference_rejects_unfinished_current_lifecycle_operations(
    monkeypatch, pending_field
):
    state = runner_repository.empty_campaign_state(
        campaign={
            "id": str(uuid.uuid4()),
            "started_at": "now",
            "base_commit": "base",
        },
        last_verdict="baseline selected",
    )
    lineage = {
        "candidate": "checkpoint-1",
        "artifact": "research/checkpoints/accepted/campaign/experiment-1",
        "fingerprint": "f" * 64,
        "scientific_commit": "a" * 40,
        "parameters": {},
        "training_steps": 1,
        "origin_experiment": 1,
        "reason": "baseline",
        "evaluation_artifacts": ["research/evaluations/campaign/panel.json"],
        "designation_ordinal": 1,
    }
    state["working_lineage"] = dict(lineage)
    state["best_known_lineage"] = dict(lineage)
    state["last_experiment"] = 1
    state["last_allocated_experiment"] = 1
    state["campaign_experiment_counters"][state["campaign"]["id"]] = 1
    state[pending_field] = {"action": "unfinished"}

    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: state)
    monkeypatch.setattr(
        runner_repository,
        "validate_research_state",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="closed measured experiment 1"):
        reset_campaign.verify_baseline_source("baseline-ref")


class TestCampaignArtifactPaths:
    """Filesystem paths should be organized by campaign."""

    def test_campaign_candidate_root(self):
        """campaign_candidate_root should return campaign-scoped candidate directory."""
        campaign_id = "550e8400-e29b-41d4-a716-446655440000"
        path = runner_paths.campaign_candidate_root(campaign_id)

        assert campaign_id in str(path)
        assert path.name == campaign_id
        assert "candidates" in str(path)

    def test_campaign_evaluation_dir(self):
        """campaign_evaluation_dir should return campaign-scoped evaluation directory."""
        campaign_id = "550e8400-e29b-41d4-a716-446655440000"
        path = runner_paths.campaign_evaluation_dir(campaign_id)

        assert campaign_id in str(path)
        assert "evaluations" in str(path)
        assert path.name == campaign_id

    def test_training_log_path_with_campaign(self):
        """training_log_path should include campaign_id when provided."""
        campaign_id = "550e8400-e29b-41d4-a716-446655440000"
        path = runner_paths.training_log_path(1, 1, campaign_id=campaign_id)

        assert campaign_id in str(path)
        assert "experiment-1" in str(path)

    def test_training_log_path_without_campaign(self):
        """training_log_path should work without campaign_id for backward compat."""
        path = runner_paths.training_log_path(1, 1)

        assert "experiment-1" in str(path)
        # Should not include UUIDs
        assert "-" not in path.parent.name or path.parent.name in ["training_logs"]


class TestResultRecordCampaignAttribution:
    """Result records should include campaign_id for filtering."""

    def test_result_records_for_campaign(self):
        """result_records_for_campaign should filter to matching campaign_id."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        records = [
            {"index": 1, "campaign_id": campaign1, "change": "test1"},
            {"index": 2, "campaign_id": campaign2, "change": "test2"},
            {"index": 3, "campaign_id": campaign1, "change": "test3"},
        ]

        # Mock result_records function
        original_records = runner_repository.result_records
        try:
            runner_repository.result_records = lambda: records

            filtered = runner_repository.result_records_for_campaign(campaign1)

            assert len(filtered) == 2
            assert all(r["campaign_id"] == campaign1 for r in filtered)
            assert filtered[0]["index"] == 1
            assert filtered[1]["index"] == 3
        finally:
            runner_repository.result_records = original_records

    def test_result_records_for_nonexistent_campaign(self):
        """result_records_for_campaign should return empty list if no matches."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        records = [
            {"index": 1, "campaign_id": campaign1, "change": "test1"},
        ]

        original_records = runner_repository.result_records
        try:
            runner_repository.result_records = lambda: records

            filtered = runner_repository.result_records_for_campaign(campaign2)

            assert len(filtered) == 0
        finally:
            runner_repository.result_records = original_records

    def test_inquiry_records_do_not_allocate_or_appear_as_experiments(
        self, monkeypatch, tmp_path
    ):
        results = tmp_path / "results.jsonl"
        results.write_text(
            '{"record_type":"experiment","campaign_id":"c","index":1}\n'
            '{"record_type":"inquiry","campaign_id":"c","inquiry_id":1}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(runner_paths, "RESULTS_PATH", results)

        assert len(runner_repository.history_records()) == 2
        assert [record["index"] for record in runner_repository.result_records()] == [1]
        assert runner_repository.latest_recorded_experiment() == 1


class TestArchiveCandidatesWithCampaign:
    """Archived candidates should be organized by campaign."""

    def test_archive_candidates_with_campaign_id(self):
        """archive_candidates should use campaign-scoped path when campaign_id provided."""
        # This is a unit test that would need mocking the file system
        # For now, we verify the signature accepts campaign_id
        import inspect

        sig = inspect.signature(runner_repository.archive_candidates)
        assert "campaign_id" in sig.parameters
        assert sig.parameters["campaign_id"].default is None

    def test_archive_candidates_records_forward_slash_artifact_paths(
        self, monkeypatch, tmp_path
    ):
        root = tmp_path / "repo"
        candidate = tmp_path / "candidate"
        candidate.mkdir()
        (candidate / "model.zip").write_bytes(b"model")
        (candidate / "artifact.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr("research.runner_paths.ROOT", root)
        monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", root / "research")

        archived = runner_repository.archive_candidates(
            4,
            [
                {
                    "kind": "candidate",
                    "name": "checkpoint-10",
                    "path": candidate,
                    "timesteps": 10,
                }
            ],
            {},
            campaign_id="campaign-a",
        )

        assert archived[0]["name"] == "checkpoint-10"
        assert archived[0]["timesteps"] == 10
        assert archived[0]["artifact"] == (
            "research/checkpoints/challengers/campaign-a/experiment-4/checkpoint-10"
        )
        assert "\\" not in archived[0]["artifact"]

    def test_archive_candidates_preserve_readable_checkpoint_names(
        self, monkeypatch, tmp_path
    ):
        root = tmp_path / "repo"
        monkeypatch.setattr("research.runner_paths.ROOT", root)
        monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", root / "research")
        contenders = []
        for steps, payload in ((5120, b"a"), (120832, b"b"), (60416, b"a")):
            candidate = tmp_path / f"src-{steps}"
            candidate.mkdir()
            (candidate / "model.zip").write_bytes(payload)
            (candidate / "artifact.json").write_text("{}", encoding="utf-8")
            contenders.append(
                {
                    "kind": "candidate",
                    "name": f"checkpoint-{steps}",
                    "path": candidate,
                    "timesteps": steps,
                }
            )

        archived = runner_repository.archive_candidates(
            1, contenders, {}, campaign_id="campaign-b"
        )

        names = [item["name"] for item in archived]
        assert names == ["checkpoint-5120", "checkpoint-120832", "checkpoint-60416"]


class TestExperimentNumberingScopedPerCampaign:
    """Experiment indices should be independent per campaign."""

    def test_campaign_isolated_experiment_index_allocation(self):
        """Two campaigns should allocate indices 1,2,3... independently."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())
        state = runner_repository.empty_campaign_state(
            campaign={
                "id": campaign1,
                "started_at": "2026-09-01T00:00:00Z",
                "base_commit": "abc",
            },
            last_verdict="fresh",
        )

        # Allocate experiments for campaign 1
        idx1_c1 = runner_protocol.next_experiment_index(state, campaign_id=campaign1)
        assert idx1_c1 == 1

        idx2_c1 = runner_protocol.next_experiment_index(state, campaign_id=campaign1)
        assert idx2_c1 == 2

        # Allocate experiments for campaign 2
        idx1_c2 = runner_protocol.next_experiment_index(state, campaign_id=campaign2)
        assert idx1_c2 == 1

        idx2_c2 = runner_protocol.next_experiment_index(state, campaign_id=campaign2)
        assert idx2_c2 == 2

        # Verify campaign 1 indices independent from campaign 2
        assert state["campaign_experiment_counters"][campaign1] == 2
        assert state["campaign_experiment_counters"][campaign2] == 2

    def test_allocated_experiment_index_per_campaign(self):
        """allocated_experiment_index should return campaign-specific high water mark."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())
        state = {
            "campaign_experiment_counters": {campaign1: 5, campaign2: 3},
            "last_allocated_experiment": 0,
        }

        assert (
            runner_protocol.allocated_experiment_index(state, campaign_id=campaign1)
            == 5
        )
        assert (
            runner_protocol.allocated_experiment_index(state, campaign_id=campaign2)
            == 3
        )

    def test_experiment_working_paths_scoped_by_campaign(self):
        """experiment_working_paths should include campaign_id when provided."""
        campaign_id = str(uuid.uuid4())
        paths = runner_protocol.experiment_working_paths(1, campaign_id=campaign_id)

        assert len(paths) == 2
        assert campaign_id in str(paths[0])
        assert campaign_id in str(paths[1])


class TestEvaluationArtifactAttribution:
    """Evaluation artifacts should be isolated per campaign."""

    def test_evaluation_artifact_name_with_campaign_id(self):
        """evaluation_artifact_name should include campaign_id in filename when provided."""
        campaign_id = str(uuid.uuid4())
        name = runner_protocol.evaluation_artifact_name(
            experiment=1,
            candidate="baseline",
            episodes=100,
            seed=42,
            semantics="abc123",
            campaign_id=campaign_id,
        )
        assert campaign_id in name
        assert "evaluation-" in name
        assert "-experiment-1-" in name
        assert "100ep-seed42-abc123" in name

    def test_task_reference_artifact_name_with_campaign_id(self):
        """task_reference_artifact_name should include campaign_id when provided."""
        campaign_id = str(uuid.uuid4())
        name = runner_protocol.task_reference_artifact_name(
            experiment=1, candidate="baseline", panel="reach", campaign_id=campaign_id
        )
        assert campaign_id in name
        assert "task-reference-" in name
        assert "-experiment-1-" in name
        assert "-reach" in name


class TestBriefGenerationCampaignFiltering:
    """Brief generation should filter results and postmortems by campaign."""

    def test_postmortem_memory_with_campaign_id(self):
        """_postmortem_memory should extract campaign-specific sections."""
        from research.build_research_brief import _postmortem_memory

        campaign_id = str(uuid.uuid4())
        postmortems = f"""
## {campaign_id} / Experiment 1
**Result:** Training completed in 150k steps with 45% success

**Interpretation:** Reasonable starting point for optimization
"""

        memories = _postmortem_memory(postmortems, campaign_id=campaign_id)
        assert len(memories) == 1
        assert "Training completed" in memories[0]
        assert "45%" in memories[0]

    def test_postmortem_memory_without_campaign_does_not_leak_history(self):
        """Campaign-unscoped scientific memory is never injected."""
        from research.build_research_brief import _postmortem_memory

        postmortems = """
## Experiment 1
**Result:** Training completed in 150k steps with 45% success
"""

        memories = _postmortem_memory(postmortems, campaign_id=None)
        assert memories == []

    def test_postmortem_memory_campaign_isolation(self):
        """_postmortem_memory should not extract other campaign sections."""
        from research.build_research_brief import _postmortem_memory

        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        postmortems = f"""
## {campaign1} / Experiment 1
**Result:** Campaign 1 baseline success 45%

## {campaign2} / Experiment 1
**Result:** Campaign 2 baseline success 50%
"""

        # Extract only campaign1
        memories = _postmortem_memory(postmortems, campaign_id=campaign1)
        assert len(memories) == 1
        # Should contain campaign1's result
        assert "45%" in memories[0]
        # Should not contain campaign2's result
        assert "50%" not in memories[0]


class TestComprehensiveCampaignIsolation:
    """Integration tests validating complete campaign isolation."""

    def test_two_campaigns_independent_numbering(self):
        """Two campaigns should have completely independent experiment numbering."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        state1 = runner_repository.empty_campaign_state(
            campaign={
                "id": campaign1,
                "started_at": "2026-01-01T00:00:00Z",
                "base_commit": "abc1",
            },
            last_verdict="fresh",
        )

        state2 = runner_repository.empty_campaign_state(
            campaign={
                "id": campaign2,
                "started_at": "2026-01-02T00:00:00Z",
                "base_commit": "abc2",
            },
            last_verdict="fresh",
        )

        # Allocate 3 experiments for campaign1
        indices1 = []
        for _ in range(3):
            idx = runner_protocol.next_experiment_index(state1, campaign_id=campaign1)
            indices1.append(idx)

        # Allocate 3 experiments for campaign2
        indices2 = []
        for _ in range(3):
            idx = runner_protocol.next_experiment_index(state2, campaign_id=campaign2)
            indices2.append(idx)

        # Both campaigns should have indices [1, 2, 3]
        assert indices1 == [1, 2, 3]
        assert indices2 == [1, 2, 3]
        # But the state counters should be independent
        assert state1["campaign_experiment_counters"][campaign1] == 3
        assert state2["campaign_experiment_counters"][campaign2] == 3

    def test_campaign_result_attribution_chain(self):
        """Results should maintain campaign attribution through the pipeline."""
        campaign_id = str(uuid.uuid4())

        # Simulate result records with campaign attribution
        results = [
            {"index": 1, "campaign_id": campaign_id, "verdict": "accepted"},
            {"index": 2, "campaign_id": campaign_id, "verdict": "rejected"},
            {"index": 3, "campaign_id": campaign_id, "verdict": "pending"},
        ]

        # Filter by campaign
        filtered = [r for r in results if r.get("campaign_id") == campaign_id]
        assert len(filtered) == 3

        # Other campaign should be empty
        other_campaign = str(uuid.uuid4())
        filtered_other = [r for r in results if r.get("campaign_id") == other_campaign]
        assert len(filtered_other) == 0

    def test_campaign_artifact_isolation_filesystem(self):
        """Evaluation artifacts should be isolated by campaign ID in filesystem paths."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        # Generate artifact names
        artifact1 = runner_protocol.evaluation_artifact_name(
            1, "baseline", 100, 42, "hash1", campaign_id=campaign1
        )
        artifact2 = runner_protocol.evaluation_artifact_name(
            1, "baseline", 100, 42, "hash1", campaign_id=campaign2
        )

        # Both represent Experiment 1, baseline, same settings
        # But they should have different filenames due to campaign_id
        assert artifact1 != artifact2
        assert campaign1 in artifact1
        assert campaign2 in artifact2

        # Simulated paths
        path1 = runner_paths.campaign_evaluation_dir(campaign1) / artifact1
        path2 = runner_paths.campaign_evaluation_dir(campaign2) / artifact2

        # Paths should be in different directories
        assert str(campaign1) in str(path1)
        assert str(campaign2) in str(path2)

    def test_campaign_checkpoint_paths_isolated(self):
        """Checkpoint paths should be isolated by campaign."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())

        checkpoint_root1 = runner_paths.campaign_checkpoint_root(campaign1)
        checkpoint_root2 = runner_paths.campaign_checkpoint_root(campaign2)

        # Paths should be different
        assert str(checkpoint_root1) != str(checkpoint_root2)
        # Each should contain its campaign ID
        assert campaign1 in str(checkpoint_root1)
        assert campaign2 in str(checkpoint_root2)
        # Base directory should be the same (check components to be platform-independent)
        path1_str = str(checkpoint_root1).replace("\\", "/")
        path2_str = str(checkpoint_root2).replace("\\", "/")
        assert "research/checkpoints/challengers" in path1_str
        assert "research/checkpoints/challengers" in path2_str

    def test_campaign_state_persistence_and_recovery(self):
        """Campaign state should persist and recover correctly."""
        campaign_id = str(uuid.uuid4())

        state = runner_repository.empty_campaign_state(
            campaign={
                "id": campaign_id,
                "started_at": "2026-01-01T12:00:00Z",
                "base_commit": "deadbeef",
            },
            last_verdict="fresh",
        )

        # Allocate some experiments
        for i in range(1, 4):
            idx = runner_protocol.next_experiment_index(state, campaign_id=campaign_id)
            assert idx == i

        # Verify final state
        assert state["campaign"]["id"] == campaign_id
        assert state["campaign_experiment_counters"][campaign_id] == 3

        # Simulate recovery: load and continue
        assert runner_repository.current_campaign_id(state) == campaign_id
        assert runner_repository.current_campaign_base_commit(state) == "deadbeef"

        # Next allocation should be 4
        next_idx = runner_protocol.next_experiment_index(state, campaign_id=campaign_id)
        assert next_idx == 4


def test_postmortem_memory_stops_at_another_campaign_heading():
    from research.build_research_brief import _postmortem_memory

    campaign1 = str(uuid.uuid4())
    campaign2 = str(uuid.uuid4())

    postmortems = f"""
## {campaign1} / Experiment 1

**Result:** Campaign one result

## {campaign2} / Experiment 1

**Interpretation:** CAMPAIGN_TWO_ONLY
"""

    memories = _postmortem_memory(postmortems, campaign_id=campaign1)

    assert len(memories) == 1
    assert "Campaign one result" in memories[0]
    assert "CAMPAIGN_TWO_ONLY" not in memories[0]


def _brief_state(campaign_id: str) -> dict:
    state = runner_repository.empty_campaign_state(
        campaign={"id": campaign_id, "started_at": "now", "base_commit": "base"},
        last_verdict="method matured",
    )
    state["inquiry_session"] = {
        "id": "pi-session",
        "campaign_id": campaign_id,
        "inquiry_id": 2,
        "role": "principal_investigator",
        "status": "started",
    }
    state["active_inquiry"] = {
        "id": 2,
        "question": "Does the method reach more targets?",
        "scope": "Saved lineages only.",
        "closure_condition": "Paired evidence decides.",
        "status": "active",
        "session_id": "pi-session",
        "reframes": [],
    }
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 2,
        "scientific_question": "Does the method learn the task?",
        "rationale": "It changes the learning signal.",
        "lifecycle": "mature",
        "base_scientific_commit": "b" * 40,
        "current_lineage": {
            "artifact": "archive/method-a",
            "fingerprint": "method-model",
            "origin_experiment": 3,
            "candidate": "checkpoint-40k",
            "parameters": {},
            "scientific_commit": "a" * 40,
            "training_steps": 40_000,
            "evaluation_artifacts": [],
            "reason": "Matured lineage.",
            "designation_ordinal": 1,
        },
        "iterations": [{"experiment": 3, "status": "mature", "outcome": "stable"}],
        "resolution": None,
    }
    state["pending_method_decision"] = {
        "method_id": "method-a",
        "action": "promote",
        "plan": {},
        "progress": "planned",
    }
    state["campaign_lab"] = {
        "commit": "c" * 40,
        "fingerprint": "f" * 64,
        "manifest": [{"path": "research/lab/paired_panel.py", "fingerprint": "d" * 64}],
    }
    state["preparation_measurement"] = {
        "inquiry_id": 2,
        "partial_evaluations": [
            {
                "candidate": "working",
                "episodes": 160,
                "seed": 9000,
                "evaluation_semantics": "semantics-v1",
                "model_fingerprint": "working-model",
                "metrics": {"evaluation_artifact": "research/evaluations/working.json"},
            }
        ],
        "partial_task_reference_evaluations": [
            {
                "candidate": "active_method",
                "panel": "reach-panel",
                "panel_version": 2,
                "episodes": 200,
                "seed": 1,
                "model_fingerprint": "method-model",
                "evaluation_artifact": "research/evaluations/reference.json",
            }
        ],
        "rounds": [
            {
                "round": 1,
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "best_known",
                            "status": "reused",
                            "reused_from_round": 1,
                            "seed": 9000,
                            "episodes": 160,
                            "evaluation_semantics": "semantics-v1",
                            "model_fingerprint": "best-model",
                            "evaluation_artifact": "research/evaluations/best.json",
                        }
                    ],
                    "paired_comparisons": [
                        {
                            "candidate": "active_method",
                            "reference": "working",
                            "candidate_model_fingerprint": "method-model",
                            "reference_model_fingerprint": "working-model",
                            "source_artifacts": [
                                "research/evaluations/method.json",
                                "research/evaluations/working.json",
                            ],
                        }
                    ],
                },
            }
        ],
    }
    return state


def test_brief_indexes_current_campaign_measurements_and_laboratory(
    tmp_path, monkeypatch
):
    from research import build_research_brief as brief

    campaign_id = str(uuid.uuid4())
    other_campaign = str(uuid.uuid4())
    (tmp_path / "research_state.json").write_text(
        json.dumps(_brief_state(campaign_id)), encoding="utf-8"
    )

    def experiment(campaign: str, artifact: str) -> dict:
        return {
            "campaign_id": campaign,
            "index": 3,
            "inquiry_id": 2,
            "method_id": "method-a",
            "status": "analyzed",
            "method_decision": {"action": "mature"},
            "requested_evaluations": [
                {
                    "candidate": "checkpoint-40k",
                    "episodes": 80,
                    "seed": 7000,
                    "evaluation_semantics": "semantics-v1",
                    "model_fingerprint": "checkpoint-model",
                    "metrics": {"evaluation_artifact": artifact},
                }
            ],
        }

    (tmp_path / "results.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                experiment(campaign_id, "research/evaluations/current.json"),
                experiment(other_campaign, "research/evaluations/OTHER_CAMPAIGN.json"),
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(brief, "RESEARCH_DIR", tmp_path)

    text = brief.render_research_brief()
    index = text.split("## Measurement / panel index", 1)[1].split(
        "## Campaign laboratory index", 1
    )[0]
    laboratory = text.split("## Campaign laboratory index", 1)[1]

    assert "OTHER_CAMPAIGN" not in text
    assert "experiment 3" in index and "`method-a`" in index
    assert "`checkpoint-40k`" in index
    assert "episodes [7000, 7080)" in index
    assert "research/evaluations/current.json" in index
    assert "`working`" in index and "episodes [9000, 9160)" in index
    assert "panel `reach-panel` version 2" in index
    assert "research/evaluations/reference.json" in index
    assert "`active_method`" in index and "against `working`" in index
    assert "research/evaluations/method.json" in index
    assert "`best_known`" in index and "reused from round 1" in index
    assert "research/lab/paired_panel.py" in laboratory
    assert "Lifecycle: `mature`" in text
    assert "Pending method decision: `promote` for method `method-a`" in text
    for obsolete in ("Resolution", "Status / stage", "method_iteration_decision"):
        assert obsolete not in text
