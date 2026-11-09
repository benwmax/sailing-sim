"""Measure the club-dock CC0 albedo scans (Poly Haven) for the dock texture loop: Lab mean, mottle and real size.

    python Tools/texloop/dock/measure_refs.py      # -> Tools/texloop/targets/dock.json (and prints a table)

The scans are albedo maps (no lighting), so no grey card is needed: the mean Lab is the surface's own colour. Each ref in
Tools/texloop/refs/dock.json names its Poly Haven id; the 1k diffuse JPG is fetched to the git-ignored
Data/Reference/raw/textures/Dock/<id>.jpg. The real size comes from the Poly Haven API (`dimensions`, mm).
"""
import json
import os
import sys
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from measure import srgb_to_lab, box_blur  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RAW = os.path.join(REPO, "Data", "Reference", "raw", "textures", "Dock")
REFS = os.path.join(os.path.dirname(HERE), "refs", "dock.json")
OUT = os.path.join(os.path.dirname(HERE), "targets", "dock.json")


def fetch(pid):
    path = os.path.join(RAW, pid + ".jpg")
    if not os.path.exists(path):
        files = json.load(urllib.request.urlopen(f"https://api.polyhaven.com/files/{pid}", timeout=60))
        key = [k for k in files if k.lower() in ("diffuse", "diff")][0]
        os.makedirs(RAW, exist_ok=True)
        urllib.request.urlretrieve(files[key]["1k"]["jpg"]["url"], path)
    return path


def board_pitch(L, size_mm, axis):
    """The strongest repeat across the boards (FFT of the mean profile), in cm: the board width plus its gap."""
    prof = L.mean(axis=1 - axis)
    prof = prof - prof.mean()
    sp = np.abs(np.fft.rfft(prof * np.hanning(len(prof))))
    f = np.arange(len(sp))
    ok = (f >= 3) & (f <= 40)
    k = f[ok][np.argmax(sp[ok])]
    return size_mm / 10.0 / k


def numbers(path, size_mm=None, axis=None):
    rgb = np.asarray(Image.open(path).convert("RGB"), np.float32) / 255.0
    lab = srgb_to_lab(rgb)
    L = lab[..., 0]
    k = max(3, L.shape[0] // 20)
    mottle = float(np.std(L - box_blur(L, k)))
    out = {"L": round(float(L.mean()), 1), "a": round(float(lab[..., 1].mean()), 1), "b": round(float(lab[..., 2].mean()), 1),
           "L_sd": round(float(L.std()), 1), "mottle": round(mottle, 1),
           "dark_share": round(float((L < L.mean() - 15).mean()), 3)}
    if size_mm and axis is not None:
        out["pitch_cm"] = round(board_pitch(L, size_mm, axis), 1)
    return out


def main():
    refs = json.load(open(REFS))
    rows = {}
    for r in refs["refs"]:
        if r.get("source") != "polyhaven":
            continue
        path = fetch(r["id"])
        size = r.get("size_mm")
        rows[r["id"]] = dict(surface=r["surface"], level=r["level"], **numbers(path, size, r.get("board_axis")))
        print(f"{r['surface']:8s} {r['level']:6s} {r['id']:28s} " + " ".join(f"{k}={v}" for k, v in rows[r['id']].items() if k not in ("surface", "level")))
    # per surface and level: the median of its refs
    targets = {}
    for sid in sorted({v["surface"] for v in rows.values()}):
        targets[sid] = {}
        for lv in ("L0", "L1", "L2", "L3", "L4"):
            vs = [v for v in rows.values() if v["surface"] == sid and lv in v["level"].split("-")]
            if vs:
                targets[sid][lv] = {k: round(float(np.median([v[k] for v in vs])), 1) for k in ("L", "a", "b", "mottle")}
                targets[sid][lv]["n"] = len(vs)
    json.dump({"refs": rows, "targets": targets}, open(OUT, "w"), indent=1)
    print(json.dumps(targets, indent=1))


if __name__ == "__main__":
    main()
