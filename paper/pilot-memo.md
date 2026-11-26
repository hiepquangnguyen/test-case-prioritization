# Pilot memo — HC-FALCON trên ActiveMQ (go/no-go #1)

*Ngày 2026-11-26. Số liệu: `results/pilot/activemq/`, chạy lại bằng `python scripts/pilot.py --project activemq`.*

## 1. Thiết lập

- Dữ liệu: LRTS ActiveMQ, 207 TSR, mức test class. Bản dữ liệu chính là DeConf (đã bỏ lỗi flaky và test fail
  liên tục).
- Đánh giá theo đúng trình tự thời gian. Lịch sử chỉ được cập nhật sau khi đã xếp hạng xong.
- Kiểm tra leakage đạt: thứ tự không đổi khi xóa hoặc xáo trộn các build tương lai. Khi cố ý cho rò rỉ, APFDc
  tăng từ 0.83 lên 0.97, chứng tỏ phép kiểm tra đủ nhạy.
- Chia dữ liệu:
  - 20% TSR đầu là warm-up (18 TSR có lỗi), chỉ dùng để chọn tham số;
  - 78 TSR có lỗi còn lại là phần eval, dùng để báo cáo.
- Cấu hình được khóa trên warm-up, sau khi thử các biến thể đã định nghĩa trước: α (11 giá trị), bộ ước lượng p,
  κ, γ, chọn theo tỉ lệ ΔF/c^γ. Kết quả: α = 0.4, ước lượng Beta, γ = 1, chọn theo tỉ lệ.
- Ngoài ra báo cáo thêm cấu hình mặc định đã chốt từ trước khi xem dữ liệu: α = 0.5, decay λ = 0.9.

## 2. Kết quả chính (phần eval, DeConf, APFDc-FFMapU, 78 TSR)

