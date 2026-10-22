# Báo cáo giai đoạn 4 — khả thi đa dự án và thiết kế HC-FALCON v1

Ngày 2026-09-13. Đã audit sâu ActiveMQ/Log4j, kiểm tra source mẫu tại commit
đã pin, chốt semantic pipeline/objective và protocol đánh giá. **Chưa triển khai
lõi HC-FALCON, chưa chạy semantic pilot và chưa mở method score trên reserved
confirmation.** Giai đoạn 4 bàn giao thiết kế có bằng chứng, không phải kết quả
hiệu quả của phương pháp mới.

Tài liệu chính: [đặc tả HC-FALCON v1](hc-falcon-v1.md),
[protocol đánh giá](evaluation-protocol.md), [tái lập](reproduction.md).

## 1. Kết luận khả thi của ba dự án

| Project | Build-stage rows | Physical builds | Test observations | Source sample tại declared SHA |
|---|---:|---:|---:|---|
| Karaf, đã audit stage3 | 726 | 726 | 156.701 | 3.697/3.740, 98,85%; 18 SHA / 20 build |
| ActiveMQ, audit mới | 446 | 446 | 379.243 | 9.957/10.407, 95,68%; 19 SHA / 20 build |
| Log4j, audit mới | 528 | 270 | 340.046 | 24.278/24.638, 98,54%; 20 SHA / 20 build / 40 stage |

**Giữ Karaf, ActiveMQ và Log4j làm ba dự án pilot.** Cả ba khả dụng cho history
replay và có bằng chứng source Java ở mẫu đầu. Đây là go có điều kiện cho
triển khai semantic: phải hoàn thành source mapping phần warm-up/development
dự định chạy và báo coverage trước pilot, không ngoại suy coverage mẫu ra toàn
cohort. Actual execution revision và pre-build inventory vẫn chưa xác minh.

## 2. Audit dữ liệu mới

Đã đọc lại toàn bộ 974 raw class CSV được metadata tham chiếu của hai dự án:
không lệch count pass/fail, không outcome ngoài 0/1, không duration thiếu/âm
hoặc availability thiếu trong adapter. Giữ 4.614 duration=0 ActiveMQ và 3.172
duration=0 Log4j. Mọi ID/inventory được kiểm tra bởi data model; không lọc theo
outcome để có tập thuận lợi.

| Chỉ số | ActiveMQ | Log4j |
|---|---:|---:|
| Stage labels | single | Ubuntu_Test, Windows_Test |
| Median / max suite size | 1.009 / 1.025 | 651 / 666 |
| Stage rows có build trước cùng context chưa hoàn tất | 216 | 124 |
| Kernel float32 lớn nhất, chỉ riêng ma trận | 4.202.500 bytes | 1.774.224 bytes |

Kích thước ma trận cho thấy kernel dense của hai cohort này không phải phần
memory lớn nhất hiển nhiên; chưa đo memory encoder hoặc runtime semantic.
Không suy từ kích thước kernel rằng toàn pipeline đã đạt gate CI.

Log4j có **270 physical builds**, không phải 528 build độc lập. Không gộp
history Ubuntu/Windows hoặc stage của cùng build hiện tại. Stage chỉ là đơn
vị ranking; thống kê phải gộp về physical build như protocol đã chốt.

Không tìm thấy raw Jenkins build/test report tương ứng trong các entry đã
kiểm tra. Dữ liệu tiếp tục có giới hạn upstream: lọc skipped/tên, gộp FQN,
timestamp/duration bị làm tròn. Giữ biên +2s và không tuyên bố inventory này
được biết trước chạy hoặc đại diện mọi build CI ban đầu.

Bằng chứng: [ActiveMQ summary](../../reports/stage4/activemq/summary.json),
[Log4j summary](../../reports/stage4/log4j/summary.json); file build-audit và
history-readiness trong cùng thư mục giữ kết quả theo cutoff.

## 3. Source audit đã thực hiện và vấn đề còn lại

Đã fetch **39 SHA cố định** từ hai repository Apache, depth1/blob limit1MiB;
không checkout/build/chạy test Java. Git blob được đọc offline, không lazy fetch.
Source sample chọn first 20 physical warm-up builds mỗi project trước xem
outcome; Log4j giữ cả hai stage. Đã kiểm tra thêm 155 bản source/config evidence.

**ActiveMQ:** 117 lượt ambiguous giữa các module, 333 lượt missing Java source
theo suffix/package matcher. Trong nhóm missing, 329 lượt thuộc
`org.objectweb.jtests.*`. POM khai báo dependency `joram-jms-tests` và
`JoramJmsTest.java` import các class này: có bằng chứng chúng liên quan test
dependency, chưa có dependency source mapping/version đầy đủ để coi matched.
Bốn lượt còn lại là các test LevelDB chưa khớp tại SHA metadata. Không lấy
source từ revision khác để lấp chỗ trống. 18/18 failing records trong mẫu có
mapping declared revision.

**Log4j:** 360 lượt ambiguous thuộc 9 FQN SLF4J, xuất hiện ở hai hoặc ba module
như `log4j-slf4j-impl`, `log4j-slf4j18-impl`, `log4j-to-slf4j`. Stage OS không
phân biệt module, nên không chọn tùy ý một file. 43/43 failing records trong
mẫu có mapping declared revision. Đây là số failing records theo stage,
không phải 43 lỗi phần mềm độc lập.

