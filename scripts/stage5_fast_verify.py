"""Compare adaptation to pinned FAST with only declared runtime/determinism fixes."""
from dataclasses import asdict
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hc_falcon.fast import prioritize
from tcp.domain import BuildKey
sys.path.insert(0, str(ROOT / 'work/artifacts/falcon/py'))
import fast as upstream
import lsh
import xxhash


class DeterministicRandom(random.Random):
    def choice(self, seq):
        return super().choice(sorted(seq) if isinstance(seq, tuple) else seq)


def main():
    # xxhash installed in this environment requires bytes, as opposed to the old wrapper.
    lsh.hashFamily = lambda i: lambda value: xxhash.xxh64(value.encode(), seed=37 * (2 * i + 1)).digest()
    key = BuildKey('fixture', 'PR-1', '1', 'single')
    fixtures = [dict(a='class Alpha {}', b='class Beta {}', c='class Alpha {}'),
                {f't{i:03}': 'class Test { ' + 'abcde ' * (i % 5) + str(i) + ' }' for i in range(30)},
                dict(a='x', b='y', c='z')]
    checked = 0
    for sources in fixtures:
        ids = sorted(sources)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'suite.txt'
            path.write_text(''.join(sources[tid] + '\n' for tid in ids), encoding='utf-8')
            for seed in range(20):
                material = json.dumps([seed, asdict(key)], sort_keys=True).encode()
                upstream.random = DeterministicRandom(int.from_bytes(hashlib.sha256(material).digest(), 'big'))
                _, _, order = upstream.fast_pw(str(path), r=1, b=10, bbox=True, k=5, memory=True)
                expected = tuple(ids[i - 1] for i in order)
                actual = prioritize(key, sources, seed)
                if expected != actual:
                    raise AssertionError((seed, expected, actual))
                with_missing = prioritize(key, dict(sources, missing=None), seed)
                if with_missing != actual + ('missing',):
                    raise AssertionError('Missing-source tail mismatch')
                checked += 1
    report = dict(comparisons=checked, passed=True,
                  upstream='work/artifacts/falcon/py/fast.py + lsh.py',
                  fixes=['UTF-8 encode xxhash input', 'per-build RNG', 'sort candidate tuple before random.choice'])
    (ROOT / 'reports/stage5/fast-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
