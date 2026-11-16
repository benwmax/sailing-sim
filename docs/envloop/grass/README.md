# Shore plan, Track B: grass and ground plants in 3D (cloud half)

Track B of the shore, grass and buildings plan (Bean approved all eleven answers on 16 Nov 2026). This is the part that
runs before the 21 Nov slice: plant cards, script-built meshes, colours, renders outside the game and the loop's
checks. **Nothing here is loaded by the game.** The import, the grass material, the camera-following placement code
and the Mac gate come after the slice, as one integration pull request through the sim thread (grass lands last, the
plan's frame-rate rule).

## What is here

| File | What it is |
| --- | --- |
| `Tools/envloop/grass/cards/*.json` | One card per plant: real sizes, where it grows on the lake, which distance bands it must hold, variants, triangle budgets, references wanted |
| `Tools/envloop/grass/grass_look.json` | Blade colours per plant and season (linear albedo), translucency and roughness: the numbers the game's grass material will read |
| `Tools/envloop/grass/grass_geo.py` | Every plant's shape, in plain Python (no Blender): blades, stalks, seed heads, flowers |
| `Tools/envloop/grass/build_grass.py` | Builds the 33 meshes in Blender and writes FBX plus `grass_meshes.json` |
| `Tools/envloop/grass/render_grass.py` | The standard renders: a natural lake bank from a boat at 3, 15 and 60 m, noon, low sun and overcast, summer and dormant, High and Ultra distances |
| `Tools/envloop/grass/check_grass.py` | The loop's automatic checks (size, colour against Track A's ground, repeat, variety, budget); `--solve` fits the lawn colours to Track A |

Run them with Python that has Blender's `bpy` module (`pip install bpy==5.3.0` on Python 3.13; the checks need only
numpy):

```
python Tools/envloop/grass/build_grass.py --out Artifacts/grass/fbx
python Tools/envloop/grass/render_grass.py --out Artifacts/grass/set            # 20 shots, about 45 min on 4 cores
python Tools/envloop/grass/render_grass.py --out Artifacts/grass/studio --studio
python3 Tools/envloop/grass/check_grass.py --renders Artifacts/grass/set
```

## The plants

| Card | Meshes | Real size | Where on the lake | Bands |
| --- | --- | --- | --- | --- |
| Mown bermuda lawn | `SM_Grass_Lawn_0..3`, `_Light` (0.5 m tiles) | blades 25 to 65 mm, mown 40 to 60 mm | every mown lawn to the bank | hero to 8 m, Light to 20 m, then Track A's texture |
| Unmown edge | `SM_Grass_Rough_0..2`, `_Light` | 0.15 to 0.5 m, bermuda finger heads, bahia V heads | the strip the mower misses, bank tops | hero to 30 m, Light to 60 m (High), 100 m (Ultra) |
| Little bluestem | `SM_Grass_Bluestem_0..2`, `_Light` | 0.45 to 1.1 m bunch | prairie banks, dam slopes | as above |
| Switchgrass | `SM_Grass_Switch_0..2`, `_Light` | 1.0 to 1.8 m | damp bank tops, coves | as above |
| Johnsongrass | `SM_Grass_Johnson_0..1`, `_Light` | 1.0 to 2.0 m, broad leaves with a white midrib | ditches, rough above natural banks | as above |
| Sedge | `SM_Grass_Sedge_0..2`, `_Light` | 0.3 to 0.7 m tussock | the water's edge | as above |
| Horseweed | `SM_Weed_Horseweed_0..1`, `_Light` | 0.5 to 1.5 m single stalk | scattered in the rough | as above |
| Lawn weeds | `SM_Weed_Dandelion`, `_Clover`, `_Plantain`, each `_Light` | rosettes 0.1 to 0.25 m | scattered in lawns | to 15 m |

Every mesh is solid blades, not see-through cards (the plan's frame-rate rule for grass near the camera), one surface
each with a two-sided material. The vertex colour carries height up the plant (wind sway and root shade), a random
number per blade (colour and sway variation), the part (leaf, stalk, seed head) and the mown tips; UV V runs root to
tip. Normals lean halfway to straight up, the usual grass trick so a blade lit from behind doesn't read black.

## Seasons and Track A

Summer and winter-dormant come first (Bean's answer 4). Dormant bermuda goes straw tan, little bluestem copper red, switchgrass
gold, johnsongrass brown, sedge stays half green. The grass material will take the same `Season` scalar (0 summer,
1 dormant) as Track A's ground material.

The lawn and rough-grass blades are solved so that, seen from above, they average to Track A's ground colour for the
same surface (`check_grass.py --solve`): tips brighter and roots darker than the ground, the same mean. That is what
makes the blades fade into the texture at 20 m without a visible edge. Track A's values are provisional (no grey-card
photos yet); rerun `--solve` when they change.

## Checks (the plan's six)

1. **Size.** Every mesh's height and blade width inside its card's real range. Automatic.
2. **Colour.** Blades against Track A's ground mean, within 10 percent. Automatic. The grey-card check against real
   photos waits on Bean's photo trip.
3. **No repeat.** The bank's strongest repeat along the shore in each 15 m render. Automatic.
4. **Variety.** At least the card's number of variants per plant. Automatic.
5. **Blind review.** Fresh reviewers, results in [blind.md](blind.md).
6. **Budget.** Triangles per mesh against the card; triangles placed per view in each render's json. The frame-time
   share (High 3.0 ms, Ultra 4.5 ms for the whole shore) can only be measured in the game, after the slice.

Results of this round: [results.md](results.md).

## What comes after the slice

1. Import the meshes (`scripts/import_world.py`, Nanite with WPO off for the Light copies) and build `M_Grass` in its
   own script file, not `make_materials.py`.
2. Camera-following placement in our own code (the way reeds and undergrowth are placed now), reading Track A's Mown
   mask and the lidar cover map; High and Ultra only (Bean's answer 10: Medium keeps bank grass only).
3. Wind sway from the trees' far wind map (`BindTreeWind`).
4. Station stills at Track 0's stations and a world gate on the Mac, with an on and off switch (`-SailingNoGrass`).
5. Far cards for the bunch grasses past 60 m, baked from these meshes, if the Ultra 100 m band needs them.