Coverage trên mẫu đủ hỗ trợ tiếp tục xây adapter; **chưa giải quyết triệt để
source identity**. Matched nghĩa là Java path/package/outer declaration tại
SHA đã khai báo, không là bằng chứng code đó thực sự chạy sau merge trong CI.
Fallback vẫn giữ test/failure, đóng góp source-based signal bằng 0 theo contract
từng method. Không tạo source giả từ tên test.

Bằng chứng:
[ActiveMQ source summary](../../reports/stage4/activemq/source-summary.json),
[Log4j source summary](../../reports/stage4/log4j/source-summary.json),
[ActiveMQ dependency/config](../../reports/stage4/activemq/source-config-evidence.json),
[Log4j config](../../reports/stage4/log4j/source-config-evidence.json).

## 4. Split mới và bảo vệ phần xác nhận

Không dùng mốc năm của Karaf cho hai dự án khác: Log4j kết thúc tháng 1/2022,
còn ActiveMQ có phần lớn dữ liệu năm 2023–2024. Quy tắc mới dùng physical
chronology 20% warm-up, tới 50% development, phần sau reserved; ties giữ cùng
split. Quy tắc không dùng score, failure hoặc source coverage.

| Project | Warm-up physical | Development physical | Reserved physical | Reserved eligible physical có failure |
|---|---:|---:|---:|---:|
| ActiveMQ | 90 | 133 | 223 | 83 |
| Log4j | 54 | 81 | 135 | 59 |

Số failure được đếm sau khi chốt split để báo khả năng đánh giá; không dời
boundary để tăng số failure. Có 2/3 PR lần lượt ActiveMQ/Log4j qua boundary,
không có SHA qua boundary. Không gọi thiết kế này là unseen-PR evaluation.

Reserved đã được audit dữ liệu/history readiness, **chưa tính method ranking
hoặc APFD/APFDc/TTFF**. Karaf chỉ dùng exploratory vì đã xem score. Vì thế có
ba dự án pilot nhưng chỉ hai dự án có tail chưa xem method score. Muốn xác
nhận độc lập trên ba dự án cần thêm dữ liệu; không chia lại Karaf đã xem rồi
gọi là holdout mới.

## 5. Quyết định phương pháp cần chú ý khi review

1. **Primary là HC-FALCON-N v1**, chuẩn hóa modular q thành q/sum(q). Công thức
   nguyên bản `topic1.md` được giữ thành đối chứng bắt buộc topic-raw. Đây là
   thay đổi thiết kế có nhãn riêng, không được báo là công thức cũ không đổi.
2. Chọn alpha=.5 cố định; sensitivity 0/.25/.5/.75/1. Không tune theo score
   reserved. Kiểm tra scale chỉ dùng development Karaf: Q median2,271,
   max43,640 so với upper bound semantic1; chưa có bằng chứng normalization
   giúp hiệu quả.
3. UniXcoder revision đã pin, masked pooling, chunk input dài tối đa16 chunk,
   cosine clip[0,1], cache theo source/model/preprocessing. Đây là adaptation
   class-level, khác artifact FALCON nguyên bản; phải báo truncation.
4. Full inventory, source mask và history cố định trong ranking. Standard
   greedy là tham chiếu cho lazy; theorem chỉ cho cardinality objective, không
   bảo đảm APFDc hoặc ngân sách thời gian.
5. Protocol định nghĩa cả Borda rank fusion, FAST-pw adaptation và DANTE-CCH
   adaptation để tránh so với baseline yếu hoặc dùng nhầm duration hiện tại.
   Các ports này chưa được triển khai ở stage4.

Đã có config JSON cho method/evaluation. Cần phân biệt **design frozen** với
**implementation frozen**: giai đoạn5 còn phải pin dependency, cài đặt và vượt
kiểm thử trước khi mở phần confirmation.

## 6. Kiểm chứng và bàn giao

**25 unit tests đã đạt**, gồm test mới cho physical/stage split, timestamp ties,
split không phụ thuộc outcome và source declaration matcher. Verifier đã đạt:

- Đối chiếu 974 build-stage rows với raw CSV và split đã chốt.
- Kiểm tra 138.881 quan hệ history hợp lệ và cold-test counts.
- Giữ đủ 35.045 source annotations trong hai mẫu; đối chiếu lại 34.235 lượt
  matched với nội dung Git blob tại SHA metadata và source hash.
- Kiểm tra config, normalization bounds, source/config evidence và liên kết
  tài liệu; code/protocol stage3 không thay đổi.

Bằng chứng cuối: [verification.json](../../reports/stage4/verification.json),
[design-freeze.json](../../reports/stage4/design-freeze.json). Không có ranking
HC nào được tính trong mốc này; confirmation_opened=false. Thiết kế đã được
đóng băng bằng checksum, phần source thực thi CI vẫn ghi verified=false.

[Related work](related-work.md) ghi đối chiếu có mục tiêu với FAST, nghiên cứu
diversification/fault-proneness và approach combinators. Chưa coi đây là systematic
review hoặc bằng chứng novelty; không tuyên bố là phương pháp đầu tiên kết hợp
history với diversity.

## 7. Công việc tiếp theo đã có đầu vào cụ thể

Giai đoạn5: hoàn thiện source mapping warm-up/development ba dự án; triển khai
semantic/cache và standard greedy; thêm lazy greedy và kiểm tra tương đương;
port baseline/ablation theo contract; khóa môi trường và kiểm tra leakage. Sau
khi qua gate kỹ thuật mới chạy pilot development ở giai đoạn6. Reserved vẫn
đóng tới khi implementation/config và toàn bộ kiểm tra cần thiết đã chốt.
