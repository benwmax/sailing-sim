"""The moth's hull from lines_moth.json: pure geometry, no Blender (docs/moth-2).

Frame: x forward from the hull's middle, y to one side, z up. The lines are drawn from the keel's lowest point; solve()
finds the waterline at which the hull floats the game's 115 kg (35 kg boat, 80 kg sailor: specs_moth.json game) and
the trim at which her centre of buoyancy sits under their centre of gravity, then every function here answers in the
design-waterline frame (z = 0 at the water, at rest with her sailor aboard, low-riding).

The section at x is a V rounding into upright topsides: half-breadth at height fraction t (0 keel, 1 deck edge) is
plan(x) * smooth-rounded t^power, the power growing from aft (fuller) to the bow (sharper), then a rounded deck edge
and a low-crowned deck. Plain convex sections: the class rule's 75 mm hollow limit (6.3.2) can't bite.

    python3 -I hull_moth.py        prints the hydrostatics, writes nothing
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = json.load(open(os.path.join(HERE, "lines_moth.json")))
CARD = json.load(open(os.path.join(HERE, "specs_moth.json")))
STEM_X = LINES["ends"]["stem_x"]
TRANSOM_X = LINES["ends"]["transom_x"]
SEC = LINES["section"]
WATER_KG_M3 = 1000.0
SAILOR_X = -0.3           # the sailor's centre of gravity at rest, sitting in the middle of the wing (front bar at x 0.58
                          # since Milestone A; it was -0.55, by the old wings' front bar): the afloat photo shows her nearly level,
                          # her bow's freeboard about twice the transom's
BOAT_CG_X = 0.05          # the boat's own (hull, foils, rig): the main foil and mast just ahead of the middle


class Spline:
    """Natural cubic spline through (x, y) points, clamped to the end values outside them."""

    def __init__(self, pts):
        self.x = [p[0] for p in pts]
        self.y = [p[1] for p in pts]
        n = len(pts)
        h = [self.x[i + 1] - self.x[i] for i in range(n - 1)]
        m, c, d = [0.0] * n, [0.0] * n, [0.0] * n
        for i in range(1, n - 1):
            r = 6 * ((self.y[i + 1] - self.y[i]) / h[i] - (self.y[i] - self.y[i - 1]) / h[i - 1])
            piv = 2 * (h[i - 1] + h[i]) - h[i - 1] * c[i - 1]
            c[i] = h[i] / piv
            d[i] = (r - h[i - 1] * d[i - 1]) / piv
        for i in range(n - 2, 0, -1):
            m[i] = d[i] - c[i] * m[i + 1]
        self.m = m

    def __call__(self, x):
        xs, ys, m = self.x, self.y, self.m
        x = min(max(x, xs[0]), xs[-1])
        i = 0
        while i < len(xs) - 2 and xs[i + 1] < x:
            i += 1
        h = xs[i + 1] - xs[i]
        a, b = (xs[i + 1] - x) / h, (x - xs[i]) / h
        return a * ys[i] + b * ys[i + 1] + ((a ** 3 - a) * m[i] + (b ** 3 - b) * m[i + 1]) * h * h / 6


KEEL = Spline(LINES["keel"]["points"])
SHEER = Spline(LINES["sheer"]["points"])
PLAN = Spline(LINES["plan"]["points"])
STATE = {"wl": 0.2, "trim": 0.0}      # waterline height over the keel's lowest point at x = 0, and bow-down slope


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


def power(x):
    """The section's V power: fuller aft, sharper forward (smootherstep blends)."""
    u = (x - TRANSOM_X) / (STEM_X - TRANSOM_X)
    if u < 0.5:
        return SEC["power_aft"] + (SEC["power_mid"] - SEC["power_aft"]) * smooth(u / 0.5)
    return SEC["power_mid"] + (SEC["power_bow"] - SEC["power_mid"]) * smooth((u - 0.5) / 0.5)


def raw_section(x, n=24):
    """The section at x in the lines' frame (z from the keel's lowest point), one side: (y, z) from the keel up the
    side, round the deck edge and in to the centreline at the deck's crown. n points up the side."""
    zk, zs, b = KEEL(x), SHEER(x), max(PLAN(x), 0.0)
    p = power(x)
    r = min(SEC["edge_round_m"], 0.45 * b, 0.3 * max(zs - zk, 1e-3))
    # the side reaches the deck edge's full breadth where the edge's roll begins (z = zs - r), so side and roll meet
    ze = zs - r
    yc, zc = b - r, zs - r
    pts = []
    for i in range(n + 1):
        t = (i / n) ** 1.7          # points closer together near the keel, where t^power turns fastest
        z = zk + (ze - zk) * t
        y = (b * t ** p) if t > 0 else 0.0
        pts.append((y, z))
    edge = [(yc + r * math.cos(a), zc + r * math.sin(a)) for a in np.linspace(0, math.pi / 2, 7)[1:]]
    crown = SEC["deck_crown_m"] * min(1.0, b / 0.1)
    deck = [(yc * (1 - s), zs + crown * (1 - (1 - s) ** 2)) for s in np.linspace(0.0, 1.0, 9)[1:]]
    return pts + edge + deck


def section(x, n=24):
    """The section in the design-waterline frame (z = 0 at the water, at rest with her sailor)."""
    dz = STATE["wl"] - STATE["trim"] * x
    return [(y, z - dz) for y, z in raw_section(x, n)]


def keel_z(x):
    return KEEL(x) - STATE["wl"] + STATE["trim"] * x


