"""JibTrack and TrackCar: the jib lead track and its car (part detail loop, Nov 2026: docs/part-detail-loop/jibtrack.md).

The J/22's jib lead: a short 22 mm small-boat track on each side deck, beside the cockpit's forward end, with a slider
car carrying the lead sheave. The jib sheet runs UNDER the sheave, between the cheeks, so the car pulls the sheet down
and the sheave sits well clear of the car's body. The car is pinned in place by a spring plunger (pinstop) that drops
into a row of holes along the track's top; on the J/22 the class's 2:1 jib sheet is tied to the car's eye strap.

Sizes are catalogue numbers (no maker's shapes copied, no logos):
- track: 22 mm small-boat low-beam pinstop track, 600 mm (also 450 and 900), 5 mm flat-head fasteners every 100 mm,
  hard-anodised 6061 aluminium; 252 g for 600 mm, which with aluminium's density gives the ~155 mm2 section built here;
- car: 22 mm pinstop slider car with sheave (the current one replaces the older 393-style cars): 95 mm long, 35 mm wide,
  38 mm sheave for line up to 12 mm;
- end stops: a low-load end stop at each end, one screw down into the track.
Proportions without a catalogue number (track height, cheek shape, plunger knob, pinstop hole pitch 25 mm) are
estimates from the cars' product photos and are flagged so on the part card.

It lives in its own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part below replaces bk_parts' older JibTrack and TrackCar of the same names.
Conventions follow bk_parts: origin at the middle of the track's underside, +X forward along the track, +Z up. The
car sits with its middle at the track's middle; `Sheave` is the sheave's centre (the hero J/22's JibLead socket is
read from it, so it stays where the old car had it) and `Lead` is where the sheet runs, under the sheave.
"""
import math

from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

M = P.M

# track section (22 mm small-boat track): a 25 mm foot, a waist the car's lips hook under, a 22 mm head
TRACK_H = 0.011
FOOT_W = 0.025
HEAD_W = 0.022
SCREW_PITCH = 0.100          # catalogue: 5 mm flat-head fasteners every 100 mm
PIN_PITCH = 0.025            # pinstop holes (estimate)
PIN_HOLE_R = 0.0030

# car (22 mm pinstop slider car with sheave): 95 x 35 mm, 38 mm sheave
CAR_L = 0.095
CAR_W = 0.035
SADDLE = 0.0150              # above the deck: the slider's top under the sheave (the sheet's channel)
SHOULDER = 0.0245            # the raised ends' top (pinstop aft, eye strap forward)
SHEAVE_X = 0.010
SHEAVE_Z = 0.045             # the old kit car's sheave centre, kept so the hero's JibLead socket doesn't move
SHEAVE_R = 0.019
SHEAVE_T = 0.013             # across the boat, for line up to 12 mm
CHEEK_T = 0.0025
CHEEK_Y = SHEAVE_T / 2 + 0.0008 + CHEEK_T / 2
CAR_X = 0.022                # the car's middle: the sheave sits in its aft half so the sheet leaves aft clear of the car
PLUNGER_X = 0.057
EYE_X = 0.041


def _track_section():
    """(across, up) outline of the track, counter-clockwise from the foot's bottom left corner."""
    f, h = FOOT_W / 2, HEAD_W / 2
    c = 0.0007
    return [(-f + c, 0.0), (f - c, 0.0), (f, c), (f, 0.0030), (f - 0.0012, 0.0036),
            (h - 0.0048, 0.0038), (h - 0.0048, 0.0060),              # the waist under the head
            (h - 0.0005, 0.0062), (h, 0.0069), (h, TRACK_H - 0.0018),
            (h - 0.0006, TRACK_H - 0.0006), (h - 0.0018, TRACK_H),
            (-h + 0.0018, TRACK_H), (-h + 0.0006, TRACK_H - 0.0006), (-h, TRACK_H - 0.0018), (-h, 0.0069),
            (-h + 0.0005, 0.0062), (-h + 0.0048, 0.0060), (-h + 0.0048, 0.0038),
            (-f + 0.0012, 0.0036), (-f, 0.0030), (-f, c)]


def _stations(length, pitch, margin):
    n = int((length - 2 * margin) / pitch + 1e-6)
    x0 = -n * pitch / 2
    return [x0 + i * pitch for i in range(n + 1)]


