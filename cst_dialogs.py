# -*- coding: utf-8 -*-
"""Modeling dialogs for CST Decoding (shapes, boolean, transform, materials)."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QVBoxLayout,
)


def _combo(parent, items, current=""):
    box = QComboBox(parent)
    box.setEditable(True)
    for it in items:
        if it:
            box.addItem(it)
    if current:
        idx = box.findText(current)
        if idx >= 0:
            box.setCurrentIndex(idx)
        else:
            box.setEditText(current)
    elif box.count():
        box.setCurrentIndex(0)
    return box


def _form_dialog(parent, title, fields) -> dict | None:
    """fields: list of (label, key, widget). Returns dict of key -> text or None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    root = QVBoxLayout(dlg)
    form = QFormLayout()
    for label, _key, widget in fields:
        form.addRow(label + ":", widget)
    root.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)
    if dlg.exec_() != QDialog.Accepted:
        return None
    out = {}
    for _label, key, widget in fields:
        if isinstance(widget, QComboBox):
            out[key] = widget.currentText().strip()
        else:
            out[key] = widget.text().strip()
    return out


def shape_dialog(parent, kind: str, components, materials) -> dict | None:
    kind = (kind or "brick").lower()
    comps = list(components) or ["component1"]
    mats = list(materials) or ["PEC", "Vacuum"]
    name = QLineEdit({"brick": "solid1", "cylinder": "cylinder1",
                      "sphere": "sphere1", "torus": "torus1",
                      "cone": "cone1"}.get(kind, "solid1"))
    comp = _combo(parent, comps, comps[0])
    mat = _combo(parent, mats, "PEC" if "PEC" in mats else mats[0])
    fields = [("Name", "name", name),
              ("Component", "component", comp),
              ("Material", "material", mat)]
    if kind == "brick":
        for lab, key, default in (
                ("Xmin", "xmin", "-5"), ("Xmax", "xmax", "5"),
                ("Ymin", "ymin", "-5"), ("Ymax", "ymax", "5"),
                ("Zmin", "zmin", "0"), ("Zmax", "zmax", "1")):
            fields.append((lab, key, QLineEdit(default)))
        title = "Brick"
    elif kind == "cylinder":
        for lab, key, default in (
                ("Radius", "radius", "2"), ("Zmin", "zmin", "0"),
                ("Zmax", "zmax", "10"), ("X center", "cx", "0"),
                ("Y center", "cy", "0")):
            fields.append((lab, key, QLineEdit(default)))
        title = "Cylinder"
    elif kind == "sphere":
        for lab, key, default in (
                ("Radius", "radius", "5"), ("X center", "cx", "0"),
                ("Y center", "cy", "0"), ("Z center", "cz", "0")):
            fields.append((lab, key, QLineEdit(default)))
        title = "Sphere"
    elif kind == "torus":
        for lab, key, default in (
                ("Major radius", "major", "8"), ("Minor radius", "minor", "1.5"),
                ("X center", "cx", "0"), ("Y center", "cy", "0"),
                ("Z center", "cz", "0")):
            fields.append((lab, key, QLineEdit(default)))
        title = "Torus"
    else:
        for lab, key, default in (
                ("Bottom radius", "r_bottom", "4"), ("Top radius", "r_top", "1"),
                ("Zmin", "zmin", "0"), ("Zmax", "zmax", "8"),
                ("X center", "cx", "0"), ("Y center", "cy", "0")):
            fields.append((lab, key, QLineEdit(default)))
        title = "Cone"
    data = _form_dialog(parent, title, fields)
    if data:
        data["kind"] = kind
    return data


def boolean_dialog(parent, solids, op="subtract") -> dict | None:
    labels = list(solids) or []
    if len(labels) < 2:
        return None
    target = _combo(parent, labels, labels[0])
    tool = _combo(parent, labels, labels[1])
    return _form_dialog(parent, f"Boolean {op.title()}", [
        ("Target", "target", target),
        ("Tool", "tool", tool),
    ])


def transform_dialog(parent, solids, mode="translate") -> dict | None:
    labels = list(solids) or []
    if not labels:
        return None
    name = _combo(parent, labels, labels[0])
    fields = [("Shape", "name", name)]
    mode = (mode or "translate").lower()
    if mode == "translate":
        title = "Transform / Translate"
        for lab, key, default in (("Dx", "dx", "0"), ("Dy", "dy", "0"), ("Dz", "dz", "0")):
            fields.append((lab, key, QLineEdit(default)))
    elif mode == "rotate":
        title = "Rotate"
        fields.append(("Axis (x/y/z)", "axis", QLineEdit("z")))
        fields.append(("Angle (deg)", "angle", QLineEdit("90")))
        for lab, key, default in (("Cx", "cx", ""), ("Cy", "cy", ""), ("Cz", "cz", "")):
            fields.append((lab, key, QLineEdit(default)))
    elif mode == "mirror":
        title = "Mirror"
        fields.append(("Plane normal (x/y/z)", "axis", QLineEdit("x")))
        for lab, key, default in (("Cx", "cx", "0"), ("Cy", "cy", "0"), ("Cz", "cz", "0")):
            fields.append((lab, key, QLineEdit(default)))
    else:
        title = "Scale"
        for lab, key, default in (("Sx", "sx", "1"), ("Sy", "sy", "1"), ("Sz", "sz", "1")):
            fields.append((lab, key, QLineEdit(default)))
        for lab, key, default in (("Cx", "cx", ""), ("Cy", "cy", ""), ("Cz", "cz", "")):
            fields.append((lab, key, QLineEdit(default)))
    data = _form_dialog(parent, title, fields)
    if data:
        data["mode"] = mode
    return data


