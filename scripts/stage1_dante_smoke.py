"""Exercise the original DANTE prioritization runner on one pinned processed build.

Select the earliest Karaf processed build that has raw history. Isolated input
directory prevents MOST_FAILURES selection. tfidf matches the bundled data.
LTR is unavailable in this single-target fixture and is explicitly not validated.
"""
import copy
import csv
import io
import json
import os
import sys
import zipfile

from stage1_audit import ROOT, OUT, LRTS, raw_name, extract_member, write_json


def main():
    run=ROOT/'work/runs/dante'
    inputs=run/'inputs'
    inputs.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ROOT/'references/artifacts/dante/ML_TCSP.zip') as z:
        rows=list(csv.DictReader(io.StringIO(z.read(LRTS+'dataset.csv').decode())))
        rows=sorted((r for r in rows if r['project']=='karaf'),key=lambda r:(float(r['build_timestamp']),r['pr_name'],r['build_id'],r['stage_id']))
        names=sorted(n for n in z.namelist() if n.startswith('ML_TCSP/src/processed_builds/karaf_') and n.endswith('.json'))
        target=None
        for row in rows:
            prefix=f"karaf_build_{row['pr_name']}_{row['build_id']}_{row['stage_id']}_"
            matches=[n for n in names if n.rsplit('/',1)[-1].startswith(prefix)]
            history=[h for h in rows if float(h['build_timestamp'])<float(row['build_timestamp'])]
            if matches and history:
                target=(row,matches[0],history[-100:])
                break
        if target is None:
            raise RuntimeError('No processed build with history')
        row,member,history=target
        for old in inputs.glob('*.json'):
            if old.name != member.rsplit('/',1)[-1]:
                raise RuntimeError('Input fixture has unexpected build: '+str(old))
        (inputs/member.rsplit('/',1)[-1]).write_bytes(z.read(member))
        extract_member(z,LRTS+'dataset.csv')
        for h in history:
            extract_member(z,raw_name(h))
    raw=ROOT/'work/artifacts/ML_TCSP/long_running_test_suites'
    overrides=dict(TARGET_PROJECT='karaf',LRTS_RAW_DATA_BASE_PATH=str(raw),LRTS_METADATA_FILE=str(raw/'dataset.csv'),PIPELINE_OUTPUT_DIR=str(inputs),RESULTS_DIR=str(run/'upstream-results'),TARGET_BUILD_SELECTION_STRATEGY='LATEST',NUM_TARGET_BUILDS_TO_TEST='1',NUM_BUILDS_FOR_PROB_MODEL='100',RELEVANCE_STRATEGY_KEY='tfidf',ML_FEATURES_DIR=str(run/'unavailable-ml-features'))
    for k,v in overrides.items():
        os.environ['EXPERIMENT_CONFIG_'+k]=v
    os.environ['MPLBACKEND']='Agg'
    os.environ['MPLCONFIGDIR']=str(ROOT/'work/cache/matplotlib')
    sys.path.insert(0,str(ROOT/'work/artifacts/ML_TCSP/src'))
    import pandas as pd
    from types import SimpleNamespace
    import run_prioritization as upstream
    os.chdir(run)
    upstream.main()
    cfg=SimpleNamespace(**{**vars(upstream.base_cfg),**upstream.PRIORITIZATION_MODE_CONFIG})
    full,available=upstream.load_and_split_data(cfg)
    target_row=upstream.select_target_builds(available,cfg).iloc[0]
    hist=full[full['timestamp_for_sort']<target_row['timestamp_for_sort']].tail(100)
    model=upstream.build_statistical_model(hist,cfg)
    data=json.loads((inputs/member.rsplit('/',1)[-1]).read_text(encoding='utf-8'))
    scores=upstream.calculate_all_scores(data,hist,model,cfg)
    upstream.calculate_hybrid_scores(scores)
    frame=pd.DataFrame.from_dict(scores,orient='index')
    order=frame.sort_values('dante_cch_score',ascending=False).index.tolist()
    assert len(order)==len(scores) and len(set(order))==len(scores)
    costs=[scores[t]['duration'] for t in order]
    total=sum(costs)
    failures=sum(scores[t]['actual_outcome']==1 for t in order)
    elapsed=area_sum=0.0
    for t,c in zip(order,costs):
        if scores[t]['actual_outcome']==1:
            area_sum+=elapsed+c/2
        elapsed+=c
    midpoint=1-area_sum/(failures*total) if failures and total>0 else None
    artifact_metric=upstream.calculate_apfdc_metric(order,frame)
    if midpoint is not None:
        assert abs(artifact_metric-midpoint-1/(2*len(order)))<1e-12
    # Diagnostic: current duration must not be a ranking feature in a prospective protocol.
    changed=copy.deepcopy(data)
    chosen=max(scores,key=lambda t:abs(scores[t]['dante_cch_score']))
    changed['test_cases'][chosen]['duration']*=2
    modified=upstream.calculate_all_scores(changed,hist,model,cfg)
    upstream.calculate_hybrid_scores(modified)
    changed_duration_score=scores[chosen]['dante_cch_score']!=modified[chosen]['dante_cch_score']
    # A concrete witness that rolling after groupby.shift crosses test boundaries.
    toy=pd.DataFrame({'testclass':['A','A','B','B'],'outcome':[1,0,0,0]})
    artifact_sticky=toy.groupby('testclass')['outcome'].shift(1).rolling(2,min_periods=1).max().tolist()
    witness=dict(testclasses=toy.testclass.tolist(),outcomes=toy.outcome.tolist(),artifact_sticky=[None if pd.isna(v) else v for v in artifact_sticky],first_B_inherits_A=artifact_sticky[2]==1)
    excluded=[t for t in data['test_cases'] if t not in scores]
    result=dict(target=row,processed_member=member,history_rows=len(hist),history_cutoff_rule='upstream start timestamp < target timestamp; not completion-aware',overrides=overrides,original_tests=len(data['test_cases']),ranked_tests=len(order),excluded_tests=len(excluded),excluded_failures=sum(data['test_cases'][t]['outcome']==1 for t in excluded),ranked_failures=failures,artifact_apfdc=artifact_metric,midpoint_apfdc=midpoint,extra_term=1/(2*len(order)),current_duration_changes_dante_score=changed_duration_score,duration_diagnostic_test=chosen,sticky_group_boundary_witness=witness,ltr_baseline_status='Not validated: no earlier processed fixtures, upstream uses -100 placeholder',note='Artifact execution smoke only. Current duration in ranking, universe filtering, history construction and metric require a documented adapter before a fair rolling comparison.')
    write_json('dante-smoke.json',result)
    write_json('dante-ranking.json',order)
    write_json('dante-excluded-tests.json',excluded)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
