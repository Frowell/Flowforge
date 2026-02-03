"""API key management endpoints.

CRUD for embed API keys. Keys are tenant-scoped and created by authenticated users.
The raw key is returned only once on creation; only the SHA-256 hash is stored.
"""

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_id, get_current_user_id, get_db, require_role
from app.models.audit_log import AuditAction, AuditResourceType
from app.models.dashboard import APIKey
from app.services.audit_service import AuditService
from app.schemas.dashboard import APIKeyCreate, APIKeyCreateResponse, APIKeyResponse

router = APIRouter()


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Create a new API key for embed mode.

    The raw key (sk_live_...) is returned only in this response.
    Store it securely — it cannot be retrieved again.
    """
    raw_key = f"sk_live_{uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = APIKey(
        tenant_id=tenant_id,
        user_id=user_id,
        key_hash=key_hash,
        label=body.label,
        scoped_widget_ids=body.scoped_widget_ids,
        rate_limit=body.rate_limit,
    )
    db.add(api_key)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.CREATED,
        resource_type=AuditResourceType.API_KEY,
        resource_id=api_key.id,
        metadata={"label": body.label},
    )

    await db.commit()
    await db.refresh(api_key)

    return APIKeyCreateResponse(
        id=api_key.id,
        key=raw_key,
        label=api_key.label,
        scoped_widget_ids=api_key.scoped_widget_ids,
        rate_limit=api_key.rate_limit,
        created_at=api_key.created_at,
        revoked_at=api_key.revoked_at,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """List all non-revoked API keys for the current tenant."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.tenant_id == tenant_id,
            APIKey.revoked_at.is_(None),
        )
    )
    keys = result.scalars().all()
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Revoke an API key (soft delete)."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoked_at = datetime.now(timezone.utc)

    audit = AuditService(db)
    await audit.log(
        tenant_id=tenant_id,
        user_id=user_id,
        action=AuditAction.REVOKED,
        resource_type=AuditResourceType.API_KEY,
        resource_id=api_key.id,
    )

    await db.commit()


@router.patch("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: UUID,
    body: APIKeyCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """Update an API key's label, scoped widgets, or rate limit."""
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if body.label is not None:
        api_key.label = body.label
    if body.scoped_widget_ids is not None:
        api_key.scoped_widget_ids = body.scoped_widget_ids
    if body.rate_limit is not None:
        api_key.rate_limit = body.rate_limit

    await db.commit()
    await db.refresh(api_key)
    return APIKeyResponse.model_validate(api_key)
