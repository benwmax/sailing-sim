"""The Catalina 22's hull shell from lines_c22.json: pure geometry, no Blender (docs/c22-2).

The design is a few curves along her length: the sheer's height and half-breadth, the canoe body's centreline (flat
at its lowest point; aft, flat and then a nearly straight run up to the transom's foot; forward, a rocker and forefoot drawn by
their turning angle into the straight raked stem, so the profile's curvature has no steps), plus each section's shape:
a nearly flat bottom turning through a firm bilge into flared topsides (a superellipse in girth), fuller toward the
transom and a V toward the stem. Every blend along her length is a smootherstep, so no line gains a kink from a seam
in the design (Tools/shapeloop/fairness.py counts no inflections, and each kink it counts is a single bend she is drawn with: the bilge, the
forefoot, the bow).
hull_c22.section(x, f) gives the hull's half-breadth and height at station x and girth fraction f (0 on the centreline
at the bottom, 1 at the sheer); build_c22.py meshes it and hydrostatics() integrates it.

The canoe body's depth is solved here so that, with the game's crew aboard, she displaces the card's 2,250 lb: the
hull's volume under the design waterline is the game's design volume (1.248 m^3 of water at 1,000 kg/m^3, the physics'
kWaterDensity) less the swing keel's own volume (249 kg of cast iron at 7,200 kg/m^3), which slice 3 hangs below it.

    python3 -I hull_c22.py         prints the hydrostatics and writes nothing

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the design waterline.
"""
import bisect
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = json.load(open(os.path.join(HERE, "lines_c22.json")))
CARD = json.load(open(os.path.join(HERE, "specs_c22.json")))

STEM_X = LINES["ends"]["stem_x"]
TRANSOM_X = LINES["ends"]["transom_x"]
WL_AFT = LINES["waterline"]["aft_x"]
STEM = LINES["stem"]
TRANSOM = LINES["transom"]
BOT = LINES["bottom"]
SEC = LINES["section"]
IRON_KG_M3 = 7200.0
WATER_KG_M3 = 1000.0


def smooth(t):
    """0 to 1 with no step in slope or curvature at either end (smootherstep)."""
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


def ease(t):
    """The integral of a sin^2 bump, 0 to 1: a turn that starts and ends with no curvature and no step in it."""
    t = min(max(t, 0.0), 1.0)
    return t - math.sin(2 * math.pi * t) / (2 * math.pi)


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


SHEER = Spline(LINES["sheer"]["points"])
PLAN = Spline(LINES["plan"]["points"])
CANOE_D = [BOT["canoe_depth"]]          # solved by solve_depth(); a list so build_c22 sees the solved value


def stem_x_at(z):
    """The stem's fore edge at height z over the waterline (a straight raked line from the head)."""
    return STEM_X - (STEM["head_z"] - z) * STEM["rake"]


_FWD = {}


def _forward_curve(depth, beta, span, n=800):
    """The profile from the lowest point forward: its angle turns from flat to the stem's, (1 - beta) of the turn
    spread over the whole span (the rocker) and beta of it over the last forefoot_length (the forefoot)."""
    th_stem, w = math.atan(1 / STEM["rake"]), STEM["forefoot_length"]
    xs, zs = [BOT["lowest_x"]], [-depth]
    ds = span / n
    for i in range(n):
        s = (i + 0.5) * ds
        th = th_stem * ((1 - beta) * ease(s / span) + beta * ease((s - (span - w)) / w))
        xs.append(xs[-1] + math.cos(th) * ds)
        zs.append(zs[-1] + math.sin(th) * ds)
    return xs, zs


def forward_profile(depth):
    """The forward profile for a canoe depth: span and beta solved (Newton) so it meets the straight stem at
    forefoot_top_z, on its line and along it."""
    if depth in _FWD:
        return _FWD[depth]
    zt = STEM["forefoot_top_z"]
    span, beta = 3.3, 0.9

    def err(sp, be):
        xs, zs = _forward_curve(depth, be, sp)
        return xs[-1] - stem_x_at(zt), zs[-1] - zt

    for _ in range(40):
        f = err(span, beta)
        if max(abs(f[0]), abs(f[1])) < 1e-8:
            break
        h = 1e-6
        fs, fb = err(span + h, beta), err(span, beta + h)
        j = [[(fs[0] - f[0]) / h, (fb[0] - f[0]) / h], [(fs[1] - f[1]) / h, (fb[1] - f[1]) / h]]
        det = j[0][0] * j[1][1] - j[0][1] * j[1][0]
        span -= (j[1][1] * f[0] - j[0][1] * f[1]) / det
        beta -= (-j[1][0] * f[0] + j[0][0] * f[1]) / det
    else:
        raise ValueError(f"forward_profile: no forefoot meets the stem for canoe depth {depth:.4f}")
    if not 0.0 <= beta <= 1.0:
        # beta over 1 turns the rocker the wrong way (the bottom hooks below the canoe depth); under 0 bends the
        # forefoot backwards: the stem and forefoot in lines_c22.json don't fit this depth
        raise ValueError(f"forward_profile: forefoot share {beta:.3f} outside 0..1 for canoe depth {depth:.4f}")
    xs, zs = _forward_curve(depth, beta, span)
    _FWD.clear()
    _FWD[depth] = (xs, zs, beta, span)
    return _FWD[depth]


