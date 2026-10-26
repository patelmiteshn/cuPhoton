# cuPhoton researcher agent on Darknight Spark

Open http://localhost:8765 while the SSH tunnel is running:

```bash
ssh -N -L 8765:127.0.0.1:8765 darknight
```

The deployed directory is `/home/nvidia/Desktop/image_understanding/cuPhoton/agent_interface`.
The dashboard is a user service: `systemctl --user status cuphoton-dashboard`.
It binds to Spark's loopback interface. Run history is stored in `runs/`.

## How the researcher agent works

A researcher asks a question in the dashboard or Hermes CLI. Hermes uses the
selected local model for reasoning. Two MCP tools give it access to the
experiment: `list_runs` reads measured results and `run_pipeline` queues a run
with a validated kernel sigma. Both the dashboard and MCP use one scheduler.
The worker executes the source notebook's six code cells, changing only the
`KERNEL_SIGMA` assignment in memory. It does not rewrite the source notebook.

The data flow is:

```text
Researcher → dashboard chat → Hermes → selected local model
                                ↓ MCP
                        list_runs / run_pipeline
                                ↓
Dashboard API → notebook worker → cuPhoton on GB10
                                ↓
               run report + logs + FITS + PNG figures
```

Dashboard chats use a dedicated `hermes-profile/` configuration with direct tool schemas (tool-search deferral disabled for this assistant). It reuses the local model selection, has separate session history, and does not copy provider secrets.

Each chat question starts a new Hermes conversation with the eight most recent
run reports included as context. This is an experiment assistant, not a
persistent multi-user conversation system. The current chat interface supplies
metrics to Hermes; it does not automatically send PNG pixels for visual analysis.
Researchers inspect the images in the dashboard.

## Create the agent

1. Prepare the Linux/CUDA 13 host using the source notebook instructions:
   `uv sync --locked --extra gpu --extra viz`, then build xDR with
   `bash src/cuphoton/xdr/src/build.sh`. xDR requires thread-safe CFITSIO.
   On this Spark it was built under
   `/home/nvidia/Desktop/image_understanding/native-build/cfitsio-install`.
   Export `CUPHOTON_XDR_CFITSIO_ROOT` to that directory when rebuilding xDR.
2. Install the MCP SDK in the cuPhoton environment:
   `uv pip install --python .venv/bin/python 'mcp>=1.11,<2'`.
3. Install/configure Nous Research Hermes. On this Spark Hermes already exists.
   `hermes model` selects the provider. The existing configuration uses
   `unsloth/gemma-4-26B-A4B-it-NVFP4` at `http://127.0.0.1:8000/v1`.
4. Start `server.py` with the cuPhoton Python environment. For this host,
   `configure_spark.py` installs a user service and adds the following MCP
   entry to Hermes, backing up the existing config first:

```yaml
mcp_servers:
  cuphoton:
    command: /home/nvidia/Desktop/image_understanding/cuPhoton/.venv/bin/python
    args:
      - /home/nvidia/Desktop/image_understanding/cuPhoton/agent_interface/mcp_server.py
    tools:
      include: [list_runs, run_pipeline]
      prompts: false
      resources: false
```

5. Start a fresh Hermes chat or use `/reload-mcp` in an existing chat.
   The dashboard invokes `hermes chat --toolsets cuphoton` with its dedicated HERMES_HOME to keep the
   experiment interface limited to these tools. From a terminal:

```bash
HERMES_HOME="$PWD/hermes-profile" ~/.local/bin/hermes chat --toolsets cuphoton
```

Try: “Run the pipeline with kernel sigma 1.6.” Then “Check the run and explain
its residuals.” Then “Run sigma 0.65 and compare the completed results.”
A run tool returns an ID immediately; results must be read after completion.

## What the pipeline measures

| Stage | Operation | What the researcher checks |
|---|---|---|
| Setup | Generate two synthetic 256×256 FITS images | Three static stars, one mover; truth is synthetic |
| Load / xDR | Load IMAGE HDU 1 into a CuPy batch | Shape, device, float pixels |
| Align / xRep | Reproject to template WCS with Lanczos3 | Stars align; mover remains displaced |
| Subtract / xPois | Fit kernel coefficients and background | Static-scene RMS, kernel flux scale, rings |
| Fit / xFit | Fit a 21×21 dipole stamp | Convergence, center errors, residual fraction |
| Plot | Save four diagnostic figure rows | Color scales and residual structure |

The notebook uses host-result APIs in later stages. xRep reads the FITS files
again rather than consuming the xDR GPU batch directly. Do not describe this
walkthrough as a fully device-resident zero-copy pipeline.

