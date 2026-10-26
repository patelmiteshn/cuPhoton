"""Serialize model changes with chats and GPU runs; expose measured readiness."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time
from urllib.request import urlopen
import yaml

BASE = Path(__file__).resolve().parent
KIT = Path.home() / 'Desktop/build-a-claw'
STATE = BASE / 'model-state.json'
LOCK = threading.RLock()
CHATS = 0
LABELS = {'gemma': 'Gemma 4 · 26B-A4B NVFP4', 'qwen': 'Qwen 3.6 · 35B-A3B NVFP4', 'nemotron': 'Nemotron 3 Nano Omni · 30B-A3B NVFP4'}

def catalog():
    configs = json.loads((KIT / 'config.json').read_text())['models']
    extra = BASE / 'models.extra.json'
    if extra.exists():
        configs.update(json.loads(extra.read_text()))
    return {k: configs[k] for k in LABELS if k in configs and configs[k].get('enabled') and (KIT / configs[k]['path']).is_dir()}

def served_model():
    try:
        with urlopen('http://127.0.0.1:8000/v1/models', timeout=1) as response:
            return json.load(response)['data'][0]['id']
    except (OSError, ValueError, KeyError, IndexError):
        return None

def write_state(value):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(value))
    tmp.replace(STATE)

def status():
    configs = catalog()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    configured = yaml.safe_load((BASE/'hermes-profile/config.yaml').read_text())['model']['default']
    actual = served_model()
    key = next((k for k, c in configs.items() if c['model_id'] == configured), None)
    ready = actual == configured and state.get('phase') != 'switching'
    return {'models': [{'key': k, 'label': LABELS[k], 'id': c['model_id']} for k,c in configs.items()],
            'selected': key, 'served_model': actual, 'ready': ready,
            'phase': state.get('phase', 'ready' if ready else 'offline'),
            'target': state.get('target'), 'message': state.get('message', ''),
            'chat_busy': CHATS > 0}

def begin_chat():
    global CHATS
    with LOCK:
        if not status()['ready']:
            raise ValueError('The selected model is loading or offline. Wait for it to be ready.')
        CHATS += 1

def end_chat():
    global CHATS
    with LOCK:
        CHATS -= 1

def check_run_allowed():
    if STATE.exists() and json.loads(STATE.read_text()).get('phase') == 'switching':
        raise ValueError('Wait for the model switch to finish before starting a GPU run.')

def switch(key, runs):
    with LOCK:
        configs = catalog()
        if key not in configs:
            raise ValueError('Choose an installed model from the list.')
        current = status()
        if current['phase'] == 'switching':
            raise ValueError('A model switch is already in progress.')
        if CHATS or any(r['status'] in ('queued', 'running') for r in runs()):
            raise ValueError('Wait for the current chat or pipeline run to finish before switching models.')
        if current['ready'] and current['selected'] == key:
            return current
        write_state({'phase': 'switching', 'target': key, 'message': 'Stopping the previous model…'})
        threading.Thread(target=_switch_worker, args=(key, configs), daemon=True).start()
        return {'phase': 'switching', 'target': key}

def _switch_worker(key, configs):
    try:
        # Stop only the dashboard's managed service and known model launch commands.
        subprocess.run(['systemctl', '--user', 'stop', 'cuphoton-model.service'], capture_output=True)
        known_paths = {str(KIT / c['path']) for c in configs.values()}
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if proc.stat().st_uid != os.getuid():
                    continue
                args = (proc/'cmdline').read_bytes().decode().split('\0')
                if 'serve' in args and any(p in args for p in known_paths) and '--port' in args and args[args.index('--port')+1] == '8000':
                    os.kill(int(proc.name), signal.SIGTERM)
            except (OSError, UnicodeError, IndexError):
                continue
        deadline = time.monotonic() + 60
        while True:
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1',8000)) != 0:
                    break
            if time.monotonic() > deadline:
                raise RuntimeError('The previous model did not release port 8000; no new model was launched.')
            time.sleep(1)
        # A separate user service survives dashboard restarts and owns the vLLM process.
        subprocess.run(['systemctl','--user','reset-failed','cuphoton-model.service'],capture_output=True)
        command = ['systemd-run', '--user', '--unit=cuphoton-model', '--collect',
                   str(BASE.parent/'.venv/bin/python'), str(BASE/'start_model.py'), key]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        write_state({'phase': 'switching', 'target': key, 'message': 'Loading weights and warming up the GPU. This can take several minutes.'})
        deadline = time.monotonic() + 600
        while served_model() != configs[key]['model_id']:
            result = subprocess.run(['systemctl','--user','is-active','cuphoton-model.service'],capture_output=True,text=True)
            if result.stdout.strip() not in ('active','activating'):
                raise RuntimeError('Model startup failed. See journalctl --user -u cuphoton-model. Select a model to retry.')
            if time.monotonic() > deadline:
                raise RuntimeError('Model startup timed out. Select a model to retry.')
            time.sleep(2)
        # Commit configuration only after the requested server is responding.
        for path in [BASE/'hermes-profile/config.yaml', Path.home()/'.hermes/config.yaml']:
            cfg = yaml.safe_load(path.read_text())
            backup = path.with_name(path.name+'.before-model-switch')
            backup.touch(mode=0o600, exist_ok=True)
            backup.chmod(0o600)
            backup.write_text(path.read_text())
            cfg['model']['default'] = configs[key]['model_id']
            cfg['model']['context_length'] = configs[key]['context_window']
            tmp = path.with_suffix('.tmp')
            tmp.touch(mode=0o600, exist_ok=True)
            tmp.chmod(path.stat().st_mode & 0o777)
            tmp.write_text(yaml.safe_dump(cfg, sort_keys=False))
            tmp.replace(path)
        write_state({'phase':'ready','target':key,'message':LABELS[key]+' is ready.'})
    except Exception as exc:
        write_state({'phase':'failed','target':key,'message':str(exc)})

def recover():
    if STATE.exists() and json.loads(STATE.read_text()).get('phase') == 'switching':
        write_state({'phase':'failed','message':'Dashboard restarted during a model switch. Select a model and apply to reconnect.'})
