# Bàn giao cho AI agent — đọc trước khi thực hiện task

Bản bàn giao lập ngày 2026-09-15. Đây là kế hoạch và hợp đồng công việc, không
phải bằng chứng rằng các task tiếp theo đã chạy. Yêu cầu hiện tại của người dùng
chỉ là chuẩn bị bộ bàn giao; chưa khởi động tái lập sáu dự án hoặc Chart A/B/C/D.

## 1. Mục tiêu và cách bắt đầu

Workspace: `C:\Users\hiepq\Projects\test-case-prioritization`, PowerShell.
Đọc file này, [task board](tasks.json), [prompt giao việc](agent-prompt.md), rồi
đọc tài liệu đầu vào của task được người dùng chỉ định. Không bắt đầu bằng cách
chạy một script cũ chỉ vì tên có vẻ phù hợp.

Mục tiêu kế tiếp: tái chạy FALCON artifact trên sáu suite Defects4J đã pin và đo
riêng ảnh hưởng thay pipeline trên Chart. Mục tiêu không phải tìm tham số giúp
HC-FALCON thắng, sửa kết quả âm, hay chạy confirmation LRTS ngay.

Ưu tiên chỉ thị hiện tại của người dùng. Nếu người dùng giao một task, thực hiện
task đó cùng dependency cần thiết; nếu dependency chưa được phép chạy và có
khối lượng ngoài phạm vi, báo rõ phần thiếu. Khi đã được giao toàn bộ một phase,
tiếp tục các task trong phase, không hỏi lại từng bước đã được cho phép.
Các task conditional không tự được mở bởi câu “tiếp tục” khi điều kiện chưa đạt.

## 2. Trạng thái thực tế cần giữ đúng

| Phần | Đã hoàn thành | Chưa hoàn thành |
|---|---|---|
| Stage1 | Audit FALCON/DANTE, sáu fault matrices; kiểm tra 60 ranking tác giả; chạy full Chart | Chưa tự chạy đủ sáu project hoặc 288 checkout fault versions |
| Stage2–4 | TCP/history/metrics/baselines, Karaf replay, audit ActiveMQ/Log4j, split và thiết kế | Các tài liệu cũ có mô tả trạng thái tại thời điểm đó, không dùng như trạng thái mới nhất |
| Stage5 | HC-N/raw/FL/ablation/Borda, FAST/DANTE adaptations, source warmup/development | Không phải bản tái lập FALCON/DANTE nguyên gốc |
| Stage6 | 596 stage, 519 physical build, 33.972 ranking, effect gate 0/3 | Chưa xác nhận hiệu quả; reserved không có method scores |
| Stage7 | Chẩn đoán từng test lỗi và kế hoạch restricted | Không phải experiment mới |
| Stage8 | Restricted và policy cache-only mô phỏng; 596 checkpoint; effect gate 0/3 | Chưa có dịch vụ async/cache-only thực tế; chưa đo lại engineering đầy đủ |
| Stage9 | Audit fidelity, probe nhỏ, kế hoạch tiếp theo | Chưa chạy kế hoạch sáu project hoặc Chart A/B/C/D |

HC-N median paired ΔAPFDc so History+cost: Karaf −1,265; ActiveMQ −1,407;
Log4j −0,117 điểm phần trăm. Restricted tương ứng −0,017; −0,154; −0,001.
Đây là số làm tròn để định hướng; khi tạo bảng, đọc số chính xác từ JSON.

Chart stage1 đã chạy 2.193 methods, APFD 0,7322775263951734. Output tác giả
0,7263144971763303; không gọi chênh lệch này là cải tiến. Cold embedding đã đo
khoảng 1.532,54s; không lấy cache-hit timing làm cold timing.

Gate LRTS đã khóa: median paired ΔAPFDc≥0,03 so với cả FL-only và History+cost
ở ít nhất 2/3 dự án. Không thay tiêu chí này bằng thắng mean hoặc một metric
thuận lợi sau khi xem kết quả. Đừng chuyển gate này thành tiêu chí ép tái lập
artifact phải thắng tác giả: đó là hai nhiệm vụ khác nhau.

