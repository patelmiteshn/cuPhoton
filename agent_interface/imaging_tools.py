"""MCP adapters for every top-level helper in run_imaging_pipeline.py.

Load only function definitions and required constants: importing that executable
script would otherwise run the entire GPU pipeline. Arrays remain on disk and
are passed between tools by opaque artifact IDs, never arbitrary filesystem paths.
"""
import ast
import contextlib
import io
from functools import lru_cache
import math
from pathlib import Path
import re
import uuid

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / 'examples/imaging-pipeline/run_imaging_pipeline.py'
STORE = BASE / 'tool-artifacts'
NAMES = {'gaussian2d', 'make_scene', 'write_fits', 'stretch_gray', 'stretch_div',
         'label_panel', 'panel', 'panel_kernel', 'residual_colorbar', 'show_row'}

@lru_cache(maxsize=1)
def helpers():
    import numpy as np
    from astropy.io import fits
    from PIL import Image, ImageDraw, ImageFont
    from scipy.ndimage import gaussian_filter
    tree = ast.parse(SOURCE.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
    if {n.name for n in nodes} != NAMES:
        raise RuntimeError('Pipeline helper definitions changed; update the MCP adapters')
    constants = [n for n in tree.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id in {'SHAPE', 'STARS'} for t in n.targets)]
    scope = dict(np=np, fits=fits, Image=Image, ImageDraw=ImageDraw,
                 ImageFont=ImageFont, gaussian_filter=gaussian_filter, display=lambda obj: None)
    exec(compile(ast.Module(body=constants + nodes, type_ignores=[]), str(SOURCE), 'exec'), scope)
    STORE.mkdir(mode=0o700, exist_ok=True)
    return scope

def finite(value, name, low=-1e6, high=1e6):
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite and between {low} and {high}')
    return value

def dimensions(shape):
    if len(shape) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1024 for v in shape):
        raise ValueError('shape must contain two integers from 1 to 1024')
    return tuple(shape)

def validate_render(size, label=None, limit=None):
    if not 32 <= size <= 1024: raise ValueError('size must be 32–1024 pixels')
    if label is not None and len(label) > 240: raise ValueError('label is limited to 240 characters')
    if limit is not None: finite(limit, 'limit', 1e-8)

def artifact_path(artifact_id, suffix):
    if not re.fullmatch(r'[0-9a-f]{32}', artifact_id): raise ValueError('Invalid artifact ID')
    path = STORE / (artifact_id + suffix)
    if not path.is_file(): raise ValueError(f'Artifact not found or wrong type: {artifact_id}')
    return path

def array(artifact_id):
    np = helpers()['np']
    arr = np.load(artifact_path(artifact_id, '.npy'), allow_pickle=False)
    if arr.ndim != 2: raise ValueError('This tool requires a two-dimensional array')
    return arr

def image(artifact_id):
    helpers()
    with helpers()['Image'].open(artifact_path(artifact_id, '.png')) as im:
        return im.convert('RGB')

def save_array(arr):
    np = helpers()['np']
    key = uuid.uuid4().hex
    np.save(STORE / (key + '.npy'), arr, allow_pickle=False)
    return {'artifact_id': key, 'kind': 'array', 'shape': list(arr.shape),
            'dtype': str(arr.dtype), 'min': float(np.min(arr)), 'max': float(np.max(arr))}

def save_image(im):
    helpers()
    key = uuid.uuid4().hex
    im.save(STORE / (key + '.png'))
    return {'artifact_id': key, 'kind': 'image', 'width': im.width, 'height': im.height,
            'url': '/tool-artifacts/' + key + '.png'}

def gaussian2d(shape: list[int], y0: float, x0: float, amp: float, sigma: float) -> dict:
    """Generate a 2D Gaussian array. Returns artifact_id for downstream tools; shape is [height,width], coordinates are pixels."""
    shape = dimensions(shape)
    for value, name in [(y0,'y0'),(x0,'x0'),(amp,'amp')]: finite(value,name)
    finite(sigma,'sigma',0.001,1024)
    return save_array(helpers()['gaussian2d'](shape,y0,x0,amp,sigma))

def make_scene(moving: list[float], seeing: float = 0.0) -> dict:
    """Generate the script's fixed 256x256 synthetic star scene. moving=[y,x,amplitude,sigma]; seeing is added Gaussian blur in pixels. Returns array artifact_id."""
    if len(moving) != 4: raise ValueError('moving must be [y,x,amplitude,sigma]')
    for value in moving: finite(value,'moving value')
    finite(moving[3],'sigma',0.001,256)
    finite(seeing,'seeing',0,32)
    return save_array(helpers()['make_scene'](moving,seeing))

