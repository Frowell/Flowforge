{{ config(materialized='table') }}

SELECT
    t.trade_id,
    t.event_time,
    t.symbol,
    t.side,
    t.quantity,
    t.price,
    t.notional,
    i.sector,
    i.exchange,
    i.currency,
    i.name AS instrument_name
FROM {{ ref('stg_trades') }} t
LEFT JOIN {{ ref('stg_instruments') }} i ON t.symbol = i.symbol
