# The water near the boat: capillary wavelets and droplet spray (Oct 24 2026)

Ultra audit 3 (`docs/ultra-audit-1024/`): the water near the boat smears. Close to the hull it was soft and smudgy, with
blurred reflections and no small glints, and the spray read as soft white sprites.

## The near water

The drawn short waves stopped at 10 cm (the ripple cascade, 64^2 over 3.1 m). Everything shorter was M_WaterV4's
roughness floor: 0.55 of Cox and Munk's slope, `alpha >= 0.55 sqrt(2 mss)`. Most of a sea's slope variance is in waves of
a few centimetres. So at the hull, where a pixel is a centimetre across, the water was one even gloss: no wavelets, and
reflections blurred by a roughness standing in for waves the pixel could have shown.

- **A third cascade on High and Ultra:** `FWaveDetail::CapillaryCascade`, 64^2 over 0.64 m, 1 cm texels, wavelengths 2 to
  10 cm.
  - Same pipeline as the ripples: evaluated on the detail worker at 30 Hz, blended, mip-mapped with slopes and squared
    slopes (LEAN).
  - M_WaterV4 samples it in the ripples' two turned frames (it faces the local wind), in full to 12 m and faded out by
    24 m.
  - Its spectrum is the saturation range continued (slope spectrum flat in log k).
- **Dispersion with surface tension:** `FWaveDetail::CapillaryOmega`, omega^2 = g k + (sigma / rho) k^3, now for every
  detail cascade.
  - A 10 cm wavelet runs 1.4% faster than a pure gravity wave and a 2 cm one a third faster.
  - The slowest water wave is 0.23 m/s near 1.7 cm.
  - The chop and ripples barely change.
- **A lower roughness floor where the capillaries are drawn.** In the saturation range down to the capillary end near
  0.5 cm, waves under 2 cm hold ln(2 / 0.5) / ln(10 / 0.5) = 46% of the slope variance that waves under 10 cm hold. So the
  floor's alpha is multiplied by sqrt(0.46) = 0.68 there.
  - At 12 kn the drawn 2–10 cm band carries 29% of Cox and Munk's mean square slope. It replaces the floor's share, not
    more.

`bow-water.jpg` is the bow from 3.5 m at 16 kn, main on the left and this change on the right. The water at the hull has
wavelets and glints instead of a milky smear.

## Spray

`M_Spray`'s pattern:
- A droplet clump was a disc of 3 cm dots over a soft veil.
- A torn sheet was a smooth translucent flap.

Bow spray is millimetre drops: at a few metres, points a pixel or two across that streak over a 1/60 s exposure (the quad
is already stretched along its motion). A sheet breaks into strands along its motion.

- **Clumps:** 9 x 6 cells, a drop in about two thirds of them, each a sixth of its cell.
- **Sheets:** seven strands along the motion, each its own width, broken where they tore.
- **Veil:** a tenth of what it was.

The mist is unchanged. `spray.jpg` shows `-SailingDebugSpray`'s fountain from the helm (capture mode, no motion blur), with
the sun behind and then low ahead. Main is on the left and this change on the right.

## Not here

- The bow wave's own sheet (the hull-water clip's lip) and wet darkening on the topsides.
- Lens drops (the round discs on the frame in an action-cam view) are the High lens-water post-process, unchanged.

Tests:
- `SailingSim.Visual.CapillaryWaves` (new) checks the dispersion and the band's share of Cox and Munk.
- `WaveMatch`, the whitecap tests, `FarCap*` and `Physics.Wave*` pass.
