# Báo cáo giai đoạn 1 — khả thi dữ liệu và artifact

Sinh từ bằng chứng cục bộ lúc 2026-10-14T11:28:30+07:00. Phạm vi: FALCON/Defects4J và
DANTE/LRTS; không triển khai HC-FALCON, không đánh giá giả thuyết hiệu quả.

## Kết luận

**Có thể bắt đầu xây bộ dữ liệu/protocol và lõi HC-FALCON, nhưng chưa đủ điều
kiện dùng nguyên DANTE làm baseline rolling công bằng.** Source Karaf đã truy
cập được tại các commit metadata. Cần khóa xử lý test thiếu/ambiguous, duration
ước lượng, lịch sử theo thời điểm hoàn tất và metric chung trước thực nghiệm.

Đã kiểm tra hai ZIP, 20,770 test methods của FALCON, 108,366
metadata rows LRTS, 50 processed JSON và source của 20
build Karaf. Đã tự chạy DANTE trên một build, FALCON trên mẫu 16 test và toàn bộ 2.193 test Chart.
Trạng thái full Chart nằm ở mục FALCON dưới đây, không suy từ kết quả tác giả.

## 1. Artifact và môi trường

- MD5 cả hai ZIP khớp manifest; SHA-256 trong [archives.json](../../reports/stage1/archives.json).
- FALCON ZIP có 2,556 entries; DANTE 417,906,
  tổng kích thước giải nén DANTE 17.02 GB.
- Hai venv riêng, Python 3.13.11; PyTorch CPU, 4 luồng, không CUDA.
  `pip check` đạt cho cả hai môi trường. Lock: [FALCON](../../reports/stage1/falcon-environment.txt),
  [DANTE](../../reports/stage1/dante-environment.txt).
- DANTE root requirements và pyproject khác nhau; smoke prioritization dùng
  root requirements. Không xác nhận solver selection hoặc ML baseline.
- FALCON root LICENSE là MIT; FAST/lsh có header GPL-3.0-or-later. DANTE và
  LRTS có file MIT riêng. Giữ khai báo từng thành phần, không gán MIT cho tất cả.
- Karaf `LICENSE` tại commit đầu mẫu `a45cb03f411863a1b65757b6c66dfcbaff9117df`
  ghi Apache License 2.0.
- Kết quả gốc giữ trong ZIP; `work/runs/` là kết quả tự chạy. Code upstream
  trích xuất giữ nguyên. Một số stage Kafka có `:`; audit đọc trực tiếp ZIP.

## 2. FALCON / Defects4J

| Project | Test methods | Fault IDs | Source version | Mapping lỗi |
| --- | --- | --- | --- | --- |
| Chart | 2193 | 26 | Chart_1f | 0 |
| Closure | 8006 | 147 | Closure_1f | 0 |
| Lang | 2239 | 32 | Lang_1f | 0 |
| Math | 2996 | 30 | Math_1f | 0 |
| Mockito | 1292 | 27 | Mockito_1f | 0 |
| Time | 4044 | 26 | Time_1f | 0 |

Tổng cộng **288 fault IDs** giữa sáu project.
Mỗi project có một suite trích xuất từ đường dẫn `*_1f` và fault matrix nhiều
cột phiên bản lỗi. Đây là dữ liệu artifact tổ chức ở mức project; chưa chứng
minh quá trình chạy từng phiên bản từ một Defects4J checkout mới.

- Không có dòng bbox rỗng hoặc test identifier trùng. Có source giống nhau ở
  các test ID khác nhau; giữ các ID, không tự deduplicate theo nội dung source.
- Mapping và index list khớp; fault key nằm trong suite.
- So source trích xuất với bbox sau chuẩn hóa whitespace: 0 sai lệch.
- So CSV fault matrix với pickle: 0 sai lệch.
- 60 ranking FALCON của tác giả đều là hoán vị đầy đủ; tính lại
  APFD độc lập khớp TSV (sai lệch tối đa 0).
  Đây là kiểm chứng output có sẵn, không phải tự chạy 60 thí nghiệm.
