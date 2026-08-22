# -*- coding: utf-8 -*-
"""Parse CST result files for viewing (no solver).

.r1d / .r0d in a .cst are usually plot templates (metadata + VBA), not
sampled traces. Farfield ``.dat`` and ASCII XY tables carry numbers.
"""

from __future__ import annotations

import math
import struct
from typing import Optional


def _u32(data: bytes, i: int) -> tuple[int, int]:
    if i + 4 > len(data):
        raise ValueError("truncated i32")
    return struct.unpack_from("<i", data, i)[0], i + 4


def _cstr(data: bytes, i: int) -> tuple[str, int]:
    n, i = _u32(data, i)
    if n < 0 or i + n > len(data):
        raise ValueError("truncated string")
    raw = data[i:i + n]
    i += n
    if raw.endswith(b"\x00"):
        raw = raw[:-1]
    return raw.decode("latin-1", "replace"), i


def parse_r1d(data: bytes) -> dict:
    """Return metadata / optional samples from a CST .r1d or .r0d blob."""
    rec = {
        "format": "r1d",
        "version": None,
        "meta": {},
        "script": "",
        "x": [],
        "y": [],
        "xlabel": "",
        "ylabel": "",
        "title": "",
    }
    if not data or len(data) < 12:
        return rec
    try:
        ver, i = _u32(data, 0)
        _flags, i = _u32(data, i)
        rec["version"] = ver
        rec["cst_stamp"], i = _cstr(data, i)
        rec["cst_stamp2"], i = _cstr(data, i)
        n, i = _u32(data, i)
        meta = {}
        if 0 <= n <= 400:
            for _ in range(n):
                key, i = _cstr(data, i)
                val, i = _cstr(data, i)
                meta[key] = val
        rec["meta"] = meta
        if i + 4 <= len(data):
            slen, j = _u32(data, i)
            if 0 <= slen <= len(data) - j:
                rec["script"] = data[j:j + slen].decode("latin-1", "replace")
                i = j + slen
        rec["format"] = "r0d" if str(meta.get("TemplateType", "")).upper() in (
            "0D", "2D", "3D") or meta.get("Plot3dSurf") else "r1d"
        rec["title"] = (meta.get("labletext") or meta.get("SPName")
                        or meta.get("ResultName") or meta.get("a0DValue") or "")
        rec["xlabel"] = meta.get("OverwriteXLabel") or meta.get("Linear") or ""
        rec["ylabel"] = meta.get("sComponentName") or meta.get("OutputType") or ""
        tail = data[i:]
        xs, ys = _floats_as_xy(tail)
        if xs:
            rec["x"], rec["y"] = xs, ys
    except (ValueError, struct.error):
        pass
    if not rec["x"]:
        ascii_xy = parse_ascii_xy(data.decode("latin-1", "replace"))
        if ascii_xy["x"]:
            rec["x"], rec["y"] = ascii_xy["x"], ascii_xy["y"]
            rec["xlabel"] = rec["xlabel"] or ascii_xy.get("xlabel") or ""
            rec["ylabel"] = rec["ylabel"] or ascii_xy.get("ylabel") or ""
    return rec


def parse_r0d(data: bytes) -> dict:
    rec = parse_r1d(data)
    rec["format"] = "r0d"
    return rec


def _floats_as_xy(blob: bytes) -> tuple[list, list]:
    """Interpret leftover bytes as interleaved or split f64 x/y samples."""
    if len(blob) < 32:
        return [], []
    n = len(blob) // 8
    if n < 4:
        return [], []
    vals = list(struct.unpack_from("<" + "d" * n, blob))
    if not all(math.isfinite(v) for v in vals):
        return [], []
    if n >= 4 and n % 2 == 0:
        xs, ys = vals[0::2], vals[1::2]
        if _looks_like_axis(xs) and any(math.isfinite(y) for y in ys):
            return xs, ys
        half = n // 2
        xs, ys = vals[:half], vals[half:]
        if _looks_like_axis(xs) and any(math.isfinite(y) for y in ys):
            return xs, ys
    return [], []


def _looks_like_axis(xs: list) -> bool:
    if len(xs) < 3:
        return False
    if not all(math.isfinite(x) for x in xs):
        return False
    span = max(xs) - min(xs)
    if span <= 0:
        return False
    inc = sum(1 for a, b in zip(xs, xs[1:]) if b >= a)
    return inc >= len(xs) - 2


