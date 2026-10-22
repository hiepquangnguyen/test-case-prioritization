import unittest
from types import SimpleNamespace
import numpy as np
from hc_falcon.restricted import rank


def snapshot(q, costs):
    return SimpleNamespace(features=tuple(SimpleNamespace(test_id=t, history_cost_score=v,
        duration_estimate=costs[t]) for t,v in q.items()))


class RestrictedTests(unittest.TestCase):
    def test_score_and_duration_exclude_attractive_semantics(self):
        s = snapshot(dict(a=1,b=.94,c=.96,d=.96), dict(a=1,b=1,c=1.26,d=1.25))
        k = np.ones((4,4),dtype=np.float32)
        k[:,0]=0
        order, trace = rank(s, ('a','b','c','d'), k)
        self.assertEqual(order[0], 'd')
        self.assertEqual(trace[0]['candidate_count'], 2)
        self.assertEqual(set(order), set('abcd'))

    def test_zero_q_and_missing_semantics(self):
        s = snapshot(dict(a=0,b=0,c=0), dict(a=1,b=1,c=10))
        k = np.eye(3,dtype=np.float32)
        k[:,0]=0
        order, trace = rank(s, ('a','b','c'), k)
        self.assertEqual(order[0], 'b')
        self.assertTrue(all(t['zero_q'] for t in trace))
        self.assertEqual(rank(s, ('c','b','a'), np.zeros((3,3)))[0], ('a','b','c'))

    def test_raw_q_history_mode_preserves_last_bit(self):
        s = snapshot(dict(a=.34218682837867176,b=.3421868283786718),dict(a=1,b=1))
        self.assertEqual(rank(s, ('a','b'), None, history_only=True)[0], ('b','a'))

    def test_gain_cost_ties_and_input_permutation(self):
        s = snapshot(dict(a=1,b=1), dict(a=1,b=1))
        self.assertEqual(rank(s, ('b','a'),np.ones((2,2)))[0], ('a','b'))
        with self.assertRaises(ValueError):
            rank(s, ('a','a'),np.ones((2,2)))
        with self.assertRaises(ValueError):
            rank(s, ('a','b'),np.full((2,2),np.nan))


if __name__ == '__main__':
    unittest.main()
