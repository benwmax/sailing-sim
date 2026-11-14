"""Builds the J-Class yacht Bluebonnet in Blender (docs/jclass-1, docs/jclass-2).

Slice 1 lofted the hull's lines (loft.py); slice 2 finishes it (shell.py, finish_bluebonnet.json): the shell split at
its paint lines (bottom, boot top, topsides, gold cove) and the lead casting's top, the plating drawn in the paint from
a UV map, the rudder cut out of the keel with its round nose and bronze stock, and the name and home port in gilt on
the transom. The deck is still slice 1's flat cambered placeholder (the real one is slice 3).

    python build_jclass.py <out dir>      (Blender's Python: pip bpy, or blender -b -P build_jclass.py -- <out>)

Writes <out>/jclass.blend, <out>/jclass.obj (the closed shell: shell, transom and deck; the rudder and stock are their
own closed pieces) and <out>/build.json (triangles, the hull's dimensions and hydrostatics, the rule check, the weights,
the finish's checks, the displacement as built and the rudder's pivot), plus two drawings from drawings_jclass.py
(plating.png, rudder_sections.png; they need matplotlib). Units are metres in the hull's frame (X forward, Y starboard, Z up),
origin on the centreline at the middle of the load waterline. Edit loft.py, shell.py and the json files, never the
.blend. The moulded hull of slice 1 stays in the .blend as `Hull`, hidden from renders: the fairness check measures it.
"""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import rule_check  # noqa: E402
import shell  # noqa: E402
import drawings_jclass  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

NU, NV = 420, 104          # slice 1's hull grid (the hidden reference the fairness check measures)
DECK_NY = 6                # deck rows across each half
DECK_CAMBER = shell.DECK_CAMBER   # the placeholder deck's crown at the widest beam (the stock's top stops under it)
FIN = shell.FIN
SLOTS = ["Topsides", "Bootstripe", "CoveStripe", "Antifouling", "Keel", "Bronze", "Gilt", "Deck"]


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def srgb(c):
    """sRGB 0-255 to linear."""
    out = []
    for v in c:
        v /= 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# ------------------------------------------------------------------------------------------------ materials
