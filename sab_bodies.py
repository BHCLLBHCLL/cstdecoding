# -*- coding: utf-8 -*-
"""Extract CST solids from ACIS SAB: names, materials, and tessellated faces.

Pointers in a body are 0-based offsets from that body's entity index
(so they coincide with absolute indices for body 0).  Faces are meshed
from plane polygons and cone/cylinder surfaces — not AABBs.
"""

from __future__ import annotations

import math
import re
import struct
from typing import Optional

import numpy as np

try:
    from scipy.spatial import Delaunay as _ScipyDelaunay
except Exception:  # pragma: no cover - optional
    _ScipyDelaunay = None

_ATTRIB_RE = re.compile(r"^([nmc])(.+?)(?:%\d+)?$")
_NULL_U32 = 0xFFFFFFFF
_EPS = 1e-8


def _parse_header(data: bytes, start: int) -> int:
    if data[start:start + 15] != b"ACIS BinaryFile":
        raise ValueError("not an ACIS BinaryFile")
    pos = start + 15 + 1 + 15
    for _ in range(3):
        if pos + 2 > len(data) or data[pos] != 0x07:
            raise ValueError("header string")
        pos += 2 + data[pos + 1]
    for _ in range(3):
        if pos + 9 > len(data) or data[pos] != 0x06:
            raise ValueError("header double")
        pos += 9
    pos += 1
    if pos + 2 > len(data):
        raise ValueError("header uuid")
    pos += 2 + data[pos + 1]
    if pos < len(data) and data[pos] == 0x04:
        pos += 15
        if pos < len(data) and data[pos] == 0x0A:
            pos += 1
    return pos


