"""The leaf-spray atlas for the tree cards (4x2 tiles, RGBA; 2x2 before T2 species) and, from T2 on, its normal map.

T2 (Inputs/clouds-trees/plan.md, "real leaves"): each tile is a spray of photographed leaves (ambientCG leaf atlases,
CC0, Inputs/trees/ambientcg) on twigs radiating from the middle (the cards are turned at random, so a spray has no up):
0 post oak (LeafSet016, lobed), 1 live oak (LeafSet022, entire, leathery), 2 cedar elm (LeafSet024, small, toothed),
3 eastern red cedar (LeafSet019, scale-leaf fronds); T2 species' second row: 4 sugarberry (LeafSet024 narrowed), 5 black
willow (LeafSet022 cut to a third of its width), 6 cottonwood (LeafSet024 widened), 7 salt cedar (LeafSet019, fine
grey-green sprays). Each leaf is cut from its atlas by the opacity, turned stem-first
along the twig, and carries its own photographed normals (turned with it). The colours are scaled to the drawn atlas's
mean so the trees' exposure doesn't jump; M_TreeLeaves tints per card and per tree on top (TREE_LOOK).
Without the photo sources (Visual V6's drawn atlas): oak sprays (lobed leaves), cedar elm, red cedar fronds.

Usage: python Tools/blender/make_leaf_atlas.py <out png>   (writes <out>.png and, from photos, <out stem>N.png)"""
import math
import os
import random
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = os.path.join(REPO, "Inputs", "trees", "ambientcg")
S = 512   # the drawn atlas's tile


