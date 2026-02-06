"""
5-minute VWAP window calculation.
Reads from raw.trades topic, computes VWAP per symbol per 5-min window,
writes results to ClickHouse metrics.vwap_5min and Redis latest state.
"""
import os
import json
from datetime import timedelta, datetime, timezone

import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaSource
from bytewax.operators.windowing import TumblingWindower, EventClock, fold_window
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


def parse_trade(msg):
    """Parse raw JSON trade message. Key by symbol."""
    data = json.loads(msg.value)
    return (data["symbol"], {
        "event_time": datetime.fromisoformat(data["event_time"]),
        "price": float(data["price"]),
        "quantity": float(data["quantity"]),
        "notional": float(data["price"]) * float(data["quantity"]),
    })


def extract_event_time(trade):
    """Extract event time for windowing."""
    return trade["event_time"]


class VWAPAccumulator:
    """Accumulates trades within a window to compute VWAP."""
    def __init__(self):
        self.total_notional = 0.0
        self.total_volume = 0.0
        self.trade_count = 0
        self.high = float("-inf")
        self.low = float("inf")

    def add(self, trade):
        self.total_notional += trade["notional"]
        self.total_volume += trade["quantity"]
        self.trade_count += 1
        self.high = max(self.high, trade["price"])
        self.low = min(self.low, trade["price"])
        return self

    @property
    def vwap(self):
        if self.total_volume == 0:
            return 0.0
        return self.total_notional / self.total_volume

    @property
    def spread_bps(self):
        if self.low == 0:
            return 0.0
        return ((self.high - self.low) / self.low) * 10000


def build_acc():
    return VWAPAccumulator()


def fold_trade(acc, trade):
    return acc.add(trade)


def merge_accs(acc1, acc2):
    acc1.total_notional += acc2.total_notional
    acc1.total_volume += acc2.total_volume
    acc1.trade_count += acc2.trade_count
    acc1.high = max(acc1.high, acc2.high)
    acc1.low = min(acc1.low, acc2.low)
    return acc1


def emit_vwap(symbol_window):
    """Write VWAP result to ClickHouse and Redis."""
    symbol, (_window_id, acc) = symbol_window
    window_end = datetime.now(timezone.utc)

    # Write to ClickHouse
    ch_client.insert(
        "metrics.vwap_5min",
        [[symbol, window_end, acc.vwap, acc.total_volume, acc.trade_count, acc.spread_bps]],
        column_names=["symbol", "window_end", "vwap", "volume", "trade_count", "spread_bps"],
    )

    # Write latest to Redis
    r_client.hset(f"latest:vwap:{symbol}", mapping={
        "vwap": str(acc.vwap),
        "volume": str(acc.total_volume),
        "trade_count": str(acc.trade_count),
        "spread_bps": str(acc.spread_bps),
        "window_end": window_end.isoformat(),
    })

    return (symbol, acc.vwap)


# Build the dataflow
flow = Dataflow("vwap_5min")

source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades"],
    starting_offset=OFFSET_END,
)

stream = op.input("trades_in", flow, source)
keyed = op.map("parse", stream, parse_trade)

clock = EventClock(extract_event_time, wait_for_system_duration=timedelta(seconds=10))
windower = TumblingWindower(length=timedelta(minutes=5), align_to=datetime(2024, 1, 1, tzinfo=timezone.utc))

windowed = fold_window("vwap_window", keyed, clock, windower, build_acc, fold_trade, merge_accs)
emitted = op.map("emit", windowed.down, emit_vwap)
op.output("sink", emitted, StdOutSink())
