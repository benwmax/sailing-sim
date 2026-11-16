# Environment loop: shore, grass and buildings (Track 0, Nov 16 2026)

Bean's ask (Nov 16): the shoreline, grass and buildings look low quality up close. The plan, with the assessment, the
ten tracks and the eleven decisions Bean took ("go with your picks", Nov 16 20:37 UTC), is the artifact "Shore, Grass
and Buildings Plan" (https://claude.ai/artifact/FMpfBPUrLhUvUmFr3eEf9B). This page is Track 0, the foundation: the
fixed shore stations, the shared size card, the texture sharpness rule and the tools every other track uses. Nothing
here changes what the game loads. The loop extends the rock loop's (`docs/shore-loop/`, whose four rock stations stay
in `Tools/shoreloop/stations.csv`) and the texture loop's (`docs/texture-loop/`).

Decisions that set the numbers here: design for a boat **15 m** off the bank at eye height, hold up at **5 m**, photo
mode to 2 m at the club only; the club and 1 km each side first, then the lesson area, then the lake by rule; summer and
winter-dormant first; CC0 first, Megascans through Bean's Fab sign-in and git-ignored; $0 by default with $100 held, asked
per purchase; Medium gets the textures and the building kit but no 3D lawn grass; lit windows with fake interiors, no
people on shore.

## Distance bands

| Band | From the camera | Must hold | Asset form | Texture sharpness |
| --- | --- | --- | --- | --- |
| Hero | 0 to 30 m | blades, stones, bark, brick relief, window depth, a messy wet edge, no repeat in a frame | full model, full textures | 100 px a metre (1 cm a pixel) |
| Near | 30 to 150 m | right materials and colour, real window and door shapes, varied roofs, tufted grass edge | full model, smaller textures | 50 px a metre |
| Mid | 150 to 600 m | silhouette, colour, variety street by street | light copy (the re-baked house tiles) | 12.5 px a metre |
| Far | past 600 m | as today | unchanged | |

Why 1 cm a pixel: one screen pixel at 1920 px across the 80 degree lens covers 2.6 mm at 3 m, 8.7 mm at 10 m and 13 mm
at 15 m (`python3 Tools/envloop/texel.py screen 15`), so 1 cm is sharp at the design distance; at the 5 m hold, relief,
decals and detail maps carry the rest. Ultra loads textures at full size, High at half, Medium at a quarter
(`size_card.json` `texture.tier_scale`). `texel.py need <tile m>` gives the pixels per tier; `texel.py check <px> <tile m>
<band>` checks one.

## The loop (every asset, every track)

1. **Card**: `Tools/envloop/cards/<track folder>/<asset>.json`, from `cards/_template.json`: what it is, where it appears,
   its bands, the size-card rows it uses, measured sizes once built, textures (px, tile metres, band), triangles,
   variety it adds, references with licences, stations, status. `python3 Tools/envloop/check_card.py --all` holds every
   card to the size card, the sharpness rule, the station list and the licence rules.
2. **Reference pack**: six to twenty photos of the real thing on this lake or one like it. Links, licences and
   measurements go in the card; the photos stay in git-ignored `Data/Reference/raw/` (`Tools/texloop/fetch_refs.py` fetches
   linked ones). Bean's own photos with the grey card first. No people, faces, plates or house numbers.
3. **Size card**: `Tools/envloop/size_card.json`, 97 rows of real dimensions with a source each (doors 0.91 x 2.03 m, the
   modular brick course 67.7 mm and the king-size 76.2, lap siding 150 mm, a shingle row 143 mm, a dock board 140 mm,
   mown bermuda 40-60 mm, a bulkhead cap 300 mm, tree heights per species, props). Tolerance 5 percent, or inside a row's
   range. Add a row with its source before modelling anything new.
4. **Build** by script: shapes in `Tools/blender/`, materials in a new `scripts/make_env_materials.py` (not
   `make_materials.py`, the merge hotspot), one material pull request at a time.
5. **Standard renders**: `python3 Tools/envloop/render_bands.py --asset model.glb (or --builder build.py) --out DIR
   [--ref photo.jpg]` renders at 3, 15 and 60 m from eye height in midday sun, low sun and overcast, with a 1.75 m scale
   pole, the game's 80 degree lens, beside the reference; one sheet plus a json (triangles, size). Needs Python with
   `bpy` (`pip install bpy==5.1.2`, as the rock loop).
