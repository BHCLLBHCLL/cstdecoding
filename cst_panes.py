# -*- coding: utf-8 -*-
"""CST-style panes for cst_gui: Navigation Tree, Properties, Messages, Parameter List.

Layout / chrome follow CST DESIGN ENVIRONMENT (Navigation Tree, Parameter List)
plus cabdecoding PaneFrame / MessageWindow / Property inspector patterns.
"""

from __future__ import annotations

import math
import os
from datetime import datetime

from html import escape as _html_escape

from PyQt5.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMenu, QProxyStyle, QStyle, QTableWidget, QTableWidgetItem,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from cst_icons import AppIcons
from sab_bodies import opacity_for

try:
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    import vtk
    try:
        import vtkmodules.vtkInteractionStyle  # noqa: F401
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    except Exception:
        pass
    _HAS_VTK = True
except Exception:
    _HAS_VTK = False
    vtk = None
    QVTKRenderWindowInteractor = None


# CST DESIGN ENVIRONMENT Navigation Tree (from UI + Model.mod Group/Solid/Folder)
NAV_TREE_ITEMS = [
    ("Components", "collection", []),
    ("Groups", "collection", [
        ("Excluded from Simulation", "collection", []),
        ("Excluded from Bounding Box", "collection", []),
        ("Mesh Groups", "meshgroup", []),
    ]),
    ("Materials", "collection", []),
    ("Faces", "collection", []),
    ("Curves", "collection", []),
    ("WCS", "collection", []),
    ("Anchor Points", "collection", []),
    ("Wires", "collection", []),
    ("Voxel Data", "collection", []),
    ("Dimensions", "gear", []),
    ("Lumped Elements", "gear", []),
    ("Plane Wave", "gear", []),
    ("Farfield Sources", "gear", []),
    ("Field Sources", "gear", []),
    ("Ports", "gear", []),
    ("Excitation Signals", "gear", []),
    ("Field Monitors", "gear", []),
    ("Voltage and Current Monitors", "gear", []),
    ("Probes", "gear", []),
    ("Mesh", "gear", []),
    ("1D Results", "results", []),
    ("2D/3D Results", "results", []),
    ("Farfields", "results", []),
    ("Tables", "results", []),
    ("codebook", "results", []),
]

NAV_ICON_MAP = {
    "component": "solid", "group": "collection", "material": "material",
    "faces": "collection", "curves": "collection", "wcs": "wcs",
    "anchor": "anchor", "wires": "wires", "dimensions": "gear",
    "lumped": "gear", "sources": "gear", "ports": "gear",
    "monitor": "gear", "voltage": "gear", "probe": "gear",
    "mesh": "gear", "1d": "results", "2d": "results", "farfield": "results",
    "tables": "results", "codebook": "results",
    "collection": "collection", "solid": "solid",
    "solid_excluded": "solid_excluded", "folder": "folder",
    "meshgroup": "meshgroup", "meshitem": "meshitem",
    "gear": "gear", "results": "results",
}

KIND_ROLE = Qt.UserRole
FULLNAME_ROLE = Qt.UserRole + 1
PAYLOAD_ROLE = Qt.UserRole + 2

_CST_GROUP_FIXED = ("Excluded from Simulation", "Excluded from Bounding Box")

_VIEW_KEY_TO_PLANE = {"x": "yz", "y": "xz", "z": "xy"}


def split_solid_path(full: str) -> tuple[list[str], str]:
    """CST solid name `Phone/Housing:cover` → (['Phone', 'Housing'], 'cover')."""
    text = (full or "").replace("\\", "/").strip()
    if ":" in text:
        path, solid = text.split(":", 1)
        folders = [p for p in path.split("/") if p]
        return folders or ["component1"], solid or "?"
    return ["component1"], text or "?"


def nest_solids(components: list) -> dict:
    """Nested folder dict: {name: {children: {...}, solids: [(name, obj)]}}."""
    root = {"children": {}, "solids": []}
    for obj in components or []:
        folders, solid = split_solid_path(obj.get("name", "?"))
        node = root
        for folder in folders:
            node = node["children"].setdefault(
                folder, {"children": {}, "solids": []})
        node["solids"].append((solid, obj))
    return root["children"]


def rgb_from_colour(colour: str):
    parts = [p.strip() for p in (colour or "").split(",") if p.strip()]
    if len(parts) != 3:
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    if max(vals) <= 1.01:
        vals = [v * 255.0 for v in vals]
    return tuple(max(0, min(255, int(round(v)))) for v in vals)


class CstTreeStyle(QProxyStyle):
    """Windows-classic +/- boxes and dotted guides (CST Navigation Tree)."""

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PE_IndicatorBranch:
            return super().drawPrimitive(element, option, painter, widget)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = option.rect
        mid_x = rect.center().x()
        mid_y = rect.center().y()
        pen = QPen(QColor("#9aa3ab"), 1, Qt.DotLine)
        painter.setPen(pen)
        if option.state & QStyle.State_Sibling:
            painter.drawLine(mid_x, rect.top(), mid_x, rect.bottom())
        elif option.state & QStyle.State_Item:
            painter.drawLine(mid_x, rect.top(), mid_x, mid_y)
        if option.state & QStyle.State_Item:
            painter.drawLine(mid_x, mid_y, rect.right(), mid_y)
        if option.state & QStyle.State_Children:
            sz = 9
            box = rect.adjusted(0, 0, 0, 0)
            box.setRect(mid_x - sz // 2, mid_y - sz // 2, sz, sz)
            painter.fillRect(box, QColor("#f4f5f7"))
            painter.setPen(QPen(QColor("#5a6270"), 1, Qt.SolidLine))
            painter.drawRect(box.adjusted(0, 0, -1, -1))
            painter.drawLine(box.left() + 2, mid_y, box.right() - 2, mid_y)
            if not (option.state & QStyle.State_Open):
                painter.drawLine(mid_x, box.top() + 2, mid_x, box.bottom() - 2)
        painter.restore()


def plane_view_camera(plane: str, *, negative: bool = False):
    """Camera (position, view_up) for orthogonal views (CST Front/Right/Top)."""
    sign = -1.0 if negative else 1.0
    p = (plane or "").lower()
    if p == "xy":
        return (0.0, 0.0, sign), (0.0, 1.0, 0.0)
    if p == "xz":
        return (0.0, sign, 0.0), (0.0, 0.0, 1.0)
    return (sign, 0.0, 0.0), (0.0, 0.0, 1.0)


class PaneFrame(QFrame):
    """Title bar + content pane (from cabdecoding / pph_gui)."""

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("PaneFrame")
        self.setFrameShape(QFrame.StyledPanel)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        bar = QFrame(self)
        bar.setObjectName("PaneTitleBar")
        bar.setFixedHeight(24)
        bar.setAutoFillBackground(True)
        bar.setAttribute(Qt.WA_StyledBackground, True)
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(8, 0, 6, 0)
        self.title_label = QLabel(title, bar)
        self.title_label.setObjectName("PaneTitle")
        hb.addWidget(self.title_label)
        hb.addStretch(1)
        lay.addWidget(bar)
        host = QFrame(self)
        host.setObjectName("PaneBody")
        host.setAutoFillBackground(True)
        host.setAttribute(Qt.WA_StyledBackground, True)
        hl = QVBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(content, 1)
        lay.addWidget(host, 1)
        self._content = content

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)


