-- Referential integrity test: every trade symbol should exist in instruments
SELECT
    t.trade_id,
    t.symbol
FROM {{ ref('stg_trades') }} t
LEFT JOIN {{ ref('stg_instruments') }} i ON t.symbol = i.symbol
WHERE i.symbol IS NULL
