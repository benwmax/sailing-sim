# Shore ground textures (Track A of the shore plan)

Track A of the shore, grass and buildings plan (Bean approved Nov 16 2026): eight real ground surfaces and one layered
ground material that replaces today's painted `M_Terrain` near the camera. This is the cloud half: the textures are
chosen, the material's maths is written and rendered outside the engine, and the loop's checks are run. Nothing the game
loads has changed. Building `M_Ground` in the editor, the terrain's new inputs and the Mac gate come after the Nov 21
slice.

## What changes on screen

Today the ground is one material for the whole lake: the vertex colour the terrain builder paints (grass, woods, the
clay and sand bank, the bed) with a few sine patterns over it. Nothing is a texture. Up close a lawn is one flat
yellow-green, a bank is a smooth tan ramp, and the lake's edge is a darker stripe.

The new material keeps the same inputs and the same layout (where grass, bank, woods and bed are does not move) and
draws each place as a real photo-scanned surface:

| Surface | Where | Source (CC0) | Real size |
|---|---|---|---|
| Mown bermuda lawn | yards and the club lawn (the Mown mask) | ambientCG Grass004 | 1.4 m |
| Rough dry grass | fields, flats, verges, unmown banks | ambientCG Ground013 | about 2 m |
| Blackland clay | eroded faces, bare bank | Poly Haven brown_mud_dry | 1.3 m |
| Limestone gravel | wave-washed shingle on the bank | ambientCG Gravel023 | 1.5 m |
| Sand | the club beach, sandy bank stretches | Poly Haven sand_01 | 1.5 m |
| Wet mud | the swash and the bed under the surface | Poly Haven brown_mud_02 | 1.3 m |
| Cracked dry mud | lake bed left dry under the pool | Poly Haven mud_cracked_dry_03 | 1.5 m |
| Leaf litter | under woods | Poly Haven forest_leaves_02 | 3.0 m |

All eight are CC0 (no attribution needed, commercial use allowed). Each scan is recoloured to a Texas colour on the card
(the region pack `Tools/envloop/ground/packs/north-texas-lake.json`), so the scan supplies the pattern and relief and the card decides the colour. The
lawn and the rough grass each have a summer and a winter-dormant colour (`Season`, 0 to 1).

## How the material works

1. **Weights.** Eight weights from what the terrain already knows: height over the water and over the pool, slope, the
   vertex colour (decoded back into canopy and sandy-or-clay), the Near alpha (open water within 14 m) and a new Mown
   mask. Swash is mud, the dry bed under the pool is cracked crust, the bank is sand or clay with shingle patches,
   steep faces are clay, woods are litter, mown ground is lawn, the rest is rough grass. Band edges are ragged (three
   noise scales), so no zone ends on a straight line.
2. **Two surfaces sampled, the rest flat.** Only the two strongest surfaces are read from the texture arrays; the others
   are drawn as their card colour. The two are joined by their height maps, so grass grows through sand and stones
   stand out of mud instead of a cross-fade.
3. **No repeat.** Each surface is read twice: at its real size, and rotated at 1.618 times that size. A slow noise and
   the height maps choose between them pixel by pixel, so neither tile's repeat survives across a 40 m frame.
4. **Slow wash and stripes.** Brightness drifts by up to 10% at 9 m and 7% at 31 m, grass drifts toward straw in dry
   patches in summer, and the lawn keeps today's mowing stripes at 4%.
