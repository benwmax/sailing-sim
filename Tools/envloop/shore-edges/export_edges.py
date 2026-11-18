"""Shore Track C: the kit shore edges as game pieces (docs/envloop/shore-edges/, "After Nov 21").

Builds each edge type of a region pack with edge_kit.py as 4 m stretches of shore (x along the shore, +y toward the land,
z = 0 the pool), three seeds a type, without the stand-in ground (edge_kit.GROUND_PARTS: in the game the terrain is the
ground), and writes them as FBX for scripts/import_shore_edges.py: SM_Edge_<Type>_<n>.fbx (the piece) and
SM_Edge_<Type>_<n>_Light.fbx (decimated to about an eighth, for 150-600 m). Vertex colour R says which surface a vertex
is (M_ShoreEdge reads it), G its shade, B a run-off source; UV0 is metres along and up (or across).

    python3 Tools/envloop/shore-edges/export_edges.py --out Artifacts/models/edges [--pack north-texas-lake] [--types bulkhead,timber]

Needs the bpy module (pip install bpy==5.1.2) or runs inside Blender (blender -b -P export_edges.py -- --out DIR).
Riprap is the rock loop's (SM_Rock_*); sheet pile and the ramp wait for the marina and slipway placement (not in this round).
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import bpy  # noqa: E402
import edge_kit as K  # noqa: E402

PIECE_M = 4.0        # ALakeTerrainActor::PlaceShoreEdges stretches each piece to its segment (about 2 m on a lot's waterline)
VARIANTS = 3         # seeds a type (PlaceShoreEdges loads _0 .. _2)
TYPES = ("bulkhead", "limestone", "timber", "claycut", "gravel", "mudflat", "reedcove")
LIGHT_RATIO = 0.125


def piece_mesh(m):
    """The kit mesh without its ground parts: vertices, faces, colours, smooth flags."""
    V, F, C, S = m.arrays()
    keep = np.ones(len(F), bool)
    # Parts are recorded by triangle count in add() order: rebuild which triangles belong to a ground part.
    start = 0
    for Vp, Fp, part in zip(m.V, m.F, m.part_of):
        n = len(Fp)
        if part in K.GROUND_PARTS:
            keep[start:start + n] = False
        start += n
    F, S = F[keep], S[keep]
    used = np.unique(F)
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[F], C[used], S


def to_object(V, F, C, S, name):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.polygons.foreach_set("use_smooth", S.tolist())
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.concatenate([C, np.ones((len(C), 1))], 1).astype(np.float32).ravel())
    # Metre UVs by the triangle's main axis: walls (x, z), ground (x, y), side faces (y, z); as render_edges.to_blender.
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    ax = np.argmax(np.abs(n), 1)
    uv = np.where((ax == 2)[:, None, None], P[..., [0, 1]], np.where((ax == 1)[:, None, None], P[..., [0, 2]], P[..., [1, 2]]))
    lay = me.uv_layers.new(name="UVMap")
    lay.data.foreach_set("uv", uv.astype(np.float32).ravel())
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def export(o, path):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="X", axis_up="Z", bake_space_transform=True, mesh_smooth_type="FACE", colors_type="LINEAR")


def decimate(o, ratio):
    mod = o.modifiers.new("light", "DECIMATE")
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=mod.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pack", default=K.DEFAULT_PACK)
    ap.add_argument("--types", default=",".join(TYPES))
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pack = K.load_pack(a.pack)
    for kind in a.types.split(","):
        if kind not in pack["types"]:
            print(f"Edges: {kind} is not in pack {a.pack}, skipped")
            continue
        cap = kind[0].upper() + kind[1:]
        for n in range(VARIANTS):
            m, _ = K.build(kind, length=PIECE_M, seed=101 + 17 * n, pack=pack)
            V, F, C, S = piece_mesh(m)
            name = f"SM_Edge_{cap}_{n}"
            o = to_object(V, F, C, S, name)
            export(o, os.path.join(a.out, name + ".fbx"))
            full = len(F)
            decimate(o, LIGHT_RATIO)
            export(o, os.path.join(a.out, name + "_Light.fbx"))
            print(f"Edges: {name} {full} tris, light {len(o.data.polygons)} faces")
            bpy.data.objects.remove(o)


if __name__ == "__main__":
    main()
