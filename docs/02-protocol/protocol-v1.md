# Protocol v1 — dữ liệu, history và baseline đơn giản

Ngày chốt cấu hình: 2026-09-13, trước khi chạy replay v1. Phạm vi được triển khai
là phần 1–3: adapter LRTS, history, evaluator và sáu baseline đơn giản. Chưa tích
hợp semantic FALCON/DANTE adaptation, rank fusion, FAST hoặc HC-FALCON.

## 1. Setting và đơn vị

- Full-suite prioritization, feedback đầy đủ từ log, không mô phỏng selection.
- Đơn vị là record test class trong LRTS, kể cả record nghi là lỗi bộ chạy.
  Không đồng nhất failing class với lỗi phần mềm riêng biệt.
- Build-stage key: `(project, PR, build_id, stage)`. Physical build key bỏ stage.
- Test history identity: `(project, base_branch, stage, FQN)`. Các PR cùng
  nhánh đích chia sẻ lịch sử; không tự ghép `main` với `master`, không ghép
  tên test đã đổi. FQN đổi tên có history mới; FQN giữ nguyên vẫn giữ history
  dù source thay đổi. Đây là lựa chọn thiết kế v1, cần sensitivity về sau.
- Raw CSV là inventory **đã quan sát sau chạy**. V1 giữ nguyên toàn bộ record,
  không lọc theo outcome/duration/source. Đây là giả định replay, chưa chứng
  minh CI thực biết inventory này trước chạy, hoặc log phản ánh toàn suite dự
  định. Kiểm thử leakage chỉ chứng minh ranh giới feature theo giả định này.

## 2. Cutoff và eligibility

Giả định đã công bố: `cutoff = build_timestamp` (start),
`available_at = cutoff + build_duration` theo giây. Collector LRTS chuyển dữ
liệu Jenkins từ ms sang s; chưa có raw build JSON đủ để xác nhận mọi timestamp.
Duration build thiếu/bằng 0/âm: availability unknown, không dùng làm history.

Chỉ nhận history khi **available_at < cutoff** (không nhận bằng cutoff), cùng
context, khác physical build và status thuộc `SUCCESS`, `FAILURE`, `UNSTABLE`.
Nhánh đích thiếu: không chia sẻ history. Mọi điều kiện được kiểm tra lại tại
snapshot, kể cả khi store đã nhận record tương lai. Không dùng thứ tự PR/build ID.

Build `ABORTED`, `NOT_BUILT` hoặc status khác vẫn sinh ranking chẩn đoán, lưu
ground truth/ledger, nhưng không chấm metric chính hoặc đưa vào history.
Status hiện tại chỉ dùng sau ranking. Không bỏ một test riêng lẻ để làm metric
trở nên xác định. Policy này được chốt cho feasibility, chưa coi là cohort đánh
giá đại diện CI thực tế.

## 3. Dữ liệu trước/sau ranking

| Kiểu | Nội dung |
|---|---|
| `RankingInput` | Key, branch, cutoff, commit, test IDs, source annotations và nguồn inventory. |
| `Snapshot` | Feature đã đóng băng, evidence build keys, cutoff, runtime reference, timestamp evidence cuối. |
| `CompletedBuild` | Outcome/duration thực tế, availability và status; chỉ history/evaluator được đọc. |

Source audit chỉ cung cấp status/path/hash theo đúng key + SHA + FQN; không
đọc cột outcome của file source audit. Không đọc `last_outcome` hoặc
`last_outcome_N` từ artifact. Snapshot không chứa current outcomes, actual test
durations, current build duration hoặc current result. Ranker chỉ nhận Snapshot.

## 4. Trường hợp biên

| Trường hợp | Chính sách đã triển khai |
|---|---|
| Test mới/vắng ở build trước | Unknown; không thêm PASS giả. |
| Outcome thiếu/ngoài 0,1 | `None`; không cập nhật failure counts, duration hợp lệ vẫn là cost observation. Metrics cần outcome đầy đủ trả NA toàn build. |
| Test thiếu source | Giữ test, annotate `missing`/`unverified`; các baseline hiện tại không cần source. |
| FQN có nhiều source module | Giữ `ambiguous`, giữ các path; không chọn tùy ý một file. |
| `JUnit4Provider` | Tag `suspected_runner_event`, vẫn giữ outcome/duration và failure denominator. Chưa có bằng chứng để loại như infrastructure failure. |
| Test duration bằng 0 | Giữ để chấm midpoint/recall nếu tổng runtime >0; không dùng làm runtime estimate. |
| Test duration thiếu/âm/không hữu hạn | Giữ test; APFD vẫn tính nếu labels đủ, các metric thời gian NA. |
| Cả suite runtime =0 | Metric thời gian NA, không chia epsilon để tạo score giả. |
| Không có failure | APFD/APFDc/recall NA; TTFF censored với horizon là total runtime nếu hợp lệ. |
| Suite rỗng | Ranking rỗng; metric NA với lý do. |
| Ranking thiếu/trùng/thừa test | Dừng bằng lỗi, không thu nhỏ denominator. |

