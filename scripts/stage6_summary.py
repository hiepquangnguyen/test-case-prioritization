"""Descriptive development-only physical-build comparisons and predeclared gates."""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
from statistics import mean, median
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage6_pilot import write_json, verify_implementation

PRIMARY = 'hc_falcon_normalized_v1'
METRICS = ('apfdc_midpoint', 'apfd', 'ttff_seconds', 'recall10', 'recall25', 'recall50')


def seed_mean(records, metric):
    values = [r[metric] for r in records if r[metric] is not None]
    return mean(values) if values else None


def paired_physical(stages, primary, comparator, metric):
    physical = defaultdict(list)
    for key, methods in stages.items():
        if primary not in methods or comparator not in methods:
            continue
        a = seed_mean(methods[primary], metric)
        b = seed_mean(methods[comparator], metric)
        if a is not None and b is not None:
            physical[key[:3]].append(a - b)
    return {key: mean(values) for key, values in physical.items()}


def describe_deltas(values):
    values = list(values)
    return dict(pairs=len(values), mean_delta=mean(values) if values else None,
                median_delta=median(values) if values else None,
                positive=sum(v > 1e-12 for v in values), tie=sum(abs(v) <= 1e-12 for v in values),
                negative=sum(v < -1e-12 for v in values))


def independent_check(record, outcomes):
    order = record['order']
    data = {o['test_id']: o for o in outcomes}
    if len(order) != len(data) or set(order) != set(data):
        raise ValueError('Ranking is not a complete permutation')
    if any(o['failed'] is None for o in outcomes):
        return
    m = sum(o['failed'] for o in outcomes)
    reported = record['metrics']
    if not m:
        if reported['apfd'] is not None or reported['apfdc_midpoint'] is not None:
            raise ValueError('No-failure score must remain NA')
        return
    n = len(order)
    apfd = sum(n - i - .5 for i, tid in enumerate(order) if data[tid]['failed']) / (n * m)
    if not math.isclose(apfd, reported['apfd'], abs_tol=1e-10):
        raise ValueError('Independent APFD mismatch')
    costs = [data[tid]['duration'] for tid in order]
    if any(c is None or not math.isfinite(c) or c < 0 for c in costs) or sum(costs) <= 0:
        return
    suffix = 0
    area = 0
    for tid in reversed(order):
        cost = data[tid]['duration']
        if data[tid]['failed']:
            area += suffix + cost / 2
        suffix += cost
    if not math.isclose(area / (m * suffix), reported['apfdc_midpoint'], abs_tol=1e-10):
        raise ValueError('Independent APFDc mismatch')


