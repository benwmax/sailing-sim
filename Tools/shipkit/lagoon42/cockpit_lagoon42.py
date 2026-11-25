"""The Lagoon 42's cockpit from cockpit_lagoon42.json: pure geometry, no Blender (docs/lagoon42-5).

The sole between the hulls from the bridge deck's aft face to the saloon's aft bulkhead, level with the sugar scoops'
landings; the aft bench with the roof's two posts; the L-shaped settee and its table to starboard; the lounge to port;
the raised helm to port against the bulkhead (its deck, steps, seat, console and wheel); a dark window in each
landing's riser. build_lagoon42.py meshes them as L42_Cockpit.

    python3 -I cockpit_lagoon42.py      prints the main numbers and writes nothing

Every part is a dict with its kind:
  box    lo, hi (opposite corners), round (bevel radius), mat, and cushion (a seat: the box stops CUSHION short of
         hi's z and a cushion of that thickness, 1 cm in, sits on it) or top (the flat top's material, a tread)
  slab   outline (a closed plan polygon), z (bottom, top), mat
  cyl    a, b (the axis' ends), radius, mat
  torus  centre, axis (unit), R (the ring's radius to the tube's centre), r (the tube's), mat
  pane   corners (a closed polygon of points on a wall), mat
The sole is rows (sole_rows), Teak.

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bridgedeck_lagoon42 as B  # noqa: E402
import hull_lagoon42 as H  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402

CK = json.load(open(os.path.join(HERE, "cockpit_lagoon42.json")))
SOLE, HELM = CK["sole"], CK["helm"]
SOLE_Z = SOLE["z"]
CUSHION = 0.075            # a seat's cushion
SEATED_EYE = 0.78          # a seated adult's eye over the seat (a man's, roughly the 50th percentile)
INTO_WALL = 0.02           # what stands against the saloon's aft bulkhead runs this far into it, so no seam shows


def sole_rows(n_in=24, step=0.1):
    """The sole as rows across, aft to forward: from the bridge deck's aft face to fwd_x, out to the hulls' inboard
    topsides at the sole's height (4 mm into them)."""
    ax, fx = B.US["aft_x"], SOLE["fwd_x"]
    n = max(2, round((fx - ax) / step))
    rows = []
    for i in range(n + 1):
        x = ax + (fx - ax) * i / n
        e = B.span(x, SOLE_Z) + 0.004
        rows.append([(x, -e + 2 * e * j / n_in, SOLE_Z) for j in range(n_in + 1)])
    return rows


def hull_y(xs, sign):
    """A box's side that runs into a hull's inboard topsides along stations xs (sign: +1 starboard, -1 port)."""
    return sign * (max(S.cockpit_edge(x) for x in xs) + 0.01)


def _ys(spec, xs):
    return [hull_y(xs, 1 if spec.index(v) == 1 else -1) if v == "hull" else v for v in spec] if "hull" in spec else spec


def seat(x, y, top_z, rnd, z0=SOLE_Z):
    """A seat box from z0 to top_z, its top a cushion."""
    return {"kind": "box", "lo": (x[0], min(y), z0), "hi": (x[1], max(y), top_z), "round": rnd, "mat": "Topsides",
            "cushion": True}


