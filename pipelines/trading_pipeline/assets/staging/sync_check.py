"""@bruin
name: staging.sync_validated
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
  - name: nq_symbol
    type: VARCHAR
  - name: nq_timestamp_utc
    type: TIMESTAMP
  - name: nq_close
    type: DOUBLE
  - name: qqq_timestamp_utc
    type: TIMESTAMP
  - name: qqq_close
    type: DOUBLE
  - name: qqq_drift_seconds
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
DRIFT_THRESHOLD_SECONDS = 10


def write_error(con: duckdb.DuckDBPyConnection, error_code: str, message: str) -> None:
    con.execute("""
        CREATE SCHEMA IF NOT EXISTS mart;
        CREATE TABLE IF NOT EXISTS mart.pipeline_errors (
            id        INTEGER,
            run_ts    TIMESTAMPTZ NOT NULL,
            error_code VARCHAR     NOT NULL,
            message   VARCHAR     NOT NULL
        )
    """)
    con.execute(
        "INSERT INTO mart.pipeline_errors (run_ts, error_code, message) VALUES (?, ?, ?)",
        [datetime.now(timezone.utc), error_code, message],
    )


def validate_and_join() -> pd.DataFrame:
    con = duckdb.connect(DB_PATH)
    md = con.execute("SELECT symbol, trade_date, timestamp_utc, close FROM raw.market_data").df()
    con.close()

    if md.empty:
        raise ValueError("SYNC_FAILURE: raw.market_data is empty")

    nq_row   = md[md["symbol"] == "NQ"].iloc[0]
    qqq_row  = md[md["symbol"] == "QQQ"].iloc[0]
    vix_row  = md[md["symbol"] == "VIX"].iloc[0]
    vvix_row = md[md["symbol"] == "VVIX"].iloc[0]

    def to_utc(ts) -> pd.Timestamp:
        t = pd.Timestamp(ts)
        return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")

    nq_ts  = to_utc(nq_row["timestamp_utc"])
    qqq_ts = to_utc(qqq_row["timestamp_utc"])

    drift = abs((qqq_ts - nq_ts).total_seconds())

    con = duckdb.connect(DB_PATH)

    if drift > DRIFT_THRESHOLD_SECONDS:
        msg = f"SYNC_FAILURE: QQQ drift {drift:.1f}s exceeds {DRIFT_THRESHOLD_SECONDS}s threshold (NQ={nq_ts}, QQQ={qqq_ts})"
        write_error(con, "SYNC_FAILURE", msg)
        con.close()
        raise RuntimeError(msg)

    vix_close  = float(vix_row["close"])
    vvix_close = float(vvix_row["close"])

    if vix_close <= 0:
        msg = f"BUSINESS_LOGIC_ERROR: VIX close is {vix_close} — division by zero would occur"
        write_error(con, "BUSINESS_LOGIC_ERROR", msg)
        con.close()
        raise RuntimeError(msg)

    if vvix_close <= 0:
        msg = f"BUSINESS_LOGIC_ERROR: VVIX close is {vvix_close} — cannot compute ratio"
        write_error(con, "BUSINESS_LOGIC_ERROR", msg)
        con.close()
        raise RuntimeError(msg)

    con.close()

    return pd.DataFrame([{
        "trade_date":        nq_row["trade_date"],
        "run_ts":            datetime.now(timezone.utc).replace(tzinfo=None),
        "nq_symbol":         "NQ",
        "nq_last_time_utc":  nq_ts.to_pydatetime().replace(tzinfo=None),
        "nq_close":          float(nq_row["close"]),
        "qqq_timestamp_utc": qqq_ts.to_pydatetime().replace(tzinfo=None),
        "qqq_close":         float(qqq_row["close"]),
        "qqq_drift_seconds": drift,
        "vix_close":         vix_close,
        "vvix_close":        vvix_close,
    }])


def materialize() -> pd.DataFrame:
    return validate_and_join()


if __name__ == "__main__":
    print(materialize().to_string())