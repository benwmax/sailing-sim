"""The Catalina 22's deck hardware and running rigging as meshes (docs/c22-7), from hardware_c22. Imported by
build_c22.py (needs Blender's Python). Built in the game's frame and written with Y mirrored to Blender's port-positive
Y, as the rest of her is (build_deck_c22.Mesh).

Objects:
  C22_Hardware        the deck's kit fittings (winches and their cleats, the genoa's and jib's tracks, fairleads and
                      padeyes, the traveller on its moulded bridge, the mooring cleats, handrails, vents, the fore
                      hatch on slice 2's curb, the bow eye, scuppers, the handle's pocket) and the folding stern ladder
  C22_Lifelines       the bow pulpit, stern rail, stanchions and the lifeline wires
  C22_MastHardware    the halyards' cleats and exit plates, the pole lift's padeye and cam: the mast's, they lower with it
  C22_Halyards        the halyards' falls, hitches and hung coils (in every state)
  C22_Lines_<State>   each state's sheets, tackles (with their blocks), turning blocks, tails and coils: Rest, Up
                      (main and genoa), Jib, Reef and Run (main and spinnaker). Only Rest is shown.

build_all returns the objects and the hardware's sockets in the game's sockets file shape, for slice 9 (the live
ropes' ends) and c22_check.py. It checks every kit socket hardware_c22.py copies against the part it builds and fails
if one moved by more than a millimetre.
"""
import math

import bpy

import build_deck_c22 as BD
import build_keel_c22 as BK
import build_rig_c22 as BR
import build_sails_c22 as BS
import deck_c22 as D
import hardware_c22 as HC
import rig_c22 as RC

ROPE_N, COIL_N, WIRE_N = 8, 6, 6     # sides of a working line, of a coil's rope, of a lifeline's wire
SIMPLIFY = 0.0015                   # a line's points kept where it bends more than this (m) off the straight
SHOWN = ("C22_Hardware", "C22_Lifelines", "C22_MastHardware", "C22_Halyards", "C22_Lines_Rest")
STATE_OB = {"rest": "Rest", "up": "Up", "jib": "Jib", "reef": "Reef", "run": "Run"}
SLOT_RGB = {"RopeSheet": (0.55, 0.64, 0.78), "RopeHalyard": (0.85, 0.84, 0.78), "RopeSpin": (0.75, 0.18, 0.15),
            "RopeControl": (0.2, 0.25, 0.45), "Lifeline": (0.85, 0.86, 0.87)}


class Mats(dict):
    """The boat's materials, with any slot the kit or the ropes name and the boat lacks made on first use."""

    def __missing__(self, name):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = (*SLOT_RGB.get(name, (0.6, 0.6, 0.6)), 1.0)
        self[name] = m
        return m


