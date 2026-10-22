"""Map only frozen warm-up/development selections; never open reserved raw data."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage4_source_audit import git, batch_blobs, declaration
from tcp.lrts import load_builds, file_sha256


def selected(project):
    stage = 'stage3' if project == 'karaf' else 'stage4'
    rows = json.loads((ROOT / 'reports' / stage / project / 'selection.json').read_text())
    return [r for r in rows if r['split'] in ('warmup', 'development')]


def verify_freeze():
    freeze = json.loads((ROOT / 'reports/stage4/design-freeze.json').read_text())
    for name, expected in freeze['files_sha256'].items():
        if file_sha256(ROOT / name) != expected:
            raise ValueError('Frozen evidence changed: ' + name)


def missing_commits(repo, shas):
    output = git(repo, 'cat-file', '--batch-check=%(objectname) %(objecttype)',
                 input=''.join(sha + '\n' for sha in shas).encode()).stdout.decode().splitlines()
    if len(output) != len(shas):
        raise ValueError('Invalid commit inventory response')
    return [sha for sha, line in zip(shas, output) if not line.endswith(' commit')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--project', choices=('karaf', 'activemq', 'log4j'), required=True)
    args = parser.parse_args()
    verify_freeze()
    project = args.project
    selection = selected(project)
    builds, metadata = load_builds(ROOT / 'references/artifacts/dante/ML_TCSP.zip', project, len(selection))
    if {tuple(sorted(r['key'].items())) for r in selection} != {tuple(sorted(asdict(b.inputs.key).items())) for b in builds}:
        raise ValueError('Allowed prefix does not match frozen selection')
    out = ROOT / 'reports/stage5' / project
    out.mkdir(parents=True, exist_ok=True)
    repo = ROOT / 'work/sources' / (project + '.git')
    shas = sorted({r[field] for r in metadata for field in ('build_head_sha', 'trunk_sha') if r.get(field)})
    (out / 'source-request.json').write_text(json.dumps(dict(project=project, reserved_opened=False,
        builds=len(builds), commits=shas), indent=2), encoding='utf-8')
    missing = missing_commits(repo, shas)
    if args.fetch:
        for start in range(0, len(missing), 24):
            print(project, 'fetch', start, '/', len(missing), flush=True)
            git(repo, 'fetch', '--refetch', '--depth=1', '--filter=blob:limit=1m', 'origin', *missing[start:start + 24], timeout=600)
    content_dir = ROOT / 'work/cache/stage5/source'
    content_dir.mkdir(parents=True, exist_ok=True)
    blob_cache = {}
    tree_cache = {}
    mapping_cache = {}
    counts = Counter()
    with gzip.open(out / 'source-mapping.jsonl.gz', 'wt', encoding='utf-8') as stream:
        for index, build in enumerate(builds):
            sha = build.inputs.commit
            if sha not in tree_cache:
                result = git(repo, 'ls-tree', '-rz', sha, check=False)
                paths = {}
                for entry in result.stdout.split(b'\0') if result.returncode == 0 else []:
                    if not entry:
                        continue
                    header, path = entry.split(b'\t', 1)
                    _, kind, oid = header.decode().split()
                    if kind == 'blob' and path.endswith(b'.java'):
                        paths[path.decode()] = oid
                tree_cache[sha] = paths
            paths = tree_cache[sha]
            pending = {}
            for test in build.inputs.tests:
                key = (sha, test.test_id)
                if key not in mapping_cache:
                    suffix = test.test_id.split('$', 1)[0].replace('.', '/') + '.java'
                    pending[test.test_id] = [p for p in paths if p == suffix or p.endswith('/' + suffix)]
            needed = {paths[p] for candidates in pending.values() for p in candidates} - blob_cache.keys()
            for start in range(0, len(needed), 200):
                blob_cache.update(batch_blobs(repo, sorted(needed)[start:start + 200]))
            for tid, candidates in pending.items():
                matched = [p for p in candidates if paths[p] in blob_cache and declaration(blob_cache[paths[p]], tid)]
                status = 'matched' if len(matched) == 1 else ('ambiguous' if len(matched) > 1 else 'missing')
                record = dict(test_id=tid, status=status, source_paths=matched, source_sha256=None,
                              nested_outer_file='$' in tid, declared_commit=sha)
                if status == 'matched':
                    content = blob_cache[paths[matched[0]]]
                    source_hash = hashlib.sha256(content).hexdigest()
                    target = content_dir / source_hash
                    if not target.exists():
                        target.write_bytes(content)
                    record['source_sha256'] = source_hash
                mapping_cache[(sha, tid)] = record
            for test in build.inputs.tests:
                record = dict(mapping_cache[(sha, test.test_id)], key=asdict(build.inputs.key))
                counts[record['status']] += 1
                stream.write(json.dumps(record, sort_keys=True) + '\n')
            if index % 50 == 0:
                print(project, 'mapped builds', index + 1, '/', len(builds), flush=True)
    summary = dict(project=project, builds=len(builds), counts=dict(counts),
                   matched_fraction=counts['matched'] / sum(counts.values()), reserved_opened=False,
                   requested_commits=len(shas), missing_commits=len(missing_commits(repo, shas)),
                   provenance='Declared metadata revision only; not independently verified CI execution revision')
    (out / 'source-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
