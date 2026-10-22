# Thuật toán và lý thuyết cho Đề tài 1

## 1. Mục đích

Tài liệu này đặc tả phần hình thức của FALCON và mô hình HC-FALCON đề xuất:
ký hiệu, metric, embedding, facility location, lịch sử, cost, chứng minh
submodular, thuật toán greedy/lazy greedy, rolling evaluation và phân tích độ
phức tạp. Bối cảnh và phần đọc hiểu paper nằm tại
[Đọc hiểu Đề tài 1](./doc-hieu-de-tai.md).

Những công thức mang nhãn **đề xuất** chưa phải kết luận của FALCON hoặc DANTE và
phải được đánh giá bằng thực nghiệm.

## 2. Ký hiệu

| Ký hiệu | Ý nghĩa |
| --- | --- |
| $b$ | chỉ số build hiện tại |
| $T_b$ | tập test tồn tại ở đầu build $b$ |
| $n_b=\lvert T_b\rvert$ | số test trong build $b$ |
| $t,u,x$ | một test case/test method |
| $z_b(t)$ | embedding của mã nguồn test $t$ |
| $w_b(u,t)$ | similarity không âm giữa $u$ và $t$ |
| $S\subseteq T_b$ | tập test đã chọn |
| $\pi_b$ | thứ tự đầy đủ của $T_b$ |
| $p_b(t)$ | rủi ro fail ước lượng chỉ từ dữ liệu trước $b$ |
| $r_b(t)$ | độ tin cậy của ước lượng lịch sử |
| $\widehat c_b(t)$ | duration dự báo từ dữ liệu trước $b$ |
| $q_b(t)$ | trọng số history–cost không âm |
| $\lambda$ | trọng số semantic, $0\leq\lambda\leq1$ |

Không dùng cùng một ký hiệu cho duration dự báo và duration quan sát. Có thể ký
hiệu duration ground truth sau khi chạy build là $c_b^{obs}(t)$.

## 3. Bài toán Test Case Prioritization

Cho tập test $T_b$, gọi $\Pi(T_b)$ là tập mọi hoán vị của nó. TCP tìm:

$$
\pi_b^* = \arg\max_{\pi\in\Pi(T_b)} g_b(\pi),
$$

trong đó $g_b$ là mục tiêu đánh giá thứ tự. Vì fault của build $b$ chưa biết
tại thời điểm ranking, APFD/APFDc không thể được dùng trực tiếp làm $g_b$. Ta
tối ưu một surrogate có thể tính trước khi chạy test và dùng APFD/APFDc để đánh
giá hậu nghiệm.

## 4. Metric đánh giá

### 4.1. APFD

Giả sử thứ tự có $n$ test và ground truth có $m>0$ fault. Gọi $TF_i$ là vị
trí, đánh số từ 1, của test đầu tiên phát hiện fault $i$. Khi mọi fault đều được
phát hiện trong suite:

$$
APFD = 1 - \frac{\sum_{i=1}^{m} TF_i}{nm} + \frac{1}{2n}.
$$

Nếu một fault không được test nào phát hiện, protocol phải quy định rõ: loại
fault khỏi tập đánh giá hoặc dùng một metric có xử lý fault không phát hiện.
Không được để phép `min` trên tập rỗng quyết định ngầm hành vi.

### 4.2. APFDc

Gọi $c_j>0$ là duration quan sát của test ở vị trí $j$,
$C=\sum_{j=1}^{n}c_j$. Một dạng cost-cognizant chuẩn là:

$$
APFDc =
\frac{1}{mC}
\sum_{i=1}^{m}
\left(\sum_{j=TF_i}^{n}c_j - \frac{1}{2}c_{TF_i}\right).
$$

Dạng tương đương:

$$
APFDc = 1-
\frac{1}{mC}
\sum_{i=1}^{m}
\left(\sum_{j=1}^{TF_i-1}c_j+\frac{1}{2}c_{TF_i}\right).
$$

