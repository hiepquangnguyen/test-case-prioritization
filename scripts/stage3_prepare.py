"""Freeze a chronological cohort, audit artifact provenance and local source."""
import csv
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tcp.lrts import PREFIX, file_sha256, load_builds, verify_archive
from tcp.history import HistoryConfig
from scripts.pilot_support import OUT, SEEDS, conservative, digest, split_for, write_json


def git(*args):
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', '--git-dir', str(ROOT/'work/sources/karaf.git'),
                           '-c', 'remote.origin.promisor=false', *args],
                          capture_output=True, env=env, timeout=30)


def source_audit():
    with (ROOT/'reports/stage1/karaf-source-mapping.csv').open(encoding='utf-8-sig') as f:
        annotations = list(csv.DictReader(f))
    issues, commits = {}, {}
    for row in annotations:
        sha = row['commit_sha']
        if sha not in commits:
            tree = git('ls-tree', '-r', '--name-only', sha)
            paths = tree.stdout.decode('utf-8').splitlines() if tree.returncode == 0 else []
            evidence = []
            # Relevant build configuration and ambiguous-module Maven descriptors.
            for path in ('Jenkinsfile', 'pom.xml', 'specs/pom.xml',
                         'specs/activator/pom.xml', 'specs/locator/pom.xml'):
                if path not in paths:
                    continue
                result = git('show', sha+':'+path)
                if result.returncode:
                    evidence.append(dict(path=path, status='blob_unavailable'))
                    continue
                content = result.stdout.decode('utf-8', errors='replace')
                write_path = OUT/'source-evidence'/sha/path
                write_path.parent.mkdir(parents=True, exist_ok=True)
                write_path.write_bytes(result.stdout)
                pattern = r'mvn |junit\(|skipStages|<module>|<id>test|surefire|failsafe|generate-test|testSourceDirectory|<artifactId>'
                evidence.append(dict(path=path, sha256=file_sha256(write_path),
                                     lines=[dict(line=i, text=line.strip()) for i,line in enumerate(content.splitlines(),1)
                                            if re.search(pattern,line)]))
            commits[sha] = dict(paths=paths, tree_available=tree.returncode==0, configuration=evidence)
        if row['status'] == 'matched':
            continue
        identity = (sha, row['test_id'])
        if identity in issues:
            issues[identity]['occurrences'].append(dict(pr=row['pr_name'], build=row['build_id'], stage=row['stage_id']))
            continue
        paths = commits[sha]['paths']
        outer = row['test_id'].split('$')[0]
        pkg, _, cls = outer.rpartition('.')
        candidates = [p for p in paths if p.rsplit('/',1)[-1] in (cls+'.java', cls+'.kt', cls+'.groovy')]
        candidate_info = []
        for path in candidates:
            blob = git('show', sha+':'+path)
            content = blob.stdout.decode('utf-8',errors='replace')
            candidate_info.append(dict(path=path, blob_available=blob.returncode==0,
                exact_java_declaration=bool(re.search(r'\bpackage\s+'+re.escape(pkg)+r'\s*;',content)
                                           and re.search(r'\bclass\s+'+re.escape(cls)+r'\b',content)),
                sha256=digest(content) if blob.returncode==0 else None))
        runner = row['test_id']=='org.apache.maven.surefire.junit4.JUnit4Provider'
        conclusion = ('suspected_runner_event_no_stacktrace' if runner else
                      'ambiguous_module_identity_lost_in_class_aggregation' if row['status']=='ambiguous' else
                      'missing_at_declared_revision_generated_or_dependency_origin_unproven')
        issues[identity] = dict(commit=sha,test_id=row['test_id'],previous_status=row['status'],
                               resolution='unresolved', conclusion=conclusion,candidates=candidate_info,
                               occurrences=[dict(pr=row['pr_name'],build=row['build_id'],stage=row['stage_id'])])
    write_json(OUT/'source-review.json', dict(scope='20 technical rows / 18 local commits; no network fetch',
        issue_occurrences=sum(len(x['occurrences']) for x in issues.values()), unique_issues=len(issues),
        issues=list(issues.values()), commits={s:{k:v for k,v in d.items() if k!='paths'} for s,d in commits.items()},
        conclusion='No ambiguous/missing test silently resolved. Execution revision and module cannot be confirmed without raw reports/logs.'))
    return commits


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = ROOT/'references/artifacts/dante/ML_TCSP.zip'
    print('Verifying pinned archive and freezing cohort before scoring...', flush=True)
    hashes = verify_archive(archive)
    with zipfile.ZipFile(archive) as z:
        metadata = [r for r in csv.DictReader(io.StringIO(z.read(PREFIX+'dataset.csv').decode('utf-8-sig'))) if r['project']=='karaf']
        metadata.sort(key=lambda r:(float(r['build_timestamp']),r['pr_name'],r['build_id'],r['stage_id']))
        names = z.namelist()
        raw_evidence = [n for n in names if 'karaf' in n and ('/PR/PR-' in n or 'test_report.csv' in n or '/build_log/' in n)]
    selection = [dict(key=dict(project='karaf',pr=r['pr_name'],build=r['build_id'],stage=r['stage_id']),
                      cutoff=float(r['build_timestamp']),split=split_for(float(r['build_timestamp'])),
                      commit=r['build_head_sha'],branch=r['pr_base_branch']) for r in metadata]
    code = [*sorted((ROOT/'tcp').glob('*.py')), *sorted((ROOT/'scripts').glob('*pilot*.py')),
            *sorted((ROOT/'scripts').glob('stage3_*.py'))]
    manifest = dict(protocol='v2-baseline-pilot', created_at=datetime.now(timezone.utc).isoformat(),
        archive=hashes, selection_sha256=digest(selection),
        split_rule='UTC calendar: <2022 warmup; 2022 development; >=2023 baseline holdout',
        split_counts=dict(Counter(r['split'] for r in selection)), seeds=list(SEEDS), config=asdict(HistoryConfig()),
        availability_guard_seconds=2, no_tuning=True,
        protocol_sha256=file_sha256(ROOT/'docs/03-pilot/protocol-v2.md'),
        code_sha256={str(p.relative_to(ROOT)):file_sha256(p) for p in code},
        annotations_sha256=file_sha256(ROOT/'reports/stage1/karaf-source-mapping.csv'),
        scope='retrospective observed-class baseline replay; not HC-FALCON confirmatory holdout')
    if (OUT/'manifest.json').exists():
        old = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
        if {k:v for k,v in old.items() if k!='created_at'} != {k:v for k,v in manifest.items() if k!='created_at'}:
            raise ValueError('Frozen manifest differs; use a new version/output rather than overwrite this experiment')
    else:
        write_json(OUT/'manifest.json',manifest)
        write_json(OUT/'selection.json',selection)
    builds, _ = load_builds(archive, 'karaf', len(metadata), ROOT/'reports/stage1/karaf-source-mapping.csv')
    builds = tuple(conservative(b) for b in builds)
    print('Auditing',len(builds),'raw class files and local source evidence...',flush=True)
    commits = source_audit()
    all_shas = sorted({b.inputs.commit for b in builds})
    # Batch local existence checks; no implicit remote object fetch.
    env = dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0')
    proc = subprocess.run(['git','--git-dir',str(ROOT/'work/sources/karaf.git'),'-c','remote.origin.promisor=false','cat-file','--batch-check'],
                          input=''.join(s+'\n' for s in all_shas),capture_output=True,text=True,env=env,check=True)
    local = {line.split()[0] for line in proc.stdout.splitlines() if len(line.split())==3 and line.split()[1]=='commit'}
    audits=[]
    for b,row in zip(builds,metadata):
        overlaps=[p for p in builds if p.inputs.cutoff < b.inputs.cutoff and p.available_at is not None
                  and p.available_at >= b.inputs.cutoff and p.inputs.context==b.inputs.context]
        near=[p for p in builds if p.usable and p.inputs.context==b.inputs.context and p.inputs.key.physical!=b.inputs.key.physical
              and p.available_at is not None and p.available_at-2 < b.inputs.cutoff <= p.available_at]
        failures=sum(o.failed is True for o in b.outcomes)
        passes=sum(o.failed is False for o in b.outcomes)
        total=sum(o.duration for o in b.outcomes if o.duration is not None)
        audits.append(dict(key=asdict(b.inputs.key),split=split_for(b.inputs.cutoff),start=b.inputs.cutoff,
            conservative_available_at=b.available_at,result=b.result,tests=len(b.outcomes),failures=failures,
            class_counts_match=passes==int(row['num_pass_class']) and failures==int(row['num_fail_class']),
            duration_sum_error=total-float(row['test_suite_duration_s']),
            invalid_durations=sum(o.duration is None or o.duration<0 for o in b.outcomes),
            zero_durations=sum(o.duration==0 for o in b.outcomes),unknown_outcomes=sum(o.failed is None for o in b.outcomes),
            timestamp_evidence='collector_conversion_verified; raw_build_start_unverified',
            inventory_evidence='insufficient_for_prebuild_inventory; upstream_skipped_filter_and_FQN_aggregation',
            declared_commit_local=b.inputs.commit in local,source_audited=b.inputs.commit in commits,
            overlap_same_context=[asdict(p.inputs.key) for p in overlaps],
            removed_by_rounding_guard=[asdict(p.inputs.key) for p in near]))
    write_json(OUT/'data-audit.json',audits)
    collector=ROOT/'work/artifacts/ML_TCSP/long_running_test_suites/artifact'
    evidence={}
    for name,pattern in [('build_buildstats.py',r'int\(|failcount \+ passcount|revision'),
                         ('extract_test_result.py',r'SKIPPED|startswith|drop_duplicates|groupby|round\('),
                         ('get_build_testdata.py',r'testReport/api/json|build_query_url')]:
        p=collector/name
        evidence[name]=dict(sha256=file_sha256(p),lines=[dict(line=i,text=line.strip()) for i,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if re.search(pattern,line)])
    overlap={}
    for field in ('pr','commit'):
        values={s:{(r['key']['pr'] if field=='pr' else r['commit']) for r in selection if r['split']==s} for s in ('warmup','development','holdout')}
        overlap[field]=dict(holdout_seen_before=len(values['holdout'] & (values['warmup']|values['development'])))
    write_json(OUT/'audit-summary.json',dict(rows=len(builds),test_observations=sum(len(b.outcomes) for b in builds),
        split_counts=manifest['split_counts'],statuses=dict(Counter(b.result for b in builds)),
        missing_availability=sum(b.available_at is None for b in builds),
        count_mismatches=sum(not a['class_counts_match'] for a in audits),
        invalid_durations=sum(a['invalid_durations'] for a in audits),zero_durations=sum(a['zero_durations'] for a in audits),
        max_duration_sum_error=max(abs(a['duration_sum_error']) for a in audits),
        overlapping_builds=sum(bool(a['overlap_same_context']) for a in audits),
        rounding_guard_affected_builds=sum(bool(a['removed_by_rounding_guard']) for a in audits),
        unique_commits=len(all_shas),local_commits=len(local),raw_report_log_entries=raw_evidence,
        split_identity_overlap=overlap,collector_evidence=evidence))
    print(json.dumps(dict(frozen=True,rows=len(builds),splits=manifest['split_counts'],source_issue_report=str(OUT/'source-review.json')),indent=2))


if __name__=='__main__':
    main()
