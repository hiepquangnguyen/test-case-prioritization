# NGUỒN SỰ THẬT SỐ LIỆU ĐỒ ÁN HC-FALCON (SINGLE SOURCE OF TRUTH)

> Tài liệu này là nguồn tham chiếu số liệu duy nhất cho toàn bộ báo cáo đồ án (Abstract, Chương 1, Chương 4, Chương 5, Kết luận).
> Mọi con số trong báo cáo đều phải truy xuất được về các mục trong file này.

---

## 1. TRỤC 1: TÁI LẬP FALCON TRÊN DEFECTS4J

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **6** | Số lượng dự án phần mềm Java đánh giá (Chart, Mockito, Lang, Math, Time, Closure) | FALCON (tái lập) | Defects4J | `reports/stage10/reproduction-summary.json` (dòng 5) |
| **20.770** | Tổng số lượng phương thức kiểm thử (test methods) | FALCON (tái lập) | Defects4J | `reports/stage10/reproduction-summary.json` (dòng 6) |
| **288** | Tổng số phiên bản lỗi thực tế (fault versions) | FALCON (tái lập) | Defects4J | `reports/stage10/reproduction-summary.json` (dòng 7) |
| **0,722310** | Điểm APFD trung bình do tác giả gốc công bố | FALCON (bài gốc) | Defects4J (6 dự án) | `reports/stage10/reproduction-summary.json` (dòng 9) |
| **0,725976** | Điểm APFD trung bình tái lập độc lập trong đồ án | FALCON (tái lập) | Defects4J (6 dự án) | `reports/stage10/reproduction-summary.json` (dòng 10) |
| **+0,003666** | Độ chênh lệch APFD trung bình có dấu (+0,3666 điểm %) | Tái lập vs Bài gốc | Defects4J (6 dự án) | `reports/stage10/reproduction-summary.json` (dòng 11) |
| **0,004214** | Sai lệch tuyệt đối trung bình (MAE qua 6 dự án: $\frac{1}{6}\sum |\Delta_p|$, tức 0,42 điểm %) | Tái lập vs Bài gốc | Defects4J (6 dự án) | `reports/stage10/reproduction-summary.json` |
| **0,013151** | Độ chênh lệch tuyệt đối lớn nhất (tại dự án Math: 0,635581 vs 0,622430) | Tái lập vs Bài gốc | Defects4J (Math) | `reports/stage10/reproduction-summary.json` (dòng 12, 57-60) |
| **0,000000** | Độ chênh lệch tại dự án Lang (0,754285 vs 0,754285 - khớp tuyệt đối) | Tái lập vs Bài gốc | Defects4J (Lang) | `reports/stage10/reproduction-summary.json` (dòng 45-48) |
| **+0,000029** | Độ chênh lệch tại dự án Mockito (0,736226 vs 0,736197 - gần như tuyệt đối) | Tái lập vs Bài gốc | Defects4J (Mockito) | `reports/stage10/reproduction-summary.json` (dòng 33-36) |
| **+0,005963** | Độ chênh lệch tại dự án Chart (0,732278 vs 0,726314) | Tái lập vs Bài gốc | Defects4J (Chart) | `reports/stage10/reproduction-summary.json` (dòng 21-24) |
| **+0,004499** | Độ chênh lệch tại dự án Time (0,798933 vs 0,794434) | Tái lập vs Bài gốc | Defects4J (Time) | `reports/stage10/reproduction-summary.json` (dòng 69-72) |
| **-0,001644** | Độ chênh lệch tại dự án Closure (0,698556 vs 0,700200) | Tái lập vs Bài gốc | Defects4J (Closure) | `reports/stage10/reproduction-summary.json` (dòng 81-84) |
| **7.108,65 s** | Tổng thời gian thực thi tái lập toàn bộ 6 dự án (~1,97 giờ) | FALCON (tái lập) | Defects4J | `reports/stage10/reproduction-summary.json` (dòng 13) |
| **1,651 GiB** | Mức đỉnh chiếm dụng bộ nhớ RAM (Peak RSS) | FALCON (tái lập) | Defects4J | `reports/stage10/reproduction-summary.json` (dòng 14) |
| **0,7323** | Điểm APFD của nhánh Base / Clip / Greedy (Bridge Chart) | Arm A / B / C | Defects4J (Chart) | `reports/stage10/bridge/summary.json` |
| **0,7635** | Điểm APFD của nhánh Pipeline kèm Attention Mask (Bridge Chart) | Arm D | Defects4J (Chart) | `reports/stage10/bridge/summary.json` |
| **+3,13 điểm %** | Mức tăng trưởng APFD nhờ tiền xử lý mã nguồn và attention mask | Arm D vs Arm A | Defects4J (Chart) | `reports/stage10/bridge/summary.json` |
| **chưa xác minh** | Điểm APFD của baseline Random trên Defects4J (bài báo gốc không ghi nhận chi tiết số này trong tệp tóm tắt; trên lý thuyết không thiên vị vị trí lỗi là ~0,50) | Baseline `random` | Defects4J | Chưa xác minh trong repo |

