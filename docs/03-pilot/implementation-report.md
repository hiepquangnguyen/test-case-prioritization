# Báo cáo chuẩn hóa dữ liệu và pilot baseline Karaf

Ngày 2026-09-13. Mốc này triển khai audit dữ liệu/source, protocol v2,
cohort/split theo thời gian, chẩn đoán History+cost và replay sáu baseline.
Đọc [protocol v2](protocol-v2.md) và [hướng dẫn tái lập](reproduction.md) để
kiểm tra các lựa chọn. Lõi HC-FALCON và semantic adapters thuộc mốc sau.

## 1. Dữ liệu đã được kiểm tra tới đâu?

Đã đọc toàn bộ **726 class CSV Karaf**, tổng **156.701 lượt quan sát test**.
Count pass/fail khớp metadata ở mọi build; không có duration thiếu/âm hoặc
availability thiếu trong adapter. Có **8.373 duration bằng 0**, được giữ nguyên.
Sai số lớn nhất của tổng duration so metadata khoảng 3,64e-12 giây, phù hợp
sai số floating-point. Cohort gồm 516 SUCCESS, 198 FAILURE và 12 ABORTED.

| Câu hỏi | Bằng chứng | Kết luận |
|---|---|---|
| Đơn vị timestamp/duration? | Collector chia milliseconds cho 1000 và dùng `int`. | Đã xác minh phép chuyển đổi trong code; chưa đối chiếu raw JSON từng build. |
| History có thể bị nhận sớm? | Cả start và duration đều bị làm tròn xuống; 273 build có build trước cùng context chưa hoàn tất tại cutoff. | Thêm biên +2 giây và giữ cutoff nghiêm ngặt. Biên +2 không thay eligibility trên cohort này, nhưng sửa rủi ro ở sát ranh giới. |
| Inventory có biết trước chạy? | Collector lấy testReport; extractor bỏ SKIPPED/tên không hợp lệ, deduplicate và gộp theo FQN. | Không đủ bằng chứng. Đây là observed postprocessed inventory, không phải full intended suite. |
| Có thể khôi phục module/revision thực thi? | Không tìm thấy raw Jenkins build/report/log tương ứng trong phần artifact đã kiểm tra. | Không xác nhận được ở cấp build; source tại SHA metadata không tự chứng minh đó là revision thực thi. |

Collector còn chỉ giữ build có `failcount + passcount > 1`. Vì vậy việc chúng
ta giữ toàn bộ 726 rows không loại bỏ selection bias đã có từ upstream.
Test duration class được cộng từ method và làm tròn 3 chữ số; giá trị 0 không
nhất thiết là test hoàn toàn không tốn thời gian thực.

Evidence theo build và số dòng collector:
[data-audit.json](../../reports/stage3/karaf/data-audit.json),
[audit-summary.json](../../reports/stage3/karaf/audit-summary.json).

## 2. Source: đã rà nhưng không ngầm sửa identity

43 lượt test có vấn đề quy về **30 cặp commit/test**, trên 18 commit cục bộ.
Đã kiểm tra tree, candidate cùng tên và 89 bản cấu hình Jenkins/Maven tại các
commit này. Không có candidate nào khôi phục được exact declaration của các
test trước đó bị đánh dấu missing.

- `OsgiLocatorTest`: 17 lượt, 15 commit/test, đều có hai file ở hai module.
  Nội dung hai candidate giống nhau trong từng cặp. Điều này giúp xác định
  nội dung source, nhưng không khôi phục module hay việc method đã bị upstream
  deduplicate. V2 vẫn giữ ambiguous theo policy identity bảo thủ.
- Candidate `ActivatorTest` và `MainTest` có cùng tên ngắn nhưng khác package;
  không dùng thay source của FQN cần tìm.
- Những test khác không có candidate cùng tên phù hợp tại SHA đã khai báo.
  Chưa có bằng chứng để kết luận là generated test, dependency hay sai revision.
- `JUnit4Provider` vẫn là suspected runner event. Không có stack trace để xác
  định nguyên nhân; record vẫn nằm trong failure denominator.

Đối chiếu [mapping giai đoạn 1](../../reports/stage1/karaf-source-mapping.csv),
tám FQN missing thuộc Karaf đều từng matched ở các revision cục bộ khác
(13–14 revision tùy FQN). Điều này không xác định revision thực thi của build
đang xét, nên không lấy source từ revision khác để lấp chỗ trống.

[source-review.json](../../reports/stage3/karaf/source-review.json) lưu issue,
candidate và bằng chứng theo commit. Hash candidate trong file này là SHA-256
của JSON canonical chứa chuỗi source (để so nội dung), không phải raw blob hash;
hash của các file cấu hình lưu trong source-evidence là raw file SHA-256.

Toàn cohort có 718 SHA khác nhau; chỉ 18 SHA hiện có cục bộ. Mốc này không tải
thêm 700 SHA và không tuyên bố đã audit source toàn cohort. Baseline history
không cần source. Trước chạy semantic toàn cohort phải thực hiện source mapping
tương ứng hoặc báo coverage thiếu theo policy đã chốt.

