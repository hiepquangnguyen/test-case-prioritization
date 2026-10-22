# Restricted semantic/cost v1

Phiên bản development sau chẩn đoán giai đoạn 7. Các hệ số cố định trước replay:
q_fraction=0,95; duration_multiplier=1,25; duration_floor=1e-6 giây.
Không quét tham số. Giữ nguyên toàn bộ file thuộc freeze giai đoạn 6 và 7.

## Quy tắc triển khai

Tại mỗi bước, b là test còn lại đứng đầu raw history_cost_score giảm dần,
FQN tăng dần. Nhóm ứng viên có q≥0,95q(b) và c≤1,25c(b), trong đó c chỉ là
duration_estimate từ snapshot lịch sử và được floor ở 1e-6. b luôn hợp lệ.

Chọn ứng viên có tổng semantic marginal gain / c cao nhất. Khi hòa, chọn raw q
cao hơn rồi FQN nhỏ hơn. Nếu mọi semantic marginal gain trong nhóm đều bằng 0,
chọn b. Khi q(b)=0, ràng buộc q cho phép mọi test còn lại; cost cap vẫn áp dụng.
Coverage cập nhật bằng maximum sau mỗi lựa chọn. Kernel float32, tổng gain và
coverage float64; so sánh hòa chính xác, không thêm tolerance để sửa ranking.
Chế độ history_only bỏ qua kernel và trả baseline raw q/FQN chính xác.

Dùng standard greedy, chưa triển khai lazy. Không kế thừa bảo đảm xấp xỉ của
objective HC-N cũ. Giới hạn q/cost theo bước không bảo đảm APFDc/TTFF toàn suite.
Module mới: `hc_falcon/restricted.py`; cấu hình: `configs/restricted-semantic-v1.json`.
Các hằng số nằm cố định trong code và cấu hình, cùng được hash trong manifest;
thay bất kỳ file nào cần run version mới, không ghép checkpoint khác phiên bản.

## Phạm vi và khả năng tái lập

Runner kiểm tra hash toàn bộ bằng chứng giai đoạn 6 và 7, load đúng prefix
warmup/development, dựng lại history theo thứ tự và cutoff cũ. Mọi vector được
đối chiếu SHA256 với source evidence của stage 6; vector cache chỉ là cách tái sử
dụng encoder đã khóa, không huấn luyện hoặc chọn model bằng dữ liệu tương lai.
Không đọc reserved. Không thay đổi ground truth, source mapping hoặc inventory.

Mỗi stage development: đối chiếu history eligible keys và baseline raw q với
checkpoint cũ; kiểm tra full permutation và APFD/APFDc bằng công thức độc lập;
lưu features q/c/N, trace từng bước, metric và history groups. Đầu/cuối mỗi dự án
còn đảo labels và đổi duration của mọi build không đủ điều kiện trong cohort,
đối chiếu snapshot và ranking không đổi. Đây là sáu mutation checks thực tế.

PowerShell, tại thư mục dự án:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
& work/envs/falcon/Scripts/python.exe -B -m unittest tests.test_stage8
& work/envs/falcon/Scripts/python.exe -B scripts/stage8_pilot.py
& work/envs/falcon/Scripts/python.exe -B scripts/stage8_summary.py
& work/envs/falcon/Scripts/python.exe -B scripts/stage8_report.py
```

Checkpoint được ghi atomic tại `reports/stage8/<project>/builds/`. Resume chỉ
chấp nhận manifest giống hệt. Không chạy đồng thời hai runner. Resume giữ timing
đã đo trong checkpoint cũ; trạng thái cache trong bộ nhớ có thể khác sau resume.

## Nhánh cache-only riêng

`cache_only_restricted_v1_simulated` mô phỏng cache theo source hash: warmup usable
nạp cache; tại đầu mỗi stage, nếu source matched có hash chưa xuất hiện ở stage
usable trước thì cả stage fallback về History+cost. Nếu đủ cache, dùng ranking
restricted mới. Sau stage usable, các hash đó được coi là đã chuẩn bị cho stage
sau. Missing/ambiguous source giữ zero mask như cũ; không loại khỏi inventory.

Mô phỏng này giả định chuẩn bị vector xong trước stage kế tiếp theo thứ tự
offline. Nó không mô phỏng lịch async/concurrency hoặc completion của job encoding
trong CI. Báo metric trên mọi stage, gồm fallback; không báo runtime deployment
hoặc gọi đây là full-pipeline engineering gate. Policy có tên riêng trong evidence
và cùng manifest chứa mô tả cố định; không trộn metric policy với thuật toán đầy đủ.

## Runtime và tiêu chí quyết định

Runtime đo history snapshot, đọc/hash vector (cache trong bộ nhớ dùng chung trong
lượt chạy), tạo kernel và ranking. Không gồm trích source, preprocessing, encoding,
download hoặc CI setup. Peak RSS là mức cao nhất trong các checkpoint process.
Gộp stage ratio theo physical build rồi lấy p95; đây là chẩn đoán cached replay.
Gate engineering full pipeline chưa được đo lại cho phiên bản mới.

Hiệu quả vẫn xét median paired ΔAPFDc≥0,03 so với cả FL-only và History+cost ở
ít nhất hai trong ba dự án. Nếu đạt hiệu quả, còn phải đánh giá engineering đầy
đủ và review trước confirmation. Nếu không đạt, báo no-go; không mở reserved hay
tự động chạy thêm tham số. Nhóm N và recall pooled chỉ là thống kê quan sát,
không phải các mẫu test độc lập. Karaf exploratory, cả lượt mới là development
được sử dụng sau khi đã xem chẩn đoán giai đoạn 6.
