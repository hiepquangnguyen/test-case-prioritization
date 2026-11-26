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

## 2026-11-26: HC-FALCON đầu-cuối (tuần 5)

**Chi tiết cài đặt chốt ở tuần này** (`estimators.py`, `scoring.py`, `hc_falcon.py`):

- Prior của Beta và decay: μ là tỉ lệ fail của stage, chỉ tính trên các lần chạy trong quá khứ; độ mạnh s = 2.
  Test mới nhận p = μ.
- Stickiness:
  - p = P(fail | kết quả lần chạy trước của test), ước lượng từ số lần chuyển trạng thái của chính test đó.
  - Số đếm được làm mượt về tỉ lệ chuyển trạng thái gộp của cả stage (cũng làm mượt về μ). Lần chạy đầu của
    một test không được tính là một lần chuyển.
- Wilson: lấy cận dưới (z = 1.96) và dùng với conf = 1, vì cận dưới đã tự co lại khi có ít dữ liệu.
- Chi phí c:
  - c = thời gian trung bình các lần chạy trước + 1 ms. Test mới nhận trung vị c của các test đã biết trong cùng
    TSR.
  - c̃ = c / trung vị c trong TSR.
  - Test chạy ~0 s có c̃ rất nhỏ, nên q bị phóng lên (giống CC của LRTS, đẩy test nhanh lên đầu).
- Phá hòa: c ước lượng nhỏ hơn trước, rồi theo tên. Với α = 0, greedy tương đương sắp theo q giảm dần, nên
  code dùng sắp xếp trực tiếp, cho kết quả trùng (có test kiểm chứng).
- RankBlend / RRF trộn thứ hạng của FALCON (α = 1) với History+Cost (α = 0, cùng bộ ước lượng). Như vậy chỉ
  khác HC-FALCON ở cách kết hợp: trộn thứ hạng thay vì một hàm submodular. β của RankBlend được tinh chỉnh trên
  warm-up giống α.

**Kiểm chứng:**
- Kiểm tra leakage trên ActiveMQ đạt với cả 4 bộ ước lượng, cho HC-FALCON và RankBlend: thứ tự không đổi khi
  xóa hoặc xáo trộn tương lai.
- Khi cố ý cho rò rỉ, APFDc của HC-FALCON tăng từ 0.826 lên 0.966.

**Tín hiệu sơ bộ, chưa phải kết luận** (dùng cho pilot tuần 6):

- Cấu hình mặc định (α = 0.5, decay λ = 0.9, κ = 3, γ = 0.5), trên 78 TSR DeConf thuộc phần eval của ActiveMQ:

  | Phương pháp | APFDc |
  |---|---|
  | HC-FALCON | 0.848 |
  | History+Cost | 0.844 |
  | LatestFail+CCH | **0.865** |
  | MostFail+CC | 0.857 |
  | LatestFail+CC | 0.846 |
  | RankBlend | 0.784 |
  | FALCON | 0.494 (≈ Random 0.488) |

- Tinh chỉnh trên warm-up (chỉ 18 TSR):
  - APFDc giảm đều khi tăng α (α = 0: 0.752; α = 0.5: 0.734; α = 1: 0.533), nên chọn α = 0 và bộ ước lượng
    Beta. Với α = 0, HC-FALCON suy về History+Cost.
  - β tốt nhất của RankBlend cũng là 0.
- Trong 10 lựa chọn đầu, phần ngữ nghĩa chỉ chiếm khoảng 12–14% gain khi α = 0.5. Sau lựa chọn đầu tiên, gain
  của FL/|T| giảm rất nhanh.
- Đây đúng là rủi ro §8.1/§8.2 của bản phân tích. Tuần 6 sẽ thử các biến thể định nghĩa trước (γ = 1, chọn
  theo tỉ lệ, prior cho test mới, ...) và viết pilot memo.

## 2026-11-26: Pilot ActiveMQ, go/no-go #1 (tuần 6)

Chi tiết và đề xuất: [pilot-memo.md](pilot-memo.md).

- **Sửa lỗi định nghĩa ablation** (phát hiện khi chạy pilot, trước khi chốt bất kỳ kết luận nào):
  - FALCON, History và FL+History từng thừa hưởng `selection: ratio` của cấu hình khóa. Kết quả là "FALCON"
    thành FALCON có xét chi phí (0.725), và "History" có chi phí.
  - Giờ ba baseline này luôn dùng `selection: gain` và không tính chi phí. FALCON có xét chi phí tách thành
    `FALCON-ratio`.
  - History+Cost = mô hình đã cấu hình với α = 0, giữ nguyên cách xử lý chi phí. RankBlend/RRF trộn với
    FALCON thuần.
  - Có test hồi quy cho điểm này.
- **Cấu hình khóa trên warm-up:** biến thể `ratio + γ = 1`, α = 0.4, ước lượng Beta, κ = 3
  (`configs/tuned/activemq-deconf-locked.yaml`).
  - Với `selection: ratio`, chi phí vào hai lần ở phần q: một lần trong q, một lần trong tỉ lệ. Đây là đúng định
    nghĩa của biến thể đã đăng ký trước (ΔF/c^γ), ghi lại để tránh hiểu nhầm.
- **Kết quả eval** (78 TSR DeConf):

  | Phương pháp | APFDc |
  |---|---|
  | HC-FALCON | 0.854 |
  | History+Cost | 0.862 (HC-FALCON kém có ý nghĩa, p_Holm = 0.04, δ không đáng kể) |
  | LatestFail+CCH | 0.865 (không khác biệt có ý nghĩa) |
  | History | 0.833 |
  | FALCON | 0.494 |

  - α trên eval giảm đều: α = 0 là tốt nhất.
  - Overhead khoảng 0.1 s mỗi lần xếp hạng.
- **Kết luận: chưa đạt ngưỡng go**, vì cải thiện trung vị khoảng 0% so với baseline mạnh nhất, trong khi kỳ vọng
  là 3–5%. Đang chờ giảng viên chọn hướng A/B/C trong memo.
- Phần eval của ActiveMQ đã được xem. Nếu chọn hướng B (biến thể mới), ActiveMQ chỉ còn là dự án phát triển,
  không dùng làm bằng chứng cho biến thể đó.

## 2026-11-26: Tái lập FALCON trên Defects4J

- Thứ tự của `lazy_greedy` trùng với artifact cho tới lần hòa tuyệt đối đầu tiên. Giá trị FL của mọi tiền tố
  bằng nhau.
- APFD từng dự án nhạy với cách phá hòa: nhiễu 1e-6 làm APFD của Math dao động 0.58–0.67.
- Hệ quả: trên LRTS dùng phá hòa tất định (thời gian ngắn trước, rồi theo tên), như đã chốt trong
  `configs/default.yaml`. Độ nhạy này được ghi vào threats.
