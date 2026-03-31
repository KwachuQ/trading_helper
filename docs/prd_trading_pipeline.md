# Product Requirements Document (PRD): Trading Analysis Pipeline

## 1. Overview & Purpose
The purpose of this product is to build a daily ETL pipeline that fetches **end-of-day** quotes for **QQQ, NQ (NQ=F), VIX (^VIX), and VVIX (^VVIX)** from **yfinance**, stores them in a local DuckDB database, and provides analytical views and tooling for pre-market analysis. The pipeline includes trend visualizations for the VVIX/VIX ratio, ADR (Average Daily Range) analysis, and an interactive calculator for converting QQQ option levels to NQ levels.

---

## 2. Problem Statement
Traders need a consolidated view of volatility regime and price-range data to prepare for each trading session. Manually gathering end-of-day quotes, computing ratios, and translating QQQ-based option levels into NQ futures levels is tedious and error-prone. There is currently no single tool that:
1. Automatically fetches and stores historical end-of-day data for QQQ, NQ, VIX, and VVIX.
2. Visualizes the VVIX/VIX ratio trend to identify volatility regime shifts.
3. Computes and visualizes ADR for QQQ and NQ alongside the VVIX/VIX ratio to assess its predictive value.
4. Provides a quick calculator to convert QQQ option levels to NQ levels using the live NQ/QQQ ratio.

---

## 3. Target Users & Personas
* **The Quantitative Trader**: Needs daily volatility-regime and range metrics to form trading biases before the open. Uses the VVIX/VIX ratio as a regime filter and ADR to gauge expected move.
* **The Options-to-Futures Translator**: Receives QQQ-based option levels (support, resistance, HVL, etc.) and needs to quickly convert them to equivalent NQ futures levels.

---

## 4. Goals & Success Metrics
* **Goal: Historical Coverage**: Fetch and store end-of-day quotes for all four symbols from **January 1, 2026** onward.
* **Goal: Analytical Insight**: Provide clear visualizations of VVIX/VIX ratio trend and ADR to help traders assess predictive relationships.
* **Goal: Operational Efficiency**: The level calculator must accept a pasted QQQ string and return NQ-converted results instantly, with a copy-to-clipboard button.
* **Success Metric**: Complete daily data for all four symbols with no gaps in the date range.
* **Success Metric**: Ratio and ADR calculations accurate to at least **4 decimal places**.

---

## 5. Scope
* **In Scope**:
    * End-of-day data ingestion for **QQQ, NQ=F, ^VIX, ^VVIX** via **yfinance**.
    * Historical backfill from **2026-01-01** to the current date.
    * Incremental daily fetches for new trading days.
    * Calculation and storage of `vvix_vix_ratio` and `nq_qqq_ratio`.
    * Calculation of **ADR (Average Daily Range)** for QQQ and NQ, derived from the daily High and Low (either via yfinance technical indicator helpers or computed as `High - Low`).
    * **Visualization**: Trend chart of the VVIX/VIX ratio over time.
    * **Visualization**: ADR chart for QQQ and NQ plotted alongside the VVIX/VIX ratio to evaluate predictive value.
    * **Level Calculator**: An in-place tool that converts QQQ option levels to NQ levels using the current NQ/QQQ ratio.
* **Out of Scope**:
    * Intraday or real-time streaming data.
    * Manual data exports from external charting platforms.
    * Sub-second timestamp synchronization between symbols.

---

## 6. Key Features (MoSCoW)
| Priority | Feature | User Story |
| :--- | :--- | :--- |
| **Must** | **End-of-Day Data Fetch** | As a trader, I want the pipeline to fetch daily closing data for QQQ, NQ, VIX, and VVIX from yfinance so I have a reliable, automated data source. |
| **Must** | **Historical Backfill** | As a trader, I want data going back to 2026-01-01 so I can analyze trends from the beginning of the year. |
| **Must** | **VVIX/VIX Ratio Visualization** | As a trader, I want to see a trend chart of the VVIX/VIX ratio so I can identify volatility regime shifts over time. |
| **Must** | **ADR Calculation** | As a trader, I want the Average Daily Range (ADR) of QQQ and NQ computed from the daily High and Low so I can gauge expected price movement. |
| **Must** | **ADR + VVIX/VIX Visualization** | As a trader, I want to see ADR plotted alongside the VVIX/VIX ratio so I can evaluate whether the ratio has predictive value for daily ranges. |
| **Must** | **QQQ-to-NQ Level Calculator** | As a trader, I want to paste QQQ option levels and instantly get NQ-equivalent levels so I can use them in my futures trading. |
| **Should** | **Copy-to-Clipboard** | As a trader, I want a copy button on the calculator output so I can quickly transfer the NQ levels to my platform. |
| **Should** | **Incremental Fetch** | As a trader, I want the pipeline to only fetch missing days on subsequent runs so it is fast and avoids redundant API calls. |

