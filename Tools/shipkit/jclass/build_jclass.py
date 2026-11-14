"""Builds the J-Class yacht Bluebonnet in Blender (docs/jclass-1, docs/jclass-2, docs/jclass-3).

Slice 1 lofted the hull's lines (loft.py); slice 2 finished it (shell.py, finish_bluebonnet.json): the shell split at
its paint lines (bottom, boot top, topsides, gold cove) and the lead casting's top, the plating drawn in the paint from
a UV map, the rudder cut out of the keel with its round nose and bronze stock, and the name and home port in gilt on
the transom. Slice 3 builds the deck and what stands on it (deck.py, deck_bluebonnet.json): the laid teak deck with the
cockpit let into it, its planking drawn by its material from three UV maps, the toe rail, hatches, skylights,
companionway, doghouse, the wheel box, wheel and binnacle; their weight replaces the size card's estimate, and the
lead takes up the difference so she still floats on her lines. Slice 4 builds the spars (spars.py, rig_bluebonnet.json):
the riveted duralumin mast with its spreaders, jumper struts, track and fittings, the boom on its gooseneck and the
spinnaker pole on its car, the boom and the pole each in its own frame so they swing; their weight replaces the size
card's estimate for the spars as the deck's does, and the rated sail area comes from the spars' measures.

    python build_jclass.py <out dir>      (Blender's Python: pip bpy, or blender -b -P build_jclass.py -- <out>)

Writes <out>/jclass.blend, <out>/jclass.obj (the closed shell: shell, transom and deck; the rudder, stock and each of the
deck's parts are their own closed pieces) and <out>/build.json (triangles, the hull's dimensions and hydrostatics, the
rule check, the weights, the finish's and the deck's checks, the displacement as built, the rudder's, the wheel's,
the boom's and the pole's frames, the rig's measures, sweeps and attachment points), plus the drawings from
drawings_jclass.py (plating.png, rudder_sections.png, deck_plan.png, deck_profile.png, sail_plan.png; they need
matplotlib). Units are metres in the hull's frame (X forward, Y starboard, Z up), origin on the centreline at the middle
of the load waterline. Edit loft.py, shell.py, deck.py, spars.py and the json files, never the .blend. The moulded hull of slice 1
stays in the .blend as `Hull`, hidden from renders: the fairness check measures it.
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
import deck  # noqa: E402
import spars  # noqa: E402
import drawings_jclass  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

NU, NV = 420, 104          # slice 1's hull grid (the hidden reference the fairness check measures)
FIN = shell.FIN
DK = deck.DK
SLOTS = ["Topsides", "Bootstripe", "CoveStripe", "Antifouling", "Keel", "Bronze", "Gilt", "Teak", "Wood", "CabinWindow",
         "Iron", "Spar", "Black"]
DECK_PARTS = ["ToeRail", "Hatches", "Skylights", "Companionway", "Doghouse", "Cockpit", "Steering", "Wheel"]
SPARS = ["Mast", "Boom", "SpinnakerPole"]


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


def spar_plating_group():
    """The spars' plating in their paint, as the hull's: a height (m, negative into the plate) from the 'Spar' UV map
    (u metres along the spar, v the fraction of the way round from its forward face, or the boom's top) and 'SparG'
    (the girth there, and whether it is plated): a lapped seam down each side (v = 1/4 and 3/4), butts every
    'plate_length' along each half, staggered half a plate between the halves, and a row of rivets each side of every
    seam and butt. Each fades out with the camera's distance."""
    pl = spars.RG["plates"]
    g = bpy.data.node_groups.new("SparPlating", "ShaderNodeTree")
    g.interface.new_socket("Height", in_out="OUTPUT", socket_type="NodeSocketFloat")
    N, Lk = g.nodes, g.links
    out = N.new("NodeGroupOutput")

    def uvmap(name):
        u = N.new("ShaderNodeUVMap")
        u.uv_map = name
        sp = N.new("ShaderNodeSeparateXYZ")
        Lk.new(u.outputs[0], sp.inputs[0])
        return sp.outputs[0], sp.outputs[1]

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
        return m("ABSOLUTE", m("SUBTRACT", v, m("MULTIPLY", m("ROUND", m("DIVIDE", v, step)), step)))

    def bell(d, width):
        q = m("DIVIDE", d, width)
        return m("EXPONENT", m("MULTIPLY", m("MULTIPLY", q, q), -1.0))

    U, Vf = uvmap("Spar")
    Gm, on = uvmap("SparG")
    lp, ro, rp = pl["plate_length"], pl["rivet_offset"], pl["rivet_pitch"]
    sw, rr = pl["seam_width"], pl["rivet_radius"]
    plated = m("GREATER_THAN", on, 0.0)
    ds = m("MULTIPLY", near(m("SUBTRACT", Vf, 0.25), 0.5), Gm)            # metres round to the nearer side seam
    half = m("FLOORED_MODULO", m("FLOOR", m("DIVIDE", m("SUBTRACT", Vf, 0.25), 0.5)), 2.0)   # 0 after, 1 forward
    db = near(m("SUBTRACT", U, m("MULTIPLY", half, lp / 2)), lp)
    seam, butt = bell(ds, sw), bell(db, sw)
    riv_seam = m("MULTIPLY", bell(m("ABSOLUTE", m("SUBTRACT", ds, ro)), rr), bell(near(U, rp), rr))
    riv_butt = m("MULTIPLY", bell(m("ABSOLUTE", m("SUBTRACT", db, ro)), rr), bell(near(m("MULTIPLY", Vf, Gm), rp), rr))
    dist = N.new("ShaderNodeCameraData").outputs["View Distance"]

    def fade(rng):
        a, b = rng
        return m("DIVIDE", m("SUBTRACT", b, dist), b - a, clamp=True)

    grooves = m("MULTIPLY", m("MULTIPLY", m("ADD", seam, butt), pl["seam_depth"]), fade(pl["fade_seams"]))
    dimples = m("MULTIPLY", m("MULTIPLY", m("ADD", riv_seam, riv_butt), pl["rivet_depth"]), fade(pl["fade_rivets"]))
    Lk.new(m("MULTIPLY", m("MULTIPLY", m("ADD", grooves, dimples), -1.0), plated), out.inputs[0])
    return g


def planking_group(mitre):
    """The laid deck in the teak's material, from the deck's three UV maps (deck.py): Planking (x, y), Margin (d, y_m),
    Aft (d_aft, s). Outputs the colour, the roughness and a height (m, negative into the seams) for a bump. The
    pattern itself (which piece a point is on, how near a seam) is deck.planking_terms, which the deck drawing runs too.

    Regions: the covering board where |y| is past its nibbed inner edge E (each plank cut along the board's edge y_m
    until it is 'nib' of its width wide, then square across, the board notched to take it), or within 'after_margin'
    of the after edge; the king plank within half its width of the centreline; planks between. Seams: along the
    planks every 'pitch' of |y| from the king plank's edge, the butts (staggered over four planks), the covering board's
    inner edge and the nibs' square ends, the after margin's edge and its mitre with the covering board, the scarfs in
    the king plank and covering boards. Each plank, king plank length and covering board length gets its own slight
    tint, and a fine grain along its length. The seams fade to the deck's average tone with the camera's distance."""
    g = bpy.data.node_groups.new("Planking", "ShaderNodeTree")
    for nm, kind in (("Color", "NodeSocketColor"), ("Roughness", "NodeSocketFloat"), ("Height", "NodeSocketFloat")):
        g.interface.new_socket(nm, in_out="OUTPUT", socket_type=kind)
    N, Lk = g.nodes, g.links
    out = N.new("NodeGroupOutput")

    def uvmap(name):
        u = N.new("ShaderNodeUVMap")
        u.uv_map = name
        sp = N.new("ShaderNodeSeparateXYZ")
        Lk.new(u.outputs[0], sp.inputs[0])
        return sp.outputs[0], sp.outputs[1]

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

    U, Ys = uvmap("Planking")
    D, YM = uvmap("Margin")
    DA, SL = uvmap("Aft")
    pl = deck.PL
    T = deck.planking_terms(m, U, Ys, D, YM, DA, SL, mitre)
    seam, Y, idx, idy = T["seam"], T["Y"], T["idx"], T["idy"]
    sw, w = pl["seam"], pl["pitch"]
    # each piece's own tint, from its id
    cv = N.new("ShaderNodeCombineXYZ")
    Lk.new(idx, cv.inputs[0])
    Lk.new(idy, cv.inputs[1])
    wn = N.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    Lk.new(cv.outputs[0], wn.inputs["Vector"])
    tint = m("ADD", 0.9, m("MULTIPLY", wn.outputs["Value"], 0.2))
    # grain: streaks along each plank
    gv = N.new("ShaderNodeCombineXYZ")
    Lk.new(m("MULTIPLY", U, 1.5), gv.inputs[0])
    Lk.new(m("ADD", m("MULTIPLY", Y, 90.0), m("MULTIPLY", wn.outputs["Value"], 37.0)), gv.inputs[1])
    nz = N.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Roughness"].default_value = 0.6
    Lk.new(gv.outputs[0], nz.inputs["Vector"])
    grain = m("ADD", 0.93, m("MULTIPLY", nz.outputs["Fac"], 0.14))
    # fade the seams with distance into the deck's average tone (seams cover seam / pitch of it)
    dist = N.new("ShaderNodeCameraData").outputs["View Distance"]
    n0, n1 = pl["fade_seams"]
    fade = m("DIVIDE", m("SUBTRACT", n1, dist), n1 - n0, clamp=True)
    c = DK["colours"]
    teak = N.new("ShaderNodeRGB")
    teak.outputs[0].default_value = (*srgb(c["Teak"]), 1)
    caulk = N.new("ShaderNodeRGB")
    caulk.outputs[0].default_value = (*srgb(c["Caulking"]), 1)
    tinted = N.new("ShaderNodeMix")
    tinted.data_type = "RGBA"
    tinted.blend_type = "MULTIPLY"
    tinted.inputs["Factor"].default_value = 1.0
    Lk.new(teak.outputs[0], tinted.inputs[6])
    tv = N.new("ShaderNodeCombineColor")
    tg = m("MULTIPLY", tint, grain)
    for i in range(3):
        Lk.new(tg, tv.inputs[i])
    Lk.new(tv.outputs[0], tinted.inputs[7])
    far = N.new("ShaderNodeMix")
    far.data_type = "RGBA"
    Lk.new(m("MULTIPLY", m("SUBTRACT", 1.0, fade), sw / w), far.inputs["Factor"])
    Lk.new(tinted.outputs[2], far.inputs[6])
    Lk.new(caulk.outputs[0], far.inputs[7])
    col = N.new("ShaderNodeMix")
    col.data_type = "RGBA"
    seen = m("MULTIPLY", seam, fade)
    Lk.new(seen, col.inputs["Factor"])
    Lk.new(far.outputs[2], col.inputs[6])
    Lk.new(caulk.outputs[0], col.inputs[7])
    Lk.new(col.outputs[2], out.inputs["Color"])
    Lk.new(m("ADD", 0.6, m("MULTIPLY", seen, 0.3)), out.inputs["Roughness"])
    Lk.new(m("MULTIPLY", seen, -0.0008), out.inputs["Height"])
    return g


def teak_material(mitre):
    planking_group(mitre)
    mt = bpy.data.materials.new("Teak")
    mt.use_nodes = True
    nt = mt.node_tree
    b = nt.nodes.get("Principled BSDF")
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = bpy.data.node_groups["Planking"]
    nt.links.new(grp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(grp.outputs["Roughness"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    nt.links.new(grp.outputs["Height"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], b.inputs["Normal"])
    return mt


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
        grp.node_tree = bpy.data.node_groups["Plating" if plating is True else plating]
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = 1.0
        bump.inputs["Strength"].default_value = 1.0
        nt.links.new(grp.outputs[0], bump.inputs["Height"])
        nt.links.new(bump.outputs[0], b.inputs["Normal"])
        if coat:
            nt.links.new(bump.outputs[0], b.inputs["Coat Normal"])
    return mt


def materials(lead_top, mitre):
    plating_group(lead_top)
    spar_plating_group()
    c = FIN["paint"]["colours"]
    sc = spars.MAT["colours"]
    return {
        "Topsides": make_material("Topsides", c["Topsides"], 0.32, plating=True, coat=0.6),
        "Bootstripe": make_material("Bootstripe", c["Bootstripe"], 0.35, plating=True, coat=0.4),
        "CoveStripe": make_material("CoveStripe", c["CoveStripe"], 0.3, metal=1.0, plating=True),
        "Antifouling": make_material("Antifouling", c["Antifouling"], 0.75, plating=True),
        "Keel": make_material("Keel", c["Keel"], 0.75, plating=True),
        "Bronze": make_material("Bronze", c["Bronze"], 0.38, metal=1.0),
        "Gilt": make_material("Gilt", c["Gilt"], 0.28, metal=1.0),
        "Teak": teak_material(mitre),
        "Wood": make_material("Wood", DK["colours"]["Wood"], 0.3, coat=1.0),
        "CabinWindow": make_material("CabinWindow", DK["colours"]["CabinWindow"], 0.04, coat=1.0),
        "Iron": make_material("Iron", DK["colours"]["Iron"], 0.45),
        "Spar": make_material("Spar", sc["Spar"], 0.35, plating="SparPlating", coat=0.5),
        "Black": make_material("Black", sc["Black"], 0.45),
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
    if uvs is not None and not isinstance(uvs, dict):
        uvs = {"Plating": uvs}
    if uvs is not None:
        uvs = {k: [list(u)[::-1] for u in v] for k, v in uvs.items()}
    R = None
    if frame is not None:
        o, X, Z = (to_blender(a) for a in frame)
        R = np.stack([X, np.cross(Z, X), Z], 1)
        verts = (verts - o) @ R
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    for name_uv, per_face in (uvs or {}).items():
        lay = me.uv_layers.new(name=name_uv)
        flat = [c for f in per_face for c in f]
        lay.data.foreach_set("uv", [float(a) for c in flat for a in c])
    if weld:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=weld)
        bm.to_mesh(me)
        bm.free()
    if smooth == "angle":
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(35.0))
    elif smooth:
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


def transom_mesh(edge):
    """The transom: the shell's aft edge (it lies in the transom's plane; `edge` keel to sheer, starboard), port and
    starboard, closed at the top by the deck's after edge (deck.aft_row), so shell, transom and deck meet edge to edge."""
    stb = [tuple(p) for p in edge]
    port = [(p[0], -p[1], p[2]) for p in edge[1:]]
    top = [tuple(p) for p in deck.aft_row(edge[-1])[1:-1]]   # port to starboard, without the sheer corners
    ring = list(reversed(stb)) + port + top      # sheer stb -> centreline -> sheer port -> deck edge -> stb
    face = tuple(range(len(ring)))
    a, b, c = (np.array(ring[k]) for k in (0, len(stb) - 1, len(stb) + len(port) - 1))
    if np.cross(b - a, c - a)[0] > 0:            # face aft: the plane's normal must point away from the hull (-x)
        face = face[::-1]
    return ring, [face]


def part_object(p, mats):
    """One of deck.py's parts (or spars.py's) as an object: its slots, its UV maps on every face corner, smooth by angle."""
    uvs = p.corner_uv() if hasattr(p, "corner_uv") else {k: [[v[i] for i in f] for f in p.F] for k, v in p.uv.items()}
    return mesh_object(p.name, p.V, p.F, mats, p.slot, uvs, smooth="angle", weld=0, frame=p.frame)


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


def wheel_sweep(wheel, solids, step=5.0):
    """Turn the wheel about its shaft through one spoke's spacing and look for any touch of its rim or spokes (the
    wood; its bronze hub and shaft run into the box by design) with the deck, the cockpit's coaming or the box, and the
    least clearance from them."""
    from mathutils.bvhtree import BVHTree
    V, P = [], []
    for ob in solids:
        M = ob.matrix_world
        off = len(V)
        V += [M @ v.co for v in ob.data.vertices]
        P += [tuple(i + off for i in p.vertices) for p in ob.data.polygons]
    tree = BVHTree.FromPolygons(V, P, epsilon=0.0)
    wood = wheel.data.materials.find("Wood")
    polys = [tuple(p.vertices) for p in wheel.data.polygons if p.material_index == wood]
    used = sorted({i for p in polys for i in p})
    M0 = wheel.matrix_world.copy()
    loc = [v.co.copy() for v in wheel.data.vertices]
    span = 360.0 / DK["steering"]["wheel"]["spokes"]
    turns = []
    for k in range(int(round(span / step)) + 1):
        deg = k * step
        M = M0 @ Matrix.Rotation(math.radians(deg), 4, "X")
        Vr = [M @ c for c in loc]
        touch = len(BVHTree.FromPolygons(Vr, polys, epsilon=0.0).overlap(tree))
        clear = min(tree.find_nearest(Vr[i])[3] for i in used)
        turns.append({"deg": deg, "touching_triangles": touch, "least_clearance_mm": round(clear * 1000, 1)})
    return {"turns_deg": [0.0, span], "step_deg": step, "touching": sum(t["touching_triangles"] for t in turns),
            "least_clearance_mm": min(t["least_clearance_mm"] for t in turns), "turns": turns}


def cockpit_room(obs, sole_z):
    """How far the cockpit's well stands inside the hull: the least distance from its walls and sole (points every
    0.15 m or less over them) to the shell and transom, and, for the record, from the sole's corners straight down and
    out to each side. The well must not come near the plating."""
    from mathutils.bvhtree import BVHTree
    V, F = [], []
    for ob in obs:
        M = ob.matrix_world
        off = len(V)
        V.extend(M @ v.co for v in ob.data.vertices)
        F.extend(tuple(off + i for i in p.vertices) for p in ob.data.polygons)
    tree = BVHTree.FromPolygons(V, F, epsilon=0.0)
    c = DK["cockpit"]
    H = deck.cockpit_outline(c)
    rim = shell.deck_z(H[:, 0], H[:, 1])
    pts = [np.column_stack([H, rim - (rim - sole_z) * f]) for f in np.linspace(0.0, 1.0, 6)]
    g = 0.1
    gx, gy = np.meshgrid(np.arange(H[:, 0].min(), H[:, 0].max(), g), np.arange(H[:, 1].min(), H[:, 1].max(), g))
    inside = np.column_stack([gx.ravel(), gy.ravel()])
    inside = inside[deck.in_poly(inside, H)]
    pts.append(np.column_stack([inside, np.full(len(inside), sole_z)]))
    pts = np.concatenate(pts)
    least, where = 1e9, None
    for q in pts:
        hit = tree.find_nearest(Vector(tuple(to_blender(q))))
        if hit[3] is not None and hit[3] < least:
            least, where = hit[3], q
    rays = {}
    for x in (c["x_forward"], c["x_aft"]):
        for y in (-c["width"] / 2, c["width"] / 2):
            p = Vector(tuple(to_blender((x, y, sole_z))))
            down = tree.ray_cast(p, Vector((0, 0, -1)))[3]
            side = tree.ray_cast(p, Vector((0, -1 if y > 0 else 1, 0)))[3]  # Blender's -y is starboard
            rays[f"x {x:+.2f} y {y:+.2f}"] = {"down_m": round(down, 3) if down else None,
                                               "out_m": round(side, 3) if side else None}
    return {"points": len(pts), "least_m": round(float(least), 3), "nearest_point": [round(float(a), 3) for a in where],
            "from_sole_corners": rays, "ok": least > 0.2}


def _tree(groups):
    """{name: (object, faces to leave out or None)} to {name: BVH tree of the object's other faces}."""
    from mathutils.bvhtree import BVHTree
    out = {}
    for name, items in groups.items():
        V, F = [], []
        for ob, skip in items:
            M = ob.matrix_world
            off = len(V)
            V.extend(M @ v.co for v in ob.data.vertices)
            F.extend(tuple(off + i for i in p.vertices) for k, p in enumerate(ob.data.polygons)
                     if skip is None or k not in skip)
        out[name] = BVHTree.FromPolygons(V, F, epsilon=0.0)
    return out


def swing_sweep(ob, part, groups, angles, leave_out, end_local):
    """Turn a moving spar about its own Z through `angles` (degrees, Blender's sense) and look, at each, for any
    triangle of it crossing one of each group's (BVH overlap), and the least clearance from its vertices to each group.
    `leave_out` names the spar's pieces that meet a fixed piece by design (a jaw round its pin), left out of the test;
    `end_local` is a point on the spar (its own frame) whose side, starboard or port, labels each turn."""
    from mathutils.bvhtree import BVHTree
    trees = _tree(groups)
    keep = [k for k, lab in enumerate(part.labels) if lab not in leave_out]
    polys = [tuple(ob.data.polygons[k].vertices) for k in keep]
    used = sorted({i for p in polys for i in p})
    M0 = ob.matrix_world.copy()
    loc = [v.co.copy() for v in ob.data.vertices]
    turns = []
    for deg in angles:
        M = M0 @ Matrix.Rotation(math.radians(deg), 4, "Z")
        Vr = [M @ c for c in loc]
        bvh = BVHTree.FromPolygons(Vr, polys, epsilon=0.0)
        end = to_blender(np.array(M @ Vector(end_local)))
        row = {"turn_deg": round(float(deg), 1), "end": [round(float(a), 2) for a in end],
               "side": "starboard" if end[1] > 1e-6 else ("port" if end[1] < -1e-6 else "centreline")}
        for name, tree in trees.items():
            row[f"touching_{name}"] = len(bvh.overlap(tree))
            row[f"clearance_{name}_mm"] = round(min(tree.find_nearest(Vr[i])[3] for i in used) * 1000, 1)
        turns.append(row)
    out = {"turns": turns, "left_out": sorted(leave_out),
           "touching": sum(r[f"touching_{n}"] for r in turns for n in trees)}
    for name in trees:
        r = min(turns, key=lambda t: t[f"clearance_{name}_mm"])
        out[f"least_clearance_{name}_mm"] = r[f"clearance_{name}_mm"]
        out[f"least_clearance_{name}_at_deg"] = r["turn_deg"]
    return out


def mast_heel_room(mast_ob, mast_part, hull_obs):
    """The mast below the deck must stand inside the hull clear of the plating: the least distance from its tube's
    vertices below the deck to the shell and transom, and a ray straight down from its heel must meet the hull."""
    trees = _tree({"hull": [(ob, None) for ob in hull_obs]})
    tree = trees["hull"]
    Vh = np.asarray(mast_part.V)
    below = [i for i, lab in enumerate(mast_part.labels) if lab == "Mast"]
    idx = sorted({v for k in below for v in mast_part.F[k] if Vh[v, 2] < spars.Z_P - 0.1})
    M = mast_ob.matrix_world
    least = min(tree.find_nearest(M @ mast_ob.data.vertices[i].co)[3] for i in idx)
    heel = Vector(tuple(to_blender(spars.at(spars.S_HEEL))))
    down = tree.ray_cast(heel, Vector((0, 0, -1)))[3]
    return {"points": len(idx), "least_m": round(float(least), 3), "heel_down_to_hull_m": round(down, 3) if down else None,
            "ok": least > 0.1 and down is not None}


def frame_report(frame, ob, local, rot_axis, what):
    """The frame of a moving piece and which way a point on it (its own frame) goes for a small positive turn."""
    o, X, Z = frame
    M = ob.matrix_world
    p0 = to_blender(np.array(M @ Vector(local)))
    p1 = to_blender(np.array(M @ Matrix.Rotation(0.1, 4, rot_axis) @ Vector(local)))
    return {"origin": [round(float(a), 4) for a in o], "X": [round(float(a), 5) for a in X],
            "Z": [round(float(a), 5) for a in Z],
            f"positive_turn_about_{rot_axis}_in_blender_moves_{what}":
                "to starboard (+y)" if p1[1] > p0[1] else "to port (-y)"}


def main():
    clear()
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    S = loft.surface(NU, NV)
    h = loft.hydrostatics(S)
    r = rule_check.check(h)
    # the deck's weight first (on the loft's sheer), so the lead can take up the difference from the size card's
    _, deck0 = deck.build()
    w0 = deck0["weights"]
    _, rig0 = spars.build()
    s0 = rig0["weights"]
    extra = (w0["card_long_tons"] - w0["total_long_tons"]) + (s0["card_long_tons"] - s0["total_long_tons"])
    pieces, finish = shell.build(extra_lead_tons=extra)
    sh = pieces["Shell"]
    parts, deck_rep = deck.build(sh.sheer)
    dw = deck_rep["weights"]
    if abs(dw["total_long_tons"] - w0["total_long_tons"]) > 0.01:
        raise SystemExit(f"the deck weighs {dw['total_long_tons']} long tons on the shell's sheer, "
                         f"{w0['total_long_tons']} on the loft's: the lead was set for the wrong weight")
    if not deck_rep["layout"]["ok"]:
        raise SystemExit(f"the deck's layout fails its checks: {deck_rep['layout']}")
    sp_parts, rig = spars.build(sh.sheer)
    sw = rig["weights"]
    if abs(sw["total_long_tons"] - s0["total_long_tons"]) > 0.01:
        raise SystemExit(f"the spars weigh {sw['total_long_tons']} long tons on the shell's sheer, "
                         f"{s0['total_long_tons']} on the loft's: the lead was set for the wrong weight")
    if not sw["meets_1937_minimum"]:
        raise SystemExit(f"the mast with its fittings weighs {sw['mast_with_fittings_lb']} lb, under the 1937 rule's "
                         f"{sw['minimum_1937_lb']}")
    if not all(v for k, v in rig["checks"].items() if isinstance(v, bool)):
        raise SystemExit(f"the rig fails a check: {rig['checks']}")
    r = rule_check.check(h, rig["sail_area_ft2"])
    mats = materials(finish["lead"]["top_z_m"], deck_rep["planking_mitre"])
    # slice 1's moulded hull: the fairness check's reference, hidden from renders
    hull = mesh_object("Hull", *hull_mesh(S), {"Topsides": mats["Topsides"]})
    hull.hide_render = True
    hull.hide_set(True)
    shell_ob = mesh_object("Shell", sh.V, sh.F, mats, sh.slot, sh.uv, weld=0, normals=sh.corner_normals())
    tv, tf = transom_mesh(sh.transom_edge)
    transom = mesh_object("Transom", tv, tf, mats, ["Topsides"], [[(p[0], shell.NO_PLATING) for p in tv]],
                          smooth=False, weld=0)
    deck_ob = part_object(parts["Deck"], mats)
    frame = shell.rudder_frame()
    rd = pieces["Rudder"]
    rudder = mesh_object("Rudder", rd.V, rd.F, mats, rd.slot, rd.uv, weld=0, frame=frame,
                         normals=rd.corner_normals())
    st = pieces["Stock"]
    stock = mesh_object("RudderStock", st.V, st.F, mats, st.slot, smooth=False, weld=0, frame=frame)
    for p in stock.data.polygons[:-2]:
        p.use_smooth = True
    letters, letter_report = lettering(mats, sh.transom_edge)
    deck_obs = {k: part_object(parts[k], mats) for k in DECK_PARTS}
    for ob in (hull,):
        ob["slice"] = 1
    for ob in [shell_ob, transom, rudder, stock] + letters:
        ob["slice"] = 2
    for ob in [deck_ob] + list(deck_obs.values()):
        ob["slice"] = 3
    spar_obs = {k: part_object(sp_parts[k], mats) for k in SPARS}
    for ob in spar_obs.values():
        ob["slice"] = 4
    checks = {"shell_transom_deck": shell_check((shell_ob, transom, deck_ob)), "rudder": shell_check((rudder,)),
              "stock": shell_check((stock,))}
    for k, ob in list(deck_obs.items()) + list(spar_obs.items()):
        checks[k] = shell_check((ob,))
    if not all(c["closed"] for c in checks.values()):
        raise SystemExit(f"a piece does not close into a shell: {[k for k, c in checks.items() if not c['closed']]}"
                         f" {checks}")
    sweep = helm_sweep(rudder, (shell_ob, transom, deck_ob))
    if sweep["touching"]:
        raise SystemExit(f"the rudder touches the hull when turned: {[t for t in sweep['turns'] if t['touching_triangles']]}")
    finish["rudder"]["helm_sweep"] = sweep
    wsweep = wheel_sweep(deck_obs["Wheel"], (deck_ob, deck_obs["Cockpit"], deck_obs["Steering"]))
    if wsweep["touching"]:
        raise SystemExit(f"the wheel touches the deck or the box: {wsweep}")
    deck_rep["wheel_sweep"] = wsweep
    deck_rep["cockpit_room"] = cockpit_room((shell_ob, transom), deck_rep["cockpit_sole_z_m"])
    if not deck_rep["cockpit_room"]["ok"]:
        raise SystemExit(f"the cockpit comes too near the hull: {deck_rep['cockpit_room']}")
    # the spars: the boom swings each way about its pin, the pole sets on either side, clear of the mast (but the pin
    # its jaw takes), the deck and everything on it; the mast's heel stands inside the hull
    mast_parts = sp_parts["Mast"]

    def pins(label):
        return {k for k, lab in enumerate(mast_parts.labels) if lab == label}
    groups = {"deck": [(deck_ob, None), (deck_obs["ToeRail"], None)],
              "on_deck": [(deck_obs[k], None) for k in DECK_PARTS if k != "ToeRail"]}
    bm = spars.RG["boom"]
    b_end = (rig["boom"]["from_mast_after_face_m"] - spars.RG["gooseneck"]["pin_aft"], 0.0, 0.0)
    rig["boom_sweep"] = swing_sweep(spar_obs["Boom"], sp_parts["Boom"],
                                    dict(groups, mast=[(spar_obs["Mast"], pins("Gooseneck pin"))]),
                                    np.arange(-bm["swing_deg"], bm["swing_deg"] + 1e-9, bm["swing_step"]),
                                    {"Boom jaw"}, b_end)
    pl = spars.RG["pole"]
    po, pX, _ = sp_parts["SpinnakerPole"].frame
    xb = to_blender(pX)
    angles, from_bow = [], []
    for side in (1, -1):
        for phi in np.arange(pl["sweep_deg"][0], pl["sweep_deg"][1] + 1e-9, pl["sweep_step"]):
            tb = to_blender(np.array([math.cos(math.radians(phi)), side * math.sin(math.radians(phi)), 0.0]))
            angles.append(math.degrees(math.atan2(tb[1], tb[0]) - math.atan2(xb[1], xb[0])))
            from_bow.append(round(float(phi), 1))
    rig["pole_sweep"] = swing_sweep(spar_obs["SpinnakerPole"], sp_parts["SpinnakerPole"],
                                    dict(groups, mast=[(spar_obs["Mast"], pins("Pole car pin"))]), angles,
                                    {"Pole jaw"}, (pl["length"], 0.0, 0.0))
    for t, phi in zip(rig["pole_sweep"]["turns"], from_bow):
        t["from_bow_deg"] = phi
    for k in ("boom_sweep", "pole_sweep"):
        if rig[k]["touching"]:
            raise SystemExit(f"the {k[:-6]} touches something when swung: "
                             f"{[t for t in rig[k]['turns'] if any(v for a, v in t.items() if a.startswith('touching'))]}")
    rig["mast_heel_room"] = mast_heel_room(spar_obs["Mast"], mast_parts, (shell_ob, transom))
    if not rig["mast_heel_room"]["ok"]:
        raise SystemExit(f"the mast's heel comes too near the hull: {rig['mast_heel_room']}")
    rig["boom_frame"] = frame_report(sp_parts["Boom"].frame, spar_obs["Boom"], (5.0, 0.0, 0.0), "Z", "its_end")
    rig["pole_frame"] = frame_report(sp_parts["SpinnakerPole"].frame, spar_obs["SpinnakerPole"], (5.0, 0.0, 0.0), "Z",
                                     "its_end")
    lt = dw["total_long_tons"]
    w = loft.weight_check(S, h, finish["lead"], measured={"deck_and_deckhouses": (lt, dw["centre"][0], dw["centre"][2]),
                                                          "spars": (sw["total_long_tons"], sw["centre"][0],
                                                                    sw["centre"][2])})
    # as built she displaces the moulded hull plus the plating, less the slot; the lead carries that and what the deck
    # and the spars weigh less than the card's estimate (shell.py measures both: the casting's top is fixed at slice 3's,
    # and trimming ballast in the bilge takes the rest), so she still floats on her lines (weight = displacement). The
    # rule check keeps the moulded hull's D (the higher rating).
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
    p0, up, deck_pt = shell.stock_axis()
    finish["rudder"]["stock_meets_deck"] = [round(float(a), 3) for a in deck_pt]
    finish["lettering"] = letter_report
    # the wheel's frame: which way its top goes for a positive turn about its X (forward along the shaft) in Blender;
    # the top to starboard is clockwise as the helmsman sees it, the bow to starboard
    wo, wX, wZ = parts["Wheel"].frame
    Mw = deck_obs["Wheel"].matrix_world
    t0 = to_blender(np.array(Mw @ Vector((0.0, 0.0, 0.7))))
    t1 = to_blender(np.array(Mw @ Matrix.Rotation(0.1, 4, "X") @ Vector((0.0, 0.0, 0.7))))
    deck_rep["wheel_frame"] = {"origin": [round(float(a), 4) for a in wo], "X": [round(float(a), 5) for a in wX],
                               "Z": [round(float(a), 5) for a in wZ],
                               "positive_turn_about_X_in_blender_moves_its_top":
                                   "to starboard (+y): clockwise as the helmsman sees it, the bow to starboard"
                                   if t1[1] > t0[1] else "to port (-y): anticlockwise as the helmsman sees it"}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "jclass.blend"))
    write_obj(os.path.join(OUT, "jclass.obj"), (shell_ob, transom, deck_ob))
    visible = [shell_ob, transom, deck_ob, rudder, stock] + letters + list(deck_obs.values()) + list(spar_obs.values())
    tris = {ob.name: tri_count(ob) for ob in visible}
    slice3 = sum(tris[ob.name] for ob in [deck_ob] + list(deck_obs.values()))
    slice4 = sum(tris[ob.name] for ob in spar_obs.values())
    build = {"slice": 4, "grid_slice_1": [NU, NV], "triangles": tris, "triangles_total": sum(tris.values()),
             "triangles_slice_3": slice3, "budget_slice_3": 500000, "triangles_slice_4": slice4,
             "budget_slice_4": 250000, "triangles_hidden_reference_hull": tri_count(hull),
             "budget_slices_1_4": 200000 + 350000 + 500000 + 250000, "sail_area_ft2": rig["sail_area_ft2"],
             "shell": checks, "hydrostatics": h, "rule": r, "weights": w, "finish": finish, "deck": deck_rep,
             "rig": rig}
    if slice3 > build["budget_slice_3"] or slice4 > build["budget_slice_4"]:
        raise SystemExit(f"slices 3 and 4 have {slice3} and {slice4} triangles, over a budget")
    with open(os.path.join(OUT, "build.json"), "w") as f:
        json.dump(build, f, indent=1)
    drawings_jclass.draw_all(pieces, FIN, OUT, parts=parts, deck_rep=deck_rep, rig=(sp_parts, rig))
    short = {k: v for k, v in finish["rudder"].items() if k != "helm_sweep"}
    short["helm_sweep"] = {k: v for k, v in sweep.items() if k != "turns"}
    print(json.dumps({"triangles": tris, "total": build["triangles_total"], "slice_3": slice3, "slice_4": slice4,
                      "sail_area_ft2": rig["sail_area_ft2"], "measures": rig["measures"],
                      "spars_weight": {k: sw[k] for k in ("spars", "mast_with_fittings_lb", "total_long_tons", "centre")},
                      "boom_sweep": {k: v for k, v in rig["boom_sweep"].items() if k != "turns"},
                      "pole_sweep": {k: v for k, v in rig["pole_sweep"].items() if k != "turns"},
                      "mast_heel_room": rig["mast_heel_room"], "boom_frame": rig["boom_frame"],
                      "pole_frame": rig["pole_frame"],
                      "shell": {k: c["closed"] for k, c in checks.items()}, "rule": r["rating_ft"],
                      "weights": w, "lead": finish["lead"], "deck_weight": {k: dw[k] for k in ("total_kg", "total_long_tons",
                                                                                            "centre")},
                      "layout_ok": deck_rep["layout"]["ok"],
                      "wheel": {k: v for k, v in wsweep.items() if k != "turns"}, "cockpit": deck_rep["cockpit_room"],
                      "rudder": short["helm_sweep"]}, indent=1))


main()
