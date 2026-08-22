# -*- coding: utf-8 -*-
"""Mutable CST project helpers: parameters, history, primitives, boolean, transform.

No Qt. GUI holds archive + parsed dict and calls these to write Model.mod /
Parameters.json / ModelHistory.json / Model.hid.
"""

from __future__ import annotations

import copy
import json
import math
import re
from typing import Callable, Iterable

HISTORY_VERSION = "2024.0|33.0.1|20230801"
HISTORY_TAG = f"[VERSION]{HISTORY_VERSION}[/VERSION]"

_PARAM_JSON = "Model/Parameters.json"
_MODEL_MOD = "Model/3D/Model.mod"
_HISTORY_JSON = "Model/3D/ModelHistory.json"
_MODEL_HID = "Model/3D/Model.hid"

_NUM = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_SAFE_EXPR = re.compile(r"^[0-9A-Za-z_+\-*/().eE\s]+$")


# ------------------------------------------------------------------ undo


class UndoStack:
    """Linear undo/redo of (undo_fn, redo_fn, label) triples."""

    def __init__(self, limit: int = 80):
        self.limit = limit
        self._undo: list[tuple[Callable, Callable, str]] = []
        self._redo: list[tuple[Callable, Callable, str]] = []

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo_label(self) -> str:
        return self._undo[-1][2] if self._undo else ""

    def redo_label(self) -> str:
        return self._redo[-1][2] if self._redo else ""

    def push(self, undo: Callable, redo: Callable, label: str = "") -> None:
        self._undo.append((undo, redo, label))
        self._redo.clear()
        if len(self._undo) > self.limit:
            self._undo.pop(0)

    def undo(self) -> str:
        if not self._undo:
            return ""
        undo, redo, label = self._undo.pop()
        undo()
        self._redo.append((undo, redo, label))
        return label

    def redo(self) -> str:
        if not self._redo:
            return ""
        undo, redo, label = self._redo.pop()
        redo()
        self._undo.append((undo, redo, label))
        return label


def snapshot_state(project_data, archive, hidden) -> dict:
    return {
        "project": copy.deepcopy(project_data or {}),
        "archive": dict(archive or {}),
        "hidden": set(hidden or []),
    }


# ------------------------------------------------------------------ archive keys


def archive_key(archive: dict, suffix: str) -> str | None:
    want = suffix.replace("\\", "/").lstrip("/")
    for key in archive:
        if key.replace("\\", "/").endswith(want):
            return key
    return None


def archive_get(archive: dict, suffix: str, default: bytes = b"") -> bytes:
    key = archive_key(archive, suffix)
    if key is None:
        return default
    return archive.get(key, default) or default


def archive_set(archive: dict, suffix: str, data: bytes) -> str:
    key = archive_key(archive, suffix) or suffix.replace("\\", "/")
    archive[key] = data
    return key


def archive_text(archive: dict, suffix: str, encoding: str = "latin-1") -> str:
    return archive_get(archive, suffix).decode(encoding, "replace")


# ------------------------------------------------------------------ parameters


def dump_parameters_json(params: Iterable[dict], version: int = 1) -> bytes:
    recs = []
    for p in params or []:
        recs.append({
            "name": p.get("name", ""),
            "expr": str(p.get("expr", "")),
            "value": str(p.get("value", "")),
            "descr": p.get("description", p.get("descr", "")),
        })
    blob = json.dumps({"parameters": recs, "version": version}, indent=4)
    return (blob + "\n").encode("utf-8")


def _fmt_num(val: float) -> str:
    if abs(val - round(val)) < 1e-12:
        return str(int(round(val)))
    text = f"{val:.12g}"
    return text


def eval_expr(expr, params) -> float:
    """Evaluate a CST-like arithmetic expression against prior parameters."""
    s = str(expr if expr is not None else "0").strip()
    if not s:
        return 0.0
    if _NUM.match(s):
        return float(s)
    if not _SAFE_EXPR.match(s):
        raise ValueError(f"unsafe expression: {expr!r}")
    env = {}
    for p in params or []:
        name = p.get("name")
        if not name:
            continue
        raw = p.get("value") if p.get("value") not in ("", None) else p.get("expr")
        try:
            env[name] = float(raw)
        except (TypeError, ValueError):
            continue
    return float(eval(s, {"__builtins__": {}}, env))