---

## 7. Acceptance Criteria

### 7.1 Data Ingestion
* The pipeline fetches end-of-day OHLCV data for QQQ, NQ=F, ^VIX, and ^VVIX from yfinance.
* On first run, it backfills all trading days from **2026-01-01** to the current date.
* On subsequent runs, it fetches only the days not yet present in the database.
* All records are stored in DuckDB with date, symbol, open, high, low, close, and volume columns.

### 7.2 Ratio & ADR Calculations
* `vvix_vix_ratio` = VVIX close / VIX close (to at least 4 decimal places).
* `nq_qqq_ratio` = NQ close / QQQ close (to at least 4 decimal places).
* `adr_qqq` = QQQ High − QQQ Low for each trading day.
* `adr_nq` = NQ High − NQ Low for each trading day.
* Division-by-zero cases (e.g., VIX = 0) must be handled gracefully with a logged warning, not a crash.

### 7.3 Visualizations
* **VVIX/VIX Ratio Trend**: A time-series line chart showing the daily VVIX/VIX ratio from 2026-01-01 onward.
* **ADR + VVIX/VIX Overlay**: A dual-axis or multi-panel chart showing QQQ ADR, NQ ADR, and VVIX/VIX ratio on the same time axis, allowing visual correlation analysis.

### 7.4 QQQ-to-NQ Level Calculator
* **Input format** (comma-separated key-value pairs pasted by the user):
  ```
  Call Resistance, 630, Put Support, 560, HVL, 600, 1D Min, 548.33, 1D Max, 568.23, Call Resistance 0DTE, 567, Put Support 0DTE, 560, HVL 0DTE, 590
  ```
* **Conversion formula**: `NQ level = QQQ level × nq_qqq_ratio` (using the latest available daily ratio).
* **Output format** (same structure, with NQ-equivalent values):
  ```
  Call Resistance, 24750, Put Support, 23000, HVL, 23325, 1D Min, 22733.79, 1D Max, 23545.71, Call Resistance 0DTE, 23600, Put Support 0DTE, 22500, HVL 0DTE, 23050
  ```
* Output values should be rounded to 2 decimal places (or whole numbers where the result is exact).
* A **copy button** must be provided so the user can copy the full output string to the clipboard with one click.

---

## 8. Non-functional Requirements
* **Reliability**: The system must handle yfinance API failures gracefully (retry logic, clear error messages). Division-by-zero and missing-data scenarios must produce logged warnings, not crashes.
* **Performance**: The full backfill (2026-01-01 to present) should complete within a reasonable timeframe. Daily incremental runs should complete in under 30 seconds.
* **Maintainability**: All transformation and calculation logic must be unit-tested. Visualization code should be decoupled from data fetching.
* **Portability**: The pipeline runs locally with Python, yfinance, and DuckDB. No cloud infrastructure required.

---

## 9. Assumptions, Constraints & Dependencies
* **Assumption**: End-of-day data from yfinance is sufficiently accurate for the analysis (no need for sub-second precision).
* **Assumption**: The NQ/QQQ ratio is relatively stable within a trading day, making the latest daily close ratio suitable for level conversion.
* **Constraint**: yfinance is the sole data source; availability and rate limits of the Yahoo Finance API apply.
* **Dependency**: `yfinance` Python package for data retrieval.
* **Dependency**: `duckdb` for local data storage.
* **Dependency**: A charting library (e.g., Plotly, Matplotlib) for visualizations.
* **Dependency**: A UI framework or HTML/JS component for the copy-to-clipboard calculator feature.