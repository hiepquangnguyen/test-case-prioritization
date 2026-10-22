"""Replay saved evidence, verify all rankings and diagnose development only."""
import csv
import gzip
import json
import sys
from collections import Counter
from dataclasses import asdict, replace
from itertools import zip_longest
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tcp.domain import BuildKey, CompletedBuild, Outcome, RankingInput, TestInput
from tcp.baselines import rank
from tcp.history import HistoryConfig, RollingHistory
from tcp.lrts import file_sha256
from tcp.metrics import evaluate
from scripts.pilot_support import OUT, compact_snapshot, digest, score_reason, split_for, write_json
from scripts.stage3_run import flatten, methods, snapshots, summarize, validate_manifest


def records(name):
    with gzip.open(OUT/(name+'.jsonl.gz'),'rt',encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)


def load_saved():
    builds=[]
    for inp,gt in zip_longest(records('inputs'),records('ground-truth')):
        assert inp is not None and gt is not None and inp['key']==gt['key']
        inp['key']=BuildKey(**inp['key'])
        inp['tests']=tuple(TestInput(**{**t,'source_paths':tuple(t['source_paths'])}) for t in inp['tests'])
        builds.append(CompletedBuild(RankingInput(**inp),gt['available_at'],gt['result'],tuple(Outcome(**o) for o in gt['outcomes'])))
    return tuple(builds)


def diagnose(build,snapshot,cohort):
    orders={m:rank(snapshot,m) for m in ('most_fail','recent_fail','history_only','history_cost')}
    metrics={m:evaluate(o,build.outcomes) for m,o in orders.items()}
    ho,hc=metrics['history_only'],metrics['history_cost']
    ranks={m:{tid:i for i,tid in enumerate(order,1)} for m,order in orders.items()}
    features={f.test_id:f for f in snapshot.features}
    runtime=[];failures=[]
    for outcome in build.outcomes:
        f=features[outcome.test_id]
        group='cold' if f.observations==0 else 'low_1_4' if f.observations<5 else 'established_5_plus'
        ratio=f.duration_estimate/outcome.duration if outcome.duration is not None and outcome.duration>0 else None
        runtime.append(dict(key=asdict(build.inputs.key),cohort=cohort,test_id=outcome.test_id,
            history_group=group,observations=f.observations,failed=outcome.failed,
            predicted=f.duration_estimate,actual=outcome.duration,origin=f.duration_origin,
            predicted_actual_ratio=ratio,absolute_error=abs(f.duration_estimate-outcome.duration) if outcome.duration is not None and outcome.duration>=0 else None))
        if outcome.failed:
            failures.append(dict(test_id=outcome.test_id,history_group=group,predicted=f.duration_estimate,
                actual=outcome.duration,history_score=f.history_score,history_cost_score=f.history_cost_score,
                history_only_rank=ranks['history_only'][outcome.test_id],history_cost_rank=ranks['history_cost'][outcome.test_id],
                rank_shift=ranks['history_cost'][outcome.test_id]-ranks['history_only'][outcome.test_id]))
    delta=lambda key:hc[key]-ho[key] if hc[key] is not None and ho[key] is not None else None
    return dict(key=asdict(build.inputs.key),cohort=cohort,eligible_history_builds=len(snapshot.eligible_builds),
        cold_tests=sum(f.observations==0 for f in snapshot.features),tests=len(snapshot.features),
        apfdc_delta_cost_minus_history=delta('apfdc_midpoint'),ttff_delta_seconds=delta('ttff_seconds'),
        recall_deltas={b:hc['recall'][b]-ho['recall'][b] if hc['recall'][b] is not None and ho['recall'][b] is not None else None for b in ho['recall']},
        metrics=metrics,most_recent_history_identical=orders['most_fail']==orders['recent_fail']==orders['history_only'],
        failure_positions=failures),runtime


