"""The Lagoon 42's hulls from lines_lagoon42.json: pure geometry, no Blender (docs/lagoon42-2).

The design is one hull, mirrored about its own centreline and set 2.9 m either side of the boat's: a few curves along
her length (the sheer's height, the deck's half-breadth, the topsides' knuckle and the canoe body's centreline) plus
the section's shape. Below the knuckle each section is a superellipse from the keel (a round bilge, fuller aft and a V
forward, easing between them by smootherstep so no line gains a kink from a seam in the design); above it the topsides
run nearly straight and flared out to the sheer, whose plan rounds into a blunt nose at the stem. The profile is a
plumb stem down to the forefoot, which turns into the bottom as a superellipse quarter (vertical at the stem, flat at
the lowest point), and a run aft that rises in one bend to the transom's foot, solved so the waterline ends where the
lines say. Aft, the shell's top steps down to the sugar scoop's swim platform.

hull_lagoon42.section(x, f) gives the half-breadth (from the hull's centreline) and height at station x and girth
fraction f (0 on the centreline at the keel, KNUCKLE_F at the knuckle, 1 at the shell's top); build_lagoon42.py meshes it
and hydrostatics() integrates it.

The canoe depth is solved so that the two hulls and the appendages displace the game's 15.5 m^3 (her 15.5 t in the
physics' 1,000 kg/m^3 water): the 12.1 t light boat, her 3.08 t of stores and four crew.

    python3 -I hull_lagoon42.py       prints the hydrostatics and writes nothing

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the game's waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = json.load(open(os.path.join(HERE, "lines_lagoon42.json")))
CARD = json.load(open(os.path.join(HERE, "specs_lagoon42.json")))

STEM_X = LINES["ends"]["stem_x"]
TRANSOM_X = LINES["ends"]["transom_x"]
HULL_Y = LINES["ends"]["hull_center_y"]
STEM = LINES["stem"]
BOT = LINES["bottom"]
WL_AFT = LINES["waterline"]["aft_x"]
SEC = LINES["section"]
SCOOP = LINES["scoop"]
KNUCKLE_F = 0.55          # the girth fraction at the knuckle: the canoe body below, the topsides above


def smooth(t):
    """0 to 1 with no step in slope or curvature at either end (smootherstep)."""
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (6 * t - 15) + 10)


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
CHINE_Z = Spline(LINES["chine"]["points"])
CHINE_Y = Spline(LINES["chine"]["half_breadth"])
CANOE_D = [BOT["canoe_depth"]]          # solved by solve_depth(); a list so build_lagoon42 sees the solved value


def stem_x_at(z):
    """The stem's fore edge at height z (a straight, nearly plumb line from the head)."""
    return STEM_X - (STEM["head_z"] - z) * STEM["rake"]


def transom_z(depth):
    """The transom's foot: the run aft is -d + (d + zt) u^c (u 0 at the lowest point, 1 at the transom, c the lines'
    bottom.run_power: 2 or more, so the keel line is flat at the lowest point with a finite bend), and zt is what makes
    it cross the waterline at waterline.aft_x."""
    lo, c = BOT["lowest_x"], BOT["run_power"]
    u0 = (lo - WL_AFT) / (lo - TRANSOM_X)
    return depth * (u0 ** -c - 1)


def keel_z(x):
    """Height of the hull's centreline at x: the run aft, the bottom and forefoot forward (a superellipse quarter
    from the lowest point, flat there, to the stem's foot, vertical there), then the stem."""
    d, lo, zf = CANOE_D[0], BOT["lowest_x"], STEM["forefoot_z"]
    if x <= lo:
        u = (lo - x) / (lo - TRANSOM_X)
        return -d + (d + transom_z(d)) * u ** BOT["run_power"]
    xf = stem_x_at(zf)
    if x >= xf:
        return min(zf + (x - xf) / STEM["rake"], STEM["head_z"]) if STEM["rake"] else STEM["head_z"]
    u = (x - lo) / (xf - lo)
    b, a = STEM["bottom_power"], STEM["forefoot_power"]
    return zf - (zf + d) * max(1 - u ** b, 0.0) ** (1 / a)


