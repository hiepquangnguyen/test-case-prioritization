"""FAST-pw-LRTS adaptation of icse18-FAST/FAST (FALCON artifact fast.py/lsh.py).

This is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. Distributed WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
https://www.gnu.org/licenses/gpl-3.0.html and the pinned upstream artifact.

Adaptations: full preprocessed class source, FQN input, local per-build RNG,
sorted candidate random choice, explicit source-unavailable tail. k=5,r=1,b=10.
"""
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
import os
import random
import xxhash
from functools import lru_cache


@lru_cache(maxsize=4096)
def signature_for(text):
    shingles = {hash(text[i:i + 5]) for i in range(len(text) - 4)}
    return tuple(min((xxhash.xxh64(str(s).encode('utf-8'), seed=37 * (2 * j + 1)).digest()
                      for s in shingles), default=b'\xff' * 8) for j in range(10))


def prioritize(key, sources, seed=0):
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('Launch Python with PYTHONHASHSEED=0 for FAST')
    material = json.dumps([seed, asdict(key)], sort_keys=True).encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(material).digest(), 'big'))
    ids = sorted(tid for tid, source in sources.items() if source and source.strip())
    tail = tuple(sorted(set(sources) - set(ids)))
    if not ids:
        return tail
    rng.shuffle(ids)
    signatures = {}
    maximum = b'\xff' * 8
    for tid in ids:
        signatures[tid] = list(signature_for(sources[tid]))

    def buckets():
        result = [defaultdict(set) for _ in range(10)]
        for tid, signature in signatures.items():
            for j in range(10):
                result[j][hash(str(signature[j:j + 1]))].add(tid)
        return result

    bucket = buckets()
    size = int(len(ids) * .5) + 1
    selected = [maximum] * 10
    order = []
    chosen = rng.choice(list(signatures))
    while signatures:
        if order:
            if len(signatures) < size:
                bucket = buckets()
                size = int(size * .5) + 1
            def candidates():
                similar = set().union(*(bucket[j].get(hash(str(selected[j:j + 1])), set()) for j in range(10)))
                return set(signatures) - similar
            choices = candidates()
            if not choices:
                selected = [maximum] * 10
                choices = candidates() or set(signatures)
            chosen = rng.choice(sorted(choices))
            distance = -1
            for tid, signature in signatures.items():
                if tid in choices:
                    d = 1 - sum(a == b for a, b in zip(selected, signature)) / 10
                    if d > distance:
                        chosen, distance = tid, d
        selected = [min(a, b) for a, b in zip(selected, signatures.pop(chosen))]
        order.append(chosen)
    return tuple(order) + tail
