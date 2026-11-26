# Phân tích chi tiết Đề tài 1 — HC-FALCON

> Ưu tiên test case bằng tối ưu hóa submodular có xét lịch sử lỗi và thời gian chạy

Tài liệu này giải thích toàn bộ đề tài trong `topic1.md`: bài toán, kiến thức nền, paper nền (FALCON), các
công trình liên quan (LRTS, DANTE, FAST…), phương pháp cần xây dựng, phần lý thuyết, thiết kế thực nghiệm,
các rủi ro, và **lộ trình cụ thể bạn cần làm**.

Nguồn đã đọc: `topic1.md`, toàn văn `paper-topic1.pdf` (FALCON, ICST 2026), mã nguồn artifact FALCON trên
GitHub, toàn văn paper LRTS (ISSTA 2024), README artifact DANTE trên Zenodo. Riêng paper DANTE **chưa đọc được
toàn văn** (máy chủ chặn tải tự động) — phần về DANTE dựa trên abstract và README của artifact.

---

## 0. Tóm tắt một trang

**Đề tài muốn gì?** Trong CI/CD, mỗi lần code thay đổi phải chạy hàng nghìn test, mất hàng giờ. Ta không bỏ
test nào, chỉ **sắp xếp lại thứ tự chạy** sao cho test sắp fail chạy càng sớm càng tốt. Vậy dev biết có lỗi
sau vài phút chứ không phải vài giờ.

**Paper nền FALCON** sắp xếp test chỉ dựa trên **độ đa dạng ngữ nghĩa**. Nó biến mã nguồn test thành vector
(embedding bằng UniXcoder), rồi dùng **facility location**, một hàm submodular, cùng thuật toán **lazy greedy**
để chọn trước các test "đại diện cho những vùng khác nhau". FALCON **không dùng** lịch sử pass/fail và **không
dùng** thời gian chạy. Nó cũng chỉ được đánh giá trên Defects4J, không phải trên chuỗi build CI thật.

**Đề tài của bạn (HC-FALCON)** thêm vào hàm mục tiêu của FALCON một thành phần **modular** `q(t)`. Thành phần
này đo "xác suất fail × độ tin cậy ÷ √thời gian chạy":

```
F_b(S) = α · FL_b(S)/|T_b|  +  (1−α) · Σ_{t∈S} q_b(t)
```

Hàm này vẫn **monotone submodular**, nên greedy vẫn có bảo đảm (1−1/e). Bạn cần chứng minh điều đó, cài đặt
phương pháp, rồi đánh giá **tuần tự theo thời gian** trên dữ liệu CI thật (LRTS). Khi đánh giá phải tuyệt đối
không để dữ liệu tương lai rò rỉ vào. Đối thủ so sánh là FALCON, các heuristic lịch sử/thời gian và DANTE.

**Bạn phải bàn giao:** code và hướng dẫn tái lập, script rolling history và kiểm tra leakage, kết quả thô và
bảng/hình, chứng minh submodular kèm phân tích độ phức tạp, báo cáo hoặc bản thảo paper 6–10 trang, bảng
threats to validity.

**Ba điều quan trọng nhất cần biết ngay:**

1. **Defects4J (dữ liệu của FALCON) không có lịch sử build và không có thời gian chạy.** Vì vậy nó chỉ dùng để
   *tái lập FALCON*. Mọi đánh giá HC-FALCON thật sự phải chạy trên **LRTS**.
2. **Baseline đơn giản trên LRTS rất mạnh.** "Test nhanh + mới fail gần đây" (LatestFail+CC) đạt APFDc trung
   bình **0.835**, còn "test nhanh nhất trước" (QTF) đạt 0.740. Cả hai đều vượt mọi kỹ thuật ML/IR. Phần
   facility location của FALCON **không biết gì về thời gian chạy**, nên có nguy cơ kéo một test tích hợp dài
   15 phút lên đầu và làm tụt APFDc. Đây là rủi ro lớn nhất của đề tài, cần kiểm tra **sớm** bằng pilot.
3. **LRTS làm việc ở mức test class, còn FALCON ở mức test method.** Hơn nữa LRTS **không kèm mã nguồn test**,
   bạn phải checkout repo theo từng build để lấy mã test rồi embedding. Đây là phần kỹ thuật tốn công nhất.

---

## 1. Bối cảnh và bài toán

### 1.1. Test Case Prioritization (TCP) là gì?

Một **test suite** là tập test `T = {t1, …, tn}`. TCP tìm một **hoán vị** `π` của T, tức một thứ tự chạy, để
lỗi được phát hiện sớm nhất. TCP **không xóa** test (khác với *test suite minimization*) và **không chọn bớt**
test (khác với *test selection*). Nếu pipeline bị dừng giữa chừng vì hết thời gian, các test giá trị nhất đã
chạy rồi.

Định nghĩa hình thức (Rothermel et al., 2001), được FALCON trích lại:

```
Cho T, Π = tập mọi hoán vị của T, g: Π → ℝ đo chất lượng thứ tự.
Tìm π* = argmax_{π∈Π} g(π)
```

Vấn đề là ta **không biết trước test nào sẽ fail**. Biết thì đã chẳng cần chạy. Vì vậy mọi kỹ thuật TCP đều
tối ưu một **đại lượng thay thế (surrogate)**:

| Họ kỹ thuật | Tín hiệu dùng | Ví dụ |
|---|---|---|
| Coverage-based (white-box) | độ phủ code | Total/Additional greedy |
| Diversity/similarity-based (black-box) | độ khác nhau giữa các test | FAST, **FALCON** |
| History-based | lịch sử pass/fail | MostFail, LatestFail |
| Time-based | thời gian chạy | QTF (Quickest-Time-First) |
| IR-based | độ giống giữa test và diff | BM25/TF-IDF |
| ML-based | học từ đặc trưng | LTR (LightGBM), RL (RETECS) |
| Hybrid | kết hợp | CC, CCH, **DANTE**, **HC-FALCON** |

### 1.2. Vì sao đề tài này có ý nghĩa?

Hai paper ICST 2026 xuất hiện cùng phiên "Test Prioritization & Build Optimization" và mạnh ở hai mặt trái
ngược nhau:

- **FALCON** mạnh về **đa dạng ngữ nghĩa**, có nền toán học (submodular), nhưng bỏ qua lịch sử và chi phí.
- **DANTE** mạnh về **lịch sử và chi phí** (stickiness, CCH) cộng thêm liên hệ commit–test, nhưng không mô hình
  hóa sự trùng lặp giữa các test.

Đề tài đặt câu hỏi: **gộp cả hai vào cùng một hàm mục tiêu submodular có tốt hơn từng cái riêng không, và có tốt
hơn cách trộn thứ hạng đơn giản không?** Ràng buộc là phải giữ được bảo đảm lý thuyết và chi phí đủ rẻ cho CI.

### 1.3. Mục tiêu "đặt test lên đầu" theo `topic1.md`

Mỗi mục trong yêu cầu ứng với một thành phần của phương pháp:

| Yêu cầu | Thành phần đáp ứng |
|---|---|
| Khả năng phát hiện lỗi cao | `p_b(t)`: xác suất fail từ lịch sử |
| Chạy tương đối nhanh | chia cho `√c̃_b(t)` |
| Đại diện nhiều nhóm hành vi | facility location `FL_b(S)` |
| Tránh lặp sớm các test giống nhau | tính chất diminishing returns của FL |
| Không bỏ quên test mới | `conf_b(t)` và FL (xem cảnh báo ở §8.5) |

---

## 2. Kiến thức nền cần nắm

### 2.1. Hàm tập hợp, monotone, submodular

Một **hàm tập hợp** `f: 2^T → ℝ` gán một số cho mỗi tập con S ⊆ T.

