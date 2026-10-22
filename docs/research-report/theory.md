# Cơ sở Lý thuyết, Chứng minh Toán học và Phân tích Độ phức tạp của HC-FALCON

Báo cáo này trình bày nền tảng toán học hình thức của phương pháp **HC-FALCON** trong bài toán Ưu tiên Bộ kiểm thử (Test Case Prioritization - TCP), bao gồm: mô hình hóa hàm mục tiêu kết hợp, chứng minh đầy đủ tính chất submodular và cận xấp xỉ greedy $1 - 1/e$, phân tích thuật toán Lazy Greedy, các phản ví dụ về ranh giới lý thuyết giữa hàm mục tiêu và metric đánh giá (APFD/APFDc), cùng phân tích độ phức tạp thời gian và không gian.

---

## 1. Mô hình Toán học Hình thức

### 1.1. Không gian bài toán và Đầu vào

Tại mỗi commit hoặc chu kỳ build $b$, ký hiệu tập hợp toàn bộ các test case cần sắp xếp là:
$$T_b = \{t_1, t_2, \dots, t_n\}, \quad n = |T_b| \ge 1$$

Mỗi test case $t \in T_b$ được đặc trưng bởi các thuộc tính quan sát độc lập với kết quả tương lai:
1. **Biểu diễn ngữ nghĩa (Semantic Embedding)**: Vector $z(t) \in \mathbb{R}^d$ ($d = 768$ sinh từ mô hình tiền huấn luyện UniXcoder) sau khi chuẩn hóa $L_2$ ($\|z(t)\|_2 = 1$).
2. **Độ tương đồng ngữ nghĩa từng cặp (Pairwise Similarity)**:
   $$K(u, t) = \operatorname{clip}\left(z(u)^\top z(t), \, 0.0, \, 1.0\right), \quad \forall u, t \in T_b$$
   với quy ước $K(t, t) = 1.0$ đối với test có mã nguồn hợp lệ, và $K(u, t) = 0.0$ nếu một trong hai test không có mã nguồn hợp lệ.
3. **Ước lượng xác suất thất bại (Failure Probability)**: $p_b(t) \in [0, 1]$, ước lượng từ lịch sử chạy trước thời điểm cutoff của build $b$.
4. **Ước lượng thời gian chạy (Execution Duration)**: $c_b(t) > 0$ (giây).
5. **Độ tin cậy lịch sử (Observation Confidence)**: $\operatorname{conf}_b(t) \in [0, 1]$.

### 1.2. Pipeline Ước lượng Lịch sử và Chi phí (Beta-Bernoulli History & Cost Estimator)

Gọi $n_t \ge 0$ là tổng số lần test $t$ đã thực thi trong các build quá khứ, và $f_t \ge 0$ là số lần thất bại ($0 \le f_t \le n_t$).

- **Xác suất lỗi Bayes với tiên nghiệm đều (Laplace / Beta Prior $\alpha_0 = 1, \beta_0 = 1$)**:
  $$p_b(t) = \frac{f_t + 1}{n_t + 2}$$
- **Hàm độ tin cậy quan sát (với ngưỡng bán bão hòa $\tau = 5.0$)**:
  $$\operatorname{conf}_b(t) = \frac{n_t}{n_t + \tau} = \frac{n_t}{n_t + 5}$$
  Hàm đạt giá trị $0$ khi $n_t = 0$ (cold-start), đạt $0.5$ khi $n_t = 5$, và tiệm cận $1$ khi $n_t \to \infty$.
- **Thời gian chạy tham chiếu và chuẩn hóa**:
  $$c_{ref} = \max\left(10^{-6}, \, \operatorname{median}\left(\{d > 0 \mid d \in \text{lịch sử ngữ cảnh}\}\right)\right)$$
  $$c_b(t) = \max\left(10^{-6}, \, \operatorname{median}\left(\{d > 0 \mid d \in \text{lịch sử của } t\}\right)\right)$$
  $$\widetilde{c}_b(t) = \frac{c_b(t)}{c_{ref}}$$
- **Điểm Rủi ro - Chi phí (Failure-Cost Score)**:
  $$r_b(t) = \operatorname{conf}_b(t) \cdot p_b(t)$$
  $$q_b(t) = \frac{r_b(t)}{\sqrt{\widetilde{c}_b(t)} + \varepsilon}$$
  với $\varepsilon = 10^{-8}$ là hằng số chống chia cho 0.

### 1.3. Hàm Bao phủ Ngữ nghĩa (Facility Location Coverage)

Với tập con test case đã chọn $S \subseteq T_b$, độ bao phủ ngữ nghĩa của $S$ lên toàn bộ không gian test $T_b$ được định nghĩa qua mô hình Facility Location:
$$FL_b(S) = \sum_{u \in T_b} \max_{t \in S} K(u, t)$$
với quy ước khi $S = \emptyset$:
$$\max_{t \in \emptyset} K(u, t) \triangleq 0 \implies FL_b(\emptyset) = 0$$

