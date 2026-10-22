"""Read-only diagnosis of frozen development rankings; no new ranker or reserved data."""
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean, median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage6_pilot import write_json, verify_implementation
from tcp.lrts import file_sha256

PRIMARY = 'hc_falcon_normalized_v1'


def timing(order, outcomes):
    elapsed = 0.0
    result = {}
    for position, tid in enumerate(order, 1):
        cost = outcomes[tid]['duration']
        result[tid] = dict(position=position, midpoint=elapsed + cost / 2,
                           completion=elapsed + cost)
        elapsed += cost
    return result


def contributions(first, second, outcomes):
    a, b = timing(first, outcomes), timing(second, outcomes)
    failures = [tid for tid, o in outcomes.items() if o['failed']]
    total = sum(o['duration'] for o in outcomes.values())
    if not failures or total <= 0:
        return []
    result = [dict(test_id=tid, position_shift=a[tid]['position'] - b[tid]['position'],
                 completion_shift_seconds=a[tid]['completion'] - b[tid]['completion'],
                 apfdc_delta=-(a[tid]['midpoint'] - b[tid]['midpoint']) / (len(failures) * total))
            for tid in failures]
    for row in result:
        tid = row['test_id']
        before_a = set(first[:a[tid]['position']-1])
        before_b = set(second[:b[tid]['position']-1])
        added, removed = before_a-before_b, before_b-before_a
        added_cost = sum(outcomes[t]['duration'] for t in added)
        removed_cost = sum(outcomes[t]['duration'] for t in removed)
        assert abs(added_cost-removed_cost-row['completion_shift_seconds']) < 1e-7
        row['added_predecessor_seconds'] = added_cost
        row['removed_predecessor_seconds'] = removed_cost
        row['largest_added_predecessors'] = [dict(test_id=t, duration=outcomes[t]['duration'],
            failed=outcomes[t]['failed']) for t in sorted(added,key=lambda t:(-outcomes[t]['duration'],t))[:5]]
    return result


def describe(values):
    return dict(count=len(values), mean=mean(values) if values else None,
                median=median(values) if values else None,
                positive=sum(v > 1e-12 for v in values),
                negative=sum(v < -1e-12 for v in values),
                tie=sum(abs(v) <= 1e-12 for v in values))


def main():
    verify_implementation()
    frozen = json.loads((ROOT / 'reports/stage6/final-evidence-freeze.json').read_text())
    for name, expected in frozen['files_sha256'].items():
        if file_sha256(ROOT / name) != expected:
            raise ValueError('Stage 6 evidence changed: ' + name)
    summary = json.loads((ROOT / 'reports/stage6/summary.json').read_text())
    reports = {}
    for project in summary['projects']:
        directory = ROOT / 'reports/stage6' / project
        ledger = json.loads((directory / 'ledger.json').read_text())
        stages, physical = [], defaultdict(list)
        variant_deltas = defaultdict(lambda: defaultdict(list))
        group_totals = {g:dict(tests=0, failures=0, delayed_failures=0, advanced_failures=0,
                              valid_failing_source=0, apfdc_contributions=[])
                        for g in ('N0', 'N1_4', 'N5plus')}
        first_shares = []
        for row in ledger:
            if not row['checkpoint']:
                continue
            assert row['split'] == 'development'
            with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as stream:
                build = json.load(stream)
            assert build['manifest']['reserved_opened'] is False
            records = {r['method']:r for r in build['rankings'] if r['seed'] == 0}
            hc, base = records[PRIMARY], records['history_cost']
            outcomes = {o['test_id']:o for o in build['outcomes']}
            sources = {s['test_id']:s for s in build['source']}
            first = hc['trace'][0]
            share = first['semantic_gain'] / first['total_gain'] if first['total_gain'] else None
            if share is not None:
                first_shares.append(share)
            groups_by_failure = {}
            for group, values in hc['history_groups'].items():
                group_totals[group]['tests'] += values['tests']
                group_totals[group]['failures'] += values['failures']
                for pos in values['failure_positions']:
                    groups_by_failure[hc['order'][pos-1]] = group
            a, b = hc['metrics']['apfdc_midpoint'], base['metrics']['apfdc_midpoint']
            if a is None or b is None:
                continue
            key = tuple(build['key'][k] for k in ('project', 'pr', 'build'))
            delta = a-b
            shifts = contributions(hc['order'], base['order'], outcomes)
            assert abs(sum(s['apfdc_delta'] for s in shifts) - delta) < 1e-10
            for shift in shifts:
                group = groups_by_failure[shift['test_id']]
                shift['history_group'] = group
                shift['valid_source'] = sources[shift['test_id']]['valid']
                totals = group_totals[group]
                totals['delayed_failures'] += shift['completion_shift_seconds'] > 1e-9
                totals['advanced_failures'] += shift['completion_shift_seconds'] < -1e-9
                totals['valid_failing_source'] += shift['valid_source']
                totals['apfdc_contributions'].append(shift['apfdc_delta'])
            record = dict(key=build['key'], delta_apfdc=delta,
                first_selected_semantic_share=share,
                first_selected_failed=outcomes[first['test_id']]['failed'],
                first_selected_duration=outcomes[first['test_id']]['duration'],
                first_selected=first['test_id'],
                failure_shifts=sorted(shifts, key=lambda s:s['apfdc_delta']))
            stages.append(record)
            physical[key].append(record)
            for name in ('hc_alpha_0.0','hc_alpha_0.25',PRIMARY,'hc_alpha_0.75','hc_alpha_1.0',
                         'hc_falcon_topic_raw_v1','no_confidence','borda_history_cost','dante_cch_adapt_r1'):
                score = records[name]['metrics']['apfdc_midpoint']
                if score is not None:
                    variant_deltas[name][key].append(score-b)
        physical_rows = [dict(key=dict(zip(('project','pr','build'), key)),
                             delta_apfdc=mean(r['delta_apfdc'] for r in rows), stages=rows)
                         for key, rows in physical.items()]
        paired = describe([r['delta_apfdc'] for r in physical_rows])
        assert abs(paired['median'] - summary['projects'][project]['paired']['history_cost']['apfdc_midpoint']['median_delta']) < 1e-10
        for totals in group_totals.values():
            totals['apfdc_contributions'] = describe(totals['apfdc_contributions'])
        reports[project] = dict(paired_vs_history_cost=paired,
            first_selected_semantic_share=describe(first_shares),
            groups_observation_level_descriptive=group_totals,
            variants_vs_history_cost={name:describe([mean(v) for v in values.values()])
                                     for name, values in variant_deltas.items()},
            worst_physical=sorted(physical_rows,key=lambda r:r['delta_apfdc'])[:5],
            best_physical=sorted(physical_rows,key=lambda r:r['delta_apfdc'],reverse=True)[:5])
        write_json(ROOT / 'reports/stage7' / project / 'physical-diagnosis.json', physical_rows)
    write_json(ROOT / 'reports/stage7/diagnosis.json', dict(projects=reports,
        reserved_opened=False, stage6_freeze_verified=True,
        interpretation='descriptive development diagnosis; contributions algebraically decompose APFDc; no causal or confirmation claim',
        source_freeze_sha256=file_sha256(ROOT / 'reports/stage6/final-evidence-freeze.json')))
    print(json.dumps({p:{k:v[k] for k in ('paired_vs_history_cost','first_selected_semantic_share','groups_observation_level_descriptive','variants_vs_history_cost')} for p,v in reports.items()},indent=2))


if __name__ == '__main__':
    main()
