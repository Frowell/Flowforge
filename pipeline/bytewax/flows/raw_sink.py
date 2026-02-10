"""
Raw data sink — consumes raw.trades and raw.quotes from Redpanda
and inserts them into ClickHouse flowforge.raw_trades / flowforge.raw_quotes.

The Bytewax VWAP and Volatility flows only write aggregated data.
This flow writes the raw events so they're queryable in the canvas.
"""
import os
import json
import time
from datetime import datetime

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

BATCH_SIZE = 50
FLUSH_INTERVAL = 0.2  # 200ms time-based flush

TRADE_COLUMNS = [
    {"name": "trade_id", "dtype": "String"},
    {"name": "event_time", "dtype": "DateTime64"},
    {"name": "symbol", "dtype": "String"},
    {"name": "side", "dtype": "String"},
    {"name": "quantity", "dtype": "Float64"},
    {"name": "price", "dtype": "Float64"},
    {"name": "notional", "dtype": "Float64"},
]

QUOTE_COLUMNS = [
    {"name": "symbol", "dtype": "String"},
    {"name": "event_time", "dtype": "DateTime64"},
    {"name": "bid", "dtype": "Float64"},
    {"name": "ask", "dtype": "Float64"},
    {"name": "bid_size", "dtype": "Float64"},
    {"name": "ask_size", "dtype": "Float64"},
    {"name": "mid_price", "dtype": "Float64"},
]

TRADE_COLUMN_NAMES = [c["name"] for c in TRADE_COLUMNS]
QUOTE_COLUMN_NAMES = [c["name"] for c in QUOTE_COLUMNS]

ch_client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Buffers for batched inserts
trade_buffer: list[list] = []
quote_buffer: list[list] = []
last_trade_flush: float = time.monotonic()
last_quote_flush: float = time.monotonic()


def _flush_trades():
    """Flush trade buffer to ClickHouse and publish row data via Redis."""
    global last_trade_flush
    if not trade_buffer:
        return
    rows = [dict(zip(TRADE_COLUMN_NAMES, row)) for row in trade_buffer]
    # Serialize datetime objects to ISO strings for JSON
    for row in rows:
        if isinstance(row.get("event_time"), datetime):
            row["event_time"] = row["event_time"].isoformat()
    ch_client.insert(
        "flowforge.raw_trades",
        trade_buffer,
        column_names=TRADE_COLUMN_NAMES,
    )
    trade_buffer.clear()
    last_trade_flush = time.monotonic()
    r_client.publish(
        "flowforge:broadcast:table_rows",
        json.dumps({
            "type": "table_rows",
            "table": "raw_trades",
            "columns": TRADE_COLUMNS,
            "rows": rows,
        }),
    )


def _flush_quotes():
    """Flush quote buffer to ClickHouse and publish row data via Redis."""
    global last_quote_flush
    if not quote_buffer:
        return
    rows = [dict(zip(QUOTE_COLUMN_NAMES, row)) for row in quote_buffer]
    for row in rows:
        if isinstance(row.get("event_time"), datetime):
            row["event_time"] = row["event_time"].isoformat()
    ch_client.insert(
        "flowforge.raw_quotes",
        quote_buffer,
        column_names=QUOTE_COLUMN_NAMES,
    )
    quote_buffer.clear()
    last_quote_flush = time.monotonic()
    r_client.publish(
        "flowforge:broadcast:table_rows",
        json.dumps({
            "type": "table_rows",
            "table": "raw_quotes",
            "columns": QUOTE_COLUMNS,
            "rows": rows,
        }),
    )


def route_message(msg):
    """Parse message and tag with topic."""
    data = json.loads(msg.value)
    topic = msg.topic
    return (topic, data)


def sink_record(topic_data):
    """Buffer and batch-insert records into ClickHouse."""
    topic, data = topic_data

    if topic == "raw.trades":
        event_time = datetime.fromisoformat(data["event_time"])
        price = float(data["price"])
        quantity = float(data["quantity"])
        trade_buffer.append([
            data["trade_id"],
            event_time,
            data["symbol"],
            data["side"],
            quantity,
            price,
            round(price * quantity, 4),
        ])

        elapsed = time.monotonic() - last_trade_flush
        if len(trade_buffer) >= BATCH_SIZE or elapsed > FLUSH_INTERVAL:
            _flush_trades()

    elif topic == "raw.quotes":
        event_time = datetime.fromisoformat(data["event_time"])
        bid = float(data["bid"])
        ask = float(data["ask"])
        quote_buffer.append([
            data["symbol"],
            event_time,
            bid,
            ask,
            float(data["bid_size"]),
            float(data["ask_size"]),
            round((bid + ask) / 2, 6),
        ])

        elapsed = time.monotonic() - last_quote_flush
        if len(quote_buffer) >= BATCH_SIZE or elapsed > FLUSH_INTERVAL:
            _flush_quotes()

    return (topic, data.get("symbol", "?"))


# Build the dataflow
flow = Dataflow("raw_sink")

source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades", "raw.quotes"],
    starting_offset=OFFSET_END,
)

stream = op.input("raw_in", flow, source)
routed = op.map("route", stream, route_message)
sunk = op.map("sink", routed, sink_record)
op.output("log", sunk, StdOutSink())
