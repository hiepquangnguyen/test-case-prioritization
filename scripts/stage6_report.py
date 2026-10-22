"""Render completed development pilot evidence without selecting a new method."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def number(value, places=4):
    return 'NA' if value is None else f'{value:.{places}f}'


def main():
    summary = json.loads((ROOT / 'reports/stage6/summary.json').read_text())
    projects = summary['projects']
    lines = ['# Giai đoạn 6 — pilot development toàn inventory', '',
             'Pilot đã chạy trên development của Karaf, ActiveMQ và Log4j bằng implementation giai đoạn 5. '
             'Warm-up chỉ cung cấp history/cache. Tập reserved confirmation chưa mở.', '',
             f"**Quyết định theo ngưỡng đã chốt: {summary['decision']}.** "
             f"Gate hiệu quả đạt ở {summary['effect_gate_projects_passed']}/3 dự án; "
             f"engineering gate toàn bộ dự án: {summary['engineering_gate_passed']}.", '',
             'Các kết quả là mô tả trên development; Karaf exploratory. Không dùng các số này như kiểm định '
             'xác nhận và không đổi alpha chính sau khi xem kết quả.', '',
             '## Hiệu quả chính', '',
             'Bảng dưới là median của paired delta APFDc (HC-FALCON-N − đối chứng), '
             'không phải hiệu của hai median. Seed mean trước, rồi gộp các stage chung trong physical build. '
             'Ngưỡng tiếp tục: delta ≥0,03 so với cả FL-only và History+cost ở ít nhất hai dự án.', '',
             '| Dự án | Stage / physical được score | Δ so với FL | Số cặp FL | Δ so với History+cost | Số cặp HC | Gate |',
             '|---|---:|---:|---:|---:|---:|---|']
    for name, report in projects.items():
        fl = report['paired']['fl_only']['apfdc_midpoint']
        hc = report['paired']['history_cost']['apfdc_midpoint']
        lines.append(f"| {name} | {report['stages_scored']} / {report['physical_scored']} | {number(fl['median_delta'])} | {fl['pairs']} | {number(hc['median_delta'])} | {hc['pairs']} | {'Đạt' if report['effect_gate_passed'] else 'Không đạt'} |")
    lines += ['', '## TTFF và Recall10', '',
              'Delta TTFF âm là tốt hơn; delta Recall10 dương là tốt hơn. TTFF ở đây là execution-only '
              'trên các cặp có failure/metric xác định; số censored stage lưu riêng trong summary.', '',
              '| Dự án | Đối chứng | Median Δ TTFF (s) | Số cặp | Median Δ Recall10 | Số cặp |',
              '|---|---|---:|---:|---:|---:|']
    for name, report in projects.items():
        for comparator in ('fl_only', 'history_cost'):
            tf = report['paired'][comparator]['ttff_seconds']
            recall = report['paired'][comparator]['recall10']
            lines.append(f"| {name} | {comparator} | {number(tf['median_delta'])} | {tf['pairs']} | {number(recall['median_delta'])} | {recall['pairs']} |")
    lines += ['', '## Chi phí và source', '',
              '| Dự án | Peak RSS process (GiB) | p95 warm overhead / suite | Gate engineering | Valid semantic / records | Valid failing source / failures | Truncated records |',
              '|---|---:|---:|---|---:|---:|---:|']
    for name, report in projects.items():
        eng = report['engineering']
        src = report['source']
        count = sum(v['records'] for v in src.values())
        valid = sum(v['valid'] for v in src.values())
        truncated = sum(v['truncated'] for v in src.values())
        failed = src.get('failing', {'valid':0, 'records':0})
        lines.append(f"| {name} | {eng['peak_rss']/1024**3:.3f} | {number(eng['p95_warm_overhead_ratio']*100,2)}% | {'Đạt' if eng['passed'] else 'Không đạt'} | {valid} / {count} | {failed['valid']} / {failed['records']} | {truncated} |")
    lines += ['', 'Warm overhead gồm source/preprocessing, embedding (kể cả cache miss khi source đổi), '
              'kernel, history và ranking cho phương pháp chính. Chi phí chuẩn bị được tính cho từng method '
              'độc lập. Cold overhead trong JSON là ước lượng dựng lại từ từng source cache miss, '
              'không phải cold end-to-end trực tiếp từng build. Chi phí fetch/model download và CI setup/queue '
              'không nằm trong phép đo offline này. Peak RSS là cả process replay.', '',
              '## Kiểm chứng và giới hạn', '',
              f"Đã kiểm tra {sum(r['rankings_verified'] for r in projects.values())} ranking: full permutation và "
              'APFD/APFDc bằng công thức độc lập. No-failure giữ NA. Không nhân số mẫu bởi seed/stage. '
              'Các checkpoint giữ đủ các baseline, ablation, raw/normalized, Borda và alpha sensitivity.', '',
              'Source là revision metadata khai báo, chưa chứng minh revision thực sự được CI chạy. '
              'Inventory lấy từ observed logs; missing/ambiguous giữ lại. Semantic truncation dùng cap đã chốt '
              'trước pilot. RQ3 lưu nhóm N=0, 1..4, ≥5 và vị trí/thời điểm phát hiện; không gọi đó là '
              'ground-truth flaky. Defects4J là nhánh riêng, chưa được chạy trong pilot này.', '',
              'Nếu no-go, bước tiếp theo là phân tích nguyên nhân và đề xuất phiên bản sửa trên development '
              'để review. Không mở reserved để tìm kết quả thuận lợi. Nếu đạt gate, vẫn cần review đầy đủ '
              'tradeoff và khóa phương án trước khi mở confirmation.', '',
              '## Bằng chứng', '',
              '- [Summary máy đọc](../../reports/stage6/summary.json)',
              '- [Runner/analysis freeze](../../reports/stage6/run-freeze.json)',
              '- [Tái lập và định nghĩa runtime](reproduction.md)',
              '- Các checkpoint và `ledger.json`, `complete.json`, `history-groups.json` nằm tại '
              '`reports/stage6/<project>/`.']
    lines += ['', '## Kiểm tra số học và tái dựng replay', '']
    for project in projects:
        check=json.loads((ROOT/'reports/stage6'/project/'replay-verification.json').read_text())
        lines.append(f"- {project}: {check['endpoint_order_checks']} objective endpoint checks; "
                     f"{len(check['numerical_tie_exceptions'])} ngoại lệ strict alpha=0 do float64 normalization; "
                     'tái dựng first/last development full inventory và mutation các build không đủ điều kiện sử dụng đã đạt.')
    lines += ['', 'Ngoại lệ alpha=0 không được che bằng tolerance để đổi ranking: giữ tie FQN của '
              'objective float đã khóa, ghi q/w và metric hai thứ tự trong `replay-verification.json`. '
              'Không coi tương đương toán học alpha=0 và History+cost là bảo đảm thứ tự tuyệt đối ở float64. '
              'Cần review/chốt quy tắc này trước một phiên bản confirmation tiếp theo.', '',
              'ActiveMQ có lần warm-up bị ngắt trước khi lưu cold-cost ledger. Chi phí cold còn thiếu '
              'được đo lại riêng, có kiểm tra vector, và ghi `cold-recovery.json`; ranking gốc không đổi. '
              'Độ phân tán seed/stage, nhóm lịch sử và TTFF có cộng preparation xem '
              '[supplement](../../reports/stage6/supplement.json).']
    lines += ['', '## Toàn bộ đối chứng và ablation', '',
              'Mean APFDc trên physical build có metric xác định; bảng này là mô tả, '
              'không thay thế median paired delta dùng cho gate.', '',
              '| Phương pháp | Karaf | ActiveMQ | Log4j |', '|---|---:|---:|---:|']
    methods=['random','shortest_test_first','most_fail','recent_fail','history_only','history_cost',
             'fl_only','hc_falcon_normalized_v1','hc_falcon_topic_raw_v1','fl_history','no_confidence',
             'borda_history','borda_history_cost','fast_pw_lrts','dante_cch_adapt_r1']
    for method in methods:
        values=[number(projects[p]['methods'][method]['apfdc_midpoint']['mean']) for p in ('karaf','activemq','log4j')]
        lines.append('| '+method+' | '+' | '.join(values)+' |')
    lines += ['', '## Alpha sensitivity', '',
              'Giữ alpha=0,5 là cấu hình chính. Mean APFDc dưới đây không được dùng '
              'để đổi cấu hình rồi gọi cùng development là confirmation.', '',
              '| Alpha | Karaf | ActiveMQ | Log4j |', '|---|---:|---:|---:|']
    for alpha in (0.0,.25,.5,.75,1.0):
        method='hc_falcon_normalized_v1' if alpha==.5 else 'hc_alpha_'+str(alpha)
        values=[number(projects[p]['methods'][method]['apfdc_midpoint']['mean']) for p in ('karaf','activemq','log4j')]
        lines.append('| '+str(alpha)+' | '+' | '.join(values)+' |')
    supplement = json.loads((ROOT / 'reports/stage6/supplement.json').read_text())
    lines += ['', '## Trường hợp overhead cao', '',
              'P95 không phải giới hạn cho mọi build. Bảng dưới bổ sung maximum của mean stage ratio '
              'trong physical build và stage có overhead lớn nhất; đây là chẩn đoán, không thay gate đã chốt.', '',
              '| Dự án | Maximum physical overhead | Stage cao nhất | Prep + ranking (s) | Source cache misses |',
              '|---|---:|---|---:|---:|']
    for project in projects:
        details = supplement['projects'][project]
        worst = details['primary_worst_overhead_stages'][0]
        key = worst['key']
        label = f"{key['pr']} / {key['build']} / {key['stage']}"
        maximum = details['primary_warm_overhead_physical_distribution']['maximum']
        lines.append(f"| {project} | {number(maximum*100,2)}% | {label} | "
                     f"{number(worst['preparation_and_ranking_seconds'],2)} | {worst['embedding_cache_misses']} |")
    lines += ['', 'Runtime có ảnh hưởng của resume và trạng thái cache. Các số đo này mô tả lượt replay '
              'đã thực hiện; chưa phải bảo đảm latency cho CI thực tế. Peak RSS lấy maximum qua completion '
              'và mọi checkpoint development để giữ số đo của worker trước khi resume '
              '([biên bản analyzer v3](../../reports/stage6/analysis-amendment-v3.json)).']
    lines += ['', '## Kết luận để quyết định bước tiếp theo', '',
              'Cấu hình alpha=0,5 cải thiện median paired APFDc so với FL-only trên cả ba dự án, '
              'nhưng median paired delta so với History+cost đều âm. Do đó chưa có cơ sở chuyển '
              'cấu hình hiện tại sang confirmation. Riêng Log4j, mean APFDc cao hơn History+cost '
              'nhưng median paired delta vẫn âm; hai phép tổng hợp này không mâu thuẫn và không '
              'được thay thế nhau khi xét gate.', '',
              'Bước tiếp theo: phân tích các build thua History+cost và nhóm lịch sử N=0/1..4/≥5, '
              'đối chiếu đóng góp semantic với history/cost và chi phí cache miss, rồi đề xuất '
              'phiên bản sửa cùng quy tắc số học để review trước lượt đánh giá mới. Các giả thuyết '
              'rút ra từ development cần được ghi rõ; chưa đổi alpha hay mở reserved.', '',
              'Tổng cộng tám ngoại lệ alpha=0 (Karaf: 1; Log4j: 7) có thứ tự khác History+cost '
              'do chuẩn hóa float64 tạo hòa điểm. Đối chiếu các metric đã lưu cho cả tám trường hợp '
              'không thấy khác biệt; điều này không bảo đảm mọi dữ liệu tương lai đều không bị ảnh hưởng.']
    target = ROOT / 'docs/06-pilot/implementation-report.md'
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
