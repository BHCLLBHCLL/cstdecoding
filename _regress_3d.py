# -*- coding: utf-8 -*-
"""Real-project 3D interaction regression on the desktop GL path.

Unlike tests/test_cst_gui.py (which forces QT_QPA_PLATFORM=offscreen and
disable_3d), this runs the real QVTKRenderWindowInteractor against the
desktop OpenGL driver, loads the phone sample project, exercises camera
interaction and drawing modes, and writes screenshots for visual review.

Run:  python _regress_3d.py            (opens a visible window briefly)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(os.path.abspath(__file__))
PHONE_DIR = os.path.join(HERE, "phone")
PHONE_CST = os.path.join(HERE, "_phone_regress.cst")
OUT = os.path.join(HERE, "_regress_out")


def build_cst():
    """Pack the extracted phone/ tree into a .cst container.

    The .cst format is a CST-specific "DE-ZIP" variant (PK sigs replaced by DE,
    plus an extra 4-byte field in each header), so a plain zipfile write is
    rejected by cst_parser.  Use the project's own writer which produces the
    exact container layout the loader expects.
    """
    if os.path.exists(PHONE_CST):
        return PHONE_CST
    from cst_parser import write_cst
    files = []
    for root, _dirs, fns in os.walk(PHONE_DIR):
        for fn in fns:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, PHONE_DIR).replace("\\", "/")
            with open(full, "rb") as fh:
                files.append((rel, fh.read()))
    files.sort()
    write_cst(PHONE_CST, files)
    return PHONE_CST


def main():
    os.makedirs(OUT, exist_ok=True)
    cst = build_cst()
    print("project:", cst, os.path.getsize(cst), "bytes")

    # Real desktop GL: do NOT set QT_QPA_PLATFORM=offscreen.
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt, QTimer
    import cst_gui

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    win = cst_gui.CSTMainWindow(cst, enable_3d=True)
    win.resize(1280, 800)
    win.show()
    app.processEvents()

    vp = win.viewport
    using_vtk = getattr(vp, "_using_vtk", False)
    n_actors = len(getattr(vp, "_actors", []))
    print("viewport using_vtk:", using_vtk)
    print("viewport actors:", n_actors)

    # --- AA diagnostics: confirm MSAA on / FXAA off on the live GL context ---
    if using_vtk:
        rw = vp.ren_win
        r = vp._renderer
        try:
            print("AA state -> MultiSamples:", rw.GetMultiSamples(),
                  "| UseFXAA:", r.GetUseFXAA())
        except Exception as e:
            print("AA state err:", e)
    modes = [m for m, _a, k in getattr(vp, "_actors", [])]
    print("surf actors:", sum(1 for _n, _a, k in getattr(vp, "_actors", []) if k == "surf"))

    results = {"using_vtk": using_vtk, "actors": n_actors, "checks": []}

    def snap(tag):
        win.repaint()
        app.processEvents()
        time.sleep(0.05)
        pm = win.grab()
        path = os.path.join(OUT, f"{tag}.png")
        pm.save(path)
        results["checks"].append((tag, path))
        print("snapshot:", path)

    # let load finish
    t0 = time.time()
    while time.time() - t0 < 30.0:
        app.processEvents()
        if getattr(win, "_project_data", None):
            break
        time.sleep(0.05)

    # --- diagnostics: why is the viewport empty? ---
    pd = getattr(win, "_project_data", {}) or {}
    print("project_data keys:", list(pd.keys()))
    print("components:", len(pd.get("components", [])))
    print("sab solids:", len(pd.get("sab_solids", []) if "sab_solids" in pd else pd.get("solids", [])))
    for k in ("components", "solids", "sab_solids", "bodies"):
        v = pd.get(k)
        if isinstance(v, list) and v:
            print(f"  {k}[0] keys:", list(v[0].keys()) if isinstance(v[0], dict) else type(v[0]))
    try:
        from cst_parser import open_cst
        meta, entries = open_cst(cst)
        sabs = win._load_sab_components(cst, entries)
        print("_load_sab_components -> bodies:", len(sabs))
        if sabs:
            print("  body[0]:", sabs[0]["name"], "faces:", len(sabs[0].get("mesh", {}).get("faces", [])))
    except Exception as exc:
        import traceback; traceback.print_exc()
        print("sab load diag FAILED:", exc)
    snap("01_loaded")

    # camera interaction: orbit / zoom via VTK interactor style calls
    try:
        cam = vp._renderer.GetActiveCamera()
        cam.Azimuth(30); cam.Elevation(15)
        vp._render(); app.processEvents()
        snap("02_orbit")
        cam.Zoom(1.5)
        vp._render(); app.processEvents()
        snap("03_zoom")
        results["checks"].append(("camera", "ok"))
    except Exception as exc:
        results["checks"].append(("camera", f"FAIL {exc}"))

    # drawing modes
    for mode in ("Shading", "Wireframe", "Mesh", "Transparent", "BoundingBox"):
        try:
            vp.set_drawing_mode(mode)
            vp._render(); app.processEvents()
            snap(f"mode_{mode.lower()}")
            results["checks"].append((f"mode_{mode}", "ok"))
        except Exception as exc:
            results["checks"].append((f"mode_{mode}", f"FAIL {exc}"))

    # CAD edges toggle
    try:
        vp.set_cad_edges(True)
        vp._render(); app.processEvents()
        snap("04_cad_edges")
        results["checks"].append(("cad_edges", "ok"))
    except Exception as exc:
        results["checks"].append(("cad_edges", f"FAIL {exc}"))

    # fit + reset camera
    try:
        vp.fit()
        vp._render(); app.processEvents()
        snap("05_fit")
        results["checks"].append(("fit", "ok"))
    except Exception as exc:
        results["checks"].append(("fit", f"FAIL {exc}"))

    ok = using_vtk and n_actors > 0
    print("\n=== REGRESSION RESULT ===")
    print("using_vtk:", using_vtk, "actors:", n_actors, "->", "PASS" if ok else "FAIL")
    for tag, val in results["checks"]:
        print(f"  {tag}: {val}")
    win.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
