# HC-FALCON v2: Problem Statement & Scientific Motivation

## 1. Context and the Frozen v0.1.1 Baseline

The HC-FALCON project investigated whether combining semantic facility-location diversity with failure history and execution cost could improve Test Case Prioritization (TCP) in Continuous Integration (CI). Across 11 stages of rigorous empirical evaluation, the following scientific facts were firmly established and frozen at version `v0.1.1`:

1. **Defects4J Fidelity Established**: On method-level benchmark suites with uniform execution costs (Defects4J 6 projects, 20,770 methods, 288 faults), the FALCON submodular semantic TCP core was replicated with 100% fidelity (author APFD 0.7223 vs rerun APFD 0.7260, $\Delta = +0.0037$).
2. **LRTS Pilot Negative Results (Stages 6, 8, 11)**: On realistic Long-Running Test Suites (LRTS) evaluated at the Java class level with highly dispersed execution costs across 596 build stages and 519 physical builds (Karaf, ActiveMQ, Log4j2), semantic augmentation failed to surpass the strong `history_cost` baseline:
   - **Stage 6 (`hc_falcon_normalized_v1`)**: Unrestricted greedy combination with $\alpha = 0.5$ lost to `history_cost` on paired median APFDc by $-1.27\%$ (Karaf), $-1.41\%$ (ActiveMQ), and $-0.12\%$ (Log4j) $\rightarrow$ **0/3 NO-GO**.
   - **Stage 8 (`restricted_v1`)**: Restricting the semantic search space to a 5% historical confidence band ($q \ge 0.95 q_{head}$) mitigated severe losses but choked semantic reordering space, remaining negative ($-0.02\%$ to $-0.15\%$) $\rightarrow$ **0/3 NO-GO**.
   - **Stage 11 (`hc_cns_v1`)**: Cost-Normalized Semantic Greedy (CNS-Greedy) discounted marginal semantic gain by $\sqrt{\text{cost}}$, reducing damage by ~60% and turning mean deltas positive (+1.7% to +3.5%), but **median paired $\Delta\text{APFDc}$ remained stubbornly negative** ($-0.40\%$ Karaf, $-0.61\%$ ActiveMQ, $-0.19\%$ Log4j) $\rightarrow$ **0/3 NO-GO**.

All 10 experimental freeze manifests from Stages 5–11 and the entire v0.1.1 codebase remain frozen and unedited.

---

## 2. Why HC-FALCON v2 is a Distinct New Research Phase

Rather than continuing post-hoc iterative tuning on the Development dataset—which would violate scientific fidelity and constitute $p$-hacking—HC-FALCON v2 is formally launched as a distinct, preregistered research phase:

- **Clean Scientific Demarcation**: All design choices, parameters, formulas, and gates are preregistered before running any Stage 12 evaluations.
- **Single Primary Candidate**: Exactly one primary candidate method, `hc_ugcs_v2` (Uncertainty-Guarded Cost-aware Semantic ranking), is admitted. No hyperparameter grids, sweeps, or multi-candidate tournaments are permitted.
- **Strict Boundary Integrity**: Release `v0.1.1` remains intact and unmodified as the direct ancestor.

---

## 3. Why Cold-Start-Only is Not the Sole Primary Hypothesis

One natural conjecture following negative class-level LRTS results was to restrict semantic prioritization strictly to "cold-start" test cases (newly added tests where observation count $N = 0$). However, empirical forensic evidence from Stage 11 (analyzing 161 failure-containing physical builds) conclusively demonstrated that cold-start-only cannot be the sole primary candidate:

- **Data Sparsity for $N=0$**: Across all 161 failure builds, only 8 failure observations involved tests with $N = 0$ (5 in wins, 3 in losses). In real CI suites, truly new classes that immediately fail represent less than 3% of failure events. A technique activating only on $N = 0$ would leave over 97% of CI builds entirely untouched.
- **Semantic Diversity Creates Value Beyond Cold-Start**: In the 38 builds where semantic prioritization outperformed `history_cost` by large margins (median win margin $+3.55\%$ in Karaf, $+10.52\%$ in Log4j), **54 out of 62 benefited failure observations had $N \ge 5$ observations**. When semantic signals succeed, they do so by promoting relevant, historically noisy or moderately ranked tests past irrelevant tests that happen to have similar history scores.
- **Statistical Indistinguishability Hypothesis**: Semantic diversity is beneficial not only when $N = 0$, but whenever the historical risk signal between candidates is *statistically indistinguishable* (uncertainty overlap).

---

## 4. The Causal Mechanism: "Heavy Predecessors"

The primary failure mode identified in Stage 11 forensics was the **Heavy Predecessors** effect:

1. **Dimensional Mismatch in Greedy Selection**:
   In Stage 6, the historical score $q_b(t)$ was divided by $\sqrt{\tilde{c}_b(t)}$, but the facility location marginal gain $\Delta FL(t \mid S) / n$ was entirely cost-agnostic.
2. **Greedy Traps**:
   A test class requiring 100–150 seconds to run (e.g., `MemoryUsageConcurrencyTest` in ActiveMQ) had the same marginal coverage potential as a 0.001-second test. At early greedy steps, the semantic gain dominated total marginal gain (97%–99%), causing the algorithm to select massive, non-failing test classes early merely to cover peripheral semantic clusters.
3. **Severe Cumulative Delay**:
   Placing a 150-second non-failing class early delays every subsequent failing test by 150 seconds, accumulating a net delay of **+39,099.3 seconds (~10.8 hours)** across the 161 failure builds.
4. **Why CNS-Greedy Was Insufficient**:
   While `hc_cns_v1` introduced cost normalization into the semantic gain ($\Delta FL / \sqrt{\tilde{c}}$), it still allowed semantic utility to pull tests forward that were historically known to be safe or irrelevant ahead of well-established high-risk anchors, causing median deltas to remain negative.

---

## 5. Development Data as a Screening Cohort Only

To prevent data snooping:
- The 596 build stages across Karaf, ActiveMQ, and Log4j on the Development split are treated strictly as a **screening cohort**.
- A positive result on Development is a necessary filter, not a confirmation of generalizability.
- The **Reserved Confirmation Dataset** (the final 50% of builds for ActiveMQ and Log4j) remains **100% unopened and sealed**.
- Reserved data will only ever be opened if `hc_ugcs_v2` strictly passes the preregistered Effect Gate and Engineering Gates on the Development screening cohort, under explicit human authorization.
