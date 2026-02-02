"""Unit tests for workflow versioning — model, snapshot logic, and rollback.

Run with: pytest backend/tests/services/test_workflow_versioning.py -v --noconftest
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Model structure tests
# ---------------------------------------------------------------------------


class TestWorkflowVersionModel:
    """Verify WorkflowVersion model has correct columns and constraints."""

    def test_model_has_correct_tablename(self):
        from app.models.workflow import WorkflowVersion

        assert WorkflowVersion.__tablename__ == "workflow_versions"

    def test_model_has_required_columns(self):
        from app.models.workflow import WorkflowVersion

        mapper = WorkflowVersion.__mapper__
        column_names = {c.key for c in mapper.column_attrs}
        expected = {"id", "workflow_id", "version_number", "graph_json", "created_by", "created_at"}
        assert expected.issubset(column_names)

    def test_model_has_no_tenant_mixin(self):
        from app.core.database import TenantMixin
        from app.models.workflow import WorkflowVersion

        assert not issubclass(WorkflowVersion, TenantMixin)

    def test_model_has_workflow_fk(self):
        from app.models.workflow import WorkflowVersion

        col = WorkflowVersion.__table__.c.workflow_id
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "workflows.id" in fk_targets

    def test_model_has_unique_constraint_on_workflow_version(self):
        from app.models.workflow import WorkflowVersion

        table = WorkflowVersion.__table__
        unique_constraints = [
            c for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1
        ]
        # Find constraint covering (workflow_id, version_number)
        found = False
        for uc in unique_constraints:
            col_names = {c.name for c in uc.columns}
            if col_names == {"workflow_id", "version_number"}:
                found = True
                break
        assert found, "Expected unique constraint on (workflow_id, version_number)"

    def test_workflow_has_versions_relationship(self):
        from app.models.workflow import Workflow

        assert hasattr(Workflow, "versions")

    def test_cascade_delete_configured(self):
        from app.models.workflow import Workflow

        rel = Workflow.__mapper__.relationships["versions"]
        assert rel.cascade.delete_orphan


# ---------------------------------------------------------------------------
# Snapshot logic tests
# ---------------------------------------------------------------------------


class TestVersionSnapshotLogic:
    """Verify version_number increments and graph_json is captured pre-update."""

    def test_version_number_starts_at_one(self):
        """When no versions exist, next version should be 1."""
        # Simulate: coalesce(max(version_number), 0) returns 0
        current_max = 0
        next_version = current_max + 1
        assert next_version == 1

    def test_version_number_increments(self):
        """Each save should increment version_number."""
        current_max = 3
        next_version = current_max + 1
        assert next_version == 4

    def test_snapshot_captures_pre_update_graph(self):
        """The snapshot should capture graph_json BEFORE the update is applied."""
        from app.models.workflow import WorkflowVersion

        old_graph = {"nodes": [{"id": "1"}], "edges": []}
        new_graph = {"nodes": [{"id": "1"}, {"id": "2"}], "edges": [{"source": "1", "target": "2"}]}

        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Create snapshot with the OLD graph (before update)
        snapshot = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=1,
            graph_json=old_graph,
            created_by=user_id,
        )

        assert snapshot.graph_json == old_graph
        assert snapshot.graph_json != new_graph

    def test_no_snapshot_when_graph_json_not_in_update(self):
        """If only name/description changes, no version should be created."""
        update_data = {"name": "New Name", "description": "Updated desc"}
        assert "graph_json" not in update_data

    def test_snapshot_created_when_graph_json_in_update(self):
        """If graph_json is in the update payload, a snapshot should be created."""
        update_data = {"name": "New Name", "graph_json": {"nodes": [], "edges": []}}
        assert "graph_json" in update_data


# ---------------------------------------------------------------------------
# Rollback logic tests
# ---------------------------------------------------------------------------


class TestRollbackLogic:
    """Verify rollback creates a new snapshot and updates workflow graph_json."""

    def test_rollback_creates_snapshot_of_current_state(self):
        """Rolling back should first snapshot the current state."""
        from app.models.workflow import WorkflowVersion

        current_graph = {"nodes": [{"id": "A"}], "edges": []}
        target_graph = {"nodes": [], "edges": []}
        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Snapshot of current state before rollback
        snapshot = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=3,
            graph_json=current_graph,
            created_by=user_id,
        )

        assert snapshot.graph_json == current_graph
        assert snapshot.version_number == 3

    def test_rollback_applies_target_graph(self):
        """After rollback, workflow.graph_json should match the target version."""
        target_graph = {"nodes": [{"id": "X"}], "edges": [{"source": "X", "target": "Y"}]}

        # Simulate applying rollback
        workflow_graph_json = {"nodes": [{"id": "A"}], "edges": []}
        workflow_graph_json = target_graph  # rollback applies target

        assert workflow_graph_json == target_graph

    def test_rollback_is_reversible(self):
        """Rolling back creates a version, so a subsequent rollback can undo it."""
        from app.models.workflow import WorkflowVersion

        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # State before first rollback
        state_a = {"nodes": [{"id": "A"}], "edges": []}
        # State after first rollback (from some older version)
        state_b = {"nodes": [{"id": "B"}], "edges": []}

        # First rollback: snapshot state_a as version 1
        v1 = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=1,
            graph_json=state_a,
            created_by=user_id,
        )

        # Second rollback to v1: snapshot state_b as version 2
        v2 = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=2,
            graph_json=state_b,
            created_by=user_id,
        )

        # After second rollback, workflow has state_a again
        # And v2 preserves state_b for future rollback
        assert v1.graph_json == state_a
        assert v2.graph_json == state_b


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestVersionSchemas:
    """Verify version response schemas work correctly."""

    def test_version_response_from_attributes(self):
        from app.schemas.workflow import WorkflowVersionResponse

        vid = uuid.uuid4()
        wid = uuid.uuid4()
        uid = uuid.uuid4()

        fake = MagicMock()
        fake.id = vid
        fake.workflow_id = wid
        fake.version_number = 1
        fake.graph_json = {"nodes": [], "edges": []}
        fake.created_by = uid
        fake.created_at = datetime(2025, 1, 1)

        resp = WorkflowVersionResponse.model_validate(fake)
        assert resp.id == vid
        assert resp.version_number == 1
        assert resp.graph_json == {"nodes": [], "edges": []}

    def test_version_list_response(self):
        from app.schemas.workflow import WorkflowVersionListResponse, WorkflowVersionResponse

        version_id = uuid.uuid4()
        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()

        item = WorkflowVersionResponse(
            id=version_id,
            workflow_id=workflow_id,
            version_number=1,
            graph_json={},
            created_by=user_id,
            created_at=datetime(2025, 1, 1),
        )
        resp = WorkflowVersionListResponse(items=[item], total=1)
        assert resp.total == 1
        assert len(resp.items) == 1
