"""Tests for the building materials (Track E2). No downloads needed: the texture tests use a stand-in grain.

    python3 -I -m pytest Tools/envloop/buildmat/test_buildmat.py -q      (or: python3 -I Tools/envloop/buildmat/test_buildmat.py)
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop", "dock"))

import buildmat_hlsl as BH   # noqa: E402
import interior as INT       # noqa: E402
import make_textures as MT   # noqa: E402
import pack as P             # noqa: E402
import wear                  # noqa: E402


def _stub_grain():
    """Replace the CC0 scans with seeded noise so the tests run without fetch_sources.py."""
    def g(sid, tile_w, tile_h, pw, ph, channel="height", hp=12.0):
        rng = np.random.default_rng(abs(hash((sid, pw, ph, hp))) % 2 ** 32)
        a = rng.normal(0, 1, (ph, pw))
        a = a - MT.blur(a, hp)
        return a / a.std()
    MT.grain = g


def test_cards_match_slots():
    """The north-texas-lake pack's finishes keep the parts kit's ids (slots.json: wall 0..6, roof 0..4)."""
    c = MT.cards()
    assert c["pack"] == "north-texas-lake"
    assert [w["name"] for w in c["walls"]] == ["brick_red", "brick_brown", "brick_buff", "limestone", "lap_siding", "board_batten", "stucco"]
    assert [r["name"] for r in c["roofs"]] == ["shingle_weathered_wood", "shingle_charcoal", "shingle_barkwood", "metal_seam", "membrane_flat"]
    for kind in ("walls", "roofs"):
        for i, w in enumerate(c[kind]):
            assert w["id"] == i


def test_every_pack_is_data_only():
    """Each pack in packs/ loads: known classes, ids 0.. in order, test houses that name its own finishes. The code
    branches on class, never on a finish name, so a new region needs no code."""
    for f in sorted(os.listdir(os.path.join(HERE, "packs"))):
        p = P.load(f[:-5])
        names = {x["name"] for x in p["walls"] + p["roofs"]}
        for kind in ("walls", "roofs"):
            assert [x["id"] for x in p[kind]] == list(range(len(p[kind]))), f
            for x in p[kind]:
                assert x["class"] in MT.MAKERS and x["class"] in P.CLASSES
        for h in p["test_houses"].values():
            assert h["wall"] in names and h["roof"] in names, (f, h)
    for f in ("buildmat_hlsl.py", "make_textures.py", "render.py", "checks.py", "make_sheet.py"):
        src = open(os.path.join(HERE, f)).read()
        for n in ("brick_red", "lap_siding", "shingle_charcoal", "metal_seam", "limestone"):
            assert '"%s"' % n not in src, (f, n)


def test_tiles_hold_whole_units():
    c = {x["name"]: x for x in MT.cards()["walls"] + MT.cards()["roofs"]}
    b = c["brick_red"]
    pitch = (b["unit_mm"]["brick"][0] + b["unit_mm"]["joint"]) / 1000.0
    assert abs(b["tile_m"][0] - b["bricks_across"] * pitch) < 0.002
    assert abs(b["tile_m"][1] - b["courses"] * b["unit_mm"]["course"] / 1000.0) < 0.002
    assert abs(c["lap_siding"]["tile_m"][1] - c["lap_siding"]["courses"] * 0.150) < 1e-6
    assert abs(c["board_batten"]["tile_m"][0] - 12 * 0.3048) < 1e-6
    for s in ("shingle_weathered_wood", "shingle_charcoal", "shingle_barkwood"):
        assert abs(c[s]["tile_m"][1] - c[s]["courses"] * 0.143) < 1e-6
    assert abs(c["metal_seam"]["tile_m"][0] - c["metal_seam"]["panels"] * 0.406) < 1e-6
    # the size card: course 76 mm, lap 150 mm, shingle row 143 mm
    assert abs(b["unit_mm"]["course"] - 76) < 1


def test_textures_tile_and_measure():
    _stub_grain()
    import checks
    for card in MT.cards()["walls"] + MT.cards()["roofs"]:
        t = MT.build(card, 256)
        h = t["h_mm"]
        # periodic: the first and last rows and columns continue each other (no seam step bigger than inside)
        inner = np.abs(np.diff(h, axis=1)).mean()
        seam = np.abs(h[:, 0] - h[:, -1]).mean()
        assert seam < 4 * inner + 0.5, (card["name"], seam, inner)
        assert np.isfinite(t["col"]).all() and t["col"].min() >= 0 and t["col"].max() <= 1
    b = [c for c in MT.cards()["walls"] if c["name"] == "brick_red"][0]
    t = MT.build(b, 512)
    got = checks.period(t["h_mm"].mean(1), b["tile_m"][1] * 1000 / 512, 76.2)
    assert abs(got - 76.2) / 76.2 < 0.05


def test_wear_matches_boats():
    """dT and dD in the shader are the boats' time_k and dirt_k (Tools/texloop/wear.py)."""
    for lv in wear.levels():
        env = dict(uv=np.zeros((1, 1, 2)), UV=np.zeros((1, 1, 2)), TS=np.array([4.0, 4.0]), C=np.full((1, 1, 3), 0.5),
                   M=np.array([1.0, 0.8, 0.5]), HT=0.3, Kind=0.0, Paint=np.array([0.5, 0.5, 0.5]), Bare=0.0,
                   Age=lv["age"], Care=lv["care"], North=0.5, Sun=0.5, Eave=2.9, N1=np.array([0.5, 0.5, 0.5]), N1W=0.0,
                   N2=np.array([0.5, 0.5, 0.5]), N2W=0.0)
        import hlsl_np
        ns = hlsl_np.run(BH.BUILDMAT_CODE, env)
        assert abs(float(np.ravel(ns["dT"])[0]) - wear.time_k(lv["age"], lv["care"])) < 1e-9
        assert abs(float(np.ravel(ns["dD"])[0]) - wear.dirt_k(lv["age"], lv["care"])) < 1e-9


