# -*- coding: utf-8 -*-
"""Offscreen regression tests for cst_gui (cabdecoding tests/test_gui.py pattern)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QGroupBox

import cst_gui
from cst_panes import PaneFrame


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


@pytest.fixture
def viewer(qapp):
    win = cst_gui.CSTMainWindow(enable_3d=False)
    yield win
    win.close()


def test_layout_panes(viewer):
    titles = {w.title_label.text() for w in viewer.findChildren(PaneFrame)}
    assert "Navigation Tree" in titles
    assert "Properties" in titles
    assert "Messages" in titles
    assert "Parameter List" in titles


def test_ribbon_tabs(viewer):
    tabs = [viewer._ribbon_tabs.tabText(i)
            for i in range(viewer._ribbon_tabs.count())]
    assert tabs == [
        "Home", "Modeling", "Simulation", "Post-Processing",
        "View", "Macros", "Help",
    ]
    assert viewer._file_btn.text() == "FILE"
    assert "#e64a19" in viewer.styleSheet().lower()
    assert "#0078d7" in viewer.styleSheet().lower()
    groups = [g.title() for g in viewer.findChildren(QGroupBox)
              if g.objectName() == "RibbonGroup"]
    assert "Clipboard" in groups
    assert "Shapes" in groups
    assert "Solver" in groups


def test_icon_sizes_unified(viewer):
    from PyQt5.QtWidgets import QToolButton
    ribbon = {
        btn.iconSize().width()
        for btn in viewer.findChildren(QToolButton)
        if btn.objectName() == "RibbonButton"
    }
    assert ribbon == {32}
    assert viewer.nav_tree.tree.iconSize().width() == 14
    names = [n[6:] for n in dir(cst_gui.AppIcons) if n.startswith("_draw_")]
    assert "brick" in names and "component" in names
    for name in names:
        pm = cst_gui.AppIcons._paint(name, 32)
        assert not pm.isNull(), name
        assert pm.devicePixelRatio() == 2
        assert pm.width() == 64


def test_nav_tree_skeleton(viewer):
    assert viewer.nav_tree.tree.topLevelItemCount() >= 10
    labels = [viewer.nav_tree.tree.topLevelItem(i).text(0)
              for i in range(viewer.nav_tree.tree.topLevelItemCount())]
    assert "Components" in labels
    assert "Materials" in labels
    assert "Ports" in labels
    assert "Parameter List" not in labels
    groups = next(viewer.nav_tree.tree.topLevelItem(i)
                  for i in range(viewer.nav_tree.tree.topLevelItemCount())
                  if viewer.nav_tree.tree.topLevelItem(i).text(0) == "Groups")
    assert [groups.child(i).text(0) for i in range(groups.childCount())] == [
        "Excluded from Simulation", "Excluded from Bounding Box", "Mesh Groups",
    ]
    assert viewer.nav_tree.search.placeholderText() == "Search"


def test_nyi_logs(viewer):
    viewer._nyi("Brick")
    text = viewer.message_win.text.toPlainText()
    assert "Brick" in text
    assert "not yet available" in text


def test_populate_and_visibility(viewer):
    data = {
        "components": [
            {"name": "component1:Patch", "material": "PEC",
             "bounds": (-10, 10, -8, 8, 0, 0.5)},
        ],
        "materials": [{"name": "PEC", "colour": "1,0,0"}],
        "ports": [],
        "monitors": [],
        "groups": [],
        "parameters": [
            {"name": "W", "expr": "20", "value": "20", "description": "width"},
        ],
        "progress": [("demo", "Ready")],
    }
    viewer._project_data = data
    viewer.nav_tree.populate_from_project(data)
    viewer.param_list.set_parameters(data["parameters"])
    viewer.viewport.render_project(data)
    assert viewer.param_list.table.rowCount() == 1
    # component child is checkable
    comps = viewer.nav_tree.tree.topLevelItem(0)
    assert comps.text(0) == "Components"
    parent = comps.child(0)
    child = parent.child(0)
    assert child.text(0) == "Patch"
    viewer._on_visibility("component1:Patch", False)
    assert "component1:Patch" in viewer._hidden_parts
    viewer._on_visibility("component1:Patch", True)
    assert "component1:Patch" not in viewer._hidden_parts


def _find_tree_item(tree, label, parent=None):
    if parent is None:
        for i in range(tree.topLevelItemCount()):
            hit = _find_tree_item(tree, label, tree.topLevelItem(i))
            if hit is not None:
                return hit
        return None
    if parent.text(0) == label:
        return parent
    for i in range(parent.childCount()):
        hit = _find_tree_item(tree, label, parent.child(i))
        if hit is not None:
            return hit
    return None


def test_nav_context_menu_actions(viewer):
    data = {
        "components": [
            {"name": "Phone/Housing:cover", "material": "Plastic",
             "bounds": (-10, 10, -8, 8, 0, 0.3)},
            {"name": "Phone/Housing:radome", "material": "Vacuum",
             "bounds": (-4, 4, -4, 4, 0, 0.1)},
            {"name": "Phone/Battery:Cell", "material": "Copper",
             "bounds": (0, 6, -3, 3, -2, 0)},
        ],
        "groups": [
            {"name": "Excluded from Simulation", "type": "", "items": []},
        ],
        "materials": [
            {"name": "PEC", "folder": "", "colour": "0,0.5,0.75"},
            {"name": "Plastic", "folder": "Phone", "colour": "0.9,0.85,0.2"},
        ],
        "ports": [], "monitors": [], "parameters": [],
    }
    viewer._project_data = data
    viewer.nav_tree.populate_from_project(data)
    tree = viewer.nav_tree.tree
    cover = _find_tree_item(tree, "cover")
    assert cover is not None
    tree.setCurrentItem(cover)

    menu = viewer.nav_tree.build_context_menu(cover)
    labels = [a.text() for a in menu.actions() if a.text()]
    assert labels[:2] == ["Rectangle Selection", "Unselect All"]
    assert "Hide" in labels and "Hide Unselected" in labels
    assert "Show" in labels and "Show All" in labels
    assert "Electrical Connections" in labels
    assert "Local Solid Coordinates" in labels
    assert "Slice by UV Plane" in labels
    assert "Transform..." in labels
    assert "Assign Material and Color..." in labels
    assert "Delete" in labels and "Rename" in labels
    assert "Copy" in labels and "Paste" in labels
    assert "Object Information..." in labels
    assert "Edit Properties..." in labels
    slice_act = next(a for a in menu.actions() if a.text() == "Slice by UV Plane")
    assert not slice_act.isEnabled()
    paste_act = next(a for a in menu.actions() if a.text() == "Paste")
    assert not paste_act.isEnabled()

    viewer.nav_tree._run_action("hide", cover)
    assert "Phone/Housing:cover" in viewer._hidden_parts
    viewer.nav_tree._run_action("show", cover)
    assert "Phone/Housing:cover" not in viewer._hidden_parts

    viewer.nav_tree._run_action("hide_unselected", cover)
    assert "Phone/Housing:cover" not in viewer._hidden_parts
    assert "Phone/Battery:Cell" in viewer._hidden_parts
    viewer.nav_tree._run_action("show_all", cover)
    assert not viewer._hidden_parts

    viewer.nav_tree._run_action("copy", cover)
    assert viewer.nav_tree._clipboard[1] == "Phone/Housing:cover"
    viewer.nav_tree._run_action("paste", cover)
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "Phone/Housing:cover_copy" in names

    cell = _find_tree_item(viewer.nav_tree.tree, "Cell")
    viewer.nav_tree.tree.setCurrentItem(cell)
    viewer.nav_tree._run_action("delete", cell)
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "Phone/Battery:Cell" not in names
    assert "Phone/Housing:cover" in names


def test_cst_nav_hierarchy(viewer):
    from cst_panes import nest_solids, split_solid_path

    assert split_solid_path("Phone/Housing:cover") == (["Phone", "Housing"], "cover")
    nested = nest_solids([
        {"name": "Phone/Housing:cover"},
        {"name": "Phone/Antennas/WiFi_1:feed_WiFi1"},
    ])
    assert set(nested["Phone"]["children"]) == {"Housing", "Antennas"}

    data = {
        "components": [
            {"name": "Phone/Housing:cover", "material": "Plastic"},
            {"name": "Phone/Housing:radome", "material": "Vacuum"},
        ],
        "groups": [
            {"name": "Excluded from Simulation", "type": "",
             "items": ["Phone/Housing:radome"]},
            {"name": "AntennaMetals", "type": "mesh", "items": []},
        ],
        "materials": [
            {"name": "PEC", "folder": "", "colour": "0,0.5,0.75"},
            {"name": "Aluminum", "folder": "Phone", "colour": "0.75,0.75,0.75"},
        ],
        "ports": [], "monitors": [], "parameters": [],
    }
    viewer.nav_tree.populate_from_project(data)
    comps = viewer.nav_tree.tree.topLevelItem(0)
    phone = comps.child(0)
    assert phone.text(0) == "Phone"
    housing = phone.child(0)
    assert housing.text(0) == "Housing"
    leaves = {housing.child(i).text(0) for i in range(housing.childCount())}
    assert leaves == {"cover", "radome"}

    groups = next(
        viewer.nav_tree.tree.topLevelItem(i)
        for i in range(viewer.nav_tree.tree.topLevelItemCount())
        if viewer.nav_tree.tree.topLevelItem(i).text(0) == "Groups")
    assert [groups.child(i).text(0) for i in range(groups.childCount())] == [
        "Excluded from Simulation", "Excluded from Bounding Box", "Mesh Groups",
    ]
    assert groups.child(2).child(0).text(0) == "AntennaMetals"

    mats = next(
        viewer.nav_tree.tree.topLevelItem(i)
        for i in range(viewer.nav_tree.tree.topLevelItemCount())
        if viewer.nav_tree.tree.topLevelItem(i).text(0) == "Materials")
    mnames = [mats.child(i).text(0) for i in range(mats.childCount())]
    assert "Phone" in mnames and "PEC" in mnames
    phone_mat = next(mats.child(i) for i in range(mats.childCount())
                     if mats.child(i).text(0) == "Phone")
    assert phone_mat.child(0).text(0) == "Aluminum"


def test_drawing_mode(viewer):
    viewer._set_drawing_mode("Wireframe")
    assert viewer._drawing_mode == "Wireframe"
    viewer._set_drawing_mode("Shading")
    assert viewer._drawing_mode == "Shading"
    assert viewer.viewport._drawing_mode == "Shading"
    assert cst_gui.CST3DViewport.cad_edges_in_mode("Shading")
    assert cst_gui.CST3DViewport.cad_edges_in_mode("Transparent")
    assert cst_gui.CST3DViewport.cad_edges_in_mode("Wireframe")
    viewer._set_drawing_mode("BoundingBox")
    assert viewer._drawing_mode == "BoundingBox"
    assert viewer.viewport._drawing_mode == "BoundingBox"
    viewer._set_drawing_mode("Shading")
    viewer._on_slice()
    assert viewer.viewport._clip_axis == "x"
    viewer._on_slice()
    assert viewer.viewport._clip_axis == "y"
    viewer._on_slice()
    viewer._on_slice()
    assert viewer.viewport._clip_axis is None
    viewer._on_measure()
    assert viewer.viewport._measure_mode is True
    viewer._on_measure()
    assert viewer.viewport._measure_mode is False
    assert viewer.viewport._parallel is True


def test_result_plot_curve_and_empty(viewer):
    import struct
    from pathlib import Path

    mini = (
        "CST Farfield Format V1\n\nDimension = 2\nFrequency = 1e9\n"
        "Type = BISTATICRCS\n\n"
        "// = Theta Phi Re(E_Theta) Im(E_Theta) Re(E_Phi) Im(E_Phi)\n\n"
        "0\t0\t3\t4\t0\t0\n10\t0\t0\t5\t0\t0\n20\t0\t8\t6\t0\t0\n"
        "0\t90\t1\t0\t0\t0\n10\t90\t0\t1\t0\t0\n20\t90\t0\t0\t1\t0\n"
    )

    def pack_r1d(meta):
        def s(text):
            raw = (text or "").encode("latin-1") + b"\x00"
            return struct.pack("<i", len(raw)) + raw
        out = struct.pack("<ii", 3, 1) + s("2024|0|test") + s("2024|0|test")
        out += struct.pack("<i", len(meta))
        for k, v in meta.items():
            out += s(k) + s(v)
        out += struct.pack("<i", 0)
        return out

    viewer._archive = {}
    viewer._open_result({
        "name": "farfield_TOTAL1",
        "path": "Result/farfield_TOTAL1.dat",
        "bytes": mini.encode("ascii"),
    })
    assert viewer.result_plot.has_curve()
    assert viewer._view_stack.currentWidget() is viewer.result_plot
    assert len(viewer._result_rec.get("x") or []) >= 3
    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    csv_path = scratch / "m8_curve.csv"
    csv_path.write_text(viewer.result_plot.to_csv(), encoding="utf-8")
    assert "10" in csv_path.read_text(encoding="utf-8")
    png = viewer.result_plot.to_pixmap()
    assert not png.isNull()
    png_path = scratch / "m8_curve.png"
    png.save(str(png_path), "PNG")
    assert png_path.is_file() and png_path.stat().st_size > 20

    viewer._open_result({
        "name": "S1,1",
        "bytes": pack_r1d({"TemplateType": "1D", "labletext": "S1,1"}),
    })
    assert not viewer.result_plot.has_curve()
    viewer._show_result_kind("farfield")
    assert viewer._view_stack.currentWidget() is viewer.result_plot
    viewer._project_data = {
        "farfields": [{
            "name": "ff", "bytes": mini.encode("ascii"),
        }],
        "results_1d": [], "results_2d": [],
    }
    viewer._show_result_kind("farfield")
    assert viewer.result_plot.has_curve()
    viewer._show_viewport()
    assert viewer._view_stack.currentWidget() is viewer.viewport


PHONE_CST = r"D:\training\cst\CST Phone 5G.cst"


@pytest.mark.skipif(not os.path.exists(PHONE_CST), reason="phone.cst not present")
def test_phone_loads_distinct_solids(viewer):
    assert viewer._load_cst(PHONE_CST) is None
    comps = viewer._project_data.get("components", [])
    names = {c["name"] for c in comps}
    assert "Phone/Battery:Cell" in names
    assert "Phone/Camera:Lens" in names
    bboxes = {c["bounds"] for c in comps}
    assert len(comps) >= 100
    assert len(bboxes) > 20
    meshed = [c for c in comps if c.get("mesh", {}).get("faces")]
    assert len(meshed) >= 100
    lens = next(c for c in comps if c["name"] == "Phone/Camera:Lens")
    assert len(lens["mesh"]["faces"]) > 24
    battery = next(c for c in comps if c["name"] == "Phone/Battery:Cell")
    assert len(battery["mesh"]["faces"]) == 12
    tree = viewer.nav_tree.tree
    root = tree.topLevelItem(0)
    phone = next(root.child(i) for i in range(root.childCount())
                 if root.child(i).text(0) == "Phone")
    camera = next(phone.child(i) for i in range(phone.childCount())
                  if phone.child(i).text(0) == "Camera")
    assert any(camera.child(i).text(0) == "Lens"
               for i in range(camera.childCount()))


def test_new_project_save_roundtrip(viewer):
    from pathlib import Path
    from cst_parser import open_cst
    viewer._on_new()
    assert viewer._dirty
    assert "Model/3D/Model.mod" in viewer._archive
    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "created.cst"
    assert viewer._write_project(str(out)) is True
    assert viewer._dirty is False
    _meta, entries = open_cst(out)
    names = {e["name"].replace("\\", "/") for e in entries}
    assert "Model/3D/Model.mod" in names
    assert "Model/Parameters.json" in names


def test_parameter_edit_writeback_undo_save(viewer):
    import json
    from pathlib import Path
    from cst_parser import open_cst

    viewer._on_new()
    viewer._on_parameters_changed([
        {"name": "W", "expr": "12", "value": "", "description": "width"},
        {"name": "half", "expr": "W/2", "value": "", "description": ""},
    ])
    assert viewer._dirty
    recs = json.loads(viewer._archive["Model/Parameters.json"])["parameters"]
    by_name = {r["name"]: r for r in recs}
    assert by_name["W"]["expr"] == "12"
    assert by_name["half"]["value"] == "6"
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'MakeSureParameterExists "W", "12"' in mod
    assert 'MakeSureParameterExists "half", "W/2"' in mod
    assert viewer.param_list.table.rowCount() == 2

    viewer._on_undo()
    recs = json.loads(viewer._archive["Model/Parameters.json"])["parameters"]
    assert recs == []
    viewer._on_redo()
    recs = json.loads(viewer._archive["Model/Parameters.json"])["parameters"]
    assert recs[0]["name"] == "W"

    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "params_edit.cst"
    assert viewer._write_project(str(out)) is True
    _meta, entries = open_cst(out)
    by = {e["name"].replace("\\", "/"): e["content"] for e in entries}
    saved = json.loads(by["Model/Parameters.json"])["parameters"]
    assert saved[0]["expr"] == "12"
    assert b'MakeSureParameterExists "W", "12"' in by["Model/3D/Model.mod"]


def test_undo_delete_restores_solid(viewer):
    viewer._project_data = {
        "components": [
            {"name": "component1:box", "material": "PEC",
             "bounds": (-1, 1, -1, 1, 0, 1)},
        ],
        "materials": [], "groups": [], "parameters": [],
    }
    viewer._archive = dict(__import__("cst_parser").new_project_files())
    viewer._refresh_geometry()
    viewer._nav_delete("solid", "component1:box")
    assert viewer._project_data["components"] == []
    viewer._on_undo()
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "component1:box" in names


def test_add_brick_history_and_reopen(viewer):
    from pathlib import Path
    from cst_parser import open_cst

    viewer._on_new()
    viewer._add_shape("brick", {
        "name": "patch", "component": "component1", "material": "PEC",
        "xmin": "-2", "xmax": "2", "ymin": "-3", "ymax": "3",
        "zmin": "0", "zmax": "0.5",
    })
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "component1:patch" in names
    patch = viewer._find_component("component1:patch")
    assert patch["bounds"][0] == -2
    assert patch["bounds"][5] == 0.5
    assert patch["mesh"]["faces"]
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert "'@ define brick: component1:patch" in mod
    assert '.Name "patch"' in mod
    hist = viewer._archive["Model/3D/ModelHistory.json"].decode("utf-8")
    assert "define brick: component1:patch" in hist

    viewer._add_shape("cylinder", {
        "name": "via", "component": "component1", "material": "PEC",
        "radius": "1", "zmin": "0", "zmax": "4", "cx": "0", "cy": "0",
    })
    assert viewer._find_component("component1:via")
    viewer._add_shape("sphere", {
        "name": "ball", "component": "component1", "material": "Vacuum",
        "radius": "3", "cx": "0", "cy": "0", "cz": "0",
    })
    viewer._add_shape("torus", {
        "name": "ring", "component": "component1", "material": "PEC",
        "major": "6", "minor": "1", "cx": "0", "cy": "0", "cz": "0",
    })
    viewer._add_shape("cone", {
        "name": "tip", "component": "component1", "material": "PEC",
        "r_bottom": "2", "r_top": "0.2", "zmin": "0", "zmax": "5",
        "cx": "0", "cy": "0",
    })
    kinds = {c["name"].split(":")[-1] for c in viewer._project_data["components"]}
    assert kinds >= {"patch", "via", "ball", "ring", "tip"}

    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "shapes.cst"
    assert viewer._write_project(str(out)) is True
    other = __import__("cst_gui").CSTMainWindow(enable_3d=False)
    try:
        other._load_cst(str(out))
        names = {c["name"] for c in other._project_data["components"]}
        assert "component1:patch" in names
        assert "component1:via" in names
        assert "component1:ball" in names
        assert "component1:ring" in names
        assert "component1:tip" in names
        patch = other._find_component("component1:patch")
        assert patch["bounds"][0] == -2
        assert patch["bounds"][1] == 2
    finally:
        other.close()


def test_rename_delete_hide_writeback(viewer):
    from cst_parser import new_project_files, open_cst
    from pathlib import Path

    viewer._on_new()
    viewer._project_data["components"] = [
        {"name": "component1:box", "material": "PEC",
         "bounds": (-1, 1, -1, 1, 0, 1)},
    ]
    viewer._refresh_geometry()
    viewer._nav_rename("solid", "component1:box\ncomponent1:brick")
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Solid.Rename "component1:box", "component1:brick"' in mod
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "component1:brick" in names

    viewer._on_visibility("component1:brick", False)
    assert "component1:brick" in viewer._hidden_parts
    hid = viewer._archive["Model/3D/Model.hid"].decode("latin-1")
    assert "component1:brick" in hid

    viewer._nav_delete("solid", "component1:brick")
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Solid.Delete "component1:brick"' in mod

    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "nav_edit.cst"
    viewer._project_data["components"] = [
        {"name": "component1:keep", "material": "PEC",
         "bounds": (0, 1, 0, 1, 0, 1)},
    ]
    viewer._hidden_parts = {"component1:keep"}
    assert viewer._write_project(str(out)) is True
    _meta, entries = open_cst(out)
    by = {e["name"].replace("\\", "/"): e["content"] for e in entries}
    assert "component1:keep" in by["Model/3D/Model.hid"].decode("latin-1")


def test_drop_to_group_and_pick_sync(viewer):
    from cst_parser import new_project_files

    viewer._archive = dict(new_project_files())
    viewer._project_data = {
        "components": [
            {"name": "component1:box", "material": "PEC",
             "bounds": (-1, 1, -1, 1, 0, 1)},
        ],
        "groups": [],
        "materials": [],
        "parameters": [],
    }
    viewer._refresh_geometry()
    viewer._on_drop_to_group("component1:box", "Excluded from Simulation")
    groups = {g["name"]: g for g in viewer._project_data["groups"]}
    assert "component1:box" in groups["Excluded from Simulation"]["items"]
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Group.AddItem "solid$component1:box"' in mod

    assert viewer.nav_tree.select_by_name("component1:box")
    viewer.viewport.select_solid("component1:box")
    assert viewer.viewport._selected == "component1:box"
    if viewer.viewport._canvas:
        assert viewer.viewport._canvas._selected == "component1:box"

    viewer._on_property_changed("solid", "component1:box", "material", "Vacuum")
    box = viewer._find_component("component1:box")
    assert box["material"] == "Vacuum"
    assert 'Solid.ChangeMaterial "component1:box", "Vacuum"' in (
        viewer._archive["Model/3D/Model.mod"].decode("latin-1"))


def test_boolean_transform_material_component(viewer):
    from pathlib import Path
    from cst_parser import open_cst

    viewer._on_new()
    viewer._add_shape("brick", {
        "name": "base", "component": "component1", "material": "PEC",
        "xmin": "0", "xmax": "10", "ymin": "0", "ymax": "4",
        "zmin": "0", "zmax": "2",
    })
    viewer._add_shape("brick", {
        "name": "cut", "component": "component1", "material": "PEC",
        "xmin": "4", "xmax": "12", "ymin": "1", "ymax": "3",
        "zmin": "-1", "zmax": "3",
    })
    viewer._apply_boolean("subtract", "component1:base", "component1:cut")
    names = {c["name"] for c in viewer._project_data["components"]}
    assert "component1:base" in names
    assert "component1:cut" not in names
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Solid.Subtract "component1:base", "component1:cut"' in mod

    viewer._apply_boolean("add", "component1:base", "component1:base")
    # rejected same solid; still one base
    assert len([c for c in viewer._project_data["components"]
                if c["name"] == "component1:base"]) == 1

    viewer._add_shape("brick", {
        "name": "tool", "component": "component1", "material": "PEC",
        "xmin": "8", "xmax": "14", "ymin": "0", "ymax": "4",
        "zmin": "0", "zmax": "2",
    })
    viewer._apply_boolean("add", "component1:base", "component1:tool")
    base = viewer._find_component("component1:base")
    assert base["bounds"][1] >= 14
    assert viewer._find_component("component1:tool") is None

    before = base["bounds"][0]
    viewer._apply_transform("translate", {
        "name": "component1:base", "dx": "5", "dy": "0", "dz": "0",
    })
    assert viewer._find_component("component1:base")["bounds"][0] == before + 5
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Transform "Shape", "Translate"' in mod

    viewer._add_material({
        "name": "FR4", "epsilon": "4.3", "mu": "1.0", "kappa": "0.0",
        "tand": "0.025", "colour": "0.9,0.6,0.2", "folder": "",
    })
    mats = {m["name"] for m in viewer._project_data["materials"]}
    assert "FR4" in mats
    assert '.Epsilon "4.3"' in viewer._archive["Model/3D/Model.mod"].decode("latin-1")

    viewer._add_component("antenna")
    assert "antenna" in viewer._component_folders()
    viewer._nav_delete("collection", "antenna")
    assert "antenna" not in viewer._project_data.get("empty_components", [])
    assert 'Component.Delete "antenna"' in viewer._archive["Model/3D/Model.mod"].decode("latin-1")

    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "bool_xfrm.cst"
    assert viewer._write_project(str(out)) is True
    other = __import__("cst_gui").CSTMainWindow(enable_3d=False)
    try:
        other._load_cst(str(out))
        names = {c["name"] for c in other._project_data["components"]}
        assert "component1:cut" not in names
        assert "component1:tool" not in names
        assert "component1:base" in names
        mats = {m["name"] for m in other._project_data["materials"]}
        assert "FR4" in mats
        # translate + add applied on parse
        base = other._find_component("component1:base")
        assert base["bounds"][0] >= 5
        assert base["bounds"][1] >= 19
    finally:
        other.close()


def test_discrete_port_monitor_probe_roundtrip(viewer):
    from pathlib import Path

    viewer._on_new()
    viewer._add_discrete_port({
        "port_number": "1", "impedance": "50.0", "label": "",
        "x1": "0", "y1": "0.5", "z1": "0",
        "x2": "0", "y2": "-0.5", "z2": "0",
        "ptype": "SParameter",
    })
    port = viewer._find_named("ports", "port1")
    assert port is not None
    assert port["impedance"] == "50.0"
    assert port["p1"] == ("0", "0.5", "0")
    assert port["p2"] == ("0", "-0.5", "0")
    assert port["p1_xyz"] == (0.0, 0.5, 0.0)
    assert port["p2_xyz"] == (0.0, -0.5, 0.0)
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert '.SetP1 "False", "0", "0.5", "0"' in mod
    assert '.SetP2 "False", "0", "-0.5", "0"' in mod
    assert '.Impedance "50.0"' in mod
    labels = [viewer.nav_tree.tree.topLevelItem(i).text(0)
              for i in range(viewer.nav_tree.tree.topLevelItemCount())]
    assert "Ports" in labels
    ports_node = next(
        viewer.nav_tree.tree.topLevelItem(i)
        for i in range(viewer.nav_tree.tree.topLevelItemCount())
        if viewer.nav_tree.tree.topLevelItem(i).text(0) == "Ports")
    assert ports_node.childCount() == 1
    assert ports_node.child(0).text(0) == "port1"

    viewer._add_monitor({
        "name": "e-field (f=2.45)", "field_type": "Efield",
        "frequency": "2.45", "domain": "Frequency", "dimension": "Volume",
    })
    viewer._add_monitor({
        "name": "h-field (f=2.45)", "field_type": "Hfield",
        "frequency": "2.45", "domain": "Frequency", "dimension": "Volume",
    })
    viewer._add_monitor({
        "name": "farfield (f=3.5)", "field_type": "Farfield",
        "frequency": "3.5", "domain": "Frequency", "dimension": "Volume",
    })
    viewer._add_probe({
        "name": "probe1", "field_name": "efield",
        "x": "0", "y": "0", "z": "1", "orientation": "Z",
    })
    mons = {m["name"]: m for m in viewer._project_data["monitors"]}
    assert mons["e-field (f=2.45)"]["field_type"] == "Efield"
    assert mons["h-field (f=2.45)"]["field_type"] == "Hfield"
    assert mons["farfield (f=3.5)"]["field_type"] == "Farfield"
    assert mons["farfield (f=3.5)"]["frequency"] == "3.5"
    assert viewer._find_named("probes", "probe1")["xyz"][2] == 1.0
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert '.FieldType "Farfield"' in mod
    assert '.FieldName "efield"' in mod

    viewer._project_data["parameters"] = [
        {"name": "x0", "expr": "5", "value": "5", "description": ""},
        {"name": "y0", "expr": "2", "value": "2", "description": ""},
        {"name": "h", "expr": "1.6", "value": "1.6", "description": ""},
    ]
    viewer._add_discrete_port({
        "port_number": "2", "impedance": "50", "label": "",
        "x1": "x0", "y1": "y0", "z1": "0.0",
        "x2": "x0", "y2": "y0", "z2": "-h",
        "ptype": "SParameter",
    })
    micro = viewer._find_named("ports", "port2")
    assert micro["p1"] == ("x0", "y0", "0.0")
    assert micro["p2"] == ("x0", "y0", "-h")
    assert micro["p1_xyz"] == (5.0, 2.0, 0.0)
    assert abs(micro["p2_xyz"][2] + 1.6) < 1e-9

    viewer._on_property_changed("port", "port1", "impedance", "75")
    assert viewer._find_named("ports", "port1")["impedance"] == "75"
    viewer._on_property_changed("port", "port1", "y1", "1")
    assert viewer._find_named("ports", "port1")["p1"][1] == "1"
    assert viewer._find_named("ports", "port1")["p1_xyz"][1] == 1.0

    viewer._nav_delete("port", "port1")
    names = {p["name"] for p in viewer._project_data["ports"]}
    assert "port1" not in names
    assert "port2" in names
    mod = viewer._archive["Model/3D/Model.mod"].decode("latin-1")
    assert 'Port.Delete "1"' in mod

    scratch = Path(__file__).resolve().parent / "_scratch"
    scratch.mkdir(exist_ok=True)
    out = scratch / "ports_m6.cst"
    assert viewer._write_project(str(out)) is True
    other = __import__("cst_gui").CSTMainWindow(enable_3d=False)
    try:
        other._load_cst(str(out))
        names = {p["name"] for p in other._project_data["ports"]}
        assert "port1" not in names
        p2 = other._find_named("ports", "port2")
        assert p2 is not None
        assert p2["impedance"] == "50"
        assert p2["p1"] == ("x0", "y0", "0.0")
        assert p2["p2"] == ("x0", "y0", "-h")
        assert p2["p1_xyz"] == (5.0, 2.0, 0.0)
        assert abs(p2["p2_xyz"][2] + 1.6) < 1e-9
        mons = {m["name"]: m for m in other._project_data["monitors"]}
        assert mons["e-field (f=2.45)"]["field_type"] == "Efield"
        assert mons["farfield (f=3.5)"]["frequency"] == "3.5"
        probe = other._find_named("probes", "probe1")
        assert probe["xyz"][2] == 1.0
        assert probe["orientation"] == "Z"
    finally:
        other.close()
