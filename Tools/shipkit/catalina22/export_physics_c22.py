"""Writes Source/SailingPhysics/Private/Catalina22HullData.inl from the rebuilt Catalina 22 (slice 10, docs/c22-10):
the game's physics floats, heels, drags and steers on the model's own hull, swing keel, kick-up rudder and sail plan.

    python3 -I Tools/shipkit/catalina22/export_physics_c22.py          writes the .inl and prints what it measured
    python3 -I Tools/shipkit/catalina22/export_physics_c22.py --check  writes nothing; exits non-zero if the .inl
                                                                       on disk is not what this script writes

Edit the slice's JSON (lines_c22, keel_c22, rig_c22, sails_c22, specs_c22) or this script, never the .inl. It only
reads the other scripts here (hull_c22, keel_c22, rig_c22, sails_c22), so their inputs stay theirs.

What it writes (game body frame: X forward, Y starboard, Z up, metres, origin amidships on the design waterline):
  kC22Sections        half sections, transom to stem, keel (Y 0) to sheer: hull_c22.section(x, f) at the solved canoe
                      depth, the girth bunched toward the keel as build_c22 meshes it
  hull particulars    LWL, waterline beam, canoe volume and centre of buoyancy, wetted area coefficient, and the
                      parametric stand-in fit the water's hull clip and BoatExport read
  appendage volume    what the swing keel's iron and the stub add under the hull less the trunk's water inside it: the
                      physics floats the sections on the rest, as hull_c22.solve_depth does
  kC22KeelSwing       the swing keel from down (Board 1) to up (Board 0): the plate turned about its pin by
                      (1 - Board) x keel_c22.raise_angle(), its area below the stub and the hull (the lateral area
                      the water sees), that area's centroid, its lowest point (grounding), and the whole plate's
                      centroid (its iron: the ballast moves with it)
  kC22RudderKick      the kick-up rudder from down (0) to kicked up (1, keel_c22.json's kick_up_deg about its bolt):
                      the blade's area under the waterline, its centroid and its lowest point
  rig and sails       the mast, the boom raised 11.5 cm (Bean, Nov 16), the main between the bands, the high-cut
                      genoa's corners and drawn area (sails_c22)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "Source", "SailingPhysics", "Private", "Catalina22HullData.inl")

import hull_c22 as H  # noqa: E402

N_STATIONS = 31
N_GIRTH = 16            # 17 points a section
N_SWING = 11            # Board 0, 0.1, ... 1
N_KICK = 11
GRID = 0.004            # m: the raster the swing and kick areas are measured on


def fmt(v, digits=4):
    s = ("%%.%df" % digits) % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------------ hull

def sections():
    out = []
    for x in H.stations(N_STATIONS):
        pts = [H.section(x, H.girth(k, N_GIRTH)) for k in range(N_GIRTH + 1)]
        ys = [p[0] for p in pts]
        for i in range(1, len(ys)):          # never decreasing, as FHullShape wants (rounding only)
            ys[i] = max(ys[i], ys[i - 1])
        out.append((x, H.sheer_z(x), ys, [p[1] for p in pts]))
    return out


def wetted_area(n=400, m=240):
    """Both sides' girth under the design waterline, integrated along her (m^2)."""
    total = 0.0
    dx = (H.STEM_X - H.TRANSOM_X) / n
    for i in range(n):
        x = H.TRANSOM_X + (i + 0.5) * dx
        if H.keel_z(x) >= 0:
            continue
        g = 0.0
        prev = H.section(x, 0.0)
        for k in range(1, m + 1):
            cur = H.section(x, H.girth(k, m))
            (y0, z0), (y1, z1) = prev, cur
            prev = cur
            if z0 >= 0.0:
                break
            if z1 > 0.0:                      # the last piece, cut at the waterline
                t = -z0 / (z1 - z0)
                y1, z1 = y0 + (y1 - y0) * t, 0.0
            g += math.hypot(y1 - y0, z1 - z0)
        # the transom's immersed face is not wetted area moving through the water: left out
        total += 2.0 * g * dx
    return total


