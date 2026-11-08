"""Hardware-fit wave 1 (Nov 8 2026): the hero J/22's deck hardware from the shared boat kit (Tools/boatkit) instead of the
hero's own simple copies. Each function stands in for one j22_details / j22_mastgear call at the same spot, so nothing
on the boat moves: cam cleats, pad eyes, the turning blocks on their pad eyes, the backstay's cascade block, the bridle's
bow shackles and the rudder's pintles and gudgeons. Plan: the Claude Doc "Fitting the new hardware to the boats"
(https://claude.ai/artifact/LjJQXzXbXhbt869TrrxuDz).

Kit frames (Tools/boatkit/README.md): origin on the mounting face, +Z out of it, +X along the part, metres. A kit part's
sockets are kept as custom properties sock_<Name> (local metres), as build_j22_hero.kit_part does, so the bake can read
them (bake_j22_hero._kit_sock). `python build_j22_hero.py -- out --old-hardware` builds the boat as before (for the
before/after renders).
"""
import math

import bpy
from mathutils import Matrix, Vector

import bk_parts as KIT

# kit slot names the hero's material table names differently
KIT_MATS = {"Teak": "TeakWeathered", "Wood": "TeakVarnish", "Deck": "Gelcoat", "CabinWindow": "HatchAcrylic",
            "Graphics": "RedPlastic"}


def basis(origin, x_axis, z_axis, scale=1.0):
    """A matrix with local X along x_axis and Z along z_axis (X made square to Z), at origin."""
    z = Vector(z_axis).normalized()
    x = Vector(x_axis)
    x = (x - z * x.dot(z)).normalized()
    y = z.cross(x)
    m = Matrix((x * scale, y * scale, z * scale)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def place(name, part, M4, MAT, size=None, **kw):
    """One kit part, its slots on the hero's materials, its sockets as sock_<Name> properties, at M4."""
    ob = KIT.build(part, size=size, **kw) if size else KIT.build(part, **kw)
    ob.name = ob.data.name = name
    for c in list(ob.children):
        ob[f"sock_{c.name[len('SOCKET_'):].split('.')[0]}"] = list(c.location)
        bpy.data.objects.remove(c, do_unlink=True)
    for slot in ob.material_slots:
        if slot.material:
            base = slot.material.name.split(".")[0]
            slot.material = MAT[KIT_MATS.get(base, base)]
    ob.matrix_world = M4
    return ob


def sock(ob, s):
    """A placed part's socket in world space."""
    return ob.matrix_world @ Vector(ob[f"sock_{s}"])


def cam_cleat(name, at, out_normal, along, MAT):
    """The kit's CamCleat (cam cleat with its fairlead) where j22_details.cam_cleat put the old one: base on `at`, out of
    `out_normal`, its fairlead toward `along` (the kit's lead is its -X end)."""
    return [place(name, "CamCleat", basis(at, -Vector(along), out_normal), MAT)]


def padeye(name, at, normal, MAT, along=None):
    """The kit's round Padeye on a surface, its loop's plane along `along` (the way the line leads; default fore and aft)."""
    n = Vector(normal).normalized()
    a = Vector(along) if along is not None else Vector((1, 0, 0))
    return place(name, "Padeye", basis(at, a, n), MAT)


def standing_block(name, head, up, axle, MAT, sheave_d=0.040):
    """A kit Block40 standing on its head (swivel and shackle at `head`, the body above it along `up`), its sheave's axle
    along `axle`: the J/22's turning blocks on their pad eyes. Under 40 mm the 40 mm block is scaled down (the kit's
    old 29 mm block is the pre-loop builder)."""
    k = sheave_d / 0.040
    z = -Vector(up).normalized()                     # the kit block hangs along its -Z
    ax = Vector(axle).normalized()
    x = ax.cross(z)                                   # local Y is the axle: X = Y x Z
    return place(name, "Block40", basis(head, x, z, k), MAT)


def block_on_padeye(name, deck, normal, axle, MAT, sheave_d=0.040):
    """The pad eye on the deck and the block standing on it, its shackle pin through the eye."""
    lead = Vector(axle).cross(-Vector(normal))        # the line runs through the block square to its axle
    pad = padeye(f"{name}_pad", deck, normal, MAT, along=lead)
    blk = standing_block(name, sock(pad, "Eye"), normal, axle, MAT, sheave_d)
    return [pad, blk]


def hanging_block(name, sheave_at, toward, axle, MAT, sheave_d=0.040):
    """A kit Block40 whose sheave centre is `sheave_at`, its head toward `toward` (j22_details.block's arguments)."""
    k = sheave_d / 0.040
    up = Vector(toward).normalized()
    ax = Vector(axle).normalized()
    head = Vector(sheave_at) + up * 0.0604 * k        # Block40's Axle socket is 60.4 mm below its head
    return [place(name, "Block40", basis(head, ax.cross(up), up, k), MAT)]


def bridle_eye(side, base, toward, MAT):
    """The backstay bridle's end: a pad eye at the transom corner and a bow shackle through it, its bow toward the line.
    The line ties to the shackle's Bow socket (BackstayPlate)."""
    lead = Vector(toward) - Vector(base)
    pad = padeye(f"BS_eye_{side}", base, (0, 0, 1), MAT, along=(lead.x, lead.y, 0))
    eye = sock(pad, "Eye")
    d = (Vector(toward) - eye).normalized()
    # the shackle's pin (its local X) through the loop, square to the loop's plane (the pad eye's local Y); the bow up the line
    pin_dir = pad.matrix_world.to_3x3() @ Vector((0, 1, 0))
    sh = place(f"BS_sh_{side}", "ShackleBow", basis(eye, pin_dir, d), MAT)
    return [pad, sh]


TRANSOM_BOTTOM = 0.176    # the hero hull's transom, its lowest point on the centreline (build_j22_hero.py's hull)


def rudder_fittings(MAT, S):
    """The kit's Pintle on the blade at each of the hero's two pintle heights (rudder part) and two strap Gudgeons on the
    transom either side of it (hull part), as Tools/boatkit/partloop/render_rudder_assembly.py lays them out: the kit's
    +X is aft, the hero's aft is -X."""
    flip = Matrix.Rotation(math.pi, 4, "Z")
    off = S.TRANSOM_X - S.PIVOT_X
    pintles, gudgeons = [], []
    for k, z in enumerate(S.PINTLE_Z):
        # the hero's lower pintle (z 0.05) is below the transom, whose bottom edge is at z 0.176 on the centreline: its
        # gudgeons hung in the water in front of nothing. The J/22's lower gudgeon sits at the transom's bottom edge.
        z = max(z, TRANSOM_BOTTOM + 0.035)
        pintles.append(place(f"Pintle_{k}", "Pintle", Matrix.Translation((S.PIVOT_X, 0, z)) @ flip, MAT,
                             blade=0.036, chord=0.35, length=0.27))
        for lug, dz in ((0, 0.028), (1, -0.028)):
            gudgeons.append(place(f"Gudgeon_{k}_{lug}", "Gudgeon", Matrix.Translation((S.TRANSOM_X, 0, z + dz)) @ flip, MAT,
                                  offset=off))
    return pintles, gudgeons