Số hạng nửa duration phụ thuộc test phát hiện fault; không thể thay bằng hằng số
$1/(2C)$ khi duration khác nhau. Khi mọi $c_j=1$, APFDc rút gọn về APFD.

### 4.3. TTFF và budget recall

Nếu $TF_{first}$ là vị trí failure đầu tiên:

$$
TTFF = \sum_{j=1}^{TF_{first}-1} c_j + \theta c_{TF_{first}},
$$

với $\theta=1$ nếu chỉ quan sát verdict sau khi test kết thúc. Budget recall tại
ngân sách $\tau C$ là tỷ lệ fault hoặc failing test được phát hiện trước khi chi
phí tích lũy vượt $\tau C$. Cần cố định rõ đơn vị là fault hay failing test.

Build không có failure không có APFD/APFDc/TTFF hữu hạn theo nghĩa phát hiện lỗi;
nó vẫn phải được dùng để cập nhật lịch sử.

## 5. Biểu diễn ngữ nghĩa

### 5.1. Embedding và pooling

Với chuỗi token của test $t$, encoder trả về hidden state $h_1,\ldots,h_L$.
Masked mean pooling là:

$$
z(t)=\frac{\sum_{j=1}^{L}a_jh_j}{\sum_{j=1}^{L}a_j},
$$

trong đó $a_j\in\{0,1\}$ là attention mask. Padding không được tham gia trung
bình. Nếu model quy định token đặc biệt hoặc pooling riêng, implementation phải
theo model card/artifact thay vì mặc định mean pooling.

### 5.2. Cosine similarity

$$
s_{cos}(u,t)=\frac{z(u)^Tz(t)}{\|z(u)\|_2\|z(t)\|_2}.
$$

Sau khi chuẩn hóa từng hàng $\widehat z(t)=z(t)/\|z(t)\|_2$, với ma trận
$\widehat Z\in\mathbb R^{n\times d}$:

$$
S=\widehat Z\widehat Z^T.
$$

Để dùng quy ước $FL(\varnothing)=0$ và bảo đảm trọng số không âm, định nghĩa:

$$
w(u,t)=\max\{0,s_{cos}(u,t)\}.
$$

Một lựa chọn khác là ánh xạ $(s_{cos}+1)/2$, nhưng nó thay đổi hình học của
objective và phải được xem như một biến thể thực nghiệm.

### 5.3. Chi phí tính similarity

Tính ma trận đặc cần $O(n^2d)$ phép toán và $O(n^2)$ bộ nhớ. Với $n=8000$,
$d=768$, phép GEMM xấp xỉ:

$$
2n^2d = 98{,}304{,}000{,}000 \approx 9.83\times10^{10}
$$

floating-point operations. Một ma trận $8000\times8000$ tốn xấp xỉ 256 MB ở
float32 hoặc 128 MB ở float16, chưa tính embedding, workspace và bản sao CPU/GPU.
Runtime phải đo trên phần cứng thật; không suy ra trực tiếp từ FLOP lý thuyết.

Content-addressed cache có thể khóa theo:

$$
key=SHA256(source\_code\parallel model\_id\parallel tokenizer\_id
\parallel max\_length\parallel pooling\_version).
$$

Chỉ hash source code là chưa đủ khi model hoặc preprocessing thay đổi.

## 6. Hàm facility location

Với $S\subseteq T_b$, đặt:

$$
FL_b(S)=\sum_{u\in T_b}\max_{t\in S}w_b(u,t),
\qquad FL_b(\varnothing)=0.
$$

Đặt coverage hiện tại của $u$:

$$
m_S(u)=\max_{s\in S}w_b(u,s),\qquad m_\varnothing(u)=0.
$$

Marginal gain khi thêm $x\notin S$:

$$
\Delta_{FL}(x\mid S)
=\sum_{u\in T_b}\max\{0,w_b(u,x)-m_S(u)\}.
$$

### 6.1. Chứng minh monotone

Vì mỗi số hạng trong marginal gain không âm:

$$
\Delta_{FL}(x\mid S)\geq0.
$$

Do đó thêm một test không làm giảm $FL_b$; hàm là monotone non-decreasing.

### 6.2. Chứng minh submodular

Cho $A\subseteq B\subseteq T_b$ và $x\notin B$. Khi đó
$m_A(u)\leq m_B(u)$ với mọi $u$. Suy ra:

$$
\max\{0,w(u,x)-m_A(u)\}
\geq
\max\{0,w(u,x)-m_B(u)\}.
$$

Cộng theo mọi $u$:

$$
\Delta_{FL}(x\mid A)\geq\Delta_{FL}(x\mid B).
$$

Đây là tính diminishing returns, nên $FL_b$ là submodular.

## 7. Greedy và bảo đảm xấp xỉ

Với ngân sách cardinality $k$:

$$
\max_{S\subseteq T_b,\ |S|\leq k} f(S).
$$

Nếu $f$ normalized ($f(\varnothing)=0$), monotone và submodular, greedy chọn
phần tử có marginal gain lớn nhất ở mỗi bước thỏa:

$$
f(S_k)\geq\left(1-\left(1-\frac1k\right)^k\right)f(S_k^*)
\geq(1-1/e)f(S_k^*).
$$

Bảo đảm áp dụng cho cardinality constraint. Nếu ràng buộc trực tiếp là tổng
duration (knapsack), greedy thuần theo marginal gain không tự động có cùng bảo
đảm; cần thuật toán knapsack-submodular thích hợp.

Chạy greedy đến $n$ bước tạo một hoán vị. Mỗi prefix $k$ chính là kết quả của
cùng quá trình greedy dừng ở bước $k$, nếu tie-breaking được giữ nhất quán.

## 8. Mô hình hóa lịch sử

### 8.1. Nguyên tắc thời gian

Đặt lịch sử khả dụng trước build $b$:

$$
H_{b-1}=\{(y_j(t),c_j^{obs}(t)):j<b\},
$$

trong đó $y_j(t)\in\{0,1\}$. Mọi $p_b(t),r_b(t),\widehat c_b(t)$ phải là hàm
của $H_{b-1}$, không phải $H_b$.

### 8.2. Các estimator ứng viên

Tỷ lệ fail dài hạn có smoothing Beta–Bernoulli:

$$
p_b^{BB}(t)=\frac{N_{fail,b-1}(t)+a}
{N_{exec,b-1}(t)+a+b_0},
$$

với prior $Beta(a,b_0)$. Dùng ký hiệu $b_0$ để không nhầm với build $b$.

Estimator decay theo độ cũ:

$$
p_b^{decay}(t)=
\frac{\sum_{j<b}\rho^{b-1-j}I[t\text{ chạy ở }j]y_j(t)}
{\sum_{j<b}\rho^{b-1-j}I[t\text{ chạy ở }j]},
\qquad 0<\rho\leq1.
$$

Nếu mẫu số bằng 0, dùng prior/cold-start rule đã khai báo trước.

Failure stickiness cần được đặc tả từ paper/artifact DANTE bằng các biến cố và
cửa sổ chính xác. Không thay thế nó bằng `mean(recent_buffer)` mà vẫn gọi cùng
tên, vì recent failure rate không đo xác suất chuyển tiếp có điều kiện.

### 8.3. Wilson confidence

Với $\widehat p=x/n$, $n>0$, và quantile $z$, Wilson interval là:

$$
center=\frac{\widehat p+z^2/(2n)}{1+z^2/n},
$$

$$
half=\frac{z}{1+z^2/n}
\sqrt{\frac{\widehat p(1-\widehat p)}{n}+\frac{z^2}{4n^2}},
$$

$$
[L,U]=[center-half,center+half].
$$

Một confidence heuristic có thể là:

$$
r_b(t)=\max\{0,1-(U-L)\}.
$$

Đây là phép biến đổi độ rộng interval thành trọng số, không phải bản thân xác
suất thống kê. Cần ablation và calibration trước khi khẳng định nó tối ưu.

