# Implementation Plan: Trading Analysis Pipeline

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage | DuckDB (`data/trading.duckdb`) | Local, zero-config, no credentials |
| Data source | yfinance end-of-day OHLCV | Free, reliable for daily bars; covers QQQ, NQ=F, ^VIX, ^VVIX |
| Backfill start | 2026-01-01 | Full year-to-date historical coverage |
| Fetch strategy | Incremental — only fetch missing dates | Fast subsequent runs, avoids redundant API calls |
| ADR calculation | `High − Low` per day | Simple, derived directly from OHLCV data |
| Trigger | Manual via Bruin CLI / VS Code extension | Run after market close or morning before RTH |
| UI | Streamlit | Simple, Python-native, no separate frontend; built-in charting |

## DAG Structure

```
raw.market_data ──▶ staging.validated_data ──▶ mart.trading_metrics
                                                      │
                                                      └──▶ mart.pipeline_errors (on failure)
```

## File Structure

```
.bruin.yml                                      # DuckDB connection config
requirements.txt                                # yfinance, pandas, duckdb, pytest, streamlit, plotly
pipelines/trading_pipeline/
    pipeline.yml                                # Pipeline name, @manual schedule
    assets/
        raw/
            market_data.py                      # yfinance OHLCV fetch with backfill + incremental
        staging/
            sync_check.py                       # Data validation + division-by-zero guards
        mart/
            pipeline_errors.sql                 # Error table DDL
            trading_metrics.sql                 # Ratios + ADR table
app/
    dashboard.py                                # Streamlit UI: charts + calculator
tests/
    test_data_validation.py
    test_transform.py
    test_calculator.py
data/
    trading.duckdb                              # Generated at runtime
```

## DuckDB Tables

| Table | Layer | Key Columns |
|---|---|---|
| `raw.market_data` | raw | `symbol`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `source` |
| `staging.validated_data` | staging | `trade_date`, `run_ts`, `nq_close`, `qqq_close`, `vix_close`, `vvix_close`, `nq_high`, `nq_low`, `qqq_high`, `qqq_low` |
| `mart.pipeline_errors` | mart | `id`, `run_ts`, `error_code`, `message` |
| `mart.trading_metrics` | mart | `trade_date`, `nq_qqq_ratio`, `vvix_vix_ratio`, `adr_nq`, `adr_qqq`, raw closes + OHLCV |

---

## Phase 1 — Foundation ✅ DONE

**Goal**: Scaffold the project so Bruin can discover and validate the pipeline.

- [x] `.bruin.yml` — DuckDB connection `duckdb_default` → `data/trading.duckdb`
- [x] `pipelines/trading_pipeline/pipeline.yml` — `@manual` schedule, default connection `duckdb_default`
- [x] `requirements.txt` — `yfinance`, `pandas`, `duckdb`, `pytest`
- [x] Folder structure: `assets/raw/`, `assets/staging/`, `assets/mart/`, `tests/`

**Updates needed:**
- [ ] Add `streamlit` and `plotly` to `requirements.txt`
- [ ] Create `app/` directory

**Verify with CLI:**
```bash
bruin validate pipelines/trading_pipeline
```

---

## Phase 2 — Raw Layer (NEEDS UPDATE)

**Goal**: Fetch end-of-day OHLCV data for QQQ, NQ=F, ^VIX, ^VVIX from yfinance with historical backfill from 2026-01-01 and incremental daily updates.

### `assets/raw/market_data.py`

Bruin Python asset. No upstream dependencies. Materializes `raw.market_data`.

**Current state**: Fetches only the last 5 days of `Close` data. Needs rewrite for full OHLCV + backfill.

**Updated logic:**
1. Query `raw.market_data` for the latest `trade_date` per symbol to determine what's already loaded.
2. If no data exists, set start date to `2026-01-01`. Otherwise, set start date to `last_trade_date + 1 day`.
3. For each ticker (`QQQ`, `NQ=F`, `^VIX`, `^VVIX`):
   - `yf.download(ticker, start=start_date, end=today, interval="1d")` → get full OHLCV
   - If start date ≥ today (data is current), skip the fetch for that ticker.
4. `NQ=F` is stored with symbol `NQ`; `^VIX` / `^VVIX` strip the leading `^`.
5. Build multi-row DataFrame with all historical OHLCV rows and return.

**Required columns out:** `symbol VARCHAR, trade_date DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, source VARCHAR`

**Materialization strategy:** `append` (not `create+replace`) — each run adds only new dates.

**Failure message:** `"INGEST_FAILURE: yfinance returned no data for {ticker}"`