def sheer_z(x):
    return SHEER(x) - STATE["wl"] + STATE["trim"] * x


def stations(n):
    """n stations from the transom to the stem, closer together at the ends (where the shape turns fastest)."""
    u = np.linspace(0.0, 1.0, n)
    u = 0.5 * u + 0.5 * (1 - np.cos(u * math.pi)) / 2
    return TRANSOM_X + (STEM_X - TRANSOM_X) * u


def half_area_below(sec, zcut):
    """Area of one side's section under z = zcut (the side curve from the keel up: y(z) integrated)."""
    a, prev = 0.0, None
    for y, z in sec:
        if prev is not None:
            (y0, z0), (y1, z1) = prev, (y, z)
            if z1 <= z0:
                break
            lo, hi = z0, min(z1, zcut)
            if hi > lo:
                f0 = y0 + (y1 - y0) * (lo - z0) / (z1 - z0)
                f1 = y0 + (y1 - y0) * (hi - z0) / (z1 - z0)
                a += 0.5 * (f0 + f1) * (hi - lo)
        prev = (y, z)
    return a


def breadth_at(sec, zc):
    prev = None
    for y, z in sec:
        if prev is not None and prev[1] <= zc <= z and z > prev[1]:
            return prev[0] + (y - prev[0]) * (zc - prev[1]) / (z - prev[1])
        prev = (y, z)
    return 0.0


def hydro(n=300):
    """Volume, centre of buoyancy (x, z), waterplane area, waterline length, at the current STATE."""
    xs = np.linspace(TRANSOM_X, STEM_X, n)
    dx = xs[1] - xs[0]
    vol = mx = wp = 0.0
    wet = []
    for x in xs:
        sec = section(float(x))
        a = 2 * half_area_below(sec, 0.0)
        w = 2 * breadth_at(sec, 0.0)
        vol += a * dx
        mx += a * x * dx
        wp += w * dx
        if a > 1e-7:
            wet.append(float(x))
    lwl = (max(wet) - min(wet)) if wet else 0.0
    return {"volume": vol, "cb_x": mx / vol if vol else 0.0, "waterplane": wp, "lwl": lwl,
            "wl_fwd": max(wet) if wet else 0.0, "wl_aft": min(wet) if wet else 0.0}


def target():
    g, t = CARD["game"], CARD["targets"]
    m = t["rigged_weight_kg"] + g["crew_kg"]
    cg = (t["rigged_weight_kg"] * BOAT_CG_X + g["crew_kg"] * SAILOR_X) / m
    return m / WATER_KG_M3, cg


def solve():
    """Waterline height and trim so that the volume is the design volume and the centre of buoyancy sits under the
    centre of gravity (a few rounds of Newton on both)."""
    vol_t, cg = target()
    for it in range(60):
        h = hydro(160)
        ev = h["volume"] - vol_t
        ex = h["cb_x"] - cg
        if abs(ev) < 1e-6 and abs(ex) < 5e-4:
            break
        STATE["wl"] -= ev / max(h["waterplane"], 0.05)
        STATE["trim"] += 0.25 * ex / 1.2         # cb ahead of cg: the stern sinks, the bow rises
    return hydro(300)


def empty_waterline():
    """Where she floats without her sailor (the boat alone, 35 kg): the static waterplane of class rule 6.3."""
    saved = dict(STATE)
    vol_t = CARD["targets"]["rigged_weight_kg"] / WATER_KG_M3
    rise = 0.0
    for _ in range(40):
        STATE["wl"] = saved["wl"] - rise
        h = hydro(160)
        e = h["volume"] - vol_t
        if abs(e) < 1e-6:
            break
        rise += e / max(h["waterplane"], 0.03)
    out = {"rise_m": rise, "draft_m": -keel_z_min(), "lwl_m": h["lwl"]}
    STATE.update(saved)
    return out


def keel_z_min():
    return min(keel_z(float(x)) for x in np.linspace(TRANSOM_X, STEM_X, 400))


def report():
    h = solve()
    vol_t, cg = target()
    xs = np.linspace(TRANSOM_X, STEM_X, 400)
    mid = max(xs, key=lambda x: PLAN(float(x)))
    sec = section(float(mid))
    e = empty_waterline()
    return {
        "volume_m3": round(h["volume"], 5), "target_volume_m3": vol_t, "cb_x": round(h["cb_x"], 4), "cg_x": round(cg, 4),
        "waterline_over_keel_m": round(STATE["wl"], 4), "trim_slope": round(STATE["trim"], 5),
        "trim_deg": round(math.degrees(math.atan(STATE["trim"])), 3),
        "draft_m": round(-keel_z_min(), 4), "lwl_m": round(h["lwl"], 4), "waterplane_m2": round(h["waterplane"], 4),
        "beam_wl_m": round(2 * breadth_at(sec, 0.0), 4), "beam_deck_m": round(2 * PLAN(float(mid)), 4),
        "depth_m": round(max(SHEER(float(x)) - KEEL(float(x)) for x in xs), 4),
        "freeboard_mid_m": round(sheer_z(float(mid)), 4), "freeboard_bow_m": round(sheer_z(STEM_X), 4),
        "freeboard_transom_m": round(sheer_z(TRANSOM_X), 4),
        "sink_per_10kg_m": round(0.01 / h["waterplane"], 4),
        "empty_rise_m": round(e["rise_m"], 4), "empty_lwl_m": round(e["lwl_m"], 4),
    }


if __name__ == "__main__":
    for k, v in report().items():
        print(f"{k:22s} {v}")
