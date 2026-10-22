# KẾ HOẠCH TRIỂN KHAI BÁO CÁO ĐỒ ÁN LIÊN NGÀNH

## Đề tài: Ưu tiên bộ kiểm thử bằng tối ưu hóa Submodular kết hợp lịch sử lỗi và chi phí thực thi (HC-FALCON)

**Phụ đề đề xuất:** Đánh giá thực nghiệm trên Defects4J và môi trường CI thực tế

---

## I. ĐÁNH GIÁ HIỆN TRẠNG TEMPLATE LATEX

Template hiện tại được viết cho một đề tài khác ("Khảo sát về trò chơi hợp tác và ứng dụng trong bài toán phá sản"). Giữ nguyên cấu trúc kỹ thuật LaTeX (class, package, định dạng), thay toàn bộ nội dung.

| File | Trạng thái | Hành động |
|:---|:---:|:---|
| `main.tex` | ⚠️ Sửa lớn | Cập nhật metadata PDF, header, cấu trúc section mới (5 chương + kết luận + phụ lục) |
| `phenikaa_template_cover.tex` | ⚠️ Sửa | Đổi tên đề tài, học phần, thông tin sinh viên/GVHD |
| `abstract.tex` | ⚠️ Viết mới | Tóm tắt cho HC-FALCON (viết sau cùng) |
| `acknowledgement.tex` | ⚠️ Sửa | Cập nhật tên, thời gian |
| `pledge.tex` | ⚠️ Sửa | Cập nhật tên, thời gian; đối chiếu quy định về khai báo hỗ trợ AI (xem mục VIII) |
| `viettat.tex` | ⚠️ Viết mới | Danh sách viết tắt cho TCP/HC-FALCON |
| `SEC1.tex` | ⚠️ Viết mới | Chương 1 |
| `SEC2.tex` | ⚠️ Viết mới | Chương 2 |
| `ketluan.tex` | ⚠️ Viết mới | Kết luận và hướng phát triển |
| `ref.bib` | ⚠️ Thay mới | Bộ tài liệu tham khảo cho TCP/SE |
| `SEC3.tex`, `SEC4.tex`, `SEC5.tex` | 🆕 Tạo mới | Ba chương bổ sung |
| `phuluc.tex` | 🆕 Tạo mới | Phụ lục A (bảng mã Stage), B (dữ liệu chi tiết), C (mã nguồn minh họa) |

---

## II. CẤU TRÚC BÁO CÁO ĐỀ XUẤT

### Phần mở đầu (đánh số La Mã)

| Nội dung | File | Dung lượng |
|:---|:---|:---:|
| Trang bìa | `phenikaa_template_cover.tex` | 1 trang |
| Lời cảm ơn | `acknowledgement.tex` | 1 trang |
| Lời cam đoan | `pledge.tex` | 1 trang |
| Tóm tắt nội dung | `abstract.tex` | 0.5–1 trang |
| Mục lục, Danh sách hình, Danh sách bảng | Tự sinh | 3–4 trang |
| Danh sách chữ viết tắt | `viettat.tex` | 1 trang |

### Phần nội dung chính (đánh số Ả Rập)

| Chương | Tiêu đề | File | Dung lượng | Vai trò |
|:---:|:---|:---|:---:|:---|
| **1** | Giới thiệu | `SEC1.tex` | 5–7 trang | Đặt vấn đề, RQ, phạm vi |
| **2** | Tổng quan lý thuyết và các công trình liên quan | `SEC2.tex` | 8–12 trang | Nền tảng và định vị đề tài |
| **3** | Phương pháp đề xuất: HC-FALCON | `SEC3.tex` | 8–10 trang | Mô hình, chứng minh, thuật toán |
| **4** | Thực nghiệm và kết quả | `SEC4.tex` | 12–15 trang | **Chỉ bằng chứng và số liệu** |
| **5** | Thảo luận | `SEC5.tex` | 5–7 trang | **Diễn giải, nguyên nhân, ý nghĩa** |
| — | Kết luận và hướng phát triển | `ketluan.tex` | 2–3 trang | Nhận định tổng hợp |