**Fallback semantic đã được đặc tả:** giữ tất cả test; record thiếu/ambiguous
source có semantic similarity bằng 0, không embedding giả; history/cost vẫn
được dùng trong hybrid. Pure semantic tie-break theo FQN khi gain bằng 0.
Coverage universe semantic chỉ gồm source hợp lệ; evaluator vẫn giữ full
inventory. Đây là đặc tả tích hợp, chưa có semantic ranker ở mốc này.

## 3. Split và cấu hình đã đóng băng

Chọn ranh giới lịch UTC dựa trên khoảng thời gian dữ liệu, trước scoring mở
rộng; không thay split sau khi nhìn failure/score. Các giá trị công thức v1
được giữ nguyên; Random có seed 0..19, deterministic chạy một lần.

| Split | Khoảng cutoff UTC | Build-stage | Test observations | ABORTED |
|---|---|---:|---:|---:|
| Warm-up | Trước 2022-01-01 | 246 | 51.205 | 7 |
| Development | Năm 2022 | 317 | 69.155 | 2 |
| Holdout baseline | Từ 2023-01-01 | 163 | 36.341 | 3 |

20 build đã xem nằm trong warm-up, chỉ phân tích riêng với nhãn technical20.
Warm-up không chấm metric chính. Trong development/holdout, chỉ nhận feedback
của build đã hoàn tất cùng context; không bảo đảm mọi test/branch đã hết cold
start. Không có PR hoặc commit holdout trùng phần trước trong cohort này,
nhưng đây vẫn là thiết kế temporal replay, không phải cross-project evaluation.

[manifest.json](../../reports/stage3/karaf/manifest.json) lưu checksum/config;
[selection.json](../../reports/stage3/karaf/selection.json) lưu từng build/split.

## 4. Kết quả và kiểm chứng

Đã sinh **18.150 ranking**: 25 ranking/build, gồm 20 seed Random và 5 baseline
deterministic. Giữ toàn inventory ở mọi ranking, kể cả warm-up và ABORTED.
Các build warm-up không có metric chính. Development có 315 build đủ điều
kiện chấm, 79 build có failure; holdout có 160 build đủ điều kiện, 48 có failure.
236/112 build không failure tương ứng có APFDc NA và TTFF censored.

| Baseline | Development: median APFDc | Holdout baseline: median APFDc |
|---|---:|---:|
| Random | 0,490777 | 0,504451 |
| Shortest-Test-First | 0,698368 | 0,681707 |
| Most-Fail | 0,742025 | 0,702719 |
| Recent-Fail | 0,843360 | 0,714637 |
| History-only | 0,773867 | 0,706626 |
| History+cost | 0,891918 | 0,799868 |

Random lấy mean của 20 seed trong mỗi build rồi median giữa build; không nhân
số mẫu độc lập lên 20 lần. Median APFDc riêng từng seed dao động 0,424526–0,586817
ở development và 0,378146–0,560222 ở holdout. Các bảng metric chỉ tổng hợp build
có metric xác định, không gán no-failure score 0 hoặc 1.

History+cost có median APFDc cao nhất trong sáu baseline ở cả hai split này.
Median TTFF execution-only của History+cost/History-only là 54,037/81,999 giây
ở development và 128,2975/132,733 giây ở holdout, chỉ tính build quan sát được
failure. Holdout Most-Fail có median TTFF thấp hơn (99,308 giây); không có một
phương pháp đứng đầu mọi metric. Đây là kết quả mô tả trên một dự án, không
có kiểm định superiority và chưa có HC-FALCON trong bảng.

Warm-up/development/holdout lần lượt còn 4/1/1 build không có history hợp lệ
trong context, và 824/245/233 lượt test có N=0. Vì vậy warm-up làm giảm cold
start nhưng không loại bỏ cold start khi xuất hiện branch hoặc test mới.

Chi tiết: [summary.json](../../reports/stage3/karaf/summary.json),
[metrics.csv](../../reports/stage3/karaf/metrics.csv),
[ledger.json](../../reports/stage3/karaf/ledger.json).

### Chẩn đoán History+cost

So APFDc trên cùng build, đặt delta = History+cost − History-only:

| Cohort chẩn đoán | Số cặp xác định | Cost tốt hơn | Cost kém hơn | Hòa | Median paired delta |
|---|---:|---:|---:|---:|---:|
| Technical20, 18 build hợp lệ | 10 | 2 | 6 | 2 | −0,004284 |
| Development, 315 build hợp lệ | 79 | 51 | 27 | 1 | +0,026318 |

Median chênh lệch từng build **không bằng** chênh lệch hai median trong bảng
trên. Kết quả đổi dấu khi mở rộng cohort không tách riêng được tác động của
warm-up, giai đoạn thời gian và phân bố failure; không quy toàn bộ cải thiện
cho việc có thêm history.

Ba phương pháp Most-Fail/Recent-Fail/History-only chỉ có ranking đồng nhất
trên 6/18 build technical và 4/315 build development. Vì vậy median trùng nhau
ở mẫu cũ không chứng minh các phương pháp tương đương.