---

## 2. TRỤC 2: TẬP DỮ LIỆU CI THỰC TẾ (LRTS)

### A. Phân tách tập dữ liệu (Data Split Reconciliation)
- **Tổng thể tập dữ liệu LRTS:** Gồm **303 physical build có lỗi thực tế** trên cả 3 dự án (Karaf: 79; ActiveMQ: 140; Log4j2: 84).
- **Tập Sàng lọc Phát triển (Development Screening Split):** Chiếm **161 / 303 physical build lỗi**:
  - **Apache Karaf:** 315 stages, 315 physical builds, **79 physical build lỗi** (315/315 stages, 79 stages lỗi; toàn bộ là exploratory).
  - **Apache ActiveMQ:** 126 stages, 126 physical builds, **57 physical build lỗi** (126/126 stages, 57 stages lỗi; thuộc 50% thời gian đầu).
  - **Apache Log4j2:** 155 stages, 78 physical builds, **25 physical build lỗi** (35 stages lỗi tương ứng gộp về 25 physical builds; thuộc 50% thời gian đầu).
  - **Tổng cộng tập Development:** **596 stages, 519 physical builds, 161 physical build lỗi** (171 stages lỗi).
- **Tập Xác nhận Niêm phong (Reserved Confirmation Split - 100% Sealed, `reserved_opened: false`):** Chiếm **142 / 303 physical build lỗi**:
  - **Apache Karaf:** 0 physical builds (không có holdout; Karaf hoàn toàn là exploratory).
  - **Apache ActiveMQ:** 223 physical builds, **83 physical build lỗi** (223 stages; thuộc 50% thời gian sau).
  - **Apache Log4j2:** 135 physical builds, **59 physical build lỗi** (264 stages; thuộc 50% thời gian sau).
  - **Tổng cộng tập Reserved:** **358 physical builds, 142 physical build lỗi** (487 stages).
  - **Tình trạng:** Ở Stage 4, hệ thống **chỉ kiểm tra định dạng và cấu trúc dữ liệu** (schema validation, counts/outcome validity, check null), tuyệt đối **hoàn toàn không được tính điểm, xếp hạng hay mở dữ liệu** (`reserved_opened: false`) xuyên suốt Stage 6 đến Stage 12 do vi phạm cổng sàng lọc.

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **3** | Số dự án mã nguồn mở Apache được đánh giá (Karaf, ActiveMQ, Log4j2) | Toàn bộ | LRTS | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 20) |
| **303** | Tổng số physical build có lỗi thực tế trên LRTS (161 Development + 142 Reserved) | Toàn bộ | Toàn bộ LRTS | Đối soát dữ liệu Stage 4 / Stage 6 |
| **596** | Tổng số lượng build stage sàng lọc phát triển | Toàn bộ | Development (3 dự án) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 286) |
| **519** | Tổng số lượt physical build sàng lọc phát triển | Toàn bộ | Development (3 dự án) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 286) |
| **171** | Tổng số build stage ghi nhận lỗi thực tế trong tập phát triển | Toàn bộ | Development (3 dự án) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 286) |
| **161** | Số physical build có lỗi tập phát triển (mẫu phân tích chính Paired Delta: 161/303) | Toàn bộ | Development (3 dự án: 79+57+25) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 286, 440) |
| **79** | Số physical build có lỗi tại Apache Karaf | Toàn bộ Karaf | Development (Karaf) | `reports/stage6/karaf/ledger.json`, `reports/release/statistical_tests.json` (dòng 4) |
| **57** | Số physical build có lỗi tại Apache ActiveMQ | 50% đầu ActiveMQ | Development (ActiveMQ) | `reports/stage6/activemq/ledger.json`, `reports/release/statistical_tests.json` (dòng 19) |
| **25** | Số physical build có lỗi tại Apache Log4j2 (gộp từ 35 stage lỗi) | 50% đầu Log4j2 | Development (Log4j2) | `reports/stage6/log4j/ledger.json`, `reports/release/statistical_tests.json` (dòng 34) |
| **126** | Tổng số physical build của ActiveMQ trong tập phát triển (cả thành công và lỗi) | 50% đầu ActiveMQ | Development (ActiveMQ) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 284) |
| **358** | Tổng số physical build trong tập niêm phong Reserved (223 ActiveMQ + 135 Log4j2) | Tập kiểm chứng | Reserved (100% Sealed) | `docs/04-design/evaluation-protocol.md` (dòng 11-12) |
| **142** | Số physical build có lỗi tập niêm phong Reserved (83 ActiveMQ + 59 Log4j2, chưa mở: 142/303) | Tập kiểm chứng | Reserved (100% Sealed) | `reports/stage4/data-audit-manifest.json` |
| **33.972** | Tổng số lượt xếp hạng (ranking operations) được mô phỏng | Toàn bộ | LRTS Development | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 20) |
| **100%** | Tỷ lệ niêm phong của tập Reserved Confirmation sau khi nhận kết quả NO-GO | Quy trình kiểm soát | Reserved (ActiveMQ & Log4j2) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 27, 295) |

