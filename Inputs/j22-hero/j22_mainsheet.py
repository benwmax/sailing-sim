"""Bean's J/22 feedback 1 (pc/j22-feedback): the traveler and the mainsheet's tackle as the class has them (Bean's cockpit
photo; traveler-deck-mount, mainsail-sheet-traveler). Replaces build_j22_hero's traveler on the cockpit sole:

- the traveler (rebuilt in the part detail loop, Nov 8 2026: docs/part-detail-loop/traveler.md): a black 22 mm
  high-beam track across the whole cockpit from seat to seat, let into each seat top (its head 4 mm proud) and
  bridging the well, the crew's white index marks over the well, a black end stop on each end; the 73 mm car with a
  pivoting shackle base and a control tang at each end; each side's control 2:1 from an eye strap, round a small block
  on the car's tang and back to a cam cleat on a swivel base, in a yellow line;
- on the car, the mainsheet's lower block: a spring over a swivel, a fiddle block (the 57 mm sheave, a smaller one
  under it, a becket) with perforated stainless side plates, and the swivelling cam cleat on its arm.

`TravelerBar` keeps its name (the bake reads Traveler_C/S/P from its top), and `MainCam` keeps its cams' names
(MainsheetCam). Both move up to the seats: the old and new values are in docs/j22-feedback. Blender frame, as
build_j22_hero.py; the traveler's sizes from the catalogue (traveler.md), the fiddle's GUESS from the photos (57 mm)."""
import math

from mathutils import Matrix, Vector

import j22_details as D

CAM = D.cam_cleat   # build_j22_hero sets the kit's (j22_kitfit.cam_cleat) unless --old-hardware
from j22_boomgear import countersunk, plate_xy, rounded
from j22_geom import cyl, tube
from j22_steering import lathe, plate


# J/22 traveler part loop r1 (Nov 8 2026): the Harken-type 22 mm high-beam track spanning the cockpit, its end stops,
# the 73 mm car with a pivoting shackle and control tangs, and the 2:1 control on each side (dead end at an eye strap on
# the seat, a small block on the car's tang, back to a cam cleat on a swivel base). Sizes: docs/part-detail-loop/traveler.md.
TRACK_W = 0.022          # catalogue: 22 mm track
TRACK_H = 0.019          # GUESS: high-beam section, its area (about 220 mm2) checked against the catalogue weight (586 g/m)
CAR_L, CAR_W = 0.073, 0.057   # catalogue (the 22 mm car with pivoting shackle and control tangs): 2 7/8 x 2 1/4 in
STOP_L, STOP_W = 0.030, 0.032  # GUESS from Bean's photo: a square block a little wider than the track
TROUGH_W = 0.056         # GUESS from Bean's photo: the seats' moulded indentation the track lies in, its width ...
TROUGH_END = 0.012       # ... and how far it runs past the track's end (build_j22_hero cuts it into the cockpit liner)

# seven-segment numerals painted on the track (the crew's own marks in Bean's photo): segments as (x0, y0, x1, y1) in a
# 1 x 2 cell, x across the digit, y up it
_SEG = {"a": (0, 2, 1, 2), "b": (1, 1, 1, 2), "c": (1, 0, 1, 1), "d": (0, 0, 1, 0), "e": (0, 0, 0, 1), "f": (0, 1, 0, 2), "g": (0, 1, 1, 1)}
_DIGITS = {"1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc"}


def _track_profile(xt, top):
    """The high-beam section in (x, z): a 22 mm head with the ball races under its edges, a stem and a foot."""
    h = TRACK_W / 2
    z = lambda d: top - d  # noqa: E731
    right = [(h - 0.0012, z(0.0)), (h, z(0.0012)), (h, z(0.0036)), (h - 0.0012, z(0.0050)),     # the head's edge
             (0.0085, z(0.0056)), (0.0080, z(0.0068)),                                            # the ball race under it
             (0.0034, z(0.0074)), (0.0030, z(TRACK_H - 0.0034)),                                  # the stem
             (0.0052, z(TRACK_H - 0.0024)), (0.0052, z(TRACK_H - 0.0008)), (0.0044, z(TRACK_H))]  # the foot
    pts = [(xt + x, zz) for x, zz in right]
    pts += [(xt - x, zz) for x, zz in reversed(right)]
    return pts


