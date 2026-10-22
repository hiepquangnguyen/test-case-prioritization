# DANH SÁCH CÁC HẠNG MỤC CẦN HOÀN THIỆN (TODO FINAL)

> Tài liệu tổng hợp toàn bộ các điểm ghi chú `TODO:`, các nội dung bảo lưu và các công việc còn lại của báo cáo Đồ án liên ngành, cập nhật theo tiến độ từng giai đoạn.

---

## 1. CÁC ĐIỂM `TODO:` HIỆN TẠI TRONG TÀI LIỆU LATEX

| STT | Tệp nguồn & Vị trí | Hạng mục | Trạng thái hiện tại | Hướng xử lý tiếp theo |
|:---:|:---|:---|:---|:---|
| 1 | `report-latex/contents/pledge.tex` (dòng 12) | **Khai báo sử dụng AI** | Đang để comment `% TODO: [Khai báo việc sử dụng công cụ AI hỗ trợ...]` | Chờ quy định cụ thể của Khoa/Trường Phenikaa về định dạng và mức độ khai báo công cụ trợ lý AI; không tự ý viết trước. |
| 2 | `report-latex/contents/sections/SEC4.tex` (Mục 4.5, dòng 576) | **Thực nghiệm bóc tách thành phần (Ablation Study)** | Đang giữ cấu trúc nháp kèm comment `% TODO: Hiện tại trong kho dữ liệu chưa ghi nhận thực nghiệm bóc tách...` | Các thực nghiệm ngắt bỏ hệ số phạt chi phí riêng rẽ hoặc cô lập cold-start độc lập chưa có trong artifacts; giữ nguyên văn bản nháp khách quan, bổ sung nếu có dữ liệu kiểm chứng sau này. |
| 3 | `report-latex/contents/sections/SEC5.tex` (Mục 5.5) | **Rủi ro ô nhiễm dữ liệu tiền huấn luyện UniXcoder (Pre-training Data Contamination)** | Cần bổ sung vào Mục 5.5 (Mối đe dọa giá trị bên ngoài - Threats to External Validity) khi viết Chương 5 | Phân tích rõ ranh giới phương pháp luận: Cơ chế `cutoff_timestamp` và giao diện outcome-free chỉ bảo đảm tính cô lập thời gian đối với dữ liệu lịch sử thực thi và nhãn kết quả động trong mô phỏng CI; không bảo vệ được nguy cơ mô hình UniXcoder đã được tiền huấn luyện trước đó trên kho mã nguồn GitHub công khai chứa mã của các dự án kiểm thử (Defects4J, LRTS). |
| 4 | `report-latex/contents/sections/SEC5.tex` (Mục 5.2/5.3) | **Giả thuyết cơ chế hiện tượng Heavy Predecessors** | Cần đưa vào phân tích chuyên sâu tại Chương 5 | **Mức bằng chứng: Gián tiếp / Tương quan thực nghiệm**. Phân tích hiện tượng các bài test chạy lâu không lỗi bị đẩy lên đầu làm trễ TTFF (Stage 7, 11, 12). Tương quan thứ bậc Spearman giữa $T_{\text{net}}$ và $\Delta\text{APFDc}$ mang dấu âm rất mạnh trên toàn bộ 161 build lỗi ($\rho = -0{,}806$ đối với v1 và $\rho = -0{,}912$ đối với UGCS v2; khi chuẩn hóa $T_{\text{net}} / T_{\text{total}}$ thì $\rho = -0{,}951$ và $\rho = -0{,}981$, toàn bộ $p < 10^{-37}$). Tuy nhiên, UGCS v2 dù cắt giảm $-9.631,3$ s độ trễ ròng vẫn thua điểm APFDc ở 72,05% số build do bản chất tích phân diện tích nhạy cảm với từng giây trễ cục bộ. Nguồn: `reports/stage11/forensic-analysis.json`, `reports/stage12/tnet_vs_apfdc_correlation.json`. |
| 5 | `report-latex/contents/sections/SEC5.tex` (Mục 5.4) | **Giả thuyết nguyên nhân kỹ thuật vi phạm Cổng thời gian chạy của UGCS v2** | Cần đưa vào phân tích tại Mục 5.4 khi viết Chương 5 | **Mức bằng chứng: Giả thuyết kỹ thuật thực thi (Implementation hypothesis)**. Độ trễ trung vị $53{,}82$ ms của UGCS v2 (chậm hơn 478 lần so với $0{,}11$ ms của `history_cost`) xuất phát từ chi phí overhead lặp qua cấu trúc dữ liệu Python phức tạp: quét mảng tìm mỏ neo, lọc danh sách ứng viên $\text{Safe}$, thực hiện phép toán ma trận NumPy và tái chuẩn hóa tương đối liên tục; trong khi `history_cost` chỉ thực hiện sắp xếp 1 lần trên mảng 1 chiều $O(n \log n)$ hoặc lookup $O(1)$. Nguồn: `hc_falcon/v2.py:119-181`, `reports/stage12/development-screen.json`. |
| 6 | `report-latex/contents/sections/SEC5.tex` (Mục 5.1) | **Kiểm chứng nguồn gốc độ phức tạp kỳ vọng $O(n^2 \log n)$ của Lazy Greedy** | Đã xác minh nguồn gốc trong bài báo gốc FALCON ICST 2026 | **Mức bằng chứng: Trích dẫn tài liệu gốc (Đã xác minh)**. Bài báo gốc FALCON (ICST 2026, trang 5, Mục IV-C) dẫn chiếu nghiên cứu thực nghiệm [23] (Leskovec et al. KDD 2007) và [30] (Minoux 1978) chỉ ra rằng đối với hàm Facility Location, số lượt đánh giá hàm mục tiêu kỳ vọng thực tế là $O(n \log n)$, mỗi lượt tốn $O(n)$, mang lại độ phức tạp kỳ vọng $O(n^2 \log n)$. Cần ghi rõ nguồn trích dẫn này khi bàn luận ở Chương 5. |
| 7 | `report-latex/contents/sections/SEC5.tex` (Mục 5.5) | **Sự phụ thuộc vào đơn vị đo thời gian của CNS-Greedy (Dimensional / Scale Inconsistency)** | Cần phân tích trong Mục 5.5 (Đe dọa giá trị xây dựng - Construct Validity) | **Mức bằng chứng: Phân tích toán học hình thức từ mã nguồn (`hc_falcon/variants.py:27, 37, 46-48`)**. Thành phần ngữ nghĩa chia cho căn bậc hai thời lượng thô tính theo giây ($c(t)$, đơn vị $\text{s}^{1/2}$ ở mẫu số), trong khi thành phần lịch sử $w$ dựa trên $q(t)$ sử dụng thời lượng chuẩn hóa phi thứ nguyên $\widetilde{c}(t) = c(t)/c_{\text{ref}}$. Việc thay đổi đơn vị thời gian (từ giây sang mili-giây) sẽ làm thay đổi độ lớn mẫu số $\sqrt{c}$ và làm lệch tỷ trọng tương đối giữa hai thành phần, khiến thuật toán phụ thuộc vào đơn vị đo. |
| 8 | `report-latex/ref.bib` (6 khóa tài liệu tham khảo) | **Các mục tài liệu tham khảo gắn thẻ `CHUA XAC MINH`** | 6 khóa chưa đối chiếu trực tiếp bản PDF gốc: `luo2014flaky` (Luo et al. FSE 2014), `memon2017taming` (Memon et al. ICSE-SEIP 2017), `gelman2013bayesian` (Gelman et al. 2013), `gelman2013garden` (Gelman & Loken 2013), `ralph2021empirical` (Ralph et al. 2021), `singhal2001modern` (Singhal 2001). | Tuyệt đối **không cite** vào thân bài các chương (Chương 2, 3, 4). Chỉ xem xét đưa vào danh mục tài liệu trích dẫn sau khi đã tìm kiếm và kiểm chứng toàn văn bản in/PDF gốc theo đúng chuẩn học thuật IEEE. |

