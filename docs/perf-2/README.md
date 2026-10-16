# Perf 2: headroom on High (the Mac)

Goal: at least +5 fps on High at helm-eye, storm, coast-day and slip, with the image unchanged, to make room for the
cinematic look pass and richer boats. Measured on Bean's M5 Pro, packaged Development build, `scripts/gate.sh`
(bench-visual, 12 s per view). Baseline: the full gate on origin/main 05d095f2 (`visual-bench-p1-base.csv`, stills in
`before/`).

## How the time was found

The bench's `ProfileGPU` dumps (the game log in the app's container) give the pass tree. On High at the helm's eye,
in a 21 ms GPU frame: shadow depths 4.6 ms (Nanite VSM 2.8, non-Nanite 1.2), deferred lighting 4.5 ms (Lumen 3.2),
volumetric clouds 3.3 ms (8 ms in the storm), hair 1.1 ms, water 1.9 ms. Single-view runs with `-dpcvars=` then
tested each suspect (`docs/perf-2` runs listed below; the run-to-run noise on the same build is about 0.1 fps).

| Run (helm-eye, High) | fps |
|---|---|
| baseline, twice | 45.9, 45.9 |
| `r.Shadow.Virtual.Cache=0` | 46.0 |
| `r.Shadow.Virtual.ResolutionLodBiasDirectionalMoving=1` | 52.8 (deck shadows visibly softer, the lines' shadows lost: rejected) |
| `r.HairStrands.Strands=0` | 49.3 (the beards go to cards elsewhere: rejected) |
| SMRT rays 4, clipmap last level 18, Lumen translucency volume off, radiance cache probes 16, fog conservative depth off, 5 water rings | within 0.6 |

## 1. The shadow cache survives the frame

Turning the virtual shadow map cache off changed nothing: the cache was being thrown away every frame. A directional
light's cache is keyed on its direction (`FVirtualShadowMapPerLightCacheEntry::UpdateClipmap`), and
`ASailingEnvironment` turned the sun (and the moon) to the clock's sun position every tick. Now each light turns in
0.05 deg steps (`LightTurned`): about one step every 12 s at the sun's rate, a 1 cm shift of the masthead's shadow on
the water; each step re-renders the pages once (one ordinary frame).

Also in this change: the helm-eye capture hid the helm's body without its children, so the helm's face, polo, life
jacket and strand hair still drew round the camera (the floating blue and red jacket at the lower right of the old
helm-eye still, and the 1.1 ms of hair). It now hides them with the body, as the cockpit view already did.

| View | Medium before | after | High before | after |
|---|---|---|---|---|
| helm-eye | 77.9 | 84.8 | 45.4 | 51.2 |
| storm | 68.6 | 69.6 | 45.6 | 50.2 |
| coast-day | 79.7 | 82.2 | 46.9 | 49.7 |
| slip | 76.4 | 80.6 | 47.2 | 51.3 |
| beam8 | 86.6 | 88.4 | 53.3 | 58.9 |
| beat15 | 82.4 | 83.9 | 49.9 | 52.7 |
| marina | 86.6 | 93.7 | 50.2 | 59.9 |
| gulf-sea | 102.0 | 104.4 | 59.4 | 63.6 |
| bridge | 95.0 | 99.0 | 53.8 | 60.3 |

Image: `after-1/` against `before/`. The helm-eye still loses the helm's floating jacket. Otherwise the deck,
rig and terrain shadows match, and the differences are frame to frame (rain, foam, puffs). CSV:
`visual-bench-p2-vsmstep.csv`.
