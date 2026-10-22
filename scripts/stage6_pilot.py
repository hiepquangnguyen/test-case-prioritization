"""Full-inventory chronological development replay of the frozen stage-5 methods."""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import selected, verify_freeze
from scripts.pilot_support import conservative
from tcp.lrts import load_builds, file_sha256
from tcp.history import RollingHistory
from tcp.baselines import METHODS
from tcp.metrics import evaluate
from hc_falcon.semantic import Encoder, kernel
from hc_falcon.preprocess import preprocess
from hc_falcon.methods import SEMANTIC_METHODS, prioritize
from hc_falcon.fast import prioritize as fast, signature_for
from hc_falcon.dante import prioritize as dante
from hc_falcon.diffs import declared_diff


def identity(key):
    return tuple(sorted(asdict(key).items()))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    for attempt in range(10):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                try:
                    path.write_text(tmp.read_text(encoding='utf-8'), encoding='utf-8')
                    tmp.unlink(missing_ok=True)
                except Exception:
                    tmp.replace(path)
                return
            time.sleep(0.05 * (attempt + 1))


def peak_rss():
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.PeakWorkingSetSize


def verify_implementation():
    verify_freeze()
    path = ROOT / 'reports/stage5/implementation-freeze.json'
    for name, expected in json.loads(path.read_text())['files_sha256'].items():
        if file_sha256(ROOT / name) != expected:
            raise ValueError('Stage-5 freeze mismatch: ' + name)
    return file_sha256(path)


