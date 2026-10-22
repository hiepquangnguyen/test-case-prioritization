"""Verify source and data evidence; freeze design. Does not run any TCP method."""
import csv
import gzip
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tcp.domain import BuildKey
from tcp.lrts import file_sha256,load_builds
from scripts.pilot_support import conservative
from scripts.stage4_design_audit import OUT,PROJECTS,physical_split,write_json
from scripts.stage4_source_audit import batch_blobs,declaration,git


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    audit_manifest=read(OUT/'data-audit-manifest.json')
    assert audit_manifest['computed_method_scores'] is False
    for p,sha in audit_manifest['implementation_sha256'].items():assert file_sha256(ROOT/p)==sha
    checked_rows=checked_sources=checked_history=checked_annotations=0
    frozen_files=[]
    for project in PROJECTS:
        directory=OUT/project
        selection=read(directory/'selection.json');audits=read(directory/'build-audit.json')
        summary=read(directory/'summary.json');source_summary=read(directory/'source-summary.json')
        raw,metadata=load_builds(ROOT/'references/artifacts/dante/ML_TCSP.zip',project,len(selection))
        builds=tuple(conservative(b) for b in raw);lookup={b.inputs.key:b for b in builds}
        assign,_,bounds=physical_split(metadata)
        assert bounds==summary['split_boundaries']
        assert len(builds)==len(selection)==len(audits)==summary['rows']
        assert len({b.inputs.key.physical for b in builds})==summary['physical_builds']
        assert file_sha256(directory/'selection.json')==audit_manifest['selections_sha256'][project]
        with gzip.open(directory/'history-readiness.jsonl.gz','rt',encoding='utf-8') as f:
            history_rows=[json.loads(l) for l in f]
        assert len(history_rows)==len(builds)
        for b,s,a,h in zip(builds,selection,audits,history_rows):
            assert asdict(b.inputs.key)==s['key']==a['key']==h['key']
            assert s['cutoff']==b.inputs.cutoff and s['commit']==b.inputs.commit and s['branch']==b.inputs.branch
            assert s['split']==a['split']==assign[b.inputs.key.physical]
            assert a['tests']==len(b.outcomes) and a['failures']==sum(o.failed is True for o in b.outcomes)
            assert a['counts_match'] and a['invalid_durations']==0 and a['unknown_outcomes']==0
            assert abs(a['duration_sum_error'])<1e-7 and a['available_at']==b.available_at
            expected=sorted((p for p in builds if p.usable and p.available_at is not None and p.available_at<b.inputs.cutoff
                and p.inputs.context==b.inputs.context and bool(b.inputs.branch) and p.inputs.key.physical!=b.inputs.key.physical),
                key=lambda p:(p.available_at,p.inputs.key))
            assert h['eligible_builds']==[asdict(p.inputs.key) for p in expected]
            assert a['history_build_stages']==len(expected)
            known={o.test_id for p in expected for o in p.outcomes if o.failed is not None}
            assert a['history_cold_tests']==sum(t.test_id not in known for t in b.inputs.tests)
            checked_rows+=1;checked_history+=len(expected)
        assert all(s['split']=='warmup' for s in selection if s['source_sample'])
        assert len({tuple(s['key'][k] for k in ('project','pr','build')) for s in selection if s['source_sample']})==20
        with (directory/'source-mapping.csv').open(encoding='utf-8',newline='') as f:mapped=list(csv.DictReader(f))
        assert file_sha256(directory/'source-mapping.csv')==source_summary['source_mapping_sha256']
        assert file_sha256(ROOT/'scripts/stage4_source_audit.py')==source_summary['script_sha256']
        assert Counter(r['status'] for r in mapped)==source_summary['statuses']
        selected={BuildKey(**s['key']) for s in selection if s['source_sample']}
        identity={(b.inputs.key,o.test_id) for b in builds if b.inputs.key in selected for o in b.outcomes}
        mapped_identity={(BuildKey(r['project'],r['pr'],r['build'],r['stage']),r['test_id']) for r in mapped}
        assert len(mapped_identity)==len(mapped) and identity==mapped_identity
        assert len(mapped)==source_summary['observations']
        checked_annotations+=len(mapped)
        assert sum(r['failed_record']=='True' for r in mapped)==source_summary['failure_observations']
        repo=ROOT/'work/sources'/f'{project}.git';trees={};oids=set()
        for sha in {r['commit'] for r in mapped}:
            paths={}
            for item in git(repo,'ls-tree','-rz',sha).stdout.split(b'\0'):
                if item:
                    header,path=item.split(b'\t',1);_,kind,oid=header.decode().split()
                    if kind=='blob':paths[path.decode()]=oid
            trees[sha]=paths
        for r in mapped:
            if r['status']=='matched_declared_revision':oids.add(trees[r['commit']][r['source_paths']])
        blobs=batch_blobs(repo,oids)
        for r in mapped:
            key=BuildKey(r['project'],r['pr'],r['build'],r['stage'])
            assert lookup[key].inputs.commit==r['commit'] and r['execution_revision_verified']=='False'
            outcome=next(o for o in lookup[key].outcomes if o.test_id==r['test_id'])
            assert (r['failed_record']=='True')==(outcome.failed is True)
            if r['status']=='matched_declared_revision':
                blob=blobs[trees[r['commit']][r['source_paths']]]
                assert hashlib.sha256(blob).hexdigest()==r['source_sha256'] and declaration(blob,r['test_id'])
                checked_sources+=1
            elif r['status']=='ambiguous':assert len(r['source_paths'].split(';'))>1
        for c in read(directory/'source-config-evidence.json'):
            if c['status']=='available':assert file_sha256(directory/'source-evidence'/c['commit']/c['path'])==c['sha256']
        frozen_files.extend(directory/name for name in ('selection.json','build-audit.json','summary.json',
            'history-readiness.jsonl.gz','source-mapping.csv','source-summary.json','source-config-evidence.json'))
        print(project,'verified',len(builds),'rows and',len(mapped),'source annotations',flush=True)
    scale=read(OUT/'objective-scale.json')
    assert scale['no_new_rankings_or_metrics'] and scale['builds']==317
    assert scale['feature_sha256']==file_sha256(ROOT/'reports/stage3/karaf/features.jsonl.gz')
    for row in scale['rows']:
        assert math.isclose(row['normalized_modular_total'],1.0 if row['Q']>0 else 0.0,abs_tol=1e-12)
    config=read(ROOT/'configs/hc-falcon-v1.json');evaluation=read(ROOT/'configs/evaluation-v1.json')
    assert config['implementation_status']=='specified_not_implemented' and config['alpha']==.5
    assert config['primary_method']==evaluation['primary_method']=='hc_falcon_normalized_v1'
    assert config['reference_method']=='hc_falcon_topic_raw_v1'
    assert evaluation['holm_primary_family_size']==len(evaluation['primary_comparators'])*len(evaluation['primary_confirmation_projects'])
    previous=read(ROOT/'reports/stage3/karaf/manifest.json')
    for p,sha in previous['code_sha256'].items():assert file_sha256(ROOT/p)==sha,'Changed stage3 code'
    assert file_sha256(ROOT/'docs/03-pilot/protocol-v2.md')==previous['protocol_sha256']
    for document in (ROOT/'docs/04-design').glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',document.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                resolved = (document.parent/target.split('#')[0]).resolve()
                if resolved in ((OUT/'verification.json').resolve(), (OUT/'design-freeze.json').resolve()):
                    continue
                assert resolved.exists(),(document,target)
    frozen_files.extend([ROOT/'configs/hc-falcon-v1.json',ROOT/'configs/evaluation-v1.json',
        ROOT/'docs/04-design/hc-falcon-v1.md',ROOT/'docs/04-design/evaluation-protocol.md',
        ROOT/'docs/04-design/related-work.md',OUT/'objective-scale.json',ROOT/'scripts/pilot_support.py',
        *sorted((ROOT/'scripts').glob('stage4_*.py')),*sorted((ROOT/'tcp').glob('*.py')),
        ROOT/'tests/test_stage4.py'])
    hashes={str(p.relative_to(ROOT)):file_sha256(p) for p in frozen_files}
    freeze=dict(design='stage4-v1',files_sha256=hashes,archive=audit_manifest['archive'],
        confirmation_status='NOT_OPENED; implementation gate pending',
        normalization_change='Primary HC-N divides q by Q; topic-raw retained as explicit comparator')
    freeze_path=OUT/'design-freeze.json'
    if freeze_path.exists():
        old=read(freeze_path)
        assert {k:v for k,v in old.items() if k!='created_at'}==freeze,'Frozen design/evidence changed; version it explicitly'
    else:write_json(freeze_path,dict(created_at=datetime.now(timezone.utc).isoformat(),**freeze))
    write_json(OUT/'verification.json',dict(status='passed',dataset_rows_verified=checked_rows,
        source_annotations_verified=checked_annotations,matched_source_blobs_verified_per_observation=checked_sources,
        history_evidence_edges_checked=checked_history,physical_split_and_stage_integrity=True,
        full_sample_inventory_preserved=True,source_at_declared_sha_verified=True,
        execution_revision_verified=False,computed_HC_rankings=0,confirmation_opened=False,
        previous_stage3_code_and_protocol_unchanged=True,
        design_freeze_sha256=file_sha256(freeze_path)))
    print(json.dumps(dict(status='passed',rows=checked_rows,matched_source_observations=checked_sources,
        history_edges=checked_history,confirmation_opened=False),indent=2))


if __name__=='__main__':main()