def plating_group(lead_top):
    """The plating in the paint: a height (m, negative into the plate) from the 'Plating' UV map (x, girth below the
    sheer; V < 0 where there is no plating): seams every 'width' of girth below the sheer, butts every
    'plate_length' staggered by a third from strake to strake, a row of rivets each side of seams and butts, a row on
    every frame, and the lead casting's top. Each is a soft groove or dimple a fraction of a millimetre deep, so it shows
    only in a raking light; the bump node turns it into shading. Both fade out with the camera's distance."""
    pl = FIN["plating"]
    g = bpy.data.node_groups.new("Plating", "ShaderNodeTree")
    g.interface.new_socket("Height", in_out="OUTPUT", socket_type="NodeSocketFloat")
    N, Lk = g.nodes, g.links
    out = N.new("NodeGroupOutput")
    uvn = N.new("ShaderNodeUVMap")
    uvn.uv_map = "Plating"
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(uvn.outputs[0], sep.inputs[0])
    tc = N.new("ShaderNodeTexCoord")
    sepo = N.new("ShaderNodeSeparateXYZ")
    Lk.new(tc.outputs["Object"], sepo.inputs[0])
    U, D, Zo = sep.outputs[0], sep.outputs[1], sepo.outputs[2]

    def m(op, a, b=None, c=None, clamp=False):
        n = N.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for k, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                Lk.new(v, n.inputs[k])
        return n.outputs[0]

    def near(v, step):
        """|v - step * round(v / step)|: distance to the nearest multiple of step."""
        return m("ABSOLUTE", m("SUBTRACT", v, m("MULTIPLY", m("ROUND", m("DIVIDE", v, step)), step)))

    def bell(d, width):
        """exp(-(d / width)^2)"""
        q = m("DIVIDE", d, width)
        return m("EXPONENT", m("MULTIPLY", m("MULTIPLY", q, q), -1.0))

    w, lp, fs = pl["width"], pl["plate_length"], pl["frame_spacing"]
    ro, rp, fp = pl["rivet_offset"], pl["rivet_pitch"], pl["frame_rivet_pitch"]
    sw, rr = pl["seam_width"], pl["rivet_radius"]
    plated = m("GREATER_THAN", D, -0.5)
    k = m("ROUND", m("DIVIDE", D, w))
    has_seam = m("GREATER_THAN", k, 0.5)                       # no seam at the sheer itself (the deck's edge)
    ds = near(D, w)
    j = m("FLOOR", m("DIVIDE", D, w))                          # the strake
    off = m("MULTIPLY", m("FLOORED_MODULO", j, 3.0), lp / 3.0)
    db = near(m("SUBTRACT", U, off), lp)
    seam = m("MULTIPLY", bell(ds, sw), has_seam)
    butt = bell(db, sw)
    # rivets: dimples on rows `ro` either side of each seam and butt, and on each frame
    rs = m("ABSOLUTE", m("SUBTRACT", ds, ro))
    riv_seam = m("MULTIPLY", m("MULTIPLY", bell(rs, rr), bell(near(U, rp), rr)), has_seam)
    rb = m("ABSOLUTE", m("SUBTRACT", db, ro))
    riv_butt = m("MULTIPLY", bell(rb, rr), bell(near(D, rp), rr))
    riv_frame = m("MULTIPLY", bell(near(U, fs), rr), bell(near(D, fp), rr))
    lead = bell(m("SUBTRACT", Zo, lead_top), sw)
    # fade each out with the camera's distance, where it would be smaller than a pixel
    dist = N.new("ShaderNodeCameraData").outputs["View Distance"]

    def fade(rng):
        near_, far_ = rng
        return m("DIVIDE", m("SUBTRACT", far_, dist), far_ - near_, clamp=True)

    grooves = m("MULTIPLY", m("MULTIPLY", m("ADD", m("ADD", seam, butt), lead), pl["seam_depth"]),
                fade(pl["fade_seams"]))
    dimples = m("MULTIPLY", m("MULTIPLY", m("ADD", m("ADD", riv_seam, riv_butt), riv_frame), pl["rivet_depth"]),
                fade(pl["fade_rivets"]))
    h = m("MULTIPLY", m("MULTIPLY", m("ADD", grooves, dimples), -1.0), plated)
    Lk.new(h, out.inputs[0])
    return g


def make_material(name, rgb, rough, metal=0.0, plating=False, coat=0.0):
    mt = bpy.data.materials.new(name)
    mt.use_nodes = True
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*srgb(rgb), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.08
    if plating:
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = bpy.data.node_groups["Plating"]
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = 1.0
        bump.inputs["Strength"].default_value = 1.0
        nt.links.new(grp.outputs[0], bump.inputs["Height"])
        nt.links.new(bump.outputs[0], b.inputs["Normal"])
        if coat:
            nt.links.new(bump.outputs[0], b.inputs["Coat Normal"])
    return mt


def materials(lead_top):
    plating_group(lead_top)
    c = FIN["paint"]["colours"]
    return {
        "Topsides": make_material("Topsides", c["Topsides"], 0.32, plating=True, coat=0.6),
        "Bootstripe": make_material("Bootstripe", c["Bootstripe"], 0.35, plating=True, coat=0.4),
        "CoveStripe": make_material("CoveStripe", c["CoveStripe"], 0.3, metal=1.0, plating=True),
        "Antifouling": make_material("Antifouling", c["Antifouling"], 0.75, plating=True),
        "Keel": make_material("Keel", c["Keel"], 0.75, plating=True),
        "Bronze": make_material("Bronze", c["Bronze"], 0.38, metal=1.0),
        "Gilt": make_material("Gilt", c["Gilt"], 0.28, metal=1.0),
        "Deck": make_material("Deck", (180, 150, 112), 0.7),
    }


