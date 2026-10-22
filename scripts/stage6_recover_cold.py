"""Remeasure orphaned cold costs after an interrupted warm-up, without altering vectors."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage6_pilot import verify_implementation, write_json
from hc_falcon.semantic import Encoder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, choices=('karaf','activemq','log4j'))
    project = parser.parse_args().project
    verify_implementation()
    with gzip.open(ROOT / 'reports/stage5' / project / 'source-mapping.jsonl.gz','rt',encoding='utf-8') as stream:
        wanted = {r['source_sha256'] for r in map(json.loads,stream) if r['source_sha256']}
    path = ROOT / 'work/cache/stage6' / (project+'-cold-costs.json')
    costs = json.loads(path.read_text()) if path.exists() else {}
    orphaned = {}
    for cached in (ROOT / 'work/cache/stage6/vectors').glob('*.npz'):
        with np.load(cached,allow_pickle=False) as data:
            metadata = json.loads(str(data['metadata']))
        sha = metadata['source_sha256']
        if sha in wanted and sha not in costs:
            orphaned[sha] = cached
    if not orphaned:
        print(project,'no orphaned cold costs',flush=True)
        return
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(0)
    config = json.loads((ROOT / 'configs/hc-falcon-v1.json').read_text())['semantic']
    encoder = Encoder(ROOT / 'work/cache/stage6/cold-recovery' / uuid.uuid4().hex,ROOT / 'work/cache/huggingface/hub',config)
    recovery_report = ROOT / 'reports/stage6' / project / 'cold-recovery.json'
    records = json.loads(recovery_report.read_text())['records'] if recovery_report.exists() else []
    for index,(sha,cached) in enumerate(sorted(orphaned.items())):
        content = (ROOT / 'work/cache/stage5/source' / sha).read_bytes()
        started = time.perf_counter()
        vector, metadata = encoder.encode(content)
        seconds = time.perf_counter()-started
        if metadata['cache_hit']:
            raise ValueError('Recovery cache hit without a saved cost; use a fresh recovery directory')
        with np.load(cached,allow_pickle=False) as data:
            original = data['vector']
        if not np.allclose(vector,original,rtol=1e-5,atol=1e-6):
            raise AssertionError('Recovered embedding differs from original vector')
        costs[sha] = seconds
        write_json(path,costs)
        records.append(dict(source_sha256=sha,seconds=seconds,max_abs_difference=float(np.max(np.abs(vector-original)))))
        write_json(ROOT / 'reports/stage6' / project / 'cold-recovery.json',dict(reason='Warm-up process interrupted by turn boundary before cost ledger was written; remeasure only missing cold costs; original vectors and rankings unchanged', records=records))
        if index % 25 == 0:
            print(project,'recovered cold cost',index+1,'/',len(orphaned),flush=True)


if __name__ == '__main__':
    main()
