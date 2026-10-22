"""Verify the first 20 chronological Karaf build rows against commit-pinned Java blobs.

Requires the local bare clone work/sources/karaf.git; --fetch needs network.
No checkout or execution of project code. Source matching is conservative (exact
package/class suffix, with nested-class outer source fallback); missing/generated
sources remain explicit. Output is evidence for feasibility, not a Java parser.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

from stage1_audit import ROOT, OUT, LRTS, raw_name, raw_rows, write_json, write_csv

REPO = ROOT / 'work/sources/karaf.git'


def git(*args, binary=False):
    result = subprocess.run(['git','--git-dir',str(REPO),*args],capture_output=True,check=True)
    return result.stdout if binary else result.stdout.decode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch',action='store_true')
    args = parser.parse_args()
    with zipfile.ZipFile(ROOT/'references/artifacts/dante/ML_TCSP.zip') as z:
        metadata = list(csv.DictReader(io.StringIO(z.read(LRTS+'dataset.csv').decode())))
        selected = sorted((r for r in metadata if r['project']=='karaf'),key=lambda r:(float(r['build_timestamp']),r['pr_name'],r['build_id'],r['stage_id']))[:20]
        write_json('karaf-pilot-selection.json',dict(rule='First 20 metadata rows by numeric timestamp, PR, build, stage; no outcome-based filtering',purpose='Technical feasibility only; not an effectiveness evaluation',rows=selected))
        shas = list(dict.fromkeys(r['build_head_sha'] for r in selected))
        fetch_error = None
        if args.fetch:
            try:
                print('Fetching',len(shas),'exact commits',flush=True)
                git('fetch','--depth=1','--filter=blob:limit=1m','origin',*shas)
            except subprocess.CalledProcessError as e:
                fetch_error = e.stderr.decode(errors='replace')
                print(fetch_error,flush=True)
        cache, records, summaries = {}, [], []
        blob_cache = {}
        for row in selected:
            sha = row['build_head_sha']
            commit_error = None
            if sha not in cache:
                try:
                    git('cat-file','-e',sha+'^{commit}')
                    tree = git('ls-tree','-rz',sha).split('\0')
                    entries = {}
                    for entry in tree:
                        if not entry: continue
                        head,path=entry.split('\t',1)
                        mode,kind,oid=head.split()
                        if kind=='blob' and path.endswith('.java'):
                            entries[path]=oid
                    cache[sha]=entries
                except subprocess.CalledProcessError as e:
                    cache[sha]={}
                    commit_error=e.stderr.decode(errors='replace')
            entries=cache[sha]
            tests=raw_rows(z,raw_name(row))
            count=fail_count=ambiguous=0
            for tc in tests:
                fqn=tc['testclass']
                outer=fqn.split('$',1)[0]
                suffix=outer.replace('.','/')+'.java'
                paths=[p for p in entries if p==suffix or p.endswith('/'+suffix)]
                status='missing'
                source_hash=None
                declaration=False
                if len(paths)>1:
                    status='ambiguous'
                    ambiguous+=1
                elif len(paths)==1:
                    oid=entries[paths[0]]
                    try:
                        if oid not in blob_cache:
                            # Disable implicit network fetch in the verification phase.
                            content=git('-c','remote.origin.promisor=false','cat-file','blob',oid,binary=True)
                            blob_cache[oid]=content
                        content=blob_cache[oid]
                        text=content.decode('utf-8',errors='replace')
                        pkg,_,cls=outer.rpartition('.')
                        declaration=bool(re.search(r'\bpackage\s+'+re.escape(pkg)+r'\s*;',text) and re.search(r'\b(?:class|interface|enum|record)\s+'+re.escape(cls)+r'\b',text))
                        status='matched' if declaration else 'declaration_unverified'
                        source_hash=hashlib.sha256(content).hexdigest()
                    except subprocess.CalledProcessError:
                        status='blob_unavailable'
                    if status=='matched':
                        count+=1
                        fail_count+=tc['outcome']=='1'
                records.append(dict(project='karaf',pr_name=row['pr_name'],build_id=row['build_id'],stage_id=row['stage_id'],commit_sha=sha,test_id=fqn,outcome=tc['outcome'],status=status,source_paths=';'.join(paths),source_sha256=source_hash,outer_declaration_verified=declaration))
            summaries.append(dict(pr_name=row['pr_name'],build_id=row['build_id'],stage_id=row['stage_id'],sha=sha,build_result=row['build_result'],tests=len(tests),matched=count,ambiguous=ambiguous,failures=sum(tc['outcome']=='1' for tc in tests),failing_matched=fail_count,java_tree_entries=len(entries),commit_error=commit_error))
            print(row['pr_name'],row['build_id'],count,'/',len(tests),'mapped',flush=True)
        write_csv('karaf-source-mapping.csv',records)
        write_json('karaf-source-summary.json',dict(repository='https://github.com/apache/karaf.git',fetch_error=fetch_error,unique_commits=len(shas),unique_blobs_read=len(blob_cache),builds=summaries))
        if fetch_error or any(r['commit_error'] for r in summaries):
            raise SystemExit('Source verification incomplete: see karaf-source-summary.json')


if __name__=='__main__':
    main()
