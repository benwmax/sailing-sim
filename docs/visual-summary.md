# Visual realism, V1 to V7: summary

The plan is the Claude Doc "Sailing Game: Visual Realism Plan". Each phase has its own README, bench and comparison under `docs/visual-N/`.

Everything below runs on Bean's Mac (M5 Pro), packaged build. There are three tiers:
- **Low** keeps the Phase 8 look and cost (about 119 fps).
- **Medium** (default) and **High** carry the new work.

## What each phase delivered

| Phase | Delivered |
| --- | --- |
| V1 rendering pipeline | Substrate materials, Lumen GI and reflections (hardware ray tracing on High), virtual shadow maps, TAA, physical camera with metered exposure, the lens profile; per-tier settings in `VisualPipeline.h`; GPU time per budget slice in every bench. |
| V2 the J/22 model | The J/22 built in Blender from the physics (the hull below the waterline is the physics hull), deck, fittings, rig with live standing and running rigging, mast bend, the `MI_Boat_*` Substrate library with wet and dry surfaces. |
| V3 sails and crew | Cloth sails shaped by the physics strips (flogging, leech flutter, luff wrinkles, spinnaker collapse), seams, battens, insignia and numbers, telltales from the same rules as the coach; proportioned, rigged sailors posed from the physics crew model. |
| V4 water | The physics' long waves drawn exactly with Gerstner chop, an FFT of the same spectrum for the short waves, whitecaps where crests fold, wakes from a wave-equation grid with every hull, Single Layer Water per water body, shore depth, spray. |
| V5 sky and storm | Layered volumetric clouds painted from the weather, a storm built on the physics gust front (shelf, rain core, anvil), stars, Milky Way and the moon's phase, haze per air mass, lightning, lens water. |
| V6 Rush Creek and the world | The club's marina, clubhouse and Bean's slip; Nanite trees; bridges with traffic; every OSM building; riprap and jetties; chart landmarks; real navaid models riding the waves. |
| V7 fleet, crew and polish | The other seven boats modelled from their physics, with class sail layouts; a full marina of rigged neighbours on glassy water; MetaHuman crew on Medium and High; sound layers, spatialised world sources and a recorded-sample slot; cockpit camera and photo-mode depth of field; the sea kept out of cockpits; a resolution governor on High. |

## Comparison scores, before and after

Twelve Phase 8 reference scenes, scored 1 (the same as the real clip) to 5 (obviously wrong). Each cell is the mean over the twelve, with the number of scenes above 2 in brackets:

| | boat | sails | light | water | sky |
| --- | --- | --- | --- | --- | --- |
| Phase 8 | 3.75 (12) | 3.17 (12) | 3.00 (12) | 2.00 (1) | 2.17 (2) |
| V1 | 3.75 (12) | 3.17 (12) | 2.17 (2) | 2.00 (1) | 2.17 (2) |
| V2 | 3.33 (11) | 3.17 (12) | 2.17 (2) | 2.00 (1) | 2.17 (2) |
| V3 | 2.83 (7) | 2.42 (5) | 2.17 (2) | 2.00 (1) | 2.17 (2) |
| V4 | 2.83 (7) | 2.42 (5) | 2.17 (2) | 1.92 (0) | 2.17 (2) |
| V5 | 2.83 (7) | 2.42 (5) | 2.17 (2) | 1.92 (0) | 2.08 (1) |
| V7 | 2.00 (0) | 2.00 (0) | 2.08 (1) | 1.92 (0) | 2.08 (1) |

V6 changed the world, not these scenes (V6 scored its own marina and causeway views). Per scene, Phase 8 against V7:

| Scene | boat | sails | light | water | sky |
| --- | --- | --- | --- | --- | --- |
| j22-heavy-chase | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| j22-light-chase | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| j22-moderate-chase | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| j22-helm-reservoir | 3 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| j22-actioncam-lake | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| rh-drone-cat | 4 → 2 | 3 → 2 | 3 → 2 | 1 → 1 | 2 → 2 |
| rh-c30-evening | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| storm-lake | 3 → 2 | 4 → 2 | 3 → 3 | 2 → 2 | 3 → 3 |
| squall-lake | 3 → 2 | 4 → 2 | 3 → 2 | 2 → 2 | 3 → 2 |
| gulf-passage | 4 → 2 | 3 → 2 | 3 → 2 | 3 → 2 | 2 → 2 |
| bay-hobie | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |
| sunfish-reach | 4 → 2 | 3 → 2 | 3 → 2 | 2 → 2 | 2 → 2 |

Still above 2: the storm-lake light and sky (3, open). In the V6 world views:
- the marina went 4 → 3 (V6) → 2 (V7);
- the causeway went 4 → 2 (V6);
- the riprap shore is 3 (open).

## Frame rate per tier

Average fps, slowest to fastest view, packaged build:

| Phase | Medium avg fps | High avg fps |
| --- | --- | --- |
| Phase 8 (before V1) | 66–105 (8 views) | 45–68 (8 views) |
| V1 | 80–119 (8 views) | 48–74 (8 views) |
| V2 | 82–119 (8 views) | 46–71 (8 views) |
| V3 | 80–119 (8 views) | 46–65 (8 views) |
| V4 | 77–119 (8 views) | 48–78 (8 views) |
| V5 | 88–113 (8 views) | 51–67 (8 views) |
| V6 | 82–119 (11 views) | 47–72 (11 views) |
| V7 | 76–117 (11 views) | 47–67 (11 views) |

The gate has been Medium ≥ 60 and High ≥ 45 on every view. It is met in every phase:
- V6 added three heavier views (Bean's slip, the I-30 bridge, the marina at night).
- From V7, High holds the line with a resolution governor (82–100% screen percentage).

V7's slowest views are Bean's slip, at 75.7 fps on Medium and 46.7 on High.

## Open items after V7

- **Storm-lake sky and light (3):** the shelf cloud's lip, bright gap and rain wall don't read from under the storm. Distant storm skies show tiled cloud puffs.
- **Riprap shore (3):** the repeated Blender rocks are faceted close up. A scan or a sculpted set would close it.
- **Action-cam crew close-ups:** closed in V7 by the MetaHumans (boat 3 → 2). Remaining:
  - no groom hair (caps instead);
  - faces don't animate;
  - the life jacket is rigid.
- **MetaHumans in the repo:** they are built locally by `scripts/make-metahumans.sh` (git-ignored: size and licence). A fresh clone has the Blender crew until it's run, which needs an Epic sign-in.
- **Medium base pass:** over 4 ms in five views, worst in the marina at 4.98 ms.
- **High:** holds 45 fps by dropping to 82% resolution in the heaviest views.
- **Fleet configs:** the Hobie 16, Corsair 880 and Lagoon 42 disagree with their published beam or LOA.
- **Physics:** three reference checks out of range since Phase 8:
  - J/22 spinnaker peak;
  - Catalina 22 DPN2;
  - Hobie 16 DPN4.
- **Sound:** no recorded samples yet. The slot is ready (Freesound CC0 needs an account and Bean's go-ahead; Bean's own recordings are better).
- **Galveston's piers:** still the legacy walkways.
- **Blind round 6:** published and awaiting marking (https://claude.ai/artifact/GoytX4ZS6gBY1GPpcEGaM7).
