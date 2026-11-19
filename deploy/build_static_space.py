"""Build the free static Hugging Face Space (demo mode only, no backend, no API key).

  python3 deploy/build_static_space.py            -> deploy/static_space/ (index.html, assets/, data/*.json, README.md)
  hf upload <user>/historical-atlas deploy/static_space . --repo-type space

Live questions need a compute Space (ZeroGPU Gradio wrapper, see deploy/zerogpu/), which a free account can host once it
is 30 days old.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / "deploy" / "static_space"
ST = R / "backend" / "data" / "static"

subprocess.run(["npm", "run", "build", "--", "--outDir", str(OUT), "--emptyOutDir"], cwd=R / "frontend", check=True,
               env={**os.environ, "VITE_STATIC": "1"})
(OUT / "data").mkdir(exist_ok=True)
shutil.copy(ST / "borders.geojson", OUT / "data" / "borders.json")
shutil.copy(ST / "cases.geojson", OUT / "data" / "cases.json")
shutil.copy(ST / "demo_conversations.json", OUT / "data" / "demo.json")
moments = {k: v for k, v in json.loads((ST / "moments.json").read_text()).items() if not k.startswith("_")}
(OUT / "data" / "moments.json").write_text(json.dumps(moments, ensure_ascii=False))
(OUT / "README.md").write_text("""---
title: Historical Atlas
emoji: 🗺️
colorFrom: gray
colorTo: blue
sdk: static
app_file: index.html
pinned: false
license: cc-by-nc-sa-4.0
---

Demo mode of github.com/JBarens/historical-atlas: grounded answers over Hansard and FRUS on five League of Nations
disputes (1920-1926). Country borders: CShapes 2.0, Schvitz et al. 2022 (ETH Zurich), CC BY-NC-SA 4.0.
Contains Parliamentary information licensed under the Open Parliament Licence v3.0. FRUS: public domain.
ONS CDKO: Open Government Licence v3.0.
""")
print("built", OUT, sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) // 1000, "kB")
