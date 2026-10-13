"""Visual V6: the shore's trees, built in Blender from code (run headless by scripts/make-world-models.sh).

North Texas cross-timbers species, two variants each, as a branch skeleton (tapered, bent tubes) carrying leaf cards:
  live oak     - short thick trunk splitting into a few massive limbs that spread wide and droop; crown wider than tall
  post oak     - crooked limbs, a broad irregular crown about as wide as it is tall
  cedar elm    - an upright vase of finer branches
  red cedar    - a dense, ragged evergreen cone on a central leader
Vertex colours carry the wind response for the material: R = how far the point is out along the tree (sway), G = a
per-card phase (leaf flutter), B = a per-card tint. Leaves use a 2x2 atlas of leaf-spray textures (Tools/blender/
make_leaf_atlas.py). Units are metres (the FBX carries the unit; Unreal imports centimetres). Prints "Trees: <name> <tris>" per tree.
Usage: blender -b --factory-startup -P build_trees.py -- <out dir>
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = sys.argv[sys.argv.index("--") + 1]

SPECIES = {
    #             height  crown w/h  trunk  limbs  limb rise (deg)  levels  leaf size  leaf density  droop  kind
    "LiveOak":   dict(h=(8.0, 11.0), w=1.7, trunk=2.4, limbs=(4, 6), rise=(12, 30), levels=3, leaf=1.5, dens=1.2, droop=0.12, kind="broad", tiles=(0, 1)),
    "PostOak":   dict(h=(10.0, 13.0), w=1.0, trunk=3.5, limbs=(4, 6), rise=(30, 55), levels=3, leaf=1.45, dens=1.2, droop=0.08, kind="broad", tiles=(0, 1)),
    "CedarElm":  dict(h=(12.0, 15.0), w=0.65, trunk=4.0, limbs=(5, 7), rise=(55, 75), levels=3, leaf=1.2, dens=1.1, droop=0.04, kind="broad", tiles=(2,)),
    "RedCedar":  dict(h=(7.0, 10.0), w=0.5, trunk=0.6, limbs=(0, 0), rise=(0, 0), levels=0, leaf=1.15, dens=1.0, droop=0.0, kind="cone", tiles=(3,)),
}


class Builder:
    def __init__(self, name):
        self.bm = bmesh.new()
        self.color = self.bm.loops.layers.color.new("Col")
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.bark_faces, self.leaf_faces = [], []
        self.leaf_centers = []
        self.height = 1.0

    def tube(self, points, radii, sides=6):
        """A tapered tube through the points; UVs wrap the bark around (U) and run along (V)."""
        rings = []
        for i, (p, r) in enumerate(zip(points, radii)):
            d = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
            a = d.orthogonal().normalized()
            b = d.cross(a).normalized()
            ring = [self.bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r) for k in range(sides)]
            rings.append(ring)
        length = 0.0
        for i in range(len(rings) - 1):
            seg = (points[i + 1] - points[i]).length
            for k in range(sides):
                k2 = (k + 1) % sides
                f = self.bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
                for loop, (u, v) in zip(f.loops, ((k / sides, length), ((k + 1) / sides, length), ((k + 1) / sides, length + seg), (k / sides, length + seg))):
                    loop[self.uv].uv = (u, v * 0.5)
                    sway = max(0.0, min(1.0, loop.vert.co.z / self.height)) ** 2
                    loop[self.color] = (sway, 0.0, 0.5, 1.0)
                self.bark_faces.append(f)
            length += seg

    def card(self, center, normal, size, tile, phase, tint, sway):
        """One leaf card: a quad facing roughly along the normal, UVs into one atlas tile."""
        up = Vector((0, 0, 1))
        a = normal.cross(up)
        if a.length < 1e-3:
            a = Vector((1, 0, 0))
        a.normalize()
        b = normal.cross(a).normalized()
        rot = random.uniform(0, 2 * math.pi)
        a, b = a * math.cos(rot) + b * math.sin(rot), b * math.cos(rot) - a * math.sin(rot)
        h = size * 0.5
        vs = [self.bm.verts.new(center + (-a - b) * h), self.bm.verts.new(center + (a - b) * h), self.bm.verts.new(center + (a + b) * h), self.bm.verts.new(center + (-a + b) * h)]
        f = self.bm.faces.new(vs)
        tu, tv = (tile % 2) * 0.5, (tile // 2) * 0.5
        for loop, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[self.uv].uv = (tu + u * 0.5, tv + v * 0.5)
            loop[self.color] = (sway, phase, tint, 1.0)
        self.leaf_faces.append(f)
        self.leaf_centers.append((center.copy(), size))


def bent(start, direction, length, segments, wobble, droop):
    pts = [start.copy()]
    d = direction.normalized()
    p = start.copy()
    for i in range(segments):
        d = (d + Vector((random.uniform(-wobble, wobble), random.uniform(-wobble, wobble), random.uniform(-wobble, wobble) * 0.5 - droop / segments))).normalized()
        p = p + d * (length / segments)
        if p.z < 1.2:  # limbs that sag toward the ground level out above it
            p.z = 1.2 + 0.2 * random.random()
            d.z = max(d.z, 0.05)
        pts.append(p.copy())
    return pts


def grow(b, spec, start, direction, length, radius, level, max_level):
    pts = bent(start, direction, length, 5, 0.25 if level > 0 else 0.08, spec["droop"] * (level + 1) * 0.5)
    radii = [radius * (1.0 - 0.75 * i / (len(pts) - 1)) for i in range(len(pts))]
    if radius > 0.025:
        b.tube(pts, radii, sides=8 if level == 0 else (6 if level == 1 else 4))
    if level >= max_level:
        # Leaf sprays along the outer twigs.
        for i in range(2, len(pts)):
            n = int(6 * spec["dens"] + random.random())
            for _ in range(n):
                c = pts[i] + Vector((random.gauss(0, 0.6), random.gauss(0, 0.6), random.gauss(0, 0.45))) * spec["leaf"]
                out = (c - Vector((0, 0, c.z * 0.6))).normalized() if c.xy.length > 0.1 else Vector((0, 0, 1))
                normal = (out + Vector((random.gauss(0, 0.6), random.gauss(0, 0.6), random.uniform(0.2, 1.0)))).normalized()
                sway = min(1.0, 0.25 + 0.75 * (c.xy.length / (0.5 * spec["w"] * b.height + 1e-3)))
                b.card(c, normal, spec["leaf"] * random.uniform(0.85, 1.35), random.choice(spec["tiles"]), random.random(), random.random(), sway)
        return
    children = random.randint(3, 5) if level > 0 else 0
    for k in range(children):
        t = random.uniform(0.45, 1.0)
        at = pts[min(len(pts) - 1, int(t * (len(pts) - 1)))]
        d = (pts[-1] - pts[0]).normalized()
        side = d.orthogonal().normalized()
        side.rotate(Matrix.Rotation(random.uniform(0, 2 * math.pi), 3, d))
        nd = (d * 0.6 + side * random.uniform(0.5, 0.9) + Vector((0, 0, random.uniform(-0.1, 0.4)))).normalized()
        grow(b, spec, at, nd, length * random.uniform(0.45, 0.7), radius * 0.55, level + 1, max_level)
    # The limb itself carries on.
    grow(b, spec, pts[-1], (pts[-1] - pts[-2]).normalized(), length * 0.6, radii[-1] * 1.1, level + 1, max_level) if level < max_level else None


def broad_tree(name, spec, seed):
    random.seed(seed)
    b = Builder(name)
    h = random.uniform(*spec["h"])
    b.height = h
    trunk_r = 0.18 + h * 0.025
    trunk = bent(Vector((0, 0, -0.3)), Vector((0, 0, 1)), spec["trunk"] + 0.3, 4, 0.06, 0.0)
    b.tube(trunk, [trunk_r * (1.15 - 0.3 * i / (len(trunk) - 1)) for i in range(len(trunk))], sides=10)
    top = trunk[-1]
    n = random.randint(*spec["limbs"])
    reach = 0.5 * spec["w"] * h
    for k in range(n):
        az = 2 * math.pi * (k + random.uniform(-0.3, 0.3)) / n
        rise = math.radians(random.uniform(*spec["rise"]))
        d = Vector((math.cos(az) * math.cos(rise), math.sin(az) * math.cos(rise), math.sin(rise)))
        length = math.hypot(reach, h - spec["trunk"]) * random.uniform(0.55, 0.75)
        grow(b, spec, top + Vector((0, 0, random.uniform(-0.4, 0.4))), d, length, trunk_r * 0.6, 1, spec["levels"])
    return b


def cone_tree(name, spec, seed):
    random.seed(seed)
    b = Builder(name)
    h = random.uniform(*spec["h"])
    b.height = h
    leader = bent(Vector((0, 0, -0.3)), Vector((0, 0, 1)), h, 8, 0.03, 0.0)
    b.tube(leader, [0.2 * (1.0 - 0.9 * i / (len(leader) - 1)) for i in range(len(leader))], sides=8)
    base_r = spec["w"] * h * 0.5
    count = int(1100 * spec["dens"])
    for i in range(count):
        z = random.uniform(0.6, h * 0.98)
        r = base_r * (1.0 - z / h) ** 0.85 * random.uniform(0.35, 1.08) + 0.15
        az = random.uniform(0, 2 * math.pi)
        c = Vector((math.cos(az) * r, math.sin(az) * r, z))
        normal = Vector((math.cos(az), math.sin(az), random.uniform(-0.2, 0.6))).normalized()
        b.card(c, normal, spec["leaf"] * random.uniform(0.7, 1.2) * (0.6 + 0.4 * (1 - z / h)), random.choice(spec["tiles"]), random.random(), random.random(),
               min(1.0, z / h))
    return b


def far_version(b, name, seed):
    """The distant tree: the same trunk and the crown as a dozen lumpy blobs where the leaf cards cluster (opaque, no
    alpha: cheap at a distance yet with the tree's own ragged outline)."""
    random.seed(seed + 1)
    far = Builder(name)
    far.height = b.height
    pts = [c for c, _ in b.leaf_centers]
    k = min(14, max(4, len(pts) // 60))
    centers = random.sample(pts, k)
    for _ in range(6):
        groups = [[] for _ in range(k)]
        for p in pts:
            groups[min(range(k), key=lambda i: (p - centers[i]).length_squared)].append(p)
        centers = [sum(g, Vector()) / len(g) if g else centers[i] for i, g in enumerate(groups)]
    trunk_top = Vector((0, 0, max(1.5, b.height * 0.3)))
    far.tube([Vector((0, 0, -0.3)), trunk_top], [0.25 + b.height * 0.02, 0.18 + b.height * 0.015], sides=6)
    for c, g in zip(centers, groups):
        if not g:
            continue
        ext = Vector((max(abs(p.x - c.x) for p in g), max(abs(p.y - c.y) for p in g), max(abs(p.z - c.z) for p in g)))
        ret = bmesh.ops.create_icosphere(far.bm, subdivisions=2, radius=1.0)
        for v in ret["verts"]:
            n = v.co.normalized()
            bump = 1.0 + 0.18 * math.sin(n.x * 7.1 + seed) * math.sin(n.y * 6.3 + 1.7 * seed) + 0.1 * random.uniform(-1, 1)
            v.co = c + Vector((n.x * ext.x * 0.85, n.y * ext.y * 0.85, n.z * ext.z * 0.75)) * bump
        for f in {f for v in ret["verts"] for f in v.link_faces}:
            for loop in f.loops:
                sway = min(1.0, loop.vert.co.z / far.height) ** 2
                loop[far.color] = (sway, random.random(), random.random(), 1.0)
                loop[far.uv].uv = (loop.vert.co.x * 0.1, loop.vert.co.z * 0.1)
            far.leaf_faces.append(f)
    return far


def finish(b, name, far=False):
    mesh = bpy.data.meshes.new(name)
    bark = bpy.data.materials.new("Bark")
    leaves = bpy.data.materials.new("Crown" if far else "Leaves")
    mesh.materials.append(bark)
    mesh.materials.append(leaves)
    for f in b.bark_faces:
        f.material_index = 0
    for f in b.leaf_faces:
        f.material_index = 1
    b.bm.normal_update()
    b.bm.to_mesh(mesh)
    b.bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    return obj, tris


def export(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="X",
                             axis_up="Z", mesh_smooth_type="FACE", use_mesh_modifiers=True, bake_space_transform=True, add_leaf_bones=False,
                             colors_type="LINEAR")


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in SPECIES.items():
        for variant in range(2):
            seed = sum(ord(ch) for ch in name) * 31 + variant * 7919
            b = cone_tree(name, spec, seed) if spec["kind"] == "cone" else broad_tree(name, spec, seed)
            full = f"SM_{name}_{variant}"
            far = far_version(b, full + "_Far", seed)
            obj, tris = finish(b, full)
            export(obj, os.path.join(OUT, full + ".fbx"))
            print(f"Trees: {full} {tris}")
            bpy.data.objects.remove(obj)
            obj, tris = finish(far, full + "_Far", far=True)
            export(obj, os.path.join(OUT, full + "_Far.fbx"))
            print(f"Trees: {full}_Far {tris}")
            bpy.data.objects.remove(obj)


main()
