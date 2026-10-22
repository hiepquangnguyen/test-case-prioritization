# BẢNG THUẬT NGỮ VÀ ĐỐI CHIẾU MÃ GIAI ĐOẠN (GLOSSARY)

> Tài liệu chuẩn hóa cách dịch thuật ngữ chuyên ngành Anh - Việt và quy định tên gọi mô tả chính thức cho các giai đoạn (Stage) nội bộ trong báo cáo đồ án.

---

## 1. BẢNG THUẬT NGỮ CHUYÊN NGÀNH ANH - VIỆT

| Thuật ngữ Tiếng Anh | Cách dịch Tiếng Việt chuẩn | Ghi chú ngữ cảnh sử dụng |
|:---|:---|:---|
| **Test Case Prioritization (TCP)** | Ưu tiên bộ kiểm thử | Bài toán sắp xếp thứ tự thực thi các bài kiểm thử |
| **Regression Testing** | Kiểm thử hồi quy | Hoạt động kiểm thử phần mềm sau khi mã nguồn thay đổi |
| **Continuous Integration (CI)** | Tích hợp liên tục | Hệ thống tự động biên dịch và kiểm thử liên tục |
| **Continuous Delivery (CD)** | Chuyển giao liên tục | Pha chuyển giao tự động trong đường ống DevOps |
| **Submodular Optimization** | Tối ưu hóa hàm Submodular | Lớp bài toán tối ưu tổ hợp có tính chất lợi tức giảm dần |
| **Diminishing Returns** | Lợi tức giảm dần | Tính chất cận biên giảm khi tập con tăng dần |
| **Facility Location (FL)** | Vị trí cơ sở (hoặc bài toán đặt cơ sở) | Lớp hàm mục tiêu submodular đo độ bao phủ không gian đa dạng |
| **Greedy Algorithm** | Thuật toán tham lam | Thuật toán chọn phần tử có độ tăng cận biên lớn nhất tại mỗi bước |
| **Lazy Greedy / CELF** | Thuật toán tham lam lười | Tối ưu hàng đợi ưu tiên dựa trên tính submodular để giảm tính toán |
| **APFD** | Tỷ lệ phần trăm trung bình lỗi phát hiện | Metric đo vị trí phát hiện lỗi trong dãy kiểm thử |
| **APFDc (Cost-cognizant APFD)** | APFD có nhận thức chi phí | APFD chuẩn hóa theo chi phí thời gian thực thi thực tế |
| **TTFF (Time to First Failure)** | Thời gian tới lỗi đầu tiên | Thời gian tích lũy cho tới khi bài kiểm thử lỗi đầu tiên chạy xong |
| **Recall@k%** | Độ phủ tại ngưỡng ngân sách $k\%$ | Tỷ lệ phần trăm lỗi phát hiện được khi đã tiêu thụ $k\%$ tổng thời gian |
| **Heavy Predecessor** | Tiền nhiệm chạy nặng (thủ phạm trễ) | Lớp kiểm thử không lỗi, chạy lâu, bị thuật toán chèn lên trước test lỗi |
| **Failure History** | Lịch sử lỗi / Tiền sử trượt | Dữ liệu kết quả pass/fail từ các lần build trước |
| **Execution Cost** | Chi phí thực thi | Thời gian chạy thực tế của bài kiểm thử (giây/mili-giây) |
| **Code Representation / Embedding** | Biểu diễn vector mã nguồn | Vector số thực đại diện cho ngữ nghĩa mã kiểm thử |
| **Code Language Model** | Mô hình ngôn ngữ mã nguồn | Mô hình như CodeBERT, UniXcoder |
| **Preregistration** | Tiền đăng ký (Đăng ký trước) | Khóa cố định siêu tham số và luật trước khi chạy thực nghiệm |
| **Decision Gates** | Các cổng thẩm định quyết định | Bộ tiêu chí Effect Gate và Engineering Gates |
| **Effect Gate** | Cổng hiệu quả | Ngưỡng tăng trưởng tối thiểu (ví dụ: $+3,0$ điểm %) so với baseline |
| **Engineering Gates** | Cổng kỹ thuật | Ngưỡng giới hạn bộ nhớ (Memory Gate) và thời gian overhead (Runtime Gate) |
| **Development Screening Split** | Tập dữ liệu sàng lọc phát triển | Tập con dùng để phát triển, chẩn đoán và sàng lọc thuật toán |
| **Reserved Confirmation Split** | Tập dữ liệu xác nhận niêm phong | Tập con độc lập dùng để phúc tra, giữ niêm phong nếu phát triển thất bại |
| **Data Leakage** | Rò rỉ dữ liệu | Hiện tượng dùng thông tin tương lai trong mô phỏng thứ tự kiểm thử |
| **Temporal Causality** | Tính nhân quả theo dòng thời gian | Nguyên tắc chỉ dùng dữ liệu build quá khứ cho build hiện tại |
| **Flaky Test** | Kiểm thử chập chờn | Test đổi trạng thái pass/fail mà không có thay đổi mã nguồn |
| **Paired Delta ($\Delta$)** | Chênh lệch ghép cặp | Hiệu số giữa phương pháp đề xuất và baseline trên cùng một build |
| **Build Stage / Logical Build** | Phân đoạn build / Build logic | Một công đoạn chạy kiểm thử độc lập trong CI (ví dụ: một job trong ma trận môi trường JDK/module) |
| **Physical Build** | Bản build vật lý | Một đợt tích hợp mã nguồn gắn liền với một commit/PR thực tế; gộp nhiều build stage có cùng commit để tránh pseudo-replication |

