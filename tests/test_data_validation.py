import pandas as pd
import pytest
from datetime import date


def make_raw_data(symbols=("NQ", "QQQ", "VIX", "VVIX"), overrides=None):
    """Create mock raw market data rows for a single trade date."""
    rows = []
    for sym in symbols:
        row = {
            "symbol": sym,
            "trade_date": date(2026, 3, 30),
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
            "volume": 1000.0,
        }
        if overrides and sym in overrides:
            row.update(overrides[sym])
        rows.append(row)
    return pd.DataFrame(rows)


def join_symbols(df: pd.DataFrame) -> pd.DataFrame:
    """Replicate the INNER JOIN logic from sync_check.py for testing."""
    nq = df[df["symbol"] == "NQ"].set_index("trade_date")
    qqq = df[df["symbol"] == "QQQ"].set_index("trade_date")
    vix = df[df["symbol"] == "VIX"].set_index("trade_date")
    vvix = df[df["symbol"] == "VVIX"].set_index("trade_date")

    joined = nq.join(qqq, lsuffix="_nq", rsuffix="_qqq", how="inner")
    joined = joined.join(vix[["close"]].rename(columns={"close": "vix_close"}), how="inner")
    joined = joined.join(vvix[["close"]].rename(columns={"close": "vvix_close"}), how="inner")
    return joined


def test_all_symbols_present_passes():
    df = make_raw_data()
    joined = join_symbols(df)
    assert len(joined) == 1


def test_missing_symbol_skips_date():
    df = make_raw_data(symbols=("NQ", "QQQ", "VIX"))
    joined = join_symbols(df)
    assert len(joined) == 0  # INNER JOIN excludes dates without all 4


def test_zero_vix_detected():
    df = make_raw_data(overrides={"VIX": {"close": 0.0}})
    joined = join_symbols(df)
    bad = joined[joined["vix_close"] <= 0]
    assert len(bad) == 1


def test_zero_qqq_detected():
    df = make_raw_data(overrides={"QQQ": {"close": 0.0}})
    joined = join_symbols(df)
    bad = joined[joined["close_qqq"] <= 0]
    assert len(bad) == 1