def leaf(draw, cx, cy, length, width, angle, color, lobes=0):
    pts = []
    for i in range(41):
        t = i / 40.0
        x = (t - 0.5) * length
        w = width * math.sin(math.pi * t) ** 0.8
        if lobes:
            w *= 0.75 + 0.25 * abs(math.sin(t * math.pi * lobes))
        pts.append((x, w))
    outline = pts + [(x, -w) for x, w in reversed(pts)]
    ca, sa = math.cos(angle), math.sin(angle)
    draw.polygon([(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in outline], fill=color)


def spray(tile, rng, kind):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "cedar":
        for _ in range(26):
            x0, y0 = rng.uniform(80, 430), rng.uniform(80, 430)
            a = rng.uniform(0, 2 * math.pi)
            for k in range(30):
                t = k / 30.0
                x, y = x0 + math.cos(a) * t * 150, y0 + math.sin(a) * t * 150
                g = rng.randint(55, 85)
                d.ellipse((x - 9 * (1 - t) - 3, y - 9 * (1 - t) - 3, x + 9 * (1 - t) + 3, y + 9 * (1 - t) + 3), fill=(30, g, 32, 255))
    else:
        n = 110 if kind in ("elm", "willow") else 60
        for _ in range(n):
            r = rng.uniform(0, 1) ** 0.6 * 215
            a = rng.uniform(0, 2 * math.pi)
            cx, cy = S / 2 + math.cos(a) * r, S / 2 + math.sin(a) * r
            g = rng.randint(70, 120) if tile == 1 else rng.randint(55, 95)
            col = (int(g * 0.45), g, int(g * 0.3), 255)
            if kind == "elm":
                leaf(d, cx, cy, rng.uniform(28, 40), rng.uniform(10, 14), rng.uniform(0, 2 * math.pi), col)
            elif kind == "willow":
                leaf(d, cx, cy, rng.uniform(40, 55), rng.uniform(4, 6), rng.uniform(0, 2 * math.pi), col)
            else:
                leaf(d, cx, cy, rng.uniform(55, 80), rng.uniform(18, 26), rng.uniform(0, 2 * math.pi), col, lobes=5)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def drawn_atlas(tiles=None):
    """Visual V6's drawn sprays, in the photo atlas's layout. drawn_atlas(4) is V6's own four (the exposure reference)."""
    rng = random.Random(5)
    atlas = Image.new("RGBA", (COLS * S, 2 * S), (0, 0, 0, 0))
    for tile, kind in enumerate(DRAWN_KINDS[:tiles]):
        atlas.paste(spray(tile, rng, kind), ((tile % COLS) * S, (tile // COLS) * S))
    return atlas


# --- T2: sprays of photographed leaves --------------------------------------------------------------------------------

T = 1024   # photo tile (a 4096 x 2048 atlas: four tiles a row, two rows)
COLS = 4
# Per tile: source, leaf length on the tile (px), leaves per twig, twigs, how far the twigs reach (px), and from T2 species
# on the leaf's width against the photo's (a narrow willow leaf from an elliptic one) and a colour scale.
SPECIES = (
    ("LeafSet016", (150, 210), 5, 7, 400),   # post oak
    ("LeafSet022", (120, 170), 7, 7, 410),   # live oak
    ("LeafSet024", (85, 120), 9, 8, 420),    # cedar elm
    ("LeafSet019", (300, 420), 1, 11, 380),  # eastern red cedar: whole fronds
    # T2 species (the plan's lake and Galveston trees), from the same four photographed sets:
    ("LeafSet024", (110, 150), 8, 8, 420, 0.8, (1.0, 1.0, 0.92)),     # sugarberry: ovate, pointed, a little narrower
    ("LeafSet022", (140, 190), 9, 9, 430, 0.32, (1.04, 1.06, 0.8)),   # black willow: long, narrow, yellow-green
    ("LeafSet024", (150, 200), 6, 7, 410, 1.15, (1.08, 1.1, 0.95)),   # cottonwood: broad, deltoid, bright
    ("LeafSet019", (140, 200), 4, 13, 330, 0.75, (0.95, 1.0, 1.08)),  # salt cedar: fine feathery sprays, grey-green
)
DRAWN_KINDS = ("oak", "oak", "elm", "cedar", "elm", "willow", "oak", "cedar")


def leaves_of(name):
    """The leaves of one ambientCG atlas: (colour RGBA, normal RGB) sprites, each turned so its long axis is vertical
    with the stem (its narrower end) at the bottom."""
    base = os.path.join(SOURCES, name, name + "_1K-JPG_")
    col = Image.open(base + "Color.jpg").convert("RGB")
    nrm = Image.open(base + "NormalGL.jpg").convert("RGB")
    opa = Image.open(base + "Opacity.jpg").convert("L")
    W = col.width
    q = 4
    small = opa.resize((W // q, W // q))
    px = small.load()
    n = small.width
    seen = [[False] * n for _ in range(n)]
    sprites = []
    for y0 in range(n):
        for x0 in range(n):
            if seen[y0][x0] or px[x0, y0] < 128:
                continue
            pts, dq = [], deque([(x0, y0)])
            seen[y0][x0] = True
            while dq:
                x, y = dq.popleft()
                pts.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    u, v = x + dx, y + dy
                    if 0 <= u < n and 0 <= v < n and not seen[v][u] and px[u, v] >= 128:
                        seen[v][u] = True
                        dq.append((u, v))
            if len(pts) < 60:
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            box = (max(0, min(xs) * q - 4), max(0, min(ys) * q - 4), min(W, (max(xs) + 1) * q + 4), min(W, (max(ys) + 1) * q + 4))
            # The long axis (principal component of the mask) and the turn that makes it vertical.
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            sxx = sum((x - mx) ** 2 for x in xs)
            syy = sum((y - my) ** 2 for y in ys)
            sxy = sum((x - mx) * (y - my) for x, y in pts)
            axis = 0.5 * math.atan2(2 * sxy, sxx - syy)            # from +x, image coordinates (y down)
            turn = math.degrees(axis) + 90.0                      # PIL turns counter-clockwise: long axis to vertical
            c = Image.merge("RGBA", (*col.crop(box).split(), opa.crop(box)))
            nm = nrm.crop(box)
            c, nm = turn_sprite(c, nm, turn)
            # Stem down: the narrower end of the leaf (its outline's width in the end tenths) at the bottom.
            a = c.split()[3].point(lambda v: 255 if v > 128 else 0)
            bb = a.getbbox()
            if not bb:
                continue
            c, nm = c.crop(bb), nm.crop(bb)
            a = c.split()[3]
            h = c.height
            top = a.crop((0, 0, c.width, max(1, h // 10))).histogram()[255]
            bot = a.crop((0, h - max(1, h // 10), c.width, h)).histogram()[255]
            if top < bot:
                c, nm = turn_sprite(c, nm, 180.0)
            sprites.append((c, nm))
    return sprites


def turn_sprite(c, nm, deg):
    """Turns a leaf's colour and its tangent-space normal map together (the normals' XY turn with the picture)."""
    c2 = c.rotate(deg, resample=Image.BICUBIC, expand=True)
    n2 = nm.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor=(128, 128, 255))
    v = np.asarray(n2, dtype=np.float32) / 127.5 - 1.0
    ca, sa = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    # GL normals: R = +x right, G = +y up; the picture turned counter-clockwise turns the vectors the same way.
    x, y = v[..., 0].copy(), v[..., 1].copy()
    v[..., 0], v[..., 1] = x * ca - y * sa, x * sa + y * ca
    return c2, Image.fromarray(np.clip((v + 1.0) * 127.5, 0, 255).astype(np.uint8), "RGB")


def photo_tile(rng, name, length, per_twig, twigs, reach, stretch=1.0, scale=(1.0, 1.0, 1.0)):
    col = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    nrm = Image.new("RGBA", (T, T), (128, 128, 255, 0))
    sprites = leaves_of(name)
    d = ImageDraw.Draw(col)
    c0 = (T / 2 + rng.uniform(-20, 20), T / 2 + rng.uniform(-20, 20))
    placed = []
    for k in range(twigs):
        a = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / twigs
        bend = rng.uniform(-0.35, 0.35)
        L = reach * rng.uniform(0.75, 1.0)
        pts = []
        for i in range(13):
            t = i / 12
            ang = a + bend * t
            pts.append((c0[0] + math.cos(ang) * L * t, c0[1] + math.sin(ang) * L * t))
        # The twig itself: grey-brown, thinning to the tip (it shows between the leaves near the middle).
        for i in range(12):
            w = int(round(7 * (1 - i / 12) + 2))
            d.line([pts[i], pts[i + 1]], fill=(74, 62, 48, 255), width=w)
        for j in range(per_twig):
            t = (j + 1) / (per_twig + 0.4) if per_twig > 1 else 0.2
            i = min(11, int(t * 12))
            px, py = pts[i]
            ang = a + bend * t
            side = 1 if j % 2 == 0 else -1
            out = ang + side * math.radians(rng.uniform(25, 55)) if per_twig > 1 else ang
            placed.append((rng.random(), px, py, out, rng.uniform(*length) * (1.0 - 0.25 * t)))
    # Back to front, at random: the overlap reads as depth; deeper leaves a little darker (shade in the spray).
    placed.sort()
    for depth, px, py, out, ln in placed:
        c, nm = sprites[rng.randrange(len(sprites))]
        s = ln / c.height
        c = c.resize((max(2, int(c.width * s * stretch)), max(2, int(c.height * s))), Image.LANCZOS)
        nm = nm.resize(c.size, Image.LANCZOS)
        if rng.random() < 0.5:
            c, nm = c.transpose(Image.FLIP_LEFT_RIGHT), flip_normals_x(nm.transpose(Image.FLIP_LEFT_RIGHT))
        # Stem at (px, py), the leaf pointing along `out`: the sprite's up (-y) turned onto the direction.
        deg = -math.degrees(out) - 90.0
        c, nm = turn_sprite(c, nm, deg)
        shade = 0.72 + 0.28 * depth
        r, g, b, a = c.split()
        c = Image.merge("RGBA", (r.point(lambda v: min(255, int(v * shade * scale[0]))), g.point(lambda v: min(255, int(v * shade * scale[1]))),
                                 b.point(lambda v: min(255, int(v * shade * scale[2]))), a))
        # Where the turned sprite's stem point lands: its centre offset by half the leaf along `out`.
        cx = px + math.cos(out) * ln * 0.5
        cy = py + math.sin(out) * ln * 0.5
        at = (int(cx - c.width / 2), int(cy - c.height / 2))
        col.alpha_composite(c, at)
        nrm.paste(Image.merge("RGBA", (*nm.split(), a)), at, a)
    return col, nrm


def flip_normals_x(nm):
    r, g, b = nm.split()
    return Image.merge("RGB", (r.point(lambda v: 255 - v), g, b))


def photo_atlas():
    rng = random.Random(12)
    atlas = Image.new("RGBA", (COLS * T, 2 * T), (0, 0, 0, 0))
    normals = Image.new("RGBA", (COLS * T, 2 * T), (128, 128, 255, 0))
    first = None
    for tile, spec in enumerate(SPECIES):
        c, n = photo_tile(rng, *spec)
        atlas.paste(c, ((tile % COLS) * T, (tile // COLS) * T))
        normals.paste(n, ((tile % COLS) * T, (tile // COLS) * T))
        if tile == 3:
            first = atlas.copy()
    # Exposure: the drawn atlas's mean leaf colour, so the trees keep their brightness and the tints mean the same. Taken
    # over the first four species (T2's scale, unchanged by the species added after them: theirs ride on the same scale).
    ref = mean_rgb(drawn_atlas(4))
    got = mean_rgb(first)
    k = sum(ref) / max(1e-6, sum(got))
    r, g, b, a = atlas.split()
    atlas = Image.merge("RGBA", (r.point(lambda v: min(255, int(v * k))), g.point(lambda v: min(255, int(v * k))), b.point(lambda v: min(255, int(v * k))), a))
    print(f"Leaf atlas: photo sprays, exposure x{k:.2f} (drawn mean {tuple(round(x) for x in ref)}, photo {tuple(round(x) for x in got)})")
    return atlas, normals


def mean_rgb(img):
    r, g, b, a = img.split()
    mask = a.point(lambda v: 255 if v > 128 else 0)
    n = max(1, mask.histogram()[255])
    return [sum(i * c for i, c in enumerate(ch.histogram(mask))) / n for ch in (r, g, b)]


def main(out):
    if os.path.isdir(SOURCES):
        atlas, normals = photo_atlas()
        stem, ext = os.path.splitext(out)
        flat = Image.new("RGB", normals.size, (128, 128, 255))
        flat.paste(normals.convert("RGB"), (0, 0), normals.split()[3])
        flat.save(stem + "N" + ext)
    else:
        atlas = drawn_atlas()
    # Fill the colour under transparent pixels with the average leaf colour so filtering doesn't darken the edges.
    bg = Image.new("RGBA", atlas.size, (40, 75, 28, 0))
    bg.alpha_composite(atlas)
    bg.save(out)
    print(f"Leaf atlas: {out} {atlas.size[0]} px")


main(sys.argv[1])