# ------------------------------------------------------------------------------------------------ meshes
def to_blender(p):
    """The hull's frame (X forward, Y starboard, Z up: Unreal's, left-handed) to Blender's right-handed one: y turns
    over, so starboard is Blender's -Y and the model looks the same in both (the FBX import turns it back, as for the
    J/22: Tools/blender/build_j22.py)."""
    p = np.array(p, float)
    p[..., 1] *= -1.0
    return p


def mesh_object(name, verts, faces, mats=None, slots=None, uvs=None, smooth=True, weld=1e-6, frame=None,
                normals=None):
    """A mesh object from geometry in the hull's frame. `slots` names each face's material (from `mats`), `uvs` gives
    each face corner's plating UV, `normals` each face corner's normal; `frame` = (origin, X, Z) puts the object's origin
    there with X and Z its axes (Y = Z x X in Blender, so the frame is a rotation). Mirroring y turns every face over,
    so each face's corners (and their UVs and normals) are taken in the reverse order to keep it facing outward."""
    verts = to_blender(verts)
    faces = [tuple(f)[::-1] for f in faces]
    if uvs is not None:
        uvs = [list(u)[::-1] for u in uvs]
    R = None
    if frame is not None:
        o, X, Z = (to_blender(a) for a in frame)
        R = np.stack([X, np.cross(Z, X), Z], 1)
        verts = (verts - o) @ R
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    if uvs is not None:
        lay = me.uv_layers.new(name="Plating")
        flat = [c for f in uvs for c in f]
        lay.data.foreach_set("uv", [float(a) for c in flat for a in c])
    if weld:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=weld)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if normals is not None:
        n = to_blender(np.array([c for f in normals for c in f[::-1]], float))
        if R is not None:
            n = n @ R
        me.normals_split_custom_set([tuple(v) for v in n])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mats:
        names = []
        for s in (slots or [next(iter(mats))]):
            if s not in names:
                names.append(s)
        for s in names:
            me.materials.append(mats[s])
        if slots:
            idx = {s: k for k, s in enumerate(names)}
            me.polygons.foreach_set("material_index", [idx[s] for s in slots])
    if frame is not None:
        M = Matrix(np.vstack([np.hstack([R, o[:, None]]), [0, 0, 0, 1]]).tolist())
        ob.matrix_world = M
    return ob


def hull_mesh(S):
    """Slice 1's grid: both halves of the surface, sharing the centreline row, faces facing outward."""
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


def transom_mesh(edge, hdm):
    """The transom: the shell's aft edge (it lies in the transom's plane; `edge` keel to sheer, starboard), port and
    starboard, closed at the top by the deck's cambered aft edge, so shell, transom and deck meet edge to edge."""
    stb = [tuple(p) for p in edge]
    port = [(p[0], -p[1], p[2]) for p in edge[1:]]
    top = deck_row(edge[-1], hdm, transom_tilt())[1:-1]   # port to starboard, without the sheer corners
    ring = list(reversed(stb)) + port + top      # sheer stb -> centreline -> sheer port -> deck edge -> stb
    face = tuple(range(len(ring)))
    a, b, c = (np.array(ring[k]) for k in (0, len(stb) - 1, len(stb) + len(port) - 1))
    if np.cross(b - a, c - a)[0] > 0:            # face aft: the plane's normal must point away from the hull (-x)
        face = face[::-1]
    return ring, [face]


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


def deck_mesh(sheer, hdm):
    """A flat placeholder deck with camber, from sheer to sheer (slice 3 builds the real one)."""
    verts, faces = [], []
    n = 2 * DECK_NY + 1
    for i, p in enumerate(sheer):
        verts += deck_row(p, hdm, transom_tilt() if i == 0 else 0.0)
    for i in range(len(sheer) - 1):
        for k in range(n - 1):
            a, b = i * n + k, (i + 1) * n + k
            faces.append((a, b, b + 1, a + 1))
    return verts, faces


