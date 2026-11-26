"""Wildlife Phase 1 (docs/wildlife-1/README.md): the mid-distance birds, one low body per flight style, built in Blender
from code (run headless by scripts/make-birds.sh). 100 to 250 triangles each, wings out level, span 1 m (AWildlifeActor
scales each instance to its bird's wingspan), X forward, Z up, the origin in the body.

Material slot "Bird" (M_BirdMid, scripts/import_birds.py) flaps and folds the wings in its vertex shader and colours them
per instance, from these vertex attributes (Unreal's FBX import flips V, so the material reads 1 - v):
  UV0.u  wing weight: 0 on the body and at the wing root (the shoulder hinge), 0.45 at the wrist, 1 at the tip
  UV0.v  the lift a folded bird stands up by (m in the 1 m bird): a wader's leg length on every vertex, else 0
  UV1    on a leg vertex, the hip (x, z in m): folded, the leg swings down about it
  colour G 1 on a leg vertex, else 0 (binary: the import may sRGB-encode colours)
Shapes from field-guide proportions (body length over span, chord, taper, sweep, tail), by style:
  HeavyGlider pelicans, FlapHang gulls, HoverPlunge terns and gannets, FastLow cormorants and skimmers, Shearing
  shearwaters, Soaring vultures, frigatebirds and raptors, Wading herons and egrets, Insect swallows and swifts, Raft ducks
  and coots. Prints "Birds: <name> <tris>". Usage: blender -b --factory-startup -P build_birds.py -- <out dir>
"""
import math
import os
import sys

import bpy  # (first: the bpy module provides bmesh and mathutils)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

# Blender passes the script's args after "--"; a python with the bpy module passes them straight.
if "--" in sys.argv:
    OUT = sys.argv[sys.argv.index("--") + 1]
elif len(sys.argv) > 1:
    OUT = sys.argv[1]
else:
    OUT = os.path.join(os.getcwd(), "birds")

# Per style, in units of the span (1 m): length (bill tip to tail tip), girth (body radius), neck (head ahead of the
# breast), bill, tail length and width at its end, fork depth, wing root / wrist / tip chords, wrist out along the half
# span, sweep of the hand (m back at the tip), crank (wrist height over the root: the gull's M), dihedral (tip height),
# legs (trailing length, waders), head_up (a heron's pulled-back neck rides high).
STYLES = {
    "HeavyGlider": dict(length=0.60, girth=0.075, neck=0.10, bill=0.13, tail=0.06, tail_w=0.07, fork=0.0,
                        root=0.17, wrist=0.15, tip=0.08, wrist_at=0.45, sweep=0.04, crank=0.01, dihedral=0.0, legs=0.0, head_up=0.05),
    "FlapHang": dict(length=0.42, girth=0.055, neck=0.06, bill=0.04, tail=0.08, tail_w=0.07, fork=0.0,
                     root=0.14, wrist=0.12, tip=0.03, wrist_at=0.42, sweep=0.10, crank=0.03, dihedral=-0.01, legs=0.0, head_up=0.0),
    "HoverPlunge": dict(length=0.42, girth=0.045, neck=0.06, bill=0.05, tail=0.12, tail_w=0.09, fork=0.07,
                        root=0.12, wrist=0.10, tip=0.025, wrist_at=0.42, sweep=0.11, crank=0.025, dihedral=-0.01, legs=0.0, head_up=0.0),
    "FastLow": dict(length=0.68, girth=0.06, neck=0.16, bill=0.06, tail=0.12, tail_w=0.06, fork=0.0,
                    root=0.15, wrist=0.13, tip=0.06, wrist_at=0.45, sweep=0.04, crank=0.0, dihedral=0.0, legs=0.0, head_up=0.0),
    "Shearing": dict(length=0.42, girth=0.05, neck=0.05, bill=0.035, tail=0.07, tail_w=0.06, fork=0.0,
                     root=0.11, wrist=0.09, tip=0.025, wrist_at=0.40, sweep=0.06, crank=0.0, dihedral=-0.015, legs=0.0, head_up=0.0),
    "Soaring": dict(length=0.40, girth=0.06, neck=0.05, bill=0.035, tail=0.10, tail_w=0.12, fork=0.0,
                    root=0.21, wrist=0.20, tip=0.12, wrist_at=0.48, sweep=0.02, crank=0.0, dihedral=0.05, legs=0.0, head_up=0.0),
    "Wading": dict(length=0.55, girth=0.05, neck=0.05, bill=0.10, tail=0.06, tail_w=0.07, fork=0.0,
                   root=0.20, wrist=0.18, tip=0.12, wrist_at=0.46, sweep=0.03, crank=-0.01, dihedral=-0.03, legs=0.30, head_up=0.045),
    "Insect": dict(length=0.46, girth=0.06, neck=0.04, bill=0.015, tail=0.16, tail_w=0.12, fork=0.10,
                   root=0.13, wrist=0.09, tip=0.02, wrist_at=0.35, sweep=0.18, crank=0.0, dihedral=0.0, legs=0.0, head_up=0.0),
    "Raft": dict(length=0.55, girth=0.09, neck=0.10, bill=0.06, tail=0.06, tail_w=0.08, fork=0.0,
                 root=0.15, wrist=0.12, tip=0.05, wrist_at=0.42, sweep=0.06, crank=0.0, dihedral=0.0, legs=0.0, head_up=0.02),
}
RING = 6   # sides of the body's cross-section