### 1.4. Hàm Mục tiêu Kết hợp (Combined Objective)

#### Phiên bản Chuẩn hóa Trọng số — HC-FALCON-N v1 (`hc_falcon_normalized_v1`):
Nhằm triệt tiêu sự lệch thang đo thứ nguyên khi tổng rủi ro $Q = \sum_{t \in T_b} q_b(t)$ biến thiên mạnh giữa các build (quan sát thực tế $Q$ dao động từ $0$ đến $43.6$), điểm rủi ro được chuẩn hóa theo phân phối xác suất trên suite hiện tại:
$$Q = \sum_{t \in T_b} q_b(t)$$
$$w_b(t) = \begin{cases} \frac{q_b(t)}{Q}, & \text{nếu } Q > 0 \\ 0, & \text{nếu } Q = 0 \end{cases}$$

Hàm mục tiêu kết hợp $F_N: 2^{T_b} \to [0, 1]$ được định nghĩa:
$$F_N(S) = \alpha \frac{FL_b(S)}{|T_b|} + (1 - \alpha) \sum_{t \in S} w_b(t), \quad 0 \le \alpha \le 1$$

Khi $\alpha = 0.5$ (cấu hình chuẩn):
$$F_N(S) = \frac{1}{2} \cdot \frac{FL_b(S)}{n} + \frac{1}{2} \sum_{t \in S} w_b(t)$$

#### Bài toán Tối ưu hóa dưới Ràng buộc Ngân sách Cardinality $k$:
$$\max_{S \subseteq T_b, \, |S| \le k} F_N(S)$$

---

## 2. Chứng minh Toán học Hình thức (Formal Proofs)

---

### Mệnh đề 1: Tính Modular, Không âm và Đơn điệu của Thành phần Lịch sử - Chi phí

**Phát biểu**: Giả sử $q(t) \ge 0$ với mọi $t \in T$. Khi đó hàm tập $h(S) = \sum_{t \in S} q(t)$ (với $h(\emptyset) = 0$) là hàm không âm, modular và đơn điệu tăng (monotone non-decreasing). Tương tự đối với hàm chuẩn hóa $h_w(S) = \sum_{t \in S} w(t)$.

**Chứng minh**:
1. **Tính không âm ($h(S) \ge 0$)**:
   - Theo định nghĩa, $n_t \ge 0 \implies \operatorname{conf}(t) \in [0, 1] \ge 0$.
   - $f_t \ge 0 \implies p(t) \in (0, 1) > 0$.
   - $\widetilde{c}(t) > 0 \implies \sqrt{\widetilde{c}(t)} + \varepsilon > 0$.
   - Do đó, $q(t) \ge 0$ với mọi $t \in T$.
   - Với mọi $S \subseteq T$, $h(S) = \sum_{t \in S} q(t)$ là tổng hữu hạn các số hạng không âm, do đó $h(S) \ge 0$.
   - Vì $Q = \sum_{t \in T} q(t) \ge 0$, nên $w(t) = q(t)/Q \ge 0 \implies h_w(S) \ge 0$.

2. **Tính Modular**:
   Xét tập con bất kỳ $S \subseteq T$ và phần tử $x \notin S$. Lượng tăng biên (marginal gain) của $x$ đối với $S$ là:
   $$\Delta_h(x \mid S) = h(S \cup \{x\}) - h(S) = \left(\sum_{t \in S} q(t) + q(x)\right) - \sum_{t \in S} q(t) = q(x)$$
   Nhận thấy $\Delta_h(x \mid S) = q(x)$ là một hằng số phụ thuộc duy nhất vào $x$, hoàn toàn độc lập với tập $S$.
   Với hai tập con bất kỳ $A \subseteq B \subseteq T$ và $x \notin B$:
   $$\Delta_h(x \mid A) = q(x) = \Delta_h(x \mid B)$$
   Theo tính chất bao hàm - loại trừ:
   $$h(A \cup B) + h(A \cap B) = \sum_{t \in A \cup B} q(t) + \sum_{t \in A \cap B} q(t) = \sum_{t \in A} q(t) + \sum_{t \in B} q(t) = h(A) + h(B)$$
   Đẳng thức thỏa mãn với dấu bằng, chứng minh $h(S)$ và $h_w(S)$ là modular.

3. **Tính đơn điệu (Monotonicity)**:
   Với hai tập con bất kỳ $A \subseteq B \subseteq T$:
   $$h(B) - h(A) = \sum_{t \in B \setminus A} q(t)$$
   Vì $q(t) \ge 0, \forall t \in T$, tổng trên luôn không âm:
   $$h(B) - h(A) \ge 0 \implies h(A) \le h(B)$$
   Do đó $h(S)$ và $h_w(S)$ là đơn điệu tăng. $\blacksquare$

