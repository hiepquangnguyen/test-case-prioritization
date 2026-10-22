# Tái lập pilot baseline Karaf

Dùng Python 3.10+ và Git đã có, chạy từ thư mục gốc. Chỉ đọc artifact và source
cục bộ; không tải model, cài package hoặc thực thi Java/Jenkinsfile.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/stage3_prepare.py
python -X utf8 -B scripts/stage3_run.py
python -X utf8 -B scripts/stage3_verify.py
```

`prepare` xác minh ZIP 3,6 GB và đóng băng manifest/split trước scoring. Sau đó
đọc 726 class CSV để audit, rà source và cấu hình tại 18 commit cục bộ. Nó không
fetch object thiếu. Có thể chạy lại prepare với cùng code/protocol; nếu checksum
thay đổi thì dừng, cần phiên bản thí nghiệm riêng. Không chỉnh manifest cũ để
làm verifier chấp nhận code mới.

`run` kiểm tra manifest, chạy snapshot theo thời gian, lưu 25 ranking/build
(20 Random seed + 5 deterministic). Warm-up vẫn có ranking chẩn đoán nhưng
metric chính rỗng. ABORTED bị loại khỏi scoring/history, không xóa khỏi ledger.
Runner từ chối ghi đè lượt đã có `run-complete.json`; sau khi đã chạy xong dùng
verifier để tái lập. Có thể chạy lại runner nếu lượt trước bị gián đoạn và chưa
có completion marker; các file streaming chưa hoàn tất sẽ được tạo lại.

`verify` kiểm tra checksum, tái dựng từ input/ground truth, so feature/ranking/
metric/CSV/summary. Mutation checks nạp cả dữ liệu tương lai vào history store
để kiểm tra chính snapshot từ chối dữ liệu đó. Các cutoff kiểm tra gồm 20 build
đầu, ranh giới split, build cuối và các build chồng lấn cùng context. Phân tích
History+cost chỉ đọc technical20/development; không dùng holdout để chẩn đoán
hoặc chọn công thức. Dùng lệnh Python bình thường, không dùng `-O` vì verifier
có assertions.

## Các file để review

Tất cả nằm trong `reports/stage3/karaf/`:

| File | Nội dung |
|---|---|
| `manifest.json`, `selection.json` | Config/checksum và split cố định, trước scoring. |
| `environment.json` | Python/platform của lượt chạy đã thực hiện, ghi bổ sung sau replay và gắn hash manifest. |
| `data-audit.json`, `audit-summary.json` | Counts/durations, timestamp/inventory evidence, overlap, commit availability và identity overlap qua split. |
| `source-review.json`, `source-evidence/` | Các issue theo commit/test, candidate và cấu hình build có số dòng/hash. |
| `inputs.jsonl.gz`, `ground-truth.jsonl.gz` | Input tách khỏi outcome/duration sau chạy. |
| `features.jsonl.gz` | Compact snapshot; evidence từng test lưu hash, có thể tái dựng từ eligible build keys và ground truth. |
| `rankings.jsonl.gz`, `metrics.csv` | Ranking đầy đủ, metric theo build/method/seed, reason/NA và timing. |
| `ledger.json`, `summary.json` | Eligibility/cold-start, số mẫu metric xác định, censoring, tổng hợp theo build. |
| `history-cost-paired.json` | Chênh lệch APFDc/TTFF/recall và vị trí từng failure trên technical20/development. |
| `development-runtime-errors.jsonl.gz` | Runtime estimate so với actual theo test và nhóm history, gồm technical20/development. |
| `history-cost-summary.json` | Tổng hợp chẩn đoán, không gồm holdout. |
| `run-complete.json`, `verification.json` | Checksum artifact hoàn tất và kết quả tái lập/mutation checks. |

JSONL được gzip để tránh lặp nhiều tên test/evidence trên đĩa. Có thể đọc bằng
`gzip.open(path, 'rt', encoding='utf-8')`; mỗi dòng là một JSON record.
Đọc [protocol v2](protocol-v2.md) trước diễn giải số liệu. Đây là replay baseline
trên class đã quan sát; không phải kết quả HC-FALCON hoặc Defects4J.
