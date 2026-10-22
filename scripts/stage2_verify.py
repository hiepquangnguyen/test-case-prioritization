"""Integration checks on the saved Karaf replay and real-cohort leakage mutations."""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tcp.domain import BuildKey, TestInput, RankingInput, Outcome, CompletedBuild
from tcp.history import HistoryConfig
from tcp.lrts import file_sha256
from tcp.replay import replay


def jsonlines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'reports/stage2/karaf20')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((ROOT/'reports/stage2').resolve()):
        raise ValueError('Output must be inside reports/stage2')
    manifest = json.loads((out/'manifest.json').read_text())
    for relative, expected in manifest['implementation_sha256'].items():
        if file_sha256(ROOT/relative) != expected:
            raise AssertionError('Code changed since run: '+relative)
    if file_sha256(ROOT/'docs/02-protocol/protocol-v1.md') != manifest['protocol_sha256']:
        raise AssertionError('Protocol changed since run')
    inputs = []
    for row in jsonlines(out/'inputs.jsonl'):
        row['key'] = BuildKey(**row['key'])
        row['tests'] = tuple(TestInput(**{**t, 'source_paths': tuple(t['source_paths'])}) for t in row['tests'])
        inputs.append(RankingInput(**row))
    lookup = {b.key:b for b in inputs}
    builds = []
    for row in jsonlines(out/'ground-truth.jsonl'):
        key = BuildKey(**row['key'])
        builds.append(CompletedBuild(lookup[key],row['available_at'],row['result'],
                                     tuple(Outcome(**o) for o in row['outcomes'])))
    saved_rankings = jsonlines(out/'rankings.jsonl')
    cfg = HistoryConfig(**manifest['config'])
    again = replay(builds,cfg,seed=manifest['seed'])
    # Normalize tuples through JSON to compare the persistent representation.
    normalize = lambda x: json.loads(json.dumps(x,allow_nan=False))
    assert normalize(again['snapshots']) == jsonlines(out/'features.jsonl')
    for expected, actual in zip(saved_rankings,again['rankings'],strict=True):
        for field in ('key','method','seed','snapshot_sha256','order','metrics','scoring_exclusion'):
            assert expected[field] == normalize(actual[field]), (field, actual['key'])
    mutations = 0
    for target in builds:
        changed = []
        for b in builds:
            if b.inputs.cutoff >= target.inputs.cutoff:
                changed.append(replace(b, available_at=b.inputs.cutoff+999999, result='ABORTED',
                                       outcomes=tuple(replace(o,failed=not o.failed if o.failed is not None else True,
                                                              duration=123456.0+i) for i,o in enumerate(b.outcomes))))
            else:
                changed.append(b)
        altered = replay(changed,cfg,seed=manifest['seed'])
        key = normalize(target.inputs.key.__dict__)
        original_rows = [r for r in again['rankings'] if r['key']==key]
        mutated_rows = [r for r in altered['rankings'] if r['key']==key]
        assert len(original_rows)==6
        for a,b in zip(original_rows,mutated_rows,strict=True):
            assert a['snapshot_sha256']==b['snapshot_sha256']
            assert a['order']==b['order']
            mutations += 1
    ledger = again['ledger']
    target = next(r for r in ledger if r['key']['pr']=='PR-1287' and r['key']['build']=='1')
    assert target['tests']==212 and target['observed_failures']==4
    assert len(builds)==20 and len(saved_rankings)==120
    assert sum(r['scoring_exclusion'] is not None for r in ledger)==2
    # Every method receives exactly one snapshot per build and retains all source statuses.
    for b in builds:
        key = b.inputs.key.__dict__
        rows = [r for r in again['rankings'] if r['key']==key]
        assert len({r['snapshot_sha256'] for r in rows})==1
        assert all(set(r['order'])=={t.test_id for t in b.inputs.tests} for r in rows)
    result = dict(status='passed',reproduced_rankings=len(saved_rankings),real_cohort_leakage_comparisons=mutations,
                  full_universe_preserved=True,code_and_protocol_hashes_match=True,
                  target_pr1287_build1=dict(tests=212,failures=4),
                  limitation='Conditional on observed inventory and declared timestamp semantics; not proof of prospective CI validity.')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
