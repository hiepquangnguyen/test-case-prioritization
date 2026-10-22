"""Check objective scale on already-exposed Karaf development features, no new ranking."""
import gzip
import json
import math
import sys
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage4_design_audit import OUT,write_json
from tcp.lrts import file_sha256


def main():
    source=ROOT/'reports/stage3/karaf'
    selection=json.loads((source/'selection.json').read_text(encoding='utf-8'))
    keys={tuple(r['key'][k] for k in ('project','pr','build','stage')) for r in selection if r['split']=='development'}
    rows=[]
    with gzip.open(source/'features.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            snap=json.loads(line)['snapshot']
            if tuple(snap['key'][k] for k in ('project','pr','build','stage')) not in keys:continue
            q=[t['history_cost_score'] for t in snap['features']]
            total=math.fsum(q)
            assert all(math.isfinite(v) and v>=0 for v in q)
            normalized=[v/total if total>0 else 0.0 for v in q]
            assert math.isclose(math.fsum(normalized),1.0 if total>0 else 0.0,abs_tol=1e-12)
            rows.append(dict(key=snap['key'],tests=len(q),Q=total,max_q=max(q,default=0),
                             normalized_modular_total=math.fsum(normalized),semantic_upper_bound=1.0))
    totals=[r['Q'] for r in rows]
    write_json(OUT/'objective-scale.json',dict(scope='317 already-exposed Karaf development build stages only',
        no_new_rankings_or_metrics=True,feature_sha256=file_sha256(source/'features.jsonl.gz'),
        source_selection_sha256=file_sha256(source/'selection.json'),
        script_sha256=file_sha256(Path(__file__)),builds=len(rows),
        Q_min=min(totals),Q_median=median(totals),Q_max=max(totals),Q_greater_than_1=sum(q>1 for q in totals),
        rows=rows,conclusion='Raw modular total is not on the same bounded scale as FL/n. This is not evidence of ranking quality.'))
    print(dict(builds=len(rows),Q_median=median(totals),Q_max=max(totals)))


if __name__=='__main__':main()
