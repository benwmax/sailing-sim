"""Part detail loop, step 6: score one round of a part against its card (docs/part-detail-loop).

    python3 Tools/boatkit/partloop/score.py <parts/<part>.json> <refs dir> <round dir> [--save-mask <photo.jpg> <ref id>]

Reads the round's renders and stats.json (render_views.py) and, from <refs dir> (git-ignored: Data/Reference/raw/parts/<part>
or the project files), each reference's outline mask (<id>.mask.png, black part on white). Writes <round dir>/score.json and
prints the scorecard. Checks:
  sizes     each size on the card against the model, measured on the orthographic outlines (and sockets for the sheave;
            overall_all runs to the lowest point, such as a becket; sheave2 is a fiddle's small sheave)
  outline   the side outline's body (shackle and becket left off; the whole outline with "whole": true on the card)
            against the reference outline, both scaled to the same height and centred: intersection over union; a card
            with "outline": null has no square-on reference and reports the outline as not checked
  Size ids: overall, overall_all, sheave, sheave2, aspect, head, thick (blocks); length, height, width, aspect_full, foot,
            waist (any part, from the whole outlines: aspect_full is height / length, foot and waist are fractions of the
            length)
  features  the card's list: `objects` must all be among the joined objects, `slots` among the material slots, and
            `manual` ticks come from <round dir>/review.json ({"ticks": {"<id>": true|false}, "notes": ...}), filled in by
            whoever looked at the renders
  budget    triangles and material slots
--save-mask makes a reference outline from a square-on photo of a dark part on a lighter, busier background (largest
dark, unsaturated region, holes filled); check its overlay (<id>.mask_overlay.jpg) before trusting it.
Needs numpy, scipy and Pillow (a system Python, not Blender's).
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

H_NORM = 400          # outlines are compared at this height


def load_mask(path):
    a = np.asarray(Image.open(path).convert("L")) < 128
    return ndi.binary_fill_holes(a)


def body_rows(m, frac=0.35):
    """Rows of the main body: from the widest row out while the outline is wider than frac of the widest (stops at a
    narrow shackle post or becket)."""
    w = m.sum(1)
    peak = int(np.argmax(w))
    lim = frac * w[peak]
    top = peak
    while top > 0 and w[top - 1] > lim:
        top -= 1
    bot = peak
    while bot < len(w) - 1 and w[bot + 1] > lim:
        bot += 1
    return top, bot


def body(m):
    top, bot = body_rows(m)
    b = m[top:bot + 1]
    cols = np.nonzero(b.any(0))[0]
    return b[:, cols.min():cols.max() + 1], top, bot


def proportions(m):
    b, top, bot = body(m)
    h, w = b.shape
    row = b[int(h * 0.04)]
    head = row.sum()
    return {"aspect": h / w, "head": head / w, "h_px": h, "w_px": w, "top": top, "bot": bot}


def whole(m):
    """The whole outline cropped to its bounding box (parts with no hanging shackle, such as cleats)."""
    rows, cols = np.nonzero(m.any(1))[0], np.nonzero(m.any(0))[0]
    return m[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def shape(m):
    """Proportions of the whole outline as fractions of its length: height, foot (the bottom row's length) and waist
    (the narrowest row in the lower half, where a cleat's pedestal pinches in)."""
    b = whole(m)
    h, w = b.shape
    widths = b.sum(1)
    foot = widths[max(0, h - 1 - max(1, h // 100)):].max()
    waist = widths[h // 2:].min()
    return {"aspect_full": h / w, "foot": foot / w, "waist": waist / w, "h_full_px": h, "w_full_px": w}


def norm(b):
    h, w = b.shape
    nw = max(1, int(round(w * H_NORM / h)))
    im = Image.fromarray((b * 255).astype(np.uint8)).resize((nw, H_NORM), Image.BILINEAR)
    return np.asarray(im) > 127


def iou(a, b):
    a, b = norm(a), norm(b)
    W = 2 * max(a.shape[1], b.shape[1]) + 4       # room for an off-centre centroid (padding leaves the IoU as it is)
    def place(x):
        c = np.zeros((H_NORM, W), bool)
        cx = int(round(np.nonzero(x)[1].mean()))
        off = W // 2 - cx
        c[:, off:off + x.shape[1]] = x
        return c
    a, b = place(a), place(b)
    return float((a & b).sum() / max(1, (a | b).sum())), a, b


def save_mask(photo, out_dir, rid):
    im = np.asarray(Image.open(photo).convert("RGB")).astype(float) / 255
    mx, mn = im.max(2), im.min(2)
    sat = (mx - mn) / (mx + 1e-6)
    m = ndi.binary_opening((mx < 0.45) & (sat < 0.40), iterations=3)
    lab, n = ndi.label(m)
    big = int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))) + 1
    m = ndi.binary_fill_holes(ndi.binary_closing(lab == big, iterations=8))
    Image.fromarray(((~m) * 255).astype(np.uint8)).save(os.path.join(out_dir, f"{rid}.mask.png"))
    ov = (im * 255).astype(np.uint8)
    ov[m] = (ov[m] * 0.4 + np.array([255, 0, 0]) * 0.6).astype(np.uint8)
    Image.fromarray(ov).save(os.path.join(out_dir, f"{rid}.mask_overlay.jpg"), quality=85)


def main():
    a = sys.argv[1:]
    if "--save-mask" in a:
        i = a.index("--save-mask")
        save_mask(a[i + 1], a[1], a[i + 2])
        print(f"Score: mask {a[i + 2]} -> {a[1]}")
        return
    card = json.load(open(a[0]))
    refs, rnd = a[1], a[2]
    stats = json.load(open(os.path.join(rnd, "stats.json")))
    review = {}
    if os.path.exists(os.path.join(rnd, "review.json")):
        review = json.load(open(os.path.join(rnd, "review.json")))
    side = load_mask(os.path.join(rnd, "outline_side.png"))
    edge = load_mask(os.path.join(rnd, "outline_edge.png"))
    mm_px = json.load(open(os.path.join(rnd, "outline_side.json")))["ortho_scale_mm"] / side.shape[1]
    ours = proportions(side)
    ref_props = {}
    for r in card["references"]:
        p = os.path.join(refs, f"{r['id']}.mask.png")
        if r.get("mask") and os.path.exists(p):
            rm = load_mask(p)
            rw = whole(rm)
            ref_props[r["id"]] = {**proportions(rm), **shape(rm), "top_aspect": rw.shape[0] / rw.shape[1]}

    out = {"part": card["part"], "round": os.path.basename(os.path.normpath(rnd)), "sizes": [], "features": []}
    # sizes
    rows = np.nonzero(side.any(1))[0]
    socks = stats["sockets"]
    sh = shape(side)
    top_p = os.path.join(rnd, "outline_top.png")
    top = load_mask(top_p) if os.path.exists(top_p) else None
    if top is not None and whole(top).shape[0] > whole(top).shape[1]:
        top = top.T                        # the straight-down camera's roll is arbitrary: lay the long side across
    tw = whole(top) if top is not None else None
    measured = {
        "across": tw.shape[1] * mm_px if tw is not None else None,         # top view, the long side
        "depth": tw.shape[0] * mm_px if tw is not None else None,          # top view, the short side
        "top_aspect": tw.shape[0] / tw.shape[1] if tw is not None else None,
        "axles": abs(socks["AxleL"][1] - socks["AxleR"][1]) if "AxleL" in socks else None,
        "length": sh["w_full_px"] * mm_px,
        "height": sh["h_full_px"] * mm_px,
        "width": whole(edge).shape[1] * mm_px,
        "aspect_full": sh["aspect_full"],
        "foot": sh["foot"],
        "waist": sh["waist"],
        "overall": (ours["bot"] - rows.min() + 1) * mm_px,
        "overall_all": (rows.max() - rows.min() + 1) * mm_px,        # top of the shackle to the lowest point (a becket)
        "sheave": abs(socks["LineIn"][0] - socks["LineOut"][0]) if "LineIn" in socks else None,
        "sheave2": abs(socks["LineIn2"][0] - socks["LineOut2"][0]) if "LineIn2" in socks else None,   # a fiddle's small sheave
        "aspect": ours["aspect"],
        "head": ours["head"],
        "thick": body(edge)[0].shape[1] * mm_px,
    }
    ok_sizes = True
    for s in card["sizes"]:
        got = measured.get(s["id"])
        tgt = s["target"]
        if isinstance(tgt, str) and tgt.startswith("ref:"):
            tgt = ref_props.get(tgt[4:], {}).get(s["id"])
        err = None if (tgt is None or got is None) else (got - tgt) / tgt
        passed = None if err is None or s["tol"] is None else bool(abs(err) <= s["tol"])
        ok_sizes &= passed is not False
        out["sizes"].append({"id": s["id"], "name": s["name"], "target": tgt, "got": got, "err": err, "tol": s["tol"], "pass": passed})
    # outline
    o = card.get("outline")
    out["outline"] = None
    if o and o["ref"] in ref_props:
        cut = whole if o.get("whole") else (lambda m: body(m)[0])
        ref_b = cut(load_mask(os.path.join(refs, f"{o['ref']}.mask.png")))
        ours_m = {"side": side, "edge": edge, "top": top}[o.get("view", "side")]
        v, A, B = iou(cut(ours_m), ref_b)
        if o.get("flip"):                       # a view whose up/down is only the camera's convention (top views)
            v2, A2, B2 = iou(cut(ours_m[::-1]), ref_b)
            if v2 > v:
                v, A, B = v2, A2, B2
        out["outline"] = {"ref": o["ref"], "iou": v, "pass": v >= o["pass"], "target": o["pass"]}
        vis = np.full(A.shape + (3,), 255, np.uint8)
        vis[A & ~B] = (40, 90, 220)      # ours only: blue
        vis[B & ~A] = (230, 60, 50)      # reference only: red
        vis[A & B] = (60, 60, 60)
        Image.fromarray(vis).save(os.path.join(rnd, "outline_compare.png"))
    # features
    objs = set(stats["objects"])
    ticks = review.get("ticks", {})
    n_ok = 0
    for f in card["features"]:
        auto = None
        if "objects" in f:
            auto = all(any(x == want or x.startswith(want) for x in objs) for want in f["objects"])
        if "slots" in f:
            s_ok = all(w in stats["slots"] for w in f["slots"]) and "(empty)" not in stats["slots"]
            auto = s_ok if auto is None else auto and s_ok
        man = ticks.get(f["id"]) if f.get("manual") else None
        passed = bool((auto is not False) and (man is not False) and (auto is not None or man is not None))
        n_ok += passed
        out["features"].append({"id": f["id"], "text": f["text"], "auto": auto, "manual": man, "pass": passed})
    # budget
    b = card["budget"]
    out["budget"] = {"tris": stats["tris"], "tris_max": b["tris"], "slots": len(stats["slots"]), "slots_max": b["slots"],
                     "pass": stats["tris"] <= b["tris"] and len(stats["slots"]) <= b["slots"] and "(empty)" not in stats["slots"]}
    out["review"] = review.get("blind")
    # a card without an outline reference ("outline": null) reports the outline as not checked (None), not failed
    out["pass"] = {"sizes": ok_sizes, "outline": None if not o else bool(out["outline"] and out["outline"]["pass"]),
                   "features": n_ok == len(card["features"]), "budget": out["budget"]["pass"],
                   "blind": review.get("blind", {}).get("pass")}
    json.dump(out, open(os.path.join(rnd, "score.json"), "w"), indent=1, default=lambda v: v.item())

    print(f"Score: {card['part']} {out['round']}")
    for s in out["sizes"]:
        g = "-" if s["got"] is None else f"{s['got']:.3f}" if s["got"] < 5 else f"{s['got']:.1f}"
        t = "-" if s["target"] is None else f"{s['target']:.3f}" if s["target"] < 5 else f"{s['target']:.1f}"
        e = "" if s["err"] is None else f"{s['err'] * 100:+.1f}%"
        print(f"  size  {s['id']:8s} got {g:>7s} target {t:>7s} {e:>7s}  {'PASS' if s['pass'] else 'fail' if s['pass'] is False else 'info'}")
    if out["outline"]:
        print(f"  outline vs {out['outline']['ref']}: {out['outline']['iou'] * 100:.1f}% overlap (pass {o['pass'] * 100:.0f}%)")
    elif not o:
        print("  outline not checked: the card has no square-on reference")
    print(f"  features {n_ok}/{len(card['features'])}: missing {[f['id'] for f in out['features'] if not f['pass']]}")
    print(f"  budget {stats['tris']} tris / {b['tris']}, {len(stats['slots'])} slots {stats['slots']}")
    print(f"  checks {out['pass']}")


if __name__ == "__main__":
    main()