def scoop_steps():
    """[(x0, x1, z)] of the sugar scoop's platform and steps, aft to forward, the last one the cockpit-level landing
    (to scoop.landing_to_x); a riser climbs from it to the sheer at its x1."""
    out, x = [], TRANSOM_X
    for z, ln in [(SCOOP["platform_z"], SCOOP["platform_length"])] + [(z, SCOOP["step_length"]) for z in SCOOP["steps_z"]]:
        out.append((x, x + ln, z))
        x += ln
    if "landing_to_x" in SCOOP:            # slice 4: the top step runs on forward as the cockpit-level landing
        x0, _, z = out[-1]
        out[-1] = (x0, SCOOP["landing_to_x"], z)
    return out


SCOOP_END = scoop_steps()[-1][1]
SKIRT = SCOOP["skirt"]


def tread_z(x):
    """The scoop's tread at x, or None forward of it."""
    for x0, x1, z in scoop_steps():
        if x0 - 1e-9 <= x < x1:
            return z
    return None


def skirt_z(x):
    """The outboard topsides' raked top aft: a straight line from the platform's corner to the deck."""
    (xa, za), (xb, zb) = SKIRT
    return za + (zb - za) * (x - xa) / (xb - xa)


def top_z(x, side=1):
    """The shell's top: the sheer; aft, the scoop's treads on the inboard side (side -1) and the raked skirt, never
    under the treads, on the outboard side (side 1)."""
    s = SHEER(x)
    t = tread_z(x)
    if side < 0:
        return s if t is None else t
    if x >= SKIRT[1][0]:
        return s
    return min(s, max(t if t is not None else s, skirt_z(x)))


def sheer_z(x):
    return SHEER(x)


def half_beam(x):
    """The deck's edge: the plan spline aft of plan.bow.from_x, the bow's superellipse forward of it."""
    b = LINES["plan"]["bow"]
    if x <= b["from_x"]:
        return max(PLAN(x), 0.004)
    u = min((x - b["from_x"]) / (STEM_X - b["from_x"]), 1.0)
    return max(PLAN(b["from_x"]) * max(1 - u ** b["power"], 0.0) ** (1 / b["round"]), 0.004)


def section_powers(x):
    """(bilge, flare) powers at station x: the mid values between mid_x, easing (smootherstep) to the stern's at the
    transom and to the bow's at the stem."""
    m0, m1 = SEC["mid_x"]
    if x < m0:
        end, t = "stern", smooth((m0 - x) / (m0 - TRANSOM_X))
    else:
        end, t = "bow", smooth((x - m1) / (STEM_X - m1))
    b, fl = SEC["bilge_power"], SEC["flare_power"]
    return b["mid"] + (b[end] - b["mid"]) * t, fl["mid"] + (fl[end] - fl["mid"]) * t


def knuckle(x):
    """(half-breadth, height) of the knuckle at x, kept between the keel and the shell's lower top and inside the deck."""
    zk, zt = keel_z(x), min(top_z(x, -1), top_z(x, 1))
    zc = min(max(CHINE_Z(x), zk + 0.02), zt - 0.02) if zt - zk > 0.05 else zk + 0.5 * (zt - zk)
    yc = min(max(CHINE_Y(x), 0.003), half_beam(x))
    return yc, zc


def topsides_y(x, z):
    """The topsides' half-breadth at height z between the knuckle and the sheer (the hull windows sit on it)."""
    yc, zc = knuckle(x)
    zs = sheer_z(x)
    t = min(max((z - zc) / (zs - zc), 0.0), 1.0)
    return yc + (half_beam(x) - yc) * t + SEC["topsides_bulge"] * math.sin(math.pi * t)


def section(x, f, side=1):
    """(half-breadth, height) at station x, girth fraction f: 0 on the keel, KNUCKLE_F at the knuckle, 1 at the
    shell's top on that side (side 1 outboard, -1 inboard: they differ only aft, above the water)."""
    zk, zt = keel_z(x), top_z(x, side)
    yc, zc = knuckle(x)
    if f <= KNUCKLE_F:
        t = f / KNUCKLE_F
        q, p = section_powers(x)
        y = yc * (1 - (1 - t) ** p) ** (1 / q) if t < 1 else yc
        z = zk + (zc - zk) * t + math.tan(math.radians(SEC["deadrise_deg"])) * y * (1 - t) ** 2
        return y, z
    t = (f - KNUCKLE_F) / (1 - KNUCKLE_F)
    zs = sheer_z(x)
    z = zc + (zt - zc) * t
    tt = min(max((z - zc) / (zs - zc), 0.0), 1.0)          # where on the full topsides this height is
    y = yc + (half_beam(x) - yc) * tt + SEC["topsides_bulge"] * math.sin(math.pi * tt)
    return y, z


