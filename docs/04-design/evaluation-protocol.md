# Protocol đánh giá HC-FALCON v1 — đóng băng trước semantic pilot

Ngày 2026-09-13. Chưa chạy HC-FALCON hoặc score baseline mới trên ActiveMQ/Log4j.
Kế thừa evaluator v2, chỉ mở rộng thiết kế đa dự án và statistical unit. Đây là
protocol nội bộ có checksum, không gọi là đăng ký nghiên cứu độc lập bên ngoài.

## 1. Dữ liệu, split và giới hạn xác nhận

| Project | Warm-up physical / stage rows | Development physical / stage rows | Reserved confirmation physical / stage rows |
|---|---|---|---|
| ActiveMQ | 90 / 90 | 133 / 133 | 223 / 223 |
| Log4j | 54 / 106 | 81 / 158 | 135 / 264 |

Chia theo physical build được sort `(start, project, PR, build)`; first ceil(20%)
làm warm-up, next tới ceil(50%) làm development, phần sau reserved. Boundary
là timestamp ở vị trí cắt; mọi timestamp bằng boundary sang cùng phần sau,
không tách tie hoặc hai stage cùng physical build. Split không dùng score,
source coverage, status hoặc failure. Danh sách thực tế:
[ActiveMQ](../../reports/stage4/activemq/selection.json),
[Log4j](../../reports/stage4/log4j/selection.json).

- ActiveMQ development từ 2023-02-02T08:38:41Z, confirmation từ 2023-09-15T13:28:36Z.
- Log4j development từ 2021-03-23T15:58:17Z, confirmation từ 2021-12-22T20:15:38Z.
- Karaf giữ split stage3; mọi kết quả HC trên Karaf chỉ là **exploratory** vì
  score baseline đã được xem. Không tạo "holdout mới" bằng cách chia lại Karaf cũ.

Reserved ActiveMQ/Log4j đã được audit counts/outcome validity và history readiness,
nhưng chưa tính ranking hoặc metric của phương pháp. Công bố mức exposure này;
không gọi dữ liệu hoàn toàn chưa được nhìn. Không dùng reserved để tune alpha,
normalization, tokenizer, chunk cap, fallback hoặc chọn baseline. Nếu thay v1
sau development, tạo protocol/config version mới trước mở score reserved.

Giữ ActiveMQ có 2 PR và Log4j có 3 PR qua ranh giới; không có SHA trùng qua ranh
giới confirmation ở hai cohort. Đây là temporal replay, không cam kết unseen PR.
Encoder pretrained được dùng hồi cứu; chưa chứng minh model có thể tồn tại hay
không từng gặp source tại thời điểm CI lịch sử. Không tuyên bố prospective CI.

Ba dự án đủ phạm vi pilot đa dự án của đề tài, nhưng chỉ **hai dự án có phần
confirmation chưa xem method score**. Muốn tuyên bố xác nhận độc lập trên ba
dự án phải bổ sung dự án hoặc dữ liệu mới; không tính Karaf exploratory thành
xác nhận thứ ba.

## 2. Cohort eligibility và source gate

Giữ mọi row trong ledger; ABORTED/status ngoài SUCCESS/FAILURE/UNSTABLE không
vào history/score chính. Timestamp/start-duration vẫn là giả định có biên +2s;
không có raw report để khôi phục inventory trước chạy. LRTS class đã bị upstream
lọc SKIPPED/tên bất thường và gộp FQN. Không chạy Java để suy đoán ground truth.

Trước semantic pilot giai đoạn 5–6 phải map source đầy đủ cho **warm-up và
development dự định chạy**, rồi báo coverage, failing-source coverage, nested
fallback và truncation. Mẫu source stage4 chỉ là first 20 physical warm-up builds,
không đủ chứng nhận toàn cohort. Không âm thầm bỏ test/build làm coverage đẹp hơn.
Gate kỹ thuật: source hợp lệ >=90% test observations trong phần pilot của mỗi
project; nếu thấp hơn, báo chưa đạt gate và điều tra, không chọn subset theo
failure/score. Gate này được chốt sau audit mẫu, không phải tiêu chí đăng ký
trước audit. Không loại failure thiếu source dù đã đạt 90%.

Chỉ tải/map source reserved sau khi khóa implementation/config bằng checksum;
vẫn không đọc score để quyết định source policy. Project không đạt gate không
được thay bằng project có score tốt hơn; project thay thế phải có audit/split riêng.

## 3. Phương pháp và adaptation contracts

