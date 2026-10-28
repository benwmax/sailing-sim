"""Storm water (docs/storm-water/): the foam mask's autocorrelation over a patch of open sea, from a -SailingDebugFoam=1
still taken straight down (the whitecaps white on black). A pattern that repeats shows as a peak away from zero lag; the
23 m chop tile (FWaveDetail) does. Prints the strongest peak past 3 m along each image axis and writes a plot.

    python Tools/water/foam_autocorr.py <mask.png> <metres across the frame> <out.png> [x0 y0 x1 y1 crop in pixels]
"""
import sys

import numpy as np
from PIL import Image, ImageDraw


def main():
    path, across, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    im = Image.open(path).convert("L")
    m_per_px = across / im.width
    if len(sys.argv) >= 8:
        im = im.crop(tuple(int(v) for v in sys.argv[4:8]))
    a = (np.asarray(im, dtype=np.float64) > 128).astype(np.float64)
    a -= a.mean()
    # Circular autocorrelation by FFT, normalised to 1 at zero lag.
    f = np.fft.fft2(a)
    ac = np.real(np.fft.ifft2(f * np.conj(f)))
    ac /= ac[0, 0]
    h, w = ac.shape
    lines = []
    plot = Image.new("RGB", (640, 260), (255, 255, 255))
    d = ImageDraw.Draw(plot)
    for name, prof, n, col in (("x", ac[0, : w // 2], w, (200, 40, 40)), ("y", ac[: h // 2, 0], h, (40, 80, 200))):
        lags = np.arange(len(prof)) * m_per_px
        start = int(3.0 / m_per_px)
        k = start + int(np.argmax(prof[start:]))
        lines.append(f"{name}: peak {prof[k]:.3f} at {lags[k]:.1f} m (max lag {lags[-1]:.0f} m)")
        pts = [(20 + 600 * L / lags[-1], 230 - 200 * max(min(v, 1.0), -0.1)) for L, v in zip(lags, prof)]
        d.line(pts, fill=col, width=2)
        d.text((24, 10 + 14 * (name == "y")), lines[-1], fill=col)
    d.line([(20, 230), (620, 230)], fill=(0, 0, 0))
    plot.save(out)
    print(f"{path}: {a.shape[1]} x {a.shape[0]} px at {m_per_px:.3f} m, foam cover {((np.asarray(im) > 128).mean()) * 100:.2f}%")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