The trial sigma is 1.6 pixels; the planted added blur is 0.65 pixels. The kernel
solve fits coefficients, not sigma. xFit shares amplitude and widths between
the two lobes, so unequal widths leave structured residuals even after optimizer
convergence. Kernel flux scale is fitted, even with `flux_conserve=True`.

No variance is supplied: `fit.chi2` is an unweighted sum of squares. Static RMS
is `sqrt(chi2 / fit_pixel_count)`. Peak dipole error is
`max(abs(fit residual)) / max(abs(stamp))`. The displayed residual is data minus
model, negating xFit's native residual convention. It has its own color scale.
Orientation is poorly constrained for these nearly circular lobes; do not
interpret the recorded theta as a reliable physical angle.

## Reproducibility and scope

Every completed run records the notebook SHA256, Git commit, selected sigma,
per-stage wall times, actual backend names, fit parameters, and synthetic center
errors. Timings include warmup and transfers and are not a benchmark. No detection
significance or real-observation accuracy is inferred. Runs currently use this
notebook's synthetic inputs only; real FITS ingestion would require validating
WCS, masks, PSF assumptions, uncertainties, and source selection.

Source baseline: `9ce72c87de6e3383a261e694ade74d86c6bc9656`.
On Darknight the trial produced peak error 9.959631%; matched sigma produced
0.009551%. Both converged. The dashboard always reads current measured reports,
not these illustrative fixed values.

The model selector uses the existing build-a-claw Gemma 4 and Qwen launch configurations;
it is separate from the dashboard service. After a reboot, restart the existing
model serving setup before using chat. Dashboard and GPU runs do not require
the language model. Logs for this setup: `/tmp/cuphoton-model.log`,
`/tmp/xdr-build.log`, and `journalctl --user -u cuphoton-dashboard`.

## Sources

