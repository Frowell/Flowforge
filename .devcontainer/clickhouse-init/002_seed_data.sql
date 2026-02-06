-- Seed data for development
-- This provides sample data without running the full pipeline
-- For more extensive historical data, use: scripts/seed_historical.py

-- Sample trades (last 7 days)
INSERT INTO flowforge.raw_trades (trade_id, event_time, symbol, side, quantity, price, notional)
SELECT
    concat('seed-', toString(number)) AS trade_id,
    now() - toIntervalDay(rand() % 7) - toIntervalHour(rand() % 24) - toIntervalMinute(rand() % 60) AS event_time,
    arrayElement(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'BAC', 'GS'], (rand() % 10) + 1) AS symbol,
    if(rand() % 2 = 0, 'BUY', 'SELL') AS side,
    arrayElement([10, 25, 50, 100, 200, 500], (rand() % 6) + 1) AS quantity,
    -- Prices with some variance around base prices
    multiIf(
        symbol = 'AAPL', 180 + (rand() % 20) - 10,
        symbol = 'MSFT', 415 + (rand() % 30) - 15,
        symbol = 'GOOGL', 150 + (rand() % 20) - 10,
        symbol = 'AMZN', 185 + (rand() % 20) - 10,
        symbol = 'NVDA', 870 + (rand() % 40) - 20,
        symbol = 'TSLA', 240 + (rand() % 30) - 15,
        symbol = 'META', 505 + (rand() % 30) - 15,
        symbol = 'JPM', 190 + (rand() % 20) - 10,
        symbol = 'BAC', 33 + (rand() % 6) - 3,
        symbol = 'GS', 415 + (rand() % 30) - 15,
        100
    ) AS price,
    quantity * price AS notional
FROM numbers(50000);

-- Sample quotes (last 7 days)
INSERT INTO flowforge.raw_quotes (symbol, event_time, bid, ask, bid_size, ask_size, mid_price)
SELECT
    arrayElement(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'BAC', 'GS'], (rand() % 10) + 1) AS symbol,
    now() - toIntervalDay(rand() % 7) - toIntervalHour(rand() % 24) - toIntervalMinute(rand() % 60) AS event_time,
    -- Bid/Ask with tight spreads
    multiIf(
        symbol = 'AAPL', 180 + (rand() % 20) - 10 - 0.05,
        symbol = 'MSFT', 415 + (rand() % 30) - 15 - 0.10,
        symbol = 'GOOGL', 150 + (rand() % 20) - 10 - 0.05,
        symbol = 'AMZN', 185 + (rand() % 20) - 10 - 0.08,
        symbol = 'NVDA', 870 + (rand() % 40) - 20 - 0.20,
        symbol = 'TSLA', 240 + (rand() % 30) - 15 - 0.10,
        symbol = 'META', 505 + (rand() % 30) - 15 - 0.15,
        symbol = 'JPM', 190 + (rand() % 20) - 10 - 0.05,
        symbol = 'BAC', 33 + (rand() % 6) - 3 - 0.02,
        symbol = 'GS', 415 + (rand() % 30) - 15 - 0.10,
        100
    ) AS bid,
    bid + (rand() % 20 + 5) / 100.0 AS ask,  -- Spread 0.05 - 0.25
    arrayElement([100, 200, 500, 1000, 2000], (rand() % 5) + 1) AS bid_size,
    arrayElement([100, 200, 500, 1000, 2000], (rand() % 5) + 1) AS ask_size,
    (bid + ask) / 2 AS mid_price
FROM numbers(100000);

-- Dimension table: Instruments
CREATE TABLE IF NOT EXISTS flowforge.dim_instruments (
    symbol        String,
    name          String,
    sector        String,
    exchange      String,
    market_cap    Decimal(18,2)
) ENGINE = MergeTree()
ORDER BY symbol;

