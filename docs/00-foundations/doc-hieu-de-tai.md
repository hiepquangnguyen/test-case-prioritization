# Đọc hiểu Đề tài 1 và hai công trình nền FALCON, DANTE

## 1. Mục đích và phạm vi

Tài liệu này giải thích bối cảnh, động lực, tư tưởng và khoảng trống nghiên cứu
của Đề tài 1: **Ưu tiên test case bằng tối ưu hóa submodular có xét lịch sử
lỗi và thời gian chạy**. Hai công trình nền là:

- **FALCON: Efficient Test Case Prioritization via Submodular Optimization**;
- **DANTE: Data-Driven Test Case Selection and Prioritization for Long-Running
  Test Suites**.

Tài liệu tập trung trả lời bốn câu hỏi: bài toán cần giải quyết là gì, FALCON và
DANTE giải quyết phần nào của bài toán, phần nào còn thiếu, và HC-FALCON dự kiến
kết hợp hai hướng như thế nào. Các định nghĩa hình thức, công thức, chứng minh và
giả mã được trình bày riêng trong
[Thuật toán và lý thuyết](./thuat-toan-va-ly-thuyet.md).

### 1.1. Quy ước về nguồn

Để không nhầm lẫn đóng góp của paper với thiết kế mới, tài liệu dùng các nhãn:

- **[FALCON]**: nội dung thuộc paper hoặc artifact FALCON;
- **[DANTE]**: nội dung thuộc paper, README hoặc artifact DANTE;
- **[HC-FALCON — đề xuất]**: giả thuyết hay thiết kế của Đề tài 1;
- **[Lựa chọn triển khai]**: quyết định kỹ thuật cần được kiểm chứng thực nghiệm;
- **[Cần kiểm chứng]**: chi tiết chưa đủ bằng chứng để dùng như kết luận khoa học.

## 2. Bối cảnh: phản hồi kiểm thử trong CI/CD

Trong CI/CD, mỗi thay đổi phần mềm có thể kích hoạt hàng trăm hoặc hàng nghìn
test. Chạy toàn bộ test suite giúp giữ độ an toàn nhưng có thể khiến phản hồi lỗi
đến quá muộn. Vấn đề thực tiễn không chỉ là tổng thời gian kiểm thử, mà còn là
**thời điểm lỗi đầu tiên và các lỗi quan trọng được phát hiện**.

Test Case Prioritization (TCP) giữ nguyên tập test và thay đổi thứ tự thực thi.
Nó khác với:

- **Test Case Selection**: chọn một tập con để chạy dưới ngân sách;
- **Test Suite Minimization**: loại bỏ lâu dài các test bị xem là dư thừa;
- **Test Generation**: tạo test mới.

Một thứ tự tốt thường phải cân bằng nhiều mong muốn:

- test có nguy cơ thất bại cao nên xuất hiện sớm;
- test ngắn có thể mang lại phản hồi nhanh hơn;
- phần đầu thứ tự nên đại diện cho nhiều hành vi khác nhau;
- nhiều test gần như trùng nhau không nên chiếm toàn bộ ngân sách đầu;
- test mới, dù chưa có lịch sử, vẫn cần cơ hội được ưu tiên.

## 3. Vì sao APFD và APFDc không phải hàm tối ưu trực tiếp

APFD đo tốc độ tích lũy lỗi theo số test đã chạy. APFDc thay trục số lượng bằng
chi phí hoặc thời gian tích lũy. Hai chỉ số này phù hợp để **đánh giá sau khi đã
biết kết quả**, nhưng tại thời điểm xếp hạng một build mới, ta chưa biết test nào
sẽ fail và test nào sẽ phát hiện lỗi.

Do đó, thuật toán TCP cần một **surrogate objective**: hàm đại diện chỉ sử dụng
thông tin có trước khi thực thi, chẳng hạn:

- mã nguồn của test;
- độ tương đồng giữa các test;
- lịch sử pass/fail của các build trước;
- thời gian chạy ước lượng từ quá khứ;
- nội dung thay đổi trong commit hiện tại.

