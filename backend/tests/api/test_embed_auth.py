"""Tests for embed endpoint authentication and API key validation.

Run: pytest backend/tests/api/test_embed_auth.py -v --noconftest
"""

import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from app.core.auth import validate_api_key

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_api_key_record(
    tenant_id=None, user_id=None, scoped_widget_ids=None, rate_limit=None
):
    """Create a mock APIKey model instance."""
    record = MagicMock()
    record.tenant_id = tenant_id or uuid4()
    record.user_id = user_id or uuid4()
    record.scoped_widget_ids = scoped_widget_ids
    record.rate_limit = rate_limit
    return record


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_api_key_format_raises_401():
    """API key not starting with 'sk_live_' should raise 401."""
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key("bad_key_123", db)
    assert exc_info.value.status_code == 401
    assert "Invalid API key format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_valid_api_key_returns_scope_dict():
    """A valid, non-revoked API key should return the correct scope dict."""
    tenant_id = uuid4()
    user_id = uuid4()
    widget_ids = [uuid4(), uuid4()]

    record = _make_api_key_record(
        tenant_id=tenant_id,
        user_id=user_id,
        scoped_widget_ids=widget_ids,
        rate_limit=50,
    )

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=mock_result)

    scope = await validate_api_key("sk_live_test123", db)

    assert scope["tenant_id"] == tenant_id
    assert scope["user_id"] == user_id
    assert scope["scoped_widget_ids"] == widget_ids
    assert scope["rate_limit"] == 50
    assert scope["key_hash"] == hashlib.sha256(b"sk_live_test123").hexdigest()


@pytest.mark.asyncio
async def test_revoked_key_raises_401():
    """A revoked or nonexistent API key should raise 401."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await validate_api_key("sk_live_revoked_key", db)
    assert exc_info.value.status_code == 401
    assert "Invalid or revoked" in exc_info.value.detail


@pytest.mark.asyncio
async def test_widget_scope_check_logic():
    """Widget scope check: None means all widgets, list means only those."""
    # None scoped_widget_ids = unrestricted
    record = _make_api_key_record(scoped_widget_ids=None)
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=mock_result)

    scope = await validate_api_key("sk_live_unscoped", db)
    assert scope["scoped_widget_ids"] is None

    # With scoped widget IDs
    widget_id = uuid4()
    record2 = _make_api_key_record(scoped_widget_ids=[widget_id])
    mock_result2 = MagicMock()
    mock_result2.scalar_one_or_none.return_value = record2
    db.execute = AsyncMock(return_value=mock_result2)

    scope2 = await validate_api_key("sk_live_scoped", db)
    assert widget_id in scope2["scoped_widget_ids"]
