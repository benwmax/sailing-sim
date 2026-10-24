# Calm water: no foam where nothing breaks (Oct 24 2026)

On a glassy lake (0.5 m/s, the bridge view, cloudless), the near water carried two kinds of foam:

- blocky 2×2 white specks;
- a thin grey-brown film over everything near the camera.

The Specular 0 test showed them: they stayed when the reflection was gone, so they were the slab's foam layer, not
reflections.

## Cause

`AWaterSurface` solves the whitecap threshold on the sea it draws (`FWaveDetail::CapThreshold`). Calm water has no
cover to reach: the target is floored at 1e-7, and the comment there intends the threshold to land below every sample.
But at calm the drawn fold scale is zero, so every sample is exactly 1. The light-air extrapolation then has no tail to
follow, and the threshold came out at 1.0, the sea itself (`-SailingDebugCaps`: "thresholds 1.000"). In M_WaterV4 that
gave:

- **Caps:** the fold ramp (0.05 wide) capped any pixel whose Jacobian dipped under 1.
- **Residue:** its ramp (to 0.12 over the threshold) put a little on every pixel: the film. The foam grid then carried
  it into blocks: the specks.

## Fix

- `FWaveDetail::CapThreshold`: a flat tail (its two quantiles under 0.002 apart) returns -1, which no drawn Jacobian
  reaches.
- M_WaterV4: a solved threshold under -0.5 passes through the 0.3–0.85 clamp as -1. At 0.3 the fine ripples' own folds
  still came through.
- `SailingSim.Visual.WhitecapOnset` checks the flat sea.
- Nothing changes where the sea has a tail: the light-air extrapolation and the solved thresholds at 7 kn and up are as
  before (`SailingSim.Visual.Whitecaps`, `WhitecapSize`, `WhitecapsSeen` pass unchanged).

## Seen

`before-after.jpg`: the glassy mirror before (left) and after (right). `near-water.jpg`: the near water at full size,
before (top) and after (bottom).

The calm lake now reads as dark, blue water. The film that greyed it is gone.

The whitecap debug view (`-SailingDebugFoam=1..3`) still shows a sparse sprinkle of single pixels at calm. It is the same
in mode 3, which draws only where the fold is under the threshold (none at -1), so it doesn't come from the foam. It is
something in that debug view's rendering, and it doesn't show in the normal view.