def resolve_parameters(params: list) -> list:
    """Fill `value` from `expr` in list order (later params may use earlier)."""
    out = []
    known = []
    for p in params or []:
        rec = dict(p)
        expr = rec.get("expr", rec.get("value", "0"))
        try:
            val = eval_expr(expr, known)
            rec["value"] = _fmt_num(val)
        except Exception:
            rec["value"] = str(expr)
        out.append(rec)
        known.append(rec)
    return out


def set_parameter_in_mod(text: str, name: str, expr: str) -> str:
    """Replace or append MakeSureParameterExists \"name\", \"expr\"."""
    pat = re.compile(
        rf'(MakeSureParameterExists\s+"{re.escape(name)}"\s*,\s*")([^"]*)(")',
        re.I)
    if pat.search(text):
        return pat.sub(rf'\g<1>{expr}\g<3>', text, count=1)
    block = format_mod_block(
        f"define parameter: {name}",
        f'MakeSureParameterExists "{name}", "{expr}"\n')
    return text.rstrip() + block


def set_parameter_description_in_mod(text: str, name: str, descr: str) -> str:
    if not descr:
        return text
    pat = re.compile(
        rf'(SetParameterDescription\s+"{re.escape(name)}"\s*,\s*")([^"]*)(")',
        re.I)
    if pat.search(text):
        return pat.sub(rf'\g<1>{descr}\g<3>', text, count=1)
    extra = f'SetParameterDescription "{name}", "{descr}"\n'
    if f'MakeSureParameterExists "{name}"' in text:
        return text.rstrip() + "\n" + extra
    return text.rstrip() + format_mod_block(
        f"define parameter: {name}",
        f'MakeSureParameterExists "{name}", "0"\n{extra}')


def write_parameters(archive: dict, params: list) -> None:
    resolved = resolve_parameters(params)
    archive_set(archive, _PARAM_JSON, dump_parameters_json(resolved))
    mod = archive_text(archive, _MODEL_MOD)
    for rec in resolved:
        name = rec.get("name") or ""
        if not name:
            continue
        mod = set_parameter_in_mod(mod, name, str(rec.get("expr", rec.get("value", "0"))))
        descr = rec.get("description", rec.get("descr", ""))
        if descr:
            mod = set_parameter_description_in_mod(mod, name, descr)
    archive_set(archive, _MODEL_MOD, mod.encode("latin-1", "replace"))


# ------------------------------------------------------------------ history / .mod blocks


def format_mod_block(caption: str, code: str) -> str:
    body = code.strip("\n") + "\n"
    return f"\n'@ {caption}\n\n{HISTORY_TAG}\n{body}"


def history_entry(caption: str, code: str) -> dict:
    lines = [ln.rstrip() for ln in code.strip("\n").split("\n")]
    return {
        "caption": caption,
        "version": HISTORY_VERSION,
        "hidden": False,
        "type": "vba",
        "code": lines,
    }


def append_history(archive: dict, caption: str, code: str) -> None:
    block = format_mod_block(caption, code)
    mod = archive_text(archive, _MODEL_MOD)
    archive_set(archive, _MODEL_MOD, (mod.rstrip() + block).encode("latin-1", "replace"))
    raw = archive_get(archive, _HISTORY_JSON)
    if raw:
        try:
            doc = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            doc = {"general": {}, "history": []}
    else:
        doc = {
            "general": {
                "version": "2024.0",
                "acis": "33.0.1",
                "project_type": "MWS",
                "length": "mm",
            },
            "history": [],
        }
    doc.setdefault("history", []).append(history_entry(caption, code))
    blob = json.dumps(doc, indent=4) + "\n"
    archive_set(archive, _HISTORY_JSON, blob.encode("utf-8"))


def rename_in_mod(text: str, old: str, new: str) -> str:
    if not old or old == new:
        return text
    return text.replace(f'"{old}"', f'"{new}"')


def append_solid_delete(archive: dict, names: Iterable[str]) -> None:
    for name in names:
        if not name:
            continue
        append_history(archive, f"delete shape: {name}",
                       f'Solid.Delete "{name}"\n')


def append_solid_rename(archive: dict, old: str, new: str) -> None:
    append_history(archive, f"rename solid: {old} to: {new}",
                   f'Solid.Rename "{old}", "{new}"\n')


def append_group_item(archive: dict, solid: str, group: str) -> None:
    append_history(
        archive, f"add to group: {solid} -> {group}",
        f'Group.AddItem "solid${solid}", "{group}"\n')