def rounded_rect(x0, x1, y0, y1, r, n=5):
    """A rounded rectangle's outline, round from the (x1, y1) corner's arc: [(x, y)]."""
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, 0.5 * math.pi), (x0 + r, y0 + r, math.pi),
                       (x1 - r, y0 + r, 1.5 * math.pi)):
        for k in range(n + 1):
            a = a0 + 0.5 * math.pi * k / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def parts():
    """Every part of the cockpit but the sole."""
    out = []
    # the aft bench across the stern, its back to the water; the roof's posts stand in it
    ab = CK["aft_bench"]
    xs = ab["x"]
    out.append(seat(xs, (hull_y(xs, -1), hull_y(xs, 1)), ab["top_z"], ab["round"]))
    po = CK["posts"]
    for sgn in (1, -1):
        y = sgn * po["y"]
        out.append({"kind": "cyl", "a": (po["x"], y, ab["top_z"] - 0.05),
                    "b": (po["x"], y, S.roof_under_z(po["x"], y) + 0.05), "radius": po["diameter"] / 2,
                    "mat": "Topsides"})
    # the settee (two boxes in an L) and the table inside it
    st = CK["settee"]
    for b in st["boxes"]:
        out.append(seat(b["x"], _ys(b["y"], b["x"]), b["top_z"], st["round"]))
    tb = CK["table"]
    (x0, x1), (y0, y1) = tb["x"], tb["y"]
    out.append({"kind": "slab", "outline": rounded_rect(x0, x1, y0, y1, tb["round"]),
                "z": (tb["top_z"] - tb["thickness"], tb["top_z"]), "mat": "Teak"})
    xm, ym, dx = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.3
    for x in (xm - dx, xm + dx):
        out.append({"kind": "cyl", "a": (x, ym, SOLE_Z - 0.01), "b": (x, ym, tb["top_z"] - tb["thickness"] + 0.005),
                    "radius": tb["leg_diameter"] / 2, "mat": "Spar"})
    # the lounge to port
    lg = CK["lounge"]
    out.append(seat(lg["x"], _ys(lg["y"], lg["x"]), lg["top_z"], lg["round"]))
    # the helm: its deck against the bulkhead, steps up to it from the cockpit, the seat, the console and the wheel
    hm, r = HELM, HELM["round"]
    wall = S.SAL["aft"][0] + INTO_WALL
    d = hm["deck"]
    out.append({"kind": "box", "lo": (d["x"][0], d["y"][0], SOLE_Z - 0.01), "hi": (wall, d["y"][1], d["top_z"]),
                "round": r, "mat": "Topsides", "top": "Teak"})
    s = hm["steps"]
    n = s["n"]
    rise = (d["top_z"] - SOLE_Z) / (n + 1)
    (sy0, sy1) = s["y"]                       # from the deck's edge (sy0) inboard to the lowest step's front (sy1)
    for k in range(1, n + 1):                 # step k, k rises up: the lowest is the most inboard
        ya, yb = sy1 + (sy0 - sy1) * (k - 1) / n, sy1 + (sy0 - sy1) * k / n
        if k == n:
            yb -= 0.02                        # the top step runs a little under the deck's edge
        out.append({"kind": "box", "lo": (s["x"][0], min(ya, yb), SOLE_Z - 0.01),
                    "hi": (s["x"][1], max(ya, yb), SOLE_Z + rise * k), "round": r, "mat": "Topsides", "top": "Teak"})
    se = hm["seat"]
    out.append(seat(se["x"], se["y"], se["top_z"], r, z0=d["top_z"] - 0.01))
    out.append({"kind": "box", "lo": (se["x"][0], se["y"][0], se["top_z"] - 0.02),
                "hi": (se["x"][0] + se["back_x"], se["y"][1], se["back_top_z"]), "round": 0.03, "mat": "Cushion"})
    co = hm["console"]
    out.append({"kind": "box", "lo": (co["x"][0], co["y"][0], d["top_z"] - 0.01), "hi": (wall, co["y"][1], co["top_z"]),
                "round": r, "mat": "Topsides"})
    wh = hm["wheel"]
    cx, cy, cz = wh["centre"]
    R = wh["diameter"] / 2 - wh["tube"]
    out.append({"kind": "torus", "centre": (cx, cy, cz), "axis": (1.0, 0.0, 0.0), "R": R, "r": wh["tube"],
                "mat": "Spar"})
    out.append({"kind": "cyl", "a": (cx - 0.03, cy, cz), "b": (co["x"][0] + 0.01, cy, cz), "radius": 0.045,
                "mat": "Spar"})
    for k in range(wh["spokes"]):
        a = math.pi / 2 + 2 * math.pi * k / wh["spokes"]
        u = (0.0, math.cos(a), math.sin(a))
        out.append({"kind": "cyl", "a": (cx, cy + 0.04 * u[1], cz + 0.04 * u[2]),
                    "b": (cx, cy + R * u[1], cz + R * u[2]), "radius": 0.009, "mat": "Spar"})
    return out


def riser_windows():
    """The dark window in each landing's riser, 4 mm aft of it: [[(x, y, z)]] closed polygons."""
    rw = CK["riser_windows"]
    x = H.SCOOP_END - 0.004
    (z0, z1), hw, c = rw["z"], rw["half_width"], rw["corner"]
    out = []
    for cy in (H.HULL_Y, -H.HULL_Y):
        out.append([(x, y, z) for z, y in rounded_rect(z0, z1, cy - hw, cy + hw, c)])
    return out


def helm_eye():
    """The seated helmsman's eye: over the seat's middle, SEATED_EYE over its top."""
    se = HELM["seat"]
    return ((se["x"][0] + se["back_x"] + se["x"][1]) / 2, sum(se["y"]) / 2, se["top_z"] + SEATED_EYE)


if __name__ == "__main__":
    H.solve_depth()
    ax, fx = B.US["aft_x"], SOLE["fwd_x"]
    print(f"cockpit sole: {SOLE_Z:.2f} m over the game's waterline, x {ax:.2f}..{fx:.2f} "
          f"({fx - ax:.2f} m), {2 * B.span(ax, SOLE_Z):.2f} m wide aft, {2 * B.span(fx, SOLE_Z):.2f} forward")
    print(f"headroom over the sole: {S.ceiling_z(0.0) - SOLE_Z:.2f} m under the ceiling, "
          f"{S.lip_at(S.ROOF['aft_x']) - SOLE_Z:.2f} m under the lip at the aft edge, "
          f"{S.roof_under_z(-2.0, 0.0) - SOLE_Z:.2f} m at x -2.0 on the centreline")
    e = helm_eye()
    print(f"helm: deck {HELM['deck']['top_z']:.2f} m, seat {HELM['seat']['top_z']:.2f} m, eye ({e[0]:.2f}, {e[1]:.2f}, "
          f"{e[2]:.2f}); the roof's top there {S.roof_top_z(e[1]):.2f} m")
    ps = parts()
    print(f"{len(ps)} parts: " + ", ".join(f"{sum(1 for p in ps if p['kind'] == k)} {k}"
                                           for k in ("box", "slab", "cyl", "torus")))
