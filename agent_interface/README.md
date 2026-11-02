# Scientific Image Analysis Lab: deployment on another DGX Spark

This directory contains the cuPhoton pipeline dashboard, Hermes chat interface,
12 MCP tools, model selector, and live GPU telemetry. Run the setup commands
on the target Spark as the Linux user who will own the services.

This guide documents the current integration. It does not install GPU drivers,
Hermes, model weights, or a model-serving runtime automatically. It is based on
the deployed Darknight system and source inspection; a clean installation on a
second Spark has not yet been validated.

## Architecture

Researcher → dashboard → Hermes → local model → cuPhoton MCP tools → experiment.

| Component | Spark address | Purpose |
| --- | --- | --- |
| Dashboard | 127.0.0.1:8765 | Main page, Hermes, GPU telemetry |
| Model endpoint | 127.0.0.1:8000/v1 | OpenAI-compatible server with tool calling |
| Optional public gateway | 127.0.0.1:8766 | Password-protected reverse proxy |

Pages are /, /hermes, and /gpu. The dashboard binds to loopback. Use SSH
forwarding for private access or the authenticated gateway for public access.

## 1. Prepare the target Spark

Required:

- Linux ARM64, working NVIDIA driver, CUDA 13 development toolkit, nvidia-smi.
- Git, uv, a C/C++ build toolchain, and thread-safe CFITSIO development files.
- Nous Research Hermes Agent installed and configured for a local custom model.
- A Spark-compatible serving runtime and downloaded model checkpoint supporting
  tool calling. Validate the runtime independently before connecting the dashboard.
- A working user systemd session and sufficient memory/storage for the model.

The application currently expects these locations:

| Location | Required content |
| --- | --- |
| ~/.hermes/hermes-agent/ | Hermes source installation |
| ~/.hermes/hermes-agent/venv/bin/python | Hermes Python environment |
| ~/.hermes/config.yaml | Existing valid Hermes configuration |
| ~/Desktop/build-a-claw/config.json | Local model catalog |
| REPOSITORY/.venv/bin/python | cuPhoton and MCP environment |

Install Hermes using its upstream installation instructions. If its paths differ,
adapt chat_jobs.py and hermes_stream.py. The streaming adapter uses Hermes's
internal cli._configure_quiet_agent and streaming/tool callbacks; verify them
when upgrading Hermes. The CLI must support chat, --quiet, --oneshot, --toolsets,
--max-turns, and --query.

## 2. Install cuPhoton and dashboard dependencies

Example location; keep the repository here after creating services:

~~~bash
mkdir -p "$HOME/Applications"
git clone https://github.com/patelmiteshn/cuPhoton.git "$HOME/Applications/cuPhoton"
cd "$HOME/Applications/cuPhoton"
export PHOTON_ROOT="$PWD"

nvidia-smi
nvcc --version
uv sync --locked --extra gpu --extra viz
uv pip install --python .venv/bin/python 'mcp>=1.11,<2' PyYAML
~~~

Build xDR following [the native build requirements](../docs/components/xdr.md).
It requires CUDA headers and a **thread-safe CFITSIO** installation. If using
a custom CFITSIO prefix:

~~~bash
# Replace this with your actual CFITSIO installation prefix.
export CUPHOTON_XDR_CFITSIO_ROOT="$HOME/local/cfitsio"
bash src/cuphoton/xdr/src/build.sh
~~~

Do not use a nonexistent example prefix. For a system installation, follow the
discovery instructions in the xDR guide.

~~~bash
.venv/bin/python -c 'import cupy as cp; import mcp, yaml; from cuphoton.xdr import batch_to_device; print(cp.cuda.runtime.getDeviceCount())'
~~~

A later uv sync may remove the additional MCP/PyYAML packages; reinstall them
after syncing. These dashboard dependencies are not added to cuPhoton's lockfile.

## 3. Configure model serving

