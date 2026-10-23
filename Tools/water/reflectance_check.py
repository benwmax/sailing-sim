"""Sea reflectance check (docs/sea-reflectance/): the water's luminance over the sky's at the mirror angle, by depression
below the horizon, measured in a capture, against Fresnel for a flat surface and averaged over Cox-Munk slopes.

    Tools/venv/bin/python -I Tools/water/reflectance_check.py <image> <pitch deg> <hfov deg> <wind m/s> [depressions ...]

Under a uniform overcast the ratio is the surface's effective reflectance (plus the body's upwelling at steep angles);
under a clear sky it is still a fair check at 3-12 deg, where the reflected sky is the same column a few degrees up.
The camera's pitch and field of view are in the capture's .camera.json (scripts/capture-scenes.sh).
"""
import math
import sys

import numpy as np
from PIL import Image


def fresnel(cosi, n=1.333):
    """Unpolarized Fresnel reflectance of water for the cosine of the incidence angle."""
    cosi = np.clip(cosi, 1e-6, 1.0)
    sint = np.sqrt(1.0 - cosi ** 2) / n
    cost = np.sqrt(np.clip(1.0 - sint ** 2, 0.0, 1.0))
    rs = ((cosi - n * cost) / (cosi + n * cost)) ** 2
    rp = ((n * cosi - cost) / (n * cosi + cost)) ** 2
    return 0.5 * (rs + rp)


def flat(dep_deg):
    return float(fresnel(math.sin(math.radians(dep_deg))))


def cox_munk(dep_deg, wind_ms, samples=200000, seed=1):
    """Mean reflectance of a uniform sky seen at a depression: isotropic Cox-Munk slopes (variance 0.003 + 0.00512 U),
    facets weighted by their area toward the eye, back-facing ones dropped, rays reflected below the horizon counted
    as 0. No shadowing between waves, so it runs a little high at grazing angles."""
    rng = np.random.default_rng(seed)
    var = 0.003 + 0.00512 * wind_ms
    sx = rng.normal(0.0, math.sqrt(var / 2.0), samples)
    sy = rng.normal(0.0, math.sqrt(var / 2.0), samples)
    nrm = np.stack([-sx, -sy, np.ones(samples)], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    d = math.radians(dep_deg)
    view = np.array([math.cos(d), 0.0, -math.sin(d)])
    cosi = -(nrm @ view)
    weight = np.clip(cosi, 0.0, None) / nrm[:, 2]
    refl = view[None, :] + 2.0 * cosi[:, None] * nrm
    f = fresnel(np.clip(cosi, 0.0, 1.0)) * (refl[:, 2] > 0.0)
    return float((f * weight).sum() / weight.sum())


def mean_reflected_elevation(dep_deg, wind_ms, samples=400000, seed=2):
    """The sky a rippled surface reflects at a depression: the mean (and spread) of the reflected rays' elevation over
    Cox-Munk slopes, weighted by the facets' area toward the eye and their Fresnel reflectance, back-facing facets and
    rays reflected below the horizon dropped. At 1-8 deg below the horizon it is about 1.35 times the slopes' rms angle
    (13 deg at 5 m/s): M_WaterV4 lifts each pixel's mirror direction to it (docs/water-sky-reflection/)."""
    rng = np.random.default_rng(seed)
    var = 0.003 + 0.00512 * wind_ms
    sx = rng.normal(0.0, math.sqrt(var / 2.0), samples)
    sy = rng.normal(0.0, math.sqrt(var / 2.0), samples)
    nrm = np.stack([-sx, -sy, np.ones(samples)], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    d = math.radians(dep_deg)
    view = np.array([math.cos(d), 0.0, -math.sin(d)])
    cosi = -(nrm @ view)
    refl = view[None, :] + 2.0 * cosi[:, None] * nrm
    weight = np.clip(cosi, 0.0, None) / nrm[:, 2] * fresnel(np.clip(cosi, 0.0, 1.0)) * (refl[:, 2] > 0.0)
    elev = np.degrees(np.arcsin(np.clip(refl[:, 2], -1.0, 1.0)))
    mean = float((elev * weight).sum() / weight.sum())
    return mean, float(np.sqrt(((elev - mean) ** 2 * weight).sum() / weight.sum()))


def linear(rgb8):
    a = rgb8 / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def measure(path, pitch_deg, hfov_deg, wind_ms, deps=(1, 2, 3, 5, 8, 12), cols=None):
    """(depression, water/sky luminance, Cox-Munk, flat) per depression, from row medians across the frame."""
    img = linear(np.asarray(Image.open(path).convert("RGB"), float)) @ [0.2126, 0.7152, 0.0722]
    h, w = img.shape
    f = (w / 2.0) / math.tan(math.radians(hfov_deg / 2.0))
    c0, c1 = cols or (int(0.07 * w), int(0.93 * w))
    out = []
    for dep in deps:
        rw = int(round(h / 2.0 + f * math.tan(math.radians(dep + pitch_deg))))
        rs = int(round(h / 2.0 - f * math.tan(math.radians(dep - pitch_deg))))
        if not (2 <= rw < h - 2 and 2 <= rs < h - 2):
            continue
        water = np.median(img[rw - 2:rw + 2, c0:c1])
        sky = np.median(img[rs - 2:rs + 2, c0:c1])
        out.append((dep, float(water / sky), cox_munk(dep, wind_ms), flat(dep)))
    return out


if __name__ == "__main__":
    path, pitch, hfov, wind = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    deps = [float(x) for x in sys.argv[5:]] or (1, 2, 3, 5, 8, 12)
    print("depression  water/sky  Cox-Munk  flat")
    for dep, r, cm, fl in measure(path, pitch, hfov, wind, deps):
        print(f"{dep:9.1f}  {r:9.2f}  {cm:8.2f}  {fl:4.2f}")
