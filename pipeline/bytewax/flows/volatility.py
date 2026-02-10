"""
Rolling volatility calculation.
Reads from raw.trades topic, computes 1h and 24h rolling volatility per symbol,
writes results to ClickHouse metrics.rolling_volatility and Redis latest state.

Volatility is computed as:
- Standard deviation of log returns over the window
- Annualized by multiplying by sqrt(252 * 6.5 * 3600 / window_seconds)
"""

import os
import json
import math
from datetime import timedelta, datetime, timezone
from collections import deque
from typing import Optional, Tuple

import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaSource
from bytewax.connectors.stdio import StdOutSink
from confluent_kafka import OFFSET_END

import clickhouse_connect
import redis

REDPANDA_BROKERS = os.environ.get("REDPANDA_BROKERS", "redpanda:29092").split(",")
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Clients
ch_client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Trading seconds per year (for annualization)
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 252 days * 6.5 hours * 3600 seconds


def parse_trade(msg):
    """Parse raw JSON trade message. Key by symbol."""
    data = json.loads(msg.value)
    return (
        data["symbol"],
        {
            "event_time": datetime.fromisoformat(data["event_time"]),
            "price": float(data["price"]),
        },
    )


class VolatilityAccumulator:
    """
    Accumulates price data to compute rolling volatility.
    Uses Welford's online algorithm for numerical stability.
    """

    def __init__(self, window_seconds: int):
        self.window_seconds = window_seconds
        self.prices = deque()  # (timestamp, price) pairs
        self.last_price = None
        self.log_returns = []

    def add(self, trade):
        price = trade["price"]
        ts = trade["event_time"]

        # Compute log return if we have a previous price
        if self.last_price is not None and self.last_price > 0:
            log_return = math.log(price / self.last_price)
            self.log_returns.append(log_return)

        self.last_price = price
        self.prices.append((ts, price))

        # Trim old data outside window
        cutoff = ts - timedelta(seconds=self.window_seconds)
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()
            if self.log_returns:
                self.log_returns.pop(0)

        return self

    @property
    def volatility(self):
        """Compute annualized volatility from log returns."""
        if len(self.log_returns) < 2:
            return 0.0

        # Standard deviation of log returns
        n = len(self.log_returns)
        mean = sum(self.log_returns) / n
        variance = sum((r - mean) ** 2 for r in self.log_returns) / (n - 1)
        std_dev = math.sqrt(variance)

        # Annualize based on window size
        # Assumes returns are per-trade, scale to annual
        avg_interval = self.window_seconds / max(n, 1)
        periods_per_year = TRADING_SECONDS_PER_YEAR / avg_interval
        annualized = std_dev * math.sqrt(periods_per_year)

        return annualized

    @property
    def return_pct(self):
        """Compute return over the window."""
        if len(self.prices) < 2:
            return 0.0
        first_price = self.prices[0][1]
        last_price = self.prices[-1][1]
        if first_price == 0:
            return 0.0
        return (last_price - first_price) / first_price * 100


class DualVolatilityState:
    """Tracks both 1h and 24h volatility."""

    def __init__(self):
        self.vol_1h = VolatilityAccumulator(3600)  # 1 hour
        self.vol_24h = VolatilityAccumulator(86400)  # 24 hours
        self.last_emit = None

    def add(self, trade):
        self.vol_1h.add(trade)
        self.vol_24h.add(trade)
        return self


def accumulate_mapper(
    state: Optional[DualVolatilityState], trade: dict
) -> Tuple[Optional[DualVolatilityState], DualVolatilityState]:
    """stateful_map callback: (state, value) -> (new_state, emit_value)."""
    if state is None:
        state = DualVolatilityState()
    state.add(trade)
    return (state, state)


def should_emit(symbol_state):
    """Emit every 5 minutes to avoid flooding."""
    _symbol, state = symbol_state
    now = datetime.now(timezone.utc)

    if state.last_emit is None or (now - state.last_emit) >= timedelta(minutes=5):
        state.last_emit = now
        return True
    return False


VOLATILITY_COLUMNS = [
    {"name": "symbol", "dtype": "String"},
    {"name": "window_end", "dtype": "DateTime64"},
    {"name": "volatility_1h", "dtype": "Float64"},
    {"name": "volatility_24h", "dtype": "Float64"},
    {"name": "return_pct", "dtype": "Float64"},
]


def emit_volatility(symbol_state):
    """Write volatility result to ClickHouse, Redis, and broadcast via pub/sub."""
    symbol, state = symbol_state

    vol_1h = state.vol_1h.volatility
    vol_24h = state.vol_24h.volatility
    return_pct = state.vol_1h.return_pct
    window_end = datetime.now(timezone.utc)

    row = {
        "symbol": symbol,
        "window_end": window_end.isoformat(),
        "volatility_1h": round(vol_1h, 6),
        "volatility_24h": round(vol_24h, 6),
        "return_pct": round(return_pct, 4),
    }

    # Write to ClickHouse
    ch_client.insert(
        "metrics.rolling_volatility",
        [[symbol, window_end, vol_1h, vol_24h, return_pct]],
        column_names=[
            "symbol",
            "window_end",
            "volatility_1h",
            "volatility_24h",
            "return_pct",
        ],
    )

    # Write latest to Redis
    r_client.hset(
        f"latest:volatility:{symbol}",
        mapping={
            "volatility_1h": f"{vol_1h:.6f}",
            "volatility_24h": f"{vol_24h:.6f}",
            "return_pct": f"{return_pct:.4f}",
            "window_end": window_end.isoformat(),
        },
    )

    # Broadcast row data to dashboards
    r_client.publish(
        "flowforge:broadcast:table_rows",
        json.dumps({
            "type": "table_rows",
            "table": "rolling_volatility",
            "columns": VOLATILITY_COLUMNS,
            "rows": [row],
        }),
    )

    return (symbol, {"vol_1h": vol_1h, "vol_24h": vol_24h})


# Build the dataflow
flow = Dataflow("rolling_volatility")

source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades"],
    starting_offset=OFFSET_END,
)

stream = op.input("trades_in", flow, source)
keyed = op.map("parse", stream, parse_trade)

# Stateful accumulation per symbol
accumulated = op.stateful_map("accumulate", keyed, accumulate_mapper)

# Filter to emit periodically
filtered = op.filter("should_emit", accumulated, should_emit)

# Emit to sinks
emitted = op.map("emit", filtered, emit_volatility)
op.output("sink", emitted, StdOutSink())
