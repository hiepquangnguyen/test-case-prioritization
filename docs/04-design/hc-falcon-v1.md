# Đặc tả HC-FALCON v1 — quyết định thiết kế giai đoạn 4

Ngày 2026-09-13. Đây là đặc tả để triển khai giai đoạn 5, **chưa phải thuật toán
đã chạy**. Config máy đọc được: [hc-falcon-v1.json](../../configs/hc-falcon-v1.json).
Baseline và protocol stage1–3 không bị sửa.

## 1. Phạm vi và ranh giới dữ liệu

T_b là toàn bộ class records quan sát của một build-stage LRTS. Không đổi ID,
không bỏ record vì source/duration thiếu. Source mapping tại SHA metadata được
gọi là matched_declared_revision; không đồng nghĩa đã xác minh revision thực
thi CI. Mọi kết luận có điều kiện trên inventory đã qua xử lý upstream.

History giữ nguyên v2: cùng project/base branch/stage, khác physical build,
status SUCCESS/FAILURE/UNSTABLE, available_at=start+duration+2 giây < cutoff.
Chỉ feedback đã quan sát; missing/unknown không thêm PASS. Không dùng outcomes,
actual duration hoặc build result hiện tại để tính gain. Snapshot, kernel và
tham số cố định trong suốt ranking. N=0 khác test đã PASS nhiều lần.

## 2. Estimator và kiểm tra thang đo

Giữ estimator đã triển khai, không thêm decay/stickiness ở v1:

```text
p(t) = (failures(t) + 1) / (observations(t) + 2)
conf(t) = observations(t) / (observations(t) + 5)
r(t) = conf(t) * p(t)
c_ref = median(positive past durations in context), fallback 1 second
c(t) = median(positive past durations of t), fallback c_ref
c(t), c_ref >= 1e-6 second
q(t) = r(t) / (sqrt(c(t)/c_ref) + 1e-8)
```

Trong 317 build development Karaf đã được xem, Q=sum(q) có median 2,271078,
max 43,639875; 316 build có Q>1. Trong khi similarity trong [0,1] bảo đảm
FL(S)/n<=1. Đây là bằng chứng **khác thang đo tổng objective**, chưa chứng minh
thành phần nào chi phối mọi marginal hoặc normalization làm score tốt hơn.
[objective-scale.json](../../reports/stage4/objective-scale.json) lưu tính toán.

## 3. Hai objective được đặt tên riêng

Với M là mask source hợp lệ, K(u,t)=0 nếu u hoặc t không có source hợp lệ.
Đặt FL(S)=sum_{u in T_b} max_{t in S} K(u,t), max rỗng bằng 0. Các hàng ngoài
M đóng góp 0; denominator **vẫn là n=|T_b|**, không đổi sang số test có source.

**Biến thể chính HC-FALCON-N v1 (`hc_falcon_normalized_v1`):**

```text
Q = sum_{t in T_b} q(t)
w(t) = q(t)/Q if Q>0 else 0
F_N(S) = alpha * FL(S)/n + (1-alpha) * sum_{t in S} w(t)
alpha = 0.5
gain(x | S) = alpha/n * sum_u max(0, K(u,x)-coverage[u])
              + (1-alpha)*w(x)
```

Đây là **thay đổi có chủ đích so với công thức topic1.md**, chuẩn hóa tổng
modular về 1 để hai thành phần cùng bị chặn trên bởi 1. Q chỉ phụ thuộc các
ước lượng quá khứ của inventory hiện tại, không dùng outcome hiện tại. Không
thêm epsilon vào Q: Q=0 được xử lý riêng, không tạo weight giả.

**Đối chứng bắt buộc `hc_falcon_topic_raw_v1`:** giữ nguyên công thức đề tài
`alpha*FL(S)/n + (1-alpha)*sum(q(t))`, cùng alpha=0.5 và mọi input còn lại.
Không đổi tên normalization rồi báo là đã thực hiện đúng nguyên công thức cũ.
Tại cùng alpha, hai objective là hai phương pháp khác nhau.

Không tune alpha theo score trong mốc này. Sensitivity đã chốt 0, .25, .5,
.75, 1; alpha=.5 là cấu hình chính. Nếu pilot khiến phải đổi thiết kế, tạo
v2 trước khi mở score reserved confirmation, không sửa lại v1 theo kết quả tail.

Q=0: chỉ semantic đóng góp khi alpha>0. n=0: trả ranking rỗng, không chia n.
M rỗng: semantic bằng 0; ranking hybrid theo history/cost. Q=0 và M rỗng:
FQN tăng dần. Alpha=0 tương đương thứ tự History+cost; alpha=1 là FL thuần.
Không tự đổi alpha hoặc đưa test mới lên đầu bằng luật ngoài objective.

## 4. Semantic pipeline đã chọn