- ZIP chỉ có timing JSON cho embedding, không chứa vector `.npy`.

### Tự chạy

Mẫu 16 test dùng encoder pin `5604afdc964f6c53782a6813140ade5216b99006`:
embedding 16×768 hữu hạn, standard/lazy greedy cùng thứ tự; không chấm APFD
full suite cho mẫu này. Gọi hàm artifact trực tiếp qua wrapper CPU để tránh
runner hardcode `python3 --device cuda` và skip vì output đã tồn tại.

Full Chart: **2193 test**, APFD tính độc lập **0.732277526**;
embedding lần đầu 896.41 s (cache hit: False),
similarity 0.10 s, ranking 33.80 s.
APFD tác giả trong cấu hình Chart/UniXcoder/cosine: **0.7263144971763303**.
Chênh lệch APFD là **+0.005963029** (thang 0–1).
Chạy được pipeline nhưng **chưa tái lập chính xác số của tác giả**. Không diễn
giải chênh lệch là cải tiến phương pháp; chưa xác định nguyên nhân và không
chỉnh preprocessing theo kết quả.
Model revision, dependency và phần cứng không được coi là giống môi trường paper.
Similarity nhỏ nhất -0.085129, số phần tử âm 1026.
Đây là vi phạm điều kiện đầu vào similarity không âm của đề xuất HC-FALCON,
không phải chứng minh trực tiếp ranking FALCON hiện tại sai. Cần định nghĩa
biến đổi similarity trong protocol, giữ baseline nguyên bản riêng.
Ranking và gain tự chạy: `work/runs/falcon/chart-full/`. Thời gian lần đầu được
giữ riêng trong `falcon-chart-full-cold-run.json`; lượt kiểm tra lại dùng cache
embedding để xác nhận exit code bằng cách ghi log subprocess trực tiếp.

Bằng chứng tự chạy: [smoke 16 test](../../reports/stage1/falcon-chart-first-16-smoke.json).
Kết quả full suite nằm trong `reports/stage1/falcon-chart-full-smoke.json` khi
lượt chạy hoàn tất; [verification](../../reports/stage1/verification.json) ghi
trạng thái kiểm tra cuối.

### Điểm cần giữ trong protocol

`submodtcp.py` dùng raw cosine chưa chặn âm; giá trị không âm trên một mẫu
không chứng minh mọi đầu vào đều không âm. Hàm embedding lấy mean trên cả
padding positions. Batch size/padding có thể ảnh hưởng representation; không
âm thầm đổi khi gọi là baseline tái lập. Lazy greedy upstream tính lại coverage
từ subset mỗi lần, chưa lưu vector coverage như lõi HC-FALCON dự kiến.

## 3. DANTE / LRTS

| Project | Metadata rows | Raw có sẵn | Build/stage có fail | Duration = 0 | Lệch count metadata | JSON mẫu |
| --- | --- | --- | --- | --- | --- | --- |
| activemq | 446 | 446 | 197 | 4614 | 0 | 5 |
| hadoop | 1980 | 1980 | 797 | 2128 | 0 | 5 |
| hbase | 1018 | 1018 | 439 | 698 | 0 | 5 |
| hive | 2131 | 2131 | 1472 | 383 | 0 | 5 |
| jackrabbit-oak | 1654 | 1654 | 1006 | 283173 | 0 | 5 |
| james | 5838 | 5838 | 2528 | 276300 | 0 | 5 |
| kafka | 53554 | 53554 | 37842 | 1661102 | 0 | 5 |
| karaf | 726 | 726 | 205 | 8373 | 0 | 5 |
| log4j | 528 | 528 | 162 | 3172 | 0 | 5 |
| tvm | 40491 | 40491 | 5027 | 59899 | 26833 | 5 |

Một row là **project + PR + build + stage**; không đồng nhất tổng row với số
build CI độc lập. Bảng thống kê toàn bộ row trong metadata đã cung cấp; chính
dataset đã được upstream lọc, không đại diện mọi build CI ban đầu.

