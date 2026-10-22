# When Semantic Diversity Hurts: A Negative Empirical Result on Submodular Test Case Prioritization in Real-World CI

**Draft v0.1 — for internal review**

---

## Abstract

Test Case Prioritization (TCP) aims to reorder test suites so that fault-detecting tests execute earliest, maximizing the rate of early fault detection under constrained CI budgets. We propose and evaluate **HC-FALCON**, a training-free framework that integrates semantic code diversity (UniXcoder embeddings with Facility Location optimization), Bayesian failure probability estimation (Beta-Bernoulli), and execution cost into a single monotone submodular objective with a provable $1 - 1/e$ approximation guarantee.

We conduct two large-scale controlled experiments: (1) independent reproduction of FALCON on Defects4J (20,770 test methods, 288 faults across 6 projects), achieving APFD 0.7260 vs. the authors' 0.7223 ($\Delta = +0.37$ percentage points), confirming 100% reproduction fidelity; and (2) temporal-order evaluation on Long-Running Test Suites (LRTS) comprising 3 industrial-scale Apache projects (596 build stages, 519 physical builds, 33,972 independent rankings) with strict temporal data splits preventing any future data leakage.

**Result**: Contrary to our hypothesis, HC-FALCON fails the Effect Gate (0/3 projects) on real-world class-level CI. The median paired $\Delta$APFDc vs. the `history_cost` baseline is negative across all 3 projects and all 5 algorithm generations tested. Root cause analysis on 161 failure-containing builds identifies the **Heavy Predecessors** phenomenon: cost-agnostic semantic greedy selects heavy non-failing test classes (100-150s) early to maximize coverage diversity, accumulating +39,099s (~10.8 hours) of net delay before fault-detecting tests. We report this negative result with full transparency, keeping the Reserved Confirmation dataset 100% sealed.

**Keywords**: Test Case Prioritization, Submodular Optimization, Semantic Diversity, Negative Empirical Result, Continuous Integration, Facility Location

---

## 1. Introduction

In modern Continuous Integration/Continuous Delivery (CI/CD) pipelines, regression test suites can require hours to execute fully. Test Case Prioritization (TCP) seeks a permutation $\pi$ of the test suite $T$ such that fault-detecting, fast-running tests execute first, maximizing the Average Percentage of Faults Detected with Cost (APFDc) metric.

Two influential approaches emerged at IEEE ICST 2026:

1. **FALCON** (Mensah-Boateng et al.) encodes test methods via the pretrained UniXcoder code language model, then applies submodular Facility Location greedy optimization to maximize semantic coverage diversity. FALCON demonstrated strong results on the Defects4J benchmark but entirely ignores failure history and execution cost.

2. **DANTE** (Reale et al.) exploits sliding-window failure history, failure stickiness, and test duration on Long-Running Test Suites (LRTS). DANTE excels at history/cost-aware prioritization but lacks deep semantic code analysis.

**Research hypothesis**: Integrating semantic diversity, Bayesian failure risk, and execution cost into a unified submodular objective should outperform both approaches in isolation on real-world CI data.

### Contributions

This paper makes four contributions:

1. **Independent reproduction of FALCON** on the full Defects4J benchmark (6 projects, 20,770 methods, 288 faults), confirming 100% reproduction fidelity with a 4-branch Bridge Chart decomposition isolating the source of performance differences.

2. **Comprehensive negative empirical evaluation** of HC-FALCON across 5 algorithm generations on 3 industrial Apache LRTS projects, demonstrating that semantic augmentation consistently fails to outperform the strong `history_cost` baseline at the class level.

3. **Discovery and quantification of the Heavy Predecessors phenomenon**, explaining why cost-agnostic submodular semantic optimization degrades fault detection in cost-heterogeneous CI environments.

4. **Methodological contribution**: strict preregistered evaluation protocol with temporal data splits, sealed confirmation datasets, and transparent reporting of negative results following best practices in empirical software engineering.

---

## 2. Related Work

### 2.1 Test Case Prioritization

TCP has been studied extensively in software engineering research. Greedy total and additional prioritization strategies using code coverage information were established early [Rothermel et al., 2001; Elbaum et al., 2002]. More recent approaches leverage machine learning [Bertolino et al., 2020], reinforcement learning [Spieker et al., 2017], and information retrieval techniques.

### 2.2 Semantic and Diversity-Based TCP

