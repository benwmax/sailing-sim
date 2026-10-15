"""Visual V3: draws the sail marks atlas (Artifacts/textures/T_SailMarks.png) for M_SailCloth: the J/22 class insignia
(top half) and a sail number (bottom half), black on transparent. Run with the repo's venv before make_materials.py
(scripts/make-content.sh does)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Artifacts", "textures", "T_SailMarks.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
W, H = 1024, 1024
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)


# Saira Condensed Bold (SIL OFL 1.1, staged with the UI fonts): the glyphs we ship as images must come from a font whose
# licence covers that, not from the build machine's Arial or Helvetica (docs/licences/README.md item 1).
FONT = os.path.join(ROOT, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")
SLANT = 0.21  # Saira has no italic: the insignia is sheared to the J/Boats slant (about 12 deg) instead


def font(size):
    return ImageFont.truetype(FONT, size)


def centered(text, f, cy, fill):
    box = d.textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((W - w) / 2 - box[0], cy - h / 2 - box[1]), text, font=f, fill=fill)


# Class insignia: "J/22" in the J/Boats italic, the J in red. Drawn upright on its own layer, then sheared.
f = font(330)
parts = [("J", (190, 20, 25, 255)), ("/22", (10, 10, 12, 255))]
layer = Image.new("RGBA", (W, 512), (0, 0, 0, 0))
ld = ImageDraw.Draw(layer)
widths = [ld.textbbox((0, 0), t, font=f)[2] - ld.textbbox((0, 0), t, font=f)[0] for t, _ in parts]
x = (W - sum(widths)) / 2
for (t, col), w in zip(parts, widths):
    box = ld.textbbox((0, 0), t, font=f)
    ld.text((x - box[0], 256 - (box[3] - box[1]) / 2 - box[1]), t, font=f, fill=col)
    x += w + 6
# x_src = x_dst + SLANT * (y_dst - 256): the top leans right, the centre line stays put.
layer = layer.transform(layer.size, Image.AFFINE, (1, SLANT, -SLANT * 256, 0, 1, 0), resample=Image.BICUBIC)
img.alpha_composite(layer, (0, 0))
# Sail numbers (class rules: block numerals on the main). Graphics G3: a strip of the ten digits, one per cell (W/10 wide),
# each centred in a cell of the widest digit's width and squeezed into its atlas cell; M_SailCloth composes each boat's number from them.
f = font(360)
cw = W // 10
gmax = max(d.textbbox((0, 0), str(k), font=f)[2] - d.textbbox((0, 0), str(k), font=f)[0] for k in range(10))
for k in range(10):
    t = str(k)
    box = d.textbbox((0, 0), t, font=f)
    gw, gh = box[2] - box[0], box[3] - box[1]
    glyph = Image.new("RGBA", (int(gmax * 1.18), 512), (0, 0, 0, 0))  # one width for all: a "1" keeps its shape
    ImageDraw.Draw(glyph).text(((glyph.width - gw) / 2 - box[0], 256 - gh / 2 - box[1]), t, font=f, fill=(10, 10, 12, 255))
    img.alpha_composite(glyph.resize((cw, 512), Image.LANCZOS), (k * cw, 512))
img.save(OUT)
print("wrote", OUT)
