# Kết quả đánh giá đã đăng ký trước (hướng B): Jackrabbit Oak và HBase

*Ngày 2026-11-26. Quy trình theo [preregistration-B.md](preregistration-B.md) (commit `650d589`, push trước khi
tải dữ liệu). Số liệu: `results/pilot/<project>/`, `results/prereg/`.*

## 1. Kết quả xác nhận (phần eval, DeConf, APFDc-FFMapU)

| Phương pháp | Oak (448 TSR) | HBase (64 TSR) | ActiveMQ (phát triển, 78 TSR) |
|---|---|---|---|
| LatestFail+CC | **0.912** | **0.803** | 0.846 |
| LatestFail+CCH | 0.886 | 0.789 | **0.865** |
| HC-FALCON (cấu hình khóa) | 0.898 | 0.781 | 0.854 |
| HC-FALCON-prop | 0.894 (η = 0.1) | 0.781 (η = 0) | 0.854 (η = 0) |
| History+Cost (α = 0) | 0.891 | 0.730 | 0.862 |
| History | 0.857 | 0.675 | 0.833 |
| FALCON | 0.374 | 0.587 | 0.494 |
| Random | 0.500 | 0.510 | 0.488 |

**Cấu hình khóa trên warm-up:**

| Dự án | Biến thể | α | Bộ ước lượng | κ | η |
|---|---|---|---|---|---|
| Oak | ratio + γ = 1 | 0.1 | decay λ = 0.95 | 1 | 0.1 |
| HBase | ratio (γ = 0.5) | 0.9 | Beta | 1 | 0 |

**Giả thuyết** (thắng = p_Holm < 0.05, δ ≥ 0.147 và trung vị cao hơn ≥ 3%):

| | Oak | HBase | Chi tiết |
|---|---|---|---|
| H1: prop thắng History+Cost | ✗ | ✗ | Oak: prop kém History+Cost. HBase: warm-up chọn η = 0 |
| H2: HC-FALCON thắng History+Cost | ✗ | ✗ | Oak: trung vị −0.1%. HBase: trung bình +5.2 điểm nhưng trung vị −0.2%, p_Holm = 1 |
| H3: thắng FALCON **và** History | ✗ | ✗ | Thắng FALCON rõ. So với History: Oak p_Holm = 0.009 nhưng trung vị chỉ +1.6% và δ = 0.06; HBase trung vị +10.7%, δ = 0.15 nhưng p_Holm = 0.16 |
| H4: thắng LatestFail+CCH | ✗ | ✗ | Oak: trung bình +1.3 điểm nhưng thua ở 285/448 TSR |

**Quyết định theo quy tắc đã đăng ký: NO-GO**, tức là viết báo cáo kỹ thuật với kết quả âm tính.

- **Leakage:**
  - Kiểm tra bất biến (xóa hoặc xáo trộn tương lai không đổi thứ tự) đạt trên cả hai dự án, cho cả HC-FALCON lẫn
    HC-FALCON-prop.
  - Kiểm tra ngược (cố ý cho rò rỉ):
    - HBase: APFDc tăng từ 0.762 lên 0.947.
    - Oak: APFDc chỉ tăng từ 0.887 lên 0.931 (+0.044), dưới ngưỡng +0.05 đặt sẵn trong `check_leakage.py`, nên
      file `leakage.json` ghi `passed: false`.
    - Ngưỡng này không nằm trong bản đăng ký và không bị sửa sau khi xem kết quả. Mức tăng nhỏ là do Oak đã gần
      trần: phần cải thiện vẫn lấp được khoảng 39% khoảng cách còn lại tới 1.0.
- Chi phí: mỗi lần xếp hạng mất 0.13 s (HBase) đến 0.27 s (Oak), tức khoảng 0.002% thời lượng TSR. Embed toàn bộ
  lịch sử trên GPU T4 mất 52–63 s.

## 2. Phân tích thăm dò (không có trong đăng ký, không phải kết luận xác nhận)

Phần ngữ nghĩa hoạt động như một **lưới an toàn hiếm khi kích hoạt**.

- Ở phần lớn TSR, HC-FALCON kém History+Cost một chút: thua 38/64 TSR ở HBase và 381/448 TSR ở Oak, trung vị
  chênh khoảng −0.001.
- Nhưng ở một số ít TSR, nó cứu được rất nhiều. Ở HBase, 5 TSR đã đóng góp tổng cộng +3.7 điểm APFDc.
- Những TSR được cứu chủ yếu là lỗi **lần đầu**, tức test chưa từng fail. Tính trên các TSR mà mọi lỗi đều là lỗi
  lần đầu:

  | Dự án | Tỉ lệ TSR toàn lỗi lần đầu | HC-FALCON so với History+Cost trên nhóm đó | Trên các TSR còn lại |
  |---|---|---|---|
  | HBase | 50% | +0.112 | −0.008 |
  | Oak | 5% | +0.094 | +0.003 |
  | ActiveMQ | 15% | +0.013 | −0.011 |

  Cả 8 TSR được cứu mạnh (+0.2 trở lên) ở HBase đều thuộc nhóm toàn lỗi lần đầu.

**Diễn giải.** Ngữ nghĩa giúp đúng ở chỗ lịch sử không có thông tin, và làm hại nhẹ ở chỗ lịch sử đã đủ mạnh. Vì
vậy hiệu quả trung bình phụ thuộc vào tỉ lệ lỗi lần đầu của từng dự án: HBase cao, Oak thấp. Điều này giải thích
vì sao đường APFDc theo α khác nhau giữa các dự án:
- HBase: bằng phẳng quanh 0.78 với α từ 0.3 đến 0.9;
- Oak: cao nhất ở α = 0.1;
- ActiveMQ: cao nhất ở α = 0.

## 3. Đề xuất cho các tuần còn lại

- **Sản phẩm chính:** báo cáo kỹ thuật trung thực, gồm:
  - kết quả âm tính đã đăng ký trước;
  - phân tích "lưới an toàn cho lỗi lần đầu";
  - phần lý thuyết (submodular, bảo đảm (1−1/e));
  - pipeline chống leakage;
  - các phát hiện phụ: rò rỉ trong QTF-Avg của LRTS, độ nhạy phá hòa của FALCON.
- **Tùy chọn (cần giảng viên đồng ý):** biến phát hiện thăm dò thành một kiểm định xác nhận trên dữ liệu mới.
  - Đăng ký trước giả thuyết H5: "HC-FALCON thắng History+Cost trên các TSR toàn lỗi lần đầu".
  - Kiểm định trên Hadoop và Karaf, hai dự án chưa từng chạy HC-FALCON.
- RQ3 (test mới và flaky) giờ là trọng tâm tự nhiên của phần phân tích.