def _track(length):
    objs = []
    sec = _track_section()
    track = G.sweep("track", [(-length / 2, 0, 0), (length / 2, 0, 0)], sec, M("Aluminium"), twist_up=(0, 0, 1))
    # the screw countersinks and the pinstop holes, cut in one go
    screws = _stations(length, SCREW_PITCH, 0.035)
    holes = [x for x in _stations(length, PIN_PITCH, 0.030) if min(abs(x - s) for s in screws) > 0.008]
    cutters = []
    for i, x in enumerate(holes):
        cutters.append(G.cyl(f"hole{i}", (x, 0, TRACK_H - 0.006), (x, 0, TRACK_H + 0.002), PIN_HOLE_R, None, 16))
    for i, x in enumerate(screws):
        cutters.append(G.lathe(f"csk{i}", [(0, TRACK_H - 0.0032), (0.0026, TRACK_H - 0.0032), (0.0050, TRACK_H + 0.0001),
                                           (0.0050, TRACK_H + 0.002), (0, TRACK_H + 0.002)], None, 20))
        cutters[-1].location = (x, 0, 0)
        G.bake_xform(cutters[-1])
    cutter = G.join("track_cuts", cutters)
    G.boolean(track, cutter)
    G.finish(track, 0.0, sharp=40)
    objs.append(track)
    # flat-head screws sitting just below the top in their countersinks, a cross recess in each
    for i, x in enumerate(screws):
        head = G.lathe(f"screw{i}", [(0, TRACK_H - 0.0030), (0.0024, TRACK_H - 0.0030), (0.0046, TRACK_H - 0.0004),
                                     (0.0044, TRACK_H - 0.0002), (0, TRACK_H - 0.0002)], M("Stainless"), 20)
        head.location = (x, 0, 0)
        G.bake_xform(head)
        objs.append(G.finish(head, 0, weighted=False))
        for a in (0, 90):
            r = G.box(f"screw{i}_x{a}", (0, 0, TRACK_H - 0.00035), (0.0042, 0.0008, 0.0004), M("BlackPlastic"))
            r.matrix_world = Matrix.Translation((x, 0, 0)) @ Matrix.Rotation(math.radians(a + 45), 4, "Z")
            G.bake_xform(r)
            objs.append(G.finish(r, 0, weighted=False))
    # a low-load end stop at each end: a moulded block over the track's end, sloped inboard, one screw on top
    for s in (-1, 1):
        x_out = s * length / 2
        stop = G.sweep(f"endstop{s}", [(x_out + s * 0.002, 0, 0), (x_out - s * 0.024, 0, 0)],
                       [(-0.0145, 0.0), (0.0145, 0.0), (0.0145, 0.010), (0.0105, 0.0145), (-0.0105, 0.0145), (-0.0145, 0.010)],
                       M("BlackPlastic"), radii=[1.0, 1.0], twist_up=(0, 0, 1))
        # slope the inboard face: pull the top inboard edge outboard
        for v in stop.data.vertices:
            if abs(v.co.x - (x_out - s * 0.024)) < 1e-6 and v.co.z > 0.009:
                v.co.x += s * 0.008 * (v.co.z - 0.009) / 0.0055
        G.finish(stop, 0.0012, sharp=40)
        objs.append(stop)
        xs = x_out - s * 0.009
        objs += G.screw_heads(f"endstop{s}_screw", [(xs, 0, 0.0145)], M("Stainless"), 0.0034, 0.0016)
    return objs


