"""Joins a sim reel shot's rendered passes into one seamless loop (docs/sim-reel/README.md).

compose(shot, pass_dirs, out_dir, ...) reads each pass's PNG frames (every `decimate`-th), builds the shot's frames by
its 'compose' rule and writes the loop's frames to out_dir (00000.png...):
- single: the one pass, with the telemetry overlay if asked;
- wipe:   the passes in order, each wiping over the one before at the given seconds along a slanted edge with a thin
          wire-blue line (the gallery's Wireframe -> Lit+Wire -> Lit);
- cuts:   each pass for each_s seconds in turn, with a short crossfade.
Then the tail (frames past `seconds`) is dissolved over the head, so the last frame runs into the first.
"""
import csv
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIRE_RGB = np.array([0.25, 0.75, 1.0])   # M_GalleryWire's colour
FONT = os.path.join(os.path.dirname(__file__), "..", "..", "Content", "UI", "Fonts", "SairaSemiCondensed-SemiBold.ttf")


def frames_of(pass_dir, decimate=1):
    names = sorted(n for n in os.listdir(pass_dir) if n.endswith(".png") and n[:-4].isdigit())
    return [os.path.join(pass_dir, n) for n in names][::max(1, decimate)]


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def wipe_mask(h, w, progress, angle_deg, soft=0.012):
    """The share of the next pass at each pixel: an edge sweeping left to right, leaning angle_deg off vertical.
    Returns the mask and the edge's distance field (screen widths) for the line."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    lean = math.tan(math.radians(angle_deg))
    d = (x + (h - y) * lean) / (w + h * lean)              # 0 at the bottom-left corner, 1 at the top-right
    edge = -0.05 + 1.1 * progress
    return smoothstep(edge + soft, edge - soft, d), d - edge


def telemetry_rows(path):
    with open(path) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]


def telemetry_at(rows, t):
    """The row nearest game time t, values averaged over 0.3 s so the numbers read like an instrument."""
    near = [r for r in rows if abs(r["time_s"] - t) <= 0.15] or [min(rows, key=lambda r: abs(r["time_s"] - t))]
    return {k: sum(r[k] for r in near) / len(near) for k in near[0]}


def draw_overlay(img, row, scale):
    """Heel, speed and wind from the run's own telemetry (the capture's <shot>.telemetry.csv): no faked HUD."""
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(pil, "RGBA")
    big = ImageFont.truetype(FONT, int(44 * scale))
    small = ImageFont.truetype(FONT, int(20 * scale))
    items = [("HEEL", f"{abs(row['heel_deg']):.0f}\N{DEGREE SIGN}"), ("SPEED", f"{row['stw_kn']:.1f} kn"),
             ("TRUE WIND", f"{row['tws_kn']:.0f} kn"), ("WIND ANGLE", f"{abs(row['twa_deg']):.0f}\N{DEGREE SIGN}")]
    x, y = int(48 * scale), pil.height - int(110 * scale)
    d.rectangle([x - int(20 * scale), y - int(18 * scale), x + int(4 * 190 * scale), pil.height - int(30 * scale)], fill=(8, 16, 24, 110))
    for label, value in items:
        d.text((x, y), label, font=small, fill=(200, 225, 240, 230))
        d.text((x, y + int(22 * scale)), value, font=big, fill=(255, 255, 255, 240))
        x += int(190 * scale)
    d.text((pil.width - int(48 * scale), pil.height - int(40 * scale)), "simulation telemetry", font=small,
           fill=(200, 225, 240, 160), anchor="rs")
    return np.asarray(pil, dtype=np.float32) / 255.0


def compose(shot, pass_dirs, out_dir, fps, decimate=1, telemetry=None, telemetry_t0=0.0, telemetry_dt=None, log=print):
    """pass_dirs: the passes' frame folders in the shot's order. telemetry: a csv path (overlay 'telemetry'), whose
    game time at output frame i is telemetry_t0 + i * telemetry_dt."""
    rule = shot["compose"]
    passes = [frames_of(d, decimate) for d in pass_dirs]
    n_loop = round(shot["seconds"] * fps)
    total = min(len(p) for p in passes)
    tail = max(0, min(total - n_loop, round(shot.get("tail", 0) * fps)))
    if total < n_loop:
        raise RuntimeError(f"{shot['_name']}: {total} frames rendered, the loop needs {n_loop}")
    h, w, _ = load(passes[0][0]).shape
    rows = telemetry_rows(telemetry) if telemetry else None
    scale = h / 1080.0

    def frame(i):
        t = i / fps
        kind = rule["type"]
        if kind == "single":
            img = load(passes[0][i])
        elif kind == "wipe":
            img = load(passes[0][i])
            for j, at in enumerate(rule["at"]):
                p = (t - at) / rule["wipe_s"]
                if p <= 0.0:
                    break
                nxt = load(passes[j + 1][i])
                if p >= 1.0:
                    img = nxt
                    continue
                m, dist = wipe_mask(h, w, p, rule.get("angle_deg", 15))
                img = img * (1 - m[..., None]) + nxt * m[..., None]
                glow = np.exp(-(dist / 0.0025) ** 2)[..., None] * 0.9
                img = img * (1 - glow) + WIRE_RGB * glow
        elif kind == "cuts":
            each, xf = rule["each_s"], rule.get("crossfade_s", 0.0)
            j = min(int(t // each), len(passes) - 1)
            img = load(passes[j][i])
            into = t - (j + 1) * each + xf     # fading into the next pass over the last xf seconds of this one
            if xf > 0 and into > 0 and j + 1 < len(passes):
                a = smoothstep(0.0, xf, into)
                img = img * (1 - a) + load(passes[j + 1][i]) * a
        else:
            raise ValueError(f"unknown compose type {kind}")
        if rows:
            img = draw_overlay(img, telemetry_at(rows, telemetry_t0 + i * telemetry_dt), scale)
        return img

    os.makedirs(out_dir, exist_ok=True)
    for i in range(n_loop):
        img = frame(i)
        if i < tail:
            # The tail dissolves over the head: frame 0 is mostly the frame after the loop's last.
            a = (i + 1) / (tail + 1)
            img = frame(n_loop + i) * (1 - a) + img * a
        Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out_dir, f"{i:05d}.png"))
        if i % 60 == 0:
            log(f"  composed {i}/{n_loop}")
    return n_loop
