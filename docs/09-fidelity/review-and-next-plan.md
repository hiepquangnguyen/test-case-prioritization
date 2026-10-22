# Đối chiếu độ trung thực và kế hoạch sau kết quả âm

## Kết luận để review

Chưa phát hiện lỗi mới làm sai công thức của các phiên bản đã khóa trong phạm vi
audit này. Có khác biệt lớn giữa pipeline LRTS và FALCON artifact, nhưng phần lớn
đã được khai báo từ giai đoạn 4–5. Chúng không được âm thầm sửa hoặc gọi là bản
tái lập nguyên gốc. Probe nhỏ xác nhận một số khác biệt có thể đổi ranking;
chưa lượng hóa chúng giải thích bao nhiêu kết quả LRTS.

Đề xuất dừng mở rộng heuristic/alpha trên LRTS ở thời điểm này. Bước kế tiếp là
hoàn tất tái lập baseline FALCON trên artifact Defects4J và một phép đối chiếu
pipeline có kiểm soát. Giữ kết quả âm của LRTS; không dùng thành công trên bộ
dữ liệu khác để thay thế kết luận LRTS. Reserved tiếp tục đóng.

**Đính chính trạng thái:** câu trả lời trước “Defects4J chưa triển khai/chưa chạy”
quá rộng. Giai đoạn 1 đã audit sáu dự án, kiểm tra output tác giả và tự chạy full
Chart 2.193 test bằng các hàm artifact qua adapter CPU. Chưa tự chạy đủ sáu dự án,
chưa chạy lại từng fault version từ checkout Defects4J và chưa có rolling history
Defects4J. Pilot giai đoạn 6/8 đúng là chỉ chạy LRTS.

Nguồn: [topic1](../../topic1.md), [đặc tả v1](../04-design/hc-falcon-v1.md),
[báo cáo stage1](../01-feasibility/stage1-report.md),
[Chart full tự chạy](../../reports/stage1/falcon-chart-full-smoke.json).

## Đối chiếu yêu cầu, artifact và implementation

| Thành phần | Đề tài / artifact gốc | Đang triển khai | Phân loại và ảnh hưởng |
|---|---|---|---|
| Đơn vị test | Artifact dùng method trong bbox, fault matrix nhiều fault IDs | LRTS class record; semantic đọc toàn compilation unit, nested dùng outer file | Thích nghi dữ liệu; không tương đương method-level FALCON. Source có thể chứa nhiều phương thức/helper. Chưa lượng hóa tác động. |
| Input preprocessing | Loader embedding artifact strip dòng, bỏ dòng rỗng; bbox đã được trích xuất trước | UTF-8 strict, BOM/LF, bỏ Java comments giữ literals | Thay đổi đã khóa; không khẳng định biết toàn bộ preprocessing trước khi tạo bbox chỉ từ loader. |
| Model | UniXcoder cùng tên; artifact gọi model name, không pin revision trong code được đọc | Revision cố định, CPU float32, framework/tokenizer identity trong cache | Tăng tái lập cục bộ nhưng không chứng minh khớp weights/framework của tác giả. |
| Token/pooling | Single sequence tối đa 512; batch mặc định 16; mean cả padding hidden states | Tối đa 16 chunk; masked mean rồi payload-weighted pooling và L2 normalization | Không tương đương. Batch composition có thể ảnh hưởng vector upstream. |
| Kernel | Raw cosine; float32 tensor | Cosine clip [0,1], zero-mask source không dùng được, diag theo valid | Đáp ứng giả thiết không âm của đề tài, nhưng khác artifact; probe âm làm đổi ranking. |
| Greedy | Float32, argmax theo chỉ số input, lazy tolerance 1e-6 | Gain/coverage float64, exact FQN tie, incremental coverage | Thích nghi có kiểm chứng standard/lazy nội bộ, không bảo đảm ranking artifact giống hệt. |
| Objective đề tài | α FL/n +(1−α)Σq | Có `hc_falcon_topic_raw_v1` đúng dạng này; primary HC-N dùng q/Q | Normalization là thay đổi có chủ đích ở stage4, không phải nguyên văn đề tài. Raw đã được chạy như đối chứng và cũng chưa đạt mức tăng yêu cầu. |
| Revision stage8 | Không có trong objective đề tài | Pool q≥0,95q(b), c≤1,25c(b), semantic gain/cost | Heuristic phát sinh từ development, không thay thế phần đóng góp submodular của đề tài; không kế thừa 1−1/e. |
| History | Đề tài chỉ dùng feedback quá khứ | Same context, available_at < cutoff, khác physical build; snapshot độc lập outcomes hiện tại | Đã kiểm chứng kỹ thuật/mutation, không phát hiện vi phạm mới trong audit này. |
| Metric | FALCON APFD: vị trí phát hiện đầu tiên của mỗi fault ID | LRTS APFD/APFDc trên observed failing test records, không có fault identity tương đương | Hai estimand khác nhau; không so số APFD giữa hai dataset như cùng điều kiện. |
| Protocol | Artifact một suite mỗi project và fault matrix | LRTS rolling development, physical-build aggregation, reserved đóng | Không suy fault IDs Defects4J thành chuỗi CI hoặc coi 288 fault IDs là 288 build độc lập. |