def main():
    manifest,selection=validate_manifest()
    completed=json.loads((OUT/'run-complete.json').read_text(encoding='utf-8'))
    assert file_sha256(OUT/'manifest.json')==completed['manifest_sha256']
    for path,sha in completed['artifacts_sha256'].items():
        assert file_sha256(OUT/path)==sha,path
    builds=load_saved()
    actual=[dict(key=asdict(b.inputs.key),cutoff=b.inputs.cutoff,split=split_for(b.inputs.cutoff),commit=b.inputs.commit,branch=b.inputs.branch) for b in builds]
    assert digest(actual)==manifest['selection_sha256']
    fs=iter(records('features'));rs=iter(records('rankings'));count=0;flat=[];paired=[];runtime_stats={}
    bykey={b.inputs.key:b for b in builds}
    with gzip.open(OUT/'development-runtime-errors.jsonl.gz','wt',encoding='utf-8') as runtime_file:
        for i,(build,snapshot,_) in enumerate(snapshots(builds,HistoryConfig(**manifest['config']))):
            stored=next(fs);compact=compact_snapshot(snapshot)
            assert digest(compact)==stored['sha256'] and json.loads(json.dumps(compact))==stored['snapshot']
            assert all(bykey[k].available_at < build.inputs.cutoff and bykey[k].usable
                       and bykey[k].inputs.context==build.inputs.context and k.physical!=build.inputs.key.physical
                       for k in snapshot.eligible_builds)
            split=split_for(build.inputs.cutoff);reason=score_reason(build,split)
            for method,seed in methods():
                row=next(rs);order=rank(snapshot,method,seed)
                assert row['key']==asdict(build.inputs.key) and row['method']==method and row['seed']==seed
                assert row['split']==split and row['reason']==reason and row['snapshot_sha256']==stored['sha256']
                assert list(order)==row['order'] and len(order)==len(build.outcomes) and set(order)=={o.test_id for o in build.outcomes}
                metric=evaluate(order,build.outcomes) if reason is None else None
                assert metric==row['metrics']
                flat.append(flatten(row['key'],split,method,seed,metric,reason));count+=1
            if build.usable and (i<20 or split=='development'):
                cohort='technical20_v2' if i<20 else 'development'
                p,runtime=diagnose(build,snapshot,cohort);paired.append(p)
                for r in runtime:
                    runtime_file.write(json.dumps(r,allow_nan=False)+'\n')
                    stats=runtime_stats.setdefault((cohort,r['history_group']),dict(count=0,ratios=[],errors=[]))
                    stats['count']+=1
                    if r['predicted_actual_ratio'] is not None: stats['ratios'].append(r['predicted_actual_ratio'])
                    if r['absolute_error'] is not None: stats['errors'].append(r['absolute_error'])
            if (i+1)%100==0: print('Verified',i+1,'builds',flush=True)
    assert next(fs,None) is None and next(rs,None) is None
    assert len(builds)==completed['builds'] and count==completed['rankings']
    assert summarize(flat)==json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    with (OUT/'metrics.csv').open(encoding='utf-8',newline='') as f:
        csvrows=list(csv.DictReader(f))
    assert len(csvrows)==len(flat)
    for saved,row in zip(csvrows,flat):
        assert all(saved[k]==('' if row.get(k) is None else str(row[k])) for k in saved)
    # All current/future records are ingested deliberately; snapshot must reject
    # them even when the store already knows their outcomes and availability.
    indexes=set(range(20))|{len(builds)-1}
    for j,b in enumerate(builds):
        if j and split_for(b.inputs.cutoff)!=split_for(builds[j-1].inputs.cutoff):indexes.update((j-1,j))
    audit=json.loads((OUT/'data-audit.json').read_text(encoding='utf-8'))
    indexes.update(i for i,a in enumerate(audit) if a['overlap_same_context'])
    checks=0
    base=RollingHistory(HistoryConfig(**manifest['config']))
    for b in builds:base.observe(b)
    for i in sorted(indexes):
        target=builds[i];changed=RollingHistory(HistoryConfig(**manifest['config']))
        for b in builds:
            if b.inputs.cutoff>=target.inputs.cutoff:
                b=replace(b,result='ABORTED',available_at=b.inputs.cutoff+999999,
                          outcomes=tuple(Outcome(o.test_id,not o.failed,987654.0) for o in b.outcomes))
            changed.observe(b)
        before=base.snapshot(target.inputs);after=changed.snapshot(target.inputs)
        assert before==after
        for method,seed in methods():assert rank(before,method,seed)==rank(after,method,seed);checks+=1
    write_json(OUT/'history-cost-paired.json',paired)
    summary=[]
    for cohort in ('technical20_v2','development'):
        subset=[p for p in paired if p['cohort']==cohort]
        deltas=[p['apfdc_delta_cost_minus_history'] for p in subset if p['apfdc_delta_cost_minus_history'] is not None]
        shifts=[f['rank_shift'] for p in subset for f in p['failure_positions']]
        summary.append(dict(cohort=cohort,builds=len(subset),apfdc_pairs=len(deltas),
            median_paired_delta=median(deltas) if deltas else None,
            cost_better=sum(d>1e-12 for d in deltas),cost_worse=sum(d < -1e-12 for d in deltas),
            tied=sum(abs(d)<=1e-12 for d in deltas),identical_most_recent_history=sum(p['most_recent_history_identical'] for p in subset),
            failures_moved_later=sum(s>0 for s in shifts),failures_moved_earlier=sum(s<0 for s in shifts),
            runtime=[dict(group=g,count=s['count'],positive_actual_count=len(s['ratios']),
                median_predicted_actual_ratio=median(s['ratios']) if s['ratios'] else None,
                median_absolute_error_seconds=median(s['errors']) if s['errors'] else None)
                for (c,g),s in runtime_stats.items() if c==cohort]))
    write_json(OUT/'history-cost-summary.json',summary)
    write_json(OUT/'verification.json',dict(status='passed',builds=len(builds),reproduced_rankings=count,
        metrics_csv_and_summary_verified=True,manifest_and_artifact_hashes_match=True,
        full_inventory_and_history_eligibility_verified=True,mutation_cutoffs=len(indexes),
        mutation_ranking_comparisons=checks,diagnostics_exclude_holdout=True,
        limitation='Conditional on postprocessed observed inventory and assumed build start/duration semantics'))
    print(json.dumps(dict(status='passed',rankings=count,mutation_comparisons=checks),indent=2))


if __name__=='__main__':main()
