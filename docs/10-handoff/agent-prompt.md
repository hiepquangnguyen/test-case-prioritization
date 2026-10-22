# Prompt giao việc cho agent khác

Thay phần trong ngoặc vuông trước khi gửi. Gửi cùng quyền truy cập repository;
chỉ gửi prompt mà không có repo/evidence thì agent không thể xác minh trạng thái.

## Mẫu 1 — yêu cầu đọc và kiểm tra kế hoạch, chưa triển khai

```text
Đọc docs/10-handoff/README.md và docs/10-handoff/tasks.json trong repository này.
Sau đó đọc evidence được tham chiếu cho phạm vi [T00–T03 / toàn phase R].

Nhiệm vụ hiện tại chỉ là review kế hoạch. Không tạo/sửa file, không chạy encoder,
ranking, cài dependency hoặc khởi động worker.
Hãy báo: trạng thái nào xác minh được; mâu thuẫn/thiếu đầu vào; dependency;
những quyết định cần làm rõ; thứ tự triển khai và điều kiện nghiệm thu.
Không gọi planned outputs là file đã có hoặc số liệu dự kiến là kết quả.
Nếu không truy cập được repo, nói rõ không thể xác minh, không đoán nội dung.
```

## Mẫu 2 — giao một nhóm task cụ thể

```text
Triển khai [T00–T03] theo docs/10-handoff/README.md và tasks.json.
Chỉ phạm vi này được giao; chưa chạy full-suite T04 trở đi, phase W hoặc C00.

Trước khi làm, kiểm tra trạng thái thực tế và dependency; task hoàn tất có
evidence thì xác minh và tái dùng, không chạy lại để ghi đè. File trong freeze
cũ phải giữ nguyên. Chỉ ghi đầu ra mới của các task được giao.

Tiếp tục tự chủ trong phạm vi đã giao cho tới khi đủ tiêu chí nghiệm thu hoặc
có blocker cụ thể. Báo bằng tiếng Việt: việc đã làm, file đầu ra, commands và
exit codes kiểm tra, kết quả/giới hạn, task kế tiếp. Không báo hoàn tất khi chỉ
mới có code, worker đang chạy hoặc output chưa được validate.
```

## Mẫu 3 — giao toàn bộ phase tái lập và bridge

```text
Triển khai toàn phase R (T00–T09) trong docs/10-handoff/tasks.json, theo hợp đồng
docs/10-handoff/README.md. Không triển khai phase W hoặc confirmation C00.
Áp dụng giới hạn vận hành 8 GiB peak RSS và 8 giờ wall-clock mỗi project, một
worker thí nghiệm tại một thời điểm. Nếu vượt, giữ checkpoint và báo blocker;
không đổi thuật toán hoặc bỏ project để gọi phase hoàn tất.

Đọc evidence và kiểm tra process/manifest trước khi bắt đầu hoặc resume.
Khóa config/runner trước kết quả mới. Giữ nguyên các freeze và các kết quả âm
LRTS. Full Chart stage1 đã có, hãy xác minh cache/provenance trước khi tái dùng.
Không chạy writer cũ làm ghi đè report stage1–9.

Đầu ra bắt buộc: sáu project rerun với metric độc lập, Chart A/B/C/D với manifest
riêng, bảng runtime đúng phạm vi, báo cáo sai lệch với artifact, closeout audit
và evidence freeze. Không thay tham số theo score. Không suy 288 fault IDs là
288 CI builds. Không dùng kết quả Defects4J để tuyên bố HC-FALCON thắng LRTS.

Không dừng sau một project rồi gọi phase hoàn tất. Nếu task đã hoàn thành,
xác minh và chuyển task tiếp theo, không xin lại quyền cho bước đã được giao.
Khi có blocker, báo task ID, action lỗi, evidence, phần đã giữ được và thông tin
thực sự cần bổ sung. Không bịa số hoặc cam kết worker nền còn chạy nếu chưa kiểm tra.
```

## Mẫu 4 — tiếp tục một run đang dở

```text
Tiếp tục phase/task đã được giao: [ghi phạm vi]. Đọc docs/10-handoff/README.md,
tasks.json và reports/stage10/task-status.json nếu đã tồn tại.
Kiểm tra worker thật, log, checkpoint và manifest trước khi launch.
Không coi PID cũ hoặc status running là bằng chứng tiến trình còn sống.
Không chạy trùng worker, không thay cấu hình giữa các checkpoint. Hoàn thành
phần còn thiếu trong phạm vi này và xác minh output trước khi báo kết quả.
```

## Cách người dùng kiểm tra agent có bám nhiệm vụ

Yêu cầu agent luôn nêu task ID đang làm và evidence đầu ra. Các dấu hiệu cần
dừng để kiểm tra: nói Defects4J chưa từng chạy; đòi đổi alpha/model để đạt;
gộp fault IDs thành build độc lập; sửa README/frozen report; chạy script stage1
ghi đè cache; báo runtime cache-hit là cold; gọi FL-only adaptation là FALCON
nguyên bản; hoặc kết luận confirmation chỉ từ kết quả development.

Một prompt không bảo đảm agent không sai. Bảo vệ thực tế là scope rõ, hash
manifest, validator độc lập, checkpoint, task ledger và kiểm tra claim bằng file.
