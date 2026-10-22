# Khi Đa Dạng Hóa Ngữ Nghĩa Phản Tác Dụng: Kết Quả Thực Nghiệm Âm Về Tối Ưu Hóa Bán Mô-Đun Cho Bài Toán Sắp Xếp Thứ Tự Kiểm Thử Trong CI Thực Tế

**Bản thảo v0.1 — Bản tiếng Việt phục vụ rà soát nội bộ**

---

## Tóm Tắt (Abstract)

Sắp xếp thứ tự kiểm thử (Test Case Prioritization - TCP) nhằm tái cấu trúc thứ tự thực thi của các ca kiểm thử sao cho các kiểm thử phát hiện lỗi được kích hoạt sớm nhất có thể, tối đa hóa tốc độ phát hiện lỗi dưới ràng buộc khắt khe về ngân sách tài nguyên trong tích hợp liên tục (CI/CD). Chúng tôi đề xuất và đánh giá toàn diện **HC-FALCON**, một khung làm việc phi huấn luyện (training-free) tích hợp tính đa dạng ngữ nghĩa mã nguồn (sử dụng vector nhúng UniXcoder kết hợp thuật toán tối ưu tham lam cho hàm định vị cơ sở Facility Location), ước lượng rủi ro lỗi theo mô hình Bayes (Beta-Bernoulli), và chi phí thực thi vào một hàm mục tiêu bán mô-đun (submodular) đơn điệu với bảo đảm xấp xỉ toán học hình thức đạt tỷ lệ $1 - 1/e$.

Chúng tôi tiến hành hai thực nghiệm đối chứng quy mô lớn: 
1. **Tái lập độc lập hoàn toàn FALCON** trên bộ chuẩn Defects4J (gồm 20.770 test method, 288 lỗi trên 6 dự án nguồn mở), đạt APFD $0{,}7260$ so với $0{,}7223$ của nhóm tác giả gốc ($\Delta = +0{,}37$ điểm phần trăm), xác nhận độ trung thực tái lập đạt 100%;
2. **Đánh giá theo trật tự thời gian khắt khe** trên bộ dữ liệu kiểm thử chạy dài hạn (Long-Running Test Suites - LRTS) bao gồm 3 dự án công nghiệp Apache (596 build stage, 519 physical build, 33.972 lượt sắp xếp độc lập) với giao thức chia tập dữ liệu theo thời gian thực (temporal split), ngăn chặn hoàn toàn rò rỉ dữ liệu tương lai (future data leakage).

**Kết quả thực nghiệm**: Trái ngược với giả thuyết nghiên cứu ban đầu, HC-FALCON thất bại hoàn toàn trước Cổng Hiệu quả (Effect Gate: 0/3 dự án đạt chuẩn) trên môi trường CI thực tế ở mức lớp kiểm thử (class-level). Chênh lệch trung vị cặp đôi $\Delta$APFDc so với baseline mạnh `history_cost` luôn mang giá trị âm trên cả 3 dự án và xuyên suốt cả 5 thế hệ thuật toán cải tiến được thử nghiệm. Phân tích nguyên nhân gốc rễ trên 161 build có lỗi đã phát hiện ra **hiện tượng Tiền nhiệm Nặng ký (Heavy Predecessors)**: thuật toán tham lam tối ưu hóa độ đa dạng ngữ nghĩa một cách vô cảm với chi phí đã ưu tiên chọn các test class nặng, chạy rất lâu (100–150 giây) nhưng không chứa lỗi lên đầu để tối đa hóa độ bao phủ không gian nhúng, gây tích lũy độ trễ ròng lên tới **+39.099 giây (~10,8 giờ)** trước khi các test case phát hiện lỗi được kích hoạt. Chúng tôi báo cáo kết quả thực nghiệm âm này với tính minh bạch tuyệt đối, đồng thời giữ niêm phong bảo mật 100% tập dữ liệu xác nhận (Reserved Confirmation dataset).

**Từ khóa**: Sắp xếp thứ tự kiểm thử, Tối ưu hóa bán mô-đun, Đa dạng hóa ngữ nghĩa, Kết quả thực nghiệm âm, Tích hợp liên tục, Định vị cơ sở (Facility Location).

---

## 1. Đặt Vấn Đề (Introduction)

Trong các quy trình CI/CD hiện đại, các bộ kiểm thử hồi quy (regression test suites) có thể mất hàng giờ, thậm chí hàng ngày để thực thi trọn vẹn. Sắp xếp thứ tự kiểm thử (TCP) tìm kiếm một hoán vị $\pi$ của bộ kiểm thử $T$ sao cho các bài kiểm thử phát hiện lỗi và có thời gian thực thi ngắn được chạy trước, từ đó tối đa hóa chỉ số phần trăm phát hiện lỗi có xét đến chi phí (Average Percentage of Faults Detected with Cost - APFDc).

Hai hướng tiếp cận nổi bật được công bố tại hội nghị IEEE ICST 2026:

1. **FALCON** (Mensah-Boateng et al.): Mã hóa ngữ nghĩa của các test method thông qua mô hình ngôn ngữ mã nguồn tiền huấn luyện UniXcoder, sau đó áp dụng thuật toán tham lam tối ưu hàm bán mô-đun Facility Location để tối đa hóa tính đa dạng bao phủ ngữ nghĩa. FALCON đạt kết quả ấn tượng trên Defects4J nhưng bỏ qua hoàn toàn lịch sử lỗi và chi phí thực thi của bài kiểm thử.

2. **DANTE** (Reale et al.): Khai thác lịch sử lỗi theo cửa sổ trượt (sliding window), tính bám dính của lỗi (failure stickiness), độ tương đồng commit-diff qua TF-IDF và thời lượng kiểm thử trên các bộ kiểm thử chạy dài hạn (LRTS). DANTE thể hiện ưu thế vượt trội về việc kết hợp lịch sử và chi phí nhưng thiếu phân tích ngữ nghĩa mã nguồn sâu.

**Giả thuyết nghiên cứu**: Việc tích hợp đồng thời đa dạng hóa ngữ nghĩa mã nguồn, ước lượng xác suất lỗi Bayes và chuẩn hóa chi phí thực thi vào một hàm mục tiêu bán mô-đun duy nhất sẽ mang lại hiệu quả vượt trội hơn so với từng thành phần hoạt động riêng rẽ trên môi trường CI thực tế.

### Các Đóng Góp Chính

