"""Bean's J/22 feedback 1 (pc/j22-feedback): the traveler and the mainsheet's tackle as the class has them (Bean's cockpit
photo; traveler-deck-mount, mainsail-sheet-traveler). Replaces build_j22_hero's traveler on the cockpit sole:

- the traveler: a dark anodised track across the whole cockpit from seat to seat, let into a channel across each seat
  top so its top is about flush with the seats, open over the well (the sole and the coiled tail show under it); a
  screwed end cap at each end; the car in the middle with its control sheaves, the blue control lines out to blocks
  at the ends and back to cam cleats on the seats;
- on the car, the mainsheet's lower block: a spring over a swivel, a fiddle block (the 57 mm sheave, a smaller one
  under it, a becket) with perforated stainless side plates, and the swivelling cam cleat on its arm.

`TravelerBar` keeps its name (the bake reads Traveler_C/S/P from its top), and `MainCam` keeps its cams' names
(MainsheetCam). Both move up to the seats: the old and new values are in docs/j22-feedback. Blender frame, as
build_j22_hero.py; sizes GUESS from the photos (a 32 mm track, 57 mm fiddle)."""
import math

from mathutils import Vector

import j22_details as D
from j22_boomgear import countersunk, plate_xy, rounded
from j22_geom import cyl, tube
from j22_steering import lathe, plate


def traveler(xt, y_end, seat_z, seat_in, M):
    """The track across the cockpit at x = xt, its ends at +-y_end over the seats (seat tops at seat_z, their inboard
    edges at +-seat_in). Returns (objects, the car's top centre)."""
    out = []
    top = seat_z + 0.004
    # the track: a 32 mm T-section, 16 mm deep, its top 4 mm over the seats (let into their channel)
    prof = [(xt - 0.016, top - 0.016), (xt + 0.016, top - 0.016), (xt + 0.016, top - 0.003), (xt + 0.013, top), (xt + 0.004, top),
            (xt + 0.004, top - 0.004), (xt - 0.004, top - 0.004), (xt - 0.004, top), (xt - 0.013, top), (xt - 0.016, top - 0.003)]
    out.append(plate("TravelerBar", prof, -y_end, y_end, M["CamBase"], bev=0.0006))
    # the channel across each seat: its dark edges either side of the track, and the track's screws there
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * (seat_in + 0.01), sgn * (y_end - 0.04)))
        for side in (1, -1):
            out.append(plate_xy(f"TravChannel_{sgn}_{side}", rounded(xt + side * 0.022 - 0.004, xt + side * 0.022 + 0.004, y0, y1, 0.002),
                                seat_z - 0.002, seat_z + 0.0008, M["BlackPlastic"], bev=0.0))
        for k in range(3):
            y = y0 + (y1 - y0) * (k + 0.5) / 3
            out += countersunk(f"TravS_{sgn}_{k}", Vector((xt, y, top)), (0, 0, 1), 0.007, M["Stainless"])
    # the end caps on the seats, two screws each, a control sheave in each and a cam cleat inboard of it on the seat
    for sgn in (1, -1):
        ye = sgn * (y_end - 0.012)
        out.append(plate(f"TravEnd_{sgn}", rounded(xt - 0.024, xt + 0.024, seat_z, top + 0.016, 0.008), min(ye, ye + sgn * 0.045), max(ye, ye + sgn * 0.045),
                         M["BlackPlastic"], bev=0.003))
        for k, dy in enumerate((0.012, 0.032)):
            out += countersunk(f"TravEndS_{sgn}_{k}", Vector((xt, ye + sgn * dy, top + 0.016)), (0, 0, 1), 0.007, M["Stainless"])
        out.append(cyl(f"TravEndSheave_{sgn}", (xt - 0.026, ye + sgn * 0.022, top + 0.006), (xt - 0.016, ye + sgn * 0.022, top + 0.006), 0.010, M["SheaveGrey"], 16))
        # the control line's cam cleat on the seat, aft of the track, its lead toward the end sheave
        cx = xt - 0.10
        out += D.cam_cleat(f"TravCam_{sgn}", (cx, sgn * (y_end - 0.06), seat_z), (0, 0, 1), (0, -sgn, 0), M, 0.055)
    # the car in the middle: a low body over the track, a control sheave each end, a swivel and spring on top
    car_top = top + 0.026
    out.append(plate_xy("TravCar", rounded(xt - 0.03, xt + 0.03, -0.045, 0.045, 0.012), top - 0.004, car_top, M["BlackPlastic"], bev=0.003))
    for sgn in (1, -1):
        out.append(cyl(f"TravCarSheave_{sgn}", (xt - 0.031, sgn * 0.034, top + 0.012), (xt - 0.039, sgn * 0.034, top + 0.012), 0.009, M["SheaveGrey"], 16))
    # the control lines: from each end of the car out round the end sheave and back to the cam cleat
    for sgn in (1, -1):
        ye = sgn * (y_end - 0.012 + 0.022)
        a = (xt - 0.035, sgn * 0.045, top + 0.012)
        b = (xt - 0.021, ye, top + 0.012)
        c = (xt - 0.10, sgn * (y_end - 0.06), seat_z + 0.014)
        out.append(tube(f"TravLine_{sgn}", [a, b, (xt - 0.04, ye - sgn * 0.01, top + 0.008), c], 0.003, M["CunnLine"], smooth_path=True))
        out.append(tube(f"TravTail_{sgn}", [c, (c[0] - 0.05, c[1] - sgn * 0.02, seat_z + 0.004), (c[0] - 0.16, c[1] - sgn * 0.05, seat_z + 0.003)],
                        0.003, M["CunnLine"], smooth_path=True))
    return out, Vector((xt, 0.0, car_top))


