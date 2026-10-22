"""Seed/stage dispersion, simulated end-to-end tradeoffs and cold-start groups."""
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean, pstdev
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage6_summary import paired_physical, describe_deltas
from scripts.stage6_pilot import write_json


def distribution(values):
    return dict(count=len(values), mean=mean(values) if values else None,
                median=float(np.median(values)) if values else None,
                p95=float(np.quantile(values, .95)) if values else None,
                maximum=max(values) if values else None)


def main():
    summary = json.loads((ROOT / 'reports/stage6/summary.json').read_text())
    supplement = {}
    for project in summary['projects']:
        directory = ROOT / 'reports/stage6' / project
        ledger = json.loads((directory / 'ledger.json').read_text())
        seed_dispersion = defaultdict(list)
        stage_dispersion = defaultdict(lambda: defaultdict(list))
        groups = {name:dict(tests=0, failing_records=0, detected10=0., normalized_failure_positions=[],
                           normalized_failure_completion=[]) for name in ('N0', 'N1_4', 'N5plus')}
        stages = {}
        warm_ratios = defaultdict(list)
        warm_stages = []
        for row in ledger:
            if not row['checkpoint']:
                continue
            with gzip.open(directory / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as f:
                build = json.load(f)
            key = tuple(build['key'][k] for k in ('project', 'pr', 'build', 'stage'))
            methods = defaultdict(list)
            end_to_end = defaultdict(list)
            for record in build['rankings']:
                methods[record['method']].append(record['metrics']['apfdc_midpoint'])
                end_to_end[record['method']].append(dict(ttff_end_to_end=record['ttff_end_to_end_simulated']))
                if record['method'] == 'hc_falcon_normalized_v1':
                    n = len(build['inventory'])
                    total = record['metrics']['total_duration_seconds']
                    if total and total > 0:
                        preparation_and_ranking = record['prep_seconds'] + record['ranking_seconds']
                        ratio = preparation_and_ranking / total
                        warm_ratios[key[:3]].append(ratio)
                        warm_stages.append(dict(key=build['key'], ratio=ratio,
                            preparation_and_ranking_seconds=preparation_and_ranking,
                            embedding_cache_misses=build['runtime']['embedding_cache_misses']))
                    for name, values in record['history_groups'].items():
                        group = groups[name]
                        group['tests'] += values['tests']
                        group['failing_records'] += values['failures']
                        if values['recall10'] is not None:
                            group['detected10'] += values['recall10'] * values['failures']
                        group['normalized_failure_positions'].extend(p/n for p in values['failure_positions'])
                        if total and total > 0:
                            group['normalized_failure_completion'].extend(t/total for t in values['failure_completion_seconds'])
            for name, values in methods.items():
                known = [v for v in values if v is not None]
                if known:
                    stage_dispersion[name][key[:3]].append(mean(known))
                    if name in ('random', 'fast_pw_lrts'):
                        seed_dispersion[name].append(pstdev(known))
            stages[key] = end_to_end
        for group in groups.values():
            group['recall10_pooled_failing_records_descriptive'] = group['detected10'] / group['failing_records'] if group['failing_records'] else None
            group['normalized_failure_positions'] = distribution(group['normalized_failure_positions'])
            group['normalized_failure_completion'] = distribution(group['normalized_failure_completion'])
        supplement[project] = dict(seed_apfdc_std_by_stage={name:distribution(values) for name,values in seed_dispersion.items()},
            stage_apfdc_std_within_multistage_physical={name:distribution([pstdev(values) for values in physical.values() if len(values)>1]) for name,physical in stage_dispersion.items()},
            paired_simulated_end_to_end_ttff={name:describe_deltas(paired_physical(stages, 'hc_falcon_normalized_v1', name, 'ttff_end_to_end').values()) for name in ('fl_only','history_only','history_cost','fast_pw_lrts','dante_cch_adapt_r1')},
            history_groups_observation_level_descriptive=groups,
            primary_warm_overhead_physical_distribution=distribution([mean(v) for v in warm_ratios.values()]),
            primary_worst_overhead_stages=sorted(warm_stages, key=lambda row:row['ratio'], reverse=True)[:5])
    balanced = {}
    for comparator in ('fl_only','history_only','history_cost','fast_pw_lrts','dante_cch_adapt_r1'):
        balanced[comparator] = {}
        for metric in ('apfdc_midpoint','apfd','ttff_seconds','recall10'):
            values = [p['paired'][comparator][metric]['mean_delta'] for p in summary['projects'].values() if p['paired'][comparator][metric]['mean_delta'] is not None]
            balanced[comparator][metric] = dict(projects=len(values), mean_of_project_means=mean(values) if values else None)
    write_json(ROOT / 'reports/stage6/supplement.json', dict(projects=supplement, project_balanced_paired_delta=balanced,
        inference='descriptive_only; seed/stage dispersion and pooled test observations are not independent statistical samples'))
    print('Supplement complete')


if __name__ == '__main__':
    main()
