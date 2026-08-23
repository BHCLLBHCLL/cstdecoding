# -*- coding: utf-8 -*-
"""M12 acceptance matrix: 11 sample .cst files, counts, save-as, screenshots.

Large customer files stay outside git. Discover them via CST_SAMPLES or
D:\\training\\cst. Container open/save always; GUI + SAB tessellation is
optional per sample (SAR skips SAB in the matrix — file is 50+ MB).
"""

from __future__ import annotations

import os
from pathlib import Path

from cst_parser import open_cst, write_cst

# Official 11-sample set from README §5.
SAMPLES = (
    {
        "id": "phone",
        "file": "CST Phone 5G.cst",
        "kind": "sab_import",
        "gui": True,
        "load_sab": True,
        "min_entries": 50,
        "min_materials": 1,
        "screens": ("nav_tree", "view_3d", "components"),
    },
    {
        "id": "ifa",
        "file": "IFA_design.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_components": 1,
        "screens": ("nav_tree", "view_3d", "parameters"),
    },
    {
        "id": "ship",
        "file": "RCS of a Ship.cst",
        "kind": "modelcache",
        "gui": True,
        "load_sab": True,
        "min_entries": 80,
        "screens": ("nav_tree", "view_3d", "mesh_view"),
    },
    {
        "id": "sar",
        "file": "SAR Head Hand and Phone.cst",
        "kind": "multi_sab",
        "gui": True,
        "load_sab": False,
        "min_entries": 100,
        "screens": ("nav_tree", "view_3d"),
    },
    {
        "id": "single_antenna",
        "file": "SingleAntenna.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_components": 1,
        "screens": ("nav_tree", "view_3d"),
    },
    {
        "id": "dipole_v1",
        "file": "dipole1_monitors7.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_monitors": 1,
        "screens": ("nav_tree", "monitors"),
    },
    {
        "id": "dipole_v2",
        "file": "dipole1_monitors7v2.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_ports": 1,
        "screens": ("nav_tree", "ports"),
    },
    {
        "id": "dipole_v3",
        "file": "dipole1_monitors7v3.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_ports": 1,
        "screens": ("nav_tree", "ports"),
    },
    {
        "id": "patch_v1",
        "file": "microstrip_patch_antenna.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_materials": 1,
        "screens": ("nav_tree", "materials"),
    },
    {
        "id": "patch_v2",
        "file": "microstrip_patch_antennav2.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_monitors": 1,
        "screens": ("nav_tree", "monitors"),
    },
    {
        "id": "patch_v3",
        "file": "microstrip_patch_antennav3.cst",
        "kind": "parametric",
        "gui": True,
        "load_sab": True,
        "min_entries": 20,
        "min_ports": 1,
        "screens": ("nav_tree", "ports", "view_3d"),
    },
)

SCREEN_CHECKLIST = (
    {"id": "nav_tree", "title": "Navigation Tree categories match CST"},
    {"id": "view_3d", "title": "3D viewport Shading of solids"},
    {"id": "components", "title": "Component / solid names and nesting"},
    {"id": "materials", "title": "Materials list and colours"},
    {"id": "ports", "title": "Discrete / waveguide ports"},
    {"id": "monitors", "title": "Field monitors in the tree"},
    {"id": "parameters", "title": "Parameter List expressions"},
    {"id": "mesh_view", "title": "Mesh View of cached triangles"},
    {"id": "copy_view", "title": "Copy View screenshot is non-empty"},
    {"id": "quad_view", "title": "Quad View 2×2 panes"},
)


def sample_dir() -> Path | None:
    env = os.environ.get("CST_SAMPLES")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend((
        Path(r"D:\training\cst"),
        Path(__file__).resolve().parent.parent / "cst",
        Path.home() / "cst-samples",
    ))
    for folder in candidates:
        if folder.is_dir() and (folder / "CST Phone 5G.cst").is_file():
            return folder
        if folder.is_dir() and any(folder.glob("*.cst")):
            return folder
    return None


def find_sample(rec: dict, root: Path | None = None) -> Path | None:
    root = root or sample_dir()
    if root is None:
        return None
    path = root / rec["file"]
    return path if path.is_file() else None