class MessageWindow(QWidget):
    """Message Window: operation log (cabdecoding pattern)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setAcceptRichText(True)
        self.text.document().setMaximumBlockCount(2000)
        self.text.setPlaceholderText("Messages…")
        v.addWidget(self.text)

    def log(self, msg: str, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#2e7d32", "WARN": "#e65100", "ERROR": "#c62828"}
        c = colors.get(level, "#333333")
        self.text.append(
            f'<span style="color:#8a8a8a">[{ts}]</span> '
            f'<span style="color:{c};font-weight:600">{_html_escape(level)}:</span> '
            f'<span style="color:#222">{_html_escape(msg)}</span>')
        bar = self.text.verticalScrollBar()
        bar.setValue(bar.maximum())

    def info(self, msg: str) -> None:
        self.log(msg, "INFO")

    def warn(self, msg: str) -> None:
        self.log(msg, "WARN")

    def error(self, msg: str) -> None:
        self.log(msg, "ERROR")

    def clear(self) -> None:
        self.text.clear()


class PropertyInspector(QWidget):
    """Lower-left Properties pane (cabdecoding Control→Property analog)."""

    property_changed = pyqtSignal(str, str, str, str)  # kind, name, field, value

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.title = QLabel("Select a Navigation Tree item")
        self.title.setWordWrap(True)
        v.addWidget(self.title)
        self.form_host = QWidget(self)
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 4, 0, 0)
        self.form.setSpacing(4)
        v.addWidget(self.form_host, 1)
        self._fields: list = []
        self._kind = ""
        self._name = ""

    def show_item(self, kind: str, name: str, payload: dict | None = None) -> None:
        self.title.setText(name or "(none)")
        self._kind = kind or ""
        self._name = name or ""
        while self.form.rowCount():
            self.form.removeRow(0)
        self._fields.clear()
        rows = [("Type", kind or "")]
        editable = kind in ("solid", "component", "material", "port", "ports",
                            "monitor", "probe")
        payload = payload or {}
        if editable:
            self._add_edit_row("Name", name or payload.get("name", ""), "name")
            if kind in ("solid", "component"):
                self._add_edit_row(
                    "Material", str(payload.get("material") or ""), "material")
            if kind in ("port", "ports"):
                self._add_edit_row(
                    "Impedance", str(payload.get("impedance") or "50"), "impedance")
                p1 = payload.get("p1") or ("", "", "")
                p2 = payload.get("p2") or ("", "", "")
                if len(p1) == 3:
                    self._add_edit_row("P1 X", str(p1[0]), "x1")
                    self._add_edit_row("P1 Y", str(p1[1]), "y1")
                    self._add_edit_row("P1 Z", str(p1[2]), "z1")
                if len(p2) == 3:
                    self._add_edit_row("P2 X", str(p2[0]), "x2")
                    self._add_edit_row("P2 Y", str(p2[1]), "y2")
                    self._add_edit_row("P2 Z", str(p2[2]), "z2")
            if kind == "monitor":
                self._add_edit_row(
                    "Field type", str(payload.get("field_type") or ""), "field_type")
                self._add_edit_row(
                    "Frequency", str(payload.get("frequency") or ""), "frequency")
            if kind == "probe":
                self._add_edit_row("X", str(payload.get("x") or ""), "x")
                self._add_edit_row("Y", str(payload.get("y") or ""), "y")
                self._add_edit_row("Z", str(payload.get("z") or ""), "z")
        if payload:
            skip = {"name", "material"} if editable else set()
            if kind in ("port", "ports"):
                skip.update({"impedance", "p1", "p2", "p1_xyz", "p2_xyz", "box"})
            if kind == "monitor":
                skip.update({"field_type", "frequency"})
            if kind == "probe":
                skip.update({"x", "y", "z", "p1", "xyz"})
            for key in ("material", "type", "field_type", "impedance",
                        "port_number", "epsilon", "mu", "colour",
                        "expr", "value", "description"):
                if key in skip:
                    continue
                val = payload.get(key)
                if val not in (None, ""):
                    rows.append((key.replace("_", " ").title(), str(val)))
            bounds = payload.get("bounds")
            if bounds and len(bounds) == 6:
                rows.append((
                    "Bounds",
                    f"[{bounds[0]:g}, {bounds[1]:g}] × "
                    f"[{bounds[2]:g}, {bounds[3]:g}] × "
                    f"[{bounds[4]:g}, {bounds[5]:g}]",
                ))
        for label, value in rows:
            lab = QLabel(value)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lab.setWordWrap(True)
            self.form.addRow(label + ":", lab)
            self._fields.append(lab)

    def _add_edit_row(self, label: str, value: str, field: str) -> None:
        edit = QLineEdit(value)
        edit.editingFinished.connect(
            lambda e=edit, f=field: self._on_edit(f, e))
        self.form.addRow(label + ":", edit)
        self._fields.append(edit)

    def _on_edit(self, field: str, edit: QLineEdit) -> None:
        text = (edit.text() or "").strip()
        if not text or not self._name:
            return
        self.property_changed.emit(self._kind, self._name, field, text)

    def clear(self) -> None:
        self.show_item("", "Select a Navigation Tree item", None)


class ParameterList(QWidget):
    """CST Parameter List (Name / Expression / Value / Description)."""

    parameters_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Expression", "Value", "Description"])
        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemChanged.connect(self._on_item_changed)
        v.addWidget(self.table)
        self._block = False

    def set_parameters(self, params) -> None:
        self._block = True
        try:
            self.table.setRowCount(len(params))
            for i, rec in enumerate(params):
                for j, key in enumerate(["name", "expr", "value", "description"]):
                    item = QTableWidgetItem(str(rec.get(key, "")))
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    self.table.setItem(i, j, item)
            self.table.resizeColumnsToContents()
        finally:
            self._block = False

    def parameters(self) -> list:
        rows = []
        for i in range(self.table.rowCount()):
            def cell(col, row=i):
                it = self.table.item(row, col)
                return it.text() if it else ""
            rows.append({
                "name": cell(0),
                "expr": cell(1),
                "value": cell(2),
                "description": cell(3),
            })
        return rows

    def _on_item_changed(self, item) -> None:
        if self._block:
            return
        if item is not None and item.column() == 2:
            self._block = True
            expr = self.table.item(item.row(), 1)
            if expr is None:
                self.table.setItem(item.row(), 1, QTableWidgetItem(item.text()))
            else:
                expr.setText(item.text())
            self._block = False
        self.parameters_changed.emit(self.parameters())

    def _context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Add Parameter", self.add_parameter)
        act_del = menu.addAction("Delete Parameter", self.delete_parameter)
        act_del.setEnabled(self.table.currentRow() >= 0)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def add_parameter(self) -> None:
        used = {r["name"] for r in self.parameters()}
        base, i = "par", 1
        name = base
        while name in used:
            i += 1
            name = f"{base}{i}"
        self._block = True
        row = self.table.rowCount()
        self.table.insertRow(row)
        for j, text in enumerate([name, "0", "0", ""]):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, j, item)
        self._block = False
        self.parameters_changed.emit(self.parameters())

    def delete_parameter(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self._block = True
        self.table.removeRow(row)
        self._block = False
        self.parameters_changed.emit(self.parameters())


class ProgressPanel(QWidget):
    """CST Progress tree analog (imported SAB / history captions)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        self.table = QTableWidget(self)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Progress"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.table)

    def set_progress(self, items) -> None:
        self.table.setRowCount(len(items))
        for i, (label, status) in enumerate(items):
            self.table.setItem(i, 0, QTableWidgetItem(f"{label} — {status}"))


class _NavTreeWidget(QTreeWidget):
    """Internal-move is suppressed; drops onto Groups emit solid_dropped_on_group."""

    solid_dropped_on_group = pyqtSignal(str, str)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        target = self.itemAt(event.pos())
        srcs = self.selectedItems()
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if target is None or not srcs:
            return
        src = srcs[0]
        if (src.data(0, KIND_ROLE) or "") != "solid":
            return
        group = target
        while group is not None and (group.data(0, KIND_ROLE) or "") != "group":
            group = group.parent()
        if group is None:
            return
        gname = group.data(0, FULLNAME_ROLE) or group.text(0)
        sname = src.data(0, FULLNAME_ROLE) or ""
        if sname and gname and gname != "Mesh Groups":
            self.solid_dropped_on_group.emit(sname, gname)


