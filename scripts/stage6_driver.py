"""Detached, logged sequential driver; resumable after the interactive tool turn ends."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.stage6_pilot import verify_implementation,write_json


def run(script, project=None):
    command=[sys.executable,'-B',str(ROOT/'scripts'/script)]
    if project:
        command += ['--project',project]
    write_json(ROOT/'reports/stage6/driver-status.json',dict(pid=os.getpid(),stage=script,project=project,status='running',updated_at=datetime.now(timezone.utc).isoformat()))
    print('START',script,project,flush=True)
    subprocess.run(command,cwd=ROOT,env=dict(os.environ,PYTHONHASHSEED='0'),check=True)


def main():
    verify_implementation()
    try:
        for project in ('karaf','activemq','log4j'):
            if not (ROOT/'reports/stage6'/project/'complete.json').exists():
                run('stage6_recover_cold.py',project)
                run('stage6_pilot.py',project)
            run('stage6_replay_check.py',project)
        run('stage6_summary.py')
        run('stage6_supplement.py')
        run('stage6_report.py')
        write_json(ROOT/'reports/stage6/driver-status.json',dict(pid=os.getpid(),status='complete',updated_at=datetime.now(timezone.utc).isoformat()))
    except Exception as exc:
        write_json(ROOT/'reports/stage6/driver-status.json',dict(pid=os.getpid(),status='failed',error=str(exc),updated_at=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__':
    main()