---

## 3. CÁC ĐƯỜNG CƠ SỞ (BASELINES) TRÊN LRTS

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **0,7746** | Điểm APFDc trung bình của `history_cost` tại Karaf | `history_cost` | Development (Karaf) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 21) |
| **0,8486** | Điểm APFDc trung bình của `history_cost` tại ActiveMQ | `history_cost` | Development (ActiveMQ) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 21) |
| **0,8940** | Điểm APFDc trung bình của `history_cost` tại Log4j2 | `history_cost` | Development (Log4j2) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 21) |
| **0,4558** | Điểm APFDc trung bình của `fl_only` (thuần ngữ nghĩa) tại Karaf | `fl_only` | Development (Karaf) | `docs/research-report/paper-draft-en.md` |
| **0,5182** | Điểm APFDc trung bình của `fl_only` tại ActiveMQ | `fl_only` | Development (ActiveMQ) | `docs/research-report/paper-draft-en.md` |
| **0,6062** | Điểm APFDc trung bình của `fl_only` tại Log4j2 | `fl_only` | Development (Log4j2) | `docs/research-report/paper-draft-en.md` |
| **0,4936** | Điểm APFDc trung bình của baseline `random` tại Karaf | `random` (20 seed) | Development (Karaf) | `docs/research-report/paper-draft-vi.md` (dòng 206) |
| **0,4945** | Điểm APFDc trung bình của baseline `random` tại ActiveMQ | `random` (20 seed) | Development (ActiveMQ) | `docs/research-report/paper-draft-vi.md` (dòng 206) |
| **0,4835** | Điểm APFDc trung bình của baseline `random` tại Log4j2 | `random` (20 seed) | Development (Log4j2) | `docs/research-report/paper-draft-vi.md` (dòng 206) |

---

## 4. KẾT QUẢ HC-FALCON V1 (STAGE 6) VS BASELINES

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **-1,2650%** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại Karaf (-0,01265) | HC-FALCON v1 (`normalized`) | Development (79 build lỗi) | `reports/release/statistical_tests.json` (dòng 10) |
| **-1,4067%** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại ActiveMQ (-0,01407) | HC-FALCON v1 (`normalized`) | Development (57 build lỗi) | `reports/release/statistical_tests.json` (dòng 25) |
| **-0,1171%** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại Log4j2 (-0,00117) | HC-FALCON v1 (`normalized`) | Development (25 build lỗi) | `reports/release/statistical_tests.json` (dòng 40) |
| **38 (23,6%)** | Tổng số build lỗi HC-FALCON v1 thắng `history_cost` | HC-FALCON v1 vs `history_cost` | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 451) |
| **1 (0,6%)** | Tổng số build lỗi hòa điểm APFDc giữa hai phương pháp | HC-FALCON v1 vs `history_cost` | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 451) |
| **122 (75,8%)** | Tổng số build lỗi HC-FALCON v1 thua `history_cost` | HC-FALCON v1 vs `history_cost` | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 451) |
| **$p = 0,00625$ ($p_{\text{holm}} = 0,01250$)** | P-value kiểm định cặp Wilcoxon tại Karaf (W = 1020,0; hiệu chỉnh Holm 3 dự án) | HC-FALCON v1 vs `history_cost` | Development (Karaf) | `reports/release/statistical_tests.json`, `reports/release/statistical_tests_v1_adjusted.json` |
| **$p = 6,98 \times 10^{-7}$ ($p_{\text{holm}} = 2,10 \times 10^{-6}$)** | P-value kiểm định cặp Wilcoxon tại ActiveMQ (W = 202,0; hiệu chỉnh Holm) | HC-FALCON v1 vs `history_cost` | Development (ActiveMQ) | `reports/release/statistical_tests.json`, `reports/release/statistical_tests_v1_adjusted.json` |
| **$p = 0,0236$ ($p_{\text{holm}} = 0,0236$)** | P-value kiểm định cặp Wilcoxon tại Log4j2 (W = 79,0; hiệu chỉnh Holm) | HC-FALCON v1 vs `history_cost` | Development (Log4j2) | `reports/release/statistical_tests.json`, `reports/release/statistical_tests_v1_adjusted.json` |
| **[-3,22%, +2,53%]** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại Karaf | HC-FALCON v1 vs `history_cost` | Development (Karaf) | `reports/release/statistical_tests.json` (dòng 15-16) |
| **[-6,15%, -1,06%]** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại ActiveMQ | HC-FALCON v1 vs `history_cost` | Development (ActiveMQ) | `reports/release/statistical_tests.json` (dòng 30-31) |
| **[-0,96%, +3,01%]** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại Log4j2 | HC-FALCON v1 vs `history_cost` | Development (Log4j2) | `reports/release/statistical_tests.json` (dòng 45-46) |
| **-0,3797 / -0,6491 / -0,6800** | Kích thước hiệu ứng Cliff's delta ghép cặp (Paired Cliff's delta = (Wins-Losses)/n) tại Karaf / ActiveMQ / Log4j2 | HC-FALCON v1 vs `history_cost` | Development (3 dự án) | `reports/release/statistical_tests_v1_paired_effect_sizes.json` |
| **-0,3535 / -0,7556 / -0,5138** | Hệ số tương quan Rank-biserial $r_{rb}$ của kiểm định Wilcoxon tại Karaf / ActiveMQ / Log4j2 | HC-FALCON v1 vs `history_cost` | Development (3 dự án) | `reports/release/statistical_tests_v1_paired_effect_sizes.json` |
| **+29,72% / +39,14% / +28,69%** | Trung vị $\Delta\text{APFDc}$ vượt trội so với baseline `fl_only` tại Karaf / ActiveMQ / Log4j2 | HC-FALCON v1 vs `fl_only` | Development (161 build lỗi) | `reports/release/statistical_tests.json` (dòng 57, 72, 87) |