- **Marginal gain**: `Δf(x | S) = f(S ∪ {x}) − f(S)`, tức phần lợi thêm khi bổ sung x vào S.
- **Monotone**: `S ⊆ S' ⇒ f(S) ≤ f(S')`. Thêm phần tử không bao giờ làm giảm giá trị.
- **Submodular** (lợi ích giảm dần, *diminishing returns*):

```
Với mọi S ⊆ S' ⊆ T và x ∉ S':   Δf(x | S) ≥ Δf(x | S')
```

Trực giác: thêm một test vào *tập nhỏ* có lợi hơn thêm nó vào *tập lớn*. Lý do là trong tập lớn đã có test
tương tự "làm thay phần việc" của nó.

- **Modular**: dấu "=" luôn xảy ra, tức `f(S) = Σ_{x∈S} w(x)`. Hàm modular vừa submodular vừa supermodular.
  Thành phần lịch sử/chi phí `Σ q(t)` của đề tài thuộc loại này.

### 2.2. Facility location

Hình dung có các "thành phố" (mọi test u ∈ T) và các "nhà máy" (các test được chọn s ∈ S). Mỗi thành phố được
phục vụ bởi nhà máy giống nó nhất:

```
FL(S) = Σ_{u∈T} max_{s∈S} sim(u, s)          (quy ước max trên ∅ bằng 0)
```

Marginal gain có dạng tường minh, rất tiện để cài đặt:

```
ΔFL(t | S) = Σ_{u∈T} max{0, sim(u,t) − cur(u)},    với cur(u) = max_{s∈S} sim(u,s)
```

Nếu `sim ≥ 0` thì FL là **monotone submodular**. Đây là kết quả kinh điển (Cornuéjols–Nemhauser–Wolsey). Ý
nghĩa đối với TCP: một test đã chạy thì "bao phủ" luôn các test giống nó. Test tiếp theo đáng chọn là test bao
phủ được những vùng **chưa ai bao phủ**.

### 2.3. Greedy, bảo đảm (1−1/e), lazy greedy

**Greedy** (Nemhauser–Wolsey–Fisher, 1978): bắt đầu với S = ∅, mỗi bước thêm phần tử có marginal gain lớn
nhất. Với f monotone submodular, `f(∅) = 0` và ràng buộc `|S| ≤ k`:

```
f(S_greedy) ≥ (1 − 1/e) · max_{|S|≤k} f(S)  ≈ 0.632 · OPT
```

**Từ greedy sang thứ tự đầy đủ:** chạy greedy đến khi hết test thì ta được hoán vị `π`. Do greedy tất định (với
quy tắc phá hòa cố định), **k phần tử đầu tiên của π chính là nghiệm greedy cho ngân sách k**. Vì vậy *mọi tiền
tố* của π đồng thời đạt bảo đảm (1−1/e). Đây là lý do một lần chạy cho được "các tập ưu tiên ứng với nhiều ngân
sách k" như mục đầu ra yêu cầu.

**Lazy greedy** (Minoux, 1978): do submodular, marginal gain của mỗi phần tử chỉ giảm qua các vòng. Vì vậy giá
trị gain cũ là một **cận trên**. Ta giữ một max-heap theo gain cũ, mỗi vòng chỉ tính lại phần tử ở đỉnh heap.
Nếu sau khi tính lại nó vẫn lớn nhất thì chọn luôn. Kết quả **giống hệt** greedy chuẩn nhưng nhanh hơn nhiều
trong thực tế.

### 2.4. Metric đánh giá

Ký hiệu: n test, m lỗi, `TF_i` là vị trí của test đầu tiên phát hiện lỗi i, `t_j` là thời gian chạy của test ở
vị trí j.

**APFD** (không xét chi phí), dùng trong FALCON:

```
APFD = 1 − (TF_1 + … + TF_m)/(n·m) + 1/(2n)
```

**APFDc** (xét chi phí, Elbaum–Malishevsky–Rothermel 2001; với mọi lỗi cùng mức nghiêm trọng):

```
APFDc = Σ_{i=1}^{m} ( Σ_{j=TF_i}^{n} t_j − ½·t_{TF_i} )  /  ( Σ_{j=1}^{n} t_j · m )
```

Hiểu nôm na, APFDc là diện tích dưới đường "% lỗi đã phát hiện theo % *thời gian* đã chạy". Trên LRTS, APFDc
tăng 0.1 tương đương phát hiện mọi lỗi sớm hơn khoảng 10% thời gian suite, tức trung bình ~39 phút. LRTS cũng
xác nhận rằng **APFD có thể cho xếp hạng kỹ thuật sai lệch so với APFDc**. Với CI, APFDc là metric chính.

**Relative APFDc:** không có định nghĩa duy nhất. Cách thường gặp là chuẩn hóa theo thứ tự tối ưu (oracle):
`APFDc / APFDc_opt`, hoặc min–max giữa thứ tự tệ nhất và tốt nhất. **Phải ghi rõ định nghĩa bạn dùng.**

**Time to First Failure (TTFF):** tổng thời gian chạy từ đầu đến hết test fail đầu tiên. Có thể báo cáo theo
giây hoặc theo % tổng thời gian suite.

**% lỗi phát hiện trong 10%/25%/50% ngân sách:** chạy theo π đến khi tích lũy đủ x% tổng thời gian, rồi đếm số
lỗi đã lộ.

**Ánh xạ failure → fault** (vì dữ liệu CI thật không biết lỗi gốc):
- `FFMapU`: mỗi test fail là một lỗi riêng.
- `FFMapS`: mọi test fail trong một lần chạy là cùng một lỗi.

LRTS báo cáo cả hai và thấy chúng cho xếp hạng kỹ thuật tương tự nhau.

### 2.5. Thống kê

- **Wilcoxon signed-rank:** kiểm định phi tham số cho dữ liệu *ghép cặp*. Mỗi build cho một cặp
  (APFDc của A, APFDc của B).
- **Holm correction:** hiệu chỉnh p-value khi so sánh nhiều cặp cùng lúc.
- **Cliff's delta (δ):** độ lớn hiệu ứng. |δ| < 0.147 là không đáng kể, < 0.33 nhỏ, < 0.474 vừa, ≥ 0.474 lớn.

### 2.6. Flaky test và "confounding failures"

**Flaky test** là test pass hoặc fail ngẫu nhiên trên cùng một mã nguồn. **Frequently-failing test** là test
fail liên tục, thường không liên quan đến thay đổi code. Cả hai làm "nhiễu" lịch sử. Theo LRTS, kỹ thuật **đếm
tần suất** như MostFail bị ảnh hưởng nặng, còn kỹ thuật **ưu tiên lịch sử gần đây** như LatestFail thì bền
vững hơn.

---

## 3. Paper nền: FALCON (đọc kỹ từ PDF)

**FALCON: Efficient Test Case Prioritization via Submodular Optimization.** Mensah-Boateng, Yuan, Do (University
of North Texas). IEEE ICST 2026, tr. 566–576, DOI 10.1109/ICST69053.2026.00079.

### 3.1. Phương pháp

Pipeline gồm bốn bước:

1. Trích các **test method**.
2. Mã hóa mỗi method bằng mô hình code pretrained **đóng băng**, không fine-tune. Lấy mean-pooling ở lớp ẩn
   cuối; method dài quá context window thì cắt đuôi.
3. Tính **ma trận similarity** bằng cosine, hoặc Euclidean quy về `1/(1+d)`.
4. Chạy **lazy greedy** trên facility location và lấy thứ tự chọn làm thứ tự ưu tiên.

Paper có ví dụ 4 test, gồm hai cụm {t1, t2} và {t3, t4}. FALCON cho thứ tự ⟨t2, t3, t4, t1⟩: lấy đại diện của
từng cụm trước, rồi mới đến các test trùng lặp.

