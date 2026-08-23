# -*- coding: utf-8 -*-
"""ModelCache index + Mesh property keywords (view / write-back, no mesher)."""

from __future__ import annotations

import re
import struct

from cst_project import archive_get, archive_key, archive_set, archive_text

_MODEL_MOD = "Model/3D/Model.mod"

# Common CST Mesh / MeshSettings keys we display. Unknown keys in the file
# are also kept (parse is open-ended).
DEFAULT_MESH_KEYS = (
    "MeshType",
    "SetMeshType",
    "SetCreator",
    "StepsPerWaveNear",
    "StepsPerWaveFar",
    "RatioLimitGeometry",
    "SrfMeshGradation",
    "Accuracy",
)

_SET_RE = re.compile(
    r'\.Set\s+"([^"]+)"\s*,\s*"([^"]*)"', re.I)
_TYPED_RE = re.compile(
    r'\.(MeshType|SetMeshType|SetCreator|Accuracy)\s+"([^"]*)"', re.I)
_MESH_DOT_RE = re.compile(
    r'^Mesh\.(\w+)\s+"([^"]*)"', re.M | re.I)
_MESH_BLOCK_RE = re.compile(
    r"With Mesh(?:Settings)?\s+(.*?)End With", re.S | re.I)


def parse_sab_index(data: bytes) -> dict:
    """ModelCache/Model.sab.index: int32 count + N×int64 offsets."""
    if not data or len(data) < 4:
        return {"count": 0, "offsets": [], "sizes": []}
    n = struct.unpack_from("<i", data, 0)[0]
    if n < 0 or n > 1_000_000:
        return {"count": 0, "offsets": [], "sizes": []}
    offs = []
    for i in range(n):
        pos = 4 + i * 8
        if pos + 8 > len(data):
            break
        offs.append(int(struct.unpack_from("<q", data, pos)[0]))
    sizes = []
    for i, off in enumerate(offs):
        nxt = offs[i + 1] if i + 1 < len(offs) else None
        sizes.append(None if nxt is None else max(0, nxt - off))
    return {"count": len(offs), "offsets": offs, "sizes": sizes}


def build_sab_index(offsets) -> bytes:
    offs = [int(o) for o in (offsets or [])]
    out = struct.pack("<i", len(offs))
    out += b"".join(struct.pack("<q", o) for o in offs)
    return out


def summarize_modelcache(archive: dict) -> dict:
    """Describe ModelCache SAB + index without generating a mesh."""
    idx_key = archive_key(archive, "ModelCache/Model.sab.index")
    sab_key = archive_key(archive, "ModelCache/Model.sab")
    idx = archive_get(archive, "ModelCache/Model.sab.index")
    sab = archive_get(archive, "ModelCache/Model.sab")
    parsed = parse_sab_index(idx)
    magic = sab.count(b"ACIS BinaryFile") if sab else 0
    segments = parsed["count"] or magic
    return {
        "has_cache": bool(sab or idx),
        "sab_key": sab_key or "",
        "index_key": idx_key or "",
        "sab_bytes": len(sab or b""),
        "segments": segments,
        "offsets": parsed["offsets"],
        "acis_headers": magic,
    }


def parse_mesh_properties(text: str) -> dict:
    """Collect Mesh / MeshSettings / Mesh.Key keywords from Model.mod."""
    items = []
    seen = set()

    def add(key, value, source):
        key = str(key or "").strip()
        if not key or key in seen:
            return
        seen.add(key)
        items.append({"key": key, "value": str(value), "source": source})

    src = (text or "").replace("\r\n", "\n")
    for block in _MESH_BLOCK_RE.finditer(src):
        body = block.group(1)
        title = "MeshSettings" if "settings" in (block.group(0)[:20].lower()) else "Mesh"
        for m in _SET_RE.finditer(body):
            add(m.group(1), m.group(2), title)
        for m in _TYPED_RE.finditer(body):
            add(m.group(1), m.group(2), title)
    for m in _MESH_DOT_RE.finditer(src):
        add(m.group(1), m.group(2), "Mesh.")
    props = {it["key"]: it["value"] for it in items}
    return {
        "items": items,
        "props": props,
        "type": props.get("SetMeshType") or props.get("MeshType") or "",
        "creator": props.get("SetCreator") or "",
    }