**Verify with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/raw/market_data.py
```

---

## Phase 3 — Staging: Data Validation (NEEDS UPDATE)

**Goal**: Validate raw data completeness and guard against division-by-zero before computing metrics.

### `assets/staging/sync_check.py`

Bruin Python asset. Depends on `raw.market_data`. Materializes `staging.validated_data`.

**Current state**: Performs NQ↔QQQ timestamp drift check (10-second threshold). Needs rewrite — drift check is no longer relevant for end-of-day data.

**Updated logic:**
1. Query `raw.market_data` to join all 4 symbols on `trade_date`.
2. For each date, verify that all 4 symbols have data (no missing symbols for a given date).
3. Assert `vix_close > 0` for each date (guard division-by-zero for VVIX/VIX ratio).
   - On failure: write `error_code="BUSINESS_LOGIC_ERROR"` to `mart.pipeline_errors` and log warning. Skip that date but do not crash.
4. Assert `qqq_close > 0` for each date (guard division-by-zero for NQ/QQQ ratio).
   - On failure: same handling as above.
5. Write validated rows to `staging.validated_data` — one row per date with all four symbols' OHLC data joined.

**Output columns:** `trade_date DATE, run_ts TIMESTAMP, nq_open DOUBLE, nq_high DOUBLE, nq_low DOUBLE, nq_close DOUBLE, qqq_open DOUBLE, qqq_high DOUBLE, qqq_low DOUBLE, qqq_close DOUBLE, vix_close DOUBLE, vvix_close DOUBLE`

**Verify with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/staging/sync_check.py
```

---

## Phase 4 — Mart Layer

**Goal**: Calculate and persist final ratios and ADR metrics.

### Task 4.1 — `assets/mart/pipeline_errors.sql`

DDL-only SQL asset. Creates the error table if it doesn't exist.

```sql
/* @bruin
name: mart.pipeline_errors
type: duckdb.sql
materialization:
  type: table
  strategy: create_replace
@bruin */

CREATE TABLE IF NOT EXISTS mart.pipeline_errors (
    id          BIGINT DEFAULT nextval('seq_pipeline_errors'),
    run_ts      TIMESTAMP NOT NULL,
    error_code  VARCHAR   NOT NULL,
    message     VARCHAR   NOT NULL
);
```

### Task 4.2 — `assets/mart/trading_metrics.sql`

SQL asset. Depends on `staging.validated_data`. Materializes `mart.trading_metrics`.

**Key calculations:**
```sql
ROUND(nq_close / qqq_close, 4)    AS nq_qqq_ratio,
ROUND(vvix_close / vix_close, 4)  AS vvix_vix_ratio,
ROUND(nq_high - nq_low, 4)        AS adr_nq,
ROUND(qqq_high - qqq_low, 4)      AS adr_qqq
```

**Output columns:** `trade_date`, `nq_qqq_ratio`, `vvix_vix_ratio`, `adr_nq`, `adr_qqq`, `nq_close`, `qqq_close`, `nq_high`, `nq_low`, `qqq_high`, `qqq_low`, `vix_close`, `vvix_close`

