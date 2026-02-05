-- Cool path: ClickHouse MVs auto-aggregate on insert
-- IMPORTANT: Target tables MUST be created before their MVs.
-- ClickHouse requires the destination table to exist when creating a MV with TO clause.

CREATE TABLE IF NOT EXISTS metrics.hourly_rollup (
    symbol        String,
    hour          DateTime,
    open          Decimal(18,6),
    high          Decimal(18,6),
    low           Decimal(18,6),
    close         Decimal(18,6),
    vwap          Decimal(18,6),
    total_volume  Decimal(18,4),
    trade_count   UInt32
) ENGINE = MergeTree()
ORDER BY (symbol, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.hourly_rollup_mv
TO metrics.hourly_rollup AS
SELECT
    symbol,
    toStartOfHour(event_time) AS hour,
    argMin(price, event_time) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, event_time) AS close,
    sum(notional) / sum(quantity) AS vwap,
    sum(quantity) AS total_volume,
    count() AS trade_count
FROM flowforge.raw_trades
GROUP BY symbol, hour;

CREATE TABLE IF NOT EXISTS metrics.daily_rollup (
    symbol        String,
    day           Date,
    open          Decimal(18,6),
    high          Decimal(18,6),
    low           Decimal(18,6),
    close         Decimal(18,6),
    vwap          Decimal(18,6),
    total_volume  Decimal(18,4),
    trade_count   UInt32
) ENGINE = MergeTree()
ORDER BY (symbol, day);

CREATE MATERIALIZED VIEW IF NOT EXISTS metrics.daily_rollup_mv
TO metrics.daily_rollup AS
SELECT
    symbol,
    toDate(event_time) AS day,
    argMin(price, event_time) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, event_time) AS close,
    sum(notional) / sum(quantity) AS vwap,
    sum(quantity) AS total_volume,
    count() AS trade_count
FROM flowforge.raw_trades
GROUP BY symbol, day;