Độ phức tạp theo paper: mỗi lần tính gain tốn O(n), greedy chuẩn tốn O(n²) lần tính, tổng cộng **O(n³)**. Lazy
greedy trong trường hợp xấu nhất vẫn vậy. Paper nói "kỳ vọng" là O(n log n) lần tính, tức O(n² log n), nhưng
đây là **quan sát thực nghiệm** từ tài liệu trước, **không phải định lý**.

### 3.2. Thực nghiệm

- **Dữ liệu:** Defects4J v2.0, 6 dự án (Closure, Lang, Math, Chart, Time, Mockito), 288 fault version, 20.770
  test method. Theo cách làm của FAST: lấy test suite của **phiên bản đầu (v1)** rồi đánh giá trên các phiên
  bản lỗi về sau.
- **Baseline:** họ FAST (pw, all, log, sqrt, one), chạy 50 lần mỗi biến thể vì có ngẫu nhiên.
- **Metric:** chỉ APFD, cộng thời gian chuẩn bị (embedding, GPU) và thời gian xếp hạng.
- **Thống kê:** FALCON tất định nên chỉ có một giá trị. Paper dùng bootstrap 95% CI trên median của 50 lần chạy
  FAST, hiệu chỉnh Holm–Bonferroni, và Cliff's δ.
- **RQ:** hiệu quả, hiệu năng, embedding nào/khoảng cách nào, so với hàm submodular khác.

### 3.3. Kết quả chính

| Cấu hình | Median APFD | Thời gian xếp hạng |
|---|---|---|
| FAST-log (FAST tốt nhất) | 0.628 | 0.06 s |
| **FALCON (UniXcoder + cosine)** | **0.731** (+16.4%) | **4.45 s** |
| Log-determinant (CodeXEmbed + Euclid) | 0.741 | 75.45 s |
| Graph cut | 0.591 | 163.07 s |

Các phát hiện kèm theo:
- UniXcoder tốt nhất và cũng embed nhanh nhất (trung bình 17.23 s/dự án). Paper giải thích bằng "effective rank"
  của ma trận similarity: UniXcoder đạt 31.7, CodeBERT chỉ 1.9.
- Cosine tốt hơn Euclid trên mọi mô hình.
- Facility location cho trade-off hiệu quả/chi phí tốt nhất.

### 3.4. Hạn chế, cũng là động lực của đề tài

- Chỉ tối ưu **độ phủ/đa dạng ngữ nghĩa**. Failure history không có trong objective.
- **Thời gian chạy không được dùng**, trong khi APFDc trong CI phụ thuộc mạnh vào nó.
- Đánh giá trên Defects4J với một suite v1 cố định: **không có chuỗi build**, không có lịch sử, không có test
  mới xuất hiện theo thời gian.
- Chính tác giả ghi ở phần future work: *"adaptive similarity functions that incorporate test execution
  feedback"*. Đề tài của bạn đi đúng hướng đó.

### 3.5. Những điểm cần đối chiếu và cảnh giác (đã kiểm tra PDF và code)

`topic1.md` có lưu ý phải đối chiếu công thức và số liệu với PDF gốc. Kết quả đối chiếu:

- **Khớp với PDF:** định nghĩa facility location, công thức APFD, Algorithm 1–2, bảo đảm (1−1/e), con số
  0.731/0.628/16.4%/4.45 s.
- **Mâu thuẫn nội bộ trong paper:**
  - Phần Kết luận ghi thời gian median **3.71 s**, phần thân ghi **4.45 s**.
  - Paper nói suite có "từ 2.193 đến 8.006 test", nhưng Mockito trong Bảng II chỉ có **1.292** test method.
  - Khi trích dẫn, dùng số trong bảng kết quả và nói rõ nguồn.
- **Cosine có thể âm.** Lớp `FacilityLocation` trong artifact **không cắt giá trị âm**, còn `GraphCut` thì có
  chuẩn hóa. Lý thuyết monotone, `f(∅) = 0`, (1−1/e) cần `sim ≥ 0`. Trong HC-FALCON phải dùng
  `sim = max(0, cos)` hoặc `(1 + cos)/2` và ghi rõ.
- **Code chưa tối ưu như phân tích:** `marginal_gain` tính lại `max` trên toàn bộ S mỗi lần gọi, tốn O(n·|S|)
  chứ không phải O(n). Khi tự cài đặt, hãy giữ vector `cur(u)` và cập nhật O(n) sau mỗi lần chọn.
- **Lazy greedy trong code** dùng ngưỡng `1e-6` khi so sánh, nên phá hòa có thể khác greedy chuẩn. Khi kiểm tra
  "lazy == standard", cần quy tắc phá hòa tất định.
- **"First submodular TCP"** là tuyên bố của tác giả FALCON. Không lặp lại tuyên bố kiểu "đầu tiên" cho đề tài
  của bạn (xem §4.4).

### 3.6. Artifact FALCON

- GitHub: `https://github.com/anonymous-ing/falcon-icst-2026` (đã kiểm tra, còn truy cập được). Zenodo DOI
  `10.5281/zenodo.18897073`.
- Gồm `py/submodtcp.py` (FL, LogDet, GraphCut), `py/fast.py` (các biến thể FAST, **dùng lại làm baseline
  được**), `py/embedding_generator.py`, `py/metric.py` (APFD), `run_all_experiments.sh`, script thống kê.
- Dữ liệu vào cho mỗi dự án: file test method (một dòng mỗi method) và `fault_matrix.pickle` (method → danh sách
  bug). **Không có thời gian chạy, không có lịch sử.** Đó là lý do Defects4J chỉ dùng để tái lập FALCON.

---

## 4. Công trình liên quan bắt buộc phải nắm

### 4.1. LRTS — bộ dữ liệu chính để đánh giá

**Revisiting Test-Case Prioritization on Long-Running Test Suites.** Cheng, Wang, Jabbarvand, Marinov (UIUC).
ISSTA 2024.

**Quy mô:** 10 dự án Apache dùng Jenkins, 21.255 build CI, 57.437 lần chạy test suite (TSR), giai đoạn
2020–2023, trung bình **6.5 giờ/TSR**. Có 9 dự án Java (TVM là Python/C++).

| Dự án | #TSR | #TC TB | Thời lượng TB (giờ) | Ghi chú |
|---|---|---|---|---|
| ActiveMQ | 207 | 676 | 4.36 | nhỏ, hợp làm pilot |
| Hadoop | 1.299 | 829 | 5.57 | |
| HBase | 553 | 1.061 | 9.28 | |
| Hive | 2.056 | 1.273 | 26.12 | rất nặng |
| Jackrabbit Oak | 860 | 1.897 | 3.27 | |
| James | 3.147 | 1.864 | 2.15 | |
| Kafka | 39.006 | 1.232 | 7.59 | cực nhiều TSR |
| Karaf | 620 | 205 | 0.58 | nhỏ, suite ngắn |
| Log4j 2 | 528 | 641 | 0.25 | nhỏ, suite ngắn |

