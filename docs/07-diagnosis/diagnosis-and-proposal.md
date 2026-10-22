# Phân tích sau pilot — đề xuất để review

Đã phân tích checkpoint development của giai đoạn 6; chưa triển khai thuật toán mới. Đã kiểm tra toàn bộ hash của bằng chứng giai đoạn 6 trước khi đọc. Reserved vẫn đóng. Các phát hiện dưới đây mang tính mô tả và hình thành giả thuyết, không phải xác nhận độc lập.

## Kết quả chính

| Dự án | Build có APFDc | Thắng / hòa / thua History+cost | Median Δ APFDc (điểm %) |
|---|---:|---:|---:|
| karaf | 79 | 24 / 1 / 54 | -1.265 |
| activemq | 57 | 10 / 0 / 47 | -1.407 |
| log4j | 25 | 4 / 0 / 21 | -0.117 |

Seed được gộp trong stage; chênh lệch stage được lấy mean trong physical build. Chỉ các cặp có metric xác định tham gia bảng này. Log4j có mean delta dương nhưng 21/25 physical build thua: một số build tăng nhiều kéo mean lên, không thay đổi kết luận theo median.

## Test lỗi nào bị chậm?

| Dự án | Nhóm lịch sử | Quan sát test | Quan sát lỗi | Phát hiện muộn hơn | Sớm hơn |
|---|---|---:|---:|---:|---:|
| karaf | N0 | 244 | 2 | 0 | 1 |
| karaf | N1_4 | 912 | 4 | 4 | 0 |
| karaf | N5plus | 67572 | 114 | 75 | 37 |
| activemq | N0 | 1779 | 5 | 2 | 3 |
| activemq | N1_4 | 4593 | 32 | 28 | 4 |
| activemq | N5plus | 103466 | 117 | 92 | 25 |
| log4j | N0 | 79 | 1 | 0 | 1 |
| log4j | N1_4 | 282 | 3 | 3 | 0 |
| log4j | N5plus | 98325 | 60 | 44 | 11 |

Nhóm N≥5 có 211/291 quan sát lỗi bị phát hiện muộn hơn; nhóm N=1..4 có 35/39. Nhóm N=0 chỉ có 8 quan sát lỗi (5 sớm hơn, 2 muộn hơn, 1 không đổi). Đây là số quan sát test-stage, có thể lặp cùng test/build, không phải mẫu độc lập hoặc ground-truth flaky. Chưa đủ bằng chứng để khẳng định semantic xử lý tốt cold start. Trong nhóm N≥5, 290/291 quan sát lỗi có source hợp lệ; missing source không giải thích được toàn bộ hiện tượng.

## Trường hợp cụ thể và phân rã APFDc

Với m test lỗi và tổng execution time T, đóng góp của một test lỗi vào ΔAPFDc là −(midpoint_HC − midpoint_HistoryCost)/(mT). Tổng các đóng góp đã được kiểm tra bằng chênh lệch metric lưu sẵn trên mọi stage có APFDc. Thời gian phát hiện tăng được đối chiếu với tổng duration của test mới đứng trước trừ tổng duration của test không còn đứng trước.

- karaf, PR-1492 build 2: ΔAPFDc physical = -57.585 điểm %.
  - single: `org.apache.karaf.jaas.modules.ldap.LdapCacheTest` (N5plus), vị trí dịch +11, phát hiện muộn 50.302s; source hợp lệ: True.
- activemq, PR-977 build 1: ΔAPFDc physical = -51.498 điểm %.
  - single: `org.apache.activemq.broker.LinkStealingTest` (N1_4), vị trí dịch +1, phát hiện muộn 172.029s; source hợp lệ: True.
  - single: `org.apache.activemq.broker.OpenwireConnectionTest` (N1_4), vị trí dịch +0, phát hiện muộn 170.430s; source hợp lệ: True.
- log4j, PR-576 build 1: ΔAPFDc physical = -5.733 điểm %.
  - Ubuntu_Test: `org.apache.logging.log4j.LoggerSupplierTest` (N5plus), vị trí dịch +23, phát hiện muộn 35.830s; source hợp lệ: True.
  - Windows_Test: `org.apache.logging.log4j.core.appender.rolling.RollingAppenderDirectWrite1906Test` (N5plus), vị trí dịch +19, phát hiện muộn 55.125s; source hợp lệ: True.

Ở ActiveMQ PR-977/build 1, `OpenwireConnectionTest` giữ nguyên vị trí nhưng chậm 170,430s. Các predecessor mới tốn 173,265s, predecessor bị bỏ tốn 2,835s. Riêng `MemoryUsageConcurrencyTest` (PASS) tốn 150,674s. Test được chọn đầu tiên chỉ tốn 0,001s: không thể quy toàn bộ mất mát cho riêng lựa chọn đầu tiên. Các duration này là ground truth dùng chẩn đoán sau replay, tuyệt đối không dùng làm feature xếp hạng.

## Đóng góp semantic: quan sát và giới hạn

| Dự án | Median tỷ trọng semantic trong gain của test được chọn đầu |
|---|---:|
| karaf | 97.56% |
| activemq | 99.95% |
| log4j | 99.71% |

Alpha=0,5 không có nghĩa hai thành phần đóng góp ngang nhau ở mỗi bước greedy. Trace cho thấy phần semantic chiếm phần lớn gain của lựa chọn đầu. Đây chỉ là tỷ trọng của ứng viên đã chọn, không chứng minh ứng viên thay thế nào tốt hơn hoặc quan hệ nhân quả. Cơ chế đáng kiểm tra là semantic đưa test có history/cost kém hơn lên trước và làm tăng thời gian trước test lỗi; ví dụ predecessor ở trên cho thấy tác động runtime thực tế.