| Phương pháp | APFDc | So với HC-FALCON (Wilcoxon + Holm, Cliff's δ) |
|---|---|---|
| LatestFail+CCH (baseline mạnh nhất của LRTS) | **0.865** | không khác biệt có ý nghĩa (trung vị +0.1%, p = 0.80) |
| History+Cost (HC-FALCON với α = 0) | 0.862 | HC-FALCON **kém hơn** có ý nghĩa (p = 0.04, δ không đáng kể) |
| MostFail+CC | 0.857 | không khác biệt có ý nghĩa |
| **HC-FALCON (cấu hình khóa)** | **0.854** | — |
| HC-FALCON (cấu hình mặc định) | 0.848 | — |
| LatestFail+CC | 0.846 | không khác biệt có ý nghĩa |
| History (chỉ lịch sử, không có chi phí) | 0.833 | HC-FALCON tốt hơn 3.6% trung vị, nhưng không có ý nghĩa (p = 0.36) |
| QTF | 0.750 | HC-FALCON thắng (p < 0.001, δ trung bình) |
| FALCON (chỉ ngữ nghĩa) | 0.494 | HC-FALCON thắng (p < 0.001, δ lớn) |
| Random | 0.488 | |

- **Phân tích độ nhạy theo α trên phần eval** (không dùng để chọn tham số): APFDc giảm đều từ 0.862 khi α = 0
  xuống 0.854 khi α = 0.4, rồi 0.725 khi α = 1.
  - Trên warm-up, α = 0.4 tốt nhất (0.791 so với 0.760 khi α = 0), nhưng kết luận này không lặp lại trên eval.
- **Lỗi lần đầu (FirstFail, 28 TSR):**
  - HC-FALCON đạt 0.713, nhỉnh hơn History+Cost (0.700) nhưng không có ý nghĩa thống kê.
  - FALCON có xét chi phí đạt 0.748. Tuy vậy QTF (0.761) và LatestFail+CC (0.768) vẫn tốt hơn.
- **Chi phí:** mỗi lần xếp hạng mất khoảng 0.1 s (trung vị 0.0005% thời lượng TSR). Embed toàn bộ lịch sử trên
  GPU T4 mất 17 s.

## 3. Vì sao phần ngữ nghĩa không giúp

1. **Đa dạng ngữ nghĩa không mang tín hiệu lỗi.** Trong thứ tự của FALCON, test fail nằm trung bình ở bách phân
   vị 55% của danh sách, trong khi thứ tự ngẫu nhiên cho 50%.
2. **Lỗi tụ cụm.** Các test fail trong cùng một build giống nhau hơn mức trung bình (cos 0.319 so với 0.275,
   p = 0.001). Facility location lại cố rải lựa chọn ra các cụm khác nhau, nên đẩy các test fail cùng cụm ra sau.
3. **Lịch sử kết hợp chi phí là tín hiệu rất mạnh trên LRTS.** Phần ngữ nghĩa chỉ thay đổi thứ tự ở các vị trí
   mà q gần bằng nhau, và ở đó nó không đúng hơn cách phá hòa theo chi phí.

## 4. Đối chiếu tiêu chí go/no-go (`topic1.md` §3.5)

| Tiêu chí | ActiveMQ | Ghi chú |
|---|---|---|
| APFDc/TTFF tốt hơn trên đa số dự án | ✗ | Ngang LatestFail+CCH, kém History+Cost |
| Tốt hơn cả FALCON và history-only | một phần | Thắng FALCON rõ. Hơn History 3.6% trung vị nhưng không có ý nghĩa |
| Overhead chấp nhận được trong CI | ✓ | 0.1 s mỗi lần xếp hạng |
| Không phụ thuộc một dự án / một α | ✗ | α tốt nhất trên eval là 0, tức là bỏ hẳn phần ngữ nghĩa |
| Không leakage | ✓ | Kiểm tra bất biến và kiểm tra ngược đều đạt |

**Kết luận pilot: chưa đạt ngưỡng.** So với baseline mạnh nhất, cải thiện trung vị khoảng 0%, trong khi kỳ vọng
là 3–5%. Đây mới là một dự án, và phần warm-up nhỏ (18 TSR), nên chưa đủ để kết luận cho toàn đề tài.

## 5. Đề xuất hướng đi (cần giảng viên quyết định)

- **A. Tiếp tục đúng kế hoạch trên Jackrabbit Oak và HBase, không đổi phương pháp.**
  - Nếu kết quả giống ActiveMQ, sản phẩm là một nghiên cứu thực nghiệm với kết quả âm tính được báo cáo trung
    thực: "đa dạng ngữ nghĩa không thêm giá trị so với lịch sử + chi phí trên CI dài hạn".
  - Phần lý thuyết, pipeline chống leakage và phát hiện về LRTS vẫn là đóng góp.
- **B. (Khuyến nghị) Như A, cộng thêm một biến thể được đăng ký trước khi xem dữ liệu Oak/HBase.**
  - Biến thể dùng embedding để **lan truyền lịch sử lỗi** thay vì để đa dạng hóa: test giống với các test vừa
    fail được tăng q. Đây là hướng của Noor & Hemmati (2015), khớp với quan sát "lỗi tụ cụm" ở mục 3.
  - Thành phần này vẫn là modular và không âm, nên giữ nguyên bảo đảm (1−1/e).
  - ActiveMQ được ghi là dự án phát triển. Kết luận cuối cùng chỉ dựa trên Oak và HBase.
- **C. Đổi trọng tâm sang FirstFail** (lỗi của test chưa từng fail), nơi lịch sử không có thông tin. Rủi ro:
  ít mẫu (28 TSR trên ActiveMQ), và QTF đang rất mạnh ở đây.

## 6. Câu hỏi cho giảng viên

1. Thầy/cô chọn hướng A, B hay C?
2. Nếu chọn B: có chấp nhận dùng ActiveMQ làm dự án phát triển và báo cáo kết luận trên Oak, HBase (thêm Hadoop
   hoặc Karaf nếu cần) không?
3. Kết quả âm tính có được chấp nhận làm sản phẩm cuối nếu đến tuần 10 vẫn không đạt ngưỡng không?