The model controller reads ~/Desktop/build-a-claw/config.json. This path is
currently fixed in model_control.py and start_model.py. You can create the
directory/catalog yourself; the build-a-claw project is not otherwise required.

The catalog must contain a models object. Supported keys are gemma, qwen, and
nemotron. Only enabled entries with existing weight directories are displayed.

The following is a **schema template**, not a complete model launch recipe:

~~~json
{
  "models": {
    "gemma": {
      "enabled": true,
      "model_id": "YOUR_EXACT_SERVED_MODEL_ID",
      "path": "/ABSOLUTE/PATH/TO/WEIGHTS",
      "context_window": 32768,
      "argv": [
        "/ABSOLUTE/PATH/TO/vllm",
        "serve", "{model_path}",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--served-model-name", "{model_id}",
        "--max-model-len", "32768"
      ],
      "env": {}
    }
  }
}
~~~

Replace all placeholders. Add the checkpoint's required architecture,
quantization, reasoning, and tool-parser flags to argv using a launch command
you have validated on that Spark. argv[0] must be an executable absolute path.
Supported substitutions are {kit_dir}, {model_path}, and {model_id}. Relative
weight paths resolve against ~/Desktop/build-a-claw; env adds environment values.

The original deployment used:
- Gemma: unsloth/gemma-4-26B-A4B-it-NVFP4
- Qwen: nvidia/Qwen3.6-35B-A3B-NVFP4
- Nemotron: nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4

Availability depends on your runtime/checkpoint combination. A generic vLLM
installation is not guaranteed to support these checkpoints on ARM64/GB10.
For other families, change the supported keys/labels in model_control.py and
start_model.py.

Optional agent_interface/models.extra.json contains the same model entries
without the outer models object. register_nemotron.py only discovers already
cached weights and assumes runtime/restored/vllm/bin/vllm under the kit directory.
Inspect/adapt it before use on another Spark; it does not download weights.

## 4. Configure Hermes and create the dashboard service

In your existing ~/.hermes/config.yaml, set a model block matching the catalog.
Preserve other settings you need:

~~~yaml
model:
  default: YOUR_EXACT_SERVED_MODEL_ID
  provider: custom
  base_url: http://127.0.0.1:8000/v1
  api_mode: chat_completions
  context_length: 32768
  max_tokens: 4096
~~~

The ID must exactly match /v1/models, and context settings must fit the server.

From the repository root:

~~~bash
.venv/bin/python agent_interface/configure_spark.py
~~~

This backs up the main Hermes configuration, registers all 12 tools, creates
agent_interface/hermes-profile/config.yaml, and enables cuphoton-dashboard.
It does not install Hermes or start the model.

**Update the generated service PATH for your account.** The installer currently
includes /home/nvidia/.local/bin. Run:

~~~bash
systemctl --user edit cuphoton-dashboard
~~~

Add the following with your actual username and CUDA location:

~~~ini
[Service]
Environment="PATH=/home/YOUR_USER/.local/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
~~~

Add any native-library runtime environment your build requires to this override.

~~~bash
systemctl --user daemon-reload
systemctl --user restart cuphoton-dashboard
systemctl --user status cuphoton-dashboard --no-pager
~~~

Start the model with its explicit catalog key (replace gemma if needed):

~~~bash
systemd-run --user --unit=cuphoton-model --collect   "$PHOTON_ROOT/.venv/bin/python"   "$PHOTON_ROOT/agent_interface/start_model.py" gemma
~~~

Do not launch a duplicate server on port 8000. Loading can take several minutes.

~~~bash
journalctl --user -u cuphoton-model -n 80 --no-pager
curl -fsS http://127.0.0.1:8000/v1/models
curl -fsS http://127.0.0.1:8765/api/models
~~~

The dashboard should report ready: true. Its **Apply model** control can also
start or switch the model service.

## 5. Open the dashboard from your laptop

Run on your laptop, using the target Spark's username and address:

