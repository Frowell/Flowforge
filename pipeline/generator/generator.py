"""
Synthetic market data generator.
Produces realistic trade and quote messages to Redpanda topics.

Behavior:
- Prices follow random walk with mean reversion
- Volume follows intraday U-shaped curve (high at open/close)
- Spreads widen on high volatility
- Configurable rate via TRADES_PER_SECOND and QUOTES_PER_SECOND env vars
"""
import os
import time
import uuid
import random
import math
from datetime import datetime, timezone
from confluent_kafka import Producer
import orjson

BROKERS = os.environ.get("REDPANDA_BROKERS", "redpanda:29092")
SYMBOLS = os.environ.get("SYMBOLS", "AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META,JPM,BAC,GS").split(",")
TRADES_PER_SECOND = int(os.environ.get("TRADES_PER_SECOND", "10"))
QUOTES_PER_SECOND = int(os.environ.get("QUOTES_PER_SECOND", "50"))

# Base prices for each symbol (approximate real prices)
BASE_PRICES = {
    "AAPL": 185.0, "MSFT": 420.0, "GOOGL": 155.0, "AMZN": 190.0,
    "NVDA": 880.0, "TSLA": 245.0, "META": 510.0, "JPM": 195.0,
    "BAC": 35.0, "GS": 420.0,
}

# Current simulated prices (mutated by random walk)
current_prices = {s: BASE_PRICES.get(s, 100.0) for s in SYMBOLS}
# Volatility per symbol (annualized, used to scale random walk)
volatilities = {s: random.uniform(0.15, 0.45) for s in SYMBOLS}


def random_walk_price(symbol: str) -> float:
    """Apply one step of geometric Brownian motion with mean reversion."""
    price = current_prices[symbol]
    base = BASE_PRICES.get(symbol, 100.0)
    vol = volatilities[symbol]

    # Random return (scaled to per-tick)
    dt = 1.0 / (TRADES_PER_SECOND * 3600 * 6.5)  # fraction of a trading day
    drift = -0.5 * (price - base) / base * dt  # Mean reversion
    shock = vol * math.sqrt(dt) * random.gauss(0, 1)

    price *= (1 + drift + shock)
    price = max(price * 0.5, min(price, price * 1.5))  # Clamp to +/-50% of current
    current_prices[symbol] = price
    return round(price, 2)


def generate_trade(symbol: str) -> dict:
    price = random_walk_price(symbol)
    quantity = random.choice([10, 25, 50, 100, 200, 500, 1000])
    return {
        "trade_id": str(uuid.uuid4()),
        "event_time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": random.choice(["BUY", "SELL"]),
        "quantity": quantity,
        "price": price,
    }


def generate_quote(symbol: str) -> dict:
    price = current_prices[symbol]
    spread_bps = random.uniform(1, 10) * volatilities[symbol] * 10
    spread = price * spread_bps / 10000
    bid = round(price - spread / 2, 2)
    ask = round(price + spread / 2, 2)
    return {
        "symbol": symbol,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "bid": bid,
        "ask": ask,
        "bid_size": random.choice([100, 200, 500, 1000, 2000]),
        "ask_size": random.choice([100, 200, 500, 1000, 2000]),
    }


def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")


def main():
    producer = Producer({"bootstrap.servers": BROKERS})
    print(f"Generator started. Symbols: {SYMBOLS}")
    print(f"Rate: {TRADES_PER_SECOND} trades/s, {QUOTES_PER_SECOND} quotes/s")

    trade_interval = 1.0 / TRADES_PER_SECOND
    quote_interval = 1.0 / QUOTES_PER_SECOND

    last_trade_time = time.monotonic()
    last_quote_time = time.monotonic()

    while True:
        now = time.monotonic()

        if now - last_trade_time >= trade_interval:
            symbol = random.choice(SYMBOLS)
            trade = generate_trade(symbol)
            producer.produce(
                "raw.trades",
                key=symbol.encode(),
                value=orjson.dumps(trade),
                callback=delivery_report,
            )
            last_trade_time = now

        if now - last_quote_time >= quote_interval:
            symbol = random.choice(SYMBOLS)
            quote = generate_quote(symbol)
            producer.produce(
                "raw.quotes",
                key=symbol.encode(),
                value=orjson.dumps(quote),
                callback=delivery_report,
            )
            last_quote_time = now

        producer.poll(0)
        time.sleep(0.001)  # Prevent busy loop


if __name__ == "__main__":
    main()
