"""Read-only dataset audit and outcome-independent physical-build splits. No ranking."""
import csv
import gzip
import io
import json
import math
import sys
import zipfile
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tcp.lrts import PREFIX, file_sha256, load_builds, verify_archive
from tcp.history import HistoryConfig, RollingHistory
from scripts.pilot_support import conservative

OUT=ROOT/'reports/stage4'
PROJECTS=('activemq','log4j')


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def physical_split(rows):
    """20% warmup, next 30% development, remainder reserved. Never split timestamp ties."""
    groups={}
    for r in rows:
        key=(r['project'],r['pr_name'],r['build_id'])
        stamp=float(r['build_timestamp'])
        if not math.isfinite(stamp):raise ValueError('Invalid timestamp')
        if key in groups and groups[key]!=stamp:raise ValueError('Stages disagree on build start')
        groups[key]=stamp
    ordered=sorted(groups,key=lambda k:(groups[k],k))
    if len(ordered)<10:raise ValueError('Insufficient physical builds for this pilot split')
    first=groups[ordered[math.ceil(.2*len(ordered))]]
    second=groups[ordered[math.ceil(.5*len(ordered))]]
    if first>=second:raise ValueError('Timestamp ties collapse split boundaries')
    assign={k:('warmup' if t<first else 'development' if t<second else 'reserved_confirmation') for k,t in groups.items()}
    if len(set(assign.values()))!=3:raise ValueError('Empty split')
    return assign,ordered,dict(development_start=first,confirmation_start=second,
        development_start_utc=datetime.fromtimestamp(first,timezone.utc).isoformat(),
        confirmation_start_utc=datetime.fromtimestamp(second,timezone.utc).isoformat())


