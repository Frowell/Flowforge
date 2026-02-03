"""Shared test fixtures.

All external stores (ClickHouse, Materialize, Redis) are mocked.
Tests never require running instances of these services.
"""

import pytest
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from unittest.mock import AsyncMock, MagicMock

from app.core.config import settings
from app.core.auth import get_current_tenant_id, get_current_user_id
from app.core.database import Base
from app.api.deps import get_db, get_websocket_manager
from app.main import app
from app.models.user import User

# Use the test database — replace only the database name (last path segment)
_async_base = settings.database_url
TEST_DATABASE_URL = _async_base.rsplit("/", 1)[0] + "/flowforge_test"

_sync_base = settings.database_url_sync
TEST_DATABASE_URL_SYNC = _sync_base.rsplit("/", 1)[0] + "/flowforge_test"

# Sync engine for DDL (create_all / drop_all) — avoids async event loop issues
_ddl_engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)


@pytest.fixture
def setup_database():
    """Create tables before tests, drop after. Uses sync engine for DDL."""
    Base.metadata.create_all(_ddl_engine)
    yield
    Base.metadata.drop_all(_ddl_engine)


@pytest.fixture
async def db_engine(setup_database):
    """Provide a fresh async engine per test (avoids event-loop conflicts)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Provide a test database session for direct use in tests."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_engine) -> AsyncClient:
    """Provide an httpx AsyncClient wired to the FastAPI test app.

    The route handlers get their own sessions from the same engine,
    so they can see committed data from db_session without sharing a connection.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Mock WebSocket manager so execution endpoint tests don't require app.state.ws_manager
    mock_ws = MagicMock()
    mock_ws.publish_execution_status = AsyncMock()
    app.dependency_overrides[get_websocket_manager] = lambda: mock_ws

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    # Only remove overrides — don't clear all (preserves mock_auth)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_websocket_manager, None)


@pytest.fixture
def tenant_id():
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def user_id():
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
async def seed_user_a(db_session: AsyncSession, tenant_id, user_id):
    """Create a test user for tenant A so FK constraints are satisfied."""
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="user_a@test.com",
        hashed_password="not-a-real-hash",
        full_name="Test User A",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def seed_user_b(db_session: AsyncSession, tenant_id_b, user_id_b):
    """Create a test user for tenant B so FK constraints are satisfied."""
    user = User(
        id=user_id_b,
        tenant_id=tenant_id_b,
        email="user_b@test.com",
        hashed_password="not-a-real-hash",
        full_name="Test User B",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def mock_auth(tenant_id, user_id):
    """Override auth dependencies for tests."""
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    yield
    app.dependency_overrides.pop(get_current_tenant_id, None)
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def tenant_id_b():
    """Second tenant for isolation tests."""
    return UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def user_id_b():
    """Second user for isolation tests."""
    return UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@pytest.fixture
def mock_auth_b(tenant_id_b, user_id_b):
    """Override auth dependencies for tenant B tests."""
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id_b
    app.dependency_overrides[get_current_user_id] = lambda: user_id_b
    yield
    app.dependency_overrides.pop(get_current_tenant_id, None)
    app.dependency_overrides.pop(get_current_user_id, None)