Hiệu quả của surrogate không được suy ra chỉ từ vẻ hợp lý của nó. Nó phải được
kiểm chứng bằng APFD, APFDc, Time to First Failure và các thước đo ngân sách trên
dữ liệu chưa được nhìn trước.

## 4. Đọc hiểu FALCON

### 4.1. Vấn đề FALCON nhắm tới

Các phương pháp diversity-based giả định rằng test khác nhau có khả năng kích
hoạt các hành vi khác nhau. Các biểu diễn dựa trên chuỗi hoặc token bề mặt có thể
bị ảnh hưởng bởi tên biến, boilerplate và cách viết. **[FALCON]** chuyển test
method sang code embedding nhằm có một biểu diễn giàu ngữ nghĩa hơn, sau đó dùng
độ tương đồng để chọn các test đại diện.

FALCON là một phương pháp black-box theo nghĩa không cần coverage của hệ thống
đang được kiểm thử. Tuy nhiên, nó vẫn cần mã nguồn test để sinh embedding.

### 4.2. Chuỗi xử lý chính

**[FALCON]** có thể được đọc thành bốn bước:

1. trích xuất từng test method;
2. sinh vector embedding bằng mô hình pretrained cho mã nguồn;
3. tạo ma trận tương đồng giữa các test;
4. tối đa hóa hàm facility location bằng greedy/lazy greedy để sinh thứ tự.

Facility location xem test được chọn như một “đại diện” cho các test tương tự.
Khi một vùng ngữ nghĩa đã được đại diện tốt, test gần giống vùng đó mang lại ít
lợi ích bổ sung. Cơ chế diminishing returns này khuyến khích phần đầu thứ tự vừa
đại diện tốt, vừa tránh dư thừa.

### 4.3. Code embedding và độ tương đồng

Embedding ánh xạ test method vào một vector số. Cosine similarity so sánh hướng
của hai vector và thường ít nhạy hơn Euclidean distance đối với độ lớn vector.
Artifact FALCON hỗ trợ nhiều mô hình embedding và cả cosine/Euclidean. README của
artifact khuyến nghị cấu hình UniXcoder–cosine, nhưng mọi con số hiệu năng cụ thể
phải được tái lập trước khi dùng làm kết quả của đề tài.

Không nên diễn giải embedding như bằng chứng rằng hai test chắc chắn thực thi
cùng nhánh. Nó là tín hiệu đại diện học được, có thể bị ảnh hưởng bởi truncation,
pooling, miền huấn luyện và cấu trúc boilerplate.

### 4.4. Vai trò của tối ưu hóa submodular

**[FALCON]** dùng facility location, một hàm monotone submodular khi similarity
không âm. Greedy dưới ràng buộc số phần tử vì thế có bảo đảm xấp xỉ lý thuyết.
Lazy greedy không thay đổi quy tắc chọn của greedy; nó giảm số lần phải tính lại
marginal gain bằng cách tận dụng tính chất marginal gain không tăng khi tập đã
chọn mở rộng.

Điểm quan trọng là bảo đảm này áp dụng cho giá trị của surrogate objective dưới
đúng giả thiết, không trực tiếp bảo đảm tỷ lệ APFD/APFDc tối ưu.

### 4.5. Thiết lập đánh giá và artifact

**[FALCON]** đánh giá trên sáu dự án Defects4J: Chart, Closure, Lang, Math,
Mockito và Time. Artifact trong workspace có dữ liệu test method, fault matrix,
embedding/timing, triển khai FALCON, LOGDET, GRAPHCUT và các baseline FAST.

Vai trò của nhánh Defects4J trong Đề tài 1 là:

- kiểm tra khả năng chạy lại artifact;
- tái lập một phần kết quả semantic TCP;
- xác nhận implementation của facility location và lazy greedy;
- tạo baseline FALCON có thể so sánh công bằng.

### 4.6. Hạn chế liên quan trực tiếp đến đề tài

