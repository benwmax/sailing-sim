"""The Hobie 16's sails and boom (docs/hobie16-6, slice 5) as plain geometry: no Blender, so they can be checked.

    python3 -I sails_hobie16.py          prints the sails' areas, corners, battens and centres of effort

sails_hobie16.json holds the edges, battens and areas' sources; rig_hobie16 the mast and forestay they hang on;
platform_hobie16 the crossbars the boom and jib are sheeted to (call hull_hobie16.solve_depth() first). Each sail's
planform is its luff, its foot and a chord at each batten (the batten's length plus its pocket's ends), the battens
parallel to the foot; the battens' heights up the luff follow (k / (n + 1)) ** p and solve() finds the p that gives
Hobie's area. Sheeted for upwind on starboard tack: the boom on the centreline, the jib's clew to port, each sail
cambered to port. build() returns platform_hobie16.Part meshes in Blender's frame, X forward, Y to PORT, Z up:
  Main   the mainsail (panels between the battens in the four sail slots, both faces) and its battens
  Jib    the jib and its battens
  Boom   the boom, its gooseneck and end cap
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_hobie16 as H  # noqa: E402
import platform_hobie16 as PL  # noqa: E402
import rig_hobie16 as RG  # noqa: E402

SA = json.load(open(os.path.join(HERE, "sails_hobie16.json")))
Part = PL.Part
N_CHORD = 16          # points along each chord
SUB = 3               # rows between battens


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def bisect(f, lo, hi, n=60):
    """The root of a function that rises from lo to hi."""
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def leech_gap(luff, t, foot, head_chord, d, leech):
    """The sail's straight leech (the head's aft corner to the clew) less its cut length."""
    return float(np.linalg.norm(luff * t - (foot - head_chord) * d)) - leech


def corners(S):
    """The two sails' corners and edge directions from the solved rig S (rig_hobie16.solve).

    The main's boom end is set over the rear crossbar (SA boom.clew_over_rear_bar_m: the mainsheet's blocks between).
    The jib's clew is SOLVED from its luff, foot and leech: sheeted in, the leech is the edge that goes taut, so the clew
    comes down only until the straight line from the head's aft corner to the clew is the jib's leech. The main's leech
    is reported against the owners' figure instead: its luff is cut to the mast's bend, which the straight mast here
    leaves out (sails_hobie16.json main.note_edges)."""
    M, J = SA["main"], SA["jib"]
    G = RG.G["mast"]
    t, s, u = RG.frame(S["rake"])
    track = (G["axis_from_le"] - 1.0) * G["chord_m"] - G["track_radius_m"]
    tack = S["heel"] + M["tack_along_mast_m"] * t + track * u

    # the main's clew is held by the mainsheet: its end over the rear crossbar's traveller, the 6:1's blocks between
    L = PL.layout()
    rc = PL.P["rear_crossbar"]
    dz = L["zr"] + rc["height_m"] / 2 + SA["boom"]["clew_over_rear_bar_m"] - tack[2]
    rise = math.asin(dz / M["foot_m"])
    main_dir = lambda r: np.array([-math.cos(r), 0.0, math.sin(r)])
    main = {"tack": tack, "luff_dir": t, "foot_dir": main_dir(rise), "luff": M["luff_m"]}

    stay = unit(S["hounds"] - S["junction"])
    jtack = S["junction"] + J["tack_over_plate_m"] * stay
    jdy = J["clew_y_m"]

    def jib_dir(dz):
        return unit([-math.sqrt(J["foot_m"] ** 2 - dz ** 2 - jdy ** 2), jdy, dz])
    jdz = bisect(lambda dz: -leech_gap(J["luff_m"], stay, J["foot_m"], J["head_chord_m"], jib_dir(dz), J["leech_m"]),
                 -1.2, 1.2)
    jib = {"tack": jtack, "luff_dir": stay, "foot_dir": jib_dir(jdz), "luff": J["luff_m"]}
    return main, jib


def plane(C):
    """The sail's own 2D frame: u along the foot, v square to it toward the head, and the luff's direction in it."""
    f = C["foot_dir"]
    n = unit(C["luff_dir"] - (C["luff_dir"] @ f) * f)
    return f, n, np.array([C["luff_dir"] @ f, C["luff_dir"] @ n])


def planform(C, spec, p):
    """The sail's knots from the foot to the head: [(luff point, chord, batten?, tilt)]. The battens' heights up the
    luff follow (k / (n + 1)) ** p; each batten is its length plus its pocket's ends long, tilted up toward the leech
    from tilt_foot_deg low to tilt_top_deg at the head (about square to the leech rather than parallel to the foot)."""
    n = len(spec["battens_m"])
    t0, t1 = math.radians(spec.get("tilt_foot_deg", 0.0)), math.radians(spec.get("tilt_top_deg", 0.0))
    rows = [(0.0, spec["foot_m"], False, 0.0)]
    for k, b in enumerate(spec["battens_m"], 1):
        a = C["luff"] * (k / (n + 1)) ** p
        rows.append((a, b + spec["pocket_ends_m"], True, t0 + (t1 - t0) * a / C["luff"]))
    rows.append((C["luff"], spec["head_chord_m"], False, 0.0))
    return rows


def pchip(x, y):
    """Fritsch-Carlson monotone cubic through (x, y): no overshoot between the knots, so the leech stays fair."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    h = np.diff(x)
    d = np.diff(y) / h
    m = np.zeros_like(y)
    for i in range(1, len(x) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0] = d[0]
    m[-1] = d[-1]

    def f(t):
        i = int(np.clip(np.searchsorted(x, t) - 1, 0, len(h) - 1))
        s = (t - x[i]) / h[i]
        return ((2 * s ** 3 - 3 * s ** 2 + 1) * y[i] + (s ** 3 - 2 * s ** 2 + s) * h[i] * m[i]
                + (-2 * s ** 3 + 3 * s ** 2) * y[i + 1] + (s ** 3 - s ** 2) * h[i] * m[i + 1])
    return f


