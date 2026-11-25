"""The Lagoon 42's cockpit from cockpit_lagoon42.json: pure geometry, no Blender (docs/lagoon42-5).

The sole between the hulls from the bridge deck's aft face to the saloon's aft bulkhead, level with the sugar scoops'
landings; the aft bench with the roof's two posts; the L-shaped settee and its table to starboard; the lounge to port;
the raised helm to port against the bulkhead (its deck, steps, seat, console, wheel, plotter, displays, compass,
throttles and guard rails); a dark window in each landing's riser. build_lagoon42.py meshes them as L42_Cockpit.

    python3 -I cockpit_lagoon42.py      prints the main numbers and writes nothing

Every part is a dict with its kind:
  box    lo, hi (opposite corners), round (bevel radius), mat, and cushion (a seat: the box stops CUSHION short of
         hi's z and a cushion of that thickness, 1 cm in, sits on it) or top (the flat top's material, a tread)
  slab   outline (a closed plan polygon), z (bottom, top), mat
  cyl    a, b (the axis' ends), radius, mat
  torus  centre, axis (unit), R (the ring's radius to the tube's centre), r (the tube's), mat
  pane   corners (a closed polygon of points on a wall), facing (its outward direction), mat
  rings  rings (closed rings of points, each the same length: a solid capped at both ends), mat, smooth
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
import appendages_lagoon42 as A  # noqa: E402
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
                    "radius": tb["leg_diameter"] / 2, "mat": "Stainless"})
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
    out += console(wall)
    out += wheel()
    out += instruments()
    out += throttles()
    out += rails()
    return out


def lathe(origin, axis, profile, n=20):
    """Rings of a body of revolution: profile [(s, r)] along the unit axis from origin, n points round each."""
    ax = axis
    u = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = _norm(_cross(ax, u))
    e2 = _cross(ax, e1)
    return [[tuple(origin[i] + ax[i] * s + r * (math.cos(2 * math.pi * j / n) * e1[i] + math.sin(2 * math.pi * j / n)
                                                * e2[i]) for i in range(3)) for j in range(n)] for s, r in profile]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    L = math.sqrt(sum(c * c for c in a))
    return tuple(c / L for c in a)


def plate(centre, u, v, hu, hv, n, t0, t1):
    """A thin rectangular solid on a face: centre, unit u and v along the face, half sizes hu and hv, the face's
    outward normal n, from t0 to t1 along it. As rings (two)."""
    def rect(t):
        return [tuple(centre[i] + n[i] * t + a * hu * u[i] + b * hv * v[i] for i in range(3))
                for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return [rect(t0), rect(t1)]


def console(wall):
    """The console on the bulkhead: one moulding in profile (x, z) from the deck up, its top edges rounded, across y."""
    co = CK["helm"]["console"]
    z0 = CK["helm"]["deck"]["top_z"] - 0.01
    (fx, fz), bz = co["face_top"], co["face_bottom_z"]
    prof = A.fillet([(co["x"][0], z0), (wall, z0), (wall, fz), (fx, fz), (co["x"][0], bz)],
                    [0.0, 0.0, 0.0, co["round"], co["round"]], 6)
    y0, y1 = co["y"]
    rings = [[(x, y, z) for x, z in prof] for y in (y0, y1)]
    return [{"kind": "rings", "rings": rings, "mat": "Topsides", "smooth": False}]


def face_frame():
    """The console's sloping instrument face: (a point on it, unit up-slope in x-z, outward normal), game frame."""
    co = CK["helm"]["console"]
    (fx, fz), bz, x0 = co["face_top"], co["face_bottom_z"], co["x"][0]
    L = math.hypot(fx - x0, fz - bz)
    s = ((fx - x0) / L, 0.0, (fz - bz) / L)
    return (x0, 0.0, bz), s, (-s[2], 0.0, s[0])


def wheel():
    wh = CK["helm"]["wheel"]
    cx, cy, cz = wh["centre"]
    R = wh["diameter"] / 2 - wh["tube"]
    out = [{"kind": "torus", "centre": (cx, cy, cz), "axis": (1.0, 0.0, 0.0), "R": R, "r": wh["tube"], "mat": "Stainless"}]
    p0, s, n = face_frame()
    xf = p0[0] + s[0] * (cz - p0[2]) / s[2] + 0.01          # where the axle meets the sloping face (and 1 cm into it)
    out.append({"kind": "cyl", "a": (cx + 0.015, cy, cz), "b": (xf, cy, cz), "radius": 0.022, "mat": "Stainless"})
    hub = [(0.0, 0.002), (0.0, 0.046), (0.012, 0.05), (0.05, 0.05), (0.058, 0.044)]
    hub += [(0.058 + 0.022 * math.sin(0.5 * math.pi * k / 5), 0.044 * math.cos(0.5 * math.pi * k / 5) + 0.002)
            for k in range(1, 6)]
    out.append({"kind": "rings", "rings": lathe((cx + 0.025, cy, cz), (-1.0, 0.0, 0.0), hub, 24), "mat": "Stainless",
                "smooth": True})
    for k in range(wh["spokes"]):
        a = math.pi / 2 + 2 * math.pi * k / wh["spokes"]
        u = (0.0, math.cos(a), math.sin(a))
        out.append({"kind": "cyl", "a": (cx, cy + 0.04 * u[1], cz + 0.04 * u[2]),
                    "b": (cx, cy + R * u[1], cz + R * u[2]), "radius": 0.009, "mat": "Stainless"})
    return out


