"""Adapt installed Hermes callbacks without modifying its installation."""
import json
import os
from pathlib import Path
import sys
import threading
import time

home = Path.home()/'.hermes/hermes-agent'
sys.path.insert(0, str(home))
import cli

lock = threading.Lock()
def emit(kind, **data):
    with lock:
        with open(os.environ['PHOTON_EVENTS'], 'a') as f:
            f.write(json.dumps({'type':kind, 'time':time.time(), **data})+'\n')

original = cli._configure_quiet_agent
def configure(agent):
    original(agent)
    agent.stream_delta_callback = lambda text: emit('delta', text=text) if text else None
    agent.tool_start_callback = lambda call_id, name, args: emit('tool_start', name=name)
    agent.tool_complete_callback = lambda call_id, name, args, result: emit('tool_complete', name=name)
    emit('status', text='Hermes connected. Generating a response…')
cli._configure_quiet_agent = configure
from hermes_cli.main import main
main()
