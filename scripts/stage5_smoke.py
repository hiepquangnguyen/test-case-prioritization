"""Offline technical smoke on 16 already-audited warm-up classes; no APFD claims."""
from dataclasses import asdict
import csv
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage4_source_audit import git, batch_blobs
from scripts.stage5_sources import verify_freeze
from hc_falcon.semantic import Encoder, kernel
from hc_falcon.preprocess import preprocess
from hc_falcon.methods import SEMANTIC_METHODS, prioritize
from hc_falcon.fast import prioritize as fast
from hc_falcon.dante import prioritize as dante
from tcp.history import RollingHistory
from tcp.domain import BuildKey, RankingInput, TestInput


def main():
    verify_freeze()
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(0)
    cfg = json.loads((ROOT / 'configs/hc-falcon-v1.json').read_text())
    encoder = Encoder(ROOT / 'work/cache/stage5/vectors', ROOT / 'work/cache/huggingface/hub', cfg['semantic'])
    out = ROOT / 'reports/stage5'
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for project in ('activemq', 'log4j'):
        with (ROOT / 'reports/stage4' / project / 'source-mapping.csv').open(newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        first = rows[0]
        rows = sorted((r for r in rows if (r['pr'], r['build'], r['stage']) == (first['pr'], first['build'], first['stage'])), key=lambda r: r['test_id'])[:16]
        repo = ROOT / 'work/sources' / (project + '.git')
        vectors, masks, metadata, sources = [], [], [], {}
        started = time.perf_counter()
        for row in rows:
            content = b''
            if row['status'] == 'matched_declared_revision':
                content = git(repo, 'show', row['commit'] + ':' + row['source_paths']).stdout
            vector, meta = encoder.encode(content)
            cached, cached_meta = encoder.encode(content)
            if not np.array_equal(vector, cached) or not cached_meta['cache_hit']:
                raise AssertionError('Cache round trip failed')
            vectors.append(vector)
            masks.append(meta['valid'])
            metadata.append(dict(test_id=row['test_id'], **meta))
            sources[row['test_id']] = preprocess(content) if meta['valid'] else None
        ids = tuple(row['test_id'] for row in rows)
        k = kernel(vectors, masks)
        key = BuildKey(project, first['pr'], first['build'], first['stage'])
        inputs = RankingInput(key, 'smoke_only', 0, first['commit'], tuple(TestInput(t) for t in ids))
        snapshot = RollingHistory().snapshot(inputs)
        rankings = {}
        for method in SEMANTIC_METHODS:
            standard = prioritize(snapshot, ids, k, method, lazy=False)
            lazy = prioritize(snapshot, ids, k, method, lazy=True)
            if standard != lazy:
                raise AssertionError('Real kernel greedy mismatch: ' + method)
            rankings[method] = lazy[0]
        rankings['fast_pw_lrts'] = {seed: fast(key, sources, seed) for seed in range(20)}
        rankings['dante_no_java_changes_fixture'] = dante(inputs, snapshot, (), sources, []).order
        results.append(dict(project=project, key=asdict(key), size=len(ids),
                            scope='First 16 FQN records of first previously audited warmup build; cold-history technical smoke',
                            seconds=time.perf_counter() - started, vectors=metadata, rankings=rankings))
        print(project, 'technical smoke complete', flush=True)
    (out / 'semantic-smoke.json').write_text(json.dumps(dict(reserved_opened=False, effectiveness_evaluated=False,
        encoder=encoder.identity, runs=results), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