def lettering(mats, edge):
    """Name and home port in gilt on the transom: Roman capitals set in the transom's plane, reading from astern,
    each line centred and shrunk if it would come within 12% of the transom's edge at its height. The letters stand
    'relief' proud of the plate and are let 0.5 mm into it, so they sit on it with no gap. Built in Blender's frame
    (starboard is -Y), so they read the right way round there and in the game."""
    L = FIN["lettering"]
    font = bpy.data.fonts.load(os.path.join(HERE, L["font"]))
    (xtb, ztb), (xtt, ztt) = loft.END["transom_bottom"], loft.END["transom_top"]
    up = np.array([xtt - xtb, 0.0, ztt - ztb])
    up /= np.linalg.norm(up)
    right = np.array([0.0, -1.0, 0.0])           # seen from astern, looking forward: to starboard
    out_n = np.cross(right, up)                  # aft and down: out of the transom
    if out_n[0] > 0:
        raise ValueError("the transom's outward normal should point aft")
    seat = 0.0005
    E = np.asarray(edge)

    def glyphs(text, spacing):
        """The text as a mesh at size 1 in the curve's own frame (x along the line, y up, z through it)."""
        cu = bpy.data.curves.new("_text", "FONT")
        cu.body, cu.font, cu.align_x = text, font, "CENTER"
        cu.space_character = spacing
        cu.extrude = 1.0
        cu.resolution_u = 6
        ob = bpy.data.objects.new("_text", cu)
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(ob)
        bpy.data.curves.remove(cu)
        return me

    me_h = glyphs("H", 1.0)
    cap = float(max(v.co.y for v in me_h.vertices))         # the cap height: a flat-topped capital, no overshoot
    bpy.data.meshes.remove(me_h)
    obs, report = [], {}
    for key in ("name", "port"):
        spec = L[key]
        me = glyphs(spec["text"], 1.0 + spec["tracking"])
        co = np.array([tuple(v.co) for v in me.vertices])
        width = float(co[:, 0].max() - co[:, 0].min())
        s = spec["cap_height"] / cap
        # the transom's half-width at the line's middle height (edge is in the hull's frame: starboard +y)
        zc = spec["z"] + 0.5 * spec["cap_height"] * up[2]
        half = float(np.interp(zc, E[:, 2], np.abs(E[:, 1])))
        if s * width > 0.76 * 2 * half:
            s = 0.76 * 2 * half / width
        base = np.array([xtb, 0.0, ztb]) + up * ((spec["z"] - ztb) / up[2])
        z0, z1 = float(co[:, 2].min()), float(co[:, 2].max())
        depth = (co[:, 2] - z0) / (z1 - z0) * (L["relief"] + seat) - seat     # back face into the plate, front proud
        world = base + s * (co[:, :1] * right + co[:, 1:2] * up) + depth[:, None] * out_n
        me.vertices.foreach_set("co", world.ravel().astype(np.float32))
        me.update()
        me.materials.clear()
        me.materials.append(mats["Gilt"])
        mo = bpy.data.objects.new(f"Letters_{key}", me)
        mo.data.name = f"Letters_{key}"
        bpy.context.scene.collection.objects.link(mo)
        obs.append(mo)
        report[key] = {"text": spec["text"], "cap_height_m": round(float(cap * s), 4),
                       "width_m": round(float(width * s), 3), "transom_width_m": round(2 * half, 3),
                       "relief_m": L["relief"], "let_into_plate_m": seat}
    return obs, report


def shell_check(obs):
    """The objects together must close: no open or shared-by-three edges, one winding throughout, and the enclosed
    volume positive (normals outward)."""
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
    where = [[round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2] for e in bm.edges
             if len(e.link_faces) != 2][:6]
    flipped = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
    small = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return {"open_edges": open_edges, "nonmanifold_edges": nonmanifold, "flipped_edges": flipped,
            "degenerate_faces": small, "enclosed_m3": round(vol, 3), "bad_edges_at": where,
            "closed": open_edges == 0 and nonmanifold == 0 and flipped == 0 and small == 0 and vol > 0}