def _run_shape(u, c):
    """0 at u 0 to 1 at u 1: flat at the start (no curvature there, like the forward profile, so the lowest point
    has no step in curvature), then straightening into a line: ((u^4 + c^4)^(1/4) - c), normalised."""
    return ((u ** 4 + c ** 4) ** 0.25 - c) / ((1 + c ** 4) ** 0.25 - c)


_RUN = {}


def run_knee(depth):
    """The run's knee c (as a share of the run's length): how long it stays flat before it straightens toward the
    transom's foot, solved (bisection) so the run crosses the waterline at waterline.aft_x."""
    if depth in _RUN:
        return _RUN[depth]
    lo, zt = BOT["lowest_x"], TRANSOM["bottom_z"]
    u0 = (lo - WL_AFT) / (lo - TRANSOM_X)
    want = depth / (depth + zt)                     # the share of the rise done at the waterline's end
    a, b = 1e-4, 5.0                                # small c: a straight run, rising early; large c: flat, then a hook
    if not 0 < want < 1 or not _run_shape(u0, b) <= want <= _run_shape(u0, a):
        raise ValueError(f"run_knee: no run from the lowest point crosses the water at x {WL_AFT} for canoe depth "
                         f"{depth:.4f} and a transom foot {zt} m up (it must be above the water)")
    for _ in range(60):
        c = (a + b) / 2
        if _run_shape(u0, c) > want:
            a = c
        else:
            b = c
    _RUN.clear()
    _RUN[depth] = (a + b) / 2
    return _RUN[depth]


def keel_z(x):
    """Height of the hull's centreline at x: flat at the lowest point; aft, a run that leaves the bottom flat and
    straightens toward the transom's foot (_run_shape); forward, the drawn rocker and forefoot (forward_profile) into the straight raked stem."""
    d, lo = CANOE_D[0], BOT["lowest_x"]
    if x <= lo:
        u = (lo - x) / (lo - TRANSOM_X)
        return -d + (d + TRANSOM["bottom_z"]) * _run_shape(u, run_knee(d))
    xs, zs, _, _ = forward_profile(d)
    if x >= xs[-1]:
        return STEM["forefoot_top_z"] + (x - xs[-1]) / STEM["rake"]
    i = bisect.bisect_right(xs, x) - 1
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return zs[i] + (zs[i + 1] - zs[i]) * t


def sheer_z(x):
    return SHEER(x)


def half_beam(x):
    return max(PLAN(x), 0.004)


def section_powers(x):
    """(bilge, flare) powers at station x: the mid values between mid_x, easing (smootherstep, so the joins have no
    curvature step) to the stern's at the transom and to the bow's at the stem."""
    m0, m1 = SEC["mid_x"]
    if x < m0:
        end, t = "stern", smooth((m0 - x) / (m0 - TRANSOM_X))
    else:
        end, t = "bow", smooth((x - m1) / (STEM_X - m1))
    b, fl = SEC["bilge_power"], SEC["flare_power"]
    return b["mid"] + (b[end] - b["mid"]) * t, fl["mid"] + (fl[end] - fl["mid"]) * t


def section(x, f):
    """(half-breadth, height) at station x, girth fraction f: 0 on the bottom's centreline, 1 at the sheer."""
    zk, zs = keel_z(x), sheer_z(x)
    z = zk + (zs - zk) * f
    q, p = section_powers(x)
    y = half_beam(x) * (1 - (1 - f) ** p) ** (1 / q) if f < 1 else half_beam(x)
    # a little deadrise: the bottom rises off the centreline
    z += math.tan(math.radians(SEC["deadrise_deg"])) * y * (1 - f) ** 2
    return y, z


