import unittest
from dataclasses import replace
from datetime import datetime, timezone

from tcp.domain import BuildKey, CompletedBuild, Outcome, RankingInput, TestInput as DomainTestInput
from tcp.history import RollingHistory
from scripts.pilot_support import conservative, compact_snapshot, digest, score_reason, split_for
from scripts.stage3_run import summarize


def build(name,start,end):
    inp=RankingInput(BuildKey('p','pr',name,'s'),'main',start,'sha',(DomainTestInput('t'),))
    return CompletedBuild(inp,end,'SUCCESS',(Outcome('t',True,1.0),))


class PilotTests(unittest.TestCase):
    def test_utc_calendar_boundaries_do_not_use_labels(self):
        for year,split in ((2021,'warmup'),(2022,'development'),(2023,'holdout')):
            t=datetime(year,1,1,tzinfo=timezone.utc).timestamp()
            self.assertEqual(split_for(t),split)
        self.assertEqual(split_for(datetime(2023,1,1,tzinfo=timezone.utc).timestamp()-1),'development')

    def test_rounding_guard_blocks_early_feedback_and_boundary(self):
        old=conservative(build('old',0,10))
        h=RollingHistory();h.observe(old)
        for t in (10.1,11,12):self.assertFalse(h.snapshot(build('new',t,t+5).inputs).eligible_builds)
        self.assertTrue(h.snapshot(build('new',12.1,20).inputs).eligible_builds)
        self.assertIsNone(conservative(build('unknown',0,None)).available_at)

    def test_warmup_and_aborted_excluded_without_dropping_inventory(self):
        b=build('a',1,2)
        self.assertEqual(score_reason(b,'warmup'),'warmup_not_scored')
        self.assertIsNone(score_reason(b,'holdout'))
        self.assertIn('ABORTED',score_reason(replace(b,result='ABORTED'),'development'))

    def test_compact_evidence_hash_changes_when_past_identity_changes(self):
        current=build('new',3,4)
        hashes=[]
        for name in ('old1','old2'):
            h=RollingHistory();h.observe(build(name,0,1))
            hashes.append(digest(compact_snapshot(h.snapshot(current.inputs))))
        self.assertNotEqual(*hashes)

    def test_random_aggregation_keeps_build_as_unit_and_na(self):
        rows=[]
        for name,values in (('a',[0.0,1.0]),('b',[0.2,0.4]),('c',[None,None])):
            for seed,v in enumerate(values):
                rows.append(dict(project='p',pr='pr',build=name,stage='s',split='holdout',method='random',seed=seed,
                                 tests=2,observed_failures=0 if v is None else 1,apfdc_midpoint=v,ttff_censored=v is None))
        summary=next(r for r in summarize(rows) if r['split']=='holdout' and r['method']=='random')
        self.assertEqual(summary['builds'],3)
        self.assertEqual(summary['no_failure_builds'],1)
        self.assertEqual(summary['metrics']['apfdc_midpoint']['defined_builds'],2)
        self.assertAlmostEqual(summary['metrics']['apfdc_midpoint']['median_of_build_means'],0.4)


if __name__=='__main__':unittest.main()