### 8.4. Duration dự báo

Ví dụ estimator causal:

$$
\widehat c_b(t)=median\{c_j^{obs}(t):j<b,\ t\text{ chạy ở }j\}.
$$

Median hoặc exponentially weighted mean thường bền vững hơn mean trước outlier.
Test mới cần fallback như median của suite/class, không được dùng duration quan
sát của build $b$.

## 9. Điểm history–cost

### 9.1. Dạng đề xuất ban đầu

Đề xuất ban đầu của Đề tài 1 là:

$$
q_b(t)=\frac{r_b(t)p_b(t)}{\sqrt{\widetilde c_b(t)}+\varepsilon}.
$$

Với $r_b,p_b,\widetilde c_b\geq0$ và $\varepsilon>0$, ta có $q_b(t)\geq0$.
Tuy nhiên, min–max normalization tạo $\widetilde c=0$ cho test nhanh nhất; khi
$\varepsilon$ rất nhỏ, điểm có thể bùng nổ.

### 9.2. Dạng ổn định nên khảo sát

Một họ an toàn hơn là:

$$
q_b(t)=\frac{r_b(t)p_b(t)}{(\delta+\widetilde c_b(t))^\gamma},
\qquad \delta>0,\quad0\leq\gamma\leq1,
$$

và chặn/scale robust:

$$
\bar q_b(t)=\min\left\{1,
\frac{q_b(t)}{Q_{1-\eta}(\{q_b(u):u\in T_b\})+\varepsilon}
\right\}.
$$

Quantile được tính từ feature khả dụng trước execution nên không gây label
leakage. $\delta,\gamma,\eta$ phải được chọn trên validation project/build, không
trên test builds.

## 10. Hàm mục tiêu HC-FALCON

### 10.1. Dạng cơ sở

$$
F_b(S)=
\lambda\frac{FL_b(S)}{n_b}
+(1-\lambda)H_b(S),
$$

trong đó:

$$
H_b(S)=\sum_{t\in S}\bar q_b(t).
$$

Chia $FL$ cho $n_b$ đưa semantic coverage về $[0,1]$, nhưng $H_b(S)$ có
thể tăng đến $|S|$. Vì vậy, $\lambda$ chưa tự động là tỷ lệ cân bằng có thể so
sánh giữa các ngân sách.

### 10.2. Hai lựa chọn scale cần đánh giá

Với ngân sách cố định $k$, có thể dùng:

$$
H_b^{(k)}(S)=\frac1k\sum_{t\in S}\bar q_b(t).
$$

Đây vẫn là modular vì $1/k$ là hằng số trong bài toán ngân sách $k$. Với một
hoán vị dùng cho mọi prefix, có thể scale từng trọng số bằng một hằng số suite:

$$
H_b^{suite}(S)=\frac{1}{Z_b}\sum_{t\in S}\bar q_b(t),
$$

với $Z_b>0$ được tính trước ranking, chẳng hạn tổng top-$k_0$ score theo một
ngân sách tham chiếu đã cố định. Không dùng mẫu số phụ thuộc $S$, như
$1/|S|$, nếu muốn giữ chứng minh modular đơn giản.

## 11. Chứng minh tính chất của HC-FALCON

### 11.1. Hạng history–cost là modular

Cho $A\subseteq B\subseteq T_b$, $x\notin B$. Khi $\bar q_b(x)$ được cố định
trước quá trình greedy:

$$
\Delta_H(x\mid A)=\bar q_b(x)=\Delta_H(x\mid B).
$$

Do marginal gain không phụ thuộc tập hiện tại, $H_b$ là modular, đồng thời vừa
submodular vừa supermodular. Vì $\bar q_b(x)\geq0$, $H_b$ là monotone.

### 11.2. Hàm hợp nhất là monotone submodular

Với $0\leq\lambda\leq1$:

$$
\Delta_F(x\mid S)=
\frac{\lambda}{n_b}\Delta_{FL}(x\mid S)
+(1-\lambda)\bar q_b(x).
$$

Cả hai số hạng không âm nên $F_b$ monotone. Với $A\subseteq B$:

$$
\Delta_{FL}(x\mid A)\geq\Delta_{FL}(x\mid B),
$$

còn modular gain bằng nhau. Nhân với hệ số không âm rồi cộng lại cho:

$$
\Delta_F(x\mid A)\geq\Delta_F(x\mid B).
$$

Vì vậy $F_b$ là monotone submodular và normalized nếu
$FL_b(\varnothing)=H_b(\varnothing)=0$.

### 11.3. Phạm vi của chứng minh

Chứng minh không còn áp dụng nguyên vẹn nếu:

- $q_b(t)$ được cập nhật dựa trên các test đã chọn;
- có trọng số âm;
- chuẩn hóa history dùng mẫu số phụ thuộc $S$;
- objective thêm penalty không chứng minh được submodular;
- duration của build hiện tại được tiết lộ trong quá trình ranking.

## 12. Standard greedy

```text
Input: similarity W, modular weights q, lambda
S <- empty
coverage[u] <- 0 for every u
order <- empty

while |S| < n:
    choose x not in S maximizing
        lambda/n * sum_u max(0, W[u,x] - coverage[u])
        + (1-lambda) * q[x]
    append x to order
    S <- S union {x}
    coverage <- elementwise_max(coverage, W[:,x])

return order
```

Nếu mỗi marginal gain duyệt $n$ hàng, standard greedy cho full order tính
$O(n^2)$ ứng viên, nên worst-case $O(n^3)$ thời gian sau khi đã có $W$.

## 13. Lazy greedy

### 13.1. Invariant

Do submodularity, marginal gain đã tính tại một tập cũ là upper bound của
marginal gain tại tập hiện tại. Max-heap lưu upper bound cùng phiên bản của tập
mà gain được tính.

### 13.2. Giả mã

```text
Input: W, q, lambda
coverage <- zeros(n)
order <- empty
heap <- empty max-heap

for each test x:
    gain <- lambda/n * sum_u W[u,x] + (1-lambda) * q[x]
    push(heap, x, gain, version=0)

for iteration = 0 .. n-1:
    loop:
        (x, bound, version) <- pop_max(heap)
        if version == iteration:
            append x to order
            coverage <- max(coverage, W[:,x])
            break

        semantic_gain <- sum_u max(0, W[u,x] - coverage[u])
        exact_gain <- lambda/n * semantic_gain + (1-lambda) * q[x]
        push(heap, x, exact_gain, version=iteration)

return order
```

Khi phần tử có gain chính xác ở trạng thái hiện tại trở lại đỉnh heap, mọi khóa
còn lại là upper bound không lớn hơn nó; phần tử đó là lựa chọn greedy hợp lệ.

Tie-breaking phải deterministic, ví dụ khóa phụ là `test_id`. Floating-point
comparison nên có tolerance được cố định và kiểm thử.

### 13.3. Độ phức tạp

- khởi tạo column sum: $O(n^2)$;
- mỗi lần recompute marginal: $O(n)$;
- heap operation: $O(\log n)$;
- bộ nhớ ma trận: $O(n^2)$;
- coverage, score và heap: $O(n)$.

Lazy greedy thường giảm mạnh số lần recompute, nhưng không có cam kết chung rằng
mọi dữ liệu đều đạt $O(n\log n)$ evaluations. Worst-case có thể vẫn gần standard
greedy. Do đó cần báo cáo số lần recompute, runtime và memory thực đo.

## 14. Rolling evaluation chống leakage

```text
state <- empty history H_0

for build b in chronological_order:
    suite <- tests available at start of build b
    semantic <- features available at start of build b
    history_features <- read_only(state)       # H_{b-1}
    predicted_costs <- estimate from state     # not observed cost of b

    order <- prioritize(suite, semantic, history_features, predicted_costs)
    metrics <- evaluate(order, outcomes_b, observed_costs_b)

    update(state, outcomes_b, observed_costs_b) # creates H_b
```

