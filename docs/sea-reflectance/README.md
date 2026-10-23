# Sea reflectance at grazing angles: a check, no change

Realism audit Oct 23 (`docs/realism-audit-1023/`), item 5 (the open Gulf reads green) and item 1 (the lake reads
olive, not blue-grey). After #275 the swell view's horizon ran from a bright deck to a dark sea, which looked like a
sea reflecting too little sky. This measures that against physics instead of a reference photo, and finds the
reflection right. What colours the water wrong is the sky it reflects.

## Method

`Tools/water/reflectance_check.py` takes a capture (`scripts/capture-scenes.sh`; the pitch and field of view are in its
`.camera.json`) and, for each depression below the horizon, divides the water's luminance by the sky's at the mirror
elevation (row medians, linear light). It compares that with:
- Fresnel for a flat surface;
- Fresnel averaged over Cox-Munk wave slopes for the wind. This counts no shadowing between waves, so it runs a
  little high at grazing angles.

Under a uniform overcast the ratio is the surface's reflectance. Under a clear sky it is still fair at 3–12 deg.

## Results

Expected (Cox-Munk) at 3 / 5 / 8 / 12 deg: 0.39 / 0.34 / 0.28 / 0.21 at 10 kn.

| | 3 deg | 5 deg | 8 deg | 12 deg |
|---|---|---|---|---|
| Game, bridge (clear) | 0.45 | 0.39 | 0.34 | 0.29 |
| Photo, bridge (Tawakoni) | 0.49 | 0.38 | 0.36 | 0.27 |
| Game, open lake (clear) | 0.52 | 0.51 | 0.45 | 0.45 |
| Photo, open lake | 0.51 | 0.44 | 0.36 | 0.22 |

The Gulf swell under an overcast (shore telephoto, 12 kn; Cox-Munk 0.39 / 0.37 / 0.35 / 0.31 at 1 / 2 / 3 / 5 deg):
- Before #275: 0.22 / 0.22 / 0.20 / 0.22.
- After #275: 0.38 / 0.29 / 0.25 / 0.23.

#275's quarter-strength sky light under the deck does not weaken the reflection; the brighter deck raised it.

At steep angles both photos fall below even Fresnel (0.06 at 25 deg against 0.09). The sky 90 deg from the sun is
strongly polarized, and water reflects less of it near Brewster's angle, so the photos can't measure the body there.
Seen from the RH-004 drone view instead, the lake body's own reflectance is about 0.03 (the water at 0.065 of the
white hull, less a 2% sky reflection). That is inside the 0.03–0.08 measured for turbid reservoirs, so phase 8's
olive-green from above still holds.

## What colours the water

Channel by channel, the water-to-sky ratio matches the photos. At 3 deg on the bridge view it is
0.42 / 0.45 / 0.45 (r, g, b) against the photo's 0.44 / 0.50 / 0.53. The difference is the sky being reflected:

- In both photos the sky 3–8 deg up is clearly blue: red over blue 0.67–0.77.
- Ours is near white: red over blue 0.86–0.92.

The water then inherits a pale sky and adds the olive body's tint. So the lever for item 1 (and for the Gulf, item 5)
is the near-horizon sky's saturation, not the water. That is the parked item 4b (`docs/realism-audit-1023/`).
