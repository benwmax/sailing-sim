# Visual V6: Rush Creek and the world

The world around the boat is now built on Medium and High:
- **Rush Creek Yacht Club:** the marina, the clubhouse and Bean's slip.
- **Trees:** Nanite trees along the shore.
- **Bridges:** the I-30 bridge and the rest of the bridges, with traffic.
- **Houses:** every OSM building as a house or block.
- **Shore:** riprap breakwaters and jetties.
- **Chart landmarks:** platforms, towers, masts.
- **Navaids:** real buoy and beacon models that ride the waves.
- **Traffic:** the traffic vessels as hull models.
- **Night:** lights at night and a city glow in the sky.
- **Distance:** the earth's curvature.

Everything is generated from code and data, and each structure is replaceable by a scan.

![Bean's slip at Rush Creek, High](bench/slip-high.png)

## Rush Creek Yacht Club (`Marina.h`, `MarinaActor.cpp`, `Content/TerrainData/RayHubbard.marina.json`)

**The layout** is in one JSON file, laid out in the map frame from aerial views and the club's OSM footprint:
- Three floating dock rows with 122 slips, fingers 7.3 m long.
- The shore walkway and two fixed piers.
- The riprap breakwater.
- The clubhouse and the pool.

`FMarina` lays out the slips and fingers. Occupancy (65%) is deterministic.

**Bean's slip** is `rcyc.dock.b.n18`. The Leave-the-Dock drill now starts the J/22 there, bow in and tied to its fingers.

**Generator.** `AMarinaActor::BuildGeometry` draws:
- floating decking on black floats;
- pilings; cleats on every finger; dock boxes; a power pedestal between every two slips;
- dock lamps;
- the clubhouse: lap siding with windows, a hip roof with eaves and fascia, floodlights;
- the pool.

The breakwater is limestone riprap from three Blender rocks. The occupied slips hold J/22 models, scaled 1.0–1.3× as stand-ins for bigger boats. The home slip is kept free.

**Physics.** The same layout is the physics:
- The rows, fingers, piers and breakwater are obstacles.
- The OSM docks and buildings inside the marina are dropped, so what you see is what you hit.

`SailingSim.Lake.Marina` checks:
- every drawn deck is an obstacle;
- the home slip floats a J/22 (2.9 m);
- the boat lies in it with its dock lines and touches nothing.

`ClubBerth` and the other lake tests are unchanged.

**Scans.** Every structure has an id (`rcyc.clubhouse`, `rcyc.dock.b`, ...). An entry in `Content/World/Scans.json` (id → static mesh, authored in the map frame) replaces the generated piece. That is where an iPhone scan of the clubhouse or Bean's own dock goes.

## World kit (`WorldKit.h`, `scripts/make-world-models.sh`)

**How the generators work.** Generators write quads per look (`EKitLook` → `MI_World_*`, UVs in metres) plus the light fixtures. The editor bakes them into Nanite static meshes in tiles (`UWorldKitLibrary::BakeMarina/BakeBridges/BakeShore`). A tile without a bake falls back to a static procedural mesh.

The bake is not optional on High. One marina-wide procedural mesh overflowed the virtual shadow map's non-Nanite marking queue every frame. The bake also cut its base-pass cost.

`make-world-models.sh` runs the Blender generators, imports their output and bakes. Rerun it after changing a generator or the marina layout.

| What | Where | Notes |
| --- | --- | --- |
| Trees | `Tools/blender/build_trees.py`, `TreePlacement.cpp` | Live oak, post oak, cedar elm, red cedar; placed from the canopy map (`SailingSim.Visual.Canopy`: correlation 0.81). Leaf cards near (600 m on High, 350 m on Medium), opaque crowns beyond. Each near tree has an opaque core with only its outer fringe of cards: this halved their cost (High base pass in the marina view 22.7 → 10.1 ms). |
| Bridges | `BuildBridgeGeometry` | By OSM kind: motorway twin decks (girders, pier bents on two or three columns, Jersey barriers, lamp posts with arms), primary and secondary roads, rail (ballast, rails, steel girders), foot bridges. The girders' underside sits where the physics stops a mast. 40 lake ways, 103 Galveston ways, plus the Gulf. |
| Bridge traffic | `ABridgesActor` | Sedans, pickups and semis from Blender, painted per instance, in their lanes at road speed (328 on the lake), every 90–300 m. Head and tail lights glow at night. |
| Shore | `BuildShoreGeometry` | Charted breakwaters, jetties and revetments as a ragged riprap band (282,000 quads around Galveston Bay, the Texas City Dike among them); the lake's private piers on pilings. The breakwater's physics width now matches the drawn waterline (2.2 m). |
| Buildings | `build_houses.py`, `PlaceHouseModels` | Ranch (gable), two-storey (hip), commercial block (flat, parapet, rooftop units), scaled to each of the 11,719 lake and 9,652 coast footprints. Brick, siding or stucco and roof colours per instance. Windows are laid out in world space (`M_HouseWall`); some are lit at night. |
| Landmarks | `build_landmarks.py`, `ALandmarksActor` | The chart's gas-well platforms (235 in the bay), water towers, radio masts, windpumps, refinery stacks, church spires, flagstaffs; scaled to charted heights. |
| Navaids | `build_navaids.py`, `ANavaidsActor` | Can, nun, pillar and sphere buoys; three-pile dolphins with square or triangular dayboards; light towers. Painted in USCG colours with rust streaks and a growth line at the waterline (`M_NavaidPaint`). Buoys heave and tilt with the waves, and their lights ride with them. |
| Traffic hulls | `build_vessels.py`, `APowerVesselActor` | Lofted hulls: a 21 ft centre console, a 70 ft Gulf shrimper with its outriggers, doors and nets, a trawler-yacht committee boat, a towboat with push knees and two hopper barges, a 230 m container ship with a bulbous bow and stacked containers (colour per box). The lights sit on the models' masts and wings. |

**Tiers.** Low keeps the old shapes. Medium and High get everything above; the marina's docks are drawn on all tiers so they match the physics.

**Tide.** On a coast, the bridges, shore and landmarks follow the terrain's tide offset in 2 cm steps.

## Night (`ANightLightsActor`, `M_SkyDome`)

**Point lights.** The generators leave fixtures:
- street lamps on the bridges (12,000 lm);
- dock lamps (1,500 lm);
- the clubhouse floodlights (4,000 lm);
- a light for each waterfront business, meaning big OSM blocks within 80 m of the water: Kemah's boardwalk and the marinas (6,000 lm).

A pool of point lights goes to the fixtures nearest the camera, re-picked four times a second:
- **Medium:** 48, unshadowed.
- **High:** 160, shadowed through MegaLights (`r.MegaLights.EnableForProject` on High).

Lumens are real, scaled into the scene's photometry the same way as the sun.

**Glow.** Lamp heads and windows glow through `MPC_World.Night`. Windows and lamps come on through dusk and under a storm's darkness.

**City glow.** The sky dome draws the nearest big city's light dome on the horizon toward it: Dallas from the lake, Houston from the bay, with Texas City and Fort Worth weighed by distance.

## Distance

The terrain and the water drop by d²/2R, with R = 7/6 of the earth's radius for standard refraction: 8 m at 10 km, 31 m at 20 km. Far shores sink behind the horizon. Trees (when regrouped) and landmarks (each 200 m the camera moves) are placed with the same drop on the CPU, so a water tower's foot goes before its top. Structures within the houses' 8 km cull distance are left as they are: the error there is under a pixel.

## Frame rate and GPU (packaged build, `bench.csv`)

Three views are new: `slip` (Bean's slip, the opening frame of Leave-the-Dock), `bridge` (I-30) and `marina-night`.

| View | Medium | High | Medium GPU ms (base / Lumen / water / clouds+fog) | High base ms |
| --- | --- | --- | --- | --- |
| beam8 | 101.5 | 56.1 | 9.46 (3.56 / 1.36 / 1.6 / 1.87) | 5.68 |
| beat15 | 93.7 | 50.9 | 8.98 (3.2 / 1.42 / 1.63 / 1.66) | 9.22 |
| storm | 88.6 | 53.3 | 11.03 (2.99 / 1.36 / 1.56 / 3.96) | 6.61 |
| marina | 96.4 | 48.6 | 10.46 (4.85 / 1.45 / 1.59 / 1.49) | 10.1 |
| coast-day | 94.3 | 53.5 | 10.04 (4.16 / 1.63 / 1.61 / 1.58) | 8.24 |
| coast-night | 119.1 | 71.6 | 7.74 (1.98 / 1.43 / 1.41 / 1.82) | 4.17 |
| gulf-sea | 118.8 | 72.5 | 7.59 (2.17 / 1.31 / 1.66 / 1.38) | 5.04 |
| helm-eye | 95.4 | 52.9 | 10.61 (3.73 / 1.89 / 1.42 / 2.55) | 9.99 |
| slip | 82.3 | 46.6 | 11.46 (4.32 / 2.95 / 1.57 / 1.51) | 10.2 |
| bridge | 104.3 | 54.3 | 8.91 (3.41 / 1.55 / 1.53 / 1.34) | 8.3 |
| marina-night | 97.8 | 63.0 | 10.57 (2.7 / 3.27 / 1.54 / 2.15) | 4.23 |

**Frame rate: met.** Every view clears the bars: Medium 82–119 fps (≥60), High 46.6–72.5 (≥45). The slip view on High (46.6) has the least margin.

**Base pass on Medium (target ≤4.0 ms): met in eight of eleven views.**
- **Over the target:** marina 4.85, slip 4.32, coast-day 4.16.
- **Not the trees:** with no leaf cards at all, the marina view's base pass is still 4.4 ms. V5's marina view, with none of this content, was already 4.36.
- **What's left:** the houses, far crowns and terrain.

The first V6 bench missed High in three views (marina 34.8 fps). The fixes:
- the hollow tree crowns;
- a 600 m leaf-card radius on High;
- 350 m on Medium.

## Comparison (`compare/index.html`) and blind test (`blind/`)

Side by side with North Texas photos from Commons. Scores: 1 the same, 5 obviously wrong. "Before" is the same camera on Low, which keeps the pre-V6 shapes.

| Frame | Reference | Before → after | Gate (≤2) |
| --- | --- | --- | --- |
| Bridge (I-30 causeway) | Lake Tawakoni causeway | 4 → 2 | Met |
| Rush Creek (slips from the lawn) | Scott's Landing Marina, Lake Grapevine | 4 → 3 | Not met |

The bridge frame now matches its reference: a low concrete causeway on regular bents sitting on the horizon.

The marina frame is short of its reference for three reasons:
- **Boats.** The berthed boats are scaled J/22 models without standing rigging, where the reference's masts carry shrouds.
- **Occupancy.** The slips are 65% full against about 90% in the reference.
- **Water.** The calm-morning lake still ruffles where the reference is a mirror.

**Blind round 5** (`blind/`, https://claude.ai/artifact/7KdSGUqa9K74PsykjdmcYj): 16 stills, eight Commons photos and eight game frames. The game frames are the marina from the shore, the causeway, the riprap shore, lake piers, the container ship, the shrimper, a tow and a channel light at sunset. The answer key is in `blind/answer-key.csv`; don't open it before marking.

## What a scan would replace (`Content/World/Scans.json`)

| Id | Today | A scan would bring |
| --- | --- | --- |
| `rcyc.clubhouse` | OSM footprint, lap siding, hip roof | The real building: porch, doors, signage, materials |
| `rcyc.dock.b` (and `.a`, `.c`) | Generated floating rows | Real decking wear, cleat and box positions, lights, utilities |
| `rcyc.dock.b.n18` | Bean's slip, generated | Bean's own finger, lines and fenders |
| `rcyc.breakwater` | Three Blender rocks repeated | The actual riprap |
| `rcyc.walkway`, `rcyc.pier.*` | Generated fixed piers | Rails, ramps, gangways as built |
| Neighbour boats | Scaled J/22 models | The fleet's real boats (a berth model per class is V7 work) |

## Open items carried forward

- **Marina frame (3):** rigged neighbours of mixed classes, fuller slips, a glassy-calm preset.
- **Medium base pass:** over 4 ms in the marina, slip and coast-day views (houses and far crowns).
- **Galveston's piers:** still the legacy walkways. 278 km of them was too heavy to bake at the lake's detail.
- **From V5:** storm-lake sky (3) and the grain in cloud edges, visible again in the overcast blind stills.