FALCON mạnh về bao phủ/đa dạng ngữ nghĩa, nhưng surrogate cốt lõi không trực tiếp
mô hình hóa:

- xác suất fail từ lịch sử CI;
- thời gian chạy dự kiến;
- chuỗi build tuần tự và cold start;
- ảnh hưởng của flaky failures.

Điều này không có nghĩa FALCON luôn xếp test chậm hoặc ổn định sai vị trí. Nó chỉ
có nghĩa objective không nhận trực tiếp các tín hiệu đó.

## 5. Đọc hiểu DANTE

### 5.1. Vấn đề DANTE nhắm tới

**[DANTE]** hướng đến test selection và prioritization cho Long-Running Test
Suites trong CI/CD. Thay vì huấn luyện một mô hình dự báo phức tạp, DANTE kết hợp
các tín hiệu có thể cập nhật từ dữ liệu vận hành:

- lịch sử pass/fail;
- tính gần đây hoặc độ bám dính của failure;
- chi phí thực thi;
- độ liên quan văn bản giữa thay đổi mã và test artifact.

README artifact mô tả DANTE là training-free, commit-aware, cost-history-
cognizant và có cơ chế tránh look-ahead bias. Artifact cung cấp runner riêng cho
prioritization và selection, cùng các phân tích duration, flakiness và lookback.

### 5.2. Failure history và stickiness

Một failure thật có thể kéo dài qua nhiều build cho đến khi được sửa. Một flaky
failure thường xen kẽ pass/fail do môi trường, thời gian, concurrency hoặc phụ
thuộc bên ngoài. “Stickiness” khai thác cấu trúc thời gian này thay vì chỉ đếm
tổng số lần fail.

Wilson confidence interval được dùng để tránh tin quá mức vào tỷ lệ quan sát từ
mẫu nhỏ. Ý nghĩa cần giữ đúng là: khoảng ước lượng rộng biểu thị bất định cao;
không được xem một lần fail duy nhất là xác suất fail chắc chắn bằng một.

Chi tiết định nghĩa cửa sổ, cách tổng hợp confidence và công thức score phải lấy
từ paper/artifact đã pin. Một tỷ lệ fail đơn giản trong 10 lần gần nhất chỉ là
baseline recency, không tự động tương đương failure stickiness của DANTE.

### 5.3. Commit relevance và cost awareness

**[DANTE]** dùng Information Retrieval, trong đó có TF-IDF, để liên kết nội dung
thay đổi với test. Tín hiệu này hữu ích khi một test chưa có failure gần đây
nhưng liên quan mạnh đến vùng vừa sửa.

Cost awareness ưu tiên giá trị phát hiện lỗi trên một đơn vị thời gian. Đây là
động lực phù hợp với APFDc và ngân sách test, nhưng phép chia trực tiếp cho thời
gian rất nhỏ có thể gây mất ổn định. Khi tái hiện, phải dùng đúng cách xử lý cost
của artifact thay vì suy đoán từ mô tả khái quát.

### 5.4. Điểm mạnh và giới hạn đối với đề tài

DANTE bổ sung phần FALCON còn thiếu: trạng thái động của CI, cost, commit context
và robustness đối với flaky data. Tuy nhiên, một xếp hạng pointwise theo score
không nhất thiết kiểm soát sự dư thừa giữa các test cùng được xếp cao. Nhiều test
có score lớn có thể cùng đại diện cho một vùng hành vi.

Nhận định “DANTE không có within-set semantic diversity” là động lực nghiên cứu
cần được kiểm chứng trên đúng cấu hình artifact, không nên biến thành tuyên bố
rằng DANTE không có bất kỳ cơ chế diversity nào trong mọi tác vụ.

## 6. Quan hệ bổ sung giữa FALCON và DANTE