| Phương pháp | Cấu hình/đơn vị cần thực thi ở giai đoạn 5 |
|---|---|
| Sáu baseline stage2 | Giữ nguyên score r/q và runtime estimate; Random 20 seed 0..19. |
| FALCON-LRTS | FL-only trên kernel/source pipeline mới, cùng full inventory; nhãn adaptation, không gọi nguyên bản. |
| HC-FALCON-N v1 | Objective normalized trong đặc tả, alpha=.5. |
| HC-FALCON-topic-raw v1 | Công thức topic1.md nguyên bản, cùng alpha/kernel/history. |
| FL+History | Thay q bằng r, normalize bằng sum(r); alpha=.5. |
| Full bỏ confidence | Thay conf*p bằng p trong q, normalize bằng tổng q tương ứng; alpha=.5. |
| Borda-FL-History | Trung bình rank chuẩn hóa `(rank-1)/(n-1)` của FL và History-only, xếp tăng dần; n=1 score=0; tie FQN. |
| Borda-FL-HistoryCost | Cùng công thức Borda nhưng dùng History+cost; đối chứng mạnh hơn để kiểm tra giá trị objective động. |
| FAST-pw-LRTS | Port wrapper artifact FALCON: bbox=True, k=5, r=1, b=10, memory=True; 20 seed. Source có cùng preprocessing nhưng chưa cắt chunk encoder. |
| DANTE-CCH-adapt-r1 | Contract bên dưới; chỉ đưa vào so sánh khi port đã qua kiểm tra và đủ declared diff. |

FAST phải pin PYTHONHASHSEED=0, random seed theo build, thứ tự input FQN; sort
candidate set trước lựa chọn ngẫu nhiên để không phụ thuộc process hash order.
Đây là adaptation về determinism, ghi riêng với chạy nguyên bản. Ưu tiên các
test có source bằng FAST rồi nối unavailable theo FQN; không tạo shingle từ
tên test hay làm biến mất record. Không tuyên bố FAST dùng cùng cosine kernel
với FL: nó dùng representation/MinHash riêng, cùng source eligibility mask.

DANTE-CCH-adapt-r1 lấy công thức score trong `run_prioritization.py`, không lấy
placeholder LTR. Chốt các khác biệt trước port:

- Lấy 15 build-stage history hợp lệ gần nhất cùng context theo completion;
  windows n=1,3,5. Recompute history, không đọc last_outcome_N từ JSON đã lọc.
- THFR là mean known outcomes của test trong 15 build đó; không có known ->0.
  Khi ước lượng P(fail|sticky_n), sticky là có known fail trong n build hợp lệ
  trước record đang xét, **trong cùng test**; unknown không thêm PASS. Conditional
  pool chỉ dùng known outcomes của các record quá khứ; <20 sticky events ->prob0.
- H(t)=THFR(t)+sum_n I(sticky_n at cutoff)*prob_n/n. Không thay bằng score q của HC.
- R(t)=max TF-IDF cosine với các Java diff documents `trunk_sha -> build_head_sha`
  đã pin. Corpus là changed Java documents, query là source test; tokenizer
  định nghĩa token `[A-Za-z_][A-Za-z_0-9]*` lowercase, sklearn TF-IDF defaults
  sau khi join token; version package được pin ở implementation freeze. Không
  method-name boost. Không có Java changes ->R=0; test thiếu source ->R=0.
- Chốt weights history=1, relevance=1, power=1.2; score
  `(H + R^1.2)*max(F_15,0.1)/c_est`, giảm dần, tie FQN. c_est là estimate chung
  từ quá khứ, không phải actual duration. Không recency boost của bản Modified.
- Nếu không lấy được declared diff cho một build, DANTE là unavailable với lý
  do, không tự cho toàn bộ relevance=0 rồi gọi là DANTE đầy đủ. Báo common paired
  subset và missingness riêng; không thay cohort của các phương pháp chính.

Contract này cố ý sửa ranh giới history/cost/inventory và xác định tokenizer;
đó là baseline adaptation, không phải tái lập nguyên paper hoặc nguyên artifact.
Original DANTE/FALCON artifacts giữ riêng để đối chiếu. Similarity mask zero
trong HC spec áp dụng FL family; DANTE relevance và FAST có fallback riêng đã
ghi ở đây vì chúng không tối ưu cùng kernel/objective.

## 4. Metric, statistical unit và thống kê

Metric chính: **APFDc midpoint**, theo failing class records, cùng evaluator
stage2. Secondary: APFD, TTFF execution-only, Recall 10/25/50% suite duration,
prep/ranking time, memory. Không đổi metric chính sau khi thấy kết quả khác dấu.
No-failure APFD/APFDc/recall NA; TTFF censored tại total duration hợp lệ. TTFF
median uncensored phải kèm số censored, không diễn giải là median của mọi CI build.

Mỗi method có ranking theo build-stage. Statistical unit là **physical build**:
mean metric trên các stage có metric xác định và cùng điều kiện giữa methods;
stage no-failure giữ NA, không thêm điểm 1. Log4j Windows/Ubuntu không được tính
như hai physical build độc lập. Báo số stage đóng góp cho từng metric/build.
Random/FAST: mean qua seed trong stage trước, rồi mean qua stage trong physical
build. Không nhân sample size bởi số seed. Báo thêm dispersion theo seed/stage.

