# HC-FALCON v2: Preregistered Evaluation Protocol

## 1. Candidate Preregistration

- **Primary Candidate**: Exactly one method is registered:
  $$\text{hc\_ugcs\_v2}$$
  *(Uncertainty-Guarded Cost-aware Semantic ranking)*
- **Fixed Hyperparameters**:
  - $\text{semantic\_weight} = 0.25$
  - $z = 1.96$
  - $\text{cost\_floor} = 10^{-6}$
  - $\epsilon = 10^{-8}$
  - $\text{gain\_tolerance} = 10^{-12}$
- **Prohibition on Post-Hoc Tuning**:
  No parameter sweeps, grid searches, or sensitivity-driven candidate selections are permitted on the Development dataset. Any post-hoc adjustment invalidates the preregistered status.

---

## 2. Evaluation Cohort and Data Boundary

- **Screening Dataset & Exact Project Set**:
  The evaluation is conducted on the 596 development build stages across exactly three Apache Java projects:
  - `karaf` (exploratory split, 149 stages, 79 failure-containing physical builds)
  - `activemq` (development split, 224 stages, 57 failure-containing physical builds)
  - `log4j` (development split, 223 stages, 25 failure-containing physical builds)
  Total: 161 failure-containing physical builds across exactly these 3 projects.
  - **Exact Project Set Enforcement & Single Source of Truth**:
    The development evaluation requires exactly this set of three projects, defined strictly at the top level of `configs/hc-falcon-v2-preregistered.json` as the single source of truth (no redundant copies in sub-sections). Any missing project report, extra project report, project name mismatch, or mismatch with preregistered `development_projects` fails closed immediately with a `NO-GO` decision.
- **Fail-Closed Preregistered Configuration Schema**:
  All configuration fields, fixed constants, gate thresholds, runtime protocol parameters, and governance settings are validated fail-closed without any hardcoded fallback defaults. Missing, malformed, or tampered configuration fields strictly prohibit a `GO` decision.
- **Frozen Embeddings**:
  Embeddings are loaded read-only from the frozen Stage 6 UniXcoder cache (`work/cache/stage6/vectors/`).
- **Reserved Confirmation Dataset Sealed**:
  The confirmation splits of ActiveMQ and Log4j2 remain **strictly sealed** (`reserved_opened: false`).
- **Path and Manifest Safety Boundary**:
  Manifest verification enforces strict path hygiene: absolute paths, directory traversal (`..`), or paths outside the exact preregistration allowlist are rejected immediately prior to any disk existence check or hash calculation. Unsafe paths are never accessed.

---

## 3. Statistical Unit and Metric Definitions

### 3.1. Statistical Aggregation Unit
In accordance with Stage 6 and Stage 11 protocols:
1. Stage-level evaluations compute the cost-cognizant failure discovery metric:
   $$\text{APFDc}_{\text{midpoint}} = 1 - \frac{\sum_{i=1}^m (\text{start}_i + \text{cost}_i / 2)}{m \cdot T_{\text{total}}}$$
2. Stages belonging to the same physical build (sharing project, PR, and build ID) are averaged:
   $$\text{APFDc}(B) = \frac{1}{|S_B|} \sum_{s \in S_B} \text{APFDc}(s)$$
3. Paired delta for physical build $B$:
   $$\Delta \text{APFDc}(B) = \text{APFDc}_{\text{hc\_ugcs\_v2}}(B) - \text{APFDc}_{\text{comparator}}(B)$$

### 3.2. Primary Decision Metric
$$\text{Median Paired } \Delta\text{APFDc}_{\text{midpoint}}$$

### 3.3. Comparators
1. `history_cost`: Strong cost-penalized historical failure rate baseline.
2. `fl_only`: FALCON facility-location semantic baseline without historical or cost awareness.

---

## 4. Preregistered Decision Gates

### 4.1. Pilot Effect Gate
To achieve a **GO** decision on the development screening cohort:
$$\text{Median Paired } \Delta\text{APFDc} \ge +0.0300 \quad (+3.0 \text{ percentage points})$$
against **BOTH** `history_cost` and `fl_only` on **at least 2 out of 3** development projects ($\ge 66.7\%$).

