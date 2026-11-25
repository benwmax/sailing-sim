"""The Lagoon 42 rebuild's doc images (docs/lagoon42-1, the C22's docs_c22.py): render_set.py's PNGs to the docs' JPEGs and a contact sheet.

    python3 -I docs_lagoon42.py <hull renders dir> <rig renders dir> <docs dir>

<hull renders dir> is render_set.py's output without --with-other (the boat without her rig), <rig renders dir> with it
(only its shade_profile is used, as rig_profile.jpg). Writes <docs dir>/<view>.jpg at 1200 px for the nine views below
and sheet.jpg, a 3 x 3 contact sheet with labels: plain-git JPEGs well under docs/.gitattributes' 300 KB. Needs Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

VIEWS = ["shade_profile", "shade_34", "shade_bow34", "shade_stern34", "shade_plan", "shade_cockpit", "shade_bow",
         "shade_stern", "zebra_34"]


def font(px):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def jpg(src, dst):
    im = Image.open(src).convert("RGB")
    im.thumbnail((1200, 1200))
    im.save(dst, quality=82)


def main(hull_dir, rig_dir, out):
    os.makedirs(out, exist_ok=True)
    for v in VIEWS:
        jpg(os.path.join(hull_dir, v + ".png"), os.path.join(out, v + ".jpg"))
    jpg(os.path.join(rig_dir, "shade_profile.png"), os.path.join(out, "rig_profile.jpg"))
    w, h, lab = 600, 300, 30
    sheet = Image.new("RGB", (3 * w, 3 * (h + lab)), "white")
    dr = ImageDraw.Draw(sheet)
    f = font(20)
    for i, v in enumerate(VIEWS):
        im = Image.open(os.path.join(hull_dir, v + ".png")).convert("RGB").resize((w, h))
        x, y = (i % 3) * w, (i // 3) * (h + lab)
        sheet.paste(im, (x, y))
        dr.text((x + 8, y + h + 4), v.replace("_", " "), fill="black", font=f)
    sheet.save(os.path.join(out, "sheet.jpg"), quality=80)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
