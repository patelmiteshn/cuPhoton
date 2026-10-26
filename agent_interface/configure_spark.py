"""Install the local dashboard service and merge a bounded Hermes MCP entry."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time
import yaml
from imaging_tools import NAMES

base = Path(__file__).resolve().parent
root = base.parent
config = Path.home()/'.hermes/config.yaml'
backup = config.with_name(f'config.yaml.cuphoton-backup-{int(time.time())}')
shutil.copy2(config, backup)
c = yaml.safe_load(config.read_text()) or {}
c.setdefault('mcp_servers', {})['cuphoton'] = {
    'command': str(root/'.venv/bin/python'), 'args': [str(base/'mcp_server.py')],
    'tools': {'include': ['list_runs', 'run_pipeline'] + sorted(NAMES), 'prompts': False, 'resources': False}}
config.write_text(yaml.safe_dump(c, sort_keys=False))
profile = base / 'hermes-profile'
profile.mkdir(exist_ok=True)
(profile / 'config.yaml').write_text(yaml.safe_dump({
    'model': c['model'],
    'mcp_servers': {'cuphoton': c['mcp_servers']['cuphoton']},
    'tools': {'tool_search': {'enabled': 'off'}},
    'terminal': {'cwd': str(base)},
}, sort_keys=False))
unit = Path.home()/'.config/systemd/user/cuphoton-dashboard.service'
unit.parent.mkdir(parents=True, exist_ok=True)
unit.write_text(f'''[Unit]
Description=cuPhoton research dashboard
After=network.target
[Service]
WorkingDirectory={root}
ExecStart="{root}/.venv/bin/python" "{base}/server.py"
Environment="PATH=/home/nvidia/.local/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
Restart=on-failure
[Install]
WantedBy=default.target
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now','cuphoton-dashboard'],check=True)
print('Dashboard service installed; Hermes configuration backup:',backup)
