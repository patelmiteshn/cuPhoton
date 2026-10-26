# Theme attribution

Palette and styling adapted from https://github.com/pastorsj/market-analysis-claw-demo
at commit b364db8cc8b6fd1703345aae4605cbd6cefbd7e6, specifically ui/src/app/globals.css and the execution workspace styling.

Upstream UI credits NVIDIA CORPORATION & AFFILIATES (2025–2026) and derives
from NVIDIA-AI-Blueprints/aiq. Distributed under Apache-2.0; see THEME-LICENSE.

Photon Lab modifications: framework-independent CSS, native HTML controls,
responsive scientific dashboard, GPU chart colors, and persisted light/dark toggle.
The reference application's runtime and market-analysis features are not included.

Edit theme.css and theme.js, then run:
python3 dashboard/build_theme.py
This embeds the shared theme into index.html and gpu.html.
