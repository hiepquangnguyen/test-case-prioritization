"""DANTE-CCH-adapt-r1; declared diff absence is explicitly unavailable."""
import re
from collections import deque
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Result:
    order: tuple | None
    reason: str | None
    scores: dict


def history_features(inputs, completed):
    eligible = sorted((b for b in completed if b.usable and b.available_at is not None
                       and b.available_at < inputs.cutoff and b.inputs.context == inputs.context
                       and bool(inputs.branch) and b.inputs.key.physical != inputs.key.physical),
                      key=lambda b: (b.available_at, b.inputs.key))
    slots = deque(maxlen=15)
    events = {n: [] for n in (1, 3, 5)}
    for build in eligible:
        outcomes = {o.test_id: o.failed for o in build.outcomes if o.failed is not None}
        for tid, failed in outcomes.items():
            for n in events:
                if any(row.get(tid) is True for row in list(slots)[-n:]):
                    events[n].append(failed)
        slots.append(outcomes)
    probability = {n: sum(values) / len(values) if len(values) >= 20 else 0 for n, values in events.items()}
    result = {}
    for test in inputs.tests:
        known = [row[test.test_id] for row in slots if test.test_id in row]
        failures = sum(known)
        h = failures / len(known) if known else 0
        h += sum(probability[n] / n for n in events
                 if any(row.get(test.test_id) is True for row in list(slots)[-n:]))
        result[test.test_id] = (h, failures)
    return result


def relevance(sources, documents):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    def tokens(text):
        return ' '.join(token.lower() for token in re.findall(r'[A-Za-z_][A-Za-z_0-9]*', text))
    result = dict.fromkeys(sources, 0.0)
    if not documents:
        return result
    vectorizer = TfidfVectorizer()
    try:
        corpus = vectorizer.fit_transform([tokens(doc) for doc in documents])
    except ValueError as exc:
        if 'empty vocabulary' in str(exc):
            return result
        raise
    ids = [tid for tid, source in sources.items() if source]
    if ids:
        query = vectorizer.transform([tokens(sources[tid]) for tid in ids])
        values = cosine_similarity(query, corpus).max(axis=1)
        result.update(zip(ids, map(float, values)))
    return result


def prioritize(inputs, snapshot, completed, sources, documents, unavailable_reason=None):
    if documents is None:
        return Result(None, unavailable_reason or 'Declared diff unavailable', {})
    ids = {t.test_id for t in inputs.tests}
    if ids != set(sources) or ids != {f.test_id for f in snapshot.features} or snapshot.key != inputs.key or snapshot.cutoff != inputs.cutoff:
        raise ValueError('DANTE input/snapshot inventory mismatch')
    history = history_features(inputs, completed)
    rel = relevance(sources, documents)
    scores = {f.test_id: (history[f.test_id][0] + rel[f.test_id] ** 1.2)
              * max(history[f.test_id][1], .1) / f.duration_estimate for f in snapshot.features}
    if not all(np.isfinite(v) for v in scores.values()):
        raise ValueError('Nonfinite DANTE score')
    return Result(tuple(sorted(ids, key=lambda tid: (-scores[tid], tid))), None, scores)
