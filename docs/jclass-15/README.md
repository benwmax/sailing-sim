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
| Teak (the laid deck, hatch lids, cockpit sole) | Teak (packed in PackDeck) | `LaidTeak` | 18 (new) | the shared `T_Detail_TeakWeathered`, each plank from its own place |

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
- Her laid deck (`LaidTeak`, kind 18). The PC's Ultra stills of the imported model showed her deck as woven cloth: it was the
  shared Teak slot, whose teak map tiles 0.25 x 0.125 m over the whole 40 m deck with no planks or seams. Her Blender deck
  draws its planking from three UV maps (`deck.py`: Planking (U, Ys), Margin (D, YM), Aft (DA, s)) in `planking_terms`;
  `BOAT_CODE` now runs the same terms, line for line: 57 mm planks fore and aft with 6 mm black caulked seams, butts every
  7.3 m staggered over four planks (starboard's an eighth of a length on), the 330 mm king plank with its scarfs, the 300 mm
  covering boards with the planks nibbed into them (each plank runs out until half its width is left, then is cut square),
  the after margin and its mitre. Each piece gets its own slight tint and its own place in the teak map, so the grain no
  longer repeats from plank to plank. Underneath it weathers as bare teak (kind 7: silvering, checks, dirt), at her
  catalogue's teak colour (sRGB 176 140 102). Far off, where a seam is under a pixel, its share of the deck darkens the teak
  instead (seams fade from one to three seams' widths a pixel, the tint from one to three planks'), and the caulking takes
  grime and standing water first. This is on every tier, not only the detail maps' High and Ultra.
  - `export_game.py` keeps the maps on her teak's faces: UV2 Planking, UV3 Margin, and the Aft map's DA in UV1.y (UV1.x is
    the pack entry). Aft's s, how fast the covering board's edge crosses the planks, is YM's slope along U, which the
    material takes from the screen derivatives (YM is a function of x alone). A teak part without the maps gets its body-frame
    x, y as Planking (plain planks, no boards).
  - The extra texture coordinates sit behind a static switch, `LaidDeck`, on only on `MI_Boat_LaidTeak`, so every other boat
    keeps its permutation without the interpolators. Its numbers are vector parameters `LaidA`..`LaidE` and `LaidCaulk`, read
    from `deck_bluebonnet.json` (planking, Caulking) and `game_bluebonnet.json`'s `laid_deck.mitre` (`BOAT_LAID`), which the
    export checks against her build's `build.json`. The frigate's deck (`Tools/shipkit/frigate`, `DeckPlanks`) has the same
    kind of maps and could take the same kind with its own numbers.
  - `BoatModelVisuals.cpp` gives `LaidTeak` the livery's teak colour as it does `Teak`.
- `scripts/import_boat_detail.py` imports `Inputs/jclass-detail` into `/Game/Boats/Detail` (the Vehicle texture groups).
- `Tools/shipkit/jclass/game_bluebonnet.json` maps her materials to the new slots.
- `Inputs/g3/boat-catalogue.json`: her wear block's notes say what the channels drive on her. With Age unset (as in play) the
  oxidation channel is the years in her surfaces and the fittings channel (x2) the verdigris; the numbers are unchanged, so
  `BoatLiveryData.inl` is byte-identical.
- Test `SailingSim.Visual.JClassMaterials`: the kinds, each slot's own maps, the stand-ins everywhere else, the sail switch,
  the laid deck's numbers against `deck_bluebonnet.json`, and her hull's `LaidTeak` slot with four UV sets.

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

Ray-traced hits and Lumen's card captures have no screen derivatives, so there the deck takes its average tone, without seams
(a raster draw of the Nanite fallback would also store the UVs as half floats, a centimetre out at her ends). Nothing here has been compiled or rendered: the shader code waits for the Mac's materials rebuild, and the look for stills
of her bronze, rope, brightwork and sails on High at 0.5, 1, 2 and 4 m, and of her deck at 1:1 from the helm (the PC's
`Inputs/bench/jclass-14/bluebonnet-helm*.jpg` on the inputs branch are the before). Her live running rigging (the game's rope lines) is
still the polyester braid colourways; manila there is a rope-look change for `M_RigRope`, not this pass.