5. **Wet band and film.** Today's wet band and algae film, per surface (mud is already wet; sand and clay darken most).
6. **Distance.** Textures fade into the card colours by 150 m (the near band's edge); past that no texture is read.
   Because the card colours are the textures' exact means, the hand-over has no seam.

`Tools/envloop/ground/ground_material.py` is the maths in numpy; `ground_hlsl.py` writes the same maths as the Custom
node's HLSL (`python3 -I Tools/envloop/ground/ground_hlsl.py`). They are kept line for line; `test_ground.py` checks
the card, the weights, the decode of the terrain's own tones and that the HLSL carries the card's constants.

## Region packs (other lakes and coasts)

Nothing in the maths names North Texas. The material has eight roles (lawn, rough, clay, gravel, sand, mud, cracked,
litter) that the weights decide from the terrain; a region pack (`packs/<name>.json`) fills each role with that
region's own scan, real size, summer and dormant colour, roughness and wetting. Every tool takes `--pack`
(default `north-texas-lake`, or `$GROUND_PACK`), and fetched and prepared maps live under `Data/Ground/*/<pack>/`.
A Galveston or Mediterranean pack is one new file plus a fetch, prep and render round; `test_ground.py` checks every
pack in the folder. The terrain's vertex-colour decode is the one regional assumption left in the maths (it reads the
lake's palette from `BuildChunk`); a new world's palette gets its own decode constants at integration. Track 0's
shared pack layout replaces `pack.py`'s paths when it lands.

## Running the loop

```
python3 -I Tools/envloop/ground/fetch_ground.py [--pack north-texas-lake]   # the eight scans, about 200 MB, into Data/Ground/raw/<pack> (git-ignored)
python3 -I Tools/envloop/ground/prep_ground.py           # calibrated maps per tier into Data/Ground/prep/<pack> (needs scipy)
python3 -I Tools/envloop/ground/test_ground.py           # self-checks, no textures needed
cd Tools/envloop/ground && python3 render.py --out ../../../Artifacts/envloop/ground/r1   # about 15 min on 4 cores
python3 -I Tools/envloop/ground/make_pack.py --renders Artifacts/envloop/ground/r1        # blind pack + sheets
python3 -I Tools/envloop/ground/checks.py --renders Artifacts/envloop/ground/r1 --reviews Tools/envloop/ground/reviews/r1.json
```

`render.py` ray-casts a synthetic 160 m shore (`scene.py`: a club beach and lawn, a natural clay cut bank with a wood,
a low cove with the drought's dry bed and a mown yard) whose vertex colours, Near and normals follow
`LakeTerrainActor::BuildChunk` exactly. "Before" is today's `M_Terrain` ported line for line (`terrain_before.py`).
Views: each bank from 3, 15 and 60 m off, the 15 m views in midday sun, low sun and overcast. Exposure follows an
incident meter as the game's does on Medium and High.

## Round 1 (Nov 16 2026)

All six checks pass (`Tools/envloop/ground/scores/r1.json`), colour provisionally:

| Check | Result |
|---|---|
| Size | Every scan's real width published except Ground013 (rough grass, set at 2 m from its tufts). 171 to 1575 px per metre at every tier, so 1 cm per pixel or finer even on Medium; the smallest named feature is 2 px or more on High. |
| Colour | Prepared maps' means equal the pack's colours. PROVISIONAL: judged, not measured; how far each was moved from its scan (Lab dE): mud 3, rough 11, sand 11, lawn 13, clay 13, litter 25, gravel 29, cracked 32. Needs Bean's grey-card ground photos. |
| Repeat | Highest off-centre autocorrelation in a 40 m frame (high-passed at 1.5 m): lawn 0.18, yard 0.27, field 0.29, woods 0.31, limit 0.35. The same scan simply tiled: 0.99. |
| Variety | All eight surfaces drawn; each bank kind shows six. |
| Blind | 3 fresh reviewers, sides shuffled: the new ground won all 15 views for all three (45 of 45). Called "photo": 8 of 9 answers at 3 m, none at 15 or 60 m. |
| Budget | Texture arrays 5.3 MB Medium, 21 MB High, 85 MB Ultra; 12 texel reads inside 150 m, none past it. Frame time is the Mac's, after Nov 21. |

What the reviewers still saw at 15 and 60 m, for round 2: band edges along the shore that run too straight; the
limestone shingle patches reading as flat grey decals with clean outlines; a cut bank that is one even texture with no
strata, slumps or roots (shape is Track C's, the strata can be a clay-face layer here); the cracked-mud and gravel tiles
repeating at 3 m; the wood's floor on the 60 m hill showing as a dark patch with hard edges (partly the test scene's
square wood). Before and after page: https://claude.ai/artifact/T9SCPjdAAP92REkYXzzRRz (renders are not in git: images go through LFS, which cloud sessions cannot push; the commands below rebuild them).

## Round 2 (Nov 18 2026): the reviewers' three complaints, in the maths

Changed in `ground_material.py` and the HLSL together (the renders are in `Artifacts/envloop/ground/r2`, rebuilt by the
commands above with `--out .../r2`): every band's top (the swash, the bank's grass line) now also wanders with a 31 m
noise, so no zone edge runs straight along the shore; the shingle patches thin out over a wide feather instead of ending
on a contour (they read as flat grey decals), and the height blend brings the sand up between the last stones; a clay face
steeper than about 30 degrees carries strata, bands 18 cm apart bent by the small noise, at 14%. The crack and gravel
tiles' repeat at 3 m and the wood's square floor are the test scene's (a 1.5 m scan seen from 3 m, a square wood) and
wait for the in-game stills.

## In the game (integration PR, Nov 18 2026)

Bean moved the slice to Dec 11 on Nov 17, so the game half lands before the Nov 27 freeze, in one pull request:

- **Material.** `scripts/import_ground.py` (its own script, not `make_materials.py`) imports the eight prepared surfaces
  as three 8-slice `Texture2DArray`s (`/Game/Materials/Ground/TA_Ground_{Albedo,Normal,RHA}`: colour sRGB BC1, normal
  BC5, RHA linear; 2048 px, the tiers below through the World texture group's LOD bias) and builds `M_Ground` from the
  committed `Tools/envloop/ground/M_Ground.hlsl` (`ground_hlsl.py`'s output; `test_ground.py` fails when it is stale).
  `tangent_space_normal` is off: the terrain's procedural mesh has no tangents, so the node outputs a world normal.
  `MPC_World.Season` is added by the same script.
- **Terrain (C++).** `ALakeTerrainActor::ChunkMaterial` gives the chunks `M_Ground` on Medium and up on the lake's
  dress; Low, the garrigue (Marseille's palette has its own decode) and `-SailingClassicGround` keep `M_Terrain`.
  `BuildChunk` writes the Mown mask to UV0.x (`SailingGround::FMownSource`, `GroundDress.h`: mown within 26 m of a
  full-detail house with a ragged 10 m edge, and the club's lawn 35 m round its buildings) and paints the bank's
  sand-or-clay tone from `SailingGround::BankTone` (20-40 m stretches; scene.py's `smooth`) instead of each 5 m cell's
  own random. `ASailingEnvironment` sets `Season` from the day of the year (`SeasonAmount`: dormant December to
  mid-March, ramps through November and April). Test: `SailingSim.Visual.GroundDress`.
- **Cost (the Mac's first world gate, Nov 18).** With 12 fetches on every pixel inside 150 m the High gate lost 9 fps on
  coast-day and 4 on slip (both held at 45 on main). The material now reads by distance: inside 35 m both scales of
  the two surfaces (12 fetches); to 75 m one scale each with their height, normal and roughness maps (6); to 150 m
  colour only, the two mixed by weight (2); nothing past it; the bands cross-fade over 10 m. The normal and RHA arrays
  are trilinear (anisotropic filtering on ground seen at a grazing angle ran its full tap count on every fetch; the colour
  keeps it), and ray-traced hits (Lumen's hit lighting) and Lumen's surface-cache card captures (`LUMEN_CARD_CAPTURE`)
  take the card colours: the second world gate (Nov 18) showed the cost mostly in Lumen (coast-day +2.4 ms, slip +1.6 ms,
  the main pass +1.1 ms on coast-day), and the cards are what Lumen renders the material into. That gate did not move
  (third run: Lumen still +2.3 ms, the main pass +1.3 ms), so the second, rotated scale inside 35 m is Ultra only
  (`MPC_World.GroundDetail`, set by ASailingEnvironment; `-SailingGroundDetail=0|1` compares): High reads 6 fetches a
  pixel near, and the bench now names the Lumen passes (`gpu.lumen_passes` in bench.json, "Bench GPU Lumen passes" in
  the log) so the next gate says which Lumen pass moved. The numpy twin has the same bands (`shade(..., detail=)`).
- **Lumen's cost was the bed under the water (round 4 gate, Nov 18).** With the same package and only the material
  swapped (`-SailingClassicGround`), the Lumen passes that moved were screen-space: ScreenProbeGather +1.2 ms and
  LumenReflections +1.2 ms on coast-day; card captures, scene lighting and card rasterising were equal. `M_Ground` had
  treated everything below the waterline as wet (the mud's wet roughness, 0.25 to 0.45, and the scans' relief), so every
  bed pixel seen through the water sat under Lumen's reflection roughness (0.4) and was traced. `M_Terrain` draws the
  bed at 0.92 and flat; `M_Ground` now does the same (`under`): the wet gloss and the relief stop at the waterline.
- **From the PC's Ultra stills (Nov 18, `Inputs/bench/ground-797/pc-0c1d9669/`).** Shingle patches on the club beach had
  box-straight sides (value noise keeps its lattice in its features): the 3.1 m and 11 m patch noises now sit on
  lattices turned 34 and -52 degrees off the map's axes. A pale column ran up the clay bank: the mowing stripes
  multiplied the whole ground by the lawn's weight, so a half-weight lawn over soil striped the soil; they now need the
  lawn to own the pixel. Wet limestone shingle sparkled in the sun: its wet roughness goes from 0.4 to 0.55. The
  ruler-straight waterline in the 5 m stills is the 1 m mesh meeting the water plane (Track C's edge types and the
  shore mesh, not the material).
- **Far colour.** The card colours are measured albedos, darker and less yellow than today's vertex colours (today's
  lawn is a bright yellow-green, linear 0.36, 0.36, 0.16). Past 150 m `M_Ground` draws the card colours, so the far
  band changes too; `M_FarLand` (the far ring past the grid) should take the same table in Track I, or there is a step
  in colour at the ring.
- **Still owed (Mac and PC, through the sim thread).** Run `import_ground.py` and commit the assets (LFS); shader
  compile on Metal and D3D; frame time at the shore stations (plan share: Medium 1.5 ms, High 3.0 ms for the whole
  shore; this material reads 12 texels inside 150 m and none past it); the in-game stills at Track 0's stations; and the
  colour check against Bean's grey-card ground photos (lawn, rough grass, clay, gravel).
- **Lawn rectangles and the club-lawn step (PC Ultra stills of main 91c8c80d, Nov 19, `Inputs/bench/main-91c8c80d/lawn-step/`,
  diagnostics in `Inputs/bench/pr813/`).** Lighter, yellower rectangles about 8 by 12 m, square to the map, lay on the
  lawns, and a straight step crossed the club lawn in the beach view; both survived `viewmode unlit` and Lumen's diffuse
  GI off and vanished with `-SailingClassicGround`, so they were in M_Ground's base colour. They were the shader's own
  macro patterns: the straw patches (`dry`) are a smoothstep of value noise on a map-aligned 9 m lattice, and a value
  noise bump is the shape of its lattice cell, so each patch was a rounded rectangle with sides along north and east;
  the mowing stripes change direction at every 40 m block seam, and a seam square to the map ran as a straight edge
  across the lawn. Now the straw noise runs on two turned lattices (p1 at 34 deg over 9 m and p3 at -52 deg over 6.3 m),
  the stripe blocks sit on the turned p1 frame and the stripes fade out over the 3 m inside each seam (the headland pass).
  The PC's stills at 1795eead (`Inputs/bench/pr813/pc-1795eead/`) showed the step and the rectangles gone, but one lone
  high cell still read as a faint diamond (the turned square): the straw lattices are now bent by the 11 m and 31 m
  noises by about 3 m, so no patch keeps a straight side.
  Not the cause, but kept: the terrain mesh's canopy colour now interpolates the 20 m tree raster (`CanopyAtSmooth`,
  `SailingSim.Lake.CanopySmooth`); the raster is flat 0.27 across those yards, so M_Ground's litter term was never on
  there.
