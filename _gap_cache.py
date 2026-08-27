# -*- coding: utf-8 -*-
"""Cache the sh_cans:top extraction so diagnostics iterate fast."""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(__file__))

CACHE = os.path.join(os.path.dirname(__file__), "_top_mesh.pkl")
SAB = os.path.join(os.path.dirname(__file__), "extracted", "Model", "3D",
                   "CSTphone2022_1.sab")


def load_top(force=False):
    if not force and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    from sab_bodies import extract_bodies
    bodies = extract_bodies(open(SAB, "rb").read())
    top = next(x for x in bodies if x["name"].endswith("sh_cans:top"))
    bot = next(x for x in bodies if x["name"].endswith("sh_cans:bottom"))
    data = {"top": top, "bot": bot}
    with open(CACHE, "wb") as fh:
        pickle.dump(data, fh)
    return data


if __name__ == "__main__":
    d = load_top(force=("-f" in sys.argv))
    t = d["top"]["mesh"]
    print("top points", len(t["points"]), "faces", len(t["faces"]))
    print("top bounds", d["top"]["bounds"])
