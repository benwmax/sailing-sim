"""Lens drops (feedback #28, docs/storm-look/lens-water/): an offline preview of M_LensWater's LENS_CODE (make_materials.py),
the drops as #707 drew them and as they are drawn now, over a plain storm frame (sky, horizon, a sail), so a change to
where the drops sit, how many there are and how they live can be judged without the editor. A numpy port of the shader:
the hash, the lattices and the drop's lens are the same; no tonemapping, film or splash layer.

  python3 -I Tools/water/lens_preview.py <out dir> [rain=1] [air=0]

writes <out dir>/lens_preview.png (rows: before, now; columns: three moments 2 s apart) and lens_preview_wind.png (now,
with the air over the glass at 12 m/s: shorter lives, drops running). The same arguments give the same image."""
import sys
import numpy as np
from PIL import Image

W, H = 960, 540
LENS_FIELD = 4.0


def scene():
    y = np.linspace(0.0, 1.0, H)[:, None] * np.ones((1, W))
    x = np.ones((H, 1)) * np.linspace(0.0, 1.0, W)[None, :]
    sky = np.stack([0.30 + 0.10 * (1 - y), 0.33 + 0.10 * (1 - y), 0.40 + 0.10 * (1 - y)], -1)
    sea = np.stack([0.06 + 0.04 * y, 0.07 + 0.04 * y, 0.09 + 0.04 * y], -1)
    img = np.where((y < 0.45)[..., None], sky, sea)
    # a sail, so the drops' upside-down view has something to show
    sail = (x > 0.46) & (x < 0.46 + 0.12 * (y - 0.1) / 0.5) & (y > 0.1) & (y < 0.6)
    img[sail] = (0.75, 0.75, 0.73)
    hull = (y > 0.6) & (y < 0.64) & (x > 0.43) & (x < 0.62)
    img[hull] = (0.85, 0.85, 0.85)
    return img


def sample(img, u, v):
    x = np.clip((u * W).astype(int), 0, W - 1)
    y = np.clip((v * H).astype(int), 0, H - 1)
    return img[y, x]


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def hash32(h):
    h = h.astype(np.uint32)
    h ^= h >> np.uint32(16)
    h = (h * np.uint32(0x7FEB352D)).astype(np.uint32)
    h ^= h >> np.uint32(15)
    h = (h * np.uint32(0x846CA68B)).astype(np.uint32)
    h ^= h >> np.uint32(16)
    return h


def unit(h):
    return (h >> np.uint32(8)).astype(np.float64) / 16777216.0


def grid():
    v, u = np.mgrid[0:H, 0:W]
    return (u + 0.5) / W, (v + 0.5) / H


def lens_before(T, rain, wind):
    """#707's LENS_CODE (sin hash, lattice scrolling with the wind, one draw per cell for ever)."""
    u, v = grid()
    aspect = W / H
    wz = np.hypot(*wind)
    wdir = np.array(wind) / max(wz, 1e-3)
    off = np.zeros((H, W, 2)); mask = np.zeros((H, W)); gain = np.ones((H, W))
    for layer in range(3):
        scale = 9.0 + 9.0 * layer
        speed = wz * (0.08 + 0.05 * layer)
        px = u * aspect * scale - wdir[0] * T * speed * scale
        py = v * scale - wdir[1] * T * speed * scale
        chance = rain * (0.18 + 0.06 * layer)
        bx, by = np.floor(px - 0.5), np.floor(py - 0.5)
        for iy in range(2):
            for ix in range(2):
                cx, cy = bx + ix, by + iy
                h = np.modf(np.sin((cx + layer * 17.0) * 127.1 + (cy + layer * 17.0) * 311.7) * 43758.5453)[0] % 1.0
                c0 = np.modf(h * 13.1)[0] * 0.6 + 0.2
                c1 = np.modf(h * 7.3)[0] * 0.6 + 0.2
                dx, dy = px - cx - c0, py - cy - c1
                along = dx * wdir[0] + dy * wdir[1]
                across = -dx * wdir[1] + dy * wdir[0]
                rad = 0.1 + 0.12 * np.modf(h * 3.3)[0]
                stretch = np.minimum(1.0 + 2.0 * np.clip(wz * 0.15, 0, 1) * np.clip(along * 4.0 + 0.5, 0, 1), 0.66 / rad)
                qx, qy = along / stretch / rad, across / rad
                r = np.hypot(qx, qy)
                life = 1.0 - 0.6 * np.modf(T * 0.2 + h)[0]
                drop = smoothstep(1.0, 0.9, r) * life * (h < chance)
                take = drop > mask
                g = np.clip(1.0 - np.hypot(qx + 0.25, qy + 0.45) / 0.2, 0, 1)
                off[take, 0] = (dx / (scale * aspect) * (1 + LENS_FIELD) * drop)[take]
                off[take, 1] = (dy / scale * (1 + LENS_FIELD) * drop)[take]
                gain[take] = ((1.0 - 0.6 * smoothstep(0.55, 0.95, r)) + 1.2 * g * g)[take]
                mask[take] = drop[take]
    return off, mask, gain


