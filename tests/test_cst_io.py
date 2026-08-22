# -*- coding: utf-8 -*-
"""DE-ZIP read/write roundtrip."""

from pathlib import Path

from cst_parser import open_cst, write_cst, new_project_files, CstParseError

_SCRATCH = Path(__file__).resolve().parent / "_scratch"


def _tmp(name: str) -> Path:
    _SCRATCH.mkdir(exist_ok=True)
    path = _SCRATCH / name
    if path.exists():
        path.unlink()
    return path


def test_write_open_roundtrip():
    payload = {
        "Model/3D/Model.mod": b"With Units\nEnd With\n",
        "Model/Parameters.json": b'{"parameters":[],"version":1}\n',
        "notes/hello.txt": b"hello",
    }
    path = _tmp("round.cst")
    write_cst(path, payload.items())
    meta, entries = open_cst(path)
    assert meta.get("cst_version", "").startswith("2024")
    by_name = {e["name"]: e["content"] for e in entries}
    assert by_name["Model/3D/Model.mod"] == payload["Model/3D/Model.mod"]
    assert by_name["Model/Parameters.json"] == payload["Model/Parameters.json"]
    assert by_name["notes/hello.txt"] == b"hello"
    assert all(e.get("crc_ok") for e in entries)


def test_new_project_files_roundtrip():
    path = _tmp("new.cst")
    write_cst(path, new_project_files())
    _meta, entries = open_cst(path)
    names = {e["name"].replace("\\", "/") for e in entries}
    assert "Model/3D/Model.mod" in names
    assert "Model/Parameters.json" in names


def test_write_rejects_empty():
    try:
        write_cst(_tmp("empty.cst"), [])
        raise AssertionError("expected CstParseError")
    except CstParseError:
        pass
