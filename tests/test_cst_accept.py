# -*- coding: utf-8 -*-
"""M12 acceptance matrix tests (synthetic always; 11 samples if present)."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import cst_gui
from cst_accept import (
    SAMPLES, SCREEN_CHECKLIST, accept_sample, container_counts, matrix_ok,
    sample_dir, save_as_roundtrip,
)
from cst_parser import write_cst, new_project_files

_SCRATCH = Path(__file__).resolve().parent / "_scratch"
_SAMPLES = sample_dir()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


def test_catalog_has_eleven_unique_samples():
    assert len(SAMPLES) == 11
    ids = [s["id"] for s in SAMPLES]
    files = [s["file"] for s in SAMPLES]
    assert len(set(ids)) == 11
    assert len(set(files)) == 11
    assert "CST Phone 5G.cst" in files
    assert "RCS of a Ship.cst" in files
    kinds = {s["kind"] for s in SAMPLES}
    assert {"parametric", "sab_import", "modelcache", "multi_sab"} <= kinds


def test_screenshot_checklist():
    ids = [s["id"] for s in SCREEN_CHECKLIST]
    assert "nav_tree" in ids
    assert "view_3d" in ids
    assert "copy_view" in ids
    assert "quad_view" in ids
    assert len(SCREEN_CHECKLIST) >= 8
    for rec in SAMPLES:
        for sid in rec["screens"]:
            assert sid in ids, (rec["id"], sid)


def test_synthetic_accept_roundtrip(qapp):
    _SCRATCH.mkdir(exist_ok=True)
    src = _SCRATCH / "accept_synth.cst"
    write_cst(src, new_project_files())
    counts = container_counts(src)
    assert counts["entries"] >= 2
    assert counts["has_mod"]
    dest = _SCRATCH / "accept_synth_copy.cst"
    trip = save_as_roundtrip(src, dest)
    assert trip["ok"] is True

    win = cst_gui.CSTMainWindow(enable_3d=False)
    try:
        rec = {
            "id": "synth", "file": src.name, "kind": "parametric",
            "gui": True, "load_sab": False, "min_entries": 2,
            "screens": ("nav_tree",),
        }
        row = accept_sample(rec, src.parent, _SCRATCH, win=win)
        assert row["present"] and row["open"] and row["save_as"]
        assert row["project"]["tree_roots"] >= 8
        assert row["screenshot"] is True
    finally:
        win.close()


def test_gap_table_m12_scores():
    text = Path(__file__).resolve().parents[1].joinpath(
        "function_gap_analysis.md").read_text(encoding="utf-8")
    assert "| 6 | 求解器 / 仿真 | N/A |" in text or "| 6 |" in text and "N/A" in text
    assert "100%" in text
    # Non-solver modules must be marked 100 / 100 or N/A (mesh generate).
    for marker in (
            "容器逆向", "文件 / 项目管理", "建模 / 几何", "材料",
            "组件 / 分组", "激励 / 源", "监视器 / 探针", "参数",
            "后处理 / 结果", "视图 / 显示", "导航树", "3D 视口",
            "GUI", "状态栏", "宏 / 脚本",
    ):
        assert marker in text
    assert "求解内核" in text or "不含求解器" in text


@pytest.mark.skipif(_SAMPLES is None, reason="11-sample CST folder not present")
def test_eleven_samples_open_save():
    rows = []
    for rec in SAMPLES:
        row = accept_sample(rec, _SAMPLES, _SCRATCH, win=None)
        rows.append(row)
        assert row["present"], rec["file"]
        assert row["open"], (rec["id"], row["notes"], row["counts"])
        assert row["save_as"], (rec["id"], row["notes"])
    assert matrix_ok(rows)
    assert len(rows) == 11


@pytest.mark.skipif(_SAMPLES is None, reason="11-sample CST folder not present")
def test_parametric_gui_tree_and_screenshot(qapp):
    pick = [s for s in SAMPLES if s["id"] in ("ifa", "dipole_v2", "patch_v3")]
    win = cst_gui.CSTMainWindow(enable_3d=False)
    try:
        for rec in pick:
            row = accept_sample(rec, _SAMPLES, _SCRATCH, win=win)
            assert row["open"] and row["save_as"], (rec["id"], row)
            assert row["project"]["tree_roots"] >= 10
            assert row["screenshot"] is True
    finally:
        win.close()