---

## 2. KẾ HOẠCH TRIỂN KHAI CÁC CHƯƠNG TIẾP THEO (THEO LỘ TRÌNH ĐỒ ÁN)

Theo thỏa thuận phương pháp luận, các chương tiếp theo sẽ được triển khai tuần tự theo kế hoạch:

- [x] **Phase 0:** Hoàn thiện cơ sở dữ liệu thực nghiệm, rà soát tính toán (`docs/facts.md`, `docs/glossary.md`, các script và tệp JSON đối soát).
- [x] **Chương 4 (`SEC4.tex`):** Trình bày toàn diện bằng chứng và số liệu thực nghiệm định lượng (Defects4J, LRTS CI, Decision Gates, Heavy Predecessors).
- [ ] **Chương 1 (`SEC1.tex`):** Tổng quan, tính cấp thiết, mục tiêu, đối tượng, phạm vi và câu hỏi nghiên cứu RQ1--RQ5.
- [ ] **Chương 2 (`SEC2.tex`):** Cơ sở lý thuyết (Kiểm thử hồi quy, TCP, Submodular Optimization, UniXcoder, Bayesian estimation).
- [ ] **Chương 3 (`SEC3.tex`):** Thiết kế phương pháp (Kiến trúc HC-FALCON, hàm mục tiêu, 4 thế hệ thuật toán, quy trình tiền đăng ký).
- [ ] **Chương 5 (`SEC5.tex`):** Thảo luận, phân tích nguyên nhân cơ chế chuyên sâu (giải thích hiện tượng quan sát được ở Chương 4), mối đe dọa giá trị (Threats to Validity).
- [ ] **Kết luận (`ketluan.tex`):** Đóng góp của đề tài, bài học thực tiễn, định hướng phát triển tương lai.
- [ ] **Phụ lục A (`phuluc.tex`):** Bảng đối chiếu mã giai đoạn nội bộ (Stage) sang tên mô tả chính thức.
- [ ] **Phụ lục C (`phuluc.tex`):** Mã nguồn cốt lõi của các thuật toán đề xuất (HC-FALCON v1, UGCS v2).
