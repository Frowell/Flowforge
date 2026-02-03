"""Audit service unit tests."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog, AuditResourceType
from app.services.audit_service import AuditService


TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def test_log_creates_record(db_session: AsyncSession, setup_database):
    """AuditService.log() persists an audit record."""
    service = AuditService(db_session)
    resource_id = uuid4()

    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=resource_id,
        metadata={"name": "Test Workflow"},
    )
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    entry = result.scalar_one()
    assert entry.tenant_id == TENANT_A
    assert entry.user_id == USER_A
    assert entry.action == AuditAction.CREATED
    assert entry.resource_type == AuditResourceType.WORKFLOW
    assert entry.metadata_ == {"name": "Test Workflow"}


async def test_list_events_filters_by_tenant(db_session: AsyncSession, setup_database):
    """list_events returns only records for the specified tenant."""
    service = AuditService(db_session)
    resource_a = uuid4()
    resource_b = uuid4()

    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=resource_a,
    )
    await service.log(
        tenant_id=TENANT_B,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.DASHBOARD,
        resource_id=resource_b,
    )
    await db_session.commit()

    result = await service.list_events(tenant_id=TENANT_A)
    assert result["total"] == 1
    assert result["items"][0].resource_id == resource_a


async def test_list_events_filters_by_resource_type(
    db_session: AsyncSession, setup_database
):
    """list_events can filter by resource_type."""
    service = AuditService(db_session)

    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=uuid4(),
    )
    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.DASHBOARD,
        resource_id=uuid4(),
    )
    await db_session.commit()

    result = await service.list_events(
        tenant_id=TENANT_A,
        resource_type=AuditResourceType.DASHBOARD,
    )
    assert result["total"] == 1
    assert result["items"][0].resource_type == AuditResourceType.DASHBOARD


async def test_list_events_filters_by_action(db_session: AsyncSession, setup_database):
    """list_events can filter by action."""
    service = AuditService(db_session)

    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=uuid4(),
    )
    await service.log(
        tenant_id=TENANT_A,
        user_id=USER_A,
        action=AuditAction.DELETED,
        resource_type=AuditResourceType.WORKFLOW,
        resource_id=uuid4(),
    )
    await db_session.commit()

    result = await service.list_events(
        tenant_id=TENANT_A,
        action=AuditAction.DELETED,
    )
    assert result["total"] == 1
    assert result["items"][0].action == AuditAction.DELETED