INSERT INTO flowforge.dim_instruments VALUES
    ('AAPL', 'Apple Inc.', 'Technology', 'NASDAQ', 2800000000000),
    ('MSFT', 'Microsoft Corporation', 'Technology', 'NASDAQ', 2750000000000),
    ('GOOGL', 'Alphabet Inc.', 'Technology', 'NASDAQ', 1900000000000),
    ('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'NASDAQ', 1850000000000),
    ('NVDA', 'NVIDIA Corporation', 'Technology', 'NASDAQ', 2200000000000),
    ('TSLA', 'Tesla Inc.', 'Consumer Discretionary', 'NASDAQ', 780000000000),
    ('META', 'Meta Platforms Inc.', 'Technology', 'NASDAQ', 1300000000000),
    ('JPM', 'JPMorgan Chase & Co.', 'Financials', 'NYSE', 580000000000),
    ('BAC', 'Bank of America Corp.', 'Financials', 'NYSE', 285000000000),
    ('GS', 'Goldman Sachs Group Inc.', 'Financials', 'NYSE', 145000000000);

-- Fact table for positions (simulated current state)
CREATE TABLE IF NOT EXISTS flowforge.fct_positions (
    symbol        String,
    account_id    String,
    quantity      Decimal(18,4),
    avg_price     Decimal(18,6),
    market_value  Decimal(18,2),
    unrealized_pnl Decimal(18,2),
    as_of         DateTime
) ENGINE = ReplacingMergeTree(as_of)
ORDER BY (account_id, symbol);

INSERT INTO flowforge.fct_positions VALUES
    ('AAPL', 'ACCT001', 1500, 175.50, 277500.00, 12000.00, now()),
    ('MSFT', 'ACCT001', 800, 400.25, 336000.00, 15200.00, now()),
    ('NVDA', 'ACCT001', 200, 820.00, 176000.00, 12000.00, now()),
    ('GOOGL', 'ACCT002', 1200, 145.00, 186000.00, 12000.00, now()),
    ('AMZN', 'ACCT002', 600, 180.50, 114000.00, 5700.00, now()),
    ('TSLA', 'ACCT002', 400, 230.00, 98000.00, 6000.00, now()),
    ('META', 'ACCT003', 500, 480.00, 255000.00, 12500.00, now()),
    ('JPM', 'ACCT003', 1000, 185.00, 195000.00, 10000.00, now()),
    ('BAC', 'ACCT003', 3000, 32.50, 102000.00, 4500.00, now()),
    ('GS', 'ACCT003', 300, 400.00, 124500.00, 4500.00, now());

-- Pre-computed daily OHLCV for charts (last 30 days)
INSERT INTO metrics.daily_rollup (symbol, day, open, high, low, close, vwap, total_volume, trade_count)
SELECT
    symbol,
    toDate(now()) - toIntervalDay(day_offset) AS day,
    -- Simulated OHLCV with some trend
    base_price * (1 + (rand() % 100 - 50) / 10000.0) AS open,
    base_price * (1 + (rand() % 150) / 10000.0) AS high,
    base_price * (1 - (rand() % 150) / 10000.0) AS low,
    base_price * (1 + (rand() % 100 - 50) / 10000.0) AS close,
    base_price AS vwap,
    (rand() % 1000000 + 100000) AS total_volume,
    (rand() % 5000 + 500) AS trade_count
FROM (
    SELECT
        arrayElement(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'BAC', 'GS'], (number % 10) + 1) AS symbol,
        number / 10 AS day_offset,
        multiIf(
            symbol = 'AAPL', 185,
            symbol = 'MSFT', 420,
            symbol = 'GOOGL', 155,
            symbol = 'AMZN', 190,
            symbol = 'NVDA', 880,
            symbol = 'TSLA', 245,
            symbol = 'META', 510,
            symbol = 'JPM', 195,
            symbol = 'BAC', 35,
            symbol = 'GS', 420,
            100
        ) AS base_price
    FROM numbers(300)  -- 10 symbols x 30 days
);

-- Pre-computed hourly rollups for today
INSERT INTO metrics.hourly_rollup (symbol, hour, open, high, low, close, vwap, total_volume, trade_count)
SELECT
    symbol,
    toStartOfHour(now()) - toIntervalHour(hour_offset) AS hour,
    base_price * (1 + (rand() % 50 - 25) / 10000.0) AS open,
    base_price * (1 + (rand() % 75) / 10000.0) AS high,
    base_price * (1 - (rand() % 75) / 10000.0) AS low,
    base_price * (1 + (rand() % 50 - 25) / 10000.0) AS close,
    base_price AS vwap,
    (rand() % 100000 + 10000) AS total_volume,
    (rand() % 500 + 50) AS trade_count
FROM (
    SELECT
        arrayElement(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'BAC', 'GS'], (number % 10) + 1) AS symbol,
        number / 10 AS hour_offset,
        multiIf(
            symbol = 'AAPL', 185,
            symbol = 'MSFT', 420,
            symbol = 'GOOGL', 155,
            symbol = 'AMZN', 190,
            symbol = 'NVDA', 880,
            symbol = 'TSLA', 245,
            symbol = 'META', 510,
            symbol = 'JPM', 195,
            symbol = 'BAC', 35,
            symbol = 'GS', 420,
            100
        ) AS base_price
    FROM numbers(240)  -- 10 symbols x 24 hours
);
