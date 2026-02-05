#!/usr/bin/env python
"""Seed development database with required data.

Run this after migrations to set up a working dev environment:
    python scripts/seed_dev.py

Creates:
- Dev user (matches settings.dev_user_id / settings.dev_tenant_id)
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.user import User


async def seed_dev_user() -> bool:
    """Create the dev user if it doesn't exist."""
    async with async_session() as db:
        user_id = UUID(settings.dev_user_id)
        tenant_id = UUID(settings.dev_tenant_id)

        result = await db.execute(select(User).where(User.id == user_id))
        if result.scalar_one_or_none():
            print(f"Dev user already exists: {user_id}")
            return False

        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="dev@flowforge.local",
            hashed_password="dev-mode-no-password",
            full_name="Dev User",
        )
        db.add(user)
        await db.commit()
        print(f"Created dev user: {user_id} (tenant: {tenant_id})")
        return True


async def main():
    print("Seeding development database...")
    print(f"  Dev user ID: {settings.dev_user_id}")
    print(f"  Dev tenant ID: {settings.dev_tenant_id}")
    print()

    created = await seed_dev_user()

    if created:
        print("\nDev seed complete!")
    else:
        print("\nNo changes needed.")


if __name__ == "__main__":
    asyncio.run(main())
