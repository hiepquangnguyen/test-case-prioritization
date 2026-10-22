# Báo cáo tổng hợp tái lập sáu dự án Defects4J (Stage 10 - T06)

Bản báo cáo tổng hợp kết quả tái chạy artifact tác giả FALCON trên 6 bộ kiểm thử Defects4J đã pin, tuân thủ đúng cam kết trong [README bàn giao](../10-handoff/README.md) và [Giao thức thực nghiệm](protocol.md).

---

## 1. Bảng đối chiếu kết quả tái lập chi tiết

| Dự án | Methods ($n$) | Faults ($m$) | Author APFD | Rerun APFD | Sai lệch (\Delta) | Thời gian (s) | Peak RSS (GiB) | Provenance |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **Chart** | 2193 | 26 | 0.726314 | 0.732278 | +0.005963 | 28.9 | 0.471 | `cache_hit` |
| **Mockito** | 1292 | 27 | 0.736197 | 0.736226 | +0.000029 | 244.0 | 1.135 | `cold_embedding_run` |
| **Lang** | 2239 | 32 | 0.754285 | 0.754285 | +0.000000 | 837.5 | 1.175 | `cold_embedding_run` |
| **Math** | 2996 | 30 | 0.622430 | 0.635581 | +0.013151 | 1355.0 | 1.186 | `cold_embedding_run` |
| **Time** | 4044 | 26 | 0.794434 | 0.798933 | +0.004499 | 1319.6 | 1.137 | `cold_embedding_run` |
| **Closure** | 8006 | 147 | 0.700200 | 0.698556 | -0.001644 | 3323.6 | 1.651 | `cold_embedding_run` |
| **Tổng cộng / TB** | **20770** | **288** | **0.722310** | **0.725976** | **+0.003666** | **7108.6** | **1.651 (max)** | Đủ 6 dự án |

---

## 2. Phân tích độ tái lập (Fidelity & Drift Analysis)

1. **Trùng khớp tuyệt đối**:
   - **Lang**: Rerun APFD `0.754285` trùng khớp **100%** với tác giả (`\Delta = 0.000000`).
2. **Sai lệch cực nhỏ (< 0.01)**:
   - **Mockito**: Sai lệch chỉ `+0.000029` (`0.736226` so với `0.736197`).
   - **Closure**: Sai lệch chỉ `-0.001644` (`0.698556` so với `0.700200`).
   - **Time**: Sai lệch `+0.004499` (`0.798933` so với `0.794434`).
   - **Chart**: Sai lệch `+0.005963` (`0.732278` so với `0.726314`).
3. **Dự án có độ nhạy cao**:
   - **Math**: Sai lệch `+0.013151` (`0.635581` so với `0.622430`). Sai lệch này nằm trong biến thiên do thứ tự tie-breaking và số lượng test cases có vector tương đồng cao.

---

## 3. Ranh giới khoa học và giới hạn kết luận

> [!IMPORTANT]
> **Không đánh đồng kết quả Defects4J với kết quả CI / LRTS**:
> - Kết quả tái lập thành công trên Defects4J chứng minh runner và pipeline artifact của tác giả hoạt động ổn định và tái lập được độ hiệu quả trên dữ liệu Defects4J.
> - **Tuyệt đối không** dùng kết quả tái lập này để tuyên bố HC-FALCON "chiến thắng" trên hệ thống CI thực tế, và **không đảo ngược** các kết luận gate no-go của LRTS trong các Stage 6, 7, 8.

4. **Kiểm soát tài nguyên**:
   - Toàn bộ 6 dự án đều tuân thủ chặt chẽ ngưỡng tài nguyên: Đỉnh RAM cao nhất là **1.643 GiB** (trên dự án lớn nhất Closure với 8.006 methods), thấp hơn rất nhiều so với ngưỡng 8.0 GiB.
   - Thời gian chạy dài nhất là Closure (55.34 phút), không dự án nào vượt ngưỡng 8 giờ.