class Builder:
    def __init__(self, name, lift):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.uv1 = self.bm.loops.layers.uv.new("Hip")
        self.col = self.bm.loops.layers.color.new("Col")
        self.lift = lift
        self.attrs = {}   # vert -> (wing weight, leg flag, hip x, hip z)

    def vert(self, co, w=0.0, leg=False, hip=(0.0, 0.0)):
        v = self.bm.verts.new(Vector(co))
        self.attrs[v] = (w, leg, hip)
        return v

    def face(self, vs):
        f = self.bm.faces.new(vs)
        return f

    def finish(self):
        bm = self.bm
        # Outward normals on every closed part, then triangles (the attributes go on the triangles' loops).
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.normal_update()
        for f in bm.faces:
            for loop in f.loops:
                w, leg, hip = self.attrs[loop.vert]
                loop[self.uv].uv = (w, self.lift)
                loop[self.uv1].uv = hip
                loop[self.col] = (1.0, 1.0 if leg else 0.0, 0.0, 1.0)
        mesh = bpy.data.meshes.new(self.name)
        tris = len(bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        for p in mesh.polygons:
            p.use_smooth = True
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        mesh.materials.append(bpy.data.materials.get("Bird") or bpy.data.materials.new("Bird"))
        return obj, tris


def tube(b, rings, nose):
    """A closed tube through rings (x, z, half width, half height), fanned shut at the tail end and to a point at nose."""
    loops = []
    for x, z, ry, rz in rings:
        loop = []
        for k in range(RING):
            a = 2.0 * math.pi * (k + 0.5) / RING
            loop.append(b.vert((x, ry * math.cos(a), z + rz * math.sin(a))))
        loops.append(loop)
    for i in range(len(loops) - 1):
        for k in range(RING):
            a, c = loops[i][k], loops[i][(k + 1) % RING]
            d, e = loops[i + 1][(k + 1) % RING], loops[i + 1][k]
            b.face([a, c, d, e])
    tail = b.vert((rings[0][0] - 0.005, 0.0, rings[0][1]))
    for k in range(RING):
        b.face([loops[0][(k + 1) % RING], loops[0][k], tail])
    tip = b.vert(nose)
    for k in range(RING):
        b.face([loops[-1][k], loops[-1][(k + 1) % RING], tip])


def slab(b, top, bottom):
    """A thin closed plate between two outlines of the same points (top and bottom), any number of points."""
    n = len(top)
    vt = [b.vert(p[0], *p[1:]) for p in top]
    vb = [b.vert(p[0], *p[1:]) for p in bottom]
    b.face(vt)
    b.face(list(reversed(vb)))
    for k in range(n):
        b.face([vt[k], vb[k], vb[(k + 1) % n], vt[(k + 1) % n]])


def build(name, s):
    L = s["length"]
    g = s["girth"]
    b = Builder(f"SM_Bird_{name}", s["legs"])
    # Body from the tail's root to the head; the bill to a point. x = 0 at the breast's widest.
    x_tail = -0.5 * L + s["tail"]
    x_head = 0.5 * L - s["bill"]
    neck_x = 0.18 * L
    hz = s["head_up"]
    rings = [
        (x_tail, 0.0, 0.25 * g, 0.2 * g),
        (x_tail + 0.35 * (0.0 - x_tail), 0.0, 0.8 * g, 0.7 * g),
        (0.0, 0.0, g, 0.85 * g),
        (0.6 * neck_x, 0.15 * hz, 0.85 * g, 0.75 * g),
        (neck_x, 0.5 * hz, 0.5 * g, 0.5 * g),
        (max(neck_x + 0.6 * s["neck"], x_head - 0.04 * L), hz, 0.42 * g, 0.45 * g),
        (x_head, hz, 0.38 * g, 0.42 * g),
    ]
    tube(b, rings, (0.5 * L, 0.0, hz - 0.1 * g))
    # Tail: a thin plate behind the body, forked when the style is.
    t0, t1, tw, fork = x_tail + 0.02, -0.5 * L, 0.5 * s["tail_w"], s["fork"]
    th = 0.006
    outline = [(t0, 0.35 * g), (t1, tw), (t1 + fork, 0.0), (t1, -tw), (t0, -0.35 * g)] if fork > 0 else \
        [(t0, 0.35 * g), (t1, tw), (t1, -tw), (t0, -0.35 * g)]
    slab(b, [((x, y, th), 0.0) for x, y in outline], [((x, y, -th), 0.0) for x, y in outline])
    # Wings: root at the body's side (the shoulder hinge), the wrist, the tip; leading edge a quarter chord ahead of the
    # hinge line, swept back through the hand. A thin plate each, thicker at the root.
    x_sh = 0.06 * L
    y_root = 0.75 * g
    for side in (1.0, -1.0):
        st = [
            (y_root, s["root"], 0.0, 0.0, 0.020),
            (0.5 * s["wrist_at"], s["wrist"], 0.15 * s["sweep"], s["crank"], 0.012),
            (0.5, s["tip"], s["sweep"], s["crank"] + s["dihedral"], 0.004),
        ]
        weights = (0.0, 0.45, 1.0)
        le = [((x_sh + 0.25 * c - sw, side * y, z), w) for (y, c, sw, z, t), w in zip(st, weights)]
        te = [((x_sh - 0.75 * c - sw, side * y, z), w) for (y, c, sw, z, t), w in zip(st, weights)]
        # Outline round the wing: leading edge out to the tip, trailing edge back in.
        out = le + list(reversed(te))
        thick = [t for (_, _, _, _, t) in st]
        th_out = thick + list(reversed(thick))
        top = [((p[0], p[1], p[2] + 0.5 * t), w) for (p, w), t in zip(out, th_out)]
        bot = [((p[0], p[1], p[2] - 0.5 * t), w) for (p, w), t in zip(out, th_out)]
        slab(b, top, bot)
    # Legs (waders): trailing past the tail, thin three-sided rods from the hip; folded, the material swings them down.
    if s["legs"] > 0.0:
        hip = (-0.12 * L, -0.6 * g)
        for side in (1.0, -1.0):
            r = 0.006
            ring0, ring1 = [], []
            for k in range(3):
                a = 2.0 * math.pi * k / 3.0
                dy, dz = r * math.cos(a), r * math.sin(a)
                ring0.append(b.vert((hip[0], side * 0.25 * g + dy, hip[1] + dz), 0.0, True, hip))
                ring1.append(b.vert((hip[0] - s["legs"], side * 0.2 * g + dy, hip[1] + dz), 0.0, True, hip))
            for k in range(3):
                b.face([ring0[k], ring0[(k + 1) % 3], ring1[(k + 1) % 3], ring1[k]])
            b.face(list(reversed(ring0)))
            b.face(ring1)
    return b.finish()


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in STYLES.items():
        obj, tris = build(name, spec)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, obj.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", axis_forward="X", axis_up="Z", bake_space_transform=True,
                                 mesh_smooth_type="FACE", colors_type="LINEAR")
        label = obj.name
        bpy.data.objects.remove(obj)
        print(f"Birds: {label} {tris}")


if __name__ == "__main__":
    main()
