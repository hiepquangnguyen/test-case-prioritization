"""Full allowed-cohort source/diff audit plus bounded development integration smoke."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import gzip
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import selected, verify_freeze
from scripts.pilot_support import conservative
from hc_falcon.semantic import Encoder, cached_kernel
from hc_falcon.preprocess import preprocess
from hc_falcon.methods import SEMANTIC_METHODS, prioritize
from hc_falcon.fast import prioritize as fast
from hc_falcon.dante import prioritize as dante
from hc_falcon.diffs import declared_diff
from tcp.history import RollingHistory
from tcp.lrts import load_builds
from tcp.baselines import METHODS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, choices=('karaf', 'activemq', 'log4j'))
    args = parser.parse_args()
    verify_freeze()
    project = args.project
    selection = selected(project)
    out = ROOT / 'reports/stage5' / project
    builds, metadata = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selection))
    if {tuple(sorted(r['key'].items())) for r in selection} != {tuple(sorted(asdict(b.inputs.key).items())) for b in builds}:
        raise ValueError('Selection mismatch')
    builds = tuple(map(conservative, builds))
    first_dev = next(r for r in selection if r['split'] == 'development')
    current = next(b for b in builds if asdict(b.inputs.key) == first_dev['key'])
    repo = ROOT / 'work/sources' / (project + '.git')
    diff_records = []
    current_documents = None
    current_reason = None
    with (out / 'diff-audit.jsonl').open('w', encoding='utf-8') as stream:
        for index, (build, row) in enumerate(zip(builds, metadata)):
            documents, reason = declared_diff(repo, row.get('trunk_sha'), row['build_head_sha'], ROOT / 'work/cache/stage5/diffs')
            record = dict(key=asdict(build.inputs.key), available=documents is not None, reason=reason,
                          documents=len(documents) if documents is not None else None,
                          trunk=row.get('trunk_sha'), head=row['build_head_sha'])
            diff_records.append(record)
            stream.write(json.dumps(record) + '\n')
            if build.inputs.key == current.inputs.key:
                current_documents, current_reason = documents, reason
            if index % 50 == 0:
                print(project, 'diff audit', index + 1, '/', len(builds), flush=True)
    annotations = {}
    counts = Counter()
    with gzip.open(out / 'source-mapping.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            counts[record['status']] += 1
            if record['key'] == asdict(current.inputs.key):
                annotations[record['test_id']] = record
    if set(annotations) != {t.test_id for t in current.inputs.tests}:
        raise ValueError('Incomplete current source mapping')
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(0)
    cfg = json.loads((ROOT / 'configs/hc-falcon-v1.json').read_text())
    encoder = Encoder(ROOT / 'work/cache/stage5/vectors', ROOT / 'work/cache/huggingface/hub', cfg['semantic'])
    inputs = replace(current.inputs, tests=tuple(sorted(current.inputs.tests, key=lambda t: t.test_id)[:16]))
    history = RollingHistory()
    for build in builds:
        history.observe(build)
    snapshot = history.snapshot(inputs)
    vectors, valid, metas, sources = [], [], [], {}
    started = time.perf_counter()
    for test in inputs.tests:
        record = annotations[test.test_id]
        content = (ROOT / 'work/cache/stage5/source' / record['source_sha256']).read_bytes() if record['status'] == 'matched' else b''
        vector, meta = encoder.encode(content)
        vectors.append(vector)
        valid.append(meta['valid'])
        metas.append(dict(test_id=test.test_id, **meta))
        sources[test.test_id] = preprocess(content) if meta['valid'] else None
    ids = tuple(t.test_id for t in inputs.tests)
    k, kernel_key, hit = cached_kernel(ROOT / 'work/cache/stage5/kernels', ids, vectors, valid, encoder.identity)
    rankings = {}
    for method in (*METHODS, *SEMANTIC_METHODS):
        reference = prioritize(snapshot, ids, k, method, lazy=False)
        actual = prioritize(snapshot, ids, k, method, lazy=True)
        if reference != actual or set(actual[0]) != set(ids) or len(actual[0]) != len(ids):
            raise AssertionError('Incorrect ranking: ' + method)
        rankings[method] = dict(order=actual[0], trace=[asdict(s) for s in actual[1]])
    rankings['fast_pw_lrts'] = {seed: fast(inputs.key, sources, seed) for seed in range(20)}
    rankings['dante_cch_adapt_r1'] = asdict(dante(inputs, snapshot, builds, sources, current_documents, current_reason))
    report = dict(project=project, scope='Full warmup/development source and diff audit; first 16 FQN records of first development build for semantic integration only',
                  reserved_opened=False, effectiveness_evaluated=False, full_suite_size=len(current.inputs.tests),
                  smoke_size=len(ids), key=asdict(inputs.key), cutoff=inputs.cutoff,
                  eligible_history_builds=len(snapshot.eligible_builds), latest_evidence_available_at=snapshot.latest_evidence_available_at,
                  source_counts=dict(counts), source_gate_passed=counts['matched'] / sum(counts.values()) >= .9,
                  diff_available=sum(r['available'] for r in diff_records), diff_total=len(diff_records),
                  semantic_seconds=time.perf_counter() - started, encoder=encoder.identity,
                  kernel_key=kernel_key, kernel_cache_hit=hit, vectors=metas, rankings=rankings)
    (out / 'technical-verification.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(project, 'technical integration complete', flush=True)


if __name__ == '__main__':
    main()