| Thành phần | Quyết định |
|---|---|
| Source | Toàn compilation unit tại SHA metadata có mapping duy nhất. Nested class dùng file outer và gắn cờ. Không trộn source khác revision. |
| Preprocessing | Decode UTF-8 strict, bỏ BOM đầu file, CRLF/CR về LF; bỏ comment Java bằng lexer giữ nguyên string/char/text block và giữ khoảng trắng phân cách token. UTF-8 lỗi là semantic unavailable, không thay ký tự âm thầm. |
| Encoder | microsoft/unixcoder-base, revision 5604afdc964f6c53782a6813140ade5216b99006; AutoTokenizer/AutoModel như nhánh artifact đã kiểm tra. |
| Input dài | Tokenize không special token; payload 512 trừ số special token của tokenizer; chunk không overlap, giữ tối đa 16 chunk đầu. Lưu token_count/chunks/truncation_fraction. |
| Pooling | Mean last_hidden_state theo attention mask (gồm special token không phải padding). Mean các vector chunk với trọng số số payload token, rồi L2 normalize. Không lấy mean cả padding như artifact FALCON. |
| Similarity | Float32 cosine của vector chuẩn hóa, clip về [0,1]; diagonal source hợp lệ bằng 1. |
| Source thiếu/ambiguous | Zero row/column, kể cả diagonal; không tạo embedding từ tên test. Pure FL dùng FQN để phá hòa; hybrid vẫn có history/cost. |
| Bất thường | Empty sau preprocessing hoặc zero-norm -> unavailable có lý do; nonfinite vector/kernel -> lỗi dừng, không tự ghi score. |

Đây là pipeline **adaptation cho class-level LRTS**, khác preprocessing/pooling
method-level của FALCON nguyên bản. Khi tái lập Defects4J giữ runner gốc riêng.
Chunking giảm mất nội dung nhưng cap 16 vẫn có thể cắt test dài; phải báo tỷ lệ
truncation. Không giả định file đầy đủ chính là class body đã được thực thi.

Cache embedding theo raw source SHA-256, preprocessing version, encoder/tokenizer
revision và hash config tokenizer, chunk/pooling config, framework versions,
dtype/device. Lưu hash vector; không dùng mtime/path làm cache identity. Test ID
khác nhau có thể dùng chung vector nhưng vẫn là hai candidate khác nhau.
Cache kernel theo ordered IDs/mask/vector hashes và similarity config. Cache
không chứa outcome. Khóa model/dependency thực thi bằng manifest ở giai đoạn 5.

## 5. Thuật toán và tính đúng

Standard greedy là bản tham chiếu; lazy greedy dùng heap upper bounds với
coverage[u] hiện tại. Mỗi lần chọn lưu semantic_gain, modular_gain, total_gain,
coverage update và vị trí. Gain float64; tie bằng nhau chính xác dùng FQN tăng
dần. Không thêm tolerance để chấp nhận candidate có gain thấp hơn. Tolerance
chỉ dùng khi so sai số số học trong kiểm thử, không phải quy tắc xếp hạng.

Với kernel hữu hạn không âm, mỗi hàng max là monotone submodular: khi coverage
đã lớn hơn, lợi ích thêm một cột không tăng. Tổng các hàng và phép chia n>0
giữ tính chất này. w(t)>=0 cố định làm sum(w) modular không âm. Tổ hợp với
alpha trong [0,1] cũng monotone submodular, F(empty)=0. Q phụ thuộc inventory
đóng băng, không phụ thuộc S nên normalization không phá tính modular.

Greedy có bảo đảm 1-1/e cho objective dưới cardinality k; prefix của full greedy
là greedy cho k tương ứng. **Không suy ra bảo đảm APFD, APFDc hoặc ngân sách
thời gian B**. Lazy phải trả cùng greedy theo tie-break, không tự là thuật toán
approximate mới. Standard dùng O(n^2) lần tính marginal cho full ranking,
mỗi lần O(n): O(n^3) sau khi có kernel. Lazy giảm số lần đánh giá trong thực tế,
nhưng worst-case vẫn O(n^2) gain evaluations, kèm heap; không hứa O(n log n).
Kernel dense O(n^2) memory, coverage/heap O(n), embeddings O(nd).

## 6. Hợp đồng nghiệm thu trước khi chạy pilot

Giai đoạn 5 phải kiểm tra: ví dụ tính tay gain/objective; standard-lazy cùng
ranking; n=0/1; q=0; mask toàn 0; duplicate source nhưng ID khác; alpha endpoints;
negative cosine đã biến đổi; cache invalidation; chunk/padding invariance;
current/future outcome/duration không đổi kernel/features/ranking. Source mask
được dựng bằng provenance, không theo outcome. Chưa có các kiểm thử semantic
này ở stage4; bộ test hiện tại chỉ xác nhận audit/split và nền replay.
