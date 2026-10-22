# Tái lập giai đoạn 5

Chạy từ root bằng PowerShell, dùng môi trường falcon đã có.
Dependencies được ghi ở `reports/stage5/environment.txt`; encoder tải từ cache
local, revision trong `configs/hc-falcon-v1.json`. Không cần chạy Java upstream.

```powershell
$env:PYTHONHASHSEED='0'
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_sources.py --project karaf
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_sources.py --project activemq
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_sources.py --project log4j
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_fast_verify.py
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_smoke.py
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_technical.py --project karaf
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_technical.py --project activemq
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_technical.py --project log4j
& work/envs/falcon/Scripts/python.exe -B scripts/stage5_verify.py
```

Nếu chưa có commit local, thêm `--fetch` cho source runner; chỉ tải endpoint của
warm-up/development đã khóa. Cần quyền mạng. Nếu audit diff báo thiếu promisor
object, `stage5_repair_diffs.py --project <project>` xác minh object là Java blob
thuộc endpoint được phép trước khi tải; sau đó chạy lại technical runner.

`source-request.json` ghi commit được phép; `source-mapping.jsonl.gz` chứa từng
record; `diff-audit.jsonl` chứa trạng thái từng build. Source/vector/kernel/diff
cache nằm ở `work/cache/stage5/`. Runner báo runtime và cache-hit của chính lần
chạy, do đó các trường thời gian/cache-hit có thể thay đổi khi tái lập.

`implementation-freeze.json` là hash của code, dependencies và bằng chứng tại
lần khóa. Không tự cập nhật freeze sau một thay đổi phương pháp; cần ghi rõ
phiên bản mới trước khi pilot hoặc so sánh.
