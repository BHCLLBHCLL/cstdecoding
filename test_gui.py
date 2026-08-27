# -*- coding: utf-8 -*-
"""Quick test of cst_gui loading phone.cst.

Usage:
    python test_gui.py                        # normal mode (with display)
    set QT_QPA_PLATFORM=offscreen && python test_gui.py  # offscreen mode
"""
import sys
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from cst_gui import CSTMainWindow
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)
app.setStyle('Fusion')

w = CSTMainWindow(enable_3d=False)
w.resize(1200, 800)
w.show()

print('Window created OK')
print(f'Window title: {w.windowTitle()}')
print(f'VTK viewport: {"VTK" if w.viewport.is_vtk_available() else "Qt Canvas (fallback)"}')
print(f'Nav tree items: {w.nav_tree.tree.topLevelItemCount()}')
for i in range(min(5, w.nav_tree.tree.topLevelItemCount())):
    item = w.nav_tree.tree.topLevelItem(i)
    print(f'  [{i}] {item.text(0)}')

print('Loading phone.cst...')
cst_path = r'D:\training\cst\CST Phone 5G.cst'
if os.path.exists(cst_path):
    w._load_cst(cst_path)
else:
    print(f'WARNING: {cst_path} not found, using default project')
    w._project_data = {
        "name": "demo.cst",
        "components": [
            {"name": "Substrate", "material": "Rogers RO4003", "bounds": (-50, 50, -30, 30, -1, 0)},
            {"name": "GroundPlane", "material": "PEC", "bounds": (-50, 50, -30, 30, -0.1, 0)},
            {"name": "Patch", "material": "Copper", "bounds": (-20, 20, -15, 15, 0.5, 0.6)},
            {"name": "Via", "material": "PEC", "bounds": (-1, 1, -1, 1, -1, 0.6)},
        ],
        "materials": [
            {"name": "PEC", "epsilon": "1", "mu": "1", "type": "Perfect"},
            {"name": "Rogers RO4003", "epsilon": "3.55", "mu": "1", "type": "Dielectric"},
            {"name": "Copper", "epsilon": "1", "mu": "1", "type": "Conductor"},
        ],
        "ports": [
            {"name": "Port 1", "port_number": 1, "impedance": "50", "type": "Discrete"},
        ],
        "monitors": [
            {"name": "FieldMonitor_0", "field_type": "E-Field"},
            {"name": "Farfield_0", "field_type": "Farfield"},
        ],
        "parameters": [
            {"name": "substrate_h", "expr": "0.508", "value": "0.508", "description": "Substrate height (mm)"},
            {"name": "patch_w", "expr": "40", "value": "40", "description": "Patch width (mm)"},
            {"name": "patch_l", "expr": "30", "value": "30", "description": "Patch length (mm)"},
            {"name": "freq", "expr": "5.0", "value": "5.0", "description": "Center frequency (GHz)"},
        ],
        "progress": [
            ("demo.cst", "Loaded (demo data)"),
        ],
    }
    w.nav_tree.populate_from_project(w._project_data)
    w.param_list.set_parameters(w._project_data.get("parameters", []))
    w.progress_panel.set_progress(w._project_data.get("progress", []))
    w.viewport.render_project(w._project_data)
    w.setWindowTitle("demo.cst — CST Studio Suite 2024")

pd = w._project_data
print(f'\n=== Project Data ===')
print(f'Components: {len(pd.get("components", []))}')
print(f'Materials: {len(pd.get("materials", []))}')
print(f'Ports: {len(pd.get("ports", []))}')
print(f'Monitors: {len(pd.get("monitors", []))}')
print(f'Parameters: {len(pd.get("parameters", []))}')
print(f'Groups: {len(pd.get("groups", []))}')
print(f'Faces: {len(pd.get("faces", []))}')
print(f'Curves: {len(pd.get("curves", []))}')
print(f'WCS: {len(pd.get("wcs", []))}')
print(f'Probes: {len(pd.get("probes", []))}')
print(f'Lumped: {len(pd.get("lumped", []))}')

print(f'\n--- Components ---')
bboxes = {c.get("bounds") for c in pd.get("components", [])}
print(f'Unique AABBs: {len(bboxes)}')
n_mesh = sum(1 for c in pd.get("components", []) if c.get("mesh"))
n_tri = sum(len(c["mesh"]["faces"]) for c in pd.get("components", []) if c.get("mesh"))
print(f'Tessellated: {n_mesh} bodies, {n_tri} triangles')
names = [c["name"] for c in pd.get("components", [])]
for key in ("Phone/Battery:Cell", "Phone/Camera:Lens", "Phone/Housing:cover"):
    print(f'  has {key}: {key in names}')
for c in pd.get('components', [])[:5]:
    print(f'  {c["name"]}: mat={c["material"]}, bounds={c["bounds"]}')

print(f'\n--- Materials ---')
for m in pd.get('materials', [])[:5]:
    print(f'  {m["name"]}')

print(f'\n--- Ports ---')
for p in pd.get('ports', [])[:5]:
    print(f'  {p["name"]}: Z={p["impedance"]} type={p.get("type", "?")}')

print(f'\n--- Monitors ---')
for m in pd.get('monitors', [])[:5]:
    print(f'  {m["name"]}: type={m.get("field_type", "?")}')

print(f'\n--- Parameters ---')
for p in pd.get('parameters', [])[:5]:
    print(f'  {p["name"]} = {p["value"]} ({p.get("description", "")})')

print(f'\n{"="*40}')
print('SUCCESS — GUI test completed')
print(f'{"="*40}')

app.quit()