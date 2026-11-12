#!/usr/bin/env python3
"""Loudness and clipping check for a recording of the game's master mix (the sound plan's slice item 6).

Usage:
  python3 scripts/loudness_check.py <file.wav> [more.wav ...] [--target -18] [--tolerance 3] [--ceiling -1] [--csv out.csv]
  python3 scripts/loudness_check.py --self-test

For each file: integrated loudness (ITU-R BS.1770-4: K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU
relative gates), loudness range (EBU Tech 3342: 3 s windows, 10th to 95th percentile), sample peak, true peak
(4x oversampled, BS.1770 Annex 2) and clipped samples (runs of 3+ samples at full scale). Passes when the integrated
loudness is within --tolerance LU of --target and the true peak is under --ceiling dBTP.

Targets: there is no single standard for PC games. The plan uses -18 LUFS +-3 (Meta's PC VR figure, between Sony's
-24 console and -16 mobile) and a -1 dBTP ceiling (every published game guideline). Channels: 1 mono, 2 stereo,
6 = 5.1 and 8 = 7.1 in WAV order (L R C LFE Ls Rs [Lb Rb]); the LFE is left out and the surrounds weigh 1.41.

numpy only (scipy is used for speed when it is installed). Exit 1 when any file fails.
"""
import argparse
import math
import struct
import sys
import wave

import numpy as np

try:
    from scipy.signal import lfilter as _lfilter
except ImportError:  # pragma: no cover
    _lfilter = None


def biquad(b, a, x):
    """Direct form I biquad (a[0] == 1)."""
    if _lfilter is not None:
        return _lfilter(b, a, x)
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    b0, b1, b2 = b
    _, a1, a2 = a
    for i, v in enumerate(x.tolist()):
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o
        y[i] = o
    return y


def k_weighting(rate):
    """BS.1770's two stages (high shelf, then the RLB high-pass), recomputed for any sample rate (the published
    48 kHz coefficients come out exactly)."""
    # Stage 1: high shelf.
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / rate)
    vh = 10 ** (g / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b_shelf = [(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0]
    a_shelf = [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    # Stage 2: high-pass.
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / rate)
    a0 = 1 + k / q + k * k
    b_hp = [1.0, -2.0, 1.0]
    a_hp = [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0]
    return (b_shelf, a_shelf), (b_hp, a_hp)


def channel_weights(n):
    if n == 6:
        return [1.0, 1.0, 1.0, 0.0, 1.41, 1.41]
    if n == 8:
        return [1.0, 1.0, 1.0, 0.0, 1.41, 1.41, 1.41, 1.41]
    return [1.0] * n


def read_wav(path):
    with wave.open(path, "rb") as w:
        n, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(frames)
    if width == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float64) / float(1 << 23)
    elif width == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"{path}: {width * 8}-bit samples are not handled")
    return x.reshape(-1, n), rate


def read_any(path):
    """WAV through the wave module; 32-bit float WAV (format 3, which wave refuses) read by hand."""
    try:
        return read_wav(path)
    except wave.Error:
        pass
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path}: not a WAV file")
    pos, fmt, samples = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            samples = body
        pos += 8 + size + (size & 1)
    if not fmt or samples is None or fmt[0] not in (3, 0xFFFE) or fmt[5] != 32:
        raise ValueError(f"{path}: unsupported WAV format {fmt}")
    n, rate = fmt[1], fmt[2]
    return np.frombuffer(samples, dtype="<f4").astype(np.float64).reshape(-1, n), rate


def block_loudness(z, weights, rate, block_s, step_s):
    """Mean squares of the K-weighted channels over sliding blocks, summed with the channel weights (LKFS per block)."""
    size, step = int(round(block_s * rate)), int(round(step_s * rate))
    if z.shape[0] < size:
        return np.array([])
    c = np.concatenate([np.zeros((1, z.shape[1])), np.cumsum(z * z, axis=0)])
    starts = np.arange(0, z.shape[0] - size + 1, step)
    ms = (c[starts + size] - c[starts]) / size
    power = ms @ np.asarray(weights)
    with np.errstate(divide="ignore"):
        return -0.691 + 10 * np.log10(power)


def integrated(blocks):
    gated = blocks[blocks > -70.0]
    if gated.size == 0:
        return float("-inf")
    rel = -0.691 + 10 * math.log10(np.mean(10 ** ((gated + 0.691) / 10))) - 10.0
    gated = gated[gated > rel]
    if gated.size == 0:
        return float("-inf")
    return -0.691 + 10 * math.log10(np.mean(10 ** ((gated + 0.691) / 10)))


def loudness_range(short):
    gated = short[short > -70.0]
    if gated.size < 2:
        return 0.0
    rel = -0.691 + 10 * math.log10(np.mean(10 ** ((gated + 0.691) / 10))) - 20.0
    gated = gated[gated > rel]
    if gated.size < 2:
        return 0.0
    return float(np.percentile(gated, 95) - np.percentile(gated, 10))


