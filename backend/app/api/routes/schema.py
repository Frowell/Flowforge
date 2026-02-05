"""Schema catalog endpoints.

Exposes the schema registry to the frontend: available tables, columns, types
from the serving layer (ClickHouse, Materialize, Redis).

All endpoints require authentication (tenant_id from JWT).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_tenant_id, get_schema_registry
from app.schemas.schema import CatalogResponse
from app.services.schema_registry import SchemaRegistry

router = APIRouter()


@router.get("", response_model=CatalogResponse)
async def get_catalog(
    tenant_id: UUID = Depends(get_current_tenant_id),
    registry: SchemaRegistry = Depends(get_schema_registry),
):
    """Return the full schema catalog from the serving layer.

    The frontend uses this to populate Data Source node table pickers
    and to seed the client-side schema propagation engine.
    """
    return await registry.get_catalog()


@router.post("/refresh", response_model=CatalogResponse)
async def refresh_catalog(
    tenant_id: UUID = Depends(get_current_tenant_id),
    registry: SchemaRegistry = Depends(get_schema_registry),
):
    """Force a refresh of the schema catalog from backing stores."""
    return await registry.refresh()
