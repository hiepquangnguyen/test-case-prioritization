# Tái lập audit và design freeze giai đoạn 4

Chạy từ root, Python 3.10+ và Git. Không cần model/GPU/package mới để audit.

**Với kết quả đã bàn giao có design-freeze.json, chỉ chạy verifier để kiểm tra
lại:** `python -X utf8 -B scripts/stage4_verify.py`. Các lệnh đầy đủ bên dưới
dành cho lượt sinh bằng chứng đầu tiên trong workspace/kết quả chưa đóng băng;
không chạy lại audit để ghi đè bộ bằng chứng đang review.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/stage4_design_audit.py
python -X utf8 -B scripts/stage4_source_audit.py --fetch
python -X utf8 -B scripts/stage4_scale_check.py
python -X utf8 -B scripts/stage4_verify.py
```

`--fetch` cần mạng lần đầu, chỉ fetch các SHA thuộc first 20 physical warm-up
builds mỗi project, depth1/blob limit1MiB; không checkout, build hoặc chạy test
upstream. Lượt đã thực hiện lấy 19 SHA ActiveMQ và 20 SHA Log4j. Khi source đã
có, chạy `stage4_source_audit.py` **không có --fetch** để audit offline. Git lazy
fetch bị tắt khi đọc blob; object thiếu được ghi là unavailable, không ngầm tải.

`design_audit` kiểm tra ZIP rồi đọc toàn bộ 446/528 class CSV, kiểm tra history
eligibility và chốt split trước khi đọc class outcomes. Nó tính thống kê dữ
liệu/history readiness nhưng không sinh ranking/metric phương pháp. Script
có thể mất vài phút do tạo history cho từng cutoff.

`scale_check` chỉ dùng feature development Karaf đã được xem ở stage3; không
mở score reserved ActiveMQ/Log4j. `verify` kiểm tra artifact, split, mapping
source tại blob đã pin, history evidence và config/doc links. Không dùng
Python `-O` vì verifier có assertions. `design-freeze.json` lưu hash thiết kế,
script và bằng chứng. Rerun verifier chỉ chấp nhận đúng các hash đã đóng băng;
thay thiết kế phải tạo phiên bản mới, không chỉnh checksum cũ để qua kiểm tra.

Audit scripts tái tạo nội dung dữ liệu, nhưng gzip header và timestamp audit/
fetch có thể thay đổi giữa lượt; không cam kết byte-identical file nén. Freeze
kiểm tra checksum đúng bộ file đã bàn giao, vì vậy tái sinh file nén vào thư
mục đã freeze có thể làm verifier từ chối dù dữ liệu giải nén tương đương.
Giữ bộ cũ, dùng một workspace/kết quả phiên bản mới nếu cần tái sinh toàn bộ.
Selection đã tồn tại nhưng khác quy tắc mới gây lỗi dừng.

## Các đầu ra

| Đường dẫn | Nội dung |
|---|---|
| `reports/stage4/{project}/selection.json` | Full cohort, split, source sample; project là activemq/log4j. |
| `build-audit.json`, `summary.json` | Count/duration/status, chronology, history readiness, physical-stage structure. |
| `history-readiness.jsonl.gz` | Danh sách evidence hợp lệ theo cutoff để kiểm tra lại. |
| `source-mapping.csv`, `source-summary.json` | Source statuses theo test/commit, coverage và giới hạn mẫu. |
| `source-config-evidence.json`, `source-evidence/` | Jenkins/Maven/dependency evidence tại các SHA đã pin. |
| `source-fetch.json` | Remote, danh sách SHA và kết quả fetch. |
| `reports/stage4/objective-scale.json` | Kiểm tra Q và normalization trên development Karaf. |
| `configs/hc-falcon-v1.json`, `configs/evaluation-v1.json` | Quyết định phương pháp và đánh giá; chưa có implementation HC. |
| `reports/stage4/design-freeze.json`, `verification.json` | Hash thiết kế/bằng chứng và kết quả kiểm tra. |

Ba tài liệu để review là [báo cáo khả thi](implementation-report.md),
[đặc tả phương pháp](hc-falcon-v1.md) và [protocol đánh giá](evaluation-protocol.md).
