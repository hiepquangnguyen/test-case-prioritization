# Giới hạn Nghiên cứu và Các Yếu tố Đe dọa Tính Hợp lệ (Limitations and Threats to Validity)

Tài liệu này phân tích chi tiết và có hệ thống các giới hạn kỹ thuật và bốn nhóm yếu tố đe dọa tính hợp lệ (Threats to Validity) theo chuẩn mực Kỹ thuật Phần mềm Thực nghiệm đối với công trình nghiên cứu **HC-FALCON**.

---

## 1. Độ Giá trị Nội tại (Threats to Internal Validity)

Độ giá trị nội tại xem xét liệu các mối quan hệ nhân quả và kết quả quan sát được có thực sự xuất phát từ các phương pháp được thử nghiệm hay do các lỗi tiềm ẩn trong triển khai phần mềm, môi trường và sai số số học.

### 1.1. Sai số Số học và Hiện tượng Chuẩn hóa Float64 (Numerical Precision & Normalization)
- **Hiện tượng quan sát**: Trong quá trình kiểm tra kiểm toán trên **33.972 lượt ranking** ở Giai đoạn 6, chúng tôi ghi nhận chính xác **8 ngoại lệ** tại điểm cực biên $\alpha = 0.0$ (1 ca ở Karaf, 7 ca ở Log4j), trong đó thứ tự của HC-FALCON không trùng khớp tuyệt đối $100\%$ với baseline `History+cost`.
- **Nguyên nhân kỹ thuật**: Khi chuẩn hóa trọng số $w(t) = q(t) / \sum_j q(j)$ sử dụng dấu phẩy động 64-bit (`np.float64`), phép chia số học tạo ra các sai số làm tròn vi mô ở bậc $10^{-16}$. Một số test case có cùng điểm $q(t)$ gốc sau khi chuẩn hóa bị lệch nhau ở bit cuối cùng (least significant bit), dẫn tới việc cơ chế giải hòa bằng tên FQN bị kích hoạt sai lệch so với việc sắp xếp trực tiếp trên mảng $q(t)$ thô.
- **Biện pháp giảm thiểu**: Các ngoại lệ này chỉ xảy ra ở mức vi mô tại các trường hợp hòa điểm của $\alpha=0.0$, hoàn toàn không làm thay đổi các kết luận thống kê chính của đề tài. Tại Stage 10 và Stage 11, chúng tôi bổ sung ngưỡng dung sai $\varepsilon_{\text{tie}} = 10^{-12}$ trong giải hòa để loại bỏ triệt để hiện tượng này.

### 1.2. Quy tắc Giải hòa Định danh (Tie-Breaking Policy Bias)
- **Quy tắc áp dụng**: Để đảm bảo tính xác định tuyệt đối (determinism) phục vụ tái lập khoa học, tất cả các thuật toán tham lam và baseline trong đề tài đều áp dụng quy tắc giải hòa duy nhất: khi hai test case có điểm lợi ích biên bằng nhau, ưu tiên test có chuỗi tên định danh đầy đủ (FQN) nhỏ hơn theo thứ tự từ điển (alphabet ascending).
- **Nguy cơ đe dọa**: Thứ tự alphabet FQN có thể mang thiên kiến hệ thống gắn liền với cấu trúc đặt tên package (ví dụ: các package bắt đầu bằng `a` như `org.apache.activemq.broker` luôn được xếp trước `org.apache.activemq.transport`).
- **Kiểm chứng độc lập**: Trong thí nghiệm Bridge Chart (Nhánh B vs Nhánh C), việc chuyển từ giải hòa theo chỉ mục ban đầu (`input_index`) sang `fqn_string` làm dịch chuyển 24 vị trí non-detecting tests, nhưng bảo toàn chính xác toàn bộ 26 mốc phát hiện lỗi đầu tiên và giữ nguyên APFD ($0.732278$). Điều này chứng minh tác động của quy tắc tie-breaking lên metric phát hiện lỗi là tối thiểu.