**Semantic fallback chưa được khóa/triển khai.** Trước khi tích hợp FALCON và
HC-FALCON phải xác minh ambiguous module, lỗi bộ chạy và inventory/source tại
revision thực thi. Nếu thiếu source vẫn tồn tại, mọi phương pháp semantic cần
cùng một policy fallback đã công bố; không lấy tên test làm source rồi giữ
nhãn “source embedding” một cách ngầm định. Phần này không chặn baseline history.

## 5. Feature và baseline

N là số outcome đã quan sát hợp lệ; F là số fail. V1 dùng toàn bộ history hợp
lệ trong cohort đã nạp, không decay/window giới hạn:

```text
p = (F + 1) / (N + 2)                  # Beta(1,1)
conf = N / (N + 5)
r = conf * p
c_ref = median(positive past durations in context), fallback 1 second
c = median(positive past durations for test), fallback c_ref
c và c_ref được chặn dưới ở 1e-6 second
c_tilde = c / c_ref
q = r / (sqrt(c_tilde) + 1e-8)
```

Positive duration quan sát được vẫn có thể dùng khi outcome unknown. Mọi
normalization dùng past observations. “Most-Fail” dùng count, không failure rate.

| Baseline | Quy tắc |
|---|---|
| Random | Shuffle list ID đã sort, seed riêng suy từ SHA-256(seed, build key). Smoke seed 42. |
| Shortest-Test-First | c tăng dần. |
| Most-Fail | F giảm dần. |
| Recent-Fail | Thời điểm availability của failure gần nhất giảm dần; chưa fail xếp sau. |
| History-only | r giảm dần. |
| History+cost | q giảm dần. |

Tie-break dùng FQN tăng dần, không phụ thuộc thứ tự CSV hoặc ground truth.
Tất cả phương pháp dùng cùng Snapshot và cùng inventory. Chưa tune các hằng
số; không diễn giải kết quả của smoke seed đơn thành hiệu quả nghiên cứu.

## 6. Metric chung

Với n test, m failing records đã quan sát; r_i là vị trí 1-based của record fail:

```text
APFD = 1 - sum(r_i)/(n*m) + 1/(2*n)
APFDc_midpoint = 1 - sum(completion_i - duration_i/2)/(m * total_duration)
TTFF = completion của test fail đầu tiên
Recall(B) = số failing records hoàn tất trước hoặc đúng B / m
```

Budgets 10%, 25%, 50% **thời gian thực toàn suite** chỉ thuộc evaluator, không
đưa ngược vào ranking. Runtime bằng 0 được giữ theo giá trị đã ghi, không tự
suy đoán độ chính xác đo. APFDc không cộng thêm `1/(2*n)` như code DANTE.
Không-failure không gán score 1. Tính toán double, tolerance so ngân sách tương
đối 1e-12 để tránh lệch floating-point tại đúng mốc, không thêm ngưỡng giây cố định.

TTFF v1 là execution-only, không phải CI wall-clock/end-to-end. Thời gian tạo
feature và ranking được lưu riêng; chưa có semantic preparation hoặc mô hình
song song để kết luận latency CI.

## 7. Cohort, output và điều kiện chuyển tiếp

Smoke mặc định: 20 metadata rows đầu của Karaf theo timestamp/PR/build/stage,
giống cách chọn giai đoạn 1. Không chọn theo outcome, source coverage hoặc score.
Không có warm-up/calibration/holdout riêng: tất cả là **technical replay**, bắt
đầu cold start và chỉ thấy các history observations trong cohort đã nạp.
Chưa đưa ra p-value, tuning hoặc kết luận baseline nào tốt hơn trong nghiên cứu.

Output tách `inputs.jsonl`, `features.jsonl`, `ground-truth.jsonl`,
`rankings.jsonl`, `metrics.csv`, `ledger.json`, `selection.json`, `manifest.json`.
Manifest lưu checksum ZIP, code, protocol, source annotation và config. Ledger
giữ mọi build với lý do không được chấm. NA xuất JSON null/CSV trống kèm reason.

Trước pilot hiệu quả: xác minh inventory/cutoff, chốt semantic fallback,
adapter DANTE/FALCON và cohort/split. Đây là cổng review, không tự chuyển từ
20 build kỹ thuật sang “evaluation set” hay sửa config theo kết quả đẹp nhất.
