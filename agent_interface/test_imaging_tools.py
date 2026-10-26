"""Exercise source fidelity, artifact chaining, FITS metadata, and MCP schemas."""
import asyncio
import tempfile
import unittest
from pathlib import Path
import numpy as np
from astropy.io import fits
import imaging_tools as t

class ImagingToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=t.STORE
        t.STORE=Path(self.temp.name)
    def tearDown(self):
        t.STORE=self.old
        self.temp.cleanup()
    def test_all_helpers_chain_and_match_source(self):
        a=t.gaussian2d([15,15],7,7,12,2)
        np.testing.assert_array_equal(t.array(a['artifact_id']),t.helpers()['gaussian2d']((15,15),7,7,12,2))
        scene=t.make_scene([120,108,14,2.1],0.65)
        np.testing.assert_array_equal(t.array(scene['artifact_id']),t.helpers()['make_scene']([120,108,14,2.1],0.65))
        gray=t.stretch_gray(scene['artifact_id'])
        self.assertEqual(gray['dtype'],'uint8')
        div=t.stretch_div(scene['artifact_id'],limit=20)
        self.assertEqual(div['shape'],[256,256,3])
        labeled=t.label_panel(div['artifact_id'],'Synthetic scene')
        p=t.panel(scene['artifact_id'],True,256,20,'Scene')
        k=t.panel_kernel(a['artifact_id'],256,10,'Kernel')
        c=t.residual_colorbar(20)
        row=t.show_row([labeled['artifact_id'],p['artifact_id'],k['artifact_id'],c['artifact_id']])
        with t.helpers()['Image'].open(t.artifact_path(row['artifact_id'],'.png')) as im:
            self.assertEqual(im.size,(928,308))
        f=t.write_fits(scene['artifact_id'])
        with fits.open(t.artifact_path(f['artifact_id'],'.fits')) as hdus:
            self.assertEqual(hdus[1].name,'IMAGE')
            self.assertEqual(hdus[1].data.shape,(256,256))
            self.assertEqual(hdus[1].header['CRVAL1'],150)
            np.testing.assert_array_equal(hdus[1].data,t.array(scene['artifact_id']))
    def test_invalid_inputs_and_paths(self):
        for call in [lambda:t.gaussian2d([100000,10],0,0,1,1),
                     lambda:t.gaussian2d([10,10],0,0,1,0),
                     lambda:t.make_scene([1,2,3,float('nan')]),
                     lambda:t.panel('../../etc/passwd'),
                     lambda:t.residual_colorbar(-1),lambda:t.show_row([])]:
            with self.assertRaises(ValueError): call()
    def test_mcp_registration(self):
        from mcp_server import mcp
        tools=asyncio.run(mcp.list_tools())
        self.assertEqual({tool.name for tool in tools},t.NAMES|{'list_runs','run_pipeline'})
        for tool in tools:
            self.assertEqual(tool.inputSchema['type'],'object')

if __name__=='__main__': unittest.main()
