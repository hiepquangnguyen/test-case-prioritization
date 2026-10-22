# Protocol v2 — pilot baseline Karaf

Chốt ngày 2026-09-13 trước khi chạy score mở rộng. Kế thừa công thức, identity,
full feedback và chính sách NA của [v1](../02-protocol/protocol-v1.md).
Không tune hằng số hoặc thay công thức History+cost trong mốc này.

## Dữ liệu và thời gian

Dùng toàn bộ 726 metadata rows Karaf trong ZIP đã pin. Adapter phải đọc được
mọi raw class CSV; thiếu file, duplicate key/ID hoặc timestamp không hợp lệ là
lỗi dừng, không tự loại hàng. Giữ ABORTED trong ledger/ranking chẩn đoán, loại
khỏi history và score chính. Không lọc theo failure hoặc source coverage.

Inventory là các class quan sát trong dữ liệu upstream đã xử lý, không phải
toàn bộ test dự định trước chạy: extractor loại SKIPPED, loại một số tên,
deduplicate method rồi gộp theo FQN. FQN trùng module có thể đã mất identity.
Không khôi phục được skipped/unreported tests từ class CSV. Do đó đây chỉ là
retrospective replay có điều kiện trên inventory quan sát; không tuyên bố CI
prospective hoặc full intended suite. Failure là failing record, không unique fault.

Collector dùng int(timestamp_ms/1000) và int(duration_ms/1000). V2 dùng
`available_at = timestamp + duration + 2 seconds`, chỉ nhận khi `< cutoff`.
Hai giây bù việc làm tròn xuống hai đại lượng; không bù độ trễ publish log.
Ý nghĩa timestamp là start, duration là elapsed vẫn là giả định từ collector,
chưa xác minh từng build bằng raw Jenkins JSON. Nhánh/stage giữ nguyên v1.

## Cohort/split cố định theo lịch UTC

Kiểm kê metadata cho thấy dữ liệu từ tháng 12/2020 đến tháng 4/2024. Chọn ranh
giới năm để không chia theo outcome, score hay thứ tự PR; cùng timestamp không
bị tách. Cấu hình này được đóng băng trước tính score mở rộng:

- Warm-up: cutoff trước 2022-01-01 UTC; có 246 rows, gồm 20 rows đã xem.
  Những rows đã xem chỉ là technical history, không vào score development/holdout.
- Development: 2022-01-01 đến trước 2023-01-01 UTC; 317 rows.
- Holdout baseline: từ 2023-01-01 UTC trở đi; 163 rows.

Warm-up không bảo đảm mọi branch/test có history. Công bố cold-start theo split.
Build trước ranh giới nhưng chưa hoàn tất vẫn phải đợi availability. History
được cập nhật tuần tự trong holdout; không cập nhật tham số phương pháp.
Không điều chỉnh split sau khi đếm failure; thiếu mẫu được báo là thiếu mẫu.
Các PR/commit có thể lặp qua split: setting là temporal CI replay, không phải
đánh giá unseen PR/project. Báo số lượng overlap, không âm thầm lọc chúng.

Sáu baseline v1. Random dùng 20 seed 0..19; các phương pháp deterministic chạy
một lần. Không coi 20 seed trên cùng build là 20 build độc lập. Tổng hợp Random
bằng mean metric theo build trước, rồi median giữa build. Báo thêm median theo
seed để thể hiện biến thiên. Các metric NA giữ NA; TTFF censor báo riêng.

## Source và semantic fallback đã chốt cho lần tích hợp tới

Mốc này rà source tại 18 SHA đã có cho 20 build kỹ thuật, không tải toàn bộ
source 726 build. Build còn lại có source_status unverified; baseline không
dùng source. Chỉ matched khi exact declaration và identity có bằng chứng.
Ambiguous module không chọn theo thứ tự file. Không dùng source ở commit khác
để thay source của commit hiện tại; candidate chỉ là bằng chứng điều tra.

Fallback giữ đủ inventory: semantic kernel của record thiếu/ambiguous source
có similarity 0 với mọi record, kể cả chính nó; không sinh embedding giả.
Chỉ record có source hợp lệ thuộc semantic coverage universe; objective ghi
rõ universe này. History/cost vẫn tính cho mọi record. Pure semantic dùng
FQN tie-break khi gain bằng 0; hybrid dùng công thức history/cost đã chốt của
phương pháp. Không thêm implicit history vào baseline pure semantic. Cùng
mask/kernel cho mọi semantic adaptation; giữ full inventory ở evaluator.
Phải báo source coverage và kết quả theo nhóm source, không đổi denominator.
Đây là đặc tả, chưa triển khai semantic ranker. DANTE có cấu trúc khác phải
ghi rõ adapter áp dụng mask này trước khi so sánh, không gọi là tái lập nguyên bản.

JUnit4Provider tiếp tục được gắn suspected_runner_event và giữ trong dữ liệu.
Chỉ raw stack trace/report mới đủ để phân loại nguyên nhân cụ thể. Không tạo
FQN giả theo module khi class-level artifact không cung cấp mapping tương ứng.

## Phân tích và giới hạn diễn giải

Chẩn đoán History+cost dùng 20 technical rows và development, tuyệt đối không
dùng holdout để chọn công thức. So từng build APFDc/TTFF/recall, vị trí failure,
runtime estimate và actual duration (actual chỉ thuộc phân tích sau ranking).
Nhóm history theo N=0, 1..4, >=5; đây là ngưỡng mô tả, không tham số ranker.

Lượt này đánh giá baseline trên holdout đã chốt. Kết quả đó có thể được xem nên
không còn là holdout chưa từng quan sát cho phát triển HC-FALCON. Trước tuyên
bố hiệu quả HC-FALCON cần preregister phương pháp và tập xác nhận mới, hoặc
ghi rõ đánh giá trên split này là exploratory. Không có p-value/claim superiority.
Defects4J giữ riêng đơn vị fault; không ghép với failing records LRTS.

Timing feature/ranking đo riêng; execution TTFF không phải wall-clock CI.
Evidence checksum, split, inputs, ground truth, compact features (hash evidence
per test), rankings và metric được lưu. Verifier tái dựng evidence từ input/GT,
kiểm tra hash/full permutation/cutoff và mutation current/future trên các cutoff
đại diện gồm ranh giới split và overlap. Dữ liệu stage1/stage2 giữ nguyên.