def append_component_new(archive: dict, name: str) -> None:
    append_history(archive, f"new component: {name}",
                   f'Component.New "{name}"\n')


def append_component_delete(archive: dict, name: str) -> None:
    append_history(archive, f"delete component: {name}",
                   f'Component.Delete "{name}"\n')


def append_change_material(archive: dict, solid: str, material: str) -> None:
    append_history(
        archive, f"change material: {solid} to: {material}",
        f'Solid.ChangeMaterial "{solid}", "{material}"\n')


# ------------------------------------------------------------------ Model.hid visibility


def parse_hidden_solids(text: str) -> set[str]:
    m = re.search(r"\[start\]solids\n(.*?)\[end\]solids", text or "", re.S)
    if not m:
        return set()
    names = []
    for sm in re.finditer(r"\[start\]([^\n\]]+)\n\[end\]\1", m.group(1)):
        names.append(sm.group(1))
    return set(names)


def dump_hidden_solids(existing: str, names: Iterable[str]) -> str:
    inner = "".join(f"[start]{n}\n[end]{n}\n" for n in sorted(names or []))
    block = (
        "[start]hidden_objects\n[start]solids\n"
        f"{inner}[end]solids\n[end]hidden_objects\n"
    )
    text = existing or ""
    if "[start]hidden_objects" in text:
        return re.sub(
            r"\[start\]hidden_objects\n.*?\[end\]hidden_objects\n",
            block, text, count=1, flags=re.S)
    if text.startswith("20100312"):
        rest = text.split("\n", 1)[1] if "\n" in text else ""
        return "20100312\n" + block + rest
    return "20100312\n" + block


def write_hidden(archive: dict, names: Iterable[str]) -> None:
    existing = archive_text(archive, _MODEL_HID)
    archive_set(
        archive, _MODEL_HID,
        dump_hidden_solids(existing, names).encode("latin-1", "replace"))


# ------------------------------------------------------------------ meshes


def _bounds_of(points) -> tuple:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def box_mesh(xmin, xmax, ymin, ymax, zmin, zmax) -> dict:
    pts = [
        (xmin, ymin, zmin), (xmax, ymin, zmin), (xmax, ymax, zmin), (xmin, ymax, zmin),
        (xmin, ymin, zmax), (xmax, ymin, zmax), (xmax, ymax, zmax), (xmin, ymax, zmax),
    ]
    faces = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    wires = [
        [pts[0], pts[1]], [pts[1], pts[2]], [pts[2], pts[3]], [pts[3], pts[0]],
        [pts[4], pts[5]], [pts[5], pts[6]], [pts[6], pts[7]], [pts[7], pts[4]],
        [pts[0], pts[4]], [pts[1], pts[5]], [pts[2], pts[6]], [pts[3], pts[7]],
    ]
    return {"points": pts, "faces": faces, "wires": wires}


def _circle(cx, cy, z, r, n, axis="z"):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        if axis == "z":
            pts.append((cx + r * c, cy + r * s, z))
        elif axis == "x":
            pts.append((z, cx + r * c, cy + r * s))
        else:
            pts.append((cx + r * c, z, cy + r * s))
    return pts


def cylinder_mesh(cx, cy, zmin, zmax, radius, n=24, inner=0.0) -> dict:
    n = max(8, int(n))
    bot = _circle(cx, cy, zmin, radius, n)
    top = _circle(cx, cy, zmax, radius, n)
    pts = list(bot) + list(top) + [(cx, cy, zmin), (cx, cy, zmax)]
    cbot, ctop = 2 * n, 2 * n + 1
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j))
        faces.append((i, n + j, n + i))
        faces.append((cbot, j, i))
        faces.append((ctop, n + i, n + j))
    wires = [bot + [bot[0]], top + [top[0]]]
    return {"points": pts, "faces": faces, "wires": wires}


def sphere_mesh(cx, cy, cz, radius, nlat=12, nlon=24) -> dict:
    nlat, nlon = max(4, int(nlat)), max(8, int(nlon))
    pts = []
    for i in range(nlat + 1):
        v = math.pi * i / nlat
        sv, cv = math.sin(v), math.cos(v)
        for j in range(nlon):
            u = 2 * math.pi * j / nlon
            pts.append((
                cx + radius * sv * math.cos(u),
                cy + radius * sv * math.sin(u),
                cz + radius * cv,
            ))
    faces = []
    for i in range(nlat):
        for j in range(nlon):
            a = i * nlon + j
            b = i * nlon + (j + 1) % nlon
            c = (i + 1) * nlon + (j + 1) % nlon
            d = (i + 1) * nlon + j
            if i:
                faces.append((a, b, d))
            if i < nlat - 1:
                faces.append((b, c, d))
    return {"points": pts, "faces": faces, "wires": []}


