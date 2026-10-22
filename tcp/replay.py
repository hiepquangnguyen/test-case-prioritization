"""Chronological full-feedback replay; ranker boundary contains no current labels."""
import hashlib
import json
import time
from dataclasses import asdict
from .baselines import METHODS, rank
from .history import HistoryConfig, RollingHistory
from .metrics import evaluate


def replay(builds, config=HistoryConfig(), methods=METHODS, seed=42):
    if len(methods) != len(set(methods)) or any(m not in METHODS for m in methods):
        raise ValueError('Unknown or duplicate method')
    keys = [b.inputs.key for b in builds]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate build keys')
    by_start = sorted(builds, key=lambda b: (b.inputs.cutoff, b.inputs.key))
    pending = sorted((b for b in builds if b.available_at is not None),
                     key=lambda b: (b.available_at, b.inputs.key))
    next_event = 0
    history = RollingHistory(config)
    snapshots, rows, ledger = [], [], []
    for build in by_start:
        inputs = build.inputs
        while next_event < len(pending) and pending[next_event].available_at < inputs.cutoff:
            history.observe(pending[next_event])
            next_event += 1
        started = time.perf_counter()
        snapshot = history.snapshot(inputs)
        feature_seconds = time.perf_counter() - started
        snapshot_data = asdict(snapshot)
        snapshot_bytes = json.dumps(snapshot_data, sort_keys=True, allow_nan=False).encode()
        snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()
        snapshots.append({'snapshot': snapshot_data, 'sha256': snapshot_hash})
        if build.usable:
            exclusion = None
        else:
            exclusion = 'unusable_build_result:'+build.result
        ledger.append(dict(key=asdict(inputs.key), result=build.result, available_at=build.available_at,
                           tests=len(inputs.tests), observed_failures=sum(o.failed is True for o in build.outcomes),
                           source_unmatched=sum(t.source_status!='matched' for t in inputs.tests),
                           suspected_runner_events=sum(t.category=='suspected_runner_event' for t in inputs.tests),
                           scoring_exclusion=exclusion, eligible_history_builds=len(snapshot.eligible_builds),
                           unknown_history_tests=sum(f.observations==0 for f in snapshot.features),
                           feature_seconds=feature_seconds))
        for method in methods:
            started = time.perf_counter()
            order = rank(snapshot, method, seed)
            ranking_seconds = time.perf_counter() - started
            # Validate every ranking, including diagnostic-only aborted builds.
            if len(order)!=len(inputs.tests) or set(order)!={t.test_id for t in inputs.tests}:
                raise ValueError('Incomplete ranking')
            metrics = evaluate(order, build.outcomes) if exclusion is None else None
            rows.append(dict(key=asdict(inputs.key), method=method, seed=seed, snapshot_sha256=snapshot_hash,
                             order=order, ranking_seconds=ranking_seconds, feature_seconds=feature_seconds,
                             metrics=metrics, scoring_exclusion=exclusion))
    return dict(snapshots=snapshots, rankings=rows, ledger=ledger)