def stations(n):
    """Stations from the transom to the stem, closer together at both ends, plus a pair at each of the scoop's
    risers (2 mm apart) so the shell's top steps instead of ramping."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        t = 0.5 * (0.5 - 0.5 * math.cos(math.pi * t)) + 0.5 * t
        out.append(TRANSOM_X + (STEM_X - TRANSOM_X) * t)
    for x1 in [x1 for _, x1, _ in scoop_steps()] + [SKIRT[1][0]]:
        out = [x for x in out if abs(x - x1) > 0.01] + [x1 - 0.001, x1 + 0.001]
    return sorted(out)


def girth(k, m):
    """The k-th of m girth steps: bunched toward the keel in the canoe body ((k / mb)^1.8 of it), even up the
    topsides, with the knuckle exactly on step mb."""
    mb = round(m * 0.62)
    if k <= mb:
        return KNUCKLE_F * (k / mb) ** 1.8
    return KNUCKLE_F + (1 - KNUCKLE_F) * (k - mb) / (m - mb)


def area_below(x, zcut=0.0, m=240):
    """Area and its height-moment of one hull's section at x below zcut (both sides of its centreline)."""
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


def waterplane(zcut=0.0, n=400):
    """Both hulls' waterplane area at zcut."""
    a = 0.0
    dx = (STEM_X - TRANSOM_X) / n
    for i in range(n):
        x = TRANSOM_X + (i + 0.5) * dx
        if keel_z(x) >= zcut:
            continue
        prev = section(x, 0.0)
        for k in range(1, 600):
            cur = section(x, k / 600)
            if prev[1] < zcut <= cur[1]:
                a += 2 * cur[0] * dx
                break
            prev = cur
    return 2 * a


def hydrostatics(n=300):
    """Both hulls' volume under the game's waterline, centre of buoyancy, waterline length and one hull's beam there."""
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
    xs = [TRANSOM_X + (STEM_X - TRANSOM_X) * i / 4000 for i in range(4001)]
    wet = [x for x in xs if keel_z(x) < 0]
    bwl = 0.0
    for x in xs[::40]:
        if keel_z(x) >= 0:
            continue
        prev = section(x, 0.0)
        for k in range(1, 400):
            cur = section(x, k / 400)
            if prev[1] < 0 <= cur[1]:
                bwl = max(bwl, 2 * cur[0])
                break
            prev = cur
    return {"volume_m3": 2 * vol, "cb": [mx / vol if vol else 0.0, 0.0, mz / vol if vol else 0.0],
            "lwl": (max(wet) - min(wet)) if wet else 0.0, "waterline_x": [min(wet), max(wet)] if wet else None,
            "beam_wl_one_hull": bwl, "canoe_depth": CANOE_D[0]}


def target_volume():
    """What the two hulls under the game's waterline must hold: the game's design volume less the appendages'."""
    return CARD["game"]["design_volume_m3"] - BOT["appendage_volume_m3"]


def solve_depth():
    """The canoe depth whose volume is target_volume() (bisection)."""
    want = target_volume()
    lo, hi = 0.35, 1.1
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
    print(f"canoe depth {d:.4f} m, both hulls {h['volume_m3']:.4f} m^3 (want {target_volume():.4f}), "
          f"CB x {h['cb'][0]:+.3f} z {h['cb'][2]:+.3f}, LWL {h['lwl']:.3f} m, one hull's beam at the waterline "
          f"{h['beam_wl_one_hull']:.3f} m, waterplane {waterplane():.2f} m^2 (15 cm down {waterplane(-0.15):.2f})")
    print("today: CB x -0.196 z -0.424, LWL 12.510, waterplane 24.28 (21.55)")
    sys.exit(0)
