# Đề tài 1: Ưu tiên test case bằng tối ưu hóa submodular có xét lịch sử lỗi và thời gian chạy

## 1. Bài toán, định nghĩa, đầu vào, đầu ra

### 1.1. Bài toán

Trong quy trình Continuous Integration/Continuous Delivery (CI/CD), mỗi lần phần
mềm thay đổi, hệ thống có thể phải chạy hàng trăm hoặc hàng nghìn test case.
Chạy toàn bộ test suite tốn nhiều thời gian, trong khi mục tiêu thực tế là phát
hiện lỗi càng sớm càng tốt.

Bài toán **Test Case Prioritization (TCP)** yêu cầu sắp xếp lại thứ tự các test
case mà không thay đổi nội dung của chúng. Các test nằm ở đầu danh sách nên:

- có khả năng phát hiện lỗi cao;
- chạy tương đối nhanh;
- đại diện cho nhiều nhóm hành vi khác nhau;
- tránh lặp lại sớm nhiều test gần giống nhau;
- không bỏ quên test mới chưa có lịch sử chạy.

Đề tài phát triển một phương pháp training-free kết hợp ba nguồn thông tin:
semantic similarity, lịch sử pass/fail và thời gian chạy của test.

### 1.2. Định nghĩa và mô hình toán học

Tại build thứ $b$, ký hiệu tập test case là

$$
T_b=\{t_1,t_2,\ldots,t_n\}.
$$

Mỗi test $t$ có:

- $z(t)$: embedding sinh từ mã nguồn test;
- $\operatorname{sim}(u,t)\geq 0$: độ tương đồng ngữ nghĩa giữa hai test;
- $p_b(t)$: xác suất test thất bại, chỉ ước lượng từ các build trước $b$;
- $c_b(t)>0$: thời gian chạy ước lượng;
- $\operatorname{conf}_b(t)$: độ tin cậy của lịch sử. Test mới hoặc ít được
  chạy có confidence thấp.

Điểm lỗi-chi-phí của một test có thể được định nghĩa bởi

$$
q_b(t)=
\frac{\operatorname{conf}_b(t)p_b(t)}
{\sqrt{\widetilde c_b(t)}+\varepsilon},
$$

trong đó $\widetilde c_b(t)$ là thời gian chạy đã chuẩn hóa.

Độ bao phủ ngữ nghĩa của một tập test $S$ được đo bằng facility location:

$$
FL_b(S)=\sum_{u\in T_b}\max_{t\in S}\operatorname{sim}(u,t).
$$

Hàm mục tiêu đề xuất là

$$
F_b(S)=
\alpha\frac{FL_b(S)}{|T_b|}
+(1-\alpha)\sum_{t\in S}q_b(t),
\qquad 0\leq\alpha\leq 1.
$$

Với ngân sách $k$, bài toán là

$$
\max_{S\subseteq T_b,\ |S|\leq k}F_b(S).
$$

Nếu similarity và các trọng số không âm thì $F_b$ là monotone submodular.
Greedy lần lượt chọn test có marginal gain lớn nhất và đạt bảo đảm
$1-1/e$ dưới ràng buộc cardinality. Chạy greedy đến hết tập test tạo ra thứ
tự đầy đủ $\pi_b=(t_{\pi_1},\ldots,t_{\pi_n})$; $k$ phần tử đầu là nghiệm
greedy cho ngân sách $k$.

### 1.3. Đầu vào

- Mã nguồn hoặc embedding của các test case trong build hiện tại.
- Kết quả pass/fail của các test trong những build trước.
- Thời gian chạy lịch sử hoặc thời gian chạy ước lượng.
- Ngân sách $k$, hoặc yêu cầu tạo thứ tự đầy đủ.
- Tham số cân bằng $\alpha$ và tham số làm mượt lịch sử.

Quy tắc bắt buộc: khi xếp hạng cho build $b$, không được dùng kết quả của
build $b$ hoặc bất kỳ build tương lai nào.

### 1.4. Đầu ra

- Một thứ tự chạy toàn bộ test suite.
- Các tập test ưu tiên ứng với nhiều ngân sách $k$.
- Marginal gain và lý do mỗi test được ưu tiên.
- Báo cáo APFD/APFDc, Time to First Failure, thời gian xếp hạng và bộ nhớ.

## 2. Paper nền

### 2.1. Paper chính

**FALCON: Efficient Test Case Prioritization via Submodular Optimization**,
Mensah-Boateng, Yuan và Do, IEEE ICST 2026.

Tài liệu trong repo:

- PDF gốc: `falcon-icst-2026.pdf`
- Tài liệu đọc hiểu: `docs/00-foundations/doc-hieu-de-tai.md`
- Công thức và thuật toán: `docs/00-foundations/thuat-toan-va-ly-thuyet.md`
- Kiểm tra artifact: `docs/01-feasibility/stage1-report.md`
- Manifest/checksum: `references/artifact-manifest.md`

FALCON mã hóa test method bằng pretrained code language model, tính ma trận
similarity và dùng lazy greedy để tối ưu facility location. Paper báo cáo kết
quả trên 288 fault versions của sáu dự án Defects4J.