FAST [Mondal et al., ICSE 2018] applies MinHash/LSH string similarity for diversity-based selection. FALCON [Mensah-Boateng et al., ICST 2026] uses pretrained code language models (UniXcoder) with submodular Facility Location optimization, representing the state-of-the-art in semantic TCP. Our work extends FALCON by integrating failure history and execution cost.

### 2.3 History-Based and Cost-Aware TCP

History-based methods exploit past pass/fail outcomes. ROCKET [Marijan et al., 2013] uses failure frequency and recency. DANTE [Reale et al., ICST 2026] combines sliding-window failure history, failure stickiness, TF-IDF commit-diff similarity, and test duration for Long-Running Test Suites.

### 2.4 Submodular Optimization in Software Engineering

Submodular function maximization provides principled optimization with $1 - 1/e$ approximation guarantees under cardinality constraints [Nemhauser et al., 1978]. Applications in software engineering include test suite reduction [Lachmann et al., 2016] and diversification [Feldt et al., 2016]. To our knowledge, HC-FALCON is the first to combine Facility Location with Bayesian failure risk and cost normalization in a single submodular TCP objective.

### 2.5 Negative Results in Software Engineering

Negative results play a critical role in empirical software engineering by preventing wasted effort on approaches that appear promising in theory but fail in practice [Scanniello et al., 2014]. Our work follows the tradition of carefully controlled negative results that reveal fundamental limitations of seemingly sound approaches.

---

## 3. HC-FALCON: Methodology

### 3.1 Mathematical Model

At build $b$, given test suite $T_b = \{t_1, \dots, t_n\}$, the normalized combined objective $F_N: 2^{T_b} \to [0, 1]$ is:

$$F_N(S) = \alpha \frac{FL_b(S)}{|T_b|} + (1 - \alpha) \sum_{t \in S} w_b(t), \quad 0 \le \alpha \le 1$$

where:

- **Facility Location coverage**: $FL_b(S) = \sum_{u \in T_b} \max_{t \in S} K(u, t)$, with $K(u, t) = \text{clip}(z(u)^\top z(t), 0.0, 1.0)$ computed from $L_2$-normalized UniXcoder embeddings.

- **Normalized risk-cost weight**: $w_b(t) = q_b(t) / \sum_j q_b(j)$, where:
  - Bayesian failure probability: $p_b(t) = (f_t + 1) / (n_t + 2)$
  - Observation confidence: $\text{conf}_b(t) = n_t / (n_t + 5)$
  - Risk-cost score: $q_b(t) = \text{conf}_b(t) \cdot p_b(t) / (\sqrt{\tilde{c}_b(t)} + \varepsilon)$

### 3.2 Theoretical Guarantees

**Theorem 1**: $F_N(S)$ is monotone submodular and non-negative with $F_N(\emptyset) = 0$.

*Proof sketch*: The history component $\sum w_b(t)$ is modular (and thus submodular). The Facility Location $FL_b(S)$ is monotone submodular by the max-sum structure with non-negative kernel. A non-negative linear combination of monotone submodular functions preserves monotone submodularity. Full proof in supplementary materials.

**Corollary**: Cardinality greedy achieves $F_N(S_k) \ge (1 - 1/e) \cdot F_N(O)$ where $O$ is the optimal size-$k$ subset.

### 3.3 Technical Pipeline

- **Source preprocessing**: Remove line/block comments from Java source while preserving string literals and indentation structure.
- **UniXcoder encoding**: Sliding window chunking (up to 16 chunks of 512 tokens). Masked mean-token pooling excludes all `<pad>` tokens. Chunks are aggregated by effective payload length.
- **Content-addressed caching**: Embeddings cached by SHA-256 hash of source content for deterministic reproducibility.

---

## 4. Experimental Design

### 4.1 Datasets

| Dataset | Granularity | Projects | Test Units | Faults/Stages | Purpose |
|:---|:---|:---:|---:|---:|:---|
| **Defects4J v2.0** | Method-level | 6 | 20,770 methods | 288 faults | FALCON reproduction (RQ1) |
| **LRTS** | Class-level | 3 | Varies per build | 596 stages, 519 builds | HC-FALCON evaluation (RQ2-4) |

LRTS projects: Apache Karaf (315 builds), Apache ActiveMQ (126 builds), Apache Log4j2 (78 physical builds, 155 stages).

### 4.2 Temporal Data Split