def stand_in():
    """The parametric hull fit (FHullShape's formula fields) that the hull clip and BoatExport read with stations."""
    xs = [H.TRANSOM_X + (H.STEM_X - H.TRANSOM_X) * i / 400 for i in range(401)]
    hb = [H.half_beam(x) for x in xs]
    i_max = max(range(len(xs)), key=lambda i: hb[i])
    sh = [H.sheer_z(x) for x in xs]
    i_low = min(range(len(xs)), key=lambda i: sh[i])
    return {
        "MaxHalfBeam": hb[i_max], "MaxBeamX": xs[i_max], "AftLength": xs[i_max] - H.TRANSOM_X,
        "TransomBeamLoss": hb[i_max] - H.half_beam(H.TRANSOM_X + 0.01),
        "SheerZ": sh[i_low], "SheerRise": H.sheer_z(H.STEM_X) - sh[i_low], "SheerRiseFromX": xs[i_low],
    }


# ------------------------------------------------------------------ polygons

def inside(poly, x, z):
    c = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > z) != (z1 > z):
            if x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
                c = not c
    return c


def raster(poly, keep):
    """Area, centroid and centre of pressure x of the part of `poly` where keep(x, z), on a GRID raster. The centre of
    pressure is each row's quarter chord (a foil's lift acts there), weighted by the row's chord."""
    x0, x1 = min(p[0] for p in poly), max(p[0] for p in poly)
    z0, z1 = min(p[1] for p in poly), max(p[1] for p in poly)
    a = mx = mz = cp = 0.0
    nx, nz = int((x1 - x0) / GRID) + 1, int((z1 - z0) / GRID) + 1
    for j in range(nz):
        z = z0 + (j + 0.5) * GRID
        row = [x0 + (i + 0.5) * GRID for i in range(nx)]
        row = [x for x in row if keep(x, z) and inside(poly, x, z)]
        if not row:
            continue
        a += len(row)
        mx += sum(row)
        mz += z * len(row)
        cp += (max(row) - 0.25 * (max(row) - min(row))) * len(row)
    if a == 0:
        return 0.0, (0.0, 0.0), 0.0
    return a * GRID * GRID, (mx / a, mz / a), cp / a


def lowest(poly):
    return min(poly, key=lambda p: p[1])


# ------------------------------------------------------------------ keel and rudder

def keel_swing(KC):
    """[(board, area, x, z, tip x, tip z, mass x, mass z)] from Board 0 (up) to 1 (down): x the exposed area's centre of
    pressure (quarter chord), z its centroid."""
    o = KC.keel_outline(32)
    phi_up = KC.raise_angle()
    # the plate below the stub's bottom (its slot is inside the stub) and, clear of the stub, below the hull
    below = lambda x, z: z < KC.stub_bottom(x)
    rows = []
    for k in range(N_SWING):
        b = k / (N_SWING - 1)
        p = KC.turn(o, (1.0 - b) * phi_up)
        area, (_, cz), cx = raster(p, below)
        _, (mx, mz), _ = raster(p, lambda x, z: True)
        tx, tz = lowest(p)
        rows.append((b, area, cx, cz, tx, tz, mx, mz))
    return rows, phi_up


def appendage(KC, swing):
    """Net fixed volume under the hull (m^3) and its centroid: the keel's iron, the stub's moulding, less the trunk's
    flooded water inside the hull's sections (hull_c22.target_volume's terms)."""
    t = KC.thickness()
    iron = KC.KL["mass_kg"] / KC.KL["iron_kg_m3"]
    solid, flooded = KC.stub_volume()
    down = swing[-1]
    x0, x1 = KC.ST["x"]
    s0, s1 = KC.SL["x"]
    stub_c = (0.5 * (KC.ST["full_x"][0] + KC.ST["full_x"][1]), 0.5 * (KC.ST["bottom_z"] + H.keel_z(0.2)))
    trunk_c = (0.5 * (s0 + s1), 0.5 * H.keel_z(0.2))
    v = iron + solid - flooded
    cx = (iron * down[6] + solid * stub_c[0] - flooded * trunk_c[0]) / v
    cz = (iron * down[7] + solid * stub_c[1] - flooded * trunk_c[1]) / v
    return v, (cx, cz), t, iron, solid, flooded


