"""Audit completed pilot scope and freeze its final review artifacts."""
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import selected
from scripts.stage6_pilot import verify_implementation, write_json
from tcp.lrts import file_sha256


def main():
    frozen = verify_implementation()
    directory = ROOT / 'reports/stage6'
    summary = json.loads((directory / 'summary.json').read_text())
    assert summary['reserved_opened'] is False
    checks = {}
    for project, result in summary['projects'].items():
        out = directory / project
        ledger = json.loads((out / 'ledger.json').read_text())
        manifest = json.loads((out / 'manifest.json').read_text())
        assert manifest['runner_sha256'] == file_sha256(ROOT / 'scripts/stage6_pilot.py')
        assert manifest['stage5_sha256'] == frozen
        expected = [(row['key'], row['split']) for row in selected(project)]
        assert [(row['key'], row['split']) for row in ledger] == expected
        count = 0
        for row in ledger:
            if row['checkpoint'] is None:
                continue
            assert row['split'] == 'development' and row['usable']
            with gzip.open(out / 'builds' / row['checkpoint'], 'rt', encoding='utf-8') as stream:
                checkpoint = json.load(stream)
            assert checkpoint['manifest'] == manifest and checkpoint['key'] == row['key']
            assert len(checkpoint['rankings']) == 57
            count += 57
        assert count == result['rankings_verified']
        replay = json.loads((out / 'replay-verification.json').read_text())
        assert replay['passed']
        exceptions = replay['numerical_tie_exceptions']
        same_metrics = all(row['alpha_zero_metrics'] == row['history_cost_metrics'] for row in exceptions)
        assert same_metrics
        source = result['source']
        coverage = sum(row['valid'] for row in source.values()) / sum(row['records'] for row in source.values())
        assert coverage >= .9
        checks[project] = dict(allowed_ledger_stages=len(ledger), rankings=count,
            valid_semantic_coverage=coverage, source_gate_passed=True,
            numerical_tie_exceptions=len(exceptions), exception_metrics_identical=same_metrics,
            replay_passed=True)
    write_json(directory / 'closeout-audit.json', dict(projects=checks,
        stage5_freeze_verified=True, reserved_opened=False, decision=summary['decision']))
    paths = [ROOT / 'README.md', ROOT / 'tests/test_stage6.py']
    paths += list((ROOT / 'scripts').glob('stage6_*.py'))
    paths += list((ROOT / 'docs/06-pilot').glob('*.md'))
    paths += [p for p in directory.rglob('*') if p.is_file()
              and p.suffix in ('.json', '.gz', '.py', '.txt')
              and p.name != 'final-evidence-freeze.json']
    write_json(directory / 'final-evidence-freeze.json', dict(
        created_at=datetime.now(timezone.utc).isoformat(), scope='completed_development_pilot',
        reserved_opened=False, decision=summary['decision'],
        files_sha256={p.relative_to(ROOT).as_posix():file_sha256(p) for p in sorted(set(paths))}))
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
