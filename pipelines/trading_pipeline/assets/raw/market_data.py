"""@bruin
name: raw.market_data
type: python
connection: duckdb_default
materialization:
    type: table
    strategy: append
columns:
  - name: symbol
    type: VARCHAR
  - name: trade_date
    type: DATE
  - name: open
    type: DOUBLE
  - name: high
    type: DOUBLE
  - name: low
    type: DOUBLE
  - name: close
    type: DOUBLE
  - name: volume
    type: DOUBLE
  - name: source
    type: VARCHAR
@bruin"""

import pandas as pd
import duckdb
import yfinance as yf
from datetime import date, timedelta

BACKFILL_START = "2026-01-01"
DB_PATH = "data/trading.duckdb"

TICKERS = {
    "QQQ": "QQQ",
    "NQ=F": "NQ",
    "^VIX": "VIX",
    "^VVIX": "VVIX",
}


def get_latest_date() -> date | None:
    """Query the DB for the most recent trade_date already loaded."""
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        result = con.execute("SELECT MAX(trade_date) FROM raw.market_data").fetchone()
        con.close()
        if result and result[0] is not None:
            d = result[0]
            return d.date() if hasattr(d, "date") else d
    except Exception:
        pass
    return None


def fetch_ohlcv(ticker: str, symbol: str, start: str, end: str) -> pd.DataFrame:
    """Fetch OHLCV data for a single ticker from yfinance."""
    df = yf.download(ticker, start=start, end=end, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()

    # yfinance may return MultiIndex columns for single ticker in newer versions
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return pd.DataFrame({
        "symbol": symbol,
        "trade_date": df.index.date,
        "open": df["Open"].values,
        "high": df["High"].values,
        "low": df["Low"].values,
        "close": df["Close"].values,
        "volume": df["Volume"].values,
        "source": "yfinance_daily",
    })


def materialize() -> pd.DataFrame:
    latest = get_latest_date()

    if latest is None:
        # First run: full backfill
        start = BACKFILL_START
        print(f"No existing data found. Backfilling from {BACKFILL_START}.")
    else:
        # Incremental: fetch from day after last loaded date
        start = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"Latest data: {latest}. Fetching from {start}.")

    end = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")  # yfinance end is exclusive

    if start >= end:
        print("Data is up to date. Nothing to fetch.")
        return pd.DataFrame(columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "source"])

    frames = []
    for ticker, symbol in TICKERS.items():
        df = fetch_ohlcv(ticker, symbol, start, end)
        if not df.empty:
            frames.append(df)
        else:
            print(f"No new data for {ticker} ({symbol}).")

    if not frames:
        print("No new data from any ticker.")
        return pd.DataFrame(columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "source"])

    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print(materialize().to_string())