"""Audit constraints and prior freezes, then freeze completed revision evidence."""
import gzip
import json
from pathlib import Path
from datetime import datetime, timezone
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage6_pilot import write_json
from tcp.lrts import file_sha256


def main():
    for name in ('reports/stage6/final-evidence-freeze.json','reports/stage7/evidence-freeze.json','reports/stage8/manifest.json'):
        for path, expected in json.loads((ROOT/name).read_text())['files_sha256'].items():
            assert file_sha256(ROOT/path) == expected, path
    projects = {}
    for project in ('karaf','activemq','log4j'):
        count, steps, mutations = 0,0,0
        for path in (ROOT/'reports/stage8'/project/'builds').glob('*.json.gz'):
            with gzip.open(path,'rt',encoding='utf-8') as stream:
                record = json.load(stream)
            features = {f['test_id']:f for f in record['input_features']}
            ids = sorted(features,key=lambda t:(-features[t]['q'],t))
            positions = {t:i for i,t in enumerate(ids)}
            q = np.asarray([features[t]['q'] for t in ids])
            cost = np.maximum(1e-6,[features[t]['cost'] for t in ids])
            remaining = np.ones(len(ids),dtype=bool)
            cursor = 0
            assert record['order'] == [s['test_id'] for s in record['trace']]
            for step in record['trace']:
                while not remaining[cursor]:
                    cursor += 1
                chosen = positions[step['test_id']]
                pool = remaining & (q >= .95*q[cursor]) & (cost <= 1.25*cost[cursor])
                assert pool[chosen] and step['candidate_count'] == int(pool.sum())
                assert step['baseline_head'] == ids[cursor]
                assert step['q'] == q[chosen] and step['head_q'] == q[cursor]
                assert step['predicted_cost'] == cost[chosen] and step['head_predicted_cost'] == cost[cursor]
                assert step['zero_q'] == (q[cursor] == 0)
                if step['zero_gain_fallback']:
                    assert chosen == cursor and step['semantic_gain'] == 0
                remaining[chosen] = False
                steps += 1
            assert not remaining.any()
            policy = record['cache_policy']
            assert policy['fallback'] == (policy['missing_hashes'] > 0)
            assert policy['order'] == (ids if policy['fallback'] else record['order'])
            if record['ineligible_mutation_count'] is not None:
                assert record['ineligible_mutation_count'] > 0
                mutations += 1
            count += 1
        expected = json.loads((ROOT/'reports/stage6'/project/'complete.json').read_text())['development_scored']
        assert count == expected and mutations == 2
        projects[project] = dict(stages=count,selection_steps_verified=steps,mutation_checks=mutations)
    out = ROOT/'reports/stage8'
    write_json(out/'closeout-audit.json',dict(projects=projects,prior_freezes_unchanged=True,reserved_opened=False,
        checks='all raw-q heads, candidate bands, cost caps, fallback traces, full inventories, policy orders; runner independently checked APFD/APFDc'))
    paths = list((ROOT/'scripts').glob('stage8_*.py'))+list((ROOT/'docs/08-revision').glob('*.md'))
    paths += [ROOT/'hc_falcon/restricted.py',ROOT/'tests/test_stage8.py',ROOT/'configs/restricted-semantic-v1.json']
    paths += [p for p in out.rglob('*') if p.is_file() and p.name != 'evidence-freeze.json']
    write_json(out/'evidence-freeze.json',dict(created_at=datetime.now(timezone.utc).isoformat(),reserved_opened=False,
        files_sha256={p.relative_to(ROOT).as_posix():file_sha256(p) for p in sorted(paths)}))
    print(json.dumps(projects,indent=2))


if __name__ == '__main__':
    main()