6. **Six checks**: `python3 Tools/envloop/score.py <card> [--colour ...] [--repeat ...] [--bands ...] [--milestone]`
   writes `Tools/envloop/scores/<asset>.json`:
   1. sizes within 5 percent of the size card;
   2. colour: Lab a*b* within 6 of a grey-card photo (`Tools/texloop/measure.py`), pending until one exists;
   3. no repeat inside a 40 m frame: `repeat_check.py tile <texture> <tile m>` lays a texture over 40 x 40 m (or
      `image` on a render) and fails if the autocorrelation's strongest off-centre peak is 0.35 or more. A plain tiled
      texture scores near 1, and a colour wash multiplied over it does not fix that: ground and walls need stochastic or
      layered tiling;
   4. variety: each track's counts in `tracks.json` (eight windows, five doors, ten edge types, nine tree species with
      three models each, thirty clutter props...), judged at a track milestone (`--milestone`);
   5. blind review: `blind_pack.py ab <old> <new>` and `photo <game> <photo>` make shuffled, metadata-free pairs for three
      fresh reviewers; `blind_pack.py record` files the answers in `Tools/envloop/reviews/<asset>.json`. Kept when new wins
      2 of 3, and at 15 m when at least one of three can't tell the game from the photo. Tell reviewers the sides are
      shuffled and "can't tell" is allowed: they lean right;
   6. budget: triangles and texture memory per tier against the card and the track; frame time is the Mac's and PC's.
7. **In-game still** at the stations (below), before beside after: `python3 Tools/envloop/make_sheet.py --before DIR
   --after DIR --out sheet.jpg [--stations ...]`. This is the step that needs the PC or Mac.
8. **Bean's look**: a one-page sheet at each track milestone; he says go, change or stop.

Each track is cut into slices, one pull request each, with an independent review. Until the Nov 21 slice ships, only
the cloud halves run: Tools and docs pull requests (each needs Bean's `bean-approved` label because it touches
`Tools/`), nothing the game loads, no gate time.

## The ten stations

`Tools/envloop/stations.json` (all the numbers) and `stations.csv` (capture-scenes format: 30 scenes,
`env-<station>-<05|15|60>m`). Each station is one piece of shore and its direction straight out to the lake, seen from a
boat at 5 m (hold), 15 m (design) and 60 m (near band) along that line, 2 m above the water with the Drone capture
(80 degrees), 15:00 on 15 June at pool level in the afternoon breeze. The boat is put 35 m further out behind the camera
(`-SailingStartAt`, `-SailingKeepStart`) and the camera fixed relative to it (`-SailingCamWorld`), so she is out of frame.

| Station | id | Subject (map N, E m) | Looking (deg, 15 m) | PC "before" still, Nov 16 |
| --- | --- | --- | --- | --- |
| Club lawn | `club-lawn` | 80, 17 | 80 | 01-clubhouse |
| Club beach (low bank north of the club) | `club-beach` | 126, -1 | 70 | 07-natural-bank |
| Club breakwater | `breakwater` | -24, 61 | 80 | 02-riprap |
| Residential street A (Rowlett) | `residential-a` | 8680, 2115 | 154 | 03-residential |
| Residential street B | `residential-b` | 6554, 1344 | 109 | none yet |
| Bulkhead lot (bulkhead, boathouse and lift) | `bulkhead` | 8658, 2073 | 147 | 04-house-bulkhead (seed 8 m east, so the lift posts sit at the side of the view) |
| Private dock (a mapped pier) | `private-dock` | 8160, 1698 | 17 | 05-dock |
| Wooded bank | `wooded` | 2488, -3717 | 291 | 06-wooded |
| Natural clay cut bank | `clay-bank` | 4890, -1614 | 356 | none yet |
| Bridge shore (I-30 west landfall) | `bridge` | 7234, 765 | 327 | 08-bridge |

