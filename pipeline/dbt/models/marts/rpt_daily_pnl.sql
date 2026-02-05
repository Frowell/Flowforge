{{ config(materialized='table', order_by='(symbol, trade_date)') }}

SELECT
    symbol,
    toDate(event_time) AS trade_date,
    SUM(CASE WHEN side = 'BUY' THEN -notional ELSE notional END) AS realized_pnl,
    SUM(quantity) AS total_volume,
    COUNT(*) AS trade_count,
    AVG(price) AS avg_price
FROM {{ ref('fct_trades') }}
GROUP BY symbol, trade_date
