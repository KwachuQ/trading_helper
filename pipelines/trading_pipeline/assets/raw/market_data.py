"""@bruin
name: raw.market_data
type: python
connection: duckdb_default
materialization:
    type: table
    strategy: create+replace
columns:
  - name: symbol
    type: VARCHAR
  - name: trade_date
    type: DATE
  - name: timestamp_utc
    type: TIMESTAMP
  - name: close
    type: DOUBLE
  - name: source
    type: VARCHAR
@bruin"""

import pandas as pd
import yfinance as yf
from datetime import date


def fetch_daily(ticker: str, symbol: str | None = None) -> dict:
    df = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
    if df.empty:  # type: ignore
        raise ValueError(f"INGEST_FAILURE: yfinance returned no data for {ticker}")
    return {
        "symbol":        symbol or ticker.lstrip("^"),
        "trade_date":    date.today(),
        "timestamp_utc": pd.Timestamp(df.index[-1]).normalize().to_pydatetime().replace(tzinfo=None),  # type: ignore
        "close":         float(df["Close"].squeeze().iloc[-1]),  # type: ignore
        "source":        "yfinance_daily",
    }


def fetch_market_data() -> pd.DataFrame:
    return pd.DataFrame([
        fetch_daily("QQQ"),
        fetch_daily("NQ=F", symbol="NQ"),
        fetch_daily("^VIX"),
        fetch_daily("^VVIX"),
    ])


def materialize() -> pd.DataFrame:
    return fetch_market_data()


if __name__ == "__main__":
    print(materialize().to_string())