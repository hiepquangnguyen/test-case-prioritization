# Đăng ký trước: hướng B (HC-FALCON-prop) và đánh giá trên Jackrabbit Oak, HBase

*Viết ngày 2026-11-26.* Tài liệu này được commit và push lên GitHub **trước khi** clone repo, xuất mã nguồn,
embed hay chạy bất kỳ phương pháp nào của đề tài trên Jackrabbit Oak và HBase. Mọi thay đổi sau thời điểm đó phải
ghi vào `decisions.md`, kèm lý do và đánh dấu là "lệch khỏi đăng ký trước".

**Những gì đã biết về Oak/HBase tại thời điểm viết** (công khai cho minh bạch):
- số TSR và nhãn lọc, dùng để kiểm tra nhãn ở tuần 3;
- APFDc mà chính LRTS công bố cho các baseline của họ (`results/reference/lrts_targets.csv`);
- kết quả baseline mình chạy lại trên hai dự án này khi so khớp (`results/parity/`).

Chưa có embedding nào, và chưa có kết quả nào của HC-FALCON hay biến thể của nó trên hai dự án này.

## 1. Câu hỏi

Có cách dùng embedding mã test nào làm tăng khả năng phát hiện lỗi sớm so với lịch sử + chi phí trên CI dài hạn
không? Đề tài thử hai cách, cả hai đều nằm trong cùng một hàm mục tiêu submodular:
- **đa dạng hóa:** thành phần facility location của HC-FALCON;
- **lan truyền lỗi:** thành phần `s(t)` của HC-FALCON-prop.

## 2. Phương pháp (cố định)

```
F_b(S) = α · FL_b(S)/|T_b| + (1−α) · Σ_{t∈S} q_b(t)
q_b(t) = (conf·p + η·s(t)) / (c̃^γ + ε),   chuẩn hóa chia cho max trong TSR
s(t)   = max_{u∈T_b, u≠t, F_u>0} max(0, (sim(t,u) − τ)/(1 − τ)) · λ^(last_failure_u − 1)
```

- τ là phân vị **0.99** của các similarity ngoài đường chéo trong TSR. λ = **0.1**.
  - Hai giá trị này được chọn trên ActiveMQ (dự án phát triển), là thiết lập cho tín hiệu láng giềng mạnh nhất
    trong ba ngưỡng đã thử (mục 5). Từ đây không đổi nữa.
- Similarity là max(0, cos) của vector test class (UniXcoder, masked mean-pool, trung bình các method), như
  tuần 4. Test không có mã nguồn được cô lập.
- Do q ≥ 0 và không phụ thuộc tập đã chọn, F_b là monotone submodular. Greedy đạt bảo đảm (1−1/e) cho mọi tiền
  tố, trừ khi chọn biến thể `selection = ratio` (khi đó là dạng knapsack, nêu rõ trong bài).
- Code: `src/hcfalcon/propagation.py`, `hc_falcon.py`. Cấu hình: `configs/default.yaml`.

## 3. Dữ liệu và quy trình

- **Dự án chính:** Jackrabbit Oak, HBase.
- **Dự án phụ:** Hadoop (lưu ý nhãn freqfail lệch 2 TSR) và Karaf, chạy nếu đủ thời gian. Kết quả phụ được báo
  cáo riêng.
- **ActiveMQ:** chỉ là dự án phát triển, không tính vào kết luận.
- **Dữ liệu:** chỉ mục TSR của artifact LRTS, bản DeConf là chính; All và FirstFail là phụ. Metric chính là
  APFDc-FFMapU.