| Khía cạnh | FALCON | DANTE | HC-FALCON dự kiến |
| --- | --- | --- | --- |
| Tín hiệu chính | Semantic similarity giữa test | History, cost, commit relevance | Semantic + history + cost |
| Cách xếp hạng | Tối ưu tập hợp | Score/heuristic theo artifact | Tối ưu tập hợp |
| Within-set redundancy | Được xử lý bởi facility location | Không phải trọng tâm chính | Được xử lý bởi facility location |
| Chuỗi build CI | Không phải trọng tâm | Trọng tâm | Rolling evaluation |
| Cost | Không nằm trong objective cốt lõi | Có | Hạng modular cost-aware |
| Bảo đảm submodular | Có cho surrogate | Không phải đóng góp trung tâm | Cần chứng minh |
| Cold start | Dựa vào semantic | Phụ thuộc fallback/context | Semantic fallback |

Bảng trên là bản đồ khái niệm, không phải kết luận rằng một phương pháp luôn tốt
hơn phương pháp kia. Hai paper có dataset, mục tiêu và protocol khác nhau; không
được so sánh trực tiếp các con số giữa chúng nếu chưa tái lập chung một pipeline.

## 7. Khoảng trống nghiên cứu

Khoảng trống mà Đề tài 1 kiểm tra là: có thể kết hợp **độ đại diện ngữ nghĩa của
một tập test** với **rủi ro lỗi và chi phí của từng test** trong một objective vẫn
monotone submodular hay không, và sự kết hợp đó có cải thiện phát hiện lỗi sớm
trên chuỗi CI thực tế hay không.

Đây là giả thuyết nghiên cứu, chưa phải kết quả. Không được tuyên bố đây là công
trình đầu tiên kết hợp diversity với history/cost nếu chưa hoàn thành khảo sát
FAST, history-based/cost-aware TCP, fault-proneness diversification và các TCP
approach combinator.

## 8. Ý tưởng HC-FALCON

### 8.1. Trực giác

**[HC-FALCON — đề xuất]** giữ facility location làm tín hiệu phụ thuộc tập hợp,
sau đó cộng một trọng số không âm cho từng test dựa trên history và cost. Hạng
thứ hai là modular: giá trị của một test không phụ thuộc test nào đã được chọn.
Tổng không âm của một hàm monotone submodular và một hàm modular không âm vẫn là
monotone submodular.

Ở mỗi vòng greedy, một test có thể được ưu tiên vì:

- mở rộng vùng semantic chưa được đại diện;
- có rủi ro fail lịch sử cao và đủ tin cậy;
- có chi phí dự kiến hợp lý;
- hoặc kết hợp các yếu tố trên.

### 8.2. Cold start và flaky tests

Test mới không có lịch sử không nên bị gán rủi ro cao một cách tùy tiện. Khi
thành phần history bằng 0 hoặc bị co về prior, test vẫn có thể lên sớm nhờ
semantic novelty. Cách này chỉ hoạt động khi trọng số semantic khác 0 và ma trận
similarity đủ phân giải.

Flaky robustness không được suy ra chỉ từ Wilson confidence. Cần định nghĩa rõ
flaky label, stickiness, cửa sổ lịch sử và đánh giá riêng failure thật/flaky.

### 8.3. Cân bằng hai thành phần

Việc chia facility location cho số test đưa nó về trung bình coverage, nhưng
tổng các trọng số history–cost vẫn có thể tăng theo độ dài prefix. Do đó, tham số
trộn không tự động có cùng ý nghĩa giữa các project hoặc ngân sách.

**[Lựa chọn triển khai]** cần so sánh ít nhất các cách hiệu chỉnh:

- chuẩn hóa hoặc chặn điểm từng test;
- chia hạng modular theo ngân sách hay thống kê suite;
- hiệu chỉnh robust theo quantile;
- sensitivity analysis cho trọng số trộn.

Không được chọn cách chuẩn hóa sau khi nhìn kết quả test của build đánh giá.

## 9. Câu hỏi nghiên cứu

- **RQ1 — Effectiveness:** HC-FALCON có cải thiện APFDc/TTFF so với FALCON,
  DANTE và các history baseline không?
