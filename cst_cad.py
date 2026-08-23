# -*- coding: utf-8 -*-
"""CAD exchange: ASCII SAT (ACIS 7.0 subset) export/import.

STEP/IGES are attempted only when OpenCASCADE or CadQuery is installed.
No CST DLLs.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from cst_project import box_mesh, mesh_bounds

__all__ = [
    "project_to_sat", "parse_sat", "sat_to_components",
    "write_sat", "write_step",
]


def _f(v) -> str:
    return f"{float(v):.12g}"


def _header() -> str:
    now = datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %Y")
    prod, ver = "CST Decoding", "ACIS 33.0.1"
    return (
        f"700 0 1 0\n"
        f"{len(prod)} {prod} {len(ver)} {ver} {len(now)} {now}\n"
        f"1 9.9999999999999995e-007 1e-10\n"
    )


def _mesh_of(comp: dict) -> dict | None:
    mesh = comp.get("mesh") or {}
    pts = mesh.get("points") or []
    faces = mesh.get("faces") or []
    if pts and faces:
        return {"points": [tuple(map(float, p)) for p in pts],
                "faces": [tuple(int(i) for i in f[:3]) for f in faces if len(f) >= 3]}
    bounds = comp.get("bounds")
    if bounds and len(bounds) == 6:
        try:
            box = box_mesh(*[float(x) for x in bounds])
        except (TypeError, ValueError):
            return None
        return {"points": box["points"], "faces": box["faces"]}
    return None


def _tri_normal(pts, face):
    a, b, c = pts[face[0]], pts[face[1]], pts[face[2]]
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / ln, ny / ln, nz / ln)


def _sat_entities(solids: list[tuple[str, dict]]) -> str:
    """Emit pointer-consistent SAT 700 records for faceted bodies."""
    ents: list[str] = []

    def add(text: str) -> int:
        ents.append(text if text.endswith(" #") else text + " #")
        return len(ents) - 1

    def ptr(i) -> str:
        return "$-1" if i is None or i < 0 else f"${i}"

    for _name, mesh in solids:
        pts = mesh["points"]
        faces = mesh["faces"]
        if not pts or not faces:
            continue
        body = add("body")
        lump = add("lump")
        xform = add(
            "transform 1 0 0 0 1 0 0 0 1 0 0 0 1 no_rotate no_reflect no_shear")
        shell = add("shell")
        point_ids = [add(f"point $-1 {_f(p[0])} {_f(p[1])} {_f(p[2])}")
                     for p in pts]
        vert_ids = [add("vertex") for _ in pts]
        # edges keyed by sorted vertex pair
        edge_map: dict[tuple[int, int], int] = {}
        straight_ids = []
        edge_ids = []
        for fa in faces:
            for a, b in ((fa[0], fa[1]), (fa[1], fa[2]), (fa[2], fa[0])):
                key = (a, b) if a < b else (b, a)
                if key in edge_map:
                    continue
                pa, pb = pts[key[0]], pts[key[1]]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                sl = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                sid = add(
                    f"straight $-1 {_f(pa[0])} {_f(pa[1])} {_f(pa[2])} "
                    f"{_f(dx / sl)} {_f(dy / sl)} {_f(dz / sl)} 1")
                eid = add("edge")
                edge_map[key] = eid
                straight_ids.append(sid)
                edge_ids.append(eid)
        face_ids = []
        loop_ids = []
        plane_ids = []
        coedge_ids = []
        for fa in faces:
            nrm = _tri_normal(pts, fa)
            o = pts[fa[0]]
            e0 = (pts[fa[1]][0] - o[0], pts[fa[1]][1] - o[1], pts[fa[1]][2] - o[2])
            el = math.sqrt(e0[0] ** 2 + e0[1] ** 2 + e0[2] ** 2) or 1.0
            xdir = (e0[0] / el, e0[1] / el, e0[2] / el)
            plane_ids.append(add(
                f"plane $-1 {_f(o[0])} {_f(o[1])} {_f(o[2])} "
                f"{_f(nrm[0])} {_f(nrm[1])} {_f(nrm[2])} "
                f"{_f(xdir[0])} {_f(xdir[1])} {_f(xdir[2])} forward 1"))
            face_ids.append(add("face"))
            loop_ids.append(add("loop"))
            for _ in range(3):
                coedge_ids.append(add("coedge"))

        ents[body] = f"body {ptr(lump)} $-1 {ptr(xform)} $-1 #"
        ents[lump] = f"lump $-1 $-1 {ptr(shell)} {ptr(body)} #"
        ents[shell] = (
            f"shell $-1 $-1 {ptr(face_ids[0] if face_ids else None)} "
            f"{ptr(lump)} $-1 #")
        for i, vid in enumerate(vert_ids):
            ents[vid] = f"vertex $-1 $-1 {ptr(point_ids[i])} #"
        key_list = list(edge_map.keys())
        for i, key in enumerate(key_list):
            ents[edge_ids[i]] = (
                f"edge $-1 {ptr(vert_ids[key[0]])} {ptr(vert_ids[key[1]])} "
                f"$-1 {ptr(straight_ids[i])} forward 0 1 $-1 #")
        ci = 0
        for ti, fa in enumerate(faces):
            nxt = face_ids[ti + 1] if ti + 1 < len(face_ids) else None
            ents[face_ids[ti]] = (
                f"face {ptr(nxt)} {ptr(loop_ids[ti])} {ptr(shell)} $-1 "
                f"{ptr(plane_ids[ti])} forward single #")
            c0, c1, c2 = coedge_ids[ci], coedge_ids[ci + 1], coedge_ids[ci + 2]
            ents[loop_ids[ti]] = f"loop $-1 {ptr(c0)} {ptr(face_ids[ti])} #"
            for k, (a, b) in enumerate(((fa[0], fa[1]), (fa[1], fa[2]), (fa[2], fa[0]))):
                key = (a, b) if a < b else (b, a)
                nxt_c = (c0, c1, c2)[(k + 1) % 3]
                prv_c = (c0, c1, c2)[(k - 1) % 3]
                sense = "forward" if a < b else "reversed"
                ents[coedge_ids[ci + k]] = (
                    f"coedge {ptr(nxt_c)} {ptr(prv_c)} $-1 "
                    f"{ptr(edge_map[key])} {sense} {ptr(loop_ids[ti])} $-1 #")
            ci += 3
    return "\n".join(ents) + ("\n" if ents else "")


def _trailer(solids: list[tuple[str, dict]]) -> str:
    lines = ["End-of-ACIS-data", f"CST-SOLIDS {len(solids)}"]
    for name, mesh in solids:
        pts = mesh["points"]
        faces = mesh["faces"]
        lines.append(f"name {name}")
        lines.append(f"v {len(pts)}")
        for p in pts:
            lines.append(f"{_f(p[0])} {_f(p[1])} {_f(p[2])}")
        lines.append(f"f {len(faces)}")
        for fa in faces:
            lines.append(f"{fa[0]} {fa[1]} {fa[2]}")
    return "\n".join(lines) + "\n"


def project_to_sat(project_data: dict) -> str:
    """ASCII SAT 700 plus a CST-SOLIDS trailer for reliable round-trip."""
    solids = []
    for comp in (project_data or {}).get("components") or []:
        mesh = _mesh_of(comp)
        if not mesh:
            continue
        solids.append((comp.get("name") or "solid", mesh))
    body = _sat_entities(solids)
    return _header() + body + _trailer(solids)


def parse_sat(text: str) -> list[dict]:
    """Read CST-SOLIDS trailer, or fall back to SAT `point` records."""
    src = (text or "").replace("\r\n", "\n")
    mark = src.find("CST-SOLIDS")
    if mark >= 0:
        return _parse_trailer(src[mark:])
    return _parse_points_only(src)


def _parse_trailer(chunk: str) -> list[dict]:
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    solids = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("name "):
            name = lines[i][5:].strip() or "solid"
            i += 1
            pts, faces = [], []
            if i < len(lines) and lines[i].startswith("v "):
                nv = int(lines[i].split()[1])
                i += 1
                for _ in range(nv):
                    if i >= len(lines):
                        break
                    xs = lines[i].split()
                    pts.append((float(xs[0]), float(xs[1]), float(xs[2])))
                    i += 1
            if i < len(lines) and lines[i].startswith("f "):
                nf = int(lines[i].split()[1])
                i += 1
                for _ in range(nf):
                    if i >= len(lines):
                        break
                    xs = lines[i].split()
                    faces.append((int(xs[0]), int(xs[1]), int(xs[2])))
                    i += 1
            solids.append({"name": name, "points": pts, "faces": faces})
            continue
        i += 1
    return solids


def _parse_points_only(text: str) -> list[dict]:
    pts = []
    for m in re.finditer(
            r"^point\s+\S+\s+([^\s#]+)\s+([^\s#]+)\s+([^\s#]+)",
            text, re.M):
        try:
            pts.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
        except ValueError:
            continue
    if not pts:
        return []
    return [{"name": "solid", "points": pts, "faces": []}]


def sat_to_components(text: str) -> list[dict]:
    out = []
    for rec in parse_sat(text):
        pts = rec.get("points") or []
        faces = rec.get("faces") or []
        if not pts:
            continue
        mesh = {"points": pts, "faces": faces, "wires": []}
        bounds = mesh_bounds(mesh) if faces else (
            min(p[0] for p in pts), max(p[0] for p in pts),
            min(p[1] for p in pts), max(p[1] for p in pts),
            min(p[2] for p in pts), max(p[2] for p in pts),
        )
        out.append({
            "name": rec.get("name") or "solid",
            "material": "PEC",
            "bounds": bounds,
            "mesh": mesh,
        })
    return out


def write_sat(path, project_data: dict) -> str:
    text = project_to_sat(project_data)
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    return text


def write_step(path, project_data: dict) -> bool:
    """Write STEP if OpenCASCADE / CadQuery is present. Otherwise False."""
    comps = sat_to_components(project_to_sat(project_data))
    if not comps:
        return False
    try:
        from OCC.Core.BRepBuilderAPI import (  # type: ignore
            BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace,
            BRepBuilderAPI_Sewing,
        )
        from OCC.Core.gp import gp_Pnt  # type: ignore
        from OCC.Core.STEPControl import (  # type: ignore
            STEPControl_Writer, STEPControl_AsIs,
        )
        from OCC.Core.IFSelect import IFSelect_RetDone  # type: ignore
    except Exception:
        try:
            import cadquery as cq  # type: ignore
        except Exception:
            return False
        assy = cq.Assembly()
        for i, rec in enumerate(comps):
            b = rec["bounds"]
            solid = cq.Workplane("XY").box(
                b[1] - b[0], b[3] - b[2], b[5] - b[4],
                centered=False).translate((b[0], b[2], b[4]))
            assy.add(solid, name=rec.get("name") or f"s{i}")
        assy.toCompound().val().exportStep(str(path))
        return True
    sew = BRepBuilderAPI_Sewing()
    for rec in comps:
        pts = rec["mesh"]["points"]
        for fa in rec["mesh"]["faces"]:
            poly = BRepBuilderAPI_MakePolygon()
            for idx in fa:
                p = pts[idx]
                poly.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
            poly.Close()
            if poly.IsDone():
                face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
                sew.Add(face)
    sew.Perform()
    writer = STEPControl_Writer()
    writer.Transfer(sew.SewedShape(), STEPControl_AsIs)
    return writer.Write(str(path)) == IFSelect_RetDone