### Phần cuối

| Nội dung | Dung lượng |
|:---|:---:|
| Tài liệu tham khảo (BibTeX, IEEE) | 2–3 trang |
| Phụ lục A, B, C | 3–5 trang |

> [!NOTE]
> **Dung lượng:** phần nội dung chính (Chương 1–5 và Kết luận) khoảng 40–54 trang; cộng phần mở đầu (~8 trang La Mã) và tài liệu tham khảo, tổng thể khoảng 52–65 trang. Cần đối chiếu quy định số trang tối thiểu/tối đa của khoa.

---

## III. CÁC CÂU HỎI NGHIÊN CỨU VÀ BẢNG ÁNH XẠ

| RQ | Câu hỏi | Bằng chứng ở Chương 4 | Trả lời ở Chương 5 |
|:---:|:---|:---|:---|
| **RQ1** | Tái lập FALCON trên Defects4J có cho kết quả tương đương bài gốc không, và những yếu tố kỹ thuật nào ảnh hưởng đến kết quả? | 4.2.1, 4.2.2, 4.2.3 | 5.1 |
| **RQ2** | Bổ sung lịch sử lỗi và chi phí thực thi vào FALCON (HC-FALCON) có cải thiện APFDc so với baseline `history_cost` trên CI thực tế không? | 4.3.1, 4.3.2 | 5.1, 5.2 |
| **RQ3** | Các biến thể cải tiến (hạn chế ngữ nghĩa, CNS-Greedy, UGCS v2) có thu hẹp được khoảng cách với baseline không? | 4.3.2, 4.3.3 | 5.1 |
| **RQ4** | Chi phí tính toán (thời gian, bộ nhớ) của phương pháp có chấp nhận được trong CI không? | 4.3.4, 4.3.5 | 5.1 |
| **RQ5** | Những khác biệt nào giữa hai môi trường đánh giá có thể liên quan đến kết quả quan sát được? | 4.4 (4.4.1, 4.4.2), 4.5 | 5.2, 5.3 |

Bảng này cần xuất hiện ở Mục 1.4 (câu hỏi) và Mục 5.1 (trả lời). Nếu một RQ không có dòng bằng chứng nào ở Chương 4, hoặc phải sửa RQ, hoặc phải bổ sung thực nghiệm.

---

## IV. DÀN Ý CHI TIẾT TỪNG CHƯƠNG

### Chương 1: Giới thiệu

```
1.1. Bối cảnh và động lực
     - Vai trò của kiểm thử trong CI/CD
     - Test suite quy mô lớn, thời gian chạy kéo dài
     - Bài toán TCP và tầm quan trọng
1.2. Khoảng trống nghiên cứu
     - FALCON: mạnh ngữ nghĩa, thiếu lịch sử lỗi + chi phí
     - DANTE: mạnh lịch sử + chi phí, thiếu ngữ nghĩa
     - Câu hỏi: kết hợp cả ba có tốt hơn không?
1.3. Mục tiêu nghiên cứu
     - Đặt theo hướng đánh giá thực nghiệm khả năng kết hợp
       (không hứa hẹn phương pháp vượt trội)
     - Xây dựng HC-FALCON; tái lập FALCON; đánh giá trên CI thực tế;
       phân tích nguyên nhân
1.4. Các câu hỏi nghiên cứu (bảng RQ1–RQ5, mục III)
1.5. Phạm vi và giới hạn
     - Java; class-level (LRTS), method-level (Defects4J); 3 dự án Apache
1.6. Cấu trúc báo cáo
```

### Chương 2: Tổng quan lý thuyết và các công trình liên quan