---

### Mệnh đề 2: Tính Đơn điệu và Submodular của Facility Location

**Phát biểu**: Cho kernel tương đồng $K \in \mathbb{R}^{n \times n}$ thỏa mãn $K(u, t) \ge 0$ với mọi $u, t \in T$. Khi đó hàm Facility Location:
$$FL(S) = \sum_{u \in T} \max_{t \in S} K(u, t), \quad S \subseteq T, \quad FL(\emptyset) = 0$$
là hàm không âm, đơn điệu tăng và submodular (thỏa mãn quy luật lợi ích biên giảm dần).

**Chứng minh**:

Đặt $m_S(u) = \max_{t \in S} K(u, t)$ với $S \ne \emptyset$, và $m_\emptyset(u) = 0$. Khi đó $FL(S) = \sum_{u \in T} m_S(u)$.

1. **Tính đơn điệu hàng-theo-hàng**:
   Xét $A \subseteq B \subseteq T$.
   - Nếu $A = \emptyset$: vì $K(u, t) \ge 0$, ta có $m_\emptyset(u) = 0 \le m_B(u)$ với mọi $u \in T$.
   - Nếu $A \ne \emptyset$: vì $A \subseteq B$, tập giá trị $\{K(u, t) \mid t \in A\} \subseteq \{K(u, t) \mid t \in B\}$. Giá trị cực đại trên tập mẹ luôn lớn hơn hoặc bằng giá trị cực đại trên tập con:
     $$m_A(u) = \max_{t \in A} K(u, t) \le \max_{t \in B} K(u, t) = m_B(u), \quad \forall u \in T$$
   Lấy tổng trên toàn bộ $u \in T$:
   $$FL(A) = \sum_{u \in T} m_A(u) \le \sum_{u \in T} m_B(u) = FL(B)$$
   Suy ra $FL(S)$ đơn điệu tăng.

2. **Công thức Lượng tăng biên (Marginal Gain)**:
   Xét tập $S \subseteq T$ và phần tử $x \notin S$:
   $$m_{S \cup \{x\}}(u) = \max\left(m_S(u), \, K(u, x)\right)$$
   Mức đóng góp tăng thêm trên từng hàng $u$ là:
   $$\Delta_m(u, x \mid S) = m_{S \cup \{x\}}(u) - m_S(u) = \max\left(0, \, K(u, x) - m_S(u)\right)$$
   Do đó, lượng tăng biên tổng thể của $x$ đối với $S$ là:
   $$\Delta_{FL}(x \mid S) = FL(S \cup \{x\}) - FL(S) = \sum_{u \in T} \max\left(0, \, K(u, x) - m_S(u)\right)$$

3. **Tính Submodular (Lợi ích biên giảm dần)**:
   Xét $A \subseteq B \subseteq T$ và $x \notin B$.
   Từ tính đơn điệu, ta đã có $m_A(u) \le m_B(u)$ với mọi $u \in T$.
   Nhân với $-1$ và cộng $K(u, x)$ vào hai vế:
   $$K(u, x) - m_A(u) \ge K(u, x) - m_B(u), \quad \forall u \in T$$
   Hàm thực $\phi(z) = \max(0, z)$ là hàm đơn điệu tăng không giảm trên $\mathbb{R}$. Áp dụng $\phi$ vào hai vế bảo toàn chiều bất đẳng thức:
   $$\max\left(0, \, K(u, x) - m_A(u)\right) \ge \max\left(0, \, K(u, x) - m_B(u)\right), \quad \forall u \in T$$
   Lấy tổng bất đẳng thức này trên toàn bộ $u \in T$:
   $$\sum_{u \in T} \max\left(0, \, K(u, x) - m_A(u)\right) \ge \sum_{u \in T} \max\left(0, \, K(u, x) - m_B(u)\right)$$
   $$\iff \Delta_{FL}(x \mid A) \ge \Delta_{FL}(x \mid B)$$
   Bất đẳng thức trên khẳng định lượng tăng biên khi bổ sung $x$ vào tập con $A$ luôn lớn hơn hoặc bằng lượng tăng biên khi bổ sung vào tập mẹ $B$.
   Vậy $FL(S)$ là hàm submodular. $\blacksquare$

---

### Mệnh đề 3: Tính Đơn điệu và Submodular của Hàm Mục tiêu Kết hợp $F_N(S)$

