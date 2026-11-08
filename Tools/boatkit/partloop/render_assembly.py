"""Part detail loop: render an assembly of kit parts in place on the J/22, so a part is judged where it is used, not only
on the turntable (docs/part-detail-loop). One assembly so far: the 4:1 boom vang.

    python3 Tools/boatkit/partloop/render_assembly.py vang <out dir> [--before] [--samples N]
    (or blender -b --factory-startup -P Tools/boatkit/partloop/render_assembly.py -- vang <out dir> ...)

After: the kit's Fiddle40 on the boom's bail and FiddleCam on the mast-base tang, the line reeved 4:1 (the becket to the
top block's small sheave, down round the bottom's small sheave, up round the top's big sheave, down round the bottom's
big sheave and out through the cam), its tail falling to the cabin top. Before (--before): the J/22 hero's vang as built
today (j22_details.vang, its upper blocks swapped for j22_boomgear.big_block, as build_j22_hero does). Both use the same
context (mast foot, boom, cabin top) and the hero's rope and spar materials, so only the hardware differs. The positions
are the hero's: the tang at (MAST_X - 0.06, zm + 0.10), the bail at (MAST_X - 0.80, BOOM_Z - 0.03) (J22H_sockets.json
MastBase and Boom_Vang). Views: side (square to the boat's side), threeq (from aft and above, where the crew stands),
close (the bottom block and its cam), clay (shape only). Writes stats.json (triangles of the hardware).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "Inputs", "j22-hero"))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import render_views as RV  # noqa: E402

# the hero's numbers (build_j22_hero.py, J22H_sockets.json)
MAST_X, BOOM_Z, ZM = 0.65, 1.45, 0.9444
VA = Vector((MAST_X - 0.06, 0, ZM + 0.10))          # mast-base tang (MastBase)
VB = Vector((MAST_X - 0.80, 0, BOOM_Z - 0.03))      # boom bail (Boom_Vang)
ROPE_R = 0.003                                       # 6 mm vang line (the 40 mm fiddle's listed maximum)

VIEWS = {
    "side":   ((0.0, -1.0, 0.05), (0.22, 0, 1.19), 1.25, 50),
    "threeq": ((-1.0, -0.75, 0.55), (0.22, 0, 1.19), 1.35, 50),
    "close":  ((-0.55, -1.0, 0.25), None, 0.30, 85),
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 32
    return a[0], os.path.abspath(a[1]), "--before" in a, samples


def hero_materials(out):
    os.environ.setdefault("J22H_TEX", os.path.join(out, "_tex"))
    import j22_materials as HM
    if os.path.getsize(HM.FONT) < 1024 and os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        HM.FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"   # a checkout without LFS has only the pointer
    from j22_style import TX7295, make_style
    return HM.build_all(make_style(7295, "club", overrides=TX7295))


def frame(head, z_axis, flip=False):
    """A kit part's placement: its origin at `head`, its +Z along z_axis, its axles (Y) athwartships (flip: turned over,
    so its +X side faces the other way)."""
    z = Vector(z_axis).normalized()
    y = Vector((0, -1 if flip else 1, 0))
    x = y.cross(z).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = head
    return m


def bail(MAT, b):
    # the same strap as j22_details.vang's, so before and after hang from the same thing
    return G.tube("Bail", [(b.x - 0.03, -0.03, b.z + 0.02), (b.x - 0.03, -0.03, b.z - 0.01), (b.x, 0, b.z - 0.03),
                           (b.x + 0.03, 0.03, b.z - 0.01), (b.x + 0.03, 0.03, b.z + 0.02)], 0.003, MAT["Stainless"], 10)


def context(MAT):
    objs = []
    deck = G.box("CabinTop", (0.45, 0, ZM - 0.01), (0.9, 0.7, 0.02), MAT.get("CabinGelcoat") or MAT["Aluminium"])
    objs.append(deck)
    # the mast step casting the tang is welded to, and the tang: a stainless plate square to the shackle's pin, from the
    # mast's aft face out past the pin (the same for before and after; neither model had one)
    objs.append(G.box("MastStep", (MAST_X - 0.052, 0, ZM + 0.065), (0.014, 0.050, 0.13), MAT.get("CastAlu") or MAT["Aluminium"]))
    vd = (VB - VA).normalized()
    y = Vector((0, 1, 0))
    xn = y.cross(-vd).normalized()
    tang = G.box("Tang", (0, 0, 0), (0.046, 0.024, 0.004), MAT["Stainless"])
    m = Matrix((-vd, y, xn)).transposed().to_4x4()
    m.translation = VA + (-vd) * 0.010
    tang.matrix_world = m
    G.bake_xform(tang)
    objs.append(tang)
    mast = G.cyl("MastFoot", (MAST_X, 0, ZM), (MAST_X - 0.002, 0, 1.75), 0.049, MAT["Aluminium"], 40)
    mast.scale = (1, 0.068 / 0.098, 1)
    objs.append(mast)
    boom = G.cyl("Boom", (0.60, 0, BOOM_Z), (-0.75, 0, BOOM_Z + 0.017), 0.0375, MAT["Aluminium"], 40)
    boom.scale = (1, 0.055 / 0.075, 1)
    objs.append(boom)
    return objs


def after(MAT):
    vd = (VB - VA).normalized()
    top = P.build("Fiddle40")
    mt = frame(VB - Vector((0, 0, 0.004)), vd)           # hangs from the bail, body toward the bottom block
    bot = P.build("FiddleCam")
    mb = frame(VA + vd * 0.012, -vd, flip=True)           # on the tang, body toward the top block, cam up: the tail leads up and aft
    for ob, m in ((top, mt), (bot, mb)):
        ob.matrix_world = m
    s = {c.name.split(".")[0][7:]: Vector(c.location) for c in bot.children}
    t = {c.name.split(".")[0][7:]: Vector(c.location) for c in top.children}

    def T(x, z):
        return mt @ Vector((x, 0, z))

    def B(x, z):
        return mb @ Vector((x, 0, z))

    rb, rs = 0.0201, 0.0131                  # rope centre: the groove bottom plus the rope's radius
    cz, cz2 = t["Axle"].z, t["Axle2"].z

    def wrap(F, rho, z, n=14, a_end=0.0):
        # over the sheave's far (head) side, from -x round to a_end (0: straight back down the +x side)
        return [F(rho * math.cos(a), z + rho * math.sin(a)) for a in (math.pi - (math.pi - a_end) * i / n for i in range(n + 1))]
    pts = [B(0, s["Becket"].z - 0.001)]
    # the bottom block is turned over (cam up), so both blocks' +x sides are the same side: the top's wraps run +x to -x
    pts += wrap(T, rs, cz2)[::-1]             # top small: in on +x, out on -x
    pts += wrap(B, rs, cz2)                   # bottom small: in on -x, out on +x
    pts += wrap(T, rb, cz)[::-1]              # top big: in on +x, out on -x
    cam = s["Cam"]
    lead = (s.get("CamLead", cam - Vector((0, 0, 0.01))) - cam).normalized()
    ex, ez = cam.x - lead.x * 0.012, cam.z - lead.z * 0.012   # the jaws' entry: the tail leaves the sheave on its tangent
    a_end = math.atan2(ez - cz, ex) + math.acos(min(1.0, rb / math.hypot(ex, ez - cz)))
    pts += wrap(B, rb, cz, a_end=a_end)       # bottom big: out on +x, the cam's side
    pts += [B(ex, ez), B(cam.x + lead.x * 0.010, cam.z + lead.z * 0.010), B(cam.x + lead.x * 0.030, cam.z + lead.z * 0.030)]
    # the tail: out of the cam, down to the cabin top and aft
    p, q = pts[-1], pts[-1] - pts[-2]
    q.normalize()
    a, b, c = p + q * 0.06, Vector((p.x - 0.16, 0.035, ZM + 0.004)), Vector((p.x - 0.40, 0.06, ZM + 0.004))
    pts += [p * (1 - t) ** 2 + a * 2 * t * (1 - t) + b * t * t for t in (i / 12 for i in range(1, 13))]
    pts += [b.lerp(c, t) + Vector((0, 0.012 * math.sin(math.pi * t), 0)) for t in (0.25, 0.5, 0.75, 1.0)]
    rope = G.tube("VangRope", [tuple(q) for q in pts], ROPE_R, MAT["RopeVang"], 12)
    return [top, bot], [rope, bail(MAT, VB)]


def before(MAT):
    import j22_boomgear as BG
    import j22_details as D
    parts = D.vang("Vang", tuple(VA), tuple(VB), MAT, MAT["RopeVang"])
    vd = (VB - VA).normalized()
    for o in [o for o in parts if o.name.startswith("Vang_hi")]:
        parts.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    parts += BG.big_block("VangBlock", VB - vd * 0.075, vd, MAT)
    rope = [o for o in parts if o.name.startswith(("Vang_part", "Vang_tail", "Vang_bail"))]
    hard = [o for o in parts if o not in rope]
    return hard, rope


def tris(objs):
    n = 0
    for o in objs:
        if o.type == "MESH":
            dg = bpy.context.evaluated_depsgraph_get()
            me = o.evaluated_get(dg).to_mesh()
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            o.evaluated_get(dg).to_mesh_clear()
    return n


def studio(c, size, samples):
    RV.reset_studio()
    R.SAMPLES = samples
    R._engine(1200, 900)
    bpy.context.scene.cycles.samples = samples
    R._floor(ZM - 0.03, 20)
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 26, 2.0), ("Rim", (1.5, 1.2, 0.8), 12, 1.5), ("Fill", (1.2, -2.0, -0.3), 5, 3.0)):
        pos = c + Vector(off) * size * 3
        R._light(nm, "AREA", pos, c, k * (pos - c).length_squared, size * spread)


def main():
    which, out, is_before, samples = args()
    assert which == "vang", "only the vang so far"
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    MAT = hero_materials(out)
    ctx = context(MAT)
    hard, rope = before(MAT) if is_before else after(MAT)
    for o in ctx + hard + rope:
        if o.name not in bpy.context.scene.collection.objects and not o.users_collection:
            bpy.context.scene.collection.objects.link(o)
    stats = {"assembly": which, "round": "before" if is_before else "after", "hardware_tris": tris(hard),
             "hardware": sorted({o.name.split(".")[0] for o in hard})}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print(f"Assembly: {which} {stats['round']} {stats['hardware_tris']} hardware tris")
    lo_block = VA + (VB - VA).normalized() * 0.09
    for view, (d, look, dist, lens) in VIEWS.items():
        c = Vector(look) if look else lo_block
        studio(c, dist * 0.5, samples)
        R._camera(c + Vector(d).normalized() * dist * (lens / 50), c, lens)
        RV.shoot(os.path.join(out, f"{view}.png"))
    # clay: everything one grey, the threeq view
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    for o in hard + rope:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = clay
    d, look, dist, lens = VIEWS["threeq"]
    studio(Vector(look), dist * 0.5, samples)
    R._camera(Vector(look) + Vector(d).normalized() * dist, Vector(look), lens)
    RV.shoot(os.path.join(out, "clay.png"))
    print(f"Assembly: views -> {out}")


if __name__ == "__main__":
    main()
