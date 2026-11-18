# Near water: smooth slopes where the wave maps' texels are bigger than a pixel (Nov 18 2026)

sailing-feedback #30: on the near water at the bulkhead lot and along the bank at the I-30 bridge, M_WaterV4 drew a
herringbone of light and dark chevrons along the wall, and hard, stair-stepped sun glints 10 to 30 px across nearer the
camera. Stills, crops and the flag isolation: `Inputs/bench/render-bugs-nov17/` on the `inputs` branch.
`-SailingClassicWater` removed both; nothing else tested did, and they kept their size on screen at 67% resolution, so
they were drawn by the water's own shading.

## Cause

The short-wave slope maps are coarse next to a near pixel:

| Map | Texels | Tile | Texel |
| --- | --- | --- | --- |
| Chop (`DetailB`) | 128 | 23 m | 18 cm |
| Long chop (`DetailE`) | 128 | 61.7 m | 48 cm |
| Ripples (`RippleB`) | 64 | 3.1 m | 4.8 cm |
| Capillaries (`CapillaryB`) | 64 | 0.64 m | 1 cm |

From a 2 m eye, water 4-5 m out is 0.5 cm a pixel across and about 1.3 cm along the view at 1080p. So the chop's and
ripples' texels are magnified to several pixels there. Bilinear filtering is continuous but its slope is not: each texel
cell is its own bilinear patch. On calm, sheltered water (low roughness, the 0.68 floor where the capillaries are drawn)
the sun's and sky's highlights are sharp enough to trace those cells. That gave the blocks, with the 45 degree stair-steps
bilinear contours make. The ripples are read in two frames turned 15 degrees either side of the local wind, so their two
cell grids cross at 30 degrees. Foreshortened along a wall or bank a few metres away, that read as the herringbone.

The shore wasn't the cause. These stills look at a wall or bank a few metres from the camera across calm water. Open-water
views have rougher water and rarely look at water that close at that angle.

## Fix

Where a map's texel spans 1.5 pixels or more, M_WaterV4 reads it with a cubic B-spline (four bilinear taps,
Sigg and Hadwiger 2005: `BSPL` in `V4_SHADE`). It crossfades back to the hardware's trilinear read as the texel shrinks
to one pixel, so nothing changes past that. This covers the chop, the long chop and the ripples.

- The B-spline is C2, so slopes and highlights are smooth across texels.
- It keeps each texel's mean, so the squared slopes (LEAN roughness) are read the same way.
- The capillaries' 1 cm texels only magnify within a metre or two, so they keep the plain read.
- The trilinear read stays outside the branch (its implicit derivatives need the whole pixel quad). The cubic reads mip 0
  explicitly, so it only runs where it's needed.
- Cost: up to 4 extra taps for the chop, 4 for the long chop and 8 for the ripples (two frames), only on near pixels.
  To be measured on the gate (water scope) and the PC's 4K Ultra.

## Checks

- PC: the four #30 stills (`env-bulkhead-05m`, `-near-20`, `-near-35`, `env-bridge-05m`; args in the issue), Ultra
  1920x1080, compared at 1:1 against `crops/` on the inputs branch.
- Mac: `scripts/gate.sh --scope water` (High 45 / Medium 60) and a near-water still on High.
