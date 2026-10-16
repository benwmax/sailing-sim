"""Owner touches: the small things a particular boat's people leave on it, picked by its character sheet.

A character sheet (Tools/boatkit/characters/<id>.json) names the boat, its seed, how it is used and cared for, and
lists touches. Each touch is a builder here plus where it goes (a socket, a placed kit part's socket, or a boat
position), jittered by the seed so two boats with the same list still differ. Touches are loose gear: they read as
"somebody sails this boat" in a still, and in the game they are static props the crew never collides with.
"""
import math
import random

from mathutils import Matrix, Vector

import bk_geom as G
import bk_materials as BM
import bk_parts as P

TOUCHES = {}


def touch(name, note):
    def deco(fn):
        TOUCHES[name] = (fn, note)
        return fn
    return deco


def M(slot):
    return BM.get(slot)


@touch("CoiledLine", "A dock line flaked in a flat coil, tail tucked")
def coiled_line(rng, radius=0.17, turns=5.0, slot="Rope"):
    pts = []
    n = int(turns * 36)
    for i in range(n + 1):
        a = G.TAU * turns * i / n
        r = radius * (1 - 0.18 * i / n) + rng.uniform(-0.004, 0.004)
        pts.append((r * math.cos(a), r * math.sin(a), 0.006 + 0.0045 * ((i // 36) % 2) + rng.uniform(0, 0.002)))
    pts += [(pts[-1][0] + 0.05 * k, pts[-1][1] + 0.08 * k, 0.012) for k in (1, 2, 3)]
    ob = G.tube("coil", pts, 0.0055, M(slot), 10)
    G.finish(ob)
    return G.join("Touch_CoiledLine", [ob])


@touch("Cooler", "A small hard cooler wedged in the cockpit")
def cooler(rng):
    body = G.prism("body", G.rrect(0.42, 0.28, 0.04), 0, 0.27, M("Deck"), taper=0.97)
    G.finish(body, 0.006)
    lid = G.prism("lid", G.rrect(0.43, 0.29, 0.045), 0.27, 0.31, M("CoolerLid"), taper=0.96)
    G.finish(lid, 0.008)
    handle = G.tube("handle", G.bezier((-0.15, 0, 0.31), (-0.15, 0, 0.36), (0.15, 0, 0.36), (0.15, 0, 0.31), 12), 0.008, M("BlackPlastic"), 12)
    G.finish(handle)
    return G.join("Touch_Cooler", [body, lid, handle])


@touch("WaterBottle", "A refillable bottle lying in a cockpit corner")
def water_bottle(rng):
    b = G.lathe("bottle", [(0, 0), (0.036, 0), (0.037, 0.005), (0.037, 0.20), (0.030, 0.225), (0.016, 0.235), (0.016, 0.26), (0, 0.26)], M("Stainless"), 32)
    G.finish(b, 0)
    cap = G.lathe("cap", [(0, 0.255), (0.020, 0.255), (0.020, 0.285), (0, 0.29)], M("BlackPlastic"), 24)
    G.finish(cap, 0.002)
    ob = G.join("Touch_WaterBottle", [b, cap])
    ob.data.transform(Matrix.Translation((0, 0, 0.037)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    return ob


@touch("FenderPair", "Two fenders left on the side deck after docking")
def fender_pair(rng):
    out = []
    for k in range(2):
        f = P.build("Fender")
        f.data.transform(Matrix.Translation((0.30 * k + rng.uniform(-0.03, 0.03), 0.17 * k, 0.076)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        for c in list(f.children):
            G.bpy.data.objects.remove(c, do_unlink=True)
        out.append(f)
    return G.join("Touch_FenderPair", out)


@touch("WinchHandleStowed", "The winch handle left in its pocket")
def handle_stowed(rng):
    h = P.build("WinchHandle")
    for c in list(h.children):
        G.bpy.data.objects.remove(c, do_unlink=True)
    h.data.transform(Matrix.Rotation(math.radians(180), 4, "Y") @ Matrix.Translation((0, 0, -0.06)))
    return h


@touch("TillerBungee", "Shock cord wrapped round the tiller to hold it amidships at the dock")
def tiller_bungee(rng):
    pts = []
    for i in range(4 * 24 + 1):
        a = G.TAU * i / 24
        pts.append((0.012 * i / 24, 0.024 * math.cos(a), 0.030 * math.sin(a)))
    ob = G.tube("bungee", pts, 0.0035, M("CrewPFD"), 8)
    G.finish(ob)
    return G.join("Touch_TillerBungee", [ob])


def _where(spec, sockets, placed):
    if "part" in spec:
        ob = placed[spec["part"]]
        for c in ob.children:
            if c.name.split(".")[0] == f"SOCKET_{spec['socket']}":
                return ob.matrix_world @ c.location, ob.matrix_world.to_3x3()
        raise KeyError(f"{spec['part']} has no socket {spec['socket']}")
    if "at" in spec:
        return sockets[spec["at"]].copy(), Matrix.Identity(3)
    return Vector(spec["pos"]), Matrix.Identity(3)


def apply(character, sockets, bvh, placed):
    rng = random.Random(character["seed"])
    records = []
    for t in character.get("touches", []):
        fn, _ = TOUCHES[t["touch"]]
        ob = fn(rng, **t.get("opts", {}))
        pos, rot = _where(t, sockets, placed)
        pos = pos + Vector(t.get("offset", (0, 0, 0)))
        if t.get("snap", True) and bvh is not None:
            hit, nrm, _, _ = bvh.ray_cast(pos + Vector((0, 0, 0.5)), Vector((0, 0, -1)), 1.5)
            if hit is not None:
                pos = hit
        yaw = math.radians(t.get("yaw", 0) + rng.uniform(-1, 1) * t.get("yaw_jitter", 20))
        Mx = (rot.to_4x4() if t.get("follow_part", False) else Matrix.Identity(4)) @ Matrix.Rotation(yaw, 4, "Z")
        Mx.translation = pos
        ob.matrix_world = Mx
        records.append({"id": ob.name, "touch": t["touch"], "matrix": [list(r) for r in Mx]})
    return records
