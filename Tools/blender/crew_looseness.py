"""Ultra audit item 7: how free each point of a sailor's polo is to move in the wind (Blender, headless).

    blender -b --factory-startup -noaudio -P Tools/blender/crew_looseness.py -- <in.fbx> <out.fbx>

A shirt's cloth flutters where it hangs free: at the hem below the life jacket and at the sleeves' cuffs. Elsewhere the
knit lies on the body (the jacket and the collar hold it). Each vertex gets a looseness in its colour's red channel: 1 at
the hem's and cuffs' open edges, falling to 0 a hand's width (10 cm) up the cloth from them, measured along the mesh's
edges. The open edges are the polo's boundary loops: the hem is the lowest, the cuffs the furthest out on each side;
the collar and the torso cut under the jacket (build_vest.py's PoloOpen) stay at 0. M_CrewFabric's wind flutter and lag
read it (make_materials.py build_crew_fabric); scripts/import_crew_clothes.py imports the colours.
"""
import heapq
import sys

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, DST = argv[0], argv[1]
REACH = 0.10   # metres up the cloth from an open edge

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    print("Looseness: no mesh in", SRC)
    sys.exit(1)

for ob in meshes:
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    world = ob.matrix_world
    scale = world.to_scale()[0] or 1.0

    # Boundary loops (edges with one face), grouped by connectivity.
    boundary = {e for e in bm.edges if len(e.link_faces) == 1}
    loops, seen = [], set()
    for e in boundary:
        if e in seen:
            continue
        stack, verts = [e], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            verts.update(x.verts)
            for v in x.verts:
                stack.extend(y for y in v.link_edges if y in boundary and y not in seen)
        pts = [world @ v.co for v in verts]
        mean = sum(pts, pts[0] * 0) / len(pts)
        loops.append((verts, mean))
    if len(loops) < 3:
        print(f"Looseness: {ob.name}: only {len(loops)} open edges; left at 0")
        continue
    # The hem: the lowest loop. The cuffs: the two loops furthest out to the sides (the arms are out in the bind pose).
    hem = min(loops, key=lambda l: l[1].z)
    rest = [l for l in loops if l is not hem]
    left = [l for l in rest if l[1].x < 0.0]
    right = [l for l in rest if l[1].x > 0.0]
    if not left or not right:
        print(f"Looseness: {ob.name}: no cuff on one side; left at 0")
        continue
    cuffs = [min(left, key=lambda l: l[1].x), max(right, key=lambda l: l[1].x)]
    free = set(hem[0])
    for c in cuffs:
        free |= c[0]

    # Distance along the edges from the open edges (Dijkstra), in metres.
    dist = {v: 0.0 for v in free}
    heap = [(0.0, v.index) for v in free]
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        v = bm.verts[i]
        if d > dist.get(v, 1e9) or d > REACH:
            continue
        for e in v.link_edges:
            w = e.other_vert(v)
            nd = d + e.calc_length() * scale
            if nd < dist.get(w, 1e9):
                dist[w] = nd
                heapq.heappush(heap, (nd, w.index))

    layer = bm.loops.layers.color.get("Looseness") or bm.loops.layers.color.new("Looseness")
    n_loose = 0
    for f in bm.faces:
        for lp in f.loops:
            d = dist.get(lp.vert, 1e9)
            x = max(0.0, 1.0 - d / REACH) ** 2
            lp[layer] = (x, 0.0, 0.0, 1.0)
    n_loose = sum(1 for v in bm.verts if dist.get(v, 1e9) < REACH)
    bm.to_mesh(me)
    bm.free()
    if me.color_attributes.get("Looseness"):
        me.color_attributes.active_color = me.color_attributes["Looseness"]
    print(f"Looseness: {ob.name}: {len(loops)} open edges, hem at z {hem[1].z:.3f}, cuffs at x {cuffs[0][1].x:.3f} and "
          f"{cuffs[1][1].x:.3f}; {n_loose} of {len(me.vertices)} vertices within {REACH:.2f} m")

# As build_vest.py exports the polo (meshes only, unit scale applied), plus the colours.
for ob in bpy.context.scene.objects:
    ob.select_set(ob.type == "MESH")
bpy.ops.export_scene.fbx(filepath=DST, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, mesh_smooth_type="FACE",
                         colors_type="LINEAR")