Mã nguồn đối chiếu:
[embedding upstream](../../work/artifacts/falcon/py/embedding_generator.py),
[FL upstream](../../work/artifacts/falcon/py/submodtcp.py),
[metric upstream](../../work/artifacts/falcon/py/metric.py),
[semantic nội bộ](../../hc_falcon/semantic.py),
[greedy nội bộ](../../hc_falcon/greedy.py),
[tích hợp objective](../../hc_falcon/methods.py),
[restricted](../../hc_falcon/restricted.py).

## Kiểm tra thực hiện trong lần audit này

- Kiểm tra mọi hash trong freeze giai đoạn 6, 7, 8; không thay file đã khóa.
- Kiểm tra SHA256 ZIP FALCON với manifest đã pin; bốn file Python upstream
  trên đĩa khớp nguyên byte với ZIP.
- Đọc CSV fault matrix trực tiếp từ ZIP, kiểm tra ID duy nhất, kích thước,
  giá trị nhị phân và mọi cột fault có test phát hiện. Không chạy pickle tùy ý.
- Gọi thân hàm/class gốc bằng AST extraction, dùng fixture CPU nhỏ; không sửa
  nội dung hàm, không tải model và không chạy lại benchmark để chọn kết quả.

| Probe | Upstream | Adapted | Ý nghĩa |
|---|---|---|---|
| Kernel không âm đơn giản | b,a,c | b,a,c | Kiểm tra chung có thể khớp, không chứng minh tương đương tổng quát. |
| Kernel cosine có −1 | c,a,b | a,b,c | Clip âm thay lựa chọn. |
| Kernel toàn 1, input c,b,a | c,b,a | a,b,c | Index tie và FQN tie khác nhau. |
| Hidden states 1,5; token thứ hai padding | Mean=3 | Masked mean=1 | Khác pooling; fixture minh họa, không phải vector UniXcoder thực. |
| q=(2,1), K=diag(0,1), α=0,5 | Raw: a,b | Normalized: b,a | Normalization có thể đổi nghiệm; đã là thiết kế riêng. |

Chart tự chạy trước đây ghi nhận cosine tối thiểu −0,085129 và 1.026 ô âm,
APFD 0,732277526; TSV tác giả UniXcoder/cosine là 0,726314497. Chênh lệch không
chứng minh bản tự chạy tốt hơn paper: revision, môi trường và timing khác.
Cold embedding Chart đã đo khoảng 1.532,54s, không được thay bằng cache-hit
timing khi báo chi phí encoder. Đây là bằng chứng cũ được đọc lại, không phải
experiment mới trong lần audit này.

## Kết quả âm phải giữ

Median paired ΔAPFDc so với History+cost, đơn vị điểm phần trăm:

| Dự án | HC-N v1 | Restricted v1 |
|---|---:|---:|
| Karaf | −1,265 | −0,017 |
| ActiveMQ | −1,407 | −0,154 |
| Log4j | −0,117 | −0,001 |

Cả hai vòng đều đạt 0/3 effect gate. Restricted giảm mức thua nhưng chưa chứng
minh semantic tạo thêm lợi ích so với baseline mạnh. Cả 8 quan sát lỗi N=0 của
restricted nằm ngoài ngân sách 10%; pool q loại N=0 khi còn q dương. Đây là đánh
đổi cấu trúc, không thể mô tả restricted là đã giải quyết cold start.

Raw objective cũng đã chạy: median delta so History+cost khoảng −0,0034;
−0,0185; 0,0000 điểm % cho Karaf/ActiveMQ/Log4j. Vì vậy chỉ quay lại raw không
đủ căn cứ để dự đoán đạt gate. Các số trên là kết quả development, không phải
p-value confirmation. Không đổi tiêu chí thắng sau khi đã xem số liệu.

## Kế hoạch tiếp theo để review

### A. Chốt protocol tái lập artifact trước khi chạy

Giữ sáu suite trong ZIP đã pin; primary UniXcoder/cosine, batch=16, max_length=512,
unmasked pooling, raw cosine, upstream lazy/tolerance/index tie. Dùng adapter CPU
như stage1, giữ model revision cục bộ cố định và ghi rõ khác biệt với môi trường
tác giả chưa xác định. Ghi hash bbox, ordered method IDs, fault matrix, config,
framework, rank order, gains, runtime cold/warm riêng.

Fault mapping và input universe phải kiểm tra 100%, không bỏ method không phát
hiện lỗi. APFD dùng fault IDs và first detection, kiểm tra permutation độc lập.
Không tái sử dụng evaluator LRTS bằng cách biến mỗi failing method thành fault.
Không báo APFDc/TTFF nếu chưa có runtime method hợp lệ. Không tạo history từ thứ
tự số bug ID; dữ liệu hiện có chưa chứng minh chuỗi completion lịch sử.

### B. Tái lập sáu project theo thứ tự cố định