def rudder_kick(KC):
    """[(kick, area, x, z, tip x, tip z)] from the blade down (0) to kicked up kick_up_deg (1): turned aft and up about
    its bolt, its area under the waterline."""
    o = KC.blade_outline(24)
    RD = KC.RD
    bolt = (RD["pivot_x"] + RD["head"]["bolt"][0], RD["head"]["bolt"][1])
    up = math.radians(RD["blade"]["kick_up_deg"])
    rows = []
    for k in range(N_KICK):
        f = k / (N_KICK - 1)
        p = KC.turn(o, f * up, about=bolt)
        area, (_, cz), cx = raster(p, lambda x, z: z < 0.0)
        if area == 0.0 and rows:                   # clear of the water: keep the last centre (the physics lerps to it)
            cx, cz = rows[-1][2], rows[-1][3]
        tx, tz = lowest(p)
        rows.append((f, area, cx, cz, tx, tz))
    return rows, bolt


# ------------------------------------------------------------------ rig and sails

def rig_and_sails():
    import rig_c22 as RC
    import sails_c22 as SC
    T, Hd, C, lp = SC.headsail_corners("Genoa")
    genoa_area = float(SC.set_sheets()["GenoaSet"].area())      # as sails_c22 checks it
    gx, _, gz = RC.gooseneck()
    return {
        "mast_x": RC.MAST_X, "masthead_z": RC.top_z(), "mast_d": RC.A,
        "boom_z": gz, "main_luff_x": gx,             # the gooseneck's pin: the main's tack
        "P": RC._card("P_m"), "E": RC._card("E_m"),
        "head_board": SC.MS["head_board"], "roach": SC.MS["roach"], "main_area": SC.MS["area"],
        "genoa_tack": [float(v) for v in T], "genoa_head": [float(v) for v in Hd], "genoa_clew": [float(v) for v in C],
        "genoa_lp": lp, "genoa_area": genoa_area,
    }


# ------------------------------------------------------------------ main

