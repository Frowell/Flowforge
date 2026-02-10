"""
Raw data sink — consumes raw.trades and raw.quotes from Redpanda
and inserts them into ClickHouse flowforge.raw_trades / flowforge.raw_quotes.

The Bytewax VWAP and Volatility flows only write aggregated data.
This flow writes the raw events so they're queryable in the canvas.
"""
import os
import json
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

ch_client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Buffers for batched inserts
trade_buffer: list[list] = []
quote_buffer: list[list] = []


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

        if len(trade_buffer) >= BATCH_SIZE:
            ch_client.insert(
                "flowforge.raw_trades",
                trade_buffer,
                column_names=["trade_id", "event_time", "symbol", "side",
                              "quantity", "price", "notional"],
            )
            trade_buffer.clear()
            r_client.publish(
                "flowforge:broadcast:table_update",
                json.dumps({"type": "table_update", "table": "raw_trades"}),
            )

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

        if len(quote_buffer) >= BATCH_SIZE:
            ch_client.insert(
                "flowforge.raw_quotes",
                quote_buffer,
                column_names=["symbol", "event_time", "bid", "ask",
                              "bid_size", "ask_size", "mid_price"],
            )
            quote_buffer.clear()
            r_client.publish(
                "flowforge:broadcast:table_update",
                json.dumps({"type": "table_update", "table": "raw_quotes"}),
            )

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
