"""Part detail loop: views for a long, thin part (a tiller, a tiller extension), where render_views.py's square stills
frame the whole length and the part shrinks to a line (docs/part-detail-loop/tiller.md).

Writes, beside render_views.py's views in the same round folder:
  long_side.png, long_threeq.png      the whole part, 1800 x 600, framed to its length
  <end>_side.png, <end>_threeq.png,   each end close up (the aft end, X max: a tiller's rudder end or an extension's joint;
  <end>_above.png, <end>_under.png    the forward end, X min: a tiller's hand end), lit for the close-up's size
  with_ext_threeq.png, with_ext_side.png   tillers only: the kit's TillerExtension on the ExtPivot socket, render-only, as
                                       it lies along the tiller when stowed

    python3 Tools/boatkit/partloop/render_long.py <Part> <round dir> [--samples N] [--ext-length 0.914] [key=value ...]

key=value are the builder's options (as render_kw.py). Run with the bpy module, or blender -b -P ... -- like render_views.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import render_views as RV  # noqa: E402  (first: it imports bpy)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402


EXPOSE = 0.4     # render_views.py's studio burns out a long pale part (varnished ash) framed this wide; its lights at 40%


def light(c, size, floor_z=None):
    RV.reset_studio()
    if floor_z is not None:
        R._floor(floor_z, size * 200)
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 26, 2.0), ("Rim", (1.5, 1.2, 0.8), 12, 1.5), ("Fill", (1.2, -2.0, -0.3), 5, 3.0)):
        pos = c + Vector(off) * size * 3
        R._light(nm, "AREA", pos, c, EXPOSE * k * (pos - c).length_squared, size * spread)


def shoot(path, c, d, dist, lens, w, h, size, floor_z):
    R._engine(w, h)
    for n in bpy.context.scene.world.node_tree.nodes:      # the sky too: it, not the lamps, washes a pale part out
        if n.type == "BACKGROUND":
            n.inputs["Strength"].default_value *= EXPOSE
    light(c, size, floor_z)
    R._camera(c + Vector(d).normalized() * dist, c, lens)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def region(ob, x0, x1):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices if x0 <= (ob.matrix_world @ v.co).x <= x1]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2, max(hi - lo)


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    kw, rest = {}, []
    for x in a:
        if "=" in x:
            k, v = x.split("=", 1)
            try:
                kw[k] = float(v)
            except ValueError:
                kw[k] = {"True": True, "False": False}.get(v, v)
        else:
            rest.append(x)
    name, out = rest[0], os.path.abspath(rest[1])
    samples = int(rest[rest.index("--samples") + 1]) if "--samples" in rest else 32
    ext_len = float(rest[rest.index("--ext-length") + 1]) if "--ext-length" in rest else 1.0
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    R.SAMPLES = samples
    ob = P.build(name, **kw)
    lo, hi = RV.bounds(ob)
    L = hi.x - lo.x
    floor_z = lo.z - 0.25
    c = (lo + hi) / 2
    for view, d in (("long_side", (0, -1, 0.0)), ("long_threeq", (0.55, -1, 0.75))):
        shoot(os.path.join(out, f"{view}.png"), c, d, L * 3.2, 105, 1800, 600, L * 0.5, floor_z)
    ends = {"aft": (hi.x - 0.26, hi.x + 0.01), "fwd": (lo.x - 0.01, lo.x + 0.26)}
    for end, (x0, x1) in ends.items():
        rc, rs = region(ob, x0, x1)
        rs = max(rs, 0.12)
        for view, d in (("side", (0, -1, 0.05)), ("threeq", (1, -1, 0.7) if end == "aft" else (-1, -1, 0.7)),
                        ("above", (0.2, -0.35, 1.0)), ("under", (0.4, 1.0, -0.6))):
            shoot(os.path.join(out, f"{end}_{view}.png"), rc, d, rs * 2.6, 85, 900, 900, rs, rc.z - rs * 1.5)
    socks = {ch.name.split(".")[0][7:]: Vector(ch.location) for ch in ob.children}
    if "ExtPivot" in socks:
        ext = P.build("TillerExtension", length=ext_len)
        # the extension's joint on the pivot, its tube lying aft along the tiller's top (its +X to the tiller's +X)
        ext.matrix_world = Matrix.Translation(socks["ExtPivot"]) @ ext.matrix_world
        lo2, hi2 = RV.bounds(ext)
        lo3 = Vector([min(lo[i], lo2[i]) for i in range(3)])
        hi3 = Vector([max(hi[i], hi2[i]) for i in range(3)])
        c3 = (lo3 + hi3) / 2
        L3 = hi3.x - lo3.x
        shoot(os.path.join(out, "with_ext_threeq.png"), c3, (0.55, -1, 0.75), L3 * 3.2, 105, 1800, 600, L3 * 0.5, floor_z)
        rc = socks["ExtPivot"] + Vector((0.02, 0, 0.0))
        shoot(os.path.join(out, "with_ext_close.png"), rc, (-1, -1, 0.8), 0.45, 85, 900, 900, 0.16, rc.z - 0.3)
    print(f"Loop: long views -> {out}")


if __name__ == "__main__":
    main()
