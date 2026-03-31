import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "trading.duckdb")

st.title("Data Tables")

SYMBOLS = {
    "QQQ": "QQQ",
    "NQ": "NQ",
    "VIX": "VIX",
    "VVIX": "VVIX",
    "Trading Metrics": None,
}


@st.cache_data(ttl=300)
def load_symbol(symbol: str) -> pd.DataFrame:
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute(
            "SELECT trade_date, open, high, low, close, volume "
            "FROM raw.market_data WHERE symbol = ? ORDER BY trade_date DESC",
            [symbol],
        ).df()
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_metrics() -> pd.DataFrame:
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute(
            "SELECT trade_date, nq_qqq_ratio, vvix_vix_ratio, adr_nq, adr_qqq, "
            "nq_close, qqq_close, vix_close, vvix_close "
            "FROM mart.trading_metrics ORDER BY trade_date DESC"
        ).df()
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


tabs = st.tabs(list(SYMBOLS.keys()))

for tab, (label, symbol) in zip(tabs, SYMBOLS.items()):
    with tab:
        if symbol is not None:
            df = load_symbol(symbol)
        else:
            df = load_metrics()

        if df.empty:
            st.info(f"No data available for {label}. Run the pipeline first.")
        else:
            st.caption(f"{len(df)} rows")
            st.dataframe(df, use_container_width=True, hide_index=True)
