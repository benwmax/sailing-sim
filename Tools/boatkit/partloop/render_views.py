"""Part detail loop, step 5: render one kit part from the same views every round (docs/part-detail-loop).

Views: six turntable stills in the preview studio (side, edge, three-quarter high, three-quarter low from behind, the
far side, from above), for blocks two "in use" stills (a 10 mm line over the sheave, render-only), one clay still
(every slot a plain grey, so only shape shows) and two outlines (orthographic, transparent film, the alpha written as
black on white) looking square at the side and at the edge. The outlines are
what score.py lays over the reference outline. It also writes stats.json: triangles, size, material slots, the
objects the part was joined from (score.py reads its features from those names) and the sockets.

Run headless:  blender -b --factory-startup -P Tools/boatkit/partloop/render_views.py -- <Part> <out dir> [--samples N]
or with the bpy module:  python3 Tools/boatkit/partloop/render_views.py <Part> <out dir>
Conventions follow bk_parts: the part's origin is its mounting point; blocks hang along -Z with the axle along Y, so
the side views look along Y and the edge views along X.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402

# name -> (direction from the part's centre to the camera, lens mm); the part's own frame
VIEWS = {
    "side":       ((0.0, -1.0, 0.0), 85),
    "edge":       ((1.0, 0.0, 0.0), 85),
    "threeq":     ((1.0, -1.0, 0.7), 85),
    "threeq_low": ((-1.0, 1.0, -0.45), 85),
    "far_side":   ((0.15, 1.0, 0.1), 85),
    "above":      ((0.35, -0.45, 1.0), 85),
}
OUTLINES = {"outline_side": (0.0, -1.0, 0.0), "outline_edge": (1.0, 0.0, 0.0)}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    samples = 32
    if "--samples" in a:
        samples = int(a[a.index("--samples") + 1])
    return a[0], os.path.abspath(a[1]), samples


def bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def reset_studio():
    for o in list(bpy.data.objects):
        if o.type in ("LIGHT", "CAMERA") or o.name.startswith("Floor"):
            bpy.data.objects.remove(o, do_unlink=True)


def studio(ob, w, h, samples, floor=True):
    reset_studio()
    R.SAMPLES = samples
    R._engine(w, h)
    bpy.context.scene.cycles.samples = samples
    lo, hi = bounds(ob)
    c, size = (lo + hi) / 2, max(hi - lo)
    if floor:
        R._floor(lo.z - size * 2.0, size * 80)
    # bk_render.closeup's lights scale with size squared but sit at a distance that scales with size, which burns out a
    # small part; here power follows distance squared (about the catalogue's 26 W per square metre of distance)
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 26, 2.0), ("Rim", (1.5, 1.2, 0.8), 12, 1.5), ("Fill", (1.2, -2.0, -0.3), 5, 3.0)):
        pos = c + Vector(off) * size * 3
        R._light(nm, "AREA", pos, c, k * (pos - c).length_squared, size * spread)
    return c, size


def shoot(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    name, out, samples = args()
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    ob = P.build(name)
    parts = sorted({p.split(".")[0] for p in ob.get("bk_parts", [])})
    me = ob.data
    me.calc_loop_triangles()
    lo, hi = bounds(ob)
    stats = {"part": name, "tris": len(me.loop_triangles), "size_mm": [round((hi[i] - lo[i]) * 1000, 1) for i in range(3)],
             "slots": [m.name if m else "(empty)" for m in me.materials], "objects": parts,
             "sockets": {c.name.split(".")[0][7:]: [round(x * 1000, 1) for x in c.location] for c in ob.children}}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print(f"Loop: {name} {stats['tris']} tris, {stats['size_mm']} mm, {len(stats['slots'])} slots")

    for view, (d, lens) in VIEWS.items():
        c, size = studio(ob, 900, 900, samples)
        R._camera(c + Vector(d).normalized() * size * 2.2 * (lens / 50), c, lens)
        shoot(os.path.join(out, f"{view}.png"))

    # in use: a 10 mm line over the sheave with both tails hanging, as blocks are photographed (render-only dressing,
    # never exported; blocks only: it needs the LineIn and Axle sockets)
    socks = stats["sockets"]
    if "LineIn" in socks and "Axle" in socks:
        R_ = abs(socks["LineIn"][0]) / 1000
        az = socks["Axle"][2] / 1000
        rp, rr = R_ + 0.002, 0.0048
        right, a_end = [(rp, 0, az - 0.09), (rp, 0, az)], 0.0
        if "Cam" in socks:
            # a fiddle with a cam: the tail leaves the sheave where its tangent meets the jaws' entry and runs out
            # through them toward the foot (render-only)
            cx, cz_ = socks["Cam"][0] / 1000, socks["Cam"][2] / 1000
            lead = Vector(socks.get("CamLead", (socks["Cam"][0], 0, socks["Cam"][2] - 10))) / 1000 - Vector((cx, 0, cz_))
            lead.normalize()                               # along the tail through the jaws, away from the sheave
            ex, ez = cx - lead.x * 0.012, cz_ - lead.z * 0.012   # the jaws' entry
            d = math.hypot(ex, ez - az)
            a_end = math.atan2(ez - az, ex) + math.acos(min(1.0, rp / d))
            right = [(cx + lead.x * 0.07, 0, cz_ + lead.z * 0.07), (cx + lead.x * 0.010, 0, cz_ + lead.z * 0.010), (ex, 0, ez)]
        path = right + G.arc_pts((0, 0, az), rp, a_end, math.pi, 24, "xz")[(0 if a_end else 1):-1] + [(-rp, 0, az), (-rp, 0, az - 0.09)]
        ropes = [G.tube("RenderRope", path, rr, None, 16)]
        if "LineIn2" in socks and "Axle2" in socks:
            # a fiddle's small sheave: a second line over it, both legs down between the big sheave's
            r2, a2 = abs(socks["LineIn2"][0]) / 1000 + 0.002, socks["Axle2"][2] / 1000
            ropes.append(G.tube("RenderRope2", [(r2, 0, a2 - 0.06), (r2, 0, a2)] + G.arc_pts((0, 0, a2), r2, 0, math.pi, 20, "xz")[1:-1]
                                + [(-r2, 0, a2), (-r2, 0, a2 - 0.06)], rr, None, 16))
        rope = G.join("RenderRope", ropes) if len(ropes) > 1 else ropes[0]
        rm = bpy.data.materials.new("RenderRopeMat")
        rm.use_nodes = True
        rb_ = rm.node_tree.nodes["Principled BSDF"]
        rb_.inputs["Base Color"].default_value = (0.02, 0.12, 0.25, 1)
        rb_.inputs["Roughness"].default_value = 0.8
        rope.data.materials.append(rm)
        for view, d in (("in_use_side", (0.0, -1.0, 0.0)), ("in_use", (1.0, -1.0, 0.7))):
            c, size = studio(ob, 900, 900, samples)
            R._camera(c + Vector(d).normalized() * size * 2.2 * 1.7, c, 85)
            shoot(os.path.join(out, f"{view}.png"))
        bpy.data.objects.remove(rope, do_unlink=True)

    # clay: every slot one grey
    keep = list(me.materials)
    clay = bpy.data.materials.new("Clay")
    clay.use_nodes = True
    bsdf = clay.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    for i in range(len(me.materials)):
        me.materials[i] = clay
    c, size = studio(ob, 900, 900, samples)
    R._camera(c + Vector((1.0, -1.0, 0.7)).normalized() * size * 2.2 * 1.7, c, 85)
    shoot(os.path.join(out, "clay.png"))
    for i, m in enumerate(keep):
        me.materials[i] = m

    # outlines: orthographic, transparent film, alpha only
    sc = bpy.context.scene
    for view, d in OUTLINES.items():
        c, size = studio(ob, 900, 900, 4, floor=False)
        cam = R._camera(c + Vector(d) * size * 3, c, 50)
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = size * 1.25
        sc.render.film_transparent = True
        sc.cycles.use_denoising = False
        shoot(os.path.join(out, f"{view}_rgba.png"))
        sc.render.film_transparent = False
        sc.cycles.use_denoising = True
        img = bpy.data.images.load(os.path.join(out, f"{view}_rgba.png"))
        px = list(img.pixels)
        w, h = img.size
        a = px[3::4]
        out_img = bpy.data.images.new(view, w, h, alpha=False)
        flat = []
        for v in a:
            g = 0.0 if v > 0.5 else 1.0
            flat += (g, g, g, 1.0)
        out_img.pixels = flat
        out_img.filepath_raw = os.path.join(out, f"{view}.png")
        out_img.file_format = "PNG"
        out_img.save()
        os.remove(os.path.join(out, f"{view}_rgba.png"))
        json.dump({"ortho_scale_mm": size * 1250, "px": w}, open(os.path.join(out, f"{view}.json"), "w"))
    print(f"Loop: {len(VIEWS) + 1 + len(OUTLINES)} views -> {out}")


if __name__ == "__main__":
    main()
