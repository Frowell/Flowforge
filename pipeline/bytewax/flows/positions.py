"""
Position tracker — computes net position per symbol from raw trades.

Reads from raw.trades topic, accumulates buy/sell quantities per symbol,
writes results to Redis latest:position:* hashes and broadcasts to dashboards.
"""

import os
import json
from datetime import timedelta, datetime, timezone
from typing import Optional, Tuple

import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaSource
from bytewax.connectors.stdio import StdOutSink
from confluent_kafka import OFFSET_END

import redis

REDPANDA_BROKERS = os.environ.get("REDPANDA_BROKERS", "redpanda:29092").split(",")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def parse_trade(msg):
    """Parse raw JSON trade message. Key by symbol."""
    data = json.loads(msg.value)
    return (
        data["symbol"],
        {
            "price": float(data["price"]),
            "quantity": float(data["quantity"]),
            "side": data["side"],
            "notional": float(data["price"]) * float(data["quantity"]),
        },
    )


class PositionAccumulator:
    """Tracks net position, average price, and market value per symbol."""

    def __init__(self):
        self.buy_qty = 0.0
        self.sell_qty = 0.0
        self.buy_notional = 0.0
        self.last_price = 0.0
        self.last_emit = None

    def add(self, trade):
        self.last_price = trade["price"]
        if trade["side"].lower() == "buy":
            self.buy_qty += trade["quantity"]
            self.buy_notional += trade["notional"]
        else:
            self.sell_qty += trade["quantity"]
        return self

    @property
    def quantity(self):
        return self.buy_qty - self.sell_qty

    @property
    def avg_price(self):
        if self.buy_qty == 0:
            return 0.0
        return self.buy_notional / self.buy_qty

    @property
    def market_value(self):
        return self.quantity * self.last_price


def accumulate_position(
    state: Optional[PositionAccumulator], trade: dict
) -> Tuple[Optional[PositionAccumulator], PositionAccumulator]:
    """stateful_map callback."""
    if state is None:
        state = PositionAccumulator()
    state.add(trade)
    return (state, state)


def should_emit(symbol_state):
    """Emit every 5 seconds for responsive updates."""
    _symbol, state = symbol_state
    now = datetime.now(timezone.utc)
    if state.last_emit is None or (now - state.last_emit) >= timedelta(seconds=5):
        state.last_emit = now
        return True
    return False


POSITION_COLUMNS = [
    {"name": "symbol", "dtype": "String"},
    {"name": "quantity", "dtype": "Float64"},
    {"name": "avg_price", "dtype": "Float64"},
    {"name": "market_value", "dtype": "Float64"},
    {"name": "timestamp", "dtype": "DateTime64"},
]


def emit_position(symbol_state):
    """Write position to Redis and broadcast via pub/sub."""
    symbol, state = symbol_state
    now = datetime.now(timezone.utc)

    row = {
        "symbol": symbol,
        "quantity": round(state.quantity, 4),
        "avg_price": round(state.avg_price, 6),
        "market_value": round(state.market_value, 2),
        "timestamp": now.isoformat(),
    }

    r_client.hset(
        f"latest:position:{symbol}",
        mapping={
            "quantity": str(row["quantity"]),
            "avg_price": str(row["avg_price"]),
            "market_value": str(row["market_value"]),
            "timestamp": now.isoformat(),
        },
    )

    r_client.publish(
        "flowforge:broadcast:table_rows",
        json.dumps({
            "type": "table_rows",
            "table": "positions",
            "columns": POSITION_COLUMNS,
            "rows": [row],
        }),
    )

    return (symbol, {"qty": state.quantity, "value": state.market_value})


# Build the dataflow
flow = Dataflow("positions")

source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades"],
    starting_offset=OFFSET_END,
)

stream = op.input("trades_in", flow, source)
keyed = op.map("parse", stream, parse_trade)
accumulated = op.stateful_map("accumulate", keyed, accumulate_position)
filtered = op.filter("should_emit", accumulated, should_emit)
emitted = op.map("emit", filtered, emit_position)
op.output("sink", emitted, StdOutSink())