def failure_groups(order, outcomes, snapshot):
    by_id = {o.test_id: o for o in outcomes}
    features = {f.test_id: f for f in snapshot.features}
    total = sum(o.duration for o in outcomes)
    result = {name: dict(tests=0, failures=0, failure_positions=[], failure_completion_seconds=[], recall10=None)
              for name in ('N0', 'N1_4', 'N5plus')}
    found = Counter()
    elapsed = 0
    for pos, tid in enumerate(order, 1):
        n = features[tid].observations
        name = 'N0' if n == 0 else ('N1_4' if n < 5 else 'N5plus')
        item = result[name]
        item['tests'] += 1
        elapsed += by_id[tid].duration
        if by_id[tid].failed:
            item['failures'] += 1
            item['failure_positions'].append(pos)
            item['failure_completion_seconds'].append(elapsed)
            found[name] += elapsed <= .1 * total or np.isclose(elapsed, .1 * total, rtol=1e-12, atol=0)
    for name, item in result.items():
        if item['failures'] and total > 0:
            item['recall10'] = found[name] / item['failures']
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, choices=('karaf', 'activemq', 'log4j'))
    args = parser.parse_args()
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise ValueError('Launch with PYTHONHASHSEED=0')
    frozen = verify_implementation()
    project = args.project
    out = ROOT / 'reports/stage6' / project
    out.mkdir(parents=True, exist_ok=True)
    selection = selected(project)
    split = {tuple(sorted(r['key'].items())): r['split'] for r in selection}
    builds, metadata = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selection))
    builds = tuple(map(conservative, builds))
    if set(split) != {identity(b.inputs.key) for b in builds}:
        raise ValueError('Selection mismatch')
    declared = {tuple(sorted(r['key'].items())): r['commit'] for r in selection}
    if any(b.inputs.commit != declared[identity(b.inputs.key)] for b in builds):
        raise ValueError('Frozen revision mismatch')
    source_rows = {}
    with gzip.open(ROOT / 'reports/stage5' / project / 'source-mapping.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            key = tuple(sorted(row['key'].items()))
            if key not in split:
                raise ValueError('Source outside allowed cohort')
            source_rows.setdefault(key, {})[row['test_id']] = row
    config = json.loads((ROOT / 'configs/hc-falcon-v1.json').read_text())
    manifest = dict(project=project, stage5_sha256=frozen, runner_sha256=file_sha256(Path(__file__)),
                    reserved_opened=False, scope='all_frozen_warmup_and_development; score_development_only',
                    alpha=.5, alpha_sensitivity=config['alpha_sensitivity'], seeds=list(range(20)))
    manifest_path = out / 'manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Runner changed; use a new run version instead of mixing checkpoints')
    write_json(manifest_path, manifest)
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(0)
    started = time.perf_counter()
    encoder = Encoder(ROOT / 'work/cache/stage6/vectors', ROOT / 'work/cache/huggingface/hub', config['semantic'])
    model_load = time.perf_counter() - started
    source_cache = ROOT / 'work/cache/stage5/source'
    cold_path = ROOT / 'work/cache/stage6' / (project + '-cold-costs.json')
    cold_costs = json.loads(cold_path.read_text()) if cold_path.exists() else {}
    history = RollingHistory()
    completed = []
    ledger = []
    for index, (build, meta_row) in enumerate(zip(builds, metadata)):
        inputs = build.inputs
        part = split[identity(inputs.key)]
        tag = hashlib.sha256(json.dumps(asdict(inputs.key), sort_keys=True).encode()).hexdigest()
        checkpoint = out / 'builds' / (tag + '.json.gz')
        annotations = source_rows[identity(inputs.key)]
        ids = tuple(t.test_id for t in inputs.tests)
        if set(annotations) != set(ids):
            raise ValueError('Incomplete source inventory')
        ledger_row = dict(key=asdict(inputs.key), split=part, cutoff=inputs.cutoff,
                          status=build.result, usable=build.usable, tests=len(ids), checkpoint=checkpoint.name if part == 'development' and build.usable else None)
        ledger.append(ledger_row)
        if checkpoint.exists():
            with gzip.open(checkpoint, 'rt', encoding='utf-8') as f:
                saved = json.load(f)
            if saved['key'] != asdict(inputs.key) or saved['manifest'] != manifest or saved['inventory'] != ids_to_list(ids):
                raise ValueError('Checkpoint mismatch')
            history.observe(build)
            completed.append(build)
            continue
        if not build.usable:
            history.observe(build)
            completed.append(build)
            continue
        began = time.perf_counter()
        prepared = {}
        source_seconds = 0.0
        embedding_seconds = 0.0
        misses = 0
        for number, tid in enumerate(ids):
            row = annotations[tid]
            source_hash = row['source_sha256'] if row['status'] == 'matched' else None
            if source_hash in prepared:
                continue
            stamp = time.perf_counter()
            content = (source_cache / source_hash).read_bytes() if source_hash else b''
            if source_hash and hashlib.sha256(content).hexdigest() != source_hash:
                raise ValueError('Source cache hash mismatch')
            try:
                text = preprocess(content)
            except (ValueError, UnicodeError):
                text = ''
            source_seconds += time.perf_counter() - stamp
            stamp = time.perf_counter()
            vector, info = encoder.encode(content)
            seconds = time.perf_counter() - stamp
            embedding_seconds += seconds
            misses += not info['cache_hit']
            if not info['cache_hit'] and source_hash:
                cold_costs[source_hash] = seconds
            prepared[source_hash] = (vector, info, text)
            if number % 100 == 0:
                print(project, index + 1, '/', len(builds), part, 'source', number, '/', len(ids), flush=True)
        write_json(cold_path, cold_costs)
        vectors, valid, sources, details = [], [], {}, []
        for tid in ids:
            row = annotations[tid]
            source_hash = row['source_sha256'] if row['status'] == 'matched' else None
            vector, info, text = prepared[source_hash]
            vectors.append(vector)
            valid.append(info['valid'])
            sources[tid] = text if info['valid'] else None
            details.append(dict(test_id=tid, mapping_status=row['status'], nested=row['nested_outer_file'], **info))
        stamp = time.perf_counter()
        for source in set(sources.values()):
            if source:
                signature_for(source)
        fast_signature_seconds = time.perf_counter() - stamp
        if part == 'warmup':
            write_json(out / 'warmup-progress.json', dict(build_index=index + 1, completed_key=asdict(inputs.key), peak_rss=peak_rss()))
            history.observe(build)
            completed.append(build)
            continue
        stamp = time.perf_counter()
        k = kernel(vectors, valid)
        kernel_seconds = time.perf_counter() - stamp
        stamp = time.perf_counter()
        snapshot = history.snapshot(inputs)
        history_seconds = time.perf_counter() - stamp
        shared_prep = source_seconds + embedding_seconds + kernel_seconds + history_seconds
        records = []

        def emit(method, seed, order, seconds, prep, trace=()):
            metrics = evaluate(tuple(order), build.outcomes)
            record = dict(method=method, seed=seed, order=order, metrics=metrics,
                          ranking_seconds=seconds, prep_seconds=prep,
                          ttff_end_to_end_simulated=prep + seconds + metrics['ttff_seconds'] if metrics['ttff_seconds'] is not None else None)
            if method == 'hc_falcon_normalized_v1':
                record['trace'] = [asdict(s) for s in trace]
                record['history_groups'] = failure_groups(order, build.outcomes, snapshot)
            records.append(record)

        for method in (*METHODS, *SEMANTIC_METHODS):
            for seed in range(20) if method == 'random' else (0,):
                stamp = time.perf_counter()
                order, trace = prioritize(snapshot, ids, k, method, seed=seed)
                seconds = time.perf_counter() - stamp
                emit(method, seed, order, seconds, history_seconds if method in METHODS else shared_prep, trace)
        for alpha in config['alpha_sensitivity']:
            if alpha == .5:
                continue
            stamp = time.perf_counter()
            order, _ = prioritize(snapshot, ids, k, 'hc_falcon_normalized_v1', alpha=alpha)
            emit('hc_alpha_' + str(alpha), 0, order, time.perf_counter() - stamp, shared_prep)
        for seed in range(20):
            stamp = time.perf_counter()
            order = fast(inputs.key, sources, seed)
            emit('fast_pw_lrts', seed, order, time.perf_counter() - stamp, source_seconds + fast_signature_seconds)
        stamp = time.perf_counter()
        documents, reason = declared_diff(ROOT / 'work/sources' / (project + '.git'), meta_row.get('trunk_sha'), inputs.commit, ROOT / 'work/cache/stage5/diffs')
        diff_seconds = time.perf_counter() - stamp
        stamp = time.perf_counter()
        dante_result = dante(inputs, snapshot, completed, sources, documents, reason)
        dante_seconds = time.perf_counter() - stamp
        if dante_result.order is not None:
            emit('dante_cch_adapt_r1', 0, dante_result.order, dante_seconds, source_seconds + diff_seconds + history_seconds)
        evidence = dict(key=asdict(inputs.key), cutoff=inputs.cutoff, commit=inputs.commit,
                        manifest=manifest, inventory=ids_to_list(ids), split=part, source=details,
                        history=dict(eligible=[asdict(key) for key in snapshot.eligible_builds], latest=snapshot.latest_evidence_available_at),
                        outcomes=[asdict(o) for o in build.outcomes], rankings=records,
                        dante_unavailable_reason=dante_result.reason, peak_rss=peak_rss(),
                        runtime=dict(model_load_seconds=model_load, source_seconds=source_seconds,
                                     embedding_seconds=embedding_seconds, embedding_cache_misses=misses,
                                     kernel_seconds=kernel_seconds, history_seconds=history_seconds,
                                     fast_signature_seconds=fast_signature_seconds,
                                     cold_embedding_reconstructed_seconds=sum(cold_costs.get(h, 0) for h in prepared if h),
                                     cold_cost_missing_hashes=sum(h not in cold_costs for h in prepared if h),
                                     build_wall_seconds=time.perf_counter() - began))
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        tmp = checkpoint.with_suffix('.tmp')
        with gzip.open(tmp, 'wt', encoding='utf-8') as f:
            json.dump(evidence, f, allow_nan=False)
        tmp.replace(checkpoint)
        write_json(out / 'progress.json', dict(build_index=index + 1, total=len(builds), last_key=asdict(inputs.key), peak_rss=peak_rss()))
        print(project, 'CHECKPOINT', index + 1, '/', len(builds), len(records), 'rankings', flush=True)
        history.observe(build)
        completed.append(build)
    write_json(out / 'ledger.json', ledger)
    write_json(out / 'complete.json', dict(project=project, manifest=manifest, build_stages=len(builds),
        development_scored=sum(r['split'] == 'development' and r['usable'] for r in ledger), peak_rss=peak_rss(), reserved_opened=False))


def ids_to_list(ids):
    return list(ids)


if __name__ == '__main__':
    main()