---

## 2. BẢNG MÃ ĐỐI CHIẾU CÁC GIAI ĐOẠN NỘI BỘ (STAGES)

> **Quy tắc bắt buộc:** Trong văn bản báo cáo chính (Chương 3, 4, 5), tuyệt đối **không** dùng mã trần ("Stage 6", "Stage 12") mà phải luôn sử dụng kèm **Tên mô tả chính thức** theo bảng dưới đây.

| Mã nội bộ | Tên mô tả chính thức trong báo cáo | Mô tả kỹ thuật cốt lõi |
|:---:|:---|:---|
| **Stage 1** | Rà soát dữ liệu đầu vào và kiểm định khả thi | Kiểm tra toàn vẹn dữ liệu Defects4J, LRTS và mô hình UniXcoder |
| **Stage 2** | Thiết lập môi trường thử nghiệm sơ bộ | Dựng pipeline chạy thử và các baseline cơ sở |
| **Stage 3** | Khảo sát thí điểm Karaf | Thử nghiệm mô phỏng trên tập Karaf exploratory |
| **Stage 4** | Thiết kế kiến trúc và mô hình toán học HC-FALCON v1 | Xây dựng hàm mục tiêu kết hợp Submodular và Bayes |
| **Stage 5** | Trích xuất mã nguồn và tiền xử lý vector embedding | Trích xuất 1.155 test class LRTS và tạo vector UniXcoder |
| **Stage 6** | Thử nghiệm mô hình kết hợp cơ sở (HC-FALCON v1) | Đánh giá hai biến thể `topic_raw` và `normalized` trên LRTS |
| **Stage 7** | Chẩn đoán nguyên nhân sâu và phát hiện Heavy Predecessors | Phân tích 161 build lỗi và đo đạc độ trễ thêm vào $T_{add}$ |
| **Stage 8** | Biến thể hạn chế ngữ nghĩa theo cửa sổ lịch sử | Thử nghiệm áp trần điểm lịch sử ($q \ge 0,95 q_{\max}$) |
| **Stage 9** | Kiểm tra độ chuẩn xác kỹ thuật và tính toàn vẹn | Đảm bảo tính toán đúng và kiểm tra rò rỉ dữ liệu |
| **Stage 10** | Tái lập độc lập FALCON trên Defects4J | Tái lập 6 dự án Defects4J và phân rã Bridge Chart A/B/C/D |
| **Stage 11** | Biến thể CNS-Greedy và phân tích nguyên nhân hệ thống | Chuẩn hóa chi phí vào hàm tham lam ngữ nghĩa và đo forensic 161 build |
| **Stage 12** | Biến thể UGCS v2 và đánh giá cổng quyết định | Thuật toán bảo vệ bất định 4 bước và phán quyết NO-GO chính thức |

---

