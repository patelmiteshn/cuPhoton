"""Loopback-only research dashboard; same run store is exposed through MCP."""
import json
import model_control
import chat_jobs
import gpu_monitor
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
RUNS = BASE / 'runs'
RUNS.mkdir(exist_ok=True)
lock = threading.Lock()

def reports():
    return sorted([json.loads(p.read_text()) for p in RUNS.glob('*/report.json')], key=lambda r: r['started'], reverse=True)

def start_run(sigma=1.6):
    sigma = float(sigma)
    if not math.isfinite(sigma) or not 0.2 <= sigma <= 3:
        raise ValueError('Kernel sigma must be between 0.2 and 3 pixels')
    with model_control.LOCK, lock:
        model_control.check_run_allowed()
        if any(r['status'] in ('queued', 'running') for r in reports()):
            raise ValueError('A run is already active; wait for it to finish')
        run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        folder = RUNS / run_id
        folder.mkdir()
        (folder / 'report.json').write_text(json.dumps(dict(id=run_id, status='queued', kernel_sigma=sigma, started=time.time(), stages=[])))
        with (folder / 'run.log').open('w') as log:
            subprocess.Popen([str(ROOT / '.venv/bin/python'), str(BASE / 'worker.py'), str(folder), str(sigma)], cwd=ROOT, stdout=log, stderr=log)
        return {'id': run_id}

class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/chat/feed':
            return self.send(chat_jobs.snapshot())
        if self.path == '/api/gpu':
            return self.send(gpu_monitor.snapshot())
        if self.path in ('/api/health', '/api/models'):
            state = model_control.status()
            return self.send({**state, 'model_ready': state['ready']})
        if self.path == '/api/runs':
            return self.send(reports())
        pages = {'/':'dashboard/index.html', '/hermes':'dashboard/index.html', '/gpu':'dashboard/gpu.html'}
        path = BASE/pages[self.path] if self.path in pages else (BASE / self.path.lstrip('/')).resolve()
        allowed = path in (BASE/'dashboard/index.html', BASE/'dashboard/gpu.html') or (path.is_relative_to(RUNS) and path.suffix in ('.png', '.json', '.log', '.fits'))
        allowed = allowed or (path.parent == BASE/'tool-artifacts' and re.fullmatch(r'[0-9a-f]{32}\.(png|fits)', path.name) is not None)
        if not allowed or not path.is_file():
            return self.send({'error': 'Not found'}, 404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'.html': 'text/html; charset=utf-8', '.png': 'image/png', '.json': 'application/json'}.get(path.suffix, 'application/octet-stream'))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # Prevent cross-origin browser pages from launching computations.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.send({'error': 'Cross-origin request rejected'}, 403)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 20000:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/model':
                return self.send(model_control.switch(body.get('model'), reports))
            if self.path == '/api/run':
                return self.send(start_run(body.get('sigma', 1.6)))
            if self.path in ('/api/chat', '/api/chat/start'):
                question = str(body.get('question', '')).strip()
                if not question or len(question) > 4000:
                    raise ValueError('Enter a question of 1–4000 characters')
                prompt = 'You are the cuPhoton research assistant. Use the cuPhoton MCP tools for requested experiments and inspect results. Helper tools generate arrays and images referenced by artifact_id; pass these IDs to later tools, never invent arrays or paths. Their url fields are relative dashboard download links: include Markdown links for generated files. Helpers are CPU scene/rendering utilities; run_pipeline executes the actual GPU experiment. Explain convergence separately from scientific adequacy. No variance is supplied: chi2 is unweighted SSE. These are synthetic images, not observations. Report measured values only from completed runs. A residual fraction near 1e-4 is small but is not machine precision. Distinguish percentages from fractions. Metric definitions: metrics.residual_fraction is exactly peak absolute dipole fit residual divided by peak absolute difference stamp; multiply it by 100 to report peak dipole error percent. metrics.centers_error_px contains coordinate errors in pixels, NEVER percentages. metrics.static_rms is static-scene residual RMS in image units. Do not invent a missing metric name or treat center errors as the dipole residual. After one successful tool read, answer directly unless the user asks for more actions.\nCurrent runs:\n' + json.dumps(reports()[:8]) + '\nResearcher question:\n' + question
                return self.send(chat_jobs.start(question, prompt))
            self.send({'error': 'Not found'}, 404)
        except subprocess.TimeoutExpired:
            self.send({'error': 'Hermes timed out; check the configured model server.'}, 504)
        except (ValueError, TypeError) as exc:
            self.send({'error': str(exc)}, 400)

if __name__ == '__main__':
    model_control.recover()
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