def material_dialog(parent, defaults=None) -> dict | None:
    d = defaults or {}
    fields = [
        ("Name", "name", QLineEdit(d.get("name", "Material1"))),
        ("Epsilon", "epsilon", QLineEdit(str(d.get("epsilon", "1.0")))),
        ("Mu", "mu", QLineEdit(str(d.get("mu", "1.0")))),
        ("Kappa", "kappa", QLineEdit(str(d.get("kappa", "0.0")))),
        ("TanD", "tand", QLineEdit(str(d.get("tand", "0.0")))),
        ("Colour R,G,B", "colour", QLineEdit(str(d.get("colour", "0.75,0.80,0.90")))),
        ("Folder", "folder", QLineEdit(str(d.get("folder", "")))),
    ]
    return _form_dialog(parent, "New Material", fields)


def component_dialog(parent) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("New Component")
    root = QVBoxLayout(dlg)
    form = QFormLayout()
    name = QLineEdit("component1")
    form.addRow("Name:", name)
    root.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    root.addWidget(buttons)
    if dlg.exec_() != QDialog.Accepted:
        return None
    return name.text().strip() or None


def discrete_port_dialog(parent, defaults=None) -> dict | None:
    d = defaults or {}
    fields = [
        ("Port number", "port_number", QLineEdit(str(d.get("port_number", "1")))),
        ("Label", "label", QLineEdit(str(d.get("label", "")))),
        ("Impedance", "impedance", QLineEdit(str(d.get("impedance", "50.0")))),
        ("P1 X", "x1", QLineEdit(str(d.get("x1", "0")))),
        ("P1 Y", "y1", QLineEdit(str(d.get("y1", "0")))),
        ("P1 Z", "z1", QLineEdit(str(d.get("z1", "0")))),
        ("P2 X", "x2", QLineEdit(str(d.get("x2", "0")))),
        ("P2 Y", "y2", QLineEdit(str(d.get("y2", "0")))),
        ("P2 Z", "z2", QLineEdit(str(d.get("z2", "1")))),
        ("Type", "ptype", _combo(parent, ["SParameter", "Voltage", "Current"],
                                 d.get("ptype", "SParameter"))),
    ]
    return _form_dialog(parent, "Discrete Port", fields)


def waveguide_port_dialog(parent, defaults=None) -> dict | None:
    d = defaults or {}
    fields = [
        ("Port number", "port_number", QLineEdit(str(d.get("port_number", "1")))),
        ("Label", "label", QLineEdit(str(d.get("label", "")))),
        ("Orientation", "orientation",
         _combo(parent, ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"],
                d.get("orientation", "zmin"))),
        ("Xmin", "xmin", QLineEdit(str(d.get("xmin", "-10")))),
        ("Xmax", "xmax", QLineEdit(str(d.get("xmax", "10")))),
        ("Ymin", "ymin", QLineEdit(str(d.get("ymin", "-5")))),
        ("Ymax", "ymax", QLineEdit(str(d.get("ymax", "5")))),
        ("Zmin", "zmin", QLineEdit(str(d.get("zmin", "0")))),
        ("Zmax", "zmax", QLineEdit(str(d.get("zmax", "0")))),
    ]
    return _form_dialog(parent, "Waveguide Port", fields)


def monitor_dialog(parent, defaults=None) -> dict | None:
    d = defaults or {}
    fields = [
        ("Name", "name", QLineEdit(str(d.get("name", "e-field (f=2.45)")))),
        ("Field type", "field_type",
         _combo(parent, ["Efield", "Hfield", "Farfield", "Powerflow"],
                d.get("field_type", "Efield"))),
        ("Frequency", "frequency", QLineEdit(str(d.get("frequency", "2.45")))),
        ("Domain", "domain",
         _combo(parent, ["Frequency", "Time"], d.get("domain", "Frequency"))),
        ("Dimension", "dimension",
         _combo(parent, ["Volume", "Surface"], d.get("dimension", "Volume"))),
    ]
    return _form_dialog(parent, "Field Monitor", fields)


