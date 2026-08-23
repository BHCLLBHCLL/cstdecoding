# -*- coding: utf-8 -*-
"""ASCII SAT export/import and optional STEP."""

from pathlib import Path

from cst_cad import parse_sat, project_to_sat, sat_to_components, write_sat, write_step
from cst_project import box_mesh

_SCRATCH = Path(__file__).resolve().parent / "_scratch"


def _tmp(name: str) -> Path:
    _SCRATCH.mkdir(exist_ok=True)
    path = _SCRATCH / name
    if path.exists():
        path.unlink()
    return path


def test_sat_box_roundtrip():
    data = {
        "components": [{
            "name": "component1:box",
            "material": "PEC",
            "bounds": (-2, 2, -3, 3, 0, 0.5),
            "mesh": box_mesh(-2, 2, -3, 3, 0, 0.5),
        }]
    }
    text = project_to_sat(data)
    assert text.startswith("700 ")
    assert "End-of-ACIS-data" in text
    assert "CST-SOLIDS" in text
    assert "body $" in text
    assert "point $-1" in text
    solids = parse_sat(text)
    assert len(solids) == 1
    assert solids[0]["name"] == "component1:box"
    assert len(solids[0]["points"]) == 8
    assert len(solids[0]["faces"]) == 12
    comps = sat_to_components(text)
    assert comps[0]["bounds"][0] == -2
    assert comps[0]["bounds"][5] == 0.5

    path = _tmp("box.sat")
    write_sat(path, data)
    again = parse_sat(path.read_text(encoding="ascii"))
    assert again[0]["name"] == "component1:box"


def test_sat_bounds_only_solid():
    data = {"components": [{"name": "c:s", "bounds": (0, 1, 0, 2, 0, 3)}]}
    comps = sat_to_components(project_to_sat(data))
    assert comps[0]["name"] == "c:s"
    assert comps[0]["bounds"] == (0, 1, 0, 2, 0, 3)


def test_write_step_optional():
    data = {"components": [{"name": "c:s", "bounds": (0, 1, 0, 1, 0, 1)}]}
    path = _tmp("maybe.step")
    ok = write_step(path, data)
    if not ok:
        assert not path.exists() or path.stat().st_size == 0
    else:
        assert path.stat().st_size > 0
