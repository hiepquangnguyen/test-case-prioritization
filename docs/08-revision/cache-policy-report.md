# Cache-only restricted v1 — mô phỏng riêng

Dùng baseline History+cost cho cả stage khi thiếu source hash trong cache trước stage. Warmup usable nạp cache; sau mỗi stage usable, các source hash được coi là sẵn sàng cho stage kế tiếp. Đây là giả định offline, chưa có worker async hoặc lịch hoàn thành encoding CI.

| Dự án | Stage fallback / tổng | Physical có fallback | Median ΔAPFDc History+cost (điểm %) | Median ΔTTFF (s) |
|---|---:|---:|---:|---:|
| karaf | 28 / 315 | 28 | -0.005 | 0.006 |
| activemq | 15 / 126 | 15 | -0.078 | 0.482 |
| log4j | 48 / 155 | 48 | 0.000 | 0.000 |

Metric tính trên cả cohort gồm fallback, theo physical build; không chỉ tính cache hit. TTFF là execution-only từ thứ tự mô phỏng. Không có số đo latency async hoặc engineering gate của policy. Chưa triển khai dịch vụ chuẩn bị vector nền. Không thay policy bằng kết quả thuật toán đầy đủ khi kết luận.

- [Policy manifest](../../reports/stage8/cache-policy-manifest.json)
- [Policy summary](../../reports/stage8/cache-policy-summary.json)