**Phát biểu**: Hàm mục tiêu kết hợp chuẩn hóa:
$$F_N(S) = \frac{\alpha}{n} FL(S) + (1 - \alpha) \sum_{t \in S} w(t)$$
với $\alpha \in [0, 1]$, $n = |T| \ge 1$, $w(t) \ge 0$, là hàm tập không âm, đơn điệu tăng và submodular trên $2^T$.

**Chứng minh**:
1. **Tính không âm**:
   Từ Mệnh đề 1 và 2, $FL(S) \ge 0$ và $\sum_{t \in S} w(t) \ge 0$. Vì $\alpha \in [0, 1]$ và $n \ge 1$, các hệ số $\frac{\alpha}{n} \ge 0$ và $(1 - \alpha) \ge 0$.
   Do đó $F_N(S) \ge 0, \forall S \subseteq T$, và $F_N(\emptyset) = 0$.

2. **Tính đơn điệu**:
   Tổ hợp tuyến tính với các hệ số không âm của các hàm đơn điệu là một hàm đơn điệu:
   Với $A \subseteq B \subseteq T$:
   $$F_N(B) - F_N(A) = \frac{\alpha}{n} \underbrace{\Big(FL(B) - FL(A)\Big)}_{\ge 0} + (1 - \alpha) \underbrace{\sum_{t \in B \setminus A} w(t)}_{\ge 0} \ge 0$$
   Suy ra $F_N(A) \le F_N(B)$.

3. **Tính Submodular**:
   Lượng tăng biên của $x \notin S$ đối với $F_N(S)$ là:
   $$\Delta_{F_N}(x \mid S) = \frac{\alpha}{n} \Delta_{FL}(x \mid S) + (1 - \alpha) w(x)$$
   Xét $A \subseteq B \subseteq T$ và $x \notin B$. Hiệu hai lượng tăng biên là:
   $$\Delta_{F_N}(x \mid A) - \Delta_{F_N}(x \mid B) = \frac{\alpha}{n} \Big(\Delta_{FL}(x \mid A) - \Delta_{FL}(x \mid B)\Big) + (1 - \alpha) \Big(w(x) - w(x)\Big)$$
   Số hạng modular triệt tiêu hoàn toàn: $(1 - \alpha)(w(x) - w(x)) = 0$.
   Do đó:
   $$\Delta_{F_N}(x \mid A) - \Delta_{F_N}(x \mid B) = \frac{\alpha}{n} \Big(\Delta_{FL}(x \mid A) - \Delta_{FL}(x \mid B)\Big)$$
   Từ Mệnh đề 2, $\Delta_{FL}(x \mid A) \ge \Delta_{FL}(x \mid B)$, và vì $\frac{\alpha}{n} \ge 0$, ta có:
   $$\Delta_{F_N}(x \mid A) - \Delta_{F_N}(x \mid B) \ge 0 \iff \Delta_{F_N}(x \mid A) \ge \Delta_{F_N}(x \mid B)$$
   Vậy $F_N(S)$ là hàm monotone submodular. Kết quả tương tự áp dụng chính xác cho hàm thô $F_{raw}(S)$. $\blacksquare$

---

### Mệnh đề 4: Bảo đảm Cận Xấp xỉ $(1 - 1/e)$ của Thuật toán Tham lam Cardinality

**Phát biểu**: Cho hàm mục tiêu $F: 2^T \to \mathbb{R}_{\ge 0}$ là monotone submodular với $F(\emptyset) = 0$. Thuật toán Cardinality Greedy bắt đầu từ $S_0 = \emptyset$ và lần lượt chọn phần tử cực đại hóa lượng tăng biên tại mỗi bước $i = 0, \dots, k-1$:
$$x_{i+1} \in \arg\max_{x \notin S_i} \Delta_F(x \mid S_i), \quad S_{i+1} = S_i \cup \{x_{i+1}\}$$
Khi đó, với mọi ngân sách $k \ge 1$, tập nghiệm $S_k$ thỏa mãn:
$$F(S_k) \ge \left[1 - \left(1 - \frac{1}{k}\right)^k\right] F(O) \ge \left(1 - \frac{1}{e}\right) F(O) \approx 0.63212 \cdot F(O)$$
trong đó $O \in \arg\max_{|S| \le k} F(S)$ là tập nghiệm tối ưu toàn cục kích thước $k$.