(#TC TB và thời lượng TB là trung bình trên các TSR có fail, theo Bảng 2 của paper.)

**Dữ liệu mỗi build:** tên, kết quả, thời gian của từng test method và test class; stack trace của test fail;
diff code, danh sách file thay đổi, commit, tác giả. Mỗi ⟨build, stage⟩ được tính là một TSR, và mỗi stage có
lịch sử riêng.

**Mức độ chi tiết khi đánh giá:** **test class**, giống các nghiên cứu trước.

**Ba phiên bản dữ liệu:**
- `LRTS-All`: giữ mọi failure (30.118 TSR fail).
- `LRTS-DeConf`: bỏ confounding failures (9.683 TSR fail). Flaky được xác định qua 746 issue JIRA/GitHub (ra
  344 flaky test kèm ngày sửa) và qua việc fail không nhất quán giữa các môi trường. Frequently-failing được
  lọc theo luật 3-sigma.
- `LRTS-FirstFail`: chỉ giữ lần fail **đầu tiên** của mỗi test không flaky (2.076 TSR).

**Kết quả quan trọng, cũng là mức bạn phải vượt** (APFDc-FFMapU trung bình, LRTS-DeConf):

| Kỹ thuật | APFDc |
|---|---|
| **LatestFail + CC** (test fail gần đây × thời gian) | **0.835** (tốt nhất) |
| QTF-Avg (test nhanh nhất trước) | 0.740 |
| LTR (LightGBM, mọi đặc trưng) | 0.736 |
| LatestFail | 0.735 |
| IR-GitDiff (TF-IDF) | 0.647 |
| MostFail | 0.613 |
| Random | 0.502 |

**Các phát hiện có ảnh hưởng trực tiếp đến đề tài:**
- Kỹ thuật đơn giản kết hợp thời gian và lịch sử thắng mọi kỹ thuật phức tạp (F3, F10).
- Các test fail thường là test **chạy lâu**. QTF đặt chúng ở vị trí ~83% nhưng vẫn thắng APFDc, vì nó đẩy các
  test tích hợp dài hàng chục phút xuống cuối.
- Đếm tần suất fail bị nhiễu bởi flaky (F11). Lịch sử gần đây thì bền vững (F12).
- **67% test chưa từng fail.** Trên `LRTS-FirstFail`, mọi kỹ thuật history-based chỉ ngang Random (≈0.31–0.47).
  QTF tốt nhất (≈0.80), IR > Random (≈0.63–0.69). Đây là chỗ thành phần ngữ nghĩa của HC-FALCON **có thể tạo
  khác biệt**, tức RQ3.
- Tác giả gợi ý hướng mới: ưu tiên theo lịch sử, phá hòa bằng thời gian hoặc IR.

**Artifact:** Zenodo `https://zenodo.org/records/12662090` (file code `LRTS-main.zip` ~0.29 GB, kèm hướng dẫn tải
toàn bộ dữ liệu), GitHub `https://github.com/lrtsuser/LRTS`. Có sẵn cài đặt của nhiều kỹ thuật TCP, dùng lại
làm baseline được.

### 4.2. DANTE — baseline training-free mạnh

**DANTE: Data-Driven Test Case Selection and Prioritization for Long-Running Test Suites.** Reale, Di Nitto,
Baresi, Di Penta, Quattrocchi. ICST 2026, tr. 577–588. **Distinguished Paper Award**.

*(Chưa đọc được toàn văn. Thông tin dưới đây lấy từ abstract và README artifact.)*

- **Ý tưởng:** biến các heuristic đơn giản thành chiến lược data-driven mà **không cần huấn luyện**. Ba thành
  phần chính:
  - **"Stickiness" xác suất:** mức độ một failure "dính" sang build sau, mô hình bằng **khoảng tin cậy Wilson**.
    Nó tự thích nghi với thói quen fail/sửa của từng dự án.
  - **"Recency boost":** đẩy mạnh các regression vừa xuất hiện.
  - **Thành phần commit-aware:** TF-IDF giữa diff và file test.
  - Kết hợp tất cả theo kiểu **cost-history-cognizant (CCH)** thành một "value score".
- **Đánh giá:** 9 dự án Java của LRTS.
  - Prioritization (APFDc) so với MostFail-CC, LastFail-CCH, QTF, LTR-CCH (HistGradientBoosting, huấn luyện
    JIT theo thời gian).
  - Selection theo ngân sách thời gian 5%, 10%… với metric %DTC (recall), SAPFDc/NAPFDc, SDS.
  - Độ bền với flaky qua %DTC_FLK.
- **Artifact:** Zenodo `https://zenodo.org/records/18900675` (MIT, có Docker, file zip ~3.6 GB).
  `pipeline_orchestrator.py` **dựng lại trạng thái repo tại từng build bằng git worktree và tokenize file
  test.** Bạn có thể học hoặc dùng lại pipeline này để lấy mã nguồn test phục vụ embedding.
- **Liên hệ với đề tài:**
  - Wilson CI chính là một cách tự nhiên để gộp `p` và `conf` thành một số: lấy cận dưới Wilson.
  - DANTE còn dùng thông tin commit, trong khi HC-FALCON theo `topic1.md` không dùng. Cần ghi điều này trong
    threats/limitations nếu DANTE thắng.

### 4.3. FAST và các hướng khác

- **FAST** (Miranda et al., ICSE 2018): similarity-based TCP black-box có độ phức tạp gần tuyến tính (shingling,
  minhash, LSH). Có sẵn trong artifact FALCON.
- **History-based và cost-aware:** MostFail, LatestFail, MostTrans, LatestTrans. Các phép lai **CC**
  (`score × thời gian`) và **CCH** (`score × thời gian / số lần fail`) từ Peng et al. (ISSTA 2020) và LRTS.
- **"TCP approach combinators":** `topic1.md` không nêu nguồn cụ thể và tôi không tìm thấy paper nào dùng đúng
  thuật ngữ này. Hiểu hợp lý nhất là **các cách tổ hợp kỹ thuật TCP**: lai CC/CCH, sắp xếp theo thứ tự từ điển
  (heuristic chính, phá hòa bằng heuristic phụ), gộp thứ hạng (Borda, Reciprocal Rank Fusion), tổ hợp tuyến
  tính điểm. **Nên hỏi lại giảng viên** để có tài liệu đúng.

### 4.4. Công trình đã kết hợp history và diversity (vì sao không được nói "đầu tiên")

- **Noor & Hemmati (ISSRE 2015):** ưu tiên test giống với các test từng fail (similarity + failure history).
- **Haghighatkhah et al. (JSS 2018), "Test prioritization in CI environments":** kết hợp *history-based* với
  *diversity-based* (khoảng cách giữa test) trong CI. FALCON có trích dẫn paper này.
- **Mahdieh et al. (Automated Software Engineering, 2022):** đa dạng hóa test bằng clustering kết hợp ước lượng
  fault-proneness từ lịch sử bug.

Đóng góp có thể bảo vệ được của bạn là: **đưa history và cost vào trong một objective submodular có bảo đảm lý
thuyết, đánh giá rolling trên CI dài hạn hiện đại (LRTS), so trực tiếp với FALCON, DANTE và phép trộn thứ hạng
đơn giản.** Không phải "lần đầu kết hợp".

---

## 5. Phương pháp đề xuất: HC-FALCON

### 5.1. Các đại lượng tại build b

Tập test của build b là `T_b`. Mọi đại lượng lịch sử **chỉ được tính từ các build trước b.**

| Ký hiệu | Ý nghĩa | Cách tính gợi ý |
|---|---|---|
| `z(t)` | embedding mã test | UniXcoder (cấu hình tốt nhất của FALCON), cache theo hash nội dung file |
| `sim(u,t)` | độ giống | `max(0, cos(z_u, z_t))` hoặc `(1+cos)/2`, bắt buộc ≥ 0 |
| `p_b(t)` | xác suất fail | xem §5.2 |
| `c_b(t)` | thời gian chạy ước lượng | trung bình hoặc EMA các lần chạy trước. Test mới: median của dự án/module, hoặc trung bình của k test giống nhất theo embedding |
| `c̃_b(t)` | thời gian chuẩn hóa | `c / median(c)` hoặc `c / max(c)` trên `T_b` |
| `conf_b(t)` | độ tin cậy | `N/(N+κ)` hoặc `1 − exp(−N/κ)`, với N là số lần đã chạy |
| `q_b(t)` | điểm lỗi-chi-phí | `conf · p / (√c̃ + ε)` |

### 5.2. Ba cách ước lượng xác suất fail (đề tài yêu cầu thử)

Ký hiệu: F là số lần fail, N là số lần chạy, tính trên các build trước b.

**(a) Beta-Bernoulli** (làm mượt bằng prior):
```
p̂ = (F + a) / (N + a + b),   prior a = μ·s, b = (1−μ)·s
```
Với μ là tỉ lệ fail nền của dự án và s là độ mạnh của prior. Test mới nhận p̂ = μ thay vì 0.

**(b) Exponential decay** (ưu tiên lịch sử gần):
```
F_λ = Σ_r λ^{age(r)} · fail(r),   N_λ = Σ_r λ^{age(r)},   p̂ = (F_λ + a)/(N_λ + a + b)
```
Ở đây `age(r)` là số lần chạy tính từ r đến hiện tại, và λ ∈ (0,1). Theo LRTS (F12), hướng này bền với flaky
hơn hẳn đếm thô.

**(c) Failure stickiness** (lỗi có xu hướng kéo dài đến khi được sửa):
```
p̂ = P(fail | lần trước fail)   nếu lần chạy trước của t fail
p̂ = P(fail | lần trước pass)   nếu lần chạy trước pass
```
Hai xác suất chuyển trạng thái được ước lượng từ lịch sử (theo test, hoặc gộp toàn dự án khi test có ít dữ
liệu), có làm mượt. DANTE dùng Wilson CI cho đại lượng này.

**Gộp `p·conf` bằng Wilson** (gợi ý thêm): lấy **cận dưới** khoảng tin cậy Wilson của tỉ lệ F/N. Cận này tự động
nhỏ khi N nhỏ, đúng ý tưởng "ít dữ liệu thì tin ít".

### 5.3. Hàm mục tiêu và thuật toán

```
F_b(S) = α · FL_b(S)/|T_b|  +  (1−α) · Σ_{t∈S} q_b(t),   0 ≤ α ≤ 1

ΔF_b(t | S) = (α/|T_b|) · Σ_u max{0, sim(u,t) − cur(u)}   +   (1−α) · q_b(t)
              └────── "độ mới ngữ nghĩa" (giảm dần) ──────┘     └ "rủi ro/chi phí" (hằng) ┘
```

**Hành vi của greedy:** ở đầu danh sách, phần FL còn lớn nên greedy chọn test vừa *đại diện vùng mới* vừa
*rủi ro*. Càng về sau, phần FL co lại (diminishing returns), còn `q` là hằng số. Vì vậy thứ tự dần do lịch sử và
chi phí quyết định. α điều khiển điểm cân bằng.

**Lazy greedy cho HC-FALCON** (giả mã):

```
cur[u] ← 0 với mọi u;  π ← []
gain[t] ← (α/n)·Σ_u sim(u,t) + (1−α)·q[t];  stamp[t] ← 0;  heap ← max-heap theo gain
for i = 1..n:
    loop:
        t ← heap.top()
        if stamp[t] == i: break                       # gain đã cập nhật ở vòng này ⇒ chọn
        gain[t] ← (α/n)·Σ_u max(0, sim(u,t) − cur[u]) + (1−α)·q[t]
        stamp[t] ← i;  heap.update(t, gain[t])
    heap.pop();  π.append(t);  ghi lại (t, phần FL, phần q)   # để giải thích
    cur[u] ← max(cur[u], sim(u,t)) với mọi u          # O(n)
return π
```

**Quy tắc phá hòa tất định:** gain bằng nhau thì chọn test có `c` nhỏ hơn, rồi đến tên theo thứ tự từ điển.

### 5.4. Ví dụ số: lịch sử thay đổi thứ tự như thế nào

Dùng đúng ma trận 4 test trong ví dụ của FALCON (cụm {t1, t2} và {t3, t4}). Chọn α = 0.5 và giả sử
`q = (t1: 0, t2: 0.04, t3: 0, t4: 0.30)`, nghĩa là t4 ngắn và vừa fail gần đây. Phần FL đóng góp ΔFL/8.

| Bước | t1 | t2 | t3 | t4 | Chọn |
|---|---|---|---|---|---|
| 1 (S=∅) | 2.2/8 = 0.275 | 0.300 + 0.02 = **0.320** | 0.2875 | 0.2625 + 0.15 = **0.4125** | **t4** |
| 2 (S={t4}) | 1.6/8 = 0.200 | 0.200 + 0.02 = **0.220** | 0.4/8 = 0.050 | — | **t2** |
| 3 (S={t4,t2}) | 0.1/8 = 0.0125 | — | 0.2/8 = **0.025** | — | **t3** |
| 4 | còn lại | | | | t1 |

- **HC-FALCON:** ⟨t4, t2, t3, t1⟩.
- **FALCON:** ⟨t2, t3, t4, t1⟩.

Lịch sử kéo t4 lên đầu. Sau đó **phần FL tự động nhảy sang cụm còn lại** (t2) chứ không chọn t3, vì cụm
{t3, t4} đã được t4 bao phủ. Đây chính là điểm khác biệt so với việc chỉ sắp theo `q`.

### 5.5. Giải thích lý do ưu tiên (đầu ra bắt buộc)

Với mỗi test trong π, lưu:
- vị trí;
- marginal gain tổng;
- phần **ngữ nghĩa** `(α/n)·ΔFL` và phần **lịch sử/chi phí** `(1−α)·q`;
- các thành phần `p`, `conf`, `c`;
- top-3 test u mà nó "bao phủ thêm" nhiều nhất.

Ví dụ diễn giải: *"Xếp thứ 3 vì: fail ở 2/5 build gần nhất (p = 0.31, conf = 0.83), chạy 4 s, đóng góp rủi ro
0.12; đại diện cho cụm test kết nối Broker chưa được phủ, đóng góp ngữ nghĩa 0.07."*

### 5.6. Vòng lặp rolling: chống rò rỉ dữ liệu

```
History ← rỗng
for b in các build sắp theo thời gian bắt đầu (theo từng ⟨project, stage⟩):
    T_b ← các test của build b
    E   ← embedding(T_b)   (dùng cache; chỉ embed file test mới/đổi)
    p, c, conf ← ước lượng từ History            # chỉ build < b
    π_b ← lazy_greedy(F_b)
    ghi π_b, gain, thời gian xếp hạng, bộ nhớ
    đánh giá π_b bằng kết quả THẬT của b          # APFDc, TTFF, …
    History.update(kết quả_b, thời gian_b)        # CHỈ sau khi xếp hạng xong
```

**Bẫy leakage cần tránh** (nên ghi vào báo cáo):
- Nhãn flaky của LRTS dùng ngày sửa issue *trong tương lai*, và danh sách frequently-failing được tính bằng 3-sigma
  trên *toàn bộ lịch sử*. Chúng **chỉ được dùng để làm sạch nhãn đánh giá** (DeConf), **không được làm đặc trưng**
  để xếp hạng.
- Build song song: build bắt đầu trước b nhưng kết thúc sau b không được dùng. Chỉ dùng build đã *kết thúc*
  trước thời điểm b bắt đầu, hoặc ghi rõ quy ước của bạn.
- Siêu tham số (α, λ, prior, κ) không được tinh chỉnh trên các build dùng để đánh giá. Hoặc cố định trước, hoặc
  tinh chỉnh trên đoạn build sớm nhất (ví dụ 20%) rồi khóa lại và chỉ báo cáo trên phần còn lại.
- Thống kê chuẩn hóa (median của c…) chỉ lấy từ `T_b` hoặc từ quá khứ.

**Script kiểm tra leakage** (sản phẩm bắt buộc):
1. **Kiểm tra bất biến:** xóa hoặc xáo trộn mọi build ≥ b rồi chạy lại. π_b phải giống hệt.
2. **Assert:** mọi bản ghi lịch sử dùng cho b có timestamp < start(b).
3. **Kiểm tra ngược:** cố tình "rò" kết quả của b vào lịch sử. APFDc phải tăng vọt, chứng tỏ test (1) đủ nhạy.

---

## 6. Phần lý thuyết phải viết

### 6.1. Mệnh đề 1: thành phần history/cost là modular không âm

Đặt `G(S) = Σ_{t∈S} q(t)`. Khi đó `ΔG(x|S) = q(x)`, không phụ thuộc S, nên dấu "=" trong định nghĩa submodular
luôn đúng: G vừa submodular vừa supermodular, tức modular. Vì `conf ≥ 0`, `p ≥ 0`, `√c̃ + ε > 0` nên `q ≥ 0`,
suy ra G monotone và `G(∅) = 0`.

### 6.2. Mệnh đề 2: FL monotone submodular khi sim ≥ 0

Với mỗi u, đặt `g_u(S) = max_{s∈S} sim(u,s)` (với `g_u(∅) = 0`). Ta có:

```
Δg_u(x|S) = max{0, sim(u,x) − g_u(S)}
```

Đại lượng này ≥ 0, nên g_u monotone. Khi `S ⊆ S'` thì `g_u(S) ≤ g_u(S')`, nên `Δg_u(x|S) ≥ Δg_u(x|S')`, tức
g_u submodular. Tổng các hàm monotone submodular vẫn là monotone submodular, nên `FL = Σ_u g_u` cũng vậy.
**Chỗ cần sim ≥ 0:** để `g_u({x}) ≥ g_u(∅) = 0`.

### 6.3. Định lý: F_b monotone submodular và có bảo đảm (1−1/e)

Tổ hợp tuyến tính với hệ số không âm (α/|T_b| và 1−α) của các hàm monotone submodular, chuẩn hóa `F(∅) = 0`, vẫn
là monotone submodular. Theo Nemhauser–Wolsey–Fisher, greedy dưới ràng buộc `|S| ≤ k` đạt `F(S_k) ≥ (1−1/e)·OPT_k`.
Nhờ tính chất tiền tố (§2.3), **mọi tiền tố của π_b** đều đạt bảo đảm này với ngân sách tương ứng.

### 6.4. Tính đúng của lazy greedy

Gain của mỗi phần tử không tăng theo vòng (do submodular), nên giá trị cũ trong heap là cận trên. Khi phần tử ở
đỉnh đã được cập nhật trong vòng hiện tại, nó lớn hơn hoặc bằng mọi cận trên còn lại, nên nó là argmax thật. Kết
quả trùng với greedy chuẩn khi dùng cùng quy tắc phá hòa.

### 6.5. Độ phức tạp

| Bước | Thời gian | Bộ nhớ |
|---|---|---|
| Embedding | O(n) lần forward mô hình (GPU), cache theo hash ⇒ mỗi build chỉ embed file mới/đổi | O(n·d) |
| Ma trận similarity | O(n²·d) | O(n²) |
| Tính `q` | O(n), cộng O(lịch sử) nếu không cập nhật gia tăng | O(n) |
| Greedy chuẩn (có `cur`) | n vòng × n ứng viên × O(n) = **O(n³)** (vector hóa được) | O(n²) |
| Lazy greedy | xấu nhất O(n³), thực tế ít lần tính gain hơn nhiều (báo cáo số lần tính đo được) | O(n²) + heap O(n) |

**Quy mô thực tế:**
- Mức class trên LRTS: n ≈ 200–2.000. Ma trận 2.000² dạng float32 chỉ khoảng 16 MB, nhẹ.
- Mức method: Hive có ~41.000 method, ma trận ~6.7 GB. Khi đó cần **làm thưa** (chỉ giữ top-k láng giềng). Đây
  thêm một lý do để làm ở mức class.

### 6.6. Giới hạn của lý thuyết (phải nói rõ trong bài)

- Bảo đảm (1−1/e) là cho **hàm surrogate F_b**, **không phải** cho APFD hay APFDc. Không được tuyên bố "đảm bảo
  63% APFDc tối ưu".
- Bảo đảm là cho **ràng buộc số lượng** (k test). Ngân sách CI thực tế là **thời gian**, tức ràng buộc knapsack:
  - Greedy theo tỉ lệ gain/chi phí không còn giữ nguyên (1−1/e).
  - Có các biến thể có bảo đảm: max(greedy theo tỉ lệ, greedy thường) đạt ½(1−1/e) (CELF, Leskovec et al. 2007,
    tài liệu [23] của FALCON); Sviridenko (2004) đạt (1−1/e) với chi phí cao.
  - Đây là hướng mở rộng hợp lý (§8.2).

---

## 7. Thiết kế thực nghiệm

### 7.1. Dữ liệu

| Bộ dữ liệu | Mục đích | Ghi chú |
|---|---|---|
| Artifact FALCON / Defects4J (6 dự án) | **Tái lập FALCON**, so sánh với Bảng IV (FALCON 0.731, FAST-log 0.628) | Không có lịch sử/thời gian nên không đánh giá HC-FALCON đầy đủ ở đây |
| LRTS, **≥ 3 dự án Java** | Đánh giá rolling theo thời gian (RQ1–RQ4) | Mức **test class**, APFDc là metric chính, báo cáo trên DeConf (chính), All và FirstFail |

**Gợi ý chọn dự án LRTS:**
- **Pilot:** ActiveMQ (207 TSR, ~676 class, 4.4 h) hoặc Karaf (620 TSR, ~205 class). Nhỏ nên chạy nhanh trọn
  vòng.
- **Chính thức:** chọn ít nhất 3 dự án đa dạng kích thước, ví dụ ActiveMQ, Jackrabbit Oak, HBase. Có thể thêm
  Hadoop hoặc James nếu đủ tài nguyên. Kafka (39.006 TSR) và Hive (26 h/TSR) rất nặng, để sau.
- Nên trùng tập dự án với DANTE để so sánh được.

**Lấy mã nguồn test cho embedding:** LRTS chỉ có tên, kết quả và thời gian test, không có mã test. Cần
clone repo và checkout commit (base + diff của PR) cho từng build. Pipeline git worktree của DANTE làm đúng việc
này. Để tiết kiệm:
- Cache embedding theo **hash nội dung file test**, chỉ embed file mới hoặc đã đổi.
- Có thể xấp xỉ bằng snapshot định kỳ (ví dụ mỗi 50 build), nhưng phải ghi vào threats.

**Embedding một test class dài:** UniXcoder giới hạn 512 token. Có hai cách:
- Embed từng method rồi lấy trung bình đã chuẩn hóa để ra vector class (khuyến nghị).
- Cắt class thành các đoạn 512 token rồi pool.

Ghi rõ lựa chọn và nếu có thể thì so sánh hai cách.

### 7.2. Baseline

| Nhóm | Baseline | Nguồn cài đặt |
|---|---|---|
| Cơ bản | Random (nhiều seed), **QTF** (= Shortest-Test-First), MostFail, LatestFail (= Recent-Fail) | tự viết hoặc LRTS artifact |
| Lai mạnh | **LatestFail+CC** (0.835 trên LRTS), MostFail-CC, LastFail-CCH | LRTS, DANTE |
| Diversity | **FALCON** (α = 1), FAST (pw/all/log/sqrt/one) | FALCON artifact |
| Training-free SOTA | **DANTE** (nếu artifact chạy được) | Zenodo DANTE |
| Trộn đơn giản | `score = β·rank_FALCON + (1−β)·rank_history`, hoặc RRF | tự viết, **rất quan trọng** |

**Vì sao baseline trộn thứ hạng quan trọng:** nếu HC-FALCON không thắng nổi phép trộn thứ hạng đơn giản thì
công thức submodular không chứng minh được giá trị của nó. Reviewer chắc chắn sẽ hỏi điều này.

### 7.3. Metric

- **Chính:** APFDc (FFMapU, kèm FFMapS ở phụ lục), relative APFDc (ghi rõ định nghĩa).
- **Phụ:** TTFF (giây và %), % lỗi phát hiện ở 10/25/50% ngân sách *thời gian*, APFD (để đối chiếu FALCON).
- **Chi phí:** thời gian embedding (lần đầu và gia tăng mỗi build), thời gian tính similarity, thời gian greedy,
  số lần tính gain (lazy so với chuẩn), bộ nhớ đỉnh. So với thời lượng suite (giờ) để ra % overhead.
- **Thống kê:**
  - Wilcoxon signed-rank ghép cặp theo build (mỗi dự án riêng, và gộp với trọng số đều giữa các dự án như LRTS
    làm).
  - Holm correction cho nhiều cặp so sánh.
  - Cliff's δ cho độ lớn hiệu ứng.
  - Baseline ngẫu nhiên chạy nhiều seed, rồi lấy trung bình theo build trước khi kiểm định.

### 7.4. Ánh xạ RQ → thí nghiệm

| RQ | Câu hỏi | Thí nghiệm cụ thể |
|---|---|---|
| RQ1 | HC-FALCON có phát hiện lỗi sớm hơn FALCON và history baseline? | Toàn bộ baseline ở §7.2 trên LRTS-DeConf (và All). APFDc, TTFF, % theo ngân sách. Wilcoxon + Holm + δ |
| RQ2 | Semantic, history, cost đóng góp bao nhiêu? | Ablation bắt buộc (bảng dưới) và quét α ∈ {0, 0.1, …, 1}, vẽ đường APFDc theo α cho từng dự án |
| RQ3 | Với test mới và flaky test thì sao? | (i) **LRTS-FirstFail:** lần fail đầu của test chưa từng fail. (ii) Vị trí xếp hạng của test xuất hiện lần đầu. (iii) Độ chênh APFDc giữa LRTS-All và DeConf. (iv) So sánh Beta, decay, stickiness khi có nhiễu flaky |
| RQ4 | Chi phí có hợp với CI? | Đo thời gian và bộ nhớ từng bước. Overhead so với thời lượng TSR. Ảnh hưởng của cache embedding |

**Ablation bắt buộc** (theo `topic1.md`):

| Biến thể | Cấu hình |
|---|---|
| FALCON thuần | α = 1 |
| History-only | α = 0, `q = conf·p` (không chia chi phí) |
| History + cost | α = 0, `q = conf·p/(√c̃+ε)` |
| FL + history | α ∈ (0,1), `q = conf·p` |
| **Mô hình đầy đủ** | α ∈ (0,1), `q = conf·p/(√c̃+ε)` |
| Đầy đủ bỏ confidence | như trên nhưng `conf ≡ 1` |

Nên thêm nếu kịp:
- Số mũ chi phí γ ∈ {0.5, 1} (√c so với c, trong đó c giống CC).
- Biến thể FL **có xét chi phí** (§8.2).
- So sánh ba bộ ước lượng p.

---

## 8. Rủi ro và những điểm "mắt thường dễ bỏ qua"

### 8.1. Baseline đơn giản quá mạnh

LatestFail+CC đạt 0.835 trên LRTS-DeConf. Tiêu chí go/no-go yêu cầu tốt hơn cả FALCON và history-only, cộng
thêm mức kỳ vọng cải thiện trung vị 3–5%. Thực tế có thể là: HC-FALCON thắng FALCON dễ dàng (vì FALCON không
biết chi phí) nhưng **khó thắng LatestFail+CC**. Cần có pilot sớm trên một dự án nhỏ để biết sớm.

### 8.2. Phần FL không biết chi phí

Ở các bước đầu, FL có thể chọn một test "đại diện" nhưng chạy 15 phút. Điều đó làm tụt APFDc, trong khi QTF đạt
APFDc cao chính nhờ đẩy test dài xuống cuối. Các hướng xử lý:
- Chuẩn hóa để α không làm phần FL áp đảo.
- Thêm biến thể **cost-benefit greedy:** chọn theo `ΔF(t|S)/c(t)^γ`. Biến thể này phù hợp với ngân sách thời gian
  và APFDc, nhưng bảo đảm lý thuyết chuyển sang dạng knapsack (§6.6).
- Báo cáo trung thực cả hai.

### 8.3. Lệch thang đo giữa hai thành phần

`FL/|T|` nằm trong [0,1], còn `Σq` thì lớn dần theo |S| và phụ thuộc thang của `q`. Vì vậy cùng một α sẽ có ý
nghĩa khác nhau giữa các dự án. Nên chuẩn hóa `q` (ví dụ chia cho max hoặc phân vị 95 của q trên `T_b`) để α
diễn giải được. Báo cáo độ nhạy theo α vì go/no-go yêu cầu kết quả *không phụ thuộc một giá trị α duy nhất*.

### 8.4. Bảo đảm lý thuyết không có nghĩa là APFDc tốt

Xem §6.6. Phải viết rõ để reviewer không bắt lỗi over-claim.

### 8.5. Test mới bị dìm, mâu thuẫn với mục "không bỏ quên test mới"

Với `q = conf·p`, test mới có conf ≈ 0 nên q ≈ 0. Khi đó chỉ còn phần FL giúp nó: test mới *khác biệt* sẽ được
ưu tiên, nhưng test mới *giống test cũ* sẽ bị đẩy xuống. Trong khi đó test mới thường gắn với code mới và dễ fail
hơn. Các phương án:
- Dùng prior Beta để p của test mới bằng tỉ lệ nền thay vì 0.
- Thêm "novelty bonus" `(1−conf)·β`.
- Ít nhất phải **đo** hiện tượng này trong RQ3.

Nếu thay đổi công thức, phải giữ `q ≥ 0` để lý thuyết vẫn đúng.

### 8.6. Mức chi tiết và mã nguồn

- LRTS ở mức class, FALCON ở mức method (xem §7.1).
- Việc dựng lại mã test theo build tốn tài nguyên: nhiều GB repo, nhiều lần checkout. Hãy lên kế hoạch lưu trữ.

### 8.7. Flaky và nhãn

Kết quả trên LRTS-All và LRTS-DeConf có thể khác nhau rất xa (LRTS F11–F13). Báo cáo cả hai, lấy DeConf làm
chính, và giải thích.

### 8.8. Tái lập FALCON có thể không khớp số

Nguyên nhân có thể là phiên bản mô hình, GPU so với CPU, hoặc cách phá hòa. Ghi lại sai khác. Nếu sai lệch lớn
thì báo cáo trung thực, không chỉnh cho khớp.

---

## 9. Bạn cần làm gì: lộ trình đề xuất (~14–16 tuần)

> Thời lượng chỉ để tham khảo. Nguyên tắc: **làm pilot trọn vòng trên một dự án nhỏ trước**, có kết quả sớm để
> quyết định go/no-go, rồi mới mở rộng.

### Giai đoạn 0: Chuẩn bị (tuần 1–2)
- [ ] Tải và đọc kỹ: FALCON (đã có), LRTS, DANTE, FAST, Peng et al. 2020 (IR + CC/CCH), Haghighatkhah et al. 2018,
      Noor & Hemmati 2015, Nemhauser–Wolsey–Fisher 1978, Minoux 1978, Elbaum et al. 2001 (APFDc).
      Lưu ý: thư mục `papers/` mà `topic1.md` nhắc tới **chưa có trong repo**, hiện chỉ có `paper-topic1.pdf`.
- [ ] Hỏi giảng viên: nguồn "TCP approach combinators"; số dự án và mức chi tiết mong muốn; có cần biến thể
      ngân sách thời gian không.
- [ ] Dựng môi trường: Python, PyTorch, transformers, GPU (nếu có), git, đủ dung lượng đĩa.
- [ ] Khởi tạo repo git có cấu trúc rõ (`data/`, `src/`, `experiments/`, `results/raw/`, `figures/`, `paper/`).

### Giai đoạn 1: Tái lập FALCON (tuần 2–4)
- [ ] Clone artifact FALCON, chạy UniXcoder + cosine trên 6 dự án Defects4J.
- [ ] So với Bảng IV (FALCON 0.731, FAST-log 0.628). Ghi lại sai khác.
- [ ] Viết lại lõi FL + lazy greedy **của riêng bạn**: vector `cur`, sim ≥ 0, phá hòa tất định. Unit test
      "lazy == standard greedy" trên dữ liệu ngẫu nhiên. Kiểm tra số học tính submodular trên các tập ngẫu nhiên.

### Giai đoạn 2: Pipeline dữ liệu LRTS (tuần 3–7, tốn công nhất)
- [ ] Tải LRTS và chọn dự án pilot (ActiveMQ hoặc Karaf).
- [ ] Dựng chuỗi TSR theo ⟨project, stage⟩, sắp theo thời gian. Bảng test-class × build gồm kết quả và thời gian.
- [ ] Áp dụng nhãn DeConf và FirstFail **chỉ cho phía đánh giá**.
- [ ] Lấy mã nguồn test theo build (git worktree, có thể học từ DANTE), embedding mức class, cache theo hash.
- [ ] Viết **script rolling history** và **script kiểm tra leakage** (§5.6).

### Giai đoạn 3: Baseline (tuần 6–8)
- [ ] Random, QTF, MostFail, LatestFail, LatestFail+CC, CCH, FALCON-on-LRTS, trộn thứ hạng.
- [ ] Thử chạy artifact DANTE (Docker). Nếu chạy được thì lấy kết quả trên cùng dự án và cùng quy ước.
- [ ] Đối chiếu số baseline của bạn với Bảng 8/10 của LRTS để kiểm tra pipeline. Nếu QTF hay LatestFail lệch xa
      so với paper thì pipeline đang có lỗi.

### Giai đoạn 4: HC-FALCON (tuần 7–10)
- [ ] Cài đặt `p` (Beta, decay, stickiness), `conf`, `c`/`c̃`, `q`, F_b, lazy greedy và log giải thích.
- [ ] **Pilot go/no-go sớm:** so với FALCON, LatestFail+CC, QTF trên dự án pilot. Nếu thua xa thì thử các biến
      thể ở §8.2, §8.3, §8.5 trước khi mở rộng.
- [ ] Chốt quy trình chọn siêu tham số **không leakage** (warm-up split).

### Giai đoạn 5: Thực nghiệm đầy đủ (tuần 10–13)
- [ ] Mở rộng lên ≥ 3 dự án Java. Chạy RQ1–RQ4, ablation, quét α.
- [ ] Lưu toàn bộ kết quả thô (mỗi build, mỗi phương pháp: π, APFDc, TTFF, thời gian, bộ nhớ).
- [ ] Script tổng hợp bảng, vẽ hình, kiểm định thống kê.

### Giai đoạn 6: Lý thuyết, viết bài, quyết định (tuần 12–16)
- [ ] Viết chứng minh (§6) và phân tích độ phức tạp, kèm số lần tính gain đo được.
- [ ] Đánh giá theo tiêu chí go/no-go (§10).
- [ ] Viết báo cáo kỹ thuật hoặc bản thảo paper 6–10 trang (cấu trúc IEEE: Intro, Background, Approach, Theory,
      Study design, Results, Discussion, Threats, Related work, Conclusion).
- [ ] Bảng limitations và threats to validity (internal / external / construct / conclusion).
- [ ] README tái lập: lệnh chạy từ đầu đến cuối, phiên bản thư viện, seed, phần cứng.

### Checklist sản phẩm bàn giao (đối chiếu `topic1.md` §3.4)

| Sản phẩm | Nội dung cụ thể |
|---|---|
| Mã nguồn + hướng dẫn tái lập | HC-FALCON, baseline, pipeline LRTS, README, file môi trường, seed |
| Script rolling history + kiểm tra leakage | vòng lặp §5.6, kiểm tra bất biến, assert timestamp, kiểm tra ngược |
| Kết quả raw, bảng tổng hợp, script vẽ hình | CSV/JSON theo build; bảng RQ1–RQ4; hình APFDc, đường α, box plot |
| Chứng minh submodular + độ phức tạp | §6, có nêu rõ giới hạn của bảo đảm |
| Báo cáo / bản thảo 6–10 trang | |
| Bảng limitations / threats to validity | |

---

## 10. Hiểu đúng tiêu chí go/no-go

Đề tài chỉ nên phát triển thành paper khi **đủ tất cả** các điều kiện sau:

| Tiêu chí | Cách kiểm tra cụ thể |
|---|---|
| APFDc hoặc TTFF tốt hơn trên **đa số dự án** | Ví dụ ≥ 2/3 dự án thắng có ý nghĩa (Wilcoxon + Holm, δ không phải "negligible") |
| Mô hình kết hợp tốt hơn **cả** FALCON **và** history-only | Lấy từ ablation. Nên so thêm với LatestFail+CC và phép trộn thứ hạng |
| Overhead chấp nhận được | Ví dụ thời gian xếp hạng cộng embedding gia tăng ≪ 1% thời lượng TSR (TSR kéo dài hàng giờ) |
| Không phụ thuộc một dự án hay một α | Đường APFDc theo α tương đối phẳng quanh vùng tốt. α chọn trên warm-up vẫn tốt trên phần đánh giá |
| Rolling evaluation không leakage | Script kiểm tra leakage pass. Có mô tả quy trình trong bài |

**Mức pilot kỳ vọng ~3–5% cải thiện trung vị là ngưỡng để quyết định, không phải kết quả được giả định.** Nếu
pilot không đạt thì kết quả âm tính (*negative result*) được báo cáo trung thực vẫn là một sản phẩm hợp lệ của
đề tài. Ví dụ: "ngữ nghĩa không thêm giá trị so với history+cost trên CI dài hạn". Tuyệt đối không chỉnh dữ liệu
hay chọn lọc dự án để đạt ngưỡng.

---

## 11. Nguồn tham khảo đã dùng

- FALCON (PDF trong repo). Artifact: https://github.com/anonymous-ing/falcon-icst-2026, Zenodo
  10.5281/zenodo.18897073
- LRTS: Cheng et al., ISSTA 2024, https://doi.org/10.1145/3650212.3680307. PDF:
  https://mir.cs.illinois.edu/marinov/publications/ChengETAL24LongRTP.pdf. Artifact:
  https://zenodo.org/records/12662090, https://github.com/lrtsuser/LRTS
- DANTE: https://conf.researchr.org/details/icst-2026/icst-2026-research/44/DANTE-Data-Driven-Test-Case-Selection-and-Prioritization-for-Long-Running-Test-Suite.
  Artifact: https://zenodo.org/records/18900675
- Mahdieh et al.: https://arxiv.org/abs/2106.10524
- Haghighatkhah et al.: https://arxiv.org/abs/1809.00143
- Tài liệu kinh điển cần tự tìm: Nemhauser–Wolsey–Fisher (1978), Minoux (1978), Elbaum–Malishevsky–Rothermel (ICSE
  2001, APFDc), Miranda et al. (FAST, ICSE 2018), Peng et al. (ISSTA 2020), Noor & Hemmati (ISSRE 2015),
  Leskovec et al. (CELF, KDD 2007), Sviridenko (2004).
