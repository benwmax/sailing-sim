"""Track D's leaf atlas: every species' spray with its leaves at TRUE size, plus a dense "clump" of each for the crown's
inside (the masked shell that replaces V6's opaque core ball), and post oak's dried winter leaves.

Layout, 4096 x 4096, sixteen 1024 px tiles (row-major, tile t at column t % 4, row t // 4):
  0-11  one spray per card (cards/*.json "tile"): a 1024 px tile spans the card's `card_m` metres, so a leaf of
        `length_cm` is length_cm / 100 * 1024 / card_m pixels (the size card: within 5 %)
  12-14 the clumps: each a 2 x 2 of 512 px sub-tiles, card tile i at tile 12 + i // 4, quadrant i % 4 (column, row),
        at the same metres per pixel as the species' spray (a 512 px clump spans card_m / 2)
  15    post oak's marcescent winter spray (ambientCG LeafSet012, dried)
A second image <out stem>N.png carries the photographed normals (OpenGL, turned with each leaf).

Compound leaves are built before they are placed: pecan's pinnate leaf (a rachis with 9-15 leaflets), mesquite's
bipinnate frond (a stalk forking into two pinnae of tiny leaflets).

Colour: each tile's mean leaf colour is scaled to the V6/T2 atlas's mean (the game's tree tone, TREE_LOOK tints on top),
then by the card's `colour` (hue and brightness between species).

Usage: python3 -I Tools/envloop/trees/make_leaf_atlas_d.py <out png> [--sources Inputs/trees]   (numpy, Pillow)
"""
import glob
import json
import math
import os
import random
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T = 1024
COLS = 4
# The T2 atlas's mean leaf colour (sRGB 0-255), what make_leaf_atlas.py scales its photos to: the game's tree tone.
REF_MEAN = (35.0, 79.0, 25.0)


def cards():
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "cards", "*.json"))):
        c = json.load(open(p))
        if c.get("leaf") and c.get("tile") is not None:
            out[c["id"]] = c
    return out


def turn_sprite(c, nm, deg):
    """Turns a leaf's colour and its tangent-space normal map together (the normals' XY turn with the picture)."""
    c2 = c.rotate(deg, resample=Image.BICUBIC, expand=True)
    n2 = nm.rotate(deg, resample=Image.BICUBIC, expand=True, fillcolor=(128, 128, 255))
    v = np.asarray(n2, dtype=np.float32) / 127.5 - 1.0
    ca, sa = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y = v[..., 0].copy(), v[..., 1].copy()
    v[..., 0], v[..., 1] = x * ca - y * sa, x * sa + y * ca
    return c2, Image.fromarray(np.clip((v + 1.0) * 127.5, 0, 255).astype(np.uint8), "RGB")


def flip_x(c, nm):
    r, g, b = nm.transpose(Image.FLIP_LEFT_RIGHT).split()
    return c.transpose(Image.FLIP_LEFT_RIGHT), Image.merge("RGB", (r.point(lambda v: 255 - v), g, b))


_LEAVES = {}