~~~bash
ssh -N -L 8765:127.0.0.1:8765 YOUR_USER@SPARK_ADDRESS
~~~

Keep the tunnel open and visit:
- http://localhost:8765/ — main dashboard
- http://localhost:8765/hermes — standalone chat
- http://localhost:8765/gpu — GPU monitoring

If port 8765 is occupied locally, forward 8876:127.0.0.1:8765 and browse port
8876. Do not expose port 8765 directly to the internet: its API has no login.

## 6. Verify the installation

From the repository root on Spark:

~~~bash
curl -fsS http://127.0.0.1:8765/api/health
curl -fsS http://127.0.0.1:8765/api/gpu
cd agent_interface
../.venv/bin/python -m unittest test_model_control test_imaging_tools -v
~~~

Then:
1. Run the matched experiment (sigma 0.65) and wait for completion.
2. Confirm backend receipts, measurements, and four diagnostic figures.
3. Ask Hermes: "List my completed runs and explain the latest residual fraction."
4. Ask: "Use make_scene with moving=[120,108,14,2.1], render a labeled panel,
   and give me its image link."
5. Confirm tool progress, final output, and a working image link.
6. Check GPU dials and the compute/graphics process details.

## 7. Optional public HTTPS access

Use the authenticated gateway on port 8766, never a public tunnel directly
to port 8765. Generate a fresh password on each Spark:

~~~bash
python3 - <<'PYSETUP'
from pathlib import Path
import secrets
p = Path.home()/'.config/cuphoton-public.env'
p.parent.mkdir(parents=True, exist_ok=True)
with p.open('x') as f:
    p.chmod(0o600)
    f.write('PHOTON_PUBLIC_PASSWORD='+secrets.token_urlsafe(24)+'\n')
print('Password saved to', p)
PYSETUP
~~~

This refuses to overwrite an existing password. The username is researcher.
Read the password locally from that file; do not put it in source control.

Create ~/.config/systemd/user/cuphoton-public.service with your repository path:

~~~ini
[Unit]
Description=Authenticated cuPhoton public gateway
After=cuphoton-dashboard.service

[Service]
EnvironmentFile=%h/.config/cuphoton-public.env
ExecStart=/usr/bin/python3 /ABSOLUTE/PATH/cuPhoton/agent_interface/public_server.py
Restart=on-failure

[Install]
WantedBy=default.target
~~~

Install the official ARM64 cloudflared executable at ~/.local/bin/cloudflared,
verifying its published release checksum. Create
~/.config/systemd/user/cuphoton-tunnel.service:

~~~ini
[Unit]
Description=cuPhoton public HTTPS tunnel
After=cuphoton-public.service
Requires=cuphoton-public.service

[Service]
ExecStart=%h/.local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8766
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
~~~

~~~bash
systemctl --user daemon-reload
systemctl --user enable --now cuphoton-public cuphoton-tunnel
journalctl --user -u cuphoton-tunnel -n 80 --no-pager
~~~

Open the printed HTTPS address with /, /hermes, or /gpu. Check that requests
without credentials return HTTP 401 and authenticated pages work. The shared
login grants control of experiments and model selection.

Quick Tunnel addresses change after restart and require Spark to remain online.
For a stable address, configure a named tunnel with your domain.
Restarting the gateway stops its dependent tunnel; start cuphoton-tunnel again
and read the new URL.

## 8. Restart, update, and reboot

~~~bash
# Restart the app without restarting the gateway or public tunnel.
systemctl --user restart cuphoton-dashboard

# Inspect logs.
journalctl --user -u cuphoton-dashboard -n 100 --no-pager
journalctl --user -u cuphoton-model -n 100 --no-pager

# Disable public access.
systemctl --user disable --now cuphoton-tunnel
~~~

Wait for experiments, chats, and model switches to finish before restarting.
Chat history is in memory and clears on restart. Reports/artifacts persist.

For enabled user services to keep running after logout, an administrator can run:

~~~bash
sudo loginctl enable-linger "$USER"
~~~

The model service created by systemd-run is transient and does not survive
reboot. After reboot, use Apply model or repeat the explicit model-start command
from step 4. A persistent model startup service requires separate provisioning
and validation with the dashboard's model-switching workflow.

Before updating, back up configuration and run data and preserve local edits.
Use git pull --ff-only on a clean checkout. Rebuild shared UI assets after edits:

~~~bash
python3 agent_interface/dashboard/build_theme.py
~~~

HTML changes are served directly; Python changes require a service restart.
If moving the repository, update service paths and both Hermes MCP configurations.
Some display labels still mention Darknight; customize these for the new host.

## 9. Troubleshooting

| Symptom | Check |
| --- | --- |
| Dashboard fails to start | Journal, Python dependencies, model catalog, Hermes profile |
| Empty model list | Supported catalog key, enabled flag, existing weight path |
| Model offline | Port 8000, exact model ID, model journal and runtime flags |
| Switch interrupted by restart | Reapply the intended model |
| Hermes fails | Installation paths, CLI flags, callback compatibility, chat-runs/*.error.log |
| Missing MCP tools | Both Hermes profiles, MCP Python path and include list |
| xDR import/build failure | CUDA headers and thread-safe CFITSIO; see xDR guide |
| Total GPU memory unavailable | Expected on GB10; use labeled process allocations/shared RAM |
| Public link stopped working | Tunnel status and most recent URL |

## 10. Code map and data

| File | Purpose |
| --- | --- |
| server.py, worker.py | Dashboard API, scheduler and notebook execution |
| chat_jobs.py, hermes_stream.py | Hermes subprocess and streaming callbacks |
| mcp_server.py, imaging_tools.py | 12 tools and artifact-based helper adapters |
| model_control.py, start_model.py | Model readiness, catalog and switching |
| gpu_monitor.py | GPU/system measurements and process allocation telemetry |
| public_server.py | Authenticated public gateway |
| dashboard/index.html, gpu.html | Main/chat and GPU views |
| dashboard/theme.css, theme.js | Theme styles and selection |
| dashboard/telemetry.js | Dials and GPU process panel |
| dashboard/build_theme.py | Embeds shared UI assets |
| dashboard/assets/ | Pipeline illustrations |

Tools: list_runs, run_pipeline, gaussian2d, make_scene, write_fits, stretch_gray,
stretch_div, label_panel, panel, panel_kernel, residual_colorbar, show_row.

Runtime files are under runs/, chat-runs/, tool-artifacts/, hermes-profile/,
and model-state.json. Most are gitignored. Never commit passwords, provider
credentials, or machine-specific configuration. Artifacts do not expire
automatically; manage retained files as needed.

## Scientific scope and limitations

The full experiment generates synthetic FITS images, loads with xDR, aligns
with xRep, matches/subtracts with xPois, fits a dipole with xFit, and saves
figures and measurements. The trial kernel is 1.6 pixels; planted blur is 0.65.

Convergence does not establish scientific adequacy. No variance is supplied:
chi2 is unweighted SSE. Residual fraction is peak absolute fit residual divided
by peak absolute stamp value; multiply by 100 for percent.

The illustration describes a broader architecture including xScan. This demo
does not execute xScan or ingest real survey images. It is not a fully
device-resident implementation: later stages use host-result APIs and xRep
rereads FITS files. Individual helper tools use NumPy/SciPy on CPU.

Each question starts a fresh Hermes turn with recent run metrics, not image
pixels. This is a shared research interface, not isolated multi-user sessions.
Helpers exchange artifact IDs, not arbitrary filesystem paths.

GB10 memory is shared with the CPU. Compute allocations exclude other driver
allocations; system RAM is not GPU-only usage. The 140 W power dial is a display
scale and does not configure a hardware power limit.

Theme attribution/license: dashboard/THEME-NOTICE.md and dashboard/THEME-LICENSE.
