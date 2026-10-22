"""Frozen pilot policies; keeps the stage-2 implementation and evidence intact."""
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/stage3/karaf'
SEEDS = tuple(range(20))
DEVELOPMENT_START = datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp()
HOLDOUT_START = datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp()


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def split_for(cutoff):
    if cutoff < DEVELOPMENT_START:
        return 'warmup'
    return 'development' if cutoff < HOLDOUT_START else 'holdout'


def conservative(build):
    # Collector floors start_ms/1000 AND duration_ms/1000. Their sum can be
    # almost two seconds early. Strict cutoff + 2s is conservative under this
    # declared start/duration model; this does not establish publication time.
    return replace(build, available_at=build.available_at+2 if build.available_at is not None else None)


def compact_snapshot(snapshot):
    # Evidence per test can be reconstructed from the eligible build list and
    # saved ground truth. Avoid repeating O(builds^2 * tests) BuildKey objects.
    features = []
    for feature in snapshot.features:
        data = {k: v for k, v in vars(feature).items() if k != 'evidence_builds'}
        data['evidence_builds_sha256'] = digest([asdict(k) for k in feature.evidence_builds])
        features.append(data)
    return dict(key=asdict(snapshot.key), cutoff=snapshot.cutoff, context=snapshot.context,
                eligible_builds=[asdict(k) for k in snapshot.eligible_builds],
                latest_evidence_available_at=snapshot.latest_evidence_available_at,
                duration_reference=snapshot.duration_reference, features=features)


def score_reason(build, split):
    if split == 'warmup':
        return 'warmup_not_scored'
    if not build.usable:
        return 'unusable_build_result:'+build.result
    return None
