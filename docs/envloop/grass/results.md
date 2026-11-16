# Track B round 1 results (16 Nov 2026)

`python3 Tools/envloop/grass/check_grass.py --renders Artifacts/grass/set` on branch claude/project-thread-q0885m:

| Check | Result |
| --- | --- |
| 1 Size | PASS: all 33 meshes inside their cards' real heights and blade widths (5 percent slack) |
| 2 Colour | PASS: lawn and rough blades seen from above match Track A's ground means, summer and dormant (solved); grey-card photo check waits on Bean's photos |
| 3 Repeat | PASS: strongest repeat along the bank at 15 m is 0.03 to 0.04 (limit 0.35) in all six 15 m renders |
| 4 Variety | PASS: every card has its variants (4 lawn tiles, 3 rough, 3 bluestem, 3 switchgrass, 2 johnsongrass, 3 sedge, 2 horseweed, 3 lawn weeds) |
| 5 Blind | New beats old 3 to 0, see [blind.md](blind.md); not yet "could pass for a photo" |
| 6 Budget | PASS per mesh (below); frame time can only be measured in the game after the slice |

## Plants and triangles placed per view (noon, summer)

| View | Plants placed | Triangles placed (million) |
| --- | --- | --- |
| `shore_15m_noon_summer` | 1093 | 1.73 |
| `shore_3m_noon_summer` | 980 | 0.91 |
| `shore_60m_noon_summer` | 0 | 0.0 |
| `shore_60m_noon_summer_Ultra` | 3221 | 0.7 |

At 60 m on High nothing is placed: the bank is past High's 60 m grass limit, so the whole shore there is Track A's
texture. Ultra (100 m) places about 3,200 Light copies (0.7 M triangles). The boat often sails 60 to 150 m off, so the
next round should test cheap far cards for the bunch grasses on High between 60 and 150 m (the cards already allow
4 triangles a plant).

## Triangles per mesh

| Mesh | Triangles | Card budget |
| --- | --- | --- |
| `SM_Grass_Lawn_0` | 821 | 900 |
| `SM_Grass_Lawn_1` | 800 | 900 |
| `SM_Grass_Lawn_2` | 805 | 900 |
| `SM_Grass_Lawn_3` | 813 | 900 |
| `SM_Grass_Lawn_Light` | 126 | 300 |
| `SM_Grass_Rough_0` | 1338 | 1400 |
| `SM_Grass_Rough_1` | 1335 | 1400 |
| `SM_Grass_Rough_2` | 1317 | 1400 |
| `SM_Grass_Rough_Light` | 234 | 450 |
| `SM_Grass_Bluestem_0` | 2202 | 2600 |
| `SM_Grass_Bluestem_1` | 2193 | 2600 |
| `SM_Grass_Bluestem_2` | 2198 | 2600 |
| `SM_Grass_Bluestem_Light` | 228 | 700 |
| `SM_Grass_Switch_0` | 2506 | 3500 |
| `SM_Grass_Switch_1` | 2584 | 3500 |
| `SM_Grass_Switch_2` | 2572 | 3500 |
| `SM_Grass_Switch_Light` | 144 | 900 |
| `SM_Grass_Johnson_0` | 1356 | 3000 |
| `SM_Grass_Johnson_1` | 1336 | 3000 |
| `SM_Grass_Johnson_Light` | 84 | 800 |
| `SM_Grass_Sedge_0` | 2036 | 2500 |
| `SM_Grass_Sedge_1` | 2028 | 2500 |
| `SM_Grass_Sedge_2` | 2044 | 2500 |
| `SM_Grass_Sedge_Light` | 300 | 700 |
| `SM_Weed_Horseweed_0` | 410 | 1500 |
| `SM_Weed_Horseweed_1` | 405 | 1500 |
| `SM_Weed_Horseweed_Light` | 43 | 500 |
| `SM_Weed_Dandelion` | 249 | 1200 |
| `SM_Weed_Clover` | 663 | 1200 |
| `SM_Weed_Plantain` | 85 | 1200 |
| `SM_Weed_Dandelion_Light` | 70 | 400 |
| `SM_Weed_Clover_Light` | 126 | 400 |
| `SM_Weed_Plantain_Light` | 35 | 400 |

## Renders

Not committed (images go through Git LFS, which the cloud can't push): rerun `render_grass.py`, or see the review page
linked from the pull request (https://claude.ai/artifact/CMv5NDMsnwH4zGz4R2pz7S). The set is 20 shore views (3, 15, 60 m; noon, low sun, overcast; summer and dormant; two
Ultra) and every hero mesh alone in both seasons.

## Next round (after Bean's look)

- Vary the stand's height by patch and thin it toward the bank top; fuller bases on the Light copies (blind notes).
- Far cards for bunch grasses past 60 m on High.
- Grey-card colour check once Bean's lawn, rough grass and bank photos exist (Commons refused this session's requests,
  HTTP 429, so no outside photos were gathered).
- After 21 Nov: import, `M_Grass` in its own script, camera-following placement, wind, station stills, Mac gate.