def build():
    depth = H.solve_depth()
    import keel_c22 as KC
    hy = H.hydrostatics()
    secs = sections()
    wet = wetted_area()
    wcoef = wet / math.sqrt(hy["volume_m3"] * hy["lwl"])
    fit = stand_in()
    swing, phi_up = keel_swing(KC)
    app_v, app_c, t, iron, solid, flooded = appendage(KC, swing)
    kick, bolt = rudder_kick(KC)
    rs = rig_and_sails()
    card = H.CARD
    wl0, wl1 = hy["waterline_x"]

    L = [
        "// Generated by Tools/shipkit/catalina22/export_physics_c22.py from the rebuilt Catalina 22 (docs/c22-10): do not edit.",
        "// Body frame metres (X forward, Y starboard, Z up, origin amidships on the design waterline, her crew aboard).",
        "// Sections from hull_c22.section at the solved canoe depth, transom to stem, each from the keel (Y 0) to the sheer.",
        "// hull_c22: canoe depth %.4f m, volume %.4f m^3, CB x %.3f z %.3f, LWL %.3f (x %.3f to %.3f), waterline beam %.3f."
        % (depth, hy["volume_m3"], hy["cb"][0], hy["cb"][2], hy["lwl"], wl0, wl1, hy["beam_wl"]),
        "",
        "constexpr int kC22Stations = %d;" % len(secs),
        "constexpr int kC22SectionPoints = %d;" % (N_GIRTH + 1),
        "constexpr double kC22CanoeVolume = %s;     // m^3 under the DWL" % fmt(hy["volume_m3"]),
        "constexpr double kC22BuoyancyX = %s; constexpr double kC22BuoyancyZ = %s;" % (fmt(hy["cb"][0]), fmt(hy["cb"][2])),
        "constexpr double kC22WaterlineMidX = %s; constexpr double kC22WaterlineHalfLength = %s;" % (fmt(0.5 * (wl0 + wl1)), fmt(0.5 * (wl1 - wl0))),
        "constexpr double kC22WaterlineBeam = %s;" % fmt(hy["beam_wl"], 3),
        "constexpr double kC22LengthOverall = %s; constexpr double kC22Beam = %s;" % (fmt(H.STEM_X - H.TRANSOM_X, 3), fmt(2 * fit["MaxHalfBeam"], 3)),
        "// Wetted area: both sides' girth under the DWL, %.2f m^2 = coef x sqrt(volume x LWL)." % wet,
        "constexpr double kC22WettedAreaCoef = %s;" % fmt(wcoef, 3),
        "// The formula's stand-in fit (the hull clip's and BoatExport's): widest at x %.2f, sheer lowest at x %.2f." % (fit["MaxBeamX"], fit["SheerRiseFromX"]),
        "constexpr double kC22MaxHalfBeam = %s; constexpr double kC22MaxBeamX = %s; constexpr double kC22AftLength = %s; constexpr double kC22TransomBeamLoss = %s;"
        % (fmt(fit["MaxHalfBeam"]), fmt(fit["MaxBeamX"], 3), fmt(fit["AftLength"], 3), fmt(fit["TransomBeamLoss"])),
        "constexpr double kC22SheerZ = %s; constexpr double kC22SheerRise = %s; constexpr double kC22SheerRiseFromX = %s;"
        % (fmt(fit["SheerZ"]), fmt(fit["SheerRise"]), fmt(fit["SheerRiseFromX"], 3)),
        "",
        "// Fixed volume under the hull: the keel's iron %.4f m^3 (%.1f mm plate) + the stub %.4f - the trunk's water %.4f."
        % (iron, 1000 * t, solid, flooded),
        "constexpr double kC22AppendageVolume = %s; constexpr double kC22AppendageX = %s; constexpr double kC22AppendageZ = %s;"
        % (fmt(app_v, 5), fmt(app_c[0], 3), fmt(app_c[1], 3)),
        "constexpr double kC22KeelMass = %s;     // kg of cast iron (specs_c22 keel_kg)" % fmt(card["targets"]["keel_kg"]),
        "constexpr double kC22KeelPivotX = %s; constexpr double kC22KeelPivotZ = %s; constexpr double kC22KeelRaiseDeg = %s;"
        % (fmt(KC.KL["pivot"][0]), fmt(KC.KL["pivot"][1]), fmt(math.degrees(phi_up), 2)),
        "constexpr double kC22KeelChord = %s;    // the plate's mean chord, square to its leading edge" % fmt(0.5 * (KC.KL["chord_root"] + KC.KL["chord_tip"]), 3),
        "// Swing keel, Board 0 (up) to 1 (down): area below the stub and hull (m^2), its centre (x at the quarter chord, z the",
        "// centroid), the lowest point, the plate's centroid (its iron).",
        "struct FC22KeelSwing { double Board, Area, X, Z, TipX, TipZ, MassX, MassZ; };",
        "constexpr int kC22KeelSwingPoints = %d;" % len(swing),
        "const FC22KeelSwing kC22KeelSwing[kC22KeelSwingPoints] = {",
    ]
    for r in swing:
        L.append("\t{ %s }," % ", ".join(fmt(v) for v in r))
    L += [
        "};",
        "",
        "// Kick-up rudder: the blade turned aft and up about its bolt (x %.4f, z %.3f) through %s deg, 0 down to 1 kicked up:"
        % (bolt[0], bolt[1], fmt(KC.RD["blade"]["kick_up_deg"])),
        "// its area under the DWL (m^2), its centre (x at the quarter chord, z the centroid), the lowest point.",
        "constexpr double kC22RudderChord = %s; constexpr double kC22RudderPivotX = %s;"
        % (fmt(0.5 * (KC.RD["blade"]["chord_top"] + KC.RD["blade"]["chord_tip"]), 3), fmt(KC.RD["pivot_x"])),
        "struct FC22RudderKick { double Kick, Area, X, Z, TipX, TipZ; };",
        "constexpr int kC22RudderKickPoints = %d;" % len(kick),
        "const FC22RudderKick kC22RudderKick[kC22RudderKickPoints] = {",
    ]
    for r in kick:
        L.append("\t{ %s }," % ", ".join(fmt(v) for v in r))
    gt, gh, gc = rs["genoa_tack"], rs["genoa_head"], rs["genoa_clew"]
    L += [
        "};",
        "",
        "// Rig (rig_c22): mast %s m fore and aft; the gooseneck at x %s; masthead %s; the gooseneck %s m up (the physics' 1.45"
        % (fmt(rs["mast_d"], 3), fmt(rs["main_luff_x"], 3), fmt(rs["masthead_z"], 3), fmt(rs["boom_z"], 3)),
        "// plus the 11.5 cm Bean asked for). Main P %s, E %s, headboard %s, roach %s m, area %s (P E / 2, the physics')."
        % (fmt(rs["P"], 3), fmt(rs["E"], 3), fmt(rs["head_board"], 3), fmt(rs["roach"], 3), fmt(rs["main_area"], 2)),
        "constexpr double kC22MastX = %s; constexpr double kC22MastheadZ = %s; constexpr double kC22MastDiameter = %s;"
        % (fmt(rs["mast_x"]), fmt(rs["masthead_z"], 3), fmt(rs["mast_d"], 3)),
        "constexpr double kC22BoomZ = %s; constexpr double kC22MainLuffX = %s; constexpr double kC22MainP = %s; constexpr double kC22MainE = %s;"
        % (fmt(rs["boom_z"], 3), fmt(rs["main_luff_x"], 3), fmt(rs["P"], 3), fmt(rs["E"], 3)),
        "constexpr double kC22MainHeadBoard = %s; constexpr double kC22MainRoach = %s; constexpr double kC22MainArea = %s;"
        % (fmt(rs["head_board"], 3), fmt(rs["roach"], 3), fmt(rs["main_area"], 2)),
        "// The genoa cut high (Bean, Nov 17): tack on its pennant, head under the hounds, clew (sails_c22), LP %.2f m; its" % rs["genoa_lp"],
        "// cloth as drawn.",
        "constexpr double kC22GenoaTackX = %s; constexpr double kC22GenoaTackZ = %s;" % (fmt(gt[0], 3), fmt(gt[2], 3)),
        "constexpr double kC22GenoaHeadX = %s; constexpr double kC22GenoaHeadZ = %s;" % (fmt(gh[0], 3), fmt(gh[2], 3)),
        "constexpr double kC22GenoaClewX = %s; constexpr double kC22GenoaClewY = %s; constexpr double kC22GenoaClewZ = %s;"
        % (fmt(gc[0], 3), fmt(gc[1], 3), fmt(gc[2], 3)),
        "constexpr double kC22GenoaArea = %s;" % fmt(rs["genoa_area"], 2),
        "",
        "struct FC22Section { double X, Sheer; double Y[kC22SectionPoints], Z[kC22SectionPoints]; };",
        "const FC22Section kC22Sections[kC22Stations] = {",
    ]
    for x, sh, ys, zs in secs:
        L.append("\t{ %s, %s, { %s }, { %s } }," % (fmt(x), fmt(sh), ", ".join(fmt(v) for v in ys), ", ".join(fmt(v) for v in zs)))
    L.append("};")
    report = {
        "depth": depth, "hydro": hy, "wet": wet, "wcoef": wcoef, "fit": fit, "swing": swing, "phi_up": math.degrees(phi_up),
        "appendage": (app_v, app_c), "kick": kick, "rig": rs,
    }
    return "\n".join(L) + "\n", report


