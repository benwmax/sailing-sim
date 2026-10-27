# High headroom after the macOS 27 update (Oct 27 2026)

At full resolution (#343) four High views sat within 4 fps of the 45 floor: crew 46.7, slip 47.9, coast-day 48.2 and
stream-run 48.5.

## What the update changed

The last High numbers from before the update (Oct 19-20, `Artifacts/gate/bench-world.csv`) were taken with the
resolution governor active, so this compares today's build at those same render scales (packaged, High):

| View @ scale | fps then → now | GPU ms then → now | render ms | RHI ms | game ms |
|---|---|---|---|---|---|
| crew @ 82% | 49.0 → 53.0 | 18.34 → 17.59 | 19.75 → 18.88 | 3.78 → 3.52 | (n/a) → 4.08 |
| slip @ 94% | 53.6 → 51.0 | 18.13 → 18.29 | 18.33 → 19.60 | 2.95 → 4.04 | 2.65 → 3.58 |
| coast-day @ 94% | 54.2 → 52.4 | 17.22 → 17.84 | 18.15 → 19.07 | 3.31 → 3.58 | 3.08 → 4.40 |

At the same scale the GPU barely moved (crew is faster). Slip and coast-day gained about 1 ms of render, RHI and game
thread, a week of content and the OS together. The "3-6 fps lost" was mostly benching at 100%, not the update.

## Where the High frame goes (ProfileGPU, 100%)

| Pass | crew | slip | coast-day |
|---|---|---|---|
| ShadowDepths (virtual shadow maps) | 3.9 | 2.6 | 3.7 |
| Lumen DiffuseIndirectAndAO | 2.4 | 3.3 | 2.0 |
| Nanite VisBuffer | 1.8 | 2.2 | - |
| Single Layer Water | 1.6 | 1.3 | 2.5 |
| Hair (strands, crew only) | 1.1 | - | - |
| Volumetric fog (mostly a timer wait) | 0.85 | 0.78 | 0.74 |
| Sky cache strip (`M_CloudCache`) | 0.65 | - | - |

High uses Epic scalability, whose `r.Shadow.Virtual.ResolutionLodBiasDirectional` is -1.5 (still and moving casters).
That puts the sun's shadow map at about three times the screen's resolution each way. The levels below Epic use 0.

## The change

On High, with the Shadows row on Auto, the sun's VSM bias is -0.5 (`ASailingGameMode::ApplyQualitySettings`). It is set
back to the scalability level's own value on any other tier or row. Ultra keeps -1.5.

Measured interleaved: main, then this, three pairs per view, packaged, 100%, same session.

| View | fps main → this | GPU ms main → this | Saved |
|---|---|---|---|
| crew | 44.6 → 47.1 | 20.77 → 19.59 | 1.18 ms |
| slip | 45.9 → 47.4 | 20.68 → 19.75 | 0.93 ms |
| coast-day | 47.1 → 50.3 | 20.10 → 18.83 | 1.27 ms |

The Mac ran about 1 ms slower in that hour than earlier, so only interleaved numbers compare.

Stills (`*-shadows.jpg`, main left, -0.5 right, full-resolution crops): the crew's shadows on deck, the marina's mast and
boat shadows on the docks, and the boat's own shadows look the same.

## What else was tried, and why 3 ms isn't here without a visible change

| Option | Saving | Why it isn't in this PR |
|---|---|---|
| VSM bias +0.5 (instead of -0.5) | a further 0.3-0.9 ms | The map would be coarser than the screen's pixels; risks the crisp rig and crew shadows up close. |
| Lumen `ScreenProbeGather.DownsampleFactor` 32 | none | High already runs 32. |
| Crew hair as cards on the Mac | 1.3 ms (crew view only) | The Mac has been SM6 since the project began, so near grooms draw strands, not the cards the code comment assumes. Cards would change the look. |
| Fewer SMRT shadow rays | lost in the noise | - |
| Volumetric fog conservative depth off | 0.3 ms | An experimental engine path; most of the pass's 1.1 ms is a wait. |
| Sky cache refreshed every 8 s (from 4) | about 0.3 ms | Risks a visible step at the 5 km seam. |

## Gate (`--scope all`, main f501e684 + this): pass

Tests 239/239. Every view passes its floor (Medium 60, High 45). The views on High:

| View | fps (#345 gate) | fps (this) | GPU ms | GPU ms (this) | base ms | base ms (this) |
|---|---|---|---|---|---|---|
| beam8 | 55.8 | 58.2 | 16.62 | 15.75 | 7.71 | 6.87 |
| beat15 | 51.2 | 55.7 | 17.67 | 16.1 | 7.98 | 6.79 |
| storm | 45.5 | 48.7 | 21.69 | 19.81 | 8.42 | 7.38 |
| marina | 52.4 | 57.6 | 17.97 | 16.11 | 7.58 | 6.62 |
| coast-day | 48.2 | 52.9 | 19.47 | 17.67 | 9.17 | 7.37 |
| coast-night | 58.4 | 59.9 | 16.28 | 15.86 | 6.63 | 6.33 |
| gulf-sea | 52.8 | 60.9 | 16.28 | 15.13 | 6.76 | 5.82 |
| helm-eye | 50.7 | 58.2 | 18.67 | 16.28 | 9.36 | 7.55 |
| slip | 47.9 | 49.9 | 19.79 | 18.66 | 8.84 | 8.03 |
| bridge | 56.6 | 60.2 | 16.57 | 15.23 | 6.78 | 5.95 |
| crew | 46.7 | 50.1 | 20.06 | 18.26 | 10.56 | 8.99 |
| marina-night | 54.7 | 55.8 | 17.3 | 16.67 | 7.79 | 7.55 |
| far-coast | 56.1 | 60.1 | 16.59 | 15.19 | 7.04 | 5.9 |
| far-coast-night | 75.0 | 76.9 | 12.08 | 11.62 | 3.5 | 3.43 |
| marseille-port | 51.1 | 53.4 | 17.8 | 17.08 | 7.41 | 6.17 |
| stream-run | 48.5 | 51.3 | 19.45 | 18.47 | 9.41 | 8.08 |

The "#345 gate" column is the previous full gate on main. Every run in both gates reported `foreground` 0.0 (most likely
a locked screen), so the two gates' differences carry the session-to-session noise. The interleaved table above is the
measure of this change.
