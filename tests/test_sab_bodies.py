# -*- coding: utf-8 -*-
"""Tests for SAB per-body extraction (phone.cst internals)."""

import os

import numpy as np

from sab_bodies import _inside_tri, _triangulate_plane, extract_bodies, opacity_for

SAB = os.path.join(os.path.dirname(__file__), "..",
                   "extracted", "Model", "3D", "CSTphone2022_1.sab")


def _mesh_covers(mesh, point, plane_tol=0.08) -> bool:
    pts = np.asarray(mesh["points"], dtype=float)
    point = np.asarray(point, dtype=float)
    for f in mesh["faces"]:
        a, b, c = pts[f[0]], pts[f[1]], pts[f[2]]
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm)
        if ln < 1e-16:
            continue
        nrm = nrm / ln
        if abs(float(np.dot(point - a, nrm))) > plane_tol:
            continue
        tmp = np.array([1.0, 0.0, 0.0]) if abs(nrm[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(nrm, tmp)
        u = u / np.linalg.norm(u)
        v = np.cross(nrm, u)

        def pr(p):
            w = p - a
            return (float(np.dot(w, u)), float(np.dot(w, v)))

        if _inside_tri(pr(a), pr(b), pr(c), pr(point)):
            return True
    return False


def test_plane_hole_is_not_filled():
    outer = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
             (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)]
    hole = [(4.0, 4.0, 0.0), (6.0, 4.0, 0.0),
            (6.0, 6.0, 0.0), (4.0, 6.0, 0.0)]
    tris = _triangulate_plane([outer, hole])
    assert len(tris) >= 8
    mesh = {"points": [p for tri in tris for p in tri],
            "faces": [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris))]}
    assert not _mesh_covers(mesh, (5.0, 5.0, 0.0))
    assert _mesh_covers(mesh, (1.0, 1.0, 0.0))
    assert _mesh_covers(mesh, (9.0, 5.0, 0.0))


def test_join_samples_flips_first_edge():
    from sab_bodies import _join_samples
    import numpy as np
    a = np.array([86.86, -29.89, 0.0])
    b = np.array([86.86, -6.62, 0.0])
    c = np.array([-7.04, -29.89, 0.0])
    poly = _join_samples([a, b], [c, a])
    assert len(poly) == 3
    assert abs(float(poly[0][1]) + 6.62) < 0.05
    assert abs(float(poly[-1][0]) + 7.04) < 0.05


def test_concave_c_opening_not_filled():
    """A C-shaped board: the opening must stay empty (CST PCB cutouts)."""
    outer = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 3.0, 0.0),
        (3.0, 3.0, 0.0), (3.0, 7.0, 0.0), (10.0, 7.0, 0.0),
        (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
    ]
    tris = _triangulate_plane([outer])
    assert len(tris) >= 6
    mesh = {"points": [p for tri in tris for p in tri],
            "faces": [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris))]}
    assert not _mesh_covers(mesh, (7.0, 5.0, 0.0))
    assert _mesh_covers(mesh, (1.0, 5.0, 0.0))
    assert _mesh_covers(mesh, (8.0, 1.0, 0.0))


def test_mmbrd_cutout_not_filled():
    """Main PCB fill must stay inside the CAD outline (no spanning ears)."""
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    mmbrd = next(b for b in bodies if b["name"].endswith(":mmbrd"))
    mesh = mmbrd["mesh"]
    # Battery bay to the right of the stem (x>25, y>-6.62) stays empty.
    assert not _mesh_covers(mesh, (40.0, 10.0, -6.316))
    assert not _mesh_covers(mesh, (70.0, 0.0, -6.316))
    assert _mesh_covers(mesh, (10.0, 20.0, -6.316))
    assert _mesh_covers(mesh, (0.0, 27.0, -4.275))
    assert _mesh_covers(mesh, (50.0, -18.0, -6.316))


def test_mdbrd_steps_not_webbed():
    """Side PCB strip must not span the stepped left cutout."""
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    mdbrd = next(b for b in bodies if b["name"].endswith(":mdbrd"))
    mesh = mdbrd["mesh"]
    assert not _mesh_covers(mesh, (100.0, 0.0, -6.191))
    assert not _mesh_covers(mesh, (100.0, -10.0, -6.191))
    assert _mesh_covers(mesh, (110.0, 0.0, -6.191))
    assert _mesh_covers(mesh, (110.0, 20.0, -6.191))


