# Giai đoạn 6 — pilot development toàn inventory

Pilot đã chạy trên development của Karaf, ActiveMQ và Log4j bằng implementation giai đoạn 5. Warm-up chỉ cung cấp history/cache. Tập reserved confirmation chưa mở.

**Quyết định theo ngưỡng đã chốt: no_go_revise_on_development.** Gate hiệu quả đạt ở 0/3 dự án; engineering gate toàn bộ dự án: True.

Các kết quả là mô tả trên development; Karaf exploratory. Không dùng các số này như kiểm định xác nhận và không đổi alpha chính sau khi xem kết quả.

## Hiệu quả chính

Bảng dưới là median của paired delta APFDc (HC-FALCON-N − đối chứng), không phải hiệu của hai median. Seed mean trước, rồi gộp các stage chung trong physical build. Ngưỡng tiếp tục: delta ≥0,03 so với cả FL-only và History+cost ở ít nhất hai dự án.

| Dự án | Stage / physical được score | Δ so với FL | Số cặp FL | Δ so với History+cost | Số cặp HC | Gate |
|---|---:|---:|---:|---:|---:|---|
| karaf | 315 / 315 | 0.2972 | 79 | -0.0127 | 79 | Không đạt |
| activemq | 126 / 126 | 0.3914 | 57 | -0.0141 | 57 | Không đạt |
| log4j | 155 / 78 | 0.2869 | 25 | -0.0012 | 25 | Không đạt |

## TTFF và Recall10

Delta TTFF âm là tốt hơn; delta Recall10 dương là tốt hơn. TTFF ở đây là execution-only trên các cặp có failure/metric xác định; số censored stage lưu riêng trong summary.

| Dự án | Đối chứng | Median Δ TTFF (s) | Số cặp | Median Δ Recall10 | Số cặp |
|---|---|---:|---:|---:|---:|
| karaf | fl_only | -459.1370 | 79 | 0.3333 | 79 |
| karaf | history_cost | 6.8060 | 79 | 0.0000 | 79 |
| activemq | fl_only | -2742.6080 | 57 | 0.1250 | 57 |
| activemq | history_cost | 200.4240 | 57 | 0.0000 | 57 |
| log4j | fl_only | -145.6900 | 25 | 1.0000 | 25 |
| log4j | history_cost | 0.9350 | 25 | 0.0000 | 25 |

## Chi phí và source

| Dự án | Peak RSS process (GiB) | p95 warm overhead / suite | Gate engineering | Valid semantic / records | Valid failing source / failures | Truncated records |
|---|---:|---:|---|---:|---:|---:|
| karaf | 1.289 | 0.27% | Đạt | 68410 / 68728 | 118 / 120 | 630 |
| activemq | 1.631 | 0.18% | Đạt | 108195 / 109838 | 153 / 154 | 1535 |
| log4j | 1.555 | 1.11% | Đạt | 96928 / 98686 | 64 / 64 | 927 |

Warm overhead gồm source/preprocessing, embedding (kể cả cache miss khi source đổi), kernel, history và ranking cho phương pháp chính. Chi phí chuẩn bị được tính cho từng method độc lập. Cold overhead trong JSON là ước lượng dựng lại từ từng source cache miss, không phải cold end-to-end trực tiếp từng build. Chi phí fetch/model download và CI setup/queue không nằm trong phép đo offline này. Peak RSS là cả process replay.

## Kiểm chứng và giới hạn

Đã kiểm tra 33972 ranking: full permutation và APFD/APFDc bằng công thức độc lập. No-failure giữ NA. Không nhân số mẫu bởi seed/stage. Các checkpoint giữ đủ các baseline, ablation, raw/normalized, Borda và alpha sensitivity.

Source là revision metadata khai báo, chưa chứng minh revision thực sự được CI chạy. Inventory lấy từ observed logs; missing/ambiguous giữ lại. Semantic truncation dùng cap đã chốt trước pilot. RQ3 lưu nhóm N=0, 1..4, ≥5 và vị trí/thời điểm phát hiện; không gọi đó là ground-truth flaky. Defects4J là nhánh riêng, chưa được chạy trong pilot này.

Nếu no-go, bước tiếp theo là phân tích nguyên nhân và đề xuất phiên bản sửa trên development để review. Không mở reserved để tìm kết quả thuận lợi. Nếu đạt gate, vẫn cần review đầy đủ tradeoff và khóa phương án trước khi mở confirmation.

## Bằng chứng

- [Summary máy đọc](../../reports/stage6/summary.json)
- [Runner/analysis freeze](../../reports/stage6/run-freeze.json)
- [Tái lập và định nghĩa runtime](reproduction.md)
- Các checkpoint và `ledger.json`, `complete.json`, `history-groups.json` nằm tại `reports/stage6/<project>/`.

## Kiểm tra số học và tái dựng replay

- karaf: 630 objective endpoint checks; 1 ngoại lệ strict alpha=0 do float64 normalization; tái dựng first/last development full inventory và mutation các build không đủ điều kiện sử dụng đã đạt.
- activemq: 252 objective endpoint checks; 0 ngoại lệ strict alpha=0 do float64 normalization; tái dựng first/last development full inventory và mutation các build không đủ điều kiện sử dụng đã đạt.
- log4j: 310 objective endpoint checks; 7 ngoại lệ strict alpha=0 do float64 normalization; tái dựng first/last development full inventory và mutation các build không đủ điều kiện sử dụng đã đạt.

