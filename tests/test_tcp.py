import csv
import io
import json
import math
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

from tcp.domain import BuildKey, TestInput as DomainTestInput, RankingInput, Outcome, CompletedBuild
from tcp.history import RollingHistory, HistoryConfig
from tcp.baselines import METHODS, rank
from tcp.metrics import evaluate
from tcp.lrts import load_builds, PREFIX
from tcp.replay import replay


def build(name, start, end, outcomes, *, project='p', stage='s', branch='main', status='SUCCESS', pr='PR-1'):
    labels = tuple(Outcome(*o) for o in outcomes)
    inputs = RankingInput(BuildKey(project, pr, name, stage), branch, start, 'sha',
                          tuple(DomainTestInput(o.test_id) for o in labels))
    return CompletedBuild(inputs, end, status, labels)


class HistoryTests(unittest.TestCase):
    def test_completion_strict_cutoff_and_physical_build(self):
        h = RollingHistory()
        h.observe(build('old', 0, 5, [('a', True, 2)]))
        h.observe(build('overlap', 1, 12, [('a', True, 500)]))
        h.observe(build('tie', 2, 10, [('a', True, 100)]))
        h.observe(build('now', 0, 4, [('a', True, 1000)]))
        current = build('now', 10, 20, [('a', False, 90)])
        s = h.snapshot(current.inputs)
        self.assertEqual([k.build for k in s.eligible_builds], ['old'])
        self.assertEqual(s.features[0].duration_estimate, 2)
        self.assertLess(s.latest_evidence_available_at, s.cutoff)

    def test_context_and_aborted_isolation(self):
        h = RollingHistory()
        for kw in ({'project':'other'}, {'stage':'other'}, {'branch':'other'}, {'status':'ABORTED'}):
            h.observe(build(str(kw), 0, 1, [('a', True, 99)], **kw))
        s = h.snapshot(build('current', 5, 6, [('a', False, 1)]).inputs)
        self.assertEqual(s.features[0].observations, 0)
        self.assertEqual(s.features[0].duration_origin, 'fixed_cold_start')

    def test_unknown_missing_rename_and_zero_are_not_pass(self):
        h = RollingHistory()
        h.observe(build('b1', 0, 1, [('a', True, 0), ('unknown', None, 8)]))
        h.observe(build('b2', 2, 3, [('other', False, 2)]))
        s = h.snapshot(build('b3', 4, 5, [('a', False, 4), ('renamed', False, 4), ('unknown', False, 4)]).inputs)
        f = {x.test_id:x for x in s.features}
        self.assertEqual((f['a'].observations, f['a'].failures), (1,1))
        self.assertEqual(f['renamed'].observations, 0)
        self.assertEqual(f['unknown'].observations, 0)
        self.assertEqual(f['unknown'].duration_estimate, 8)
        self.assertEqual(f['a'].duration_estimate, 5)  # past context median(8,2)

    def test_beta_confidence_and_median(self):
        h = RollingHistory()
        h.observe(build('1', 0, 1, [('a', True, 2)]))
        h.observe(build('2', 2, 3, [('a', False, 6)]))
        s = h.snapshot(build('3', 4, 5, [('a', False, 999)]).inputs)
        f = s.features[0]
        self.assertEqual(f.probability, .5)
        self.assertAlmostEqual(f.confidence, 2/7)
        self.assertEqual(f.duration_estimate, 4)
        self.assertEqual(f.normalized_duration, 1)

    def test_query_past_after_ingesting_future(self):
        h = RollingHistory()
        target = build('q', 10, 20, [('a', True, 999)])
        before = h.snapshot(target.inputs)
        h.observe(build('future', 11, 12, [('a', True, 10000)]))
        self.assertEqual(before, h.snapshot(target.inputs))

    def test_invalid_config_and_duplicate_observation(self):
        with self.assertRaises(ValueError): HistoryConfig(epsilon=0)
        with self.assertRaises(ValueError): HistoryConfig(beta_fail=float('nan'))
        h = RollingHistory()
        b = build('b', 0, 1, [('a', False, 1)])
        h.observe(b)
        with self.assertRaises(ValueError): h.observe(b)


class MetricTests(unittest.TestCase):
    def test_hand_example_and_units(self):
        truth = (Outcome('a',True,2), Outcome('b',False,5), Outcome('c',True,1), Outcome('d',False,4))
        m = evaluate(('a','b','c','d'), truth)
        self.assertAlmostEqual(m['apfd'], .625)
        self.assertAlmostEqual(m['apfdc_midpoint'], 1-8.5/24)
        self.assertEqual(m['ttff_seconds'], 2)
        self.assertEqual(m['recall'], {'0.1':0, '0.25':.5, '0.5':.5})
        for scale in (1000, 0.001):
            other = evaluate(('a','b','c','d'), tuple(replace(o,duration=o.duration*scale) for o in truth))
            self.assertAlmostEqual(other['apfdc_midpoint'], m['apfdc_midpoint'])
            self.assertEqual(other['recall'], m['recall'])
            self.assertAlmostEqual(other['ttff_seconds'], m['ttff_seconds']*scale)

    def test_uniform_cost_matches_apfd_and_single_test(self):
        truth = (Outcome('a',False,2),Outcome('b',True,2),Outcome('c',True,2))
        m = evaluate(('a','b','c'), truth)
        self.assertAlmostEqual(m['apfd'], m['apfdc_midpoint'])
        self.assertEqual(evaluate(('x',),(Outcome('x',True,2),))['apfdc_midpoint'], .5)

    def test_zero_cost_retained_and_budget_completion(self):
        truth = (Outcome('a',True,0),Outcome('b',True,1),Outcome('c',False,3))
        m = evaluate(('a','b','c'), truth)
        self.assertEqual(m['observed_failures'], 2)
        self.assertEqual(m['ttff_seconds'], 0)
        self.assertEqual(m['recall']['0.25'], 1)

    def test_undefined_metrics_are_not_perfect_scores(self):
        self.assertIn('empty_inventory', evaluate((),())['reasons'])
        m = evaluate(('a',), (Outcome('a',False,3),))
        self.assertIsNone(m['apfdc_midpoint'])
        self.assertTrue(m['ttff_censored'])
        self.assertEqual(m['censor_time_seconds'], 3)
        for cost in (None, -1, float('nan')):
            m = evaluate(('a',),(Outcome('a',True,cost),))
            self.assertEqual(m['apfd'], .5)
            self.assertIsNone(m['apfdc_midpoint'])
        self.assertIsNone(evaluate(('a',),(Outcome('a',True,0),))['apfdc_midpoint'])
        self.assertIsNone(evaluate(('a',),(Outcome('a',None,1),))['apfd'])

    def test_invalid_ranking_and_budget_rejected(self):
        truth = (Outcome('a',True,1),Outcome('b',False,1))
        for order in (('a',), ('a','a'), ('a','x'), ('a','b','b')):
            with self.assertRaises(ValueError): evaluate(order, truth)
        with self.assertRaises(ValueError): evaluate(('a','b'),truth,(1.2,))