- [cuPhoton notebook](https://github.com/NVIDIA/cuPhoton/blob/main/examples/imaging-pipeline/run_imaging_pipeline.ipynb)
- [Hermes setup](https://github.com/NousResearch/hermes-agent/blob/main/README.md)
- [Hermes MCP integration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md)

To restart the existing local model after a reboot, from this directory:

```bash
nohup ../.venv/bin/python start_model.py > /tmp/cuphoton-model.log 2>&1 &
```

Wait until the dashboard says “Local model ready”; cold startup can take several
minutes. Do not launch another instance while an earlier startup is still loading.
The Hermes MCP SDK was repaired by reinstalling its pinned `mcp==2.0.0` package;
its original installation had a missing auth handler module. The pipeline MCP
server uses its own environment and SDK, independently of Hermes.

The installed Hermes CLI filters MCP startup by the bare server name `cuphoton`; using `mcp-cuphoton` here prevents discovery in this version.

## Verified on Darknight

- Trial and matched notebook runs completed on GB10; all three later stages
  reported `cupy` and xDR reported CUDA device 0.
- All generated figure routes responded, and invalid sigma values were rejected.
- Dashboard rendered in Chromium; JavaScript and Python syntax checks passed.
- Hermes discovered both MCP tools, called `list_runs`, and correctly compared
  peak dipole residual percentages.
- A natural-language request through the final dashboard profile called
  `run_pipeline`; that GPU run completed successfully.


## Switch models in the dashboard

In the right-hand **Ask Hermes** panel, choose **Gemma 4 · 26B-A4B NVFP4**
or **Qwen 3.6 · 35B-A3B NVFP4**, then select **Apply model**. The page shows
shutdown, loading, and ready status. Switching changes the shared local model
server and both Hermes model configurations. It may take several minutes.
Chats and new GPU experiments pause during the switch; an existing chat or
experiment must finish before switching. Configuration is saved only after the
requested model responds. A failed switch displays an error and allows a retry;
it does not silently claim the old server is still available.

Dashboard-initiated models run in the separate `cuphoton-model` user service.
Inspect logs with `journalctl --user -u cuphoton-model`. After reboot, use the
existing restart command above or select **Apply model** in the dashboard.
`start_model.py` now follows the saved profile selection when run without an
argument. A dashboard restart during switching reports an interrupted switch;
select and apply the desired model again to reconnect.

Model-selector validation: five control tests passed; real Chromium interactions
switched Gemma → Qwen → Gemma, verified configuration against the served model
ID, and confirmed chat re-enabled and answered correctly after the return switch.
Concurrent switching, chat, and GPU-run requests were rejected during loading.

## Nemotron and sample questions

Darknight also has a complete cached **NVIDIA Nemotron 3 Nano Omni 30B-A3B
Reasoning NVFP4** checkpoint (snapshot
`16993199e436da4ba75ddc410855f87e0d996ee6`). `register_nemotron.py` verifies
all weight shards before adding it to `models.extra.json`; no weights are
downloaded. The dropdown includes this additional local model. Its launch
configuration uses vLLM's `nemotron_v3` reasoning parser and `qwen3_coder` tool
parser. This dashboard uses it for text and tool calls; image, video, and audio
inputs remain disabled. Registration does not change the selected model.

Seven **Try a question** buttons fill the composer with editable prompts:
pipeline explanation, measured run comparison, convergence versus fit quality,
residual colors, trial run, matched run, and requirements for real FITS data.
Selecting a sample does not submit it; use **Ask Hermes** to send it.

Nemotron was validated on Darknight: its endpoint became ready, Hermes invoked
`run_pipeline`, and GPU run `20261025-121136-ed0aa7` completed successfully.
All seven sample buttons were clicked in Chromium and verified to populate the
composer with their full prompt without submitting it.

## Live Hermes output and GPU monitor

Open `http://localhost:8765/hermes` for the standalone agent or use the
embedded dashboard panel. Both show the same recent chat feed, including
elapsed time, actual tool start/completion events, streamed response text,
and the final answer. Requests run in the background, so opening another tab
does not interrupt them. Each question still starts a fresh Hermes turn.
The adapter uses installed Hermes callbacks without modifying its source.
Reasoning content is not streamed. Recent chat history is held in memory
(up to 20 questions) and resets when the dashboard service restarts.
Event files are stored locally in ignored `chat-runs/`.

Open `http://localhost:8765/gpu` for GPU utilization, memory-controller
utilization, temperature, power, shared system RAM, and the currently served
model. It polls read-only NVIDIA telemetry every two seconds and plots four
minutes of activity while the tab is open. GB10 does not report dedicated
GPU memory usage through this query, so that field is marked unavailable;
shared system RAM must not be interpreted as GPU-only usage.

These localhost links use the existing SSH tunnel to Darknight port 8765.

## Internet access

Darknight runs an authenticated gateway on loopback port 8766
(`public_server.py`) and an outbound Cloudflare Quick Tunnel. Public HTTPS
routes include `/hermes`, `/gpu`, and the pipeline dashboard at `/`.
The gateway requires HTTP Basic login for every page and API, checks
cross-origin POST requests, and forwards only to the local dashboard.
The shared login grants control of Hermes, model selection, and experiments.

The password is in `~/.config/cuphoton-public.env` on Darknight (mode 0600).
The user services are `cuphoton-public` and `cuphoton-tunnel`.
Find the current public URL with
`journalctl --user -u cuphoton-tunnel --no-pager`.
Stop internet access with `systemctl --user disable --now cuphoton-tunnel`.
The address changes after a tunnel restart; a fixed URL requires a named
tunnel and a domain. Spark must remain online.

## Individual script functions as MCP tools

Hermes now exposes all ten top-level helpers defined in
`examples/imaging-pipeline/run_imaging_pipeline.py`, alongside `list_runs`
and `run_pipeline` (12 tools total):

- `gaussian2d`, `make_scene`: generate numeric array artifacts.
- `write_fits`: save an array to a new FITS file with a north-up WCS.
- `stretch_gray`, `stretch_div`: create display-scaled uint8 arrays.
- `label_panel`, `panel`, `panel_kernel`, `residual_colorbar`,
  `show_row`: create labeled PNG images and compositions.

Adapters live in `imaging_tools.py`. They load the original helper definitions
and scene constants via AST without executing the script's top-level pipeline.
The nested fallback `display` is an environment shim, not a scientific helper.
Imported cuPhoton APIs are not independently exposed by this change.
The original source is unchanged; the existing full GPU pipeline remains
available through `run_pipeline`.

Calls pass opaque artifact IDs instead of raw arrays or arbitrary file paths.
Arrays are saved under ignored `tool-artifacts/`; PNG and FITS outputs have
relative download URLs served by the dashboard (and its authenticated public
gateway). Artifacts persist across MCP subprocess restarts. They are not
automatically deleted; manage the directory when outputs are no longer needed.
Helper computations use NumPy/SciPy on CPU, as in the original script.

Example prompt: "Create the synthetic scene with moving=[120,108,14,2.1] and
seeing=0.65, render it as a labeled grayscale panel, and give me its image link."

Validation: `../.venv/bin/python -m unittest test_imaging_tools -v` from this
directory covers all ten adapters, array fidelity, FITS HDU/WCS, image
composition dimensions, invalid inputs/path traversal, and all 12 MCP schemas.

## Dashboard theme

The main dashboard, standalone Hermes page, and GPU monitor share the
market-analysis-claw-demo charcoal/NVIDIA-green theme. The top-right theme
button switches between dark and light and saves the preference in this
browser. See dashboard/THEME-NOTICE.md for the source revision and license.
After editing dashboard/theme.css or theme.js, run
`python3 dashboard/build_theme.py` to regenerate the embedded assets.
