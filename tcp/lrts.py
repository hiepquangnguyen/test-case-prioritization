"""LRTS adapter: raw observations and separate source-audit annotations.

Inventory comes from observed logs, NOT an independently collected pre-build
manifest. This is an explicit retrospective replay assumption, recorded in every
RankingInput. Precomputed last_outcome fields are deliberately never read.
"""
import csv
import hashlib
import io
import math
import zipfile
from pathlib import Path
from .domain import BuildKey, TestInput, RankingInput, Outcome, CompletedBuild

PREFIX = 'ML_TCSP/long_running_test_suites/'
EXPECTED_MD5 = 'b268b21616f6ceb396e8df89d382f298'


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_archive(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            md5.update(chunk)
            sha.update(chunk)
    if md5.hexdigest() != EXPECTED_MD5:
        raise ValueError('DANTE archive does not match pinned stage-1 artifact')
    return {'md5': md5.hexdigest(), 'sha256': sha.hexdigest()}


def finite_number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def load_source_annotations(path):
    result = {}
    if path is None:
        return result
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            key = (BuildKey(row['project'], row['pr_name'], row['build_id'], row['stage_id']),
                   row['commit_sha'], row['test_id'])
            if key in result:
                raise ValueError('Duplicate source annotation')
            # Only these pre-ranking source fields cross the boundary. Never copy outcome.
            result[key] = {k: row[k] for k in ('status', 'source_paths', 'source_sha256')}
    return result


def load_builds(archive, project='karaf', limit=20, source_annotations=None):
    if limit <= 0:
        raise ValueError('limit must be positive')
    annotations = load_source_annotations(source_annotations)
    with zipfile.ZipFile(archive) as z:
        rows = list(csv.DictReader(io.StringIO(z.read(PREFIX+'dataset.csv').decode('utf-8-sig'))))
        rows = [r for r in rows if r['project'] == project]
        if not rows:
            raise ValueError('Project absent from metadata')
        if any(finite_number(r['build_timestamp']) is None for r in rows):
            raise ValueError('Cannot silently order missing timestamps')
        rows.sort(key=lambda r: (float(r['build_timestamp']), r['pr_name'], r['build_id'], r['stage_id']))
        selected = rows[:limit]
        builds, seen = [], set()
        for row in selected:
            key = BuildKey(project, row['pr_name'], row['build_id'], row['stage_id'])
            if key in seen:
                raise ValueError('Duplicate build-stage key')
            seen.add(key)
            name = (PREFIX+f"artifact/processed_test_result/{project}/"
                    f"{row['pr_name'].replace('/', '_')}_build{row['build_id']}/"
                    f"stage_{row['stage_id']}/test_class.csv.zip")
            # A missing raw file is a hard error, not a smaller favourable cohort.
            with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                csv_names = [n for n in inner.namelist() if n.endswith('test_class.csv')]
                if len(csv_names) != 1:
                    raise ValueError('Ambiguous nested CSV')
                raw = list(csv.DictReader(io.StringIO(inner.read(csv_names[0]).decode('utf-8-sig'))))
            tests, outcomes = [], []
            for test in raw:
                tid = test['testclass']
                source = annotations.get((key, row['build_head_sha'], tid), {})
                category = 'suspected_runner_event' if tid == 'org.apache.maven.surefire.junit4.JUnit4Provider' else 'test'
                tests.append(TestInput(tid, source.get('status', 'unverified'),
                                       tuple(p for p in source.get('source_paths', '').split(';') if p),
                                       source.get('source_sha256') or None, category))
                outcomes.append(Outcome(tid, {'0': False, '1': True}.get(test['outcome']),
                                        finite_number(test.get('duration'))))
            inputs = RankingInput(key, row.get('pr_base_branch', ''), float(row['build_timestamp']),
                                  row['build_head_sha'], tuple(sorted(tests, key=lambda t: t.test_id)))
            duration = finite_number(row.get('build_duration'))
            # Zero/missing total build duration cannot establish completion.
            available = inputs.cutoff + duration if duration is not None and duration > 0 else None
            builds.append(CompletedBuild(inputs, available, row['build_result'],
                                         tuple(sorted(outcomes, key=lambda o: o.test_id))))
    return tuple(builds), selected