def project_summary(project):
    directory = ROOT / 'reports/stage6' / project
    complete = json.loads((directory / 'complete.json').read_text())
    ledger = json.loads((directory / 'ledger.json').read_text())
    stages = {}
    source = defaultdict(lambda: defaultdict(int))
    overhead = defaultdict(lambda: defaultdict(list))
    cold_ratios = defaultdict(list)
    verified = 0
    source_truncation = []
    runtime = []
    groups = []
    observed_peak_rss = complete['peak_rss']
    for row in ledger:
        if row['split'] != 'development' or not row['usable']:
            continue
        with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as f:
            build = json.load(f)
        observed_peak_rss = max(observed_peak_rss, build['peak_rss'])
        if build['key'] != row['key'] or build['split'] != 'development' or build['manifest']['reserved_opened']:
            raise ValueError('Checkpoint/cohort mismatch')
        if build['history']['latest'] is not None and build['history']['latest'] >= build['cutoff']:
            raise ValueError('History cutoff violation')
        key = tuple(build['key'][k] for k in ('project', 'pr', 'build', 'stage'))
        methods = defaultdict(list)
        outcomes = {o['test_id']: o for o in build['outcomes']}
        for item in build['source']:
            category = 'failing' if outcomes[item['test_id']]['failed'] else 'other'
            source[category]['records'] += 1
            source[category]['valid'] += item['valid']
            source[category]['nested'] += item['nested']
            source[category]['truncated'] += item['truncation_fraction'] > 0
            source_truncation.append(item['truncation_fraction'])
        for record in build['rankings']:
            independent_check(record, build['outcomes'])
            verified += 1
            metric = record['metrics']
            values = {name: metric[name] for name in ('apfd', 'apfdc_midpoint', 'ttff_seconds')}
            values.update({f'recall{int(float(b)*100)}': value for b, value in metric['recall'].items()})
            values.update(ttff_censored=metric['ttff_censored'], prep=record['prep_seconds'], ranking=record['ranking_seconds'])
            methods[record['method']].append(values)
            if record['method'] == PRIMARY:
                groups.append(dict(key=build['key'], groups=record['history_groups']))
        for method, samples in methods.items():
            total = next(r['metrics']['total_duration_seconds'] for r in build['rankings'] if r['method'] == method)
            if total is not None and total > 0:
                overhead[method][key[:3]].append(mean(r['prep'] + r['ranking'] for r in samples) / total)
        stages[key] = methods
        measured = build['runtime']
        runtime.append(measured)
        primary = next(r for r in build['rankings'] if r['method'] == PRIMARY)
        total = primary['metrics']['total_duration_seconds']
        if total and measured['cold_cost_missing_hashes'] == 0:
            cold_ratios[key[:3]].append((measured['model_load_seconds'] + measured['source_seconds'] +
                                measured['cold_embedding_reconstructed_seconds'] + measured['kernel_seconds'] +
                                measured['history_seconds'] + primary['ranking_seconds']) / total)
    names = sorted({name for methods in stages.values() for name in methods})
    comparisons = {name: {metric: describe_deltas(paired_physical(stages, PRIMARY, name, metric).values())
                           for metric in METRICS} for name in names if name != PRIMARY}
    method_summary = {}
    for name in names:
        method_summary[name] = {}
        for metric in METRICS:
            physical = defaultdict(list)
            censored = 0
            for key, methods in stages.items():
                if name not in methods:
                    continue
                value = seed_mean(methods[name], metric)
                if value is not None:
                    physical[key[:3]].append(value)
                if metric == 'ttff_seconds':
                    censored += any(r['ttff_censored'] for r in methods[name])
            values = [mean(v) for v in physical.values()]
            method_summary[name][metric] = dict(physical_builds=len(values), mean=mean(values) if values else None,
                                                median=median(values) if values else None,
                                                censored_stage_count=censored if metric == 'ttff_seconds' else None)
    effect = all(comparisons[name]['apfdc_midpoint']['median_delta'] is not None and
                 comparisons[name]['apfdc_midpoint']['median_delta'] >= .03 for name in ('fl_only', 'history_cost'))
    stage_overhead_p95 = {name:float(np.quantile([v for values in physical.values() for v in values], .95))
                          for name, physical in overhead.items()}
    overhead = {name:[mean(values) for values in physical.values()] for name, physical in overhead.items()}
    cold_ratios = [mean(values) for values in cold_ratios.values()]
    p95 = float(np.quantile(overhead[PRIMARY], .95)) if overhead[PRIMARY] else None
    report = dict(project=project, development_only=True, stages_scored=len(stages),
                  physical_scored=len({key[:3] for key in stages}), rankings_verified=verified,
                  source=dict(source), truncation_fraction_p95=float(np.quantile(source_truncation, .95)),
                  methods=method_summary, paired= comparisons, effect_gate_passed=effect,
                  engineering=dict(peak_rss=observed_peak_rss, p95_warm_overhead_ratio=p95,
                                   peak_rss_scope='maximum_of_completion_and_all_development_checkpoints_across_resumes',
                                   unit='physical_build_mean_of_defined_stage_ratios_after_seed_mean',
                                   stage_overhead_p95_diagnostic=stage_overhead_p95,
                                   passed=p95 is not None and p95 <= .1 and observed_peak_rss <= 8 * 1024**3,
                                   overhead_p95_by_method={name:float(np.quantile(values,.95)) for name, values in overhead.items()},
                                   cold_reconstructed_overhead_p95=float(np.quantile(cold_ratios,.95)) if cold_ratios else None,
                                   cold_reconstructed_builds=len(cold_ratios), cold_not_direct_full_build_measurement=True),
                  embedding_cache_misses=sum(r['embedding_cache_misses'] for r in runtime))
    write_json(directory / 'summary.json', report)
    write_json(directory / 'history-groups.json', groups)
    return report


def main():
    verify_implementation()
    reports = {project:project_summary(project) for project in ('karaf', 'activemq', 'log4j')}
    passed = sum(r['effect_gate_passed'] for r in reports.values())
    engineering_passed = all(r['engineering']['passed'] for r in reports.values())
    write_json(ROOT / 'reports/stage6/summary.json', dict(projects=reports, reserved_opened=False,
        effect_gate_projects_passed=passed, effect_gate_passed=passed >= 2,
        engineering_gate_passed=engineering_passed,
        decision='eligible_for_review_before_confirmation' if passed >= 2 and engineering_passed else 'no_go_revise_on_development',
        inference='descriptive_development_only; no confirmation significance claims'))
    print('Pilot summary complete:', passed, '/ 3 effect gates; engineering', engineering_passed)


if __name__ == '__main__':
    main()
