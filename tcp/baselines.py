"""Rankers accept a snapshot, never a CompletedBuild or current ground truth."""
import hashlib
import json
import random
from dataclasses import asdict
from .history import Snapshot

METHODS = ('random', 'shortest_test_first', 'most_fail', 'recent_fail', 'history_only', 'history_cost')


def rank(snapshot: Snapshot, method: str, seed: int = 42) -> tuple[str, ...]:
    features = sorted(snapshot.features, key=lambda f: f.test_id)
    if method == 'random':
        # Independent of iteration order, other methods and Python hash randomization.
        material = json.dumps([seed, asdict(snapshot.key)], sort_keys=True).encode()
        random.Random(int.from_bytes(hashlib.sha256(material).digest(), 'big')).shuffle(features)
    elif method == 'shortest_test_first':
        features.sort(key=lambda f: (f.duration_estimate, f.test_id))
    elif method == 'most_fail':
        features.sort(key=lambda f: (-f.failures, f.test_id))
    elif method == 'recent_fail':
        features.sort(key=lambda f: (f.last_failure_available_at is None,
                                     -(f.last_failure_available_at or 0), f.test_id))
    elif method == 'history_only':
        features.sort(key=lambda f: (-f.history_score, f.test_id))
    elif method == 'history_cost':
        features.sort(key=lambda f: (-f.history_cost_score, f.test_id))
    else:
        raise ValueError(f'Unknown method: {method}')
    return tuple(f.test_id for f in features)
