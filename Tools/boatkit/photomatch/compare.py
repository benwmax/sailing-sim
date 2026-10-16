"""Compose a photo and the render from its solved camera into one review image: side by side, a 50% blend and the
render's silhouette and edges drawn over the photo, so differences ("winch base 4 cm aft", "coaming too thick") show
at a glance. The output contains the photo, so it stays out of the public repo when the photo shows people.

  python3 Tools/boatkit/photomatch/compare.py <photo.jpg> <render.png> <out.jpg>
"""
import sys

from PIL import Image, ImageChops, ImageFilter, ImageOps


def compose(photo_path, render_path, out_path, width=1600):
    photo = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
    render = Image.open(render_path).convert("RGBA")
    render = render.resize(photo.size)
    alpha = render.getchannel("A")
    rgb = render.convert("RGB")
    blend = Image.blend(photo, rgb, 0.5)
    edges = rgb.convert("L").filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 24 else 0)
    outline = alpha.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 64 else 0)
    lines = ImageChops.lighter(edges, outline).filter(ImageFilter.MaxFilter(3))
    over = photo.copy()
    over.paste((255, 214, 0), mask=lines)
    h = int(width / 2 * photo.size[1] / photo.size[0])
    tiles = [im.resize((width // 2, h)) for im in (photo, rgb, blend, over)]
    sheet = Image.new("RGB", (width, 2 * h))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * (width // 2), (i // 2) * h))
    sheet.save(out_path, quality=88)
    print(f"Photomatch: compare -> {out_path}")


if __name__ == "__main__":
    compose(*sys.argv[1:4])