def true_peak(x):
    """4x oversampling with a windowed-sinc interpolator (48 taps a phase), the peak of all channels."""
    taps = 48
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    for phase in range(1, 4):
        t = np.arange(-taps // 2, taps // 2) + phase / 4.0
        h = np.sinc(t) * np.kaiser(taps, 8.0)
        h /= h.sum()
        for ch in range(x.shape[1]):
            y = np.convolve(x[:, ch], h[::-1], mode="same")
            peak = max(peak, float(np.max(np.abs(y))))
    return peak


def clipped_runs(x, run=3):
    full = np.abs(x) >= 0.9999
    count = 0
    for ch in range(x.shape[1]):
        f = np.concatenate([[False], full[:, ch], [False]]).astype(np.int8)
        d = np.diff(f)
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        count += int(np.sum((ends - starts) >= run))
    return count


def db(v):
    return 20 * math.log10(v) if v > 0 else float("-inf")


def measure(x, rate):
    (bs, as_), (bh, ah) = k_weighting(rate)
    z = np.column_stack([biquad(bh, ah, biquad(bs, as_, x[:, c])) for c in range(x.shape[1])])
    w = channel_weights(x.shape[1])
    lufs = integrated(block_loudness(z, w, rate, 0.4, 0.1))
    lra = loudness_range(block_loudness(z, w, rate, 3.0, 0.1))
    short = block_loudness(z, w, rate, 3.0, 0.1)
    return {
        "lufs": lufs,
        "lra": lra,
        "short_max": float(np.max(short)) if short.size else float("-inf"),
        "sample_peak_db": db(float(np.max(np.abs(x))) if x.size else 0.0),
        "true_peak_db": db(true_peak(x)),
        "clipped": clipped_runs(x),
        "seconds": x.shape[0] / rate,
        "channels": x.shape[1],
    }


def self_test():
    rate = 48000
    t = np.arange(rate * 10) / rate
    ok = True
    # BS.1770: a 1 kHz sine at full scale in one channel reads -3.01 LKFS; at 0.1 it reads -23.01.
    for amp, want in ((1.0, -3.01), (0.1, -23.01)):
        m = measure((amp * np.sin(2 * math.pi * 1000 * t))[:, None], rate)
        good = abs(m["lufs"] - want) < 0.05
        ok &= good
        print(f"1 kHz sine at {amp}: {m['lufs']:.2f} LUFS (want {want}) {'ok' if good else 'FAIL'}")
    # A full-scale sine between samples (fs/4 at 45 deg) peaks 3 dB over its samples.
    x = np.sin(2 * math.pi * (rate / 4) * t + math.pi / 4)[:, None]
    m = measure(x, rate)
    good = abs(m["true_peak_db"] - 0.0) < 0.3 and m["sample_peak_db"] < -2.9
    ok &= good
    print(f"inter-sample peak: true {m['true_peak_db']:.2f} dBTP, sample {m['sample_peak_db']:.2f} dBFS {'ok' if good else 'FAIL'}")
    clip = np.clip(1.5 * np.sin(2 * math.pi * 100 * t), -1, 1)[:, None]
    good = clipped_runs(clip) > 100
    ok &= good
    print(f"clipping found: {clipped_runs(clip)} runs {'ok' if good else 'FAIL'}")
    # Silence gates out.
    good = measure(np.zeros((rate * 2, 2)), rate)["lufs"] == float("-inf")
    ok &= good
    print(f"silence: gated out {'ok' if good else 'FAIL'}")
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("files", nargs="*")
    p.add_argument("--target", type=float, default=-18.0)
    p.add_argument("--tolerance", type=float, default=3.0)
    p.add_argument("--ceiling", type=float, default=-1.0)
    p.add_argument("--csv")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if not a.files:
        p.error("no files")
    rows, failed = [], False
    for path in a.files:
        x, rate = read_any(path)
        m = measure(x, rate)
        loud_ok = abs(m["lufs"] - a.target) <= a.tolerance
        peak_ok = m["true_peak_db"] < a.ceiling
        ok = loud_ok and peak_ok and m["clipped"] == 0
        failed |= not ok
        notes = []
        if not loud_ok:
            notes.append(f"loudness {m['lufs'] - a.target:+.1f} LU off target")
        if not peak_ok:
            notes.append("true peak over the ceiling")
        if m["clipped"]:
            notes.append(f"{m['clipped']} clipped runs")
        print(f"{path}: {m['lufs']:.1f} LUFS, range {m['lra']:.1f} LU, loudest 3 s {m['short_max']:.1f} LUFS, "
              f"peak {m['sample_peak_db']:.1f} dBFS / {m['true_peak_db']:.1f} dBTP, {m['channels']} ch, {m['seconds']:.0f} s: "
              f"{'PASS' if ok else 'FAIL (' + '; '.join(notes) + ')'}")
        rows.append((path, m, ok))
    if a.csv:
        with open(a.csv, "w") as f:
            f.write("file,lufs,lra,short_max,sample_peak_db,true_peak_db,clipped,channels,seconds,pass\n")
            for path, m, ok in rows:
                f.write(f"{path},{m['lufs']:.2f},{m['lra']:.2f},{m['short_max']:.2f},{m['sample_peak_db']:.2f},"
                        f"{m['true_peak_db']:.2f},{m['clipped']},{m['channels']},{m['seconds']:.1f},{int(ok)}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
