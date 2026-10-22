# HC-FALCON v2: Formal Specification (`hc_ugcs_v2`)

## 1. Overview

**Algorithm Name**: `hc_ugcs_v2`
**Full Name**: Uncertainty-Guarded Cost-aware Semantic ranking
**Core Purpose**: Combine historical failure risk, statistical uncertainty bounds, execution cost, and submodular semantic facility location to safely reorder tests in Continuous Integration.

---

## 2. Mathematical Formulation

### 2.1. Feature Extraction from Snapshot
For each test $t \in T$ in declared test inventory $T$ of size $n$, the ranker extracts the frozen feature fields from `Snapshot.features`:

- $N_t$: Number of historical observations (`feature.observations`)
- $F_t$: Number of historical failures (`feature.failures`, where $0 \le F_t \le N_t$)
- $\text{conf}_t$: Historical confidence factor (`feature.confidence` $= N_t / (N_t + 5.0)$)
- $q_t$: Cost-penalized history score (`feature.history_cost_score` $\ge 0$)
- $\tilde{c}_t$: Normalized execution duration (`feature.normalized_duration` $\ge 0$)

### 2.2. Bayesian Failure Probability Credibility Bounds
Under a standard uninformative conjugate prior $\text{Beta}(1, 1)$:
- Posterior parameters:
  $$a_t = F_t + 1$$
  $$b_t = N_t - F_t + 1$$
- Posterior mean:
  $$\mu_t = \frac{a_t}{a_t + b_t} = \frac{F_t + 1}{N_t + 2}$$
- Posterior standard deviation:
  $$\sigma_t = \sqrt{\frac{a_t \cdot b_t}{(a_t + b_t)^2 (a_t + b_t + 1)}}$$
- Cost-scaling denominator:
  $$\text{denom}_t = \sqrt{\max(\tilde{c}_t, 10^{-6})} + 10^{-8}$$
- Credibility interval risk bounds:
  $$\text{lower}_t = \text{conf}_t \cdot \frac{\max(0.0, \mu_t - z \cdot \sigma_t)}{\text{denom}_t}$$
  $$\text{upper}_t = \text{conf}_t \cdot \frac{\min(1.0, \mu_t + z \cdot \sigma_t)}{\text{denom}_t}$$

### 2.3. Preregistered Constants
All parameters are fixed and immutable:
- Primary semantic mixing weight: $\lambda = 0.25$ (`semantic_weight`)
- Normal credibility multiplier: $z = 1.96$ (`z_value`, 95% two-sided normal approximation)
- Cost floor: $\text{cost\_floor} = 10^{-6}$
- Numerical denominator epsilon: $\epsilon = 10^{-8}$
- Gain and score comparison tolerance: $\tau = 10^{-12}$ (`gain_tolerance`)

---

## 3. Step-by-Step Ranking Procedure

Let $K \in [0, 1]^{n \times n}$ be the precomputed cosine similarity kernel for the current build inventory.

1. **Initialization**:
   - Coverage vector: $\mathbf{c} \in \mathbb{R}^n$, initialized to $\mathbf{0}$.
   - Remaining candidate indices: $R = \{0, 1, \dots, n-1\}$.
   - Output permutation: $P = []$.

2. **Loop**: For position $k = 1, 2, \dots, n$:
   1. **Select History Anchor**:
      Identify the top history-ranked candidate $t^* \in R$ by:
      $$t^* = \operatorname{argmin}_{i \in R} (-q_i, \text{test\_id}_i)$$
      (i.e., highest $q_i$, breaking ties by lexicographically smallest Fully Qualified Name).
   2. **Filter Safe Candidate Pool**:
      A remaining test $t \in R$ is admitted to the safe pool $S \subseteq R$ if and only if its upper risk bound is within numerical tolerance of the anchor's lower risk bound:
      $$S = \{t \in R \mid \text{upper}_t + 10^{-12} \ge \text{lower}_{t^*}\}$$
      *(Note: Since $\text{upper}_{t^*} \ge \text{lower}_{t^*}$, the anchor $t^*$ is guaranteed to belong to $S$. Hence $S \neq \emptyset$.)*
   3. **Compute Marginal Semantic Gain**:
      For each $t \in S$, compute the facility-location marginal coverage:
      $$\Delta FL(t \mid \mathbf{c}) = \frac{1}{n} \sum_{i=0}^{n-1} \max(K_{i, t} - c_i, 0.0)$$
   4. **Compute Cost-Aware Semantic Density**:
      Scale marginal coverage by cost:
      $$\text{density}_t = \frac{\Delta FL(t \mid \mathbf{c})}{\sqrt{\max(\tilde{c}_t, 10^{-6})}}$$
   5. **Relative Score Normalization**:
      Normalize scores over the relevant sets:
      $$M_q = \max_{i \in R} q_i$$
      $$q_{\text{rel}}(t) = \begin{cases} q_t / M_q & \text{if } M_q > 0 \\ 0.0 & \text{if } M_q = 0 \end{cases}$$
      $$M_d = \max_{i \in S} \text{density}_i$$
      $$\text{sem}_{\text{rel}}(t) = \begin{cases} \text{density}_t / M_d & \text{if } M_d > 0 \\ 0.0 & \text{if } M_d = 0 \end{cases}$$
   6. **Compute Combined Utility**:
      For each $t \in S$:
      $$U(t) = (1 - \lambda) \cdot q_{\text{rel}}(t) + \lambda \cdot \text{sem}_{\text{rel}}(t)$$
   7. **Select Winning Test**:
      Select test $t_{\text{win}} \in S$ that maximizes:
      1. Highest utility $U(t)$ (with tolerance $\tau = 10^{-12}$),
      2. Highest historical score $q_t$ (with tolerance $\tau = 10^{-12}$),
      3. Lexicographically smallest `test_id` string (exact FQN tie-break).
   8. **Update State**:
      - Append $t_{\text{win}}$ to $P$.
      - Update coverage: $c_i \leftarrow \max(c_i, K_{i, t_{\text{win}}})$ for all $i = 0, \dots, n-1$.
      - Remove $t_{\text{win}}$ from $R$.

