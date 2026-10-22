# Báo cáo Phân tích Forensic LRTS Development (Phase 1)

**Ngày thực hiện**: 2026-09-16  
**Dữ liệu phân tích**: 161 physical builds có lỗi (79 Karaf, 57 ActiveMQ, 25 Log4j) trên tập development của Stage 6 và chẩn đoán Stage 7.  
**Mục tiêu**: Làm rõ khi nào và vì sao semantic giúp hoặc hại, từ đó xác định liệu có nguồn cải thiện thực sự trên LRTS class-level hay không.

---

## 1. Phân loại Builds Thắng vs Thua (Phát hiện 1A)

| Dự án | Tổng builds có lỗi | Thắng (Win) | Thua (Loss) | Hòa (Tie) | Tỷ lệ Thắng | Median $\Delta$ của Wins | Median $\Delta$ của Losses |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Karaf** | 79 | **24** | 54 | 1 | 30.4% | **+3.55%** pts (max +77.25%) | −2.27% pts (min −57.58%) |
| **ActiveMQ** | 57 | **10** | 47 | 0 | 17.5% | **+0.42%** pts (max +19.92%) | −1.62% pts (min −51.50%) |
| **Log4j** | 25 | **4** | 21 | 0 | 16.0% | **+10.52%** pts (max +18.31%) | −0.13% pts (min −5.73%) |
| **Tổng cộng** | **161** | **38** | **122** | **1** | **23.6%** | — | — |

### Quan sát:
1. **Phân phối $\Delta$APFDc bất đối xứng nghiêm trọng**:
   - Ở các build thắng, mức tăng rất lớn (Karaf median +3.55% pts, max +77.25% pts; Log4j median +10.52% pts, max +18.31% pts).
   - Tuy nhiên, số lượng build thua áp đảo (122 vs 38), kéo median tổng thể về mức âm (−1.26% ở Karaf, −1.41% ở ActiveMQ, −0.12% ở Log4j).

---

## 2. Vai trò Semantic theo Nhóm Lịch sử (Phát hiện 1B)

Phân bổ số lượt test lỗi theo nhóm lịch sử quan sát giữa các build thắng và thua:

| Nhóm Lịch sử | Quan sát lỗi trong Wins | Quan sát lỗi trong Losses | Tỷ lệ trong Wins | Nhận xét |
|---|---:|---:|---:|---|
| **$N = 0$ (Cold-start)** | 5 | 3 | 62.5% | Mẫu rất nhỏ (chỉ 8 quan sát trên 161 builds), nhưng tỷ lệ thắng chiếm ưu thế |
| **$N = 1..4$ (Lịch sử mỏng)** | 3 | 36 | 7.7% | Thua áp đảo (36/39 quan sát bị chậm) |
| **$N \ge 5$ (Lịch sử dày)** | 54 | 236 | 18.6% | Chiếm đa số mẫu; 236 quan sát bị chậm, 54 quan sát được cải thiện |

### Quan sát:
- Trong nhóm thắng, phần lớn các test lỗi được hưởng lợi **vẫn là nhóm $N \ge 5$** (35 ở Karaf, 12 ở ActiveMQ, 7 ở Log4j).
- Điều này bác bỏ định kiến rằng semantic chỉ hữu ích cho $N=0$. Khi semantic hoạt động tốt, nó có khả năng đưa cả các test $N \ge 5$ từ các vị trí sâu lên đầu danh sách trước các test $N \ge 5$ khác ít liên quan hơn.

---

## 3. Cơ chế Tạo Giá trị vs Cơ chế Gây Hại (Phát hiện 1C & 1D)

### 3.1. Dịch chuyển vị trí của Test Lỗi (Failure Shifts)
- **Trong các build Thắng (38 builds)**:
  - **46 test lỗi được đẩy lên sớm hơn** (promoted) so với History+cost.
  - 14 test lỗi bị đẩy lùi (demoted).
  - 2 test lỗi giữ nguyên vị trí.