## 3. BẢNG ĐỐI CHIẾU CÁC BIẾN THỂ THUẬT TOÁN

| Mã nội bộ | Tên gọi chuẩn trong báo cáo | Công thức / Cơ chế cốt lõi |
|:---|:---|:---|
| `history_cost` | Baseline Lịch sử và Chi phí | Sắp xếp theo $q_b(t) = \frac{p_b(t) \cdot \text{conf}_b(t)}{\sqrt{c_b(t)}}$ |
| `fl_only` | Baseline Ngữ nghĩa Submodular thuần túy | Tối ưu hàm bao phủ Submodular Facility Location $FL(S)$ |
| `hc_falcon_topic_raw_v1` | HC-FALCON v1 dạng Trọng số thô | $F_N(S) = \frac{FL(S)}{n} + \sum_{t \in S} q_b(t)$ |
| `hc_falcon_normalized_v1` | HC-FALCON v1 dạng Chuẩn hóa (Stage 6) | $F_N(S) = \frac{FL(S)}{n} + \sum_{t \in S} \frac{q_b(t)}{\sum q}$ |
| `restricted_v1` | Biến thể Hạn chế Ngữ nghĩa (Stage 8) | Giới hạn ứng viên trong cửa sổ động: $q_b(i) \ge 0{,}95 q_b(t^*)$ và $c_b(i) \le 1{,}25 c_b(t^*)$ (neo theo baseline $t^*$) |
| `hc_cns_v1` | Biến thể CNS-Greedy (Stage 11) | Lợi ích biên kết hợp: $\alpha \cdot \frac{\Delta FL(t \mid S)}{n \cdot \sqrt{\max(c(t), 10^{-6})}} + (1 - \alpha) \cdot w(t)$ với $c(t)$ là thời lượng thô tính bằng giây, $w(t) = q(t) / \sum q$ |
| `hc_ugcs_v2` | Biến thể UGCS v2 (Stage 12) | 4 bước: Ước lượng Bayes $\to$ Khoanh vùng bất định $\to$ Greedy có ý thức chi phí $\to$ Tie-breaking |

---

## 4. BẢNG ĐỐI CHIẾU CÁC KHÓA ĐỘ ĐO KỸ THUẬT (ENGINEERING METRICS)

| Tên khóa trong JSON | Tên chuẩn trong báo cáo | Định nghĩa toán học & Nguồn sinh mã |
|:---|:---|:---|
| `median_latency_hc_seconds` | Độ trễ trung vị mỗi stage của `history_cost` | Thời gian xếp hạng trung vị mỗi build stage của baseline `history_cost` ($0,11$ ms, tức $0,0001126$ s). **Lưu ý quan trọng:** Tiếp vĩ ngữ `hc` ở đây là viết tắt của baseline **`history_cost`**, tuyệt đối không phải HC-FALCON. Nguồn mã: `scripts/stage12_evaluate.py#L880-L881, L992`. |
| `median_latency_ugcs_seconds` | Độ trễ trung vị mỗi stage của UGCS v2 | Thời gian xếp hạng trung vị mỗi build stage của phương pháp đề xuất UGCS v2 ($53,82$ ms, tức $0,053819$ s). Nguồn mã: `scripts/stage12_evaluate.py#L890-L891, L991`. |
| `p95_warm_overhead_fraction` | Tỷ lệ overhead P95 của UGCS v2 vs `history_cost` | Phân vị thứ 95 của tỷ số gia tăng thời gian chạy giữa UGCS v2 và `history_cost`: $\text{Overhead}_{\text{stage}} = \frac{T_{\text{ugcs}} - T_{\text{hc}}}{\max(T_{\text{hc}}, 10^{-9})}$. Mẫu số chuẩn hóa chính là thời gian chạy của baseline `history_cost`. Quan sát đạt $14.257,90\times$ ($+1.425.790\%$). Nguồn: `scripts/stage12_evaluate.py#L894-L895, L985`. |
| *P95 Latency tuyệt đối* | Phân vị P95 tuyệt đối (ms) | **Không xác định được** từ `reports/stage12/development-screen.json` do tệp báo cáo chỉ lưu trung vị độ trễ của từng phương pháp và tỷ lệ trần P95 toàn cục. |

