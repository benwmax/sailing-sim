# J-Class 15: Bluebonnet's own wear and detail textures in the game

Slice 11 (`docs/jclass-11`) made Bluebonnet's own close-up maps (`Inputs/jclass-detail`, `Tools/shipkit/jclass/textures.py`)
and her wear at the texture loop's five levels, but only in her Blender build. Step 2 of J-Class 14 exported her model to the
game on the shared boat library, so her bronze was the library's Brass, her manila the polyester braid's Rope and her
varnished teak the J/22 tiller's WoodMahogany. This puts her own surfaces into the game.

## What changed

| Her build's material | Game slot before | Game slot now | Kind | Detail map |
| --- | --- | --- | --- | --- |
| Bronze (winches, blocks, cleats, portlights, binnacle) | Brass | `CastBronze` | 16 (new) | her own `T_JClass_CastBronze_N/_M`, 100 mm, fades 0.8 to 3 m |
| Rope (manila sheets, guys, tails, coils) | Rope | `Manila` | 17 (new) | her own `T_JClass_Manila_N/_M`, 60 x 30 mm, fades 0.6 to 2.5 m |
| Wood (varnished teak brightwork) | WoodMahogany | `VarnishedTeak` | 6 (varnish) | the shared `T_Detail_WoodVarnish`, 1.5 to 6 m |
| Sails (drawn by the game) | white Dacron | cream cotton, `Cloth` 1 | | her own `T_JClass_Cotton_N/_M`, 40 mm, fades 1 to 4 m |

The new slots' colours are her build's: bronze sRGB 150 104 60 (`finish_bluebonnet.json`), manila 196 168 118 held to the
Rope001 scan as `weathering.py` does (`standing_bluebonnet.json`), teak 124 70 32 (`deck_bluebonnet.json`), cotton 232 222 196
(`sails_bluebonnet.json`) at the 0.77 the game draws white Dacron at. The gilt stays Brass. The slots are unpacked.

## How

- `scripts/make_materials.py`: `M_BoatSurface` (`BOAT_CODE`) has kinds 16 (sand-cast bronze) and 17 (three-strand manila),
  ported from `weathering.py`'s `bronze` and `manila`: the bronze's open faces brown to a patina unless polished, its recesses
  (the map's pits, close up) keep theirs and darken, verdigris gathers in the pits and as a thin bloom; the manila greys,
  darkens, grows hairs and mildews, at the rope's own age (kept yachts renew it). Their maps are two texture parameters,
  `OwnDetailN` and `OwnDetailM` (pins `TOwnN`/`TOwnM`), stand-ins on the parent; `MI_Boat_CastBronze` and `MI_Boat_Manila` set
  their own (`BOAT_OWN_MAPS`). So the shared material references none of her maps and no other boat loads them (Medium's
  boat texture budget, `docs/boat-tex-medium`, was 22.4 of 24 MB).
- `M_SailCloth` (`SAIL_CODE`) takes `Cloth` (1 cotton) and the weave as texture parameters `ClothN`/`ClothM`: no resin crinkle,
  the map's weave and yarn tone in place of the procedural 0.6 mm weave, dirt in the gaps. `ASailboatPawn` sets them, her cream
  and a matt 0.72 roughness on her main and jib only, and resets the others (the showroom swaps boats on the same materials).
  An AI Bluebonnet no longer gets the race profile's laminate sails.
- `scripts/import_boat_detail.py` imports `Inputs/jclass-detail` into `/Game/Boats/Detail` (the Vehicle texture groups).
- `Tools/shipkit/jclass/game_bluebonnet.json` maps her materials to the new slots.
- `Inputs/g3/boat-catalogue.json`: her wear block's notes say what the channels drive on her. With Age unset (as in play) the
  oxidation channel is the years in her surfaces and the fittings channel (x2) the verdigris; the numbers are unchanged, so
  `BoatLiveryData.inl` is byte-identical.
- Test `SailingSim.Visual.JClassMaterials`: the kinds, each slot's own maps, the stand-ins everywhere else, the sail switch.

Medium draws no detail maps (`MPC_Boat.Detail` 0, the sails' `Detail` 0), as her slice 11 budget has it; her colours and
weathering math are on every tier.

## To build (Mac or PC)

1. `import_boat_detail.py` (`DETAIL_NEW_ONLY=1` imports only the new maps).
2. `MATERIALS_ONLY=build_boat_library,build_sail_cloth scripts/make-content.sh` (or `run-python.ps1 make_materials.py -Only
   build_boat_library,build_sail_cloth`).
3. Re-export and reimport her model (`make-boat-models.sh`, `import_boats.py bluebonnet`): her FBX slots are renamed.
4. `scripts/test.sh SailingSim.Visual.JClassMaterials`, `SailingSim.Visual.BoatLibrary`, `SailingSim.Visual.BoatTextureBudget`,
   then the boats gate.

## Not checked yet

Nothing here has been compiled or rendered: the shader code waits for the Mac's materials rebuild, and the look for stills
of her bronze, rope, brightwork and sails on High at 0.5, 1, 2 and 4 m. Her live running rigging (the game's rope lines) is
still the polyester braid colourways; manila there is a rope-look change for `M_RigRope`, not this pass.