## Đối chiếu các biến thể đã chạy

Median paired ΔAPFDc so với History+cost (điểm %); không chạy thêm cấu hình.

| Biến thể | Karaf | ActiveMQ | Log4j |
|---|---:|---:|---:|
| hc_alpha_0.0 | 0.000 | 0.000 | 0.000 |
| hc_alpha_0.25 | -0.006 | -0.373 | -0.005 |
| hc_falcon_normalized_v1 | -1.265 | -1.407 | -0.117 |
| hc_alpha_0.75 | -5.756 | -3.818 | -0.531 |
| hc_alpha_1.0 | -30.928 | -41.866 | -28.877 |
| hc_falcon_topic_raw_v1 | -0.003 | -0.018 | 0.000 |
| no_confidence | -1.406 | -1.354 | -0.322 |
| borda_history_cost | -7.708 | -7.640 | -0.066 |
| dante_cch_adapt_r1 | 0.042 | -4.848 | 0.042 |

Giảm alpha xuống 0,25 làm giảm mức thua ở median nhưng chưa vượt History+cost. Raw gần baseline hơn, chưa tạo mức tăng cần thiết. Bỏ confidence hoặc dùng Borda không đem lại cải thiện median nhất quán. Vì vậy chưa có cơ sở chọn ngay một biến thể đã chạy để gọi là phương án thành công.

## Đề xuất triển khai kế tiếp

Ứng viên để review: dùng semantic trong nhóm ứng viên có history/cost gần đầu bảng, kèm giới hạn duration dự đoán. Đây là giả thuyết mới hình thành từ development, chưa được triển khai hoặc đánh giá; không kế thừa bảo đảm xấp xỉ của objective cũ.

1. Giữ nguyên cách tạo history, q, duration dự đoán, cutoff, inventory, source và model. Tại mỗi bước lấy b là test còn lại đứng đầu History+cost theo raw q và FQN.
2. Khi q(b)>0, nhóm ứng viên gồm test có q≥0,95×q(b) và duration dự đoán ≤1,25×duration dự đoán của b. b luôn thuộc nhóm. Chọn theo semantic marginal gain / duration dự đoán (dùng floor duration đã chốt), sau đó raw q giảm dần và FQN tăng dần khi hòa.
3. Khi mọi q còn lại bằng 0, dùng cùng giới hạn duration so với b và cùng quy tắc semantic/cost. Đây là trường hợp lịch sử không phân biệt được ứng viên; phải báo riêng số build, số lỗi và fallback. Nếu gain semantic đều bằng 0, dùng b.
4. Các hệ số 0,95 và 1,25 là đề xuất kỹ thuật ban đầu, chưa được dữ liệu chứng minh tối ưu. Khóa trước lượt thử; không quét nhiều ngưỡng rồi chọn kết quả thuận lợi. Giới hạn theo từng bước không bảo đảm APFDc hoặc độ trễ toàn prefix sẽ tốt hơn baseline.
5. Kiểm chứng thuật toán mới bằng standard/lazy (nếu có lazy), full permutation, mutation current/future outcomes, tình huống q=0/source thiếu/cost fallback. Chế độ chỉ history phải trả đúng baseline raw q; không suy strict equivalence từ q/Q.
6. Chạy một phiên bản development riêng với manifest mới, giữ nguyên checkpoint cũ. So sánh với History+cost, HC-N v1 và FL-only trên toàn cohort, gộp physical build như cũ. Giữ gate +0,03 ở ít nhất 2/3 dự án; báo thêm TTFF, Recall10, nhóm lịch sử và mức thua lớn nhất.

Nhánh runtime cần đánh giá riêng: cache-only có fallback toàn stage về History+cost nếu source matched cần vector mới; chuẩn bị vector ngoài đường chạy đồng bộ. Ghi rõ tỷ lệ fallback và đo cả cohort, không chỉ các cache hit. Đây là một policy khác, phải có manifest và báo cáo riêng; không ghép số đo của policy này vào kết quả thuật toán đầy đủ.

Đầu ra vòng kế tiếp: đặc tả phiên bản mới và tham số khóa, implementation/tests, checkpoint development mới, báo cáo so sánh và quyết định go/no-go. Chỉ cân nhắc confirmation sau review; không mở reserved trong bước phân tích hoặc tìm tham số này. Nếu vẫn không đạt, ghi nhận kết quả âm và xem lại đóng góp nghiên cứu thay vì tiếp tục thử không giới hạn.

## Bằng chứng và tái lập

- [Diagnosis JSON](../../reports/stage7/diagnosis.json): nhóm lịch sử, biến thể, năm build tốt/xấu nhất.
- `reports/stage7/<project>/physical-diagnosis.json`: toàn bộ cặp physical và đóng góp từng test lỗi.
- Chạy `work/envs/falcon/Scripts/python.exe -B -m unittest tests.test_stage7`, sau đó `scripts/stage7_diagnosis.py` và `scripts/stage7_report.py` bằng cùng Python.
- Một kiểm thử hồi quy đối chiếu phân rã APFDc với evaluator, có duration không đều, duration bằng 0 và no-failure. Assertions trên dữ liệu thực đối chiếu mọi stage được phân rã.
- Không thay đổi README hoặc các file nằm trong freeze giai đoạn 6.