Karaf exploratory vì đã xem baseline holdout. Reserved ActiveMQ/Log4j đã được
audit dữ liệu nhưng chưa mở ranking/score phương pháp. “Reserved đóng” không
có nghĩa chưa bao giờ đọc metadata; có nghĩa không dùng tail để chọn/đánh giá
method trong các vòng development vừa qua.

## 3. Nguồn sự thật và quy tắc diễn giải

Đọc theo quan hệ version, không chọn báo cáo có kết quả đẹp hơn:

1. `topic1.md`: yêu cầu đề tài gốc, raw objective.
2. `docs/04-design/hc-falcon-v1.md`, `configs/hc-falcon-v1.json`: thay đổi
   normalized v1 đã khai báo; không phải nguyên văn topic1.
3. `reports/stage6/summary.json`, `supplement.json`, `closeout-audit.json`:
   kết quả vòng đầu; `docs/06-pilot/implementation-report.md` để đọc diễn giải.
4. `reports/stage7/diagnosis.json`: chẩn đoán development, không phải causal proof.
5. `reports/stage8/summary.json`, `cache-policy-summary.json`, `closeout-audit.json`:
   bản sửa và policy riêng; không thay thế/xóa kết quả stage6.
6. `reports/stage9/fidelity-audit.json`, `docs/09-fidelity/review-and-next-plan.md`:
   kết luận fidelity mới nhất và phạm vi kế hoạch này.
7. `reports/stage1/falcon-chart-full-smoke.json`, `falcon-chart-full-cold-run.json`,
   `falcon-author-ranking-checks.json`: bằng chứng Chart/author đã có.

Mỗi kết luận phải thuộc một loại: **đã xác minh bằng evidence**, **suy ra bằng
phép tính có công thức**, **giả thuyết**, hoặc **chưa thực hiện/chưa biết**. Gắn
đường dẫn evidence cho kết quả định lượng. Không biến kế hoạch, log “START”,
cache tồn tại hoặc tiến trình đã exit thành bằng chứng hoàn thành thí nghiệm.
Nếu JSON và báo cáo khác nhau, kiểm tra manifest/generator và báo mâu thuẫn;
không tự chọn số. Không cộng số test của các mốc vốn là tập kiểm thử tích lũy.

Không được tuyên bố:

- Defects4J hoàn toàn chưa chạy; đã có full Chart.
- 288 fault IDs là 288 build CI độc lập hay 288 checkout đã được chạy lại.
- FL-only LRTS tương đương FALCON artifact: khác method/class, encoder/pooling,
  clipping, tie và numeric. Probe stage9 chỉ chứng minh có thể khác.
- Restricted có bảo đảm 1−1/e; theorem cũ không áp dụng.
- Không phát hiện leakage bằng test nghĩa là chứng minh mọi nguồn dữ liệu đều
  đúng. Pre-build inventory và actual CI revision vẫn chưa xác minh đầy đủ.
- P95 đạt nghĩa là mọi build nhanh; cold reconstruction là cold measurement;
  cached ranking runtime là runtime full pipeline.
- Test N=0 là ground-truth flaky. Dữ liệu nhóm này có rất ít lỗi.

## 4. Đường dẫn, dữ liệu và phiên bản

Python hiện có: `work/envs/falcon/Scripts/python.exe`. Không mặc định dùng Python
global. Kiểm tra phiên bản thực tế và dependency lock, không cài/upgrade tự động.
Encoder `microsoft/unixcoder-base`, revision
`5604afdc964f6c53782a6813140ade5216b99006`.
HF cache: `work/cache/huggingface/hub`. Ưu tiên offline; không resolve lại main.

ZIP FALCON: `references/artifacts/falcon/falcon.zip`, SHA256
`d60fa62edf1d1838185edf19e61146f5981895702f6a7afce0ab8c3f65ee36c8`.
Upstream đã trích: `work/artifacts/falcon/py/`.
Input: `work/artifacts/falcon/input/<Project>/`; xác minh entry từ ZIP trước khi
dùng. Thư mục source Mockito trong ZIP là `projects/mokito`, không suy đường
dẫn chỉ từ tên project. CSV fault matrices ở `projects/*/bug_data/`.

