"""The Catalina 22's mast, boom and standing rigging from rig_c22.json: pure geometry, no Blender (docs/c22-5).

Answers where the rig's points are (the mast's heel and cap, the forestay's and backstay's pins, the spreaders' tips, the
shrouds' tangs and chainplates, the gooseneck, the bands) and checks the rig: the sail plan's I, J, P and E, the
spreaders bisecting the uppers' angle, the boom's swing to the aft lowers against the physics' MainMaxEaseDeg, the boom
over the cabin top, the backstay clear of the tiller. build_rig_c22.py meshes it.

    python3 -I rig_c22.py          prints the points and the checks; exits 1 if a check fails

Frame: the game's body frame (X forward, Y starboard, Z up, metres), origin amidships on the design waterline.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_c22 as H  # noqa: E402
import deck_c22 as D  # noqa: E402

R = json.load(open(os.path.join(HERE, "rig_c22.json")))
MS, MH, SP, SH, FS, BS, BM, BD = (R[k] for k in ("mast", "masthead", "spreaders", "shrouds", "forestay", "backstay",
                                                  "boom", "bands"))
CARD = H.CARD
G = CARD["game"]
MAST_X = G["mast_x_m"]
A, B = MS["section"]                 # the mast's section: fore and aft, across
FT = 0.3048
CHAIN_PIN = 0.035 * 0.85             # the kit Chainplate's Pin socket over its base, at its 4 mm size (scale 0.85)
STEM_PIN = (-0.012, 0.034)           # the kit Stemhead's Forestay socket (x, z) from its base, the deck edge at the stem
STEM_DROP = 0.15                     # how far down the stem's face its bar is laid: a short strap (the final round)
TB_LEN = 0.216 * 0.85                # the kit Turnbuckle at its 4 mm size: the pin to its swage sleeve's end
TANG_T = 0.005                       # the strap tangs' thickness, flat on the mast's sides
EYE_T = 0.003                        # a shroud's eye terminal, pinned on the outer face of its tang
BOOM_EASE_DEG = 70.0                 # the physics' MainMaxEaseDeg for her (Fleet.cpp): the model's boom must reach it


def add(p, q, k=1.0):
    return tuple(a + k * b for a, b in zip(p, q))


def sub(p, q):
    return tuple(a - b for a, b in zip(p, q))


def norm(v):
    return math.sqrt(sum(c * c for c in v))


def unit(v):
    n = norm(v)
    return tuple(c / n for c in v)


def dot(p, q):
    return sum(a * b for a, b in zip(p, q))


# ------------------------------------------------------------------ the mast

def step_z():
    """The cabin top under the mast, where the kit's MastStep stands."""
    return D.top_z(MAST_X, 0.0)


def surface_normal(f, x, y, h=0.005):
    """The unit normal of the surface z = f(x, y), upward."""
    dx = (f(x + h, y) - f(x - h, y)) / (2 * h)
    dy = (f(x, y + h) - f(x, y - h)) / (2 * h)
    return unit((-dx, -dy, 1.0))


def step_frame():
    """The kit MastStep's origin and its Z, square to the cabin top (sunk 1 mm, so its plate's edges meet the top)."""
    n = surface_normal(D.top_z, MAST_X, 0.0)
    return add((MAST_X, 0.0, step_z()), n, -0.001), n


def heel_z():
    """The mast's heel: on the step's shoe (its Mast socket along the step's Z), 1 mm into it. The mast stands plumb."""
    o, n = step_frame()
    return o[2] + R["mast_step"]["kit_mast_z"] * n[2] - 0.0015          # the shoe follows the top's 1.9 deg: no gap aft


def top_z():
    return heel_z() + MS["length"]


def hounds():
    """The forestay's pin in the masthead's forward tang (the Hounds socket: I is measured to it)."""
    return (MAST_X + A / 2 + MH["forestay_out"], 0.0, top_z() - MH["forestay_below_top"])


