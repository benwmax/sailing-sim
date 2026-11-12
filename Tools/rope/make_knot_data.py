#!/usr/bin/env python3
"""Rope realism phase 2 (docs/rope-lay/): bakes the knots the player's boat shows into RopeKnotData.inl.

Each knot is a rope's centreline in units of the rope's diameter, tied loose from a hand-laid path and then pulled tight
here by a small position-based solver (the rope inextensible, its parts kept a diameter apart, the standing part pulled,
a bowline's loop held round the clew's bar), so it comes out jammed the way a real knot sets. The game places the
centreline at a fitting, scaled by the rope's diameter, and draws it as part of the live rope (BoatModelVisuals.cpp).

Frame: +X along the standing part (towards the live rope), +Z up (the sail's plane at a clew), +Y = Z x X.
  Bowline: the loop round a bar along Z at the origin (a jib's clew cringle); the points run from the tail's end round the
           knot and the loop to the standing part's exit, the last point, where the live sheet starts along +X.
  Figure eight (stopper): on a rope's end; the points run from the standing part's exit at the origin (the live line
           ends there, coming in along -X... the knot lies beyond it along -X) to the tail's end.

Run: python3 Tools/rope/make_knot_data.py [--png <dir>]  (writes Source/SailingPhysics/Public/RopeKnotData.inl;
deterministic: the same file every run). No Unreal, numpy only (Pillow for the --png previews).
"""
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "Source", "SailingPhysics", "Public", "RopeKnotData.inl")

H = 0.2            # solver spacing (diameters)
CONTACT = 1.0      # parts of the rope kept a diameter apart (centre to centre)
OUT_STEP = 0.45    # the baked points' spacing (12 sides round a 1-diameter rope; 0.32 cost the High crew view 0.2 ms of game thread, #649)


def catmull(ctrl, step):
    """A Catmull-Rom curve through the control points, resampled to an even spacing."""
    c = np.asarray(ctrl, float)
    p = np.vstack([c[0] * 2 - c[1], c, c[-1] * 2 - c[-2]])
    dense = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0.0, 1.0, 40, endpoint=False):
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (3 * p1 - p0 - 3 * p2 + p3) * t3))
    dense.append(c[-1])
    return resample(np.array(dense), step)


def resample(pts, step):
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(round(s[-1] / step)), 2)
    at = np.linspace(0.0, s[-1], n + 1)
    return np.stack([np.interp(at, s, pts[:, k]) for k in range(3)], axis=1)


def relax(p, pull, iters, bar=None, fixed_tail=False, gap=None):
    """Position-based tightening. pull: {index: direction} ends pulled outward each step (a small, fading rate), the rope
    inextensible, non-neighbouring parts kept CONTACT apart, a light smoothing, and an optional bar (a line along Z through
    the origin, radius bar) the rope can't enter."""
    p = p.copy()
    n = len(p)
    rest = np.linalg.norm(np.diff(p, axis=0), axis=1).mean()
    gap = gap or int(math.ceil(1.6 / rest))           # parts closer than this along the rope are neighbours
    idx = np.arange(n)
    far = np.abs(idx[:, None] - idx[None, :]) > gap
    for it in range(iters):
        rate = 0.02 * (1.0 - it / iters)
        for i, d in pull.items():
            p[i] += rate * np.asarray(d, float)
        for _ in range(4):
            # contacts (vectorised: each pair pushed apart half each)
            diff = p[:, None, :] - p[None, :, :]
            dist = np.linalg.norm(diff, axis=2) + 1e-12
            over = far & (dist < CONTACT)
            if over.any():
                push = np.where(over, (CONTACT - dist) * 0.5 / dist, 0.0)
                p += 0.5 * (push[:, :, None] * diff).sum(axis=1)
            # the bar
            if bar is not None:
                r = np.linalg.norm(p[:, :2], axis=1) + 1e-12
                inside = r < bar + 0.5
                p[inside, :2] *= ((bar + 0.5) / r[inside])[:, None]
            # inextensible (even segments, then odd ones: each a vectorised pass)
            for parity in (0, 1, 0, 1):
                i = np.arange(parity, n - 1, 2)
                d = p[i + 1] - p[i]
                L = np.linalg.norm(d, axis=1)
                corr = ((L - rest) / np.maximum(L, 1e-12) * 0.5)[:, None] * d
                p[i] += corr
                p[i + 1] -= corr
        # smoothing (not the ends)
        p[1:-1] += 0.03 * (0.5 * (p[:-2] + p[2:]) - p[1:-1])
    return p