- **RQ2 — Contribution:** Semantic, history, confidence và cost đóng góp bao
  nhiêu qua ablation?
- **RQ3 — Robustness:** Phương pháp phản ứng thế nào với test mới, lịch sử thưa
  và flaky failures?
- **RQ4 — Efficiency:** Chi phí embedding, similarity và prioritization có phù
  hợp với CI/CD không?

## 10. Khung đánh giá dự kiến

### 10.1. Datasets

- Defects4J/artifact FALCON dùng cho replication semantic baseline.
- Tối thiểu ba dự án LRTS dùng cho rolling evaluation theo thời gian.

Defects4J và LRTS phục vụ hai mục đích khác nhau. Không nên giả lập history cho
Defects4J theo cách tạo ra thông tin không tồn tại trong thiết kế dataset.

### 10.2. Baselines

- Random với nhiều seed;
- Shortest-Test-First;
- MostFail và Latest/RecentFail;
- FAST theo cấu hình tái lập được;
- FALCON;
- DANTE nếu artifact chạy được trên dữ liệu chọn;
- phép trộn thứ hạng đơn giản giữa semantic và history.

### 10.3. Ablation

- semantic-only;
- history-only;
- history + cost;
- semantic + history;
- HC-FALCON đầy đủ;
- HC-FALCON bỏ confidence.

### 10.4. Metrics và thống kê

- APFD khi chi phí test có thể xem là đồng đều;
- APFDc với duration thực tế chỉ dùng để đánh giá sau ranking;
- Time to First Failure;
- fault/failing-test recall tại 10%, 25% và 50% ngân sách;
- prioritization runtime và peak memory;
- Friedman khi so sánh nhiều phương pháp;
- Wilcoxon signed-rank cho dữ liệu bắt cặp;
- Holm correction cho nhiều so sánh;
- effect size đi cùng p-value.

Đơn vị bắt cặp phải được xác định trước, ví dụ cùng build giữa hai phương pháp.
Không nên trộn mọi build của mọi project như các quan sát độc lập nếu cấu trúc
phân cấp và tương quan thời gian chưa được xử lý.

## 11. Nguyên tắc chống rò rỉ dữ liệu

Khi xếp hạng build $b$, thuật toán chỉ được dùng:

- mã nguồn test và commit context có tại thời điểm bắt đầu build $b$;
- kết quả và duration từ các build trước $b$;
- embedding/model đã được tạo mà không nhìn verdict của $b$.

Verdict và duration quan sát của build $b$ chỉ được dùng để đánh giá, rồi cập
nhật tracker sau khi ranking/evaluation hoàn tất. Duration dùng trong objective
phải là ước lượng từ quá khứ; duration thực tế của build hiện tại là ground truth
đánh giá và không được truyền vào ranker.

## 12. Những kết luận chưa được phép giả định

Trước thực nghiệm, chưa được kết luận rằng:

- HC-FALCON tốt hơn FALCON hoặc DANTE;
- confidence chắc chắn giảm tác động của mọi flaky test;
- UniXcoder luôn là embedding tốt nhất trên LRTS;
- lazy greedy luôn đạt một độ phức tạp trung bình cố định;
- GPU luôn làm preparation time không đáng kể;
- một giá trị trọng số trộn dùng tốt cho mọi project.

Mục tiêu pilot cải thiện trung vị 3–5% là tiêu chí go/no-go, không phải kết quả
được phép điền trước.

## 13. Tài liệu và artifact trong workspace

- `topic1.md`: mô tả chính thức của Đề tài 1;
- `falcon-icst-2026.pdf`: paper FALCON;
- `falcon/falcon.zip`: artifact FALCON;
- `dante-icst-2026.pdf`: paper DANTE;
- `dante/readme.md`: hướng dẫn artifact DANTE;
- `dante/ML_TCSP.zip`: artifact DANTE/LRTS.

Các trích dẫn thư mục, DOI, phiên bản artifact và checksum cần được bổ sung vào
bibliography/manifest trước khi viết bản thảo công bố.