def test_sh_cans_top_not_spanning():
    """Top shield-can layer must not scribble a spanning grey face on the PCB."""
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    top = next(b for b in bodies if b["name"].endswith("sh_cans:top"))
    bot = next(b for b in bodies if b["name"].endswith("sh_cans:bottom"))
    mesh = top["mesh"]
    # Incomplete fillet loops used to fill this as one grey triangle.
    assert not _mesh_covers(mesh, (45.0, -18.0, -4.275))
    assert len(top.get("wires") or []) < 80
    # Underside cans stay five boxes; top still has some side/top faces.
    assert len(bot["mesh"]["faces"]) == 60
    assert len(bot["mesh"]["points"]) == 40
    assert len(mesh["faces"]) >= 2


def test_phone_sab_has_internal_solids():
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    assert len(bodies) >= 100
    names = {b["name"] for b in bodies}
    assert "Phone/Battery:Cell" in names
    assert "Phone/Camera:Lens" in names
    assert "Phone/Housing:cover" in names
    bboxes = {b["bounds"] for b in bodies}
    assert len(bboxes) > 20  # not one shared monitor subvolume
    meshed = [b for b in bodies if b.get("mesh", {}).get("faces")]
    assert len(meshed) == len(bodies)
    battery = next(b for b in bodies if b["name"] == "Phone/Battery:Cell")
    assert len(battery["mesh"]["faces"]) == 12
    assert len(battery["mesh"]["points"]) == 8
    lens = next(b for b in bodies if b["name"] == "Phone/Camera:Lens")
    assert len(lens["mesh"]["faces"]) > 24
    pins = [b for b in bodies if b["name"].endswith(":Pin")]
    assert pins and len(pins[0]["mesh"]["faces"]) > 24
    cover = next(b for b in bodies if b["name"] == "Phone/Housing:cover")
    pts = cover["mesh"]["points"]
    # Quarter-pipe fillets must not emit the inner half of a full cylinder
    # (that used to draw rings through the phone interior).
    assert not any(abs(p[0] - 96.385) < 0.6 and abs(p[1] + 22.0) < 0.6
                   for p in pts)
    assert len(battery.get("wires") or []) == 12
    cover_wires = cover.get("wires") or []
    assert cover_wires
    assert len(cover_wires) < len(cover["mesh"]["faces"])
    # Wires are CAD edges, not spanning tessellation diagonals across the cover.
    assert all(len(w) >= 2 for w in cover_wires)


def test_cover_camera_hole_not_filled():
    """Cover top/bottom must keep the camera cutout empty (CST shows a hole)."""
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    cover = next(b for b in bodies if b["name"] == "Phone/Housing:cover")
    mesh = cover["mesh"]
    for pt in ((0.0, 0.0, 0.0), (0.0, 0.0, -0.3),
               (4.0, 0.0, 0.0), (0.0, 4.0, -0.3)):
        assert not _mesh_covers(mesh, pt), pt
    assert _mesh_covers(mesh, (50.0, 0.0, 0.0))
    assert _mesh_covers(mesh, (50.0, 0.0, -0.3))
    assert _mesh_covers(mesh, (96.0, 0.0, 0.0))


def test_cma_arm_wires_stay_in_bounds():
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    arm = next((b for b in bodies if b["name"].endswith("CMA_antenna:arm1")), None)
    if arm is None:
        return
    bb = arm["bounds"]
    pad = 0.6
    for w in arm.get("wires") or []:
        for p in w:
            assert bb[0] - pad <= p[0] <= bb[1] + pad
            assert bb[2] - pad <= p[1] <= bb[3] + pad
            assert bb[4] - pad <= p[2] <= bb[5] + pad
        chord = ((w[0][0] - w[-1][0]) ** 2 + (w[0][1] - w[-1][1]) ** 2
                 + (w[0][2] - w[-1][2]) ** 2) ** 0.5
        diag = ((bb[1] - bb[0]) ** 2 + (bb[3] - bb[2]) ** 2
                + (bb[5] - bb[4]) ** 2) ** 0.5
        assert chord <= diag + pad


def test_opacity_cover_vs_metal():
    assert opacity_for("Phone/Housing:cover", "Phone/PlasticCover") < 0.3
    assert opacity_for("Phone/Battery:Cell", "Phone/Copper (annealed)") > 0.8
    assert opacity_for("Phone/Housing:ring", "Phone/Plastic") > 0.9
    assert opacity_for("Phone/Fillers and Shields:foam1", "Phone/Vacuum") < 0.1
