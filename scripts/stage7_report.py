"""Render the development diagnosis and a reviewable, unimplemented revision proposal."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / 'reports/stage7/diagnosis.json').read_text())['projects']
    lines = ['# Phân tích sau pilot — đề xuất để review', '',
        'Đã phân tích checkpoint development của giai đoạn 6; chưa triển khai thuật toán mới. '
        'Đã kiểm tra toàn bộ hash của bằng chứng giai đoạn 6 trước khi đọc. Reserved vẫn đóng. '
        'Các phát hiện dưới đây mang tính mô tả và hình thành giả thuyết, không phải xác nhận độc lập.', '',
        '## Kết quả chính', '',
        '| Dự án | Build có APFDc | Thắng / hòa / thua History+cost | Median Δ APFDc (điểm %) |',
        '|---|---:|---:|---:|']
    for p, r in data.items():
        d = r['paired_vs_history_cost']
        lines.append(f"| {p} | {d['count']} | {d['positive']} / {d['tie']} / {d['negative']} | {100*d['median']:.3f} |")
    lines += ['', 'Seed được gộp trong stage; chênh lệch stage được lấy mean trong physical build. '
        'Chỉ các cặp có metric xác định tham gia bảng này. Log4j có mean delta dương nhưng 21/25 '
        'physical build thua: một số build tăng nhiều kéo mean lên, không thay đổi kết luận theo median.', '',
        '## Test lỗi nào bị chậm?', '',
        '| Dự án | Nhóm lịch sử | Quan sát test | Quan sát lỗi | Phát hiện muộn hơn | Sớm hơn |',
        '|---|---|---:|---:|---:|---:|']
    for p, r in data.items():
        for g, v in r['groups_observation_level_descriptive'].items():
            lines.append(f"| {p} | {g} | {v['tests']} | {v['failures']} | {v['delayed_failures']} | {v['advanced_failures']} |")
    lines += ['', 'Nhóm N≥5 có 211/291 quan sát lỗi bị phát hiện muộn hơn; nhóm N=1..4 có 35/39. '
        'Nhóm N=0 chỉ có 8 quan sát lỗi (5 sớm hơn, 2 muộn hơn, 1 không đổi). '
        'Đây là số quan sát test-stage, có thể lặp cùng test/build, không phải mẫu độc lập hoặc ground-truth flaky. '
        'Chưa đủ bằng chứng để khẳng định semantic xử lý tốt cold start. Trong nhóm N≥5, '
        '290/291 quan sát lỗi có source hợp lệ; missing source không giải thích được toàn bộ hiện tượng.', '',
        '## Trường hợp cụ thể và phân rã APFDc', '',
        'Với m test lỗi và tổng execution time T, đóng góp của một test lỗi vào ΔAPFDc là '
        '−(midpoint_HC − midpoint_HistoryCost)/(mT). Tổng các đóng góp đã được kiểm tra bằng '
        'chênh lệch metric lưu sẵn trên mọi stage có APFDc. Thời gian phát hiện tăng được đối chiếu '
        'với tổng duration của test mới đứng trước trừ tổng duration của test không còn đứng trước.', '']
    for p, r in data.items():
        worst = r['worst_physical'][0]
        k = worst['key']
        lines.append(f"- {p}, {k['pr']} build {k['build']}: ΔAPFDc physical = {100*worst['delta_apfdc']:.3f} điểm %.")
        for stage in worst['stages']:
            for shift in stage['failure_shifts']:
                lines.append(f"  - {stage['key']['stage']}: `{shift['test_id']}` ({shift['history_group']}), "
                    f"vị trí dịch {shift['position_shift']:+d}, phát hiện muộn {shift['completion_shift_seconds']:.3f}s; "
                    f"source hợp lệ: {shift['valid_source']}.")
    lines += ['', 'Ở ActiveMQ PR-977/build 1, `OpenwireConnectionTest` giữ nguyên vị trí nhưng chậm '
        '170,430s. Các predecessor mới tốn 173,265s, predecessor bị bỏ tốn 2,835s. '
        'Riêng `MemoryUsageConcurrencyTest` (PASS) tốn 150,674s. Test được chọn đầu tiên chỉ tốn '
        '0,001s: không thể quy toàn bộ mất mát cho riêng lựa chọn đầu tiên. Các duration này là '
        'ground truth dùng chẩn đoán sau replay, tuyệt đối không dùng làm feature xếp hạng.', '',
        '## Đóng góp semantic: quan sát và giới hạn', '',
        '| Dự án | Median tỷ trọng semantic trong gain của test được chọn đầu |', '|---|---:|']
    for p, r in data.items():
        lines.append(f"| {p} | {100*r['first_selected_semantic_share']['median']:.2f}% |")
    lines += ['', 'Alpha=0,5 không có nghĩa hai thành phần đóng góp ngang nhau ở mỗi bước greedy. '
        'Trace cho thấy phần semantic chiếm phần lớn gain của lựa chọn đầu. Đây chỉ là tỷ trọng '
        'của ứng viên đã chọn, không chứng minh ứng viên thay thế nào tốt hơn hoặc quan hệ nhân quả. '
        'Cơ chế đáng kiểm tra là semantic đưa test có history/cost kém hơn lên trước và làm tăng '
        'thời gian trước test lỗi; ví dụ predecessor ở trên cho thấy tác động runtime thực tế.', '',
        '## Đối chiếu các biến thể đã chạy', '',
        'Median paired ΔAPFDc so với History+cost (điểm %); không chạy thêm cấu hình.', '',
        '| Biến thể | Karaf | ActiveMQ | Log4j |', '|---|---:|---:|---:|']
    for name in data['karaf']['variants_vs_history_cost']:
        values = [f"{100*data[p]['variants_vs_history_cost'][name]['median']:.3f}" for p in data]
        lines.append('| '+name+' | '+' | '.join(values)+' |')
    lines += ['', 'Giảm alpha xuống 0,25 làm giảm mức thua ở median nhưng chưa vượt History+cost. '
        'Raw gần baseline hơn, chưa tạo mức tăng cần thiết. Bỏ confidence hoặc dùng Borda không '
        'đem lại cải thiện median nhất quán. Vì vậy chưa có cơ sở chọn ngay một biến thể đã chạy '
        'để gọi là phương án thành công.', '',
        '## Đề xuất triển khai kế tiếp', '',
        'Ứng viên để review: dùng semantic trong nhóm ứng viên có history/cost gần đầu bảng, '
        'kèm giới hạn duration dự đoán. Đây là giả thuyết mới hình thành từ development, chưa được '
        'triển khai hoặc đánh giá; không kế thừa bảo đảm xấp xỉ của objective cũ.', '',
        '1. Giữ nguyên cách tạo history, q, duration dự đoán, cutoff, inventory, source và model. '
        'Tại mỗi bước lấy b là test còn lại đứng đầu History+cost theo raw q và FQN.',
        '2. Khi q(b)>0, nhóm ứng viên gồm test có q≥0,95×q(b) và duration dự đoán ≤1,25×duration '
        'dự đoán của b. b luôn thuộc nhóm. Chọn theo semantic marginal gain / duration dự đoán '
        '(dùng floor duration đã chốt), sau đó raw q giảm dần và FQN tăng dần khi hòa.',
        '3. Khi mọi q còn lại bằng 0, dùng cùng giới hạn duration so với b và cùng quy tắc '
        'semantic/cost. Đây là trường hợp lịch sử không phân biệt được ứng viên; phải báo riêng '
        'số build, số lỗi và fallback. Nếu gain semantic đều bằng 0, dùng b.',
        '4. Các hệ số 0,95 và 1,25 là đề xuất kỹ thuật ban đầu, chưa được dữ liệu chứng minh tối ưu. '
        'Khóa trước lượt thử; không quét nhiều ngưỡng rồi chọn kết quả thuận lợi. Giới hạn theo '
        'từng bước không bảo đảm APFDc hoặc độ trễ toàn prefix sẽ tốt hơn baseline.',
        '5. Kiểm chứng thuật toán mới bằng standard/lazy (nếu có lazy), full permutation, '
        'mutation current/future outcomes, tình huống q=0/source thiếu/cost fallback. '
        'Chế độ chỉ history phải trả đúng baseline raw q; không suy strict equivalence từ q/Q.',
        '6. Chạy một phiên bản development riêng với manifest mới, giữ nguyên checkpoint cũ. '
        'So sánh với History+cost, HC-N v1 và FL-only trên toàn cohort, gộp physical build như cũ. '
        'Giữ gate +0,03 ở ít nhất 2/3 dự án; báo thêm TTFF, Recall10, nhóm lịch sử và mức thua lớn nhất.', '',
        'Nhánh runtime cần đánh giá riêng: cache-only có fallback toàn stage về History+cost nếu '
        'source matched cần vector mới; chuẩn bị vector ngoài đường chạy đồng bộ. Ghi rõ tỷ lệ '
        'fallback và đo cả cohort, không chỉ các cache hit. Đây là một policy khác, phải có manifest '
        'và báo cáo riêng; không ghép số đo của policy này vào kết quả thuật toán đầy đủ.', '',
        'Đầu ra vòng kế tiếp: đặc tả phiên bản mới và tham số khóa, implementation/tests, checkpoint '
        'development mới, báo cáo so sánh và quyết định go/no-go. Chỉ cân nhắc confirmation sau '
        'review; không mở reserved trong bước phân tích hoặc tìm tham số này. Nếu vẫn không đạt, '
        'ghi nhận kết quả âm và xem lại đóng góp nghiên cứu thay vì tiếp tục thử không giới hạn.', '',
        '## Bằng chứng và tái lập', '',
        '- [Diagnosis JSON](../../reports/stage7/diagnosis.json): nhóm lịch sử, biến thể, năm build tốt/xấu nhất.',
        '- `reports/stage7/<project>/physical-diagnosis.json`: toàn bộ cặp physical và đóng góp từng test lỗi.',
        '- Chạy `work/envs/falcon/Scripts/python.exe -B -m unittest tests.test_stage7`, '
        'sau đó `scripts/stage7_diagnosis.py` và `scripts/stage7_report.py` bằng cùng Python.',
        '- Một kiểm thử hồi quy đối chiếu phân rã APFDc với evaluator, có duration không đều, '
        'duration bằng 0 và no-failure. Assertions trên dữ liệu thực đối chiếu mọi stage được phân rã.',
        '- Không thay đổi README hoặc các file nằm trong freeze giai đoạn 6.']
    target = ROOT / 'docs/07-diagnosis/diagnosis-and-proposal.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