def main():
    archive=ROOT/'references/artifacts/dante/ML_TCSP.zip'
    print('Checking pinned ZIP...',flush=True)
    hashes=verify_archive(archive)
    with zipfile.ZipFile(archive) as z:
        allrows=list(csv.DictReader(io.StringIO(z.read(PREFIX+'dataset.csv').decode('utf-8-sig'))))
        names=z.namelist()
    project_summaries=[]
    for project in PROJECTS:
        rows=sorted((r for r in allrows if r['project']==project),key=lambda r:(float(r['build_timestamp']),r['pr_name'],r['build_id'],r['stage_id']))
        splits,ordered,bounds=physical_split(rows)
        sample=set(ordered[:20])
        selection=[dict(key=dict(project=project,pr=r['pr_name'],build=r['build_id'],stage=r['stage_id']),
            branch=r['pr_base_branch'],commit=r['build_head_sha'],cutoff=float(r['build_timestamp']),
            split=splits[(project,r['pr_name'],r['build_id'])],
            source_sample=(project,r['pr_name'],r['build_id']) in sample) for r in rows]
        path=OUT/project/'selection.json'
        if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=selection:
            raise ValueError('Existing selection differs; do not overwrite a frozen cohort')
        write_json(path,selection)
        # The split above is fixed solely from metadata identity and timestamps,
        # before reading test outcomes/durations below. No method score is computed.
        builds,_=load_builds(archive,project,len(rows))
        builds=tuple(conservative(b) for b in builds)
        keymap={b.inputs.key:b for b in builds}
        physical={}
        for b in builds:physical.setdefault(b.inputs.key.physical,[]).append(b)
        inconsistency=[]
        for key,stages in physical.items():
            if len({(b.inputs.cutoff,b.available_at,b.inputs.commit,b.inputs.branch,b.result) for b in stages})!=1:
                inconsistency.append(key)
        if inconsistency:raise ValueError('Inconsistent metadata across physical-build stages: '+repr(inconsistency))
        history=RollingHistory()
        for b in builds:history.observe(b)
        evidence=[]
        with gzip.open(OUT/project/'history-readiness.jsonl.gz','wt',encoding='utf-8') as f:
            for i,(b,r) in enumerate(zip(builds,rows)):
                snap=history.snapshot(b.inputs)
                eligible=snap.eligible_builds
                assert all(keymap[k].available_at<b.inputs.cutoff and keymap[k].usable and
                    keymap[k].inputs.context==b.inputs.context and k.physical!=b.inputs.key.physical for k in eligible)
                overlapping=[p.inputs.key for p in builds if p.inputs.cutoff<b.inputs.cutoff and p.available_at is not None
                             and p.available_at>=b.inputs.cutoff and p.inputs.context==b.inputs.context]
                fail=sum(o.failed is True for o in b.outcomes);passed=sum(o.failed is False for o in b.outcomes)
                costs=[o.duration for o in b.outcomes]
                valid=all(c is not None and c>=0 for c in costs)
                rawmatch=passed==int(r['num_pass_class']) and fail==int(r['num_fail_class'])
                data=dict(key=asdict(b.inputs.key),physical=list(b.inputs.key.physical),split=splits[b.inputs.key.physical],
                    cutoff=b.inputs.cutoff,available_at=b.available_at,status=b.result,tests=len(costs),
                    failures=fail,unknown_outcomes=sum(o.failed is None for o in b.outcomes),
                    invalid_durations=sum(c is None or c<0 for c in costs),zero_durations=costs.count(0),
                    total_test_seconds=math.fsum(costs) if valid else None,
                    duration_sum_error=math.fsum(costs)-float(r['test_suite_duration_s']) if valid else None,
                    counts_match=rawmatch,history_build_stages=len(eligible),
                    history_cold_tests=sum(x.observations==0 for x in snap.features),
                    history_low_tests=sum(0<x.observations<5 for x in snap.features),
                    duration_fallbacks=dict(Counter(x.duration_origin for x in snap.features)),
                    overlapping_same_context=[asdict(k) for k in overlapping],
                    source_sample=b.inputs.key.physical in sample)
                evidence.append(data)
                f.write(json.dumps(dict(key=data['key'],eligible_builds=[asdict(k) for k in eligible],
                                       latest_evidence=snap.latest_evidence_available_at),allow_nan=False)+'\n')
                if (i+1)%100==0:print(project,'audited',i+1,'/',len(builds),flush=True)
        write_json(OUT/project/'build-audit.json',evidence)
        split_summary=[]
        for split in ('warmup','development','reserved_confirmation'):
            e=[a for a in evidence if a['split']==split]
            usable=[a for a in e if a['status'] in ('SUCCESS','FAILURE','UNSTABLE')]
            split_summary.append(dict(split=split,rows=len(e),physical_builds=len({tuple(a['physical']) for a in e}),
                eligible_physical_builds=len({tuple(a['physical']) for a in usable}),
                failing_stage_rows=sum(a['failures']>0 for a in usable),
                failing_physical_builds=len({tuple(a['physical']) for a in usable if a['failures']>0}),
                tests=sum(a['tests'] for a in e),cold_tests=sum(a['history_cold_tests'] for a in e),
                no_history_stage_rows=sum(a['history_build_stages']==0 for a in e)))
        before={r['commit'] for r in selection if r['split']!='reserved_confirmation'}
        confirmed={r['commit'] for r in selection if r['split']=='reserved_confirmation'}
        before_pr={r['key']['pr'] for r in selection if r['split']!='reserved_confirmation'}
        confirm_pr={r['key']['pr'] for r in selection if r['split']=='reserved_confirmation'}
        sizes=[len(b.outcomes) for b in builds]
        summary=dict(project=project,rows=len(rows),physical_builds=len(physical),unique_commits=len({b.inputs.commit for b in builds}),
            branches=dict(Counter(b.inputs.branch for b in builds)),stages=dict(Counter(b.inputs.key.stage for b in builds)),
            statuses=dict(Counter(b.result for b in builds)),test_observations=sum(sizes),
            suite_size=dict(min=min(sizes),median=median(sizes),max=max(sizes)),
            dense_similarity_float32_max_bytes=4*max(sizes)**2,
            missing_availability=sum(b.available_at is None for b in builds),
            unknown_outcomes=sum(a['unknown_outcomes'] for a in evidence),
            invalid_durations=sum(a['invalid_durations'] for a in evidence),
            zero_durations=sum(a['zero_durations'] for a in evidence),
            count_mismatches=sum(not a['counts_match'] for a in evidence),
            max_duration_sum_error=max(abs(a['duration_sum_error'] or 0) for a in evidence),
            overlap_stage_rows=sum(bool(a['overlapping_same_context']) for a in evidence),
            split_boundaries=bounds,splits=split_summary,confirmation_prior_commit_overlap=len(before&confirmed),
            confirmation_prior_pr_overlap=len(before_pr&confirm_pr),
            source_sample_physical_builds=len(sample),source_sample_rows=sum(r['source_sample'] for r in selection),
            source_sample_commits=len({r['commit'] for r in selection if r['source_sample']}),
            raw_build_report_entries=[n for n in names if f'/{project}/' in n and ('/PR/PR-' in n or 'test_report.csv' in n)],
            claim_scope='observed postprocessed class replay; raw start/publication/inventory/revision unverified',
            score_exposure='No ranking or method metric computed; aggregate outcome counts inspected for audit only')
        write_json(OUT/project/'summary.json',summary);project_summaries.append(summary)
    write_json(OUT/'data-audit-manifest.json',dict(created_at=datetime.now(timezone.utc).isoformat(),archive=hashes,
        split_rule='Physical build chronology: first 20% warmup, next 30% development, remaining reserved; ties stay together',
        source_rule='First 20 physical builds, all stages; no outcome filtering',
        history_config=asdict(HistoryConfig()),availability_guard_seconds=2,
        implementation_sha256={str(p.relative_to(ROOT)):file_sha256(p) for p in [Path(__file__),*sorted((ROOT/'tcp').glob('*.py'))]},
        selections_sha256={p:file_sha256(OUT/p/'selection.json') for p in PROJECTS},
        computed_method_scores=False))
    print(json.dumps([dict(project=s['project'],rows=s['rows'],physical=s['physical_builds'],splits=s['splits']) for s in project_summaries],indent=2))


if __name__=='__main__':main()
