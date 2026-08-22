# -*- coding: utf-8 -*-
"""Tests for cst_project: parameters, history, primitives, boolean, transform."""

from cst_parser import new_project_files, open_cst, write_cst
from cst_project import (
    UndoStack, append_history, archive_text, boolean_vba, box_mesh,
    brick_vba, cone_mesh, cylinder_mesh, discrete_port_vba, dump_parameters_json,
    eval_excitations, eval_expr, eval_point, eval_range, intersect_bounds,
    material_vba, mesh_bounds, merge_meshes, monitor_vba, next_port_number,
    parse_hidden_solids, dump_hidden_solids, parse_set_point, probe_vba,
    resolve_parameters, rotate_fn, set_parameter_in_mod, sphere_mesh,
    torus_mesh, transform_component, transform_translate_vba, translate_fn,
    union_bounds, unique_solid_name, waveguide_port_vba, write_parameters,
)
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parent / "_scratch"


def _tmp(name: str) -> Path:
    _SCRATCH.mkdir(exist_ok=True)
    path = _SCRATCH / name
    if path.exists():
        path.unlink()
    return path


def test_undo_stack_linear():
    state = {"n": 0}
    stack = UndoStack()

    def set_n(v, s=state):
        s["n"] = v

    stack.push(lambda: set_n(0), lambda: set_n(1), "one")
    set_n(1)
    stack.push(lambda: set_n(1), lambda: set_n(2), "two")
    set_n(2)
    assert stack.undo() == "two"
    assert state["n"] == 1
    assert stack.undo() == "one"
    assert state["n"] == 0
    assert stack.redo() == "one"
    assert state["n"] == 1
    stack.push(lambda: set_n(1), lambda: set_n(9), "nine")
    set_n(9)
    assert not stack.can_redo()
    assert stack.undo() == "nine"
    assert state["n"] == 1


def test_eval_and_resolve_parameters():
    params = [
        {"name": "W", "expr": "20", "value": "", "description": "width"},
        {"name": "half", "expr": "W/2", "value": "", "description": ""},
        {"name": "max_frequency", "expr": "30", "value": "", "description": ""},
        {"name": "max_cell", "expr": "1000*3e8/(max_frequency*1e9*15)",
         "value": "", "description": ""},
    ]
    out = resolve_parameters(params)
    assert out[0]["value"] == "20"
    assert out[1]["value"] == "10"
    assert abs(float(out[3]["value"]) - 0.666666666666667) < 1e-9
    assert eval_expr("W+half", out) == 30


def test_parameter_json_and_mod_writeback(tmp_path=None):
    archive = {n: b for n, b in new_project_files()}
    params = [
        {"name": "L", "expr": "40", "value": "40", "description": "length"},
        {"name": "W", "expr": "L/2", "value": "20", "description": "width"},
    ]
    write_parameters(archive, params)
    blob = archive["Model/Parameters.json"].decode("utf-8")
    assert '"name": "L"' in blob
    assert '"expr": "40"' in blob
    assert '"value": "20"' in blob
    mod = archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'MakeSureParameterExists "L", "40"' in mod
    assert 'MakeSureParameterExists "W", "L/2"' in mod
    assert 'SetParameterDescription "L", "length"' in mod
    write_parameters(archive, [
        {"name": "L", "expr": "50", "value": "50", "description": "length"},
        {"name": "W", "expr": "L/2", "value": "25", "description": "width"},
    ])
    mod = archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'MakeSureParameterExists "L", "50"' in mod
    assert mod.count('MakeSureParameterExists "L"') == 1


def test_parameter_save_reopen_roundtrip():
    archive = {n: b for n, b in new_project_files()}
    write_parameters(archive, [
        {"name": "gap", "expr": "0.5", "value": "0.5", "description": "slot"},
    ])
    path = _tmp("params_round.cst")
    write_cst(path, archive.items())
    _meta, entries = open_cst(path)
    by = {e["name"].replace("\\", "/"): e["content"] for e in entries}
    import json
    recs = json.loads(by["Model/Parameters.json"])["parameters"]
    assert recs[0]["name"] == "gap"
    assert recs[0]["expr"] == "0.5"
    assert recs[0]["value"] == "0.5"
    assert b'MakeSureParameterExists "gap", "0.5"' in by["Model/3D/Model.mod"]


def test_set_parameter_in_mod_replace_existing():
    text = 'MakeSureParameterExists "W", "10"\n'
    out = set_parameter_in_mod(text, "W", "Wsub+2")
    assert 'MakeSureParameterExists "W", "Wsub+2"' in out
    assert out.count("MakeSureParameterExists") == 1


def test_hidden_solids_roundtrip():
    names = {"component1:solid1", "Phone/Housing:cover"}
    dumped = dump_hidden_solids("", names)
    assert parse_hidden_solids(dumped) == names
    again = dump_hidden_solids(dumped, {"component1:a"})
    assert parse_hidden_solids(again) == {"component1:a"}


def test_append_history_mod_and_json():
    archive = {n: b for n, b in new_project_files()}
    append_history(archive, "define brick: component1:box",
                   brick_vba("box", "component1", "PEC",
                             ("-1", "1"), ("-2", "2"), ("0", "0.5")))
    mod = archive_text(archive, "Model/3D/Model.mod")
    assert "'@ define brick: component1:box" in mod
    assert '.Name "box"' in mod
    hist = archive["Model/3D/ModelHistory.json"].decode("utf-8")
    assert "define brick: component1:box" in hist
    assert "With Brick" in hist