---

## 5. DỮ LIỆU FORENSIC VÀ HEAVY PREDECESSORS (STAGE 11 TRÊN STAGE 6)

### Phân biệt rõ hai con số "38" độc lập:
1. **Tập 38 build thắng của HC-FALCON v1 vs `history_cost`:** Tổng cộng 38/161 build lỗi trên cả 3 dự án (Karaf: 24 build; ActiveMQ: 10 build; Log4j2: 4 build).
2. **Tập 38 build lỗi tại ActiveMQ bị `MQTTAutoNioTest` chèn làm Heavy Predecessor:** Đúng 38 trên tổng số 57 build lỗi của riêng ActiveMQ (tổng cộng 102 lượt failure shift).
3. **Độ giao thoa giữa hai tập:** Hai tập này hoàn toàn khác nhau về bản chất và chỉ giao nhau đúng **3 build** tại ActiveMQ (`activemq:PR-965:8`, `activemq:PR-978:1`, `activemq:PR-984:3`).

### Giao thoa tập build thắng qua các thế hệ thuật toán (Winning Builds Intersection):
- **HC-FALCON v1:** 38 build thắng / 1 hòa / 122 thua vs `history_cost`.
- **Stage 8 (Restricted Semantic):** 31 build thắng / 24 hòa / 106 thua. Cơ chế lọc: Cửa sổ ứng viên động theo từng bước với điều kiện kép $q_b(i) \ge 0{,}95 \cdot q_b(t^*)$ và $c_b(i) \le 1{,}25 \cdot c_b(t^*)$ neo theo phần tử đầu baseline $t^*$ (`hc_falcon/restricted.py:27-28`). Giữ lại **15/38** build thắng của v1 (39,5%), mất 23 build, nhưng mở ra thêm **16 build thắng mới** mà v1 không có. (Bác bỏ nhận định sai "Stage 8 chặn/bóp chết 38 ca thắng").
- **Stage 11 (CNS-Greedy):** 38 build thắng / 1 hòa / 122 thua. Cơ chế: Lợi ích biên kết hợp $\text{gain}_{\text{CNS}}(i \mid S) = \alpha \cdot \frac{\Delta FL_b(i \mid S)}{n \cdot \sqrt{\max\left(c_b(i), \, 10^{-6}\right)}} + (1 - \alpha) \cdot w_b(i)$ (`hc_falcon/variants.py:26-27, 35-37, 46-48`; đề xuất tại `docs/11-improvement/hypothesis-and-design.md:13-17`) với $c_b(i)$ là thời lượng thô tính bằng giây, $w_b(i) = q_b(i) / \sum q$. Giữ lại **23/38** build thắng của v1 (60,5%), mất 15 build, và có **15 build thắng mới**.
  - **Xác nhận:** Tập 38 build thắng của Stage 11 và v1 **KHÔNG TRÙNG NHAU** (`identical_sets_v1_vs_stage11: False`), chỉ giao nhau 23 build.