def torus_mesh(cx, cy, cz, major, minor, n_major=24, n_minor=12) -> dict:
    n_major, n_minor = max(8, int(n_major)), max(6, int(n_minor))
    pts = []
    for i in range(n_major):
        u = 2 * math.pi * i / n_major
        cu, su = math.cos(u), math.sin(u)
        for j in range(n_minor):
            v = 2 * math.pi * j / n_minor
            cv, sv = math.cos(v), math.sin(v)
            r = major + minor * cv
            pts.append((cx + r * cu, cy + r * su, cz + minor * sv))
    faces = []
    for i in range(n_major):
        i2 = (i + 1) % n_major
        for j in range(n_minor):
            j2 = (j + 1) % n_minor
            a = i * n_minor + j
            b = i * n_minor + j2
            c = i2 * n_minor + j2
            d = i2 * n_minor + j
            faces.append((a, b, d))
            faces.append((b, c, d))
    return {"points": pts, "faces": faces, "wires": []}


def cone_mesh(cx, cy, zmin, zmax, r_bottom, r_top, n=24) -> dict:
    n = max(8, int(n))
    bot = _circle(cx, cy, zmin, max(r_bottom, 1e-9), n)
    top = _circle(cx, cy, zmax, max(r_top, 1e-9), n)
    pts = bot + top + [(cx, cy, zmin), (cx, cy, zmax)]
    cbot, ctop = 2 * n, 2 * n + 1
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j))
        faces.append((i, n + j, n + i))
        if r_bottom > 1e-9:
            faces.append((cbot, j, i))
        if r_top > 1e-9:
            faces.append((ctop, n + i, n + j))
    return {"points": pts, "faces": faces, "wires": [bot + [bot[0]], top + [top[0]]]}


def mesh_bounds(mesh: dict) -> tuple:
    pts = mesh.get("points") or []
    if not pts:
        return (0, 0, 0, 0, 0, 0)
    return _bounds_of(pts)


def union_bounds(a, b) -> tuple:
    return (
        min(a[0], b[0]), max(a[1], b[1]),
        min(a[2], b[2]), max(a[3], b[3]),
        min(a[4], b[4]), max(a[5], b[5]),
    )


def intersect_bounds(a, b) -> tuple | None:
    xmin, xmax = max(a[0], b[0]), min(a[1], b[1])
    ymin, ymax = max(a[2], b[2]), min(a[3], b[3])
    zmin, zmax = max(a[4], b[4]), min(a[5], b[5])
    if xmax <= xmin or ymax <= ymin or zmax <= zmin:
        return None
    return (xmin, xmax, ymin, ymax, zmin, zmax)


def merge_meshes(a: dict, b: dict) -> dict:
    pa = list(a.get("points") or [])
    pb = list(b.get("points") or [])
    off = len(pa)
    faces = list(a.get("faces") or []) + [
        tuple(i + off for i in f) for f in (b.get("faces") or [])
    ]
    wires = list(a.get("wires") or []) + list(b.get("wires") or [])
    return {"points": pa + pb, "faces": faces, "wires": wires}


def transform_points(points, fn) -> list:
    return [fn(*p) for p in points]


def transform_mesh(mesh: dict, fn) -> dict:
    pts = transform_points(mesh.get("points") or [], fn)
    wires = [[fn(*p) for p in w] for w in (mesh.get("wires") or [])]
    out = dict(mesh)
    out["points"] = pts
    out["wires"] = wires
    return out


def translate_fn(dx, dy, dz):
    return lambda x, y, z: (x + dx, y + dy, z + dz)


def scale_fn(cx, cy, cz, sx, sy, sz):
    return lambda x, y, z: (cx + (x - cx) * sx, cy + (y - cy) * sy, cz + (z - cz) * sz)


def mirror_fn(axis: str, origin=(0.0, 0.0, 0.0)):
    ox, oy, oz = origin
    axis = (axis or "x").lower()

    def fn(x, y, z):
        if axis == "x":
            return (2 * ox - x, y, z)
        if axis == "y":
            return (x, 2 * oy - y, z)
        return (x, y, 2 * oz - z)

    return fn


