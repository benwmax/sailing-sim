"""Contact sheets from render_trees.py's stills: a grid with a label under each picture.

  python3 -I Tools/envloop/trees/make_sheet.py <out.jpg> <cols> <image> [<image> ...]   (labels: the file names)
  python3 -I Tools/envloop/trees/make_sheet.py <out.jpg> <cols> --pairs <dir> <name pattern with {gen}> ...
     --pairs puts each v6 still beside its Track D twin (before | after), one pair per row.
"""
import os
import sys

from PIL import Image, ImageDraw


def sheet(paths, out, cols, labels=None, cell_w=480):
    ims = [Image.open(p).convert("RGB") for p in paths]
    w = cell_w
    h = int(ims[0].height * w / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * (h + 18)), (250, 250, 248))
    d = ImageDraw.Draw(S)
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 18)
        S.paste(im.resize((w, h), Image.LANCZOS), (x, y))
        d.text((x + 4, y + h + 3), (labels[i] if labels else os.path.splitext(os.path.basename(paths[i]))[0]), fill=(20, 20, 20))
    S.save(out, quality=86)


def main(argv):
    out, cols = argv[0], int(argv[1])
    if argv[2] == "--pairs":
        d = argv[3]
        paths, labels = [], []
        for pat in argv[4:]:
            for gen, tag in (("v6", "before"), ("d", "after")):
                p = os.path.join(d, pat.format(gen=gen))
                if os.path.exists(p):
                    paths.append(p)
                    labels.append(f"{tag}: {pat.format(gen=gen)[:-4]}")
        sheet(paths, out, cols, labels)
    else:
        sheet(argv[2:], out, cols)


if __name__ == "__main__":
    main(sys.argv[1:])
