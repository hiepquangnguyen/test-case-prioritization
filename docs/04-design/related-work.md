# Đối chiếu novelty và baseline — phạm vi giai đoạn 4

Kiểm tra ngày 2026-09-13. Đây là đối chiếu có mục tiêu, không phải systematic
review hoàn chỉnh. Paper FALCON/DANTE và code artifact đã có trong repo là
nguồn chính cho thiết kế; các nguồn dưới đây bổ sung đối chứng cần thiết.

| Nguồn trực tiếp | Điều đã kiểm tra | Ảnh hưởng tới đề tài |
|---|---|---|
| [FALCON, tài liệu đọc hiểu](../00-foundations/doc-hieu-de-tai.md#4-falcon-đa-dạng-hóa-có-mục-tiêu-toán-học), [công thức/thuật toán](../00-foundations/thuat-toan-va-ly-thuyet.md#5-submodular-và-facility-location) và [audit code](../01-feasibility/stage1-report.md) | Facility location/lazy greedy; cosine âm và pooling padding trong artifact. | Giữ bản nguyên gốc riêng, gắn nhãn adaptation cho class/clip/pooling mới. |
| [DANTE, tài liệu đọc hiểu](../00-foundations/doc-hieu-de-tai.md#5-dante-học-từ-lịch-sử-và-thay-đổi-hiện-tại), [công thức/thuật toán](../00-foundations/thuat-toan-va-ly-thuyet.md#9-dante) và [audit code](../01-feasibility/stage1-report.md) | History/duration/relevance; runner lọc inventory, dùng current cost và history rolling không phù hợp. | Baseline phải port rõ ranh giới, không báo smoke nguyên bản là đối chứng công bằng. |
| [FAST — repository tác giả](https://github.com/icse18-FAST/FAST), [paper tác giả](https://robertoverdecchia.github.io/papers/ICSE_2018.pdf) | Nguồn baseline similarity-based và artifact. Lượt này đọc README; implementation FAST trong artifact FALCON đã đọc cục bộ. | Chốt FAST-pw theo wrapper đã pin, cùng source eligibility và báo adaptation determinism. Chưa tự chạy FAST trong stage4. |
| [Mahdieh et al., diversification và fault-proneness](https://arxiv.org/abs/2106.10524v3) | Đã đọc abstract/bibliographic record: kết hợp coverage, bug history và diversification qua clustering. | Không tuyên bố là công trình đầu tiên kết hợp diversity với lịch sử/rủi ro lỗi. Chưa tái lập phương pháp này. |
| [Chojnacki & Madeyski, approach combinators](https://arxiv.org/abs/2603.00183v2) | Đã đọc abstract/bibliographic record: nghiên cứu ensemble TCP và framework kết hợp approach. | Rank fusion đơn giản là đối chứng cần thiết; kết hợp hai tín hiệu tự nó chưa chứng minh novelty. Chưa port TCPFramework. |

Chưa có bằng chứng để tuyên bố HC-FALCON-N tốt hơn các công trình trên. Đóng góp
cần kiểm chứng là objective semantic facility-location + confidence/history/cost,
thiết kế chuẩn hóa được nêu rõ, triển khai lazy greedy và đánh giá rolling trên
LRTS với nguồn thông tin trước cutoff. Normalization Q không phải theorem hay
novelty tự động; phải so với công thức topic-raw và rank fusion.

Khảo sát đầy đủ trước bản thảo còn phải đọc full text các công trình bổ sung,
so coverage requirements, định nghĩa history, cost objective, evaluation unit
và khả năng tái lập. Không trích metric của paper khác để so trực tiếp với replay
LRTS hiện tại vì khác dataset/protocol. Kết quả xác minh stage4 dựa vào code và
dữ liệu cục bộ, không lấy tuyên bố hiệu quả trong abstract làm số liệu dự án.