- Raw CSV được kiểm tra outcome, duration, ID trùng, số test/fail so metadata.
  Chi tiết: [project audit](../../reports/stage1/lrts-project-audit.json),
  [build audit](../../reports/stage1/lrts-build-audit.csv).
- Tất cả metadata row có raw CSV tương ứng; không thấy duration âm/không hữu
  hạn hoặc outcome ngoài 0/1 trong raw đã kiểm tra. Có duration bằng 0 ở cả
  mười dự án. Điều này không chứng minh raw giữ đầy đủ skipped/cancelled:
  upstream đã tổng hợp và lọc trước khi đóng gói.
- Quét 104,042,398 test observations trong 108,366
  CSV được metadata tham chiếu. ZIP còn các raw CSV ngoài metadata; chưa audit
  nội dung các file ngoài tập tham chiếu này.
- TVM có 26.833 row lệch số test/fail giữa raw và metadata; chưa kết luận
  nguyên nhân. TVM không nằm trong ba ứng viên Java và không đưa vào pilot.
- Chỉ có 5 processed JSON mỗi project. Tổng số test records có tokens:
  1013; không coi tokens là source Java.
  Relevance có trong mẫu dùng `tfidf`; mặc định config `bm25` không khớp.
- Không có file Java độc lập trong ZIP. Source cho HC cần lấy đúng commit.
- Không coi `last_outcome` và `last_outcome_N` là cùng semantics: raw giữ
  outcome quan sát gần nhất theo class/stage; augmentation đi qua danh sách
  processed JSON đã lọc và điền 0 khi thiếu test/build.

## 4. Source mapping và chronology Karaf

Quy tắc mẫu: 20 metadata row đầu theo timestamp, PR, build, stage; không lọc
theo fail. Có 18 commit khác nhau, đều fetch được từ
`apache/karaf`. Không chạy test hoặc build mã Java.

- Mapping xác minh package/class: **3697/3740 (98.85%)** lượt test.
- Failing records có source: **17/18**.
- `OsgiLocatorTest` xuất hiện ở hai module (`specs/activator`, `specs/locator`):
  giữ ambiguous; log class-level không đủ để chọn một module tùy ý.
- Failure chưa map là `org.apache.maven.surefire.junit4.JUnit4Provider` ở
  PR-1287/build1. Tên gợi ý lỗi bộ chạy; chưa đủ bằng chứng phân loại chính
  thức, không tự xóa khỏi tập failure.
- Một số class không có trong tree của SHA metadata. Chưa chứng minh SHA
  metadata là chính xác revision thực thi sau merge CI; đây là giới hạn cần
  đối chiếu raw build/test report nếu mở rộng tuyên bố về source.
- Có 4 / 20 row mà ít nhất một build bắt đầu trước
  còn chưa hoàn tất theo `timestamp + duration`. Upstream collector chia
  Jenkins timestamp/duration cho 1000; raw build JSON chưa được kiểm tra vì
  không thấy trong các thư mục metadata/testdata đã đóng gói. Cutoff completion
  vẫn cần xác nhận semantics, xử lý tie và các stage cùng build.
- Các JSON có trong mẫu có 12 history lag khác so với chuỗi raw
  start-time. Đây là chênh lệch định nghĩa lịch sử, không tự là chứng minh
  future leakage. Không dùng sẵn history này cho HC-FALCON.

Bằng chứng: [source summary](../../reports/stage1/karaf-source-summary.json),
[mapping từng test](../../reports/stage1/karaf-source-mapping.csv),
[history crosscheck](../../reports/stage1/karaf-history-crosscheck.json).

## 5. Smoke DANTE và các vấn đề đã tái hiện

Chọn PR-1287/build1: processed build Karaf sớm nhất có raw history, 4 history
rows. Runner nguyên bản chạy được với override đường dẫn, một target và
`tfidf`. Không sửa thuật toán của tác giả.