**Chứng minh**:
1. **Đánh giá khoảng cách thiếu hụt (Deficit)**:
   Đặt $R_i = F(O) - F(S_i)$ là độ thiếu hụt mục tiêu tại bước $i$.
   Vì $O \subseteq S_i \cup O$, tính đơn điệu của $F$ cho ta $F(O) \le F(S_i \cup O)$, suy ra:
   $$R_i \le F(S_i \cup O) - F(S_i)$$
   Biểu diễn tập $O \setminus S_i = \{o_1, o_2, \dots, o_r\}$ với $r = |O \setminus S_i| \le |O| \le k$.
   Đặt dãy tập kính thiên văn (telescoping sets): $A_0 = S_i$, và $A_j = S_i \cup \{o_1, \dots, o_j\}$ với $j = 1, \dots, r$.
   Khai triển hiệu giá trị hàm mục tiêu thành chuỗi tổng:
   $$F(S_i \cup O) - F(S_i) = \sum_{j=1}^r \Big(F(A_j) - F(A_{j-1})\Big) = \sum_{j=1}^r \Delta_F(o_j \mid A_{j-1})$$
   Vì $S_i = A_0 \subseteq A_{j-1}$ với mọi $j \ge 1$, áp dụng tính submodular của $F$:
   $$\Delta_F(o_j \mid A_{j-1}) \le \Delta_F(o_j \mid S_i)$$
   Do đó:
   $$R_i \le \sum_{j=1}^r \Delta_F(o_j \mid S_i)$$

2. **Ưu thế của bước chọn Greedy**:
   Gọi $g_i = \Delta_F(x_{i+1} \mid S_i) = F(S_{i+1}) - F(S_i)$ là lượng tăng biên tối đa mà greedy thu được ở bước $i$.
   Theo quy tắc chọn của greedy, $g_i \ge \Delta_F(x \mid S_i)$ với mọi $x \notin S_i$, do đó:
   $$\Delta_F(o_j \mid S_i) \le g_i, \quad \forall j \in \{1, \dots, r\}$$
   Thay vào bất đẳng thức độ thiếu hụt:
   $$R_i \le \sum_{j=1}^r g_i = r \cdot g_i \le k \cdot g_i \implies g_i \ge \frac{R_i}{k}$$

3. **Hệ thức truy hồi thu hẹp độ thiếu hụt**:
   Độ thiếu hụt tại bước $i+1$ là:
   $$R_{i+1} = F(O) - F(S_{i+1}) = F(O) - F(S_i) - g_i = R_i - g_i \le R_i - \frac{R_i}{k} = \left(1 - \frac{1}{k}\right) R_i$$
   Áp dụng liên tiếp hệ thức truy hồi này qua $k$ bước từ $S_0 = \emptyset$:
   $$R_k \le \left(1 - \frac{1}{k}\right)^k R_0$$
   Vì $S_0 = \emptyset$ và $F(\emptyset) = 0$, ta có $R_0 = F(O) - F(\emptyset) = F(O)$. Do đó:
   $$F(O) - F(S_k) \le \left(1 - \frac{1}{k}\right)^k F(O) \iff F(S_k) \ge \left[1 - \left(1 - \frac{1}{k}\right)^k\right] F(O)$$

4. **Cận tiệm cận qua hằng số Euler $e$**:
   Xét hàm số $g(x) = \ln(1 - x) + x$ với $x \in (0, 1)$.
   Ta có $g(0) = 0$ và đạo hàm $g'(x) = -\frac{1}{1-x} + 1 = -\frac{x}{1-x} < 0, \forall x \in (0, 1)$.
   Do đó $g(x) \le 0 \implies \ln(1 - x) \le -x$.
   Đặt $x = 1/k$ với $k \ge 1$:
   $$\ln\left(1 - \frac{1}{k}\right) \le -\frac{1}{k} \iff k \ln\left(1 - \frac{1}{k}\right) \le -1 \iff \left(1 - \frac{1}{k}\right)^k \le e^{-1} = \frac{1}{e}$$
   Suy ra:
   $$1 - \left(1 - \frac{1}{k}\right)^k \ge 1 - \frac{1}{e} \approx 0.632120558$$
   Với các giá trị $k$ hữu hạn nhỏ, cận thực tế còn chặt chẽ hơn:
   - $k = 1$: $1 - (1 - 1)^1 = 1.0$ (Tối ưu tuyệt đối).
   - $k = 2$: $1 - (1 - 1/2)^2 = 0.7500$.
   - $k = 3$: $1 - (1 - 1/3)^3 = 19/27 \approx 0.7037$.
   - Khi $k \to \infty$, giá trị hội tụ về $1 - 1/e$. $\blacksquare$

---

### Mệnh đề 5: Tính Đúng đắn và Tương đương Toán học của Lazy Greedy

**Phát biểu**: Dưới cùng một quy tắc giải hòa tie-breaking (FQN tăng dần), thuật toán Lazy Greedy (`hc_falcon/greedy.py`, `lazy=True`) sinh ra hoán vị hoàn toàn đồng nhất với thuật toán Standard Greedy (`lazy=False`).