```
2.1. Kiểm thử hồi quy và tích hợp liên tục
     2.1.1. Kiểm thử phần mềm
     2.1.2. CI/CD và kiểm thử hồi quy
     2.1.3. Bài toán TCP (định nghĩa hình thức)
2.2. Các độ đo hiệu quả TCP
     2.2.1. APFD
     2.2.2. APFDc
     2.2.3. Time to First Failure (TTFF)
     2.2.4. Recall@k%
2.3. Tối ưu hóa Submodular
     2.3.1. Hàm tập hợp và tính Submodular
     2.3.2. Hàm Facility Location
     2.3.3. Cận xấp xỉ (1 − 1/e) của thuật toán Greedy
     2.3.4. Lazy Greedy
2.4. Biểu diễn ngữ nghĩa mã nguồn
     2.4.1. Code Language Models (CodeBERT, UniXcoder)
     2.4.2. Embedding và cosine similarity
2.5. Các công trình liên quan
     2.5.1. FALCON (Mensah-Boateng et al., ICST 2026)
     2.5.2. DANTE (Reale et al., ICST 2026)
     2.5.3. TCP dựa trên lịch sử lỗi (gồm công trình nền tảng, ví dụ
            Rothermel, Elbaum, Spieker/RETECS)
     2.5.4. TCP nhận thức chi phí (APFDc, Elbaum; tổng quan Yoo & Harman)
     2.5.5. Định vị đề tài
2.6. Tổng kết chương
```

### Chương 3: Phương pháp đề xuất: HC-FALCON

```
3.1. Tổng quan kiến trúc
     - Hai pha: Offline (embedding) và Online (replay)
     - Nguyên tắc chống rò rỉ dữ liệu
3.2. Mô hình toán học HC-FALCON v1
     3.2.1. Hàm mục tiêu kết hợp F_N(S)
     3.2.2. Thành phần Facility Location FL(S)
     3.2.3. Ước lượng rủi ro Beta-Bernoulli p_b(t)
     3.2.4. Hệ số tin cậy conf_b(t)
     3.2.5. Chỉ số rủi ro-chi phí q_b(t)
     3.2.6. Hai biến thể trọng số: topic_raw và normalized
3.3. Tính chất Monotone Submodular
     - Định lý 1, chứng minh, ý nghĩa cận 1 − 1/e
3.4. Khoảng trống giữa hàm mục tiêu proxy và độ đo APFDc
     - Phản ví dụ minh hoạ
3.5. Các biến thể cải tiến
     3.5.1. Biến thể hạn chế ngữ nghĩa (Restricted Semantic, Stage 8)
     3.5.2. CNS-Greedy (Stage 11)
     3.5.3. UGCS v2 (Stage 12): thuật toán 4 bước
3.6. Phân tích độ phức tạp (thời gian, bộ nhớ từng biến thể)
3.7. Tổng kết chương
```

### Chương 4: Thực nghiệm và kết quả (chỉ bằng chứng)

```
4.1. Thiết kế thực nghiệm
     4.1.1. Hệ thống câu hỏi nghiên cứu (RQ1–RQ5)
     4.1.2. Hai trục đánh giá độc lập
     4.1.3. Tập dữ liệu Defects4J
     4.1.4. Tập dữ liệu LRTS trên môi trường CI thực tế
     4.1.5. Các đường cơ sở đối chứng (Baselines)
     4.1.6. Tiêu chí quyết định tiền đăng ký (Decision Gates)
     4.1.7. Phân tách dữ liệu và cơ chế niêm phong tập kiểm chứng
     4.1.8. Phương pháp thống kê và kiểm định ghép cặp
4.2. Kết quả Trục 1: Tái lập FALCON trên benchmark Defects4J
     4.2.1. Đối chiếu APFD trên 6 dự án phần mềm
     4.2.2. Phân tích phân rã kỹ thuật Bridge trên dự án Chart
     4.2.3. Phát hiện kỹ thuật về Attention Mask
4.3. Kết quả Trục 2: HC-FALCON trên hệ thống CI thực tế (LRTS)
     4.3.1. Mốc đối chứng cơ sở ngẫu nhiên trên chuỗi thời gian CI
     4.3.2. Diễn tiến các biến thể từ HC-FALCON v1 đến CNS-Greedy
     4.3.3. Kết quả của biến thể cuối UGCS v2 (Stage 12)
     4.3.4. Đánh giá các chỉ tiêu kỹ thuật (Overhead thời gian và Bộ nhớ)
     4.3.5. Phán quyết thẩm định theo tiêu chí tiền đăng ký
4.4. Dữ liệu chẩn đoán sâu về hiện tượng Heavy Predecessors
     4.4.1. Thống kê độ trễ ròng tích lũy trên 161 build lỗi
     4.4.2. Các lớp kiểm thử đóng vai trò thủ phạm gây trễ điển hình
4.5. Phân tích bóc tách các thành phần (Ablation Study)
4.6. Tổng kết chương (chỉ nêu kết quả, chưa giải thích nguyên nhân)
```