def simplify(pts, tol=SIMPLIFY):
    """Douglas-Peucker: the polyline's points that stand more than tol off the chord of their neighbours kept."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    ab = b - a
    L2 = max(ab.length_squared, 1e-12)
    best, k = -1.0, 0
    for i in range(1, len(pts) - 1):
        t = max(0.0, min(1.0, (pts[i] - a).dot(ab) / L2))
        d = (pts[i] - (a + ab * t)).length
        if d > best:
            best, k = d, i
    if best <= tol:
        return [a, b]
    return simplify(pts[:k + 1], tol)[:-1] + simplify(pts[k:], tol)


def rope(m, ln):
    pts = [p.copy() for p in ln["pts"]]
    pts = [p for i, p in enumerate(pts) if i == 0 or (p - pts[i - 1]).length > 1e-5]
    if len(pts) < 2:
        return
    n = {"coil": COIL_N, "wire": WIRE_N}.get(ln["kind"], ROPE_N)
    if ln["kind"] != "coil":
        pts = simplify(pts)
    BS.tube(m, [tuple(p) for p in pts], ln["d"] / 2, ln["slot"], n)


MISMATCH = []
TALLY = {}                          # each placed part's triangles, for the report


def place(m, f):
    """A kit fitting merged into m; its sockets, and any hardware_c22 copy of them that moved, noted."""
    kw = dict(f.kw)
    if f.size is not None:
        kw["size"] = f.size
    first = len(m.bm.faces)
    socks = BR.kit_frame(m, f.kit, tuple(f.o), tuple(f.X), tuple(f.Y), tuple(f.Z), light=f.light, **kw)
    m.bm.faces.ensure_lookup_table()
    TALLY[f.name] = sum(len(fc.verts) - 2 for fc in m.bm.faces[first:])
    if f.local is HC.KIT.get(f.kit + (f.size or "") if f.kit == "HornCleat" else f.kit):
        for k, loc in f.local.items():
            if k in socks:
                d = (HC.V(socks[k]) - f.p(loc)).length
                if d > 0.001:
                    MISMATCH.append(f"{f.name}.{k} {d * 1000:.1f} mm")
            else:
                MISMATCH.append(f"{f.name}.{k} missing")
    return socks


def build_hardware(mats, F):
    m = BK.Mesh("C22_Hardware")
    c, h = HC.bridge()
    BR.plank(m, tuple(c), (1, 0, 0), (0, 1, 0), (0, 0, 1), h.x, h.y, h.z, "Deck")
    rails, rungs = HC.ladder()
    for r in rails:
        BS.tube(m, [tuple(p) for p in r], 0.0110, "Stainless", 12)
    for a, b in rungs:
        BR.rod(m, tuple(a), tuple(b), 0.0125, "Stainless", 12)
        BR.plank(m, tuple((a + b) / 2 + HC.Vector((0.0, 0.0, 0.006))), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.030,
                 (b - a).length / 2 - 0.012, 0.006, "BlackPlastic")
    m.seal()
    socks = {}
    for f in F:
        if f.group == "fittings" and f.kit not in ("BowPulpit", "Pushpit", "Stanchion"):
            socks[f.name] = place(m, f)
    return m.finish(mats), socks


def build_lifelines(mats, F, L):
    m = BK.Mesh("C22_Lifelines")
    for name, ln in sorted(L["all"].items()):
        if name.startswith("Lifeline_"):
            rope(m, ln)
    m.seal()
    socks = {}
    for f in F:
        if f.kit in ("BowPulpit", "Pushpit", "Stanchion"):
            socks[f.name] = place(m, f)
    return m.finish(mats), socks


def build_mast_hardware(mats, F, L):
    m = BK.Mesh("C22_MastHardware")
    for name, ex in sorted(L["all"].items()):
        if name.endswith("Exit"):
            c, h = ex["box"]
            BR.plank(m, tuple(c), (1, 0, 0), (0, 1, 0), (0, 0, 1), abs(h.x), abs(h.y), abs(h.z), ex["slot"])
    m.seal()
    socks = {}
    for f in F:
        if f.group == "mast":
            socks[f.name] = place(m, f)
    return m.finish(mats), socks


def build_halyards(mats, L):
    m = BK.Mesh("C22_Halyards")
    for name, ln in sorted(L["all"].items()):
        if "pts" in ln and not name.startswith("Lifeline_"):
            rope(m, ln)
    return m.finish(mats)


def build_state(mats, state, L):
    """A state's lines and the blocks they run through."""
    m = BK.Mesh("C22_Lines_" + STATE_OB[state])
    blocks = []
    for name, v in sorted(L[state].items()):
        if name.startswith("_"):
            blocks += list(v) if isinstance(v, tuple) else [v]
        elif "pts" in v:
            rope(m, v)
    m.seal()
    socks = {}
    for f in blocks:
        socks[f.name] = place(m, f)
    return m.finish(mats), socks