def _poly_area(pts):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def _digit(name, ch, cx, cy, size, z, sgn, M):
    """One painted numeral flat on the track at (cx, cy), its foot toward -sgn*y (readable from that end's seat)."""
    out = []
    w, s = size * 0.5, size * 0.5
    t = size * 0.11
    for k, seg in enumerate(_DIGITS[ch]):
        x0, y0, x1, y1 = _SEG[seg]
        # the digit's own x runs aft (-x) and its up outboard (sgn * y)
        ax0, ax1 = sorted((cx + (x0 - 0.5) * w * -1, cx + (x1 - 0.5) * w * -1))
        ay0, ay1 = sorted((cy + sgn * (y0 - 1) * s, cy + sgn * (y1 - 1) * s))
        out.append(plate_xy(f"{name}_{k}", rounded(ax0 - t / 2, ax1 + t / 2, ay0 - t / 2, ay1 + t / 2, t * 0.3, 2), z, z + 0.0002, M["WhitePlastic"], bev=0.0))
    return out


def traveler(xt, y_end, seat_z, seat_in, M):
    """The track across the cockpit at x = xt, its ends at +-y_end over the seats (seat tops at seat_z, their inboard
    edges at +-seat_in). Returns (objects, the car's top centre). TravelerBar keeps its name and its top and ends (the
    bake reads Traveler_C/S/P from them); the car's top centre is unchanged, so the lower block and its sockets stay."""
    out = []
    top = seat_z + 0.004
    # the track: black hardcoat, let into each seat (its head 4 mm proud) and spanning the well between them
    prof = _track_profile(xt, top)
    bar = plate("TravelerBar", prof, -y_end, y_end, M["CamBase"], bev=0.0004)
    bar["section_mm2"] = round(_poly_area(prof) * 1e6, 1)
    out.append(bar)
    # the track lies in the seats' indentation (cut by build_j22_hero), its foot on the trough's floor; flat-head screws
    # every 100 mm where it lies on the seats
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * (seat_in + 0.012), sgn * (y_end - STOP_L - 0.004)))
        n = int((y1 - y0) / 0.1)
        for k in range(n + 1):
            y = sgn * (seat_in + 0.05 + 0.1 * k)
            if abs(y) < abs(y_end) - STOP_L - 0.015:
                out += countersunk(f"TravS_{sgn}_{k}", Vector((xt, y, top)), (0, 0, 1), 0.0075, M["Stainless"])
    # the crew's index marks over the well: a tick every 25 mm, a long one and a numeral every 100 mm out from the
    # middle, painted by hand (Bean's photo)
    for sgn in (1, -1):
        for k in range(1, 20):
            y = sgn * 0.025 * k
            if abs(y) > seat_in - 0.01 + 1e-6:      # (0.025 * 12 is a hair over 0.30: keep the mark 1 cm in)
                break
            long_ = k % 4 == 0
            w = 0.016 if long_ else 0.008
            off = -0.003 if long_ else -0.007
            out.append(plate_xy(f"TravMark_{sgn}_{k}", rounded(xt + off - w / 2, xt + off + w / 2, y - 0.0009, y + 0.0009, 0.0004, 1),
                                top, top + 0.0002, M["WhitePlastic"], bev=0.0))
            if long_:
                out += _digit(f"TravNum_{sgn}_{k}", str(k // 4), xt + 0.0055, y + sgn * 0.012, 0.010, top, sgn, M)
    # the end stops: a black block over each end of the track, two screws on top
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * (y_end - STOP_L), sgn * (y_end + 0.002)))
        out.append(plate("TravStop_" + str(sgn), rounded(xt - STOP_W / 2, xt + STOP_W / 2, top - TRACK_H, top + 0.018, 0.0025),
                         y0, y1, M["BlackPlastic"], bev=0.0015))
        for k, dx in enumerate((-0.008, 0.008)):
            out += countersunk(f"TravStopS_{sgn}_{k}", Vector((xt + dx, sgn * (y_end - STOP_L / 2), top + 0.018)), (0, 0, 1), 0.0060, M["Stainless"])
    # the car: one black anodised body wrapping the track's head (its skirts down past the ball races), chamfered along
    # its top, with moulded end caps of the same section whose tops slope down to the ends, a screw in each cap
    hl, hw = CAR_L / 2, CAR_W / 2
    body_l = hl - 0.010
    sk = TRACK_W / 2 + 0.0012
    half = [(sk, top - 0.0080), (hw - 0.002, top - 0.0080), (hw, top - 0.0060), (hw, top + 0.0040), (hw - 0.007, top + 0.0095),
            (0.010, top + 0.0110)]
    car_prof = [(xt + x, z) for x, z in half] + [(xt - x, z) for x, z in reversed(half)] + [(xt - sk, top + 0.0006), (xt + sk, top + 0.0006)]
    out.append(plate("TravCar", car_prof, -body_l, body_l, M["BlackPlastic"], bev=0.0012))
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * (body_l + 0.0004), sgn * hl))
        o = plate(f"TravCarEnd_{sgn}", [(x, z) if z < top else (x, z - 0.0005) for x, z in car_prof], y0, y1, M["BlackPlastic"], bev=0.0015)
        for v in o.data.vertices:
            if abs(v.co.y) > hl - 0.001 and v.co.z > top + 0.002:
                v.co.z -= 0.0055
        out.append(o)
        out += countersunk(f"TravCarEndS_{sgn}", Vector((xt + 0.016, sgn * (body_l + 0.004), top + 0.0098)), (0, 0, 1), 0.0045, M["Stainless"])
        out += countersunk(f"TravCarEndS2_{sgn}", Vector((xt - 0.016, sgn * (body_l + 0.004), top + 0.0098)), (0, 0, 1), 0.0045, M["Stainless"])
    # the pivoting shackle's base: a stainless boss with two ears and a pin across the boat; the lower block's swivel
    # (lower_block) stands on it at the car's top centre, as before
    car_top = top + 0.026
    out.append(lathe("TravCarBoss", [(0.0, 0.0), (0.012, 0.0), (0.012, 0.002), (0.008, 0.004), (0.0, 0.004)],
                     Vector((xt, 0, top + 0.0108)), (0, 0, 1), M["Stainless"], 20))
    for sgn in (1, -1):
        out.append(plate(f"TravCarEar_{sgn}", rounded(xt - 0.007, xt + 0.007, top + 0.012, car_top - 0.001, 0.006),
                         min(sgn * 0.006, sgn * 0.009), max(sgn * 0.006, sgn * 0.009), M["Stainless"], bev=0.0006))
    out.append(cyl("TravCarPin", (xt, -0.011, top + 0.020), (xt, 0.011, top + 0.020), 0.0025, M["Stainless"], 14))
    for sgn in (1, -1):
        out.append(cyl(f"TravCarPinHead_{sgn}", (xt, sgn * 0.011, top + 0.020), (xt, sgn * 0.0125, top + 0.020), 0.0038, M["Stainless"], 14))
    # the control tangs: a stainless plate standing up at each end, a small block shackled to it
    blocks = {}
    for sgn in (1, -1):
        yt = sgn * (hl - 0.004)
        out.append(plate_yz_tang(f"TravTang_{sgn}", xt, yt, top + 0.004, sgn, M))
        bc = Vector((xt, sgn * (hl + 0.017), top + 0.010))
        out += D.block(f"TravBlock_{sgn}", bc, (0, 0, 1), (0, -sgn, 0), M, 0.018, with_shackle=False)
        # the block's head to the tang: a small shackle's bow
        sh = D.torus(f"TravBlockSh_{sgn}", 0.005, 0.0013, M["Stainless"], 14, 6)
        sh.matrix_world = D.frame(Vector((xt, sgn * (hl + 0.0015), top + 0.010)), (0, 1, 0), (1, 0, 0))
        out.append(sh)
        blocks[sgn] = bc
    # each side's control, 2:1: the line dead-ends on an eye strap on the seat forward of the track's end, runs in to the
    # car's block and back out to a cam cleat on a swivel base aft of the track's end; its tail lies on the seat
    for sgn in (1, -1):
        ye = sgn * (y_end - 0.012)
        eye = Vector((xt + 0.050, ye, seat_z))
        out += D.padeye(f"TravEye_{sgn}", eye, (0, 0, 1), M)
        # the dead end's stopper knot on the far side of the loop
        kn = D.torus(f"TravLineKnot_{sgn}", 0.0035, 0.0028, M["TravLine"], 14, 8)
        kn.matrix_world = D.frame(eye + Vector((0, sgn * 0.009, 0.009)), (1, 0, 0), (0, 1, 0))
        out.append(kn)
        cam_at = Vector((xt - 0.062, sgn * (y_end - 0.018), seat_z + 0.009))
        out.append(cyl(f"TravCamBase_{sgn}", (cam_at.x, cam_at.y, seat_z), (cam_at.x, cam_at.y, seat_z + 0.009), 0.024, M["BlackPlastic"], 28))
        out.append(cyl(f"TravCamBaseRing_{sgn}", (cam_at.x, cam_at.y, seat_z + 0.009), (cam_at.x, cam_at.y, seat_z + 0.0098), 0.0205, M["Stainless"], 28))
        lead = (Vector((xt, blocks[sgn].y, 0)) - Vector((cam_at.x, cam_at.y, 0))).normalized()
        cam = CAM(f"TravCam_{sgn}", cam_at, (0, 0, 1), tuple(lead), M, 0.055)
        out += cam
        bc = blocks[sgn]
        r = 0.0095
        # in from the eye strap's loop to the block's forward side, round the sheave, and out from its aft side
        a = eye + Vector((0, 0, 0.009))
        b = Vector((bc.x + r, bc.y, bc.z))
        wrap = [tuple(bc + Vector((r * math.cos(t), -sgn * r * math.sin(t), 0))) for t in (0.0, 0.6, 1.2, 1.57, 1.97, 2.54, math.pi)]
        c = Vector((bc.x - r, bc.y, bc.z))
        jaw = cam_at + lead * 0.012 + Vector((0, 0, 0.016))
        lead_in = cam_at + lead * 0.034 + Vector((0, 0, 0.016))
        out.append(tube(f"TravLine_{sgn}a", [tuple(a), tuple(a.lerp(b, 0.5) + Vector((0, 0, 0.004))), tuple(b)], 0.0025, M["TravLine"], smooth_path=False))
        out.append(tube(f"TravLine_{sgn}w", wrap, 0.0025, M["TravLine"], smooth_path=True))
        tail0 = cam_at - lead * 0.032 + Vector((0, 0, 0.012))
        through = [tuple(lead_in), tuple(jaw)]
        if "sock_Line" in cam[0]:
            # the kit's cam (hardware-fit wave 2): in through its fairlead, between the cams' jaws, out behind them, each at
            # the line's own height over the base (the old points floated a centimetre over the micro cam)
            ob = cam[0]
            fair = ob.matrix_world @ Vector(ob["sock_Lead"])
            jaw = ob.matrix_world @ Vector(ob["sock_Line"])
            lead_in = fair + lead * 0.022
            tail0 = jaw - lead * 0.024
            through = [tuple(lead_in), tuple(fair), tuple(jaw)]
        out.append(tube(f"TravLine_{sgn}b", [tuple(c), tuple(c.lerp(lead_in, 0.5) + Vector((0, 0, 0.004)))] + through,
                        0.0025, M["TravLine"], smooth_path=False))
        out.append(tube(f"TravTail_{sgn}", [tuple(jaw), tuple(tail0), tuple(tail0 + Vector((-0.05, sgn * 0.012, -0.012))),
                                            (cam_at.x - 0.16, cam_at.y - sgn * 0.03, seat_z + 0.0026),
                                            (cam_at.x - 0.24, cam_at.y - sgn * 0.09, seat_z + 0.0026),
                                            (cam_at.x - 0.20, cam_at.y - sgn * 0.16, seat_z + 0.0026)],
                        0.0025, M["TravLine"], smooth_path=True))
    return out, Vector((xt, 0.0, car_top))