Paired delta = metric(HC-N) − metric(baseline) trên cùng physical build; TTFF
âm là tốt hơn. Báo median paired delta, win/tie/loss (tolerance 1e-12 cho mô tả),
và từng project; không thay bằng chênh lệch hai median. Tổng hợp đa dự án cân
bằng dự án, không pool tất cả rows để project lớn chi phối.

Để giảm giả định độc lập từng build, primary inference dùng các block không
overlap gồm **10 physical builds liên tiếp** theo chronology reserved, gồm cả
build no-failure/ABORTED khi xác định biên block. Trong block lấy mean của paired
delta xác định; block không có cặp là NA. Cuối chuỗi giữ block ngắn. Quy tắc này
không bảo đảm hết autocorrelation; báo thêm sensitivity block 5/20, không chọn
block size theo p-value.

Wilcoxon two-sided trên block mean paired deltas, zero_method=pratt,
correction=False, method=approx; yêu cầu >=10 block có delta khác 0 và >=20
physical pairs xác định, thiếu thì **insufficient evidence**, không gộp thêm
stage/seed để đạt ngưỡng. Primary Holm family là 6 phép so: HC-N với FL-only,
History-only, History+cost trên ActiveMQ và Log4j, family alpha=.05. Các so khác
là secondary/exploratory, ghi rõ và điều chỉnh Holm trong family riêng đã liệt
kê trước thực nghiệm. Karaf không đi vào primary confirmation family.

Cliff's delta giữa các phân bố physical-build metric là effect size mô tả,
không tận dụng pairing; báo thêm win/tie/loss và paired delta để tránh nhầm.
95% interval cho mean block paired delta bằng bootstrap các block đã định nghĩa,
10.000 lần, seed2026; ghi là conditional/descriptive interval và giới hạn phụ
thuộc thời gian. Không tuyên bố inference tới mọi dự án từ hai project xác nhận.

## 5. RQ3/RQ4 và go/no-go đã định nghĩa

RQ3: nhóm N=0, 1..4, >=5 được xác định trước cutoff; báo vị trí, thời gian phát
hiện và failing-record recall theo nhóm, số mẫu luôn đi kèm. Chuỗi pass/fail
khác nhau qua các revision không đủ xác nhận flaky. Không có ground-truth flaky
thì chỉ báo outcome-instability proxy với tên đó; phần flaky RQ còn hạn chế.

RQ4: đo local source lookup/preprocessing, model load, embedding, kernel,
history, ranking riêng. Warm cache vẫn tính embedding cache misses do source
đổi; cold gồm load model và toàn bộ embedding. Chi phí fetch source lần đầu
báo riêng, không giả sử download miễn phí. Mỗi method được tính chi phí chạy
độc lập, không hưởng embedding miễn phí vì đã chạy sau method khác.
TTFF end-to-end mô phỏng = prep + ranking + execution TTFF; không gọi là CI
wall-clock vì không có mô hình parallel stages/setup/queue chính xác.

Gate engineering v1: peak RSS <=8 GiB, p95 của warm prep+ranking / total suite
execution <=10% trên các build có total>0. Đây là ngưỡng thiết kế để đo, chưa
chứng minh đạt. Báo cold riêng, không che bằng cache hit. Nếu source retrieval
không có sẵn trước chạy, chỉ được kết luận về offline replay.

Gate hiệu quả pilot: median paired APFDc improvement >=0.03 (3 điểm phần trăm
trên thang 0–1) so với **cả FL và History+cost** trên ít nhất 2/3 project
development; không suy từ difference of medians. Đồng thời báo tradeoff TTFF
và Recall10, không được gọi tốt hơn toàn diện nếu chúng giảm. Ngưỡng này là
quyết định tiếp tục, không là giả thuyết đã chứng minh. Thiếu baseline/source
hoặc không qua gate thì báo no-go/revise trên development, không mở tail để tìm
kết quả thuận lợi.

## 6. Điều kiện mở reserved và nhánh Defects4J

Trước mở score reserved: freeze source policy, model/dependency versions,
implementation/config hashes, baseline ports, alpha và metric/statistics;
pass standard/lazy, cache, mask, granularity và leakage tests. Lưu access log
và completion marker. Sau mở score, không gọi lần tune tiếp theo trên cùng
tail là independent confirmation. Stage4 chưa mở cửa này.

Defects4J là nhánh riêng: tái lập FALCON trên sáu suite/fault matrices đã audit,
điều tra sai khác Chart; không suy CI history từ fault ID, không gán class outcome
evaluator cho fault matrix. Runtime thiếu thì không tự dựng APFDc. Không gộp
method-level fault metrics với class-level LRTS records.
