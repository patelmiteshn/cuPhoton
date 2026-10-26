"""Start the Spark's selected model configuration; do not launch a duplicate."""
import json
import os
import sys
import yaml
from pathlib import Path
from urllib.request import urlopen

kit = Path.home() / 'Desktop/build-a-claw'
configs = json.loads((kit / 'config.json').read_text())['models']
extra = Path(__file__).resolve().parent / 'models.extra.json'
if extra.exists():
    configs.update(json.loads(extra.read_text()))
if len(sys.argv) > 1:
    key = sys.argv[1]
else:
    profile = Path(__file__).resolve().parent / 'hermes-profile/config.yaml'
    selected = yaml.safe_load(profile.read_text())['model']['default']
    key = next(k for k in ('gemma','qwen','nemotron') if configs[k]['model_id'] == selected)
if key not in ('gemma', 'qwen', 'nemotron'):
    raise SystemExit('Unsupported model')
config = configs[key]
try:
    with urlopen('http://127.0.0.1:8000/v1/models', timeout=2) as response:
        actual = json.load(response)['data'][0]['id']
    if actual == config['model_id']:
        print('The selected model is already ready.')
        raise SystemExit(0)
    raise SystemExit('Another model is serving port 8000; use the dashboard to switch.')
except OSError:
    pass
args = [a.replace('{kit_dir}', str(kit)).replace('{model_path}', str(kit / config['path'])).replace('{model_id}', config['model_id']) for a in config['argv']]
env = os.environ.copy()
env.update(config['env'])
os.execve(args[0], args, env)
