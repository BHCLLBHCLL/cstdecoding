# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict
from sab_bodies import extract_bodies

SAB = os.path.join("extracted", "Model", "3D", "CSTphone2022_1.sab")
b = next(x for x in extract_bodies(open(SAB, "rb").read()) if x["name"].endswith("sh_cans:top"))
m = b["mesh"]
pts = np.asarray(m["points"], float)
faces = m["faces"]

# boundary edges
edge_map = defaultdict(list)
for fi, f in enumerate(faces):
    for k in range(3):
        a, c = f[k], f[(k+1) % 3]
        edge_map[(min(a,c), max(a,c))].append(fi)
bnd = [e for e, v in edge_map.items() if len(v) == 1]

fig, ax = plt.subplots(figsize=(13, 8))
# draw bottom tris (z=-4.275)
for f in faces:
    t = pts[list(f)]
    if abs(t[:, 2].mean() + 4.275) < 0.05:
        arr = np.asarray([t[0], t[1], t[2], t[0]])
        ax.fill(arr[:, 0], arr[:, 1], alpha=0.35, color="gray", edgecolor="0.4", lw=0.4)
# boundary edges in red thick
for e in bnd:
    pa, pb = pts[e[0]], pts[e[1]]
    ax.plot([pa[0], pb[0]], [pa[1], pb[1]], "r-", lw=3, zorder=5)
    ax.plot(*pa[:2], "rs", ms=6, zorder=6)
# label boundary vertices
for e in bnd:
    for vi in e:
        p = pts[vi]
        ax.annotate(f"{p[0]:.1f},{p[1]:.1f}", (p[0], p[1]), fontsize=6, color="red")
ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
ax.set_title("bottom (z=-4.275) triangles + boundary edges (red)")
ax.set_xlim(28, 80); ax.set_ylim(-30, -6)
plt.savefig("_gap_detail.png", dpi=110, bbox_inches="tight")
print("wrote _gap_detail.png, boundary edges:", len(bnd))
