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
    # 罐间空隙 (60,-15)/(62,-20) 必须保持为空：变体 coedge 布局曾把多罐
    # 轮廓焊成一张跨罐的灰色 spanning 面覆盖这里，现在多罐已按簇分离。
    assert not _mesh_covers(mesh, (60.0, -15.0, -4.275))
    assert not _mesh_covers(mesh, (62.0, -20.0, -4.275))
    # 罐 A 底部与罐 B 一样是开口：薄壁屏蔽罩的底面只是墙体底缘围成的环形
    # 框架（face0 把 can A 作为孔、can B 作为缺口，模型里并不存在 can A 底板
    # 面），两罐内腔在底层开放。face4 的 wrap fallback 曾误把整个底面（含
    # can A）填满——既与 face0 共面重叠造成 z-fight 条纹，又错误盖住开口。
    assert not _mesh_covers(mesh, (45.0, -18.0, -4.275))
    assert not _mesh_covers(mesh, (32.0, -23.0, -4.275))  # 左下凹口保留
    # 顶盖是一整块连续板（罩住两罐），罐间 (60,-15)/(62,-20) 在顶层被盖住；
    # 凹口 (32,-23) 在各层都保留。侧墙补齐后实体才有厚度（原先只有悬空薄片）。
    assert _mesh_covers(mesh, (60.0, -15.0, -3.2775))
    assert _mesh_covers(mesh, (62.0, -20.0, -3.2775))
    assert _mesh_covers(mesh, (45.0, -18.0, -3.2775))
    assert not _mesh_covers(mesh, (32.0, -23.0, -3.2775))
    # 侧墙：顶盖与底层之间的竖直壁面必须存在（法线水平的三角形）。
    pts = np.asarray(mesh["points"], dtype=float)
    has_wall = False
    for f in mesh["faces"]:
        a, b_, c = pts[f[0]], pts[f[1]], pts[f[2]]
        n = np.cross(b_ - a, c - a)
        ln = float(np.linalg.norm(n))
        if ln < 1e-12:
            continue
        if abs(n[2] / ln) < 0.2:  # 法线近水平 -> 竖直壁面
            zspan = max(a[2], b_[2], c[2]) - min(a[2], b_[2], c[2])
            if zspan > 0.5:
                has_wall = True
                break
    assert has_wall, "shield-can side walls missing (solid has no thickness)"
    # Local-frame nubs glued onto world vertices used to draw a 190 mm
    # trapezoid at z≈33; CAD wires must stay inside the body AABB.
    zmin, zmax = top["bounds"][4], top["bounds"][5]
    for w in (top.get("wires") or []):
        for p in w:
            assert zmin - 1.5 <= p[2] <= zmax + 1.5
            assert top["bounds"][0] - 2.0 <= p[0] <= top["bounds"][1] + 2.0
            assert top["bounds"][2] - 2.0 <= p[1] <= top["bounds"][3] + 2.0
    # Fillet / nubs samples add CAD wires; a spanning scribble used to
    # emit hundreds. A handful of cans stays well under this cap.
    assert len(top.get("wires") or []) < 150
    # Underside cans stay five boxes (40 verts).  A couple of extra
    # triangles on a lid (both diagonals) is harmless; a wrap would
    # add vertices and dozens of faces.
    assert len(bot["mesh"]["points"]) == 40
    assert 60 <= len(bot["mesh"]["faces"]) <= 72
    assert len(mesh["faces"]) >= 2


def test_sh_cans_top_mesh_outward_consistent():
    """Closed-solid triangles must be oriented outward consistently, else
    back-face culling carves streaky see-through holes into the plate (the
    'torn' look on sh_cans:top).  Interior step faces leave a few non-manifold
    edges, so require a large consistent majority plus positive volume."""
    path = os.path.normpath(SAB)
    if not os.path.exists(path):
        return
    bodies = extract_bodies(open(path, "rb").read())
    top = next(b for b in bodies if b["name"].endswith("sh_cans:top"))
    mesh = top["mesh"]
    pts = [np.asarray(p, dtype=float) for p in mesh["points"]]
    faces = mesh["faces"]
    edge_dir = {}
    for f in faces:
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            key = (min(a, b), max(a, b))
            edge_dir.setdefault(key, []).append(1 if (a, b) == key else -1)
    shared = [v for v in edge_dir.values() if len(v) == 2]
    consistent = sum(1 for v in shared if v[0] != v[1])
    # before the outward-orientation pass roughly half the shared edges were
    # traversed same-direction; afterwards the visible shell is consistent.
    assert consistent >= 0.8 * len(shared)
    vol = 0.0
    for f in faces:
        a, b, c = pts[f[0]], pts[f[1]], pts[f[2]]
        vol += float(np.dot(a, np.cross(b, c)))
    assert vol > 0.0


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


def test_clip_poly_rejects_local_frame_nubs():
    from sab_bodies import _clip_poly_to_ends
    a = (53.968, -16.907, -4.275)
    b = (53.968, -16.907, -3.577)
    junk = [
        a,
        (0.0, 1.0, 33.423),
        (-8.83, -2.491, 33.423),
        (0.0, 1.0, 0.0),
        b,
    ]
    out = _clip_poly_to_ends(junk, a, b)
    assert len(out) == 2
    assert abs(float(out[0][2]) + 4.275) < 0.01
    assert abs(float(out[1][2]) + 3.577) < 0.01


