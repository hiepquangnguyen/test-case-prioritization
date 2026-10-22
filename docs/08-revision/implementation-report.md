# Kết quả restricted semantic/cost v1

**Quyết định: no_go. Gate hiệu quả đạt 0/3 dự án.**

Đã triển khai và replay toàn development với q_fraction=0,95, duration_multiplier=1,25. Giữ encoder/history/source và dữ liệu giai đoạn 6; không quét tham số. Reserved vẫn đóng.

## Hiệu quả theo physical build

Median paired ΔAPFDc tính bằng điểm %, số âm là kém hơn đối chứng. Gate cần ≥3 điểm % so với cả History+cost và FL-only ở ít nhất hai dự án. Các cặp no-failure giữ NA.

| Dự án | Stage / physical | Cặp có APFDc | Δ History+cost | Δ HC-N v1 | Δ FL-only | Gate |
|---|---:|---:|---:|---:|---:|---|
| karaf | 315 / 315 | 79 | -0.017 | 1.286 | 31.450 | False |
| activemq | 126 / 126 | 57 | -0.154 | 1.134 | 42.071 | False |
| log4j | 155 / 78 | 25 | -0.001 | 0.112 | 28.787 | False |

## Thời gian phát hiện lỗi và Recall10

TTFF execution-only; median delta âm tốt hơn. Recall10 delta dương tốt hơn.

| Dự án | Đối chứng | Median ΔTTFF (s) | Median ΔRecall10 | APFDc thắng / hòa / thua |
|---|---|---:|---:|---:|
| karaf | history_cost | 0.063 | 0.000 | 13 / 17 / 49 |
| karaf | hc_falcon_normalized_v1 | -8.822 | 0.000 | 55 / 1 / 23 |
| karaf | fl_only | -459.708 | 0.500 | 63 / 0 / 16 |
| activemq | history_cost | 6.763 | 0.000 | 13 / 1 / 43 |
| activemq | hc_falcon_normalized_v1 | -186.518 | 0.000 | 46 / 2 / 9 |
| activemq | fl_only | -3310.407 | 0.452 | 52 / 2 / 3 |
| log4j | history_cost | 0.000 | 0.000 | 5 / 6 / 14 |
| log4j | hc_falcon_normalized_v1 | -0.636 | 0.000 | 22 / 0 / 3 |
| log4j | fl_only | -159.973 | 1.000 | 22 / 0 / 3 |

## Nhóm lịch sử và fallback trong greedy

| Dự án | Nhóm | Quan sát test | Quan sát lỗi | Recall10 pooled |
|---|---|---:|---:|---:|
| karaf | N0 | 244 | 2 | 0.000 |
| karaf | N1_4 | 912 | 4 | 0.500 |
| karaf | N5plus | 67572 | 114 | 0.482 |
| activemq | N0 | 1779 | 5 | 0.000 |
| activemq | N1_4 | 4593 | 32 | 0.406 |
| activemq | N5plus | 103466 | 117 | 0.632 |
| log4j | N0 | 79 | 1 | 0.000 |
| log4j | N1_4 | 282 | 3 | 1.000 |
| log4j | N5plus | 98325 | 60 | 0.750 |

Đây là quan sát test-stage có lặp, không phải mẫu độc lập. Nhóm N=0 vẫn rất ít lỗi.

Giới hạn quan trọng của quy tắc mới: q=0 không thể vào nhóm ứng viên khi còn q(b)>0. Vì vậy test chưa có lịch sử bị đẩy sau các test có q dương; semantic chỉ sắp lại nhóm này khi nhóm q dương đã hết. Trong lượt này cả 8 quan sát lỗi N=0 đều nằm ngoài ngân sách 10%. Không thể coi đây là phương án đã giải quyết cold start.

- karaf: 13 stage có ít nhất một bước q(b)=0; 318 bước semantic gain toàn nhóm bằng 0 và dùng baseline head.
- activemq: 15 stage có ít nhất một bước q(b)=0; 1653 bước semantic gain toàn nhóm bằng 0 và dùng baseline head.
- log4j: 45 stage có ít nhất một bước q(b)=0; 1758 bước semantic gain toàn nhóm bằng 0 và dùng baseline head.

## Runtime cached replay

| Dự án | p95 prep+rank / execution | Maximum physical ratio | Peak RSS (GiB) |
|---|---:|---:|---:|
| karaf | 0.023% | 0.234% | 0.547 |
| activemq | 0.018% | 0.085% | 0.620 |
| log4j | 0.037% | 0.964% | 0.672 |

Các số này không gồm trích source và encoding, có cache vector trong bộ nhớ; không dùng để tuyên bố đã đạt engineering full pipeline hoặc cải thiện latency CI so với lượt đo giai đoạn 6. Không ghép chi phí đo ở các lượt khác nhau thành benchmark mới.

## Các physical build thua nhiều nhất

| Dự án | PR / build | ΔAPFDc so với History+cost (điểm %) |
|---|---|---:|
| karaf | PR-1536 / 1 | -3.285 |
| karaf | PR-1501 / 2 | -1.624 |
| karaf | PR-1502 / 3 | -1.381 |
| activemq | PR-1005 / 4 | -1.989 |
| activemq | PR-967 / 1 | -1.981 |
| activemq | PR-1051 / 1 | -1.545 |
| log4j | PR-576 / 1 | -0.635 |
| log4j | PR-608 / 3 | -0.571 |
| log4j | PR-544 / 2 | -0.280 |

## Kiểm chứng và giới hạn

Đã lưu 596 checkpoint mới, mỗi checkpoint có ranking thuật toán và policy riêng. Full permutation và APFD/APFDc được đối chiếu độc lập cho cả hai. Baseline raw q khớp chính xác giai đoạn 6 ở mọi stage. Sáu phép mutation đầu/cuối dự án giữ nguyên snapshot và ranking khi thay outcomes/duration không đủ điều kiện. Bốn unit tests đạt.

Phiên bản mới được chọn sau khi xem development nên kết quả chỉ là thăm dò. Giới hạn q/cost từng bước không bảo đảm toàn bộ thứ tự tốt hơn History+cost. Không kế thừa chứng minh xấp xỉ của objective cũ và không triển khai lazy.

Kết quả phiên bản này cho thấy giới hạn q/cost giảm mức thiệt hại so với HC-N v1, nhưng chưa tạo lợi ích vượt History+cost theo gate. Đây là kết quả âm cần giữ trong báo cáo, không phải bằng chứng xác nhận giả thuyết semantic kết hợp luôn tốt hơn.

Nếu no-go, dừng vòng cấu hình này và review đóng góp nghiên cứu hoặc phạm vi câu hỏi; không tự động quét thêm tham số hay mở reserved. Nếu đạt hiệu quả, cần đo engineering đầy đủ trước khi review confirmation.

- [Đặc tả và tái lập](specification-and-reproduction.md)
- [Summary](../../reports/stage8/summary.json)
- [Manifest](../../reports/stage8/manifest.json)
- [Báo cáo policy cache-only riêng](cache-policy-report.md)