### 1.3. Trôi dạt Môi trường và Phiên bản Thư viện (Environment & Library Drift)
- **Hiện tượng**: Khi tái lập FALCON gốc trên 6 dự án Defects4J (Stage 10), APFD trung bình đạt $0.7260$, lệch nhẹ $+0.0037$ (+0.37 điểm %) so với số liệu của tác giả ($0.7223$).
- **Nguồn gốc**: Mã nguồn tác giả FALCON chạy trên môi trường cũ (năm 2024), trong khi quá trình tái lập độc lập của chúng tôi sử dụng stack phần mềm hiện đại và đã được pin cố định: Python 3.11, PyTorch 2.14.0 và Hugging Face Transformers 5.17.0. Sự khác biệt nhỏ trong kernel tích chập hoặc ma trận embedding của thư viện nền tảng là không thể tránh khỏi. Tuy nhiên, việc dự án Lang đạt độ trùng khớp $100\%$ tuyệt đối ($\Delta = 0.000000$) chứng minh pipeline tái lập của chúng tôi có độ trung thực cực kỳ cao.

### 1.4. Tính Nhất quán của Trạng thái Checkpoint (Checkpoint Resume vs Cold Run)
- Các thí nghiệm quy mô lớn được thiết kế với cơ chế lưu checkpoint nguyên tử (atomic checkpointing). Chúng tôi đã viết bộ kiểm thử tự động chuyên biệt (`tests/test_stage10_reproduction.py`) với 16 test suites độc lập nhằm kiểm tra và xác nhận rằng: việc resume lại từ checkpoint giữa chừng sinh ra đúng $100\%$ các vector padding, ma trận tương đồng và thứ tự ranking so với việc chạy liền mạch từ đầu (uninterrupted run).

---

## 2. Độ Giá trị Ngoại tại (Threats to External Validity)

Độ giá trị ngoại tại đánh giá khả năng khái quát hóa (generalization) của các phát hiện nghiên cứu sang các dự án, ngôn ngữ lập trình và bối cảnh công nghiệp khác.

### 2.1. Giới hạn Phạm vi Dự án LRTS
- **Hiện trạng**: Toàn bộ các kết luận thực nghiệm trên CI dài hạn được rút ra từ 3 hệ thống mã nguồn mở lớn của Apache Software Foundation: **Karaf, ActiveMQ và Log4j2**.
- **Giới hạn**:
  - Cả 3 dự án đều được viết bằng ngôn ngữ **Java**, quản lý phụ thuộc bằng Apache Maven.
  - Các phát hiện chưa được kiểm chứng trên các ngôn ngữ thông dịch động (như Python, JavaScript) nơi không có pha biên dịch tĩnh và thông tin kiểu dữ liệu ngữ nghĩa có thể phân tán hơn.
  - Chưa thử nghiệm trên các hệ thống phát triển bằng C/C++, Rust hoặc Go với các đặc thù về thời gian liên kết (linking time) và bộ kiểm thử đơn vị mức hệ thống.

### 2.2. Độ Mịn của Đơn vị Kiểm thử (Test Granularity: Class-level vs Method-level)
- **Khác biệt cốt lõi**:
  - Trên benchmark **Defects4J**, đơn vị kiểm thử là từng **Test Method** độc lập ($20.770$ methods).
  - Trên benchmark **LRTS**, đơn vị kiểm thử là từng **Test Class** (tổng cộng hàng trăm ngàn lượt chạy class).
- **Ảnh hưởng đến tính khái quát**:
  Trong môi trường CI thực tế của các dự án lớn, chạy kiểm thử ở mức class là chuẩn mực phổ biến để tránh overhead khởi tạo fixture lặp lại. Tuy nhiên, việc gộp nhiều test method vào một class làm loãng tín hiệu biểu diễn ngữ nghĩa của UniXcoder (do phải chia thành nhiều chunk và pooling trung bình). Do đó, kết luận âm của đề tài phản ánh chính xác bài toán **Class-level TCP trên CI thực tế**, và không nên suy diễn rằng Semantic TCP cũng sẽ thất bại trên các bài toán Method-level có chi phí đồng đều.

### 2.3. Môi trường CI Mã nguồn mở so với Môi trường CI Doanh nghiệp (OSS vs Enterprise CI)
- Dữ liệu LRTS phản ánh quy trình CI của các dự án nguồn mở với chu kỳ commit và pull-request tuần tự. Trong các hệ thống CI nội bộ doanh nghiệp lớn (như Google, Meta, Microsoft), các test suite thường được phân tán (sharded) song song trên hàng trăm máy ảo đồng thời, và tỷ lệ test chập chờn (flaky tests) có thể khác biệt so với tập dữ liệu nghiên cứu này.

---

## 3. Độ Giá trị Khái niệm (Threats to Construct Validity)

Độ giá trị khái niệm xem xét liệu các đại lượng đo lường và hàm toán học có phản ánh chính xác mục tiêu thực tế của bài toán hay không.

