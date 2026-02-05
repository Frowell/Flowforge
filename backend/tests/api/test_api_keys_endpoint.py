"""Tests for API key management endpoints."""

import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import APIKey


@pytest.mark.usefixtures("mock_auth", "seed_user_a")
class TestAPIKeyCreate:
    async def test_create_api_key_returns_raw_key(self, client: AsyncClient):
        response = await client.post("/api/v1/api-keys", json={"label": "Test Key"})
        assert response.status_code == 201
        data = response.json()
        assert data["key"].startswith("sk_live_")
        assert data["label"] == "Test Key"
        assert data["id"] is not None

    async def test_create_api_key_stores_hash_not_raw(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        response = await client.post("/api/v1/api-keys", json={"label": "Hash Test"})
        raw_key = response.json()["key"]
        key_id = response.json()["id"]

        from sqlalchemy import select

        from app.models.dashboard import APIKey

        result = await db_session.execute(select(APIKey).where(APIKey.id == key_id))
        api_key = result.scalar_one()

        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert api_key.key_hash == expected_hash

    async def test_create_api_key_with_scoped_widgets(self, client: AsyncClient):
        widget_ids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]
        response = await client.post(
            "/api/v1/api-keys",
            json={"label": "Scoped", "scoped_widget_ids": widget_ids, "rate_limit": 50},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rate_limit"] == 50
        assert len(data["scoped_widget_ids"]) == 2


@pytest.mark.usefixtures("mock_auth", "seed_user_a")
class TestAPIKeyList:
    async def test_list_api_keys_returns_own_tenant_only(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        tenant_id,
        user_id,
        tenant_id_b,
        user_id_b,
    ):
        # Create keys via API (tenant A)
        await client.post("/api/v1/api-keys", json={"label": "Key A"})

        # Create a key for tenant B directly in DB
        from app.models.user import User

        user_b = User(
            id=user_id_b,
            tenant_id=tenant_id_b,
            email="user_b@test.com",
            hashed_password="not-a-real-hash",
            full_name="Test User B",
        )
        db_session.add(user_b)
        await db_session.flush()

        key_b = APIKey(
            tenant_id=tenant_id_b,
            user_id=user_id_b,
            key_hash=hashlib.sha256(b"sk_live_fakekeyb").hexdigest(),
            label="Key B",
        )
        db_session.add(key_b)
        await db_session.commit()

        response = await client.get("/api/v1/api-keys")
        assert response.status_code == 200
        keys = response.json()
        assert all(k["label"] != "Key B" for k in keys)
        assert any(k["label"] == "Key A" for k in keys)


@pytest.mark.usefixtures("mock_auth", "seed_user_a")
class TestAPIKeyRevoke:
    async def test_revoke_api_key_sets_revoked_at(self, client: AsyncClient):
        create_resp = await client.post("/api/v1/api-keys", json={"label": "To Revoke"})
        key_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/v1/api-keys/{key_id}")
        assert delete_resp.status_code == 204

        # Revoked key should not appear in list
        list_resp = await client.get("/api/v1/api-keys")
        ids = [k["id"] for k in list_resp.json()]
        assert key_id not in ids

    async def test_revoke_nonexistent_key_returns_404(self, client: AsyncClient):
        fake_id = "99999999-9999-9999-9999-999999999999"
        response = await client.delete(f"/api/v1/api-keys/{fake_id}")
        assert response.status_code == 404


@pytest.mark.usefixtures("mock_auth", "seed_user_a")
class TestAPIKeyUpdate:
    async def test_update_api_key_scoped_widgets(self, client: AsyncClient):
        create_resp = await client.post("/api/v1/api-keys", json={"label": "Original"})
        key_id = create_resp.json()["id"]

        new_widgets = ["33333333-3333-3333-3333-333333333333"]
        patch_resp = await client.patch(
            f"/api/v1/api-keys/{key_id}",
            json={
                "label": "Updated",
                "scoped_widget_ids": new_widgets,
                "rate_limit": 200,
            },
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["label"] == "Updated"
        assert data["rate_limit"] == 200
        assert len(data["scoped_widget_ids"]) == 1