def leech_curve(C, rows):
    """The leech as u(v) in the sail's frame: a monotone curve through the clew, each batten's aft end and the head's
    aft corner, so the cloth between them is fair rather than a polygon with a shoulder at the top batten."""
    _, _, l2 = plane(C)
    pts = [a * l2 + c * np.array([math.cos(t), math.sin(t)]) for a, c, _, t in rows]
    v = [q[1] for q in pts]
    return pchip(v, [q[0] for q in pts]), v[0], v[-1]


def fine_rows(C, rows, sub):
    """Rows between the knots (sub to a band): each [(luff point, chord, band, tilt)] reaching the leech curve."""
    _, _, l2 = plane(C)
    u_of, v0, v1 = leech_curve(C, rows)
    out = []
    for i, (r0, r1) in enumerate(zip(rows[:-1], rows[1:])):
        for k in range(sub + (1 if i == len(rows) - 2 else 0)):
            f = k / sub
            a, t = r0[0] + (r1[0] - r0[0]) * f, r0[3] + (r1[3] - r0[3]) * f
            if k == 0 or k == sub:
                c = (r0 if k == 0 else r1)[1]
            else:
                p0, d = a * l2, np.array([math.cos(t), math.sin(t)])
                c = bisect(lambda c: (p0 + c * d)[0] - u_of(float(np.clip((p0 + c * d)[1], v0, v1))), 0.0, 4.0)
            out.append((a, c, i, t))
    return out


def flat_area(C, rows, sub=8):
    """The planform's area in the sail's plane: the luff and the faired leech as one polygon (shoelace in 3D)."""
    f, n, _ = plane(C)
    fine = fine_rows(C, rows, sub)
    luff = [C["tack"] + a * C["luff_dir"] for a, _, _, _ in fine]
    leech = [C["tack"] + a * C["luff_dir"] + c * (math.cos(t) * f + math.sin(t) * n) for a, c, _, t in fine]
    poly = luff + leech[::-1]
    acc = np.zeros(3)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        acc += np.cross(a, b)
    return 0.5 * float(np.linalg.norm(acc)), poly


def solve_p(C, spec, target):
    # a higher p bunches the battens low, where the triangle is already wide: less roach, less area
    return bisect(lambda p: target - flat_area(C, planform(C, spec, p))[0], 0.4, 3.0)


def centroid(poly):
    """The planform polygon's area centroid (fan triangles from its first point)."""
    a0 = poly[0]
    tot, cen = 0.0, np.zeros(3)
    for b, c in zip(poly[1:-1], poly[2:]):
        ar = 0.5 * float(np.linalg.norm(np.cross(b - a0, c - a0)))
        tot += ar
        cen += ar * (a0 + b + c) / 3.0
    return cen / tot


