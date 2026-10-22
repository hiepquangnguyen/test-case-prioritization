"""Verify stage-1 evidence and upstream immutability. No model rerun required."""
import argparse
import csv
import io
import json
import math
import zipfile

from stage1_audit import ROOT, OUT, data_pickle, independent_apfd, write_json


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--allow-pending-full',action='store_true')
    args=parser.parse_args()
    passed=[]
    def check(label,condition):
        if not condition:
            raise AssertionError(label)
        passed.append(label)
    archives=read('archives.json')
    check('Both archive checksums match',all(a['md5_matches_manifest'] for a in archives))
    f=read('falcon-data-audit.json')
    check('Six FALCON projects and 288 project-scoped faults',len(f)==6 and sum(r['faults'] for r in f)==288)
    check('FALCON indices and method identifiers consistent',all(r['mapping_indices_exact'] and r['index_list_indices_exact'] and r['index_list_mismatches']==r['fault_keys_outside_suite']==r['duplicate_identifiers']==r['blank_lines']==0 for r in f))
    c=read('falcon-csv-pickle-check.json')
    check('Independent source and fault representations agree',all(r['csv_to_pickle_mismatches']==r['source_to_bbox_mismatches']==0 for r in c))
    authors=read('falcon-author-ranking-checks.json')
    check('All 60 supplied rankings/APFDs verified',len(authors)==60 and all(r['valid_permutation'] and r['absolute_difference']==0 for r in authors))
    small=read('falcon-chart-first-16-smoke.json')
    check('Real encoder smoke has 16x768 finite embeddings and equal greedy orders',small['embedding_shape']==[16,768] and small['valid_permutation'] and small['standard_greedy_equal'])
    # Independent metric invariants, including rejecting incomplete ranking.
    faults={0:[1,2],1:[2],2:[]}
    check('APFD hand example',math.isclose(independent_apfd([0,1,2],faults),5/6))
    try:
        independent_apfd([2],faults)
    except ValueError:
        passed.append('APFD refuses missing faults rather than shrinking denominator')
    else:
        raise AssertionError('Incomplete ranking accepted')
    projects=read('lrts-project-audit.json')
    coverage=read('lrts-coverage.json')
    check('All LRTS metadata references have raw CSV',sum(r['metadata_rows'] for r in projects)==coverage['metadata_rows']==108366 and all(r['raw_builds']==r['metadata_rows'] for r in projects))
    check('No duplicate metadata/test IDs or invalid raw durations/outcomes',all(all(r[k]==0 for k in ('duplicate_metadata_keys','duplicate_test_ids','invalid_duration','negative_duration','unknown_outcomes')) for r in projects))
    check('TVM count discrepancy remains visible',next(r for r in projects if r['project']=='tvm')['metadata_count_mismatches']==26833)
    check('Java candidate metadata counts agree',all(r['metadata_count_mismatches']==0 for r in projects if r['project'] in ('karaf','activemq','log4j')))
    source=read('karaf-source-summary.json')
    check('Twenty build source audit with 18 fetched commits',len(source['builds'])==20 and source['unique_commits']==18 and source['fetch_error'] is None and all(r['java_tree_entries']>0 for r in source['builds']))
    check('Unmapped test/failure not silently dropped',sum(r['matched'] for r in source['builds'])==3697 and sum(r['tests'] for r in source['builds'])==3740 and sum(r['failing_matched'] for r in source['builds'])==17 and sum(r['failures'] for r in source['builds'])==18)
    dante=read('dante-smoke.json')
    order=read('dante-ranking.json')
    check('DANTE ranking valid on its declared filtered universe',len(order)==len(set(order))==dante['ranked_tests']==206)
    check('DANTE exclusion of a failure recorded',dante['original_tests']==212 and dante['excluded_failures']==1)
    check('DANTE metric difference explained exactly',math.isclose(dante['artifact_apfdc']-dante['midpoint_apfdc'],1/(2*206),abs_tol=1e-12))
    check('Current-duration and group-boundary diagnostics reproduced',dante['current_duration_changes_dante_score'] and dante['sticky_group_boundary_witness']['first_B_inherits_A'])
    # Confirm the code invoked by the smoke adapters is still byte-identical.
    checked_files=0
    for label,filename,prefix in [('falcon','falcon.zip','falcon/py/'),('dante','ML_TCSP.zip','ML_TCSP/src/')]:
        with zipfile.ZipFile(ROOT/'references/artifacts'/label/filename) as z:
            for n in z.namelist():
                if n.startswith(prefix) and n.endswith('.py') and n.count('/')==2:
                    local=ROOT/'work/artifacts'/n
                    check('Upstream unchanged: '+n,local.read_bytes()==z.read(n))
                    checked_files+=1
    full_path=OUT/'falcon-chart-full-smoke.json'
    full_status='pending'
    if full_path.exists():
        full=read(full_path.name)
        run=ROOT/'work/runs/falcon/chart-full'
        order=json.loads((run/'ranking.json').read_text())
        faults=data_pickle((ROOT/'work/artifacts/falcon/input/Chart/fault_matrix.pickle').read_bytes())
        check('Full Chart is a permutation of all 2193 test indices',len(order)==2193 and set(order)==set(range(2193)))
        check('Full Chart APFD agrees with independent recalculation',math.isclose(full['apfd'],independent_apfd(order,faults),abs_tol=1e-12))
        if (OUT/'falcon-chart-full-cold-run.json').exists():
            cold=read('falcon-chart-full-cold-run.json')
            check('Cold and cached runs agree on APFD',cold['apfd']==full['apfd'])
            check('Python process exits successfully with clean logging',read('falcon-process-exit.json')['python_exit_code']==0)
        check('Negative cosine entries are exposed in full-suite evidence',full['negative_similarities']>0 and full['similarity_min']<0)
        full_status='passed'
    elif not args.allow_pending_full:
        raise AssertionError('Full Chart run has not completed')
    report=(ROOT/'docs/01-feasibility/stage1-report.md').read_text(encoding='utf-8')
    check('Report exposes TVM discrepancy and baseline limitations','26.833' in report and 'placeholder' in report and '206' in report)
    result=dict(passed_checks=passed,check_count=len(passed),upstream_python_files_verified=checked_files,full_chart_status=full_status,note='Checks confirm evidence and known limitations; no claim of HC-FALCON effectiveness or baseline correctness.')
    write_json('verification.json',result)
    print(json.dumps(dict(checks=len(passed),upstream_files=checked_files,full_chart=full_status)))


if __name__=='__main__':
    main()