def test_primitive_meshes_closed():
    box = box_mesh(-1, 1, -2, 2, 0, 0.5)
    assert len(box["points"]) == 8
    assert len(box["faces"]) == 12
    assert mesh_bounds(box) == (-1, 1, -2, 2, 0, 0.5)
    cyl = cylinder_mesh(0, 0, -5, 5, 3, n=16)
    assert len(cyl["faces"]) == 16 * 4
    sph = sphere_mesh(0, 0, 0, 10)
    assert min(p[2] for p in sph["points"]) < -9
    tor = torus_mesh(0, 0, 0, 8, 1.5)
    assert len(tor["faces"]) > 100
    cone = cone_mesh(0, 0, 0, 10, 4, 1)
    assert mesh_bounds(cone)[5] == 10


def test_boolean_bounds_and_vba():
    a = (-10, 10, -4, 4, 0, 2)
    b = (0, 12, -1, 1, -1, 3)
    u = union_bounds(a, b)
    assert u == (-10, 12, -4, 4, -1, 3)
    inter = intersect_bounds(a, b)
    assert inter == (0, 10, -1, 1, 0, 2)
    assert intersect_bounds(a, (100, 101, 0, 1, 0, 1)) is None
    assert 'Solid.Subtract "A", "B"' in boolean_vba("subtract", "A", "B")
    ma = box_mesh(*a)
    mb = box_mesh(*b)
    merged = merge_meshes(ma, mb)
    assert len(merged["points"]) == 16
    assert len(merged["faces"]) == 24


def test_transform_component_translate_rotate():
    comp = {"name": "c:s", "bounds": (0, 2, 0, 2, 0, 2), "mesh": box_mesh(0, 2, 0, 2, 0, 2)}
    moved = transform_component(comp, translate_fn(10, 0, 0))
    assert moved["bounds"][0] == 10
    assert moved["bounds"][1] == 12
    rot = transform_component(comp, rotate_fn("z", 90, (0, 0, 0)))
    # (2,0,0) -> (0,2,0); bbox x from 0..2 becomes about -2..0
    assert rot["bounds"][0] < 0.01
    assert rot["bounds"][3] > 1.9
    vba = transform_translate_vba("c:s", "1", "0", "0")
    assert 'Transform "Shape", "Translate"' in vba


def test_material_vba_and_unique_name():
    vba = material_vba("FR4", epsilon="4.3", tand="0.025", colour=("0.9", "0.8", "0.1"))
    assert '.Epsilon "4.3"' in vba
    assert '.TanD "0.025"' in vba
    assert '.Name "FR4"' in vba
    names = {"component1:solid1"}
    assert unique_solid_name(names, "component1", "solid1") == "component1:solid11"
    assert unique_solid_name(names, "component1", "box") == "component1:box"


def test_dump_parameters_json_descr_key():
    blob = dump_parameters_json([
        {"name": "a", "expr": "1", "value": "1", "description": "one"},
    ]).decode("utf-8")
    assert '"descr": "one"' in blob
    assert '"name": "a"' in blob


def test_port_monitor_probe_vba_and_eval():
    vba = discrete_port_vba(1, "50.0", ("0", "0.5", "0"), ("0", "-0.5", "0"))
    assert '.PortNumber "1"' in vba
    assert '.Impedance "50.0"' in vba
    assert '.SetP1 "False", "0", "0.5", "0"' in vba
    assert '.SetP2 "False", "0", "-0.5", "0"' in vba
    p1 = parse_set_point(vba, "SetP1")
    p2 = parse_set_point(vba, "SetP2")
    assert p1 == ("0", "0.5", "0")
    assert p2 == ("0", "-0.5", "0")
    dipole = (
        'With DiscretePort\n'
        '     .SetP1 "True", "0", "0.5", "0"\n'
        '     .SetP2 "True", "0", "-0.5", "0"\n'
        'End With\n'
    )
    assert parse_set_point(dipole, "SetP1") == ("0", "0.5", "0")
    wg = waveguide_port_vba(2, "zmin", ("-10", "10"), ("-5", "5"), ("0", "0"))
    assert 'With Port' in wg
    assert '.Orientation "zmin"' in wg
    mon = monitor_vba("farfield (f=3.5)", "Farfield", "3.5")
    assert '.FieldType "Farfield"' in mon
    assert '.MonitorValue "3.5"' in mon
    pr = probe_vba("probe1", "efield", "0", "0", "1", "Z")
    assert '.FieldName "efield"' in pr
    assert '.Location "0", "0", "1"' in pr
    assert next_port_number([{"port_number": 1}, {"port_number": 3}]) == 4
    assert next_port_number([]) == 1
    params = [
        {"name": "x0", "expr": "5", "value": "5", "description": ""},
        {"name": "y0", "expr": "2", "value": "2", "description": ""},
        {"name": "h", "expr": "1.6", "value": "1.6", "description": ""},
    ]
    assert eval_point(("x0", "y0", "0.0"), params) == (5.0, 2.0, 0.0)
    assert eval_range(("-h", "h"), params) == (-1.6, 1.6)
    data = {
        "parameters": params,
        "ports": [{
            "p1": ("x0", "y0", "0.0"),
            "p2": ("x0", "y0", "-h"),
            "xrange": None,
        }],
        "probes": [{"x": "x0", "y": "y0", "z": "h"}],
    }
    eval_excitations(data)
    assert data["ports"][0]["p1_xyz"] == (5.0, 2.0, 0.0)
    assert abs(data["ports"][0]["p2_xyz"][2] + 1.6) < 1e-9
    assert data["probes"][0]["xyz"] == (5.0, 2.0, 1.6)
