"""Shared chat feed for the embedded panel and standalone Hermes page."""
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
import model_control

BASE = Path(__file__).resolve().parent
STORE = BASE/'chat-runs'
STORE.mkdir(mode=0o700, exist_ok=True)
LOCK = threading.Lock()
JOBS = []

def start(question, prompt):
    with LOCK:
        if any(j['status']=='running' for j in JOBS):
            raise ValueError('Hermes is already answering. Its live output is shown in the panel.')
        model_control.begin_chat()
        job = {'id':uuid.uuid4().hex, 'question':question, 'status':'running', 'started':time.time(), 'answer':''}
        JOBS.append(job)
        del JOBS[:-20]
        threading.Thread(target=_run,args=(job,prompt),daemon=True).start()
        return {'id':job['id']}

def _run(job, prompt):
    try:
        events = STORE/(job['id']+'.jsonl')
        env = {**os.environ,'HERMES_HOME':str(BASE/'hermes-profile'), 'PHOTON_EVENTS':str(events), 'PYTHONUNBUFFERED':'1'}
        command = [str(Path.home()/'.hermes/hermes-agent/venv/bin/python'), str(BASE/'hermes_stream.py'),
                   'chat','--quiet','--oneshot','--toolsets','cuphoton','--max-turns','8','--query',prompt]
        proc = subprocess.run(command,cwd=BASE,env=env,capture_output=True,text=True,timeout=240)
        answer = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',proc.stdout).strip()
        with LOCK:
            job.update(status='complete' if proc.returncode==0 else 'failed',
                       answer=answer if proc.returncode==0 else 'Hermes could not finish. Check the local model and retry.')
        if proc.returncode:
            (STORE/(job['id']+'.error.log')).write_text(proc.stderr)
    except subprocess.TimeoutExpired:
        with LOCK: job.update(status='failed',answer='Hermes timed out after four minutes. Please retry.')
    except Exception as exc:
        with LOCK: job.update(status='failed',answer=f'Unable to start Hermes: {exc}')
    finally:
        model_control.end_chat()

def snapshot():
    with LOCK: jobs = [dict(j) for j in JOBS]
    for job in jobs:
        partial = []
        activity = [{'text':'Starting Hermes…','time':job['started']}]
        path = STORE/(job['id']+'.jsonl')
        if path.exists():
            for line in path.read_text().splitlines():
                try: event = json.loads(line)
                except ValueError: continue  # a final line may still be in flight
                if event['type']=='delta': partial.append(event['text'])
                elif event['type']=='status': activity.append({'text':event['text'],'time':event['time']})
                elif event['type'] in ('tool_start','tool_complete'):
                    name=event['name'].replace('mcp__cuphoton__','')
                    activity.append({'text':('Running tool: ' if event['type']=='tool_start' else 'Tool completed: ')+name,'time':event['time']})
        job['partial']=''.join(partial)
        job['activity']=activity[-50:]
        job['elapsed']=round(time.time()-job['started']) if job['status']=='running' else None
    return {'jobs':jobs}