class ReplayTests(unittest.TestCase):
    def test_current_and_future_labels_costs_do_not_affect_rankings(self):
        cohort = [build('old',0,4,[('a',True,2),('b',False,6)]),
                  build('overlap',5,50,[('a',True,8),('b',True,1)]),
                  build('target',10,20,[('a',False,100),('b',True,1),('new',True,0)]),
                  build('future',30,40,[('a',True,2),('b',False,1)])]
        original = replay(cohort)
        changed = [cohort[0], cohort[1],
                   replace(cohort[2], available_at=99, result='ABORTED', outcomes=tuple(replace(o,failed=not o.failed,duration=99999) for o in cohort[2].outcomes)),
                   replace(cohort[3],outcomes=tuple(replace(o,failed=not o.failed,duration=999999) for o in cohort[3].outcomes))]
        altered = replay(changed)
        self.assertEqual(original['snapshots'][:3], altered['snapshots'][:3])
        for before, after in zip(original['rankings'][:18], altered['rankings'][:18]):
            self.assertEqual(before['order'], after['order'])
        target = original['snapshots'][2]['snapshot']
        self.assertEqual([k['build'] for k in target['eligible_builds']], ['old'])

    def test_completed_history_changes_later_features(self):
        old = build('old',0,1,[('a',True,2),('b',False,1)])
        target = build('target',2,3,[('a',True,1),('b',False,1)])
        before = replay([old,target])
        after = replay([replace(old,outcomes=(Outcome('a',False,2),Outcome('b',True,1))),target])
        a = next(r for r in before['rankings'] if r['key']['build']=='target' and r['method']=='most_fail')
        b = next(r for r in after['rankings'] if r['key']['build']=='target' and r['method']=='most_fail')
        self.assertEqual(a['order'], ('a','b'))
        self.assertEqual(b['order'], ('b','a'))

    def test_deterministic_ties_random_and_full_inventory(self):
        b = build('b',0,1,[('z',True,0),('a',False,1),('missing_source',True,2)])
        s = RollingHistory().snapshot(b.inputs)
        reversed_s = replace(s,features=tuple(reversed(s.features)))
        for method in METHODS:
            self.assertEqual(rank(s,method),rank(reversed_s,method))
            self.assertEqual(set(rank(s,method)),{'a','z','missing_source'})
        self.assertEqual(rank(s,'most_fail'),('a','missing_source','z'))

    def test_aborted_kept_in_ledger_not_scored(self):
        b = build('b',0,1,[('a',True,1)],status='ABORTED')
        r = replay([b])
        self.assertEqual(len(r['rankings']),6)
        self.assertTrue(all(x['metrics'] is None for x in r['rankings']))
        self.assertEqual(r['ledger'][0]['observed_failures'],1)


class AdapterTests(unittest.TestCase):
    def test_adapter_retains_unknown_and_zero_ignores_precomputed_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.zip'
            nested = io.BytesIO()
            with zipfile.ZipFile(nested,'w') as z:
                z.writestr('test_class.csv','testclass,duration,outcome,last_outcome\na,0,1,0\nb,,SKIP,1\n')
            metadata = ('project,pr_name,build_id,stage_id,pr_base_branch,build_timestamp,build_duration,build_head_sha,build_result\n'
                        'p,PR-1,1,s,main,10,5,sha,FAILURE\n')
            with zipfile.ZipFile(path,'w') as z:
                z.writestr(PREFIX+'dataset.csv',metadata)
                z.writestr(PREFIX+'artifact/processed_test_result/p/PR-1_build1/stage_s/test_class.csv.zip',nested.getvalue())
            builds,_ = load_builds(path,'p',20)
            self.assertEqual(len(builds[0].inputs.tests),2)
            self.assertEqual(builds[0].outcomes[0],Outcome('a',True,0))
            self.assertEqual(builds[0].outcomes[1],Outcome('b',None,None))
            self.assertEqual(builds[0].available_at,15)
            self.assertEqual(RollingHistory().snapshot(builds[0].inputs).features[1].observations,0)
            self.assertNotIn('outcome',vars(builds[0].inputs))


if __name__=='__main__':
    unittest.main()
