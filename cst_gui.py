# -*- coding: utf-8 -*-
"""cst_gui.py — CST 项目查看器与编辑器（非求解器）。

Chrome 对齐 CST DESIGN ENVIRONMENT；文件格式由 cst_parser / sab_bodies 读写。

Usage:
    python cst_gui.py
    python cst_gui.py phone.cst
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import traceback

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QFrame, QGroupBox, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QSplitter, QStackedWidget, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from cst_parser import (
    CstParseError, open_cst, write_cst, new_project_files, read_entry,
)
from cst_project import (
    UndoStack, append_change_material, append_component_delete,
    append_component_new, append_group_item, append_history, history_code,
    history_entry, load_history, write_history,
    append_solid_delete, append_solid_rename, archive_get, boolean_vba,
    bounds_center, box_mesh, brick_vba, cone_mesh, cone_vba, cylinder_mesh,
    cylinder_vba, discrete_port_vba, eval_expr, eval_excitations, eval_point,
    intersect_bounds, material_vba, merge_meshes, mesh_bounds,
    mirror_fn, monitor_vba, next_port_number, parse_hidden_solids,
    parse_set_point, probe_vba, resolve_parameters, rotate_fn, scale_fn,
    snapshot_state, sphere_mesh, sphere_vba, torus_mesh, torus_vba,
    transform_component, transform_mirror_vba, transform_rotate_vba,
    transform_scale_vba, transform_translate_vba, translate_fn, union_bounds,
    unique_solid_name, waveguide_port_vba, write_hidden, write_parameters,
)
from cst_dialogs import (
    boolean_dialog, component_dialog, discrete_port_dialog,
    history_list_dialog, material_dialog,
    monitor_dialog, probe_dialog, shape_dialog, transform_dialog,
    mesh_properties_dialog, units_dialog, waveguide_port_dialog,
)
from cst_icons import AppIcons
from cst_panes import (
    CST3DCanvas, CST3DViewport, FULLNAME_ROLE, KIND_ROLE, MessageWindow,
    NavigationTree, PAYLOAD_ROLE, PaneFrame, ParameterList, ProgressPanel,
    PropertyInspector, QuadView, ResultPlot, split_solid_path,
)
from cst_results import (
    parse_result_bytes, result_has_curve, result_has_grid,
)
from sab_bodies import extract_bodies, opacity_for

# Re-export for tests / `from cst_gui import AppIcons`
__all__ = [
    "CSTMainWindow", "AppIcons", "PaneFrame", "MessageWindow",
    "NavigationTree", "ParameterList", "ProgressPanel", "CST3DViewport",
    "CST3DCanvas", "PropertyInspector", "QuadView", "ResultPlot",
]


# Ribbon groups reconstructed from CST DESIGN ENVIRONMENT_AMD64.exe command IDs
# (DE_File / DE_Misc / 3D_Modeling_* / 3D_Simulation_* / Plot_Results_*).
RIBBON_TABS = (
    "Home", "Modeling", "Simulation", "Post-Processing", "View", "Macros", "Help",
)

SOLVER_TIP = "本产品不含求解器"


class CSTMainWindow(QMainWindow):
    """Main window: load / browse a CST .cst project in DESIGN ENVIRONMENT layout."""

    def __init__(self, path: str | None = None, enable_3d: bool = True):
        super().__init__()
        self.setWindowTitle("CST Studio Suite 2024")
        self.setWindowIcon(AppIcons.get("component", 32))
        self.resize(1400, 900)
        self._enable_3d = enable_3d
        self._project_data: dict = {}
        self._current_path: str | None = None
        self._archive: dict[str, bytes] = {}
        self._eocd_comment: bytes = b""
        self._dirty = False
        self._recent: list[str] = []
        self._hidden_parts: set[str] = set()
        self._drawing_mode = "Shading"
        self._ribbon_minimized = False
        self._undo = UndoStack()
        self._restoring = False
        self._selected_solid = ""
        self._result_rec: dict = {}
        self._quad_mode = False
        self._cad_edges = True
        self._mesh_prev = "Shading"
        self._wcs_mode = "global"
        self._last_view_pixmap = None
        self._solver_ribbon_buttons: list = []
        self._build_ui()
        self._apply_style()
        if path:
            QTimer.singleShot(0, lambda: self._load_cst(path))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self._create_actions()
        self._create_ribbon()
        self._create_central()
        self._create_statusbar()

    def _create_actions(self) -> None:
        def act(text, slot, shortcut=None, icon=None):
            a = QAction(text, self)
            if icon:
                a.setIcon(AppIcons.get(icon, 20))
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            self.addAction(a)
            return a

        self.act_open = act("&Open…", self._on_open, QKeySequence.Open, "open")
        self.act_new = act("&New", self._on_new, QKeySequence.New, "new")
        self.act_save = act("&Save", self._on_save, QKeySequence.Save, "save")
        self.act_save_as = act("Save &As…", self._on_save_as,
                               QKeySequence("Ctrl+Shift+S"), "save")
        self.act_import = act("&Import SAT…", self._on_import, None, "open")
        self.act_export = act("&Export SAT…", self._on_export, None, "export")
        self.act_exit = act("E&xit", self.close, QKeySequence.Quit)
        self.act_undo = act("&Undo", self._on_undo, QKeySequence.Undo, "undo")
        self.act_redo = act("&Redo", self._on_redo, QKeySequence.Redo, "redo")
        self.act_fit = act("&Fit", self._on_fit, "F", "fit")
        self.act_about = act("&About CST GUI", self._on_about, None, "help")

    def _create_ribbon(self) -> None:
        """Qtitan-style ribbon: Quick Access + File button + contextual tabs."""
        host = QWidget()
        host.setObjectName("RibbonHost")
        root = QVBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        qat = QFrame()
        qat.setObjectName("QuickAccess")
        qat.setFixedHeight(30)
        qat_l = QHBoxLayout(qat)
        qat_l.setContentsMargins(6, 2, 6, 2)
        qat_l.setSpacing(3)
        for action in (self.act_open, self.act_save, self.act_undo, self.act_redo):
            btn = QToolButton()
            btn.setDefaultAction(action)
            btn.setAutoRaise(True)
            btn.setIconSize(QSize(20, 20))
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            qat_l.addWidget(btn)
        qat_l.addStretch(1)
        title = QLabel("CST Studio Suite 2024")
        title.setObjectName("QatTitle")
        qat_l.addWidget(title)
        qat_l.addStretch(1)
        root.addWidget(qat)

        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(0)

        self._file_btn = QToolButton()
        self._file_btn.setObjectName("FileButton")
        self._file_btn.setText("FILE")
        self._file_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._file_btn.setPopupMode(QToolButton.InstantPopup)
        self._file_btn.setFixedWidth(72)
        self._file_menu = QMenu(self._file_btn)
        self._file_menu.addAction(self.act_new)
        self._file_menu.addAction(self.act_open)
        self._file_menu.addAction(self.act_save)
        self._file_menu.addAction(self.act_save_as)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self.act_import)
        self._file_menu.addAction(self.act_export)
        self._file_menu.addSeparator()
        self._recent_menu = self._file_menu.addMenu("Recent Files")
        self._rebuild_recent_menu()
        self._file_menu.addSeparator()
        self._file_menu.addAction(self.act_exit)
        self._file_btn.setMenu(self._file_menu)
        row_l.addWidget(self._file_btn, 0, Qt.AlignTop)

        self._ribbon_tabs = QTabWidget()
        self._ribbon_tabs.setObjectName("RibbonTabs")
        self._ribbon_tabs.setDocumentMode(True)
        self._ribbon_tabs.addTab(self._build_home_tab(), "Home")
        self._ribbon_tabs.addTab(self._build_modeling_tab(), "Modeling")
        self._ribbon_tabs.addTab(self._build_simulation_tab(), "Simulation")
        self._ribbon_tabs.addTab(self._build_post_tab(), "Post-Processing")
        self._ribbon_tabs.addTab(self._build_view_tab(), "View")
        self._ribbon_tabs.addTab(self._build_macros_tab(), "Macros")
        self._ribbon_tabs.addTab(self._build_help_tab(), "Help")
        row_l.addWidget(self._ribbon_tabs, 1)

        min_btn = QToolButton()
        min_btn.setObjectName("RibbonMinimize")
        min_btn.setText("▴")
        min_btn.setToolTip("Minimize the Ribbon")
        min_btn.setAutoRaise(True)
        min_btn.clicked.connect(self._toggle_ribbon)
        row_l.addWidget(min_btn, 0, Qt.AlignTop)
        root.addWidget(row)

        self.setMenuWidget(host)
        self._ribbon_host = host
        self._ribbon_content_height = 88

    def _make_ribbon_button(self, text, icon_name, slot=None, big=False,
                            enabled=True, tooltip=""):
        b = QToolButton()
        b.setObjectName("RibbonButton")
        size = 24
        b.setIcon(AppIcons.get(icon_name, size))
        b.setIconSize(QSize(size, size))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setText(text)
        b.setAutoRaise(True)
        b.setFixedHeight(56)
        b.setMinimumWidth(52 if big else 48)
        if tooltip:
            b.setToolTip(tooltip)
        if not enabled:
            b.setEnabled(False)
            b.setToolTip(tooltip or SOLVER_TIP)
            self._solver_ribbon_buttons.append(b)
        elif slot:
            b.clicked.connect(lambda _checked=False, s=slot: s())
        return b

    def _make_ribbon_group(self, title, buttons, *, big_first=False):
        box = QGroupBox(title)
        box.setObjectName("RibbonGroup")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(3, 1, 3, 6)
        bl.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)
        for i, item in enumerate(buttons):
            extra = {}
            if len(item) == 4:
                text, icon, slot, extra = item
            else:
                text, icon, slot = item
            extra = extra or {}
            row.addWidget(self._make_ribbon_button(
                text, icon, slot, big=big_first and i == 0,
                enabled=extra.get("enabled", True),
                tooltip=extra.get("tooltip", "")))
        row.addStretch(1)
        bl.addLayout(row)
        return box

    def _solver_btn(self):
        return {"enabled": False, "tooltip": SOLVER_TIP}

    def _nyi_slot(self, name: str):
        return lambda _=False, n=name: self._nyi(n)

    def _build_home_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        # DE_Misc Paste / Cut / Copy / CopyView
        layout.addWidget(self._make_ribbon_group("Clipboard", [
            ("Paste", "paste", self._on_paste),
            ("Cut", "cut", self._on_cut),
            ("Copy", "copy", self._on_copy),
            ("Copy View", "screenshot", self._on_copy_view),
        ], big_first=True))
        layout.addWidget(self._make_ribbon_group("Settings", [
            ("Units", "units", lambda: self._on_units()),
            ("Background", "background", self._on_background),
            ("Frequency", "frequency", lambda: self._on_units()),
            ("Boundaries", "boundary", self._on_boundaries),
        ]))
        layout.addWidget(self._make_ribbon_group("Simulation", [
            ("Setup\nSolver", "setup", None, self._solver_btn()),
            ("Start", "start", None, self._solver_btn()),
            ("Pause", "pause", None, self._solver_btn()),
            ("Abort", "stop", None, self._solver_btn()),
        ], big_first=True))
        layout.addWidget(self._make_ribbon_group("Mesh", [
            ("Update", "mesh", None, self._solver_btn()),
            ("Mesh View", "mesh", self._on_mesh_view),
            ("Global\nProperties", "editprops",
             lambda: self._on_mesh_properties(interactive=self._want_dialogs())),
            ("Local\nProperties", "list",
             lambda: self._on_mesh_properties(interactive=self._want_dialogs())),
        ]))
        layout.addWidget(self._make_ribbon_group("Edit", [
            ("Properties", "editprops", self._on_edit_properties),
            ("History List", "history",
             lambda: self._on_history_list(interactive=self._want_dialogs())),
            ("Delete", "delete", self._on_delete),
        ]))
        layout.addWidget(self._make_ribbon_group("Parameters", [
            ("Parameter\nList", "list", self._show_parameter_list),
            ("Parametric\nSweep", "parametric", None, self._solver_btn()),
            ("Optimizer", "optimizer", None, self._solver_btn()),
        ]))
        layout.addWidget(self._make_ribbon_group("Report", [
            ("Open\nReport", "report", self._on_open_report),
        ]))
        layout.addStretch(1)
        return w

    def _build_modeling_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        # 3D_Modeling_Shape Brick / Cylinder / Sphere / Torus / ECylinder
        layout.addWidget(self._make_ribbon_group("Shapes", [
            ("Brick", "brick", lambda: self._on_shape("brick")),
            ("Cylinder", "cylinder", lambda: self._on_shape("cylinder")),
            ("Sphere", "sphere", lambda: self._on_shape("sphere")),
            ("Torus", "torus", lambda: self._on_shape("torus")),
            ("Cone", "cone", lambda: self._on_shape("cone")),
        ], big_first=True))
        # 3D_Modeling_Shape BooleanAdd / BooleanSubtract / BooleanInsert
        layout.addWidget(self._make_ribbon_group("Boolean", [
            ("Add", "union", lambda: self._on_boolean("add")),
            ("Subtract", "subtract", lambda: self._on_boolean("subtract")),
            ("Intersect", "intersect", lambda: self._on_boolean("intersect")),
        ]))
        # 3D_Modeling_Shape Transform / Align
        layout.addWidget(self._make_ribbon_group("Transform", [
            ("Transform", "translate", lambda: self._on_transform("translate")),
            ("Rotate", "rotate", lambda: self._on_transform("rotate")),
            ("Mirror", "mirror", lambda: self._on_transform("mirror")),
            ("Scale", "scale", lambda: self._on_transform("scale")),
        ]))
        # 3D_Modeling_WCS Align / AlignGlobal
        layout.addWidget(self._make_ribbon_group("WCS", [
            ("Local WCS", "wcs", lambda: self._on_wcs("local")),
            ("Align Global", "wcs", lambda: self._on_wcs("global")),
        ]))
        layout.addWidget(self._make_ribbon_group("Materials", [
            ("New", "material", lambda: self._on_new_material()),
            ("Library", "material", self._on_material_library),
        ]))
        # Discrete / Waveguide ports live under simulation but are modeled here
        layout.addWidget(self._make_ribbon_group("Ports", [
            ("Discrete", "ports", lambda: self._on_discrete_port()),
            ("Waveguide", "ports", lambda: self._on_waveguide_port()),
        ]))
        layout.addStretch(1)
        return w

    def _build_simulation_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.addWidget(self._make_ribbon_group("Solver", [
            ("Frequency\nDomain", "setup", None, self._solver_btn()),
            ("Time\nDomain", "setup", None, self._solver_btn()),
            ("Eigenmode", "setup", None, self._solver_btn()),
            ("Integral\nEquation", "setup", None, self._solver_btn()),
        ]))
        layout.addWidget(self._make_ribbon_group("Sources", [
            ("Field\nSource", "sources", lambda: self._on_source("field")),
            ("Plane\nWave", "sources", lambda: self._on_source("plane_wave")),
            ("Farfield\nSource", "farfield", lambda: self._on_source("farfield")),
        ]))
        layout.addWidget(self._make_ribbon_group("Monitors", [
            ("Field", "monitor", lambda: self._on_field_monitor()),
            ("Probe", "probe", lambda: self._on_probe()),
            ("S-Parameters", "1d", lambda: self._show_result_kind("result_1d")),
        ]))
        layout.addWidget(self._make_ribbon_group("Run", [
            ("Start", "start", None, self._solver_btn()),
            ("Sweep", "parametric", None, self._solver_btn()),
        ], big_first=True))
        layout.addStretch(1)
        return w

    def _build_post_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        # Plot_Results_Plot 1D / Field Farfield
        layout.addWidget(self._make_ribbon_group("Results", [
            ("1D Plot", "1d", lambda: self._show_result_kind("result_1d")),
            ("2D/3D", "2d", lambda: self._show_result_kind("result_2d")),
            ("Farfield", "farfield", lambda: self._show_result_kind("farfield")),
            ("Smith", "1d", self._on_smith),
        ]))
        layout.addWidget(self._make_ribbon_group("Field", [
            ("On Face", "faces", lambda: self._on_field_sample("face")),
            ("On Curve", "curves", lambda: self._on_field_sample("curve")),
        ]))
        layout.addWidget(self._make_ribbon_group("Image", [
            ("Export", "export", lambda: self._on_export_plot()),
            ("Copy View", "screenshot", self._on_copy_view),
        ]))
        layout.addStretch(1)
        return w

    def _build_view_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        # Plot_Results_View Front / Left / Perspective / ResetView / Wireframe
        layout.addWidget(self._make_ribbon_group("Views", [
            ("Fit", "fit", self._on_fit),
            ("Front", "front", lambda: self._set_plane("yz")),
            ("Top", "top", lambda: self._set_plane("xy")),
            ("Side", "side", lambda: self._set_plane("xz")),
            ("Perspective", "perspective", self._on_perspective),
        ]))
        layout.addWidget(self._make_ribbon_group("Display", [
            ("Wireframe", "wireframe", lambda: self._set_drawing_mode("Wireframe")),
            ("Shading", "faces", lambda: self._set_drawing_mode("Shading")),
            ("Transparent", "component", lambda: self._set_drawing_mode("Transparent")),
            ("Bounding Box", "bounding", lambda: self._set_drawing_mode("BoundingBox")),
        ]))
        layout.addWidget(self._make_ribbon_group("Tools", [
            ("Slice", "slice", lambda: self._on_slice()),
            ("Measure", "dimensions", lambda: self._on_measure()),
            ("CAD Edges", "wireframe", self._on_toggle_edges),
            ("Quad View", "perspective", self._on_quad_view),
        ]))
        layout.addWidget(self._make_ribbon_group("Windows", [
            ("Navigation", "list", lambda: self._toggle_pane("nav")),
            ("Properties", "editprops", lambda: self._toggle_pane("props")),
            ("Messages", "logfile", lambda: self._toggle_pane("msg")),
            ("Parameters", "parametric", lambda: self._toggle_pane("params")),
        ]))
        layout.addStretch(1)
        return w

    def _build_macros_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._make_ribbon_group("Macros", [
            ("VBA", "macros", lambda: self._on_macro("vba")),
            ("Python", "python", lambda: self._on_macro("python")),
        ], big_first=True))
        layout.addStretch(1)
        return w

    def _build_help_tab(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        # DE_Misc Help / DE_Document GettingStarted / Videos / Tutorials
        layout.addWidget(self._make_ribbon_group("Help", [
            ("Help", "help", self._on_about),
            ("Getting\nStarted", "help", lambda: self._on_help_topic("started")),
            ("Videos", "help", lambda: self._on_help_topic("videos")),
            ("Tutorials", "help", lambda: self._on_help_topic("tutorials")),
        ]))
        layout.addStretch(1)
        return w

    def _create_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        self.nav_tree = NavigationTree()
        self.nav_tree.item_selected.connect(self._on_nav_selected)
        self.nav_tree.visibility_changed.connect(self._on_visibility)
        self.nav_tree.context_action.connect(self._on_nav_context)
        self.nav_tree.solid_dropped_on_group.connect(self._on_drop_to_group)
        self.nav_pane = PaneFrame("Navigation Tree", self.nav_tree)

        self.properties = PropertyInspector()
        self.properties.property_changed.connect(self._on_property_changed)
        self.prop_pane = PaneFrame("Properties", self.properties)

        left = QSplitter(Qt.Vertical)
        left.addWidget(self.nav_pane)
        left.addWidget(self.prop_pane)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 1)
        left.setSizes([520, 200])
        self._left_split = left

        self.viewport = CST3DViewport(enable_3d=self._enable_3d)
        self.viewport.solid_picked.connect(self._on_solid_picked)
        self.viewport.status_coords.connect(self._on_pick_coords)
        self.result_plot = ResultPlot()
        self.quad_view = QuadView()
        self._view_stack = QStackedWidget()
        # CST 3D view has no pane caption; keep a thin frame only
        view_host = QFrame()
        view_host.setObjectName("ViewportFrame")
        vh = QVBoxLayout(view_host)
        vh.setContentsMargins(0, 0, 0, 0)
        self._view_stack.addWidget(self.viewport)
        self._view_stack.addWidget(self.result_plot)
        self._view_stack.addWidget(self.quad_view)
        vh.addWidget(self._view_stack)

        self.message_win = MessageWindow()
        self.msg_pane = PaneFrame("Messages", self.message_win)

        right = QSplitter(Qt.Vertical)
        right.addWidget(view_host)
        right.addWidget(self.msg_pane)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)
        right.setSizes([640, 140])
        self._right_split = right

        hsplit = QSplitter(Qt.Horizontal)
        hsplit.addWidget(left)
        hsplit.addWidget(right)
        hsplit.setStretchFactor(0, 0)
        hsplit.setStretchFactor(1, 1)
        hsplit.setSizes([280, 1120])
        self._hsplit = hsplit

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("BottomTabs")
        self.param_list = ParameterList()
        self.param_list.parameters_changed.connect(self._on_parameters_changed)
        self.progress_panel = ProgressPanel()
        self.bottom_tabs.addTab(self.param_list, "Parameter List")
        self.bottom_tabs.addTab(self.progress_panel, "Progress")
        self._param_pane = PaneFrame("Parameter List", self.bottom_tabs)

        vsplit = QSplitter(Qt.Vertical)
        vsplit.addWidget(hsplit)
        vsplit.addWidget(self._param_pane)
        vsplit.setStretchFactor(0, 1)
        vsplit.setStretchFactor(1, 0)
        vsplit.setSizes([620, 180])
        self._vsplit = vsplit

        main_layout.addWidget(vsplit, 1)
        self.message_win.info("CST GUI initialized. Ready to load .cst files.")

        # aliases used by older test_gui.py
        self._param_list = self.param_list
        self._progress_panel = self.progress_panel

    def _create_statusbar(self) -> None:
        sb = self.statusBar()
        self._status_label = QLabel("Ready")
        self._status_xy = QLabel("( —, —, — )")
        self._status_mode = QLabel("Selection: Shape")
        self._status_units = QLabel("Units: mm  GHz  ns  K")
        self._status_dim = QLabel("Normal")
        self._status_progress = QProgressBar()
        self._status_progress.setMaximumWidth(180)
        self._status_progress.setVisible(False)
        self._status_progress.setTextVisible(True)
        self._status_progress.setFormat("%p%")
        sb.addWidget(self._status_label, 1)
        sb.addWidget(self._status_xy)
        sb.addWidget(self._status_progress)
        sb.addPermanentWidget(self._status_mode)
        sb.addPermanentWidget(self._status_units)
        sb.addPermanentWidget(self._status_dim)
        self.status = sb
        sb.showMessage("No project")

    def _apply_style(self) -> None:
        # Object-name selectors (#PaneFrame) match cabdecoding; File orange
        # matches CST DESIGN ENVIRONMENT / Qtitan Ribbon File button.
        self.setStyleSheet("""
            QMainWindow { background: #d5d9df; }
            #RibbonHost { background: #e2e5ea; }
            #QuickAccess {
                background: #cfd4da;
                border-bottom: 1px solid #a8b0b8;
            }
            #QatTitle { color: #333; font-size: 11px; }
            #FileButton {
                background: #e64a19;
                color: #fff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 10px;
                border: none;
                min-height: 28px;
            }
            #FileButton:hover { background: #c43c12; }
            #FileButton::menu-indicator { image: none; }
            #RibbonTabs::pane {
                border: none;
                background: #e6e9ee;
                border-bottom: 1px solid #a8b0b8;
            }
            #RibbonTabs > QTabBar::tab {
                padding: 6px 16px;
                margin-right: 1px;
                background: #d5d9df;
                color: #1a1a1a;
                border: 1px solid transparent;
            }
            #RibbonTabs > QTabBar::tab:selected {
                background: #e6e9ee;
                border: 1px solid #a8b0b8;
                border-bottom: 1px solid #e6e9ee;
            }
            #RibbonTabs > QTabBar::tab:hover:!selected { background: #c5ced8; }
            QGroupBox#RibbonGroup {
                border: 1px solid #b4bcc4;
                border-top: none;
                border-bottom: none;
                margin: 0px 2px 6px 2px;
                padding: 1px 2px 0px 2px;
                background: transparent;
                font-size: 10px;
            }
            QGroupBox#RibbonGroup::title {
                subcontrol-origin: margin;
                subcontrol-position: bottom center;
                padding: 0 4px;
                color: #444;
            }
            QToolButton#RibbonButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 1px 3px 0px 3px;
                color: #222;
                font-size: 10px;
            }
            QToolButton#RibbonButton:hover {
                background: #c5d8ec;
                border: 1px solid #7e9fc0;
            }
            QToolButton#RibbonButton:pressed { background: #9ec0e0; }
            #PaneFrame, #PaneBody {
                background: #f4f5f7;
                border: 1px solid #8e969e;
            }
            #PaneBody { border: none; background: #f4f5f7; }
            #PaneTitleBar {
                background: #c5c9ce;
                border-bottom: 1px solid #8e969e;
            }
            #PaneTitle { font-weight: bold; color: #222; font-size: 11px; }
            #ViewportFrame { background: #9aa7b3; border: 1px solid #6d7882; }
            QTreeWidget {
                border: none; background: #eceef1; font-size: 11px;
                font-family: "Segoe UI", sans-serif; outline: none;
            }
            QTreeWidget::item { padding: 1px 2px; min-height: 18px; }
            QTreeWidget::item:selected { background: #d0d0d0; color: #111; }
            QTreeWidget::item:hover { background: #e4e4e4; }
            QLineEdit {
                border: 1px solid #8e969e; border-radius: 2px;
                padding: 3px 6px; background: #f4f5f7;
            }
            QTabWidget::pane { border: 1px solid #8e969e; background: #eceef1; }
            QTabBar::tab {
                padding: 5px 12px; border: 1px solid #8e969e;
                border-bottom: none; background: #d5d9df; margin-right: 1px;
            }
            QTabBar::tab:selected { background: #eceef1; }
            QTableWidget {
                gridline-color: #c5c9ce; font-size: 11px; border: none;
                background: #eceef1;
                alternate-background-color: #e2e5ea;
            }
            QHeaderView::section {
                background: #6e6e6e; padding: 4px; color: #fff;
                border: 1px solid #5a5a5a; font-weight: bold; font-size: 11px;
            }
            QPlainTextEdit, QTextEdit {
                border: none; background: #eceef1;
                font-family: Consolas, Monaco, monospace; font-size: 11px;
            }
            QSplitter::handle { background: #a8b0b8; }
            QSplitter::handle:horizontal { width: 3px; }
            QSplitter::handle:vertical { height: 3px; }
            QStatusBar { background: #cfd4da; border-top: 1px solid #a8b0b8; }
            QStatusBar QLabel { color: #333; padding: 0 8px; }
            QMenu { background: #f0f0f0; border: 1px solid #a0a0a0; padding: 2px; }
            QMenu::item { padding: 4px 28px 4px 8px; min-height: 18px; }
            QMenu::item:selected { background: #0078d7; color: white; }
            QMenu::item:disabled { color: #a0a0a0; }
            QMenu::separator { height: 1px; background: #c8c8c8; margin: 4px 10px; }
            QMenu::icon { padding-left: 4px; }
        """)

    # ------------------------------------------------------------------ ribbon helpers

    def _toggle_ribbon(self) -> None:
        self._ribbon_minimized = not self._ribbon_minimized
        stack = self._ribbon_tabs.findChild(QStackedWidget)
        if stack is not None:
            stack.setVisible(not self._ribbon_minimized)
        self.message_win.info(
            "Ribbon minimized." if self._ribbon_minimized else "Ribbon restored.")

    def _toggle_pane(self, which: str) -> None:
        mapping = {
            "nav": self.nav_pane,
            "props": self.prop_pane,
            "msg": self.msg_pane,
            "params": self._param_pane,
        }
        w = mapping.get(which)
        if w is not None:
            w.setVisible(not w.isVisible())

    def _show_parameter_list(self) -> None:
        self._param_pane.setVisible(True)
        self.bottom_tabs.setCurrentWidget(self.param_list)

    def _on_edit_properties(self) -> None:
        item = self.nav_tree.tree.currentItem()
        if item is not None:
            self.nav_tree._on_item_clicked(item, 0)
        self.prop_pane.setVisible(True)
        self.message_win.info("Properties pane shown.")

    # ------------------------------------------------------------------ view

    def _on_fit(self) -> None:
        self.viewport.fit()
        self.message_win.info("Fitted view.")
        self.status.showMessage("Fit", 1500)

    def _set_plane(self, plane: str) -> None:
        self.viewport.set_plane(plane)
        label = {"xy": "Top (XY)", "xz": "Side (XZ)", "yz": "Front (YZ)"}.get(plane, plane)
        self.message_win.info(f"View: {label}")
        self._status_mode.setText(f"View: {label}")

    def _on_perspective(self) -> None:
        to_perspective = self.viewport._parallel
        self.viewport.set_perspective(to_perspective)
        if to_perspective:
            self.message_win.info("Perspective view.")
            self._status_mode.setText("View: Perspective")
        else:
            self.message_win.info("Parallel view.")
            self._status_mode.setText("View: Parallel")

    def _set_drawing_mode(self, mode: str) -> None:
        self._drawing_mode = mode
        if mode != "BoundingBox" and getattr(self.viewport, "_measure_mode", False):
            pass
        self.viewport.set_drawing_mode(mode)
        if getattr(self, "quad_view", None) is not None:
            self.quad_view.set_drawing_mode(mode)
        self.message_win.info(f"Drawing: {mode}")
        self._status_mode.setText(f"Drawing: {mode}")
        if mode != "BoundingBox":
            self._status_dim.setText("Normal")
        else:
            self._status_dim.setText("Bounding Box")

    def _on_slice(self) -> None:
        order = [None, "x", "y", "z"]
        cur = getattr(self.viewport, "_clip_axis", None)
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "x"
        self.viewport.set_clip_axis(nxt)
        if nxt is None:
            self.message_win.info("Clip plane off")
            self._status_dim.setText("Normal")
        else:
            self.message_win.info(f"Clip plane {nxt.upper()} at model mid")
            self._status_dim.setText(f"Clip {nxt.upper()}")

    def _on_measure(self) -> None:
        on = not getattr(self.viewport, "_measure_mode", False)
        self.viewport.set_measure_mode(on)
        if on:
            self.message_win.info("Measure: click two points")
            self._status_mode.setText("Measure")
        else:
            self.message_win.info("Measure off")
            self._status_mode.setText(f"Drawing: {self._drawing_mode}")

    def _current_nav(self):
        item = self.nav_tree.tree.currentItem()
        if item is None:
            return "", "", None
        kind = item.data(0, KIND_ROLE) or ""
        name = item.data(0, FULLNAME_ROLE) or item.text(0)
        return kind, name, item

    def _on_copy(self) -> None:
        kind, name, _item = self._current_nav()
        self._nav_copy(kind, name)

    def _on_cut(self) -> None:
        kind, name, _item = self._current_nav()
        if not name:
            self.message_win.info("Cut: nothing selected.")
            return
        self._nav_copy(kind, name)
        self._nav_delete(kind, name)

    def _on_paste(self) -> None:
        kind, name, _item = self._current_nav()
        self._nav_paste(kind, name)

    def _on_delete(self) -> None:
        kind, name, _item = self._current_nav()
        if not name:
            self.message_win.info("Delete: nothing selected.")
            return
        self._nav_delete(kind, name)

    def _on_copy_view(self) -> None:
        stack = getattr(self, "_view_stack", None)
        if stack is not None and stack.currentWidget() is self.result_plot:
            pm = self.result_plot.to_pixmap()
        elif self._quad_mode and getattr(self, "quad_view", None) is not None:
            pm = self.quad_view.grab()
        else:
            pm = self.viewport.grab_view()
        self._last_view_pixmap = pm
        QApplication.clipboard().setPixmap(pm)
        self.message_win.info("Copied view to clipboard.")
        self.status.showMessage("Copy View", 1500)

    def _on_toggle_edges(self) -> None:
        self._cad_edges = not self._cad_edges
        self.viewport.set_cad_edges(self._cad_edges)
        if getattr(self, "quad_view", None) is not None:
            self.quad_view.set_cad_edges(self._cad_edges)
        state = "on" if self._cad_edges else "off"
        self.message_win.info(f"CAD edges {state}")
        self._status_dim.setText(f"Edges {state}")

    def _on_quad_view(self) -> None:
        self._quad_mode = not self._quad_mode
        data = self._project_data or {}
        if self._quad_mode:
            self.quad_view.render_project(data)
            self.quad_view.set_hidden(self._hidden_parts)
            self.quad_view.set_drawing_mode(self._drawing_mode)
            self.quad_view.set_cad_edges(self._cad_edges)
            self._view_stack.setCurrentWidget(self.quad_view)
            self.message_win.info("Quad view: Top / Front / Side / 3D")
            self._status_mode.setText("View: Quad")
        else:
            self._show_viewport()
            self.message_win.info("Single viewport")
            self._status_mode.setText(f"Drawing: {self._drawing_mode}")

    def _apply_units(self, values: dict) -> None:
        units = self._project_data.setdefault("units", {})
        for key in ("length", "frequency", "time", "fmin", "fmax"):
            if values.get(key) not in (None, ""):
                units[key] = values[key]
        self._apply_units_status()
        self._mark_dirty(True)
        self.message_win.info(
            f"Units: {units.get('length', 'mm')}  {units.get('frequency', 'GHz')}")

    def _on_units(self, values=None) -> None:
        if values is None:
            values = units_dialog(self, self._project_data.get("units") or {})
            if values is None:
                return
        self._apply_units(values)

    def _on_background(self) -> None:
        display = self._project_data.setdefault("display", {})
        cur = display.get("background", "default")
        nxt = "dark" if cur != "dark" else "default"
        display["background"] = nxt
        self.message_win.info(f"Background: {nxt}")
        self._mark_dirty(True)

    def _on_boundaries(self) -> None:
        bounds = self._project_data.setdefault("boundaries", {
            "x": "open", "y": "open", "z": "open",
        })
        self.message_win.info(
            f"Boundaries: x={bounds.get('x')} y={bounds.get('y')} z={bounds.get('z')} "
            "(stored; not solved)")

    def _want_dialogs(self) -> bool:
        return os.environ.get("QT_QPA_PLATFORM") != "offscreen"

    def _sync_history_progress(self, entries) -> None:
        recs = list(entries or [])
        self._project_data["history"] = recs
        lines = [(e.get("caption") or "op", "history") for e in recs]
        self._project_data["progress"] = lines or [("History List", "Ready")]
        self._history_lines = [f"history: {c}" for c, _ in lines]
        if getattr(self, "progress_panel", None) is not None:
            self.progress_panel.set_progress(self._project_data["progress"])

    def _apply_history(self, entries) -> None:
        recs = [history_entry(e.get("caption") or "macro", history_code(e))
                for e in (entries or [])]

        def apply():
            write_history(self._archive, recs)
            self._sync_history_progress(recs)

        self._mutate("edit history", apply)

    def _on_history_list(self, action=None, index=None, caption=None, code=None,
                         interactive=False) -> None:
        entries = [dict(e) for e in load_history(self._archive)]
        if action == "insert":
            pos = len(entries) if index is None else max(0, min(int(index), len(entries)))
            entries.insert(pos, history_entry(caption or "macro",
                                              code or "' VBA\n"))
            self._apply_history(entries)
            self.message_win.info(f"Inserted history: {caption or 'macro'}")
            return
        if action == "edit":
            if index is None or not (0 <= int(index) < len(entries)):
                self.message_win.info("History edit: bad index.")
                return
            rec = entries[int(index)]
            if caption is not None:
                rec["caption"] = caption
            if code is not None:
                rec["code"] = code.split("\n") if isinstance(code, str) else code
            entries[int(index)] = history_entry(rec.get("caption") or "macro",
                                                history_code(rec))
            self._apply_history(entries)
            self.message_win.info(f"Edited history [{index}]")
            return
        if action == "delete":
            if index is None or not (0 <= int(index) < len(entries)):
                self.message_win.info("History delete: bad index.")
                return
            gone = entries.pop(int(index))
            self._apply_history(entries)
            self.message_win.info(f"Deleted history: {gone.get('caption')}")
            return
        self._history_lines = [e.get("caption") or "" for e in entries]
        if not entries:
            self.message_win.info("History List is empty.")
        else:
            self.message_win.info(f"History List: {len(entries)} entries")
            for rec in entries[:12]:
                self.message_win.info(f"  {rec.get('caption')}")
        if interactive:
            result = history_list_dialog(self, entries)
            if result is not None:
                self._apply_history(result)
                self.message_win.info(f"History List saved ({len(result)} entries)")

    def _mesh_stats(self) -> dict:
        from cst_mesh import mesh_stats, summarize_modelcache
        data = self._project_data or {}
        if not data.get("modelcache"):
            data["modelcache"] = summarize_modelcache(self._archive)
        return mesh_stats(data)

    def _on_mesh_view(self) -> None:
        if self._drawing_mode == "Mesh":
            self._set_drawing_mode(self._mesh_prev or "Shading")
            self.message_win.info("Mesh View off")
            return
        self._mesh_prev = self._drawing_mode if self._drawing_mode != "Mesh" else "Shading"
        self._set_drawing_mode("Mesh")
        st = self._mesh_stats()
        cache = ""
        if st["has_cache"]:
            cache = (f"  ModelCache: {st['cache_segments']} segment(s), "
                     f"{st['cache_bytes']:,} bytes.")
        else:
            cache = "  No ModelCache SAB."
        self.message_win.info(
            f"Mesh View: {st['solids']} solids, {st['triangles']} triangles "
            f"(surface cache). Hex/tet cells: none. "
            f"This product does not generate meshes.{cache}")
        self._status_dim.setText(f"Mesh {st['triangles']} tri")

    def _on_mesh_properties(self, values=None, interactive=False) -> None:
        from cst_mesh import load_mesh_properties, save_mesh_properties
        parsed = (self._project_data or {}).get("mesh_properties")
        if not parsed:
            parsed = load_mesh_properties(self._archive)
            self._project_data["mesh_properties"] = parsed
        props = dict(parsed.get("props") or {})
        if values is None and interactive:
            values = mesh_properties_dialog(self, props)
            if values is None:
                return
        if values is None:
            if not props:
                self.message_win.info(
                    "Mesh properties: none stored. No mesher in this product.")
            else:
                bits = [f"{k}={v}" for k, v in list(props.items())[:8]]
                self.message_win.info(
                    "Mesh properties (no mesher): " + ", ".join(bits))
            return

        def apply():
            rec = save_mesh_properties(self._archive, values)
            self._project_data["mesh_properties"] = rec

        self._mutate("mesh properties", apply)
        shown = (self._project_data.get("mesh_properties") or {}).get("props") or values
        self.message_win.info(
            "Mesh properties saved: "
            + ", ".join(f"{k}={shown.get(k, values.get(k))}" for k in list(values)[:6]))

    def _on_open_report(self) -> None:
        self.msg_pane.setVisible(True)
        self.message_win.info("Report: messages pane (no solver report file).")

    def _on_wcs(self, mode: str) -> None:
        self._wcs_mode = "local" if mode == "local" else "global"
        self.message_win.info(
            f"WCS: {self._wcs_mode} (display only; solids stay in global).")

    def _on_material_library(self) -> None:
        mats = (self._project_data or {}).get("materials") or []
        names = [m.get("name", "?") for m in mats]
        self._library_names = names
        if names:
            self.message_win.info("Material library: " + ", ".join(names[:12]))
        else:
            self.message_win.info("Material library is empty.")

    def _on_source(self, kind: str) -> None:
        label = {"field": "Field source", "plane_wave": "Plane wave",
                 "farfield": "Farfield source"}.get(kind, kind)
        rec = {"name": label, "type": kind}
        bucket = self._project_data.setdefault("sources", [])
        bucket.append(rec)
        self._mark_dirty(True)
        self.message_win.info(f"{label} added (not solved).")

    def _on_smith(self) -> None:
        self.result_plot.set_result({}, "Smith chart needs S-parameter samples.")
        self._show_plot()
        self.message_win.info("Smith chart: no S-parameter samples.")

    def _on_field_sample(self, where: str) -> None:
        self.message_win.info(
            f"Field on {where}: no field samples in this project.")

    def _on_macro(self, lang: str, code=None, caption=None) -> None:
        if code is not None:
            self._on_history_list(
                action="insert",
                caption=caption or f"{lang} macro",
                code=code)
            return
        n = len(load_history(self._archive))
        self.message_win.info(
            f"{lang.upper()} macro: History has {n} entries "
            "(macros are stored, not executed).")

    def _on_help_topic(self, topic: str) -> None:
        text = {
            "started": "CST Decoding is a viewer/editor for .cst files. "
                       "It does not include a solver.",
            "videos": "No bundled videos. Open a sample .cst from File → Open.",
            "tutorials": "Load a project, edit solids in Modeling, inspect "
                         "results under Post-Processing.",
        }.get(topic, "Help")
        self.message_win.info(text)

    def keyPressEvent(self, event):
        # cabdecoding Draw Window keys: F fit, X/Y/Z orthogonal
        key = event.key()
        if key == Qt.Key_F and not event.modifiers():
            self._on_fit()
            return
        mapping = {Qt.Key_X: "yz", Qt.Key_Y: "xz", Qt.Key_Z: "xy"}
        if key in mapping:
            self._set_plane(mapping[key])
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ nav

    def _on_nav_selected(self, kind: str, label: str, payload) -> None:
        self.message_win.info(f"Selected: {label} ({kind})")
        self.properties.show_item(kind, label, payload if isinstance(payload, dict) else None)
        self._status_label.setText(label)
        if kind in ("solid", "component"):
            self._selected_solid = label
            self.viewport.select_solid(label)
            self._show_viewport()
            comp = payload if isinstance(payload, dict) else self._find_component(label)
            bounds = (comp or {}).get("bounds")
            if bounds and len(bounds) == 6:
                cx = 0.5 * (bounds[0] + bounds[1])
                cy = 0.5 * (bounds[2] + bounds[3])
                cz = 0.5 * (bounds[4] + bounds[5])
                self._status_xy.setText(f"({cx:.3g}, {cy:.3g}, {cz:.3g})")
        elif kind in ("result_1d", "result_2d", "farfield", "table", "results"):
            self._selected_solid = ""
            self.viewport.select_solid("")
            self._open_result(payload if isinstance(payload, dict) else {"name": label})
        else:
            self._selected_solid = ""
            self.viewport.select_solid("")
            self._show_viewport()

    def _on_solid_picked(self, name: str) -> None:
        self._selected_solid = name
        self.nav_tree.select_by_name(name, emit=False)
        comp = self._find_component(name)
        self.properties.show_item("solid", name, comp)
        self._status_label.setText(name)
        self.message_win.info(f"Picked: {name}")

    def _on_pick_coords(self, text: str) -> None:
        self._status_xy.setText(text)

    def _on_visibility(self, name: str, visible: bool) -> None:
        if visible:
            self._hidden_parts.discard(name)
        else:
            self._hidden_parts.add(name)
        write_hidden(self._archive, self._hidden_parts)
        self.viewport.set_hidden(self._hidden_parts)
        self.nav_tree.set_hidden_names(self._hidden_parts)
        self._mark_dirty(True)

    def _on_nav_context(self, action: str, kind: str, name: str) -> None:
        handlers = {
            "properties": self._on_edit_properties,
            "edit_properties": self._on_edit_properties,
            "show_all": lambda: self.message_win.info("Show All"),
            "copy": lambda: self._nav_copy(kind, name),
            "paste": lambda: self._nav_paste(kind, name),
            "delete": lambda: self._nav_delete(kind, name),
            "rename": lambda: self._nav_rename(kind, name),
            "object_info": lambda: self._nav_object_info(kind, name),
            "assign_material": lambda: self._nav_assign_material(name),
            "edit_material": lambda: self._nav_edit_material(kind, name),
            "change_component": lambda: self._nav_change_component(name),
            "change_group": lambda: self._nav_change_group(name),
            "new_component": self._on_new_component,
            "transform": lambda: self._on_transform("translate"),
            "rect_select": lambda: self._nyi("Rectangle Selection"),
            "slice_uv": lambda: self._nyi("Slice by UV Plane"),
            "separate": lambda: self._nyi("Separate Shape"),
            "align": lambda: self._nyi("Align"),
            "local_mesh": lambda: self._on_mesh_properties(
                interactive=self._want_dialogs()),
            "elec_calc": lambda: self._nyi("Calculate Electrical Connections"),
            "elec_show": lambda: self._nyi("Show Electrical Connections"),
            "elec_hide": lambda: self._nyi("Hide Electrical Connections"),
            "wcs_align_solid": lambda: self._nyi("Align WCS with Solid"),
            "wcs_to_center": lambda: self._nyi("Move WCS to Solid Center"),
            "wcs_reset": lambda: self._nyi("Reset WCS to Global"),
        }
        fn = handlers.get(action)
        if fn is None:
            self._nyi(action)
            return
        fn()

    def _sync_viewports(self, data=None) -> None:
        data = data if data is not None else (self._project_data or {})
        self.viewport.render_project(data)
        self.viewport.set_hidden(self._hidden_parts)
        self.viewport.set_cad_edges(self._cad_edges)
        if getattr(self, "quad_view", None) is not None:
            self.quad_view.render_project(data)
            self.quad_view.set_hidden(self._hidden_parts)
            self.quad_view.set_drawing_mode(self._drawing_mode)
            self.quad_view.set_cad_edges(self._cad_edges)

    def _refresh_geometry(self) -> None:
        data = self._project_data or {}
        self.nav_tree.populate_from_project(data)
        self.nav_tree.set_hidden_names(self._hidden_parts)
        self._sync_viewports(data)
        if self._selected_solid:
            self.nav_tree.select_by_name(self._selected_solid, emit=False)
            self.viewport.select_solid(self._selected_solid)

    def _find_component(self, name: str):
        for comp in (self._project_data or {}).get("components") or []:
            if comp.get("name") == name:
                return comp
        return None

    def _eval_num(self, expr, default=0.0) -> float:
        try:
            return float(eval_expr(expr, (self._project_data or {}).get("parameters") or []))
        except Exception:
            try:
                return float(expr)
            except (TypeError, ValueError):
                return float(default)

    def _on_shape(self, kind: str) -> None:
        data = shape_dialog(
            self, kind, self._component_folders() or ["component1"],
            self._material_names())
        if not data:
            return
        try:
            self._add_shape(kind, data)
        except Exception as exc:
            self.message_win.error(f"{kind}: {exc}")

    def _material_names(self) -> list:
        names = [m.get("name") for m in (self._project_data or {}).get("materials") or []
                 if m.get("name")]
        for extra in ("PEC", "Vacuum"):
            if extra not in names:
                names.append(extra)
        return names

    def _add_shape(self, kind: str, data: dict) -> None:
        kind = (kind or data.get("kind") or "brick").lower()
        component = (data.get("component") or "component1").replace("\\", "/")
        raw_name = data.get("name") or kind
        material = data.get("material") or "PEC"
        existing = {c.get("name") for c in (self._project_data or {}).get("components") or []}
        full = unique_solid_name(existing, component, raw_name)
        solid = full.split(":", 1)[-1]

        def num(key, default="0"):
            return self._eval_num(data.get(key, default), float(default))

        if kind == "brick":
            xmin, xmax = num("xmin", "-5"), num("xmax", "5")
            ymin, ymax = num("ymin", "-5"), num("ymax", "5")
            zmin, zmax = num("zmin", "0"), num("zmax", "1")
            mesh = box_mesh(xmin, xmax, ymin, ymax, zmin, zmax)
            vba = brick_vba(solid, component, material,
                            (data.get("xmin", xmin), data.get("xmax", xmax)),
                            (data.get("ymin", ymin), data.get("ymax", ymax)),
                            (data.get("zmin", zmin), data.get("zmax", zmax)))
            caption = f"define brick: {full}"
        elif kind == "cylinder":
            radius = num("radius", "2")
            zmin, zmax = num("zmin", "0"), num("zmax", "10")
            cx, cy = num("cx", "0"), num("cy", "0")
            mesh = cylinder_mesh(cx, cy, zmin, zmax, radius)
            vba = cylinder_vba(solid, component, material,
                               data.get("radius", radius),
                               data.get("zmin", zmin), data.get("zmax", zmax),
                               data.get("cx", cx), data.get("cy", cy))
            caption = f"define cylinder: {full}"
        elif kind == "sphere":
            radius = num("radius", "5")
            cx, cy, cz = num("cx", "0"), num("cy", "0"), num("cz", "0")
            mesh = sphere_mesh(cx, cy, cz, radius)
            vba = sphere_vba(solid, component, material,
                             data.get("radius", radius),
                             data.get("cx", cx), data.get("cy", cy),
                             data.get("cz", cz))
            caption = f"define sphere: {full}"
        elif kind == "torus":
            major, minor = num("major", "8"), num("minor", "1.5")
            cx, cy, cz = num("cx", "0"), num("cy", "0"), num("cz", "0")
            mesh = torus_mesh(cx, cy, cz, major, minor)
            vba = torus_vba(solid, component, material,
                            data.get("major", major), data.get("minor", minor),
                            data.get("cx", cx), data.get("cy", cy),
                            data.get("cz", cz))
            caption = f"define torus: {full}"
        else:
            r_bot, r_top = num("r_bottom", "4"), num("r_top", "1")
            zmin, zmax = num("zmin", "0"), num("zmax", "8")
            cx, cy = num("cx", "0"), num("cy", "0")
            mesh = cone_mesh(cx, cy, zmin, zmax, r_bot, r_top)
            vba = cone_vba(solid, component, material,
                           data.get("r_bottom", r_bot), data.get("r_top", r_top),
                           data.get("zmin", zmin), data.get("zmax", zmax),
                           data.get("cx", cx), data.get("cy", cy))
            caption = f"define cone: {full}"

        comp = {
            "name": full,
            "material": material,
            "bounds": mesh_bounds(mesh),
            "mesh": mesh,
            "source": "primitive",
        }
        folders = self._component_folders()
        need_component = component not in folders

        def apply():
            if need_component:
                append_component_new(self._archive, component)
                empties = self._project_data.setdefault("empty_components", [])
                if component in empties:
                    empties.remove(component)
            append_history(self._archive, caption, vba)
            self._project_data.setdefault("components", []).append(comp)
            self._selected_solid = full
            self._refresh_geometry()

        self._mutate(caption, apply)
        self.message_win.info(f"Created {full}")
        self.status.showMessage(f"Created {full}", 2500)

    def _solid_names(self) -> list:
        return [c.get("name") for c in (self._project_data or {}).get("components") or []
                if c.get("name")]

    def _on_boolean(self, op: str) -> None:
        names = self._solid_names()
        data = boolean_dialog(self, names, op)
        if not data:
            if len(names) < 2:
                self.message_win.warn("Boolean needs two solids.")
            return
        self._apply_boolean(op, data.get("target", ""), data.get("tool", ""))

    def _apply_boolean(self, op: str, target: str, tool: str) -> None:
        a = self._find_component(target)
        b = self._find_component(tool)
        if a is None or b is None or target == tool:
            self.message_win.warn("Boolean: pick two different solids.")
            return
        op = (op or "subtract").lower()

        def apply():
            comps = self._project_data.setdefault("components", [])
            if op == "add":
                ma, mb = a.get("mesh") or {}, b.get("mesh") or {}
                if ma.get("faces") and mb.get("faces"):
                    a["mesh"] = merge_meshes(ma, mb)
                    a["bounds"] = mesh_bounds(a["mesh"])
                elif a.get("bounds") and b.get("bounds"):
                    a["bounds"] = union_bounds(a["bounds"], b["bounds"])
                    a["mesh"] = box_mesh(*a["bounds"])
            elif op == "intersect":
                if not (a.get("bounds") and b.get("bounds")):
                    raise ValueError("intersect needs bounds on both solids")
                inter = intersect_bounds(a["bounds"], b["bounds"])
                if inter is None:
                    raise ValueError("solids do not overlap")
                a["bounds"] = inter
                a["mesh"] = box_mesh(*inter)
            self._project_data["components"] = [
                c for c in comps if c.get("name") != tool]
            append_history(
                self._archive, f"boolean {op} shapes: {target}, {tool}",
                boolean_vba(op, target, tool))
            if self._selected_solid == tool:
                self._selected_solid = target
            self._refresh_geometry()

        try:
            self._mutate(f"boolean {op}", apply)
        except Exception as exc:
            self.message_win.warn(f"Boolean {op}: {exc}")
            return
        self.message_win.info(f"Boolean {op}: {target} ← {tool}")

    def _origin_from(self, data: dict, comp: dict) -> tuple:
        bounds = comp.get("bounds") or (0, 0, 0, 0, 0, 0)
        cx, cy, cz = bounds_center(bounds)
        if data.get("cx"):
            cx = self._eval_num(data["cx"], cx)
        if data.get("cy"):
            cy = self._eval_num(data["cy"], cy)
        if data.get("cz"):
            cz = self._eval_num(data["cz"], cz)
        return (cx, cy, cz)

    def _on_transform(self, mode: str) -> None:
        names = self._solid_names()
        if self._selected_solid and self._selected_solid in names:
            names = [self._selected_solid] + [n for n in names if n != self._selected_solid]
        data = transform_dialog(self, names, mode)
        if not data:
            if not names:
                self.message_win.warn("No solids to transform.")
            return
        self._apply_transform(mode, data)

    def _apply_transform(self, mode: str, data: dict) -> None:
        name = data.get("name") or self._selected_solid
        comp = self._find_component(name)
        if comp is None:
            self.message_win.warn(f"Transform: {name} not found.")
            return
        mode = (mode or data.get("mode") or "translate").lower()
        origin = self._origin_from(data, comp)
        if mode == "translate":
            dx = self._eval_num(data.get("dx", "0"))
            dy = self._eval_num(data.get("dy", "0"))
            dz = self._eval_num(data.get("dz", "0"))
            fn = translate_fn(dx, dy, dz)
            vba = transform_translate_vba(
                name, data.get("dx", dx), data.get("dy", dy), data.get("dz", dz))
            caption = f"transform: translate {name}"
        elif mode == "rotate":
            axis = (data.get("axis") or "z").lower()[:1] or "z"
            angle = self._eval_num(data.get("angle", "90"))
            fn = rotate_fn(axis, angle, origin)
            ax = ay = az = 0
            if axis == "x":
                ax = angle
            elif axis == "y":
                ay = angle
            else:
                az = angle
            vba = transform_rotate_vba(
                name, ax, ay, az, origin[0], origin[1], origin[2])
            caption = f"transform: rotate {name}"
        elif mode == "mirror":
            axis = (data.get("axis") or "x").lower()[:1] or "x"
            fn = mirror_fn(axis, origin)
            nx = 1 if axis == "x" else 0
            ny = 1 if axis == "y" else 0
            nz = 1 if axis == "z" else 0
            vba = transform_mirror_vba(
                name, nx, ny, nz, origin[0], origin[1], origin[2])
            caption = f"transform: mirror {name}"
        else:
            sx = self._eval_num(data.get("sx", "1"), 1.0)
            sy = self._eval_num(data.get("sy", "1"), 1.0)
            sz = self._eval_num(data.get("sz", "1"), 1.0)
            fn = scale_fn(origin[0], origin[1], origin[2], sx, sy, sz)
            vba = transform_scale_vba(
                name, data.get("sx", sx), data.get("sy", sy), data.get("sz", sz),
                origin[0], origin[1], origin[2])
            caption = f"transform: scale {name}"

        def apply():
            updated = transform_component(comp, fn)
            comp["bounds"] = updated.get("bounds")
            if updated.get("mesh"):
                comp["mesh"] = updated["mesh"]
            append_history(self._archive, caption, vba)
            self._refresh_geometry()

        self._mutate(caption, apply)
        self.message_win.info(caption)

    def _on_new_material(self, checked=False) -> None:
        data = material_dialog(self)
        if not data or not data.get("name"):
            return
        self._add_material(data)

    def _add_material(self, data: dict) -> None:
        colour = data.get("colour") or "0.75,0.80,0.90"
        parts = [p.strip() for p in colour.split(",") if p.strip()]
        while len(parts) < 3:
            parts.append("0.8")
        rgb = tuple(parts[:3])
        mat = {
            "name": data["name"],
            "epsilon": data.get("epsilon") or "1.0",
            "mu": data.get("mu") or "1.0",
            "kappa": data.get("kappa") or "0.0",
            "tand": data.get("tand") or "0.0",
            "type": "Normal",
            "folder": data.get("folder") or "",
            "colour": ",".join(rgb),
        }
        vba = material_vba(
            mat["name"], mat["epsilon"], mat["mu"], mat["kappa"], mat["tand"],
            rgb, mat["folder"])

        def apply():
            self._project_data.setdefault("materials", []).append(mat)
            append_history(self._archive, f"define material: {mat['name']}", vba)
            self._refresh_geometry()

        self._mutate(f"material {mat['name']}", apply)
        self.message_win.info(f"Material {mat['name']}")

    def _on_new_component(self) -> None:
        name = component_dialog(self)
        if not name:
            return
        self._add_component(name.replace("\\", "/"))

    def _add_component(self, name: str) -> None:
        name = (name or "").replace("\\", "/")
        if not name:
            return
        if name in self._component_folders():
            self.message_win.warn(f"Component {name} already exists.")
            return

        def apply():
            empties = self._project_data.setdefault("empty_components", [])
            if name not in empties:
                empties.append(name)
            append_component_new(self._archive, name)
            self._refresh_geometry()

        self._mutate(f"new component {name}", apply)
        self.message_win.info(f"Component {name}")

    def _on_discrete_port(self) -> None:
        n = next_port_number((self._project_data or {}).get("ports") or [])
        data = discrete_port_dialog(self, {"port_number": str(n)})
        if data:
            self._add_discrete_port(data)

    def _add_discrete_port(self, data: dict) -> None:
        ports = (self._project_data or {}).setdefault("ports", [])
        num = int(data.get("port_number") or next_port_number(ports))
        label = data.get("label") or ""
        name = label or f"port{num}"
        p1 = (data.get("x1", "0"), data.get("y1", "0"), data.get("z1", "0"))
        p2 = (data.get("x2", "0"), data.get("y2", "0"), data.get("z2", "1"))
        impedance = data.get("impedance") or "50.0"
        ptype = data.get("ptype") or "SParameter"
        params = (self._project_data or {}).get("parameters") or []
        rec = {
            "name": name,
            "port_number": num,
            "impedance": impedance,
            "type": ptype,
            "kind": "Discrete",
            "label": label,
            "p1": p1,
            "p2": p2,
            "p1_xyz": eval_point(p1, params),
            "p2_xyz": eval_point(p2, params),
        }
        vba = discrete_port_vba(num, impedance, p1, p2, label, ptype)

        def apply():
            ports.append(rec)
            append_history(self._archive, f"define discrete port: {num}", vba)
            eval_excitations(self._project_data)
            self._refresh_geometry()

        self._mutate(f"discrete port {num}", apply)
        self.message_win.info(f"Discrete port {num}  Z={impedance}")

    def _on_waveguide_port(self) -> None:
        n = next_port_number((self._project_data or {}).get("ports") or [])
        data = waveguide_port_dialog(self, {"port_number": str(n)})
        if data:
            self._add_waveguide_port(data)

    def _add_waveguide_port(self, data: dict) -> None:
        ports = (self._project_data or {}).setdefault("ports", [])
        num = int(data.get("port_number") or next_port_number(ports))
        label = data.get("label") or ""
        ori = data.get("orientation") or "zmin"
        xr = (data.get("xmin", "-10"), data.get("xmax", "10"))
        yr = (data.get("ymin", "-5"), data.get("ymax", "5"))
        zr = (data.get("zmin", "0"), data.get("zmax", "0"))
        rec = {
            "name": label or f"port{num}",
            "port_number": num,
            "impedance": "50",
            "type": "Waveguide",
            "kind": "Waveguide",
            "orientation": ori,
            "xrange": xr,
            "yrange": yr,
            "zrange": zr,
        }
        vba = waveguide_port_vba(num, ori, xr, yr, zr, label)

        def apply():
            ports.append(rec)
            append_history(self._archive, f"define waveguide port: {num}", vba)
            eval_excitations(self._project_data)
            self._refresh_geometry()

        self._mutate(f"waveguide port {num}", apply)
        self.message_win.info(f"Waveguide port {num} ({ori})")

    def _on_field_monitor(self) -> None:
        data = monitor_dialog(self)
        if data:
            self._add_monitor(data)

    def _add_monitor(self, data: dict) -> None:
        ft = data.get("field_type") or "Efield"
        freq = data.get("frequency") or "2.45"
        name = data.get("name") or f"{ft.lower()} (f={freq})"
        rec = {
            "name": name,
            "field_type": ft,
            "frequency": freq,
            "domain": data.get("domain") or "Frequency",
            "dimension": data.get("dimension") or "Volume",
        }
        vba = monitor_vba(name, ft, freq, rec["domain"], rec["dimension"])

        def apply():
            self._project_data.setdefault("monitors", []).append(rec)
            cap = "farfield" if ft.lower() == "farfield" else "monitor"
            append_history(self._archive, f"define {cap}: {name}", vba)
            self._refresh_geometry()

        self._mutate(f"monitor {name}", apply)
        self.message_win.info(f"Monitor {name}")

    def _on_probe(self) -> None:
        data = probe_dialog(self)
        if data:
            self._add_probe(data)

    def _add_probe(self, data: dict) -> None:
        name = data.get("name") or "probe1"
        field = data.get("field_name") or "efield"
        x, y, z = data.get("x", "0"), data.get("y", "0"), data.get("z", "0")
        ori = data.get("orientation") or "X"
        params = (self._project_data or {}).get("parameters") or []
        rec = {
            "name": name,
            "field_type": field,
            "x": x, "y": y, "z": z,
            "orientation": ori,
            "p1": (x, y, z),
            "xyz": eval_point((x, y, z), params),
        }
        vba = probe_vba(name, field, x, y, z, ori)

        def apply():
            self._project_data.setdefault("probes", []).append(rec)
            append_history(self._archive, f"define probe: {name}", vba)
            eval_excitations(self._project_data)
            self._refresh_geometry()

        self._mutate(f"probe {name}", apply)
        self.message_win.info(f"Probe {name}")

    def _find_named(self, collection: str, name: str):
        for rec in (self._project_data or {}).get(collection) or []:
            if rec.get("name") == name:
                return rec
        return None

    def _port_vba(self, rec: dict) -> str:
        n = rec.get("port_number")
        if rec.get("kind") == "Waveguide" or rec.get("type") == "Waveguide":
            return waveguide_port_vba(
                n, rec.get("orientation") or "zmin",
                rec.get("xrange") or ("-10", "10"),
                rec.get("yrange") or ("-5", "5"),
                rec.get("zrange") or ("0", "0"),
                rec.get("label") or "")
        ptype = rec.get("type") or "SParameter"
        if ptype not in ("SParameter", "Voltage", "Current"):
            ptype = "SParameter"
        return discrete_port_vba(
            n, rec.get("impedance") or "50.0",
            rec.get("p1") or ("0", "0", "0"),
            rec.get("p2") or ("0", "0", "1"),
            rec.get("label") or "", ptype)

    def _monitor_vba(self, rec: dict) -> str:
        return monitor_vba(
            rec.get("name") or "monitor",
            rec.get("field_type") or "Efield",
            rec.get("frequency") or "2.45",
            rec.get("domain") or "Frequency",
            rec.get("dimension") or "Volume")

    def _probe_vba(self, rec: dict) -> str:
        return probe_vba(
            rec.get("name") or "probe1",
            rec.get("field_type") or rec.get("field_name") or "efield",
            rec.get("x", "0"), rec.get("y", "0"), rec.get("z", "0"),
            rec.get("orientation") or "X")

    def _rewrite_excitation_history(self, coll: str, rec: dict,
                                    old_name: str | None = None) -> None:
        if coll == "ports":
            n = rec.get("port_number")
            append_history(
                self._archive, f"define port: {n}",
                f'Port.Delete "{n}"\n' + self._port_vba(rec))
        elif coll == "monitors":
            old = old_name or rec.get("name") or ""
            append_history(
                self._archive, f"define monitor: {rec.get('name')}",
                f'Monitor.Delete "{old}"\n' + self._monitor_vba(rec))
        elif coll == "probes":
            old = old_name or rec.get("name") or ""
            append_history(
                self._archive, f"define probe: {rec.get('name')}",
                f'Probe.Delete "{old}"\n' + self._probe_vba(rec))

    def _component_folders(self) -> list:
        seen, folders = set(), []
        for name in (self._project_data or {}).get("empty_components") or []:
            if name and name not in seen:
                seen.add(name)
                folders.append(name)
        for comp in (self._project_data or {}).get("components") or []:
            path, _solid = split_solid_path(comp.get("name", ""))
            key = "/".join(path)
            if key and key not in seen:
                seen.add(key)
                folders.append(key)
        return folders

    def _nav_copy(self, kind: str, name: str) -> None:
        if not name:
            self.message_win.info("Copy: nothing selected.")
            return
        payload = None
        item = self.nav_tree.tree.currentItem()
        if item is not None:
            payload = item.data(0, PAYLOAD_ROLE)
        self.nav_tree._clipboard = (kind, name, payload)
        QApplication.clipboard().setText(name)
        self.message_win.info(f"Copied {name}")
        self.status.showMessage(f"Copied {name}", 2000)

    def _nav_paste(self, kind: str, name: str) -> None:
        clip = self.nav_tree._clipboard
        if not clip:
            self.message_win.info("Paste: clipboard is empty.")
            return
        _ckind, src_name, _payload = clip
        src = self._find_component(src_name)
        if src is None:
            self.message_win.warn(f"Paste: {src_name} is not a solid in this project.")
            return
        comps = self._project_data.setdefault("components", [])
        folders, solid = split_solid_path(src.get("name", "solid"))
        names = {c.get("name") for c in comps}
        i = 1
        new_solid = f"{solid}_copy"
        new_name = "/".join(folders) + ":" + new_solid
        while new_name in names:
            i += 1
            new_solid = f"{solid}_copy{i}"
            new_name = "/".join(folders) + ":" + new_solid
        dup = copy.deepcopy(src)
        dup["name"] = new_name
        def apply():
            comps.append(dup)
            self._refresh_geometry()
        self._mutate(f"paste {new_name}", apply)
        self.message_win.info(f"Pasted as {new_name}")

    def _nav_delete(self, kind: str, name: str) -> None:
        names = [n for n in (name or "").split("\n") if n]
        if not names:
            return
        if kind in ("port", "ports"):
            self._delete_named("ports", names, "Port.Delete")
            return
        if kind == "monitor":
            self._delete_named("monitors", names, "Monitor.Delete")
            return
        if kind == "probe":
            self._delete_named("probes", names, "Probe.Delete")
            return
        comps = (self._project_data or {}).get("components") or []
        folder = names[0] if len(names) == 1 else None
        if kind in ("collection", "folder") and folder and not any(
                (c.get("name") or "").startswith(folder + ":")
                or (c.get("name") or "").startswith(folder + "/")
                for c in comps):
            def apply_empty():
                empties = self._project_data.setdefault("empty_components", [])
                self._project_data["empty_components"] = [
                    e for e in empties if e != folder]
                append_component_delete(self._archive, folder)
                self._refresh_geometry()
            self._mutate(f"delete component {folder}", apply_empty)
            self.message_win.info(f"Deleted component {folder}")
            return
        remain = [c for c in comps if c.get("name") not in names]
        if len(remain) == len(comps) and kind not in ("solid", "component",
                                                      "collection", "group"):
            self.message_win.info(f"Cannot delete {kind or 'this item'}.")
            return
        if self._project_data is not None:
            def apply():
                self._project_data["components"] = remain
                for n in names:
                    self._hidden_parts.discard(n)
                append_solid_delete(self._archive, names)
                write_hidden(self._archive, self._hidden_parts)
                if self._selected_solid in names:
                    self._selected_solid = ""
                self._refresh_geometry()
            self._mutate("delete " + names[0], apply)
        self.message_win.info(
            "Deleted " + (", ".join(n.split(":")[-1] for n in names[:6]))
            + ("…" if len(names) > 6 else ""))

    def _delete_named(self, collection: str, names: list, vba_cmd: str) -> None:
        items = (self._project_data or {}).get(collection) or []
        remain = [x for x in items if x.get("name") not in names]
        if len(remain) == len(items):
            self.message_win.warn(f"Nothing to delete in {collection}.")
            return

        def apply():
            self._project_data[collection] = remain
            for n in names:
                rec = next((x for x in items if x.get("name") == n), None)
                arg = n
                if rec and rec.get("port_number") is not None and "Port" in vba_cmd:
                    arg = str(rec["port_number"])
                append_history(self._archive, f"delete {collection[:-1]}: {n}",
                               f'{vba_cmd} "{arg}"\n')
            self._refresh_geometry()

        self._mutate(f"delete {names[0]}", apply)
        self.message_win.info("Deleted " + ", ".join(names[:6]))

    def _nav_rename(self, kind: str, name: str) -> None:
        if "\n" not in (name or ""):
            return
        old, new = name.split("\n", 1)

        def apply():
            comps = (self._project_data or {}).get("components") or []
            if kind == "solid":
                for comp in comps:
                    if comp.get("name") == old:
                        comp["name"] = new
                if old in self._hidden_parts:
                    self._hidden_parts.discard(old)
                    self._hidden_parts.add(new)
            elif kind in ("collection", "folder", "group"):
                prefix = old.rstrip("/") + "/"
                colon = old + ":"
                for comp in comps:
                    nm = comp.get("name") or ""
                    if nm.startswith(colon):
                        comp["name"] = new + ":" + nm.split(":", 1)[1]
                    elif nm.startswith(prefix):
                        comp["name"] = new + nm[len(old):]
                hidden = set()
                for n in self._hidden_parts:
                    if n.startswith(colon):
                        hidden.add(new + ":" + n.split(":", 1)[1])
                    elif n.startswith(prefix):
                        hidden.add(new + n[len(old):])
                    else:
                        hidden.add(n)
                self._hidden_parts = hidden
            elif kind == "material":
                for mat in (self._project_data or {}).get("materials") or []:
                    if mat.get("name") == old:
                        mat["name"] = new
                for comp in comps:
                    if comp.get("material") == old:
                        comp["material"] = new
            elif kind in ("port", "ports"):
                rec = None
                for item in (self._project_data or {}).get("ports") or []:
                    if item.get("name") == old:
                        item["name"] = new
                        item["label"] = new
                        rec = item
                        break
                if rec is not None:
                    self._rewrite_excitation_history("ports", rec, old_name=old)
            elif kind == "monitor":
                rec = None
                for item in (self._project_data or {}).get("monitors") or []:
                    if item.get("name") == old:
                        item["name"] = new
                        rec = item
                        break
                if rec is not None:
                    self._rewrite_excitation_history("monitors", rec, old_name=old)
            elif kind == "probe":
                rec = None
                for item in (self._project_data or {}).get("probes") or []:
                    if item.get("name") == old:
                        item["name"] = new
                        rec = item
                        break
                if rec is not None:
                    self._rewrite_excitation_history("probes", rec, old_name=old)
            if kind == "solid":
                append_solid_rename(self._archive, old, new)
                if self._selected_solid == old:
                    self._selected_solid = new
            self._refresh_geometry()

        self._mutate(f"rename {old}", apply)
        self.message_win.info(f"Renamed {old} → {new}")

    def _nav_object_info(self, kind: str, name: str) -> None:
        comp = self._find_component(name)
        if comp is None and kind in ("collection", "folder", "group"):
            names = [c.get("name") for c in
                     (self._project_data or {}).get("components") or []
                     if (c.get("name") or "").startswith(name + "/")
                     or (c.get("name") or "").startswith(name + ":")]
            QMessageBox.information(
                self, "Object Information",
                f"Component: {name}\nSolids: {len(names)}")
            return
        if comp is None:
            self.message_win.warn(f"No object data for {name}")
            return
        mesh = comp.get("mesh") or {}
        bounds = comp.get("bounds")
        lines = [
            f"Name: {comp.get('name', name)}",
            f"Material: {comp.get('material', '')}",
        ]
        if comp.get("colour"):
            lines.append(f"Colour: {comp.get('colour')}")
        if bounds and len(bounds) == 6:
            lines.append(
                f"Bounds: [{bounds[0]:g}, {bounds[1]:g}] × "
                f"[{bounds[2]:g}, {bounds[3]:g}] × "
                f"[{bounds[4]:g}, {bounds[5]:g}]")
        if mesh.get("faces"):
            lines.append(f"Mesh faces: {len(mesh['faces'])}")
            lines.append(f"Mesh points: {len(mesh.get('points') or [])}")
        wires = mesh.get("wires") or comp.get("wires") or []
        if wires:
            lines.append(f"CAD edges: {len(wires)}")
        QMessageBox.information(self, "Object Information", "\n".join(lines))

    def _nav_assign_material(self, name: str) -> None:
        comp = self._find_component(name)
        if comp is None:
            self.message_win.warn(f"Assign Material: {name} not found.")
            return
        mats = (self._project_data or {}).get("materials") or []
        labels = [m.get("name", "") for m in mats if m.get("name")]
        if not labels:
            self.message_win.warn("No materials in this project.")
            return
        current = comp.get("material") or ""
        idx = labels.index(current) if current in labels else 0
        chosen, ok = QInputDialog.getItem(
            self, "Assign Material and Color", "Material:", labels, idx, False)
        if not ok or not chosen:
            return
        mat = next((m for m in mats if m.get("name") == chosen), None)

        def apply():
            comp["material"] = chosen
            if mat and mat.get("colour"):
                comp["colour"] = mat["colour"]
            append_change_material(self._archive, name, chosen)
            self._refresh_geometry()

        self._mutate(f"assign {chosen}", apply)
        self.message_win.info(f"{name} → material {chosen}")

    def _nav_edit_material(self, kind: str, name: str) -> None:
        mat_name = name
        if kind != "material":
            comp = self._find_component(name)
            mat_name = (comp or {}).get("material") or ""
        mats = (self._project_data or {}).get("materials") or []
        mat = next((m for m in mats if m.get("name") == mat_name), None)
        if mat is None:
            short = mat_name.split("/")[-1]
            mat = next((m for m in mats if m.get("name") == short
                        or (m.get("name") or "").endswith("/" + short)), None)
        if mat is None:
            self.message_win.warn(f"Material not found: {mat_name or name}")
            return
        self.properties.show_item("material", mat.get("name", mat_name), mat)
        self.prop_pane.setVisible(True)
        self.message_win.info(f"Material: {mat.get('name', mat_name)}")

    def _nav_change_component(self, name: str) -> None:
        comp = self._find_component(name)
        if comp is None:
            self.message_win.warn(f"Change Component: {name} not found.")
            return
        folders = self._component_folders()
        if not folders:
            return
        cur_path, solid = split_solid_path(name)
        current = "/".join(cur_path)
        idx = folders.index(current) if current in folders else 0
        chosen, ok = QInputDialog.getItem(
            self, "Change Component", "Component:", folders, idx, True)
        if not ok or not chosen:
            return
        new_name = chosen.strip().replace("\\", "/") + ":" + solid
        if new_name == name:
            return
        names = {c.get("name") for c in (self._project_data or {}).get("components") or []}
        if new_name in names:
            self.message_win.warn(f"{new_name} already exists.")
            return
        comp["name"] = new_name
        if name in self._hidden_parts:
            self._hidden_parts.discard(name)
            self._hidden_parts.add(new_name)
        self._refresh_geometry()
        self.message_win.info(f"{name} → {new_name}")

    def _nav_change_group(self, name: str) -> None:
        groups = (self._project_data or {}).get("groups") or []
        labels = [g.get("name", "") for g in groups if g.get("name")]
        if not labels:
            self.message_win.warn("No groups in this project.")
            return
        chosen, ok = QInputDialog.getItem(
            self, "Change Group", "Group:", labels, 0, False)
        if not ok or not chosen:
            return
        grp = next((g for g in groups if g.get("name") == chosen), None)
        if grp is None:
            return
        if name in (grp.get("items") or []):
            return

        def apply():
            items = list(grp.get("items") or [])
            if name not in items:
                items.append(name)
                grp["items"] = items
            append_group_item(self._archive, name, chosen)
            self._refresh_geometry()

        self._mutate(f"group {chosen}", apply)
        self.message_win.info(f"{name} added to group {chosen}")

    def _on_drop_to_group(self, solid: str, group: str) -> None:
        if not solid or not group:
            return
        groups = (self._project_data or {}).setdefault("groups", [])
        grp = next((g for g in groups if g.get("name") == group), None)
        if grp is not None and solid in (grp.get("items") or []):
            return

        def apply():
            groups_ = self._project_data.setdefault("groups", [])
            g = next((x for x in groups_ if x.get("name") == group), None)
            if g is None:
                g = {"name": group, "type": "", "items": []}
                groups_.append(g)
            items = list(g.get("items") or [])
            if solid not in items:
                items.append(solid)
                g["items"] = items
            append_group_item(self._archive, solid, group)
            self._refresh_geometry()

        self._mutate(f"group {group}", apply)
        self.message_win.info(f"{solid} added to group {group}")

    def _on_property_changed(self, kind: str, name: str, field: str, value: str) -> None:
        if not name or not value:
            return
        if field == "name" and kind in ("solid", "component"):
            folders, _solid = split_solid_path(name)
            new_full = value if ":" in value else "/".join(folders) + ":" + value
            if new_full != name:
                self._nav_rename("solid", f"{name}\n{new_full}")
            return
        if field == "name" and kind == "material":
            if value != name:
                self._nav_rename("material", f"{name}\n{value}")
            return
        if field == "material" and kind in ("solid", "component"):
            comp = self._find_component(name)
            if comp is None:
                return
            mats = (self._project_data or {}).get("materials") or []
            mat = next((m for m in mats if m.get("name") == value), None)

            def apply():
                comp["material"] = value
                if mat and mat.get("colour"):
                    comp["colour"] = mat["colour"]
                append_change_material(self._archive, name, value)
                self._refresh_geometry()

            self._mutate(f"material {value}", apply)
            return
        coll = {"port": "ports", "ports": "ports", "monitor": "monitors",
                "probe": "probes"}.get(kind)
        if coll:
            rec = self._find_named(coll, name)
            if rec is None:
                return
            if field == "name" and value == name:
                return
            if field == "impedance" and str(rec.get("impedance") or "") == value:
                return
            pmap = {"x1": 0, "y1": 1, "z1": 2, "x2": 0, "y2": 1, "z2": 2}

            def apply():
                old_name = rec.get("name")
                if coll == "ports" and field in pmap:
                    p1 = list(rec.get("p1") or ("0", "0", "0"))
                    p2 = list(rec.get("p2") or ("0", "0", "0"))
                    idx = pmap[field]
                    if field in ("x1", "y1", "z1"):
                        p1[idx] = value
                    else:
                        p2[idx] = value
                    rec["p1"], rec["p2"] = tuple(p1), tuple(p2)
                elif coll == "probes" and field in ("x", "y", "z"):
                    rec[field] = value
                    rec["p1"] = (rec.get("x", "0"), rec.get("y", "0"),
                                 rec.get("z", "0"))
                elif field == "name":
                    rec["name"] = value
                    if coll == "ports":
                        rec["label"] = value
                else:
                    rec[field] = value
                eval_excitations(self._project_data)
                self._rewrite_excitation_history(coll, rec, old_name=old_name)
                self._refresh_geometry()

            self._mutate(f"edit {name} {field}", apply)
            return

    # ------------------------------------------------------------------ file

    def _nyi(self, name: str = "") -> None:
        label = name or "This command"
        self.message_win.info(f"{label} is not yet available.")
        self.status.showMessage(f"{label}: not implemented", 2500)

    def _sync_title(self) -> None:
        name = os.path.basename(self._current_path) if self._current_path else "untitled.cst"
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"{star}{name} — CST Decoding")

    def _mark_dirty(self, dirty: bool = True) -> None:
        self._dirty = bool(dirty)
        self._sync_title()

    def _snapshot(self) -> dict:
        return snapshot_state(self._project_data, self._archive, self._hidden_parts)

    def _restore_snapshot(self, snap: dict) -> None:
        self._restoring = True
        try:
            self._project_data = copy.deepcopy(snap.get("project") or {})
            self._archive = dict(snap.get("archive") or {})
            self._hidden_parts = set(snap.get("hidden") or [])
            self._reload_views()
            self._mark_dirty(True)
        finally:
            self._restoring = False

    def _reload_views(self) -> None:
        data = self._project_data or {}
        self.nav_tree.populate_from_project(data)
        self.nav_tree.set_hidden_names(self._hidden_parts)
        self.param_list.set_parameters(data.get("parameters") or [])
        self.progress_panel.set_progress(data.get("progress") or [])
        self._sync_viewports(data)
        if self._selected_solid:
            self.nav_tree.select_by_name(self._selected_solid, emit=False)
            self.viewport.select_solid(self._selected_solid)

    def _mutate(self, label: str, fn) -> None:
        if self._restoring:
            fn()
            return
        before = self._snapshot()
        fn()
        after = self._snapshot()
        self._undo.push(
            lambda s=before: self._restore_snapshot(s),
            lambda s=after: self._restore_snapshot(s),
            label)
        self._mark_dirty(True)

    def _on_undo(self) -> None:
        if not self._undo.can_undo():
            self.message_win.info("Nothing to undo.")
            return
        label = self._undo.undo()
        self.message_win.info(f"Undo {label}" if label else "Undo")
        self.status.showMessage(f"Undo {label}".strip(), 2000)

    def _on_redo(self) -> None:
        if not self._undo.can_redo():
            self.message_win.info("Nothing to redo.")
            return
        label = self._undo.redo()
        self.message_win.info(f"Redo {label}" if label else "Redo")
        self.status.showMessage(f"Redo {label}".strip(), 2000)

    def _on_parameters_changed(self, params: list) -> None:
        def apply():
            resolved = resolve_parameters(params)
            if self._project_data is None:
                self._project_data = {}
            self._project_data["parameters"] = resolved
            write_parameters(self._archive, resolved)
            eval_excitations(self._project_data)
            self.param_list.set_parameters(resolved)
            self._refresh_geometry()
        self._mutate("edit parameters", apply)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        ans = QMessageBox.question(
            self, "Unsaved changes",
            "Save changes to the current project?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)
        if ans == QMessageBox.Cancel:
            return False
        if ans == QMessageBox.Save:
            return self._on_save()
        return True

    def _on_new(self) -> None:
        if not self._confirm_discard():
            return
        files = new_project_files()
        self._archive = {name: data for name, data in files}
        self._eocd_comment = b"-cst-version:2024:0:cstdecoding\n"
        self._current_path = None
        entries = [{"name": n, "content": b} for n, b in files]
        self._apply_loaded_project("untitled.cst", entries, self._eocd_comment)
        self._undo.clear()
        self._mark_dirty(True)
        self.message_win.info("New project.")

    def _on_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CST Project", "",
            "CST Files (*.cst);;All Files (*)")
        if path:
            self._load_cst(path)

    def _archive_from_entries(self, entries) -> dict[str, bytes]:
        out = {}
        for e in entries:
            name = e["name"].replace("\\", "/")
            data = e.get("content")
            if data is None:
                continue
            out[name] = data
        return out

    def _on_save(self) -> bool:
        if not self._archive and not self._current_path:
            return self._on_save_as()
        if not self._current_path:
            return self._on_save_as()
        return self._write_project(self._current_path)

    def _on_save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CST Project",
            self._current_path or "untitled.cst",
            "CST Files (*.cst);;All Files (*)")
        if not path:
            return False
        if not path.lower().endswith(".cst"):
            path += ".cst"
        return self._write_project(path)

    def _write_project(self, path: str) -> bool:
        if not self._archive:
            self.message_win.warn("Nothing to save.")
            return False
        try:
            if self._project_data is not None:
                write_parameters(
                    self._archive, self._project_data.get("parameters") or [])
                write_hidden(self._archive, self._hidden_parts)
            files = list(self._archive.items())
            write_cst(path, files, comment=self._eocd_comment or None)
            self._current_path = path
            self._mark_dirty(False)
            self._add_recent(path)
            self.message_win.info(f"Saved {os.path.basename(path)}")
            self.status.showMessage(f"Saved {path}", 3000)
            return True
        except Exception as exc:
            self.message_win.error(f"Save failed: {exc}")
            return False

    def _on_export(self, path=None) -> None:
        if (path is None
                and getattr(self, "_view_stack", None) is not None
                and self._view_stack.currentWidget() is self.result_plot):
            self._on_export_plot()
            return
        if path is None:
            if not self._want_dialogs():
                self.message_win.info("Export SAT: no path.")
                return
            path, filt = QFileDialog.getSaveFileName(
                self, "Export CAD", "model.sat",
                "SAT ASCII (*.sat);;STEP (*.stp *.step)")
            if not path:
                return
        try:
            lower = str(path).lower()
            if lower.endswith((".stp", ".step")):
                from cst_cad import write_step
                if not write_step(path, self._project_data):
                    self.message_win.info(
                        "STEP export needs OpenCASCADE or CadQuery. Use SAT.")
                    return
            else:
                if not lower.endswith(".sat"):
                    path = str(path) + ".sat"
                from cst_cad import write_sat
                write_sat(path, self._project_data)
            self.message_win.info(f"Exported {os.path.basename(path)}")
        except Exception as exc:
            self.message_win.error(f"Export failed: {exc}")

    def _on_import(self, path=None) -> None:
        if path is None:
            if not self._want_dialogs():
                self.message_win.info("Import SAT: no path.")
                return
            path, _ = QFileDialog.getOpenFileName(
                self, "Import SAT", "",
                "SAT ASCII (*.sat);;All Files (*)")
            if not path:
                return
        try:
            from cst_cad import sat_to_components
            text = open(path, encoding="utf-8", errors="replace").read()
            comps = sat_to_components(text)
            if not comps:
                self.message_win.warn("Import SAT: no solids in file.")
                return

            def apply():
                bucket = self._project_data.setdefault("components", [])
                names = {c.get("name") for c in bucket}
                for rec in comps:
                    name = rec.get("name") or "solid"
                    if name in names:
                        name = unique_solid_name(names, "imported",
                                                 name.split(":")[-1])
                        rec = dict(rec)
                        rec["name"] = name
                    names.add(name)
                    bucket.append(rec)
                self._refresh_geometry()

            self._mutate("import sat", apply)
            self.message_win.info(
                f"Imported {len(comps)} solid(s) from {os.path.basename(path)}")
        except Exception as exc:
            self.message_win.error(f"Import failed: {exc}")

    def _show_viewport(self) -> None:
        if getattr(self, "_view_stack", None) is None:
            return
        if self._quad_mode:
            self._view_stack.setCurrentWidget(self.quad_view)
        else:
            self._view_stack.setCurrentWidget(self.viewport)

    def _show_plot(self) -> None:
        if getattr(self, "_view_stack", None) is not None:
            self._view_stack.setCurrentWidget(self.result_plot)

    def _result_bytes(self, rec: dict) -> bytes:
        if rec.get("bytes"):
            return rec["bytes"]
        path = (rec.get("path") or "").replace("\\", "/")
        if path and path in self._archive:
            return self._archive[path]
        return b""

    def _open_result(self, rec: dict) -> None:
        data = self._result_bytes(rec)
        parsed = parse_result_bytes(data, rec.get("path") or rec.get("name") or "")
        parsed["name"] = rec.get("name") or parsed.get("name") or ""
        if not parsed.get("title"):
            parsed["title"] = parsed["name"]
        self._result_rec = parsed
        empty = "No sampled curve in this result (plot template only)."
        if result_has_curve(parsed) or result_has_grid(parsed):
            empty = ""
        self.result_plot.set_result(parsed, empty)
        self._show_plot()
        n = len(parsed.get("x") or [])
        if n >= 2:
            self.message_win.info(f"Result: {parsed['name']}  {n} samples")
            self._status_mode.setText("1D Plot")
        elif result_has_grid(parsed):
            self.message_win.info(f"Result: {parsed['name']}  farfield grid")
            self._status_mode.setText("Farfield")
        else:
            self.message_win.info(f"Result: {parsed['name']}  (template, no samples)")
            self._status_mode.setText("Result")

    def _show_result_kind(self, kind: str) -> None:
        data = self._project_data or {}
        bucket = {
            "result_1d": data.get("results_1d") or [],
            "result_2d": data.get("results_2d") or [],
            "farfield": data.get("farfields") or [],
        }.get(kind) or []
        if not bucket:
            self.result_plot.set_result({}, "No results in this project.")
            self._show_plot()
            self.message_win.info("No results of that type.")
            return
        self._open_result(bucket[0])

    def _on_export_plot(self) -> None:
        rec = self._result_rec or {}
        if not result_has_curve(rec) and not result_has_grid(rec):
            self.message_win.warn("Nothing to export — select a result with samples.")
            return
        path, filt = QFileDialog.getSaveFileName(
            self, "Export result",
            (rec.get("name") or "result") + ".csv",
            "CSV (*.csv);;PNG (*.png)")
        if not path:
            return
        try:
            if path.lower().endswith(".png") or "PNG" in (filt or ""):
                if not path.lower().endswith(".png"):
                    path += ".png"
                self.result_plot.to_pixmap().save(path, "PNG")
            else:
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                from cst_results import curve_to_csv
                open(path, "w", encoding="utf-8").write(curve_to_csv(rec))
            self.message_win.info(f"Exported {os.path.basename(path)}")
        except Exception as exc:
            self.message_win.error(f"Export failed: {exc}")

    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About CST Decoding",
            "CST Decoding — reverse engineering, viewer, and editor\n"
            "for CST Studio Suite project files.\n\n"
            "Not a solver: simulation kernels are out of scope.\n"
            "Formats: DE-ZIP .cst, ACIS SAB, Model.mod, Parameters.json.",
        )

    def _add_recent(self, path: str) -> None:
        path = os.path.abspath(path)
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:12]
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        if not self._recent:
            act = self._recent_menu.addAction("(empty)")
            act.setEnabled(False)
            return
        for path in self._recent:
            act = self._recent_menu.addAction(path)
            act.triggered.connect(lambda _=False, p=path: self._load_cst(p))

    # ------------------------------------------------------------------ load

    def _load_cst(self, path: str, *, load_sab: bool = True) -> None:
        self.message_win.info(f"Loading: {path}")
        self._status_progress.setVisible(True)
        self._status_progress.setValue(0)
        try:
            self._status_progress.setValue(10)
            meta, entries = open_cst(path)
            self.message_win.info(f"Found {len(entries)} entries in container.")
            self._status_progress.setValue(40)
            self._archive = self._archive_from_entries(entries)
            self._eocd_comment = meta.get("comment_bytes") or b""
            self._apply_loaded_project(path, entries, self._eocd_comment,
                                       load_sab=load_sab)
            self._status_progress.setValue(100)
            self._current_path = path
            self._undo.clear()
            self._mark_dirty(False)
            self._add_recent(path)
            self.status.showMessage(f"Loaded {os.path.basename(path)}")
            self.message_win.info("Project loaded successfully.")
        except CstParseError as exc:
            self.message_win.error(f"Parse error: {exc}")
        except Exception as exc:
            self.message_win.error(f"Error loading: {type(exc).__name__}: {exc}")
            traceback.print_exc()
        finally:
            self._status_progress.setVisible(False)

    def _apply_loaded_project(self, path, entries, comment=b"",
                             load_sab: bool = True) -> None:
        self._project_data = self._build_project_data(
            path, entries, comment, load_sab=load_sab)
        from cst_mesh import summarize_modelcache
        self._project_data["modelcache"] = summarize_modelcache(self._archive)
        self._hidden_parts.clear()
        self._selected_solid = ""
        hid = archive_get(self._archive, "Model/3D/Model.hid")
        if hid:
            self._hidden_parts = parse_hidden_solids(
                hid.decode("latin-1", "replace"))
        self.nav_tree.populate_from_project(self._project_data)
        self.nav_tree.set_hidden_names(self._hidden_parts)
        self.param_list.set_parameters(self._project_data.get("parameters", []))
        self.progress_panel.set_progress(self._project_data.get("progress", []))
        self._sync_viewports(self._project_data)
        self._apply_units_status()
        self._sync_title()

    def _apply_units_status(self) -> None:
        units = self._project_data.get("units") or {}
        length = units.get("length", "mm")
        freq = units.get("frequency", "GHz")
        time_u = units.get("time", "ns")
        fmin, fmax = units.get("fmin"), units.get("fmax")
        self._status_units.setText(f"Units: {length}  {freq}  {time_u}  K")
        if fmin is not None and fmax is not None:
            self._status_dim.setText(f"f = {fmin} – {fmax} {freq}")
        else:
            self._status_dim.setText("Normal")

    def _entry_bytes(self, cst_path, entry) -> bytes:
        data = entry.get("content")
        if data is not None:
            return data
        name = entry.get("name", "").replace("\\", "/")
        if name in self._archive:
            return self._archive[name]
        with open(cst_path, "rb") as f:
            content, _crc_ok, _ = read_entry(f, entry)
        return content

    def _build_project_data(self, cst_path, entries, comment=b"",
                           load_sab: bool = True) -> dict:
        data = {
            "name": os.path.basename(cst_path),
            "components": [],
            "materials": [],
            "ports": [],
            "monitors": [],
            "groups": [],
            "faces": [],
            "curves": [],
            "wcs": [],
            "probes": [],
            "lumped": [],
            "parameters": [],
            "progress": [],
            "units": {},
            "results_1d": [],
            "results_2d": [],
            "farfields": [],
            "tables": [],
            "mesh_properties": {},
            "modelcache": {},
        }
        parsed: dict = {}
        mod_entry = params_entry = history_entry = None
        for e in entries:
            name = e["name"].replace("\\", "/")
            if name.endswith("Model/3D/Model.mod"):
                mod_entry = e
            if name.endswith("Model/Parameters.json"):
                params_entry = e
            if name.endswith("Model/3D/ModelHistory.json") or name.endswith(
                    "Model/ModelHistory.json"):
                history_entry = e

        if mod_entry:
            try:
                content = self._entry_bytes(cst_path, mod_entry)
                parsed = self._parse_model_mod(content.decode("latin1"))
                for key in ("components", "materials", "ports", "monitors",
                            "groups", "faces", "curves", "wcs", "probes",
                            "lumped", "units", "mesh_properties"):
                    if key in parsed and parsed[key]:
                        data[key] = parsed[key]
                data["_solid_materials"] = parsed.get("_solid_materials") or {}
                self.message_win.info(
                    f"Parsed Model.mod: {len(content):,} bytes — "
                    f"{len(data['components'])} comps, {len(data['materials'])} mats, "
                    f"{len(data['ports'])} ports, {len(data['monitors'])} monitors")
            except Exception as exc:
                self.message_win.warn(f"Could not parse Model.mod: {exc}")

        if params_entry:
            try:
                content = self._entry_bytes(cst_path, params_entry)
                params_json = json.loads(content)
                for rec in params_json.get("parameters", []):
                    data["parameters"].append({
                        "name": rec.get("name", ""),
                        "expr": rec.get("expr", ""),
                        "value": rec.get("value", ""),
                        "description": rec.get("descr", rec.get("description", "")),
                    })
                self.message_win.info(f"Loaded {len(data['parameters'])} parameters")
            except Exception as exc:
                self.message_win.warn(f"Could not parse Parameters.json: {exc}")

        if history_entry:
            try:
                content = self._entry_bytes(cst_path, history_entry)
                history_json = json.loads(content)
                general = history_json.get("general") or {}
                if general:
                    freq = general.get("frequency") or {}
                    data["units"].update({
                        "length": general.get("length", data["units"].get("length", "mm")),
                        "frequency": freq.get("unit", data["units"].get("frequency", "GHz"))
                        if isinstance(freq, dict) else data["units"].get("frequency", "GHz"),
                        "time": general.get("time", data["units"].get("time", "ns")),
                        "fmin": freq.get("minimum") if isinstance(freq, dict) else None,
                        "fmax": freq.get("maximum") if isinstance(freq, dict) else None,
                    })
                    data["progress"].append(
                        (f"CST {general.get('version', '')}  ACIS {general.get('acis', '')}",
                         "History"))
                for hop in history_json.get("history", [])[:80]:
                    cap = hop.get("caption") or hop.get("type") or "op"
                    data["progress"].append((cap, "history"))
            except Exception:
                pass

        for se in entries:
            n = se["name"].replace("\\", "/")
            low = n.lower()
            if low.endswith(".sab"):
                data["progress"].append((os.path.basename(n), "Imported SAB"))
            elif low.endswith(".sat"):
                data["progress"].append((os.path.basename(n), "Imported SAT"))
            elif low.endswith(".r1d"):
                data["results_1d"].append({
                    "name": os.path.splitext(os.path.basename(n))[0],
                    "path": n, "format": "r1d",
                })
            elif low.endswith(".r0d"):
                data["results_2d"].append({
                    "name": os.path.splitext(os.path.basename(n))[0],
                    "path": n, "format": "r0d",
                })
            elif low.endswith(".dat") and (
                    "/result" in low or "farfield" in low or n.lower().count("farfield")):
                data["farfields"].append({
                    "name": os.path.splitext(os.path.basename(n))[0],
                    "path": n, "format": "farfield",
                })
            elif low.endswith(".txt") and "/result" in low:
                data["tables"].append({
                    "name": os.path.splitext(os.path.basename(n))[0],
                    "path": n, "format": "ascii",
                })

        sab_comps = self._load_sab_components(cst_path, entries) if load_sab else []
        if sab_comps:
            mat_override = parsed.get("_solid_materials") or {}
            for comp in sab_comps:
                new_mat = mat_override.get(comp["name"])
                if new_mat:
                    comp["material"] = new_mat
            # Keep parametric bricks; imported SAB replaces the fake
            # same-bbox solids that used to be synthesised from .mod.
            bricks = [c for c in data["components"] if c.get("source") != "sab"]
            data["components"] = sab_comps + bricks
            n_mesh = sum(1 for c in sab_comps if c.get("mesh"))
            n_tri = sum(len(c["mesh"]["faces"]) for c in sab_comps if c.get("mesh"))
            self.message_win.info(
                f"SAB geometry: {len(sab_comps)} bodies, "
                f"{n_mesh} tessellated, {n_tri} triangles")

        if comment:
            meta = comment.decode("utf-8", "replace")
            if "cst-version" in meta:
                ver = meta.split("cst-version:", 1)[-1].split("-")[0]
                self.message_win.info(f"CST Version: {ver}")

        if not data["progress"]:
            data["progress"] = [("Project loaded", "Ready")]
        if not data["components"]:
            self.message_win.warn(
                "No solid geometry (no Bricks in .mod and no SAB bodies).")
        self.message_win.info(
            f"Project: {data['name']} — {len(entries)} entries, "
            f"{len(data['components'])} components, "
            f"{len(data['materials'])} materials, "
            f"{len(data['ports'])} ports")
        eval_excitations(data)
        return data

    def _load_sab_components(self, cst_path, entries) -> list:
        """Read imported / cache SAB members and turn ACIS bodies into solids."""
        sab_entries = []
        for e in entries:
            n = e["name"].replace("\\", "/")
            if n.lower().endswith(".sab"):
                # Prefer Model/3D CAD imports over ModelCache bbox segments.
                rank = 0 if "/3D/" in n or n.startswith("Model/3D/") else 1
                sab_entries.append((rank, n, e))
        sab_entries.sort(key=lambda t: (t[0], t[1]))
        all_bodies: list[dict] = []
        seen_names: set[str] = set()
        for _rank, n, entry in sab_entries:
            try:
                content = self._entry_bytes(cst_path, entry)
                bodies = extract_bodies(content)
            except Exception as exc:
                self.message_win.warn(f"Could not parse {os.path.basename(n)}: {exc}")
                continue
            if not bodies:
                continue
            self.message_win.info(
                f"{os.path.basename(n)}: {len(bodies)} ACIS bodies")
            for b in bodies:
                if b["name"] in seen_names:
                    continue
                seen_names.add(b["name"])
                all_bodies.append(b)
            # One imported CAD file is enough for the 3D view.
            if _rank == 0 and all_bodies:
                break
        return all_bodies

    def _parse_model_mod(self, text: str) -> dict:
        result = {
            "components": [], "materials": [], "ports": [], "monitors": [],
            "groups": [], "faces": [], "curves": [], "wcs": [],
            "probes": [], "lumped": [], "units": {},
            "_solid_materials": {},
            "mesh_properties": {},
        }

        geom = re.search(r'\.Geometry\s+"([^"]+)"', text) or re.search(
            r'\.SetUnit\s+"Length"\s*,\s*"([^"]+)"', text)
        freq_u = re.search(r'\.Frequency\s+"([^"]+)"', text) or re.search(
            r'\.SetUnit\s+"Frequency"\s*,\s*"([^"]+)"', text)
        time_u = re.search(r'\.Time\s+"([^"]+)"', text)
        frange = re.search(r'Solver\.FrequencyRange\s+"([^"]+)"\s*,\s*"([^"]+)"', text)
        result["units"] = {
            "length": geom.group(1) if geom else "mm",
            "frequency": freq_u.group(1) if freq_u else "GHz",
            "time": time_u.group(1) if time_u else "ns",
            "fmin": frange.group(1) if frange else None,
            "fmax": frange.group(2) if frange else None,
        }
        from cst_mesh import parse_mesh_properties
        result["mesh_properties"] = parse_mesh_properties(text)

        seen_materials = set()
        for m in re.finditer(r"With Material\s+(.*?)End With", text, re.S):
            block = m.group(1)
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            if not name_m:
                continue
            mat_name = name_m.group(1)
            if mat_name in seen_materials:
                continue
            seen_materials.add(mat_name)
            eps_match = re.search(r'\.Epsilon\s+"?([\d.eE+-]+)"?', block)
            mu_match = re.search(r'\.Mu\s+"?([\d.eE+-]+)"?', block)
            color_match = re.search(
                r'\.Colour\s+"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', block)
            folder_match = re.search(r'\.Folder\s+"([^"]+)"', block)
            mat_type_match = re.search(r'\.Type\s+"([^"]+)"', block)
            colour = ""
            if color_match:
                try:
                    colour = ",".join(
                        f"{float(color_match.group(i)):.2f}" for i in range(1, 4))
                except ValueError:
                    pass
            result["materials"].append({
                "name": mat_name,
                "epsilon": eps_match.group(1) if eps_match else "",
                "mu": mu_match.group(1) if mu_match else "",
                "type": mat_type_match.group(1) if mat_type_match else "Normal",
                "folder": folder_match.group(1) if folder_match else "",
                "colour": colour,
            })

        group_defs: dict[str, dict] = {}
        for m in re.finditer(r'Group\.Add\s+"([^"]+)"\s*,\s*"([^"]*)"', text):
            group_name, group_type = m.group(1), m.group(2)
            group_defs.setdefault(
                group_name, {"name": group_name, "type": group_type, "items": []})
        for m in re.finditer(
                r'Group\.AddItem\s+"solid\\?\$([^"]+)"\s*,\s*"([^"]+)"', text):
            solid_path, group_name = m.group(1), m.group(2)
            group_defs.setdefault(
                group_name, {"name": group_name, "type": "", "items": []})
            group_defs[group_name]["items"].append(solid_path)
        result["groups"] = list(group_defs.values())

        solid_materials = {}
        for m in re.finditer(
                r'Solid\.ChangeMaterial\s+"([^"]+)"\s*,\s*"([^"]+)"', text):
            solid_materials[m.group(1)] = m.group(2)
        result["_solid_materials"] = solid_materials

        subvolume_bounds = None
        for m in re.finditer(
                r'\.SetSubvolume\s+"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"'
                r'\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', text):
            try:
                sv = [float(m.group(i)) for i in range(1, 7)]
            except (ValueError, TypeError):
                continue
            if subvolume_bounds is None:
                subvolume_bounds = sv
            else:
                for j in range(3):
                    subvolume_bounds[2 * j] = min(subvolume_bounds[2 * j], sv[2 * j])
                    subvolume_bounds[2 * j + 1] = max(
                        subvolume_bounds[2 * j + 1], sv[2 * j + 1])
        if subvolume_bounds:
            result["_subvolume_bounds"] = tuple(subvolume_bounds)

        def _float_pair(match, default):
            if not match:
                return default
            try:
                return float(match.group(1)), float(match.group(2))
            except (ValueError, TypeError):
                return default

        for block in re.findall(r"With Brick\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            comp_m = re.search(r'\.Component\s+"([^"]+)"', block)
            mat_m = re.search(r'\.Material\s+"([^"]+)"', block)
            xr = re.search(r'\.Xrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
            yr = re.search(r'\.Yrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
            zr = re.search(r'\.Zrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
            xmin, xmax = _float_pair(xr, (-100, 100))
            ymin, ymax = _float_pair(yr, (-100, 100))
            zmin, zmax = _float_pair(zr, (-10, 10))
            result["components"].append({
                "name": f"{comp_m.group(1) if comp_m else 'Default'}:"
                        f"{name_m.group(1) if name_m else 'Brick'}",
                "material": mat_m.group(1) if mat_m else "PEC",
                "bounds": (xmin, xmax, ymin, ymax, zmin, zmax),
            })

        for block in re.findall(r"With Cylinder\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            comp_m = re.search(r'\.Component\s+"([^"]+)"', block)
            mat_m = re.search(r'\.Material\s+"([^"]+)"', block)
            r_m = (re.search(r'\.OuterRadius\s+"([^"]*)"', block)
                   or re.search(r'\.Radius\s+"([^"]*)"', block))
            zr = re.search(r'\.Zrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
            h_m = re.search(r'\.Height\s+"([^"]*)"', block)
            cx_m = re.search(r'\.Xcenter\s+"([^"]*)"', block)
            cy_m = re.search(r'\.Ycenter\s+"([^"]*)"', block)
            try:
                radius = float(r_m.group(1)) if r_m else 10.0
                if zr:
                    zmin, zmax = float(zr.group(1)), float(zr.group(2))
                else:
                    height = float(h_m.group(1)) if h_m else 20.0
                    zmin, zmax = -height / 2, height / 2
                cx = float(cx_m.group(1)) if cx_m else 0.0
                cy = float(cy_m.group(1)) if cy_m else 0.0
                bounds = (cx - radius, cx + radius, cy - radius, cy + radius,
                          zmin, zmax)
            except (ValueError, TypeError):
                bounds = (-10, 10, -10, 10, -10, 10)
            result["components"].append({
                "name": f"{comp_m.group(1) if comp_m else 'Default'}:"
                        f"{name_m.group(1) if name_m else 'Cylinder'}",
                "material": mat_m.group(1) if mat_m else "PEC",
                "bounds": bounds,
            })

        for block in re.findall(r"With Sphere\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            comp_m = re.search(r'\.Component\s+"([^"]+)"', block)
            mat_m = re.search(r'\.Material\s+"([^"]+)"', block)
            r_m = (re.search(r'\.CenterRadius\s+"([^"]*)"', block)
                   or re.search(r'\.Radius\s+"([^"]*)"', block))
            c_m = re.search(r'\.Center\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"', block)
            try:
                radius = float(r_m.group(1)) if r_m else 10.0
                cx = float(c_m.group(1)) if c_m else 0.0
                cy = float(c_m.group(2)) if c_m else 0.0
                cz = float(c_m.group(3)) if c_m else 0.0
            except (ValueError, TypeError):
                radius, cx, cy, cz = 10.0, 0.0, 0.0, 0.0
            result["components"].append({
                "name": f"{comp_m.group(1) if comp_m else 'Default'}:"
                        f"{name_m.group(1) if name_m else 'Sphere'}",
                "material": mat_m.group(1) if mat_m else "PEC",
                "bounds": (cx - radius, cx + radius, cy - radius, cy + radius,
                           cz - radius, cz + radius),
            })

        for block in re.findall(r"With Torus\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            comp_m = re.search(r'\.Component\s+"([^"]+)"', block)
            mat_m = re.search(r'\.Material\s+"([^"]+)"', block)
            maj = re.search(r'\.OuterRadius\s+"([^"]*)"', block)
            mn = re.search(r'\.InnerRadius\s+"([^"]*)"', block)
            cx_m = re.search(r'\.Xcenter\s+"([^"]*)"', block)
            cy_m = re.search(r'\.Ycenter\s+"([^"]*)"', block)
            cz_m = re.search(r'\.Zcenter\s+"([^"]*)"', block)
            try:
                major = float(maj.group(1)) if maj else 8.0
                minor = float(mn.group(1)) if mn else 1.5
                cx = float(cx_m.group(1)) if cx_m else 0.0
                cy = float(cy_m.group(1)) if cy_m else 0.0
                cz = float(cz_m.group(1)) if cz_m else 0.0
            except (ValueError, TypeError):
                major, minor, cx, cy, cz = 8.0, 1.5, 0.0, 0.0, 0.0
            r = major + minor
            result["components"].append({
                "name": f"{comp_m.group(1) if comp_m else 'Default'}:"
                        f"{name_m.group(1) if name_m else 'Torus'}",
                "material": mat_m.group(1) if mat_m else "PEC",
                "bounds": (cx - r, cx + r, cy - r, cy + r, cz - minor, cz + minor),
            })

        for block in re.findall(r"With Cone\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            comp_m = re.search(r'\.Component\s+"([^"]+)"', block)
            mat_m = re.search(r'\.Material\s+"([^"]+)"', block)
            rb = re.search(r'\.OuterRadius\s+"([^"]*)"', block)
            rt = re.search(r'\.TopRadius\s+"([^"]*)"', block)
            zr = re.search(r'\.Zrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
            cx_m = re.search(r'\.Xcenter\s+"([^"]*)"', block)
            cy_m = re.search(r'\.Ycenter\s+"([^"]*)"', block)
            try:
                r_bot = float(rb.group(1)) if rb else 4.0
                r_top = float(rt.group(1)) if rt else 0.0
                zmin, zmax = (float(zr.group(1)), float(zr.group(2))) if zr else (0.0, 10.0)
                cx = float(cx_m.group(1)) if cx_m else 0.0
                cy = float(cy_m.group(1)) if cy_m else 0.0
            except (ValueError, TypeError):
                r_bot, r_top, zmin, zmax, cx, cy = 4.0, 0.0, 0.0, 10.0, 0.0, 0.0
            r = max(r_bot, r_top)
            result["components"].append({
                "name": f"{comp_m.group(1) if comp_m else 'Default'}:"
                        f"{name_m.group(1) if name_m else 'Cone'}",
                "material": mat_m.group(1) if mat_m else "PEC",
                "bounds": (cx - r, cx + r, cy - r, cy + r, zmin, zmax),
            })

        def _comp(name):
            for c in result["components"]:
                if c.get("name") == name:
                    return c
            return None

        for m in re.finditer(
                r'Solid\.(Add|Subtract|Intersect)\s+"([^"]+)"\s*,\s*"([^"]+)"',
                text):
            op, target, tool = m.group(1).lower(), m.group(2), m.group(3)
            a, b = _comp(target), _comp(tool)
            if a is None:
                continue
            if op == "add" and a.get("bounds") and b and b.get("bounds"):
                a["bounds"] = union_bounds(a["bounds"], b["bounds"])
            elif op == "intersect" and a.get("bounds") and b and b.get("bounds"):
                inter = intersect_bounds(a["bounds"], b["bounds"])
                if inter:
                    a["bounds"] = inter
            result["components"] = [
                c for c in result["components"] if c.get("name") != tool]

        for block in re.findall(r"With Transform\s+(.*?)End With", text, re.S):
            name_m = re.search(r'\.Name\s+"([^"]+)"', block)
            kind_m = re.search(r'\.Transform\s+"[^"]*"\s*,\s*"([^"]+)"', block)
            if not name_m or not kind_m:
                continue
            comp = _comp(name_m.group(1))
            if comp is None or not comp.get("bounds"):
                continue
            op = kind_m.group(1).lower()
            origin = bounds_center(comp["bounds"])
            try:
                if op == "translate":
                    vec = re.search(
                        r'\.Vector\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"',
                        block)
                    if not vec:
                        continue
                    fn = translate_fn(float(vec.group(1)), float(vec.group(2)),
                                      float(vec.group(3)))
                elif op == "rotate":
                    ang = re.search(
                        r'\.Angle\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"',
                        block)
                    if not ang:
                        continue
                    ax, ay, az = (float(ang.group(i)) for i in range(1, 4))
                    if abs(ax) >= abs(ay) and abs(ax) >= abs(az):
                        fn = rotate_fn("x", ax, origin)
                    elif abs(ay) >= abs(az):
                        fn = rotate_fn("y", ay, origin)
                    else:
                        fn = rotate_fn("z", az, origin)
                elif op == "mirror":
                    nrm = re.search(
                        r'\.PlaneNormal\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"',
                        block)
                    axis = "x"
                    if nrm:
                        nx, ny, nz = (float(nrm.group(i)) for i in range(1, 4))
                        axis = "x" if abs(nx) >= abs(ny) and abs(nx) >= abs(nz) else (
                            "y" if abs(ny) >= abs(nz) else "z")
                    fn = mirror_fn(axis, origin)
                elif op == "scale":
                    sc = re.search(
                        r'\.ScaleFactor\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"',
                        block)
                    if not sc:
                        continue
                    fn = scale_fn(origin[0], origin[1], origin[2],
                                  float(sc.group(1)), float(sc.group(2)),
                                  float(sc.group(3)))
                else:
                    continue
            except (ValueError, TypeError):
                continue
            updated = transform_component(comp, fn)
            comp["bounds"] = updated.get("bounds")
            if updated.get("mesh"):
                comp["mesh"] = updated["mesh"]

        # Imported SAT/SAB solids are filled later from the .sab body AABBs.
        # Do not stamp the field-monitor subvolume onto every solid — that is
        # what collapsed phone.cst into a single overlapping box.

        # Ports / monitors / probes are sequential: Create then Delete then
        # recreate must leave the last live object (property edits rewrite this way).
        events = []
        def _mark(kind, pattern):
            for m in re.finditer(pattern, text, re.S):
                events.append((m.start(), kind, m))

        _mark("discrete", r"With DiscretePort\s+(.*?)End With")
        _mark("face", r"With DiscreteFacePort\s+(.*?)End With")
        _mark("waveguide", r"With WaveguidePort\s+(.*?)End With")
        _mark("port", r"With Port\s+(.*?)End With")
        _mark("pdel", r'Port\.Delete\s+"([^"]+)"')
        _mark("monitor", r"With Monitor\s+(.*?)End With")
        _mark("fieldmon", r"With FieldMonitor\s+(.*?)End With")
        _mark("sparam", r"With SParameterMonitor\s+(.*?)End With")
        _mark("voltage", r"With VoltageMonitor\s+(.*?)End With")
        _mark("mdel", r'Monitor\.Delete\s+"([^"]+)"')
        _mark("probe", r"With Probe\s+(.*?)End With")
        _mark("prdel", r'Probe\.Delete\s+"([^"]+)"')
        events.sort(key=lambda t: t[0])

        def _upsert(lst, rec, key):
            k = rec.get(key)
            for i, old in enumerate(lst):
                if old.get(key) == k:
                    lst[i] = rec
                    return
            lst.append(rec)

        def _drop(lst, pred):
            lst[:] = [x for x in lst if not pred(x)]

        for _pos, kind, m in events:
            if kind == "discrete":
                _upsert(result["ports"], self._parse_discrete_port_block(m.group(1)),
                        "port_number")
            elif kind == "face":
                result["ports"].append(self._parse_face_port_block(
                    m.group(1), len(result["ports"])))
            elif kind == "waveguide":
                _upsert(result["ports"],
                        self._parse_waveguide_block(m.group(1), result),
                        "port_number")
            elif kind == "port":
                block = m.group(1)
                if re.search(r'\.Orientation\s+"', block) or re.search(
                        r'\.NumberOfModes\s+"', block):
                    _upsert(result["ports"],
                            self._parse_waveguide_block(block, result),
                            "port_number")
            elif kind == "pdel":
                arg = m.group(1)
                _drop(result["ports"],
                      lambda p, a=arg: str(p.get("port_number")) == a
                      or p.get("name") == a)
            elif kind in ("monitor", "fieldmon"):
                rec = self._parse_monitor_block(m.group(1), kind)
                if rec:
                    _upsert(result["monitors"], rec, "name")
            elif kind == "sparam":
                name_m = re.search(r'\.Name\s+"([^"]+)"', m.group(1))
                rec = {
                    "name": name_m.group(1) if name_m else "SParam",
                    "field_type": "S-Parameters",
                }
                _upsert(result["monitors"], rec, "name")
            elif kind == "voltage":
                name_m = re.search(r'\.Name\s+"([^"]+)"', m.group(1))
                rec = {
                    "name": name_m.group(1) if name_m else "Voltage",
                    "field_type": "Voltage",
                }
                _upsert(result["monitors"], rec, "name")
            elif kind == "mdel":
                arg = m.group(1)
                _drop(result["monitors"], lambda x, a=arg: x.get("name") == a)
            elif kind == "probe":
                rec = self._parse_probe_block(m.group(1))
                if rec:
                    _upsert(result["probes"], rec, "name")
            elif kind == "prdel":
                arg = m.group(1)
                _drop(result["probes"], lambda x, a=arg: x.get("name") == a)

        for kind, pattern, dest in (
                ("faces", r"With Face\s+(.*?)End With", "faces"),
                ("curves", r"With Curve\s+(.*?)End With", "curves"),
                ("wcs", r"With WCS\s+(.*?)End With", "wcs"),
                ("lumped", r"With LumpedElement\s+(.*?)End With", "lumped"),
        ):
            for block in re.findall(pattern, text, re.S):
                name_m = re.search(r'\.Name\s+"([^"]+)"', block)
                if name_m:
                    result[dest].append({"name": name_m.group(1)})
        for ws_name in re.findall(r'WCS\.Store\s+"([^"]+)"', text):
            if not any(w["name"] == ws_name for w in result["wcs"]):
                result["wcs"].append({"name": ws_name})
        return result

    def _parse_discrete_port_block(self, block: str) -> dict:
        pnum_m = re.search(r'\.PortNumber\s+"(\d+)"', block)
        imp_m = re.search(r'\.Impedance\s+"([^"]+)"', block)
        name_m = re.search(r'\.Name\s+"([^"]+)"', block)
        label_m = re.search(r'\.Label\s+"([^"]+)"', block)
        type_m = re.search(r'\.Type\s+"([^"]+)"', block)
        p1 = parse_set_point(block, "SetP1")
        p2 = parse_set_point(block, "SetP2")
        pnum = pnum_m.group(1) if pnum_m else "1"
        label = (label_m.group(1) if label_m else "") or ""
        return {
            "name": (name_m.group(1) if name_m else "") or label or f"port{pnum}",
            "port_number": int(pnum) if pnum.isdigit() else 1,
            "impedance": imp_m.group(1) if imp_m else "50",
            "type": type_m.group(1) if type_m else "Discrete",
            "kind": "Discrete",
            "label": label,
            "p1": p1,
            "p2": p2,
        }

    def _parse_face_port_block(self, block: str, index: int) -> dict:
        name_m = re.search(r'\.Name\s+"([^"]+)"', block)
        label_m = re.search(r'\.Label\s+"([^"]+)"', block)
        pnum_m = re.search(r'\.PortNumber\s+"(\d+)"', block)
        type_m = re.search(r'\.Type\s+"([^"]+)"', block)
        face_m = re.search(r'\.FaceType\s+"([^"]+)"', block)
        pnum = int(pnum_m.group(1)) if pnum_m else index + 1
        return {
            "name": name_m.group(1) if name_m else (
                label_m.group(1) if label_m else f"FacePort_{index}"),
            "port_number": pnum,
            "impedance": "50",
            "type": f"Face {type_m.group(1) if type_m else 'SParameter'}"
                    f" ({face_m.group(1) if face_m else 'Linear'})",
            "kind": "Face",
        }

    def _parse_monitor_block(self, block: str, kind: str) -> dict | None:
        ft_m = re.search(r'\.FieldType\s+"([^"]+)"', block)
        name_m = re.search(r'\.Name\s+"([^"]+)"', block)
        fv_m = re.search(r'\.MonitorValue\s+"([^"]+)"', block)
        dim_m = re.search(r'\.Dimension\s+"([^"]+)"', block)
        dom_m = re.search(r'\.Domain\s+"([^"]+)"', block)
        default = "FieldMonitor" if kind == "fieldmon" else "Monitor"
        mname = name_m.group(1) if name_m else default
        return {
            "name": mname,
            "field_type": ft_m.group(1) if ft_m else "?",
            "frequency": fv_m.group(1) if fv_m else "",
            "domain": dom_m.group(1) if dom_m else "Frequency",
            "dimension": dim_m.group(1) if dim_m else "Volume",
        }

    def _parse_probe_block(self, block: str) -> dict | None:
        name_m = re.search(r'\.Name\s+"([^"]+)"', block)
        loc = re.search(
            r'\.Location\s+"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"', block)
        pos = parse_set_point(block, "SetPosition1")
        if pos is None:
            pos = parse_set_point(block, "SetPosition")
        if pos is None and loc:
            pos = (loc.group(1), loc.group(2), loc.group(3))
        field = (re.search(r'\.FieldName\s+"([^"]+)"', block)
                 or re.search(r'\.FieldType\s+"([^"]+)"', block)
                 or re.search(r'\.Field\s+"([^"]+)"', block))
        ori = re.search(r'\.Orientation\s+"([^"]+)"', block)
        rec = {
            "name": name_m.group(1) if name_m else "probe",
            "field_type": field.group(1) if field else "efield",
            "orientation": ori.group(1) if ori else "X",
        }
        if pos:
            rec["x"], rec["y"], rec["z"] = pos
            rec["p1"] = pos
        return rec

    def _parse_waveguide_block(self, block: str, result: dict) -> dict:
        pnum_m = re.search(r'\.PortNumber\s+"(\d+)"', block)
        imp_m = re.search(r'\.Impedance\s+"([^"]+)"', block)
        name_m = re.search(r'\.Name\s+"([^"]+)"', block)
        label_m = re.search(r'\.Label\s+"([^"]+)"', block)
        ori_m = re.search(r'\.Orientation\s+"([^"]+)"', block)
        xr = re.search(r'\.Xrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
        yr = re.search(r'\.Yrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
        zr = re.search(r'\.Zrange\s+"([^"]*)"\s*,\s*"([^"]*)"', block)
        pnum = pnum_m.group(1) if pnum_m else str(len(result["ports"]) + 1)
        rec = {
            "name": (name_m.group(1) if name_m else "")
                    or (label_m.group(1) if label_m else "")
                    or f"port{pnum}",
            "port_number": int(pnum) if pnum.isdigit() else len(result["ports"]) + 1,
            "impedance": imp_m.group(1) if imp_m else "50",
            "type": "Waveguide",
            "kind": "Waveguide",
            "orientation": ori_m.group(1) if ori_m else "",
        }
        if xr:
            rec["xrange"] = (xr.group(1), xr.group(2))
        if yr:
            rec["yrange"] = (yr.group(1), yr.group(2))
        if zr:
            rec["zrange"] = (zr.group(1), zr.group(2))
        return rec


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("CST Studio Suite 2024")
    path = sys.argv[1] if len(sys.argv) > 1 else None
    window = CSTMainWindow(path)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
