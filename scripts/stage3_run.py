"""Streaming baseline pilot with frozen manifest and compact auditable evidence."""
import csv
import gzip
import json
import sys
import time
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tcp.baselines import METHODS, rank
from tcp.history import HistoryConfig, RollingHistory
from tcp.lrts import file_sha256, load_builds, verify_archive
from tcp.metrics import evaluate
from scripts.pilot_support import OUT, SEEDS, compact_snapshot, conservative, digest, score_reason, split_for, write_json


def validate_manifest():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['protocol_sha256']==file_sha256(ROOT/'docs/03-pilot/protocol-v2.md'), 'Protocol changed'
    for path,sha in manifest['code_sha256'].items():
        assert file_sha256(ROOT/path)==sha, 'Implementation changed: '+path
    assert manifest['annotations_sha256']==file_sha256(ROOT/'reports/stage1/karaf-source-mapping.csv')
    selection=json.loads((OUT/'selection.json').read_text(encoding='utf-8'))
    assert digest(selection)==manifest['selection_sha256']
    return manifest,selection


def snapshots(builds,config=HistoryConfig()):
    history=RollingHistory(config)
    pending=sorted((b for b in builds if b.available_at is not None),key=lambda b:(b.available_at,b.inputs.key))
    cursor=0
    for build in sorted(builds,key=lambda b:(b.inputs.cutoff,b.inputs.key)):
        while cursor<len(pending) and pending[cursor].available_at<build.inputs.cutoff:
            history.observe(pending[cursor]);cursor+=1
        started=time.perf_counter()
        snapshot=history.snapshot(build.inputs)
        yield build,snapshot,time.perf_counter()-started


def methods():
    return [(method,seed) for method in METHODS for seed in (SEEDS if method=='random' else (42,))]


def flatten(key,split,method,seed,metrics,reason):
    row=dict(**key,split=split,method=method,seed=seed,reason=reason)
    if metrics is not None:
        for field in ('tests','observed_failures','apfd','apfdc_midpoint','ttff_seconds',
                      'ttff_censored','censor_time_seconds','invalid_durations','zero_durations'):
            row[field]=metrics[field]
        row.update(recall_10=metrics['recall']['0.1'],recall_25=metrics['recall']['0.25'],
                   recall_50=metrics['recall']['0.5'],reason=';'.join(metrics['reasons']))
    return row


def summarize(rows):
    result=[]
    metric_names=('apfd','apfdc_midpoint','ttff_seconds','recall_10','recall_25','recall_50')
    for split in ('development','holdout'):
        for method in METHODS:
            subset=[r for r in rows if r['split']==split and r['method']==method]
            grouped={}
            for r in subset:
                grouped.setdefault(tuple(r[k] for k in ('project','pr','build','stage')),[]).append(r)
            entry=dict(split=split,method=method,builds=len(grouped),
                       scored_builds=sum('tests' in g[0] for g in grouped.values()),
                       no_failure_builds=sum(g[0].get('observed_failures')==0 for g in grouped.values()),
                       ttff_censored_builds=sum(g[0].get('ttff_censored') is True for g in grouped.values()),
                       metrics={})
            for metric in metric_names:
                values=[mean(r[metric] for r in g if r.get(metric) is not None) for g in grouped.values()
                        if any(r.get(metric) is not None for r in g)]
                entry['metrics'][metric]=dict(defined_builds=len(values),median_of_build_means=median(values) if values else None)
            if method=='random':
                entry['apfdc_seed_medians']={str(s):median(v) if (v:=[r['apfdc_midpoint'] for r in subset if r['seed']==s and r.get('apfdc_midpoint') is not None]) else None for s in SEEDS}
            result.append(entry)
    return result


def main():
    manifest,selection=validate_manifest()
    archive=ROOT/'references/artifacts/dante/ML_TCSP.zip'
    assert verify_archive(archive)==manifest['archive']
    raw,_=load_builds(archive,'karaf',len(selection),ROOT/'reports/stage1/karaf-source-mapping.csv')
    builds=tuple(conservative(b) for b in raw)
    actual=[dict(key=asdict(b.inputs.key),cutoff=b.inputs.cutoff,split=split_for(b.inputs.cutoff),commit=b.inputs.commit,branch=b.inputs.branch) for b in builds]
    assert digest(actual)==manifest['selection_sha256']
    if (OUT/'run-complete.json').exists():
        raise ValueError('Completed pilot already exists; run verifier instead of overwriting evidence')
    rows=[];ledger=[]
    with ExitStack() as stack:
        streams={name:stack.enter_context(gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf-8'))
                 for name in ('inputs','ground-truth','features','rankings')}
        def emit(name,data):
            streams[name].write(json.dumps(data,ensure_ascii=False,allow_nan=False)+'\n')
        for i,(build,snapshot,seconds) in enumerate(snapshots(builds,HistoryConfig(**manifest['config'])),1):
            key=asdict(build.inputs.key);split=split_for(build.inputs.cutoff)
            emit('inputs',asdict(build.inputs))
            emit('ground-truth',dict(key=key,result=build.result,available_at=build.available_at,outcomes=[asdict(o) for o in build.outcomes]))
            compact=compact_snapshot(snapshot);sha=digest(compact)
            emit('features',dict(snapshot=compact,sha256=sha))
            reason=score_reason(build,split)
            ledger.append(dict(key=key,split=split,result=build.result,tests=len(build.outcomes),
                failures=sum(o.failed is True for o in build.outcomes),reason=reason,
                eligible_history_builds=len(snapshot.eligible_builds),
                cold_tests=sum(f.observations==0 for f in snapshot.features),
                low_history_tests=sum(1<=f.observations<5 for f in snapshot.features),
                feature_seconds=seconds))
            # Construct all rankings before current-result eligibility/evaluation affects outputs.
            orders=[]
            for method,seed in methods():
                start=time.perf_counter();order=rank(snapshot,method,seed)
                elapsed=time.perf_counter()-start
                assert len(order)==len(build.outcomes) and set(order)=={o.test_id for o in build.outcomes}
                orders.append((method,seed,order,elapsed))
            for method,seed,order,elapsed in orders:
                metric=evaluate(order,build.outcomes) if reason is None else None
                emit('rankings',dict(key=key,split=split,method=method,seed=seed,order=order,
                    snapshot_sha256=sha,ranking_seconds=elapsed,feature_seconds=seconds,metrics=metric,reason=reason))
                rows.append(flatten(key,split,method,seed,metric,reason))
            if i%50==0 or i==len(builds):
                print(f'Replayed {i}/{len(builds)} builds',flush=True)
    fields=['project','pr','build','stage','split','method','seed','tests','observed_failures','apfd',
            'apfdc_midpoint','ttff_seconds','ttff_censored','censor_time_seconds','recall_10','recall_25','recall_50',
            'invalid_durations','zero_durations','reason']
    with (OUT/'metrics.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(rows)
    write_json(OUT/'ledger.json',ledger)
    write_json(OUT/'summary.json',summarize(rows))
    artifacts=['inputs.jsonl.gz','ground-truth.jsonl.gz','features.jsonl.gz','rankings.jsonl.gz','metrics.csv','ledger.json','summary.json']
    write_json(OUT/'run-complete.json',dict(builds=len(builds),rankings=len(rows),
        manifest_sha256=file_sha256(OUT/'manifest.json'),artifacts_sha256={p:file_sha256(OUT/p) for p in artifacts}))
    print(json.dumps(dict(builds=len(builds),rankings=len(rows),output=str(OUT)),indent=2))


if __name__=='__main__':
    main()
