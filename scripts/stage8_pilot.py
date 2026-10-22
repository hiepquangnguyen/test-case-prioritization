"""Frozen-parameter revision replay from full stage-6 source/kernel evidence."""
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hc_falcon.restricted import rank
from hc_falcon.semantic import kernel
from scripts.stage5_sources import selected
from scripts.stage6_pilot import write_json, verify_implementation, failure_groups, peak_rss
from scripts.stage6_summary import independent_check
from scripts.pilot_support import conservative
from tcp.lrts import load_builds, file_sha256
from tcp.history import RollingHistory
from tcp.metrics import evaluate


def main():
    verify_implementation()
    for name in ('reports/stage6/final-evidence-freeze.json','reports/stage7/evidence-freeze.json'):
        for path, expected in json.loads((ROOT/name).read_text())['files_sha256'].items():
            assert file_sha256(ROOT/path) == expected, path
    manifest = dict(reserved_opened=False, source_freeze=file_sha256(ROOT/'reports/stage6/final-evidence-freeze.json'),
        files_sha256={p:file_sha256(ROOT/p) for p in ('hc_falcon/restricted.py','scripts/stage8_pilot.py',
            'configs/restricted-semantic-v1.json','tests/test_stage8.py')},
        runtime_scope='cached vector reconstruction + history + kernel + ranking; excludes source extraction and encoding; not a new full-pipeline engineering gate')
    out = ROOT/'reports/stage8'
    if (out/'manifest.json').exists():
        assert json.loads((out/'manifest.json').read_text()) == manifest
    write_json(out/'manifest.json',manifest)
    vectors_cache = {}
    for project in ('karaf','activemq','log4j'):
        old = ROOT/'reports/stage6'/project
        ledger = json.loads((old/'ledger.json').read_text())
        builds, _ = load_builds(ROOT/'references/artifacts/dante/ML_TCSP.zip',project,len(selected(project)))
        builds = tuple(map(conservative,builds))
        assert [asdict(b.inputs.key) for b in builds] == [r['key'] for r in ledger]
        mapping = {}
        with gzip.open(ROOT/'reports/stage5'/project/'source-mapping.jsonl.gz','rt',encoding='utf-8') as stream:
            for item in map(json.loads,stream):
                if item['status'] == 'matched':
                    mapping.setdefault(json.dumps(item['key'],sort_keys=True),set()).add(item['source_sha256'])
        history = RollingHistory()
        seen = set()
        scored = [r for r in ledger if r['checkpoint']]
        endpoints = (scored[0]['key'],scored[-1]['key'])
        for index,(build,row) in enumerate(zip(builds,ledger)):
            hashes = mapping.get(json.dumps(row['key'],sort_keys=True),set())
            unseen = hashes-seen
            if row['checkpoint']:
                path = out/project/'builds'/row['checkpoint']
                if path.exists():
                    with gzip.open(path,'rt',encoding='utf-8') as stream:
                        assert json.load(stream)['manifest'] == manifest
                else:
                    with gzip.open(old/'builds'/row['checkpoint'],'rt',encoding='utf-8') as stream:
                        saved = json.load(stream)
                    started = time.perf_counter()
                    snapshot = history.snapshot(build.inputs)
                    history_seconds = time.perf_counter()-started
                    ids = tuple(saved['inventory'])
                    assert ids == tuple(t.test_id for t in build.inputs.tests)
                    old_records = {r['method']:r for r in saved['rankings'] if r['seed']==0}
                    baseline, _ = rank(snapshot,ids,None,history_only=True)
                    assert baseline == tuple(old_records['history_cost']['order'])
                    assert [asdict(k) for k in snapshot.eligible_builds] == saved['history']['eligible']
                    started = time.perf_counter()
                    vectors,valid = [],[]
                    for source in saved['source']:
                        cache_key = source['cache_key']
                        if cache_key not in vectors_cache:
                            with np.load(ROOT/'work/cache/stage6/vectors'/(cache_key+'.npz'),allow_pickle=False) as cached:
                                vectors_cache[cache_key] = cached['vector'].copy()
                        vector = vectors_cache[cache_key]
                        assert hashlib.sha256(vector.tobytes()).hexdigest() == source['vector_sha256']
                        vectors.append(vector)
                        valid.append(source['valid'])
                    k = kernel(vectors,valid)
                    kernel_prep_seconds = time.perf_counter()-started
                    started = time.perf_counter()
                    order,trace = rank(snapshot,ids,k)
                    ranking_seconds = time.perf_counter()-started
                    mutation_count = None
                    if row['key'] in endpoints:
                        changed = RollingHistory()
                        mutation_count = 0
                        for other in builds:
                            if other.inputs.key not in snapshot.eligible_builds:
                                other = replace(other,outcomes=tuple(replace(o,failed=not o.failed if o.failed is not None else None,duration=987654.) for o in other.outcomes))
                                mutation_count += 1
                            changed.observe(other)
                        changed_snapshot = changed.snapshot(build.inputs)
                        assert changed_snapshot == snapshot
                        assert rank(changed_snapshot,ids,k)[0] == order
                    policy_order = baseline if unseen else order
                    metrics = evaluate(order,build.outcomes)
                    policy_metrics = evaluate(policy_order,build.outcomes)
                    outcomes = [asdict(o) for o in build.outcomes]
                    independent_check(dict(order=order,metrics=metrics),outcomes)
                    independent_check(dict(order=policy_order,metrics=policy_metrics),outcomes)
                    evidence = dict(manifest=manifest,key=row['key'],order=order,metrics=metrics,trace=trace,
                        comparators={m:old_records[m]['metrics'] for m in ('history_cost','hc_falcon_normalized_v1','fl_only')},
                        history_groups=failure_groups(order,build.outcomes,snapshot),
                        cache_policy=dict(method='cache_only_restricted_v1_simulated',fallback=bool(unseen),
                            missing_hashes=len(unseen),order=policy_order,metrics=policy_metrics),
                        history_only_exact_match=True,ineligible_mutation_count=mutation_count,
                        runtime=dict(history_seconds=history_seconds,kernel_prep_seconds=kernel_prep_seconds,
                            ranking_seconds=ranking_seconds,peak_rss=peak_rss()),
                        input_features=[dict(test_id=f.test_id,q=f.history_cost_score,cost=f.duration_estimate,N=f.observations,
                                             cost_origin=f.duration_origin) for f in snapshot.features])
                    path.parent.mkdir(parents=True,exist_ok=True)
                    tmp = path.with_suffix('.tmp')
                    with gzip.open(tmp,'wt',encoding='utf-8') as stream:
                        json.dump(evidence,stream,allow_nan=False)
                    for attempt in range(10):
                        try:
                            tmp.replace(path)
                            break
                        except PermissionError:
                            if attempt == 9:
                                path.write_bytes(tmp.read_bytes())
                                try:
                                    tmp.unlink(missing_ok=True)
                                except Exception:
                                    pass
                                break
                            time.sleep(0.05 * (attempt + 1))
                    print(project,index+1,'/',len(builds),'checkpoint',flush=True)
            if build.usable:
                seen.update(hashes)
            history.observe(build)
        write_json(out/project/'complete.json',dict(manifest=manifest,stages=len(scored),reserved_opened=False))
    print('All stage8 development replays complete',flush=True)


if __name__ == '__main__':
    main()
