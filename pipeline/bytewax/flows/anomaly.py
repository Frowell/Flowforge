"""
Anomaly detection for spread and volume.
Reads from raw.trades and raw.quotes topics, detects statistical outliers,
writes alerts to ClickHouse and publishes to Redis pub/sub for real-time alerting.

Anomaly types detected:
- Spread anomaly: Bid-ask spread > 3 standard deviations from rolling mean
- Volume anomaly: Trade volume > 3 standard deviations from rolling mean
- Price jump: Price move > 2% in a single trade
"""

import os
import json
import math
from datetime import timedelta, datetime, timezone
from collections import deque
from dataclasses import dataclass
from typing import Optional

import bytewax.operators as op
from bytewax.dataflow import Dataflow
from bytewax.connectors.kafka import KafkaSource

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

# Anomaly thresholds
SPREAD_STD_THRESHOLD = 3.0
VOLUME_STD_THRESHOLD = 3.0
PRICE_JUMP_THRESHOLD = 0.02  # 2%

# Rolling window for baseline statistics
WINDOW_SIZE = 100  # Number of observations


@dataclass
class Anomaly:
    symbol: str
    anomaly_type: str
    severity: str  # 'low', 'medium', 'high'
    value: float
    threshold: float
    z_score: float
    event_time: datetime
    message: str


class RollingStats:
    """Online mean and standard deviation using Welford's algorithm."""

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self.values = deque(maxlen=window_size)
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0  # Sum of squared differences from mean

    def add(self, value: float):
        if len(self.values) >= self.window_size:
            # Remove oldest value from stats
            old_value = self.values[0]
            old_n = self.n
            old_mean = self.mean
            self.n -= 1
            if self.n > 0:
                self.mean = (old_mean * old_n - old_value) / self.n
                self.m2 -= (old_value - old_mean) * (old_value - self.mean)

        # Add new value
        self.values.append(value)
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def std(self) -> float:
        if self.n < 2:
            return 0.0
        return math.sqrt(self.m2 / (self.n - 1))

    def z_score(self, value: float) -> float:
        std = self.std
        if std == 0:
            return 0.0
        return (value - self.mean) / std


class AnomalyDetector:
    """Detects anomalies in trades and quotes for a single symbol."""

    def __init__(self):
        self.spread_stats = RollingStats()
        self.volume_stats = RollingStats()
        self.last_price: Optional[float] = None
        self.last_alert_time: dict[str, datetime] = {}

    def _should_alert(self, anomaly_type: str) -> bool:
        """Rate limit alerts to once per minute per type."""
        now = datetime.now(timezone.utc)
        last = self.last_alert_time.get(anomaly_type)
        if last is None or (now - last) >= timedelta(minutes=1):
            self.last_alert_time[anomaly_type] = now
            return True
        return False

    def check_trade(self, symbol: str, trade: dict) -> Optional[Anomaly]:
        """Check trade for volume and price jump anomalies."""
        volume = trade["quantity"]
        price = trade["price"]
        event_time = trade["event_time"]

        anomalies = []

        # Volume anomaly
        if self.volume_stats.n >= 10:  # Need baseline
            z = self.volume_stats.z_score(volume)
            if abs(z) > VOLUME_STD_THRESHOLD and self._should_alert("volume"):
                severity = "high" if abs(z) > 5 else ("medium" if abs(z) > 4 else "low")
                anomalies.append(
                    Anomaly(
                        symbol=symbol,
                        anomaly_type="volume_spike",
                        severity=severity,
                        value=volume,
                        threshold=self.volume_stats.mean
                        + VOLUME_STD_THRESHOLD * self.volume_stats.std,
                        z_score=z,
                        event_time=event_time,
                        message=f"Volume spike: {volume:.0f} shares ({z:.1f} std devs)",
                    )
                )
        self.volume_stats.add(volume)

        # Price jump anomaly
        if self.last_price is not None:
            pct_change = abs(price - self.last_price) / self.last_price
            if pct_change > PRICE_JUMP_THRESHOLD and self._should_alert("price_jump"):
                direction = "up" if price > self.last_price else "down"
                severity = (
                    "high"
                    if pct_change > 0.05
                    else ("medium" if pct_change > 0.03 else "low")
                )
                anomalies.append(
                    Anomaly(
                        symbol=symbol,
                        anomaly_type="price_jump",
                        severity=severity,
                        value=pct_change * 100,
                        threshold=PRICE_JUMP_THRESHOLD * 100,
                        z_score=0.0,  # Not z-score based
                        event_time=event_time,
                        message=f"Price jump {direction}: {pct_change * 100:.2f}% (${self.last_price:.2f} → ${price:.2f})",
                    )
                )
        self.last_price = price

        return anomalies[0] if anomalies else None

    def check_quote(self, symbol: str, quote: dict) -> Optional[Anomaly]:
        """Check quote for spread anomalies."""
        bid = quote["bid"]
        ask = quote["ask"]
        event_time = quote["event_time"]

        if bid <= 0:
            return None

        spread_bps = (ask - bid) / bid * 10000  # Basis points

        # Spread anomaly
        if self.spread_stats.n >= 10:  # Need baseline
            z = self.spread_stats.z_score(spread_bps)
            if abs(z) > SPREAD_STD_THRESHOLD and self._should_alert("spread"):
                severity = "high" if abs(z) > 5 else ("medium" if abs(z) > 4 else "low")
                return Anomaly(
                    symbol=symbol,
                    anomaly_type="spread_widening",
                    severity=severity,
                    value=spread_bps,
                    threshold=self.spread_stats.mean
                    + SPREAD_STD_THRESHOLD * self.spread_stats.std,
                    z_score=z,
                    event_time=event_time,
                    message=f"Spread widening: {spread_bps:.1f} bps ({z:.1f} std devs)",
                )
        self.spread_stats.add(spread_bps)

        return None