def instruments():
    """The plotter on the sloping face, two displays on the upright face, the compass on top: bezels and screens."""
    ins = CK["helm"]["instruments"]
    co = CK["helm"]["console"]
    inset, depth = ins["bezel"]
    yc = sum(co["y"]) / 2
    out = []
    p0, s, n = face_frame()
    f = (ins["plotter"]["z"] - p0[2]) / s[2]
    c = (p0[0] + s[0] * f, yc, ins["plotter"]["z"])
    w, h = ins["plotter"]["size"]
    screens = [(c, (0.0, 1.0, 0.0), s, w / 2, h / 2, n)]
    for y in ins["displays"]["y"]:
        e = ins["displays"]["size"] / 2
        screens.append(((co["x"][0], y, ins["displays"]["z"]), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), e, e, (-1.0, 0.0, 0.0)))
    for cen, u, v, hu, hv, nn in screens:
        out.append({"kind": "rings", "rings": plate(cen, u, v, hu, hv, nn, -0.004, depth), "mat": "Rubber",
                    "smooth": False})
        out.append({"kind": "pane", "corners": plate(cen, u, v, hu - inset, hv - inset, nn, depth + 0.0008, 0)[0],
                    "facing": nn, "mat": "CabinWindow"})
    cp = ins["compass"]
    r, ht = cp["diameter"] / 2, cp["height"]
    top = co["face_top"][1]
    base = [(-0.005, 0.002), (-0.005, r), (0.016, r), (0.02, r - 0.006)]
    out.append({"kind": "rings", "rings": lathe((cp["x"], yc, top), (0.0, 0.0, 1.0), base, 28), "mat": "Rubber",
                "smooth": True})
    dome = [(0.019, r - 0.012)] + [(0.019 + (ht - 0.019) * math.sin(0.5 * math.pi * k / 6),
                                    (r - 0.012) * math.cos(0.5 * math.pi * k / 6) + 0.002) for k in range(1, 7)]
    out.append({"kind": "rings", "rings": lathe((cp["x"], yc, top), (0.0, 0.0, 1.0), dome, 28), "mat": "CabinWindow",
                "smooth": True})
    return out


def throttles():
    """The control box on the console's outboard side and its two levers with their knobs."""
    th = CK["helm"]["throttles"]
    b = th["box"]
    out = [{"kind": "box", "lo": (b["x"][0], b["y"][0], b["z"][0]), "hi": (b["x"][1], b["y"][1], b["z"][1]),
            "round": 0.015, "mat": "Rubber"}]
    a = math.radians(th["rake_deg"])
    d = (-math.sin(a), 0.0, math.cos(a))
    for y in th["y"]:
        p = (th["pivot_x"], y, b["z"][1] - 0.01)
        q = tuple(p[i] + d[i] * th["lever"] for i in range(3))
        out.append({"kind": "cyl", "a": p, "b": q, "radius": 0.007, "mat": "Stainless"})
        out.append({"kind": "rings", "rings": lathe(p, d, [(0.004, 0.002), (0.004, 0.016), (0.012, 0.02)], 16),
                    "mat": "Rubber", "smooth": True})
        kr = th["knob_diameter"] / 2
        knob = [(th["lever"] - 0.01 + kr * (1 - math.cos(math.pi * k / 8)), kr * math.sin(math.pi * k / 8) + 0.002)
                for k in range(9)]
        out.append({"kind": "rings", "rings": lathe(p, d, knob, 16), "mat": "Rubber", "smooth": True})
    return out


def rails():
    """The helm deck's guard rails: posts from the deck, a top and a middle rail along each run, round ends."""
    rl = CK["helm"]["rail"]
    z0 = CK["helm"]["deck"]["top_z"]
    rad = rl["tube"] / 2
    out = []
    for (xa, ya), (xb, yb) in rl["runs"]:
        L = math.hypot(xb - xa, yb - ya)
        n = max(1, round(L / rl["post_spacing"]))
        for k in range(n + 1):
            x, y = xa + (xb - xa) * k / n, ya + (yb - ya) * k / n
            out.append({"kind": "cyl", "a": (x, y, z0 - 0.01), "b": (x, y, z0 + rl["height"]), "radius": rad,
                        "mat": "Stainless"})
            out.append({"kind": "cyl", "a": (x, y, z0 - 0.002), "b": (x, y, z0 + 0.02), "radius": rad * 1.9,
                        "mat": "Stainless"})                                 # the post's base
        for zh in (rl["height"], rl["mid_height"]):
            out.append({"kind": "cyl", "a": (xa, ya, z0 + zh), "b": (xb, yb, z0 + zh), "radius": rad, "mat": "Stainless"})
        for x, y in ((xa, ya), (xb, yb)):
            sph = [(-rad * 1.15 * math.cos(math.pi * k / 8), rad * 1.15 * math.sin(math.pi * k / 8) + 0.0005)
                   for k in range(9)]
            out.append({"kind": "rings", "rings": lathe((x, y, z0 + rl["height"]), (0.0, 0.0, 1.0), sph, 16),
                        "mat": "Stainless", "smooth": True})
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
                                           for k in ("box", "slab", "cyl", "torus", "rings", "pane")))