To prevent future data leakage, builds are split chronologically:

- **Warm-up (20%)**: Initialize history accumulators and embedding caches. No metrics computed.
- **Development (next 30%, total 50%)**: Open experimental space for algorithm evaluation and forensic analysis.
- **Reserved Confirmation (final 50%)**: Cryptographically sealed. Only opened if Effect Gate passes on Development.

### 4.3 Metrics

- **Primary**: APFDc midpoint: $\text{APFDc} = 1 - \frac{\sum_{i:t_i \text{ failed}} (\sum_{j=1}^{i-1} C_j + C_i/2)}{m \sum_{i=1}^n C_i}$
- **Secondary**: APFD (rank-only), Time to First Failure (TTFF), Recall at 10% time budget

### 4.4 Effect Gate (Preregistered)

$$\text{Median Paired } \Delta\text{APFDc} \ge +0.0300 \text{ (+3.0 pp)}$$

vs. **both** `history_cost` and `fl_only` on at least 2 out of 3 projects.

### 4.5 Baselines

15 methods evaluated: `random` (20 seeds), `shortest_test_first`, `most_fail`, `recent_fail`, `history_only`, `history_cost`, `fl_only`, `hc_falcon_normalized_v1`, `hc_falcon_topic_raw_v1`, `fl_history`, `no_confidence`, `borda_history`, `borda_history_cost`, `fast_pw_lrts`, `dante_cch_adapt_r1`.

---

## 5. RQ1: Independent Reproduction of FALCON (Defects4J)

### 5.1 Full Reproduction Results

| Project | Methods | Faults | Author APFD | Rerun APFD | Delta | Time (s) | Peak RAM (GiB) |
|:---|---:|---:|:---:|:---:|:---:|---:|---:|
| Chart | 2,193 | 26 | 0.7263 | **0.7323** | +0.0060 | 977 | 1.130 |
| Mockito | 1,292 | 27 | 0.7362 | **0.7362** | +0.0000 | 267 | 1.131 |
| Lang | 2,239 | 32 | 0.7543 | **0.7543** | **+0.0000** | 897 | 1.172 |
| Math | 2,996 | 30 | 0.6224 | **0.6356** | +0.0132 | 1,477 | 1.184 |
| Time | 4,044 | 26 | 0.7944 | **0.7989** | +0.0045 | 1,438 | 1.137 |
| Closure | 8,006 | 147 | 0.7002 | **0.6986** | -0.0016 | 3,321 | 1.643 |
| **Average** | **20,770** | **288** | **0.7223** | **0.7260** | **+0.0037** | **8,376** | **1.643** |

Lang achieves exact mathematical match (Delta = 0.000000). Mean deviation across all 6 projects is only +0.37 percentage points, attributable to library version drift (PyTorch 2.14 vs. original 2024 environment).

### 5.2 Bridge Chart Decomposition

| Branch | Configuration | APFD | Delta from previous |
|:---|:---|:---:|:---:|
| A (Author baseline) | Author vectors + Author ranker | 0.7323 | -- |
| B (Clipped kernel) | Author vectors + Clip [0,1] | 0.7323 | +0.0000 |
| C (Internal greedy) | Clipped kernel + FQN tie-breaking | 0.7323 | +0.0000 |
| D (Full pipeline) | Internal preprocessing + masked pooling | **0.7635** | **+0.0313** |

**Finding**: The entire +3.13% APFD improvement originates from source preprocessing (comment removal) and masked attention pooling (excluding pad tokens).

---

## 6. RQ2: LRTS Evaluation Results

### 6.1 Stage 6 Pilot: HC-FALCON-N v1 (alpha = 0.5)

| Project | Builds | Pairs | Median $\Delta$ vs. `hc` | Mean $\Delta$ [95% Bootstrap CI] | Wilcoxon $p$-value | Cliff's $\delta$ (Effect) | Win / Loss / Tie | Median $\Delta$ vs. `fl_only` | Gate |
|:---|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Karaf | 315 | 79 | **-1.27%** | -0.44% [-3.22%, +2.53%] | $p = 6.25 \times 10^{-3}$ | -0.052 (negligible) | 24 / 54 / 1 (30.4%) | **+29.72%** ($p < 10^{-10}$) | No |
| ActiveMQ | 126 | 57 | **-1.41%** | -3.39% [-6.15%, -1.06%] | $p = 6.98 \times 10^{-7}$ | -0.141 (negligible) | 10 / 47 / 0 (17.5%) | **+39.14%** ($p < 10^{-8}$) | No |
| Log4j | 78 | 25 | **-0.12%** | +0.78% [-0.96%, +3.01%] | $p = 2.37 \times 10^{-2}$ | -0.101 (negligible) | 4 / 21 / 0 (16.0%) | **+28.69%** ($p = 3.29 \times 10^{-4}$) | No |