def write_fits(array_id: str, crval: list[float] = [150.0,2.0], pixel_scale: float = 0.2) -> dict:
    """Write an array artifact as FITS with a north-up WCS and IMAGE extension (HDU 1). crval=[RA,Dec] degrees; pixel_scale arcsec/pixel. Returns a downloadable artifact; cannot overwrite arbitrary paths."""
    from cuphoton.xrep import make_north_up_wcs
    arr = array(array_id)
    if len(crval) != 2: raise ValueError('crval must be [RA,Dec]')
    finite(crval[0],'RA',0,360); finite(crval[1],'Dec',-90,90)
    finite(pixel_scale,'pixel_scale',0.0001,3600)
    wcs = make_north_up_wcs(tuple(crval),arr.shape,pixel_scale)
    key = uuid.uuid4().hex
    helpers()['write_fits'](STORE/(key+'.fits'),arr,wcs)
    return {'artifact_id':key,'kind':'fits','url':'/tool-artifacts/'+key+'.fits','hdu':1,'shape':list(arr.shape)}

def stretch_gray(array_id: str) -> dict:
    """Apply the script's 1st–99.5th percentile grayscale stretch to an array. Returns uint8 array artifact_id (visualization values, not scientific intensities)."""
    return save_array(helpers()['stretch_gray'](array(array_id)))

def stretch_div(array_id: str, limit: float | None = None) -> dict:
    """Map a signed array to red-positive/blue-negative RGB uint8. limit is symmetric range in image units; default is 99th percentile absolute value. Returns RGB array and PNG preview with the same artifact_id."""
    if limit is not None: finite(limit,'limit',1e-8)
    data = helpers()['stretch_div'](array(array_id),limit)
    result = save_array(data)
    helpers()['Image'].fromarray(data).save(STORE/(result['artifact_id']+'.png'))
    result['url']='/tool-artifacts/'+result['artifact_id']+'.png'
    return result

def label_panel(image_id: str, label: str) -> dict:
    """Add a text label above a PNG image artifact. Returns a new image artifact and URL."""
    validate_render(256,label)
    im = image(image_id)
    if im.height > 2048 or im.width > 8192: raise ValueError('Image too large to label')
    return save_image(helpers()['label_panel'](im,label))

def panel(array_id: str, diverging: bool = False, size: int = 256,
          limit: float | None = None, label: str | None = None) -> dict:
    """Render a 2D array artifact as a square PNG. Use diverging=True for signed residuals; limit is in image units. Returns image artifact_id and URL."""
    validate_render(size,label,limit)
    return save_image(helpers()['panel'](array(array_id),diverging,size,limit,label))

def panel_kernel(array_id: str, size: int = 256, zoom: int = 10, label: str | None = None) -> dict:
    """Render an array as a centered, zoomed grayscale kernel PNG. zoom is an integer magnification; output is cropped to size."""
    validate_render(size,label)
    if not 1 <= zoom <= 32: raise ValueError('zoom must be 1–32')
    arr=array(array_id)
    if max(arr.shape)*zoom > 4096: raise ValueError('Zoomed array exceeds 4096 pixels')
    return save_image(helpers()['panel_kernel'](arr,size,zoom,label))

def residual_colorbar(limit: float, size: int = 256) -> dict:
    """Create a PNG colorbar labeled from +limit to -limit in image units for residual panels."""
    validate_render(size,limit=limit)
    return save_image(helpers()['residual_colorbar'](limit,size))

def show_row(image_ids: list[str], gap: int = 16) -> dict:
    """Combine 1–8 PNG image artifacts into one horizontal row. Returns a new image artifact and downloadable URL."""
    if not 1 <= len(image_ids) <= 8: raise ValueError('Supply 1–8 image IDs')
    if not 0 <= gap <= 128: raise ValueError('gap must be 0–128 pixels')
    ims=[image(key) for key in image_ids]
    width=sum(im.width for im in ims)+(len(ims)-1)*gap
    if width > 8192 or max(im.height for im in ims) > 2048: raise ValueError('Combined image too large')
    key=uuid.uuid4().hex
    with contextlib.redirect_stdout(io.StringIO()):
        helpers()['show_row'](*ims,path=STORE/(key+'.png'),gap=gap)
    return {'artifact_id':key,'kind':'image','width':width,'height':max(im.height for im in ims),'url':'/tool-artifacts/'+key+'.png'}

def register(mcp):
    for name in sorted(NAMES): mcp.tool()(globals()[name])