### 4.2. Engineering Feasibility Gates
1. **P95 Warm Runtime Overhead**:
   $$\text{Overhead}_{p95} \le 10\% \quad (0.10)$$
   relative to the baseline `history_cost` ranking latency on warm cache.
   - **Warm-cache Measurement Protocol**:
     - Measured per scored stage under warm-cache conditions (all embeddings pre-loaded).
     - Warm-up runs: 1 warm-up execution of both `history_cost` and `hc_ugcs_v2` prior to measurement.
     - Repetitions: 3 timed repetitions using high-resolution monotonic timer (`time.perf_counter`), taking the median elapsed duration for each method ($T_{\text{ugcs}}$, $T_{\text{hc}}$).
     - Stage overhead fraction:
       $$\text{Overhead}_{\text{stage}} = \frac{T_{\text{ugcs}} - T_{\text{hc}}}{\max(T_{\text{hc}}, 10^{-9})}$$
     - Aggregate metric: 95th percentile ($\text{P95}$) across all scored development stages must satisfy $\text{Overhead}_{p95} \le 0.10$.
2. **Peak Memory Footprint**:
   $$\text{Peak RSS} \le 8.0 \text{ GiB} \quad (8,589,934,592 \text{ bytes})$$
   measured across the entire evaluation run using process working set / resident set size.
3. **Fail-Closed Metric & Sample Count Completeness**:
   - Every primary and secondary metric must be present, have valid numeric types (booleans strictly rejected), and be strictly finite according to `math.isfinite()`.
   - Secondary metric summaries (`paired_ttff_vs_history_cost` and `paired_recall10_vs_history_cost`) are validated identically to primary APFDc summaries using `validate_delta_summary()`: must be a dictionary, require strictly positive integer `count` (`> 0`), finite `mean`, finite `median`, non-negative integer win/tie/loss counts (`pos`, `tie`, `neg`), and exact conservation $\text{pos} + \text{tie} + \text{neg} == \text{count}$.
   - Sample counts (`count`, `physical_builds`, `stages`, `scored_stages_total`) must be strictly positive integers (`> 0`).
   - Runtime latencies and peak RSS bytes must be strictly positive finite numbers (`> 0`).
   - If any required metric is missing, non-finite ($\text{NaN}, \pm\infty$), non-positive when required, or has mismatched sample counts, the completeness check fails closed, engineering gates fail, and a `GO` decision is strictly prohibited.

---

## 5. Secondary Descriptive Metrics (Non-Selection)

The following metrics are collected strictly for diagnostic characterization and cannot be used to overturn the primary effect gate:
- **Mean Paired $\Delta\text{APFDc}$**
- **Win / Tie / Loss Counts** (positive delta $> 10^{-12}$, tie within $\pm 10^{-12}$, negative delta $< -10^{-12}$)
- **Time to First Failure (TTFF)**
- **Recall @ 10% Execution Cost Budget**
- **Cumulative Predecessor Delay Seconds** ($\sum \Delta \text{predecessor\_seconds}$)
- **Runtime Latency & Peak RSS**

---

## 6. Strict Stop / Go Decision Rules

1. **GO (Screening Passed)**:
   - Exactly the 3 preregistered development projects (`karaf`, `activemq`, `log4j`) are reported (no missing, no extra, no substitutions);
   - Median paired $\Delta\text{APFDc} \ge +0.0300$ vs both `history_cost` and `fl_only` on $\ge 2/3$ projects;
   - All engineering gates pass (P95 warm overhead $\le 0.10$, Peak RSS $\le 8\text{ GiB}$);
   - All mandatory metrics (primary and secondary) are valid, finite, and have valid sample counts;
   - Zero audit errors recorded;
   - Code and manifest verification passes cleanly.
   $\rightarrow$ Authorize drafting of the Confirmation Preregistration Protocol for human approval.
2. **NO-GO (Screening Failed)**:
   - Any failure to reach $+0.0300$ on $\ge 2/3$ projects;
   - Any missing, extra, or substituted project report;
   - Any engineering gate failure (overhead $> 0.10$ or peak RSS $> 8\text{ GiB}$);
   - Any missing, null, or non-finite metric ($\text{NaN}, \pm\infty$), count $= 0$, or $\text{pos} + \text{tie} + \text{neg} \ne \text{count}$.
   $\rightarrow$ Terminate with negative result documented. Reserved Confirmation data remains permanently unopened. Zero parameter tuning rounds allowed.
