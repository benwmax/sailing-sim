"""Builds the J-Class yacht Bluebonnet in Blender (docs/jclass-1).

Slice 1 is the hull's lines: the hull surface lofted by loft.py (canoe body and keel in one surface), the transom, and
a flat cambered placeholder deck so renders read as a yacht. Plating, the lead keel's casting line and the rudder are
slice 2, the deck and deckhouses slice 3.

    python build_jclass.py <out dir>      (Blender's Python: pip bpy, or blender -b -P build_jclass.py -- <out>)

Writes <out>/jclass.blend, <out>/jclass.obj (the closed shell: hull, transom and deck) and <out>/build.json (triangles,
the hull's dimensions and hydrostatics, the rule check). Units are metres in Unreal's body frame (X forward, Y starboard,
Z up), origin on the centreline at the middle of the load waterline. Edit loft.py and lines_bluebonnet.json, never the
.blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import rule_check  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

NU, NV = 420, 104          # the hull grid: along the length, round the girth (keel to sheer)
DECK_NY = 6                # deck rows across each half
DECK_CAMBER = 0.11         # m of crown at the widest beam (about 4 in, the period's figure for a deck this wide)


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, rgb, rough=0.6):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def mesh_object(name, verts, faces, material=None, smooth=True, weld=1e-6):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(f) for f in faces])
    bm = bmesh.new()
    bm.from_mesh(me)
    if weld:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=weld)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material:
        me.materials.append(material)
    return ob


def hull_mesh(S):
    """Both halves of the surface grid, sharing the centreline row, faces facing outward."""
    nu, nv, _ = S.shape
    stb = S.reshape(-1, 3)
    port = S[:, 1:, :].copy()
    port[..., 1] *= -1
    verts = np.concatenate([stb, port.reshape(-1, 3)])

    def vi(i, j, side):
        if side == 0 or j == 0:
            return i * nv + j
        return nu * nv + i * (nv - 1) + (j - 1)

    faces = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            a, b, c, d = vi(i, j, 0), vi(i + 1, j, 0), vi(i + 1, j + 1, 0), vi(i, j + 1, 0)
            faces.append((a, d, c, b))                   # starboard: outward is +y
            a, b, c, d = vi(i, j, 1), vi(i + 1, j, 1), vi(i + 1, j + 1, 1), vi(i, j + 1, 1)
            faces.append((a, b, c, d))
    return verts, faces


def transom_tilt():
    """dx/dz of the transom's plane (its top leans aft)."""
    (xtb, ztb), (xtt, ztt) = loft.END["transom_bottom"], loft.END["transom_top"]
    return (xtt - xtb) / (ztt - ztb)


def transom_mesh(S):
    """The transom: the surface's aft edge (it lies in the transom's plane), port and starboard, closed at the top by
    the deck's cambered aft edge, so hull, transom and deck meet edge to edge."""
    edge = S[0]                                  # keel (centreline) to sheer, starboard
    stb = [tuple(p) for p in edge]
    port = [(p[0], -p[1], p[2]) for p in edge[1:]]
    top = deck_row(S[0, -1], hd_max(S), transom_tilt())[1:-1]   # port to starboard, without the sheer corners
    ring = list(reversed(stb)) + port + top      # sheer stb -> centreline -> sheer port -> deck edge -> stb
    face = tuple(range(len(ring)))
    # face aft: the plane's normal must point away from the hull (-x)
    a, b, c = (np.array(ring[k]) for k in (0, len(stb) - 1, len(stb) + len(port) - 1))
    if np.cross(b - a, c - a)[0] > 0:
        face = face[::-1]
    return ring, [face]


def hd_max(S):
    """The deck's widest half-breadth: the camber is DECK_CAMBER there and in proportion elsewhere."""
    return float(S[:, -1, 1].max())


def deck_row(p, hdm, tilt=0.0):
    """One row of the placeholder deck across the sheer point p (starboard), port to starboard. The aft row leans with
    the transom (tilt dx/dz) so it stays in the transom's plane."""
    x, hd, zs = p
    crown = DECK_CAMBER * hd / hdm
    n = 2 * DECK_NY + 1
    row = []
    for k in range(n):
        s = -1 + 2 * k / (n - 1)
        z = zs + crown * (1 - s * s)
        row.append((x + tilt * (z - zs), s * hd, z))
    return row


def deck_mesh(S):
    """A flat placeholder deck with camber, from sheer to sheer (slice 3 builds the real one)."""
    sheer = S[:, -1, :]
    hdm = hd_max(S)
    verts, faces = [], []
    n = 2 * DECK_NY + 1
    for i, p in enumerate(sheer):
        verts += deck_row(p, hdm, transom_tilt() if i == 0 else 0.0)
    for i in range(len(sheer) - 1):
        for k in range(n - 1):
            a, b = i * n + k, (i + 1) * n + k
            faces.append((a, b, b + 1, a + 1))
    return verts, faces


def shell_check(obs):
    """Hull, transom and deck together must close: no open or shared-by-three edges, one winding throughout, and the
    enclosed volume positive (normals outward)."""
    bm = bmesh.new()
    for ob in obs:
        tmp = bmesh.new()
        tmp.from_mesh(ob.data)
        tmp.transform(ob.matrix_world)
        me = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bm.edges.ensure_lookup_table()
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonmanifold = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    flipped = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    small = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return {"open_edges": open_edges, "nonmanifold_edges": nonmanifold, "flipped_edges": flipped,
            "degenerate_faces": small, "enclosed_m3": round(vol, 2),
            "closed": open_edges == 0 and nonmanifold == 0 and flipped == 0 and small == 0 and vol > 0}


def tri_count(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def main():
    clear()
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    S = loft.surface(NU, NV)
    hull = mesh_object("Hull", *hull_mesh(S), mat("Hull", (0.18, 0.32, 0.62), 0.45))
    deck = mesh_object("DeckPlaceholder", *deck_mesh(S), mat("Deck", (0.62, 0.5, 0.36), 0.7))
    transom = mesh_object("Transom", *transom_mesh(S), mat("Transom", (0.18, 0.32, 0.62), 0.45), smooth=False, weld=0)
    for ob in (hull, transom, deck):
        ob["slice"] = 1
    shell = shell_check((hull, transom, deck))
    h = loft.hydrostatics(S)
    r = rule_check.check(h)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "jclass.blend"))
    # obj of the closed shell (hull, transom, deck) for the checks
    with open(os.path.join(OUT, "jclass.obj"), "w") as f:
        off = 1
        for ob in (hull, transom, deck):
            f.write(f"o {ob.name}\n")
            me = ob.data
            for v in me.vertices:
                f.write(f"v {v.co.x:.5f} {v.co.y:.5f} {v.co.z:.5f}\n")
            for p in me.polygons:
                f.write("f " + " ".join(str(off + k) for k in p.vertices) + "\n")
            off += len(me.vertices)
    tris = {ob.name: tri_count(ob) for ob in (hull, transom, deck)}
    build = {"slice": 1, "grid": [NU, NV], "triangles": tris, "triangles_total": sum(tris.values()),
             "budget_slice_1": 200000, "shell": shell, "hydrostatics": h, "rule": r}
    with open(os.path.join(OUT, "build.json"), "w") as f:
        json.dump(build, f, indent=1)
    print(json.dumps({"triangles": tris, "shell": shell, "rule": r}, indent=1))
    assert shell["closed"], "the hull, transom and deck do not close into one shell"


main()
