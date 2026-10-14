"""Visual V6: the leaf-spray atlas for the tree cards (2x2 tiles, RGBA, 1024 px): 0-1 oak sprays (lobed leaves, glossy
dark green and paler), 2 cedar elm (small, toothed), 3 eastern red cedar (scale-leaf fronds). Alpha cuts the shapes.
Usage: Tools/venv/bin/python Tools/blender/make_leaf_atlas.py <out png>"""
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

S = 512


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
        n = 110 if kind == "elm" else 60
        for _ in range(n):
            r = rng.uniform(0, 1) ** 0.6 * 215
            a = rng.uniform(0, 2 * math.pi)
            cx, cy = S / 2 + math.cos(a) * r, S / 2 + math.sin(a) * r
            g = rng.randint(70, 120) if tile == 1 else rng.randint(55, 95)
            col = (int(g * 0.45), g, int(g * 0.3), 255)
            if kind == "elm":
                leaf(d, cx, cy, rng.uniform(28, 40), rng.uniform(10, 14), rng.uniform(0, 2 * math.pi), col)
            else:
                leaf(d, cx, cy, rng.uniform(55, 80), rng.uniform(18, 26), rng.uniform(0, 2 * math.pi), col, lobes=5)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main(out):
    rng = random.Random(5)
    atlas = Image.new("RGBA", (2 * S, 2 * S), (0, 0, 0, 0))
    for tile, kind in enumerate(("oak", "oak", "elm", "cedar")):
        atlas.paste(spray(tile, rng, kind), ((tile % 2) * S, (tile // 2) * S))
    # Fill the colour under transparent pixels with the average leaf colour so filtering doesn't darken the edges.
    bg = Image.new("RGBA", atlas.size, (40, 75, 28, 0))
    bg.alpha_composite(atlas)
    bg.save(out)


main(sys.argv[1])