How they were fixed (`python3 Tools/envloop/pick_stations.py`, about 5 minutes; run once, then left alone so every
before and after is from the same place): eight start from the PC's before stills of Nov 16 (inputs branch,
`Inputs/bench/env-before-nov16/args.csv`): that camera's bearing finds the bank, then the bank's own normal (land and water
centroids within 20 m) sets the line. Two are found by rule: street B is the stretch with the most banked lots within
60 m, 2 km or more from street A, its subject lot without a boathouse (mixed banks and wall finishes scored up); the clay
bank is the nearest to the club with 1.5 m of rise within 6 m of the water, dry 15 to 60 m inland (mainland, not an
island or the dam), no houses within 100 m and three crowns or fewer on the face. The breakwater counts its distances
from the toe stones (5.5 m off its centreline); the private dock looks at the pier from its open-water side, 25 degrees
off square toward its head (straight out from the bank the pier would run at the camera).

Every camera is checked: over water, open water all the way to the bank, not within 4 m of a map dock, not inside one of
the generated boathouses or the club's docks, and the boat afloat in a metre or more. `lake.py` reads the bakes the way
the game does (`FLakeTerrain::HeightAt` with the 1 m shore detail, `LoadHouses`) and mirrors `HouseKit.cpp`'s lot dressing
(the street side, the bank type from `Hash01(K, 51)`: bulkhead under 0.55, riprap to 0.85, natural above; the boathouse
rule), so a station picked here is the same bank in the game. On today's bakes 992 full-detail houses have a dressed lot at
the water: 551 bulkhead (177 with a boathouse), 274 riprap (105 with one), 167 natural; 12,319 more are too far from it. If `HouseKit.cpp`'s rules
change, change `lake.py` too (`test_envloop.py` holds the hash to the C++ arithmetic and one lot to the PC's still).

`python3 Tools/envloop/station_maps.py OUT` draws each station from above (ground and water, houses, crowns, docks,
generated boathouses, the three cameras and their view). The maps of Nov 16 are in the project files
(`shore-env/track0/maps/`). Pictures stay out of git from the cloud (no Git LFS there).

Capture on the PC (uncooked, as the before set): `scripts\windows\capture-scenes-win.ps1` with this CSV, or on the Mac
`SCENES=Tools/envloop/stations.csv OUT=<dir> scripts/capture-scenes.sh 8`. A winter-dormant set adds `-SailingDate=2026-01-15`
(Track A's second season).

## Today's frame cost and the shore's share

`python3 Tools/envloop/frame_cost.py plan --platform pc|mac [--quality Ultra|High|Medium]` prints the bench runs: each
station's 15 m camera on the packaged build, facing the bank and, from the same spot, turned to open water. `collect DIR`
reads the copied `bench.json` files and writes `frame_cost.csv` with the GPU time of each and the difference (the shore's
share, and the base slice's, where geometry and shadows land). The plan's proposed shares (Ultra 4.5 ms, High 3.0, Medium
1.5) are checked against this at the worst station. Uncooked runs are not representative of frame rate.

### Baseline, Nov 16 2026 (PC, before any track)

RTX 4090, Development package of main 00b43920, Ultra, 1920x1080 windowed, one warm-up then the 20 runs
(`baseline/frame_cost_pc_ultra_nov16.csv`, bench files on `inputs` 1a10160a `Inputs/bench/env-stations-nov16/cost/`).

| Station (15 m) | fps | GPU ms, bank | GPU ms, open water | Shore's share ms | Base slice share ms |
| --- | --- | --- | --- | --- | --- |
| club-lawn | 58.9 | 7.35 | 7.41 | -0.06 | 0.12 |
| club-beach | 54.3 | 7.28 | 7.08 | 0.20 | 0.28 |
| breakwater | 55.0 | 7.70 | 7.47 | 0.23 | -0.07 |
| residential-a | 60.5 | 7.19 | 7.07 | 0.12 | 0.22 |
| residential-b | 57.9 | 7.73 | 7.35 | 0.38 | 0.24 |
| bulkhead (old cameras) | 62.5 | 7.43 | 7.31 | 0.12 | 0.12 |
| private-dock | 62.5 | 7.30 | 7.66 | -0.36 | -0.10 |
| wooded | 59.2 | 7.33 | 7.49 | -0.16 | 0.10 |
| clay-bank | 58.4 | 7.38 | 7.28 | 0.10 | 0.03 |
| bridge | 64.3 | 6.91 | 6.98 | -0.07 | -0.08 |

Today's shore costs nothing measurable: every station's share is within run-to-run noise (about +-0.4 ms), so the whole
Ultra share (4.5 ms) is still free for the tracks. These runs are CPU-bound (render thread 15-18 ms, game 11.5-13.3 ms,
GPU about 9 ms a frame), so fps here says nothing about the shore: judge each track by the GPU slices. A 4K run would
make the GPU the limit if a track needs it.

## Region packs

What each track makes for this lake, and where it goes, is listed in the region pack `Tools/envloop/packs/north-texas-lake/`
(one file per track, placement by rule from map data, buildings as parts plus recipes): [packs.md](packs.md).

## Where each track starts

| Track | Starts from | Its stations | Folder |
| --- | --- | --- | --- |
| A Ground textures | size card rows `grass.*`, the texture rule (a 2 m ground tile is 256 px on Ultra), `repeat_check.py` (stochastic or layered tiling needed), 8 surfaces x 2 seasons (`packs/north-texas-lake/ground.json`) | club-lawn, club-beach, clay-bank, residential-a, wooded | `cards/ground` |
| B 3D grass | `grass.*` and `plant.*` rows, draw distances (Ultra 100 m, High 60, Medium none), 6 species | club-lawn, club-beach, clay-bank, wooded | `cards/grass` |
| C Shoreline types | `bulkhead.*`, `sheet_pile.*`, `limestone_block.*`, `timber_wall.*`, `riprap.*`, `launch_ramp.*`; `lake.py lot()` says which lots get which bank | breakwater, bulkhead, residential-a/b, clay-bank, club-beach, bridge | `cards/shoreline` |
| D Trees up close | `tree.*` rows for nine species, 3 models each | wooded, club-lawn, residential-b, bridge | `cards/trees` |
| E Building parts kit | `door.*`, `window.*`, `brick.*`, `siding.*`, `roof.*`, `gutter.*`, `trim.*`, `porch.*`, `stair.*`, `ac.*`; trim sheet at the near band's 50 px/m (4096 px over 4 m) | residential-a/b, bulkhead, club-lawn | `cards/buildings` |
| F Docks and boathouses | `dock.*`, `boathouse.*`, `boat_lift.*` | private-dock, bulkhead, residential-a | `cards/docks` |
| G Clubhouse | Bean's clubhouse photos, then E's parts | club-lawn, club-beach | `cards/clubhouse` |
| H Yard clutter | `prop.*` rows, 30 props | residential-a/b, private-dock | `cards/clutter` |
| I Rollout | all ten stations, `frame_cost.py` on each tier | all | |

## Files

| File | What |
| --- | --- |
| `Tools/envloop/lake.py` | reads the lake's bakes like the game; `lot(k)` mirrors HouseKit's lot dressing |
| `Tools/envloop/pick_stations.py` | fixed the ten stations (`stations.json`, `stations.csv`) |
| `Tools/envloop/station_maps.py` | the stations from above |
| `Tools/envloop/size_card.json` | shared real sizes, bands, texture rule |
| `Tools/envloop/tracks.json` | per track: card folder, stations, variety targets, budgets, pack file |
| `Tools/envloop/pack.py`, `packs/` | region packs and their checks ([packs.md](packs.md)) |
| `Tools/envloop/cards/_template.json` | the card every asset starts from |
| `Tools/envloop/check_card.py` | card checks |
| `Tools/envloop/texel.py` | texture sharpness and memory |
| `Tools/envloop/render_bands.py` | standard renders (Blender `bpy`) |
| `Tools/envloop/repeat_check.py` | the 40 m repeat check |
| `Tools/envloop/blind_pack.py` | blind A/B and photo-or-game packs, answers to `reviews/` |
| `Tools/envloop/score.py` | the six checks in one score file |
| `Tools/envloop/make_sheet.py` | station before/after sheet |
| `Tools/envloop/frame_cost.py` | station benches and the shore's share |
| `Tools/envloop/test_envloop.py` | self-tests (the lake ones need `git lfs pull --include "Content/TerrainData/RayHubbard.*"`) |

Python 3 with numpy, Pillow (scipy for the colour measure); `render_bands.py` also needs `bpy`. None of it needs Unreal.