### Chương 5: Thảo luận (chỉ diễn giải)

```
5.1. Trả lời RQ1–RQ5 (bảng tổng hợp, trỏ về Chương 4)
5.2. Giải thích kết quả, phân theo mức bằng chứng
     5.2.1. Có bằng chứng trực tiếp
            - Heavy Predecessors và chuỗi nhân quả
              (hiện tượng → cơ chế → hệ quả trên APFDc)
     5.2.2. Có bằng chứng gián tiếp
            - Baseline history_cost đã khai thác gần hết tín hiệu
            - Xung đột giữa đa dạng toàn cục và lỗi cục bộ
     5.2.3. Giả thuyết chưa kiểm chứng
            - Mô hình ngữ nghĩa tĩnh không phản ánh trạng thái runtime
5.3. Ý nghĩa của kết quả âm
     5.3.1. Giá trị của kết quả âm trong nghiên cứu SE
     5.3.2. Ranh giới áp dụng: method-level và class-level
     5.3.3. Bài học cho thực hành CI
5.4. Đóng góp
     5.4.1. Tái lập FALCON trên 6 dự án, sai lệch so với bài gốc là [X]
     5.4.2. Phát hiện và đo lường hiện tượng Heavy Predecessors
     5.4.3. Kiến trúc chống rò rỉ dữ liệu
     5.4.4. Quy trình đăng ký tiêu chí trước và niêm phong dữ liệu
5.5. Giới hạn và mối đe dọa đến tính hợp lệ
     5.5.1. External validity
     5.5.2. Internal validity
     5.5.3. Construct validity
     5.5.4. Giới hạn về độ phức tạp thuật toán
5.6. Tổng kết chương
```

### Kết luận và hướng phát triển

```
- Nhận định tổng hợp (không chỉ nhắc lại từng chương):
  điều gì đã học được về việc kết hợp ba nguồn tín hiệu
- Bài học rút ra
- Hướng nghiên cứu tương lai:
  1. TCP mức method trên CI
  2. Semantic chỉ dùng cho cold-start
  3. Chỉ số cho CI chạy song song/chia shard
  4. Mở rộng sang Python, Go, Rust
```

### Phụ lục

```
A. Bảng đối chiếu mã nội bộ (Stage 6–12) với tên mô tả dùng trong báo cáo
B. Bảng dữ liệu chi tiết theo từng dự án/build (làm sau nếu còn trang/thời gian)
C. Mã nguồn minh hoạ (phần cốt lõi của thuật toán)
```

---

## V. THỨ TỰ TRIỂN KHAI

Viết từ phần có số liệu chắc chắn nhất đến phần phụ thuộc vào kết quả cuối cùng.