### 3.1. Sự Tương thích của Metric APFDc Midpoint với Môi trường Đa luồng
- **Giả định của metric**: Công thức $\text{APFDc}_{\text{midpoint}}$ giả định một mô hình thực thi đơn luồng tuần tự hoàn hảo (strictly single-threaded linear execution), trong đó một test chạy chậm sẽ đẩy lùi toàn bộ thời gian của các test phía sau.
- **Thực tế**: Nếu hệ thống CI chạy đa luồng hoặc song song theo từng module Maven, tác động tiêu cực của các test chạy chậm ("Heavy Predecessors") có thể được giảm thiểu một phần nhờ cơ chế đa nhiệm. Tuy nhiên, APFDc Midpoint vẫn là tiêu chuẩn vàng khắt khe nhất hiện nay trong các nghiên cứu học thuật về Cost-cognizant TCP.

### 3.2. Ước lượng Chi phí qua Trung vị Lịch sử
- Chi phí thực thi của test case $c(t)$ được ước lượng thông qua trung vị lịch sử các lần chạy trước (`median past durations`). Trong thực tế, thời gian chạy của test có thể biến động do tải CPU, I/O mạng hoặc trạng thái cơ sở dữ liệu tạm thời. Mặc dù trung vị là một ước lượng thống kê rất vững (robust estimator) trước các giá trị ngoại lai, nó vẫn không thể dự báo chính xác $100\%$ thời lượng của một lần chạy cụ thể trong tương lai.

### 3.3. Khóa Cố định Siêu tham số $\alpha = 0.5$
- Nhằm tránh hiện tượng "dò tìm tham số" (data dredging), đề tài khóa cố định trọng số cân bằng $\alpha = 0.5$ trên biến thể chính `hc_falcon_normalized_v1`.
- Mặc dù bảng phân tích độ nhạy $\alpha \in \{0.0, 0.25, 0.5, 0.75, 1.0\}$ đã được khảo sát toàn diện ở Giai đoạn 6, việc không tinh chỉnh $\alpha$ tối ưu riêng biệt cho từng dự án có thể khiến phương pháp chưa đạt được điểm cân bằng lý tưởng nhất tại từng ngữ cảnh. Tuy nhiên, bảng độ nhạy cho thấy ngay cả khi $\alpha = 0.25$ thì hiệu quả vẫn không vượt qua được $\alpha = 0.0$ (`History+cost`), chứng minh đây là giới hạn bản chất chứ không phải do chọn sai $\alpha$.

### 3.4. Khiếm khuyết Thiết kế của Cổng Kỹ thuật Runtime Overhead trong Stage 12
- **Đặc tả tiền đăng ký**: Giao thức Stage 12 quy định $P95\text{ warm overhead fraction} \le 0{,}10$ (+10%) đo tương đối so với độ trễ xếp hạng của baseline:
  $$\text{Overhead}_{\text{stage}} = \frac{T_{\text{ugcs}} - T_{\text{hc}}}{\max(T_{\text{hc}}, 10^{-9})}$$
- **Khiếm khuyết cấu trúc**: Phương pháp `history_cost` chỉ thực hiện phép sắp xếp mảng đơn giản $O(n \log n)$ với phép chia số học sơ cấp, thời gian xếp hạng chỉ mất khoảng $50 - 100\ \mu\text{s}$ ($10^{-4}\text{ s}$). Yêu cầu một thuật toán tối ưu hóa ngữ nghĩa submodular greedy (vốn phải duyệt ma trận kernel tương đồng qua các vòng lặp) có thời gian chạy không vượt quá $+10\%$ so với phép sort $50\ \mu\text{s}$ này là **bất khả thi về mặt cấu trúc (structurally impossible)**. Mọi thuật toán ngữ nghĩa đều chắc chắn vi phạm cổng này (quan sát thực tế: P95 overhead đạt $12.184\times$).
- **Hệ quả thực tiễn**: Trong môi trường CI/CD thực tế, overhead của bước xếp hạng cần được đo tương đối so với **tổng thời gian thực thi của cả bộ kiểm thử** (ví dụ: mất 50 ms xếp hạng cho build chạy 500 s chỉ chiếm $0{,}01\%$, hoàn toàn chấp nhận được). Tuy nhiên, tuân thủ nguyên tắc tiền đăng ký, đề tài chấp nhận kết quả đánh giá fail-closed và ghi nhận đây là bài học thiết kế giao thức quan trọng.

---

## 4. Độ Giá trị Kết luận (Threats to Conclusion Validity)

