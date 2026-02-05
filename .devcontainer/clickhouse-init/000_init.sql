CREATE DATABASE IF NOT EXISTS flowforge;
CREATE DATABASE IF NOT EXISTS metrics;
CREATE DATABASE IF NOT EXISTS marts;

-- Raw trades table (warm path writes here)
CREATE TABLE IF NOT EXISTS flowforge.raw_trades (
    trade_id      String,
    event_time    DateTime64(3),
    symbol        String,
    side          Enum8('BUY'=1, 'SELL'=2),
    quantity      Decimal(18,4),
    price         Decimal(18,6),
    notional      Decimal(18,4)
) ENGINE = MergeTree()
ORDER BY (symbol, event_time)
PARTITION BY toYYYYMM(event_time);

-- Raw quotes table
CREATE TABLE IF NOT EXISTS flowforge.raw_quotes (
    symbol        String,
    event_time    DateTime64(3),
    bid           Decimal(18,6),
    ask           Decimal(18,6),
    bid_size      Decimal(18,4),
    ask_size      Decimal(18,4),
    mid_price     Decimal(18,6)
) ENGINE = MergeTree()
ORDER BY (symbol, event_time)
PARTITION BY toYYYYMM(event_time);

-- VWAP 5-min windows (Bytewax writes here)
CREATE TABLE IF NOT EXISTS metrics.vwap_5min (
    symbol        String,
    window_end    DateTime64(3),
    vwap          Decimal(18,6),
    volume        Decimal(18,4),
    trade_count   UInt32,
    spread_bps    Decimal(8,2)
) ENGINE = MergeTree()
ORDER BY (symbol, window_end);

-- Rolling volatility (Bytewax writes here)
CREATE TABLE IF NOT EXISTS metrics.rolling_volatility (
    symbol        String,
    window_end    DateTime64(3),
    volatility_1h Decimal(18,8),
    volatility_24h Decimal(18,8),
    return_pct    Decimal(18,8)
) ENGINE = MergeTree()
ORDER BY (symbol, window_end);