def container_counts(path) -> dict:
    meta, entries = open_cst(path)
    names = [e["name"].replace("\\", "/") for e in entries]
    has_mod = any(n.endswith("Model/3D/Model.mod") for n in names)
    has_params = any(n.endswith("Model/Parameters.json") for n in names)
    has_cache = any("ModelCache/" in n for n in names)
    n_sab = sum(1 for n in names if n.lower().endswith(".sab"))
    n_r1d = sum(1 for n in names if n.lower().endswith(".r1d"))
    return {
        "entries": len(entries),
        "has_mod": has_mod,
        "has_params": has_params,
        "has_cache": has_cache,
        "sab_files": n_sab,
        "r1d_files": n_r1d,
        "cst_version": (meta or {}).get("cst_version") or "",
        "entry_names": names,
    }


def save_as_roundtrip(src, dest) -> dict:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    _meta, entries = open_cst(src)
    files = [(e["name"], e["content"]) for e in entries]
    write_cst(dest, files)
    again = container_counts(dest)
    first = container_counts(src)
    return {
        "ok": again["entries"] == first["entries"]
        and set(again["entry_names"]) == set(first["entry_names"]),
        "src_entries": first["entries"],
        "dst_entries": again["entries"],
    }


def project_counts(win) -> dict:
    data = win._project_data or {}
    tree = win.nav_tree.tree
    return {
        "components": len(data.get("components") or []),
        "materials": len(data.get("materials") or []),
        "ports": len(data.get("ports") or []),
        "monitors": len(data.get("monitors") or []),
        "probes": len(data.get("probes") or []),
        "parameters": len(data.get("parameters") or []),
        "groups": len(data.get("groups") or []),
        "results_1d": len(data.get("results_1d") or []),
        "tree_roots": tree.topLevelItemCount(),
        "cache_segments": int((data.get("modelcache") or {}).get("segments") or 0),
    }


def grab_ok(win) -> bool:
    try:
        win.resize(640, 400)
        win.show()
        win._on_copy_view()
        pm = win._last_view_pixmap
        return pm is not None and not pm.isNull()
    except Exception:
        return False


def accept_sample(rec: dict, root: Path | None, scratch: Path,
                  win=None) -> dict:
    """Open, count, save-as, optional GUI tree + screenshot."""
    path = find_sample(rec, root)
    out = {
        "id": rec["id"],
        "file": rec["file"],
        "present": path is not None,
        "open": False,
        "save_as": False,
        "counts": {},
        "project": {},
        "screenshot": False,
        "notes": [],
    }
    if path is None:
        out["notes"].append("sample file not found")
        return out
    counts = container_counts(path)
    out["counts"] = {k: v for k, v in counts.items() if k != "entry_names"}
    out["open"] = counts["entries"] >= rec.get("min_entries", 1) and counts["has_mod"]
    if counts["entries"] < rec.get("min_entries", 1):
        out["notes"].append(f"entries {counts['entries']} < {rec.get('min_entries')}")
    dest = scratch / f"accept_{rec['id']}_round.cst"
    trip = save_as_roundtrip(path, dest)
    out["save_as"] = bool(trip["ok"])
    if not trip["ok"]:
        out["notes"].append(
            f"save-as mismatch {trip['src_entries']} vs {trip['dst_entries']}")
    if win is not None and rec.get("gui"):
        win._load_cst(str(path), load_sab=bool(rec.get("load_sab", True)))
        proj = project_counts(win)
        out["project"] = proj
        for key, mk in (
                ("min_components", "components"),
                ("min_materials", "materials"),
                ("min_ports", "ports"),
                ("min_monitors", "monitors"),
        ):
            need = rec.get(key)
            if need and proj.get(mk, 0) < need:
                out["open"] = False
                out["notes"].append(f"{mk} {proj.get(mk)} < {need}")
        if proj.get("tree_roots", 0) < 8:
            out["notes"].append("navigation tree missing categories")
        out["screenshot"] = grab_ok(win)
        if not out["screenshot"]:
            out["notes"].append("Copy View pixmap empty")
    return out


def matrix_ok(rows: list[dict]) -> bool:
    present = [r for r in rows if r.get("present")]
    if not present:
        return False
    return all(r.get("open") and r.get("save_as") for r in present)
