# cuPhoton capability and contract guide

Use documents in the deployed checkout first. The source index is [NVIDIA/cuPhoton/docs](https://github.com/NVIDIA/cuPhoton/tree/main/docs). This reference synthesizes the local checkout at revision `987111ee0cbfa0c8b3f322a9782f5c821f3430b8`; verify APIs against the running installation.

| Research need | Read in the checkout | Adapter boundary |
| --- | --- | --- |
| Load FITS pixels | `docs/components/xdr.md` | Explicit HDU, dtype, reader and read receipt; xDR requires CUDA 13, shared readers may use Astropy. |
| Align celestial images | `docs/components/xrep.md` | Input/target WCS, output grid, interpolation, mask and variance propagation. |
| Match PSF/background and subtract | `docs/components/xpois.md` | Aligned reference/target, solver, odd kernel, selected pixels and target variance. |
| Measure dipoles | `docs/components/xfit.md` | Candidate stamps, model, masks/variance, fit status, covariance and residuals. |
| Score transient candidates | `docs/components/xscan.md` | Compatible checkpoint and preprocessing, supplied candidates, pair/triplet channels. |
| Analyze X-ray traces/detectors | `docs/xray/README.md` | HDF5 schema, delay axis, normalization, ROI and detector artifact contract. |
| Compose or extend stages | `docs/architecture.md`, `docs/adapting-workflows.md`, `docs/data-artifacts.md` | Explicit contracts and minimal adapters; candidate detection remains caller-owned where not supplied by a workflow. |
| Choose runtime/test inputs | `docs/getting-started.md`, `docs/quickstarts.md`, `docs/troubleshooting.md` | Installed extras, native extensions, CPU smoke test and target GPU verification. |

For multi-process/multi-host requests, additionally read the installed distributed execution and MPI/Dragon guides; do not introduce a distributed runtime for a small single-host task.

## Semantics that adapters must retain

- Arrays generally use `(y, x)` storage. xFit FITS manifests specify candidate centers as zero-based `(x, y)`; xScan FITS APIs use `(y, x)`. Convert explicitly at boundaries.
- Boolean fit masks use `True` for included pixels. Instrument bit masks require an explicit bad-bit policy.
- Fit variance is in squared image units and positive on selected pixels. xRep variance propagation accepts nonnegative finite variance and has documented no-data behavior. Resampling introduces covariance that a diagonal variance plane does not capture.
- xFit difference batches have shape `(batch, y, x)`; split batches are `(batch, 3, y, x)` ordered difference, positive, negative. A `(batch, y, x)` auxiliary is per-candidate even when batch equals three.
- xPois requires shape-matched aligned image pairs. Its residual is target minus matched reference. Spatial fit positions use post-crop `(y, x)` coordinates; duplicates increase weight.
- xRep handles geometry; it does not make PSFs identical. Preserve target WCS and invalid footprints.
- xScan needs appropriate checkpoints and preprocessing. Synthetic/placeholder labels establish plumbing only; they are not validated training labels. Feature joins must preserve candidate IDs and exact stamp identity.
- xRay detector ROIs use `(x, y)` origins and `(width, height)` extents; output arrays remain row-major. Detector maps may represent tile-level fits.
- Load numerical artifacts without pickle. Preserve units, source hashes, WCS/HDU identity, mask policy and candidate order with outputs.

## Existing notebook interpretation

The deployed experiment uses synthetic images. Kernel sigma 1.6 is a trial and 0.65 matches planted added blur; neither value is a universal observational default. The solver fits kernel coefficients, not sigma. Pipeline fit chi-square has no supplied variance and is an unweighted sum of squares. `residual_fraction` is peak dipole residual divided by stamp peak, while center error is in pixels. Convergence and residual quality are separate.

Host transfers exist in the walkthrough. Do not call it zero-copy or assume xDR means native GPUDirect Storage. Use measured backend/read receipts and distinguish end-to-end timing from kernel timing. No detection significance or real-observation accuracy follows from the synthetic fixture.
