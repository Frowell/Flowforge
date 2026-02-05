"""
Seeds 6 months of historical trade data into ClickHouse.
Run once after infrastructure is up: kubectl exec deploy/backend -- python /workspace/scripts/seed_historical.py
"""
import random
import math
from datetime import datetime, timedelta, timezone
import clickhouse_connect

CH_HOST = "clickhouse.flowforge.svc.cluster.local"
CH_PORT = 8123

SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "BAC", "GS"]
BASE_PRICES = {
    "AAPL": 185.0, "MSFT": 420.0, "GOOGL": 155.0, "AMZN": 190.0,
    "NVDA": 880.0, "TSLA": 245.0, "META": 510.0, "JPM": 195.0,
    "BAC": 35.0, "GS": 420.0,
}

DAYS_BACK = 180
TRADES_PER_DAY_PER_SYMBOL = 500  # ~500k total trades
BATCH_SIZE = 10_000


def generate_historical_trades():
    """Generate 6 months of historical trades."""
    client = clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT)

    start_date = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    batch = []
    total = 0

    for day_offset in range(DAYS_BACK):
        day = start_date + timedelta(days=day_offset)
        if day.weekday() >= 5:  # Skip weekends
            continue

        for symbol in SYMBOLS:
            price = BASE_PRICES[symbol]
            vol = random.uniform(0.15, 0.45)

            for i in range(TRADES_PER_DAY_PER_SYMBOL):
                # Random time during trading hours (9:30 - 16:00 ET)
                hour = random.uniform(9.5, 16.0)
                trade_time = day.replace(
                    hour=int(hour),
                    minute=int((hour % 1) * 60),
                    second=random.randint(0, 59),
                    microsecond=random.randint(0, 999999),
                )

                # Price walk
                dt = 1.0 / TRADES_PER_DAY_PER_SYMBOL
                shock = vol * math.sqrt(dt / 252) * random.gauss(0, 1)
                price *= (1 + shock)
                price = max(price * 0.8, min(price, price * 1.2))

                qty = random.choice([10, 25, 50, 100, 200, 500])
                batch.append([
                    f"hist-{day_offset}-{symbol}-{i}",
                    trade_time,
                    symbol,
                    random.choice(["BUY", "SELL"]),
                    qty,
                    round(price, 2),
                    round(qty * price, 2),
                ])

                if len(batch) >= BATCH_SIZE:
                    client.insert(
                        "flowforge.raw_trades",
                        batch,
                        column_names=["trade_id", "event_time", "symbol", "side", "quantity", "price", "notional"],
                    )
                    total += len(batch)
                    print(f"Inserted {total} trades...")
                    batch = []

    if batch:
        client.insert(
            "flowforge.raw_trades",
            batch,
            column_names=["trade_id", "event_time", "symbol", "side", "quantity", "price", "notional"],
        )
        total += len(batch)

    print(f"Done. Total trades seeded: {total}")


if __name__ == "__main__":
    generate_historical_trades()