def rotate_fn(axis: str, deg: float, origin=(0.0, 0.0, 0.0)):
    ox, oy, oz = origin
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    axis = (axis or "z").lower()

    def fn(x, y, z):
        x, y, z = x - ox, y - oy, z - oz
        if axis == "x":
            y, z = y * c - z * s, y * s + z * c
        elif axis == "y":
            x, z = x * c + z * s, -x * s + z * c
        else:
            x, y = x * c - y * s, x * s + y * c
        return (x + ox, y + oy, z + oz)

    return fn


def transform_component(comp: dict, fn) -> dict:
    out = copy.deepcopy(comp)
    mesh = out.get("mesh") or {}
    if mesh.get("points"):
        out["mesh"] = transform_mesh(mesh, fn)
        out["bounds"] = mesh_bounds(out["mesh"])
    elif out.get("bounds"):
        xmin, xmax, ymin, ymax, zmin, zmax = out["bounds"]
        corners = [
            (xmin, ymin, zmin), (xmax, ymin, zmin), (xmax, ymax, zmin), (xmin, ymax, zmin),
            (xmin, ymin, zmax), (xmax, ymin, zmax), (xmax, ymax, zmax), (xmin, ymax, zmax),
        ]
        out["bounds"] = _bounds_of([fn(*p) for p in corners])
        out["mesh"] = box_mesh(*out["bounds"])
    return out


def bounds_center(bounds) -> tuple:
    return (
        0.5 * (bounds[0] + bounds[1]),
        0.5 * (bounds[2] + bounds[3]),
        0.5 * (bounds[4] + bounds[5]),
    )


# ------------------------------------------------------------------ VBA for modeling ops


def brick_vba(name, component, material, xr, yr, zr) -> str:
    return (
        "With Brick\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Component "{component}"\n'
        f'     .Material "{material}"\n'
        f'     .Xrange "{xr[0]}", "{xr[1]}"\n'
        f'     .Yrange "{yr[0]}", "{yr[1]}"\n'
        f'     .Zrange "{zr[0]}", "{zr[1]}"\n'
        "     .Create\n"
        "End With\n"
    )


def cylinder_vba(name, component, material, radius, zmin, zmax,
                 cx="0", cy="0", inner="0") -> str:
    return (
        "With Cylinder\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Component "{component}"\n'
        f'     .Material "{material}"\n'
        f'     .OuterRadius "{radius}"\n'
        f'     .InnerRadius "{inner}"\n'
        '     .Axis "z"\n'
        f'     .Zrange "{zmin}", "{zmax}"\n'
        f'     .Xcenter "{cx}"\n'
        f'     .Ycenter "{cy}"\n'
        '     .Segments "0"\n'
        "     .Create\n"
        "End With\n"
    )


def sphere_vba(name, component, material, radius, cx="0", cy="0", cz="0") -> str:
    return (
        "With Sphere\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Component "{component}"\n'
        f'     .Material "{material}"\n'
        '     .Axis "z"\n'
        f'     .CenterRadius "{radius}"\n'
        '     .TopRadius "0"\n'
        '     .BottomRadius "0"\n'
        f'     .Center "{cx}", "{cy}", "{cz}"\n'
        '     .Segments "0"\n'
        "     .Create\n"
        "End With\n"
    )


def torus_vba(name, component, material, major, minor,
              cx="0", cy="0", cz="0") -> str:
    return (
        "With Torus\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Component "{component}"\n'
        f'     .Material "{material}"\n'
        f'     .OuterRadius "{major}"\n'
        f'     .InnerRadius "{minor}"\n'
        '     .Axis "z"\n'
        f'     .Xcenter "{cx}"\n'
        f'     .Ycenter "{cy}"\n'
        f'     .Zcenter "{cz}"\n'
        '     .Segments "0"\n'
        "     .Create\n"
        "End With\n"
    )


def cone_vba(name, component, material, r_bot, r_top, zmin, zmax,
             cx="0", cy="0") -> str:
    return (
        "With Cone\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Component "{component}"\n'
        f'     .Material "{material}"\n'
        f'     .OuterRadius "{r_bot}"\n'
        f'     .TopRadius "{r_top}"\n'
        '     .InnerRadius "0"\n'
        '     .Axis "z"\n'
        f'     .Zrange "{zmin}", "{zmax}"\n'
        f'     .Xcenter "{cx}"\n'
        f'     .Ycenter "{cy}"\n'
        '     .Segments "0"\n'
        "     .Create\n"
        "End With\n"
    )