def _parse_chain(data: bytes, p: int, type_names: dict):
    chain = []
    while True:
        if p + 2 > len(data):
            raise ValueError("truncated chain")
        t = data[p]
        if t not in (0x0D, 0x0E):
            raise ValueError(f"chain tag {t:#x}")
        ln = data[p + 1]
        payload = data[p + 2:p + 2 + ln]
        if payload == b"End-of-ACIS-data":
            return ("END",), p + 2 + ln
        if ln == 4:
            tid = struct.unpack("<i", payload)[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        if ln >= 5 and payload[-5] == 0x25:
            tid = struct.unpack("<i", payload[-4:])[0]
            name = payload[:-5].decode("latin1") if ln > 5 else None
        elif ln == 5 and payload[0] == 0x04:
            tid = struct.unpack("<I", payload[1:5])[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        else:
            raise ValueError(f"chain ln={ln}")
        if name is not None:
            type_names[tid] = name
        chain.append((t, name, tid))
        p += 2 + ln
        if t == 0x0D:
            return chain, p


def _typename(chain, type_names: dict) -> str:
    for _t, n, tid in chain:
        if n:
            return n
    return type_names.get(chain[0][2], f"#{chain[0][2]}")


def _scan_entities(data: bytes, start: int) -> list[dict]:
    type_names: dict[int, str] = {}
    pos = start
    ents: list[dict] = []
    cur = None
    while pos < len(data) - 16:
        tag = data[pos]
        if tag == 0x0B:
            pos += 1
        elif tag in (0x0A, 0x0F, 0x10, 0x11):
            pos += 1
            if pos < len(data) and data[pos] in (0x0D, 0x0E):
                r = _parse_chain(data, pos, type_names)
                if r[0] == ("END",):
                    break
                chain, pos = r
                cur = {"type": _typename(chain, type_names), "fields": []}
                ents.append(cur)
        elif tag in (0x0D, 0x0E):
            r = _parse_chain(data, pos, type_names)
            if r[0] == ("END",):
                break
            chain, pos = r
            cur = {"type": _typename(chain, type_names), "fields": []}
            ents.append(cur)
        elif tag == 0x07:
            ln = data[pos + 1]
            s = data[pos + 2:pos + 2 + ln].decode("latin1", "replace")
            if cur is not None:
                cur["fields"].append(("str", s))
            pos += 2 + ln
        elif tag == 0x04:
            v = struct.unpack("<I", data[pos + 1:pos + 5])[0]
            if cur is not None:
                cur["fields"].append(("u32", v))
            pos += 5
        elif tag == 0x0C:
            v = struct.unpack("<i", data[pos + 1:pos + 5])[0]
            if cur is not None:
                cur["fields"].append(("i32", v))
            pos += 5
        elif tag == 0x15:
            v = struct.unpack("<I", data[pos + 1:pos + 5])[0]
            if cur is not None:
                cur["fields"].append(("ptr", v))
            pos += 5
        elif tag == 0x19:
            v = struct.unpack("<h", data[pos + 1:pos + 3])[0]
            if cur is not None:
                cur["fields"].append(("i16", v))
            pos += 3
        elif tag == 0x06:
            v = struct.unpack("<d", data[pos + 1:pos + 9])[0]
            if cur is not None:
                cur["fields"].append(("f64", v))
            pos += 9
        elif tag == 0x13:
            v = struct.unpack("<3d", data[pos + 1:pos + 25])
            if cur is not None:
                cur["fields"].append(("pos", v))
            pos += 25
        elif tag == 0x14:
            v = struct.unpack("<3d", data[pos + 1:pos + 25])
            if cur is not None:
                cur["fields"].append(("vec", v))
            pos += 25
        else:
            pos += 1
    return ents


def _payload(ent: dict) -> list:
    return ent.get("fields", [])[4:]


def _as_ptr(val) -> Optional[int]:
    if val is None:
        return None
    try:
        iv = int(val)
    except (TypeError, ValueError):
        return None
    if iv < 0 or iv == _NULL_U32:
        return None
    return iv


def _resolve(ents, base: int, rel) -> Optional[dict]:
    rel = _as_ptr(rel)
    if rel is None:
        return None
    idx = base + rel
    if 0 <= idx < len(ents):
        return ents[idx]
    if 0 <= rel < len(ents):
        return ents[rel]
    return None


def _payload_ptrs(ent: dict) -> list[int]:
    out = []
    for k, v in _payload(ent):
        if k in ("i32", "ptr"):
            out.append(int(v))
        elif k == "u32" and v != _NULL_U32:
            out.append(int(v))
    return out


def _first_pos(ent: dict):
    for k, v in ent.get("fields", []):
        if k in ("pos", "vec"):
            return np.asarray(v, dtype=float)
    return None


def _geom_vecs(ent: dict) -> list:
    return [np.asarray(v, dtype=float)
            for k, v in ent.get("fields", []) if k in ("pos", "vec")]


def _decode_attrib(text: str) -> Optional[tuple[str, str]]:
    m = _ATTRIB_RE.match(text)
    if not m:
        return None
    kind, value = m.group(1), m.group(2)
    if kind == "n":
        return "name", value
    if kind == "m":
        return "material", value
    if kind == "c":
        return "colour", value
    return None


def _parse_rgb(text: str) -> Optional[tuple[float, float, float]]:
    parts = text.replace(",", " ").split()
    try:
        rgb = tuple(float(x) for x in parts[:3])
    except (ValueError, TypeError):
        return None
    if len(rgb) < 3:
        return None
    return rgb


def _pad_bounds(bounds):
    vals = list(bounds)
    for i in range(3):
        lo, hi = vals[2 * i], vals[2 * i + 1]
        if hi - lo < 1e-4:
            mid = 0.5 * (lo + hi)
            vals[2 * i], vals[2 * i + 1] = mid - 0.05, mid + 0.05
    return tuple(vals)


def _unit(v):
    n = np.linalg.norm(v)
    if n < _EPS:
        return v
    return v / n


def _eval_ellipse(center, normal, major, ratio, t):
    u = np.asarray(major, dtype=float)
    n = _unit(np.asarray(normal, dtype=float))
    v = np.cross(n, u)
    vn = np.linalg.norm(v)
    if vn < _EPS:
        v = np.cross(n, np.array([1.0, 0.0, 0.0]))
        vn = np.linalg.norm(v)
        if vn < _EPS:
            v = np.cross(n, np.array([0.0, 1.0, 0.0]))
            vn = np.linalg.norm(v)
    v = v / max(vn, _EPS) * (np.linalg.norm(u) * max(ratio, _EPS))
    return np.asarray(center, dtype=float) + math.cos(t) * u + math.sin(t) * v


def _eval_straight(origin, direction, t):
    return np.asarray(origin, dtype=float) + t * np.asarray(direction, dtype=float)


def _edge_end_points(ents, base, edge):
    """Start/end from vertices, falling back to the two pos fields on the edge."""
    ints, poses = [], []
    for k, v in _payload(edge):
        if k in ("i32", "ptr"):
            ints.append(int(v))
        elif k == "pos":
            poses.append(np.asarray(v, dtype=float))
    pts = []
    for rel in ints[:2]:
        vtx = _resolve(ents, base, rel)
        if vtx is None or vtx["type"] != "vertex":
            continue
        vptrs = _payload_ptrs(vtx)
        pt_ent = _resolve(ents, base, vptrs[1] if len(vptrs) > 1 else None)
        p = _first_pos(pt_ent) if pt_ent is not None else None
        if p is not None:
            pts.append(np.asarray(p, dtype=float))
    if len(pts) >= 2:
        return pts[0], pts[1]
    if len(poses) >= 2:
        return poses[0], poses[1]
    return None


def _sample_edge(ents, base, edge) -> list:
    if edge is None or edge["type"] != "edge":
        return []
    ints, flts = [], []
    for k, v in _payload(edge):
        if k in ("i32", "ptr"):
            ints.append(int(v))
        elif k == "f64":
            flts.append(float(v))
    t0 = flts[0] if len(flts) >= 1 else 0.0
    t1 = flts[1] if len(flts) >= 2 else t0
    curve = _resolve(ents, base, ints[3]) if len(ints) >= 4 else None
    ends = _edge_end_points(ents, base, edge)
    # Straights are infinite lines; t0/t1 are not always origin-relative.
    # Vertices / embedded pos are the true bounded segment (CST wireframe).
    if curve is None or curve["type"] == "straight":
        if ends is not None and _dist(ends[0], ends[1]) > 1e-12:
            return [ends[0], ends[1]]
        if curve is not None:
            vecs = _geom_vecs(curve)
            if len(vecs) >= 2:
                return [_eval_straight(vecs[0], vecs[1], t0),
                        _eval_straight(vecs[0], vecs[1], t1)]
        return []
    pts = []
    if curve["type"] == "ellipse":
        vecs = _geom_vecs(curve)
        ratio = 1.0
        for k, v in _payload(curve):
            if k == "f64":
                ratio = float(v)
                break
        if len(vecs) >= 3:
            span = abs(t1 - t0)
            n = max(12, min(48, int(span / math.pi * 16) + 4))
            if span < 1e-6:
                n = 2
            ts = np.linspace(t0, t1, n)
            pts = [_eval_ellipse(vecs[0], vecs[1], vecs[2], ratio, t) for t in ts]
            if ends is not None and len(pts) >= 2:
                pts[0] = ends[0]
                pts[-1] = ends[1]
    if len(pts) >= 2:
        return pts
    if ends is not None and _dist(ends[0], ends[1]) > 1e-12:
        return [ends[0], ends[1]]
    return []


def _dist(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


def _join_samples(poly: list, samples: list, eps: float = 0.05) -> list:
    if not samples:
        return poly
    samples = [np.asarray(p, dtype=float) for p in samples]
    if not poly:
        return samples

    def orient(anchor, pts):
        if _dist(anchor, pts[0]) <= eps:
            return pts
        if _dist(anchor, pts[-1]) <= eps:
            return list(reversed(pts))
        return None

    oriented = orient(poly[-1], samples)
    # First edge is often stored opposite the loop sense; if the next
    # coedge meets poly[0] instead of poly[-1], flip the starter.
    if oriented is None and len(poly) <= 2:
        if orient(poly[0], samples) is not None:
            poly.reverse()
            oriented = orient(poly[-1], samples)
    if oriented is None:
        # A disjoint coedge is a broken fillet pointer, not the next
        # boundary edge. Concatenating it invented spanning grey faces.
        return poly
    if oriented and _dist(poly[-1], oriented[0]) <= eps:
        oriented = oriented[1:]
    poly.extend(oriented)
    return poly


def _dedup_poly(poly: list, eps: float = 1e-6) -> list:
    if not poly:
        return []
    out = [np.asarray(poly[0], dtype=float)]
    for p in poly[1:]:
        p = np.asarray(p, dtype=float)
        if _dist(out[-1], p) > eps:
            out.append(p)
    if len(out) > 1 and _dist(out[0], out[-1]) <= eps:
        out = out[:-1]
    return out


def _strip_spikes(poly: list, eps: float = 1e-6) -> list:
    """Drop A–B–A reversals left by a mis-oriented coedge."""
    pts = [np.asarray(p, dtype=float) for p in poly]
    for _ in range(len(pts) + 2):
        n = len(pts)
        if n < 3:
            break
        keep = []
        removed = False
        for i in range(n):
            prv, cur, nxt = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
            if _dist(prv, nxt) <= eps:
                removed = True
                continue
            keep.append(cur)
        pts = _dedup_poly(keep, eps)
        if not removed:
            break
    return pts


def _iter_loops(ents, base, loop) -> list:
    out = []
    seen = set()
    cur = loop
    while cur is not None and cur.get("type") == "loop":
        cid = id(cur)
        if cid in seen:
            break
        seen.add(cid)
        out.append(cur)
        ptrs = _payload_ptrs(cur)
        nxt = ptrs[0] if ptrs else None
        if nxt is None or int(nxt) < 0:
            break
        cur = _resolve(ents, base, nxt)
    return out


_SURF_TYPES = frozenset({
    "plane", "cone", "sphere", "torus", "spline", "skinsur", "nubs",
})


def _coedge_next(ents, base, ce):
    """Return the next coedge in the loop via hardcoded ptrs[0] (standard ACIS layout)."""
    if ce is None:
        return None
    ptrs = _payload_ptrs(ce)
    nxt = _resolve(ents, base, ptrs[0] if ptrs else None)
    if nxt is not None and nxt.get("type") == "coedge":
        return nxt
    return None


def _coedge_prev(ents, base, ce):
    """Return the previous coedge in the loop via hardcoded ptrs[1] (standard ACIS layout)."""
    if ce is None:
        return None
    ptrs = _payload_ptrs(ce)
    prv = _resolve(ents, base, ptrs[1] if len(ptrs) > 1 else None)
    if prv is not None and prv.get("type") == "coedge":
        return prv
    return None


def _coedge_edge(ents, base, ce, end=None):
    """Return the edge referenced by a coedge entity.

    In the most common ACIS layout the edge sits at ptrs[3].  For records
    that embed the edge in alternative slots (e.g. ptrs[2]) we fall back to
    scanning the remaining pointer slots, and finally to a reverse-reference
    scan of the body's edge entities.  This preserves historic behaviour for
    standard-layout records while robustly handling layout variants used by
    some newer/more complex solid bodies.
    """
    if ce is None:
        return None
    ptrs = _payload_ptrs(ce)
    # Primary / standard slot.
    edge = _resolve(ents, base, ptrs[3] if len(ptrs) > 3 else None)
    if edge is not None and edge.get("type") == "edge":
        return edge
    # Fallback A: scan other pointer slots for an edge entity.
    for i, p in enumerate(ptrs):
        if i == 3:
            continue  # already checked above
        cand = _resolve(ents, base, p)
        if cand is not None and cand.get("type") == "edge":
            return cand
    # Fallback B: reverse-reference scan across the body entity range.
    if end is None:
        return None
    for e in ents[base:end]:
        if e.get("type") != "edge":
            continue
        for p in _payload_ptrs(e):
            if _resolve(ents, base, p) is ce:
                return e
    return None


def _collect_loop_coedges(ents, base, loop, end) -> list:
    """Return every coedge in ents[base:end] that points (by entity identity)
    to the given loop record via any of its pointer slots.

    Identity resolution is used intentionally instead of raw integer matching
    because small integer values can appear in non-pointer fields (e.g. surface
    or attribute indices) and would otherwise produce false positives that
    pull unrelated coedges from adjacent faces into the geometric stitch.
    """
    if loop is None or end is None:
        return []
    out = []
    seen = set()
    scan_end = end if end is not None else min(base + 4096, len(ents))
    for j in range(base, scan_end):
        e = ents[j]
        if e.get("type") != "coedge":
            continue
        eid = id(e)
        if eid in seen:
            continue
        for p in _payload_ptrs(e):
            if _resolve(ents, base, p) is loop:
                seen.add(eid)
                out.append(e)
                break
    return out


def _chain_edges_by_geometry(edges: list, max_gap: float = 0.1):
    """
    Chain a list of edge samples (each a list of 2+ 3D points) into a single
    polyline by matching end[i] ≈ start[j] geometrically. Returns (poly, closed).
    Each edge is allowed to be reversed to continue the chain.
    """
    if not edges:
        return [], False
    # Work on copies; we will reverse in place as needed.
    working = [list(e) for e in edges if len(e) >= 2]
    if not working:
        return [], False

    def close(a, b):
        return _dist(a, b) <= max_gap

    used = [False] * len(working)
    # Start with first edge
    used[0] = True
    poly = list(working[0])
    count = 1
    while count < len(working):
        anchor_end = poly[-1]
        anchor_start = poly[0]
        found = False
        # Try to append to the end
        for i in range(1, len(working)):
            if used[i]:
                continue
            e = working[i]
            if close(anchor_end, e[0]):
                poly.extend(e[1:])
                used[i] = True
                found = True
                break
            if close(anchor_end, e[-1]):
                # reverse before appending
                poly.extend(reversed(e[:-1]))
                used[i] = True
                found = True
                break
        if found:
            count += 1
            continue
        # Try to prepend to the start (only if chain hasn't closed yet)
        closed_here = close(poly[0], poly[-1])
        if closed_here:
            break
        for i in range(1, len(working)):
            if used[i]:
                continue
            e = working[i]
            if close(anchor_start, e[-1]):
                poly = list(e) + poly[1:]
                used[i] = True
                found = True
                break
            if close(anchor_start, e[0]):
                poly = list(reversed(e)) + poly[1:]
                used[i] = True
                found = True
                break
        if found:
            count += 1
        else:
            # Cannot extend further; remaining edges may be disjoint holes or different loops
            break
    # Close if endpoints close enough
    poly = _dedup_poly(poly)
    closed = len(poly) >= 3 and _loop_is_closed(poly)
    return _strip_spikes(poly), closed


def _walk_loop(ents, base, loop, end=None) -> tuple[list, bool]:
    """Return (polyline, closed).

    Walk the coedge chain via pointer fields first (the fast, standard-layout
    path).  If that yields a closed loop we return it immediately.  Otherwise,
    fall back to collecting every coedge that references this loop and
    stitching their edge samples together purely by geometric end-point
    continuity.  The geometric fallback is only used when it produces a
    strictly better result (closed AND strictly longer than the pointer
    walk), ensuring bodies that rely on the standard ACIS layout never
    regress while variant-layout loops are still recovered.
    """
    if loop is None or loop["type"] != "loop":
        return [], False
    ptrs = _payload_ptrs(loop)
    start = _resolve(ents, base, ptrs[1] if len(ptrs) > 1 else None)
    if start is None or start.get("type") != "coedge":
        start = None
        for p in ptrs:
            ent = _resolve(ents, base, p)
            if ent is not None and ent.get("type") == "coedge":
                start = ent
                break
        if start is None:
            return [], False
    seq = []
    seen = set()
    ce = start
    for _ in range(256):
        if id(ce) in seen:
            break
        seen.add(id(ce))
        seq.append(ce)
        nxt = _coedge_next(ents, base, ce)
        if nxt is None or nxt is start:
            break
        ce = nxt
    prv = _coedge_prev(ents, base, start)
    while prv is not None and id(prv) not in seen and len(seq) < 256:
        seq.insert(0, prv)
        seen.add(id(prv))
        prv = _coedge_prev(ents, base, prv)
    poly = []
    for ce in seq:
        samples = _sample_edge(ents, base, _coedge_edge(ents, base, ce, end))
        if len(samples) >= 2:
            poly = _join_samples(poly, samples)
    closed = _loop_is_closed(poly)
    poly = _strip_spikes(_dedup_poly(poly))
    # Fast path: pointer walk produced a closed, usable loop → keep it.
    if closed and len(poly) >= 3:
        return poly, closed
    # Geometric fallback: stitch all edges in the loop by continuity.
    if end is None:
        return poly, closed
    coedges = _collect_loop_coedges(ents, base, loop, end)
    edges = []
    for c in coedges:
        samples = _sample_edge(ents, base, _coedge_edge(ents, base, c, end))
        if len(samples) >= 2:
            edges.append(samples)
    if not edges:
        return poly, closed
    geom_poly, geom_closed = _chain_edges_by_geometry(edges)
    # Use the geometry polyline only when it is unambiguously superior:
    # closed AND strictly more points than the pointer walk produced.  This
    # guard is conservative by design — it prevents pointer-walk regressions
    # on bodies that use the standard ACIS layout.
    if geom_closed and len(geom_poly) > len(poly):
        return geom_poly, geom_closed
    # Geometry poly was not strictly better — fall back to whichever is
    # longer (prefer a partial pointer walk to an even worse geometry chain).
    if len(geom_poly) > len(poly):
        return geom_poly, geom_closed
    return poly, closed


def _loop_is_closed(poly, snap: float = 0.05) -> bool:
    """True for a real cycle; false for a path whose closing chord would span the face."""
    if len(poly) < 3:
        return False
    gap = _dist(poly[0], poly[-1])
    if gap <= snap:
        return True
    if len(poly) < 4:
        return False
    edges = [_dist(poly[i], poly[i + 1]) for i in range(len(poly) - 1)]
    typical = sorted(edges)[len(edges) // 2]
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    zs = [float(p[2]) for p in poly]
    diag = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2
                     + (max(zs) - min(zs)) ** 2)
    return gap <= max(3.0 * typical, 0.2) and gap < 0.25 * max(diag, 1e-6)


def _cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _same2(a, b, eps: float = 1e-12) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _inside_tri(a, b, c, p):
    c1 = _cross2(a, b, p)
    c2 = _cross2(b, c, p)
    c3 = _cross2(c, a, p)
    return (c1 >= -_EPS and c2 >= -_EPS and c3 >= -_EPS) or (
        c1 <= _EPS and c2 <= _EPS and c3 <= _EPS)


def _poly_area2(p2) -> float:
    area = 0.0
    n = len(p2)
    for i in range(n):
        x1, y1 = p2[i]
        x2, y2 = p2[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area


def _fan_tris(poly3d: list) -> list:
    if len(poly3d) < 3:
        return []
    origin = np.asarray(poly3d[0], dtype=float)
    tris = []
    for i in range(1, len(poly3d) - 1):
        a = np.asarray(poly3d[i], dtype=float)
        b = np.asarray(poly3d[i + 1], dtype=float)
        if np.linalg.norm(np.cross(a - origin, b - origin)) > 1e-16:
            tris.append((origin, a, b))
    return tris


def _earclip(poly3d: list) -> list:
    poly3d = _dedup_poly(poly3d)
    n = len(poly3d)
    if n < 3:
        return []
    if n == 3:
        return [(poly3d[0], poly3d[1], poly3d[2])]
    pts = np.asarray(poly3d, dtype=float)
    nrm = np.zeros(3)
    for i in range(n):
        nrm += np.cross(pts[i] - pts[0], pts[(i + 1) % n] - pts[0])
    if np.linalg.norm(nrm) < 1e-16:
        return _fan_tris(poly3d)
    nrm = _unit(nrm)
    tmp = np.array([1.0, 0.0, 0.0]) if abs(nrm[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = _unit(np.cross(nrm, tmp))
    v = np.cross(nrm, u)
    p2 = [(float(np.dot(p - pts[0], u)), float(np.dot(p - pts[0], v))) for p in pts]
    if _poly_area2(p2) < 0:
        poly3d = list(reversed(poly3d))
        pts = np.asarray(poly3d, dtype=float)
        p2 = [(float(np.dot(p - pts[0], u)), float(np.dot(p - pts[0], v))) for p in pts]
    idx = list(range(n))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < n * n + 8:
        guard += 1
        found = False
        m = len(idx)
        for i in range(m):
            ia, ib, ic = idx[(i - 1) % m], idx[i], idx[(i + 1) % m]
            a, b, c = p2[ia], p2[ib], p2[ic]
            ab = math.hypot(b[0] - a[0], b[1] - a[1])
            bc = math.hypot(c[0] - b[0], c[1] - b[1])
            if _cross2(a, b, c) <= 1e-18 * (ab * bc + 1e-12):
                continue
            blocked = False
            for j in range(m):
                if idx[j] in (ia, ib, ic):
                    continue
                q = p2[idx[j]]
                if (_same2(q, a) or _same2(q, b) or _same2(q, c)):
                    continue
                if _inside_tri(a, b, c, q):
                    blocked = True
                    break
            if blocked:
                continue
            tris.append((poly3d[ia], poly3d[ib], poly3d[ic]))
            idx.pop(i)
            found = True
            break
        if not found:
            break
    if len(idx) == 3:
        tris.append((poly3d[idx[0]], poly3d[idx[1]], poly3d[idx[2]]))
    if len(tris) < n - 2:
        # Fan only tiny convex faces. A fan on a rounded phone outline
        # would draw diameters across the whole part.
        if n <= 8:
            return _fan_tris(poly3d)
        return tris
    return tris


def _cyl_frame(origin, axis, major):
    origin = np.asarray(origin, dtype=float)
    axis = _unit(np.asarray(axis, dtype=float))
    major = np.asarray(major, dtype=float)
    u = major - np.dot(major, axis) * axis
    r0 = float(np.linalg.norm(u))
    if r0 < _EPS:
        u = np.cross(axis, np.array([1.0, 0.0, 0.0]))
        if np.linalg.norm(u) < _EPS:
            u = np.cross(axis, np.array([0.0, 1.0, 0.0]))
        r0 = float(np.linalg.norm(major)) if np.linalg.norm(major) > _EPS else 1.0
        u = _unit(u) * r0
    v = np.cross(axis, u)
    vn = float(np.linalg.norm(v))
    if vn < _EPS:
        return None
    v = v / vn * r0
    u = _unit(u) * r0
    return origin, axis, u, v, r0


def _htheta(origin, axis, u, v, r0, p):
    w = np.asarray(p, dtype=float) - origin
    h = float(np.dot(w, axis))
    radial = w - h * axis
    uu = u / max(r0, _EPS)
    vv = v / max(r0, _EPS)
    th = math.atan2(float(np.dot(radial, vv)), float(np.dot(radial, uu)))
    return h, th


def _theta_span(thetas):
    if not thetas:
        return 0.0, 0.0, False
    ang = sorted(t % (2 * math.pi) for t in thetas)
    uniq = [ang[0]]
    for a in ang[1:]:
        if a - uniq[-1] > 1e-6:
            uniq.append(a)
    if len(uniq) == 1:
        return uniq[0], uniq[0], False
    gaps = [uniq[i + 1] - uniq[i] for i in range(len(uniq) - 1)]
    wrap = uniq[0] + 2 * math.pi - uniq[-1]
    gaps.append(wrap)
    max_gap = max(gaps)
    covered = (uniq[-1] - uniq[0]) + wrap
    if max_gap < math.radians(45) and covered > math.radians(300):
        return 0.0, 2 * math.pi, True
    i = gaps.index(max_gap)
    if i == len(gaps) - 1:
        return uniq[0], uniq[-1], False
    return uniq[i + 1], uniq[i] + 2 * math.pi, False


def _mesh_revolution(origin, axis, major, sine, cosine, polys) -> list:
    """Mesh a cylinder / cone / fillet using only the (h, theta) span of the loops."""
    frame = _cyl_frame(origin, axis, major)
    if frame is None:
        return []
    origin, axis, u, v, r0 = frame
    tan_a = (sine / cosine) if abs(cosine) > 0.05 else 0.0
    hs, thetas = [], []
    for poly in polys:
        for p in poly:
            h, th = _htheta(origin, axis, u, v, r0, p)
            hs.append(h)
            thetas.append(th)
    if len(hs) < 2:
        return []
    h0, h1 = min(hs), max(hs)
    if abs(h1 - h0) < 1e-6:
        return []
    th0, th1, full = _theta_span(thetas)
    span = abs(th1 - th0)
    if span < 1e-3:
        return []
    n_theta = max(4, min(64, int(span / math.pi * 16) + 2))
    if full:
        n_theta = max(16, n_theta)
        th0, th1, span = 0.0, 2 * math.pi, 2 * math.pi
    uu = u / max(r0, _EPS)
    vv = v / max(r0, _EPS)

    def point(h, th):
        rh = max(0.0, r0 + h * tan_a)
        return origin + h * axis + rh * (math.cos(th) * uu + math.sin(th) * vv)

    tris = []
    for i in range(n_theta):
        t0 = th0 + span * i / n_theta
        t1 = th1 if i == n_theta - 1 else th0 + span * (i + 1) / n_theta
        p00, p10 = point(h0, t0), point(h0, t1)
        p01, p11 = point(h1, t0), point(h1, t1)
        tris.append((p00, p10, p11))
        tris.append((p00, p11, p01))
    return tris


def _point_in_poly2(p, poly2d) -> bool:
    x, y = p
    inside = False
    n = len(poly2d)
    for i in range(n):
        x1, y1 = poly2d[i]
        x2, y2 = poly2d[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xing = (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-30) + x1
            if x < xing:
                inside = not inside
    return inside


def _on_poly_edge(p, poly2d, eps: float = 1e-8) -> bool:
    x, y = p
    n = len(poly2d)
    for i in range(n):
        x1, y1 = poly2d[i]
        x2, y2 = poly2d[(i + 1) % n]
        if (x < min(x1, x2) - eps or x > max(x1, x2) + eps or
                y < min(y1, y2) - eps or y > max(y1, y2) + eps):
            continue
        dx, dy = x2 - x1, y2 - y1
        scale = abs(dx) + abs(dy) + 1.0
        if abs((x - x1) * dy - (y - y1) * dx) <= eps * scale:
            return True
    return False


def _in_face_region(p, outer2, hole2d) -> bool:
    if _point_in_poly2(p, outer2):
        for h in hole2d:
            if len(h) >= 3 and _point_in_poly2(p, h) and not _on_poly_edge(p, h):
                return False
        return True
    return _on_poly_edge(p, outer2)


def _tri_in_face_region(a, b, c, outer2, hole2d) -> bool:
    """Keep a triangle only if it lies in the face (not a spanning ear)."""
    samples = (
        ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5),
        ((b[0] + c[0]) * 0.5, (b[1] + c[1]) * 0.5),
        ((c[0] + a[0]) * 0.5, (c[1] + a[1]) * 0.5),
        ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0),
    )
    return all(_in_face_region(p, outer2, hole2d) for p in samples)


def _poly_normal(poly):
    pts = np.asarray(poly, dtype=float)
    nrm = np.zeros(3)
    for i in range(len(pts)):
        nrm += np.cross(pts[i] - pts[0], pts[(i + 1) % len(pts)] - pts[0])
    return _unit(nrm)


def _project_poly(poly, origin, u, v):
    return [(float(np.dot(np.asarray(p, dtype=float) - origin, u)),
             float(np.dot(np.asarray(p, dtype=float) - origin, v)))
            for p in poly]


def _plane_basis(poly):
    nrm = _poly_normal(poly)
    if np.linalg.norm(nrm) < _EPS:
        nrm = np.array([0.0, 0.0, 1.0])
    tmp = np.array([1.0, 0.0, 0.0]) if abs(nrm[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = _unit(np.cross(nrm, tmp))
    v = np.cross(nrm, u)
    origin = np.asarray(poly[0], dtype=float)
    return origin, u, v


def _abs_loop_area(poly) -> float:
    acc = np.zeros(3)
    p0 = np.asarray(poly[0], dtype=float)
    for i in range(len(poly)):
        acc = acc + np.cross(
            np.asarray(poly[i], dtype=float) - p0,
            np.asarray(poly[(i + 1) % len(poly)], dtype=float) - p0)
    return float(np.linalg.norm(acc))


def _delaunay_in_region(pts3, pts2, outer2, hole2d) -> list:
    """Delaunay of outer+hole vertices, keeping triangles in the solid region.

    Ear-clipping the outer loop alone draws spanning triangles across holes
    (the extra yellow wedges in the GUI).  Including hole vertices and
    dropping simplices whose centroid is outside the face (or inside a hole)
    matches the CST cutouts.
    """
    if _ScipyDelaunay is None or len(pts3) < 3:
        return []
    pts2 = np.asarray(pts2, dtype=float)
    if pts2.ndim != 2 or pts2.shape[0] != len(pts3):
        return []
    _, uniq = np.unique(np.round(pts2, 9), axis=0, return_index=True)
    uniq = np.sort(uniq)
    pts2u = pts2[uniq]
    pts3u = [pts3[int(i)] for i in uniq]
    if len(pts2u) < 3:
        return []
    mesh = None
    rng = np.random.RandomState(0)
    for scale in (1e-11, 1e-10, 1e-9):
        try:
            mesh = _ScipyDelaunay(pts2u + rng.normal(0.0, scale, pts2u.shape))
            break
        except Exception:
            mesh = None
    if mesh is None:
        return []
    kept = []
    for simp in mesh.simplices:
        a, b, c = (pts2u[int(i)] for i in simp)
        if abs(_cross2(a, b, c)) < 1e-18:
            continue
        if not _tri_in_face_region(a, b, c, outer2, hole2d):
            continue
        ia, ib, ic = (int(i) for i in simp)
        kept.append((pts3u[ia], pts3u[ib], pts3u[ic]))
    return kept


def _reject_hole_overlap(tris, origin, u, v, hole2d) -> list:
    """Fallback: drop triangles that cover a hole (centroid or hole vertex)."""
    if not hole2d:
        return tris
    kept = []
    for tri in tris:
        p2 = _project_poly(tri, origin, u, v)
        cent = ((p2[0][0] + p2[1][0] + p2[2][0]) / 3.0,
                (p2[0][1] + p2[1][1] + p2[2][1]) / 3.0)
        skip = False
        for h in hole2d:
            if len(h) < 3:
                continue
            if _point_in_poly2(cent, h):
                skip = True
                break
            if any(_inside_tri(p2[0], p2[1], p2[2], hv)
                   and not (_same2(hv, p2[0]) or _same2(hv, p2[1])
                            or _same2(hv, p2[2]))
                   for hv in h):
                skip = True
                break
        if not skip:
            kept.append(tri)
    return kept


def _reject_outside(tris, origin, u, v, outer2) -> list:
    kept = []
    for tri in tris:
        p2 = _project_poly(tri, origin, u, v)
        if _tri_in_face_region(p2[0], p2[1], p2[2], outer2, []):
            kept.append(tri)
    return kept


def _triangulate_plane(polys: list) -> list:
    usable = [_strip_spikes(_dedup_poly(p)) for p in polys if len(p) >= 3]
    usable = [p for p in usable if len(p) >= 3]
    if not usable:
        return []
    areas = [_abs_loop_area(poly) for poly in usable]
    outer_i = int(np.argmax(areas))
    outer = usable[outer_i]
    holes = [p for i, p in enumerate(usable) if i != outer_i]
    origin, u, v = _plane_basis(outer)
    # Normalize winding: outer must be counter-clockwise in 2-D (face normal
    # pointing out of the plane); holes must be clockwise (opposite).  When
    # the surface-normal alignment step (upstream) reversed an entire poly
    # list in lockstep it flipped outer AND holes together.  We then flip
    # the outer back to CCW here.  To keep holes opposite — which is what
    # _delaunay_in_region / _reject_hole_overlap rely on — every hole that
    # now has the same 2-D winding sign as outer is also flipped.
    outer2 = _project_poly(outer, origin, u, v)
    outer_sign = 1.0
    if _poly_area2(outer2) < 0:
        outer = list(reversed(outer))
        outer2 = list(reversed(outer2))
        outer_sign = -1.0
    hole2d_raw = [_project_poly(h, origin, u, v) for h in holes]
    fixed_holes = []
    fixed_hole2d = []
    for h, h2 in zip(holes, hole2d_raw):
        same_sign = (_poly_area2(h2) >= 0) if (outer_sign > 0) else (_poly_area2(h2) < 0)
        if same_sign:
            # Hole currently has same winding as outer — flip it so it's
            # opposite (interior boundary for subtraction).
            h = list(reversed(h))
            h2 = list(reversed(h2))
        fixed_holes.append(h)
        fixed_hole2d.append(h2)
    holes = fixed_holes
    hole2d = fixed_hole2d
    n = len(outer)

    # Simple concave faces (PCB outlines): constrained earclip stays inside
    # the CAD wires. Unconstrained Delaunay spans bays and looks webbed.
    if not holes:
        tris = _earclip(outer)
        if len(tris) >= max(1, n - 2):
            return tris

    pts3 = list(outer)
    for h in holes:
        pts3.extend(h)
    pts2 = _project_poly(pts3, origin, u, v)
    cdt = _delaunay_in_region(pts3, pts2, outer2, hole2d)
    if cdt:
        return cdt
    tris = _earclip(outer)
    if holes:
        return _reject_hole_overlap(tris, origin, u, v, hole2d)
    return _reject_outside(tris, origin, u, v, outer2)


def _face_surface(ents, base, face):
    ptrs = _payload_ptrs(face)
    if len(ptrs) < 5:
        return None
    loop = _resolve(ents, base, ptrs[1])
    if loop is None or loop.get("type") != "loop":
        return None
    surf = _resolve(ents, base, ptrs[4])
    if surf is not None and surf.get("type") in _SURF_TYPES:
        return surf
    for p in ptrs:
        ent = _resolve(ents, base, p)
        if ent is not None and ent.get("type") in _SURF_TYPES:
            return ent
    return None


def _filter_edges_on_plane(edges_sampled: list, surf, eps: float = 0.05) -> list:
    """Keep only sampled edges whose endpoints all lie on a planar surface.

    Used to drop coedges that reference a loop structurally (adjacent side-wall
    faces share loop back-references in some ACIS layouts) but whose geometry
    belongs to a different face. Filtering by plane membership prior to
    geometric stitching keeps outer / inner / adjacent contours from being
    merged together.
    """
    if surf is None or surf.get("type") != "plane":
        return list(edges_sampled)
    vecs = _geom_vecs(surf)
    if len(vecs) < 3:
        return list(edges_sampled)
    origin = np.asarray(vecs[0], dtype=float)
    axis = _unit(np.asarray(vecs[1], dtype=float))
    kept = []
    for samples in edges_sampled:
        if len(samples) < 2:
            continue
        arr = np.asarray(samples, dtype=float)
        dists = np.abs(np.dot(arr - origin, axis))
        if dists.max() <= eps:
            kept.append(samples)
    return kept


def _plane_edges_convex_hull(plane_edges: list, surf) -> list:
    """Return the 2-D convex hull of all on-plane edge endpoints as a 3-D polyline.

    Used as a last-resort outer contour when pointer walks and geometric
    stitching both yield a fragmented outer (the per-coedge identity scan
    misses orphan edges on variant-layout ACIS records, and the separate
    fragments do not chain into a single closed loop because the shared
    straight boundary between the outer and an inner hole was encoded
    without a dedicated top-plate edge record).  The convex hull is a
    conservative outer boundary and the identity-recovered hole loops are
    preserved exactly, so tessellation stays inside the true CAD shape.
    """
    if not plane_edges or surf is None or surf.get("type") != "plane":
        return []
    vecs = _geom_vecs(surf)
    if len(vecs) < 3:
        return []
    s_origin = np.asarray(vecs[0], dtype=float)
    s_axis = _unit(np.asarray(vecs[1], dtype=float))
    tmp_s = np.array([1.0, 0.0, 0.0]) if abs(s_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u_s = _unit(np.cross(s_axis, tmp_s))
    v_s = np.cross(s_axis, u_s)
    pts3 = []
    for e in plane_edges:
        for p in e:
            pts3.append(np.asarray(p, dtype=float))
    if not pts3:
        return []
    arr = np.array(pts3)
    arr = np.unique(np.round(arr, 8), axis=0)
    p2 = np.column_stack([np.dot(arr - s_origin, u_s), np.dot(arr - s_origin, v_s)])
    # Graham scan for 2D convex hull
    order = sorted(range(len(p2)), key=lambda i: (p2[i, 0], p2[i, 1]))
    if len(order) < 3:
        return [arr[i].tolist() for i in order]

    def cross(o, a, b):
        return (p2[a, 0] - p2[o, 0]) * (p2[b, 1] - p2[o, 1]) - (p2[a, 1] - p2[o, 1]) * (p2[b, 0] - p2[o, 0])

    lower = []
    for i in order:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], i) <= 0:
            lower.pop()
        lower.append(i)
    upper = []
    for i in reversed(order):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], i) <= 0:
            upper.pop()
        upper.append(i)
    hull_idx = lower[:-1] + upper[:-1]
    if len(hull_idx) < 3:
        return [arr[i].tolist() for i in order[:3]]
    return [arr[i].tolist() for i in hull_idx]


def _collect_all_body_plane_edges(ents, base, end, surf, eps: float = 0.005) -> list:
    """Scan every edge record in [base:end] and keep samples on the plane.

    Unlike the coedge-guided identity path, this does not rely on coedge
    parent lookups at all. It therefore recovers variant-layout edges whose
    parent records have been mis-classified by the type-name mapping or
    whose pointers do not resolve into coedge entities via the standard
    body-relative base offset.
    """
    if end is None or surf is None or surf.get("type") != "plane":
        return []
    vecs = _geom_vecs(surf)
    if len(vecs) < 3:
        return []
    origin = np.asarray(vecs[0], dtype=float)
    axis = _unit(np.asarray(vecs[1], dtype=float))
    edges_out = []
    for e in ents[base:end]:
        if e.get("type") != "edge":
            continue
        samples = _sample_edge(ents, base, e)
        if len(samples) < 2:
            continue
        arr = np.asarray(samples, dtype=float)
        dists = np.abs(np.dot(arr - origin, axis))
        if dists.max() <= eps:
            edges_out.append(samples)
    return edges_out


def _tessellate_face(ents, base, face, end=None) -> list:
    ptrs = _payload_ptrs(face)
    surf = _face_surface(ents, base, face)
    if surf is None:
        return []
    loops = _iter_loops(ents, base, _resolve(ents, base, ptrs[1]))
    walked = [_walk_loop(ents, base, lp, end) for lp in loops]
    polys = [p for p, closed in walked if closed and len(p) >= 3]

    if surf["type"] == "plane" and end is not None:
        def _area2_of(poly3d) -> float:
            if not poly3d or len(poly3d) < 3:
                return 0.0
            pts = np.asarray(poly3d, dtype=float)
            v0 = pts[1] - pts[0]
            v1 = pts[2] - pts[0]
            nrm = np.cross(v0, v1)
            if np.linalg.norm(nrm) < _EPS:
                return 0.0
            nrm = _unit(nrm)
            tmp = np.array([1.0, 0.0, 0.0]) if abs(nrm[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            u = _unit(np.cross(nrm, tmp))
            v = np.cross(nrm, u)
            origin = pts[0]
            p2 = [(float(np.dot(p - origin, u)), float(np.dot(p - origin, v))) for p in pts]
            return abs(_poly_area2(p2))

        # Per-loop rebuild: pointer walk is always preferred.  If it didn't
        # yield a closed polygon (or produced a trivially short one because
        # some coedges on this loop use variant pointer layouts) we collect
        # every coedge that references the loop record by entity identity,
        # drop coedges whose geometry lives on a different face (plane
        # membership filter), and stitch the survivors geometrically.  This
        # stays local to each loop, so small cuboid can faces are not
        # polluted by edges from neighbouring cans that happen to share the
        # same z-level.
        def _try_close_rect(poly, min_pts=4):
            """If poly is an open chain whose 2-D convex hull has 4 vertices
            (i.e. the open chain covers three sides of a planar rectangle),
            append the first point to close it.  Recovers variant-layout
            can-step faces (sh_cans:top mid-platform / top-rim) whose walks
            and geometric chains both miss the last edge due to pointer-
            layout ambiguity."""
            if len(poly) < min_pts:
                return None
            try:
                origin, u, v = _plane_basis(poly)
                pts2 = []
                for p in poly:
                    d = np.asarray(p, dtype=float) - origin
                    pts2.append((float(np.dot(d, u)), float(np.dot(d, v))))
                uniq = sorted(set(pts2))
                if len(uniq) < 3:
                    return None
                def _cross(o, a, b):
                    return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
                lower = []
                for pt in uniq:
                    while len(lower) >= 2 and _cross(lower[-2], lower[-1], pt) <= 1e-9:
                        lower.pop()
                    lower.append(pt)
                upper = []
                for pt in reversed(uniq):
                    while len(upper) >= 2 and _cross(upper[-2], upper[-1], pt) <= 1e-9:
                        upper.pop()
                    upper.append(pt)
                hull = lower[:-1] + upper[:-1]
                if len(hull) < 3:
                    return None
                # Accept if hull has exactly 3 or 4 distinct vertices and
                # closing the chain spans a side comparable to the hull size.
                dx = max(x for x, y in hull) - min(x for x, y in hull)
                dy = max(y for x, y in hull) - min(y for x, y in hull)
                hull_span = max(dx, dy)
                if hull_span <= 0:
                    return None
                gap_vec = np.asarray(poly[0], dtype=float) - np.asarray(poly[-1], dtype=float)
                gap_len = float(np.linalg.norm(gap_vec))
                if gap_len <= 1e-6 or gap_len > 3.0 * hull_span:
                    return None
                closed_poly = list(poly) + [poly[0]]
                return closed_poly
            except Exception:
                return None

        rebuilt_polys = []
        for walk_poly, walk_closed in walked:
            if walk_closed and len(walk_poly) >= 3:
                rebuilt_polys.append(walk_poly)
                continue
            lp = loops[len(rebuilt_polys)]
            coedges = _collect_loop_coedges(ents, base, lp, end)
            edge_samples = []
            for c in coedges:
                s = _sample_edge(ents, base, _coedge_edge(ents, base, c, end))
                if len(s) >= 2:
                    edge_samples.append(s)
            edge_samples = _filter_edges_on_plane(edge_samples, surf)
            used_fallback = False
            best_poly, best_closed = None, False
            if edge_samples:
                geom_poly, geom_closed = _chain_edges_by_geometry(edge_samples)
                if geom_closed and len(geom_poly) >= 3 and (not walk_closed or len(geom_poly) > len(walk_poly)):
                    best_poly, best_closed = geom_poly, True
                    used_fallback = True
                elif len(geom_poly) >= 4 and not geom_closed:
                    rect_poly = _try_close_rect(geom_poly, min_pts=4)
                    if rect_poly is not None:
                        best_poly, best_closed = rect_poly, True
                        used_fallback = True
            if not used_fallback and walk_closed and len(walk_poly) >= 3:
                rebuilt_polys.append(walk_poly)
                continue
            if not used_fallback and len(walk_poly) >= 4 and not walk_closed:
                rect_poly = _try_close_rect(walk_poly, min_pts=4)
                if rect_poly is not None:
                    best_poly, best_closed = rect_poly, True
                    used_fallback = True
            if best_poly is not None and best_closed and len(best_poly) >= 4:
                rebuilt_polys.append(best_poly)
                used_fallback = True
            if not used_fallback and walk_closed and len(walk_poly) >= 3:
                rebuilt_polys.append(walk_poly)
        polys = rebuilt_polys if rebuilt_polys else polys

        # Large-face hull fallback: when every loop failed to recover a
        # closed outer boundary for a face that (judging by its own loop
        # coedge endpoints) spans well over a hundred mm², we assume we are
        # on a PCB plate or can-lid top and build a conservative outer
        # boundary via the convex hull of every body edge lying on this
        # plane.  Existing small recovered loops are kept verbatim as holes.
        # Tight thresholds deliberately avoid activating this on small
        # box / can walls, and the reference area is computed from THIS
        # FACE'S OWN loop coedges so multi-can compound bodies do not see
        # their individual small can faces trigger hull fallback just
        # because a neighbour can happens to share the same z-level.
        face_plane_edges = []
        for lp in loops:
            coedges = _collect_loop_coedges(ents, base, lp, end)
            for c in coedges:
                s = _sample_edge(ents, base, _coedge_edge(ents, base, c, end))
                if len(s) >= 2:
                    face_plane_edges.append(s)
        face_plane_edges = _filter_edges_on_plane(face_plane_edges, surf)
        ref_area = 0.0
        if face_plane_edges:
            mids = np.array([(np.asarray(e[0]) + np.asarray(e[-1])) * 0.5 for e in face_plane_edges])
            if len(mids) >= 2:
                vecs_surf = _geom_vecs(surf)
                if len(vecs_surf) >= 3:
                    s_origin = np.asarray(vecs_surf[0], dtype=float)
                    s_axis = _unit(np.asarray(vecs_surf[1], dtype=float))
                    tmp_s = np.array([1.0, 0.0, 0.0]) if abs(s_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
                    u_s = _unit(np.cross(s_axis, tmp_s))
                    v_s = np.cross(s_axis, u_s)
                    mids2 = np.column_stack([np.dot(mids - s_origin, u_s), np.dot(mids - s_origin, v_s)])
                    ref_area = float((mids2[:, 0].max() - mids2[:, 0].min()) * (mids2[:, 1].max() - mids2[:, 1].min()))
        body_plane_edges = _collect_all_body_plane_edges(ents, base, end, surf)
        current_max_area = max((_area2_of(p) for p in polys), default=0.0)
        # Consistency guard: compute a face-local bbox area from the pointer
        # walks and rebuilt polygons.  Variant-layout coedges sometimes
        # cause _collect_loop_coedges to grab coedges from neighbouring
        # faces (they share loop-record references indirectly).  That
        # inflates ref_area far beyond the real face extent — the hull
        # fallback then builds a giant 40×20 mm hull for a ~2×1 mm can-step
        # face and produces zero valid triangles.  Require that ref_area is
        # at most a moderate multiple of the walk-bbox area before firing.
        walk_bbox_area = 0.0
        try:
            all_p = []
            for wp, wc in walked:
                all_p.extend(wp)
            all_p.extend([pt for poly in polys for pt in poly])
            if len(all_p) >= 3:
                vecs_surf2 = _geom_vecs(surf)
                if len(vecs_surf2) >= 3:
                    s_o2 = np.asarray(vecs_surf2[0], dtype=float)
                    s_a2 = _unit(np.asarray(vecs_surf2[1], dtype=float))
                    tmp2 = np.array([1.0, 0.0, 0.0]) if abs(s_a2[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
                    u2 = _unit(np.cross(s_a2, tmp2))
                    v2 = np.cross(s_a2, u2)
                    arr = np.asarray(all_p, dtype=float)
                    x2 = np.dot(arr - s_o2, u2)
                    y2 = np.dot(arr - s_o2, v2)
                    wba = (float(x2.max()) - float(x2.min())) * (float(y2.max()) - float(y2.min()))
                    walk_bbox_area = max(wba, 1e-6)
        except Exception:
            walk_bbox_area = 0.0
        ref_area_ok = True
        if walk_bbox_area > 1e-3 and ref_area > 100.0:
            if ref_area > 30.0 * walk_bbox_area:
                ref_area_ok = False
        polys_bbox_area = walk_bbox_area  # already includes union of polys & walks
        current_large_poly_ok = current_max_area < 0.30 * ref_area
        polys_too_small_for_ref = ref_area > 150.0 and polys_bbox_area < 0.50 * ref_area
        if (ref_area_ok and ref_area > 150.0 and (current_large_poly_ok or polys_too_small_for_ref)
                and len(body_plane_edges) >= 12 and len(face_plane_edges) >= 6):
            full_edges = body_plane_edges
            if full_edges:
                hull = _plane_edges_convex_hull(full_edges, surf)
                hull = _strip_spikes(_dedup_poly(hull))
                if len(hull) >= 3:
                    hull_area = _abs_loop_area(hull)
                    # Existing identity-recovered loops are always kept as
                    # explicit holes.  Then sweep every body-plane edge via
                    # endpoint stitching to catch any additional closed
                    # interior contours that identity-guided resolution
                    # missed (variant pointer layouts).  Any closed loop
                    # whose area is a small fraction of the hull area is
                    # appended to the hole list; the outer boundary can
                    # produce a duplicate large closed contour via the
                    # same sweep so a 70 % area guard drops it.
                    hole_polys = []
                    for p in polys:
                        pa = _abs_loop_area(p)
                        # Only treat pre-recovered polygons as holes when
                        # they are clearly interior: small area relative to
                        # the convex hull AND bounded well inside the hull's
                        # 2-D footprint.  Partial outer-contour fragments
                        # recovered from geom-chain walks sit on the hull
                        # boundary and can be 20-50 % of hull area — we must
                        # NOT subtract them as holes or the plate face ends
                        # up with giant interior "bites" cut out of it.
                        if pa < 0.30 * hull_area and pa > 0.001:
                            hole_polys.append(p)
                    # Sweep body-plane edges repeatedly with bidirectional
                    # geometric stitching; each pass pulls out one stitched
                    # contour (outer perimeter, interior holes, or disjoint
                    # fragments).  Closed contours smaller than the hull are
                    # treated as holes; the first large (≈hull-size) closed
                    # contour is skipped because it duplicates the outer hull
                    # already in hand.
                    remaining_edges = [list(e) for e in full_edges if len(e) >= 2]
                    for _sweep_pass in range(20):
                        if not remaining_edges:
                            break
                        chain, chain_closed = _chain_edges_by_geometry(remaining_edges, max_gap=0.1)
                        if not chain:
                            break
                        chain_key = set()
                        for cp in chain:
                            k = (round(cp[0], 3), round(cp[1], 3), round(cp[2], 3))
                            chain_key.add(k)

                        def _on_chain(pt, tol2=0.05 ** 2):
                            k0 = (round(pt[0], 3), round(pt[1], 3), round(pt[2], 3))
                            if k0 in chain_key:
                                return True
                            for cx, cy, cz in chain_key:
                                ddx = pt[0] - cx
                                ddy = pt[1] - cy
                                ddz = pt[2] - cz
                                if ddx * ddx + ddy * ddy + ddz * ddz < tol2:
                                    return True
                            return False

                        kept = []
                        for e in remaining_edges:
                            if len(e) < 2:
                                continue
                            if not (_on_chain(e[0]) and _on_chain(e[-1])):
                                kept.append(e)
                        if len(kept) == len(remaining_edges):
                            break
                        remaining_edges = kept
                        if chain_closed and len(chain) >= 3:
                            cand = _strip_spikes(_dedup_poly(chain))
                            if len(cand) >= 3:
                                cand_area = _abs_loop_area(cand)
                                if cand_area < 0.7 * hull_area and cand_area > 0.01:
                                    hole_polys.append(cand)
                    polys = [hull] + hole_polys

    # Align the outer (first / largest) polygon winding to the surface normal
    # so triangles produced by _triangulate_plane face out of the ACIS solid
    # regardless of whether the input polygons came from a pointer walk, a
    # geometric stitch, or a synthetic convex hull.  Synthetic loops (hull
    # fallback, variant-layout recovered holes) don't carry ACIS sense
    # information and can end up with reversed winding relative to the
    # surface — back-face culling then drops those triangles completely,
    # which is why sh_cans:top used to appear as a handful of stray side
    # wires with no visible plate face in the GUI.
    if polys and surf is not None:
        try:
            areas_p = [_abs_loop_area(p) for p in polys if len(p) >= 3]
            if areas_p:
                outer_p = polys[int(np.argmax(areas_p))]
                if len(outer_p) >= 3:
                    pn = _poly_normal(outer_p)
                    if np.linalg.norm(pn) >= _EPS:
                        pn = _unit(pn)
                        sn = None
                        vecs_s = _geom_vecs(surf)
                        if len(vecs_s) >= 2:
                            sn = _unit(np.asarray(vecs_s[1], dtype=float))
                        if sn is not None and float(np.dot(pn, sn)) < -0.3:
                            polys = [list(reversed(p)) for p in polys]
        except Exception:
            pass

    if surf["type"] == "cone":
        vecs = _geom_vecs(surf)
        if len(vecs) >= 3:
            flts = [v for k, v in _payload(surf) if k == "f64"]
            sine = flts[1] if len(flts) > 1 else 0.0
            cosine = flts[2] if len(flts) > 2 else 1.0
            wall = _mesh_revolution(vecs[0], vecs[1], vecs[2], sine, cosine, polys)
            if wall:
                return wall
            return []
    if not polys:
        return []
    return _triangulate_plane(polys)


def _body_mesh(ents, base, end) -> tuple[list, list]:
    tris = []
    for e in ents[base:end]:
        if e["type"] == "face":
            tris.extend(_tessellate_face(ents, base, e, end))
    if not tris:
        return [], []
    key_to_i = {}
    points = []
    faces = []
    for tri in tris:
        ids = []
        for p in tri:
            key = (round(float(p[0]), 5), round(float(p[1]), 5), round(float(p[2]), 5))
            if key not in key_to_i:
                key_to_i[key] = len(points)
                points.append((float(p[0]), float(p[1]), float(p[2])))
            ids.append(key_to_i[key])
        if len(set(ids)) == 3:
            faces.append(tuple(ids))
    return points, faces


def _body_wires(ents, base, end, mesh_points=None) -> list:
    """ACIS edges as polylines — CST wireframe draws these, not triangle diagonals."""
    mesh_keys = None
    if mesh_points:
        mesh_keys = {(round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3))
                     for p in mesh_points}
    wires = []
    for e in ents[base:end]:
        if e["type"] != "edge":
            continue
        samples = _sample_edge(ents, base, e)
        if len(samples) < 2:
            continue
        poly = []
        for p in samples:
            pt = (float(p[0]), float(p[1]), float(p[2]))
            if poly:
                dx = pt[0] - poly[-1][0]
                dy = pt[1] - poly[-1][1]
                dz = pt[2] - poly[-1][2]
                if dx * dx + dy * dy + dz * dz < 1e-16:
                    continue
            poly.append(pt)
        if len(poly) < 2:
            continue
        if mesh_keys is not None:
            a = (round(poly[0][0], 3), round(poly[0][1], 3), round(poly[0][2], 3))
            b = (round(poly[-1][0], 3), round(poly[-1][1], 3), round(poly[-1][2], 3))
            if a not in mesh_keys and b not in mesh_keys:
                continue
        wires.append(poly)
    return wires


def _bodies_from_entities(ents: list) -> list[dict]:
    body_idx = [i for i, e in enumerate(ents) if e["type"] == "body"]
    out = []
    for bi, start in enumerate(body_idx):
        end = body_idx[bi + 1] if bi + 1 < len(body_idx) else len(ents)
        name, material, colour = "", "", None
        pts = []
        for e in ents[start:end]:
            if e["type"] == "point":
                p = _first_pos(e)
                if p is not None:
                    pts.append(p)
            if "color" in e["type"]:
                rgb = [v for k, v in e["fields"] if k == "f64" and 0.0 <= v <= 1.0]
                if len(rgb) >= 3 and colour is None:
                    colour = tuple(rgb[:3])
            if e["type"] != "name_attrib":
                continue
            for k, s in e["fields"]:
                if k != "str":
                    continue
                decoded = _decode_attrib(s)
                if decoded is None:
                    continue
                kind, value = decoded
                if kind == "name" and not name:
                    name = value
                elif kind == "material" and not material:
                    material = value
                elif kind == "colour" and colour is None:
                    rgb = _parse_rgb(value)
                    if rgb:
                        colour = rgb
        if not pts:
            continue
        xs, ys, zs = zip(*[(p[0], p[1], p[2]) for p in pts])
        bounds = _pad_bounds((min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
        mpts, mfaces = _body_mesh(ents, start, end)
        wires = _body_wires(ents, start, end, mpts)
        rec = {
            "name": name or f"body_{bi}",
            "material": material or "PEC",
            "colour": ",".join(f"{c:.6f}" for c in colour) if colour else "",
            "bounds": bounds,
            "source": "sab",
        }
        if mpts and mfaces:
            rec["mesh"] = {"points": mpts, "faces": mfaces, "wires": wires}
        if wires:
            rec["wires"] = wires
        out.append(rec)
    return out


def extract_bodies(data: bytes) -> list[dict]:
    """Return CST-solid dicts (with optional triangle meshes) from SAB bytes."""
    if not data:
        return []
    starts = []
    idx = data.find(b"ACIS BinaryFile")
    while idx != -1:
        starts.append(idx)
        idx = data.find(b"ACIS BinaryFile", idx + 1)
    if not starts:
        return []
    best: list[dict] = []
    for start in starts:
        try:
            epos = _parse_header(data, start)
            ents = _scan_entities(data, epos)
            bodies = _bodies_from_entities(ents)
        except (ValueError, struct.error):
            continue
        meshed = sum(1 for b in bodies if b.get("mesh"))
        best_m = sum(1 for b in best if b.get("mesh"))
        if meshed > best_m or (meshed == best_m and len(bodies) > len(best)):
            best = bodies
    return best


def opacity_for(name: str, material: str) -> float:
    """CST Shading is opaque by default; only the outer cover/glass is see-through."""
    solid = (name or "").split(":")[-1].lower()
    mat = (material or "").lower()
    blob = f"{name} {material}".lower()
    if any(k in blob for k in ("vacuum", "foam", "radome", "space", "air")):
        return 0.06
    if solid in ("cover", "screen") or (
            "plasticcover" in mat and solid == "cover"):
        return 0.28
    if solid in ("glass",) or "fused silica" in mat:
        return 0.35
    return 1.0
