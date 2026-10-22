# Báo cáo triển khai protocol v1

Ngày: 2026-09-13. Đã hoàn thành phần 1–3: chốt protocol, adapter dữ liệu/rolling
history, evaluator và sáu baseline đơn giản. Kết quả là một pipeline replay có
thể kiểm tra và tái lập trên LRTS Karaf. Chưa triển khai lõi HC-FALCON, semantic
FALCON, DANTE adaptation hoặc FAST; chưa mở rộng đánh giá Defects4J.

## 1. Những gì đã triển khai

| Thành phần | Hành vi và bằng chứng |
|---|---|
| [Protocol v1](protocol-v1.md) | Chốt đơn vị, cutoff, context, missing data, công thức và eligibility trước lượt replay. |
| [Data model](../../tcp/domain.py), [adapter LRTS](../../tcp/lrts.py) | Tách input trước ranking khỏi ground truth; đọc raw CSV trong ZIP, giữ mọi test, annotate source và lỗi nghi thuộc runner. |
| [Rolling history](../../tcp/history.py) | Chỉ dùng build đã hoàn tất trước cutoff, cùng project/base branch/stage và khác physical build. Không dùng history tính sẵn trong artifact. |
| [Baselines](../../tcp/baselines.py) | Random, Shortest-Test-First, Most-Fail, Recent-Fail, History-only, History+cost. Cùng inventory và feature snapshot. |
| [Evaluator](../../tcp/metrics.py) | APFD, APFDc midpoint, TTFF và recall tại 10/25/50% thời gian; kiểm tra permutation đầy đủ, xử lý NA và censoring rõ ràng. |
| [Replay](../../tcp/replay.py), [runner](../../scripts/stage2_run.py) | Lưu input, feature, ground truth, ranking, metric, ledger và manifest có checksum. |

Runtime dùng để xếp hạng là ước lượng từ quá khứ. Runtime thực của build hiện
tại chỉ phục vụ evaluator. Test mới không bị gán PASS; test thiếu source hoặc
duration bằng 0 không bị loại để làm score đẹp hơn. Build ABORTED vẫn có ranking
chẩn đoán nhưng không vào history hoặc metric chính.

## 2. Kết quả lượt chạy Karaf20

Chọn 20 build-stage đầu theo timestamp, không chọn theo outcome. Seed 42,
cấu hình cố định trong [manifest](../../reports/stage2/karaf20/manifest.json).

| Chỉ số kiểm tra | Kết quả |
|---|---:|
| Build-stage được giữ | 20 |
| Ranking đầy đủ, 6 phương pháp/build | 120 |
| Tổng lượt quan sát test | 3.740 |
| Tổng failing records trong cohort | 18 |
| Build đủ điều kiện chấm | 18 |
| Build ABORTED chỉ dùng chẩn đoán | 2 |
| Build có failure và APFDc xác định | 10 |
| Build đủ điều kiện nhưng không có failure | 8 |
| Lượt test thiếu hoặc ambiguous source vẫn giữ | 43 |

Hai build ABORTED là PR-1213/build3 và build4, chứa tổng cộng 3 failing records.
Vì vậy tập đủ điều kiện chấm còn 15 failing records. Đây là số record fail,
không phải số lỗi phần mềm độc lập.

**PR-1287/build1 giữ đủ 212 test và 4 failure**, bao gồm record nghi thuộc
JUnit4Provider. Runner DANTE ở giai đoạn 1 đã thu nhỏ còn 206 test và 3 failure.
V1 không lặp lại việc lọc đó. Theo chính sách chỉ dùng build hoàn tất và tách
base branch, build này có history rỗng trong cohort hiện tại. Không so trực tiếp
score v1 với smoke DANTE cũ vì inventory, history và evaluator đã khác.

Median APFDc dưới đây chỉ là số chẩn đoán trên 10 build có metric xác định;
8 build không failure có APFDc NA, không được gán 1 hoặc 0.

| Baseline | Median APFDc midpoint |
|---|---:|
| Random | 0,635700 |
| Shortest-Test-First | 0,647738 |
| Most-Fail | 0,877600 |
| Recent-Fail | 0,877600 |
| History-only | 0,877600 |
| History+cost | 0,760628 |

Các median trùng nhau không chứng minh ranking giống nhau. Chênh lệch score
chưa chứng minh ưu thế tổng quát; không dùng kết quả này để chọn tham số.
Chi tiết nằm trong [metrics.csv](../../reports/stage2/karaf20/metrics.csv),
[summary.json](../../reports/stage2/karaf20/summary.json) và
[ledger.json](../../reports/stage2/karaf20/ledger.json).

## 3. Kiểm chứng đã thực hiện

- **16 unit tests đạt**: công thức tính tay, đổi đơn vị thời gian, zero/missing
  duration, unknown/no-failure, permutation, cutoff nghiêm ngặt, context và
  physical-build isolation, cold start, tie-break và random có thể tái lập.
- **Tái lập 120 ranking và metric đạt** từ input/ground truth đã lưu; so snapshot
  đầy đủ và bỏ qua timing vốn phụ thuộc máy.
- **120 phép so sánh chống leakage trên cohort thật đạt**: tại từng cutoff,
  thay outcome, duration, status và availability của current/future builds;
  feature snapshot và ranking của cả sáu phương pháp không đổi.
- Kiểm tra giữ toàn inventory, cùng snapshot giữa các phương pháp và checksum
  code/protocol đều đạt. Unit test có đối chứng thay history quá khứ làm ranking
  tương lai thay đổi, tránh kiểm tra một pipeline vô tình bỏ qua toàn bộ history.

Kết quả máy đọc được: [verification.json](../../reports/stage2/karaf20/verification.json).
Lệnh tái lập: [reproduction.md](reproduction.md).

## 4. Kết luận và ảnh hưởng tới bước tiếp theo

Pipeline hiện đủ làm nền để tích hợp phương pháp mới: cùng dữ liệu đầu vào,
cùng history, cùng evaluator và có bằng chứng kiểm tra ranh giới thời gian.
Việc giữ nguyên test universe khắc phục một nguồn sai lệch cụ thể của smoke
DANTE trước đó. Tuy nhiên, đây chưa phải bằng chứng hiệu quả của HC-FALCON.

Các giới hạn phải được giải quyết trước pilot đánh giá hiệu quả:

1. **Inventory và timestamp:** inventory hiện lấy từ log sau chạy; chưa xác minh
   được toàn suite dự định trước chạy. Availability dùng giả định timestamp là
   start và duration là thời gian build. Mutation checks chỉ có hiệu lực trong
   các giả định này, không chứng minh tính hợp lệ khi chạy CI thực.
2. **Semantic input:** xác minh source/module tại revision thực thi, xử lý
   ambiguous source và runner event, rồi chốt fallback chung trước khi tích hợp
   semantic FALCON/HC-FALCON. Không ngầm thay source bằng tên test.
3. **Cohort đánh giá:** 20 build này là technical replay, chỉ có history trong
   cohort, chưa có warm-up/calibration/holdout. Cần chốt split và mở rộng dữ liệu
   trước so sánh thống kê; không biến cohort này thành tập đánh giá sau khi đã
   xem kết quả.
4. **Tích hợp phương pháp:** sau các quyết định trên, đưa FALCON/DANTE adaptation
   vào cùng interface và evaluator, rồi triển khai fusion HC-FALCON và ablation.
   TTFF hiện chỉ tính execution; latency end-to-end cần thêm chi phí chuẩn bị
   semantic và ranking khi các thành phần đó được triển khai.

Phạm vi được duyệt đã hoàn tất; các mục trên là công việc của mốc tiếp theo.
