"""Schema catalog endpoints.

Exposes the schema registry to the frontend: available tables, columns, types
from the serving layer (ClickHouse, Materialize, Redis).
"""

from fastapi import APIRouter

from app.schemas.schema import CatalogResponse

router = APIRouter()


@router.get("", response_model=CatalogResponse)
async def get_catalog():
    """Return the full schema catalog from the serving layer.

    The frontend uses this to populate Data Source node table pickers
    and to seed the client-side schema propagation engine.
    """
    # TODO: Inject schema_registry service via Depends
    # TODO: Return cached catalog (refreshed periodically from ClickHouse/Materialize)
    return CatalogResponse(tables=[])


@router.post("/refresh")
async def refresh_catalog():
    """Force a refresh of the schema catalog from backing stores."""
    # TODO: Invalidate Redis cache and re-query system.columns / mz_catalog
    return {"status": "refreshed"}
