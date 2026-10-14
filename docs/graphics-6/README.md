# Graphics G6: fixing the tells

Bean marked all four blind packs. He caught 34 of 35 game frames: skies 10/10, boats and crews 10/10, the whole game
30/30, and round 7 19/20. Only the marina masts seen from the shore passed as real. G6 fixes what his reasons named,
in priority order. Bean's eight J/22 lesson photos (`Data/Reference/raw/j22-lessons`, git-ignored because they show
faces) were the reference for the crew, the deck and the water.

**Round 8:** `game/game-01.png` to `game-10.png` are the ten round 7 scenes recaptured with the same arguments
(`docs/graphics-5/game/final.csv`): High, capture mode, 1440x1080. The cloud pairs them with the same ten photos.
`compare/` puts each round 7 frame next to its G6 frame.

## Fixes

| # | Bean's reason | What changed | Before / after |
|---|---|---|---|
| 1 | "Clouds have a lot of noise", "very noisy" (six mentions) | The grain was optical depth per march step. A view ray near the horizon takes 600 m steps and a shadow ray 400 m steps, and the storm went opaque inside one, so each pixel was lit at whatever depth its jittered sample hit. The material now caps optical depth per step (view and shadow) and filters its noise at the step. The overcast deck is capped by the view step, so it stays grey, and its coverage is 1.0 (no blue holes). | [game-04](compare/game-04.jpg), [game-08](compare/game-08.jpg), [game-01](compare/game-01.jpg) |
| 2 | Odd tall trees, box houses (four mentions) | **Houses** come from the G2 footprints (`Tools/terrain/build_houses.py`, `HouseKit.cpp`): 35k houses on the lake, each with its lidar eave and ridge, roof shape, NAIP roof colour and L, T or U wings. Within 400 m of the water they get windows, doors and garage doors; beyond that the windows are painted on. They're baked into 553 Nanite tiles. **Trees** are the G2 lidar crowns (`Tools/terrain/build_crowns.py`, `PlaceCrownTrees`): 279k trees at their real positions, heights and crown widths, all of them within 400 m of the water and one in three beyond. Species follow the crown's shape. The tree models' opaque cores are smaller, smooth and shaded, so they no longer show as faceted green balls. | [game-09](compare/game-09.jpg), [game-03](compare/game-03.jpg), [game-10](compare/game-10.jpg) |
| 3 | Boats and crew lack close-up detail; "all the boats are exactly the same" | **Marina:** six dresses per keelboat (`build_berthed.py` variants), one per slip. They vary the cover colour (navy, burgundy, green, faded tan), use a flaked main under sail ties or a canvas cockpit cover, bag the jib or roll it on its stay, add dodgers on the Catalinas, vary the fenders, and add gear: cooler, bucket, boat hook, tiller cover, cushions, a Mercury outboard on its bracket, a burgee. **Player's J/22:** self-tailing winches, cam cleats, blocks, coiled tails, the jib sheet and tiller extension in the crew's hands, grey teak toe rails, and beige grimy non-skid (from the photos). **Crew:** the club's royal blue Type III vests (light blue piping, three grey chest straps with black buckles, a strap down each front panel). Each is tailored over that sailor's polo and skinned like it (`build_vest.py`, `SKM_<Role>_Vest`), so it wraps the body however they sit. | [game-06](compare/game-06.jpg), [game-07](compare/game-07.jpg), [game-02](compare/game-02.jpg) |
| 4 | "Sails are too white and don't have wrinkles or cloth feel" | Off-white Dacron (0.70 albedo, was 0.82). It yellows toward the leech and head, each panel a little differently, with a greyed foot and a few mildew specks. Flaking fold lines, stress wrinkles from the clew and seam pucker go into the normal. Folds read darker and rougher than the resin sheen around them. | [game-04](compare/game-04.jpg), [game-06](compare/game-06.jpg) |
| 5 | The container ship is low detail | A five-tier house with window bands and rails on every deck, bridge wings, radar mast, a funnel with its band, three cranes stowed along the port side, lashing bridges, bulwark rails, windlasses, bollards, hawse pipes, and freefall and rescue boats. The containers are corrugated, with corner castings and lock bars. Rust weeps from the deck edge (`M_WorldSurface` pattern 8). The old ship's stripes were a UV bug: every vessel's box UVs were projected along X. | [ship](compare/ship.jpg) |
| 6 | Odd far water reflections from the drone | Slope too fine to resolve now counts as roughness (Cox and Munk), so a breeze never mirrors like a calm. Bare clay and the wet band appear only within 14 m of open water: a cove's head no longer reads as a glossy mud plain. | [game-03](compare/game-03.jpg) |
| 7 | The slip photo has the boom down and sails stowed | Tied up in her slip, a keelboat wears her berthed dress: sails stowed, cover on, boom on the centreline. Casting off (T) hoists the sails. | [game-07](compare/game-07.jpg) |