- **Trong các build Thua (122 builds)**:
  - **179 test lỗi bị đẩy lùi về sau** (demoted) so với History+cost.
  - 81 test lỗi được đẩy lên trước nhưng vẫn không cứu được build vì bị test nặng chắn đường.
  - 15 test lỗi giữ nguyên vị trí.

### 3.2. Hiệu ứng "Heavy Predecessors" — Thủ phạm triệt tiêu APFDc
Tổng hợp thời gian test chạy chen vào trước test lỗi (`added_predecessor_seconds`) đối chiếu với thời gian test được giảm bớt (`removed_predecessor_seconds`):

| Dự án | Added Predecessor Secs | Removed Predecessor Secs | Net Added Secs |
|---|---:|---:|---:|
| **Karaf** | 18.205,5 s | 23.384,8 s | **−5.179,3 s** (Net giảm thời gian) |
| **ActiveMQ** | 115.759,2 s | 71.872,9 s | **+43.886,3 s** (Net tăng thời gian khổng lồ) |
| **Log4j** | 1.027,2 s | 635,0 s | **+392,2 s** (Net tăng thời gian) |
| **Tổng cộng** | **134.991,9 s** | **95.892,7 s** | **+39.099,3 s** (~10,8 giờ trễ tích lũy) |

### 3.3. Nguyên nhân gốc rễ toán học: Sự mất cân bằng thứ nguyên (Dimensional Mismatch)
Trong hàm mục tiêu Stage 6:
$$F_N(S) = \alpha \frac{FL(S)}{n} + (1 - \alpha) \sum_{t \in S} w_b(t)$$
- Điểm $w_b(t) = q_b(t) / Q$ đã được chuẩn hóa theo chi phí: $q_b(t) \propto 1 / \sqrt{c_b(t)}$.
- **Nhưng thành phần Semantic marginal gain $\Delta FL(t \mid S) / n$ HOÀN TOÀN KHÔNG CÓ THỜI GIAN/CHI PHÍ!**
- Một test chạy **150 giây** (ví dụ `MemoryUsageConcurrencyTest` trong ActiveMQ) có semantic coverage tương đương một test chạy **0,001 giây**.
- Vì $\alpha = 0.5$, ở những bước greedy đầu tiên, semantic gain chiếm tới **97.5% - 99.9%** tổng marginal gain.
- Thuật toán greedy sẵn sàng chọn test 150s lên đầu suite chỉ vì nó có độ bao phủ đa dạng cao hơn 0.01 so với test khác, **làm trì hoãn toàn bộ 150 giây cho tất cả các test lỗi phía sau**, phá hủy trực tiếp APFDc (vốn đo bằng timestamp hoàn thành).

---

## 4. Kết luận Deliverable Phase 1

1. **Semantic trên LRTS CÓ tạo ra giá trị thực sự**: 38 build thắng với biên độ rất cao (median +3.55% đến +10.52%) chứng minh semantic không phải dead weight.
2. **Nguồn gây thua là cơ chế Greedy thiếu ý thức về chi phí (Cost-agnostic Semantic)**: Semantic đẩy các test nặng không lỗi lên đầu suite chỉ để tối ưu đa dạng ngữ nghĩa.
3. **Bài học từ Stage 8 (Restricted v1)**: Stage 8 áp trần cứng lên điểm lịch sử ($q \ge 0.95 q_{head}$), đã ngăn được các ca thua nặng nhưng cũng bóp chết luôn 38 ca thắng lớn vì triệt tiêu không gian hoán đổi của semantic.
4. **Hướng đi khả thi cho Phase 2**: Điều chỉnh trực tiếp hàm marginal gain của Greedy sao cho **mọi thành phần (kể cả semantic) đều phải chịu tỷ lệ chi phí thời gian (cost-aware)**, thay vì lọc thô bạo trên pool lịch sử.
