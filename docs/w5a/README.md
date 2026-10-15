# W5a: cloud fixes (PC clouds, Mac gates)

Plan: "Water and weather realism plan", W5, the cloud fixes from G8's diagnosis. Blind round 10 named the clouds as
the top tell on 4 frames, the third round running. Branch `w5a-clouds` from main `b219e6e`. Built, tested and
captured on Bean's PC on Oct 15 2026.

## Changes

- **Size mix** (`FWeatherMap::Paint`). The cumulus field was one 2 km noise, so every cloud was the same size. It's now
  seeded cells in four size classes (radii 2000, 1100, 600 and 330 m, ±25%), on jittered lattices whose spacing grows
  as r^0.75. That's a power law, n(D) ~ D^-2.5: each class has about 2.4 times the clouds of the next larger one.
  - A cell's peak grows as r^0.6, so after the coverage threshold small cells are low puffs and big ones build to the
    full height.
  - Outlines are lumpy at each cell's own scale. Streets and the land bias are kept, plus a little of the old noise.
  - `Threshold` now solves for the edge whose mean presence equals the coverage (the cells are a skewed field).
  - New test (`SailingSim.Visual.CloudNoise`): on the afternoon map there are 574 clouds under 1 km², 94 of 1–4 km² and
    58 over 4 km². Coverage from the map still matches every preset exactly.
- **Billows scale with the cloud.** Cells that never build past a low presence take the shape noise at twice the
  frequency, and towers take the full-size billows. It's the same noise blended between two scales, never a warped
  frequency.
- **The march fitted, not the cap.**
  - Rays shorter than `r.VolumetricCloud.DistanceToSampleMaxCount` get proportionally fewer samples. At the engine's
    15 km, every near ray stepped about 94 m whatever the slab, so the material had to cap each step's opacity (cotton
    edges) or show grain.
  - Ultra now sets it to 3 km: about 19 m steps under a cumulus deck. The cap is relative to the step, so it no longer
    binds there and near cumulus keep their real density.
  - The noise footprint follows the step (floor 110 m, was a fixed 160 m). At 50 m the G8 frosting came back.
  - The cap itself stays at G8's 1.5. Lifting it to 4 brought the grain straight back at 94 m steps.
  - Medium and High keep the engine's 15 km, because the Mac's High is GPU-bound.
- **Darkened by depth, not altitude.**
  - The outline glows, since it takes the sky's light from all sides.
  - Inside, occlusion grows with the cell's build: a tower has a heavy grey base, while a small puff stays light.
  - The upper half of a cell keeps most of the sky's light.
- **Storm.**
  - The interior is smooth: billow erosion only near the outline and underneath, and fine detail only underneath.
  - The shelf's face climbs in three broad tiers, 700 m apart in run and about 600 m of rise each (`ShelfTierM`).
    `FStormShape::TierX` mirrors it in C++, so `SailingSim.Visual.ShelfCloud` still holds the shape to the front.
- **No rain in the clouds.** The march no longer fills the air under the core: W5b's `M_RainCurtain` draws the rain
  curtains and the rain foot. This took the storm view's cloud slice on Ultra from 3.55 ms to about 1.5 ms.
- **Not done:** cloud stamps from simulation data (optional in the plan). The haze and aerial-perspective check wasn't
  measured separately.

## Stills (packaged, 1920×1080)

Before: main `b219e6e` (taken from the W2 bench, whose clouds are main's). After: this branch.

| Before (Ultra) | After (Ultra) |
|---|---|
| ![](before-beat15-ultra.jpg) | ![](beat15-ultra.jpg) |
| ![](before-storm-ultra.jpg) | ![](storm-ultra.jpg) |

| After, Ultra | After, High |
|---|---|
| ![](sky15-ultra.jpg) | ![](sky15-high.jpg) |
| ![](shelf-ultra.jpg) | ![](shelf-high.jpg) |

The demo autopilot's heading differs between runs, so the before/after pairs aren't the same framing.

**Honest read.**
- The size mix is the clearest change: many small puffs among fewer towers, instead of one billow size.
- Ultra's near clouds are now hard-edged and grain-free. They can look sculpted, though.
- High, which keeps the cap, is softer, and to my eye reads more naturally in `sky15`.
- Some legacy problems remain on both tiers: flat, wind-smeared shapes and thin vertical columns. They were in the
  before shots too.

The next blind round should judge Ultra against High. If the soft High look wins, the Ultra step fit can stay with
the cap pulled back.

## Cost (Ultra / High, GPU clouds+fog slice, ms)

| View | Before | After |
|---|---|---|
| beat15 | 1.60 / 0.46 | 1.95 / 0.52 |
| storm | 3.55 / 0.63 | 1.67 / 0.50 |
| sky15 | – | 2.29 / 0.59 |
| shelf | – | 1.58 / 0.41 |

Frame rates are unchanged within run noise (Ultra is CPU-bound at about 68 fps; High about 71).
