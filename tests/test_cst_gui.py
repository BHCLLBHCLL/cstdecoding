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
    assert viewer.viewport._parallel is True


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