Also changed: the Gulf's water is greener and less teal, and house windows light only at dusk, not in a storm's gloom.
`-SailingClassicTrees`, `-SailingClassicHouses` and `-SailingNoPolo` show the old trees, houses and crew clothes.

## Cost

The lidar crowns tripled the shore's trees, and the first bench missed the High gate badly: marina 36.5 fps, slip 37.2.
Measuring with `-SailingClassicTrees` and `-SailingClassicHouses` showed the houses cost nothing measurable. The trees
cost two things:

- Leaf cards out to 600 m: 8 ms of base pass at the marina.
- The far crowns' virtual shadow pages: 6.5 ms at the slip.

The trees now come in three bands:

| Band | High | Medium |
|---|---|---|
| Leaf cards | to 250 m (was 600) | to 200 m (was 350) |
| Opaque crowns with shadows | to 1 km | to 600 m |
| Opaque crowns, no shadows | beyond | beyond |

The vests use one subdivision (38k triangles, not 85k). Measuring args: `-SailingNearTrees`, `-SailingMidTrees` and
`-SailingFarTreeShadows=1`.

Results of `scripts/bench-visual.sh 12 g6b Medium High` on the packaged build (full table in `bench-visual.csv`;
screenshots in `bench/`):

| View | Medium fps (G5 -> G6) | High fps (G5 -> G6) |
|---|---|---|
| beam8 | 90.6 -> 91.6 | 50.4 -> 52.3 |
| beat15 | 88.5 -> 90.8 | 50.2 -> 52.0 |
| storm | 81.5 -> 77.3 | 48.4 -> 47.5 |
| marina | 84.5 -> 88.1 | 46.9 -> 49.2 |
| coast-day | 81.5 -> 84.5 | 47.3 -> 50.0 |
| coast-night | 107.8 -> 104.7 | 54.0 -> 52.7 |
| gulf-sea | 108.5 -> 111.3 | 59.3 -> 59.8 |
| helm-eye | 80.4 -> 84.0 | 43.1 -> 44.9 (reruns 45.0, 45.6) |
| slip | 74.0 -> 75.1 | 45.3 -> 47.3 |
| bridge | 91.2 -> 98.9 | 50.3 -> 54.0 |
| crew | 68.5 -> 73.8 | 44.9 -> 46.6 |
| marina-night | 88.7 -> 81.4 | 54.8 -> 51.8 |

Every view holds Medium 60 and High 45. Helm-eye is on the line, as it was in G5. Tests: 94 passed, 0 failed.

## Open

- The vests' armholes are ragged where the polo's panels end, and the bigger helm's sleeves sometimes show through at
  the shoulder.
- Big flat-roofed commercial blocks are still plain boxes with painted windows (game-10's right side).
- The Mercury outboard and the drive-on lifts with blue floats from the photos: the outboard is on two marina dresses
  and not yet on the player's boat; no lifts yet.
- The townhouses behind the Rush Creek docks take their colours from NAIP and the house kit's wall palette, not the
  photos' grey-blue.
