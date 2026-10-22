"""Fetch only missing blob IDs proven reachable from allowed declared diff endpoints."""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage5_sources import verify_freeze
from scripts.stage4_source_audit import git


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, choices=('karaf', 'activemq', 'log4j'))
    args = parser.parse_args()
    verify_freeze()
    out = ROOT / 'reports/stage5' / args.project
    allowed = set(json.loads((out / 'source-request.json').read_text())['commits'])
    records = [json.loads(line) for line in (out / 'diff-audit.jsonl').read_text().splitlines()]
    repo = ROOT / 'work/sources' / (args.project + '.git')
    missing = set()
    for record in records:
        if record['available']:
            continue
        if record['trunk'] not in allowed or record['head'] not in allowed:
            raise ValueError('Diff endpoints outside allowed selection')
        match = re.search(r'could not fetch ([0-9a-f]{40}) from promisor remote', record['reason'] or '')
        if not match:
            continue
        oid = match.group(1)
        reachable = set()
        for sha in (record['trunk'], record['head']):
            for entry in git(repo, 'ls-tree', '-rz', sha).stdout.split(b'\0'):
                if entry:
                    header, path = entry.split(b'\t', 1)
                    _, kind, candidate = header.decode().split()
                    if kind == 'blob' and path.endswith(b'.java'):
                        reachable.add(candidate)
        if oid not in reachable:
            raise ValueError('Missing object not an allowed Java blob')
        missing.add(oid)
    if missing:
        git(repo, 'fetch', '--refetch', '--no-filter', 'origin', *sorted(missing), timeout=600)
    (out / 'diff-blob-repair.json').write_text(json.dumps(dict(blobs=sorted(missing), reserved_opened=False), indent=2), encoding='utf-8')
    print(args.project, 'repaired', len(missing), 'allowed blobs')


if __name__ == '__main__':
    main()