3. **Output**:
   Return permutation $P$ as an immutable tuple of test ID strings.

---

## 4. Invariants, Boundary Conditions, and Guarantees

### 4.1. Degenerate and Boundary Behaviors
- **Zero Kernel ($K = \mathbf{0}_{n \times n}$)**:
  When the kernel is zero, marginal semantic gain is identically zero for all tests ($\text{sem}_{\text{rel}}(t) = 0$). The utility reduces strictly to $(1 - \lambda) \cdot q_{\text{rel}}(t)$. The winning candidate is always the anchor $t^*$, exactly matching `tcp.baselines.rank(snapshot, "history_cost")`.
- **All-Zero History Scores ($q = \mathbf{0}$)**:
  When no historical failure evidence exists ($N_t = 0$ or $q_t = 0$ for all $t$), $\text{conf}_t = 0$, leading to $\text{lower}_t = \text{upper}_t = 0$. All candidates are safe ($S = R$). Utility is dictated entirely by cost-aware semantic density, broken by lexicographical FQN.
- **Single Test ($n = 1$)**:
  Returns `(test_ids[0],)`.
- **Empty Inventory ($n = 0$)**:
  Returns `()`.

### 4.2. Failure Prevention: The Heavy Predecessor Guard
Suppose an expensive non-failing test $B$ ($\tilde{c}_B \gg 1, F_B = 0, N_B \ge 5$) has high semantic similarity to many tests, while anchor $A$ is a known failure candidate ($F_A > 0, \tilde{c}_A \le 1$). Because $\text{conf}_A$ is high and $\mu_A - z\sigma_A > 0$, $\text{lower}_A$ is strictly positive. Meanwhile, $F_B = 0$ combined with large $\tilde{c}_B$ suppresses $\text{upper}_B$. Whenever $\text{upper}_B + 10^{-12} < \text{lower}_A$, $B \notin S$. Test $B$ cannot be selected ahead of anchor $A$, eliminating the Heavy Predecessor failure mode.

### 4.3. Data Leakage and State Safety Boundary
- **Input Integrity**: `rank_ugcs` and `rank_ugcs_reference` accept `Snapshot`, `test_ids`, and `kernel`. They never accept or consume `Outcome`, `CompletedBuild`, or execution timestamps from the current build.
- **Immutability**: Neither `Snapshot` nor the input `kernel` array are modified in place.
- **Fail-Closed Strictness**:
  Any input with NaN, Inf, negative scores, duplicate IDs, or inventory mismatches raises `ValueError`.

### 4.4. Computational Complexity
- **Worst-case Time Complexity**: $O(n^3)$ for the current reference and vectorized implementations.
  - The greedy ranking procedure executes $n$ selection steps.
  - At each step $k \in \{0, \dots, n-1\}$, up to $O(n)$ unselected candidates are evaluated.
  - Evaluating each safe candidate's marginal semantic coverage gain $\sum_{i=1}^n \max(K[i, t] - C[i], 0)$ inspects $n$ coverage entries, which takes $O(n)$ work per candidate.
  - Therefore, each greedy step performs $O(n^2)$ operations in the worst case, yielding $O(n^3)$ total time across all $n$ steps.
- **Space Complexity**:
  - Input kernel: $O(n^2)$ space for the pairwise cosine similarity matrix.
  - Auxiliary state: $O(n)$ space for coverage tracking arrays, precomputed history scores, risk bounds, and selection masks.
