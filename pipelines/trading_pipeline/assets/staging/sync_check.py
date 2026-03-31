"""@bruin
name: staging.validated_data
type: python
connection: duckdb_default
materialization:
    type: table
    strategy: create+replace
depends:
    - raw.market_data
columns:
  - name: trade_date
    type: DATE
  - name: run_ts
    type: TIMESTAMP
  - name: nq_open
    type: DOUBLE
  - name: nq_high
    type: DOUBLE
  - name: nq_low
    type: DOUBLE
  - name: nq_close
    type: DOUBLE
  - name: qqq_open
    type: DOUBLE
  - name: qqq_high
    type: DOUBLE
  - name: qqq_low
    type: DOUBLE
  - name: qqq_close
    type: DOUBLE
  - name: vix_close
    type: DOUBLE
  - name: vvix_close
    type: DOUBLE
@bruin"""

import pandas as pd
import duckdb
from datetime import datetime, timezone

DB_PATH = "data/trading.duckdb"


def write_error(con: duckdb.DuckDBPyConnection, error_code: str, message: str) -> None:
    con.execute("""
        CREATE SCHEMA IF NOT EXISTS mart;
        CREATE TABLE IF NOT EXISTS mart.pipeline_errors (
            run_ts      TIMESTAMP NOT NULL,
            error_code  VARCHAR   NOT NULL,
            message     VARCHAR   NOT NULL
        )
    """)
    con.execute(
        "INSERT INTO mart.pipeline_errors (run_ts, error_code, message) VALUES (?, ?, ?)",
        [datetime.now(timezone.utc).replace(tzinfo=None), error_code, message],
    )


def materialize() -> pd.DataFrame:
    con = duckdb.connect(DB_PATH)

    # Join all 4 symbols on trade_date (INNER JOIN ensures all 4 present)
    query = """
    SELECT
        nq.trade_date,
        nq.open   AS nq_open,
        nq.high   AS nq_high,
        nq.low    AS nq_low,
        nq.close  AS nq_close,
        qqq.open  AS qqq_open,
        qqq.high  AS qqq_high,
        qqq.low   AS qqq_low,
        qqq.close AS qqq_close,
        vix.close AS vix_close,
        vvix.close AS vvix_close
    FROM (SELECT * FROM raw.market_data WHERE symbol = 'NQ') nq
    INNER JOIN (SELECT * FROM raw.market_data WHERE symbol = 'QQQ') qqq
        ON nq.trade_date = qqq.trade_date
    INNER JOIN (SELECT * FROM raw.market_data WHERE symbol = 'VIX') vix
        ON nq.trade_date = vix.trade_date
    INNER JOIN (SELECT * FROM raw.market_data WHERE symbol = 'VVIX') vvix
        ON nq.trade_date = vvix.trade_date
    ORDER BY nq.trade_date
    """

    df = con.execute(query).df()

    if df.empty:
        con.close()
        raise ValueError("VALIDATION_FAILURE: No dates with all 4 symbols present in raw.market_data")

    # Log and filter division-by-zero cases
    bad_vix = df[df["vix_close"] <= 0]
    for _, row in bad_vix.iterrows():
        msg = f"BUSINESS_LOGIC_ERROR: VIX close is {row['vix_close']} on {row['trade_date']}"
        write_error(con, "BUSINESS_LOGIC_ERROR", msg)
        print(f"WARNING: {msg}")

    bad_qqq = df[df["qqq_close"] <= 0]
    for _, row in bad_qqq.iterrows():
        msg = f"BUSINESS_LOGIC_ERROR: QQQ close is {row['qqq_close']} on {row['trade_date']}"
        write_error(con, "BUSINESS_LOGIC_ERROR", msg)
        print(f"WARNING: {msg}")

    con.close()

    df = df[(df["vix_close"] > 0) & (df["qqq_close"] > 0)]

    if df.empty:
        raise ValueError("VALIDATION_FAILURE: All dates filtered out due to zero-value closes")

    df["run_ts"] = datetime.now(timezone.utc).replace(tzinfo=None)

    return df[["trade_date", "run_ts",
               "nq_open", "nq_high", "nq_low", "nq_close",
               "qqq_open", "qqq_high", "qqq_low", "qqq_close",
               "vix_close", "vvix_close"]]


if __name__ == "__main__":
    print(materialize().to_string())