def _alias_keys(key: str) -> tuple[str, ...]:
    if key in ("MeshType", "SetMeshType"):
        return ("SetMeshType", "MeshType")
    return (key,)


def _replace_existing(text: str, key: str, value: str) -> tuple[str, bool]:
    value = str(value)
    for name in _alias_keys(key):
        patterns = (
            rf'(\.Set\s+"{re.escape(name)}"\s*,\s*")[^"]*(")',
            rf'(Mesh\.{re.escape(name)}\s+")[^"]*(")',
            rf'(\.{re.escape(name)}\s+")[^"]*(")',
        )
        for pat in patterns:
            rx = re.compile(pat, re.I)
            if rx.search(text):
                return rx.sub(rf"\g<1>{value}\2", text, count=1), True
    return text, False


def _meshsettings_block(updates: dict) -> str:
    lines = ["With MeshSettings", '     .SetMeshType "Hex"']
    if "SetMeshType" not in updates and "MeshType" not in updates:
        pass
    for key, val in updates.items():
        if key in ("SetMeshType", "MeshType"):
            lines[1] = f'     .SetMeshType "{val}"'
            continue
        if key == "SetCreator":
            lines.append(f'     .SetCreator "{val}"')
            continue
        lines.append(f'     .Set "{key}", "{val}"')
    lines.append("End With")
    return "\n" + "\n".join(lines) + "\n"


def write_mesh_properties(text: str, updates: dict) -> str:
    """Replace existing mesh keywords; append a MeshSettings block for new ones."""
    if not updates:
        return text or ""
    out = text or ""
    pending = {}
    for key, val in updates.items():
        if not key:
            continue
        out, ok = _replace_existing(out, key, val)
        if not ok:
            pending[key] = val
    if not pending:
        return out
    m = None
    for m in _MESH_BLOCK_RE.finditer(out):
        pass
    if m is not None:
        insert = "".join(
            f'     .Set "{k}", "{v}"\n' for k, v in pending.items()
            if k not in ("SetMeshType", "MeshType", "SetCreator"))
        extra = ""
        if "SetMeshType" in pending or "MeshType" in pending:
            extra += f'     .SetMeshType "{pending.get("SetMeshType") or pending.get("MeshType")}"\n'
        if "SetCreator" in pending:
            extra += f'     .SetCreator "{pending["SetCreator"]}"\n'
        chunk = extra + insert
        end = m.end()
        # insert before the matching End With
        end_with = out.rfind("End With", m.start(), end)
        if end_with > 0:
            out = out[:end_with] + chunk + out[end_with:]
            return out
    return out.rstrip() + _meshsettings_block(pending)


def load_mesh_properties(archive: dict) -> dict:
    return parse_mesh_properties(archive_text(archive, _MODEL_MOD))


def save_mesh_properties(archive: dict, updates: dict) -> dict:
    mod = archive_text(archive, _MODEL_MOD)
    new_mod = write_mesh_properties(mod, updates)
    archive_set(archive, _MODEL_MOD, new_mod.encode("latin-1", "replace"))
    return parse_mesh_properties(new_mod)


def mesh_stats(project_data: dict) -> dict:
    """Triangle counts from already-cached solid tessellation (not a hex mesh)."""
    comps = (project_data or {}).get("components") or []
    n_pts = n_faces = n_solids = 0
    for c in comps:
        mesh = c.get("mesh") or {}
        faces = mesh.get("faces") or []
        pts = mesh.get("points") or []
        if faces:
            n_solids += 1
            n_faces += len(faces)
            n_pts += len(pts)
    cache = (project_data or {}).get("modelcache") or {}
    return {
        "solids": n_solids,
        "triangles": n_faces,
        "points": n_pts,
        "cache_segments": int(cache.get("segments") or 0),
        "cache_bytes": int(cache.get("sab_bytes") or 0),
        "has_cache": bool(cache.get("has_cache")),
        "hex_cells": 0,
        "tet_cells": 0,
    }
