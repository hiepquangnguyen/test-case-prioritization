import unittest
from scripts.stage7_diagnosis import contributions
from tcp.domain import Outcome
from tcp.metrics import evaluate


class DiagnosisTests(unittest.TestCase):
    def test_failure_timing_decomposes_apfdc_with_unequal_costs(self):
        outcomes = (Outcome('a', True, 2), Outcome('b', False, 20), Outcome('c', True, 0))
        data = {o.test_id:dict(failed=o.failed, duration=o.duration) for o in outcomes}
        first, second = ('b','a','c'), ('c','a','b')
        values = contributions(first, second, data)
        expected = evaluate(first, outcomes)['apfdc_midpoint'] - evaluate(second, outcomes)['apfdc_midpoint']
        self.assertAlmostEqual(sum(v['apfdc_delta'] for v in values), expected)
        self.assertTrue(all(v['completion_shift_seconds'] > 0 for v in values))
        self.assertEqual(contributions(first, second, {k:dict(failed=False,duration=v['duration']) for k,v in data.items()}), [])


if __name__ == '__main__':
    unittest.main()
