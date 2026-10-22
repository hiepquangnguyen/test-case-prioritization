"""Physical-build comparisons for the fixed restricted revision and separate cache policy."""
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage6_summary import paired_physical, describe_deltas
from scripts.stage6_pilot import write_json

PRIMARY = 'restricted_semantic_cost_v1'
POLICY = 'cache_only_restricted_v1_simulated'


def flatten(metrics):
    return dict(apfdc=metrics['apfdc_midpoint'],ttff=metrics['ttff_seconds'],
                recall10=metrics['recall']['0.1'])


def main():
    reports = {}
    manifest = json.loads((ROOT/'reports/stage8/manifest.json').read_text())
    for project in ('karaf','activemq','log4j'):
        directory = ROOT/'reports/stage8'/project
        complete = json.loads((directory/'complete.json').read_text())
        assert complete['manifest'] == manifest
        stages, costs = {},defaultdict(list)
        fallback_stages, fallback_keys, zero_q_stages, zero_gain_steps = 0,set(),0,0
        groups = {g:dict(tests=0,failures=0,detected10=0.) for g in ('N0','N1_4','N5plus')}
        mutations, peak = [],0
        for path in sorted((directory/'builds').glob('*.json.gz')):
            with gzip.open(path,'rt',encoding='utf-8') as stream:
                record = json.load(stream)
            assert record['manifest'] == manifest and record['history_only_exact_match']
            key = tuple(record['key'][k] for k in ('project','pr','build','stage'))
            assert key not in stages
            methods = {name:[flatten(m)] for name,m in record['comparators'].items()}
            methods[PRIMARY] = [flatten(record['metrics'])]
            methods[POLICY] = [flatten(record['cache_policy']['metrics'])]
            stages[key] = methods
            if record['cache_policy']['fallback']:
                fallback_stages += 1
                fallback_keys.add(key[:3])
            zero_q_stages += any(step['zero_q'] for step in record['trace'])
            zero_gain_steps += sum(step['zero_gain_fallback'] for step in record['trace'])
            for name, values in record['history_groups'].items():
                groups[name]['tests'] += values['tests']
                groups[name]['failures'] += values['failures']
                if values['recall10'] is not None:
                    groups[name]['detected10'] += values['recall10']*values['failures']
            runtime = record['runtime']
            total = record['metrics']['total_duration_seconds']
            if total and total > 0:
                costs[key[:3]].append(sum(runtime[n] for n in ('history_seconds','kernel_prep_seconds','ranking_seconds'))/total)
            peak = max(peak,runtime['peak_rss'])
            if record['ineligible_mutation_count'] is not None:
                mutations.append(dict(key=record['key'],mutated=record['ineligible_mutation_count']))
        assert len(stages) == complete['stages']
        comparisons = {}
        for method in (PRIMARY,POLICY):
            comparisons[method] = {name:{metric:describe_deltas(paired_physical(stages,method,name,metric).values())
                for metric in ('apfdc','ttff','recall10')}
                for name in ('history_cost','hc_falcon_normalized_v1','fl_only')}
        effect = all(comparisons[PRIMARY][name]['apfdc']['median_delta'] is not None and
                     comparisons[PRIMARY][name]['apfdc']['median_delta'] >= .03 for name in ('history_cost','fl_only'))
        deltas = paired_physical(stages,PRIMARY,'history_cost','apfdc')
        for group in groups.values():
            group['recall10_pooled'] = group['detected10']/group['failures'] if group['failures'] else None
        ratios = [mean(v) for v in costs.values()]
        reports[project] = dict(stages=len(stages),physical=len({k[:3] for k in stages}),
            comparisons=comparisons,effect_gate_passed=effect,
            cache_policy=dict(fallback_stages=fallback_stages,physical_with_fallback=len(fallback_keys),
                              assumptions='chronological offline source cache; prepare after each usable stage, no async latency model'),
            zero_q_stages=zero_q_stages,zero_gain_fallback_steps=zero_gain_steps,
            groups_observation_level=groups,mutation_checks=mutations,
            runtime=dict(p95_cached_reconstruction_ratio=float(np.quantile(ratios,.95)),
                maximum_cached_reconstruction_ratio=max(ratios),peak_rss=peak,
                full_pipeline_engineering_gate='not_remeasured; source extraction and encoding excluded'),
            worst_physical=[dict(key=dict(zip(('project','pr','build'),k)),delta_apfdc=v)
                            for k,v in sorted(deltas.items(),key=lambda item:item[1])[:5]])
    passed = sum(r['effect_gate_passed'] for r in reports.values())
    result = dict(projects=reports,reserved_opened=False,effect_gate_projects_passed=passed,
        decision='no_go' if passed < 2 else 'effect_gate_passed_pending_full_pipeline_engineering_review',
        inference='development-only revision selected after stage6 diagnosis; no independent confirmation claim')
    write_json(ROOT/'reports/stage8/summary.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