def camber_shape(xi, at, exit_power=1.6):
    """The chord's camber line, 1 at its deepest point `at`: a parabola forward, and aft a curve that leaves the leech
    flatter than a parabola's (round 2's reviewers saw the jib's leech hooked to windward)."""
    return 1 - ((at - xi) / at) ** 2 if xi < at else 1 - ((xi - at) / (1 - at)) ** exit_power


def solve():
    S = RG.solve()
    main, jib = corners(S)
    out = {"rig": S}
    for name, C in (("main", main), ("jib", jib)):
        spec = SA[name]
        target = H.CARD["targets"][f"{name}_area_m2"]
        p = solve_p(C, spec, target)
        rows = planform(C, spec, p)
        area, poly = flat_area(C, rows)
        side = unit(np.cross(C["luff_dir"], C["foot_dir"]))
        if side[1] < 0:
            side = -side            # cambered to port (wind from starboard)
        out[name] = dict(C, p=p, rows=rows, area=area, poly=poly, side=side, ce=centroid(poly))
    return out


def rotate(v, axis, ang):
    """v turned by ang about the unit axis (Rodrigues)."""
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * (axis @ v) * (1 - math.cos(ang))


def row_frame(sail, spec, a, t):
    """A row's chord direction and camber direction: tilted in the sail's plane, then twisted off to leeward about
    the luff by twist_deg times the row's height share (the head opens more than the foot)."""
    f, n, _ = plane(sail)
    d = math.cos(t) * f + math.sin(t) * n
    tw = math.radians(spec.get("twist_deg", 0.0)) * (a / sail["luff"]) ** 1.3
    side = sail["side"]
    # turn toward leeward: the leech moves to the side the camber bulges
    sgn = 1.0 if (np.cross(sail["luff_dir"], d) @ side) > 0 else -1.0
    return rotate(d, sail["luff_dir"], sgn * tw), rotate(side, sail["luff_dir"], sgn * tw)


def sail_mesh(part, sail, spec, slots):
    """Both faces of the cambered sail, the rows subdivided between battens; each band between battens one slot.
    Camber runs from spec camber at the foot to camber_top at the head, its deepest point from camber_at to
    camber_at_top."""
    fine = fine_rows(sail, sail["rows"], SUB)
    xs = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, N_CHORD))   # closer near the luff and leech, where it curves
    grid, sides = [], []
    for a, c, _, t in fine:
        p0 = sail["tack"] + a * sail["luff_dir"]
        d, sd = row_frame(sail, spec, a, t)
        h = a / sail["luff"]
        depth = (spec["camber"] + (spec.get("camber_top", spec["camber"]) - spec["camber"]) * h) * c
        at = spec["camber_at"] + (spec.get("camber_at_top", spec["camber_at"]) - spec["camber_at"]) * h
        grid.append([p0 + x * c * d + depth * camber_shape(x, at) * sd for x in xs])
        sides.append(sd)
    grid = np.array(grid)
    for sgn, flip in ((1, False), (-1, True)):
        base = part.add_verts(np.concatenate([g + sgn * 0.0008 * sd for g, sd in zip(grid, sides)]))
        idx = lambda r, k: base + r * N_CHORD + k
        for r in range(len(fine) - 1):
            slot = slots[fine[r][2] % len(slots)]
            for k in range(N_CHORD - 1):
                q = (idx(r, k), idx(r, k + 1), idx(r + 1, k + 1), idx(r + 1, k))
                part.face(q[::-1] if flip else q, slot)
    return grid, fine, sides


def battens(part, sail, spec, grid, fine, sides):
    """A batten strip along each batten row, on the sail's port face, its pocket's ends short of luff and leech."""
    knots = [r[0] for r in sail["rows"] if r[2]]
    rows = [i for i, (a, _, _, _) in enumerate(fine) if any(abs(a - k) < 1e-9 for k in knots)]
    for r in rows:
        pts = grid[r]
        c = fine[r][1]
        e = max(spec["pocket_ends_m"] / 2, 0.03) / c
        xs = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, N_CHORD))
        keep = [k for k in range(1, N_CHORD - 1) if e <= xs[k] <= 1 - e]
        path = [pts[k] + 0.004 * sides[r] for k in keep]
        if len(path) >= 2:
            PL.sweep(part, path, PL.rrect(0.006, 0.022, 0.002, 2), "Batten", up=tuple(sides[r]))