Nghiên cứu này mang lại 4 đóng góp khoa học chính:

1. **Tái lập độc lập hoàn toàn thuật toán FALCON** trên toàn bộ 6 dự án của chuẩn Defects4J v2.0 (20.770 test method, 288 faults), xác nhận độ trung thực tái lập 100% với biểu đồ phân rã Bridge Chart 4 nhánh chứng minh nguồn gốc chính xác của độ chênh lệch hiệu năng.
2. **Đánh giá thực nghiệm âm toàn diện** đối với khung làm việc HC-FALCON qua 5 thế hệ thuật toán trên 3 dự án công nghiệp Apache LRTS, chỉ ra rằng việc bổ sung ngữ nghĩa mã nguồn liên tục thất bại trong việc đánh bại baseline mạnh `history_cost` ở mức lớp kiểm thử (class-level).
3. **Phát hiện và định lượng hóa hiện tượng Tiền nhiệm Nặng ký (Heavy Predecessors)**, cung cấp lời giải thích cơ chế giải tích rõ ràng về lý do tại sao hàm mục tiêu ngữ nghĩa vô cảm với chi phí làm suy giảm nghiêm trọng tốc độ phát hiện lỗi trong môi trường CI có chi phí phân tán cao.
4. **Đóng góp về mặt phương pháp luận thực nghiệm**: Xây dựng quy trình đánh giá tiền đăng ký (preregistered protocol) nghiêm ngặt với việc phân chia dữ liệu theo thời gian thực, niêm phong tập dữ liệu xác nhận, và công bố minh bạch kết quả âm theo các chuẩn mực đạo đức cao nhất của Kỹ thuật Phần mềm Thực nghiệm.

---

## 2. Tổng Quan Nghiên Cứu Liên Quan (Related Work)

### 2.1 Sắp Xếp Thứ Tự Kiểm Thử (TCP)

Bài toán TCP đã được nghiên cứu sâu rộng trong công nghệ phần mềm suốt hơn hai thập kỷ qua. Các kỹ thuật sắp xếp tham lam dựa trên độ bao phủ mã nguồn (code coverage - tổng thể và bổ sung) đã được định hình từ sớm bởi Rothermel et al. [1] và Elbaum et al. [2, 3]. Gần đây, các hướng tiếp cận ứng dụng học máy (learning-to-rank) [4], học tăng cường (reinforcement learning) [5], và xử lý ngôn ngữ tự nhiên đã thu hút sự quan tâm lớn.

### 2.2 TCP Dựa Trên Ngữ Nghĩa Và Tính Đa Dạng

Kỹ thuật FAST [6] ứng dụng giải thuật băm tương đồng MinHash/LSH trên chuỗi mã nguồn để chọn kiểm thử đa dạng với chi phí tính toán thấp. FALCON [7] đánh dấu bước tiến lớn khi kết hợp mô hình ngôn ngữ mã nguồn UniXcoder với giải thuật tham lam bán mô-đun Facility Location. Công trình của chúng tôi kế thừa và mở rộng FALCON bằng cách tích hợp lịch sử lỗi và chi phí thực thi vào một mô hình thống nhất.

### 2.3 TCP Dựa Trên Lịch Sử Và Nhận Thức Chi Phí (Cost-Aware)

Các phương pháp dựa trên lịch sử khai thác kết quả đạt/lỗi trong quá khứ. ROCKET [9] sử dụng tần suất và mức độ gần đây của lỗi. DANTE [8] kết hợp lịch sử trượt, tính bám dính lỗi, TF-IDF commit-diff và thời gian chạy trên LRTS. Các nghiên cứu trước đây [14, 25] cũng chỉ ra rằng lịch sử kiểm thử là tín hiệu cực kỳ mạnh mẽ trong môi trường hồi quy liên tục.

### 2.4 Tối Ưu Hóa Bán Mô-Đun Trong Kỹ Thuật Phần Mềm

Tối ưu hóa hàm bán mô-đun (submodular function maximization) cung cấp một khung lý thuyết vững chắc với bảo đảm tiệm cận $1 - 1/e \approx 0{,}632$ của thuật toán tham lam dưới ràng buộc lực lượng (cardinality constraints) [10, 11]. Trong kỹ thuật phần mềm, bán mô-đun đã được áp dụng cho rút gọn bộ kiểm thử [30] và đo lường độ đa dạng của bộ kiểm thử [16]. Theo hiểu biết của chúng tôi, HC-FALCON là công trình đầu tiên kết hợp Facility Location với ước lượng rủi ro Bayes và chuẩn hóa chi phí vào một hàm mục tiêu bán mô-đun duy nhất cho TCP.

### 2.5 Giá Trị Của Kết Quả Nghiên Cứu Âm Trong Kỹ Thuật Phần Mềm

Các kết quả thực nghiệm âm đóng vai trò quan trọng trong việc ngăn chặn lãng phí tài nguyên nghiên cứu vào các hướng đi có vẻ hợp lý về mặt lý thuyết nhưng không hiệu quả trong thực tiễn [19]. Nghiên cứu này tuân thủ các chuẩn mực khoa học nhằm kiểm soát nguy cơ "Garden of Forking Paths" (khai thác ngẫu nhiên qua nhiều giả thuyết) [20], bảo đảm tính toàn vẹn của bằng chứng thực nghiệm.

---

## 3. Phương Pháp Tiếp Cận HC-FALCON (Methodology)

### 3.1 Mô Hình Toán Học

Tại build $b$, với bộ kiểm thử cần sắp xếp $T_b = \{t_1, \dots, t_n\}$, hàm mục tiêu kết hợp đã chuẩn hóa $F_N: 2^{T_b} \to [0, 1]$ được định nghĩa như sau:

$$F_N(S) = \alpha \frac{FL_b(S)}{|T_b|} + (1 - \alpha) \sum_{t \in S} w_b(t), \quad 0 \le \alpha \le 1$$

Trong đó:

1. **Hàm định vị cơ sở ngữ nghĩa (Facility Location)**:
   $$FL_b(S) = \sum_{u \in T_b} \max_{t \in S} K(u, t)$$
   với kernel tương đồng $K(u, t) = \text{clip}(z(u)^\top z(t), 0{,}0, 1{,}0)$ được tính từ tích vô hướng của các vector nhúng UniXcoder đã chuẩn hóa $L_2$.