**Chứng minh**:
1. **Bất biến Cận trên (Upper Bound Invariant)**:
   Lazy Greedy duy trì một hàng đợi ưu tiên (Priority Queue / Min-Heap theo khóa đối ngẫu âm) lưu các phần tử $(-\hat{g}_i, \text{id}_i, i, \text{stamp}_i)$, trong đó $\hat{g}_i = \Delta_F(i \mid S_{\text{stamp}_i})$ là lượng tăng biên của $i$ được tính tại trạng thái tập đã chọn $S_{\text{stamp}_i}$ (với $\text{stamp}_i \le |S_{\text{current}}|$).
   Vì $S_{\text{stamp}_i} \subseteq S_{\text{current}}$, theo tính chất submodular của $F$:
   $$\hat{g}_i = \Delta_F(i \mid S_{\text{stamp}_i}) \ge \Delta_F(i \mid S_{\text{current}})$$
   Do đó, khóa $\hat{g}_i$ trong hàng đợi luôn là một **cận trên hợp lệ** của lượng tăng biên thực tế hiện tại.

2. **Điều kiện Dừng Tối ưu**:
   Tại mỗi bước, thuật toán lấy phần tử $x^*$ có cận trên $\hat{g}_{x^*}$ lớn nhất từ đỉnh heap.
   - Nếu $\text{stamp}_{x^*} == |S_{\text{current}}|$, giá trị $\hat{g}_{x^*}$ vừa được tính toán trực tiếp trên chính tập hiện tại $S_{\text{current}}$, nghĩa là:
     $$\Delta_F(x^* \mid S_{\text{current}}) = \hat{g}_{x^*}$$
   - Vì $x^*$ đứng đầu heap, cận trên của nó lớn hơn hoặc bằng cận trên của mọi phần tử $y$ còn lại trong heap:
     $$\hat{g}_{x^*} \ge \hat{g}_y, \quad \forall y \in \text{remaining}$$
   - Kết hợp với bất biến cận trên của các phần tử $y$:
     $$\Delta_F(x^* \mid S_{\text{current}}) = \hat{g}_{x^*} \ge \hat{g}_y \ge \Delta_F(y \mid S_{\text{current}}), \quad \forall y \in \text{remaining}$$
   Bất đẳng thức trên chứng minh phần tử $x^*$ chính là phần tử cực đại hóa lượng tăng biên hiện tại mà **không cần phải tái tính toán** giá trị biên của các phần tử $y$ còn lại.
   Do đó, tập được chọn tại mỗi bước của Lazy Greedy trùng khớp 100% với Standard Greedy. $\blacksquare$

---

## 3. Ranh giới Lý thuyết và Các Phản ví dụ Hình thức

---

### 3.1. Phản ví dụ 1: Cận $1 - 1/e$ của Hàm Mục tiêu KHÔNG Bảo đảm Hiệu quả Phát hiện Lỗi (APFD / APFDc)

Một ngộ nhận phổ biến là bảo đảm tiệm cận $1 - 1/e$ của hàm mục tiêu $F(S)$ sẽ chuyển hóa thành bảo đảm cho metric phát hiện lỗi APFD. Phản ví dụ sau chứng minh điều này hoàn toàn sai lệch:

**Phản ví dụ**:
- Xét suite gồm $n$ tests: $T = \{t_1, t_2, \dots, t_n\}$ với $n \ge 100$.
- Giả sử ma trận tương đồng là đồng nhất hoàn toàn: $K(u, t) = 1.0, \forall u, t \in T$.
- Thiết lập trọng số lịch sử bằng 0: $q(t) = 0, \forall t$, và chọn $\alpha = 1.0$.
- Khi đó, với bất kỳ tập đơn tử nào $S = \{t_i\}$, độ bao phủ đạt giá trị cực đại tuyệt đối ngay từ bước đầu tiên:
  $$FL(\{t_i\}) = \sum_{u \in T} 1.0 = n \implies F(\{t_i\}) = \frac{n}{n} = 1.0$$
  Do $F(O) \le 1.0$, nên mọi tập đơn tử đều đạt **100% giá trị tối ưu** ($F(S_1) = F(O) = 1.0 \ge (1 - 1/e) F(O)$).
- Giả sử trong toàn bộ suite chỉ có duy nhất 1 test case $t^*$ phát hiện lỗi ($m = 1$).
- Theo quy tắc giải hòa tie-breaking theo thứ tự từ điển FQN tăng dần (`hc_falcon/greedy.py`), nếu $t^*$ có tên định danh lớn nhất (ví dụ `zzz.Test`), greedy sẽ chọn $t^*$ ở bước cuối cùng ($n$).
- Khi đó, chỉ số APFD thực tế đạt được là:
  $$\text{APFD} = 1 - \frac{n}{n \cdot 1} + \frac{1}{2n} = \frac{1}{2n} \xrightarrow{n \to \infty} 0$$
