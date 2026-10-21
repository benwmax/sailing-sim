"""Visual V3: draws the sail marks atlas (Artifacts/textures/T_SailMarks.png) for M_SailCloth: the class insignia (top
half; boat fidelity 4: a made-up emblem, no real class mark) and the sail number digits (bottom half), on transparent.
Run with the repo's venv before make_materials.py (scripts/make-content.sh does)."""
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


def font(size):
    return ImageFont.truetype(FONT, size)


def centered(text, f, cy, fill):
    box = d.textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((W - w) / 2 - box[0], cy - h / 2 - box[1]), text, font=f, fill=fill)


# Class insignia (boat fidelity 4): a made-up emblem, never a real class's mark or a maker's logo. A red sail over two
# navy swells, drawn at 4x and filtered down, centred in the top half.
import math  # noqa: E402

S4 = 4
layer = Image.new("RGBA", (W * S4, 512 * S4), (0, 0, 0, 0))
ld = ImageDraw.Draw(layer)


def swell(cx, cy, half, amp, thick, col):
    """A breaking swell: a sine crest from cx - half to cx + half, `thick` deep, its crest curling forward."""
    top = [(cx + half * (2 * t - 1), cy - amp * math.sin(math.pi * t) ** 1.6 * (1 + 0.25 * t)) for t in [i / 64 for i in range(65)]]
    bottom = [(x + thick * 0.15, y + thick) for x, y in reversed(top)]
    ld.polygon([(x * S4, y * S4) for x, y in top + bottom], fill=col)


navy, red = (16, 34, 92, 255), (190, 24, 28, 255)
swell(W / 2 - 20, 360, 260, 70, 34, navy)
swell(W / 2 + 40, 430, 230, 55, 30, navy)
# The sail: a leaning triangle with a curved leech, its foot on the upper swell.
sail = [(W / 2 - 150, 300), (W / 2 + 10, 60)] + [(W / 2 + 10 + 120 * t, 60 + 240 * t + 40 * math.sin(math.pi * t)) for t in [i / 24 for i in range(1, 25)]]
ld.polygon([(x * S4, y * S4) for x, y in sail], fill=red)
img.alpha_composite(layer.resize((W, 512), Image.LANCZOS), (0, 0))
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