def tri_count(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def write_obj(path, obs):
    """The objects as one .obj in the hull's frame (starboard +y, as loft.py and the game have it)."""
    with open(path, "w") as f:
        off = 1
        for ob in obs:
            f.write(f"o {ob.name}\n")
            M = ob.matrix_world
            for v in ob.data.vertices:
                w = M @ v.co
                f.write(f"v {w.x:.5f} {-w.y:.5f} {w.z:.5f}\n")
            for p in ob.data.polygons:
                f.write("f " + " ".join(str(off + k) for k in reversed(p.vertices)) + "\n")
            off += len(ob.data.vertices)


def helm_sweep(rudder, solids, max_deg=35.0, step=2.5):
    """Turn the rudder hard over each way about its stock, a step at a time, and look for any touch with the hull: a
    triangle of the rudder crossing one of the shell's, transom's or deck's (BVH overlap), and the least clearance from
    the rudder's vertices to the hull at each turn."""
    from mathutils.bvhtree import BVHTree
    V, P = [], []
    for ob in solids:
        M = ob.matrix_world
        off = len(V)
        V += [M @ v.co for v in ob.data.vertices]
        P += [tuple(i + off for i in p.vertices) for p in ob.data.polygons]
    hull = BVHTree.FromPolygons(V, P, epsilon=0.0)
    M0 = rudder.matrix_world.copy()
    loc = [v.co.copy() for v in rudder.data.vertices]
    polys = [tuple(p.vertices) for p in rudder.data.polygons]
    turns = []
    n = int(round(2 * max_deg / step))
    for k in range(n + 1):
        deg = -max_deg + k * step
        M = M0 @ Matrix.Rotation(math.radians(deg), 4, "Z")
        Vr = [M @ c for c in loc]
        touch = len(BVHTree.FromPolygons(Vr, polys, epsilon=0.0).overlap(hull))
        clear = min(hull.find_nearest(v)[3] for v in Vr)
        turns.append({"deg": round(deg, 1), "touching_triangles": touch, "least_clearance_mm": round(clear * 1000, 1)})
    return {"turns_deg": [-max_deg, max_deg], "step_deg": step,
            "touching": sum(t["touching_triangles"] for t in turns),
            "least_clearance_mm": min(t["least_clearance_mm"] for t in turns),
            "least_clearance_at_deg": min(turns, key=lambda t: t["least_clearance_mm"])["deg"],
            "turns": turns}


def main():
    clear()
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    S = loft.surface(NU, NV)
    h = loft.hydrostatics(S)
    r = rule_check.check(h)
    pieces, finish = shell.build()
    mats = materials(finish["lead"]["top_z_m"])
    # slice 1's moulded hull: the fairness check's reference, hidden from renders
    hull = mesh_object("Hull", *hull_mesh(S), {"Topsides": mats["Topsides"]})
    hull.hide_render = True
    hull.hide_set(True)
    sh = pieces["Shell"]
    shell_ob = mesh_object("Shell", sh.V, sh.F, mats, sh.slot, sh.uv, weld=0, normals=sh.corner_normals())
    hdm = float(sh.sheer[:, 1].max())
    tv, tf = transom_mesh(sh.transom_edge, hdm)
    transom = mesh_object("Transom", tv, tf, mats, ["Topsides"], [[(p[0], shell.NO_PLATING) for p in tv]],
                          smooth=False, weld=0)
    dv, df = deck_mesh(sh.sheer, hdm)
    deck = mesh_object("DeckPlaceholder", dv, df, mats, ["Deck"] * len(df))
    frame = shell.rudder_frame()
    rd = pieces["Rudder"]
    rudder = mesh_object("Rudder", rd.V, rd.F, mats, rd.slot, rd.uv, weld=0, frame=frame,
                         normals=rd.corner_normals())
    st = pieces["Stock"]
    stock = mesh_object("RudderStock", st.V, st.F, mats, st.slot, smooth=False, weld=0, frame=frame)
    for p in stock.data.polygons[:-2]:
        p.use_smooth = True
    letters, letter_report = lettering(mats, sh.transom_edge)
    for ob in (hull, transom, deck):
        ob["slice"] = 1
    for ob in [shell_ob, rudder, stock] + letters:
        ob["slice"] = 2
    checks = {"shell_transom_deck": shell_check((shell_ob, transom, deck)), "rudder": shell_check((rudder,)),
              "stock": shell_check((stock,))}
    if not all(c["closed"] for c in checks.values()):
        raise SystemExit(f"a piece does not close into a shell: {checks}")
    sweep = helm_sweep(rudder, (shell_ob, transom, deck))
    if sweep["touching"]:
        raise SystemExit(f"the rudder touches the hull when turned: {[t for t in sweep['turns'] if t['touching_triangles']]}")
    finish["rudder"]["helm_sweep"] = sweep
    w = loft.weight_check(S, h, finish["lead"])
    # as built she displaces the moulded hull plus the plating, less the slot: the lead carries the difference (shell.py
    # measures both and sets the casting's top), so she still floats on her lines (weight = displacement). The rule
    # check keeps the moulded hull's D (the higher rating).
    dsp = finish["displacement"]
    d_mould = h["volume_ft3"] / 35.0
    dsp["moulded_long_tons"] = round(d_mould, 2)
    dsp["as_built_long_tons"] = round(d_mould + dsp["added_long_tons"], 2)
    dsp["rating_if_plating_counted_ft"] = round(r["rating_ft"] * (d_mould / (d_mould + dsp["added_long_tons"])) ** (1 / 3),
                                                2)
    w["displacement_as_built_long_tons"] = dsp["as_built_long_tons"]
    # which way the rudder turns in Blender: a point on its X (toward the trailing edge) turned a little about its Z
    o, X, Z = frame
    M0 = rudder.matrix_world
    te0 = to_blender(np.array(M0 @ Vector((1.0, 0.0, 0.0))))
    te1 = to_blender(np.array(M0 @ Matrix.Rotation(0.1, 4, "Z") @ Vector((1.0, 0.0, 0.0))))
    finish["rudder"]["frame"] = {"origin": [round(float(a), 4) for a in o], "X": [round(float(a), 5) for a in X],
                                 "Z": [round(float(a), 5) for a in Z],
                                 "positive_turn_about_Z_in_blender_moves_trailing_edge":
                                     "starboard (+y): the bow turns to starboard" if te1[1] > te0[1]
                                     else "port (-y): the bow turns to port"}
    p0, up, deck_pt = shell.stock_axis(DECK_CAMBER)
    finish["rudder"]["stock_meets_deck"] = [round(float(a), 3) for a in deck_pt]
    finish["lettering"] = letter_report
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "jclass.blend"))
    write_obj(os.path.join(OUT, "jclass.obj"), (shell_ob, transom, deck))
    visible = [shell_ob, transom, deck, rudder, stock] + letters
    tris = {ob.name: tri_count(ob) for ob in visible}
    build = {"slice": 2, "grid_slice_1": [NU, NV], "triangles": tris, "triangles_total": sum(tris.values()),
             "triangles_hidden_reference_hull": tri_count(hull), "budget_slices_1_2": 200000 + 350000,
             "shell": checks, "hydrostatics": h, "rule": r, "weights": w, "finish": finish}
    with open(os.path.join(OUT, "build.json"), "w") as f:
        json.dump(build, f, indent=1)
    drawings_jclass.draw_all(pieces, FIN, OUT)
    short = {k: v for k, v in finish["rudder"].items() if k != "helm_sweep"}
    short["helm_sweep"] = {k: v for k, v in sweep.items() if k != "turns"}
    print(json.dumps({"triangles": tris, "total": build["triangles_total"], "shell": checks, "rule": r,
                      "weights": w, "lead": finish["lead"], "displacement": dsp, "rudder": short,
                      "lettering": letter_report}, indent=1))


main()
