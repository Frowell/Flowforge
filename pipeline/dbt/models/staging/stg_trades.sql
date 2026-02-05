{{ config(materialized='view') }}

SELECT
    trade_id,
    event_time,
    symbol,
    side,
    quantity,
    price,
    quantity * price AS notional
FROM flowforge.raw_trades
