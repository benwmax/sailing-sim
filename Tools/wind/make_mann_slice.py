"""W1: the fine turbulence texture (eddies under 200 m) for FWindField: a horizontal slice of a Mann (1994) turbulence box.

Generated with DTU's Hipersim (MIT; pip install hipersim): the Mann spectral tensor with length scale L = 30 m and shear
distortion Gamma = 3.9 (the IEC 61400-1 neutral values; L as at 10-30 m over water), on a 256 x 256 x 32 box at 2 m in x
and y (a 512 m tile, periodic in x and y because nothing is doubled) and 2 m in z. One slice at 10 m: the along-wind (u)
and cross-wind (v) components, each along-wind line's mean removed, scaled so u has unit standard deviation (v keeps its
ratio to u). The game advects it as frozen flow at the mean wind (x along the wind, read on a line slanted 1 in 7.3 across
the tile so a fixed point does not see the 512 m period) and scales it by the mechanical turbulence intensity.

Writes Content/TerrainData/Wind.mann: "MANN", uint32 version 1, uint32 nx, uint32 ny, float32 dx, L, gamma, v/u, then
nx*ny float16 u (index iy*nx + ix), then v. Falls back to a numpy implementation of the same tensor if Hipersim is
missing (--numpy forces it).
Usage: Tools/venv/bin/python Tools/wind/make_mann_slice.py [--numpy] [--seed N]
"""
import os
import struct
import sys

import numpy as np

N, DX, NZ, DZ = 256, 2.0, 32, 2.0
L, GAMMA = 30.0, 3.9
SEED = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 22
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "Content", "TerrainData", "Wind.mann")


def numpy_mann(seed):
    """Mann (1994) by hand: the sheared von Karman tensor (Eqs. 26-29 there), white noise in Fourier space, one inverse
    FFT. Same model as Hipersim, without its high-frequency compensation."""
    from scipy.special import hyp2f1
    rng = np.random.default_rng(seed)
    k1 = 2 * np.pi * np.fft.fftfreq(N, DX)
    k2 = 2 * np.pi * np.fft.fftfreq(N, DX)
    k3 = 2 * np.pi * np.fft.fftfreq(NZ, DZ)
    K1, K2, K3 = np.meshgrid(k1, k2, k3, indexing="ij")
    k = np.sqrt(K1 ** 2 + K2 ** 2 + K3 ** 2)
    k[0, 0, 0] = 1e-9
    kl = k * L
    beta = GAMMA / (kl ** (2 / 3) * np.sqrt(np.maximum(hyp2f1(1 / 3, 17 / 6, 4 / 3, -kl ** -2), 1e-30)))
    k30 = K3 + beta * K1
    k0 = np.sqrt(K1 ** 2 + K2 ** 2 + k30 ** 2)
    k0[k0 == 0] = 1e-9
    E0 = (k0 * L) ** 4 / (1 + (k0 * L) ** 2) ** (17 / 6)
    kh2 = np.maximum(K1 ** 2 + K2 ** 2, 1e-12)
    C1 = beta * K1 ** 2 * (k0 ** 2 - 2 * k30 ** 2 + beta * K1 * k30) / (k ** 2 * kh2)
    C2 = K2 * k0 ** 2 / kh2 ** 1.5 * np.arctan2(beta * K1 * np.sqrt(kh2), k0 ** 2 - k30 * K1 * beta)
    r = np.divide(K2, K1, out=np.zeros_like(K1), where=K1 != 0)
    z1 = C1 - r * C2
    z2 = r * C1 + C2
    s = np.sqrt(E0 / (4 * np.pi)) / k0 ** 2
    n = (rng.standard_normal((3,) + K1.shape) + 1j * rng.standard_normal((3,) + K1.shape))
    a1 = s * (K2 * n[2] - k30 * n[1])
    a2 = s * (k30 * n[0] - K1 * n[2])
    a3 = s * (K1 * n[1] - K2 * n[0])
    u = a1 + z1 * a3
    v = a2 + z2 * a3
    u = np.real(np.fft.ifftn(u))
    v = np.real(np.fft.ifftn(v))
    return u, v


def main():
    if "--numpy" not in sys.argv:
        try:
            from hipersim import MannTurbulenceField
            f = MannTurbulenceField.generate(alphaepsilon=1.0, L=L, Gamma=GAMMA, Nxyz=(N, N, NZ), dxyz=(DX, DX, DZ), seed=SEED,
                                             HighFreqComp=0, double_xyz=(False, False, False), n_cpu=4)
            u, v = np.asarray(f.uvw[0]), np.asarray(f.uvw[1])
            source = "hipersim"
        except ImportError:
            u, v = numpy_mann(SEED)
            source = "numpy"
    else:
        u, v = numpy_mann(SEED)
        source = "numpy"
    k = int(round(10.0 / DZ)) % NZ
    # Each along-wind line's own mean out (the box's k1 = 0 modes): in frozen flow they would be a permanent lane of more
    # or less wind at a fixed point.
    us = u[:, :, k] - u[:, :, k].mean(axis=0, keepdims=True)
    vs = v[:, :, k] - v[:, :, k].mean(axis=0, keepdims=True)
    sd = us.std()
    us, vs = us / sd, vs / sd
    ratio = float(vs.std())
    # Stored [iy][ix] (x fastest): u[x, y] transposed.
    data = struct.pack("<4sIIIffff", b"MANN", 1, N, N, DX, L, GAMMA, ratio)
    data += us.T.astype("<f2").tobytes() + vs.T.astype("<f2").tobytes()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(data)
    # Integral length along the wind from the autocorrelation (for the README).
    ac = np.real(np.fft.ifft(np.abs(np.fft.fft(us, axis=0)) ** 2, axis=0)).mean(axis=1)
    ac /= ac[0]
    first = np.argmax(ac < 0) if np.any(ac < 0) else len(ac)
    lint = float(ac[:first].sum() * DX)
    print(f"{source}: {N}x{N} at {DX} m, L {L} m, Gamma {GAMMA}; v/u {ratio:.2f}; along-wind integral length {lint:.0f} m; "
          f"{len(data) / 1024:.0f} KB -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