def crane_pin():
    """The backstay's pin at the end of the masthead's crane (the MastheadAft socket)."""
    return (MAST_X - A / 2 - MH["crane"], 0.0, top_z() - 0.035)


def cap_tang(side):
    """The upper shroud's top: its eye terminal on the outer face of its strap tang (the pin through both), below the
    masthead."""
    return (MAST_X, side * (B / 2 + TANG_T + EYE_T / 2), top_z() - MH["cap_tang_below_top"])


def lower_tang(side, which):
    """The lower shroud's pin in the tang under the spreaders: which = +1 forward, -1 aft."""
    return (MAST_X + which * SH["lower_tang_spread"] / 2, side * (B / 2 + TANG_T + EYE_T / 2),
            SP["z"] - SH["lower_tang_below_spreader"])


# ------------------------------------------------------------------ the deck's ends of the wires

def chainplate_base(x, side):
    """A chainplate's origin on the side deck (sunk 0.5 mm along the deck's normal) and that normal: the kit's part
    stands square to the deck, so its cover lies on the camber."""
    y = side * (H.half_beam(x) - SH["inboard"])
    n = surface_normal(D.deck_z, x, y)
    return add((x, y, D.deck_z(x, y)), n, -0.0005), n


def chainplate_pin(x, side):
    b, n = chainplate_base(x, side)
    return add(b, n, CHAIN_PIN)


def stemhead_base():
    """The kit Stemhead's origin: the stem's leading edge at the deck."""
    z = D.deck_z(H.stem_x_at(H.sheer_z(3.25)), 0.0)
    return (H.stem_x_at(z), 0.0, z)


def stem_line(n=9):
    """The stem's leading edge (x, z) from the deck down STEM_DROP, in the Stemhead's frame (its origin at the deck)."""
    x0, _, z0 = stemhead_base()
    return [(H.stem_x_at(z0 - STEM_DROP * k / (n - 1)) - x0, -STEM_DROP * k / (n - 1)) for k in range(n)]


def tack_pin():
    """The forestay's pin in the stemhead (the ForestayTack socket: J is measured to it)."""
    return add(stemhead_base(), (STEM_PIN[0], 0, STEM_PIN[1]))


def backstay_base():
    x, y = BS["plate"]
    n = surface_normal(D.deck_z, x, y)
    return add((x, y, D.deck_z(x, y)), n, -0.0005), n


def backstay_pin():
    b, n = backstay_base()
    return add(b, n, CHAIN_PIN)


def wire_foot(pin, top):
    """Where a wire ends in its turnbuckle: the turnbuckle runs from the deck's pin toward the wire's top, and the wire
    reaches 5 mm into its swage sleeve."""
    return add(pin, unit(sub(top, pin)), TB_LEN - 0.005)


def vang_foot():
    """The vang's pin aft of the mast's after face, 8 cm over the step (the old 20 cm laid it flat under this low boom)."""
    return (MAST_X - A / 2 - 0.016, 0.0, step_z() + 0.08)


# ------------------------------------------------------------------ the spreaders

def spreader_tip(side, tilt=None):
    t = spreader_tilt() if tilt is None else tilt
    return (MAST_X, side * SP["half_span"] * math.cos(t), SP["z"] + SP["half_span"] * math.sin(t))


def spreader_root(side):
    return (MAST_X, side * B / 2, SP["z"])


def _bisect_err(t):
    tip = spreader_tip(1, t)
    pin = chainplate_pin(SH["upper_x"], 1)
    inward = unit(sub(spreader_root(1), tip))
    up = unit(sub(cap_tang(1), tip))
    dn = unit(sub(wire_foot(pin, tip), tip))
    return math.acos(max(-1, min(1, dot(inward, up)))) - math.acos(max(-1, min(1, dot(inward, dn))))


_TILT = []