def lower_block(car, M):
    """The mainsheet's lower block on the car (photo mainsail-sheet-traveler): a spring over the swivel, the fiddle block
    standing up from it (57 mm sheave over a 40 mm one, axle fore and aft so the sheet runs athwartships into it), its
    stainless side plates perforated, a becket, and the cam cleat on its swivelling arm. MainCam's cams keep their names
    (the MainsheetCam socket reads them)."""
    out = []
    c = Vector(car)
    # the swivel post and the spring round it
    out.append(lathe("MainSwivel", [(0.0, 0.0), (0.012, 0.0), (0.012, 0.006), (0.006, 0.008), (0.006, 0.040), (0.0, 0.040)], c, (0, 0, 1), M["Stainless"], 20))
    out.append(tube("MainSpring", [(c.x + 0.011 * math.cos(t * 0.5), c.y + 0.011 * math.sin(t * 0.5), c.z + 0.006 + t * 0.0009) for t in range(36)],
                    0.0012, M["Stainless"], smooth_path=True))
    # the fiddle: the big sheave (the sheet's two parts from the boom) over the small one
    big = c + Vector((0, 0, 0.040 + 0.045))
    out += D.block("MainsheetLow", big, (1, 0, 0), (0, 0, 1), M, 0.057, becket=False, with_shackle=False)
    small = c + Vector((0, 0, 0.040 + 0.006))
    out += D.block("MainsheetLow2", small, (1, 0, 0), (0, 0, 1), M, 0.040, with_shackle=False)
    # the stainless side plates over the cheeks, a long diamond, perforated (shown by grey dots)
    for sgn in (1, -1):
        xs = c.x + sgn * 0.022
        prof = [(0.0, 0.0), (0.028, 0.030), (0.020, 0.110), (0.0, 0.125), (-0.020, 0.110), (-0.028, 0.030)]
        out.append(plate(f"MainPlate_{sgn}", [(c.y + p, c.z + 0.025 + q) for p, q in prof], min(xs, xs + sgn * 0.002), max(xs, xs + sgn * 0.002),
                         M["Stainless"], bev=0.0005))
        # (plate() extrudes an (x, z) outline across y: turn it to lie across x)
        o = out[-1]
        for v in o.data.vertices:
            v.co.x, v.co.y = v.co.y, v.co.x
        for k in range(6):
            zk = c.z + 0.045 + 0.014 * k
            out.append(cyl(f"MainPlateHole_{sgn}_{k}", (xs + sgn * 0.0021, c.y - 0.008, zk), (xs + sgn * 0.0024, c.y - 0.008, zk), 0.0035, M["SheaveGrey"], 10))
            out.append(cyl(f"MainPlateHoleB_{sgn}_{k}", (xs + sgn * 0.0021, c.y + 0.008, zk), (xs + sgn * 0.0024, c.y + 0.008, zk), 0.0035, M["SheaveGrey"], 10))
    # the becket at the top (the sheet's dead end)
    bk = D.torus("MainBecket", 0.007, 0.0018, M["Stainless"], 16, 6)
    bk.matrix_world = D.frame(c + Vector((0, 0, 0.160)), (1, 0, 0), (0, 1, 0))
    out.append(bk)
    # the cam cleat on its arm, swung aft of the block, the line's lead toward the block's small sheave
    arm0 = c + Vector((-0.012, 0, 0.060))
    arm1 = c + Vector((-0.070, 0, 0.085))
    out.append(tube("MainCamArm", [tuple(arm0), tuple(arm0 + Vector((-0.03, 0, 0.004))), tuple(arm1)], 0.004, M["Stainless"], smooth_path=True))
    out += D.cam_cleat("MainCam", arm1, (-0.35, 0, 1), (0.9, 0, 0.4), M, 0.055)
    return out