| Phase | Công việc | File |
|:---:|:---|:---|
| **0** | Chuẩn bị khung; lập **bảng nguồn sự thật số liệu**; chốt RQ; chốt bảng thuật ngữ và tên mô tả cho các Stage | `main.tex`, bìa, cảm ơn, cam đoan, `viettat.tex`, `ref.bib`, file số liệu |
| **1** | Chương 4 (kèm chạy bổ sung kiểm định thống kê và CI) | `SEC4.tex` |
| **2** | Chương 3 (tự viết phần chứng minh) | `SEC3.tex` |
| **3** | Chương 2 | `SEC2.tex` |
| **4** | Chương 5 và Kết luận | `SEC5.tex`, `ketluan.tex` |
| **5** | Chương 1, Abstract, Phụ lục | `SEC1.tex`, `abstract.tex`, `phuluc.tex` |
| **6** | Rà soát cuối: số liệu, thuật ngữ, cross-reference, chính tả, định dạng | Toàn bộ |

Mỗi phase xong thì review trước khi sang phase tiếp.

---

## VI. QUY TẮC CHUẨN VIẾT BÁO CÁO ĐỒ ÁN

### A. Quy tắc hình thức

1. **Căn lề:** Trái 3.5 cm, Phải 2.0 cm, Trên 3.5 cm, Dưới 3.0 cm.
2. **Font chữ:** Times New Roman, cỡ 12pt (`\documentclass[12pt,a4paper]{article}`).
3. **Giãn dòng:** 1.5 dòng (`\onehalfspacing`).
4. **Đánh số trang:** front matter số La Mã; main matter số Ả Rập từ 1.
5. **Đánh số chương mục:** tự động theo `\section`, `\subsection`, `\subsubsection`.
6. **Đánh số hình, bảng, công thức:** theo chương (Hình 3.1, Bảng 4.2, Công thức 2.5).
7. **Tài liệu tham khảo:** IEEE (`ieeetr`).

### B. Quy tắc nội dung

1. Mỗi chương có phần mở đầu (1–2 đoạn) và phần tổng kết chuyển tiếp.
2. Mọi hình/bảng có caption rõ ràng, được nhắc đến và phân tích trong văn bản; bảng ghi nguồn dữ liệu và cách tính ở chú thích dưới bảng.
3. Mọi công thức quan trọng được đánh số, giải thích từng ký hiệu.
4. Thuật ngữ chuyên ngành dùng lần đầu: tiếng Việt kèm tiếng Anh trong ngoặc.
5. Mọi tuyên bố khoa học có trích dẫn hoặc bằng chứng thực nghiệm.
6. Số liệu lấy từ **một file nguồn sự thật duy nhất** (`docs/facts.md`); Chương 1, Abstract, Chương 4, Chương 5 và Kết luận cùng trích từ đó.
7. Mỗi đoạn một ý chính, 5–8 câu, có câu chủ đề.
8. Phát biểu về nguyên nhân phải ghi rõ mức bằng chứng (trực tiếp, gián tiếp, giả thuyết) và dùng động từ tương ứng ("cho thấy", "gợi ý", "có thể"), không dùng giọng khẳng định cho giả thuyết.

### C. Quy tắc trình bày toán học

1. Dùng `equation` hoặc `align` cho công thức cần đánh số; `$...$` cho biểu thức inline.
2. Định nghĩa mọi ký hiệu trước khi dùng.
3. Chứng minh dùng môi trường `cm` đã định nghĩa trong template.
4. Dùng `\label`/`\ref`/`\eqref` cho mọi cross-reference.

---

## VII. QUY TẮC ĐỂ VĂN BẢN TỰ NHIÊN, MANG DẤU ẤN CÁ NHÂN

### Nhóm 1: Ngôn ngữ và giọng văn

1. **Tránh mở đầu sáo rỗng.** Vào thẳng vấn đề thực tế.
2. **Không dùng tính từ mức độ rỗng nghĩa.** Thay bằng con số đo đạc cụ thể.
3. **Độ dài câu đa dạng.** Xen câu ngắn (8–12 từ) với câu dài (30–40 từ); không viết câu quá 50 từ.
4. **Tránh đối xứng quá hoàn hảo.** Thay đổi giữa văn xuôi, bullet và bảng tùy ngữ cảnh.
5. **Giọng học thuật nhưng có cá tính.** Được dùng câu hỏi tu từ, câu khẳng định dứt khoát.