| Thứ tự cố định | Project | Methods | Fault IDs |
|---|---|---:|---:|
| 1 | Chart | 2193 | 26 |
| 2 | Mockito | 1292 | 27 |
| 3 | Lang | 2239 | 32 |
| 4 | Math | 2996 | 30 |
| 5 | Time | 4044 | 26 |
| 6 | Closure | 8006 | 147 |

Đây là expected counts để phát hiện sai input. Nếu không khớp, điều tra; không
sửa số hoặc bỏ row cho khớp bảng. Tổng methods=20770, fault IDs=288.

Chart legacy cache: `work/runs/falcon/chart-full/{embeddings.npy,embedding-config.json,ranking.json,gains.json}`.
Cache key legacy thiếu một số identity hiện đại như tokenizer/dependency hashes.
Không tự khẳng định nó đủ provenance cho run mới. Kiểm tra hash/source/order/
shape/config và dùng deterministic first batch 16 với cùng batch composition
để kiểm tra tương thích (rtol=1e-5, atol=1e-6, khóa trước kiểm tra). Nếu khác,
giữ cache cũ nguyên trạng, tạo cache mới và báo lý do; không nới tolerance để
“đạt”. First-batch check không chứng minh provenance toàn cache.

## 5. Bảo toàn dữ liệu và phạm vi ghi

Không sửa file được liệt kê trong:

- `reports/stage4/design-freeze.json`
- `reports/stage5/implementation-freeze.json`
- `reports/stage6/final-evidence-freeze.json`
- `reports/stage7/evidence-freeze.json`
- `reports/stage8/evidence-freeze.json`
- `reports/stage9/evidence-freeze.json`

Lưu ý `README.md` cũng nằm trong freeze cũ. Một số manifest đời đầu được bổ sung
bởi amendment: stage6 analysis-v2/v3 là lịch sử hợp lệ, không sửa file hiện tại
về hash analyzer cũ. Kiểm tra final freeze cùng amendment, không xem mọi manifest
cũ là mô tả đồng thời cùng một file hiện tại.

Không chạy lại `scripts/stage1_falcon_smoke.py` để “kiểm tra nhanh”: script ghi đè
report stage1 và cache Chart cũ. Không chạy `stage6_driver.py` hoặc script report
cũ trong preflight; nhiều script audit cũng có tác dụng ghi file.

Các đường dẫn đầu ra dưới đây **được đề xuất, chưa tồn tại/chưa triển khai**:

- `scripts/stage10_*.py`, `tests/test_stage10_*.py`;
- `configs/falcon-reproduction-v1.json`, `configs/chart-bridge-v1.json`;
- `reports/stage10/`, `docs/10-reproduction/`, `work/runs/stage10/`,
  `work/cache/stage10/`.

Chỉ ghi các đường dẫn này khi được giao task tương ứng. Nếu chúng đã tồn tại,
đọc trạng thái/manifest trước; không ghi đè một run khác cấu hình. Bản sửa bug
phải dùng version mới, regression test và liên kết evidence cũ. Không thay code
upstream tại chỗ. Không tải model/dataset mới hoặc gửi dữ liệu ra dịch vụ ngoài
nếu nhiệm vụ không cần; tuân thủ quyền mạng của môi trường.

## 6. Hợp đồng tái lập và chẩn đoán

Primary artifact: UniXcoder/cosine; CPU float32, torch 4 threads, seed=0,
batch=16, max_length=512; upstream unmasked pooling, raw cosine, lazy tolerance
1e-6 và input-index tie. Không dùng masked pooling hoặc clip âm để “sửa” baseline.
Kiểm tra phiên bản và pin đầy đủ trước lượt chạy. Ghi hardware/platform và
thread env; không trộn cached/cold hoặc encoder preparation/ranking time.

APFD theo **fault IDs**: lấy vị trí đầu tiên của mỗi fault trong full permutation.
Với n methods và m fault IDs đã xác minh có thể phát hiện:
`APFD = 1 - sum(first_detection_positions)/(n*m) + 1/(2*n)`.
Nếu thiếu mapping/undetected expected fault, dừng audit; không giảm denominator
âm thầm. Với fixture no-fault, ghi rõ policy riêng và không đưa score vào bảng
thí nghiệm có fault. Không tạo APFDc/TTFF nếu không có runtime method đáng tin.

