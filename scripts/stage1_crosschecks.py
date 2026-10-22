"""Cross-check independent representations and history lineage (stdlib only)."""
import collections
import csv
import io
import json
import re
import zipfile

from stage1_audit import ROOT, OUT, PROJECTS, LRTS, data_pickle, raw_name, raw_rows, write_json


def falcon():
    results=[]
    for project in PROJECTS:
        base=ROOT/'work/artifacts/falcon'
        p=base/'projects'/('mokito' if project=='Mockito' else project.lower())/'bug_data'
        mapping=json.loads((base/'input'/project/'test_method_mapping.json').read_text())['index_to_method']
        faults=data_pickle((base/'input'/project/'fault_matrix.pickle').read_bytes())
        with (p/(project+'_fault_matrix.csv')).open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        columns=list(rows[0])[1:]
        lookup={r['']:r for r in rows}
        extracted=json.loads((p/'extracted_test_methods.json').read_text(encoding='utf-8'))
        sources={r['className']+'::'+r['testCase']:r['code'] for r in extracted}
        bbox=(base/'input'/project/(project+'-bbox.txt')).read_text(encoding='utf-8').splitlines()
        mismatches=[]
        source_mismatches=[]
        for key,method in mapping.items():
            row=lookup.get(method['fullIdentifier'])
            expected=[] if row is None else [int(c.rsplit('_',1)[1]) for c in columns if row[c]=='1']
            actual=faults.get(int(key),[])
            if set(expected)!=set(actual):
                mismatches.append(dict(test_index=int(key),expected=expected,actual=actual))
            # Whitespace comparison checks the provided extracted source, not a fresh D4J checkout.
            normalize=lambda s: re.sub(r'\s+',' ',s).strip()
            if normalize(sources.get(method['fullIdentifier'],''))!=normalize(bbox[int(key)]):
                source_mismatches.append(int(key))
        results.append(dict(project=project,csv_rows=len(rows),csv_fault_columns=len(columns),mapped_fault_columns=sum(any(r[c]=='1' for r in rows) for c in columns),csv_to_pickle_mismatches=len(mismatches),examples=mismatches[:3],extracted_source_rows=len(extracted),source_to_bbox_mismatches=len(source_mismatches),source_examples=source_mismatches[:10]))
    write_json('falcon-csv-pickle-check.json',results)


def history():
    selection=json.loads((OUT/'karaf-pilot-selection.json').read_text())['rows']
    diagnostics=[]
    with zipfile.ZipFile(ROOT/'references/artifacts/dante/ML_TCSP.zip') as z:
        rows=list(csv.DictReader(io.StringIO(z.read(LRTS+'dataset.csv').decode())))
        all_rows=sorted((r for r in rows if r['project']=='karaf'),key=lambda r:(float(r['build_timestamp']),r['pr_name'],r['build_id'],r['stage_id']))
        processed_names=sorted(n for n in z.namelist() if n.startswith('ML_TCSP/src/processed_builds/karaf_') and n.endswith('.json'))
        raw_cache={}
        def raw(row):
            name=raw_name(row)
            if name not in raw_cache:
                raw_cache[name]={r['testclass']:r for r in raw_rows(z,name)}
            return raw_cache[name]
        for row in selection:
            stamp=float(row['build_timestamp'])
            earlier=[r for r in all_rows if float(r['build_timestamp'])<stamp]
            not_completed=[r for r in earlier if float(r['build_timestamp'])+float(r['build_duration'])>=stamp]
            prefix=f"karaf_build_{row['pr_name']}_{row['build_id']}_{row['stage_id']}_"
            matches=[n for n in processed_names if n.rsplit('/',1)[-1].startswith(prefix)]
            rec=dict(pr_name=row['pr_name'],build_id=row['build_id'],stage_id=row['stage_id'],earlier_start_rows=len(earlier),not_completed_under_start_plus_duration=len(not_completed),processed_matches=len(matches),processed_raw_mismatches=None,history_field_disagreements_with_previous_raw_builds=None,history_fields_unknown_in_raw=None,excluded_by_upstream=None)
            if matches:
                d=json.loads(z.read(matches[0]))
                cases=d['test_cases']
                current=raw(row)
                mismatches=[]
                history_mismatch=unknown=checked=0
                excluded=[]
                for name,tc in cases.items():
                    r=current.get(name)
                    if r is None or tc['outcome']!=int(r['outcome']) or abs(tc['duration']-float(r['duration']))>1e-9:
                        mismatches.append(name)
                    if not tc.get('source_file_found') or tc.get('duration',0)<=0:
                        excluded.append(dict(test_id=name,outcome=tc['outcome'],duration=tc['duration'],source_file_found=tc.get('source_file_found')))
                    for lag in range(1,11):
                        key=f'last_outcome_{lag}'
                        if key not in tc: continue
                        checked+=1
                        past=raw(earlier[-lag]).get(name) if len(earlier)>=lag else None
                        if past is None:
                            unknown+=1
                        elif int(past['outcome'])!=tc[key]:
                            history_mismatch+=1
                rec.update(processed_raw_mismatches=mismatches,raw_tests_absent_from_processed=sorted(set(current)-set(cases)),sha_matches=d.get('build_commit_sha')==row['build_head_sha'],history_field_disagreements_with_previous_raw_builds=history_mismatch,history_fields_checked=checked,history_fields_unknown_in_raw=unknown,excluded_by_upstream=excluded)
            diagnostics.append(rec)
    write_json('karaf-history-crosscheck.json',dict(definition='Compare bundled last_outcome_N to Nth earlier raw metadata row by start time; discrepancies diagnose semantics, not proof of future leakage. Completion estimate assumes Jenkins timestamp=start and build_duration=seconds; raw build JSON not bundled.',builds=diagnostics))


def tvm_examples():
    selected=[]
    with (OUT/'lrts-build-audit.csv').open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['project']=='tvm' and row['metadata_counts_match']=='False':
                selected.append(row)
                if len(selected)==3:
                    break
    results=[]
    with zipfile.ZipFile(ROOT/'references/artifacts/dante/ML_TCSP.zip') as z:
        metadata=list(csv.DictReader(io.StringIO(z.read(LRTS+'dataset.csv').decode())))
        lookup={raw_name(r):r for r in metadata}
        for row in selected:
            meta=lookup[row['raw_member']]
            raw=raw_rows(z,row['raw_member'])
            results.append(dict(raw_member=row['raw_member'],metadata_pass=meta['num_pass_class'],metadata_fail=meta['num_fail_class'],raw_pass=sum(t['outcome']=='0' for t in raw),raw_fail=sum(t['outcome']=='1' for t in raw),stage_id=meta['stage_id'],first_test_ids=[t['testclass'] for t in raw[:3]]))
    write_json('tvm-count-mismatch-examples.json',results)


if __name__=='__main__':
    falcon()
    history()
    tvm_examples()
