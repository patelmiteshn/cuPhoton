"""Execute the source notebook, retaining stage status and scientific provenance."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'examples/imaging-pipeline/run_imaging_pipeline.ipynb'

def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False))
    tmp.replace(path)

def run(folder, sigma):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    os.environ['WORK_DIR'] = str(folder)
    source = NOTEBOOK.read_bytes()
    cells = [c for c in json.loads(source)['cells'] if c['cell_type'] == 'code']
    stages = ['Setup', 'Load', 'Align', 'Subtract', 'Fit', 'Plot']
    report = {'id': folder.name, 'status': 'running', 'kernel_sigma': sigma,
              'seeing_sigma': 0.65, 'stages': [], 'source_sha256': hashlib.sha256(source).hexdigest(),
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'started': time.time(), 'synthetic': True}
    ns = {'__name__': '__main__'}
    try:
        if len(cells) != len(stages):
            raise ValueError('Notebook structure changed; review worker stage mapping')
        for index, (cell, stage) in enumerate(zip(cells, stages)):
            entry = {'name': stage, 'status': 'running'}
            report['stages'].append(entry)
            write(folder / 'report.json', report)
            tree = ast.parse(''.join(cell['source']))
            if index == 0:
                found = False
                for node in tree.body:
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'KERNEL_SIGMA' for t in node.targets):
                        node.value = ast.Constant(sigma)
                        found = True
                if not found:
                    raise ValueError('Notebook no longer defines KERNEL_SIGMA')
                ast.fix_missing_locations(tree)
            start = time.monotonic()
            exec(compile(tree, str(NOTEBOOK), 'exec'), ns)
            if index == 0:
                ns['display'] = lambda obj: None
            entry.update(status='complete', seconds=round(time.monotonic()-start, 3))
        import numpy as np
        fit, result = ns['fit'], ns['result']
        report.update(status='complete', metrics={
            'static_rms': float(np.sqrt(fit.chi2 / fit.fit_pixel_count)),
            'kernel_sum': float(fit.kernel.sum()), 'fit_pixels': int(fit.fit_pixel_count),
            'converged': bool(result.converged[0]),
            'residual_fraction': float(ns['residual_fraction']),
            'centers_error_px': (result.parameters[0, 4:] - ns['truth_xy']).tolist(),
            'parameters': dict(zip(ns['model'].parameter_names, result.parameters[0].tolist())),
            'backends': {'load': str(ns['images'].device), 'align': ns['aligned'].backend,
                         'subtract': fit.backend, 'fit': result.backend},
        }, figures=['01_loaded_fits.png', '02_xrep_aligned.png', '03_subtraction.png', '04_dipole.png'])
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if report['stages']:
            report['stages'][-1]['status'] = 'failed'
        raise
    finally:
        report['finished'] = time.time()
        write(folder / 'report.json', report)

if __name__ == '__main__':
    run(sys.argv[1], float(sys.argv[2]))
