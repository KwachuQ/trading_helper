import streamlit as st

st.title("Info")

st.markdown("""
## Trading Analysis Pipeline

Built with [**Bruin**](https://github.com/bruin-data/bruin) — a data pipeline framework that
orchestrates Python and SQL assets with dependency management, validation, and DuckDB integration.

---

### What it does

A daily ETL pipeline that fetches **end-of-day** OHLCV quotes for four symbols from **yfinance**,
stores them in a local DuckDB database, and provides analytical views and tooling for pre-market
analysis.

### Data loading strategy

The pipeline uses an **incremental append** strategy:

- **First run** — backfills all data from **January 1, 2026** to today.
- **Subsequent runs** — queries `MAX(trade_date)` in the database and fetches only dates after
  the latest stored record. If already up to date, no download is performed.

This means the pipeline is safe to run multiple times a day without duplicating data, and will
automatically catch up on any missed days.

---

### Tracked Symbols

| Symbol | Ticker | Description |
|--------|--------|-------------|
| **QQQ** | `QQQ` | Invesco QQQ Trust — ETF tracking the Nasdaq-100 index |
| **NQ** | `NQ=F` | E-mini Nasdaq-100 futures (continuous front-month contract) |
| **VIX** | `^VIX` | CBOE Volatility Index — measures expected 30-day volatility of the S&P 500 |
| **VVIX** | `^VVIX` | CBOE VIX of VIX — measures expected volatility of VIX itself |

---

### Charts & Ratios

#### VVIX / VIX Ratio
The ratio of VVIX to VIX captures the **volatility-of-volatility regime**:

- **Low (< 5):** Typically occurs during or just after a volatility event. VIX is elevated — fear
  has been realized — but VVIX lags. Often marks peak stress; the market may be near a turning point.
- **Mid (5–6):** Neutral zone. VVIX and VIX are proportionally aligned. No strong signal, but
  worth watching for directional drift.
- **High (> 6):** Markets appear calm but VVIX is rising — traders are pricing in future
  volatility. Often precedes sharp corrections.

#### VIX & VVIX Charts
Time-series of daily closes. Rising VVIX when VIX is low signals increasing hedging demand under
the surface.

#### NQ ADR (Average Daily Range)
Computed as **High − Low** for each trading day. Plotted alongside the VVIX/VIX ratio to evaluate
whether the ratio has **predictive value** for upcoming daily price ranges.

#### NQ / QQQ Ratio
`NQ close ÷ QQQ close` — the conversion multiplier used by the **QQQ → NQ Level Calculator**.

---

### QQQ → NQ Level Calculator

Paste comma-separated QQQ levels (e.g. from SpotGamma) and the calculator multiplies each value
by the latest NQ/QQQ ratio to produce the NQ equivalent.

**Input:** `Call Resistance, 630, Put Support, 560, HVL, 600, ...`
**Output:** `Call Resistance, 24750, Put Support, 22000, HVL, 23571.43, ...`

---

### Pipeline layers

| Layer | Asset | Description |
|-------|-------|-------------|
| **Raw** | `raw.market_data` | Fetches OHLCV from yfinance (incremental append) |
| **Staging** | `staging.validated_data` | Joins symbols on trade date, validates completeness |
| **Mart** | `mart.trading_metrics` | Computes NQ/QQQ ratio, VVIX/VIX ratio, and ADR |

```bash
bruin run pipelines/trading_pipeline
```
""")