Các kiểm tra tự động tối thiểu:

- mọi timestamp feature nhỏ hơn timestamp target build;
- snapshot history bất biến trong lúc ranking;
- update chỉ xảy ra sau evaluation;
- test mới không có record được xử lý bằng cold-start rule;
- test vắng mặt ở một build không mặc định được ghi là pass;
- retry/flaky executions không bị gộp thành một verdict mà không có policy.

## 15. Edge cases

### 15.1. Test mới

Không có lịch sử: dùng prior cho $p_b$, confidence thấp và cost fallback. Nếu
$\lambda>0$, semantic vẫn có thể ưu tiên test mới. Với history-only, tie-breaking
phải được khai báo; không nên ngầm đẩy mọi test mới xuống cuối.

### 15.2. Duration bằng 0 hoặc âm

Duration âm là dữ liệu lỗi. Duration bằng 0 do độ phân giải đo phải được thay bởi
measurement floor trước normalization. Chỉ cộng epsilon cực nhỏ sau khi min–max
không đủ để ngăn score mất cân bằng.

### 15.3. Similarity NaN hoặc zero norm

Embedding zero norm/NaN phải bị phát hiện trước khi nhân ma trận. Có thể retry,
fallback embedding hoặc loại record với log rõ ràng; không âm thầm biến NaN về 0.

### 15.4. Không có fault

Không tính APFD/APFDc cho build không fault. Vẫn đo ranking overhead và cập nhật
pass/duration vào history.

### 15.5. Nhiều test phát hiện cùng fault

Dùng vị trí/chi phí sớm nhất. Nếu dataset chỉ có failing-test labels mà không có
fault identity, phải nói rõ metric đang đo tốc độ phát hiện failing tests, không
được gọi nhầm là fault-level APFD.

## 16. Ablation được ánh xạ vào công thức

| Biến thể | Semantic | History | Cost | Confidence |
| --- | ---: | ---: | ---: | ---: |
| Pure FALCON | có | không | không | không |
| History-only | không | có | không | có |
| History + cost | không | có | có | có |
| Semantic + history | có | có | không | có |
| HC-FALCON full | có | có | có | có |
| HC-FALCON no-conf | có | có | có | không |

Các biến thể phải dùng cùng tập test, build split, tie-breaking và metric code.
Nếu thay nhiều chi tiết cùng lúc, kết quả không còn cô lập đóng góp của thành phần.

## 17. Các kiểm chứng bắt buộc trước thực nghiệm lớn

1. Unit test APFD/APFDc bằng ví dụ tính tay.
2. So sánh standard greedy và lazy greedy: thứ tự phải giống nhau khi tie-break
   giống nhau.
3. Property test: marginal gain không âm và diminishing returns trên ma trận nhỏ.
4. Leakage test: thay outcome build $b$ không được làm thay order của chính
   build $b$.
5. Cold-start test cho test mới và suite chỉ có một test.
6. Numerical test cho zero duration, equal durations, zero-norm embedding và NaN.
7. Memory/runtime benchmark theo $n,d,dtype$, gồm cả peak memory.
8. Reproduction test cho ít nhất một cấu hình FALCON artifact trước khi mở rộng.

## 18. Những lựa chọn còn mở

- estimator history chính: Beta–Bernoulli, decay hay DANTE stickiness;
- định nghĩa confidence và cách calibration;
- duration estimator và fallback cho test mới;
- cách scale hạng modular so với facility location;
- $\lambda$ cố định, validation theo project hay adaptive nhưng causal;
- full matrix, block matrix hay approximate nearest neighbors;
- test-method hoặc test-class granularity;
- fault-level hay failing-test-level ground truth trên LRTS.

Mỗi lựa chọn phải được đóng băng trong config và lưu cùng kết quả để bảo đảm khả
năng tái lập.