def units_dialog(parent, units=None) -> dict | None:
    units = units or {}
    length = _combo(parent, ["mm", "cm", "m", "um", "inch"],
                    units.get("length") or "mm")
    freq = _combo(parent, ["GHz", "MHz", "kHz", "Hz"],
                  units.get("frequency") or "GHz")
    time_u = _combo(parent, ["ns", "ps", "us", "s"],
                    units.get("time") or "ns")
    fmin = QLineEdit(str(units.get("fmin") or "0"))
    fmax = QLineEdit(str(units.get("fmax") or "10"))
    return _form_dialog(parent, "Units", [
        ("Length", "length", length),
        ("Frequency", "frequency", freq),
        ("Time", "time", time_u),
        ("Fmin", "fmin", fmin),
        ("Fmax", "fmax", fmax),
    ])


def history_list_dialog(parent, entries=None) -> list | None:
    """Edit VBA history blocks. Returns the new list, or None if cancelled."""
    rows = []
    for item in entries or []:
        if isinstance(item, dict):
            cap = item.get("caption") or "macro"
            code = item.get("code")
            if isinstance(code, list):
                code = "\n".join(str(ln) for ln in code)
            rows.append({"caption": cap, "code": str(code or "")})
        else:
            rows.append({"caption": str(item), "code": ""})

    dlg = QDialog(parent)
    dlg.setWindowTitle("History List")
    dlg.resize(720, 480)
    root = QVBoxLayout(dlg)
    split = QHBoxLayout()
    lst = QListWidget()
    for rec in rows:
        lst.addItem(rec["caption"])
    split.addWidget(lst, 1)
    right = QVBoxLayout()
    cap_edit = QLineEdit()
    code_edit = QPlainTextEdit()
    code_edit.setPlaceholderText("VBA block")
    right.addWidget(QLabel("Caption"))
    right.addWidget(cap_edit)
    right.addWidget(QLabel("Code"))
    right.addWidget(code_edit, 1)
    split.addLayout(right, 2)
    root.addLayout(split, 1)

    state = {"index": -1}

    def flush():
        i = state["index"]
        if 0 <= i < len(rows):
            rows[i]["caption"] = cap_edit.text().strip() or "macro"
            rows[i]["code"] = code_edit.toPlainText()
            lst.item(i).setText(rows[i]["caption"])

    def show_row(i: int):
        flush()
        state["index"] = i
        if 0 <= i < len(rows):
            cap_edit.setText(rows[i]["caption"])
            code_edit.setPlainText(rows[i]["code"])
        else:
            cap_edit.clear()
            code_edit.clear()

    def on_insert():
        flush()
        rows.append({"caption": "macro", "code": "' VBA\n"})
        lst.addItem("macro")
        lst.setCurrentRow(len(rows) - 1)

    def on_delete():
        i = lst.currentRow()
        if i < 0 or i >= len(rows):
            return
        state["index"] = -1
        rows.pop(i)
        lst.takeItem(i)
        if rows:
            lst.setCurrentRow(min(i, len(rows) - 1))
        else:
            cap_edit.clear()
            code_edit.clear()

    lst.currentRowChanged.connect(show_row)
    btns = QHBoxLayout()
    ins = QPushButton("Insert")
    ins.clicked.connect(on_insert)
    dele = QPushButton("Delete")
    dele.clicked.connect(on_delete)
    btns.addWidget(ins)
    btns.addWidget(dele)
    btns.addStretch(1)
    root.addLayout(btns)
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    root.addWidget(box)
    if rows:
        lst.setCurrentRow(0)
        show_row(0)
    if dlg.exec_() != QDialog.Accepted:
        return None
    flush()
    return rows


def probe_dialog(parent, defaults=None) -> dict | None:
    d = defaults or {}
    fields = [
        ("Name", "name", QLineEdit(str(d.get("name", "probe1")))),
        ("Field", "field_name",
         _combo(parent, ["efield", "hfield", "voltage", "current"],
                d.get("field_name", "efield"))),
        ("X", "x", QLineEdit(str(d.get("x", "0")))),
        ("Y", "y", QLineEdit(str(d.get("y", "0")))),
        ("Z", "z", QLineEdit(str(d.get("z", "0")))),
        ("Orientation", "orientation",
         _combo(parent, ["X", "Y", "Z"], d.get("orientation", "X"))),
    ]
    return _form_dialog(parent, "Probe", fields)


def mesh_properties_dialog(parent, props=None) -> dict | None:
    """Edit existing mesh keywords. Does not generate a mesh."""
    props = dict(props or {})
    keys = list(props.keys()) or [
        "MeshType", "StepsPerWaveNear", "StepsPerWaveFar", "RatioLimitGeometry",
    ]
    defaults = {
        "MeshType": "Hex",
        "StepsPerWaveNear": "10",
        "StepsPerWaveFar": "4",
        "RatioLimitGeometry": "15",
    }
    fields = []
    for key in keys:
        fields.append((key, key, QLineEdit(str(props.get(key, defaults.get(key, ""))))))
    return _form_dialog(parent, "Mesh Properties", fields)