def boolean_vba(op: str, target: str, tool: str) -> str:
    names = {"add": "Add", "subtract": "Subtract", "intersect": "Intersect"}
    method = names.get(op.lower(), op)
    return f'Solid.{method} "{target}", "{tool}"\n'


def transform_translate_vba(name, dx, dy, dz) -> str:
    return (
        "With Transform\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Vector "{dx}", "{dy}", "{dz}"\n'
        '     .UsePickedPoints "False"\n'
        '     .InvertPickedPoints "False"\n'
        '     .MultipleObjects "False"\n'
        '     .GroupObjects "False"\n'
        '     .Repetitions "1"\n'
        '     .MultipleSelection "False"\n'
        '     .Destination ""\n'
        '     .Material ""\n'
        '     .Transform "Shape", "Translate"\n'
        "End With\n"
    )


def transform_rotate_vba(name, ax, ay, az, cx="0", cy="0", cz="0") -> str:
    return (
        "With Transform\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        '     .Origin "Free"\n'
        f'     .Center "{cx}", "{cy}", "{cz}"\n'
        f'     .Angle "{ax}", "{ay}", "{az}"\n'
        '     .MultipleObjects "False"\n'
        '     .GroupObjects "False"\n'
        '     .Repetitions "1"\n'
        '     .MultipleSelection "False"\n'
        '     .Destination ""\n'
        '     .Material ""\n'
        '     .Transform "Shape", "Rotate"\n'
        "End With\n"
    )


def transform_mirror_vba(name, nx, ny, nz, cx="0", cy="0", cz="0") -> str:
    return (
        "With Transform\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        '     .Origin "Free"\n'
        f'     .Center "{cx}", "{cy}", "{cz}"\n'
        f'     .PlaneNormal "{nx}", "{ny}", "{nz}"\n'
        '     .MultipleObjects "False"\n'
        '     .GroupObjects "False"\n'
        '     .Repetitions "1"\n'
        '     .MultipleSelection "False"\n'
        '     .Destination ""\n'
        '     .Material ""\n'
        '     .Transform "Shape", "Mirror"\n'
        "End With\n"
    )


def transform_scale_vba(name, sx, sy, sz, cx="0", cy="0", cz="0") -> str:
    return (
        "With Transform\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        '     .Origin "Free"\n'
        f'     .Center "{cx}", "{cy}", "{cz}"\n'
        f'     .ScaleFactor "{sx}", "{sy}", "{sz}"\n'
        '     .MultipleObjects "False"\n'
        '     .GroupObjects "False"\n'
        '     .Repetitions "1"\n'
        '     .MultipleSelection "False"\n'
        '     .Destination ""\n'
        '     .Material ""\n'
        '     .Transform "Shape", "Scale"\n'
        "End With\n"
    )


def material_vba(name, epsilon="1.0", mu="1.0", kappa="0.0", tand="0.0",
                 colour=("0.75", "0.80", "0.90"), folder="") -> str:
    r, g, b = colour
    return (
        "With Material\n"
        "     .Reset\n"
        f'     .Name "{name}"\n'
        f'     .Folder "{folder}"\n'
        '.FrqType "all"\n'
        '.Type "Normal"\n'
        '.SetMaterialUnit "GHz", "mm"\n'
        f'.Epsilon "{epsilon}"\n'
        f'.Mu "{mu}"\n'
        f'.Kappa "{kappa}"\n'
        f'.TanD "{tand}"\n'
        '.TanDFreq "0.0"\n'
        '.TanDGiven "False"\n'
        '.TanDModel "ConstTanD"\n'
        '.KappaM "0.0"\n'
        '.TanDM "0.0"\n'
        '.TanDMFreq "0.0"\n'
        '.TanDMGiven "False"\n'
        '.TanDMModel "ConstKappa"\n'
        '.Rho "0.0"\n'
        '.ThermalType "Normal"\n'
        '.ThermalConductivity "0"\n'
        '.SetActiveMaterial "all"\n'
        f'.Colour "{r}", "{g}", "{b}"\n'
        '.Wireframe "False"\n'
        '.Transparency "0"\n'
        "     .Create\n"
        "End With\n"
    )


def unique_solid_name(existing: set, component: str, base: str) -> str:
    name = f"{component}:{base}"
    if name not in existing:
        return name
    i = 1
    while f"{component}:{base}{i}" in existing:
        i += 1
    return f"{component}:{base}{i}"