**Verify both with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/mart/pipeline_errors.sql
bruin run pipelines/trading_pipeline/assets/mart/trading_metrics.sql
```

---

## Phase 5 — Tests

**Goal**: Regression coverage for validation and calculation logic. Run with `pytest tests/`.

### `tests/test_data_validation.py`
| Test | What it checks |
|---|---|
| `test_all_symbols_present_passes` | 4 symbols for a date → no error |
| `test_missing_symbol_skips_date` | Only 3 symbols for a date → date excluded, warning logged |
| `test_zero_vix_logs_warning_and_skips` | VIX = 0 → warning logged, date skipped, no crash |
| `test_zero_qqq_logs_warning_and_skips` | QQQ = 0 → warning logged, date skipped, no crash |

### `tests/test_transform.py`
| Test | What it checks |
|---|---|
| `test_nq_qqq_ratio_precision_4dp` | Ratio rounded to exactly 4 decimal places |
| `test_vvix_vix_ratio_precision_4dp` | Ratio rounded to exactly 4 decimal places |
| `test_adr_calculation` | ADR = High − Low for both QQQ and NQ |

### `tests/test_calculator.py`
| Test | What it checks |
|---|---|
| `test_parse_input_string` | Comma-separated key-value pairs are parsed correctly |
| `test_conversion_formula` | QQQ level × ratio = NQ level |
| `test_output_format` | Output string matches expected comma-separated format |
| `test_rounding` | Whole numbers stay whole, decimals round to 2 places |

---

## Phase 6 — Visualization & UI

**Goal**: Streamlit dashboard that reads from `mart.trading_metrics` and provides visualizations and a level calculator.

### `app/dashboard.py`

Single-page Streamlit app. Reads all rows from `mart.trading_metrics` on load.

#### Section 1 — VVIX/VIX Ratio Trend

- **Time-series line chart** of `vvix_vix_ratio` over time (from 2026-01-01 onward).
- X-axis: `trade_date`. Y-axis: ratio value.
- Use Plotly for interactive hover/zoom or Streamlit's built-in `st.line_chart`.
- Display the latest ratio value as a `st.metric` with delta from prior day.

#### Section 2 — ADR + VVIX/VIX Overlay

- **Dual-axis or multi-panel chart** showing:
  - `adr_qqq` (QQQ Average Daily Range) over time
  - `adr_nq` (NQ Average Daily Range) over time
  - `vvix_vix_ratio` over time (on secondary axis)
- Purpose: visual correlation analysis to evaluate whether the VVIX/VIX ratio has predictive value for daily ranges.
- Use Plotly `make_subplots` with shared x-axis and secondary y-axis for the ratio.

#### Section 3 — NQ/QQQ Ratio & Level Calculator

- Display the latest `nq_qqq_ratio` as a `st.metric`.
- **Text area input**: user pastes QQQ levels in comma-separated key-value format:
  ```
  Call Resistance, 630, Put Support, 560, HVL, 600, 1D Min, 548.33, 1D Max, 568.23, Call Resistance 0DTE, 567, Put Support 0DTE, 560, HVL 0DTE, 590
  ```
- **Parsing logic**:
  1. Split input by commas → flat list of tokens.
  2. Iterate pairwise: odd-index tokens are labels, even-index tokens are numeric values.
  3. For each value: `nq_value = float(qqq_value) * nq_qqq_ratio`.
  4. Round: if result is a whole number, display as integer; otherwise round to 2 decimal places.
- **Output**: reconstructed comma-separated string with NQ-equivalent values:
  ```
  Call Resistance, 24750, Put Support, 23000, HVL, 23325, 1D Min, 22733.79, 1D Max, 23545.71, Call Resistance 0DTE, 23600, Put Support 0DTE, 22500, HVL 0DTE, 23050
  ```
- **Copy button**: renders the output in a `st.code` block and provides a **copy-to-clipboard** button (use `st.components.v1.html` with a small JS snippet, or `streamlit-copy-to-clipboard` package).
- Input validation: `st.error` if a value token cannot be parsed as a number.

#### Run the UI

```bash
streamlit run app/dashboard.py
```

#### Notes
- Connect directly to `data/trading.duckdb` (read-only)
- If `mart.trading_metrics` is empty, show a friendly message prompting the user to run the pipeline first
- Charts should be responsive and interactive (Plotly recommended)

---

## Full Pipeline Run

```bash
# Validate all assets
bruin validate pipelines/trading_pipeline

# Run full pipeline (backfills from 2026-01-01 on first run)
bruin run pipelines/trading_pipeline

# Check results
duckdb data/trading.duckdb "SELECT * FROM mart.trading_metrics ORDER BY trade_date DESC LIMIT 5;"

# Check errors (if any)
duckdb data/trading.duckdb "SELECT * FROM mart.pipeline_errors ORDER BY run_ts DESC LIMIT 10;"

# Launch UI
streamlit run app/dashboard.py
```

---

## Edge Cases & Notes

1. **Weekends & holidays**: yfinance only returns data for trading days. The backfill will naturally skip non-trading days.
2. **Incremental fetch**: On subsequent runs, the pipeline queries the latest `trade_date` in `raw.market_data` and fetches only newer dates. If fully up-to-date, the raw layer is a no-op.
3. **Materialization strategy**: `raw.market_data` uses `append` to accumulate historical data. `staging` and `mart` tables use `create+replace` to recompute from the full raw dataset each run.
4. **`trading.duckdb` in `.gitignore`**: The database is generated at runtime — do not commit it.
5. **VIX/VVIX = 0 or missing**: Dates with zero or missing values are excluded from `staging.validated_data` with a warning logged to `mart.pipeline_errors`. No crash.
6. **NQ/QQQ ratio stability**: The calculator uses the latest daily close ratio. This is acceptable for converting option levels since the ratio is relatively stable intraday.
7. **Clipboard on Linux**: The copy-to-clipboard feature uses a JavaScript snippet embedded in Streamlit, so it works in any browser regardless of OS.