def spreader_tilt():
    """How far the spreaders tilt up from level (radians), so each bisects the upper's angle at its tip."""
    if not _TILT:
        lo, hi = math.radians(-10), math.radians(25)
        for _ in range(60):
            mid = (lo + hi) / 2
            if (_bisect_err(lo) > 0) == (_bisect_err(mid) > 0):
                lo = mid
            else:
                hi = mid
        _TILT.append((lo + hi) / 2)
    return _TILT[0]


# ------------------------------------------------------------------ the wires

def wires():
    """Every wire's path, top to foot: {name: (points, deck pin)}. The uppers bend over the spreaders' tips."""
    out = {}
    h = hounds()
    out["Forestay"] = ([h, wire_foot(tack_pin(), h)], tack_pin())
    c = crane_pin()
    out["Backstay"] = ([c, wire_foot(backstay_pin(), c)], backstay_pin())
    for side, tag in ((1, "S"), (-1, "P")):
        tip = spreader_tip(side)
        pin = chainplate_pin(SH["upper_x"], side)
        out["Upper_" + tag] = ([cap_tang(side), tip, wire_foot(pin, tip)], pin)
        for which, x, nm in ((1, SH["lower_x"][0], "LowerFwd_"), (-1, SH["lower_x"][1], "LowerAft_")):
            t = lower_tang(side, which)
            pin = chainplate_pin(x, side)
            out[nm + tag] = ([t, wire_foot(pin, t)], pin)
    return out


# ------------------------------------------------------------------ the boom and bands

def gooseneck():
    """The gooseneck's pin: the boom's pivot, on the mast's after face at the physics' boom height."""
    return (MAST_X - A / 2 - BM["gooseneck_aft"], 0.0, BM["gooseneck_z"])


def boom_top():
    return BM["gooseneck_z"] + BM["section"][0] / 2


def mast_bands():
    """(z0, z1) of the mast's two bands: the lower's top edge is the boom's top (P's foot), the upper's lower edge P
    above it."""
    P = _card("P_m")
    w = BD["width"]
    bt = boom_top()
    return (bt - w, bt), (bt + P, bt + P + w)


def boom_band():
    """(x_aft, x_fwd) of the boom's band: its forward edge E aft of the mast's after face (the Boom_Clew socket)."""
    xf = MAST_X - A / 2 - _card("E_m")
    return (xf - BD["width"], xf)


def boom_x():
    """The boom's ends: its forward end at the gooseneck's jaw, its after end past the band by the end casting."""
    return (boom_band()[0] - BM["end"], gooseneck()[0] + 0.012)


def _card(key):
    v = CARD["targets"][key]
    return v["value"] if isinstance(v, dict) else v


# ------------------------------------------------------------------ checks

def boom_swing(side=1):
    """How far the boom swings out from the centreline (degrees) before its side touches the aft lower."""
    g = gooseneck()
    top, foot = wires()["LowerAft_" + ("S" if side > 0 else "P")][0]
    t = (top[2] - BM["gooseneck_z"]) / (top[2] - foot[2])
    p = add(top, sub(foot, top), t)
    dx, dy = g[0] - p[0], abs(p[1])
    d = math.hypot(dx, dy)
    return math.degrees(math.atan2(dy, dx) - math.asin((BM["section"][1] / 2 + SH["wire_d"] / 2) / d)), d


def sheer_at_mast():
    return H.sheer_z(MAST_X)


def measures():
    h, tk = hounds(), tack_pin()
    (_, _), (pz0, _) = mast_bands()
    return {"I_m": h[2] - sheer_at_mast(), "J_m": tk[0] - (MAST_X + A / 2),
            "P_m": pz0 - boom_top(), "E_m": (MAST_X - A / 2) - boom_band()[1]}


