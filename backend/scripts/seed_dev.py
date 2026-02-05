#!/usr/bin/env python
"""Seed development database with required data.

Run this after migrations to set up a working dev environment:
    python scripts/seed_dev.py

Creates:
- Dev user (matches settings.dev_user_id / settings.dev_tenant_id)
- Sample trades + quotes in ClickHouse (if reachable)
"""

import asyncio
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.user import User

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC", "GS"]
BASE_PRICES = {
    "AAPL": 185.0,
    "MSFT": 420.0,
    "GOOGL": 155.0,
    "AMZN": 190.0,
    "NVDA": 880.0,
    "TSLA": 245.0,
    "META": 510.0,
    "JPM": 195.0,
    "BAC": 35.0,
    "GS": 420.0,
}


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


def seed_clickhouse_data() -> bool:
    """Seed ClickHouse with sample trades and quotes."""
    try:
        import clickhouse_connect  # type: ignore[import-untyped]
    except ImportError:
        print("clickhouse-connect not installed, skipping ClickHouse seed")
        return False

    try:
        client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
        )
        client.query("SELECT 1")
    except Exception as exc:
        print(f"ClickHouse not reachable ({exc}), skipping seed")
        return False

    # Check if already seeded
    result = client.query("SELECT count() FROM flowforge.raw_trades")
    if result.result_rows[0][0] > 0:
        count = result.result_rows[0][0]
        print(f"ClickHouse already has {count} trades, skipping seed")
        return False

    print("Seeding ClickHouse with sample data...")

    # Generate ~1000 trades over the last 7 days
    trades = []
    start_date = datetime.now(UTC) - timedelta(days=7)

    for symbol in SYMBOLS:
        price = BASE_PRICES[symbol]
        vol = random.uniform(0.15, 0.45)

        for i in range(100):
            day_offset = random.uniform(0, 7)
            trade_time = start_date + timedelta(days=day_offset)
            trade_time = trade_time.replace(
                hour=random.randint(9, 15),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )

            shock = vol * math.sqrt(1.0 / 252) * random.gauss(0, 1)
            price *= 1 + shock
            price = max(price * 0.8, min(price, price * 1.2))

            qty = random.choice([10, 25, 50, 100, 200, 500])
            trades.append(
                [
                    f"seed-{symbol}-{i}",
                    trade_time,
                    symbol,
                    random.choice(["BUY", "SELL"]),
                    qty,
                    round(price, 2),
                    round(qty * price, 2),
                ]
            )

    col_names = [
        "trade_id",
        "event_time",
        "symbol",
        "side",
        "quantity",
        "price",
        "notional",
    ]
    client.insert("flowforge.raw_trades", trades, column_names=col_names)
    print(f"  Inserted {len(trades)} trades")

    # Generate ~500 quotes
    quotes = []
    for symbol in SYMBOLS:
        price = BASE_PRICES[symbol]
        for _i in range(50):
            day_offset = random.uniform(0, 7)
            quote_time = start_date + timedelta(days=day_offset)
            quote_time = quote_time.replace(
                hour=random.randint(9, 15),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )

            spread = price * random.uniform(0.0001, 0.001)
            bid = round(price - spread / 2, 2)
            ask = round(price + spread / 2, 2)
            mid = round((bid + ask) / 2, 6)

            quotes.append(
                [
                    symbol,
                    quote_time,
                    bid,
                    ask,
                    random.choice([100, 200, 500, 1000]),
                    random.choice([100, 200, 500, 1000]),
                    mid,
                ]
            )

    quote_cols = [
        "symbol",
        "event_time",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "mid_price",
    ]
    client.insert("flowforge.raw_quotes", quotes, column_names=quote_cols)
    print(f"  Inserted {len(quotes)} quotes")

    return True


async def main():
    print("Seeding development database...")
    print(f"  Dev user ID: {settings.dev_user_id}")
    print(f"  Dev tenant ID: {settings.dev_tenant_id}")
    print()

    created = await seed_dev_user()

    if created:
        print("\nDev user seed complete!")
    else:
        print("\nDev user already exists.")

    print()
    ch_seeded = seed_clickhouse_data()

    if ch_seeded:
        print("\nClickHouse seed complete!")
    else:
        print("\nClickHouse seed skipped or already done.")


if __name__ == "__main__":
    asyncio.run(main())
