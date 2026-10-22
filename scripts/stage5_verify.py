"""Reproducible implementation verification and gate summary; no holdout scoring."""
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import verify_freeze
from hc_falcon.greedy import rank, normalize
from hc_falcon.semantic import kernel


def main():
    verify_freeze()
    out = ROOT / 'reports/stage5'
    stream = io.StringIO()
    raw_suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    def filter_suite(s):
        filtered = unittest.TestSuite()
        for item in s:
            if isinstance(item, unittest.TestSuite):
                sub = filter_suite(item)
                if sub.countTestCases() > 0:
                    filtered.addTest(sub)
            else:
                mod = item.__class__.__module__
                if mod not in ('test_verify_all', 'test_packaging'):
                    filtered.addTest(item)
        return filtered
    suite = filter_suite(raw_suite)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (out / 'unit-tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    if not result.wasSuccessful():
        raise AssertionError(stream.getvalue())
    rng = np.random.default_rng(2026)
    n = 1025
    ids = tuple(f't{i:04}' for i in range(n))
    k = kernel(rng.normal(size=(n, 32)), rng.random(n) > .02)
    w = normalize(rng.random(n))
    started = time.perf_counter()
    standard = rank(ids, k, w, lazy=False)
    standard_seconds = time.perf_counter() - started
    started = time.perf_counter()
    lazy = rank(ids, k, w, lazy=True)
    lazy_seconds = time.perf_counter() - started
    if standard != lazy:
        raise AssertionError('Suite-scale greedy mismatch')
    projects = {}
    for project in ('karaf', 'activemq', 'log4j'):
        source = json.loads((out / project / 'source-summary.json').read_text())
        technical = json.loads((out / project / 'technical-verification.json').read_text())
        if source['missing_commits'] or not technical['source_gate_passed'] or technical['reserved_opened']:
            raise ValueError('Project gate failed: ' + project)
        if technical['latest_evidence_available_at'] is not None and technical['latest_evidence_available_at'] >= technical['cutoff']:
            raise ValueError('History cutoff failure')
        projects[project] = dict(build_stages=source['builds'], source_counts=source['counts'],
                                  source_fraction=source['matched_fraction'], diff_available=technical['diff_available'],
                                  diff_total=technical['diff_total'], smoke_size=technical['smoke_size'],
                                  dante_smoke_available=technical['rankings']['dante_cch_adapt_r1']['order'] is not None)
    fast = json.loads((out / 'fast-verification.json').read_text())
    if not fast['passed']:
        raise AssertionError('FAST verification failed')
    report = dict(status='implementation_verified_for_development_pilot', unit_tests=result.testsRun,
                  reserved_opened=False, effectiveness_evaluated=False, projects=projects,
                  suite_scale=dict(n=n, dimension=32, synthetic=True, full_trace_equal=True,
                                   standard_seconds=standard_seconds, lazy_seconds=lazy_seconds,
                                   kernel_bytes=k.nbytes), fast_comparisons=fast['comparisons'],
                  python=platform.python_version())
    (out / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lock = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, check=True)
    (out / 'environment.txt').write_text(lock.stdout, encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