- **Kết luận**: Nghiệm greedy đạt xấp xỉ mục tiêu hoàn hảo $F(S) = F(O) = 1.0$, nhưng APFD thực tế tiệm cận 0. Hàm mục tiêu $F$ chỉ đóng vai trò là một heuristic gián tiếp (proxy) nhằm tăng tốc độ đa dạng hóa kiểm thử, hoàn toàn không có bảo đảm toán học trực tiếp nào cho APFD, APFDc hay TTFF.

---

### 3.2. Phản ví dụ 2: Ràng buộc Cardinality Thất bại Hoàn toàn dưới Ràng buộc Ngân sách Thời gian (Knapsack Time Budget)

Thuật toán Cardinality Greedy tối ưu hóa dưới ràng buộc số lượng test $|S| \le k$, trong khi bài toán CI thực tế bị giới hạn bởi tổng thời gian thực thi: $\sum_{t \in S} C_t \le B$.

**Phản ví dụ**:
- Xét ngân sách thời gian $B > 1$ (giả sử $B = 100$ giây).
- Bộ test gồm:
  - 1 test chạy cực nặng $t_{long}$: thời gian chạy $C(t_{long}) = B = 100\text{s}$, mang lại giá trị mục tiêu $F(\{t_{long}\}) = 1 + \delta$ (với $0 < \delta < 1$).
  - $B$ tests chạy cực nhanh $\{t_1, \dots, t_B\}$: mỗi test chạy $C(t_i) = 1\text{s}$, mỗi test mang lại giá trị $F(\{t_i\}) = 1$ (các test độc lập).
- Thuật toán Cardinality Greedy chỉ quan sát lượng tăng biên thuần túy:
  $$\Delta_F(t_{long} \mid \emptyset) = 1 + \delta > 1 = \Delta_F(t_i \mid \emptyset)$$
  Do đó, Greedy chọn $t_{long}$ ngay ở bước 1.
- Sau khi chọn $t_{long}$, tổng thời gian chạy đạt $100\text{s} = B$, cạn kiệt toàn bộ ngân sách. Thuật toán phải dừng lại với tổng giá trị thu được là $1 + \delta$.
- Trong khi đó, nghiệm knapsack tối ưu sẽ chọn toàn bộ $B$ test ngắn, tiêu tốn đúng $B \times 1\text{s} = 100\text{s}$, đạt tổng giá trị là $B = 100$.
- Tỷ số xấp xỉ thực tế:
  $$\frac{F(S_{\text{greedy}})}{F(O)} = \frac{1 + \delta}{B} \xrightarrow{B \to \infty} 0$$
- **Ý nghĩa**: Điều này giải thích chính xác hiện tượng **"Heavy Predecessors"** phát hiện trong phân tích Forensic ở Stage 11: thuật toán greedy nguyên bản đưa các test nặng hàng trăm giây lên đầu suite chỉ vì lợi ích ngữ nghĩa nhỉnh hơn một chút, tiêu tốn hết ngân sách thời gian ban đầu và gây trễ lũy kế hàng chục ngàn giây cho các test phát hiện lỗi phía sau.

---

## 4. Phân tích Độ phức tạp Thuật toán (Complexity Analysis)

### 4.1. Độ phức tạp Thời gian (Time Complexity)

| Giai đoạn Thực thi | Thuật toán / Thành phần | Độ phức tạp tiệm cận | Diễn giải chi tiết |
|---|---|:---:|---|
| **1. Mã hóa Ngữ nghĩa** | UniXcoder Inference | $O(n \cdot C_{\max} \cdot L_{\max}^2 \cdot d)$ | Với $C_{\max} \le 16$, $L_{\max} = 512$, $d = 768$. Tuyến tính theo số test $n$. Hoàn toàn tái sử dụng qua cache SHA-256. |
| **2. Ma trận Tương đồng** | Dense Dot-product Kernel | $O(n^2 \cdot d)$ | Nhân ma trận embedding $(n \times d) \times (d \times n)$. Với $n = 2{,}193$ (Chart), tốn $\approx 3.7 \times 10^9$ phép tính FLOPs ($< 0.1$s trên CPU). |
| **3. Lịch sử Rolling** | Beta-Bernoulli Update | $O(n)$ | Cập nhật thống kê $f_t, n_t$ từ ledger lịch sử; tuyến tính theo inventory. |
| **4A. Standard Greedy** | `greedy.py` (`lazy=False`) | $O(k \cdot n^2) \xrightarrow{k=n} O(n^3)$ | Tại bước $i$, duyệt qua $(n - i)$ ứng viên; mỗi ứng viên quét $n$ phần tử của hàng ma trận. Tổng số phép tính: $\sum_{i=1}^n (n - i) n \approx \frac{1}{2} n^3$. |
| **4B. Lazy Greedy** | `greedy.py` (`lazy=True`) | $O(n^2 \log n)$ kỳ vọng<br>$O(n^3)$ xấu nhất | Khởi tạo heap tốn $O(n^2 + n)$. Mỗi bước pop tốn $O(\log n)$. Số lượt tái tính toán $R \ll n^2$. Thực tế trên 6 dự án Defects4J chạy trong vài giây. |