Bridge Chart cố định: A=artifact; B=cùng vectors A, clip kernel, artifact ranker;
C=cùng kernel B, internal exact greedy FQN; D=cùng ordered source methods,
internal preprocess/chunk/masked encoder rồi kernel/ranker như C. Dùng full
FQN method IDs từ mapping, tuyệt đối không suy FQN từ source text hoặc dùng
string index làm tie FQN. A/B/C/D có manifests và cache identity riêng.
Không chọn nhánh tốt nhất rồi thay baseline LRTS. Không thêm nhánh theo score.

Giới hạn vận hành đề xuất: 8 GiB peak RSS, 8 giờ wall-clock/project, một worker
thí nghiệm tại một thời điểm. Đây là giới hạn, không phải ETA hoặc gate hiệu quả.
Ghi giới hạn vào manifest khi phase được giao; nếu người dùng đổi giới hạn,
ghi thay đổi trước chạy. Guard phải giám sát đúng process tree, không chỉ shell.

## 7. Quy trình task, resume và nghiệm thu

Task board là trạng thái ban đầu. Sau khi được giao công việc, tạo ledger tại
`reports/stage10/task-status.json`, không sửa lịch sử evidence để cập nhật tiến độ.
Mỗi task có `status`, `started_at`, `finished_at`, `inputs_sha256`, `outputs`,
`validation_commands`, `exit_codes`, `limitations`, `next_task`, `blocker`.
Status hợp lệ: not_started/running/blocked/completed/failed; ghi completed chỉ
khi artifact tồn tại và validation đạt. `blocked` cần nguyên nhân cụ thể.

Khi nhận “tiếp tục”: đọc task được giao và ledger, kiểm tra process thật, log,
checkpoint, manifest; tiếp tục phần còn thiếu trong phạm vi đã giao. File status
ghi running nhưng process không còn sống chỉ là stale status. Không chạy trùng
worker, không tin PID/session từ một turn cũ. Archive log trước lần launch mới.
Process ID phải gắn run_id/command/start time. Checkpoint atomic, resume phải
khớp ordered IDs/model/config/version. Batch boundary của encoder upstream phải
giữ nguyên vì pooling có padding; không chia batch khác khi resume.

Completion project cần embeddings đầy đủ/hash, ranking đủ permutation, APFD
đối chiếu độc lập, timing scope và exclusions rõ, exit code thành công, manifest
đúng. “Có log cuối” hoặc “đã chạy nền” không đủ. Không bảo đảm worker sống qua
turn boundary nếu chưa kiểm tra. Không che lỗi stderr hoặc overwrite cold time
bằng timing cache-hit. Không dừng toàn bộ phase sau một project rồi gọi phase xong.

Mỗi cập nhật cho người dùng: việc đã xong có evidence; việc đang chạy; vấn đề
chưa biết; bước sẽ làm tiếp. Báo cáo cuối task: file thay đổi, cách kiểm tra,
kết quả định lượng có denominator, giới hạn và task tiếp theo. Không báo kết
quả dự kiến như kết quả đã đo. Trong task planning-only, không launch experiment.

## 8. Phạm vi phase và điểm dừng

Phase R (tái lập và bridge): T00→T01→T02→T03→T04→T05→T06→T07→T08→T09.
Các dependency cụ thể nằm trong task board; làm tuần tự để không làm nhiễu runtime.
Phase W (báo cáo/lý thuyết): T10, chỉ triển khai nếu được người dùng giao riêng
hoặc giao cả R+W. C00 confirmation luôn ngoài hai phase này.

Không phát hiện bug ≠ chứng minh tương đương artifact. Nếu artifact rerun khác
TSV tác giả, báo delta và điều tra provenance; không sửa code để ép khớp. Khi
không giải thích hết, nhãn đúng là “tái chạy artifact với môi trường pin”.
Nếu vượt tài nguyên hoặc fail integrity/metric, giữ evidence và dừng phần phụ
thuộc, báo lỗi cụ thể. Không bỏ project khó để gọi đủ sáu project.

Không tự mở confirmation, tạo lịch sử từ số bug, chạy lại LRTS với alpha mới,
quét model/tham số, hoặc cài một hệ thống CI deployment ngoài phạm vi. Giữ
kết quả âm như một phần đóng góp; tái lập Defects4J tốt không xóa no-go LRTS.
