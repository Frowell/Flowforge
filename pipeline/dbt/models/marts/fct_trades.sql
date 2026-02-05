{{ config(materialized='table', order_by='(symbol, event_time)') }}

SELECT
    trade_id,
    event_time,
    symbol,
    instrument_name,
    sector,
    exchange,
    currency,
    side,
    quantity,
    price,
    notional,
    toDate(event_time) AS trade_date,
    toHour(event_time) AS trade_hour
FROM {{ ref('int_trades_enriched') }}