def parse_ascii_xy(text: str) -> dict:
    """Two-or-more-column numeric table (CST export / generic 1D)."""
    rec = {"format": "ascii", "x": [], "y": [], "xlabel": "", "ylabel": "",
           "title": "", "meta": {}}
    if not text:
        return rec
    xs, ys = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#%;/":
            if line.lower().startswith("# x") or "frequency" in line.lower():
                rec["xlabel"] = rec["xlabel"] or line.lstrip("#%;/ ").strip()
            continue
        if line.startswith("//") or line.startswith("Dimension") or "=" in line[:24]:
            if " = " in line:
                k, _, v = line.partition("=")
                rec["meta"][k.strip()] = v.strip()
            continue
        parts = line.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
        except ValueError:
            continue
    rec["x"], rec["y"] = xs, ys
    return rec


def parse_farfield_dat(text: str) -> dict:
    """CST Farfield Format V1 ASCII (theta, phi, E components)."""
    rec = {
        "format": "farfield",
        "meta": {},
        "theta": [],
        "phi": [],
        "values": [],
        "x": [],
        "y": [],
        "xlabel": "Theta (deg)",
        "ylabel": "|E|",
        "title": "",
        "grid": None,
    }
    if not text:
        return rec
    rows = []
    header_done = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("//"):
            header_done = True
            continue
        if not header_done and "=" in line:
            k, _, v = line.partition("=")
            rec["meta"][k.strip()] = v.strip()
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            th, ph = float(parts[0]), float(parts[1])
            re_t, im_t = float(parts[2]), float(parts[3])
            re_p, im_p = float(parts[4]), float(parts[5])
        except ValueError:
            continue
        mag = math.hypot(math.hypot(re_t, im_t), math.hypot(re_p, im_p))
        rows.append((th, ph, mag))
    if not rows:
        return rec
    thetas = sorted({r[0] for r in rows})
    phis = sorted({r[1] for r in rows})
    rec["theta"], rec["phi"] = thetas, phis
    grid = [[0.0] * len(phis) for _ in thetas]
    imap = {t: i for i, t in enumerate(thetas)}
    jmap = {p: j for j, p in enumerate(phis)}
    for th, ph, mag in rows:
        grid[imap[th]][jmap[ph]] = mag
    rec["grid"] = grid
    rec["title"] = rec["meta"].get("Type") or "Farfield"
    freq = rec["meta"].get("Frequency")
    if freq:
        rec["title"] = f"{rec['title']}  f={freq}"
    cut = farfield_cut(rec, phi=None)
    rec["x"], rec["y"] = cut["x"], cut["y"]
    return rec


def farfield_cut(ff: dict, phi: Optional[float] = None) -> dict:
    """1D |E| vs theta at a phi cut (default: first / 0 deg)."""
    phis = ff.get("phi") or []
    thetas = ff.get("theta") or []
    grid = ff.get("grid")
    if not phis or not thetas or not grid:
        return {"x": [], "y": []}
    if phi is None:
        phi = 0.0 if 0.0 in phis else phis[0]
    j = min(range(len(phis)), key=lambda k: abs(phis[k] - phi))
    return {"x": list(thetas), "y": [row[j] for row in grid],
            "xlabel": "Theta (deg)", "ylabel": "|E|",
            "title": f"phi={phis[j]:g} deg"}


def parse_result_bytes(data: bytes, name: str = "") -> dict:
    """Auto-detect r1d / r0d / farfield / ASCII XY."""
    low = (name or "").lower()
    if data.startswith(b"CST Farfield") or data.startswith(b"CST FARFIELD"):
        rec = parse_farfield_dat(data.decode("latin-1", "replace"))
        rec["name"] = name
        return rec
    text = None
    if data[:1] in (b"#", b"%", b"/") or (data[:1].isdigit() or data[:1] == b"-"):
        text = data.decode("latin-1", "replace")
        if "CST Farfield" in text[:80]:
            rec = parse_farfield_dat(text)
            rec["name"] = name
            return rec
    if low.endswith(".r0d"):
        rec = parse_r0d(data)
        rec["name"] = name
        return rec
    if low.endswith(".r1d") or (len(data) >= 8 and data[0] in (2, 3, 4)):
        rec = parse_r1d(data)
        rec["name"] = name
        return rec
    rec = parse_ascii_xy(data.decode("latin-1", "replace") if text is None
                         else text)
    rec["name"] = name
    return rec


def result_has_curve(rec: dict) -> bool:
    return bool(rec and rec.get("x") and rec.get("y")
                and len(rec["x"]) == len(rec["y"]) and len(rec["x"]) >= 2)


def result_has_grid(rec: dict) -> bool:
    grid = rec.get("grid") if rec else None
    return bool(grid and grid[0])


def curve_to_csv(rec: dict) -> str:
    xs = rec.get("x") or []
    ys = rec.get("y") or []
    xlab = rec.get("xlabel") or "x"
    ylab = rec.get("ylabel") or "y"
    lines = [f"{xlab},{ylab}"]
    for x, y in zip(xs, ys):
        lines.append(f"{x},{y}")
    return "\n".join(lines) + "\n"
