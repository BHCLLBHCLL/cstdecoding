# -*- coding: utf-8 -*-
"""Parse and plot CST 1D / farfield results (no solver)."""

import os
import struct
from pathlib import Path

from cst_results import (
    curve_to_csv, farfield_cut, parse_ascii_xy, parse_farfield_dat,
    parse_r1d, parse_result_bytes, result_has_curve, result_has_grid,
)

_SCRATCH = Path(__file__).resolve().parent / "_scratch"
_SHIP_DAT = Path(__file__).resolve().parent.parent / "extracted_ship" / "Result" / "farfield_TOTAL1.dat"
_R1D = Path(__file__).resolve().parent.parent / "extracted" / "Model" / "3D" / "beam-3-1-boreH.r1d"

_MINI_FF = """CST Farfield Format V1

Dimension     = 2
Frequency     = 1e9
Type          = BISTATICRCS

// = Theta Phi Re(E_Theta) Im(E_Theta) Re(E_Phi) Im(E_Phi)

0	0	3	4	0	0
10	0	0	5	0	0
20	0	8	6	0	0
0	90	1	0	0	0
10	90	0	1	0	0
20	90	0	0	1	0
"""


def _pack_r1d(meta: dict, script: str = "") -> bytes:
    def s(text):
        raw = (text or "").encode("latin-1") + b"\x00"
        return struct.pack("<i", len(raw)) + raw

    out = struct.pack("<ii", 3, 1)
    out += s("2024|0|test") + s("2024|0|test")
    out += struct.pack("<i", len(meta))
    for k, v in meta.items():
        out += s(k) + s(v)
    raw = script.encode("latin-1")
    out += struct.pack("<i", len(raw)) + raw
    return out


def test_parse_ascii_xy():
    rec = parse_ascii_xy("# freq dB\n1.0 -10\n2.0 -12\n3.0 -11\n")
    assert rec["x"] == [1.0, 2.0, 3.0]
    assert rec["y"][1] == -12.0
    assert result_has_curve(rec)
    csv = curve_to_csv(rec)
    assert "2.0,-12.0" in csv or "2.0,-12" in csv


def test_parse_farfield_mini():
    rec = parse_farfield_dat(_MINI_FF)
    assert result_has_grid(rec)
    assert rec["theta"] == [0.0, 10.0, 20.0]
    assert rec["phi"] == [0.0, 90.0]
    assert abs(rec["grid"][0][0] - 5.0) < 1e-9  # |3+4j|
    cut = farfield_cut(rec, phi=0.0)
    assert cut["x"] == [0.0, 10.0, 20.0]
    assert abs(cut["y"][1] - 5.0) < 1e-9
    assert result_has_curve(rec)


def test_parse_r1d_template_has_meta_no_curve():
    blob = _pack_r1d({"TemplateType": "1D", "labletext": "S1,1", "Linear": "dB"})
    rec = parse_r1d(blob)
    assert rec["meta"]["TemplateType"] == "1D"
    assert rec["title"] == "S1,1"
    assert rec["x"] == []
    assert not result_has_curve(rec)


def test_parse_r1d_with_xy_tail():
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [-1.0, -2.0, -1.5, -3.0]
    tail = b"".join(struct.pack("<d", v) for v in xs + ys)
    blob = _pack_r1d({"TemplateType": "1D", "labletext": "trace"}) + tail
    rec = parse_r1d(blob)
    assert result_has_curve(rec)
    assert rec["x"] == xs
    assert rec["y"] == ys


def test_parse_result_bytes_auto():
    rec = parse_result_bytes(_MINI_FF.encode("ascii"), "farfield_TOTAL1.dat")
    assert rec["format"] == "farfield"
    assert result_has_grid(rec)


def test_ship_farfield_if_present():
    if not _SHIP_DAT.is_file():
        return
    rec = parse_farfield_dat(_SHIP_DAT.read_text(encoding="latin-1"))
    assert result_has_grid(rec)
    assert result_has_curve(rec)
    assert len(rec["x"]) >= 8


def test_extracted_r1d_template_if_present():
    if not _R1D.is_file():
        return
    rec = parse_r1d(_R1D.read_bytes())
    assert rec["meta"].get("TemplateType") == "1D"
    assert rec["script"]
