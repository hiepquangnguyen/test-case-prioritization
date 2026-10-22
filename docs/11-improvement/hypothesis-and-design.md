# Tài liệu Giả thuyết Cải tiến và Thiết kế Thí nghiệm (Phase 2)

**Ngày lập**: 2026-09-16  
**Căn cứ**: Báo cáo phân tích forensic [forensic-report.md](forensic-report.md) và kết quả 161 build lỗi.

---

## 1. Các Giả thuyết Cải tiến Có Bằng chứng Hỗ trợ

### Giả thuyết A (Cost-Normalized Semantic Greedy — CNS-Greedy) [Ưu tiên 1]
- **Bằng chứng từ Phase 1**:
  - Semantic gây trễ lũy kế ròng tới **+39.099,3 giây** trên 161 builds lỗi, nặng nhất tại ActiveMQ (+43.886,3s).
  - Thành phần lịch sử $q_b(t)$ trong Topic 1 đã được chia cho $\sqrt{\widetilde{c}_b(t)}$, nhưng thành phần Semantic $\Delta FL(t \mid S)/n$ lại **hoàn toàn phi chi phí (cost-agnostic)**.
  - Điều này khiến các test chạy 100–150s có cùng trọng lượng ngữ nghĩa với test chạy 0,001s, dễ dàng bị greedy chọn sớm chỉ vì marginal coverage nhỉnh hơn một chút.
- **Cơ chế cải tiến**:
  Đưa yếu tố chi phí thời gian vào chính thành phần ngữ nghĩa ở mỗi bước greedy:
  $$\Delta \text{Gain}(t \mid S) = \alpha \frac{\Delta FL(t \mid S) / |T_b|}{\sqrt{\widetilde{c}_b(t)}} + (1 - \alpha) w_b(t)$$
  hoặc chuẩn hóa tỷ số chi phí toàn diện (Knapsack Submodular Ratio):
  $$\Delta \text{Gain}(t \mid S) = \frac{\alpha \frac{\Delta FL(t \mid S)}{|T_b|} + (1 - \alpha) w_b(t)}{(\widetilde{c}_b(t))^\gamma}$$
- **Mục tiêu**: Loại trừ hiện tượng test nặng không lỗi chen ngang, giữ lại trọn vẹn 38 ca thắng lớn của semantic.

---

### Giả thuyết B (Tiered History-Semantic Optimization — THS-Greedy) [Ưu tiên 2]
- **Bằng chứng từ Phase 1**:
  - Stage 8 (Restricted v1) áp dải lọc $q \ge 0.95 q_{head}$ quá hẹp (5%), làm triệt tiêu khả năng tìm kiếm của semantic (chỉ còn 13 ca thắng ở Karaf).
  - Ngược lại, Stage 6 để semantic tự do cạnh tranh trực tiếp với lịch sử ($w_b(t)$) dẫn tới việc semantic lấn át (chiếm 97–99% gain đầu).
- **Cơ chế cải tiến**:
  Phân tầng test case theo mức độ tin cậy của lịch sử:
  - **Tầng 1 (High Confidence Risk)**: Các test có $q_b(t) \ge \theta_{high} \cdot q_{\max}$ (test có lịch sử fail rõ ràng).
  - **Tầng 2 (Moderate Risk / Historical Candidates)**: Các test có $0 < q_b(t) < \theta_{high} \cdot q_{\max}$.
  - **Tầng 3 (Cold-start / Zero History)**: Các test chưa từng fail ($N=0$ hoặc $F=0$).
  Trong mỗi tầng, áp dụng greedy semantic kết hợp chi phí $\Delta FL(t \mid S) / \sqrt{\widetilde{c}_b(t)}$ để đa dạng hóa tối đa khả năng phát hiện lỗi trong phạm vi tầng đó trước khi chuyển sang tầng tiếp theo.
- **Mục tiêu**: Bảo vệ tuyệt đối các test lỗi có độ tin cậy cao không bị trễ, đồng thời phát huy tối đa sức mạnh phân loại của semantic trong nhóm test cold-start và nhóm rủi ro tương đương.

---

## 2. Thiết kế Thí nghiệm Có Kiểm soát (Phase 3 Design)

### 2.1. Ma trận Biến thể Cần Đánh giá (Cohort)

| Tên biến thể | Cơ chế cốt lõi | Siêu tham số khóa trước chạy |
|---|---|---|
| `hc_cns_v1` (Ứng viên A1) | Cost-normalized semantic greedy | $\alpha = 0.5$, mẫu số semantic $\sqrt{\widetilde{c}_b(t)}$ |
| `hc_knapsack_v1` (Ứng viên A2) | Knapsack submodular greedy | $\alpha = 0.5, \gamma = 0.5$ |
| `hc_tiered_v1` (Ứng viên B) | Tiered history-semantic greedy | Tầng theo phân vị $q$: $q \ge 0.5 q_{\max}$, $q > 0$, $q = 0$ |

### 2.2. Giao thức Đánh giá Bắt buộc (Tuân thủ Evaluation Protocol v1)
1. **Dữ liệu**: Chạy trên toàn bộ 596 build stages thuộc tập **Development** của cả 3 dự án (Karaf, ActiveMQ, Log4j). Sử dụng 3.647 vector embedding UniXcoder đã lưu trong cache `work/cache/stage6/vectors/`.
2. **Đối chứng so sánh**:
   - `history_cost` (Baseline chính, đã freeze)
   - `hc_falcon_normalized_v1` (Stage 6, đã freeze)
   - `fl_only` (Stage 6, đã freeze)
3. **Chỉ số và Đơn vị thống kê**:
   - Đơn vị: Physical build paired delta (mean của các stage trong build, sau đó tính paired $\Delta = \text{APFDc}_{\text{candidate}} - \text{APFDc}_{\text{comparator}}$).
   - Chỉ số chính: **Median paired $\Delta$ APFDc midpoint**.
   - Kiểm tra đánh đổi: TTFF (Time to First Failure) và Recall@10%.
4. **Ngưỡng Cổng (Effect Gate)**:
   $$\text{Median } \Delta\text{APFDc} \ge +0.0300 \quad (+3.0 \text{ điểm phần trăm})$$
   so với **CẢ HAI** đối chứng (`history_cost` và `fl_only`) trên **ít nhất 2 trong 3 dự án**.
5. **Ràng buộc an toàn**:
   - Tuyệt đối không mở tập Reserved (ActiveMQ/Log4j confirmation).
   - Giới hạn tối đa 2 vòng thử nghiệm (vòng 1: đánh giá A1, A2, B; vòng 2: tinh chỉnh 1 biến thể tốt nhất nếu có triển vọng). Nếu cả 2 vòng không đạt, ghi nhận kết quả âm theo đúng quy định fidelity.