| Kiểm tra | Kết quả |
|---|---|
| Test trong đầu vào | 212 |
| Test được runner xếp hạng | 206 |
| Test bị loại | 6, gồm 1 failure |
| APFDc theo artifact, trên universe đã lọc | 0.676730021 |
| APFDc midpoint, cùng universe | 0.674302837 |
| Đổi duration hiện tại làm đổi score DANTE | True |

Không dùng hai APFDc này làm ước lượng hiệu quả toàn suite. Cả hai chấm trên
206 test còn lại, không trên 212 test ban đầu.

Các vấn đề cụ thể trong `run_prioritization.py`:

1. `calculate_all_scores` lọc test theo `source_file_found` và duration hiện
   tại; `calculate_hybrid_scores` chia score cho duration hiện tại. Đã tái
   hiện việc đổi duration làm đổi score.
2. APFDc dùng midpoint rồi cộng thêm `1/(2n)`; không-failure trả 1. Cần một
   evaluator chung, xử lý NA và tập failure cố định. Báo metric gốc riêng.
3. `groupby(...).shift(1).rolling(...)` áp rolling sau groupby nên có thể
   đi qua ranh giới class. Witness A:[1,0], B:[0,0] khiến quan sát đầu B có
   sticky=1 từ A. Đây là kiểm tra biểu thức code, chưa lượng hóa ảnh hưởng
   trên toàn dataset.
4. `augment_history.py` chỉ đi qua processed builds và dùng 0 khi thiếu;
   không đủ cho semantics unknown và rolling history đầy đủ.
5. LTR output trong smoke là placeholder -100 do fixture không có ML history;
   **không phải baseline LTR đã tái lập**. Không đưa vào bảng so sánh nghiên cứu.

Chi tiết chạy và diagnostics: [dante-smoke.json](../../reports/stage1/dante-smoke.json).

## 6. Dataset pilot và điều kiện chuyển giai đoạn

Đề xuất **Karaf** để hoàn thiện adapter trước: repository nhỏ, đã kiểm tra
20 build và chạy được DANTE. **ActiveMQ và Log4j** là hai ứng viên Java tiếp
theo dựa trên số row vừa phải và raw data có sẵn; chưa xác nhận source mapping
toàn bộ cho hai dự án này. Không chọn vì score HC-FALCON (chưa có score).

20 build Karaf hiện tại chỉ là mẫu feasibility, chưa phải holdout đánh giá.
Mẫu có build ABORTED và inventory thay đổi; cần quy tắc inclusion trước pilot.
Khoảng warm-up/calibration/evaluation sẽ chốt sau khi kiểm tra nguồn đầy đủ,
không lấy best result trên khoảng này rồi gọi là đánh giá độc lập.

| Việc cần làm ở giai đoạn 2 | Tiêu chí |
|---|---|
| Chốt inventory, ID và source fallback | Không làm biến mất test/failure vì thiếu source; ghi riêng framework errors và ambiguous module. |
| Dựng rolling history từ raw | Unknown khác PASS; chỉ dùng outcome đã có tại cutoff, xét stage/branch và rename. |
| Dựng runtime estimate | Dùng quá khứ/fallback, không lấy actual duration hiện tại để ranking. |
| Adapter baseline và metric | Cùng universe/cutoff; giữ kết quả artifact gốc để đối chiếu. |
| Chốt HC-FALCON v1 | Similarity không âm, estimator/confidence/cost/alpha cố định, tuning chỉ trên quá khứ. |

## 7. Tái lập và giới hạn

Lệnh tại [reproduction.md](reproduction.md). Audit có thể chạy lại mà không
download dataset. Model và source fetch cần mạng lần đầu. Không clone đầy đủ
Defects4J, không chạy test Java từng fault version, không kiểm chứng giấy phép
mọi thành phần phụ thuộc và không đánh giá novelty trong giai đoạn này.

Các scripts/report là sản phẩm mới của dự án; bộ reading guide trước đây là
tài liệu lịch sử và có thể còn câu "chưa kiểm tra artifact". Trạng thái hiện
tại lấy theo báo cáo này và evidence JSON, không sửa lại lời giải thích paper.