Độ giá trị kết luận liên quan đến độ tin cậy của các phép suy luận thống kê và tính xác thực của các kết luận rút ra từ dữ liệu.

### 4.1. Quy mô Mẫu và Năng lực Thống kê (Statistical Power)
- Tổng số build có lỗi được phân tích trong tập Development là **161 physical builds** (79 ở Karaf, 57 ở ActiveMQ và 25 ở Log4j2).
- Mẫu 79 và 57 builds ở Karaf và ActiveMQ là hoàn toàn đủ lớn để các kiểm định phi tham số (Wilcoxon Signed-Rank Test) đạt năng lực thống kê tin cậy cao. Riêng đối với Log4j2 ($25$ builds), kích thước mẫu có phần hạn chế hơn, song xu hướng thất bại ở mức trung vị vẫn nhất quán với hai dự án còn lại.

### 4.2. Dữ liệu Phụ thuộc Thời gian và Hiện tượng Tự tương quan (Non-IID & Autocorrelation)
- Các chu kỳ build trong CI/CD kế thừa mã nguồn từ commit liền trước, do đó các quan sát không hoàn toàn độc lập và phân phối đồng nhất (Non-IID).
- **Biện pháp xử lý**:
  - Tuân thủ nghiêm ngặt giao thức chia tách thời gian (không tráo đổi ngẫu nhiên giữa quá khứ và tương lai).
  - Áp dụng kỹ thuật gộp khối thời gian không chồng lấn ($B = 10$ physical builds) trước khi kiểm định thống kê.
  - Sử dụng phép kiểm định phi tham số Wilcoxon cặp đôi với phương pháp xử lý giá trị 0 của Pratt và ước lượng khoảng tin cậy $95\%$ qua Bootstrap 10.000 lần lặp.

### 4.3. Tuân thủ Tuyệt đối Quy tắc Khoa học — Khóa Tập Reserved Confirmation
- **Nguy cơ tiềm ẩn trong nghiên cứu**: Khi một phương pháp thất bại, các nhà nghiên cứu thường có xu hướng thử nghiệm thêm nhiều biến thể phụ hoặc nới lỏng tiêu chí gate để tìm kiếm kết quả dương, hoặc mở tập dữ liệu holdout để "thử vận may".
- **Chính sách của đề tài**: Dự án tuân thủ nghiêm ngặt hợp đồng khoa học tiên nghiệm:
  - Khi Cổng Hiệu quả đạt **0/3 dự án (NO-GO)** ở Giai đoạn 6, toàn bộ tập dữ liệu **Reserved Confirmation tiếp tục bị KHÓA MẬT MÃ 100%**.
  - Các thử nghiệm ở Giai đoạn 8 (Restricted) và Giai đoạn 11 (CNS-Greedy) đều được thực hiện hoàn toàn trong phạm vi tập Development đã mở, tuyệt đối không xâm phạm tập xác nhận.
  - Khi các biến thể cải tiến vẫn không vượt qua được Cổng Effect Gate $+3.0\%$, đề tài quyết định **kết thúc và công bố kết quả âm trung thực**, bảo vệ tính liêm chính khoa học và ngăn chặn hoàn toàn rủi ro $p$-hacking.

### 4.4. Nguy cơ Đa giả thuyết trên cùng Tập Quan sát (Garden of Forking Paths)
- **Bản chất**: Bốn thế hệ thuật toán liên tiếp (`normalized_v1`, `restricted_v1`, `cns_v1`, `ugcs_v2`) đều được thiết kế, tinh chỉnh và đánh giá trên cùng tập dữ liệu Development (596 build stages).
- **Nguy cơ**: Thử nghiệm lặp lại nhiều giả thuyết trên cùng một tập quan sát dẫn đến rủi ro "Garden of Forking Paths" (Gelman & Loken, 2013), trong đó các heuristic vô tình được tối ưu hóa quá mức cho các đặc tính ngẫu nhiên của tập Development.
- **Biện pháp kiểm soát**: Đề tài kiểm soát rủi ro này bằng cách: (1) Tiền đăng ký (preregistration) toàn bộ mã nguồn, cấu hình và gate của Stage 12 trước khi kích hoạt; (2) Nghiêm cấm hoàn toàn việc quét tham số (tuning rounds = 0); và (3) Giữ niêm phong tuyệt đối 100% tập xác nhận (Reserved Confirmation) khi kết quả sàng lọc là NO-GO, ngăn chặn hoàn toàn thiên kiến công bố (publication bias).