def plate_yz_tang(name, xt, yt, z0, sgn, M):
    """A control tang: a 3 mm stainless plate in the y-z plane at the car's end, rounded on top, its hole implied by the
    shackle through it."""
    from j22_boomgear import plate_yz
    t = 0.0015
    y0, y1 = sorted((yt, yt + sgn * 0.010))
    return plate_yz(name, rounded(y0, y1, z0, z0 + 0.012, 0.004, 4), xt - t, xt + t, M["Stainless"], bev=0.0004)



def lower_block(car, M, kit_part):
    """The mainsheet's lower block on the car (Bean's photo; part detail loop, docs/part-detail-loop/traveler.md): the
    boat kit's FiddleCam at its 57 mm size (made from the same photo: black moulded cheeks, the cam cleat with red jaws on
    an aluminium bracket round the big hub, a becket), standing head down on the car's pivoting shackle, its axles fore
    and aft so the sheet comes down athwartships into it, a coil spring round the swivel holding it upright. Its big
    sheave's centre stays where the old block's was (MainsheetBlock); MainsheetCam is its jaws (the kit's Cam socket)."""
    c = Vector(car)
    ob = kit_part("MainsheetLow", "FiddleCam", (0, 0, 0), size="57")[0]
    axle = Vector(ob["sock_Axle"])
    # part X (the cam's side) to port, part Y (the axles) forward, part Z (up the block toward its head) down
    rot = Matrix(((0, 1, 0), (1, 0, 0), (0, 0, -1))).to_4x4()
    target = c + Vector((0, 0, 0.085))                    # the old block's big sheave (build_j22_hero's mainsheet ends here)
    rot.translation = target - rot.to_3x3() @ axle
    ob.matrix_world = rot
    out = [ob]
    head = rot.translation
    # from the car's shackle pin up to the block's own swivel: a stainless post and a coil spring round it
    base = c - Vector((0, 0, 0.006))
    if head.z > base.z + 0.004:
        out.append(lathe("MainSwivel", [(0.0, 0.0), (0.0045, 0.0), (0.0045, head.z - base.z + 0.002), (0.0, head.z - base.z + 0.002)],
                         base, (0, 0, 1), M["Stainless"], 16))
        h = head.z - base.z
        turns = max(3, int(h / 0.0045))
        n = turns * 10
        out.append(tube("MainSpring", [(c.x + 0.0095 * math.cos(2 * math.pi * t / 10), c.y + 0.0095 * math.sin(2 * math.pi * t / 10),
                                        base.z + 0.002 + h * 0.9 * t / n) for t in range(n + 1)], 0.0011, M["Stainless"], res=6, smooth_path=True))
    return out
