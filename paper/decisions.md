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

## 2026-11-26: Mã nguồn test và corpus embedding (tuần 4)

- **Commit cho mỗi build:** dùng `build_head_sha` (PR head mà Jenkins build).
  - 131/391 commit head của ActiveMQ không còn trên `refs/pull/*/head` vì PR bị force-push, nhưng GitHub vẫn
    cho fetch theo SHA, nên lấy đủ 391/391.
  - Class không có ở PR head thì tìm tiếp ở `trunk_sha` của cùng build. Jenkins chạy bản merge của PR vào
    trunk, nên test được thêm vào trunk sau khi PR tách nhánh có trong lần chạy nhưng không có ở head.
  - Fallback này đưa 4 TSR từ độ phủ 68–88% lên trên 95%. Dùng head + trunk thay cho commit merge thật là
    một xấp xỉ, ghi vào threats.
- **Nội dung embed** cho một file test:
  1. các method test (`@Test` và các annotation JUnit 5 tương tự, hoặc kiểu JUnit 3 `public void test*()`);
  2. nếu không có thì mọi method (class kế thừa test từ lớp cha);
  3. nếu không parse được method nào thì cả file.
  - Bỏ annotation, xuống dòng thành dấu cách (giống FALCON). Method trùng nội dung chỉ embed một lần (id =
    SHA-1 của text).
- **ActiveMQ (chỉ mục Drive, 446 TSR):** tìm được mã nguồn cho 98.1% số cặp (TSR, test class); TSR thấp nhất
  đạt 94.8%.
  - Gần như toàn bộ phần thiếu (91%) là các test conformance `org.objectweb.jtests...` chạy từ một jar phụ
    thuộc, không có mã nguồn trong repo. Không tính nhóm này thì độ phủ là 99.99%.
  - Class thiếu mã nguồn được cô lập: sim = 0 với mọi test khác, chỉ phủ chính nó.
  - Corpus: 2.198 phiên bản file, 4.456 method duy nhất.
- **Embedding ActiveMQ** (Colab T4, UniXcoder, masked mean-pool):
  - 17.0 s cho toàn bộ 4.456 method (886k token); 420 method (9.4%) bị cắt ở 512 token.
  - Mọi test fail trong các TSR DeConf đều có vector (344/344).
- **Quan sát cho pilot, chưa phải kết luận:**
  - Cosine giữa các class gần như luôn dương (chỉ 0.46% cặp âm), nên `clip` hầu như không đổi ma trận.
  - Láng giềng gần nhất cùng package ở 44% class (ngẫu nhiên 4%).
  - Các test fail cùng một TSR giống nhau hơn trung bình (0.319 so với 0.275, p = 0.001). Lỗi có xu hướng tụ
    cụm, trong khi facility location chọn đại diện rải đều các cụm: tốt cho việc tìm sớm lỗi đầu tiên của mỗi
    cụm, nhưng có thể đẩy các test fail còn lại trong cụm ra sau. Cần xem trong pilot tuần 6.

## 2026-11-26: Tái lập FALCON trên Defects4J

- Thứ tự của `lazy_greedy` trùng với artifact cho tới lần hòa tuyệt đối đầu tiên. Giá trị FL của mọi tiền tố
  bằng nhau.
- APFD từng dự án nhạy với cách phá hòa: nhiễu 1e-6 làm APFD của Math dao động 0.58–0.67.
- Hệ quả: trên LRTS dùng phá hòa tất định (thời gian ngắn trước, rồi theo tên), như đã chốt trong
  `configs/default.yaml`. Độ nhạy này được ghi vào threats.