| Thứ tự | Project | Methods | Fault IDs | Công việc |
|---|---|---:|---:|---|
| 1 | Chart | 2.193 | 26 | Kiểm tra cache/config/ranking/APFD của lượt stage1 và tái kiểm chứng; không encode lại nếu cache đúng. |
| 2 | Mockito | 1.292 | 27 | Full embedding/ranking mới. Giữ mapping tên thư mục `mokito` của ZIP. |
| 3 | Lang | 2.239 | 32 | Full embedding/ranking mới. |
| 4 | Math | 2.996 | 30 | Full embedding/ranking mới. |
| 5 | Time | 4.044 | 26 | Full embedding/ranking mới. |
| 6 | Closure | 8.006 | 147 | Chạy sau khi có số đo scale; kernel float32 riêng khoảng 244,5 MiB, chưa gồm tensors/model. |

Tổng 288 fault IDs. Đây là tái lập trên artifact project-level, không phải dựng
và chạy 288 checkout fault versions. Đọc output tác giả để đối chiếu tách biệt
với output tự chạy; không coi output tác giả là replicate mới.

Điều kiện tiếp tục sau mỗi project: đủ inventory, mọi fault có mapping,
APFD độc lập khớp APFD từ cùng order trong sai số 1e-10, vector hữu hạn và
manifest không thay đổi. APFD tự chạy khác TSV tác giả phải báo và điều tra,
không sửa tie/model để ép khớp. Nếu không giải thích được sai khác, giữ nhãn
“tái chạy artifact với môi trường pin”, không tuyên bố tái lập số paper.

Giới hạn tài nguyên đề xuất cho review: peak RSS 8 GiB và tối đa 8 giờ wall-clock
mỗi project; đây là giới hạn vận hành, không phải dự báo thời gian. Nếu vượt,
dừng project, giữ checkpoint/cache, lập phương án tối ưu có kiểm chứng riêng;
không âm thầm chuyển pooling hoặc greedy để kịp thời gian.

### C. Một phép đối chiếu pipeline trên Chart, không tìm cấu hình thắng

Giữ đúng bbox/method IDs và fault matrix Chart; dùng một nhánh so sánh định trước:

1. A: encoder và ranker artifact như bước tái lập ở mục B, tái dùng output Chart hợp lệ.
2. B: cùng vector A; đổi riêng kernel sang clip [0,1], vẫn dùng ranker artifact.
3. C: cùng kernel B; dùng exact greedy FQN nội bộ.
4. D: cùng source methods; dùng pipeline semantic nội bộ đã khóa (preprocess,
   chunk/masked pooling), kernel/ranker như C. Không đưa history giả vào D.

B−A đo thay kernel; C−B đo thay ranker/tie/numeric như một nhóm; D−C đo thay
pipeline encoder/preprocessing như một nhóm, không tách riêng từng thành phần.
Giữ thứ tự, cấu hình và APFD mọi nhánh dù kết quả xấu. Đây là diagnostic một
project, không đủ kết luận ảnh hưởng lên LRTS class-level hay generalization.
Không chọn nhánh tốt nhất rồi thay baseline trong bảng giai đoạn 6.

### D. Chốt đóng góp và điểm dừng

- Nếu thấy bug so với **đặc tả đã khóa**: mô tả trigger, expected/actual, thêm
  kiểm thử hồi quy, tạo phiên bản sửa; sau đó mới đánh giá lại cohort bị ảnh hưởng.
- Nếu chỉ thấy adaptation đã khai báo: giữ kết quả âm; đánh giá giới hạn chuyển
  method-level sang class-level và mối quan hệ giữa semantic coverage với thời gian.
- Nếu tái lập artifact thành công: hoàn tất phần baseline mà đề tài yêu cầu,
  nhưng không tự suy ra HC-FALCON thành công. Đóng gói chứng minh raw/normalized
  objective, giới hạn restricted, raw results và bản thảo kết quả âm/threats.
- Không mở reserved trừ khi có phương án cụ thể qua review và đủ gate. Không
  chạy thêm vòng heuristic/alpha chỉ để tìm kết quả dương. Nhánh Defects4J không
  thay thế hay gộp với các cặp physical-build LRTS trong kiểm định.

Đầu ra cần review cuối bước A–C: manifest mới, sáu bảng APFD/runtime và sai lệch
so tác giả, bảng Chart A/B/C/D, lỗi thực sự nếu có, và quyết định tiếp tục hoặc
giữ kết quả âm. Phần này mới là kế hoạch; chưa chạy A–C trong lần audit hiện tại.

## Bằng chứng và tái lập audit

[JSON audit](../../reports/stage9/fidelity-audit.json) chứa checksum, inventory và
probe; [script](../../scripts/stage9_fidelity_audit.py) chỉ đọc dữ liệu đã pin và
ghi bằng chứng stage9. Chạy:

```powershell
& work/envs/falcon/Scripts/python.exe -B scripts/stage9_fidelity_audit.py
```

Đây là audit đặc tả và code artifact cục bộ, không phải systematic literature
review hay xác nhận metadata/phiên bản mới nhất trên mạng. Chưa chạy encoder
thật để lượng hóa chênh lệch pooling trong lượt này. Probe không bao phủ mọi
đầu vào và không chứng minh code không còn bug.
