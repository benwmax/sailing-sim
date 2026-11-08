"""Part detail loop: an outline check against a photo that is NOT square-on (docs/part-detail-loop/padeye.md).

score.py's outline check needs a square-on side photo. When the only good reference is a three-quarter product shot on a
plain white background (Bean's hardware sheet), this finds the camera angle that best matches the photo and reports the
overlap there: the part is rendered as a silhouette from a grid of angles (azimuth round Z, elevation above the deck),
each silhouette is cropped, scaled to the photo's height and centred, and the best intersection over union wins. A
match near 90% at a sensible angle says the proportions seen in the photo (loop height and width against the base,
the base's thickness) are right; it can't see the holes or anything inside the outline.

    python3 Tools/boatkit/partloop/photo_outline.py mask <photo.png> <out mask.png>         # system Python: numpy, scipy, Pillow
    python3 Tools/boatkit/partloop/photo_outline.py render <Part> <round dir>               # the bpy module (or blender -b -P ... --)
    python3 Tools/boatkit/partloop/photo_outline.py score <mask.png> <round dir> [--pass 0.85]

`mask` keeps the largest non-white region of the photo and fills only small holes (a countersink's highlight), so the
opening under a loop stays open: check <out>_overlay.jpg. `render` writes <round dir>/photo_angles/<az>_<el>.png.
`score` writes <round dir>/photo_outline.json and photo_outline_compare.png (blue ours only, red photo only).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AZ = list(range(0, 360, 15))
EL = [20, 25, 30, 35, 40, 45, 50]
H_NORM = 300


def make_mask(photo, out):
    import numpy as np
    from PIL import Image
    from scipy import ndimage as ndi
    im = np.asarray(Image.open(photo).convert("RGB")).astype(float)
    m = im.min(2) < 236
    m = ndi.binary_closing(m, iterations=1)
    lab, n = ndi.label(m)
    big = int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))) + 1
    m = lab == big
    holes = ndi.binary_fill_holes(m) & ~m
    hl, hn = ndi.label(holes)
    sizes = ndi.sum(holes, hl, range(1, hn + 1))
    for i, s in enumerate(sizes):
        if s < 0.02 * m.sum():
            m |= hl == i + 1
    Image.fromarray(((~m) * 255).astype(np.uint8)).save(out)
    ov = im.astype(np.uint8).copy()
    ov[m] = (ov[m] * 0.4 + np.array([255, 0, 0]) * 0.6).astype(np.uint8)
    Image.fromarray(ov).save(out[:-4] + "_overlay.jpg", quality=85)
    print(f"Photo outline: mask -> {out}")


def render(name, rnd):
    sys.path.insert(0, os.path.dirname(HERE))
    import bpy
    from mathutils import Vector
    import bk_geom as G
    import bk_parts as P
    import bk_render as R
    out = os.path.join(rnd, "photo_angles")
    os.makedirs(out, exist_ok=True)
    G.clear_scene()
    ob = P.build(name)
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c, size = (lo + hi) / 2, max(hi - lo)
    R._engine(240, 240)
    sc = bpy.context.scene
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.film_transparent = True
    for az in AZ:
        for el in EL:
            d = Vector((math.cos(math.radians(el)) * math.cos(math.radians(az)),
                        math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el))))
            for o in [o for o in bpy.data.objects if o.type == "CAMERA"]:
                bpy.data.objects.remove(o, do_unlink=True)
            R._camera(c + d * size * 2.2 * (85 / 50), c, 85)     # the product photo's long lens, as render_views
            sc.render.filepath = os.path.join(out, f"{az:03d}_{el:02d}_rgba.png")
            bpy.ops.render.render(write_still=True)
    print(f"Photo outline: {len(AZ) * len(EL)} angles -> {out}")


def _fill_small(m, share=0.02):
    from scipy import ndimage as ndi
    holes = ndi.binary_fill_holes(m) & ~m
    hl, hn = ndi.label(holes)
    sizes = ndi.sum(holes, hl, range(1, hn + 1))
    m = m.copy()
    for i, s in enumerate(sizes):
        if s < share * m.sum():
            m |= hl == i + 1
    return m


def _crop(m):
    import numpy as np
    rows, cols = np.nonzero(m.any(1))[0], np.nonzero(m.any(0))[0]
    return m[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def _norm(b):
    import numpy as np
    from PIL import Image
    h, w = b.shape
    nw = max(1, int(round(w * H_NORM / h)))
    return np.asarray(Image.fromarray((b * 255).astype(np.uint8)).resize((nw, H_NORM), Image.BILINEAR)) > 127


def _iou(a, b):
    import numpy as np
    a, b = _norm(a), _norm(b)
    W = 2 * max(a.shape[1], b.shape[1]) + 4      # room to centre either one on its centroid
    def place(x):
        cv = np.zeros((H_NORM, W), bool)
        off = W // 2 - int(round(np.nonzero(x)[1].mean()))
        cv[:, off:off + x.shape[1]] = x
        return cv
    a, b = place(a), place(b)
    return float((a & b).sum() / max(1, (a | b).sum())), a, b


def score(mask, rnd, need):
    import numpy as np
    from PIL import Image
    ref = _crop(np.asarray(Image.open(mask).convert("L")) < 128)
    best = None
    folder = os.path.join(rnd, "photo_angles")
    for f in sorted(os.listdir(folder)):
        if not f.endswith("_rgba.png"):
            continue
        a = np.asarray(Image.open(os.path.join(folder, f)).convert("RGBA"))[:, :, 3] > 127
        if not a.any():
            continue
        a = _fill_small(a)                 # the photo's mask fills a hole's bright bore: do the same here
        v, A, B = _iou(_crop(a), ref)
        if best is None or v > best[0]:
            best = (v, f, A, B)
    v, f, A, B = best
    az, el = int(f[:3]), int(f[4:6])
    vis = np.full(A.shape + (3,), 255, np.uint8)
    vis[A & ~B] = (40, 90, 220)
    vis[B & ~A] = (230, 60, 50)
    vis[A & B] = (60, 60, 60)
    Image.fromarray(vis).save(os.path.join(rnd, "photo_outline_compare.png"))
    res = {"iou": v, "azimuth": az, "elevation": el, "pass": v >= need, "target": need, "mask": os.path.basename(mask)}
    json.dump(res, open(os.path.join(rnd, "photo_outline.json"), "w"), indent=1)
    print(f"Photo outline: best {v * 100:.1f}% at azimuth {az}, elevation {el} (pass {need * 100:.0f}%)")


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if a[0] == "mask":
        make_mask(a[1], a[2])
    elif a[0] == "render":
        render(a[1], os.path.abspath(a[2]))
    else:
        need = float(a[a.index("--pass") + 1]) if "--pass" in a else 0.85
        score(a[1], a[2], need)


if __name__ == "__main__":
    main()
