# Tái lập giai đoạn 1

Lệnh dưới đây chạy từ thư mục gốc trên PowerShell. Cần hai ZIP đúng checksum
trong manifest. `python` dùng Python 3.12; hai môi trường riêng lưu trong `work/`.
Không cần Docker, WSL hay checkout đầy đủ Defects4J cho các kiểm tra này.

## 1. Audit dữ liệu, trích xuất chọn lọc

```powershell
python -X utf8 -B scripts/stage1_audit.py --extract
```

Đọc toàn bộ metadata và raw `test_class.csv.zip` mà metadata LRTS tham chiếu;
đọc 50 JSON processed. Audit không chạy code từ ZIP. Pickle dữ liệu FALCON
được đọc bằng unpickler không cho phép khởi tạo class tùy ý.

Trích xuất code, dữ liệu FALCON, metadata DANTE, processed JSON và raw log cho
ActiveMQ/Karaf/Log4j. Nếu file trích xuất đã tồn tại nhưng khác upstream, dừng
thay vì ghi đè. Kết quả tác giả vẫn đọc trong ZIP. Một số raw stage của các
dự án khác không có tên hợp lệ trên Windows, nên audit đọc trực tiếp từ ZIP.

## 2. Môi trường

```powershell
python -m venv work/envs/falcon
python -m venv work/envs/dante
& work/envs/falcon/Scripts/python.exe -m pip install -r reports/stage1/falcon-environment.txt
& work/envs/dante/Scripts/python.exe -m pip install -r reports/stage1/dante-environment.txt
& work/envs/falcon/Scripts/python.exe -m pip check
& work/envs/dante/Scripts/python.exe -m pip check
```

Các lock là kết quả `pip freeze` sau khi cài requirements upstream và kiểm tra
thành công, không phải lock gốc của tác giả. DANTE README ghi Python 3.8+,
nhưng `src/pyproject.toml` ghi >=3.10. Smoke dùng root `requirements.txt`,
không cài các solver QUBO không thuộc prioritization. Không suy ra rằng toàn
bộ pipeline selection/ML đã được kiểm thử từ smoke này.

## 3. Source mapping Karaf

Chỉ cần clone lần đầu:

```powershell
git clone --bare --filter=blob:none --single-branch --depth=1 https://github.com/apache/karaf.git work/sources/karaf.git
python -X utf8 -B scripts/stage1_source_mapping.py --fetch
```

Script lấy 20 metadata row đầu theo timestamp, PR, build, stage, không xem
outcome để chọn. Fetch 18 commit cùng các blob nhỏ để kiểm tra source. Lần
sau dùng `python -X utf8 -B scripts/stage1_source_mapping.py` để đọc dữ liệu
cục bộ. Không checkout hay chạy Java. Mapping dựa trên package/class path
và kiểm tra khai báo; trường hợp nhiều module cùng FQN giữ là ambiguous.

```powershell
python -X utf8 -B scripts/stage1_crosschecks.py
```

Đối chiếu source trích xuất với bbox, CSV fault với pickle, raw/current JSON
DANTE và history lag. Chênh lệch lag không tự là bằng chứng nhìn tương lai:
artifact dùng danh sách processed build đã lọc, khác chuỗi raw metadata.

## 4. Smoke DANTE

```powershell
& work/envs/dante/Scripts/python.exe -X utf8 -B scripts/stage1_dante_smoke.py
```

Wrapper chọn processed build Karaf sớm nhất có raw history, đặt `tfidf` đúng
với JSON đầu vào, gọi nguyên `run_prioritization.main()`. Output nằm trong
`work/runs/dante/`; ranking và diagnostics xuất thêm vào `reports/stage1/`.
Output LTR do runner sinh ra trong fixture này dùng placeholder vì không
có training features và **không phải kết quả baseline LTR hợp lệ**.

## 5. Smoke FALCON

Lần đầu tải model (cần mạng), revision cố định trong `unixcoder-pin.json`:

```powershell
& work/envs/falcon/Scripts/python.exe -X utf8 -B scripts/stage1_falcon_smoke.py --download --limit 16
```

Lần sau không cần mạng:

```powershell
& work/envs/falcon/Scripts/python.exe -X utf8 -B scripts/stage1_falcon_smoke.py --limit 16
& work/envs/falcon/Scripts/python.exe -X utf8 -B scripts/stage1_falcon_smoke.py
```

Không có `--limit` là full Chart, 2.193 test. Bản 16 test kiểm tra standard vs
lazy greedy, không chấm APFD full-suite. Wrapper gọi nguyên hàm embedding và
FacilityLocation trong artifact trên CPU, batch 16, max length 512 và giữ
mean pooling upstream. Không dùng runner tự gọi `python3 --device cuda` hoặc
skip vì đã có output của tác giả. Không sửa upstream.

Model cache và embedding có khóa theo source hash/cấu hình; kết quả tự chạy
ở `work/runs/falcon/`. Encoder không được fine-tune. Phiên bản thư viện và CPU
có thể làm kết quả khác paper; báo cáo ghi rõ phạm vi của việc đối chiếu.

## 6. Tổng hợp

```powershell
python -X utf8 -B scripts/stage1_report.py
python -X utf8 -B scripts/stage1_verify.py
```

Report đọc bằng chứng có sẵn, không tự chạy lại model. Verification kiểm tra
những invariant cần thiết và xác nhận các vấn đề đã tìm được được giữ trong
báo cáo. Kết quả này không chứng minh HC-FALCON có hiệu quả hơn baseline.