def min_clearance(p, step):
    gap = int(math.ceil(1.6 / step))
    best = 1e9
    for i in range(len(p)):
        j = np.arange(i + gap + 1, len(p))
        if len(j):
            best = min(best, float(np.linalg.norm(p[j] - p[i], axis=1).min()))
    return best


def bowline():
    """A bowline tied loose round the clew's bar: the standing part comes in along -X, makes the small loop (the rabbit
    hole) with its outgoing part on top, runs down to the clew as the loop's first leg, round the bar, back as the second
    leg, up through the small loop, round behind the standing part and back down through the small loop, the tail lying
    inside the big loop beside the second leg."""
    ctrl = [
        (2.6, -0.9, -0.2),     # tail end (inside the loop, beside the second leg)
        (4.4, -0.5, -0.5),
        (6.0, 0.3, -1.0),      # down through the small loop (from above)
        (6.4, 0.5, 0.6),
        (7.4, 1.9, 0.7),       # round behind the standing part (on its +Y side)...
        (8.8, 2.0, 0.0),
        (9.6, 1.0, -1.1),      # ...under it...
        (8.8, -0.6, -0.4),
        (7.6, -1.0, 0.8),      # ...and over towards the small loop
        (6.4, -0.2, 1.1),
        (5.6, -0.4, -0.2),     # up through the small loop (from below)
        (4.6, -1.6, -1.0),
        (2.5, -2.3, -0.5),     # the second leg
        (0.4, -2.0, 0.0),
        (-1.4, 0.0, 0.0),      # round the bar
        (0.4, 2.0, 0.0),
        (3.0, 2.3, 0.0),       # the first leg
        (5.4, 2.1, 0.2),
        (6.8, 1.7, 0.4),       # into the small loop's crossing (on top)
        (7.6, 0.6, 0.6),
        (7.0, -1.0, 0.2),      # the small loop
        (5.2, -1.4, 0.0),
        (4.2, 0.0, -0.1),
        (5.2, 1.0, -0.3),
        (7.0, 0.8, -0.5),      # under its own crossing
        (9.0, 0.3, -0.2),
        (11.0, 0.0, 0.0),      # the standing part
        (16.0, 0.0, 0.0),
    ]
    p = catmull(ctrl, H)
    p = relax(p, {len(p) - 1: (1, 0, 0), 0: (-0.35, 0, 0)}, 900, bar=0.6)
    return p


def figure_eight():
    """A figure eight on a rope's end, tied loose the way it is tied: the standing part comes in along -X, makes a loop
    below it, the end goes once round the standing part (under it, then back over) and down through the loop, the tail
    leading out along -X; then pulled tight (the standing part one way, the tail the other)."""
    ctrl = [
        (14.0, 0.0, 0.0),      # the standing part
        (8.0, 0.0, 0.0),
        (4.6, 0.0, 0.1),
        (2.6, -0.4, 0.2),      # the loop, below the standing part
        (1.4, -1.6, 0.0),
        (2.6, -2.8, 0.0),
        (4.6, -2.4, -0.2),
        (5.6, -0.9, -0.6),
        (6.0, 0.0, -0.9),      # under the standing part
        (6.4, 1.4, -0.3),
        (5.2, 2.4, 0.3),       # round it...
        (3.6, 1.4, 0.8),
        (3.4, 0.0, 1.0),       # ...back over it
        (3.0, -1.2, 0.7),
        (2.8, -1.6, 0.0),      # down through the loop
        (2.2, -1.4, -0.8),
        (0.6, -0.6, -0.5),
        (-1.8, -0.2, 0.0),     # the tail
        (-4.0, 0.0, 0.0),
    ]
    p = catmull(ctrl, H)
    p = relax(p, {0: (1, 0, 0), len(p) - 1: (-1, 0, 0)}, 900)
    return p


