"""Render separate algorithm and offline cache-policy revision reports."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    summary = json.loads((ROOT/'reports/stage8/summary.json').read_text())
    projects = summary['projects']
    primary = 'restricted_semantic_cost_v1'
    policy = 'cache_only_restricted_v1_simulated'
    lines = ['# Kết quả restricted semantic/cost v1', '',
        f"**Quyết định: {summary['decision']}. Gate hiệu quả đạt {summary['effect_gate_projects_passed']}/3 dự án.**", '',
        'Đã triển khai và replay toàn development với q_fraction=0,95, duration_multiplier=1,25. '
        'Giữ encoder/history/source và dữ liệu giai đoạn 6; không quét tham số. Reserved vẫn đóng.', '',
        '## Hiệu quả theo physical build', '',
        'Median paired ΔAPFDc tính bằng điểm %, số âm là kém hơn đối chứng. Gate cần ≥3 điểm % '
        'so với cả History+cost và FL-only ở ít nhất hai dự án. Các cặp no-failure giữ NA.', '',
        '| Dự án | Stage / physical | Cặp có APFDc | Δ History+cost | Δ HC-N v1 | Δ FL-only | Gate |',
        '|---|---:|---:|---:|---:|---:|---|']
    for p,r in projects.items():
        c = r['comparisons'][primary]
        values = [100*c[m]['apfdc']['median_delta'] for m in ('history_cost','hc_falcon_normalized_v1','fl_only')]
        lines.append(f"| {p} | {r['stages']} / {r['physical']} | {c['history_cost']['apfdc']['pairs']} | "
            +' | '.join(f'{v:.3f}' for v in values)+f" | {r['effect_gate_passed']} |")
    lines += ['', '## Thời gian phát hiện lỗi và Recall10', '',
        'TTFF execution-only; median delta âm tốt hơn. Recall10 delta dương tốt hơn.', '',
        '| Dự án | Đối chứng | Median ΔTTFF (s) | Median ΔRecall10 | APFDc thắng / hòa / thua |',
        '|---|---|---:|---:|---:|']
    for p,r in projects.items():
        for name,c in r['comparisons'][primary].items():
            d = c['apfdc']
            lines.append(f"| {p} | {name} | {c['ttff']['median_delta']:.3f} | {c['recall10']['median_delta']:.3f} | "
                         f"{d['positive']} / {d['tie']} / {d['negative']} |")
    lines += ['', '## Nhóm lịch sử và fallback trong greedy', '',
        '| Dự án | Nhóm | Quan sát test | Quan sát lỗi | Recall10 pooled |', '|---|---|---:|---:|---:|']
    for p,r in projects.items():
        for g,v in r['groups_observation_level'].items():
            recall = 'NA' if v['recall10_pooled'] is None else f"{v['recall10_pooled']:.3f}"
            lines.append(f"| {p} | {g} | {v['tests']} | {v['failures']} | {recall} |")
    lines += ['', 'Đây là quan sát test-stage có lặp, không phải mẫu độc lập. Nhóm N=0 vẫn rất ít lỗi.', '',
        'Giới hạn quan trọng của quy tắc mới: q=0 không thể vào nhóm ứng viên khi còn q(b)>0. '
        'Vì vậy test chưa có lịch sử bị đẩy sau các test có q dương; semantic chỉ sắp lại nhóm này '
        'khi nhóm q dương đã hết. Trong lượt này cả 8 quan sát lỗi N=0 đều nằm ngoài ngân sách 10%. '
        'Không thể coi đây là phương án đã giải quyết cold start.', '']
    for p,r in projects.items():
        lines.append(f"- {p}: {r['zero_q_stages']} stage có ít nhất một bước q(b)=0; "
                     f"{r['zero_gain_fallback_steps']} bước semantic gain toàn nhóm bằng 0 và dùng baseline head.")
    lines += ['', '## Runtime cached replay', '',
        '| Dự án | p95 prep+rank / execution | Maximum physical ratio | Peak RSS (GiB) |',
        '|---|---:|---:|---:|']
    for p,r in projects.items():
        v=r['runtime']
        lines.append(f"| {p} | {100*v['p95_cached_reconstruction_ratio']:.3f}% | "
                     f"{100*v['maximum_cached_reconstruction_ratio']:.3f}% | {v['peak_rss']/1024**3:.3f} |")
    lines += ['', 'Các số này không gồm trích source và encoding, có cache vector trong bộ nhớ; '
        'không dùng để tuyên bố đã đạt engineering full pipeline hoặc cải thiện latency CI so với '
        'lượt đo giai đoạn 6. Không ghép chi phí đo ở các lượt khác nhau thành benchmark mới.', '',
        '## Các physical build thua nhiều nhất', '',
        '| Dự án | PR / build | ΔAPFDc so với History+cost (điểm %) |', '|---|---|---:|']
    for p,r in projects.items():
        for v in r['worst_physical'][:3]:
            lines.append(f"| {p} | {v['key']['pr']} / {v['key']['build']} | {100*v['delta_apfdc']:.3f} |")
    lines += ['', '## Kiểm chứng và giới hạn', '',
        f"Đã lưu {sum(r['stages'] for r in projects.values())} checkpoint mới, mỗi checkpoint có ranking "
        'thuật toán và policy riêng. Full permutation và APFD/APFDc được đối chiếu độc lập cho cả hai. '
        'Baseline raw q khớp chính xác giai đoạn 6 ở mọi stage. Sáu phép mutation đầu/cuối dự án '
        'giữ nguyên snapshot và ranking khi thay outcomes/duration không đủ điều kiện. Bốn unit tests đạt.', '',
        'Phiên bản mới được chọn sau khi xem development nên kết quả chỉ là thăm dò. '
        'Giới hạn q/cost từng bước không bảo đảm toàn bộ thứ tự tốt hơn History+cost. '
        'Không kế thừa chứng minh xấp xỉ của objective cũ và không triển khai lazy.', '',
        'Kết quả phiên bản này cho thấy giới hạn q/cost giảm mức thiệt hại so với HC-N v1, '
        'nhưng chưa tạo lợi ích vượt History+cost theo gate. Đây là kết quả âm cần giữ trong báo cáo, '
        'không phải bằng chứng xác nhận giả thuyết semantic kết hợp luôn tốt hơn.', '',
        'Nếu no-go, dừng vòng cấu hình này và review đóng góp nghiên cứu hoặc phạm vi câu hỏi; '
        'không tự động quét thêm tham số hay mở reserved. Nếu đạt hiệu quả, cần đo engineering đầy đủ '
        'trước khi review confirmation.', '',
        '- [Đặc tả và tái lập](specification-and-reproduction.md)',
        '- [Summary](../../reports/stage8/summary.json)',
        '- [Manifest](../../reports/stage8/manifest.json)',
        '- [Báo cáo policy cache-only riêng](cache-policy-report.md)']
    target = ROOT/'docs/08-revision'
    (target/'implementation-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    policy_lines = ['# Cache-only restricted v1 — mô phỏng riêng', '',
        'Dùng baseline History+cost cho cả stage khi thiếu source hash trong cache trước stage. '
        'Warmup usable nạp cache; sau mỗi stage usable, các source hash được coi là sẵn sàng cho '
        'stage kế tiếp. Đây là giả định offline, chưa có worker async hoặc lịch hoàn thành encoding CI.', '',
        '| Dự án | Stage fallback / tổng | Physical có fallback | Median ΔAPFDc History+cost (điểm %) | Median ΔTTFF (s) |',
        '|---|---:|---:|---:|---:|']
    for p,r in projects.items():
        c=r['comparisons'][policy]['history_cost']
        policy_lines.append(f"| {p} | {r['cache_policy']['fallback_stages']} / {r['stages']} | "
            f"{r['cache_policy']['physical_with_fallback']} | {100*c['apfdc']['median_delta']:.3f} | {c['ttff']['median_delta']:.3f} |")
    policy_lines += ['', 'Metric tính trên cả cohort gồm fallback, theo physical build; không chỉ tính '
        'cache hit. TTFF là execution-only từ thứ tự mô phỏng. Không có số đo latency async hoặc '
        'engineering gate của policy. Chưa triển khai dịch vụ chuẩn bị vector nền. Không thay policy '
        'bằng kết quả thuật toán đầy đủ khi kết luận.', '',
        '- [Policy manifest](../../reports/stage8/cache-policy-manifest.json)',
        '- [Policy summary](../../reports/stage8/cache-policy-summary.json)']
    (target/'cache-policy-report.md').write_text('\n'.join(policy_lines)+'\n',encoding='utf-8')
    (ROOT/'reports/stage8/cache-policy-summary.json').write_text(json.dumps(dict(reserved_opened=False,
        scope='offline_simulation_only',projects={p:dict(coverage=r['cache_policy'],comparisons=r['comparisons'][policy])
        for p,r in projects.items()}),indent=2),encoding='utf-8')
    print(target/'implementation-report.md')


if __name__ == '__main__':
    main()