def test_wear_ladder_darkens_or_dirties():
    """Each finish moves further from new as the levels go L0 -> L2 -> L4. Painted finishes in the packs' default white
    (#EDEAE0): on a mid grey paint the bare primer under peeling is the paint's own shade, so the test would see nothing."""
    rng = np.random.default_rng(3)
    n = 4000
    uv = np.stack([rng.uniform(0, 8, n), rng.uniform(0, 2.5, n)], -1).reshape(1, n, 2)
    base = dict(uv=uv, UV=uv, TS=np.array([4.0, 4.0]), C=np.full((1, n, 3), 0.5), M=np.concatenate([np.full((1, n, 2), [0.9, 0.8]), rng.uniform(0.02, 1, (1, n, 1))], -1),
                HT=np.full((1, n, 1), 0.4), Paint=np.array([0.84, 0.82, 0.75]), Bare=0.0, North=np.full((1, n, 1), 0.5), Sun=np.full((1, n, 1), 0.5),
                Eave=2.9, N1=rng.uniform(0, 1, (1, n, 3)), N1W=rng.uniform(0, 1, (1, n, 1)), N2=rng.uniform(0, 1, (1, n, 3)), N2W=rng.uniform(0, 1, (1, n, 1)))
    for name in P.finishes():
        kind = BH.kind_of(name)
        cols = []
        for lid in ("L0", "L2", "L4"):
            lv = [x for x in wear.levels() if x["id"] == lid][0]
            env = dict(base, Kind=float(kind), Age=lv["age"], Care=lv["care"])
            c, r, m, a = BH.run_np(env)
            cols.append(c)
        # how far each pixel has moved from new (chalk lightens while dirt darkens, so the mean alone can stand still)
        d2 = np.abs(cols[1] - cols[0]).mean(); d4 = np.abs(cols[2] - cols[0]).mean()
        assert d4 >= d2 * 0.9 and d4 > 0.004, (name, d2, d4)


def test_interior_projection_is_exact():
    """A room point hit by the view ray lands where the atlas camera pictured it: render one point both ways."""
    # straight in through the pane's centre: the ray hits the back wall at the window's centre
    seed = np.array([0.25])
    uvp = np.array([[0.5, 0.5]]); size = np.array([[0.9, 1.5]])
    vt = np.array([[0.0, 0.0, -1.0]])
    auv, H = INT.room_uv(uvp, size, seed, np.zeros(1), vt)
    assert abs(H[0, 2] + INT.ROOM_D) < 1e-9
    # the back wall fills the middle F / (F + D) of the cell: the far corner maps to that fraction
    pt = np.array([INT.ROOM_W / 2, INT.ROOM_H, -INT.ROOM_D])
    s = INT.F / (INT.F - pt[2])
    assert abs(pt[0] * s / (INT.ROOM_W / 2) - INT.F / (INT.F + INT.ROOM_D)) < 1e-12
    # oblique rays from the left hit the right wall, and stay inside the cell
    rng = np.random.default_rng(1)
    n = 500
    uvp = rng.uniform(0, 1, (n, 2)); vt = np.stack([rng.uniform(-2, 2, n), rng.uniform(-1, 1, n), -np.ones(n)], -1)
    seeds = rng.uniform(0, 1, n)
    auv, H = INT.room_uv(uvp, np.broadcast_to([0.9, 1.5], (n, 2)), seeds, np.zeros(n), vt)
    assert (auv >= 0).all() and (auv <= 1).all()
    inside = (np.abs(H[:, 0]) <= INT.ROOM_W / 2 + 1e-6) & (H[:, 1] >= -1e-6) & (H[:, 1] <= INT.ROOM_H + 1e-6) & (H[:, 2] >= -INT.ROOM_D - 1e-6)
    assert inside.all()


def test_interior_hlsl_and_numpy_agree_on_constants():
    code = INT.INTERIOR_CODE
    assert "RW = %.1f" % INT.ROOM_W in code and "RH = %.1f" % INT.ROOM_H in code and "RD = %.1f" % INT.ROOM_D in code
    assert "FF = %.1f" % INT.F in code
    assert len(INT.ROOMS) == INT.GRID * INT.GRID


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
