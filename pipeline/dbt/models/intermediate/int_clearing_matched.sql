{{ config(materialized='table') }}

SELECT
    t.trade_id,
    t.event_time,
    t.symbol,
    t.side,
    t.quantity,
    t.price,
    t.notional,
    c.name AS counterparty_name,
    c.type AS counterparty_type,
    c.region AS counterparty_region,
    c.risk_rating
FROM {{ ref('stg_trades') }} t
LEFT JOIN {{ ref('counterparties') }} c
    ON t.trade_id IS NOT NULL
    AND c.counterparty_id = 'CP00' || ((ABS(cityHash64(t.trade_id)) % 5) + 1)::String