- **Quy trình cho mỗi dự án**, chạy đúng một lần, không sửa sau khi xem kết quả eval:
  1. `export_blobs` rồi embed trên Colab (chế độ b). Báo cáo `emb_coverage`.
  2. `tune_warmup.py --dataset deconf`: chọn lần lượt α → bộ ước lượng p → κ → γ → β của RankBlend, chỉ trên
     20% TSR đầu.
  3. `pilot.py`, gồm hai bước trên warm-up rồi một lần chạy eval:
     - thử các biến thể định nghĩa trước (tuned, γ = 1, ratio, ratio + γ = 1, prior Beta), mỗi biến thể với cả
       lưới α. Khóa cấu hình tốt nhất làm **HC-FALCON**;
     - tìm η ∈ {0, 0.05, 0.1, 0.2, 0.5, 1} cùng α trên cấu hình đó. Khóa làm **HC-FALCON-prop**. Nếu η = 0 được
       chọn thì HC-FALCON-prop trùng HC-FALCON, và vẫn báo cáo như vậy;
     - chạy một lần trên phần eval với mọi phương pháp: HC-FALCON, HC-FALCON-prop, HC-FALCON(default),
       History+Cost(+Prop), History, FL+History, FALCON, FALCON-ratio, HC-FALCON-noconf, RankBlend, RRF, cùng
       10 baseline LRTS.
  4. Kiểm tra leakage (bất biến khi xóa hoặc xáo trộn tương lai, và kiểm tra ngược) trên vài TSR của mỗi dự án.
- Phá hòa tất định. Baseline ngẫu nhiên lấy trung bình 10 seed theo từng TSR.

## 4. Giả thuyết và tiêu chí quyết định

Mỗi so sánh dùng Wilcoxon signed-rank hai phía, ghép cặp theo TSR, trên phần eval DeConf. Hiệu chỉnh Holm áp dụng
trên cả họ so sánh của mỗi phương pháp trong mỗi dự án. Một phương pháp được tính là **thắng** một baseline trên
một dự án khi thỏa cả ba điều kiện:
- p_Holm < 0.05;
- Cliff's δ > 0 và không ở mức "negligible" (|δ| ≥ 0.147);
- trung vị APFDc cao hơn ít nhất **3%**.

Các giả thuyết:

| | Giả thuyết | Ý nghĩa |
|---|---|---|
| H1 | HC-FALCON-prop thắng History+Cost | Lan truyền lỗi có thêm giá trị |
| H2 | HC-FALCON thắng History+Cost | Đa dạng hóa có thêm giá trị (ablation chính) |
| H3 | HC-FALCON hoặc HC-FALCON-prop thắng FALCON **và** History | Tiêu chí go/no-go của `topic1.md` |
| H4 | HC-FALCON hoặc HC-FALCON-prop thắng LatestFail+CCH | Vượt baseline mạnh nhất của LRTS |

**Quyết định ở tuần 10:**
- **GO (viết paper):** H1 hoặc H2 đúng trên cả hai dự án chính, và H3 cũng đúng trên cả hai.
- **Ngược lại:** báo cáo kỹ thuật với kết quả âm tính. Câu hỏi được trả lời là "dùng ngữ nghĩa theo hai cách
  đều không thêm giá trị so với lịch sử + chi phí". Đi kèm các phân tích ở mục 5 và đường APFDc theo α, η trên
  phần eval (chỉ để chẩn đoán).

Không thêm dự án, không bỏ dự án, không đổi metric hay tiêu chí sau khi đã xem kết quả eval.

## 5. Bằng chứng từ dự án phát triển (ActiveMQ) để đặt kỳ vọng

- **HC-FALCON** (khóa: ratio, γ = 1, α = 0.4): 0.854 trên eval, so với History+Cost 0.862 và LatestFail+CCH
  0.865. APFDc giảm đều khi tăng α.
- **Tiền đề lan truyền yếu.** Xét các test chưa từng fail:
  - Có láng giềng (phân vị 0.99) vừa fail ở lần chạy trước: tỉ lệ fail 0.127% (33 lỗi).
  - Không có láng giềng như vậy: 0.086%.
  - Như vậy tín hiệu chỉ tăng khoảng 1.5 lần, trong khi lịch sử của chính test tăng 10–100 lần (0.92% nếu fail
    trước đó, 9.3% nếu vừa fail ở lần trước).
  - Với λ = 0.8 và phân vị 0.95 (thiết kế ban đầu): không tăng (0.092% so với 0.097%). Với các test gần như
    trùng lặp (phân vị 0.999): chỉ 1 lỗi trong 3.338 lượt chạy.
- **Kết quả trên ActiveMQ với thiết lập đã chốt:** warm-up chọn η = 0. Trên eval, APFDc giảm đều khi tăng η, từ
  0.854 xuống 0.840.
- **Kỳ vọng thành thật:** H1 và H2 nhiều khả năng không đúng. Đăng ký này tồn tại để kết luận, dù dương hay âm,
  đều đáng tin.
