"""Audit pinned archives without executing artifact code; Python standard library only.

Run from any directory: python -X utf8 scripts/stage1_audit.py [--extract]
Archive members are read in place. --extract copies selected inputs/code to work/.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import math
import pickle
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/stage1"
WORK = ROOT / "work/artifacts"
LRTS = "ML_TCSP/long_running_test_suites/"
PROJECTS = ("Chart", "Closure", "Lang", "Math", "Mockito", "Time")


class DataOnlyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"Object construction forbidden: {module}.{name}")


def data_pickle(blob):
    return DataOnlyUnpickler(io.BytesIO(blob)).load()


def write_json(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def csv_in_zip(z, name):
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def raw_name(row):
    pr = row['pr_name'].replace('/', '_')
    return f"{LRTS}artifact/processed_test_result/{row['project']}/{pr}_build{row['build_id']}/stage_{row['stage_id']}/test_class.csv.zip"


def raw_rows(z, name):
    with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
        candidates = [n for n in inner.namelist() if n.endswith("test_class.csv")]
        if len(candidates) != 1:
            raise ValueError(f"Ambiguous CSV in {name}: {candidates}")
        return csv_in_zip(inner, candidates[0])


def extract_member(z, name):
    target = (WORK / name).resolve()
    if not target.is_relative_to(WORK.resolve()):
        raise ValueError(f"Unsafe archive path: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(z.read(name)).digest():
            raise ValueError(f"Existing artifact differs; refusing overwrite: {target}")
        return
    with z.open(name) as src, target.open("wb") as dest:
        shutil.copyfileobj(src, dest)


def archive_info(path, expected_md5):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    with zipfile.ZipFile(path) as z:
        result = dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                      md5=md5.hexdigest(), sha256=sha.hexdigest(),
                      md5_matches_manifest=md5.hexdigest() == expected_md5,
                      entries=len(z.infolist()), uncompressed_bytes=sum(i.file_size for i in z.infolist()),
                      java_files=sum(n.endswith('.java') for n in z.namelist()))
    if not result['md5_matches_manifest']:
        raise ValueError(f"Checksum mismatch: {path}")
    return result


def independent_apfd(order, faults):
    universe = {fault for values in faults.values() for fault in values}
    if not universe:
        return None
    first = {}
    for rank, test in enumerate(order, 1):
        for fault in faults.get(test, []):
            first.setdefault(fault, rank)
    if set(first) != universe:
        raise ValueError("Ranking misses faults")
    return 1 - sum(first.values()) / (len(order) * len(universe)) + 1 / (2 * len(order))


def audit_falcon(z, extract):
    summaries, author_checks = [], []
    names = set(z.namelist())
    for project in PROJECTS:
        base = f"falcon/input/{project}/"
        lines = z.read(base + project + '-bbox.txt').decode('utf-8').splitlines()
        mapping_doc = json.loads(z.read(base + 'test_method_mapping.json'))
        mapping = {int(k): v for k, v in mapping_doc['index_to_method'].items()}
        faults = {int(k): v for k, v in data_pickle(z.read(base + 'fault_matrix.pickle')).items()}
        indexed = {int(i): name for i, name in re.findall(r'^\s*(\d+):\s*(.+)$', z.read(base + 'method_index_list.txt').decode(), re.M)}
        ids = set(range(len(lines)))
        source_mismatch = [i for i, v in mapping.items() if i not in ids or not re.search(r'\b' + re.escape(v['methodName']) + r'\s*\(', lines[i])]
        versions = collections.Counter(re.findall(r'/([^/]+_[0-9]+[bf])/', v['filePath'])[0] if re.findall(r'/([^/]+_[0-9]+[bf])/', v['filePath']) else 'unknown' for v in mapping.values())
        identifiers = [v['fullIdentifier'] for v in mapping.values()]
        faults_unique = sorted({f for v in faults.values() for f in v})
        record = dict(project=project, tests=len(lines), blank_lines=sum(not s.strip() for s in lines),
                      duplicate_source_rows=len(lines)-len(set(lines)), mapping_entries=len(mapping),
                      duplicate_identifiers=len(identifiers)-len(set(identifiers)),
                      mapping_indices_exact=set(mapping)==ids, index_list_indices_exact=set(indexed)==ids,
                      index_list_mismatches=sum(indexed.get(i) != v['fullIdentifier'] for i,v in mapping.items()),
                      method_name_source_mismatches=len(source_mismatch), fault_keys_outside_suite=len(set(faults)-ids),
                      failing_methods=sum(bool(v) for v in faults.values()), faults=len(faults_unique),
                      source_versions=dict(versions), source_paths_present=sum('falcon/'+v['filePath'] in names for v in mapping.values()),
                      embedding_vectors=sum(n.startswith(base+'embeddings/') and n.endswith('.npy') for n in names),
                      fault_ids=faults_unique, source_name_mismatch_examples=source_mismatch[:10])
        summaries.append(record)
        prefix = f"falcon/output/{project}/FALCON/prioritized/"
        for name in sorted(names):
            if not name.startswith(prefix) or not name.endswith('.pickle'):
                continue
            order = data_pickle(z.read(name))
            valid = len(order)==len(ids) and len(set(order))==len(ids) and set(order)==ids
            stem = name.rsplit('/',1)[-1].rsplit('-',1)[0]
            tsv = f"falcon/output/{project}/FALCON/{stem}.tsv"
            author = list(csv.DictReader(io.StringIO(z.read(tsv).decode()), delimiter='\t')) if tsv in names else []
            score = independent_apfd(order, faults) if valid else None
            author_checks.append(dict(project=project, archive_member=name, valid_permutation=valid,
                                      recalculated_apfd=score, author_apfd=number(author[0].get('APFD')) if author else None,
                                      absolute_difference=abs(score-float(author[0]['APFD'])) if valid and author else None))
        print('FALCON',project,record['tests'],'tests',record['faults'],'faults',flush=True)
    if extract:
        for name in sorted(names):
            if not name.endswith('/') and (name.startswith(('falcon/py/','falcon/input/','falcon/projects/','falcon/config/')) or name in ('falcon/README.md','falcon/LICENSE','falcon/requirements.txt')):
                extract_member(z,name)
    write_json('falcon-data-audit.json',summaries)
    write_json('falcon-author-ranking-checks.json',author_checks)
    write_csv('falcon-summary.csv',[{k:v for k,v in r.items() if not isinstance(v,(list,dict))} for r in summaries])


def audit_lrts(z, extract):
    names = set(z.namelist())
    metadata = csv_in_zip(z,LRTS+'dataset.csv')
    by_project = collections.defaultdict(list)
    for row in metadata:
        by_project[row['project']].append(row)
    processed = sorted(n for n in names if n.startswith('ML_TCSP/src/processed_builds/') and n.endswith('.json'))
    processed_stats = []
    for n in processed:
        doc = json.loads(z.read(n))
        cases = doc.get('test_cases',{})
        counts = collections.Counter(k for tc in cases.values() for fs in tc.get('relevance_to_changed_files',{}).values() for k in fs)
        processed_stats.append(dict(member=n,project=doc.get('project'),sha=doc.get('build_commit_sha'),tests=len(cases),
                                    failures=sum(tc.get('outcome')==1 for tc in cases.values()),
                                    source_found=sum(bool(tc.get('source_file_found')) for tc in cases.values()),
                                    tokens_available=sum(bool(tc.get('tokens')) for tc in cases.values()),relevance_keys=dict(counts)))
        if extract:
            extract_member(z,n)
    write_json('dante-processed-builds.json',processed_stats)
    builds, projects = [], []
    for project, rows in sorted(by_project.items()):
        stats = collections.Counter()
        outcomes = collections.Counter()
        tests_seen = set()
        keys_seen = set()
        previous_end = None
        sorted_rows = sorted(rows,key=lambda r:(number(r['build_timestamp']) or 0,r['pr_name'],r['build_id'],r['stage_id']))
        for row in sorted_rows:
            key = tuple(row[k] for k in ('project','pr_name','build_id','stage_id'))
            stats['duplicate_metadata_keys'] += key in keys_seen
            keys_seen.add(key)
            stamp, duration = number(row['build_timestamp']), number(row['build_duration'])
            stats['missing_timestamp'] += stamp is None
            stats['missing_sha'] += not bool(re.fullmatch('[0-9a-f]{40}',row['build_head_sha']))
            overlap = bool(stamp is not None and previous_end is not None and stamp < previous_end)
            stats['possible_overlap_if_timestamp_is_start'] += overlap
            if stamp is not None and duration is not None:
                previous_end = max(previous_end or 0,stamp+duration)
            name = raw_name(row)
            record = {k:row[k] for k in ('project','pr_name','build_id','stage_id','build_timestamp','build_duration','build_head_sha','build_date','pr_base_branch')}
            record.update(raw_member=name,raw_present=name in names,tests=0,failures=0,invalid_duration=0,zero_duration=0,negative_duration=0,unknown_outcomes=0,duplicate_test_ids=0,new_test_ids=0,absent_previous_test_ids=0,metadata_counts_match=False,possible_overlap=overlap)
            if name in names:
                tests = raw_rows(z,name)
                test_ids = [tc['testclass'] for tc in tests]
                ids = set(test_ids)
                record.update(tests=len(tests),failures=sum(tc['outcome']=='1' for tc in tests),duplicate_test_ids=len(test_ids)-len(ids),new_test_ids=len(ids-tests_seen),absent_previous_test_ids=len(tests_seen-ids))
                tests_seen = ids
                for tc in tests:
                    cost = number(tc.get('duration'))
                    record['invalid_duration'] += cost is None
                    record['zero_duration'] += cost == 0
                    record['negative_duration'] += cost is not None and cost < 0
                    record['unknown_outcomes'] += tc.get('outcome') not in ('0','1')
                    outcomes[tc.get('outcome','missing')] += 1
                record['metadata_counts_match'] = record['failures']==number(row['num_fail_class']) and len(tests)==(number(row['num_pass_class']) or 0)+(number(row['num_fail_class']) or 0)
                stats['metadata_count_mismatches'] += not record['metadata_counts_match']
                for k in ('tests','failures','invalid_duration','zero_duration','negative_duration','unknown_outcomes','duplicate_test_ids'):
                    stats[k] += record[k]
                stats['raw_builds'] += 1
                stats['failing_builds'] += record['failures']>0
                if extract and project in ('activemq','karaf','log4j'):
                    extract_member(z,name)
            else:
                stats['missing_raw_builds'] += 1
            builds.append(record)
        project_processed = [r for r in processed_stats if r['project']==project]
        summary = dict(project=project,metadata_rows=len(rows),date_from=min(r['build_date'] for r in rows),date_to=max(r['build_date'] for r in rows),processed_jsons=len(project_processed),**dict(stats),outcome_counts=dict(outcomes))
        projects.append(summary)
        print('LRTS',project,len(rows),'metadata rows',stats['raw_builds'],'raw present',flush=True)
    if extract:
        for n in sorted(names):
            direct_src = n.startswith('ML_TCSP/src/') and n.count('/')==2 and n.endswith(('.py','.toml','.txt','.md','.lock'))
            direct_raw_code = n.startswith(LRTS+'artifact/') and n.count('/')==3 and n.endswith(('.py','.md','.sh')) and not n.endswith('token_pool.py')
            if direct_src or direct_raw_code or n in (LRTS+'dataset.csv',LRTS+'flaky_tests.csv',LRTS+'LICENSE.txt','ML_TCSP/LICENSE.txt','ML_TCSP/requirements.txt','ML_TCSP/Dockerfile','ML_TCSP/docker-compose.yml'):
                extract_member(z,n)
    write_json('lrts-project-audit.json',projects)
    write_csv('lrts-build-audit.csv',builds)
    write_json('lrts-coverage.json',dict(metadata_rows=len(metadata),processed_jsons=len(processed),raw_csv_zip_members=sum(n.endswith('/test_class.csv.zip') for n in names),metadata_columns=list(metadata[0]),note='new_test_ids compares adjacent observed suites, not first-ever appearance; overlap assumes timestamp=start and duration=seconds until independently verified.'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract',action='store_true')
    args = parser.parse_args()
    archives = [('falcon','falcon.zip','a1cfd6c32eb5889c0e08f23872739aae'),('dante','ML_TCSP.zip','b268b21616f6ceb396e8df89d382f298')]
    checks = []
    for label,filename,md5 in archives:
        path = ROOT / 'references/artifacts' / label / filename
        checks.append(archive_info(path,md5))
        with zipfile.ZipFile(path) as z:
            (audit_falcon if label=='falcon' else audit_lrts)(z,args.extract)
    write_json('archives.json',checks)


if __name__ == '__main__':
    main()