def lens_now(T, rain, wind):
    """LENS_CODE now, line for line (no splash layer, no film)."""
    u, v = grid()
    aspect = W / H
    wz = np.hypot(*wind)
    wdir = np.array([wind[0], wind[1] + 1e-3]); wdir /= np.hypot(*wdir)
    share = np.clip((wz - 3.0) / 12.0, 0, 1)
    off = np.zeros((H, W, 2)); mask = np.zeros((H, W)); gain = np.ones((H, W))
    for layer in range(3):
        scale = (11.0, 17.0, 26.0)[layer]
        chance = (0.16, 0.13, 0.10)[layer] * min(max(rain, 0.0), 1.0)
        if chance < 0.002:
            continue
        visible = 0.9 + (0.4 - 0.9) * share
        ca, sa = np.cos(0.7 * layer), np.sin(0.7 * layer)
        sx, sy = u * aspect * scale, v * scale
        px = ca * sx - sa * sy + 0.37 * layer
        py = sa * sx + ca * sy + 0.61 * layer
        wl = np.array([ca * wdir[0] - sa * wdir[1], sa * wdir[0] + ca * wdir[1]])
        bx, by = np.floor(px - 0.5), np.floor(py - 0.5)
        for iy in range(2):
            for ix in range(2):
                cx, cy = bx + ix, by + iy
                seed = ((cx.astype(np.int64).astype(np.uint32) * np.uint32(0x8DA6B343))
                        ^ (cy.astype(np.int64).astype(np.uint32) * np.uint32(0xD8163841))
                        ^ np.uint32((layer * 0xCB1AB31F) & 0xFFFFFFFF)).astype(np.uint32)
                h = hash32(seed); r0 = unit(h)
                h = hash32(h); r1 = unit(h)
                period = 4.5 * (0.6 + 0.8 * r0)
                tt = T / period + r1
                epoch = np.floor(tt); age = tt - epoch
                h = hash32(seed ^ ((epoch + 1).astype(np.int64).astype(np.uint32) * np.uint32(0x9E3779B9)).astype(np.uint32))
                r = [r0, r1, unit(h)]
                for _ in range(3, 12):
                    h = hash32(h); r.append(unit(h))
                present = np.clip((chance - r[2]) / 0.05, 0, 1)
                life = np.clip(age / 0.03, 0, 1) * (1.0 - smoothstep(0.6 * visible, visible, age))
                rad = (0.07 + 0.23 * r[3] ** 2) * (1.0 - 0.35 * smoothstep(0.5 * visible, visible, age))
                aspd = 0.8 + 0.25 * r[8]
                c0, c1 = r[4] * 0.6 + 0.2, r[5] * 0.6 + 0.2
                runs = r[6] < 0.7 * share
                rx = (0.8 - c0) / max(wl[0], 1e-4) if wl[0] > 0 else (c0 - 0.2) / max(-wl[0], 1e-4)
                ry = (0.8 - c1) / max(wl[1], 1e-4) if wl[1] > 0 else (c1 - 0.2) / max(-wl[1], 1e-4)
                run = np.where(runs, np.minimum(rx, ry) * (0.5 + 0.5 * r[7]) * smoothstep(0.15, visible, age), 0.0)
                c0, c1 = c0 + wl[0] * run, c1 + wl[1] * run
                dx, dy = px - cx - c0, py - cy - c1
                along = dx * wl[0] + dy * wl[1]
                across = -dx * wl[1] + dy * wl[0]
                tail = np.where(runs, 2.0, 0.6 * share)
                stretch = np.minimum(1.0 + tail * np.clip(along * 4.0 + 0.5, 0, 1), 0.66 / (rad * 1.1))
                qx, qy = along / stretch / rad, across / aspd / rad
                th = np.arctan2(qy, qx + 1e-5)
                rr = np.hypot(qx, qy) / (1.0 + 0.06 * np.sin(3 * th + 6.2832 * r[7]) + 0.04 * np.sin(5 * th + 6.2832 * r[9]))
                drop = smoothstep(1.0, 0.9, rr) * life * present
                take = drop > mask
                dsx, dsy = ca * dx + sa * dy, -sa * dx + ca * dy
                gx = dsx / rad - (-0.25 + 0.2 * (r[10] - 0.5))
                gy = dsy / rad - (-0.45 + 0.15 * (r[11] - 0.5))
                g = np.clip(1.0 - np.hypot(gx, gy) / 0.2, 0, 1)
                off[take, 0] = (dsx / (scale * aspect) * (1 + LENS_FIELD) * drop)[take]
                off[take, 1] = (dsy / scale * (1 + LENS_FIELD) * drop)[take]
                gain[take] = ((1.0 - 0.6 * smoothstep(0.55, 0.95, rr)) + (0.8 + 0.8 * r[10]) * g * g)[take]
                mask[take] = drop[take]
    return off, mask, gain


def render(img, lens):
    off, mask, gain = lens
    u, v = grid()
    su, sv = u - off[..., 0], v - off[..., 1]
    su = 1.0 - np.abs(1.0 - np.abs(su)); sv = 1.0 - np.abs(1.0 - np.abs(sv))
    refr = sample(img, su, sv) * gain[..., None]
    out = img * (1 - mask[..., None]) + refr * mask[..., None]
    return (np.clip(out, 0, 1) ** (1 / 1.4) * 255).astype(np.uint8)


def main():
    out = sys.argv[1]
    kv = dict(a.split("=") for a in sys.argv[2:])
    rain = float(kv.get("rain", 1.0)); air = float(kv.get("air", 0.0))
    img = scene()
    wind = (0.2 * air, air + 3.0)   # WindScreen: the air on the glass in screen axes, plus 3 m/s of gravity down the screen
    times = (20.0, 22.0, 24.0)
    rows = [[render(img, f(t, rain, wind)) for t in times] for f in (lens_before, lens_now)]
    sheet = np.concatenate([np.concatenate(r, 1) for r in rows], 0)
    Image.fromarray(sheet).save(f"{out}/lens_preview.png")
    windy = (3.6, 12.0)
    row = [render(img, lens_now(t, rain, windy)) for t in times]
    Image.fromarray(np.concatenate(row, 1)).save(f"{out}/lens_preview_wind.png")


if __name__ == "__main__":
    main()