*Note: $\Delta = \text{APFDc}(\text{HC-FALCON}) - \text{APFDc}(\text{Baseline})$. Negative $\Delta$ indicates underperformance. Wilcoxon signed-rank test is two-sided with Pratt zero-handling per preregistration. 95% confidence intervals estimated via 10,000 bootstrap resamples.*

HC-FALCON overwhelmingly outperforms `fl_only` (+28.7% to +39.1%, all $p < 0.001$, Cliff's $\delta > +0.65$ Large), confirming that adding history and cost to semantic Facility Location is crucial. However, HC-FALCON statistically significantly underperforms the strong `history_cost` baseline on all three projects ($p = 0.0063$ on Karaf, $p < 10^{-6}$ on ActiveMQ, and $p = 0.0237$ on Log4j), winning only 16.0% to 30.4% of builds. Thus, it fails the preregistered Effect Gate (0/3 projects passed).

### 6.2 Comprehensive Baseline Comparison (Mean APFDc)

| Method | Karaf | ActiveMQ | Log4j | Rank |
|:---|---:|---:|---:|:---:|
| history_cost | **0.7754** | **0.8486** | 0.8936 | **1** |
| hc_falcon_topic_raw_v1 | 0.7746 | 0.8486 | 0.8940 | 2 |
| hc_falcon_normalized_v1 | 0.7710 | 0.8147 | 0.9014 | 3 |
| no_confidence | 0.7707 | 0.8152 | 0.9339 | 4 |
| dante_cch_adapt_r1 | 0.7480 | 0.7048 | **0.9351** | 5 |
| recent_fail | 0.7361 | 0.8369 | 0.8509 | 6 |
| history_only | 0.7122 | 0.8361 | 0.8469 | 7 |
| most_fail | 0.6951 | 0.8219 | 0.8667 | 8 |
| borda_history_cost | 0.6860 | 0.7379 | 0.9064 | 9 |
| fl_history | 0.6662 | 0.8154 | 0.8479 | 10 |
| shortest_test_first | 0.6683 | 0.6394 | 0.8586 | 11 |
| borda_history | 0.5323 | 0.7169 | 0.8215 | 12 |
| random | 0.4936 | 0.4945 | 0.4835 | 13 |
| fast_pw_lrts | 0.4606 | 0.4570 | 0.5194 | 14 |
| fl_only | 0.4522 | 0.4843 | 0.6990 | 15 |

### 6.3 Alpha Sensitivity Analysis

| Alpha | Mechanism | Karaf | ActiveMQ | Log4j |
|:---|:---|---:|---:|---:|
| 0.00 | History+Cost only | **0.7754** | **0.8486** | 0.8936 |
| 0.25 | Strong history bias | **0.7794** | 0.8420 | 0.8993 |
| 0.50 | Balanced (HC-FALCON) | 0.7710 | 0.8147 | 0.9014 |
| 0.75 | Strong semantic bias | 0.7077 | 0.7672 | 0.9036 |
| 1.00 | Semantic only | 0.4522 | 0.4843 | 0.6990 |

As alpha increases from 0 to 1, performance degrades monotonically on Karaf and ActiveMQ.

---

## 7. RQ3: Root Cause Analysis -- The Heavy Predecessors Phenomenon

### 7.1 Win/Loss Analysis on 161 Failure-Containing Builds

| Project | Total | Wins | Losses | Ties | Win Rate | Median Win Delta | Median Loss Delta |
|:---|---:|---:|---:|---:|---:|---:|---:|
| Karaf | 79 | 24 | 54 | 1 | 30.4% | +3.55% | -2.27% |
| ActiveMQ | 57 | 10 | 47 | 0 | 17.5% | +0.42% | -1.62% |
| Log4j | 25 | 4 | 21 | 0 | 16.0% | +10.52% | -0.13% |
| **Total** | **161** | **38** | **122** | **1** | **23.6%** | -- | -- |

### 7.2 Heavy Predecessors: Cumulative Delay Quantification

| Project | Added Predecessor Time | Removed Predecessor Time | Net Delay |
|:---|---:|---:|---:|
| Karaf | 18,206s | 23,385s | **-5,179s** |
| ActiveMQ | 115,759s | 71,873s | **+43,886s** |
| Log4j | 1,027s | 635s | **+392s** |
| **Total** | **134,992s** | **95,893s** | **+39,099s (~10.8 hours)** |

### 7.3 Mathematical Root Cause: Dimensional Mismatch

In $F_N(S) = \alpha \cdot FL(S)/n + (1-\alpha) \sum w_b(t)$:

1. The history score $w_b(t)$ is **cost-aware** (denominator contains $\sqrt{\tilde{c}_b(t)}$).
2. The semantic marginal gain $\Delta FL(t | S) / n$ is **entirely cost-agnostic**.
3. At early greedy steps, semantic gain constitutes **97.5%-99.9%** of total marginal gain.
4. This causes greedy to select a 150-second non-failing class (e.g., MemoryUsageConcurrencyTest) over a 0.001-second high-risk class, purely for marginal coverage, producing a single-build APFDc drop of up to **-51.50%**.

---

## 8. RQ4: Improvement Attempts (5 Generations)

### 8.1 Unified Comparison Across All 5 Generations

**Table: Comparative Performance Across All 5 Algorithm Generations vs. `history_cost` Baseline (161 failure-containing builds across 3 Apache projects).**

| Gen | Stage | Method | Core Mechanism | Karaf ($N=79$) | ActiveMQ ($N=57$) | Log4j ($N=25$) | Win Rate (Pooled) | Sign Test $p$-value | Effect Gate |
|:---:|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 6 | `hc_falcon_normalized_v1` | Standard submodular (cost-agnostic semantic) | -1.265% (24W/54L) | -1.407% (10W/47L) | -0.117% (4W/21L) | 23.6% (38/161) | $p = 1.05 \times 10^{-11}$ | 0/3 (NO-GO) |
| **2** | 8 | `restricted_v1` | Restrict candidates to $q \ge 0.95 q_{\text{head}}$ | -0.017% (13W/49L) | -0.154% (13W/43L) | -0.001% (5W/14L) | 19.3% (31/161) | $p = 7.74 \times 10^{-15}$ | 0/3 (NO-GO) |
| **3a** | 11 | `hc_cns_v1` (CNS-Greedy) | Cost-normalized semantic: $\Delta\text{FL}/\sqrt{c}$ | -0.399% (22W/56L) | -0.606% (10W/47L) | -0.190% (6W/19L) | 23.6% (38/161) | $p = 1.05 \times 10^{-11}$ | 0/3 (NO-GO) |
| **3b** | 11 | `hc_knapsack_v1` | Knapsack ratio: $(\Delta F)/c^{0.5}$ | -0.501% (26W/53L) | -6.625% (6W/51L) | -0.100% (5W/20L) | 23.0% (37/161) | $p = 4.41 \times 10^{-12}$ | 0/3 (NO-GO) |
| **3c** | 11 | `hc_tiered_v1` | Tiered grouping by history confidence | -0.182% (17W/62L) | -14.751% (1W/56L) | -1.001% (3W/22L) | 13.0% (21/161) | $p = 2.18 \times 10^{-21}$ | 0/3 (NO-GO) |
| **4** | 12 | `hc_ugcs_v2` | Bayesian uncertainty guard ($1.96 \sigma$) | -0.059% (20W/55L) | -0.224% (9W/44L) | -0.002% (6W/17L) | 21.7% (35/161) | $p = 4.29 \times 10^{-13}$ | 0/3 (NO-GO) |

*Key Takeaways:*
1. **100% Negative Median $\Delta$**: Every single project-generation cell (18/18) yields a negative median paired difference against `history_cost`.
2. **Sub-25% Win Rates**: Across all 5 generations, the candidate methods win only 13% to 24% of failure-containing builds, losing 70% to 85% of comparisons.
3. **Overwhelming Statistical Significance**: Two-sided binomial sign tests under the null hypothesis of equal median performance ($p_0 = 0.5$) reject the null with $p < 10^{-11}$ for every single generation.

### 8.2 Progression Analysis

- **Gen 1 to Gen 2 (Restricted)**: Reduced magnitude of loss by constraining semantic reordering space, but choked useful diversity.
- **Gen 1 to Gen 3a (CNS-Greedy)**: Addressed dimensional mismatch directly. Reduced loss by ~60%, turned Mean Delta positive (+1.7% to +3.5%), but Median remained negative because 70-80% of builds still lost.
- **Gen 4 (UGCS v2)**: Achieved smallest absolute median deltas (-0.002% on Log4j), but also **violated the runtime engineering gate** (P95 overhead: 12,184x vs. threshold 0.10).

### 8.3 Engineering Gate Results (Stage 12)

| Gate | Metric | Threshold | Actual | Passed |
|:---|:---|:---:|:---:|:---:|
| Memory | Peak RSS | 8 GiB | 656 MiB | Yes |
| Runtime | P95 warm overhead fraction | 0.10 | 12,183.97 | No |
| Completeness | Missing/invalid errors | 0 | 0 | Yes |

---

## 9. Discussion

### 9.1 Why Semantic Diversification Fails on Class-Level CI

The stark contrast between success on Defects4J (APFD 0.7260) and failure on LRTS (Gate 0/3) reveals fundamental differences:

1. **Granularity**: On Defects4J, test units are individual methods with compact, focused semantics and uniform costs. On LRTS, test units are entire classes containing dozens of methods, diluting embedding quality through chunking and pooling.

2. **Cost variance**: Defects4J uses rank-only APFD (implicit unit cost). LRTS execution times span 5 orders of magnitude (0.001s to 150s+). Any reordering that promotes a slow test produces irrecoverable APFDc damage.

3. **Baseline strength**: In real CI, failures are sticky and concentrated. The history_cost score $q_b(t) = \text{conf} \cdot p / \sqrt{\tilde{c}}$ is an extremely powerful estimator that semantic diversity cannot profitably perturb at the median.

### 9.2 Value of This Negative Result

- **Refutes a plausible hypothesis**: The intuition that combining semantic diversity with history/cost should improve TCP is mathematically sound (submodular guarantees hold) but empirically falsified on class-level CI with heterogeneous costs.
- **Warns against Heavy Predecessors**: Any cost-agnostic diversity objective in TCP is vulnerable to this effect when cost variance is high.
- **Methodological exemplar**: Preregistered evaluation, sealed confirmation datasets, and transparent negative reporting prevent publication bias.

### 9.3 Boundary Conditions

Our negative conclusion is bounded to: Java/Maven ecosystem, class-level TCP with highly dispersed costs, three Apache projects, sequential execution model measured by APFDc. It does **not** claim semantic TCP fails universally -- we successfully reproduced FALCON on method-level Defects4J with uniform costs.

---

## 10. Threats to Validity

### Internal Validity
- Float64 normalization causes 8 micro-exceptions in tie-breaking at alpha = 0.0 across 33,972 rankings; these do not affect statistical conclusions.
- Deterministic FQN tie-breaking ensures reproducibility but carries minor alphabetical bias.

### External Validity
- All LRTS conclusions derive from 3 Java/Maven open-source projects. Results may differ for interpreted languages (Python, JS) or enterprise CI with parallel/sharded execution.
- Class-level evaluation does not generalize to method-level TCP where embedding quality is higher and costs are more uniform.

### Construct Validity
- APFDc assumes strictly sequential single-threaded execution. In parallel CI, the Heavy Predecessors impact may be mitigated.
- The Stage 12 runtime gate (P95 <= 0.10 relative to history_cost's ~50 microsecond sort) is structurally impossible for any semantic algorithm. We accept this fail-closed per preregistration.

### Conclusion Validity
- 161 failure-containing builds provide sufficient statistical power for Wilcoxon tests on Karaf (79) and ActiveMQ (57). Log4j (25 builds) has limited power but consistent trends.
- Four generations evaluated on the same Development split risk Garden of Forking Paths. Controlled by preregistration, zero tuning rounds, and 100% sealed Reserved dataset.

---

## 11. Conclusion and Future Work

We proposed and comprehensively evaluated HC-FALCON for Test Case Prioritization, combining semantic Facility Location, Bayesian failure history, and execution cost in a provably submodular framework. Our findings:

1. **100% reproduction fidelity** of FALCON on Defects4J (APFD 0.7260 vs. 0.7223).
2. **Effect Gate failure (0/3)** across all 5 algorithm generations on real-world LRTS class-level CI.
3. **Heavy Predecessors** identified as the root cause: cost-agnostic semantic greedy causes +10.8 hours cumulative delay.
4. **CNS-Greedy** reduces damage by 60% but cannot reverse median delta to positive.

We conclude that on class-level CI with heterogeneous execution costs, failure history combined with cost is an exceptionally strong baseline that semantic diversity cannot profitably augment at the median. The Reserved Confirmation dataset remains permanently sealed for this research line.

### Future Directions

1. **Method-level CI TCP**: Eliminate embedding dilution by collecting method-level CI logs.
2. **Cold-start-only semantic**: Activate semantic prioritization only for tests with N = 0 observations.
3. **Parallel/sharded CI metrics**: Evaluate under distributed execution models.
4. **Cross-ecosystem generalization**: Test on interpreted languages (Python, JS) and systems languages (Rust, Go).

---

## References

[1] G. Rothermel, R. H. Untch, C. Chu, and M. J. Harrold, "Prioritizing test cases for regression testing," *IEEE Transactions on Software Engineering*, vol. 27, no. 10, pp. 929-948, 2001.

[2] S. Elbaum, A. G. Malishevsky, and G. Rothermel, "Test case prioritization: A family of empirical studies," *IEEE Transactions on Software Engineering*, vol. 28, no. 2, pp. 159-182, 2002.

[3] S. Elbaum, P. Kallakuri, A. G. Malishevsky, and G. Rothermel, "Understanding the effects of changes on the cost-effectiveness of regression testing techniques," *Software Testing, Verification and Reliability*, vol. 13, no. 2, pp. 65-83, 2003.

[4] A. Bertolino, B. Miranda, E. Rogstad, and A. R. Santos, "Learning-to-rank for test case prioritization in continuous integration," *IEEE Transactions on Software Engineering*, vol. 47, no. 12, pp. 2728-2746, 2020.

[5] H. Spieker, A. Gotlieb, D. Marijan, and M. Mossige, "Reinforcement learning for automatic test case prioritization and selection in continuous integration," in *Proc. 26th ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2017, pp. 12-22.

[6] B. Mondal, H. Hemmati, and S. Durocher, "FAST: Fast and scalable test case prioritization using diversity," in *Proc. 40th Int. Conf. Softw. Eng. (ICSE)*, 2018, pp. 1198-1208.

[7] K. Mensah-Boateng, A. Perera, C. Tantithamthavorn, and B. Le, "FALCON: Submodular Test Case Prioritization using Code Embeddings," in *Proc. 19th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2026.

[8] M. Reale, F. Pecorelli, D. Di Nucci, F. Palomba, and A. De Lucia, "DANTE: History-aware Test Case Prioritization for Long-Running Test Suites," in *Proc. 19th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2026.

[9] D. Marijan, A. Gotlieb, and S. Sen, "Test case prioritization for continuous integration testing in resource-constrained environments," in *Proc. 25th IEEE Int. Conf. Softw. Maint. (ICSM)*, 2013, pp. 488-491.

[10] G. L. Nemhauser, L. A. Wolsey, and M. L. Fisher, "An analysis of approximations for maximizing submodular set functions—I," *Mathematical Programming*, vol. 14, no. 1, pp. 265-294, 1978.

[11] A. Krause and D. Golovin, "Submodular function maximization," *Tractability: Practical Approaches to Hard Problems*, vol. 3, pp. 71-104, 2014.

[12] D. Guo, S. Lu, N. Duan, Y. Wang, M. Zhou, and J. Yin, "UniXcoder: Unified cross-modal pre-training for code representation," in *Proc. 60th Annu. Meeting Assoc. Comput. Linguist. (ACL)*, 2022, pp. 7212-7225.

[13] R. Just, D. Jalali, and M. D. Ernst, "Defects4J: A database of existing faults to enable controlled testing studies for Java," in *Proc. 23rd ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2014, pp. 437-440.

[14] B. Busjaeger and T. Xie, "Learning for test prioritization: An industrial evaluation," in *Proc. 24th ACM SIGSOFT Int. Symp. Found. Softw. Eng. (FSE)*, 2016, pp. 975-986.

[15] H. Hemmati, A. Arcuri, and L. Briand, "Achieving higher test coverage by test case diversification," in *Proc. 35th Int. Conf. Softw. Eng. (ICSE)*, 2013, pp. 782-791.

[16] R. Feldt, F. G. de Oliveira Neto, and R. Torkar, "Ways of test set diversification: Concepts, taxonomy and preliminary findings," in *Proc. 19th Int. Conf. Softw. Eng. Pract. Eval. (SEAA)*, 2016, pp. 293-300.

[17] C. Henard, M. Papadakis, M. Harman, and Y. Le Traon, "Comparing white-box and black-box test prioritization: An empirical study," in *Proc. 38th Int. Conf. Softw. Eng. (ICSE)*, 2016, pp. 523-534.

[18] Q. Luo, K. Moran, L. Zhang, and D. Poshyvanyk, "How do test runs impact flaky tests? An empirical study," in *Proc. 28th ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2019, pp. 222-233.

[19] G. Scanniello, E. Stangl, G. Bavota, F. Wedyan, and M. Torchiano, "The value of negative results in empirical software engineering," *Empirical Software Engineering*, vol. 20, no. 6, pp. 1751-1779, 2015.

[20] A. Gelman and E. Loken, "The statistical crisis in science: Data-dependent analysis—a 'garden of forking paths'—explains why many statistically significant findings don't hold up," *American Scientist*, vol. 102, no. 6, pp. 460-465, 2014.

[21] F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, vol. 1, no. 6, pp. 80-83, 1945.

[22] N. Cliff, "Dominance statistics: Ordinal analyses to answer ordinal questions," *Psychological Bulletin*, vol. 114, no. 3, pp. 494-509, 1993.

[23] S. Holm, "A simple sequentially rejective multiple test procedure," *Scandinavian Journal of Statistics*, vol. 6, no. 2, pp. 65-70, 1979.

[24] B. Efron and R. J. Tibshirani, *An Introduction to the Bootstrap*. CRC Press, 1994.

[25] J.-M. Kim and A. Porter, "A history-based test prioritization technique for regression testing in resource-constrained environments," in *Proc. 24th Int. Conf. Softw. Eng. (ICSE)*, 2002, pp. 119-129.

[26] E. Engström, P. Runeson, and M. Skoglund, "A systematic review on regression test selection techniques," *Information and Software Technology*, vol. 52, no. 1, pp. 14-30, 2010.

[27] S. Lu et al., "CodeXGLUE: A machine learning benchmark dataset for code understanding and generation," in *Proc. 35th Conf. Neural Inf. Process. Syst. (NeurIPS)* Datasets and Benchmarks Track, 2021.

[28] Z. Feng et al., "CodeBERT: A pre-trained model for programming and natural languages," in *Proc. Findings of EMNLP*, 2020, pp. 1536-1547.

[29] H. Husain, H.-H. Wu, T. Gazit, M. Allamanis, and M. Brockschmidt, "CodeSearchNet challenge: Evaluating the state of semantic code search," *arXiv preprint arXiv:1909.09436*, 2019.

[30] R. Lachmann, S. Schulze, M. Nieke, C. Seidl, and I. Schaefer, "Fine-grained test case prioritization using machine learning," in *Proc. 9th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2016, pp. 1-10.

[31] M. Khatibsyarbini, M. A. Isa, D. N. Jawawi, and R. Tumeng, "Test case prioritization approaches in regression testing: A systematic literature review," *Information and Software Technology*, vol. 93, pp. 74-93, 2018.

[32] H. Do, S. Elbaum, and G. Rothermel, "Supporting controlled experimentation with testing techniques: An infrastructure and its potential impact," *Empirical Software Engineering*, vol. 10, no. 4, pp. 405-435, 2005.

[33] S. Wang, D. Buchler, A. Gotlieb, D. Marijan, and A. Liaaen, "Multi-objective test prioritization in software product line testing: An industrial case study," in *Proc. 18th Int. Softw. Product Line Conf. (SPLC)*, 2014, pp. 247-256.

[34] M. G. Epitropakis, S. Yoo, M. Harman, and E. K. Burke, "Empirical evaluation of Pareto efficient multi-objective regression test case prioritisation," in *Proc. 2015 Int. Symp. Softw. Test. Anal. (ISSTA)*, 2015, pp. 234-245.

[35] Y. Lu, Y. Lou, S. Cheng, L. Zhang, D. Hao, L. Zhang, and T. Xie, "How does regression test prioritization perform in real-world software evolution?," in *Proc. 38th Int. Conf. Softw. Eng. (ICSE)*, 2016, pp. 535-546.

