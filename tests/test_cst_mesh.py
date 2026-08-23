# -*- coding: utf-8 -*-
"""ModelCache index and mesh-property write-back (no mesher)."""

from cst_mesh import (
    build_sab_index, mesh_stats, parse_mesh_properties, parse_sab_index,
    save_mesh_properties, summarize_modelcache, write_mesh_properties,
)
from cst_project import archive_text
from cst_parser import new_project_files


def test_parse_sab_index_roundtrip():
    raw = build_sab_index([0, 4096, 8192])
    parsed = parse_sab_index(raw)
    assert parsed["count"] == 3
    assert parsed["offsets"] == [0, 4096, 8192]
    assert parsed["sizes"][0] == 4096
    assert parsed["sizes"][1] == 4096
    assert parse_sab_index(b"")["count"] == 0


def test_summarize_modelcache_from_archive():
    sab = b"ACIS BinaryFile" + b"\x00" * 32 + b"ACIS BinaryFile" + b"\x00" * 8
    archive = {
        "ModelCache/Model.sab": sab,
        "ModelCache/Model.sab.index": build_sab_index([0, 15]),
    }
    info = summarize_modelcache(archive)
    assert info["has_cache"] is True
    assert info["segments"] == 2
    assert info["acis_headers"] == 2
    assert info["sab_bytes"] == len(sab)
    assert summarize_modelcache({})["has_cache"] is False


def test_mesh_properties_parse_and_replace():
    text = (
        "With MeshSettings\n"
        '     .SetMeshType "Hex"\n'
        '     .SetCreator "High Frequency"\n'
        '     .Set "StepsPerWaveNear", "10"\n'
        '     .Set "RatioLimitGeometry", "15"\n'
        "End With\n"
        'Mesh.Accuracy "1e-3"\n'
    )
    rec = parse_mesh_properties(text)
    assert rec["type"] == "Hex"
    assert rec["creator"] == "High Frequency"
    assert rec["props"]["StepsPerWaveNear"] == "10"
    assert rec["props"]["Accuracy"] == "1e-3"

    out = write_mesh_properties(text, {
        "StepsPerWaveNear": "20",
        "MeshType": "Tet",
        "NewKey": "7",
    })
    again = parse_mesh_properties(out)
    assert again["props"]["StepsPerWaveNear"] == "20"
    assert again["type"] == "Tet"
    assert again["props"]["NewKey"] == "7"
    assert again["props"]["RatioLimitGeometry"] == "15"


def test_mesh_properties_append_on_new_project():
    archive = {n: b for n, b in new_project_files()}
    rec = save_mesh_properties(archive, {
        "StepsPerWaveNear": "12",
        "SetMeshType": "Hex",
    })
    assert rec["props"]["StepsPerWaveNear"] == "12"
    mod = archive_text(archive, "Model/3D/Model.mod")
    assert "With MeshSettings" in mod
    assert 'StepsPerWaveNear", "12"' in mod


def test_mesh_stats_from_components():
    data = {
        "components": [
            {"name": "a:s", "mesh": {"points": [(0, 0, 0)] * 3,
                                     "faces": [(0, 1, 2), (0, 2, 1)]}},
            {"name": "b:s"},
        ],
        "modelcache": {"has_cache": True, "segments": 3, "sab_bytes": 99},
    }
    st = mesh_stats(data)
    assert st["solids"] == 1
    assert st["triangles"] == 2
    assert st["cache_segments"] == 3
    assert st["hex_cells"] == 0
