"""Fetch only selected SHAs if requested; map source without checkout/build/lazy fetch."""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage4_design_audit import OUT, PROJECTS, write_json
from tcp.lrts import PREFIX, file_sha256

REMOTES={'activemq':'https://github.com/apache/activemq.git','log4j':'https://github.com/apache/logging-log4j2.git'}


def git(repo,*args,input=None,check=True,timeout=180):
    result=subprocess.run(['git','--git-dir',str(repo),'-c','remote.origin.promisor=false',*args],input=input,
        capture_output=True,env=dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_TERMINAL_PROMPT='0'),timeout=timeout)
    if check and result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
    return result


def batch_blobs(repo,oids):
    if not oids:return {}
    result=git(repo,'cat-file','--batch',input=''.join(o+'\n' for o in sorted(oids)).encode())
    stream=io.BytesIO(result.stdout);blobs={}
    for oid in sorted(oids):
        header=stream.readline().decode().strip().split()
        if len(header)==2 and header[1]=='missing':continue
        if len(header)!=3 or header[0]!=oid or header[1]!='blob':raise ValueError('Invalid git batch record')
        content=stream.read(int(header[2]))
        if len(content)!=int(header[2]) or stream.read(1)!=b'\n':raise ValueError('Truncated git blob')
        blobs[oid]=content
    if stream.read():raise ValueError('Unexpected git output')
    return blobs