def to_frame(p, standing_last):
    """Turns a relaxed knot into the game's frame: the standing part along +X, ending at the origin (stopper) or at its
    exit (bowline), its tangent there exactly +X."""
    p = p.copy()
    if standing_last:
        e, f = p[-1], p[-6]
    else:
        e, f = p[0], p[5]
    x = e - f
    x /= np.linalg.norm(x)
    up = np.array([0.0, 0.0, 1.0])
    y = np.cross(up, x)
    if np.linalg.norm(y) < 1e-6:
        y = np.array([0.0, 1.0, 0.0])
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    R = np.stack([x, y, z])
    return (p - (np.zeros(3) if standing_last else e)) @ R.T


def trim_standing(p, standing_last, keep):
    """Cuts the standing part to keep diameters past the knot body (the live rope takes over there), with a straight
    last stretch so the join is on its tangent."""
    q = p if standing_last else p[::-1]
    # the knot body ends where the standing part leaves the other parts' reach
    body_end = 0
    for i in range(len(q)):
        if min(np.linalg.norm(q[: max(i - 8, 1)] - q[i], axis=1)) < CONTACT * 1.4:
            body_end = i
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])
    stop = np.searchsorted(s, s[min(body_end, len(q) - 1)] + keep)
    q = q[: max(stop, body_end + 2)]
    return q if standing_last else q[::-1]


def bake():
    knots = {}
    b = bowline()
    b = trim_standing(b, True, 1.5)
    b = resample(b, OUT_STEP)
    # frame: the bar stays at the origin, the exit along +X
    exit_dir = b[-1] - b[-4]
    exit_dir /= np.linalg.norm(exit_dir)
    ang = math.atan2(exit_dir[1], exit_dir[0])
    c, s = math.cos(-ang), math.sin(-ang)
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    b = b @ Rz.T
    knots["Bowline"] = b
    f = figure_eight()
    f = trim_standing(f, False, 1.0)
    f = resample(f, OUT_STEP)
    f = to_frame(f, False)
    knots["FigureEight"] = f
    return knots


def write(knots):
    lines = [
        "// Generated by Tools/rope/make_knot_data.py (rope realism phase 2, docs/rope-lay/). Do not edit: edit the script.",
        "// Knot centrelines in rope diameters (RopeKnots.h has the frames).",
        "#pragma once",
    ]
    for name, p in knots.items():
        lines.append(f"inline constexpr int kKnot{name}Count = {len(p)};")
        lines.append(f"inline constexpr double kKnot{name}[kKnot{name}Count][3] = {{")
        for q in p:
            lines.append("\t{ %.4f, %.4f, %.4f }," % (q[0] + 0.0, q[1] + 0.0, q[2] + 0.0))
        lines.append("};")
    with open(OUT, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def png(knots, out_dir):
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    for name, p in knots.items():
        for view, (a, b, dep) in {"top": (0, 1, 2), "side": (0, 2, 1)}.items():
            S, W = 40, 900
            img = Image.new("RGB", (W, 500), (245, 245, 240))
            d = ImageDraw.Draw(img)
            pts = resample(p, 0.1)
            lo = pts.min(axis=0)
            hi = pts.max(axis=0)
            mid = 0.5 * (lo + hi)
            order = np.argsort(pts[:, dep] * (1 if view == "top" else -1))
            n = len(pts)
            for i in order:
                q = pts[i]
                x = W / 2 + (q[a] - mid[a]) * S
                y = 250 - (q[b] - mid[b]) * S
                shade = int(120 + 100 * (i / n))
                d.ellipse([x - S / 2, y - S / 2, x + S / 2, y + S / 2], fill=(shade, 60, 60), outline=(30, 20, 20))
            img.save(os.path.join(out_dir, f"{name}_{view}.png"))


def main():
    knots = bake()
    for name, p in knots.items():
        print(f"{name}: {len(p)} points, length {np.linalg.norm(np.diff(p, axis=0), axis=1).sum():.1f} d, "
              f"closest parts {min_clearance(p, OUT_STEP):.2f} d, extent {np.round(p.max(axis=0) - p.min(axis=0), 1)}")
    write(knots)
    if "--png" in sys.argv:
        png(knots, sys.argv[sys.argv.index("--png") + 1])


if __name__ == "__main__":
    main()
