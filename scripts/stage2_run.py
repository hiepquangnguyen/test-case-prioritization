"""Reproduce protocol-v1 technical replay, stdlib only; no dataset/model download."""
import argparse
import csv
import json
import platform
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tcp.baselines import METHODS
from tcp.history import HistoryConfig
from tcp.lrts import load_builds, verify_archive, file_sha256
from tcp.replay import replay


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='karaf')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/stage2/karaf20')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'reports/stage2').resolve()):
        raise ValueError('Output must be inside reports/stage2')
    output.mkdir(parents=True, exist_ok=True)
    archive = ROOT/'references/artifacts/dante/ML_TCSP.zip'
    config = HistoryConfig()
    print('Verifying pinned archive...', flush=True)
    hashes = verify_archive(archive)
    annotations = ROOT/'reports/stage1/karaf-source-mapping.csv' if args.project=='karaf' else None
    builds, selection = load_builds(archive, args.project, args.limit, annotations)
    result = replay(builds, config, seed=args.seed)
    manifest = dict(protocol='v1-technical-replay', created_at=datetime.now().astimezone().isoformat(),
                    python=platform.python_version(), archive=hashes, project=args.project,
                    requested_rows=args.limit, selected_rows=len(builds), seed=args.seed, config=asdict(config),
                    selection_rule='First rows by start timestamp, PR, build, stage; no outcome filtering',
                    history_rule='completed strictly before cutoff, same project/base-branch/stage, other physical build',
                    inventory_assumption='observed_log_inventory; not independently verified pre-build inventory',
                    timestamp_assumption='start=build_timestamp; completion=start+build_duration (seconds)',
                    source_annotations_sha256=file_sha256(annotations) if annotations else None,
                    implementation_sha256={str(p.relative_to(ROOT)): file_sha256(p) for p in sorted((ROOT/'tcp').glob('*.py'))},
                    protocol_sha256=file_sha256(ROOT/'docs/02-protocol/protocol-v1.md'),
                    role='Technical checks only: no holdout, hyperparameter tuning or effectiveness claim')
    write_json(output/'manifest.json', manifest)
    write_json(output/'selection.json', selection)
    write_json(output/'ledger.json', result['ledger'])
    for name, records in [('inputs', [asdict(b.inputs) for b in builds]),
                          ('ground-truth', [dict(key=asdict(b.inputs.key), result=b.result, available_at=b.available_at,
                                                 outcomes=[asdict(o) for o in b.outcomes]) for b in builds]),
                          ('features', result['snapshots']), ('rankings', result['rankings'])]:
        with (output/(name+'.jsonl')).open('w', encoding='utf-8') as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')
    summaries = []
    for method in METHODS:
        rows = [r for r in result['rankings'] if r['method']==method]
        scored = [r['metrics'] for r in rows if r['metrics'] is not None]
        values = [m['apfdc_midpoint'] for m in scored if m['apfdc_midpoint'] is not None]
        summaries.append(dict(method=method, ranked_builds=len(rows), eligible_builds=len(scored),
                              apfdc_defined=len(values), no_failure_builds=sum(m['observed_failures']==0 for m in scored),
                              median_apfdc=median(values) if values else None))
    write_json(output/'summary.json', summaries)
    with (output/'metrics.csv').open('w', encoding='utf-8', newline='') as f:
        fields = ['project','pr','build','stage','method','tests','failures','apfd','apfdc_midpoint',
                  'ttff_seconds','ttff_censored','censor_time_seconds','recall_10','recall_25','recall_50','reason']
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for row in result['rankings']:
            m = row['metrics']
            record = {**row['key'], 'method': row['method'], 'reason': row['scoring_exclusion']}
            if m is not None:
                record.update(tests=m['tests'],failures=m['observed_failures'],apfd=m['apfd'],
                              apfdc_midpoint=m['apfdc_midpoint'],ttff_seconds=m['ttff_seconds'],
                              ttff_censored=m['ttff_censored'],censor_time_seconds=m['censor_time_seconds'],
                              recall_10=m['recall']['0.1'],recall_25=m['recall']['0.25'],recall_50=m['recall']['0.5'],
                              reason=';'.join(m['reasons']))
            writer.writerow(record)
    print(json.dumps(dict(output=str(output), builds=len(builds), rankings=len(result['rankings']),
                          excluded_builds=sum(r['scoring_exclusion'] is not None for r in result['ledger'])), indent=2))


if __name__=='__main__':
    main()