### Nhóm 2: Cấu trúc và logic

6. **Mạch dẫn dắt: mỗi đoạn trả lời câu hỏi mà đoạn trước vừa mở ra.**

   *Nguyên tắc:* đọc xong một đoạn, người đọc đoán được đoạn sau thuộc loại nào. Quan hệ giữa hai đoạn liền kề phải là nhân quả hoặc đối lập thật, không chỉ "cùng chủ đề".

   *Ví dụ minh hoạ (đã cập nhật đối chuẩn nhất quán):*
   > Trên Defects4J, FALCON đạt APFD trung bình 0,726, vượt xa mức phân bổ ngẫu nhiên (~0,500). Khi chuyển sang CI thực tế (LRTS), HC-FALCON v1 cũng duy trì điểm số vượt trội so với baseline Random (đạt APFDc trung bình từ 0,771 đến 0,901 so với ~0,490 của Random). Tuy nhiên, khi đối chiếu với baseline vận hành thực tế của CI là `history_cost`, HC-FALCON v1 lại thua ở phần lớn các build lỗi (122/161 build). Sự đảo chiều này không xuất phát từ lỗi cài đặt: bước tái lập ở Mục 4.2 đã khớp với bài gốc. Điều thay đổi là bản chất của dữ liệu và sự hiện diện của tín hiệu chi phí/lịch sử mạnh, và để thấy cụ thể cơ chế tác động, cần nhìn vào những test class bị xếp lên đầu danh sách.

7. **Chuyển tiếp tự nhiên giữa các đoạn.**
8. **Trích dẫn tự nhiên theo ngữ cảnh.**
9. **Thừa nhận điểm yếu cụ thể.**

### Nhóm 3: Dữ liệu và lập luận

10. **Số liệu cụ thể kèm kiểm định thống kê.**
11. **Trình bày trung thực kết quả âm.**
12. **Ví dụ cụ thể cho khái niệm trừu tượng (như test class `MQTTAutoNioTest`).**

    *Ví dụ minh hoạ:* Thay vì chỉ phát biểu trừu tượng "một số test chạy lâu bị đẩy lên đầu làm giảm APFDc", hãy chỉ rõ đối tượng: "`MQTTAutoNioTest` trong ActiveMQ là ví dụ điển hình của hiện tượng Heavy Predecessors, xuất hiện 102 lượt trong 38/57 build lỗi của dự án, gây thiệt hại thời gian cộng dồn lớn trước khi test phát hiện lỗi đầu tiên được thực thi."

### Nhóm 4: Kỹ thuật LaTeX

13. **Hình vẽ:** dùng biểu đồ trong `reports/figures/`; bổ sung TikZ.
14. **Bảng:** có nguồn gốc rõ ràng, không quá lớn.
15. **Cross-reference nhất quán:** dùng `\label{}`, `\ref{}`, `\eqref{}`.
16. **Thuật ngữ nhất quán:** tuân theo `docs/glossary.md`.

---

## VIII. DANH SÁCH CẤM VÀ LƯU Ý

1. Không copy-paste từ `BAO_CAO_TONG_HOP_DU_AN.md`.
2. Không dùng emoji, icon trong văn bản chính.
3. Không viết câu quá dài (> 50 từ).
4. Phân tách rạch ròi: Chương 4 chỉ có số liệu; Chương 5 chỉ có diễn giải.
5. Không dùng "chúng tôi" (làm đồ án cá nhân, xưng "em" ở cảm ơn/cam đoan, phần chính viết khách quan).
6. Không để hình/bảng trôi xa đoạn văn nhắc tới nó.
7. Không dùng mã nội bộ (Stage X) mà không kèm tên mô tả.
8. Không tự bịa số liệu, p-value hay trích dẫn; thiếu thì ghi `TODO:`.