def build(Sv=None):
    Sv = Sv or solve()
    main, jib, boom = Part("Main"), Part("Jib"), Part("Boom")
    g, f, sd = sail_mesh(main, Sv["main"], SA["main"], SA["main"]["slot_cycle"])
    battens(main, Sv["main"], SA["main"], g, f, sd)
    g, f, sd = sail_mesh(jib, Sv["jib"], SA["jib"], [SA["jib"]["slot"]])
    battens(jib, Sv["jib"], SA["jib"], g, f, sd)

    # the boom: gooseneck at the tack, the extrusion under the foot to its end cap past the clew
    B = SA["boom"]
    m = Sv["main"]
    d = m["foot_dir"]
    start = m["tack"] - 0.04 * d - 0.05 * np.array([0, 0, 1.0])
    end = m["tack"] + (SA["main"]["foot_m"] + B["end_cap_m"]) * d - 0.05 * np.array([0, 0, 1.0])
    PL.sweep(boom, [start, end], PL.rrect(B["width_m"], B["height_m"], 0.025, 4), "Mast", up=(0.0, 0.0, 1.0))
    PL.box(boom, end + 0.01 * d, (0.04, B["width_m"] + 0.01, B["height_m"] + 0.01), "Cast")
    PL.box(boom, start - 0.02 * d + np.array([0, 0, 0.02]), (0.06, 0.05, 0.09), "Cast")
    return [main, jib, boom], Sv


def report(Sv):
    out = {}
    L = PL.layout()
    rc = PL.P["rear_crossbar"]
    for name in ("main", "jib"):
        s = Sv[name]
        spec = SA[name]
        head = s["tack"] + s["luff"] * s["luff_dir"]
        clew = s["tack"] + spec["foot_m"] * s["foot_dir"]
        top_leech = head + spec["head_chord_m"] * s["foot_dir"]
        r = lambda v: [round(float(x), 3) for x in v]
        out[name] = {"area_m2": round(s["area"], 3), "batten_power": round(s["p"], 3),
                     "batten_heights_m": [round(r[0], 3) for r in s["rows"] if r[2]],
                     "tack": r(s["tack"]), "head": r(head), "clew": r(clew), "centre_of_effort": r(s["ce"]),
                     "leech_m": round(float(np.linalg.norm(top_leech - clew)), 3),
                     "triangle_m2": round(0.5 * float(np.linalg.norm(np.cross(head - s["tack"], clew - s["tack"]))), 3)}
    m = Sv["main"]
    boom_end = m["tack"] + (SA["main"]["foot_m"] + SA["boom"]["end_cap_m"]) * m["foot_dir"]
    out["boom_end"] = [round(float(x), 3) for x in boom_end]
    out["boom_end_aft_of_rear_bar_m"] = round(L["rx"] - float(boom_end[0]), 3)
    out["boom_rise_deg"] = round(math.degrees(math.asin(m["foot_dir"][2])), 2)
    out["clew_over_rear_bar_m"] = SA["boom"]["clew_over_rear_bar_m"]
    out["main_leech_m"] = {"drawn": out["main"]["leech_m"], "owners": SA["main"]["leech_m"]}
    j = Sv["jib"]
    jclew = j["tack"] + SA["jib"]["foot_m"] * j["foot_dir"]
    fc = PL.P["front_crossbar"]
    out["jib_clew_aft_of_front_bar_m"] = round(L["fx"] - float(jclew[0]), 3)
    out["jib_clew_over_front_bar_m"] = round(float(jclew[2]) - (L["zf"] + fc["height_m"] / 2), 3)
    out["gooseneck_over_tramp_m"] = round(float(m["tack"][2]) - 0.278, 3)
    a = Sv["main"]["area"] + Sv["jib"]["area"]
    out["sailplan_ce"] = [round(float(x), 3) for x in (Sv["main"]["ce"] * Sv["main"]["area"] + Sv["jib"]["ce"] * Sv["jib"]["area"]) / a]
    return out


if __name__ == "__main__":
    H.solve_depth()
    parts, Sv = build()
    print(json.dumps(report(Sv), indent=1))
    for p in parts:
        print(f"{p.name}: {len(p.v)} verts, {p.tris()} triangles")
