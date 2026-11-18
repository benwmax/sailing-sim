"""Track A: the environment loop's six checks for the ground set.

    python3 -I Tools/envloop/ground/checks.py --renders Artifacts/envloop/ground/r1 [--reviews Tools/envloop/ground/reviews/r1.json]

Writes Tools/envloop/ground/scores/<round>.json and prints one line per check.
  size     each scan's real width is published (or estimated and said so), and every tier keeps the hero band's 1 cm per
           pixel; the smallest feature the card names spans 2 px or more at High
  colour   the prepared maps' means are the card's colours (exact by construction), and the card against the source
           scan's own calibrated colour (Lab dE, reported). PROVISIONAL until Bean's grey-card ground photos
  repeat   no visible repeat in a 40 m frame: normalised autocorrelation of the top-down 40 m renders, highest peak
           off the centre (past 1 m) under 0.35; the same for the scan simply tiled, for comparison
  variety  all eight surfaces drawn on the test shore (each winning 0.3% or more of a station area), and each kind of bank
           shows at least three
  blind    from the reviews file: new beats old for 2 of 3 reviewers in every view, and "photo or game" answers
  budget   texture memory per tier (8-slice arrays: BC1 colour, BC5 normal, BC1 RHA, with mips) against the plan's
           share; samples per pixel; frame time is the Mac's (after Nov 21)
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import ground_material as gm  # noqa: E402
import scene as sc  # noqa: E402
import pack as packs  # noqa: E402

PREP = packs.prep_dir()
RAW = packs.raw_dir()


def lab(rgb_lin):
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = np.asarray(rgb_lin) @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def check_size(card):
    rows, ok = {}, True
    for s in card["surfaces"]:
        px_m = {t: v["res"] / s["tile_m"] for t, v in card["tiers"].items() if v["res"]}
        feat_px_high = s["feature_mm"][0] / 1000 * px_m["High"]
        good = min(px_m.values()) >= 100 and feat_px_high >= 2
        ok &= good
        rows[s["id"]] = dict(tile_m=s["tile_m"], published=s["tile_m_known"], px_per_m={k: round(v) for k, v in px_m.items()},
                             smallest_feature_px_high=round(feat_px_high, 1), ok=good)
    return dict(ok=ok, rows=rows)


def check_colour(card):
    rows = {}
    prep = json.load(open(os.path.join(PREP, "prep.json"))) if os.path.exists(os.path.join(PREP, "prep.json")) else {}
    exact = True
    for s in card["surfaces"]:
        tgt = np.array(s["albedo_linear"]["summer"])
        got = prep.get(s["id"], {}).get("1024", {}).get("albedo_mean")
        if got is not None:
            exact &= bool(np.abs(np.array(got) - tgt).max() < 0.002)
        src = os.path.join(RAW, s["id"])
        scan_mean = None
        for f in os.listdir(src) if os.path.isdir(src) else []:
            if f.startswith("color."):
                a = np.asarray(Image.open(os.path.join(src, f)).convert("RGB").resize((256, 256)), np.float32) / 255
                a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
                scan_mean = a.mean(axis=(0, 1))
        rows[s["id"]] = dict(card=[round(float(v), 3) for v in tgt], prepared=got,
                             scan=None if scan_mean is None else [round(float(v), 3) for v in scan_mean],
                             dE_card_vs_scan=None if scan_mean is None else round(float(np.linalg.norm(lab(tgt) - lab(scan_mean))), 1))
    return dict(ok=exact, provisional=True, note="No grey-card ground photo yet: the card's colours are judged, not measured. "
                "dE against the scan shows how far each was moved from the scan to Texas.", rows=rows)


def autocorr_peak(img, metres=40.0, exclude_m=1.0, highpass_m=1.5):
    a = np.asarray(img.convert("L"), np.float32)
    n = a.shape[0]
    # High-pass at 1.5 m: a repeat is the texture's own pattern coming back; the zones, the wash and a tree's shade
    # are meant to be large and are not repeats.
    from scipy import ndimage
    a = a - ndimage.gaussian_filter(a, highpass_m * n / metres, mode="wrap")
    f = np.fft.fft2(a)
    ac = np.fft.ifft2(f * np.conj(f)).real
    ac /= ac[0, 0]
    yy, xx = np.meshgrid(np.fft.fftfreq(n) * n, np.fft.fftfreq(n) * n, indexing="ij")
    r = np.hypot(xx, yy) * metres / n
    return float(ac[r > exclude_m].max())


def check_repeat(renders):
    rows, ok = {}, True
    for name in ("lawn", "yard", "field", "woods"):
        p = os.path.join(renders, f"top40_{name}.png")
        if not os.path.exists(p):
            continue
        peak = autocorr_peak(Image.open(p))
        rows[name] = round(peak, 3)
        ok &= peak < 0.35
    # The control: the lawn scan tiled across 40 m with nothing done to it.
    d = np.load(os.path.join(PREP, "lawn_512.npz"))["albedo"].astype(np.float32)
    reps = int(round(40.0 / gm.TILE[gm.S["lawn"]]))
    tiled = np.tile(d, (reps, reps, 1))
    tiled = Image.fromarray((np.clip(tiled / tiled.max(), 0, 1) * 255).astype(np.uint8)).resize((640, 640))
    rows["control_plain_tiling"] = round(autocorr_peak(tiled), 3)
    return dict(ok=ok and bool(rows), limit=0.35, rows=rows)


def check_variety():
    scn = sc.Scene()
    out, ok = {}, True
    for st, x0 in {"club": (-80, -35), "cutbank": (-28, 18), "cove": (30, 90)}.items():
        xs = np.linspace(x0[0], x0[1], 120)
        ys = np.linspace(-10, 60, 140)
        X, Y = np.meshgrid(xs, ys)
        x, y = X.ravel(), Y.ravel()
        at = scn.attributes(x, y)
        P = np.stack([x, y, at["Z"]], -1)
        w = gm.weights(P, at["N"], at["C"], at["Near"], scn.water, at["Mown"])
        share = np.bincount(w.argmax(-1), minlength=8) / len(x)
        shown = [gm.IDS[i] for i in range(8) if share[i] > 0.003]     # 0.3%: about 25 m² of a 60 x 70 m frame (the shingle band is narrow)
        out[st] = dict(shown=shown, share={gm.IDS[i]: round(float(share[i]), 3) for i in range(8)})
        ok &= len(shown) >= 3
    every = set(sum((v["shown"] for v in out.values()), []))
    out["all_eight"] = len(every) == 8
    return dict(ok=ok and out["all_eight"], rows=out)


def check_blind(reviews_path):
    if not reviews_path or not os.path.exists(reviews_path):
        return dict(ok=None, note="no reviews yet")
    r = json.load(open(reviews_path))
    views = {}
    for rev in r["reviewers"]:
        for v, ans in rev["answers"].items():
            views.setdefault(v, []).append(ans)
    rows, ok = {}, True
    for v, answers in views.items():
        wins = sum(1 for a in answers if a["better"] == "after")
        photo = sum(1 for a in answers if a.get("after_photo_or_game") == "photo")
        rows[v] = dict(after_wins=f"{wins}/{len(answers)}", after_called_photo=f"{photo}/{len(answers)}")
        ok &= wins * 3 >= 2 * len(answers)
    return dict(ok=ok, rows=rows)


def check_budget(card):
    rows = {}
    for t, v in card["tiers"].items():
        res = v["res"]
        if not res:
            rows[t] = dict(mb=0)
            continue
        bpp = 0.5 + 1.0 + 0.5        # BC1 colour, BC5 normal, BC1 RHA
        mb = 8 * res * res * bpp * 4 / 3 / 2 ** 20
        rows[t] = dict(res=res, mb=round(mb, 1))
    return dict(ok=rows["Medium"]["mb"] <= 8 and rows["High"]["mb"] <= 32, rows=rows,
                fetches_inside_150m=12, fetches_past_150m=0, note="frame time: Mac gate after Nov 21 (plan share: Medium 1.5 ms, High 3.0 ms for the whole shore)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", default=os.path.join(REPO, "Artifacts", "envloop", "ground", "r1"))
    ap.add_argument("--reviews", default="")
    ap.add_argument("--round", default="")
    ap.add_argument("--pack", default=None)
    args = ap.parse_args()
    global PREP, RAW
    card = packs.load(args.pack)
    gm.use_pack(args.pack)
    PREP, RAW = packs.prep_dir(args.pack), packs.raw_dir(args.pack)
    rnd = args.round or os.path.basename(os.path.normpath(args.renders))
    res = dict(round=rnd, size=check_size(card), colour=check_colour(card), repeat=check_repeat(args.renders),
               variety=check_variety(), blind=check_blind(args.reviews), budget=check_budget(card))
    os.makedirs(os.path.join(HERE, "scores"), exist_ok=True)
    res["pack"] = card["pack"]
    json.dump(res, open(os.path.join(HERE, "scores", f"{rnd}.json"), "w"), indent=1)
    for k in ("size", "colour", "repeat", "variety", "blind", "budget"):
        v = res[k]
        flag = {True: "PASS", False: "FAIL", None: "WAIT"}[v["ok"]]
        extra = " (provisional)" if v.get("provisional") else ""
        print(f"{flag} {k}{extra}")


if __name__ == "__main__":
    main()
