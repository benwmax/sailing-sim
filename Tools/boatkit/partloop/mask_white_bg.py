"""Part detail loop: a reference outline from a catalogue-style photo of a bright (stainless) part on a white background,
where score.py --save-mask (a dark part on a busier background) finds nothing.

    python3 Tools/boatkit/partloop/mask_white_bg.py <photo> <out dir> <ref id> [--crop x0 y0 x1 y1] [--rotate auto|<deg>]
        [--flip] [--thresh 0.93]

Everything darker or more coloured than the paper white is the part; the largest region is kept and its holes filled.
--rotate auto turns the photo so the outline's long axis is vertical (principal axes of the mask); --flip mirrors it
left to right afterwards (so the part faces the way the side render does). Writes <id>.mask.png (black part on white),
<id>.mask_overlay.jpg to check by eye, and <id>.rot.png, the photo turned the same way (for the sheet).
Needs numpy, scipy and Pillow.
"""
import argparse
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def part_mask(im, thresh):
    a = np.asarray(im.convert("RGB")).astype(float) / 255
    mx, mn = a.max(2), a.min(2)
    m = (mn < thresh) | ((mx - mn) > 0.08)
    m = ndi.binary_opening(m, iterations=2)
    lab, n = ndi.label(m)
    big = int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))) + 1
    return ndi.binary_fill_holes(ndi.binary_closing(lab == big, iterations=4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("out")
    ap.add_argument("rid")
    ap.add_argument("--crop", type=int, nargs=4)
    ap.add_argument("--rotate", default="0")
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--thresh", type=float, default=0.93)
    a = ap.parse_args()
    im = Image.open(a.photo).convert("RGB")
    if a.crop:
        im = im.crop(tuple(a.crop))
    pad = max(im.size) // 2                        # room to turn without cutting a corner off
    big = Image.new("RGB", (im.width + 2 * pad, im.height + 2 * pad), (255, 255, 255))
    big.paste(im, (pad, pad))
    m = part_mask(big, a.thresh)
    if a.rotate == "auto":
        ys, xs = np.nonzero(m)
        cov = np.cov(np.vstack([xs - xs.mean(), ys - ys.mean()]))
        w, v = np.linalg.eigh(cov)
        ax = v[:, np.argmax(w)]                    # long axis (x, y) in image coordinates
        deg = math.degrees(math.atan2(ax[0], ax[1]))
    else:
        deg = float(a.rotate)
    big = big.rotate(-deg, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    if a.flip:
        big = big.transpose(Image.FLIP_LEFT_RIGHT)
    m = part_mask(big, a.thresh)
    ys, xs = np.nonzero(m)
    box = (xs.min() - 8, ys.min() - 8, xs.max() + 9, ys.max() + 9)
    big, m = big.crop(box), m[box[1]:box[3], box[0]:box[2]]
    os.makedirs(a.out, exist_ok=True)
    Image.fromarray(((~m) * 255).astype(np.uint8)).save(os.path.join(a.out, f"{a.rid}.mask.png"))
    big.save(os.path.join(a.out, f"{a.rid}.rot.png"))
    ov = np.asarray(big).copy()
    ov[m] = (ov[m] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)
    Image.fromarray(ov).save(os.path.join(a.out, f"{a.rid}.mask_overlay.jpg"), quality=88)
    print(f"Mask: {a.rid} turned {deg:.1f} deg, {m.shape[1]} x {m.shape[0]} px -> {a.out}")


if __name__ == "__main__":
    main()
