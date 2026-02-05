{{ config(materialized='table') }}

SELECT
    symbol,
    name,
    sector,
    exchange,
    currency,
    lot_size
FROM {{ ref('stg_instruments') }}
