"""Hermes tools proxy to the dashboard's single scheduler."""
import json
from urllib.request import Request, urlopen
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('cuphoton')

@mcp.tool()
def list_runs() -> list:
    """Read saved runs. metrics.residual_fraction is peak dipole residual / stamp peak (multiply by 100 for percent). centers_error_px is coordinate error in pixels, never percent. static_rms is image-unit RMS."""
    with urlopen('http://127.0.0.1:8765/api/runs', timeout=10) as r:
        return json.load(r)

@mcp.tool()
def run_pipeline(kernel_sigma: float = 1.6) -> dict:
    """Start the synthetic notebook on GPU. 1.6 is trial; 0.65 matches planted seeing. Poll list_runs in a later turn; never invent results."""
    req = Request('http://127.0.0.1:8765/api/run', data=json.dumps({'sigma': kernel_sigma}).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=10) as r:
        return json.load(r)

from imaging_tools import register
register(mcp)

if __name__ == '__main__':
    mcp.run()
