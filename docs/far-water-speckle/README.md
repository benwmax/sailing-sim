# Far water: no dark speckle at grazing angles

**The symptom:** from the helm and the chase camera, on Medium and High, the far water was peppered with single dark
pixels: a salt-and-pepper grain over the grey sheen toward the horizon (`far-band-3x.jpg`: 20 kn above and 12 kn below,
before on the left, after on the right).

**The cause:** Lumen's reflections on the water. Turned off (`r.Lumen.Reflections.Allow 0`) the far water was smooth;
with the anti-aliasing or the screen-space reflections off the speckle stayed. At a grazing view a short wave's slope
can turn a pixel's mirror direction below the horizon. The reflection ray then meets the dark lake or shore close by,
and that pixel goes dark, one pixel at a time, at random.

**The fix (`V4_SHADE`, M_WaterV4, Medium and High):** where a pixel's mirror direction would point below the horizon,
it is lifted to just above it (z 0.02) in the same vertical plane, and the normal becomes the half-vector between the
view and that direction. It is exact, and it touches only those pixels:
- the sun's glints (mirrors toward a sun above the horizon) are untouched;
- the far caps (foam albedo, W8 and the far-cap sprites) are untouched;
- the near water is untouched (`glint-*`, `caps-20kn-*`).

Stills (`*-before.jpg` / `*-after.jpg`): `helm-high`, `chase-high`, `helm-medium`, `chase-medium`, `caps-20kn` (helm
eye) and `glint` (a low sun, 17:30).
