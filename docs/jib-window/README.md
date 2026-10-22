# The jib's window you can see through, and the clew without a starburst

The two most visible things on the sails from the helm's eye in the first minute (helm-eye, 10 kn, beat, reach and
run, `helm-*-before.jpg` / `-after.jpg`).

**1. The window.** The keelboat jib's vinyl window (Sails look, #227) was drawn as cloth darkened to 0.1 grey: a solid
dark-grey panel in the middle of the view forward. A real window is clear: you look through it at the water and the
boats to leeward, which is what it's for.

- `M_SailCloth` is now Masked. Outside the window every pixel is opaque cloth, as before.
- Inside it, a temporal-AA dither (`DitherTemporalAA`, clip 0.5) lets 88% of the view through. The pixels left are the
  vinyl's milky haze (0.42 grey) and its gloss (roughness 0.08).
- The window's shape is one HLSL snippet (`JIB_WINDOW`), shared by the sail's shading and a small mask node, so the
  depth and shadow passes don't run the whole sail shader. The sun also comes through the window.

**2. The clew's wrinkles.** The stress wrinkles from the clew were 34 even rays fading over 0.7 m. On the jib seen
past the mast on a run, they read as a starburst. They are now about 9 creases:
- unevenly spaced, each with its own strength;
- sharp, each a ((1 + cos)/2)^4 profile, zero between creases so their strengths can differ without a step;
- gone within about 0.4 m.

Both changes are in `scripts/make_materials.py` (`build_sail_cloth`, `SAIL_CODE`), rebuilt with
`MATERIALS_ONLY=build_sail_cloth`.