# Global state per symbol
detectors: dict[str, AnomalyDetector] = {}


def get_detector(symbol: str) -> AnomalyDetector:
    if symbol not in detectors:
        detectors[symbol] = AnomalyDetector()
    return detectors[symbol]


def parse_trade(msg):
    """Parse raw JSON trade message."""
    data = json.loads(msg.value)
    return (
        "trade",
        data["symbol"],
        {
            "event_time": datetime.fromisoformat(data["event_time"]),
            "price": float(data["price"]),
            "quantity": float(data["quantity"]),
        },
    )


def parse_quote(msg):
    """Parse raw JSON quote message."""
    data = json.loads(msg.value)
    return (
        "quote",
        data["symbol"],
        {
            "event_time": datetime.fromisoformat(data["event_time"]),
            "bid": float(data["bid"]),
            "ask": float(data["ask"]),
        },
    )


def detect_anomaly(event):
    """Detect anomalies in trades and quotes."""
    event_type, symbol, data = event
    detector = get_detector(symbol)

    if event_type == "trade":
        anomaly = detector.check_trade(symbol, data)
    else:
        anomaly = detector.check_quote(symbol, data)

    return anomaly


def emit_anomaly(anomaly: Anomaly):
    """Write anomaly to ClickHouse and publish to Redis."""
    if anomaly is None:
        return None

    # Create alerts table if not exists
    ch_client.command("""
        CREATE TABLE IF NOT EXISTS metrics.anomaly_alerts (
            symbol        String,
            anomaly_type  String,
            severity      String,
            value         Float64,
            threshold     Float64,
            z_score       Float64,
            event_time    DateTime64(3),
            message       String
        ) ENGINE = MergeTree()
        ORDER BY (symbol, event_time)
        TTL toDateTime(event_time) + INTERVAL 7 DAY
    """)

    # Write to ClickHouse
    ch_client.insert(
        "metrics.anomaly_alerts",
        [
            [
                anomaly.symbol,
                anomaly.anomaly_type,
                anomaly.severity,
                anomaly.value,
                anomaly.threshold,
                anomaly.z_score,
                anomaly.event_time,
                anomaly.message,
            ]
        ],
        column_names=[
            "symbol",
            "anomaly_type",
            "severity",
            "value",
            "threshold",
            "z_score",
            "event_time",
            "message",
        ],
    )

    # Publish to Redis for real-time alerting
    alert_data = json.dumps(
        {
            "symbol": anomaly.symbol,
            "type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "message": anomaly.message,
            "value": anomaly.value,
            "threshold": anomaly.threshold,
            "event_time": anomaly.event_time.isoformat(),
        }
    )
    r_client.publish("alerts:anomalies", alert_data)

    # Also store latest per symbol/type in Redis
    r_client.hset(
        f"latest:anomaly:{anomaly.symbol}",
        mapping={
            "type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "message": anomaly.message,
            "event_time": anomaly.event_time.isoformat(),
        },
    )
    r_client.expire(f"latest:anomaly:{anomaly.symbol}", 3600)  # 1 hour TTL

    print(f"[ANOMALY] {anomaly.severity.upper()}: {anomaly.symbol} - {anomaly.message}")

    return anomaly


# Build the dataflow
flow = Dataflow("anomaly_detection")

# Two input sources
trades_source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.trades"],
    starting_offset="end",
)

quotes_source = KafkaSource(
    brokers=REDPANDA_BROKERS,
    topics=["raw.quotes"],
    starting_offset="end",
)

# Parse both streams
trades_stream = op.input("trades_in", flow, trades_source)
quotes_stream = op.input("quotes_in", flow, quotes_source)

trades_parsed = op.map("parse_trades", trades_stream, parse_trade)
quotes_parsed = op.map("parse_quotes", quotes_stream, parse_quote)

# Merge streams
# Note: In production, use op.merge for proper stream merging
# For simplicity, we process them separately and both feed into detection

trades_anomalies = op.map("detect_trade_anomaly", trades_parsed, detect_anomaly)
quotes_anomalies = op.map("detect_quote_anomaly", quotes_parsed, detect_anomaly)

# Filter out None (non-anomalies)
trades_filtered = op.filter(
    "filter_trade_anomalies", trades_anomalies, lambda x: x is not None
)
quotes_filtered = op.filter(
    "filter_quote_anomalies", quotes_anomalies, lambda x: x is not None
)

# Emit to sinks
op.map("emit_trade_anomalies", trades_filtered, emit_anomaly)
op.map("emit_quote_anomalies", quotes_filtered, emit_anomaly)