Các hạn chế trực tiếp tạo ra đề tài:

- FALCON chủ yếu tối ưu semantic coverage/diversity.
- Failure history chưa phải một thành phần rõ ràng của objective.
- Execution time chưa được dùng trực tiếp để đưa test ngắn và có rủi ro cao
  lên đầu.
- Đánh giá Defects4J chưa phản ánh đầy đủ chuỗi build CI thực tế.

### 2.2. Paper bổ trợ

**DANTE: Data-Driven Test Case Selection and Prioritization for Long-Running
Test Suites**, Reale et al., IEEE ICST 2026.

DANTE là phương pháp training-free khai thác failure history, test duration và
commit information trên Long-Running Test Suites (LRTS). Đây là baseline quan
trọng: DANTE mạnh về history/cost, còn FALCON mạnh về semantic diversity.

Tài liệu trong repo:

- PDF bản tác giả: `dante-icst-2026.pdf`
- Tài liệu đọc hiểu: `docs/00-foundations/doc-hieu-de-tai.md`
- Công thức và thuật toán: `docs/00-foundations/thuat-toan-va-ly-thuyet.md`
- Kiểm tra artifact: `docs/01-feasibility/stage1-report.md`

Sinh viên cũng phải khảo sát FAST, history-based/cost-aware TCP, các phương
pháp kết hợp diversification với fault-proneness và TCP approach combinators.
Không được tuyên bố đây là công trình đầu tiên kết hợp history và diversity.

Lưu ý: hai PDF đã được đối chiếu ngày 2026-09-03. DANTE hiện là bản tác giả đầy
đủ, không phải file dàn trang IEEE cuối. Các chi tiết implementation chưa nêu rõ
trong paper vẫn phải được kiểm tra bằng artifact đã pin trước khi tái hiện.

## 3. Hướng phát triển

### 3.1. Phương pháp đề xuất

Xây dựng phương pháp tạm gọi **HC-FALCON**:

1. Sinh embedding và semantic similarity cho các test.
2. Ước lượng failure probability bằng Beta-Bernoulli, exponential decay hoặc
   failure stickiness.
3. Tính confidence dựa trên lượng lịch sử quan sát được.
4. Kết hợp facility location với failure-history/cost thành hàm $F_b$.
5. Dùng lazy greedy để tạo thứ tự test.
6. Chỉ cập nhật lịch sử sau khi build hiện tại kết thúc.

Phần lý thuyết tối thiểu:

- chứng minh thành phần history/cost là modular không âm;
- chứng minh $F_b$ là monotone submodular;
- suy ra bảo đảm $1-1/e$ của cardinality greedy;
- phân tích thời gian và bộ nhớ của standard/lazy greedy.

### 3.2. Câu hỏi nghiên cứu

- RQ1: HC-FALCON có phát hiện lỗi sớm hơn FALCON và history-based baseline?
- RQ2: Semantic, history và cost đóng góp bao nhiêu?
- RQ3: Phương pháp hoạt động thế nào với test mới và flaky tests?
- RQ4: Chi phí embedding và xếp hạng có phù hợp CI/CD?

### 3.3. Thực nghiệm

Datasets:

- Artifact FALCON/Defects4J để tái lập kết quả nền.
- Tối thiểu ba dự án Java trong LRTS để đánh giá tuần tự theo thời gian.

Baselines:

- Random, Shortest-Test-First, Most-Fail và Recent-Fail;
- FAST, FALCON và DANTE nếu artifact chạy được;
- phép trộn thứ hạng đơn giản giữa FALCON và history score.

Metrics:

- APFD, APFDc hoặc relative APFDc;
- Time to First Failure;
- tỷ lệ lỗi được phát hiện trong 10%, 25% và 50% ngân sách đầu;
- prioritization runtime và memory;
- Wilcoxon signed-rank, Holm correction và Cliff's delta.

Ablation bắt buộc: FALCON thuần, history-only, history+cost,
facility-location+history, mô hình đầy đủ và mô hình đầy đủ bỏ confidence.

### 3.4. Sản phẩm sinh viên phải bàn giao

- Mã nguồn và hướng dẫn tái lập.
- Script xử lý rolling history và kiểm tra data leakage.
- Kết quả raw, bảng tổng hợp và script vẽ hình.
- Chứng minh tính submodular và phân tích độ phức tạp.
- Báo cáo kỹ thuật hoặc bản thảo paper 6-10 trang.
- Bảng limitations/threats to validity.

### 3.5. Tiêu chí go/no-go

Chỉ nên phát triển thành paper nếu:

- APFDc hoặc Time to First Failure tốt hơn trên đa số dự án;
- mô hình kết hợp tốt hơn cả FALCON và history-only;
- overhead vẫn chấp nhận được trong CI;
- kết quả không phụ thuộc một dự án hay một giá trị $\alpha$ duy nhất;
- rolling evaluation không có data leakage.

Mức kỳ vọng cho pilot là cải thiện trung vị khoảng 3-5% trên metric chính.
Đây là tiêu chí quyết định có tiếp tục hay không, không phải kết quả được phép
giả định trước.