def tiller_to_backstay():
    """The backstay's least distance from the tiller's top, swung 45 degrees to port about the rudder's pin."""
    import keel_c22 as KC
    px = KC.RD["pivot_x"]
    top, foot = wires()["Backstay"][0]
    best = 9.0
    a = math.radians(45)
    for (x, z) in KC.tiller_path():
        r = px - x
        p = (px - r * math.cos(a), -r * math.sin(a), z + KC.RD["tiller"]["depth"][0] / 2)
        for k in range(101):
            q = add(foot, sub(top, foot), k / 100)
            best = min(best, norm(sub(p, q)))
    return best


def main():
    H.solve_depth()
    fails = []
    print(f"mast: heel z {heel_z():.3f} on the step (cabin top {step_z():.3f}), cap z {top_z():.3f} "
          f"({top_z() / FT:.1f} ft over the waterline; the physics' masthead {G['masthead_z_m']})")
    m = measures()
    tol = _card("tolerance")
    for k, v in m.items():
        want = _card(k)
        off = v / want - 1
        ok = abs(off) <= tol
        print(f"  {k} {v:.3f} against {want:.3f} ({off:+.1%}) {'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(k)
    t = spreader_tilt()
    print(f"spreaders: {SP['half_span']:.2f} m from the mast's middle, tilted up {math.degrees(t):.1f} deg to bisect "
          f"the upper's angle (err {math.degrees(_bisect_err(t)):.3f} deg)")
    for name, (pts, pin) in sorted(wires().items()):
        L = sum(norm(sub(b, a)) for a, b in zip(pts, pts[1:]))
        print(f"  {name:12s} {L:6.3f} m of wire, deck pin ({pin[0]:.3f}, {pin[1]:.3f}, {pin[2]:.3f})")
    up = wires()["Upper_S"][0]
    ang = math.degrees(math.atan2(up[2][1] - 0.0, up[0][2] - up[2][2]))
    print(f"  the uppers' angle to the mast at the masthead {math.degrees(math.atan2(up[1][1] - up[0][1], up[0][2] - up[1][2])):.1f} deg, "
          f"chainplate to cap {ang:.1f} deg")
    sw, d = boom_swing()
    ok = sw >= BOOM_EASE_DEG + 2
    print(f"boom: swings {sw:.1f} deg out before touching the aft lower ({d:.2f} m from the gooseneck at boom height); "
          f"the physics eases it to {BOOM_EASE_DEG:.0f} {'ok' if ok else 'FAIL'}")
    if not ok:
        fails.append("boom swing")
    bot = BM["gooseneck_z"] - BM["section"][0] / 2
    cab = max(D.top_z(-0.78 + 0.02 * k, 0.0) for k in range(int((MAST_X + 0.78) / 0.02)))
    print(f"  its underside z {bot:.3f}, {bot - cab:.3f} m over the cabin top's highest point aft of the mast "
          f"(the pop-top closed is 2.5 cm proud of it)")
    if bot - cab < 0.08:
        fails.append("boom over the cabin")
    xs = boom_x()
    print(f"  from x {xs[1]:.3f} to {xs[0]:.3f}, band at x {boom_band()[1]:.3f} (the Boom_Clew socket)")
    tb = tiller_to_backstay()
    print(f"backstay: {tb * 1000:.0f} mm from the tiller swung 45 deg to port")
    if tb < 0.03:
        fails.append("backstay and tiller")
    v = vang_foot()
    bail = (BM["vang_x"], 0.0, BM["gooseneck_z"] - BM["section"][0] / 2)
    va = math.degrees(math.atan2(bail[2] - v[2], v[0] - bail[0]))
    print(f"vang: {va:.1f} deg from its foot on the mast to the boom's bail (MastBase to Boom_Vang)")
    if va < 12:
        fails.append("vang too flat")
    (_, b0), (b1, _) = mast_bands()
    room = hounds()[2] - b1
    print(f"bands: mast {b0:.3f} and {b1:.3f}, {room:.2f} m from the upper band to the forestay's pin")
    if fails:
        print("FAIL: " + ", ".join(fails))
        sys.exit(1)
    print("pass")


if __name__ == "__main__":
    main()