Ngoại lệ alpha=0 không được che bằng tolerance để đổi ranking: giữ tie FQN của objective float đã khóa, ghi q/w và metric hai thứ tự trong `replay-verification.json`. Không coi tương đương toán học alpha=0 và History+cost là bảo đảm thứ tự tuyệt đối ở float64. Cần review/chốt quy tắc này trước một phiên bản confirmation tiếp theo.

ActiveMQ có lần warm-up bị ngắt trước khi lưu cold-cost ledger. Chi phí cold còn thiếu được đo lại riêng, có kiểm tra vector, và ghi `cold-recovery.json`; ranking gốc không đổi. Độ phân tán seed/stage, nhóm lịch sử và TTFF có cộng preparation xem [supplement](../../reports/stage6/supplement.json).

## Toàn bộ đối chứng và ablation

Mean APFDc trên physical build có metric xác định; bảng này là mô tả, không thay thế median paired delta dùng cho gate.

| Phương pháp | Karaf | ActiveMQ | Log4j |
|---|---:|---:|---:|
| random | 0.4936 | 0.4945 | 0.4835 |
| shortest_test_first | 0.6683 | 0.6394 | 0.8586 |
| most_fail | 0.6951 | 0.8219 | 0.8667 |
| recent_fail | 0.7361 | 0.8369 | 0.8509 |
| history_only | 0.7122 | 0.8361 | 0.8469 |
| history_cost | 0.7754 | 0.8486 | 0.8936 |
| fl_only | 0.4522 | 0.4843 | 0.6990 |
| hc_falcon_normalized_v1 | 0.7710 | 0.8147 | 0.9014 |
| hc_falcon_topic_raw_v1 | 0.7746 | 0.8486 | 0.8940 |
| fl_history | 0.6662 | 0.8154 | 0.8479 |
| no_confidence | 0.7707 | 0.8152 | 0.9339 |
| borda_history | 0.5323 | 0.7169 | 0.8215 |
| borda_history_cost | 0.6860 | 0.7379 | 0.9064 |
| fast_pw_lrts | 0.4606 | 0.4570 | 0.5194 |
| dante_cch_adapt_r1 | 0.7480 | 0.7048 | 0.9351 |

## Alpha sensitivity

Giữ alpha=0,5 là cấu hình chính. Mean APFDc dưới đây không được dùng để đổi cấu hình rồi gọi cùng development là confirmation.

| Alpha | Karaf | ActiveMQ | Log4j |
|---|---:|---:|---:|
| 0.0 | 0.7754 | 0.8486 | 0.8936 |
| 0.25 | 0.7794 | 0.8420 | 0.8993 |
| 0.5 | 0.7710 | 0.8147 | 0.9014 |
| 0.75 | 0.7077 | 0.7672 | 0.9036 |
| 1.0 | 0.4522 | 0.4843 | 0.6990 |

## Trường hợp overhead cao

P95 không phải giới hạn cho mọi build. Bảng dưới bổ sung maximum của mean stage ratio trong physical build và stage có overhead lớn nhất; đây là chẩn đoán, không thay gate đã chốt.

| Dự án | Maximum physical overhead | Stage cao nhất | Prep + ranking (s) | Source cache misses |
|---|---:|---|---:|---:|
| karaf | 1.09% | PR-1490 / 1 / single | 9.80 | 9 |
| activemq | 5.63% | PR-1043 / 1 / single | 1152.53 | 572 |
| log4j | 212.54% | PR-511 / 3 / Windows_Test | 51.62 | 25 |

Runtime có ảnh hưởng của resume và trạng thái cache. Các số đo này mô tả lượt replay đã thực hiện; chưa phải bảo đảm latency cho CI thực tế. Peak RSS lấy maximum qua completion và mọi checkpoint development để giữ số đo của worker trước khi resume ([biên bản analyzer v3](../../reports/stage6/analysis-amendment-v3.json)).

## Kết luận để quyết định bước tiếp theo

Cấu hình alpha=0,5 cải thiện median paired APFDc so với FL-only trên cả ba dự án, nhưng median paired delta so với History+cost đều âm. Do đó chưa có cơ sở chuyển cấu hình hiện tại sang confirmation. Riêng Log4j, mean APFDc cao hơn History+cost nhưng median paired delta vẫn âm; hai phép tổng hợp này không mâu thuẫn và không được thay thế nhau khi xét gate.

Bước tiếp theo: phân tích các build thua History+cost và nhóm lịch sử N=0/1..4/≥5, đối chiếu đóng góp semantic với history/cost và chi phí cache miss, rồi đề xuất phiên bản sửa cùng quy tắc số học để review trước lượt đánh giá mới. Các giả thuyết rút ra từ development cần được ghi rõ; chưa đổi alpha hay mở reserved.

Tổng cộng tám ngoại lệ alpha=0 (Karaf: 1; Log4j: 7) có thứ tự khác History+cost do chuẩn hóa float64 tạo hòa điểm. Đối chiếu các metric đã lưu cho cả tám trường hợp không thấy khác biệt; điều này không bảo đảm mọi dữ liệu tương lai đều không bị ảnh hưởng.
