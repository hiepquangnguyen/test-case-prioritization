# Quyết định đóng Phase R và Báo cáo nghiệm thu kỹ thuật (Decision)

Tài liệu này là quyết định đóng chính thức của **Phase R (Tái lập và Bridge Chart)** trong dự án nghiên cứu Đánh giá độ ưu tiên bộ kiểm thử (Test Case Prioritization), tuân thủ đúng các cam kết trong [README bàn giao](../10-handoff/README.md) và [Bảng công việc](../10-handoff/tasks.json).

---

## 1. Kết luận nghiệm thu tổng thể Phase R

Toàn bộ **10 tasks của Phase R (T00 đến T09)** đã được thực thi và nghiệm thu thành công 100%:

1. **Nghiệm thu tái lập 6 dự án Defects4J (T04–T06)**:
   - Tái chạy thành công toàn bộ **20.770 test methods** và **288 fault IDs** trên 6 dự án: Chart, Mockito, Lang, Math, Time, Closure.
   - Điểm số APFD tái lập trung bình đạt **0.725976** so với **0.722310** của tác giả (sai lệch trung bình toàn bộ chỉ **+0.003666** hay +0.37 điểm phần trăm).
   - Dự án Lang đạt độ trùng khớp tuyệt đối 100% ($\Delta = 0.000000$); Mockito lệch chỉ 0.0028 điểm phần trăm; Closure lệch chỉ 0.16 điểm phần trăm.
2. **Nghiệm thu phân rã 4 nhánh Bridge Chart A/B/C/D (T07–T08)**:
   - Nhánh A (Artifact Baseline): APFD = **0.732278**.
   - Nhánh B (Clipped Kernel): APFD = **0.732278** ($\Delta_{B-A} = 0.000000$).
   - Nhánh C (Internal Greedy FQN): APFD = **0.732278** ($\Delta_{C-B} = 0.000000$).
   - Nhánh D (Full Internal Pipeline): APFD = **0.763531** ($\Delta_{D-C} = +0.031253$, $\Delta_{D-A} = +0.031253$).
   - Kết luận nguyên nhân: Toàn bộ mức tăng APFD (+3.13%) của pipeline nội bộ (Nhánh D) bắt nguồn từ **cơ chế tiền xử lý code và attention mask**. Phép cắt ngưỡng toán học ($B - A$) và thuật toán ranker nội bộ ($C - B$) có làm thay đổi thứ tự ưu tiên các test cases (lệch lần lượt 42 và 24 vị trí), nhưng bảo toàn toàn bộ 26 thứ hạng phát hiện lỗi đầu tiên nên APFD không đổi ($\Delta = 0.000000$), do đó không giải thích được mức tăng điểm của D.

---

## 2. Phân loại kỹ thuật và Ranh giới khoa học

| Hạng mục | Phân loại | Diễn giải |
|---|---|---|
| **Rerun vs Author APFD** | *Declared Environment & Provenance* | Chênh lệch APFD nhỏ giữa các lần chạy (+0.37%) bắt nguồn từ việc pin môi trường offline, phiên bản thư viện hiện đại (PyTorch 2.14, Transformers 5.17), và độ nhạy của thứ tự tie-breaking. Không phải là lỗi logic. |
| **Ranker Greedy Internal vs Upstream** | *Permutation Shift with Metric Invariance* | Thuật toán exact greedy nội bộ với FQN tie-breaking làm thay đổi vị trí của 24 test cases so với upstream lazy greedy, nhưng bảo toàn chính xác 26 mốc phát hiện lỗi đầu tiên và giữ nguyên APFD ($0.732278$). |
| **Pipeline Nội bộ vs Artifact** | *Intentional Architectural Improvement* | Nhánh D có APFD cao hơn (+3.13%) do sử dụng attention mask loại bỏ padding token và chia chunk code hàm dài. |
| **Kết quả LRTS CI** | *Strictly Invariant (NO-GO)* | **Tuyệt đối không** dùng kết quả tái lập Defects4J hay điểm số của Nhánh D để lật ngược kết luận gate LRTS (0/3). HC-FALCON không chứng minh được ưu thế trên CI dài hạn. |
| **Tập dữ liệu Reserved** | *Strictly Closed* | Các tập dữ liệu reserved của ActiveMQ và Log4j tiếp tục được **niêm phong đóng hoàn toàn**, chưa từng bị mở score hay can thiệp. |

---

## 3. Tuân thủ giới hạn vận hành

- **Bộ nhớ**: Đỉnh RAM cao nhất trong toàn bộ Phase R là **1.643 GiB** (Closure), nằm an toàn dưới trần quy định 8.0 GiB.
- **Thời gian**: Thời gian chạy đơn lẻ dài nhất là 55.34 phút (Closure), tuân thủ giới hạn 8.0 giờ/dự án.
- **Độc quyền luồng**: Chỉ duy nhất 1 tiến trình worker thực thi tại một thời điểm, không gây nhiễu đo lường thời gian.
- **Tính toàn vẹn niêm phong**: Toàn bộ 6 tệp freeze từ Stage 4 đến Stage 9 giữ nguyên vẹn 100%.

---

## 4. Quyết định kết thúc Phase R

1. **Đóng Phase R**: Đánh dấu toàn bộ Phase R (T00 đến T09) ở trạng thái **`COMPLETED`**.
2. **Khóa niêm phong bằng chứng mới**: Tạo [`reports/stage10/evidence-freeze.json`](../../reports/stage10/evidence-freeze.json) niêm phong toàn bộ các tệp kết quả của Stage 10.
3. **Các phase tiếp theo**:
   - **Phase W** (Viết báo cáo lý thuyết T10): Tạm dừng ở trạng thái chưa mở, chỉ thực hiện khi người dùng có chỉ thị riêng.
   - **Confirmation C00**: Tiếp tục **bị chặn (Blocked)** do điều kiện gate LRTS chưa đạt.