def stations(n):
    """Stations from the transom to the stem, closer together at both ends."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        t = 0.5 * (0.5 - 0.5 * math.cos(math.pi * t)) + 0.5 * t
        out.append(TRANSOM_X + (STEM_X - TRANSOM_X) * t)
    return out


def girth(k, m):
    """The k-th of m girth steps, bunched toward the centreline (f = t^2.5), where the bottom widens fastest: the
    section's breadth grows as f^(1 / bilge power) there, which even steps under-sample."""
    return (k / m) ** 2.5


def area_below(x, zcut=0.0, m=240):
    """Area and its height-moment of the section at x below zcut (both sides)."""
    area, az = 0.0, 0.0
    prev = section(x, 0.0)
    for k in range(1, m + 1):
        cur = section(x, girth(k, m))
        (y0, z0), (y1, z1) = prev, cur
        prev = cur
        if z0 >= zcut and z1 >= zcut:
            continue
        lo, hi = min(z0, z1), min(max(z0, z1), zcut)
        if hi <= lo:
            continue
        ym = (y0 + y1) / 2
        da = 2 * ym * (hi - lo)
        area += da
        az += da * (lo + hi) / 2
    return area, az


def hydrostatics(n=300):
    """Volume under the design waterline, centre of buoyancy, waterline length and beam."""
    vol = mx = mz = 0.0
    dx = (STEM_X - TRANSOM_X) / n
    for i in range(n):
        x = TRANSOM_X + (i + 0.5) * dx
        if keel_z(x) >= 0:
            continue
        a, az = area_below(x)
        vol += a * dx
        mx += a * dx * x
        mz += az * dx
    xs = [TRANSOM_X + (STEM_X - TRANSOM_X) * i / 2000 for i in range(2001)]
    wet = [x for x in xs if keel_z(x) < 0]
    # waterline half-breadth: the section's breadth where it crosses z 0
    bwl = 0.0
    for x in xs[::20]:
        if keel_z(x) >= 0:
            continue
        prev = section(x, 0.0)
        for k in range(1, 400):
            cur = section(x, k / 400)
            if prev[1] < 0 <= cur[1]:
                bwl = max(bwl, 2 * cur[0])
                break
            prev = cur
    return {"volume_m3": vol, "cb": [mx / vol if vol else 0.0, 0.0, mz / vol if vol else 0.0],
            "lwl": (max(wet) - min(wet)) if wet else 0.0, "waterline_x": [min(wet), max(wet)] if wet else None,
            "beam_wl": bwl, "canoe_depth": CANOE_D[0]}


_STUB = []      # the keel stub's net volume (keel_c22.stub_volume), measured at the last depth solved


def target_volume():
    """What the hull under the design waterline must hold: the game's design volume less the swing keel's iron and
    the keel stub's moulding under the hull, plus the water in its trunk inside the hull (slice 3, docs/c22-4)."""
    g = CARD["game"]
    return g["design_volume_m3"] - CARD["targets"]["keel_kg"] / IRON_KG_M3 - (_STUB[0] if _STUB else 0.0)


def solve_depth():
    """The canoe depth that floats her at the design waterline. The stub's volume depends on where the hull's bottom
    is, so: solve without it, measure it there, solve again, twice (the second pass moves the depth under 0.1 mm)."""
    import keel_c22 as KC
    _STUB.clear()
    _solve_depth()
    for _ in range(2):
        solid, flooded = KC.stub_volume()
        _STUB[:] = [solid - flooded]
        _solve_depth()
    return CANOE_D[0]


def _solve_depth():
    """The canoe depth whose volume is target_volume() (bisection)."""
    want = target_volume()
    lo, hi = 0.18, 0.40
    for d in (lo, hi):
        CANOE_D[0] = d
        v = hydrostatics(160)["volume_m3"]
        if (v < want) != (d == lo):
            raise ValueError(f"solve_depth: canoe depth {d} gives {v:.4f} m^3, so {lo}..{hi} doesn't bracket {want:.4f}")
    for _ in range(40):
        CANOE_D[0] = (lo + hi) / 2
        if hydrostatics(160)["volume_m3"] < want:
            lo = CANOE_D[0]
        else:
            hi = CANOE_D[0]
    CANOE_D[0] = (lo + hi) / 2
    return CANOE_D[0]


if __name__ == "__main__":
    d = solve_depth()
    h = hydrostatics()
    print(f"canoe depth {d:.4f} m, volume {h['volume_m3']:.4f} m^3 (want {target_volume():.4f}), "
          f"CB x {h['cb'][0]:+.3f} z {h['cb'][2]:+.3f}, LWL {h['lwl']:.3f} m, beam at the waterline {h['beam_wl']:.3f} m")
    print("game: CB x %+.3f z %+.3f, LWL %.3f" % (-0.112, -0.102, 5.89))
    sys.exit(0)