class NavigationTree(QWidget):
    """CST Navigation Tree (Search + hierarchy from Model.mod / SAB names)."""

    item_selected = pyqtSignal(str, str, object)  # kind, name, payload
    visibility_changed = pyqtSignal(str, bool)    # component name, visible
    context_action = pyqtSignal(str, str, str)    # action, kind, name
    solid_dropped_on_group = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(2)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        v.addWidget(self.search)
        self.tree = _NavTreeWidget(self)
        self.tree.setObjectName("NavTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setAnimated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(14, 14))
        self.tree.setRootIsDecorated(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setEditTriggers(QTreeWidget.EditKeyPressed)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDrop)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.solid_dropped_on_group.connect(self.solid_dropped_on_group)
        self._tree_style = CstTreeStyle()
        self.tree.setStyle(self._tree_style)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        v.addWidget(self.tree, 1)
        self._block = False
        self._excluded: set[str] = set()
        self._hidden: set[str] = set()
        self._clipboard = None
        self._build_skeleton()
        self._install_shortcuts()

    def _icon(self, key: str, size: int = 14):
        return AppIcons.get(NAV_ICON_MAP.get(key, key), size)

    def _set_item(self, item, kind, fullname=None, payload=None, icon_key=None):
        item.setIcon(0, self._icon(icon_key or kind))
        item.setData(0, KIND_ROLE, kind)
        item.setData(0, FULLNAME_ROLE, fullname or item.text(0))
        if payload is not None:
            item.setData(0, PAYLOAD_ROLE, payload)

    def _build_skeleton(self) -> None:
        self.tree.clear()
        self._excluded = set()

        def add_nodes(parent, items):
            for label, icon_key, children in items:
                if parent is None:
                    item = QTreeWidgetItem(self.tree, [label])
                else:
                    item = QTreeWidgetItem(parent, [label])
                self._set_item(item, icon_key, label, icon_key=icon_key)
                if children:
                    add_nodes(item, children)

        add_nodes(None, NAV_TREE_ITEMS)
        self.tree.expandToDepth(0)

    def _on_item_clicked(self, item, _col) -> None:
        kind = item.data(0, KIND_ROLE) or ""
        label = item.data(0, FULLNAME_ROLE) or item.text(0)
        payload = item.data(0, PAYLOAD_ROLE)
        if kind == "solid":
            self._highlight_solid(label)
        self.item_selected.emit(kind, label, payload)

    def select_by_name(self, fullname: str, emit: bool = True) -> bool:
        hit = None
        for item in self._iter_items():
            if ((item.data(0, KIND_ROLE) or "") == "solid"
                    and (item.data(0, FULLNAME_ROLE) or "") == fullname):
                hit = item
                break
        self._highlight_solid(fullname if hit is not None else "")
        if hit is None:
            return False
        self._block = True
        self.tree.setCurrentItem(hit)
        self.tree.scrollToItem(hit)
        self._block = False
        if emit:
            self.item_selected.emit(
                "solid", fullname, hit.data(0, PAYLOAD_ROLE))
        return True

    def _highlight_solid(self, fullname: str) -> None:
        hl = QColor("#fff3c4")
        clear = QColor(0, 0, 0, 0)
        for item in self._iter_items():
            if (item.data(0, KIND_ROLE) or "") != "solid":
                continue
            match = (item.data(0, FULLNAME_ROLE) or "") == fullname
            item.setBackground(0, hl if match and fullname else clear)

    def _on_item_changed(self, item, _col) -> None:
        if self._block:
            return
        kind = item.data(0, KIND_ROLE) or ""
        old_full = item.data(0, FULLNAME_ROLE) or ""
        new_short = (item.text(0) or "").strip()
        if kind == "solid":
            folders, old_solid = split_solid_path(old_full)
            if not new_short or new_short == old_solid:
                self._block = True
                item.setText(0, old_solid)
                self._block = False
                return
            new_full = "/".join(folders) + ":" + new_short
            item.setData(0, FULLNAME_ROLE, new_full)
            self.context_action.emit("rename", kind, f"{old_full}\n{new_full}")
            return
        if kind in ("collection", "folder", "group"):
            parts = [p for p in (old_full or "").replace("\\", "/").split("/") if p]
            old_leaf = parts[-1] if parts else old_full
            if not new_short or new_short == old_leaf:
                self._block = True
                item.setText(0, old_leaf or item.text(0))
                self._block = False
                return
            parts = parts or [new_short]
            parts[-1] = new_short
            new_full = "/".join(parts)
            item.setData(0, FULLNAME_ROLE, new_full)
            self.context_action.emit("rename", kind, f"{old_full}\n{new_full}")
            return
        if kind == "material":
            if not new_short or new_short == old_full:
                self._block = True
                item.setText(0, old_full or item.text(0))
                self._block = False
                return
            item.setData(0, FULLNAME_ROLE, new_short)
            self.context_action.emit("rename", kind, f"{old_full}\n{new_short}")
            return
        if kind in ("port", "ports", "monitor", "probe"):
            if not new_short or new_short == old_full:
                self._block = True
                item.setText(0, old_full or item.text(0))
                self._block = False
                return
            item.setData(0, FULLNAME_ROLE, new_short)
            self.context_action.emit("rename", kind, f"{old_full}\n{new_short}")

    def _collect_solid_names(self, item) -> list:
        names = []
        kind = item.data(0, KIND_ROLE) or ""
        full = item.data(0, FULLNAME_ROLE) or ""
        if kind in ("solid", "component") and full:
            names.append(full)
        for i in range(item.childCount()):
            names.extend(self._collect_solid_names(item.child(i)))
        return names

    def _all_solid_names(self) -> list:
        names = []
        for i in range(self.tree.topLevelItemCount()):
            names.extend(self._collect_solid_names(self.tree.topLevelItem(i)))
        # Unique, preserve order (solids appear under Components and Groups).
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def _iter_items(self, parent=None):
        if parent is None:
            for i in range(self.tree.topLevelItemCount()):
                yield from self._iter_items(self.tree.topLevelItem(i))
            return
        yield parent
        for i in range(parent.childCount()):
            yield from self._iter_items(parent.child(i))

    def _target_items(self, item) -> list:
        selected = self.tree.selectedItems()
        if item in selected:
            return list(selected)
        return [item]

    def set_hidden_names(self, names) -> None:
        self._hidden = set(names or [])
        self._refresh_hidden_style()

    def _refresh_hidden_style(self) -> None:
        hidden_fg = QColor("#9aa0a6")
        normal_fg = QColor("#1f1f1f")
        for item in self._iter_items():
            names = self._collect_solid_names(item)
            if not names:
                continue
            item.setForeground(
                0, hidden_fg if all(n in self._hidden for n in names)
                else normal_fg)

    def _emit_visible(self, name: str, visible: bool) -> None:
        if visible:
            self._hidden.discard(name)
        else:
            self._hidden.add(name)
        self.visibility_changed.emit(name, visible)

    def _install_shortcuts(self) -> None:
        def add(seq, action):
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.setShortcutContext(Qt.WidgetShortcut)
            act.triggered.connect(lambda _=False, a=action: self._shortcut(a))
            self.tree.addAction(act)

        add("Ctrl+H", "hide")
        add("Ctrl+Shift+H", "show")
        add("Ctrl+U", "show_all")
        add("Delete", "delete")
        add("Ctrl+C", "copy")
        add("Ctrl+V", "paste")
        add("Ctrl+E", "edit_properties")
        add("Ctrl+Shift+A", "align")

    def _shortcut(self, action: str) -> None:
        if self.tree.state() == QTreeWidget.EditingState:
            return
        item = self.tree.currentItem()
        if item is None and action not in ("show_all", "unselect_all"):
            return
        self._run_action(action, item)

    def _menu_icon(self, name: str):
        if not name:
            return QIcon()
        return AppIcons.get(name, 16)

    def _add_menu_action(self, menu, text, action, icon="", shortcut="",
                         enabled=True):
        act = menu.addAction(self._menu_icon(icon), text)
        act.setData(action)
        act.setEnabled(bool(enabled))
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
            try:
                act.setShortcutVisibleInContextMenu(True)
            except Exception:
                pass
        return act

    def build_context_menu(self, item) -> QMenu:
        """CST DESIGN ENVIRONMENT solid context menu (screenshot layout)."""
        kind = item.data(0, KIND_ROLE) or ""
        is_solid = kind in ("solid", "component")
        is_folder = kind in ("collection", "folder", "group")
        is_material = kind == "material"
        geom = is_solid
        menu = QMenu(self)

        self._add_menu_action(menu, "Rectangle Selection", "rect_select",
                              "select_rect")
        self._add_menu_action(menu, "Unselect All", "unselect_all")
        menu.addSeparator()
        self._add_menu_action(menu, "Hide", "hide", "hide", "Ctrl+H",
                              enabled=is_solid or is_folder)
        self._add_menu_action(menu, "Hide Unselected", "hide_unselected",
                              enabled=is_solid or is_folder)
        self._add_menu_action(menu, "Show", "show", "show", "Ctrl+Shift+H",
                              enabled=is_solid or is_folder)
        self._add_menu_action(menu, "Show All", "show_all", shortcut="Ctrl+U")
        if (item.text(0) == "Components"
                or (item.data(0, FULLNAME_ROLE) or "") == "Components"):
            self._add_menu_action(menu, "New Component...", "new_component",
                                  "component")
        menu.addSeparator()

        elec = menu.addMenu("Electrical Connections")
        self._add_menu_action(elec, "Calculate Electrical Connections",
                              "elec_calc", enabled=geom)
        self._add_menu_action(elec, "Show Electrical Connections",
                              "elec_show", enabled=geom)
        self._add_menu_action(elec, "Hide Electrical Connections",
                              "elec_hide", enabled=geom)
        wcs = menu.addMenu("Local Solid Coordinates")
        self._add_menu_action(wcs, "Align WCS with Solid", "wcs_align_solid",
                              "wcs", enabled=geom)
        self._add_menu_action(wcs, "Move WCS to Solid Center", "wcs_to_center",
                              "wcs", enabled=geom)
        self._add_menu_action(wcs, "Reset WCS to Global", "wcs_reset",
                              "wcs", enabled=geom)
        menu.addSeparator()

        self._add_menu_action(menu, "Slice by UV Plane", "slice_uv", "slice",
                              enabled=False)
        self._add_menu_action(menu, "Separate Shape", "separate",
                              enabled=geom)
        self._add_menu_action(menu, "Transform...", "transform", "translate",
                              enabled=geom)
        self._add_menu_action(menu, "Align...", "align", "align",
                              "Ctrl+Shift+A", enabled=geom)
        self._add_menu_action(menu, "Change Component...", "change_component",
                              enabled=geom)
        self._add_menu_action(menu, "Change Group...", "change_group",
                              enabled=geom)
        self._add_menu_action(menu, "Assign Material and Color...",
                              "assign_material", "material",
                              enabled=geom)
        menu.addSeparator()

        can_edit = is_solid or is_folder or is_material
        self._add_menu_action(menu, "Delete", "delete", "delete", "Del",
                              enabled=can_edit)
        self._add_menu_action(menu, "Rename", "rename", "rename", "F2",
                              enabled=can_edit)
        self._add_menu_action(menu, "Copy", "copy", "copy", "Ctrl+C",
                              enabled=can_edit)
        self._add_menu_action(menu, "Paste", "paste", "paste", "Ctrl+V",
                              enabled=self._clipboard is not None)
        menu.addSeparator()

        self._add_menu_action(menu, "Object Information...", "object_info",
                              "info", enabled=is_solid or is_folder)
        self._add_menu_action(menu, "Local Mesh Properties...", "local_mesh",
                              "mesh", enabled=geom)
        self._add_menu_action(menu, "Edit Material Properties...",
                              "edit_material", enabled=is_solid or is_material)
        self._add_menu_action(menu, "Edit Properties...", "edit_properties",
                              "editprops", "Ctrl+E")
        return menu

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        if item not in self.tree.selectedItems():
            self.tree.setCurrentItem(item)
        self._on_item_clicked(item, 0)
        menu = self.build_context_menu(item)
        chosen = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        action = chosen.data()
        if not action:
            return
        self._run_action(action, item)

    def _run_action(self, action: str, item) -> None:
        if action == "unselect_all":
            self.tree.clearSelection()
            return
        if action == "rename" and item is not None:
            self.tree.editItem(item, 0)
            return
        if action == "show_all":
            for name in self._all_solid_names():
                self._emit_visible(name, True)
            self._refresh_hidden_style()
            self.context_action.emit("show_all", "collection", "")
            return
        if item is None:
            return
        kind = item.data(0, KIND_ROLE) or ""
        name = item.data(0, FULLNAME_ROLE) or item.text(0)
        if action in ("hide", "show"):
            visible = action == "show"
            names = []
            for it in self._target_items(item):
                names.extend(self._collect_solid_names(it) or (
                    [it.data(0, FULLNAME_ROLE)] if it.data(0, KIND_ROLE)
                    in ("solid", "component") else []))
            for n in names:
                if n:
                    self._emit_visible(n, visible)
            self._refresh_hidden_style()
            return
        if action == "hide_unselected":
            keep = set()
            for it in self._target_items(item):
                keep.update(self._collect_solid_names(it))
            if not keep and name:
                keep.add(name)
            for n in self._all_solid_names():
                self._emit_visible(n, n in keep)
            self._refresh_hidden_style()
            return
        if action == "copy":
            payload = item.data(0, PAYLOAD_ROLE)
            self._clipboard = (kind, name, payload)
            self.context_action.emit("copy", kind, name)
            return
        if action == "delete":
            names = []
            for it in self._target_items(item):
                names.extend(self._collect_solid_names(it))
            self.context_action.emit(
                "delete", kind, "\n".join(names) if names else name)
            return
        self.context_action.emit(action, kind, name)

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()

        def match(item) -> bool:
            ok = needle in item.text(0).lower() if needle else True
            child_hit = False
            for i in range(item.childCount()):
                if match(item.child(i)):
                    child_hit = True
            visible = ok or child_hit or not needle
            item.setHidden(not visible)
            if needle and (ok or child_hit):
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            match(self.tree.topLevelItem(i))

    def _add_child(self, parent, label, icon_key, payload=None, fullname=None,
                   kind=None):
        child = QTreeWidgetItem(parent, [label])
        self._set_item(child, kind or icon_key, fullname or label, payload,
                       icon_key=icon_key)
        kind_name = kind or icon_key
        flags = child.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if kind_name in ("solid", "component", "material", "collection",
                         "folder", "group", "port", "ports", "monitor", "probe"):
            flags |= Qt.ItemIsEditable
        if kind_name in ("solid", "component"):
            flags |= Qt.ItemIsDragEnabled
        if kind_name == "group":
            flags |= Qt.ItemIsDropEnabled
        child.setFlags(flags)
        return child

    def _add_solid_tree(self, parent, node_map, excluded, prefix=""):
        for folder in node_map:
            path = f"{prefix}/{folder}" if prefix else folder
            folder_item = self._add_child(
                parent, folder, "collection", kind="collection",
                fullname=path)
            sub = node_map[folder]
            self._add_solid_tree(
                folder_item, sub.get("children") or {}, excluded, path)
            for solid_name, obj in sub.get("solids") or []:
                full = obj.get("name", solid_name)
                icon = "solid_excluded" if full in excluded else "solid"
                self._add_child(
                    folder_item, solid_name, icon, obj, fullname=full,
                    kind="solid")

    def _add_material_item(self, parent, mat: dict):
        rgb = rgb_from_colour(mat.get("colour") or "") or (80, 170, 190)
        child = QTreeWidgetItem(parent, [mat.get("name", "?")])
        child.setIcon(0, AppIcons.material(rgb, 14))
        child.setData(0, KIND_ROLE, "material")
        child.setData(0, FULLNAME_ROLE, mat.get("name", "?"))
        child.setData(0, PAYLOAD_ROLE, mat)
        child.setFlags(child.flags() | Qt.ItemIsEditable)
        return child

    def populate_from_project(self, project_data: dict) -> None:
        self._block = True
        self.tree.clear()
        self._hidden = set()

        groups_data = list(project_data.get("groups") or [])
        components = project_data.get("components") or []
        materials = project_data.get("materials") or []
        ports = project_data.get("ports") or []
        monitors = project_data.get("monitors") or []
        faces = project_data.get("faces") or []
        curves = project_data.get("curves") or []
        wcs = project_data.get("wcs") or []
        probes = project_data.get("probes") or []
        lumped = project_data.get("lumped") or []
        results_1d = project_data.get("results_1d") or []
        results_2d = project_data.get("results_2d") or []
        farfields = project_data.get("farfields") or []
        tables = project_data.get("tables") or []

        by_group = {g.get("name", ""): g for g in groups_data}
        excluded = set()
        excl = by_group.get("Excluded from Simulation") or {}
        excluded.update(excl.get("items") or [])
        self._excluded = excluded

        items_def = [
            ("Components", "collection", "components", components),
            ("Groups", "collection", "groups", groups_data),
            ("Materials", "collection", "materials", materials),
            ("Faces", "collection", "dict_list", faces),
            ("Curves", "collection", "dict_list", curves),
            ("WCS", "collection", "wcs", wcs),
            ("Anchor Points", "collection", "empty", []),
            ("Wires", "collection", "empty", []),
            ("Voxel Data", "collection", "empty", []),
            ("Dimensions", "gear", "empty", []),
            ("Lumped Elements", "gear", "dict_list", lumped),
            ("Plane Wave", "gear", "empty", []),
            ("Farfield Sources", "gear", "empty", []),
            ("Field Sources", "gear", "empty", []),
            ("Ports", "ports", "dict_list", ports),
            ("Excitation Signals", "gear", "empty", []),
            ("Field Monitors", "monitor", "dict_list", monitors),
            ("Voltage and Current Monitors", "gear", "empty", []),
            ("Probes", "probe", "dict_list", probes),
            ("Mesh", "gear", "empty", []),
            ("1D Results", "results", "dict_list", results_1d),
            ("2D/3D Results", "results", "dict_list", results_2d),
            ("Farfields", "results", "dict_list", farfields),
            ("Tables", "results", "dict_list", tables),
            ("codebook", "results", "empty", []),
        ]

        for label, icon_key, data_type, data in items_def:
            item = QTreeWidgetItem(self.tree, [label])
            self._set_item(item, icon_key, label, icon_key=icon_key)

            if data_type == "components":
                nested = nest_solids(data) if data else {}
                if nested:
                    self._add_solid_tree(item, nested, excluded)
                for folder in project_data.get("empty_components") or []:
                    if folder and folder not in nested:
                        self._add_child(
                            item, folder.split("/")[-1], "collection",
                            kind="collection", fullname=folder)
            elif data_type == "groups":
                for fixed in _CST_GROUP_FIXED:
                    g = by_group.get(fixed) or {"name": fixed, "items": []}
                    gitem = self._add_child(
                        item, fixed, "collection", g, kind="group")
                    for gi in (g.get("items") or [])[:80]:
                        short = gi.split(":")[-1] if ":" in gi else gi.split("/")[-1]
                        icon = ("solid_excluded" if fixed.startswith("Excluded")
                                else "solid")
                        self._add_child(
                            gitem, short, icon, {"name": gi}, fullname=gi,
                            kind="solid")
                mesh_item = self._add_child(
                    item, "Mesh Groups", "meshgroup", kind="group")
                seen_fixed = set(_CST_GROUP_FIXED)
                for g in groups_data:
                    gname = g.get("name", "?")
                    if gname in seen_fixed:
                        continue
                    is_mesh = (g.get("type") or "").lower() == "mesh"
                    parent_g = mesh_item if is_mesh else item
                    gitem = self._add_child(
                        parent_g, gname,
                        "meshitem" if is_mesh else "collection", g,
                        kind="group")
                    for gi in (g.get("items") or [])[:40]:
                        short = gi.split(":")[-1] if ":" in gi else gi.split("/")[-1]
                        self._add_child(
                            gitem, short, "solid", {"name": gi}, fullname=gi,
                            kind="solid")
            elif data_type == "materials" and data:
                folders: dict[str, list] = {}
                root_mats = []
                for mat in data:
                    folder = (mat.get("folder") or "").strip()
                    if folder:
                        folders.setdefault(folder, []).append(mat)
                    else:
                        root_mats.append(mat)
                for folder, mats in folders.items():
                    fitem = self._add_child(
                        item, folder, "folder", kind="folder")
                    for mat in mats:
                        self._add_material_item(fitem, mat)
                for mat in root_mats:
                    self._add_material_item(item, mat)
            elif data_type == "wcs" and data:
                for obj in data:
                    self._add_child(
                        item, obj.get("name", "?"), "wcs", obj, kind="wcs")
            elif data_type == "dict_list" and data:
                child_kind = {"ports": "port"}.get(icon_key, icon_key)
                for obj in data:
                    self._add_child(
                        item, obj.get("name", "?"), icon_key, obj,
                        kind=child_kind)

        self.tree.expandToDepth(1)
        self._block = False
        self._apply_filter(self.search.text())


class CST3DCanvas(QWidget):
    """Fallback isometric 3D viewport (QPainter) when VTK/OpenGL is unavailable."""

    solid_picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_data: dict = {}
        self._view_angle = 30
        self._zoom = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._bounds = None
        self._hidden: set[str] = set()
        self._drawing_mode = "Shading"
        self._dragging = False
        self._last_pos = None
        self._press_pos = None
        self._selected = ""
        self._color_list = [
            (0.95, 0.85, 0.3), (0.3, 0.75, 0.4), (0.8, 0.3, 0.3),
            (0.3, 0.5, 0.9), (0.7, 0.4, 0.7), (0.9, 0.6, 0.2),
            (0.2, 0.6, 0.6), (0.5, 0.5, 0.8), (0.8, 0.5, 0.5),
            (0.4, 0.8, 0.5),
        ]
        self.setMinimumSize(200, 150)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_project(self, data: dict) -> None:
        self._project_data = data
        self._compute_bounds()
        self.update()

    def set_hidden(self, names: set[str]) -> None:
        self._hidden = set(names)
        self.update()

    def set_drawing_mode(self, mode: str) -> None:
        self._drawing_mode = mode
        self.update()

    def _compute_bounds(self) -> None:
        mins = [float("inf")] * 3
        maxs = [float("-inf")] * 3
        found = False

        def acc(pt):
            nonlocal found
            if not pt or len(pt) != 3:
                return
            try:
                xyz = (float(pt[0]), float(pt[1]), float(pt[2]))
            except (TypeError, ValueError):
                return
            found = True
            for i, v in enumerate(xyz):
                mins[i] = min(mins[i], v)
                maxs[i] = max(maxs[i], v)

        def acc_box(b):
            if not b or len(b) != 6:
                return
            acc((b[0], b[2], b[4]))
            acc((b[1], b[3], b[5]))

        for comp in self._project_data.get("components") or []:
            acc_box(comp.get("bounds"))
        for port in self._project_data.get("ports") or []:
            acc(port.get("p1_xyz"))
            acc(port.get("p2_xyz"))
            acc_box(port.get("box"))
        for probe in self._project_data.get("probes") or []:
            acc(probe.get("xyz"))
        if not found:
            self._bounds = None
            return
        for i in range(3):
            if maxs[i] - mins[i] < 1e-6:
                mins[i] -= 1.0
                maxs[i] += 1.0
        self._bounds = (mins[0], maxs[0], mins[1], maxs[1], mins[2], maxs[2])

    def _world_to_screen(self, x, y, z):
        angle = math.radians(self._view_angle)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        if self._bounds:
            xmin, xmax, ymin, ymax, zmin, zmax = self._bounds
            cx = (xmin + xmax) / 2
            cy = (ymin + ymax) / 2
            cz = (zmin + zmax) / 2
            sx, sy, sz = x - cx, y - cy, z - cz
        else:
            sx, sy, sz = x, y, z
        px = (sx - sy) * cos_a
        py = (sx + sy) * sin_a - sz
        return (self.width() / 2 + self._offset_x + px * self._zoom,
                self.height() / 2 + self._offset_y - py * self._zoom)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        grad = QLinearGradient(0, 0, 0, max(1, self.height()))
        grad.setColorAt(0.0, QColor(138, 163, 186))
        grad.setColorAt(1.0, QColor(208, 218, 228))
        p.fillRect(self.rect(), grad)
        if not self._project_data:
            p.setPen(QColor(150, 150, 150))
            p.setFont(QFont("Segoe UI", 12))
            p.drawText(self.rect(), Qt.AlignCenter, "No project loaded")
            p.end()
            return
        self._draw_axes(p)
        self._draw_components(p)
        self._draw_ports(p)
        self._draw_info(p)
        p.end()

    def _draw_grid(self, p):
        p.setPen(QPen(QColor(215, 215, 220), 1))
        if not self._bounds:
            for x in range(0, self.width(), 50):
                p.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), 50):
                p.drawLine(0, y, self.width(), y)
            return
        xmin, xmax, ymin, ymax, _, _ = self._bounds
        step = max(1.0, min(xmax - xmin, ymax - ymin) / 10) * self._zoom
        cx, cy = self._world_to_screen(0, 0, 0)
        for i in range(-24, 25):
            x_line = cx + i * step
            if 0 <= x_line <= self.width():
                p.drawLine(int(x_line), 0, int(x_line), self.height())
            y_line = cy + i * step
            if 0 <= y_line <= self.height():
                p.drawLine(0, int(y_line), self.width(), int(y_line))

    def _draw_axes(self, p):
        ox, oy = self._world_to_screen(0, 0, 0)
        ax, ay = self._world_to_screen(50, 0, 0)
        bx, by = self._world_to_screen(0, 50, 0)
        cx, cy = self._world_to_screen(0, 0, 50)
        p.setPen(QPen(QColor(200, 50, 50), 2))
        p.drawLine(int(ox), int(oy), int(ax), int(ay))
        p.drawText(int(ax) + 4, int(ay), "X")
        p.setPen(QPen(QColor(50, 180, 50), 2))
        p.drawLine(int(ox), int(oy), int(bx), int(by))
        p.drawText(int(bx) + 4, int(by), "Y")
        p.setPen(QPen(QColor(50, 100, 220), 2))
        p.drawLine(int(ox), int(oy), int(cx), int(cy))
        p.drawText(int(cx) + 4, int(cy), "Z")

    def _draw_components(self, p):
        components = self._project_data.get("components", [])
        materials_map = {}
        for mat in self._project_data.get("materials", []):
            colour = mat.get("colour", "")
            if colour:
                try:
                    parts = [float(x.strip()) for x in colour.split(",")]
                    if len(parts) >= 3:
                        materials_map[mat["name"]] = tuple(parts[:3])
                except (ValueError, IndexError):
                    pass
        many = len(components) > 24
        for i, comp in enumerate(components):
            name = comp.get("name", f"C{i}")
            if name in self._hidden or name.split(":")[-1] in self._hidden:
                continue
            color = CST3DViewport._component_color(comp, materials_map, i)
            if self._drawing_mode == "Transparent":
                alpha_scale = 0.32
            elif self._drawing_mode == "Wireframe":
                alpha_scale = 1.0
            else:
                alpha_scale = 1.0
            label = "" if many else name.split(":")[-1]
            mesh = comp.get("mesh") or {}
            if mesh.get("points") and mesh.get("faces"):
                self._draw_mesh(p, mesh, color, label, alpha_scale)
                continue
            bounds = comp.get("bounds")
            if not bounds:
                continue
            self._draw_box(p, bounds, color, label, alpha_scale)

    def _draw_ports(self, p):
        p.setPen(QPen(QColor(220, 40, 40), 2))
        p.setFont(QFont("Segoe UI", 8))
        for port in self._project_data.get("ports") or []:
            box = port.get("box")
            if box:
                self._draw_box(p, box, (0.86, 0.16, 0.16),
                               port.get("name") or "", 0.35)
            a, b = port.get("p1_xyz"), port.get("p2_xyz")
            if not a or not b:
                continue
            s1 = self._world_to_screen(*a)
            s2 = self._world_to_screen(*b)
            p.setPen(QPen(QColor(220, 40, 40), 2))
            p.drawLine(int(s1[0]), int(s1[1]), int(s2[0]), int(s2[1]))
            mx, my = (s1[0] + s2[0]) / 2, (s1[1] + s2[1]) / 2
            p.drawText(int(mx) + 4, int(my),
                       port.get("name") or f"port{port.get('port_number', '')}")
        p.setBrush(QColor(40, 160, 40, 180))
        p.setPen(QPen(QColor(20, 80, 20), 1))
        for probe in self._project_data.get("probes") or []:
            xyz = probe.get("xyz")
            if not xyz:
                continue
            sx, sy = self._world_to_screen(*xyz)
            p.drawEllipse(int(sx) - 4, int(sy) - 4, 8, 8)
            p.drawText(int(sx) + 6, int(sy) - 4, probe.get("name") or "probe")

    def _draw_mesh(self, p, mesh, color, name, alpha_scale=0.8):
        points = mesh.get("points") or []
        faces = mesh.get("faces") or []
        wires = mesh.get("wires") or []
        r0, g0, b0 = [int(ch * 255) for ch in color]
        wire = self._drawing_mode == "Wireframe"
        if wire and wires:
            if alpha_scale >= 0.12:
                self._stroke_cad_wires(p, wires)
            return
        if not points or not faces:
            if wires:
                self._stroke_cad_wires(p, wires)
            return
        screen = [self._world_to_screen(pt[0], pt[1], pt[2]) for pt in points]
        order = []
        for fi, tri in enumerate(faces):
            if len(tri) < 3:
                continue
            a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
            if max(a, b, c) >= len(points):
                continue
            z = (points[a][2] + points[b][2] + points[c][2]) / 3.0
            order.append((z, fi, a, b, c))
        order.sort()
        r0, g0, b0 = [int(ch * 255) for ch in color]
        wire = self._drawing_mode == "Wireframe"
        base_alpha = 255 if alpha_scale >= 0.99 else int(255 * max(0.08, min(1.0, alpha_scale)))
        alpha = 82 if self._drawing_mode == "Transparent" else (0 if wire else base_alpha)
        for _z, _fi, a, b, c in order:
            pa, pb, pc = points[a], points[b], points[c]
            ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
            vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            shade = 0.94 + 0.06 * abs(nz) / nlen
            fr, fg, fb = [min(255, int(ch * shade)) for ch in (r0, g0, b0)]
            pts = [QPoint(int(screen[i][0]), int(screen[i][1])) for i in (a, b, c)]
            if wire:
                p.setPen(QPen(QColor(fr, fg, fb), 1))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(fr, fg, fb, alpha))
            p.drawPolygon(pts)
        if not wire and wires and alpha_scale >= 0.12:
            self._stroke_cad_wires(p, wires)
        if name and screen:
            center_x = sum(pt[0] for pt in screen) / len(screen)
            center_y = min(pt[1] for pt in screen) - 5
            p.setPen(QPen(QColor(40, 40, 40), 1))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(int(center_x) - 20, int(center_y), name)

    def _stroke_cad_wires(self, p, wires):
        p.setPen(QPen(QColor(58, 58, 62), 1))
        p.setBrush(Qt.NoBrush)
        for poly in wires:
            if len(poly) < 2:
                continue
            prev = self._world_to_screen(poly[0][0], poly[0][1], poly[0][2])
            for pt in poly[1:]:
                cur = self._world_to_screen(pt[0], pt[1], pt[2])
                p.drawLine(QPoint(int(prev[0]), int(prev[1])),
                           QPoint(int(cur[0]), int(cur[1])))
                prev = cur

    def _draw_box(self, p, bounds, color, name, alpha_scale=0.8):
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        corners = [
            (xmin, ymin, zmin), (xmax, ymin, zmin),
            (xmax, ymax, zmin), (xmin, ymax, zmin),
            (xmin, ymin, zmax), (xmax, ymin, zmax),
            (xmax, ymax, zmax), (xmin, ymax, zmax),
        ]
        screen_pts = [self._world_to_screen(*c) for c in corners]
        faces = [
            (0, 1, 2, 3), (4, 5, 6, 7), (0, 4, 7, 3),
            (1, 5, 6, 2), (3, 2, 6, 7), (0, 1, 5, 4),
        ]
        face_depths = sorted(
            ((sum(corners[i][2] for i in face) / 4, fi)
             for fi, face in enumerate(faces)))
        r0, g0, b0 = [int(c * 255) for c in color]
        wire = self._drawing_mode == "Wireframe"
        base_alpha = 255 if alpha_scale >= 0.99 else int(255 * max(0.08, min(1.0, alpha_scale)))
        alpha = 82 if self._drawing_mode == "Transparent" else (0 if wire else base_alpha)
        for _, fi in face_depths:
            pts = [QPoint(int(screen_pts[i][0]), int(screen_pts[i][1]))
                   for i in faces[fi]]
            shade = 0.96 if fi in (0, 5) else (0.90 if fi in (1, 4) else 0.84)
            fr, fg, fb = [min(255, int(c * shade)) for c in (r0, g0, b0)]
            p.setPen(QPen(QColor(58, 58, 62), 1))
            if name and name == self._selected:
                p.setPen(QPen(QColor(230, 170, 20), 2))
            if wire:
                p.setBrush(Qt.NoBrush)
            else:
                p.setBrush(QColor(fr, fg, fb, alpha))
            p.drawPolygon(pts)
        if name and screen_pts:
            center_x = sum(pt[0] for pt in screen_pts) / len(screen_pts)
            center_y = min(pt[1] for pt in screen_pts) - 5
            p.setPen(QPen(QColor(40, 40, 40), 1))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(int(center_x) - 20, int(center_y), name)

    def _draw_info(self, p):
        n_comp = len(self._project_data.get("components", []))
        n_mat = len(self._project_data.get("materials", []))
        n_port = len(self._project_data.get("ports", []))
        p.setPen(QColor(80, 80, 80))
        p.setFont(QFont("Consolas", 9))
        y = self.height() - 10
        for line in reversed((
                f"Components: {n_comp}",
                f"Materials: {n_mat}",
                f"Ports: {n_port}",
        )):
            p.drawText(10, y, line)
            y -= 14

    def clear(self) -> None:
        self._project_data = {}
        self._bounds = None
        self.update()

    def render_project(self, project_data: dict) -> None:
        self._project_data = project_data or {}
        self._compute_bounds()
        self._offset_x = 0
        self._offset_y = 0
        self._auto_zoom()
        self.update()

    def _auto_zoom(self) -> None:
        if not self._bounds:
            self._zoom = 1.0
            return
        xmin, xmax, ymin, ymax, zmin, zmax = self._bounds
        span = max(xmax - xmin, ymax - ymin, zmax - zmin, 1.0)
        w = max(self.width(), 200)
        h = max(self.height(), 150)
        self._zoom = 0.65 * min(w, h) / span

    def fit(self) -> None:
        self._offset_x = 0
        self._offset_y = 0
        self._auto_zoom()
        self.update()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._zoom = max(0.05, min(200.0, self._zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._dragging = True
            self._last_pos = event.pos()
            self._press_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_pos:
            self._offset_x += event.x() - self._last_pos.x()
            self._offset_y += event.y() - self._last_pos.y()
            self._last_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.LeftButton and self._press_pos is not None
                and (event.pos() - self._press_pos).manhattanLength() < 6):
            name = self._hit_test(event.pos())
            self._selected = name
            self.update()
            if name:
                self.solid_picked.emit(name)
        self._dragging = False
        self._last_pos = None
        self._press_pos = None

    def _hit_test(self, pos) -> str:
        x, y = pos.x(), pos.y()
        hit = ""
        for comp in self._project_data.get("components") or []:
            name = comp.get("name") or ""
            if not name or name in self._hidden:
                continue
            bounds = comp.get("bounds")
            if not bounds or len(bounds) != 6:
                continue
            xmin, xmax, ymin, ymax, zmin, zmax = bounds
            corners = [
                (xmin, ymin, zmin), (xmax, ymin, zmin),
                (xmax, ymax, zmin), (xmin, ymax, zmin),
                (xmin, ymin, zmax), (xmax, ymin, zmax),
                (xmax, ymax, zmax), (xmin, ymax, zmax),
            ]
            pts = [self._world_to_screen(*c) for c in corners]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                hit = name
        return hit


class CST3DViewport(QWidget):
    """3D viewport: VTK trackball + orientation widget, QPainter fallback."""

    status_coords = pyqtSignal(str)
    solid_picked = pyqtSignal(str)

    def __init__(self, parent=None, enable_3d: bool = True):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._renderer = None
        self._vtk_widget = None
        self._bounds = None
        self._actors: list[tuple] = []
        self._base_opacity: dict[str, float] = {}
        self._hidden: set[str] = set()
        self._drawing_mode = "Shading"
        self._using_vtk = False
        self._canvas = None
        self._orientation = None
        self._iren_ready = False
        self._light_kit = None
        self._parallel = True
        self._selected = ""
        self._pick_xy = None
        if enable_3d and _HAS_VTK and not self._is_offscreen():
            try:
                self._init_vtk()
            except Exception as exc:
                print(f"VTK initialization failed ({exc}), using Qt canvas fallback")
                self._init_canvas()
        else:
            self._init_canvas()

    @staticmethod
    def _is_offscreen() -> bool:
        return os.environ.get("QT_QPA_PLATFORM", "") == "offscreen"

    def _init_vtk(self) -> None:
        self._vtk_widget = QVTKRenderWindowInteractor(self)
        self._layout.addWidget(self._vtk_widget)
        self._renderer = vtk.vtkRenderer()
        self._vtk_widget.GetRenderWindow().AddRenderer(self._renderer)
        self.ren_win = self._vtk_widget.GetRenderWindow()
        self._configure_studio_view()
        try:
            self._vtk_widget.Initialize()
            self._iren_ready = True
        except Exception:
            self._iren_ready = False
        iren = self.ren_win.GetInteractor()
        if iren is not None:
            style = vtk.vtkInteractorStyleTrackballCamera()
            iren.SetInteractorStyle(style)
            iren.AddObserver("LeftButtonPressEvent", self._vtk_left_press, 1.0)
            iren.AddObserver("LeftButtonReleaseEvent", self._vtk_left_release, 1.0)
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(1.2, 1.2, 1.2)
        try:
            marker = vtk.vtkOrientationMarkerWidget()
            marker.SetOrientationMarker(axes)
            if iren is not None:
                marker.SetInteractor(iren)
            marker.SetViewport(0.0, 0.0, 0.18, 0.18)
            marker.SetEnabled(1)
            marker.InteractiveOff()
            self._orientation = marker
        except Exception:
            self._renderer.AddActor(axes)
            self._orientation = None
        self._using_vtk = True
        self.ren_win.Render()

    def _configure_studio_view(self) -> None:
        """CST viewport: steel-blue top fading to cooler grey at the floor."""
        r = self._renderer
        r.SetBackground(0.80, 0.85, 0.89)
        r.SetBackground2(0.52, 0.62, 0.72)
        r.GradientBackgroundOn()
        r.TwoSidedLightingOn()
        r.SetAutomaticLightCreation(0)
        try:
            r.UseFXAAOn()
        except Exception:
            pass
        self._set_translucent_pass(False)
        self._install_lights()
        self._apply_projection()

    def _set_translucent_pass(self, on: bool) -> None:
        """Depth peeling is for Transparent mode only.

        Leaving it on for opaque Shading makes coplanar CAD faces z-fight as
        extra coloured triangles (the artifacts vs CST).
        """
        r = self._renderer
        if r is None:
            return
        try:
            if on:
                self.ren_win.SetAlphaBitPlanes(1)
                self.ren_win.SetMultiSamples(0)
                r.SetUseDepthPeeling(1)
                r.SetMaximumNumberOfPeels(8)
                r.SetOcclusionRatio(0.1)
            else:
                r.SetUseDepthPeeling(0)
                try:
                    r.SetUseDepthPeelingForVolumes(0)
                except Exception:
                    pass
        except Exception:
            pass

    def _reset_camera(self) -> None:
        if not self._renderer:
            return
        self._renderer.ResetCamera()
        self._apply_projection()
        try:
            self._renderer.ResetCameraClippingRange()
            cam = self._renderer.GetActiveCamera()
            near, far = cam.GetClippingRange()
            if far > near * 5000.0:
                cam.SetClippingRange(max(near, far / 5000.0), far)
        except Exception:
            pass

    def _apply_projection(self) -> None:
        if not self._renderer:
            return
        cam = self._renderer.GetActiveCamera()
        if self._parallel:
            cam.ParallelProjectionOn()
        else:
            cam.ParallelProjectionOff()

    def _install_lights(self) -> None:
        """CST-like headlight: even planes, slight shading on curves, no dark sides."""
        r = self._renderer
        try:
            r.RemoveAllLights()
        except Exception:
            pass
        self._light_kit = None
        try:
            head = vtk.vtkLight()
            head.SetLightTypeToHeadLight()
            head.SetColor(1.0, 1.0, 1.0)
            head.SetIntensity(0.38)
            r.AddLight(head)
            fill = vtk.vtkLight()
            fill.SetLightTypeToCameraLight()
            fill.SetPosition(0.35, 0.55, 0.75)
            fill.SetFocalPoint(0.0, 0.0, 0.0)
            fill.SetColor(0.96, 0.97, 1.0)
            fill.SetIntensity(0.16)
            r.AddLight(fill)
            return
        except Exception:
            pass
        for pos, intensity, color in (
                ((0.0, 0.0, 1.0), 0.40, (1.0, 1.0, 1.0)),
                ((0.5, 0.4, 0.7), 0.18, (0.95, 0.96, 1.0)),
        ):
            light = vtk.vtkLight()
            light.SetLightTypeToSceneLight()
            light.SetPosition(*pos)
            light.SetFocalPoint(0.0, 0.0, 0.0)
            light.SetColor(*color)
            light.SetIntensity(intensity)
            r.AddLight(light)

    def _init_canvas(self) -> None:
        self._canvas = CST3DCanvas(self)
        self._canvas.solid_picked.connect(self.solid_picked)
        self._layout.addWidget(self._canvas)
        self._renderer = None
        self._using_vtk = False

    def _render(self) -> None:
        if self._using_vtk and self._renderer:
            self.ren_win.Render()
        elif self._canvas:
            self._canvas.update()

    def clear(self) -> None:
        if self._using_vtk and self._renderer:
            self._renderer.RemoveAllViewProps()
            self._actors.clear()
            self._base_opacity.clear()
            if self._orientation is None:
                axes = vtk.vtkAxesActor()
                axes.SetTotalLength(1.2, 1.2, 1.2)
                self._renderer.AddActor(axes)
            self._reset_camera()
            self._render()
        elif self._canvas:
            self._canvas.clear()
        self._bounds = None

    def add_box(self, name, bounds, color=(0.3, 0.6, 0.9), opacity=0.8):
        if not self._using_vtk or not self._renderer:
            return
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        cube = vtk.vtkCubeSource()
        cube.SetBounds(xmin, xmax, ymin, ymax, zmin, zmax)
        cube.Update()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(cube.GetOutputPort())
        self._add_actor(name, mapper, color, opacity, bounds, kind="surf",
                        cube_edges=True)

    def add_mesh(self, name, points, faces, color=(0.3, 0.6, 0.9),
                 opacity=0.8, bounds=None, wires=None):
        if not self._using_vtk or not self._renderer:
            return
        if not points or not faces:
            return
        vtk_pts = vtk.vtkPoints()
        vtk_pts.SetNumberOfPoints(len(points))
        for i, pt in enumerate(points):
            vtk_pts.SetPoint(i, float(pt[0]), float(pt[1]), float(pt[2]))
        cells = vtk.vtkCellArray()
        for tri in faces:
            if len(tri) < 3:
                continue
            cells.InsertNextCell(3)
            cells.InsertCellPoint(int(tri[0]))
            cells.InsertCellPoint(int(tri[1]))
            cells.InsertCellPoint(int(tri[2]))
        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_pts)
        poly.SetPolys(cells)
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(poly)
        normals.ComputePointNormalsOff()
        normals.ComputeCellNormalsOn()
        normals.SplittingOff()
        normals.ConsistencyOn()
        normals.AutoOrientNormalsOff()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        mapper.ScalarVisibilityOff()
        if bounds is None:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            zs = [p[2] for p in points]
            bounds = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
        self._add_actor(name, mapper, color, opacity, bounds, kind="surf")
        if wires:
            self._add_wire_actor(name, wires, bounds)

    def add_glyph_line(self, name, p1, p2, color=(0.86, 0.16, 0.16)):
        if vtk is None or not self._using_vtk or not self._renderer:
            return
        src = vtk.vtkLineSource()
        src.SetPoint1(float(p1[0]), float(p1[1]), float(p1[2]))
        src.SetPoint2(float(p2[0]), float(p2[1]), float(p2[2]))
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(src.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*color)
        prop.SetLineWidth(2.4)
        prop.SetRepresentationToWireframe()
        try:
            prop.LightingOff()
        except Exception:
            pass
        self._renderer.AddActor(actor)
        self._actors.append((name, actor, "glyph"))
        xs = (float(p1[0]), float(p2[0]))
        ys = (float(p1[1]), float(p2[1]))
        zs = (float(p1[2]), float(p2[2]))
        self._update_bounds((min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

    def add_glyph_box(self, name, bounds, color=(0.86, 0.16, 0.16)):
        if vtk is None or not self._using_vtk or not self._renderer:
            return
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        cube = vtk.vtkCubeSource()
        cube.SetBounds(xmin, xmax, ymin, ymax, zmin, zmax)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(cube.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*color)
        prop.SetLineWidth(1.6)
        prop.SetRepresentationToWireframe()
        try:
            prop.LightingOff()
        except Exception:
            pass
        self._renderer.AddActor(actor)
        self._actors.append((name, actor, "glyph"))
        self._update_bounds(bounds)

    def add_glyph_point(self, name, xyz, color=(0.16, 0.62, 0.16)):
        if vtk is None or not self._using_vtk or not self._renderer:
            return
        x, y, z = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
        span = 1.0
        if self._bounds:
            span = max(self._bounds[1] - self._bounds[0],
                       self._bounds[3] - self._bounds[2],
                       self._bounds[5] - self._bounds[4], 1.0)
        r = max(span * 0.015, 0.08)
        src = vtk.vtkSphereSource()
        src.SetCenter(x, y, z)
        src.SetRadius(r)
        src.SetThetaResolution(12)
        src.SetPhiResolution(12)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(src.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*color)
        try:
            prop.LightingOff()
        except Exception:
            pass
        self._renderer.AddActor(actor)
        self._actors.append((name, actor, "glyph"))
        self._update_bounds((x - r, x + r, y - r, y + r, z - r, z + r))

    def _style_edge_mapper(self, mapper) -> None:
        mapper.ScalarVisibilityOff()
        try:
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
            mapper.SetRelativeCoincidentTopologyLineOffsetParameters(-2, -8)
        except Exception:
            pass

    def _add_wire_actor(self, name, wires, bounds):
        vtk_pts = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        idx = 0
        for poly in wires:
            if len(poly) < 2:
                continue
            start = idx
            for p in poly:
                vtk_pts.InsertNextPoint(float(p[0]), float(p[1]), float(p[2]))
                idx += 1
            n = idx - start
            lines.InsertNextCell(n)
            for i in range(n):
                lines.InsertCellPoint(start + i)
        if vtk_pts.GetNumberOfPoints() < 2:
            return
        pdata = vtk.vtkPolyData()
        pdata.SetPoints(vtk_pts)
        pdata.SetLines(lines)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(pdata)
        self._style_edge_mapper(mapper)
        self._append_edge_actor(name, mapper, bounds)

    def _add_feature_edge_actor(self, name, input_port, bounds):
        """Fallback outlines when SAB has no B-rep edges (still not triangle mesh)."""
        try:
            fe = vtk.vtkFeatureEdges()
            fe.SetInputConnection(input_port)
            fe.BoundaryEdgesOn()
            fe.FeatureEdgesOn()
            fe.ManifoldEdgesOff()
            fe.NonManifoldEdgesOff()
            fe.ColoringOff()
            fe.SetFeatureAngle(48.0)
            fe.Update()
            out = fe.GetOutput()
            if out is None or out.GetNumberOfLines() < 1:
                return
            pdata = vtk.vtkPolyData()
            pdata.DeepCopy(out)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(pdata)
            self._style_edge_mapper(mapper)
            self._append_edge_actor(name, mapper, bounds)
        except Exception:
            return

    def _append_edge_actor(self, name, mapper, bounds):
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(0.22, 0.22, 0.24)
        prop.SetOpacity(1.0)
        prop.SetLineWidth(1.0)
        prop.SetRepresentationToWireframe()
        try:
            prop.LightingOff()
        except Exception:
            pass
        actor.SetVisibility(0)
        self._renderer.AddActor(actor)
        self._actors.append((name, actor, "wire"))
        if bounds:
            self._update_bounds(bounds)

    def _add_actor(self, name, mapper, color, opacity, bounds, kind="surf",
                   cube_edges=False):
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        try:
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
            n_surf = sum(1 for _n, _a, k in self._actors if k == "surf")
            mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(
                -0.4, -1.0 - 0.15 * n_surf)
        except Exception:
            pass
        prop = actor.GetProperty()
        color = self._lift_color(color)
        prop.SetColor(*color)
        prop.SetAmbientColor(*color)
        prop.SetDiffuseColor(*color)
        # Surfaces start opaque; Transparent mode lowers this in _sync.
        prop.SetOpacity(1.0)
        # Triangle-mesh edges stay off. Cube sources have true CAD edges.
        if cube_edges:
            prop.SetEdgeVisibility(1)
            prop.SetEdgeColor(0.10, 0.10, 0.12)
            prop.SetLineWidth(1.15)
        else:
            prop.SetEdgeVisibility(0)
        try:
            prop.SetInterpolationToFlat()
        except Exception:
            try:
                prop.SetInterpolationToGouraud()
            except Exception:
                prop.SetInterpolationToPhong()
        prop.BackfaceCullingOn()
        prop.SetAmbient(0.78)
        prop.SetDiffuse(0.24)
        prop.SetSpecular(0.0)
        try:
            actor.ForceOpaqueOn()
        except Exception:
            pass
        self._renderer.AddActor(actor)
        self._actors.append((name, actor, kind))
        self._base_opacity[name] = opacity
        if bounds:
            self._update_bounds(bounds)

    def _update_bounds(self, bounds) -> None:
        if self._bounds is None:
            self._bounds = list(bounds)
            return
        for i in range(3):
            self._bounds[2 * i] = min(self._bounds[2 * i], bounds[2 * i])
            self._bounds[2 * i + 1] = max(self._bounds[2 * i + 1], bounds[2 * i + 1])

    def set_hidden(self, names) -> None:
        self._hidden = set(names)
        if self._canvas:
            self._canvas.set_hidden(self._hidden)
        if self._using_vtk:
            self._sync_actor_visibility()
            self._render()

    def set_drawing_mode(self, mode: str) -> None:
        self._drawing_mode = mode
        if self._canvas:
            self._canvas.set_drawing_mode(mode)
        if not self._using_vtk:
            return
        self._sync_actor_visibility()
        self._apply_highlight()
        self._render()

    def select_solid(self, name: str) -> None:
        self._selected = name or ""
        if self._canvas is not None:
            self._canvas._selected = self._selected
            self._canvas.update()
        if self._using_vtk:
            self._apply_highlight()
            self._render()

    def _vtk_left_press(self, _obj, _evt) -> None:
        iren = self.ren_win.GetInteractor()
        if iren is None:
            return
        self._pick_xy = iren.GetEventPosition()

    def _vtk_left_release(self, _obj, _evt) -> None:
        if vtk is None or not self._using_vtk or self._renderer is None:
            return
        iren = self.ren_win.GetInteractor()
        if iren is None:
            return
        x, y = iren.GetEventPosition()
        if self._pick_xy is not None:
            dx = abs(x - self._pick_xy[0]) + abs(y - self._pick_xy[1])
            if dx > 5:
                return
        picker = vtk.vtkPropPicker()
        picker.Pick(float(x), float(y), 0, self._renderer)
        actor = picker.GetActor()
        name = ""
        for n, a, k in self._actors:
            if a is actor and k == "surf":
                name = n
                break
        self.select_solid(name)
        if name:
            self.solid_picked.emit(name)
            try:
                b = actor.GetBounds()
                cx = 0.5 * (b[0] + b[1])
                cy = 0.5 * (b[2] + b[3])
                cz = 0.5 * (b[4] + b[5])
                self.status_coords.emit(f"({cx:.3g}, {cy:.3g}, {cz:.3g})")
            except Exception:
                pass

    def _apply_highlight(self) -> None:
        if not self._using_vtk:
            return
        for n, actor, kind in self._actors:
            if kind != "surf":
                continue
            prop = actor.GetProperty()
            if n == self._selected and self._selected:
                prop.SetAmbient(0.95)
                prop.SetEdgeVisibility(1)
                prop.SetEdgeColor(1.0, 0.82, 0.12)
                prop.SetLineWidth(2.2)
            else:
                prop.SetAmbient(0.78)

    def _sync_actor_visibility(self) -> None:
        mode = self._drawing_mode
        self._set_translucent_pass(mode == "Transparent")
        wired = {n for n, _a, k in self._actors if k == "wire"}
        for name, actor, kind in self._actors:
            hide = name in self._hidden or name.split(":")[-1] in self._hidden
            prop = actor.GetProperty()
            if kind == "wire":
                actor.SetVisibility(0 if hide else 1)
                prop.SetColor(0.22, 0.22, 0.24)
                prop.SetLineWidth(1.15 if mode == "Wireframe" else 1.0)
                continue
            if kind == "glyph":
                actor.SetVisibility(0 if hide else 1)
                continue
            if hide:
                actor.SetVisibility(0)
                continue
            if mode == "Wireframe" and name in wired:
                actor.SetVisibility(0)
                continue
            actor.SetVisibility(1)
            if mode == "Wireframe":
                prop.SetRepresentationToWireframe()
                prop.SetOpacity(1.0)
                prop.BackfaceCullingOn()
                try:
                    actor.ForceOpaqueOn()
                except Exception:
                    pass
            elif mode == "Transparent":
                prop.SetRepresentationToSurface()
                prop.SetOpacity(0.32)
                prop.BackfaceCullingOff()
                try:
                    actor.ForceOpaqueOff()
                except Exception:
                    pass
            else:
                prop.SetRepresentationToSurface()
                prop.SetOpacity(1.0)
                prop.BackfaceCullingOn()
                try:
                    actor.ForceOpaqueOn()
                except Exception:
                    pass

    def set_plane(self, plane: str, negative: bool = False) -> None:
        if not self._using_vtk or not self._renderer:
            if self._canvas:
                self._canvas._view_angle = {"xy": 90, "xz": 0, "yz": 35}.get(plane, 30)
                self._canvas.update()
            return
        pos, up = plane_view_camera(plane, negative=negative)
        cam = self._renderer.GetActiveCamera()
        cam.SetPosition(*pos)
        cam.SetFocalPoint(0.0, 0.0, 0.0)
        cam.SetViewUp(*up)
        cam.ParallelProjectionOn()
        self._parallel = True
        self._reset_camera()
        self._render()

    def set_perspective(self, on: bool = True) -> None:
        self._parallel = not on
        if self._using_vtk and self._renderer:
            self._apply_projection()
            self._render()

    def fit(self) -> None:
        if self._using_vtk and self._renderer:
            self._reset_camera()
            self._render()
        elif self._canvas:
            self._canvas.fit()

    def render_project(self, project_data: dict) -> None:
        if self._using_vtk and self._renderer:
            self._render_vtk(project_data)
        elif self._canvas:
            self._canvas.render_project(project_data)

    def _render_vtk(self, project_data: dict) -> None:
        self.clear()
        materials_map = {}
        for mat in project_data.get("materials", []):
            colour = mat.get("colour", "")
            if colour:
                try:
                    parts = [float(x.strip()) for x in colour.split(",")]
                    if len(parts) >= 3:
                        materials_map[mat["name"]] = tuple(parts[:3])
                except (ValueError, IndexError):
                    pass
        for i, comp in enumerate(project_data.get("components", [])):
            bounds = comp.get("bounds")
            mesh = comp.get("mesh") or {}
            points, faces = mesh.get("points"), mesh.get("faces")
            if not bounds and not (points and faces):
                continue
            mat_name = comp.get("material", "")
            color = self._component_color(comp, materials_map, i)
            opacity = opacity_for(comp.get("name", ""), mat_name)
            name = comp.get("name", f"comp_{i}")
            if points and faces:
                wires = mesh.get("wires") or comp.get("wires") or []
                self.add_mesh(name, points, faces, color, opacity, bounds,
                              wires=wires)
            elif bounds:
                self.add_box(name, bounds, color, opacity)
        for port in project_data.get("ports") or []:
            pname = port.get("name") or f"port{port.get('port_number', '')}"
            if port.get("p1_xyz") and port.get("p2_xyz"):
                self.add_glyph_line(pname, port["p1_xyz"], port["p2_xyz"])
            elif port.get("box"):
                self.add_glyph_box(pname, port["box"], (0.86, 0.16, 0.16))
        for probe in project_data.get("probes") or []:
            xyz = probe.get("xyz")
            if xyz:
                self.add_glyph_point(probe.get("name") or "probe", xyz)
        self.set_drawing_mode(self._drawing_mode)
        if self._selected:
            self._apply_highlight()
        if self._bounds:
            self._reset_camera()
            self._render()

    @staticmethod
    def _component_color(comp, materials_map, index):
        default_colors = [
            (0.95, 0.85, 0.3), (0.3, 0.75, 0.4), (0.8, 0.3, 0.3),
            (0.3, 0.5, 0.9), (0.7, 0.4, 0.7), (0.9, 0.6, 0.2),
            (0.2, 0.6, 0.6), (0.5, 0.5, 0.8), (0.8, 0.5, 0.5),
            (0.4, 0.8, 0.5),
        ]
        colour = comp.get("colour", "")
        if colour:
            try:
                parts = [float(x.strip()) for x in colour.split(",")]
                if len(parts) >= 3:
                    return CST3DViewport._lift_color(tuple(parts[:3]))
            except (ValueError, IndexError):
                pass
        mat_name = comp.get("material", "")
        if mat_name in materials_map:
            return CST3DViewport._lift_color(materials_map[mat_name])
        short = mat_name.split("/")[-1]
        if short in materials_map:
            return CST3DViewport._lift_color(materials_map[short])
        return default_colors[index % len(default_colors)]

    @staticmethod
    def _lift_color(color):
        r, g, b = [max(0.0, min(1.0, float(c))) for c in color[:3]]
        if max(r, g, b) < 0.12:
            return (0.38, 0.38, 0.40)
        return tuple(max(0.0, min(1.0, c * 0.96)) for c in (r, g, b))

    @staticmethod
    def cad_edges_in_mode(mode: str) -> bool:
        """CST Shading/Transparent still draw B-rep silhouettes, not only Wireframe."""
        return mode in ("Wireframe", "Shading", "Transparent")

    def is_vtk_available(self) -> bool:
        return self._using_vtk
