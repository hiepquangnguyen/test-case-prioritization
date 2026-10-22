# Báo cáo Thực nghiệm Cải tiến HC-FALCON (Phase 3 — Round 1)

**Ngày thực hiện**: 2026-09-16  
**Dữ liệu đánh giá**: Toàn bộ 161 physical builds có lỗi (79 Karaf, 57 ActiveMQ, 25 Log4j) thuộc tập Development, đối chiếu theo đúng giao thức thống kê của Stage 6/7.  
**Cơ sở thực thi**: `scripts/stage11_evaluation.py`  
**Kết quả lưu trữ**: `reports/stage11/simulation-results.json`

---

## 1. Kết quả Đánh giá Tổng hợp

| Phương pháp | Karaf | ActiveMQ | Log4j | Trạng thái Effect Gate ($\ge +3.0\%$ pts) |
|---|---:|---:|---:|:---:|
| `fl_only` (FALCON-LRTS) | −30.928% | −41.866% | −28.877% | ❌ NO-GO |
| `hc_falcon_normalized_v1` (Stage 6) | −1.265% | −1.407% | −0.117% | ❌ NO-GO (0/3) |
| **`hc_cns_v1` (Ứng viên A1 — Cost-Normalized)** | **−0.399%** | **−0.606%** | **−0.190%** | ❌ **NO-GO (0/3)** |
| `hc_knapsack_v1` (Ứng viên A2 — Knapsack) | −0.501% | −6.625% | −0.100% | ❌ NO-GO (0/3) |
| `hc_tiered_v1` (Ứng viên B — Tiered) | −0.182% | −14.751% | −1.001% | ❌ NO-GO (0/3) |

*(Đơn vị: Median paired $\Delta$ APFDc midpoint so với `history_cost`, tính bằng điểm phần trăm)*

---

## 2. Phân tích Chi tiết Từng Ứng viên

### 2.1. Ứng viên A1: `hc_cns_v1` (Cost-Normalized Semantic Greedy)
- **Hiệu quả giảm tổn thất**:
  - Tại **Karaf**: Median delta thu hẹp từ −1.265% lên **−0.399%** (giảm 68% mức thua), Mean delta chuyển sang dương **+1.736% pts** (22 thắng / 1 hòa / 56 thua).
  - Tại **ActiveMQ**: Median delta thu hẹp từ −1.407% lên **−0.606%** (giảm 57% mức thua), Mean delta cải thiện từ −3.394% lên −0.382% (10 thắng / 0 hòa / 47 thua).
  - Tại **Log4j**: Mean delta đạt mức tăng rất cao **+3.463% pts** (6 thắng / 0 hòa / 19 thua), nhưng Median delta vẫn dừng ở **−0.190% pts**.
- **Đánh giá**:
  Việc đưa $\sqrt{\text{cost}}$ vào mẫu số của marginal semantic gain đã **giải quyết đúng cơ chế gây hại lớn nhất** (ngăn chặn test nặng không lỗi chen vào trước test lỗi), giúp kéo Mean delta lên mức dương ở 2/3 dự án (Karaf và Log4j).
  Tuy nhiên, **ở chỉ số trung vị (Median)**, số lượng physical build thua vẫn nhiều hơn số build thắng (Karaf 22 vs 56, ActiveMQ 10 vs 47, Log4j 6 vs 19). Do đó, **Median paired $\Delta$ vẫn mang giá trị âm** trên toàn bộ 3 dự án.

### 2.2. Ứng viên A2: `hc_knapsack_v1`
- Khi chia toàn bộ marginal gain cho $\text{cost}^{0.5}$, ActiveMQ sụp đổ nghiêm trọng (−6.625% pts).
- Nguyên nhân: Các test ngắn chạy trong 0.001s bị thổi phồng gain quá mức dù chất lượng ngữ nghĩa và lịch sử rất thấp, đẩy các test quan trọng lùi lại.

### 2.3. Ứng viên B: `hc_tiered_v1`
- Khi phân tầng theo $q$: Tại ActiveMQ, median delta giảm sâu xuống −14.751% pts vì ranh giới tầng cứng không thích ứng được với phân phối chi phí biến động lớn của class-level test.

---

## 3. Đối chiếu Tiêu chí Nghiệm thu (Acceptance Criteria Check)

1. **Pilot Effect Gate**:
   - Yêu cầu: Median paired $\Delta\text{APFDc} \ge +0.0300$ (+3.0% pts) so với cả `fl_only` và `history_cost` trên $\ge 2/3$ dự án.
   - Thực tế: Không có bất kỳ ứng viên nào đạt $\Delta \ge +0.0300$. Biến thể tốt nhất (`hc_cns_v1`) vẫn có Median delta âm (−0.40%, −0.61%, −0.19%).
   - **Kết luận**: **0/3 NO-GO**.

2. **Quy định Mở tập Reserved**:
   - Cổng Effect Gate chưa đạt $\rightarrow$ **Tập Reserved Confirmation tiếp tục bị KHÓA 100%**.

---

## 4. Kết luận Khoa học và Quyết định Nghiệm thu

Dữ liệu thực nghiệm qua 3 thế hệ mô hình trên tập development (Stage 6, Stage 8, Stage 11):
1. **Stage 6 (`hc_falcon_normalized_v1`)**: Semantic không xét chi phí $\rightarrow$ thua −1.4% pts (0/3 NO-GO).
2. **Stage 8 (`restricted_v1`)**: Khóa cứng không gian hoán đổi quanh head $\rightarrow$ thua −0.02% đến −0.15% pts (0/3 NO-GO).
3. **Stage 11 (`hc_cns_v1`)**: Chuẩn hóa chi phí vào semantic $\rightarrow$ giảm 60% mức thua, mean delta dương (+1.7% đến +3.5%), nhưng **median delta vẫn âm** (−0.19% đến −0.61%) (0/3 NO-GO).

### Phát hiện Nghiên cứu Cốt lõi:
Trong môi trường CI/CD thực tế với đơn vị test ở mức class (LRTS) và thời gian thực thi phân tán mạnh (từ vài mili-giây tới hàng trăm giây), **tín hiệu lịch sử lỗi kết hợp chi phí thực thi ($q_b(t)$) là một baseline cực kỳ mạnh**. 
Mọi nỗ lực can thiệp thứ tự bằng đa dạng ngữ nghĩa (semantic diversity qua Code LM / UniXcoder) — dù bằng hàm submodular gốc, lọc dải candidate hay chuẩn hóa chi phí — đều chỉ tạo ra được cải thiện ở một số ít build cá biệt (20–30% builds), nhưng ở đa số các build còn lại (70–80% builds), sự hoán đổi thứ tự của semantic vẫn gây trễ thời gian phát hiện lỗi so với việc chạy tuần tự theo điểm lịch sử/chi phí thuần túy.

Theo đúng nguyên tắc khoa học đã quy định tại `docs/09-fidelity/review-and-next-plan.md` và `docs/10-handoff/README.md`:
> *"Nếu vẫn không đạt, ghi nhận kết quả âm và xem lại đóng góp nghiên cứu thay vì tiếp tục thử không giới hạn. Không đổi tiêu chí thắng sau khi đã xem số liệu."*