def sockets(F, L):
    """The hardware's sockets in the game's sockets file shape (centimetres, Y starboard): where the live ropes end."""
    cm = lambda p: [round(c * 100, 2) for c in p]
    s, own = {}, {}
    hull, mast = "SM_Catalina22_Hull", "SM_Catalina22_Mast"
    Fn = HC.by_name(F)

    def put(name, p, owner=hull):
        s[name], own[name] = cm(p), owner
    for sd, t in HC.sides():
        # where the headsails' sheets come onto the drum (from forward: its starboard side, the winches turning
        # clockwise), not the kit's Drum socket, which is on the side a line from aft comes on
        put("JibWinch_" + t, HC.winch_wraps(Fn["Winch_" + t], Fn["GenoaTrack_" + t].s("Sheave"), HC.RP["sheet_d"])[0])
        put("WinchCleat_" + t, Fn["WinchCleat_" + t].s("Wrap"))
        put("JibLead_" + t, Fn["GenoaTrack_" + t].s("Sheave"))                 # the genoa's car (today's name)
        put("WorkingJibLead_" + t, Fn["JibTrack_" + t].s("Sheave"))
        put("JibFairlead_" + t, Fn["JibFairlead_" + t].s("Line"))
        put("JibTurn_" + t, Fn["JibTurnPadeye_" + t].s("Eye"))
        put("QuarterBlock_" + t, Fn["QuarterPadeye_" + t].s("Eye"))
        put("SternCleat_" + t, Fn["SternCleat_" + t].s("Wrap"))
        put("PulpitLifeline_" + t, Fn["BowPulpit"].s("Lifeline" + t))
        put("SternRailLifeline_" + t, Fn["SternRail"].s("Lifeline" + t))
    put("LazySheetVia", HC.Vector((1.45, 0.0, HC.surface(1.45, 0.0) + HC.RP["sheet_d"] / 2)))
    tr = Fn["Traveller"]
    put("Traveler_C", tr.s("Car"))
    for sd, t in HC.sides():
        put("Traveler_" + t, tr.p((sd * (HC.HW["traveller"]["length"] / 2 - 0.06), 0.0, 0.04)))   # (its X is athwartships)
    up, dn = L["rest"]["_mainsheet"]
    put("MainsheetBlock", dn.o)
    put("MainsheetCam", dn.s("CamLead"))
    put("BowCleat", Fn["BowCleat"].s("Wrap"))
    put("BowEye", Fn["BowEye"].o)
    put("ForeguyPadeye", Fn["ForeguyPadeye"].s("Eye"))
    for name in ("MainHalyardCleat", "JibHalyardCleat", "SpinHalyardCleat"):
        put(name, Fn[name].s("Wrap"), mast)
    put("PoleLift", Fn["PoleLiftPadeye"].s("Eye"), mast)
    put("PoleLiftCam", Fn["PoleLiftCam"].s("Line"), mast)
    vu, vd = L["rest"]["_vang"]
    put("VangCam", vd.s("CamLead"), mast)
    return {"sockets": s, "owner": own,
            "note": "Slice 6's hardware sockets (docs/c22-7), Unreal frame, centimetres: where the game's live ropes "
                    "end. JibWinch_* is where the headsails' sheets come onto the drum (its starboard side: the winches turn "
                    "clockwise), JibLead_* the genoa's car's sheave (today's "
                    "name), WorkingJibLead_*, JibFairlead_* and JibTurn_* the working jib's lead over the cabin top, "
                    "Traveler_C the car at the centre and Traveler_S/P its ends' stops, LazySheetVia where the lazy "
                    "sheet crosses forward of the mast, the *Cleat* sockets each cleat's hitch."}


def build_all(mats):
    mats = Mats(mats)
    F = HC.fittings()
    L = HC.lines()
    obs, socks = [], {}
    for fn in (lambda: build_hardware(mats, F), lambda: build_lifelines(mats, F, L),
               lambda: build_mast_hardware(mats, F, L)):
        ob, s = fn()
        obs.append(ob)
        socks.update(s)
    obs.append(build_halyards(mats, L))
    for st in HC.STATES:
        ob, s = build_state(mats, st, L)
        obs.append(ob)
    for ob in obs:
        if ob.name not in SHOWN:
            ob.hide_render = ob.hide_viewport = True
    if MISMATCH:
        raise SystemExit("build_hardware_c22: kit sockets moved from hardware_c22.KIT: " + ", ".join(MISMATCH))
    tris = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob in obs}
    print("C22 hardware triangles: " + ", ".join(f"{k} {v}" for k, v in tris.items()) + f"; {sum(tris.values())} in all")
    return obs, sockets(F, L)