def declaration(content,fqn):
    # Conservative file/package + outer declaration check, not a Java AST or
    # proof that this file was executed. Matches inside comments are removed.
    text=content.decode('utf-8',errors='replace')
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    outer=fqn.split('$',1)[0];pkg,_,name=outer.rpartition('.')
    return bool(re.search(r'\bpackage\s+'+re.escape(pkg)+r'\s*;',text) and
                re.search(r'\b(?:class|interface|enum|record)\s+'+re.escape(name)+r'\b',text))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    for project in PROJECTS:
        selection=json.loads((OUT/project/'selection.json').read_text(encoding='utf-8'))
        selected=[r for r in selection if r['source_sample']]
        assert all(r['split']=='warmup' for r in selected)
        shas=list(dict.fromkeys(r['commit'] for r in selected))
        if len(shas)>20:raise ValueError('Source sample exceeds approved 20 physical builds')
        repo=ROOT/'work/sources'/f'{project}.git'
        if args.fetch:
            if not repo.exists():
                repo.mkdir(parents=True)
                subprocess.run(['git','init','--bare',str(repo)],check=True,capture_output=True)
                git(repo,'remote','add','origin',REMOTES[project])
            remote=git(repo,'remote','get-url','origin').stdout.decode().strip()
            if remote!=REMOTES[project]:raise ValueError('Unexpected origin')
            print(project,'fetching',len(shas),'pinned commits...',flush=True)
            result=git(repo,'fetch','--depth=1','--filter=blob:limit=1m','origin',*shas,check=False,timeout=300)
            write_json(OUT/project/'source-fetch.json',dict(remote=remote,commits=shas,returncode=result.returncode,
                stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace'),
                fetched_at=datetime.now(timezone.utc).isoformat()))
            if result.returncode:raise RuntimeError('Source fetch failed: '+result.stderr.decode(errors='replace'))
        trees={};needed=set();config_paths={}
        for sha in shas:
            tree=git(repo,'ls-tree','-rz',sha,check=False)
            paths={}
            if tree.returncode==0:
                for entry in tree.stdout.split(b'\0'):
                    if not entry:continue
                    head,path=entry.split(b'\t',1);mode,kind,oid=head.decode().split()
                    if kind=='blob':paths[path.decode('utf-8')]=oid
            trees[sha]=paths
            cfg=[p for p in paths if p in ('pom.xml','Jenkinsfile','.jenkins/Jenkinsfile','LICENSE','LICENSE.txt',
                 'activemq-unit-tests/pom.xml','activemq-unit-tests/src/test/java/org/apache/activemq/joramtests/JoramJmsTest.java') or
                 (p.endswith(('.groovy','.yml','.yaml')) and ('jenkins' in p.lower() or p.startswith('.github/workflows/')))]
            config_paths[sha]=cfg
            needed.update(paths[p] for p in cfg)
        raw_by_key={};candidates={}
        with zipfile.ZipFile(ROOT/'references/artifacts/dante/ML_TCSP.zip') as z:
            for row in selected:
                k=row['key'];sha=row['commit']
                name=PREFIX+f"artifact/processed_test_result/{project}/{k['pr'].replace('/','_')}_build{k['build']}/stage_{k['stage']}/test_class.csv.zip"
                with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                    csvnames=[n for n in inner.namelist() if n.endswith('test_class.csv')]
                    if len(csvnames)!=1:raise ValueError('Ambiguous raw CSV')
                    raw=list(csv.DictReader(io.StringIO(inner.read(csvnames[0]).decode('utf-8-sig'))))
                key=(k['pr'],k['build'],k['stage']);raw_by_key[key]=raw
                for test in raw:
                    tid=test['testclass'];suffix=tid.split('$',1)[0].replace('.','/')+'.java'
                    paths=[p for p in trees[sha] if p==suffix or p.endswith('/'+suffix)]
                    candidates[(sha,tid)]=paths
                    needed.update(trees[sha][p] for p in paths)
        blobs=batch_blobs(repo,needed) if repo.exists() else {}
        records=[];config=[]
        for sha,paths in config_paths.items():
            for path in paths:
                oid=trees[sha][path];content=blobs.get(oid)
                if content is None:
                    config.append(dict(commit=sha,path=path,status='blob_unavailable'));continue
                evidence=OUT/project/'source-evidence'/sha/path
                evidence.parent.mkdir(parents=True,exist_ok=True);evidence.write_bytes(content)
                snippets=[dict(line=i,text=line.strip()) for i,line in enumerate(content.decode('utf-8',errors='replace').splitlines(),1)
                    if re.search(r'mvn |junit\(|surefire|failsafe|<module>|<testSourceDirectory>|generate-test|checkout|skipTests|joram|org.objectweb',line)]
                config.append(dict(commit=sha,path=path,status='available',sha256=hashlib.sha256(content).hexdigest(),lines=snippets))
        for row in selected:
            k=row['key'];sha=row['commit']
            for test in raw_by_key[(k['pr'],k['build'],k['stage'])]:
                tid=test['testclass'];paths=candidates[(sha,tid)];status='missing';sha256=None
                if not trees[sha]:status='commit_unavailable'
                elif len(paths)>1:status='ambiguous'
                elif len(paths)==1:
                    content=blobs.get(trees[sha][paths[0]])
                    if content is None:status='blob_unavailable'
                    else:
                        sha256=hashlib.sha256(content).hexdigest()
                        status='matched_declared_revision' if declaration(content,tid) else 'declaration_unverified'
                records.append(dict(project=project,pr=k['pr'],build=k['build'],stage=k['stage'],commit=sha,test_id=tid,
                    status=status,source_paths=';'.join(paths),source_sha256=sha256,
                    source_kind_hint='external_test_dependency_candidate' if tid.startswith('org.objectweb.jtests.') else 'repository_source_candidate',
                    failed_record=test['outcome']=='1',outer_fallback='$' in tid,
                    suspected_runner_event=tid.startswith('org.apache.maven.surefire.'),
                    execution_revision_verified=False))
        with (OUT/project/'source-mapping.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,list(records[0]));writer.writeheader();writer.writerows(records)
        write_json(OUT/project/'source-config-evidence.json',config)
        failures=[r for r in records if r['failed_record']]
        summary=dict(project=project,sample_rule='First 20 physical warmup builds; all stages',sample_rows=len(selected),
            sample_commits=len(shas),available_commit_trees=sum(bool(p) for p in trees.values()),
            observations=len(records),statuses=dict(Counter(r['status'] for r in records)),
            failure_observations=len(failures),failure_statuses=dict(Counter(r['status'] for r in failures)),
            unique_source_blobs=len({r['source_sha256'] for r in records if r['source_sha256']}),
            outer_fallback_observations=sum(r['outer_fallback'] for r in records),
            unresolved_test_ids=sorted({r['test_id'] for r in records if r['status']!='matched_declared_revision'}),
            source_mapping_sha256=file_sha256(OUT/project/'source-mapping.csv'),
            selection_sha256=file_sha256(OUT/project/'selection.json'),script_sha256=file_sha256(Path(__file__)),
            no_checkout_or_test_execution=True,source_execution_revision_verified=False,
            conclusion='Coverage at declared metadata SHA on an early sample only; no claim of full-cohort source readiness')
        write_json(OUT/project/'source-summary.json',summary)
        print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
