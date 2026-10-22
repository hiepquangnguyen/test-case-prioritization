# Tái lập protocol v1

Chạy từ thư mục gốc, dùng Python 3.10+ và standard library. Không cần pip,
Docker, GPU, mạng hoặc tải lại encoder.

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B scripts/stage2_run.py
python -X utf8 -B scripts/stage2_verify.py
```

Runner mặc định đọc ZIP DANTE và kiểm tra MD5, chọn 20 build-stage Karaf đầu,
đọc source annotations của giai đoạn 1. Output ở `reports/stage2/karaf20/`.
Thời gian chạy phụ thuộc đọc/hash ZIP 3,6 GB; không chạy embedding.

Unit tests dùng dữ liệu tổng hợp và ZIP giả nhỏ, kiểm tra công thức tính tay,
đổi đơn vị, missing/zero duration, no-failure, unknown, cutoff, context isolation,
negative control khi history quá khứ thay đổi và các phép thay current/future data.

Integration verifier tái dựng replay từ input/ground truth đã lưu, so toàn bộ
snapshot/ranking/metric và thay outcome, duration, status, thời điểm hoàn tất
của current/future builds tại từng cutoff. Giữ inventory cố định vì log hiện
không cung cấp pre-build inventory độc lập. Đây là kiểm chứng implementation,
không chứng minh rằng nguồn dataset không có selection bias.

## Đầu ra

| File | Dùng để review |
|---|---|
| `manifest.json` | Config, checksum code/protocol/ZIP, giả định và quy tắc chọn mẫu. |
| `selection.json` | Metadata của toàn bộ cohort đã chọn. |
| `inputs.jsonl` | Inventory/source annotations, không có outcome hay actual duration. |
| `features.jsonl` | Snapshot theo build, evidence keys, p/conf/c/r/q và nguồn fallback runtime. |
| `ground-truth.jsonl` | Quan sát sau chạy, tách khỏi ranker. |
| `rankings.jsonl` | Ranking đầy đủ theo phương pháp, snapshot hash, timing và metric. |
| `ledger.json` | Mọi build, trạng thái, lý do không chấm, số history/test cold-start. |
| `metrics.csv` | Metric từng build/phương pháp; ô trống là NA có reason. |
| `summary.json` | Tổng hợp chẩn đoán; không có p-value hoặc chọn tham số tốt nhất. |
| `verification.json` | Kết quả integration/mutation checks. |

Có thể thay `--seed`, `--limit`, `--project`, `--output` ở runner. Output phải
nằm trong `reports/stage2/`; nên dùng thư mục riêng cho mỗi cấu hình để không
ghi đè kết quả review trước. Ví dụ `--output reports/stage2/karaf20-seed7 --seed 7`.
Verifier hiện dành cho cohort Karaf20 mặc định; `--output` chỉ chọn thư mục
kết quả của cùng cohort, không phải verifier tổng quát mọi project/limit.

Nếu thay code hoặc protocol, chạy lại runner rồi verifier; verifier dừng nếu
checksum không khớp. Không tự chạy lại stage1 audit/model vốn tốn thời gian.