def main():
    text, r = build()
    if "--check" in sys.argv:
        cur = open(OUT).read() if os.path.exists(OUT) else ""
        if cur != text:
            print("Catalina22HullData.inl is stale: rerun Tools/shipkit/catalina22/export_physics_c22.py")
            return 1
        print("Catalina22HullData.inl is current")
        return 0
    with open(OUT, "w") as f:
        f.write(text)
    hy = r["hydro"]
    print("wrote", os.path.relpath(OUT, ROOT))
    print("hull: canoe depth %.4f, volume %.4f m^3, CB x %+.3f z %+.3f, LWL %.3f, BWL %.3f, wetted %.2f m^2 (coef %.3f)"
          % (r["depth"], hy["volume_m3"], hy["cb"][0], hy["cb"][2], hy["lwl"], hy["beam_wl"], r["wet"], r["wcoef"]))
    print("appendage %.4f m^3 at x %.3f z %.3f" % (r["appendage"][0], *r["appendage"][1]))
    print("keel raised %.1f deg:" % r["phi_up"])
    for s in r["swing"]:
        print("  board %.1f  area %.3f at (%.3f, %.3f)  tip (%.3f, %.3f)  iron (%.3f, %.3f)" % s)
    print("rudder kick:")
    for k in r["kick"]:
        print("  kick %.1f  area %.3f at (%.3f, %.3f)  tip (%.3f, %.3f)" % k)
    rs = r["rig"]
    print("rig: masthead %.3f, boom %.3f, genoa tack %s head %s clew %s area %.2f" % (
        rs["masthead_z"], rs["boom_z"], [round(v, 3) for v in rs["genoa_tack"]], [round(v, 3) for v in rs["genoa_head"]],
        [round(v, 3) for v in rs["genoa_clew"]], rs["genoa_area"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
