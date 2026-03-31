/* @bruin
name: mart.trading_metrics
type: duckdb.sql
materialization:
    type: table
    strategy: create+replace
depends:
    - staging.validated_data
columns:
  - name: trade_date
    type: DATE
  - name: nq_qqq_ratio
    type: DOUBLE
  - name: vvix_vix_ratio
    type: DOUBLE
  - name: adr_nq
    type: DOUBLE
  - name: adr_qqq
    type: DOUBLE
  - name: nq_close
    type: DOUBLE
  - name: qqq_close
    type: DOUBLE
  - name: nq_high
    type: DOUBLE
  - name: nq_low
    type: DOUBLE
  - name: qqq_high
    type: DOUBLE
  - name: qqq_low
    type: DOUBLE
  - name: vix_close
    type: DOUBLE
  - name: vvix_close
    type: DOUBLE
@bruin */

SELECT
    trade_date,
    ROUND(nq_close / qqq_close, 4)   AS nq_qqq_ratio,
    ROUND(vvix_close / vix_close, 4)  AS vvix_vix_ratio,
    ROUND(nq_high - nq_low, 4)       AS adr_nq,
    ROUND(qqq_high - qqq_low, 4)     AS adr_qqq,
    nq_close,
    qqq_close,
    nq_high,
    nq_low,
    qqq_high,
    qqq_low,
    vix_close,
    vvix_close
FROM staging.validated_data
ORDER BY trade_date
