# Product Requirements Document (PRD): Pre-RTH Inter-market Relationship Pipeline

## 1. Overview & Purpose
The purpose of this product is to build a "change-safe" daily ETL pipeline that calculates normalized volatility and price ratios for pre-market analysis. The pipeline runs once per day, anchored by a manual export of **NQM26** data, to generate risk-regime filters before the US Regular Trading Hours (RTH) session begins.

---

## 2. Problem Statement
Traders face significant risk when using non-synchronized market data. Currently, there is no automated way to ensure that futures (NQM26), ETFs (QQQ), and volatility indices (VIX/VVIX) are perfectly aligned in time. Small time skews (over 10 seconds) result in inaccurate ratios, leading to flawed trading biases and "silent failures" in data integrity.

---

## 3. Target Users & Personas
* **The Quantitative Trader**: Requires a single, synchronized row of data per day to identify price/volatility anomalies before the open.
* **The System Operator**: Needs clear, non-technical error messages to troubleshoot ingestion or synchronization issues before the 9:30 AM ET bell.

---

## 4. Goals & Success Metrics
* **Goal: Temporal Integrity**: Ensure 100% of processed records have all four symbols aligned within a **10-second window**.
* **Goal: Operational Reliability**: The pipeline must act as a "robust appliance" that fails immediately if data is incomplete or out of sync.
* **Success Metric**: **0% partial updates** allowed in the production database.
* **Success Metric**: Pipeline completion time of **under 2 minutes** from the moment of NQM26 file detection.

---

## 5. Scope
* **In Scope**:
    * Ingestion anchored by the **NQM26** master symbol (manual Sierra Chart export).
    * High-speed retrieval of QQQ, VIX, and VVIX to match the NQM26 timestamp.
    * Validation of the 10-second drift threshold across all symbols.
    * Calculation of `vvix_vix_ratio` and `nqm26_qqq_ratio`.
* **Out Scope**:
    * Retention of original raw CSV/TXT strings after parsing (only transformed data is stored).
    * Automated backfilling of historical days.
    * Intraday streaming updates.

---

## 6. Key Features (MoSCoW)
| Priority | Feature | User Story |
| :--- | :--- | :--- |
| **Must** | **Master-Anchor Synchronization** | As a trader, I want the NQM26 timestamp to dictate the search window for all other symbols so my ratios are anchored to current futures prices. |
| **Must** | **10-Second "Kill Switch"** | As a user, I want the pipeline to fail immediately if any symbol is skewed by >10 seconds so I don't act on unaligned data. |
| **Must** | **Atomic Schema Validation** | As an operator, I want the pipeline to reject the daily run if any single required column is missing from any source. |
| **Should** | **Pre-RTH Alerting** | As a trader, I want a clear error message (e.g., `SYNC_FAILURE`) if the alignment check fails before the market opens. |
| **Should** | **`--dry-run` Validation** | As a developer, I want to test the synchronization logic against mock data without writing to the production database. |
| **Won't** | **Raw Data Persistence** | We will not store the original raw text file data to keep the database lean. |

---

## 7. Acceptance Criteria
* **Master Sync Logic**: The pipeline must identify the latest timestamp in the NQM26 export and successfully fetch QQQ, VIX, and VVIX within T ± 10 seconds.
* **Failure Protocol**: If any of the four symbols are missing or outside the 10-second tolerance, the `load.py` module must not execute, and an entry must be made in the `pipeline_errors` table.
* **Ratio Precision**: `nq_qqq_ratio` and `vvix_vix_ratio` must be calculated to at least 4 decimal places.

---

## 8. Non-functional Requirements
* **Reliability**: The system must handle "Division by Zero" (e.g., VIX = 0) by logging a specific business logic error instead of a raw system crash.
* **Performance**: The pipeline must prioritize "as fast as possible" retrieval for QQQ once the NQM26 file is detected to minimize real-world time drift.
* **Maintainability**: All transformation logic must be unit-tested against historical edge cases before any deployment.

---

## 9. Assumptions, Constraints & Dependencies
* **Assumption**: The NQM26 manual export is the trigger; the pipeline depends on the user performing this action daily.
* **Constraint**: The failure is absolute; if synchronization is not achieved within 10 seconds, the system will not write data for that day.
* **Dependency**: Reliable API access for QQQ, VIX, and VVIX that allows for "point-in-time" queries to match the NQM26 timestamp.