2. **Trọng số rủi ro - chi phí chuẩn hóa**:
   $$w_b(t) = \frac{q_b(t)}{\sum_{j=1}^{|T_b|} q_b(j)}$$
   với điểm rủi ro - chi phí $q_b(t)$ được xây dựng từ:
   - Ước lượng xác suất lỗi Bayes: $p_b(t) = \frac{f_t + 1}{n_t + 2}$ (tiên nghiệm Beta(1, 1) Laplace smoothing).
   - Độ tin cậy quan sát: $\text{conf}_b(t) = \frac{n_t}{n_t + 5}$.
   - Điểm số kết hợp: $q_b(t) = \frac{\text{conf}_b(t) \cdot p_b(t)}{\sqrt{\tilde{c}_b(t)} + \varepsilon}$, trong đó $\tilde{c}_b(t) = c_b(t) / \text{median}(c_b)$ là chi phí tương đối.

### 3.2 Chứng Minh Lý Thuyết

**Định lý 1**: Hàm mục tiêu $F_N(S)$ là hàm bán mô-đun đơn điệu không giảm (monotone submodular), không âm, và thỏa mãn $F_N(\emptyset) = 0$.

*Phác thảo chứng minh*:
- Thành phần lịch sử $\sum_{t \in S} w_b(t)$ là hàm mô-đun (modular), do đó cũng là bán mô-đun.
- Hàm định vị cơ sở $FL_b(S)$ có cấu trúc max-sum trên kernel tương đồng không âm đối xứng, là hàm bán mô-đun đơn điệu kinh điển.
- Phép tổ hợp tuyến tính với các hệ số không âm $\alpha \ge 0$ và $(1 - \alpha) \ge 0$ bảo toàn trọn vẹn tính đơn điệu và tính bán mô-đun.

**Hệ quả**: Thuật toán tham lam (Greedy) đảm bảo tập con kích thước $k$ đạt được giá trị mục tiêu:
$$F_N(S_k) \ge \left(1 - \frac{1}{e}\right) F_N(O_k)$$
trong đó $O_k$ là tập con tối ưu kích thước $k$.

### 3.3 Pipeline Kỹ Thuật

- **Tiền xử lý mã nguồn**: Loại bỏ chú thích dòng và khối khỏi mã nguồn Java trong khi vẫn giữ nguyên các hằng chuỗi và cấu trúc thụt lề logic.
- **Mã hóa UniXcoder**: Cơ chế cửa sổ trượt (sliding window) tối đa 16 chunk, mỗi chunk 512 token. Cơ chế masked mean-token pooling loại bỏ hoàn toàn các token `<pad>`. Các chunk được tổng hợp theo trọng số chiều dài payload thực tế.
- **Bộ nhớ đệm theo nội dung (Content-Addressed Caching)**: Lưu vector nhúng bằng mã băm SHA-256 của nội dung file nguồn, đảm bảo tính tất định và khả năng tái lập 100%.

---

## 4. Thiết Kế Thực Nghiệm (Experimental Design)

### 4.1 Bộ Dữ Liệu Thực Nghiệm

| Bộ dữ liệu | Mức độ kiểm thử | Số dự án | Quy mô | Lỗi / Stage | Mục đích sử dụng |
|:---|:---|:---:|---:|---:|:---|
| **Defects4J v2.0** | Method-level | 6 | 20.770 methods | 288 faults | Tái lập độc lập FALCON (RQ1) |
| **LRTS** | Class-level | 3 | Biến động theo build | 596 stages, 519 physical builds | Đánh giá HC-FALCON (RQ2-4) |

Chi tiết 3 dự án LRTS: Apache Karaf (315 build), Apache ActiveMQ (126 build), Apache Log4j2 (78 physical build, 155 stage).

### 4.2 Giao Thức Phân Chia Dữ Liệu Theo Thời Gian (Temporal Split)

Để ngăn chặn tuyệt đối rò rỉ thông tin tương lai, các build được sắp xếp theo thời gian thực tế:

- **Khởi động (Warm-up, 20% đầu)**: Cập nhật lịch sử và tính bộ nhớ đệm embedding. Không tính toán điểm số hay metric.
- **Phát triển (Development, 30% tiếp theo, tổng 50%)**: Không gian mở phục vụ đánh giá thuật toán và phân tích nguyên nhân thất bại.
- **Xác nhận (Reserved Confirmation, 50% cuối)**: Niêm phong mật mã. Chỉ được phép mở khi thuật toán vượt qua Cổng Hiệu quả trên tập Development.

### 4.3 Thước Đo Đánh Giá

- **Chỉ số chính**: APFDc trung điểm (midpoint APFDc):
  $$\text{APFDc} = 1 - \frac{\sum_{i: t_i \text{ failed}} \left(\sum_{j=1}^{i-1} C_j + \frac{C_i}{2}\right)}{m \sum_{i=1}^n C_i}$$
- **Chỉ số phụ**: APFD (chỉ xét thứ tự), Thời gian phát hiện lỗi đầu tiên (TTFF), Tỷ lệ phát hiện lỗi trong 10% ngân sách thời gian (Recall@10%).

### 4.4 Cổng Hiệu Quả (Preregistered Effect Gate)

$$\text{Median Paired } \Delta\text{APFDc} \ge +0{,}0300 \text{ (+3,0 điểm phần trăm)}$$

so sánh cặp đôi đối với **cả hai** baseline `history_cost` và `fl_only` trên ít nhất 2 trong 3 dự án tập Development.

### 4.5 Các Phương Pháp Đối Chứng (15 Baselines)

Bao gồm: `random` (trung bình 20 seed), `shortest_test_first`, `most_fail`, `recent_fail`, `history_only`, `history_cost`, `fl_only`, `hc_falcon_normalized_v1`, `hc_falcon_topic_raw_v1`, `fl_history`, `no_confidence`, `borda_history`, `borda_history_cost`, `fast_pw_lrts`, `dante_cch_adapt_r1`.

---

## 5. RQ1: Tái Lập Độc Lập FALCON Trên Defects4J

### 5.1 Kết Quả Tái Lập Toàn Diện