- **Stage 12 (UGCS v2):** 35 build thắng / 10 hòa / 116 thua. Giữ lại **20/38** build thắng của v1 (52,6%).
- **Giao thoa cả 4 thế hệ:** Đúng **14 build lỗi** luôn duy trì vị thế thắng xuyên suốt từ v1 đến UGCS v2.
- **Nguồn dữ liệu:** Tệp đối soát `reports/stage12/winning_builds_intersection.json`.

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **+134.991,9 s** | Tổng thời gian trễ do các bài kiểm thử nặng bị đẩy lên trước test lỗi ($T_{add}$) | HC-FALCON v1 ($T_{add}$) | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **-95.892,7 s** | Tổng thời gian tiết kiệm được khi test lỗi được đẩy lên trước ($T_{rem}$) | HC-FALCON v1 ($T_{rem}$) | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **+39.099,3 s** | Độ trễ ròng tích lũy khiến người phát triển phải chờ thêm ($T_{net} = T_{add} - T_{rem} \approx 10,86$ giờ) | HC-FALCON v1 ($T_{net}$) | Development (161 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **-5.179,3 s** | Độ trễ ròng tại Karaf ($T_{add}=18.205,5\text{s}$, $T_{rem}=23.384,8\text{s}$; tỷ lệ thua vẫn 68,4%) | HC-FALCON v1 | Development (Karaf: 79 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **+43.886,3 s** | Độ trễ ròng tích lũy tại ActiveMQ ($T_{add}=115.759,2\text{s}$, $T_{rem}=71.872,9\text{s}$; tỷ lệ thua 82,5%) | HC-FALCON v1 | Development (ActiveMQ: 57 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **+392,2 s** | Độ trễ ròng tích lũy tại Log4j2 ($T_{add}=1.027,2\text{s}$, $T_{rem}=635,0\text{s}$; tỷ lệ thua 84,0%) | HC-FALCON v1 | Development (Log4j2: 25 build lỗi) | `reports/stage11/forensic-analysis.json`, `reports/stage12/predecessor_comparison.json` |
| **102** | Số lượt (failure shifts / failure instances) mà test `MQTTAutoNioTest` bị chèn làm Heavy Predecessor | `MQTTAutoNioTest` (ActiveMQ) | Development (xuất hiện ở 38/57 build lỗi) | `reports/stage11/forensic-analysis.json` (dòng 319-320) |
| **38** | Số physical build lỗi (trên 57 build lỗi của ActiveMQ) bị `MQTTAutoNioTest` gây nhiễu | `MQTTAutoNioTest` (ActiveMQ) | Development (ActiveMQ) | `reports/stage7/activemq/physical-diagnosis.json` |
| **150s – 250s** | Thời gian thực thi trung bình của lớp kiểm thử `MQTTAutoNioTest` | `MQTTAutoNioTest` (ActiveMQ) | CI runtime | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 465) |
| **76** | Số lượt test `StompAutoNioSslTest` bị chèn làm predecessor tại ActiveMQ | `StompAutoNioSslTest` | Development (ActiveMQ) | `reports/stage11/forensic-analysis.json` (dòng 324) |
| **42** | Số lượt test `Spring43FeaturesTest` bị chèn làm predecessor tại Karaf | `Spring43FeaturesTest` | Development (Karaf) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 462) |
| **40** | Số lượt test `SystemCommandSecurityTest` bị chèn làm predecessor tại Karaf | `SystemCommandSecurityTest` | Development (Karaf) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 463) |
| **24** | Số lượt test `RollingAppenderDirectWriteTest` bị chèn tại Log4j2 | `RollingAppenderDirectWriteTest` | Development (Log4j2) | `docs/BAO_CAO_TONG_HOP_DU_AN.md` (dòng 469) |

---

## 6. KẾT QUẢ BIẾN THỂ CUỐI UGCS V2 (STAGE 12) VÀ QUYẾT ĐỊNH CỔNG

