import unittest
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from scripts import stage6_summary
from scripts.stage6_summary import paired_physical, independent_check
from tcp.domain import Outcome
from tcp.metrics import evaluate


class Stage6Tests(unittest.TestCase):
    def test_resume_preserves_previous_worker_memory_gate_failure(self):
        key = dict(project='p', pr='1', build='1', stage='single')
        outcomes = (Outcome('a', True, 2), Outcome('b', False, 5))
        rankings = [dict(method=name, order=['a', 'b'],
                         metrics=evaluate(('a', 'b'), outcomes),
                         prep_seconds=0, ranking_seconds=0, history_groups={})
                    for name in (stage6_summary.PRIMARY, 'fl_only', 'history_cost')]
        build = dict(key=key, split='development', manifest=dict(reserved_opened=False),
                     cutoff=2, history=dict(latest=1), peak_rss=9 * 1024**3,
                     source=[dict(test_id=o.test_id, valid=True, nested=False,
                                  truncation_fraction=0) for o in outcomes],
                     outcomes=[dict(test_id=o.test_id, failed=o.failed, duration=o.duration)
                               for o in outcomes], rankings=rankings,
                     runtime=dict(cold_cost_missing_hashes=0, model_load_seconds=0,
                                  source_seconds=0, cold_embedding_reconstructed_seconds=0,
                                  kernel_seconds=0, history_seconds=0, embedding_cache_misses=0))
        with TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'reports/stage6/p'
            (directory / 'builds').mkdir(parents=True)
            (directory / 'complete.json').write_text(json.dumps(dict(peak_rss=1024**3)))
            (directory / 'ledger.json').write_text(json.dumps([
                dict(key=key, split='development', usable=True, checkpoint='one.json.gz')]))
            with gzip.open(directory / 'builds/one.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(build, stream)
            with patch.object(stage6_summary, 'ROOT', Path(tmp)):
                result = stage6_summary.project_summary('p')
        self.assertEqual(result['engineering']['peak_rss'], 9 * 1024**3)
        self.assertFalse(result['engineering']['passed'])

    def test_seed_then_common_stage_physical_pairing(self):
        stages = {
            ('p', 'pr', '1', 'linux'): {'hc': [{'apfd': .9}], 'base': [{'apfd': .1}, {'apfd': .5}]},
            ('p', 'pr', '1', 'win'): {'hc': [{'apfd': .5}], 'base': [{'apfd': .7}, {'apfd': .7}]},
            ('p', 'pr', '2', 'linux'): {'hc': [{'apfd': None}], 'base': [{'apfd': .8}]},
            ('p', 'pr', '3', 'linux'): {'hc': [{'apfd': .9}]},
        }
        result = paired_physical(stages, 'hc', 'base', 'apfd')
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[('p','pr','1')], .2)

    def test_independent_metric_verification(self):
        outcomes = (Outcome('a', True, 2), Outcome('b', False, 5), Outcome('c', True, 1))
        raw = [dict(test_id=o.test_id, failed=o.failed, duration=o.duration) for o in outcomes]
        for order in (('a','b','c'), ('c','a','b'), ('b','c','a')):
            metric = evaluate(order, outcomes)
            independent_check(dict(order=order, metrics=metric), raw)
            metric['apfdc_midpoint'] += .1
            with self.assertRaises(ValueError):
                independent_check(dict(order=order, metrics=metric), raw)


if __name__ == '__main__':
    unittest.main()
