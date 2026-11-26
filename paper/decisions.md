# Nhật ký quyết định

Mỗi thay đổi so với giao thức trong `configs/default.yaml` hoặc kế hoạch phải được ghi ở đây kèm lý do.

## 2026-11-26: Ba điểm đề bài chưa rõ (chốt theo phương án đề xuất)

**D1. "TCP approach combinators".** Đề bài không nêu nguồn và chưa tìm thấy paper dùng đúng thuật ngữ này.
Hiểu là các cách *kết hợp kỹ thuật TCP*:
- lai điểm với chi phí: CC (`score × time`), CCH (`score × time / failcount`), theo Peng et al. (ISSTA 2020) và
  LRTS;
- sắp xếp theo thứ tự từ điển: heuristic chính, phá hòa bằng heuristic phụ;
- gộp thứ hạng: Borda, Reciprocal Rank Fusion (RRF);
- tổ hợp tuyến tính điểm.

Hệ quả: phần Related work khảo sát các nhóm trên. RankBlend(β) và RRF là baseline kết hợp bắt buộc. Nếu giảng
viên đưa nguồn cụ thể thì bổ sung, không đổi thiết kế thực nghiệm.

**D2. Mức chi tiết: test class trên LRTS.** Processed LRTS chỉ có kết quả theo test class
(`testclass, duration, outcome, last_outcome`), và các baseline LRTS/DANTE cũng làm ở mức class.
- HC-FALCON trên LRTS xếp hạng test class. Vector của một class là trung bình các vector method đã chuẩn hóa L2.
- Phần tái lập FALCON trên Defects4J giữ mức test method, giống paper gốc.
- Ghi vào threats (construct validity): kết quả mức class không suy ra trực tiếp cho mức method.

**D3. Ngân sách: theo số test, không làm biến thể knapsack theo thời gian.**
- Kết quả chính là thứ tự đầy đủ do greedy tạo ra. Mọi tiền tố có bảo đảm (1−1/e) dưới ràng buộc cardinality.
- Hiệu quả theo thời gian đo bằng APFDc, TTFF và tỉ lệ lỗi phát hiện trong 10/25/50% thời gian chạy
  (`det10/25/50`).
- Greedy theo tỉ lệ `ΔF/c^γ` (`objective.selection: ratio`) chỉ là biến thể dự phòng trong pilot tuần 6, dùng
  khi FL kéo test dài lên đầu. Nếu dùng thì nêu rõ bảo đảm chỉ còn ½(1−1/e) (dạng knapsack, CELF).

## 2026-11-26: Tập TSR của LRTS

`dataset.csv` trên Google Drive (108.366 TSR, tới 2024-04) là tập mẹ của `artifact/metadata/dataset.csv`
(57.437 TSR, tới 2023-07). Phần chung khớp từng dòng.
- Kiểm tra baseline (tuần 3, 7) dùng tập của artifact để so được với `eval_outcome`.
- Các TSR từ 2023-08 có thể dùng làm tập kiểm tra ngoài thời gian. Sẽ quyết sau pilot.

## 2026-11-26: Pipeline LRTS và kiểm tra baseline (tuần 3)

- **Nhãn lọc tự sinh lại** (`lrts/filters.py`, bản chép lại `extract_filtered_test_result.py` của LRTS, kể cả
  các điểm lạ của nó). Kết quả khớp 100% với `dataset_filter.csv` ở ActiveMQ, Oak, HBase và Karaf.
  - Hadoop: nhãn freqfail chỉ khớp 97.5%, nên DeConf có 423 TSR thay vì 421. Đếm số lần fail trên chỉ mục
    artifact hay trên toàn bộ dữ liệu Drive đều không ra đúng; có lẽ thư mục dữ liệu lúc tác giả chạy chứa
    một tập build nằm giữa hai tập này.
  - Hadoop chỉ là dự án dự phòng nên giữ nguyên, ghi vào threats nếu dùng đến.
- **Các TSR cùng timestamp** trong một stage được xếp hạng hết rồi mới cập nhật lịch sử. LRTS thì cập nhật
  tuần tự. Mỗi dự án chỉ có 0–7 trường hợp, ảnh hưởng không đáng kể.
- **Dòng ngẫu nhiên riêng cho từng TSR** (`rolling.tsr_rng`, sinh từ seed và CRC32 của khóa TSR).
  - Bản đầu dùng chung seed 0–9 cho mọi TSR, nên các TSR cùng số test nhận cùng một hoán vị. Với 10 seed,
    Random trên Karaf ra 0.55, trong khi 200 seed cho 0.498.
  - LRTS có lẽ bị cùng vấn đề: `random.Random(10)` dùng chung khi tách tiến trình. Vì thế giá trị Random của
    LRTS có sai số lớn hơn sai số chuẩn danh nghĩa.
- **Phát hiện về LRTS: QTF(Avg) trong `eval_outcome` bị rò rỉ.**
  - Thời gian trung bình họ dùng có tính cả lần chạy đang được xếp hạng. Tính lại theo cách đó thì khớp từng TSR
    (sai khác tuyệt đối trung bình 0.0003) ở HBase, Oak và ActiveMQ. Code trong repo của họ tính đúng.
  - Trên HBase, rò rỉ này làm QTF(Avg) **tệ đi** (0.545 so với 0.601 bản sạch), vì test fail thường chạy lâu hơn
    ở chính lần fail.
  - Mình dùng định nghĩa sạch. Khi so sánh với số trong paper LRTS phải nêu rõ điểm này.

## 2026-11-26: Tái lập FALCON trên Defects4J

- Thứ tự của `lazy_greedy` trùng với artifact cho tới lần hòa tuyệt đối đầu tiên. Giá trị FL của mọi tiền tố
  bằng nhau.
- APFD từng dự án nhạy với cách phá hòa: nhiễu 1e-6 làm APFD của Math dao động 0.58–0.67.
- Hệ quả: trên LRTS dùng phá hòa tất định (thời gian ngắn trước, rồi theo tên), như đã chốt trong
  `configs/default.yaml`. Độ nhạy này được ghi vào threats.
