# Implementation Plan: Pre-RTH Trading Pipeline

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage | DuckDB (`data/trading.duckdb`) | Local, zero-config, no credentials |
| NQ source | yfinance daily close (`NQ=F`) | No broker file dependency |
| QQQ data | yfinance daily close | Previous session close, consistent with NQ |
| VIX/VVIX data | yfinance daily OHLC | No intraday available on yfinance |
| Sync check | NQ ↔ QQQ timestamp drift (both yfinance daily) | Guards against stale data |
| Trigger | Manual via Bruin CLI / VS Code extension | Run morning before RTH open |
| UI | Streamlit | Simple, Python-native, no separate frontend |

## DAG Structure

```
raw.market_data ──▶ staging.sync_validated ──▶ mart.trading_metrics
                              │
                              └──▶ mart.pipeline_errors (on failure)
```

## File Structure

```
.bruin.yml                                      # DuckDB connection config
requirements.txt                                # yfinance, pandas, duckdb, pytest, streamlit
pipelines/trading_pipeline/
    pipeline.yml                                # Pipeline name, @manual schedule
    assets/
        raw/
            market_data.py                      # yfinance daily fetch (QQQ, NQ=F, VIX, VVIX)
        staging/
            sync_check.py                       # timestamp drift check + error writing
        mart/
            pipeline_errors.sql                 # Error table DDL
            trading_metrics.sql                 # Final ratios table
app/
    dashboard.py                                # Streamlit UI
tests/
    test_sync_validation.py
    test_transform.py
data/
    trading.duckdb                              # Generated at runtime
```

## DuckDB Tables

| Table | Layer | Key Columns |
|---|---|---|
| `raw.market_data` | raw | `symbol`, `trade_date`, `timestamp_utc`, `close`, `source` |
| `staging.sync_validated` | staging | `nq_symbol`, `nq_timestamp_utc`, `nq_close`, `qqq_timestamp_utc`, `qqq_close`, `qqq_drift_seconds`, `vix_close`, `vvix_close` |
| `mart.pipeline_errors` | mart | `id`, `run_ts`, `error_code`, `message` |
| `mart.trading_metrics` | mart | `trade_date`, `run_ts`, `nq_qqq_ratio`, `vvix_vix_ratio`, `qqq_drift_seconds`, raw closes |

---

## Phase 1 — Foundation ✅ DONE

**Goal**: Scaffold the project so Bruin can discover and validate the pipeline.

- [x] `.bruin.yml` — DuckDB connection `duckdb_default` → `data/trading.duckdb`
- [x] `pipelines/trading_pipeline/pipeline.yml` — `@manual` schedule, default connection `duckdb_default`
- [x] `requirements.txt` — `yfinance`, `pandas`, `duckdb`, `pytest`, `streamlit`
- [x] Folder structure: `assets/raw/`, `assets/staging/`, `assets/mart/`, `tests/`, `app/`

**Verify with CLI:**
```bash
bruin validate pipelines/trading_pipeline
```

---

## Phase 2 — Raw Layer ✅ DONE

**Goal**: Pull previous session closes for QQQ, NQ=F, VIX, VVIX from yfinance.

### `assets/raw/market_data.py`

Bruin Python asset. No upstream dependencies. Materializes `raw.market_data`.

**Logic:**
1. For each ticker (`QQQ`, `NQ=F`, `^VIX`, `^VVIX`): `yf.download(ticker, period="5d", interval="1d")` → take `Close` of the last available bar
2. `NQ=F` ticker is stored with symbol `NQ`
3. `^VIX` / `^VVIX` strip the leading `^` for the symbol field
4. Build 4-row DataFrame and return

**Required columns out:** `symbol VARCHAR, trade_date DATE, timestamp_utc TIMESTAMP, close DOUBLE, source VARCHAR`

**Failure message:** `"INGEST_FAILURE: yfinance returned no data for {ticker}"`

**Verify with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/raw/market_data.py
```

---

## Phase 3 — Staging: Sync Validation ✅ DONE

**Goal**: Guard against stale data and division-by-zero before computing ratios.

### `assets/staging/sync_check.py`

Bruin Python asset. Depends on `raw.market_data`. Materializes `staging.sync_validated`.

**Logic:**
1. Query `raw.market_data` for all 4 symbols
2. Compute `qqq_drift_seconds = abs((qqq_timestamp_utc - nq_timestamp_utc).total_seconds())`
3. If `qqq_drift_seconds > 10`:
   - Write to `mart.pipeline_errors`: `error_code="SYNC_FAILURE"`, descriptive message with actual drift value
   - `raise RuntimeError("SYNC_FAILURE: QQQ/NQ drift {n}s exceeds 10s threshold")`
4. Assert `vix_close > 0` and `vvix_close > 0` (guard division-by-zero)
   - On failure: write `error_code="BUSINESS_LOGIC_ERROR"` to `mart.pipeline_errors` and raise
5. Write joined + validated row to `staging.sync_validated`

**Output columns:** `trade_date`, `run_ts`, `nq_symbol`, `nq_timestamp_utc`, `nq_close`, `qqq_timestamp_utc`, `qqq_close`, `qqq_drift_seconds`, `vix_close`, `vvix_close`

**Verify with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/staging/sync_check.py
```