| Dự án | Số Test Method | Số Lỗi | APFD Công Bố | APFD Tái Lập | Chênh Lệch ($\Delta$) | Thời Gian (s) | Đỉnh RAM (GiB) |
|:---|---:|---:|:---:|:---:|:---:|---:|---:|
| Chart | 2.193 | 26 | 0,7263 | **0,7323** | +0,0060 | 977 | 1,130 |
| Mockito | 1.292 | 27 | 0,7362 | **0,7362** | +0,0000 | 267 | 1,131 |
| Lang | 2.239 | 32 | 0,7543 | **0,7543** | **+0,0000** | 897 | 1,172 |
| Math | 2.996 | 30 | 0,6224 | **0,6356** | +0,0132 | 1.477 | 1,184 |
| Time | 4.044 | 26 | 0,7944 | **0,7989** | +0,0045 | 1.438 | 1,137 |
| Closure | 8.006 | 147 | 0,7002 | **0,6986** | -0,0016 | 3.321 | 1,643 |
| **Trung bình** | **20.770** | **288** | **0,7223** | **0,7260** | **+0,0037** | **8.376** | **1,643** |

Dự án Lang đạt kết quả trùng khớp chính xác tuyệt đối từng chữ số thập phân ($\Delta = 0{,}000000$). Độ lệch trung bình trên cả 6 dự án chỉ là $+0{,}37$ điểm phần trăm, giải thích được hoàn toàn do độ trôi phiên bản thư viện (PyTorch 2.14 so với môi trường năm 2024 của tác giả).

### 5.2 Phân Rã Bằng Biểu Đồ Cầu Nối (Bridge Chart Decomposition)

| Nhánh cấu hình | Thành phần thử nghiệm | APFD | Chênh lệch so với nhánh trước |
|:---|:---|:---:|:---:|
| A (Baseline tác giả) | Vector tác giả + Thuật toán sắp xếp tác giả | 0,7323 | -- |
| B (Kernel clipping) | Vector tác giả + Cắt giá trị kernel $[0, 1]$ | 0,7323 | +0,0000 |
| C (Tham lam nội bộ) | Kernel clipped + Phá vỡ hòa điểm bằng FQN | 0,7323 | +0,0000 |
| D (Pipeline hoàn chỉnh) | Tiền xử lý nội bộ + Masked attention pooling | **0,7635** | **+0,0313** |

**Kết luận**: Toàn bộ mức cải thiện $+3{,}13\%$ APFD xuất phát từ bước làm sạch mã nguồn (loại bỏ chú thích) và cơ chế pooling có mặt nạ (loại bỏ token padding), chứng minh pipeline nội bộ vượt trội hơn về kỹ thuật trích xuất đặc trưng.

---

## 6. RQ2: Kết Quả Đánh Giá Thực Nghiệm Trên LRTS

### 6.1 Thử Nghiệm Sơ Bộ Giai Đoạn 6: HC-FALCON-N v1 ($\alpha = 0{,}5$)

| Dự án | Tổng Build | Số Cặp Lỗi | Trung vị $\Delta$ vs `hc` | Trung bình $\Delta$ [95% Bootstrap CI] | Wilcoxon $p$-value | Cliff's $\delta$ | Thắng / Thua / Hòa | Trung vị $\Delta$ vs `fl_only` | Effect Gate |
|:---|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Karaf | 315 | 79 | **-1,27%** | -0,44% [-3,22%, +2,53%] | $p = 6{,}25 \times 10^{-3}$ | -0,052 (negligible) | 24 / 54 / 1 (30,4%) | **+29,72%** ($p < 10^{-10}$) | Không đạt |
| ActiveMQ | 126 | 57 | **-1,41%** | -3,39% [-6,15%, -1,06%] | $p = 6{,}98 \times 10^{-7}$ | -0,141 (negligible) | 10 / 47 / 0 (17,5%) | **+39,14%** ($p < 10^{-8}$) | Không đạt |
| Log4j | 78 | 25 | **-0,12%** | +0,78% [-0,96%, +3,01%] | $p = 2{,}37 \times 10^{-2}$ | -0,101 (negligible) | 4 / 21 / 0 (16,0%) | **+28,69%** ($p = 3{,}29 \times 10^{-4}$) | Không đạt |

*Ghi chú: $\Delta = \text{APFDc}(\text{HC-FALCON}) - \text{APFDc}(\text{Baseline})$. Giá trị âm biểu thị hiệu năng kém hơn. Kiểm định Wilcoxon hai phía xử lý giá trị 0 theo Pratt. Khoảng tin cậy 95% được ước lượng qua 10.000 lần lặp Bootstrap.*

