# Boat slots: one material slot per pack (boat fidelity phase 0's 8-slot budget)

Each material slot on a mesh costs a draw and a Nanite shading bin. Phase 0 set the budget at 8 a mesh, and the boats
had up to 16. Nearly all of those slots shared one parent, `M_BoatSurface`, and differed only in the instance's values.
So slots of the one parent are folded into **packs**: one slot draws up to 8 library entries, and each face carries its
entry in a second UV set.

## How it works

| Piece | What it does |
| --- | --- |
| `Tools/blender/boat_packs.json` | The packs: `PackCanoe` (topsides, boot and cove stripes, antifouling), `PackDeck`, `PackFit` (metal, plastic, wood, rope), `PackCanvas` (covers, tarp, fenders). Entries are appended, never reordered. |
| `Tools/blender/boat_packs.py` | `pack_slots`: moves each face to its pack's slot and writes its entry index as UV1.x. Called by `build_j22.py`, `build_fleet.py`, `build_berthed.py` and `build_maxi.py`. |
| `M_BoatPacked` (`make_materials.py`) | `M_BoatSurface` with a selector in front of `BOAT_CODE`: it reads UV1.x and takes that entry's values from `P<k>C` (colour), `P<k>A` (roughness, metallic, clear coat, non-skid) and `P<k>B` (porosity, surface kind, hull, grain). Everything else is unchanged: the same inputs, the same `MPC_Boat` wetness, rain, spray and detail; per-instance wear and hull colour on the marina's boats; the same usage flags. |
| `MI_Boat_Pack*` | Built by `build_boat_library` from `BOAT_LIBRARY`, so every entry equals its `MI_Boat_<slot>`. `SailingSim.Visual.BoatPacks` checks this and checks `BoatPacks.h` against the json. |
| `BoatPacks.h` | The C++ mirror. Liveries recolour pack entries (`P<k>C`) where they used to recolour slots. |
| Hero J/22 | Its flat hardware slots go into `J22H_PackMetal` and `J22H_PackPlastic` (`Inputs/j22-hero/J22H_packs.json`, `MI_J22H_Pack*` from `import_j22_hero.py`). The baked groups, the glass and the mast's aluminium keep their own slots. `pack_j22_hero.py` packed the committed fbx in place, with no rebake. Geometry, UV0 and normals are unchanged; the only normal differences are on zero-area faces, which the import drops. `bake_j22_hero.py` now packs before export. |

Masts keep their bending slot (`Aluminium` on `M_BoatMast`, the maxi's `CarbonMast`). `PackCanoe` holds exactly the
slots `J22Mesh` and `FleetMesh` measure, so the hull checks are unchanged.

The entry is uniform over each triangle, so `BOAT_CODE`'s branches on the surface kind stay coherent, and the detail
maps still use `Texture2DSample`.

## Slots before and after

| Mesh | Before | After |
| --- | ---: | ---: |
| Hero J/22: hull, rudder, boom, mast | 16, 8, 5, 7 | 5, 3, 2, 3 |
| Light J/22: hull, rudder, boom, mast | 15, 3, 3, 2 | 3, 2, 1, 2 |
| J/22 berthed dresses 0-5 | 5, 9, 7, 8, 7, 8 | 3, 3, 3, 2, 3, 3 |
| Sunfish, ILCA 7 hulls | 11, 9 | 3, 3 |
| Catalina 22, Catalina 30 hulls | 14, 15 | 3, 4 |
| Hobie 16, Corsair 880, Lagoon 42 hulls | 8, 14, 15 | 3, 3, 4 |
| Maxi hull | 10 | 3 |
| Catalina 22 / 30 berthed dresses | 5-10 | 3 |

Every boat mesh now meets the 8, and `SailingSim.Visual.BoatBudget` enforces it, plus each mesh's own count as a
ratchet. The glass (3) and the interior (1) were already under.

Side fix: `import_boats.py`'s `add_lods` now also sets the maxi's Nanite fallback target to percent. On Auto, the engine
ignored the 6% and fell back by relative error.

## Look: unchanged on Low, Medium and High

Stills at 1600x900, uncooked, before on the left. Differences are confined to the water, the clouds and the sheets,
which move from run to run. The boats match at full resolution: non-skid, gelcoat streaks, lettering, stripes, hardware,
covers and liveries.

| Still | View |
| --- | --- |
| `j22-light-{low,medium,high}-before-after.jpg` | The light J/22 (AI boats), close |
| `hero-cockpit-{low,medium,high}-before-after.jpg` | The hero's cockpit hardware |
| `hero-mastbase-high-before-after.jpg` | The hero's mast step: blocks, cams, winch |
| `marina-high-before-after.jpg` | The home marina row: berthed J/22s, Catalinas, covers |
| `<boat>-medium-before-after.jpg` | Each fleet boat and the maxi |

## Frame time

These are uncooked A/B runs on Bean's RTX 4090 on High, 3 runs of 15 s each, with main's `Content/Boats` swapped in for
"before". Uncooked numbers aren't representative in absolute terms, but each pair shares its conditions.

| View | fps before | fps after | Render thread (ms) | GPU (ms) |
| --- | ---: | ---: | --- | --- |
| Marina (about 40 berthed boats) | 77.2 | 85.2 | 5.45 to 4.92 | 4.58 to 4.61 |
| Sailing with traffic | 72.9 | 72.0 | 5.80 to 5.87 | 4.45 to 4.42 |

The marina gains about 8 fps from fewer draws on the render thread. The GPU time is unchanged: the shading work is
the same, just in fewer bins. Out sailing, with a few boats in view, the difference is within noise.
