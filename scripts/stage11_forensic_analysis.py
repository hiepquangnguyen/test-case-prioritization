"""Phase 1 forensic analysis: classify wins/losses, find patterns in semantic value.

Reads Stage 7 physical-diagnosis.json + Stage 6 checkpoints to answer:
1. Distribution of delta APFDc across wins/losses
2. Characteristics of winning builds (semantic share, history groups, suite size)
3. Heavy predecessor patterns
4. Q-score tie analysis
5. Semantic failure transfer potential

Output: reports/stage11/forensic-analysis.json + console summary.
"""
import json, gzip, os, sys, math
from pathlib import Path
from collections import Counter, defaultdict
import statistics

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ['karaf', 'activemq', 'log4j']
STAGE7 = ROOT / 'reports' / 'stage7'
STAGE6 = ROOT / 'reports' / 'stage6'
STAGE8 = ROOT / 'reports' / 'stage8'
OUT = ROOT / 'reports' / 'stage11'
OUT.mkdir(parents=True, exist_ok=True)


def percentile(data, p):
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


def describe(values):
    if not values:
        return {'count': 0}
    return {
        'count': len(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'std': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'max': max(values),
        'p5': percentile(values, 5),
        'p25': percentile(values, 25),
        'p75': percentile(values, 75),
        'p95': percentile(values, 95),
    }


def load_physical_diagnosis(project):
    path = STAGE7 / project / 'physical-diagnosis.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_checkpoint(project, checkpoint_name):
    path = STAGE6 / project / 'builds' / checkpoint_name
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def load_ledger(project):
    path = STAGE6 / project / 'ledger.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def key_to_tuple(key):
    return (key['project'], key['pr'], key['build'])


def stage_key_to_tuple(key):
    return (key['project'], key['pr'], key['build'], key['stage'])


def analyze_project(project):
    diag = load_physical_diagnosis(project)

    wins, losses, ties = [], [], []
    for b in diag:
        d = b['delta_apfdc']
        if d > 1e-12:
            wins.append(b)
        elif d < -1e-12:
            losses.append(b)
        else:
            ties.append(b)

    all_deltas = [b['delta_apfdc'] for b in diag]
    win_deltas = [b['delta_apfdc'] for b in wins]
    loss_deltas = [b['delta_apfdc'] for b in losses]

    def avg_semantic_share(builds):
        shares = []
        for b in builds:
            for s in b['stages']:
                shares.append(s['first_selected_semantic_share'])
        return shares

    win_shares = avg_semantic_share(wins)
    loss_shares = avg_semantic_share(losses)

    def group_stats(builds):
        groups = Counter()
        for b in builds:
            for s in b['stages']:
                for fs in s['failure_shifts']:
                    groups[fs['history_group']] += 1
        return dict(groups)

    win_groups = group_stats(wins)
    loss_groups = group_stats(losses)

    def first_failed_rate(builds):
        total, failed = 0, 0
        for b in builds:
            for s in b['stages']:
                total += 1
                if s['first_selected_failed']:
                    failed += 1
        return {'total': total, 'first_failed': failed,
                'rate': failed / total if total else 0}

    heavy_pred_counter = Counter()
    total_added_pred_sec = 0
    total_removed_pred_sec = 0
    large_shift_builds = []

    for b in diag:
        for s in b['stages']:
            for fs in s['failure_shifts']:
                total_added_pred_sec += fs['added_predecessor_seconds']
                total_removed_pred_sec += fs['removed_predecessor_seconds']
                for lp in fs.get('largest_added_predecessors', []):
                    heavy_pred_counter[lp['test_id']] += 1
                if fs.get('completion_shift_seconds', 0) > 100:
                    large_shift_builds.append({
                        'build': b['key'],
                        'test': fs['test_id'],
                        'shift_seconds': fs['completion_shift_seconds'],
                        'position_shift': fs['position_shift'],
                    })

    top_heavy = heavy_pred_counter.most_common(10)

    all_shifts = []
    for b in diag:
        for s in b['stages']:
            for fs in s['failure_shifts']:
                all_shifts.append(fs['position_shift'])

    ledger = load_ledger(project)
    stage_to_cp = {}
    for entry in ledger:
        if entry.get('checkpoint'):
            k = (entry['key']['project'], entry['key']['pr'],
                 entry['key']['build'], entry['key']['stage'])
            stage_to_cp[k] = entry['checkpoint']

    q_tie_analysis = {'win': [], 'loss': []}
    semantic_transfer_potential = []

    for cat, builds in [('win', wins), ('loss', losses)]:
        for b in builds:
            for s in b['stages']:
                sk = stage_key_to_tuple(s['key'])
                cp_name = stage_to_cp.get(sk)
                if not cp_name:
                    continue
                try:
                    cp = load_checkpoint(project, cp_name)
                except Exception:
                    continue

                hc_ranking = [r for r in cp['rankings'] if r['method'] == 'history_cost']
                hcf_ranking = [r for r in cp['rankings'] if r['method'] == 'hc_falcon_normalized_v1']
                if not hc_ranking or not hcf_ranking:
                    continue

                failing_tests = [o['test_id'] for o in cp['outcomes'] if o['failed']]
                n_tests = len(cp['outcomes'])
                n_failures = len(failing_tests)

                hc_order = hc_ranking[0]['order']
                hcf_order = hcf_ranking[0]['order']

                hc_pos = {t: hc_order.index(t) for t in failing_tests if t in hc_order}
                hcf_pos = {t: hcf_order.index(t) for t in failing_tests if t in hcf_order}

                for ft in failing_tests:
                    if ft in hc_pos and ft in hcf_pos:
                        delta_pos = hcf_pos[ft] - hc_pos[ft]
                        hc_rank_pct = hc_pos[ft] / n_tests if n_tests else 0
                        semantic_transfer_potential.append({
                            'project': project,
                            'category': cat,
                            'build': b['key'],
                            'failing_test': ft,
                            'hc_position': hc_pos[ft],
                            'hcf_position': hcf_pos[ft],
                            'delta_position': delta_pos,
                            'hc_rank_pct': hc_rank_pct,
                            'n_tests': n_tests,
                            'n_failures': n_failures,
                        })

                valid_sources = sum(1 for s2 in cp['source'] if s2.get('valid'))
                q_tie_analysis[cat].append({
                    'n_tests': n_tests,
                    'n_failures': n_failures,
                    'valid_sources': valid_sources,
                    'invalid_sources': n_tests - valid_sources,
                })

    return {
        'project': project,
        'total_physical_builds': len(diag),
        'wins': len(wins),
        'losses': len(losses),
        'ties': len(ties),
        'delta_distribution': {
            'all': describe(all_deltas),
            'wins': describe(win_deltas),
            'losses': describe(loss_deltas),
        },
        'semantic_share': {
            'wins': describe(win_shares),
            'losses': describe(loss_shares),
        },
        'history_groups': {
            'wins': win_groups,
            'losses': loss_groups,
        },
        'first_selected_failed': {
            'wins': first_failed_rate(wins),
            'losses': first_failed_rate(losses),
        },
        'predecessor_analysis': {
            'total_added_seconds': total_added_pred_sec,
            'total_removed_seconds': total_removed_pred_sec,
            'net_added_seconds': total_added_pred_sec - total_removed_pred_sec,
            'top_heavy_predecessors': [{'test_id': t, 'count': c} for t, c in top_heavy],
            'builds_with_100s_shift': len(large_shift_builds),
        },
        'position_shifts': describe(all_shifts),
        'failing_test_movement': {
            'win': {
                'promoted': sum(1 for x in semantic_transfer_potential if x['category'] == 'win' and x['delta_position'] < 0),
                'demoted': sum(1 for x in semantic_transfer_potential if x['category'] == 'win' and x['delta_position'] > 0),
                'same': sum(1 for x in semantic_transfer_potential if x['category'] == 'win' and x['delta_position'] == 0),
                'position_shift': describe([x['delta_position'] for x in semantic_transfer_potential if x['category'] == 'win']),
                'hc_rank_pct': describe([x['hc_rank_pct'] for x in semantic_transfer_potential if x['category'] == 'win']),
            },
            'loss': {
                'promoted': sum(1 for x in semantic_transfer_potential if x['category'] == 'loss' and x['delta_position'] < 0),
                'demoted': sum(1 for x in semantic_transfer_potential if x['category'] == 'loss' and x['delta_position'] > 0),
                'same': sum(1 for x in semantic_transfer_potential if x['category'] == 'loss' and x['delta_position'] == 0),
                'position_shift': describe([x['delta_position'] for x in semantic_transfer_potential if x['category'] == 'loss']),
                'hc_rank_pct': describe([x['hc_rank_pct'] for x in semantic_transfer_potential if x['category'] == 'loss']),
            },
        }
    }


def cross_project_summary(results):
    total_wins = sum(r['wins'] for r in results)
    total_losses = sum(r['losses'] for r in results)
    total_ties = sum(r['ties'] for r in results)
    total_builds = total_wins + total_losses + total_ties

    total_promoted_win = sum(r['failing_test_movement']['win']['promoted'] for r in results)
    total_demoted_win = sum(r['failing_test_movement']['win']['demoted'] for r in results)
    total_same_win = sum(r['failing_test_movement']['win']['same'] for r in results)
    total_promoted_loss = sum(r['failing_test_movement']['loss']['promoted'] for r in results)
    total_demoted_loss = sum(r['failing_test_movement']['loss']['demoted'] for r in results)
    total_same_loss = sum(r['failing_test_movement']['loss']['same'] for r in results)

    total_net_added = sum(r['predecessor_analysis']['net_added_seconds'] for r in results)

    return {
        'total_builds': total_builds,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'total_ties': total_ties,
        'win_rate': total_wins / total_builds if total_builds else 0,
        'failing_test_movement_aggregate': {
            'wins': {
                'promoted': total_promoted_win,
                'demoted': total_demoted_win,
                'same': total_same_win,
            },
            'losses': {
                'promoted': total_promoted_loss,
                'demoted': total_demoted_loss,
                'same': total_same_loss,
            },
        },
        'total_net_predecessor_seconds_added': total_net_added,
    }


def main():
    results = []
    for project in PROJECTS:
        result = analyze_project(project)
        results.append(result)

    summary = cross_project_summary(results)

    report = {
        'analysis': 'forensic_phase1',
        'projects': {r['project']: r for r in results},
        'cross_project': summary,
    }

    out_path = OUT / 'forensic-analysis.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    print(f'Full report saved to: {out_path}')


if __name__ == '__main__':
    main()