def _car(z0=0.0):
    """The slider car with its sheave, pinstop and eye strap; z0 is the track's top (the car's parts are built to the
    J/22 heights above the deck and moved by z0 - TRACK_H)."""
    dz = z0 - TRACK_H
    objs = []
    x0, x1 = CAR_X - CAR_L / 2, CAR_X + CAR_L / 2
    # the slider: a low aluminium base, rounded ends, its skirts hugging the track's head down to the waist; a low
    # saddle aft under the sheave, where the sheet runs and leaves aft over the car's end, and a raised shoulder forward
    # carrying the eye strap and the pinstop
    base = G.prism("car_body", G.rrect(CAR_L - 0.008, CAR_W, 0.010, 8), 0.0035, SADDLE, M("Aluminium"), taper=0.95)
    base.location = (CAR_X, 0, 0)
    G.bake_xform(base)
    objs.append(G.finish(base, 0.0016, sharp=40))
    sx0, sx1 = SHEAVE_X + 0.023, x1 - 0.008
    sh_ = G.prism("car_shoulder", G.rrect(sx1 - sx0, CAR_W - 0.006, 0.009, 8), SADDLE - 0.002, SHOULDER, M("Aluminium"), taper=0.84)
    sh_.location = ((sx0 + sx1) / 2, 0, 0)
    G.bake_xform(sh_)
    objs.append(G.finish(sh_, 0.0018, sharp=40))
    # black moulded end caps at each end of the slider (they hold its slide balls), wrapping the track's head
    for s, xe in ((-1, x0 + 0.0030), (1, x1 - 0.0030)):
        cap = G.prism(f"liner{s}", G.rrect(0.008, CAR_W - 0.007, 0.0035, 6), 0.0045, SADDLE - 0.0015, M("BlackPlastic"), taper=0.88)
        cap.location = (xe, 0, 0)
        G.bake_xform(cap)
        objs.append(G.finish(cap, 0.0012))
    # the sheave carrier: two stainless cheeks standing on the saddle, the sheave's rim showing round their tops
    rc = SHEAVE_R - 0.0035                       # the cheeks' top arc: inside the sheave's rim
    for s in (-1, 1):
        outline = [(SHEAVE_X - 0.022, SADDLE - 0.001), (SHEAVE_X + 0.024, SADDLE - 0.001)]
        for k in range(15):
            a = math.radians(-10 + 200 * k / 14)
            outline.append((SHEAVE_X + rc * math.cos(a), SHEAVE_Z + rc * math.sin(a)))
        # back down to the boss in a straight run each side (the line passes under the sheave between them)
        cheek = G.prism(f"cheek{s}", [(x, z) for x, z in outline], -CHEEK_T / 2, CHEEK_T / 2, M("Stainless"))
        cheek.matrix_world = Matrix.Translation((0, s * CHEEK_Y, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
        G.bake_xform(cheek)
        objs.append(G.finish(cheek, 0.0006, sharp=40))
        # axle head and the spacer rivet's head low at the front
        for (hx, hz, hr) in ((SHEAVE_X, SHEAVE_Z, 0.0045), (SHEAVE_X + 0.018, SADDLE + 0.006, 0.0025), (SHEAVE_X - 0.016, SADDLE + 0.006, 0.0025)):
            head = G.lathe(f"axle{s}_{hx:.3f}", [(0, 0), (hr, 0), (hr * 0.85, 0.0012), (0, 0.0015)], M("Stainless"), 16)
            head.matrix_world = Matrix.Translation((hx, s * (CHEEK_Y + CHEEK_T / 2), hz)) @ Matrix.Rotation(math.radians(-90 * s), 4, "X")
            G.bake_xform(head)
            objs.append(G.finish(head, 0, weighted=False))
    # the sheave: grooved for 8-12 mm line, a stainless bearing race round the axle
    t = SHEAVE_T / 2
    prof = [(0.0045, -t), (SHEAVE_R - 0.0010, -t), (SHEAVE_R, -t + 0.0010), (SHEAVE_R, -t + 0.0022),
            (SHEAVE_R - 0.0050, -0.0015), (SHEAVE_R - 0.0058, 0.0), (SHEAVE_R - 0.0050, 0.0015),
            (SHEAVE_R, t - 0.0022), (SHEAVE_R, t - 0.0010), (SHEAVE_R - 0.0010, t), (0.0045, t)]
    sh = G.lathe("sheave", prof, M("BlackPlastic"), 40)
    sh.matrix_world = Matrix.Translation((SHEAVE_X, 0, SHEAVE_Z)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(sh)
    objs.append(G.finish(sh, 0, sharp=50))
    race = G.lathe("sheave_race", [(0.0025, -t - 0.0002), (0.0050, -t - 0.0002), (0.0050, t + 0.0002), (0.0025, t + 0.0002)], M("Stainless"), 20)
    race.matrix_world = Matrix.Translation((SHEAVE_X, 0, SHEAVE_Z)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(race)
    objs.append(G.finish(race, 0, sharp=50))
    # the pinstop at the forward end: a turned housing, the pin's collar and a black pull knob
    housing = G.lathe("plunger_housing", [(0, SHOULDER - 0.001), (0.0068, SHOULDER - 0.001), (0.0068, SHOULDER + 0.0045),
                                          (0.0055, SHOULDER + 0.0060), (0, SHOULDER + 0.0060)], M("Aluminium"), 24)
    housing.location = (PLUNGER_X, 0, 0)
    G.bake_xform(housing)
    objs.append(G.finish(housing, 0.0006))
    pin = G.cyl("plunger_pin", (PLUNGER_X, 0, SHOULDER + 0.005), (PLUNGER_X, 0, SHOULDER + 0.010), 0.0022, M("Stainless"), 14)
    objs.append(G.finish(pin, 0, weighted=False))
    knob = G.lathe("plunger_knob", [(0, SHOULDER + 0.0095), (0.0045, SHOULDER + 0.0095), (0.0068, SHOULDER + 0.0115),
                                    (0.0072, SHOULDER + 0.0150), (0.0060, SHOULDER + 0.0172), (0, SHOULDER + 0.0178)], M("BlackPlastic"), 24)
    knob.location = (PLUNGER_X, 0, 0)
    G.bake_xform(knob)
    objs.append(G.finish(knob, 0, sharp=50))
    for k in range(24):                          # fine knurling round the knob
        a = 2 * math.pi * k / 24
        fl = G.box(f"knob_flute{k}", (0, 0, 0), (0.0007, 0.0009, 0.0030), M("BlackPlastic"))
        fl.matrix_world = (Matrix.Translation((PLUNGER_X, 0, SHOULDER + 0.0135)) @ Matrix.Rotation(a, 4, "Z")
                           @ Matrix.Translation((0.0070, 0, 0)))
        G.bake_xform(fl)
        objs.append(G.finish(fl, 0.0002))
    # the eye strap just forward of the cheeks (the J/22's 2:1 jib sheet is tied here): a stainless bar loop on two rivets
    ex, ze = EYE_X, SHOULDER
    arc = [(ex, 0.0085 * math.cos(a), ze + 0.0010 + 0.0050 * math.sin(a)) for a in [math.radians(180 - 180 * i / 12) for i in range(1, 12)]]
    path = [(ex, -0.0085, ze - 0.0005), (ex, -0.0085, ze + 0.0010)] + arc + [(ex, 0.0085, ze + 0.0010), (ex, 0.0085, ze - 0.0005)]
    eye = G.sweep("eyestrap", path, G.ellipse(0.0032, 0.0014, 12), M("Stainless"), twist_up=(1, 0, 0))
    objs.append(G.finish(eye, 0, weighted=False))
    for s in (-1, 1):
        foot = G.lathe(f"eyestrap_foot{s}", [(0, ze - 0.001), (0.0042, ze - 0.001), (0.0042, ze + 0.0008),
                                             (0.0030, ze + 0.0020), (0, ze + 0.0022)], M("Stainless"), 16)
        foot.location = (ex, s * 0.0085, 0)
        G.bake_xform(foot)
        objs.append(G.finish(foot, 0, weighted=False))
    if abs(dz) > 1e-9:
        for o in objs:
            o.location = (0, 0, dz)
            G.bake_xform(o)
    return objs


def _car_sockets(dz=0.0):
    return [("Sheave", (SHEAVE_X, 0, SHEAVE_Z + dz)),
            ("Lead", (SHEAVE_X, 0, (SADDLE + SHEAVE_Z - SHEAVE_R) / 2 + dz)),      # where the sheet runs, under the sheave
            ("SheetEye", (EYE_X, 0, SHOULDER + 0.006 + dz)),
            ("Plunger", (PLUNGER_X, 0, SHOULDER + 0.0178 + dz))]


@P.part("JibTrack", "track", "22 mm small-boat pinstop track with end stops and a jib lead car (sheave, pinstop, eye strap); length option")
def jib_track(length=0.60):
    objs = _track(length) + _car(TRACK_H)
    return P.done("JibTrack", objs, _car_sockets() + [("CarFwd", (0.045, 0, 0.026)), ("TrackEnd", (length / 2, 0, 0))])


@P.part("TrackCar", "track", "Jib lead car for 22 mm track alone: a sheave between stainless cheeks, pinstop, eye strap")
def track_car():
    objs = _car(z0=0.0)
    return P.done("TrackCar", objs, _car_sockets(-TRACK_H) + [("Track", (0, 0, 0))])