### 4.2. Độ phức tạp Không gian (Space Complexity)

| Thành phần Dữ liệu | Kích thước mảng | Kiểu dữ liệu | Bộ nhớ thực tế ($n = 2{,}193$ - Chart) | Bộ nhớ thực tế ($n = 8{,}006$ - Closure) |
|---|---|:---:|---:|---:|
| **Embedding Matrix** | $n \times 768$ | `float32` | $2{,}193 \times 768 \times 4\text{ B} \approx \mathbf{6.73\text{ MB}}$ | $8{,}006 \times 768 \times 4\text{ B} \approx \mathbf{24.59\text{ MB}}$ |
| **Similarity Kernel $K$** | $n \times n$ | `float32` | $2{,}193^2 \times 4\text{ B} \approx \mathbf{18.35\text{ MB}}$ | $8{,}006^2 \times 4\text{ B} \approx \mathbf{244.57\text{ MB}}$ |
| **Coverage State Array** | $n$ | `float64` | $2{,}193 \times 8\text{ B} \approx 17.5\text{ KB}$ | $8{,}006 \times 8\text{ B} \approx 64.0\text{ KB}$ |
| **Modular Weights $w$** | $n$ | `float64` | $17.5\text{ KB}$ | $64.0\text{ KB}$ |
| **Lazy Greedy Heap** | $n$ tuples | Object refs | $\approx 70\text{ KB}$ | $\approx 256\text{ KB}$ |
| **Tổng Đỉnh RAM (Lý thuyết)** | — | — | $\approx \mathbf{25.2\text{ MB}}$ | $\approx \mathbf{269.5\text{ MB}}$ |
| **Đỉnh RAM Đo đạc Thực tế** | Toàn bộ tiến trình Python | WorkingSet | **1.130 GiB** | **1.643 GiB** |

*Ghi chú*: Đỉnh RAM đo đạc thực tế ($\le 1.643$ GiB) phần lớn đến từ không gian nạp PyTorch runtime, bộ nhớ đệm Transformers và trình phân giải Python AST, hoàn toàn nằm trong giới hạn an toàn 8.0 GiB đã khóa của đề tài.

---

## 5. Phân tích Lý thuyết Biến thể CNS-Greedy (Phase 3)

Trong nỗ lực khắc phục hiện tượng Heavy Predecessors, biến thể **Cost-Normalized Semantic Greedy (CNS-Greedy)** (`hc_falcon/variants.py`) được thiết kế:

$$\text{gain}_{\text{CNS}}(x \mid S) = \alpha \frac{\Delta_{FL}(x \mid S) / n}{\sqrt{\max(c(x), 10^{-6})}} + (1 - \alpha) w(x)$$

### 5.1. Sự Phá vỡ Tính Chất Submodular Toàn cục

Hàm mục tiêu ngầm định tương ứng với tỷ số trên là:
$$F_{\text{CNS}}(S) = \sum_{t \in S} \Delta_{FL}(t \mid S_{< t}) \cdot \frac{1}{\sqrt{c(t)}} + \dots$$
Do mẫu số $\sqrt{c(x)}$ gắn liền với từng phần tử riêng lẻ $x$, phép chia này **phá vỡ cấu trúc submodular chuẩn**:
- Xét hai phần tử $x_1, x_2$ có cùng $\Delta_{FL}$ nhưng $c(x_1) \ll c(x_2)$. Tỷ số ưu tiên $x_1$ áp đảo hoàn toàn.
- Tuy nhiên, khi xét hàm tập tổng thể, phép chuẩn hóa chi phí trên từng bước tham lam biến bài toán thành dạng Knapsack Submodular Heuristic.
- Do đó, **CNS-Greedy không còn được bảo vệ bởi định lý Nemhauser $1 - 1/e$**, mà thuộc lớp thuật toán xấp xỉ heuristic cục bộ (Greedy Benefit-to-Cost Ratio).

### 5.2. Kết luận Lý thuyết cho CNS-Greedy

Mặc dù CNS-Greedy giải quyết triệt để cơ chế trễ thứ nguyên (kéo Mean delta từ âm sang dương $+1.7\%$ đến $+3.5\%$), sự biến thiên chi phí quá lớn ở mức class (từ $0.001$s đến $150$s) khiến việc chuẩn hóa $\sqrt{c}$ vẫn không đủ để vượt qua tín hiệu lịch sử $q(t)$ ở mức trung vị (Median delta vẫn âm: $-0.19\%$ đến $-0.61\%$).