def test_drop_weld_keeps_tab_splits_bridge():
    from sab_bodies import _drop_weld_edges, _cluster_edge_groups
    can_a = [
        [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
        [(20.0, 0.0, 0.0), (20.0, 10.0, 0.0)],
        [(20.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        [(0.0, 10.0, 0.0), (0.0, 0.0, 0.0)],
        [(20.0, 10.0, 0.0), (48.0, 10.0, 0.0)],  # 28 mm tab, far vertex only
    ]
    can_b = [
        [(70.0, 0.0, 0.0), (80.0, 0.0, 0.0)],
        [(80.0, 0.0, 0.0), (80.0, 10.0, 0.0)],
        [(80.0, 10.0, 0.0), (70.0, 10.0, 0.0)],
        [(70.0, 10.0, 0.0), (70.0, 0.0, 0.0)],
    ]
    bridge = [[(20.0, 0.0, 0.0), (70.0, 0.0, 0.0)]]
    kept = _drop_weld_edges(can_a + can_b + bridge)
    lens = [((e[0][0] - e[-1][0]) ** 2 + (e[0][1] - e[-1][1]) ** 2) ** 0.5
            for e in kept]
    assert max(lens) < 35.0  # 50 mm bridge dropped
    assert any(abs(l - 28.0) < 0.1 for l in lens)  # tab kept
    assert len(_cluster_edge_groups(kept)) == 2


def test_nubs_polyline_skips_surface_net():
    from sab_bodies import _nubs_world_polyline
    curve = {"type": "nubs", "fields": [
        ("f64", 0.0), ("f64", 0.0), ("f64", 0.0),
        ("f64", 2.0), ("f64", 0.1), ("f64", 0.0),
        ("f64", 4.0), ("f64", 0.0), ("f64", 0.0),
        ("f64", 6.0), ("f64", -0.1), ("f64", 0.0),
    ]}
    pts = _nubs_world_polyline(curve)
    assert len(pts) >= 3
    xs = [float(p[0]) for p in pts]
    assert min(xs) < 0.5
    assert max(xs) > 5.5
    net = {"type": "nubs", "fields": []}
    for x in (0.0, 1.0, 2.0):
        for y in (0.0, 1.0, 2.0):
            net["fields"].extend([("f64", x), ("f64", y), ("f64", 0.0)])
    assert _nubs_world_polyline(net) == []


def test_disjoint_edge_clusters():
    from sab_bodies import _cluster_edge_groups, _hull_groups_from_edges
    sq1 = [
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        [(2.0, 0.0, 0.0), (2.0, 2.0, 0.0)],
        [(2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        [(0.0, 2.0, 0.0), (0.0, 0.0, 0.0)],
    ]
    sq2 = [
        [(20.0, 0.0, 0.0), (22.0, 0.0, 0.0)],
        [(22.0, 0.0, 0.0), (22.0, 2.0, 0.0)],
        [(22.0, 2.0, 0.0), (20.0, 2.0, 0.0)],
        [(20.0, 2.0, 0.0), (20.0, 0.0, 0.0)],
    ]
    assert len(_cluster_edge_groups(sq1 + sq2)) == 2
    surf = {"type": "plane", "fields": [
        ("pos", (0.0, 0.0, 0.0)), ("vec", (0.0, 0.0, 1.0)), ("vec", (1.0, 0.0, 0.0)),
    ]}
    groups = _hull_groups_from_edges(sq1 + sq2, surf)
    assert len(groups) == 2
    mid = (11.0, 1.0, 0.0)
    from sab_bodies import _triangulate_plane
    tris = []
    for g in groups:
        tris.extend(_triangulate_plane(g))
    mesh = {"points": [p for tri in tris for p in tri],
            "faces": [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris))]}
    assert not _mesh_covers(mesh, mid)
    assert _mesh_covers(mesh, (1.0, 1.0, 0.0))
    assert _mesh_covers(mesh, (21.0, 1.0, 0.0))
    # A leftover intcurve chord must not merge the two cans into one wrap.
    bridge = [[(2.0, 1.0, 0.0), (20.0, 1.0, 0.0)]]
    groups2 = _hull_groups_from_edges(sq1 + sq2 + bridge, surf)
    assert len(groups2) == 2
    tris2 = []
    for g in groups2:
        tris2.extend(_triangulate_plane(g))
    mesh2 = {"points": [p for tri in tris2 for p in tri],
             "faces": [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris2))]}
    assert not _mesh_covers(mesh2, mid)


def test_notched_island_keeps_opening():
    """Chained can outlines must keep concave notches (convex hull would fill)."""
    from sab_bodies import _hull_groups_from_edges, _triangulate_plane
    # U-shape opening to +x: the bay at (7, 3) is empty only if we chain.
    edges = [
        [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0)],
        [(8.0, 0.0, 0.0), (8.0, 2.0, 0.0)],
        [(8.0, 2.0, 0.0), (3.0, 2.0, 0.0)],
        [(3.0, 2.0, 0.0), (3.0, 4.0, 0.0)],
        [(3.0, 4.0, 0.0), (8.0, 4.0, 0.0)],
        [(8.0, 4.0, 0.0), (8.0, 6.0, 0.0)],
        [(8.0, 6.0, 0.0), (0.0, 6.0, 0.0)],
        [(0.0, 6.0, 0.0), (0.0, 0.0, 0.0)],
    ]
    surf = {"type": "plane", "fields": [
        ("pos", (0.0, 0.0, 0.0)), ("vec", (0.0, 0.0, 1.0)), ("vec", (1.0, 0.0, 0.0)),
    ]}
    groups = _hull_groups_from_edges(edges, surf)
    assert len(groups) == 1
    tris = _triangulate_plane(groups[0])
    mesh = {"points": [p for tri in tris for p in tri],
            "faces": [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(tris))]}
    assert not _mesh_covers(mesh, (6.0, 3.0, 0.0))
    assert _mesh_covers(mesh, (1.5, 3.0, 0.0))
    assert _mesh_covers(mesh, (6.0, 0.8, 0.0))