---

## Phase 4 — Mart Layer

**Goal**: Persist the error table and calculate final ratios.

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

> Note: Bruin's `create_replace` DDL strategy — check Bruin docs for exact YAML frontmatter syntax for your version.

### Task 4.2 — `assets/mart/trading_metrics.sql`

SQL asset. Depends on `staging.sync_validated`. Materializes `mart.trading_metrics`.

**Key calculations:**
```sql
ROUND(nq_last_price / qqq_close, 4)   AS nq_qqq_ratio,
ROUND(vvix_close / vix_close, 4)       AS vvix_vix_ratio
```

**Verify both with CLI:**
```bash
bruin run pipelines/trading_pipeline/assets/mart/pipeline_errors.sql
bruin run pipelines/trading_pipeline/assets/mart/trading_metrics.sql
```

---

## Phase 5 — Tests

**Goal**: Regression coverage for all failure modes. Run with `pytest tests/`.

### `tests/test_sync_validation.py`
| Test | What it checks |
|---|---|
| `test_drift_within_threshold_passes` | 8-second drift → no exception, row written |
| `test_drift_over_threshold_raises_and_writes_error` | 15-second drift → `RuntimeError` with `SYNC_FAILURE`, error row written |
| `test_zero_vix_raises_business_error` | VIX = 0 → `RuntimeError` with `BUSINESS_LOGIC_ERROR` |
| `test_zero_vvix_raises_business_error` | VVIX = 0 → `RuntimeError` with `BUSINESS_LOGIC_ERROR` |

### `tests/test_transform.py`
| Test | What it checks |
|---|---|
| `test_ratio_precision_4dp` | Both ratios rounded to exactly 4 decimal places |
| `test_schema_change_detected` | Removing a required column from input raises before load |

---

## Phase 6 — Visualization & UI

**Goal**: Streamlit dashboard that reads from `mart.trading_metrics` and provides pre-market decision support.

### `app/dashboard.py`

Single-page Streamlit app. Reads the latest row from `mart.trading_metrics` on load.

#### Section 1 — VVIX/VIX Ratio

Displays the ratio and a pre-defined signal message based on its value:

| Condition | Message |
|---|---|
| ratio < 5 | Low volatility of volatility — conditions are calm |
| 5 ≤ ratio ≤ 6 | Elevated vol-of-vol — proceed with caution |
| ratio > 6 | High vol-of-vol — risk-off, expect erratic moves |

Render with a colored badge or `st.metric` + `st.info / st.warning / st.error` matching the condition.

#### Section 2 — NQ/QQQ Ratio & Level Calculator

- Display the current `nq_qqq_ratio` as a metric
- Text area input: user pastes a block of QQQ price levels (one per line or comma-separated)
- On submit: multiply each QQQ level by `nq_qqq_ratio` → display NQ equivalent levels
- **Copy button**: copies the NQ levels to clipboard (use `st.code` block + `st.button("Copy")` with `pyperclip` or `streamlit-copy-to-clipboard`)

#### Run the UI

```bash
streamlit run app/dashboard.py
```

#### Notes
- Connect directly to `data/trading.duckdb` (read-only)
- If `mart.trading_metrics` is empty, show a friendly message prompting the user to run the pipeline first
- Input parsing: strip whitespace, skip blank lines, raise a visible `st.error` if a non-numeric value is pasted

---

## Full Pipeline Run

```bash
# Validate all assets
bruin validate pipelines/trading_pipeline

# Run full pipeline
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

1. **VIX/VVIX on Mondays**: `period="5d"` ensures data is available after weekends and holidays.
2. **Drift check**: Since QQQ and NQ=F are both yfinance daily bars, drift should always be 0. The check guards against unexpected data shape issues.
3. **Idempotency**: `market_data` uses `materialization.strategy: create+replace` so re-running for the same day overwrites rather than appends.
4. **`trading.duckdb` in `.gitignore`**: The database is generated at runtime — do not commit it.
5. **UI clipboard**: `pyperclip` requires `xclip` / `xsel` on Linux; works natively on Windows and macOS.