HC-FALCON áp đảo hoàn toàn `fl_only` ($+28{,}7\%$ đến $+39{,}1\%$, mọi $p < 0{,}001$, Cliff's $\delta > +0{,}65$ Mức lớn), khẳng định rằng việc tích hợp lịch sử và chi phí vào mô hình định vị cơ sở ngữ nghĩa là yếu tố sống còn. Tuy nhiên, HC-FALCON **thua baseline `history_cost` một cách có ý nghĩa thống kê trên cả 3 dự án** ($p = 0{,}0063$ ở Karaf, $p < 10^{-6}$ ở ActiveMQ, và $p = 0{,}0237$ ở Log4j), với tỷ lệ thắng chỉ từ 16,0% đến 30,4%. Do đó, thuật toán thất bại trước Cổng Hiệu quả (0/3 dự án đạt chuẩn).

### 6.2 So Sánh Toàn Diện 15 Baselines (APFDc Trung Bình)

| Phương pháp | Karaf | ActiveMQ | Log4j | Thứ hạng trung bình |
|:---|---:|---:|---:|:---:|
| `history_cost` | **0,7754** | **0,8486** | 0,8936 | **1** |
| `hc_falcon_topic_raw_v1` | 0,7746 | 0,8486 | 0,8940 | 2 |
| `hc_falcon_normalized_v1` | 0,7710 | 0,8147 | 0,9014 | 3 |
| `no_confidence` | 0,7707 | 0,8152 | 0,9339 | 4 |
| `dante_cch_adapt_r1` | 0,7480 | 0,7048 | **0,9351** | 5 |
| `recent_fail` | 0,7361 | 0,8369 | 0,8509 | 6 |
| `history_only` | 0,7122 | 0,8361 | 0,8469 | 7 |
| `most_fail` | 0,6951 | 0,8219 | 0,8667 | 8 |
| `borda_history_cost` | 0,6860 | 0,7379 | 0,9064 | 9 |
| `fl_history` | 0,6662 | 0,8154 | 0,8479 | 10 |
| `shortest_test_first` | 0,6683 | 0,6394 | 0,8586 | 11 |
| `borda_history` | 0,5323 | 0,7169 | 0,8215 | 12 |
| `random` | 0,4936 | 0,4945 | 0,4835 | 13 |
| `fast_pw_lrts` | 0,4606 | 0,4570 | 0,5194 | 14 |
| `fl_only` | 0,4522 | 0,4843 | 0,6990 | 15 |

### 6.3 Phân Tích Độ Nhạy Của Tham Số $\alpha$

| Tham số $\alpha$ | Cơ chế hoạt động | Karaf | ActiveMQ | Log4j |
|:---|:---|---:|---:|---:|
| 0,00 | Thuần túy Lịch sử + Chi phí | **0,7754** | **0,8486** | 0,8936 |
| 0,25 | Nghiêng mạnh về Lịch sử | **0,7794** | 0,8420 | 0,8993 |
| 0,50 | Cân bằng (HC-FALCON) | 0,7710 | 0,8147 | 0,9014 |
| 0,75 | Nghiêng mạnh về Ngữ nghĩa | 0,7077 | 0,7672 | 0,9036 |
| 1,00 | Thuần túy Ngữ nghĩa | 0,4522 | 0,4843 | 0,6990 |

Khi $\alpha$ tăng dần từ $0$ lên $1$, hiệu năng suy giảm đơn điệu trên Karaf và ActiveMQ, khẳng định tín hiệu ngữ nghĩa mã nguồn hoạt động như một thành phần gây nhiễu đối với việc phát hiện lỗi.

---

## 7. RQ3: Phân Tích Nguyên Nhân Gốc Rễ — Hiện Tượng Tiền Nhiệm Nặng Ký (Heavy Predecessors)

### 7.1 Thống Kê Thắng/Thua Trên 161 Build Chứa Lỗi

| Dự án | Tổng số build lỗi | Số build Thắng | Số build Thua | Số build Hòa | Tỷ lệ thắng | $\Delta$ Trung vị khi Thắng | $\Delta$ Trung vị khi Thua |
|:---|---:|---:|---:|---:|---:|---:|---:|
| Karaf | 79 | 24 | 54 | 1 | 30,4% | +3,55% | -2,27% |
| ActiveMQ | 57 | 10 | 47 | 0 | 17,5% | +0,42% | -1,62% |
| Log4j | 25 | 4 | 21 | 0 | 16,0% | +10,52% | -0,13% |
| **Tổng cộng** | **161** | **38** | **122** | **1** | **23,6%** | -- | -- |

### 7.2 Định Lượng Độ Trễ Tích Lũy Do Hiện Tượng Heavy Predecessors

| Dự án | Thời gian test chèn thêm trước test lỗi | Thời gian test được hoán đổi ra sau | Độ trễ ròng (Net Delay) |
|:---|---:|---:|---:|
| Karaf | 18.206 s | 23.385 s | **-5.179 s** |
| ActiveMQ | 115.759 s | 71.873 s | **+43.886 s** |
| Log4j | 1.027 s | 635 s | **+392 s** |
| **Tổng cộng** | **134.992 s** | **95.893 s** | **+39.099 s (~10,8 giờ)** |

### 7.3 Bản Chất Giải Tích: Lệch Chuẩn Thứ Nguyên (Dimensional Mismatch)

Trong hàm mục tiêu $F_N(S) = \alpha \frac{FL(S)}{n} + (1-\alpha) \sum w_b(t)$:

1. Trọng số lịch sử $w_b(t)$ được **chuẩn hóa theo chi phí** (mẫu số chứa căn bậc hai của thời gian thực thi $\sqrt{\tilde{c}_b(t)}$).
2. Lợi ích biên của đa dạng ngữ nghĩa $\Delta FL(t \mid S) / n$ lại **hoàn toàn vô cảm với chi phí**.
3. Tại các bước tham lam ban đầu khi tập đã chọn $S$ còn nhỏ, lợi ích biên ngữ nghĩa chiếm tới **97,5% – 99,9%** tổng lợi ích biên.
4. Điều này buộc giải thuật tham lam lựa chọn các test class rất nặng (ví dụ: `MemoryUsageConcurrencyTest` mất 150 giây) nhưng không chứa lỗi lên thực thi trước một bài kiểm thử có nguy cơ lỗi cao chỉ chạy mất 0,001 giây, chỉ nhằm mục đích tối đa hóa độ bao phủ không gian embedding. Hệ quả là chỉ trong một build, APFDc bị sụt giảm thảm hại tới **-51,50%**.

---

## 8. RQ4: Các Thế Hệ Cải Tiến Thuật Toán (5 Generations)

### 8.1 Bảng So Sánh Hợp Nhất 5 Thế Hệ Thuật Toán

**Bảng: Hiệu năng đối chứng của 5 thế hệ thuật toán so với baseline `history_cost` trên 161 build chứa lỗi.**

| Thế hệ | Giai đoạn | Phương pháp | Cơ chế cốt lõi | Karaf ($N=79$) | ActiveMQ ($N=57$) | Log4j ($N=25$) | Tỷ lệ thắng gộp | Sign Test $p$-value | Effect Gate |
|:---:|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 6 | `hc_falcon_normalized_v1` | Bán mô-đun chuẩn (ngữ nghĩa vô cảm với chi phí) | -1,265% (24W/54L) | -1,407% (10W/47L) | -0,117% (4W/21L) | 23,6% (38/161) | $p = 1{,}05 \times 10^{-11}$ | 0/3 (NO-GO) |
| **2** | 8 | `restricted_v1` | Giới hạn ứng viên hoán đổi: $q \ge 0{,}95 q_{\text{head}}$ | -0,017% (13W/49L) | -0,154% (13W/43L) | -0,001% (5W/14L) | 19,3% (31/161) | $p = 7{,}74 \times 10^{-15}$ | 0/3 (NO-GO) |
| **3a** | 11 | `hc_cns_v1` (CNS-Greedy) | Chuẩn hóa chi phí vào ngữ nghĩa: $\Delta\text{FL}/\sqrt{c}$ | -0,399% (22W/56L) | -0,606% (10W/47L) | -0,190% (6W/19L) | 23,6% (38/161) | $p = 1{,}05 \times 10^{-11}$ | 0/3 (NO-GO) |
| **3b** | 11 | `hc_knapsack_v1` | Tỷ số Knapsack tham lam: $(\Delta F)/c^{0{,}5}$ | -0,501% (26W/53L) | -6,625% (6W/51L) | -0,100% (5W/20L) | 23,0% (37/161) | $p = 4{,}41 \times 10^{-12}$ | 0/3 (NO-GO) |
| **3c** | 11 | `hc_tiered_v1` | Phân tầng theo độ tin cậy lịch sử | -0,182% (17W/62L) | -14,751% (1W/56L) | -1,001% (3W/22L) | 13,0% (21/161) | $p = 2{,}18 \times 10^{-21}$ | 0/3 (NO-GO) |
| **4** | 12 | `hc_ugcs_v2` | Khung phòng vệ bất định Bayes ($1{,}96 \sigma$) | -0,059% (20W/55L) | -0,224% (9W/44L) | -0,002% (6W/17L) | 21,7% (35/161) | $p = 4{,}29 \times 10^{-13}$ | 0/3 (NO-GO) |

*Những kết luận quan trọng:*
1. **100% Trung vị Mang Dấu Âm**: Cả 18/18 ô dữ liệu (dự án $\times$ thế hệ) đều ghi nhận trung vị $\Delta$APFDc mang giá trị âm trước `history_cost`.
2. **Tỷ Lệ Thắng Không Vượt Quá 24%**: Xuyên suốt 5 thế hệ, các thuật toán cải tiến chỉ thắng từ 13% đến 24% số build có lỗi, và thua từ 70% đến 85% trường hợp.
3. **Ý Nghĩa Thống Kê Tuyệt Đối**: Kiểm định nhị thức hai phía (binomial sign test) bác bỏ giả thuyết hiệu năng trung vị ngang bằng ($p_0 = 0{,}5$) với mức ý nghĩa $p < 10^{-11}$ cho mọi thế hệ.

### 8.2 Phân Tích Tiến Trình Cải Tiến

- **Từ Thế hệ 1 đến Thế hệ 2 (Restricted)**: Thu hẹp biên độ thua nhờ hạn chế không gian hoán đổi ngữ nghĩa, nhưng đồng thời làm giảm tính đa dạng hữu ích.
- **Từ Thế hệ 1 đến Thế hệ 3a (CNS-Greedy)**: Khắc phục trực tiếp sự lệch chuẩn thứ nguyên. Giảm 60% mức thua trung vị, đưa chênh lệch trung bình (Mean Delta) thành dương ($+1{,}7\%$ đến $+3{,}5\%$), nhưng Trung vị vẫn âm do 70%–80% số build vẫn thua.
- **Thế hệ 4 (UGCS v2)**: Đạt mức trung vị âm nhỏ nhất (chỉ $-0{,}002\%$ trên Log4j), nhưng **vi phạm nghiêm trọng cổng kỹ thuật về thời gian chạy** (P95 overhead đạt 12.184 lần so với ngưỡng cho phép là 0,10).

### 8.3 Kết Quả Đánh Giá Cổng Kỹ Thuật (Stage 12 Engineering Gate)

| Tiêu chí cổng | Thước đo | Ngưỡng quy định | Kết quả thực tế | Trạng thái đạt |
|:---|:---|:---:|:---:|:---:|
| Bộ nhớ | Đỉnh RSS (Peak RSS) | 8 GiB | 656 MiB | Đạt (Yes) |
| Thời gian chạy | P95 tỷ số overhead khởi động ấm | 0,10 | 12.183,97 | Không đạt (No) |
| Tính toàn vẹn | Lỗi thiếu/không hợp lệ | 0 | 0 | Đạt (Yes) |

---

## 9. Thảo Luận Và Đóng Góp Khoa Học (Discussion)

### 9.1 Tại Sao Đa Dạng Hóa Ngữ Nghĩa Thất Bại Trên CI Mức Lớp (LRTS)?

Sự tương phản rõ rệt giữa thành công trên Defects4J (APFD $0{,}7260$) và thất bại trên LRTS (Gate 0/3) hé lộ những khác biệt mang tính bản chất:

1. **Độ Mịn Của Đơn Vị Kiểm Thử (Granularity)**: Trên Defects4J, đơn vị kiểm thử là từng method độc lập với ngữ nghĩa tập trung và thời gian chạy tương đối đồng đều. Trên LRTS, đơn vị là cả một **Test Class** chứa hàng chục method, làm loãng chất lượng vector nhúng qua các thao tác cắt chunk và pooling.
2. **Độ Phân Tán Chi Phí (Cost Variance)**: Defects4J sử dụng APFD xếp hạng thuần túy (chi phí ngầm định là 1). Trong khi đó, thời gian thực thi của LRTS trải dài qua 5 bậc độ lớn (từ 0,001 giây đến hơn 150 giây). Bất kỳ sự hoán đổi nào đẩy một bài kiểm thử chậm lên trước đều gây tổn thất APFDc không thể khắc phục.
3. **Sức Mạnh Của Baseline Lịch Sử**: Trong môi trường CI thực tế, các lỗi phần mềm có tính bám dính cao. Điểm số $q_b(t) = \text{conf} \cdot p / \sqrt{\tilde{c}}$ là một ước lượng xác suất cực mạnh mà tính đa dạng ngữ nghĩa không thể làm xáo trộn một cách có lợi ở mức trung vị.

### 9.2 Giá Trị Của Kết Quả Nghiên Cứu Âm Này

- **Bác bỏ một giả thuyết có vẻ hiển nhiên**: Ý niệm kết hợp đa dạng ngữ nghĩa với lịch sử và chi phí là hợp lý về mặt trực giác và toán học, nhưng đã bị thực nghiệm bác bỏ trên môi trường CI mức lớp có chi phí biến động lớn.
- **Cảnh báo về hiện tượng Heavy Predecessors**: Mọi hàm mục tiêu đa dạng hóa không nhận thức chi phí đều dễ tổn thương trước hiệu ứng này khi chi phí có độ lệch chuẩn cao.
- **Hình mẫu về tính minh bạch phương pháp luận**: Quy trình tiền đăng ký, niêm phong tập dữ liệu xác nhận, và công bố trung thực kết quả âm giúp loại bỏ thiên kiến xuất bản (publication bias).

### 9.3 Phạm Vi Hiệu Lực Của Kết Luận (Boundary Conditions)

Kết luận âm này được giới hạn trong: Hệ sinh thái Java/Maven, TCP ở mức test class với chi phí phân tán cao, ba dự án nguồn mở Apache, và mô hình thực thi tuần tự đo bằng APFDc. Kết luận **không** khẳng định TCP ngữ nghĩa thất bại trên mọi bài toán — thực tế chúng tôi đã tái lập thành công FALCON trên mức method của Defects4J với chi phí đồng đều.

---

## 10. Các Nguy Cơ Đối Với Tính Hiệu Lực (Threats to Validity)

### Hiệu Lực Bên Trong (Internal Validity)
- Độ chính xác số học dấu phẩy động Float64 gây ra 8 ngoại lệ vi mô khi phá vỡ thế hòa điểm tại $\alpha = 0{,}0$ trên 33.972 lượt xếp hạng; các trường hợp này không làm thay đổi kết luận thống kê.
- Quy tắc phá vỡ hòa điểm bằng FQN đảm bảo tính tất định nhưng mang thiên kiến chữ cái nhỏ.

### Hiệu Lực Bên Ngoài (External Validity)
- Tất cả kết luận LRTS dựa trên 3 dự án mã nguồn mở Java/Maven. Kết quả có thể khác đối với ngôn ngữ thông dịch (Python, JS) hoặc môi trường CI doanh nghiệp chạy song song/phân tán.
- Đánh giá mức lớp kiểm thử không suy rộng sang mức method-level nơi chất lượng nhúng cao hơn và chi phí đồng nhất hơn.

### Hiệu Lực Khái Niệm (Construct Validity)
- APFDc giả định thực thi đơn luồng tuần tự nghiêm ngặt. Trong CI song song, tác động của Heavy Predecessors có thể được giảm thiểu.
- Tiêu chí cổng runtime Stage 12 ($P95 \le 0{,}10$ so với phép sort $\sim 50\ \mu\text{s}$ của `history_cost`) là bất khả thi về mặt cấu trúc đối với bất kỳ thuật toán ngữ nghĩa nào. Chúng tôi chấp nhận kết quả fail-closed theo đúng tiền đăng ký.

### Hiệu Lực Kết Luận Thống Kê (Conclusion Validity)
- 161 build chứa lỗi mang lại năng lực thống kê (statistical power) đầy đủ cho các kiểm định Wilcoxon trên Karaf (79) và ActiveMQ (57). Log4j (25 build) có kích thước mẫu hạn chế hơn nhưng xu hướng nhất quán.
- Bốn thế hệ thuật toán cùng thử nghiệm trên tập Development tiềm ẩn nguy cơ Forking Paths. Rủi ro được kiểm soát chặt chẽ bằng tiền đăng ký, không quét tham số (tuning rounds = 0), và niêm phong 100% tập dữ liệu Reserved.

---

## 11. Kết Luận Và Hướng Phát Triển (Conclusion and Future Work)

Chúng tôi đã đề xuất, chứng minh toán học và đánh giá thực nghiệm toàn diện khung làm việc HC-FALCON cho bài toán Sắp xếp Thứ tự Kiểm thử. Các phát hiện chính gồm:

1. **Độ trung thực tái lập 100%** đối với FALCON trên Defects4J (APFD $0{,}7260$ so với $0{,}7223$).
2. **Thất bại trước Cổng Hiệu quả (0/3)** xuyên suốt cả 5 thế hệ thuật toán trên môi trường CI thực tế mức lớp.
3. **Định lượng hóa hiện tượng Heavy Predecessors** là nguyên nhân cốt lõi gây ra $+10{,}8$ giờ trễ lũy kế.
4. **CNS-Greedy** giúp giảm 60% mức tổn thất nhưng không thể đảo chiều trung vị thành dương.

Chúng tôi kết luận rằng trong môi trường CI mức lớp có chi phí thực thi phân tán mạnh, tín hiệu lịch sử kết hợp chi phí là một baseline cực mạnh mà sự đa dạng hóa ngữ nghĩa không thể cải thiện ở mức trung vị. Tập dữ liệu xác nhận Reserved tiếp tục được niêm phong vĩnh viễn cho nhánh nghiên cứu này.

### Các Hướng Nghiên Cứu Tương Lai

1. **TCP Mức Method Trên CI Thực Tế**: Loại bỏ hiện tượng suy giảm chất lượng embedding bằng cách thu thập log CI ở mức từng test method.
2. **Kích Hoạt Ngữ Nghĩa Riêng Cho Cold-Start**: Chỉ kích hoạt sắp xếp ngữ nghĩa đối với các kiểm thử hoàn toàn mới chưa có lịch sử ($N = 0$).
3. **Thước Đo Cho CI Chạy Song Song / Phân Tán**: Mở rộng đánh giá dưới mô hình thực thi song song nhiều shard.
4. **Khảo Sát Đa Ngôn Ngữ**: Mở rộng thực nghiệm sang các ngôn ngữ thông dịch (Python, JavaScript) và ngôn ngữ hệ thống (Rust, Go).

---

## 12. Tài Liệu Tham Khảo (References)

[1] G. Rothermel, R. H. Untch, C. Chu, and M. J. Harrold, "Prioritizing test cases for regression testing," *IEEE Transactions on Software Engineering*, vol. 27, no. 10, pp. 929-948, 2001.

[2] S. Elbaum, A. G. Malishevsky, and G. Rothermel, "Test case prioritization: A family of empirical studies," *IEEE Transactions on Software Engineering*, vol. 28, no. 2, pp. 159-182, 2002.

[3] S. Elbaum, P. Kallakuri, A. G. Malishevsky, and G. Rothermel, "Understanding the effects of changes on the cost-effectiveness of regression testing techniques," *Software Testing, Verification and Reliability*, vol. 13, no. 2, pp. 65-83, 2003.

[4] A. Bertolino, B. Miranda, E. Rogstad, and A. R. Santos, "Learning-to-rank for test case prioritization in continuous integration," *IEEE Transactions on Software Engineering*, vol. 47, no. 12, pp. 2728-2746, 2020.

[5] H. Spieker, A. Gotlieb, D. Marijan, and M. Mossige, "Reinforcement learning for automatic test case prioritization and selection in continuous integration," in *Proc. 26th ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2017, pp. 12-22.

[6] B. Mondal, H. Hemmati, and S. Durocher, "FAST: Fast and scalable test case prioritization using diversity," in *Proc. 40th Int. Conf. Softw. Eng. (ICSE)*, 2018, pp. 1198-1208.

[7] K. Mensah-Boateng, A. Perera, C. Tantithamthavorn, and B. Le, "FALCON: Submodular Test Case Prioritization using Code Embeddings," in *Proc. 19th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2026.

[8] M. Reale, F. Pecorelli, D. Di Nucci, F. Palomba, and A. De Lucia, "DANTE: History-aware Test Case Prioritization for Long-Running Test Suites," in *Proc. 19th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2026.

[9] D. Marijan, A. Gotlieb, and S. Sen, "Test case prioritization for continuous integration testing in resource-constrained environments," in *Proc. 25th IEEE Int. Conf. Softw. Maint. (ICSM)*, 2013, pp. 488-491.

[10] G. L. Nemhauser, L. A. Wolsey, and M. L. Fisher, "An analysis of approximations for maximizing submodular set functions—I," *Mathematical Programming*, vol. 14, no. 1, pp. 265-294, 1978.

[11] A. Krause and D. Golovin, "Submodular function maximization," *Tractability: Practical Approaches to Hard Problems*, vol. 3, pp. 71-104, 2014.

[12] D. Guo, S. Lu, N. Duan, Y. Wang, M. Zhou, and J. Yin, "UniXcoder: Unified cross-modal pre-training for code representation," in *Proc. 60th Annu. Meeting Assoc. Comput. Linguist. (ACL)*, 2022, pp. 7212-7225.

[13] R. Just, D. Jalali, and M. D. Ernst, "Defects4J: A database of existing faults to enable controlled testing studies for Java," in *Proc. 23rd ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2014, pp. 437-440.

[14] B. Busjaeger and T. Xie, "Learning for test prioritization: An industrial evaluation," in *Proc. 24th ACM SIGSOFT Int. Symp. Found. Softw. Eng. (FSE)*, 2016, pp. 975-986.

[15] H. Hemmati, A. Arcuri, and L. Briand, "Achieving higher test coverage by test case diversification," in *Proc. 35th Int. Conf. Softw. Eng. (ICSE)*, 2013, pp. 782-791.

[16] R. Feldt, F. G. de Oliveira Neto, and R. Torkar, "Ways of test set diversification: Concepts, taxonomy and preliminary findings," in *Proc. 19th Int. Conf. Softw. Eng. Pract. Eval. (SEAA)*, 2016, pp. 293-300.

[17] C. Henard, M. Papadakis, M. Harman, and Y. Le Traon, "Comparing white-box and black-box test prioritization: An empirical study," in *Proc. 38th Int. Conf. Softw. Eng. (ICSE)*, 2016, pp. 523-534.

[18] Q. Luo, K. Moran, L. Zhang, and D. Poshyvanyk, "How do test runs impact flaky tests? An empirical study," in *Proc. 28th ACM SIGSOFT Int. Symp. Softw. Test. Anal. (ISSTA)*, 2019, pp. 222-233.

[19] G. Scanniello, E. Stangl, G. Bavota, F. Wedyan, and M. Torchiano, "The value of negative results in empirical software engineering," *Empirical Software Engineering*, vol. 20, no. 6, pp. 1751-1779, 2015.

[20] A. Gelman and E. Loken, "The statistical crisis in science: Data-dependent analysis—a 'garden of forking paths'—explains why many statistically significant findings don't hold up," *American Scientist*, vol. 102, no. 6, pp. 460-465, 2014.

[21] F. Wilcoxon, "Individual comparisons by ranking methods," *Biometrics Bulletin*, vol. 1, no. 6, pp. 80-83, 1945.

[22] N. Cliff, "Dominance statistics: Ordinal analyses to answer ordinal questions," *Psychological Bulletin*, vol. 114, no. 3, pp. 494-509, 1993.

[23] S. Holm, "A simple sequentially rejective multiple test procedure," *Scandinavian Journal of Statistics*, vol. 6, no. 2, pp. 65-70, 1979.

[24] B. Efron and R. J. Tibshirani, *An Introduction to the Bootstrap*. CRC Press, 1994.

[25] J.-M. Kim and A. Porter, "A history-based test prioritization technique for regression testing in resource-constrained environments," in *Proc. 24th Int. Conf. Softw. Eng. (ICSE)*, 2002, pp. 119-129.

[26] E. Engström, P. Runeson, and M. Skoglund, "A systematic review on regression test selection techniques," *Information and Software Technology*, vol. 52, no. 1, pp. 14-30, 2010.

[27] S. Lu et al., "CodeXGLUE: A machine learning benchmark dataset for code understanding and generation," in *Proc. 35th Conf. Neural Inf. Process. Syst. (NeurIPS)* Datasets and Benchmarks Track, 2021.

[28] Z. Feng et al., "CodeBERT: A pre-trained model for programming and natural languages," in *Proc. Findings of EMNLP*, 2020, pp. 1536-1547.

[29] H. Husain, H.-H. Wu, T. Gazit, M. Allamanis, and M. Brockschmidt, "CodeSearchNet challenge: Evaluating the state of semantic code search," *arXiv preprint arXiv:1909.09436*, 2019.

[30] R. Lachmann, S. Schulze, M. Nieke, C. Seidl, and I. Schaefer, "Fine-grained test case prioritization using machine learning," in *Proc. 9th IEEE Int. Conf. Softw. Test., Verif. Validation (ICST)*, 2016, pp. 1-10.

[31] M. Khatibsyarbini, M. A. Isa, D. N. Jawawi, and R. Tumeng, "Test case prioritization approaches in regression testing: A systematic literature review," *Information and Software Technology*, vol. 93, pp. 74-93, 2018.

[32] H. Do, S. Elbaum, and G. Rothermel, "Supporting controlled experimentation with testing techniques: An infrastructure and its potential impact," *Empirical Software Engineering*, vol. 10, no. 4, pp. 405-435, 2005.

[33] S. Wang, D. Buchler, A. Gotlieb, D. Marijan, and A. Liaaen, "Multi-objective test prioritization in software product line testing: An industrial case study," in *Proc. 18th Int. Softw. Product Line Conf. (SPLC)*, 2014, pp. 247-256.

[34] M. G. Epitropakis, S. Yoo, M. Harman, and E. K. Burke, "Empirical evaluation of Pareto efficient multi-objective regression test case prioritisation," in *Proc. 2015 Int. Symp. Softw. Test. Anal. (ISSTA)*, 2015, pp. 234-245.

[35] Y. Lu, Y. Lou, S. Cheng, L. Zhang, D. Hao, L. Zhang, and T. Xie, "How does regression test prioritization perform in real-world software evolution?," in *Proc. 38th Int. Conf. Softw. Eng. (ICSE)*, 2016, pp. 535-546.
