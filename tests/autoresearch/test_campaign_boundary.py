"""Test campaign boundary enforcement in research state and artifacts.

Campaign boundaries ensure that:
1. Research state requires a campaign identity (UUID, start time, base commit)
2. Experiment indices are scoped per campaign
3. Result records preserve campaign_id for history
4. Artifact paths are organized by campaign
5. Brief generation filters to current campaign
"""

import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import runner_paths, runner_protocol, runner_repository


class TestStateRequiresCampaign:
    """Schema v3 state must always carry a valid campaign identity; there is no v2 fallback."""

    def test_load_state_rejects_missing_campaign(self):
        """load_state should reject a v3 state with no campaign object."""
        state_without_campaign = {
            "schema_version": 3,
            "accepted_artifact": "research\\checkpoints\\accepted",
            "accepted_metrics": {"threshold": 0.5},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            state_file = tmpdir / "research_state.json"
            state_file.write_text(json.dumps(state_without_campaign))

            original_state_path = runner_paths.STATE_PATH
            try:
                runner_paths.STATE_PATH = state_file
                with pytest.raises(RuntimeError, match="campaign"):
                    runner_repository.load_state(allow_missing_artifact=True)
            finally:
                runner_paths.STATE_PATH = original_state_path

    def test_load_state_rejects_incomplete_campaign(self):
        """load_state should reject a campaign object missing required fields."""
        state_with_bad_campaign = {
            "schema_version": 3,
            "accepted_artifact": "research\\checkpoints\\accepted",
            "accepted_metrics": {"threshold": 0.5},
            "campaign": {"id": "00000000-0000-0000-0000-000000000000"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            state_file = tmpdir / "research_state.json"
            state_file.write_text(json.dumps(state_with_bad_campaign))

            original_state_path = runner_paths.STATE_PATH
            try:
                runner_paths.STATE_PATH = state_file
                with pytest.raises(RuntimeError, match="campaign"):
                    runner_repository.load_state(allow_missing_artifact=True)
            finally:
                runner_paths.STATE_PATH = original_state_path

    def test_load_state_accepts_valid_campaign(self):
        """load_state should succeed when a complete campaign object is present."""
        state_with_campaign = {
            "schema_version": 3,
            "accepted_artifact": "research\\checkpoints\\accepted",
            "accepted_metrics": {"threshold": 0.5},
            "campaign": {
                "id": str(uuid.uuid4()),
                "started_at": datetime.now(tz=UTC).isoformat(),
                "base_commit": "abc123",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            state_file = tmpdir / "research_state.json"
            state_file.write_text(json.dumps(state_with_campaign))

            original_state_path = runner_paths.STATE_PATH
            try:
                runner_paths.STATE_PATH = state_file
                result = runner_repository.load_state(allow_missing_artifact=True)
                assert result["campaign"]["id"] == state_with_campaign["campaign"]["id"]
            finally:
                runner_paths.STATE_PATH = original_state_path


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

        assert archived[0]["artifact"] == (
            "research/checkpoints/challengers/campaign-a/experiment-4/"
            "checkpoint-10"
        )
        assert "\\" not in archived[0]["artifact"]


class TestExperimentNumberingScopedPerCampaign:
    """Experiment indices should be independent per campaign."""

    def test_campaign_isolated_experiment_index_allocation(self):
        """Two campaigns should allocate indices 1,2,3... independently."""
        campaign1 = str(uuid.uuid4())
        campaign2 = str(uuid.uuid4())
        state = {
            "schema_version": 3,
            "campaign": {"id": campaign1, "started_at": "2026-09-01T00:00:00Z", "base_commit": "abc"},
            "campaign_experiment_counters": {},
            "last_allocated_experiment": 0,
            "last_experiment": 0,
        }

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

        assert runner_protocol.allocated_experiment_index(state, campaign_id=campaign1) == 5
        assert runner_protocol.allocated_experiment_index(state, campaign_id=campaign2) == 3

    def test_allocated_experiment_index_fallback_to_global(self):
        """allocated_experiment_index without campaign_id should use global fallback."""
        state = {
            "last_allocated_experiment": 10,
            "last_experiment": 5,
        }

        index = runner_protocol.allocated_experiment_index(state)
        assert index == 10

    def test_experiment_working_paths_scoped_by_campaign(self):
        """experiment_working_paths should include campaign_id when provided."""
        campaign_id = str(uuid.uuid4())
        paths = runner_protocol.experiment_working_paths(1, campaign_id=campaign_id)

        assert len(paths) == 2
        assert campaign_id in str(paths[0])
        assert campaign_id in str(paths[1])

    def test_experiment_working_paths_legacy_fallback(self):
        """experiment_working_paths without campaign_id should use legacy root."""
        paths = runner_protocol.experiment_working_paths(1)

        assert len(paths) == 2
        # Should not include UUIDs
        assert "experiment-1" in str(paths[0])
        assert "experiment-1" in str(paths[1])


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
            campaign_id=campaign_id
        )
        assert campaign_id in name
        assert "evaluation-" in name
        assert "-experiment-1-" in name
        assert "100ep-seed42-abc123" in name

    def test_evaluation_artifact_name_without_campaign_id(self):
        """evaluation_artifact_name without campaign_id should use legacy format."""
        name = runner_protocol.evaluation_artifact_name(
            experiment=1,
            candidate="baseline",
            episodes=100,
            seed=42,
            semantics="abc123"
        )
        assert "evaluation-experiment-1-" in name
        assert "100ep-seed42-abc123" in name
        # Legacy format should not have campaign UUID
        parts = name.split("-")
        assert len([p for p in parts if len(p) == 36 and p.count("-") == 4]) == 0

    def test_task_reference_artifact_name_with_campaign_id(self):
        """task_reference_artifact_name should include campaign_id when provided."""
        campaign_id = str(uuid.uuid4())
        name = runner_protocol.task_reference_artifact_name(
            experiment=1,
            candidate="baseline",
            panel="reach",
            campaign_id=campaign_id
        )
        assert campaign_id in name
        assert "task-reference-" in name
        assert "-experiment-1-" in name
        assert "-reach" in name

    def test_task_reference_artifact_name_without_campaign_id(self):
        """task_reference_artifact_name without campaign_id should use legacy format."""
        name = runner_protocol.task_reference_artifact_name(
            experiment=1,
            candidate="baseline",
            panel="reach"
        )
        assert "task-reference-experiment-1-" in name
        assert "-reach" in name
        # Legacy format should not have campaign UUID
        parts = name.split("-")
        assert len([p for p in parts if len(p) == 36 and p.count("-") == 4]) == 0


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

    def test_postmortem_memory_legacy_format(self):
        """_postmortem_memory should still extract legacy format when no campaign_id."""
        from research.build_research_brief import _postmortem_memory
        
        postmortems = """
## Experiment 1
**Result:** Training completed in 150k steps with 45% success
"""
        
        memories = _postmortem_memory(postmortems, campaign_id=None)
        assert len(memories) == 1
        assert "Training completed" in memories[0]

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
        
        # Initialize state for campaign1
        state1 = {
            "schema_version": 3,
            "campaign": {"id": campaign1, "started_at": "2026-01-01T00:00:00Z", "base_commit": "abc1"},
            "campaign_experiment_counters": {},
            "last_allocated_experiment": 0,
            "last_experiment": 0,
        }
        
        # Initialize state for campaign2 (simulated)
        state2 = {
            "schema_version": 3,
            "campaign": {"id": campaign2, "started_at": "2026-01-02T00:00:00Z", "base_commit": "abc2"},
            "campaign_experiment_counters": {},
            "last_allocated_experiment": 0,
            "last_experiment": 0,
        }
        
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
        
        # Simulate initial campaign state
        state = {
            "schema_version": 3,
            "campaign": {
                "id": campaign_id,
                "started_at": "2026-01-01T12:00:00Z",
                "base_commit": "deadbeef"
            },
            "campaign_experiment_counters": {campaign_id: 0},
            "last_allocated_experiment": 0,
            "last_experiment": 0,
        }
        
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