def leaves_of(sources, set_name):
    """The single leaves of one ambientCG leaf atlas as (RGBA, normal) sprites, long axis vertical, stem (the narrower
    end) at the bottom, cropped to the leaf. Cached."""
    if set_name in _LEAVES:
        return _LEAVES[set_name]
    source, asset = set_name.split("/", 1)
    base = os.path.join(sources, source, asset, asset + "_1K-JPG_")
    col = Image.open(base + "Color.jpg").convert("RGB")
    nrm = Image.open(base + "NormalGL.jpg").convert("RGB")
    opa = Image.open(base + "Opacity.jpg").convert("L")
    W = col.width
    q = 4
    small = np.asarray(opa.resize((W // q, W // q))) >= 128
    n = small.shape[0]
    seen = np.zeros_like(small)
    sprites = []
    for y0 in range(n):
        for x0 in range(n):
            if seen[y0, x0] or not small[y0, x0]:
                continue
            pts, dq = [], deque([(x0, y0)])
            seen[y0, x0] = True
            while dq:
                x, y = dq.popleft()
                pts.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    u, v = x + dx, y + dy
                    if 0 <= u < n and 0 <= v < n and not seen[v, u] and small[v, u]:
                        seen[v, u] = True
                        dq.append((u, v))
            if len(pts) < 60:
                continue
            xs = np.array([p[0] for p in pts], dtype=np.float64)
            ys = np.array([p[1] for p in pts], dtype=np.float64)
            box = (max(0, int(xs.min()) * q - 4), max(0, int(ys.min()) * q - 4), min(W, (int(xs.max()) + 1) * q + 4), min(W, (int(ys.max()) + 1) * q + 4))
            mx, my = xs.mean(), ys.mean()
            axis = 0.5 * math.atan2(2 * ((xs - mx) * (ys - my)).sum(), ((xs - mx) ** 2).sum() - ((ys - my) ** 2).sum())
            c = Image.merge("RGBA", (*col.crop(box).split(), opa.crop(box)))
            nm = nrm.crop(box)
            c, nm = turn_sprite(c, nm, math.degrees(axis) + 90.0)
            bb = c.split()[3].point(lambda v: 255 if v > 128 else 0).getbbox()
            if not bb:
                continue
            c, nm = c.crop(bb), nm.crop(bb)
            a = np.asarray(c.split()[3]) > 128
            h = a.shape[0]
            k = max(1, h // 10)
            if a[:k].sum() < a[h - k:].sum():
                c, nm = turn_sprite(c, nm, 180.0)
            sprites.append((c, nm))
    if not sprites:
        raise SystemExit(f"No leaves found in {set_name}: run fetch_sets.py")
    _LEAVES[set_name] = sprites
    return sprites


def scaled(sprite, length_px, width_scale=1.0):
    c, nm = sprite
    s = length_px / c.height
    size = (max(2, int(round(c.width * s * width_scale))), max(2, int(round(c.height * s))))
    return c.resize(size, Image.LANCZOS), nm.resize(size, Image.LANCZOS)


class Canvas:
    def __init__(self, size):
        self.col = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.nrm = Image.new("RGBA", (size, size), (128, 128, 255, 0))
        self.draw = ImageDraw.Draw(self.col)

    def stamp(self, sprite, x, y, ang, shade=1.0):
        """Puts a stem-down sprite with its stem at (x, y) pointing along `ang` (radians, image coordinates)."""
        c, nm = sprite
        ln = c.height
        c, nm = turn_sprite(c, nm, -math.degrees(ang) - 90.0)
        if shade != 1.0:
            r, g, b, a = c.split()
            c = Image.merge("RGBA", (*(ch.point(lambda v: min(255, int(v * shade))) for ch in (r, g, b)), a))
        cx, cy = x + math.cos(ang) * ln * 0.5, y + math.sin(ang) * ln * 0.5
        at = (int(cx - c.width / 2), int(cy - c.height / 2))
        a = c.split()[3]
        self.col.alpha_composite(c, at)
        self.nrm.paste(Image.merge("RGBA", (*nm.split(), a)), at, a)

    def line(self, pts, w0, w1, colour=(74, 62, 48, 255)):
        for i in range(len(pts) - 1):
            w = w0 + (w1 - w0) * i / max(1, len(pts) - 2)
            self.draw.line([pts[i], pts[i + 1]], fill=colour, width=max(1, int(round(w))))


def compound(rng, leaflets, kind, length_px, leaflet_px, n_leaflets):
    """A pecan's pinnate leaf or a mesquite's bipinnate frond, built stem-down on its own canvas: returns a sprite."""
    L = int(length_px * 1.15) + 8
    W = int(length_px * (0.9 if kind == "bipinnate" else 0.75)) + 8
    cv = Canvas(max(L, W))
    size = cv.col.width
    x0, y0 = size / 2, size - 4
    if kind == "pinnate":
        # Rachis straight up, a slight curve; leaflets in pairs (and one at the tip), longest in the middle.
        pts = [(x0 + math.sin(t * 1.3) * length_px * 0.04, y0 - t * length_px) for t in np.linspace(0, 1, 12)]
        cv.line(pts, 3, 1.2, (96, 104, 60, 255))
        pairs = n_leaflets // 2
        for k in range(pairs):
            t = 0.22 + 0.7 * (k + 0.5) / pairs
            px, py = pts[min(11, int(t * 11))]
            size_k = leaflet_px * (0.65 + 0.35 * math.sin(math.pi * (0.25 + 0.75 * t)))
            for side in (-1, 1):
                ang = -math.pi / 2 + side * math.radians(rng.uniform(55, 75))
                cv.stamp(scaled(leaflets[rng.randrange(len(leaflets))], size_k, 0.8), px, py, ang)
        cv.stamp(scaled(leaflets[rng.randrange(len(leaflets))], leaflet_px * 0.85, 0.8), *pts[-1], -math.pi / 2)
    else:
        # Mesquite: a stalk, then two pinnae forking at about 50 deg, each with tiny narrow leaflets in close pairs.
        stalk = length_px * 0.22
        cv.line([(x0, y0), (x0, y0 - stalk)], 2.5, 2, (110, 112, 66, 255))
        fx, fy = x0, y0 - stalk
        for side in (-1, 1):
            a = -math.pi / 2 + side * math.radians(rng.uniform(18, 30))
            pl = length_px * 0.78
            pts = [(fx + math.cos(a + side * 0.12 * t) * pl * t, fy + math.sin(a + side * 0.12 * t) * pl * t) for t in np.linspace(0, 1, 10)]
            cv.line(pts, 2, 1, (110, 112, 66, 255))
            pairs = n_leaflets // 2
            for k in range(pairs):
                t = 0.08 + 0.9 * k / pairs
                px, py = pts[min(9, int(t * 9))]
                for s2 in (-1, 1):
                    ang = a + s2 * math.radians(rng.uniform(60, 80))
                    cv.stamp(scaled(leaflets[rng.randrange(len(leaflets))], leaflet_px * rng.uniform(0.85, 1.1), 0.55), px, py, ang)
    bb = cv.col.split()[3].getbbox()
    c, nm = cv.col.crop(bb), cv.nrm.crop(bb)
    # Re-anchor: the stem (bottom middle of the bounding box) stays at the bottom.
    return c, nm.convert("RGB")


def spray_tile(rng, card, sources, size=T, dense=False, set_override=None):
    """One species' spray on a size x size canvas at the card's metres per pixel. Twigs radiate from the middle (a card
    is turned at random, so a spray has no up), each with side shoots; leaves sit along them, alternate, until the
    disc is about half covered. dense=True makes the clump: leaves scattered (no twigs) to about 80 % cover, deeper."""
    leaf = card["leaf"]
    px_per_m = T / leaf["card_m"]          # the clump keeps the spray's scale (its tile is half the size)
    sprites = leaves_of(sources, set_override or leaf["set"])
    lo, hi = (x / 100.0 * px_per_m for x in leaf["length_cm"])
    kind = leaf.get("compound")
    if kind:
        llo, lhi = (x / 100.0 * px_per_m for x in leaf["leaflet_cm"])
        n_lf = leaf["leaflets"]
        # A handful of compound leaves, each built once, reused turned and scaled a little.
        protos = [compound(rng, sprites, kind, rng.uniform(lo, hi), rng.uniform(llo, lhi), rng.randint(*n_lf) | 1) for _ in range(6)]
        pick = lambda ln: scaled(protos[rng.randrange(len(protos))], ln)   # noqa: E731
    else:
        width = leaf.get("width_scale", 0.7 if leaf.get("fine") else 1.0)
        pick = lambda ln: scaled(sprites[rng.randrange(len(sprites))], ln, width)   # noqa: E731
    cv = Canvas(size)
    centre = (size / 2 + rng.uniform(-10, 10), size / 2 + rng.uniform(-10, 10))
    target = 0.62 if dense else 0.42
    mask_r = size * 0.47

    def coverage():
        a = np.asarray(cv.col.split()[3]) > 128
        yy, xx = np.mgrid[0:size, 0:size]
        disc = (xx - size / 2) ** 2 + (yy - size / 2) ** 2 < mask_r ** 2
        return a[disc].mean()

    if dense:
        placed = 0
        while placed < 4000:
            for _ in range(40):
                ln = rng.uniform(lo, hi)
                x, y = rng.uniform(0.05, 0.95) * size, rng.uniform(0.05, 0.95) * size
                cv.stamp(pick(ln), x, y, rng.uniform(0, 2 * math.pi), shade=rng.uniform(0.55, 0.85))
                placed += 1
            if coverage() >= target:
                break
        return cv
    twigs = leaf["twigs"]
    # Leaves stay inside the tile: the twigs stop a leaf short of the edge.
    reach = size * 0.47 - hi * 0.95
    shoots = []
    # A leafy branch, not a rosette: the twigs fan out from a stem entering near one edge, across the tile, at uneven
    # lengths, so a card's outline is a ragged fan (a rosette's round outline read as one big leaf from 15 m).
    A = rng.uniform(0, 2 * math.pi)
    base = (centre[0] - math.cos(A) * reach * 0.9, centre[1] - math.sin(A) * reach * 0.9)
    cv.line([base, (base[0] + math.cos(A) * reach * 0.35, base[1] + math.sin(A) * reach * 0.35)], max(3.0, 0.016 * px_per_m), 2.5)
    for k in range(twigs):
        a = A + math.radians(-55 + 110 * (k + rng.uniform(0.1, 0.9)) / twigs)
        bend = rng.uniform(-0.3, 0.3)
        L = reach * rng.uniform(0.9, 1.85)
        start = (base[0] + math.cos(A) * reach * rng.uniform(0.1, 0.35), base[1] + math.sin(A) * reach * rng.uniform(0.1, 0.35))
        steps = max(13, int(L / max(6.0, lo * 0.55)))
        pts = [(start[0] + math.cos(a + bend * t) * L * t, start[1] + math.sin(a + bend * t) * L * t) for t in np.linspace(0, 1, steps)]
        # Clip to the tile, a leaf short of the edge.
        lim = size * 0.5 - hi * 0.55
        pts = [p for p in pts if abs(p[0] - size / 2) < lim and abs(p[1] - size / 2) < lim] or pts[:2]
        if len(pts) < 3:
            continue
        cv.line(pts, max(2.0, 0.012 * px_per_m), 1.5)
        shoots.append((pts, a, bend))
        # Side shoots: two or three off each twig's outer half, carrying their own leaves.
        for j in range(rng.randint(2, 3)):
            t = rng.uniform(0.35, 0.8)
            i = int(t * (len(pts) - 1))
            sa = a + bend * t + (1 if j % 2 else -1) * math.radians(rng.uniform(30, 55))
            sl = L * rng.uniform(0.25, 0.4)
            sp = [(pts[i][0] + math.cos(sa) * sl * u, pts[i][1] + math.sin(sa) * sl * u) for u in np.linspace(0, 1, max(7, int(sl / max(6.0, lo * 0.55))))]
            cv.line(sp, max(1.5, 0.008 * px_per_m), 1)
            shoots.append((sp, sa, 0.0))
    # Leaves along the shoots, alternate sides, tips last, deeper ones darker; until the disc is covered enough.
    order = []
    for pts, a, bend in shoots:
        n = len(pts)
        for i in range(1, n):
            order.append((rng.random(), pts, i, n, a, bend))
    rng.shuffle(order)
    count = 0
    for depth, pts, i, n, a, bend in order:
        t = i / (n - 1)
        ang = a + bend * t
        side = 1 if (i + count) % 2 else -1
        per = leaf["per_twig"]
        out = ang + side * math.radians(rng.uniform(25, 60)) if per > 1 else ang
        ln = rng.uniform(lo, hi) * (1.0 - 0.2 * t)
        cv.stamp(pick(ln), pts[i][0], pts[i][1], out, shade=0.72 + 0.28 * depth)
        count += 1
        if count % 25 == 0 and coverage() >= target:
            break
    return cv


def tone(img, colour, ref=REF_MEAN):
    """Scales the leaves' mean colour to the game's tree tone (or `ref`), then by the species' colour."""
    arr = np.asarray(img, dtype=np.float32)
    a = arr[..., 3] > 128
    if not a.any():
        return img
    mean = arr[a][:, :3].mean(axis=0)
    k = sum(ref) / max(1e-3, mean.sum())
    arr[..., :3] = np.clip(arr[..., :3] * k * np.asarray(colour, dtype=np.float32), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def main(argv):
    out = argv[0]
    sources = os.path.join(REPO, "Inputs", "trees")
    if "--sources" in argv:
        sources = argv[argv.index("--sources") + 1]
    rng = random.Random(1611)
    atlas = Image.new("RGBA", (COLS * T, COLS * T), (0, 0, 0, 0))
    normals = Image.new("RGBA", (COLS * T, COLS * T), (128, 128, 255, 0))
    report = {}
    for cid, card in sorted(cards().items(), key=lambda kv: kv[1]["tile"]):
        t = card["tile"]
        cv = spray_tile(rng, card, sources)
        col = tone(cv.col, card["leaf"].get("colour", (1, 1, 1)))
        atlas.paste(col, ((t % COLS) * T, (t // COLS) * T))
        normals.paste(cv.nrm, ((t % COLS) * T, (t // COLS) * T))
        # The clump: half-size tile, same scale.
        cl = spray_tile(rng, card, sources, size=T // 2, dense=True)
        ct = 12 + t // 4
        q = t % 4
        at = ((ct % COLS) * T + (q % 2) * T // 2, (ct // COLS) * T + (q // 2) * T // 2)
        atlas.paste(tone(cl.col, [c * 0.8 for c in card["leaf"].get("colour", (1, 1, 1))]), at)
        normals.paste(cl.nrm, at)
        a = np.asarray(col.split()[3]) > 128
        report[cid] = dict(tile=t, cover=round(float(a.mean()), 3), px_per_m=round(T / card["leaf"]["card_m"]),
                           leaf_px=[round(x / 100 * T / card["leaf"]["card_m"]) for x in card["leaf"]["length_cm"]])
        print(f"Atlas D: {cid} tile {t} cover {report[cid]['cover']} leaf {report[cid]['leaf_px']} px")
        if cid == "PostOak" and card.get("winter", {}).get("set"):
            wc = spray_tile(rng, card, sources, set_override=card["winter"]["set"])
            # Dried oak leaves: their own tone (a dull tan-brown at the green leaves' brightness), not the green's.
            atlas.paste(tone(wc.col, (1.0, 1.0, 1.0), ref=(68.0, 50.0, 30.0)), ((15 % COLS) * T, (15 // COLS) * T))
            normals.paste(wc.nrm, ((15 % COLS) * T, (15 // COLS) * T))
    stem, ext = os.path.splitext(out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    flat = Image.new("RGB", normals.size, (128, 128, 255))
    flat.paste(normals.convert("RGB"), (0, 0), normals.split()[3])
    flat.save(stem + "N" + ext)
    bg = Image.new("RGBA", atlas.size, (40, 75, 28, 0))
    bg.alpha_composite(atlas)
    bg.save(out)
    json.dump(report, open(stem + ".json", "w"), indent=1)
    print(f"Atlas D: {out} {atlas.size[0]} px")


if __name__ == "__main__":
    main(sys.argv[1:])