**Cost chủ yếu đổi thứ tự để chạy nhiều test ngắn trước, không đưa failure lên
đầu danh sách.** Trong development, 117 failing records chuyển xuống vị trí
muộn hơn, chỉ 1 chuyển sớm hơn khi thêm cost. Ví dụ:

- PR-1583/build1: `ExampleWithConfigITest` từ vị trí 35 xuống 99 nhưng TTFF
  giảm từ 944,751 xuống 50,111 giây; APFDc tăng từ 0,338394 lên 0,968284.
  Đứng sau nhiều test hơn vẫn có thể hoàn tất sớm hơn nếu các test trước ngắn.
- PR-1504/build3: `MainLockingTest` từ vị trí 1 xuống 133, TTFF tăng từ 16,457
  lên 48,703 giây; APFDc giảm 0,332402. Đây là trường hợp cost làm xấu kết quả.
- Ở mẫu cũ PR-1294/build1, test LDAP từ vị trí 1 xuống 63; runtime dự đoán
  9,603 giây so với actual 11,801 giây. Vì vậy điểm giảm không chỉ là vấn đề
  ước lượng runtime; mức phạt cost có thể lấn át tín hiệu failure history.

Đánh đổi thể hiện rõ ở các metric khác (median trên các build xác định):

| Metric | Development HO / HC | Holdout baseline HO / HC |
|---|---|---|
| APFD, theo vị trí test | 0,958716 / 0,446667 | 0,948349 / 0,471366 |
| Recall tại 10% thời gian | 0,25 / 0,50 | 0,143581 / 0,00 |
| Recall tại 25% thời gian | 0,50 / 1,00 | 0,416667 / 0,666667 |

HO = History-only; HC = History+cost. Holdout ở đây chỉ là bảng mô tả metric
của cấu hình cố định, không được dùng để chọn công thức. APFDc cao hơn chưa
bảo đảm tốt hơn ở ngân sách rất nhỏ hoặc số lượng test được chạy trước.

Runtime estimate cũng chưa đồng đều giữa nhóm test. Trên development, median
tỷ lệ predicted/actual của nhóm N>=5 khoảng 0,985; nhóm N=0 khoảng 3,800.
Median absolute error tương ứng 0,0365 và 0,981 giây. Tỷ lệ chỉ tính actual>0;
error tuyệt đối vẫn tính actual=0. Các thống kê này gộp theo test observation,
không chứng minh dự đoán tốt riêng trên failing/long-running tests. Chi tiết
theo build/test được giữ để kiểm tra sai số lớn và sự thay đổi runtime.

Đầu ra phân tích chỉ gồm technical20/development:
[history-cost-paired.json](../../reports/stage3/karaf/history-cost-paired.json),
[history-cost-summary.json](../../reports/stage3/karaf/history-cost-summary.json),
[development-runtime-errors.jsonl.gz](../../reports/stage3/karaf/development-runtime-errors.jsonl.gz).
Không chỉnh công thức sau phân tích này.

### Kiểm chứng đã hoàn tất

- **21 unit tests đạt**: 16 test nền và 5 test mới cho split UTC, rounding guard,
  warm-up/status eligibility, evidence hash và tổng hợp Random theo build.
- **Tái lập đủ 726 snapshot và 18.150 ranking/metric** từ input/ground truth
  đã lưu; kiểm tra full permutation, history eligibility, CSV và summary.
- **295 cutoff, 7.375 phép so sánh mutation đạt**: thay outcome, duration,
  status và availability của toàn bộ current/future builds, snapshot và mọi
  ranking giữ nguyên. Cutoff gồm ranh giới split, 20 build kỹ thuật, build cuối
  và build chồng lấn cùng context.
- Manifest, code/protocol và checksum artifact đều khớp. Code/protocol v1
  cùng kết quả stage2 được giữ nguyên. Lượt chạy dùng Python 3.12.10 trên Windows.

Bằng chứng: [verification.json](../../reports/stage3/karaf/verification.json),
[run-complete.json](../../reports/stage3/karaf/run-complete.json),
[environment.json](../../reports/stage3/karaf/environment.json).
Các kiểm tra này xác nhận implementation theo giả định đã khai báo, không
chứng minh inventory/timestamp của nguồn dữ liệu hợp lệ cho CI prospective.

## 5. Ý nghĩa và điều kiện chuyển tiếp

Mốc triển khai đã hoàn tất. Các hạn chế của nguồn dữ liệu đã được cụ thể hóa thành bằng chứng và phạm vi
kết luận. Không thể dùng replay này để khẳng định thời gian CI thực, inventory
biết trước hoặc số lỗi phần mềm độc lập. Đặc biệt, metric tốt không khắc phục
việc upstream đã lọc/gộp test.

Sau khi xem score baseline, holdout này không còn là tập chưa từng quan sát
cho việc phát triển HC-FALCON. Khi tích hợp FALCON/DANTE/HC-FALCON, cần tập xác
nhận mới và phương pháp đã chốt trước khi xem kết quả; nếu tiếp tục dùng split
này phải ghi nhãn exploratory. Defects4J tiếp tục là nhánh riêng với đơn vị
fault; không tổng hợp chung denominator với LRTS failing records.