| Con số | Ý nghĩa | Biến thể / Thuật toán | Tập dữ liệu | Đường dẫn file nguồn |
|:---|:---|:---|:---|:---|
| **0,7802 / 0,8799** | Điểm APFDc trung bình / trung vị suy ra từ chênh lệch ghép cặp ($\text{APFDc}_{hc} + \Delta$) tại Karaf | UGCS v2 (tuyệt đối) | Development (79 build lỗi) | `reports/stage12/ugcs_v2_absolute_apfdc.json` |
| **0,8471 / 0,9045** | Điểm APFDc trung bình / trung vị suy ra từ chênh lệch ghép cặp tại ActiveMQ | UGCS v2 (tuyệt đối) | Development (57 build lỗi) | `reports/stage12/ugcs_v2_absolute_apfdc.json` |
| **0,8952 / 0,9827** | Điểm APFDc trung bình / trung vị suy ra từ chênh lệch ghép cặp tại Log4j2 | UGCS v2 (tuyệt đối) | Development (25 build lỗi) | `reports/stage12/ugcs_v2_absolute_apfdc.json` |
| **0,8217 / 0,9203** | Điểm APFDc trung bình / trung vị suy ra trên toàn bộ 161 build lỗi | UGCS v2 (tuyệt đối) | Development (161 build lỗi) | `reports/stage12/ugcs_v2_absolute_apfdc.json` |
| **-0,0586 điểm phần trăm** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại Karaf (-0,0005856) | UGCS v2 | Development (79 build lỗi) | `reports/stage12/development-screen.json` (dòng 38), `reports/stage12/stage12_statistical_tests.json` |
| **-0,2235 điểm phần trăm** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại ActiveMQ (-0,0022354) | UGCS v2 | Development (57 build lỗi) | `reports/stage12/development-screen.json` (dòng 58), `reports/stage12/stage12_statistical_tests.json` |
| **-0,0017 điểm phần trăm** | Trung vị $\Delta\text{APFDc}$ so với `history_cost` tại Log4j2 (-0,0000170) | UGCS v2 | Development (25 build lỗi) | `reports/stage12/development-screen.json` (dòng 178), `reports/stage12/stage12_statistical_tests.json` |
| **+0,4788 điểm phần trăm** | Điểm trung bình Mean $\Delta\text{APFDc}$ so với `history_cost` tại Karaf | UGCS v2 | Development (79 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **-0,1508 điểm phần trăm** | Điểm trung bình Mean $\Delta\text{APFDc}$ so với `history_cost` tại ActiveMQ | UGCS v2 | Development (57 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **+0,1663 điểm phần trăm** | Điểm trung bình Mean $\Delta\text{APFDc}$ so với `history_cost` tại Log4j2 | UGCS v2 | Development (25 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **[-0,2659, +1,4488] điểm %** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại Karaf | UGCS v2 vs `history_cost` | Development (79 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **[-0,8112, +0,6703] điểm %** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại ActiveMQ | UGCS v2 vs `history_cost` | Development (57 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **[-0,1606, +0,6060] điểm %** | Khoảng tin cậy 95% Bootstrap của Mean $\Delta\text{APFDc}$ tại Log4j2 | UGCS v2 vs `history_cost` | Development (25 build lỗi) | `reports/stage12/stage12_statistical_tests.json` |
| **$p = 0,01268$ ($p_{\text{holm}} = 0,02537$)** | P-value kiểm định Wilcoxon tại Karaf (W = 1067,0; Holm hiệu chỉnh 3 dự án) | UGCS v2 vs `history_cost` | Development (Karaf) | `reports/stage12/stage12_statistical_tests.json` |
| **$p = 6,30 \times 10^{-5}$ ($p_{\text{holm}} = 1,89 \times 10^{-4}$)** | P-value kiểm định Wilcoxon tại ActiveMQ (W = 318,0; Holm hiệu chỉnh) | UGCS v2 vs `history_cost` | Development (ActiveMQ) | `reports/stage12/stage12_statistical_tests.json` |
| **$p = 0,18732$ ($p_{\text{holm}} = 0,18732$)** | P-value kiểm định Wilcoxon tại Log4j2 (W = 113,0; Holm hiệu chỉnh; không có ý nghĩa thống kê) | UGCS v2 vs `history_cost` | Development (Log4j2) | `reports/stage12/stage12_statistical_tests.json` |
| **-0,4430 / -0,6140 / -0,4400** | Kích thước hiệu ứng Cliff's delta ghép cặp (Paired Cliff's delta = (Wins-Losses)/n) tại Karaf / ActiveMQ / Log4j2 | UGCS v2 vs `history_cost` | Development (3 dự án) | `reports/stage12/stage12_statistical_tests_paired_effect_sizes.json` |
| **-0,3102 / -0,6059 / -0,2681** | Hệ số tương quan Rank-biserial $r_{rb}$ của kiểm định Wilcoxon tại Karaf / ActiveMQ / Log4j2 | UGCS v2 vs `history_cost` | Development (3 dự án) | `reports/stage12/stage12_statistical_tests_paired_effect_sizes.json` |
| **-0,0018 / -0,0249 / -0,0144** | Cliff's delta không ghép cặp (Unpaired cross-product diagnostic, bị triệt tiêu do phương sai giữa các build) | Đo lường chẩn đoán | Development (3 dự án) | `reports/stage12/stage12_statistical_tests_paired_effect_sizes.json` |
| **20 Thắng / 4 Hòa / 55 Thua** | Tỷ số thắng/hòa/thua của UGCS v2 tại Karaf (Thắng 25,32%) | UGCS v2 vs `history_cost` | Development (Karaf) | `reports/stage12/stage12_statistical_tests.json` |
| **9 Thắng / 4 Hòa / 44 Thua** | Tỷ số thắng/hòa/thua của UGCS v2 tại ActiveMQ (Thắng 15,79%) | UGCS v2 vs `history_cost` | Development (ActiveMQ) | `reports/stage12/stage12_statistical_tests.json` |
| **6 Thắng / 2 Hòa / 17 Thua** | Tỷ số thắng/hòa/thua của UGCS v2 tại Log4j2 (Thắng 24,00%) | UGCS v2 vs `history_cost` | Development (Log4j2) | `reports/stage12/stage12_statistical_tests.json` |
| **+43.699,3 s** | Tổng thời gian thêm $T_{add}$ của UGCS v2 (Karaf: 4.858,5 s; ActiveMQ: 38.644,6 s; Log4j2: 196,2 s) | UGCS v2 ($T_{add}$) | Development (161 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **-53.330,6 s** | Tổng thời gian bớt $T_{rem}$ của UGCS v2 (Karaf: -11.378,1 s; ActiveMQ: -41.746,1 s; Log4j2: -206,4 s) | UGCS v2 ($T_{rem}$) | Development (161 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **-9.631,3 s** | Tổng thời gian tiền nhiệm ròng ($T_{net}$) cắt giảm so với `history_cost` (-6.519,6 s tại Karaf, -3.101,4 s tại ActiveMQ, -10,2 s tại Log4j2), tuy nhiên 116/161 build (72,05%) vẫn thua `history_cost` về $\Delta\text{APFDc}$ | UGCS v2 vs `history_cost` | Development (161 build lỗi) | `reports/stage12/development-screen.json` (dòng 377, 630, 883), `reports/stage12/predecessor_comparison.json` |
| **+3,0 điểm %** | Ngưỡng yêu cầu tối thiểu của cổng hiệu quả (Effect Gate) so với cả 2 baseline | Tiêu chí Effect Gate | Preregistration | `configs/hc-falcon-v2-preregistered.json` |
| **0/3** | Số lượng dự án đạt tiêu chí Effect Gate $\rightarrow$ Thất bại (NO-GO) | UGCS v2 | Development (3 dự án) | `reports/stage12/development-screen.json` (dòng 34) |
| **0,11 ms ($0,0001126$ s)** | Độ trễ trung vị mỗi stage của `history_cost` (khóa `median_latency_hc_seconds`, trong đó `hc` là viết tắt của `history_cost`, tuyệt đối không phải HC-FALCON) | `history_cost` | Development (171 stages) | `reports/stage12/development-screen.json` (dòng 112) |
| **53,82 ms ($0,053819$ s)** | Độ trễ trung vị mỗi stage của UGCS v2 (khóa `median_latency_ugcs_seconds`) | UGCS v2 | Development (171 stages) | `reports/stage12/development-screen.json` (dòng 111) |
| **Không xác định được** | Phân vị P95 tuyệt đối (ms) của thời gian chạy từng stage cho `history_cost` và UGCS v2 (chỉ có trung vị và tỷ lệ trần P95 toàn cục được lưu) | Cả hai phương pháp | Development (171 stages) | `reports/stage12/development-screen.json` |
| **-65,56 s vs -82,53 s** | $T_{net}$ trung bình mỗi build vật lý tại Karaf (v1: $-5.179,3 / 79$ s vs UGCS v2: $-6.519,6 / 79$ s) | v1 vs UGCS v2 | Development (79 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **+769,94 s vs -54,41 s** | $T_{net}$ trung bình mỗi build vật lý tại ActiveMQ (v1: $+43.886,3 / 57$ s vs UGCS v2: $-3.101,4 / 57$ s) | v1 vs UGCS v2 | Development (57 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **+15,69 s vs -0,41 s** | $T_{net}$ trung bình mỗi build vật lý tại Log4j2 (v1: $+392,2 / 25$ s vs UGCS v2: $-10,2 / 25$ s) | v1 vs UGCS v2 | Development (25 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **+242,85 s vs -59,82 s** | $T_{net}$ trung bình mỗi build vật lý toàn bộ tập phát triển (v1: $+39.099,3 / 161$ s vs UGCS v2: $-9.631,3 / 161$ s) | v1 vs UGCS v2 | Development (161 build lỗi) | `reports/stage12/predecessor_comparison.json` |
| **656,4 MiB ($688.287.744$ bytes)** | Mức đỉnh bộ nhớ RAM chiếm dụng thực tế (Peak RSS) | UGCS v2 | Development | `reports/stage12/development-screen.json` (dòng 110) |
| **$\le 8{,}0$ GiB** | Ngưỡng trần bộ nhớ cho phép của cổng kỹ thuật (Memory Gate) $\rightarrow$ ĐẠT | Tiêu chí Memory Gate | Preregistration | `configs/hc-falcon-v2-preregistered.json` |
| **14.257,90$\times$ ($+1.425.790\%$)** | Tỷ lệ overhead trần P95 quan sát chính thức so với `history_cost` (mẫu số chuẩn hóa là độ trễ của `history_cost`) | UGCS v2 | Development (171 stages) | `reports/stage12/development-screen.json` (dòng 89, 109) |
| **$\le 1,10\times$ ($+10\%$)** | Ngưỡng trần overhead cho phép của cổng thời gian chạy (Runtime Gate) $\rightarrow$ KHÔNG ĐẠT (VI PHẠM) | Tiêu chí Runtime Gate | Preregistration | `configs/hc-falcon-v2-preregistered.json` |
| **NO-GO** | Quyết định thẩm định chính thức: Giữ niêm phong vĩnh viễn 142 build lỗi tập Reserved | Quyết định nghiên cứu | Toàn dự án | `reports/stage12/development-screen.json` (dòng 11) |

---

## 7. RỦI RO TÍNH HỢP LỆ VÀ ĐỐI SOÁT TẬP DỮ LIỆU (THREATS TO VALIDITY)

Mục này ghi nhận trung thực các ranh giới phương pháp luận và kiểm định tính hợp lệ của dữ liệu theo đúng chuẩn mực nghiên cứu thực nghiệm:

1. **Kiểm tra rò rỉ dữ liệu (Data Leakage & Split Audit):**
   - **Xác nhận không rò rỉ:** Toàn bộ quá trình thực nghiệm, chẩn đoán nguyên nhân sâu (Stage 7, Stage 11 Forensic) và đánh giá các biến thể thuật toán (`topic_raw_v1`, `normalized_v1`, `restricted_v1`, `cns_v1`, `ugcs_v2`) **hoàn toàn chỉ chạy trên tập Sàng lọc Phát triển (Development Screening Split: 161 physical build lỗi)**.
   - **Bảo toàn niêm phong:** Tập Xác nhận Niêm phong (**Reserved Confirmation Split: 358 physical builds, 142 build lỗi**) được giữ niêm phong 100% (`reserved_opened: false`). Không có bất kỳ dòng dữ liệu nào thuộc tập Reserved bị đọc điểm, xếp hạng hay rò rỉ vào quá trình thiết kế thuật toán xuyên suốt vòng đời dự án.

2. **Rủi ro về tính đại diện và khám phá (Exploratory Nature of Karaf):**
   - Dự án Apache Karaf (315 build, 79 build lỗi) được sử dụng trọn vẹn làm tập khám phá (exploratory) từ Stage 3 và không có phân tách holdout/reserved. Mọi kết luận trên Karaf phải được diễn giải dưới góc độ phân tích khám phá giả thuyết.

3. **Rủi ro bậc tự do của nhà nghiên cứu ("Garden of Forking Paths") và phạm vi hiệu chỉnh Holm:**
   - Các biến thể cải tiến liên tiếp ở Stage 8 (`restricted_v1`), Stage 11 (`cns_v1`) và Stage 12 (`ugcs_v2`) đều được đề xuất và tinh chỉnh dựa trên quan sát chẩn đoán trên **chính 161 build lỗi của tập phát triển này**.
   - Việc thử nghiệm lặp lại các giả thuyết trên cùng một tập quan sát tiềm ẩn rủi ro khai thác ngẫu nhiên các đặc điểm cục bộ của tập dữ liệu (Gelman & Loken, 2013).
   - **Phạm vi hiệu chỉnh Holm:** Các giá trị $p_{\text{holm}}$ trong báo cáo hiện tại **chỉ hiệu chỉnh theo gia đình 3 dự án** ($m=3$) cho từng biến thể riêng biệt, chưa bao quát toàn bộ không gian giả thuyết tích lũy qua nhiều thế hệ thuật toán.
   - **Biện pháp kiểm soát chặt chẽ:** Đồ án đã áp dụng cơ chế tiền đăng ký (Preregistration) cố định mã nguồn, cấu hình và ngưỡng cổng trước khi chạy Stage 12; nghiêm cấm chạy quét tinh chỉnh siêu tham số (zero tuning rounds); và kiên quyết ra quyết định NO-GO, giữ niêm phong tập Reserved thay vì mở tập Reserved để tìm kiếm kết quả thuận lợi.

4. **Đơn vị thống kê vật lý loại trừ hiện tượng thổi phồng mẫu (Pseudo-replication):**
   - Trong các hệ thống CI đa module (như Log4j2), một lần commit có thể kích hoạt nhiều build stage độc lập (155 stages). Việc gộp các stage cùng commit về **đơn vị physical build (78 physical builds, 25 build lỗi)** trước khi tính trung bình paired delta là bắt buộc để tránh vi phạm giả định độc lập của kiểm định thống kê.
