# J/22 hero model, proof of concept

A more detailed J/22 built entirely by script in Blender: hull, deck mould, cockpit, cabin trunk, keel and rudder,
deck hardware, rig, sails and procedural PBR textures, modelled on the lesson boat TX 7295 EC at Rush Creek
(Bean's photos, Oct 2026). It sits beside the game's current boat (Tools/blender/build_j22.py) and does not replace
it until it wins a side-by-side and the Mac gate. Plan and open questions: J/22 hero model plan (Claude doc,
https://claude.ai/code/artifact/466e1966-f37d-45fa-bd26-2239398eb811).

## Files

| File | What it is |
| --- | --- |
| `build_j22_hero.py` | Builds the model and saves `j22_hero.blend`; prints canoe volume and centre of buoyancy against the physics |
| `j22_style.py` | Style generator: a preset (`new`, `race`, `club`, `neglected`) plus a seed gives one boat's look as JSON (wear, care, gelcoat tint, streaks, scum line, chips, fender marks, repairs, grey bottom, registration, line colours, sail cloth, sail number, sailmaker, stains, patches, windex, telltales, tape colour) |
| `j22_details.py` | Fine fittings built from parts: gooseneck, vang, masthead crane and windex, hounds tang, spreader roots and taped tips, turnbuckles with toggles and cotter rings, chainplates, blocks with sheaves and beckets, cam cleats with teeth, padeyes, shackles, clevis pins, screws, coils, stopper knots, whippings, sail rings, headboard, telltales |
| `j22_fabric.py` | Rope and cloth behaviour for the stills: a position-based rope solver (lines hang under gravity, slack lines drape over the deck, cabin and mast, loaded lines run nearly straight) and sail wrinkles (clew and tack tension fans, scallops between jib hanks, leech flutter between battens, crinkle that grows with sail age) |
| `j22_geom.py` | Small mesh helpers shared by the two scripts above |
| `j22_materials.py` | Procedural materials driven by the style (gelcoat with rain streaks, chalking, chips, repairs and scum line, crosshatch non-skid with foot-wear paths, silvered or oiled teak, varnish with peel, worn anodising, tea-stained stainless, faded braided rope) and the sail textures drawn with PIL (crosscut Dacron or grey laminate, panels, numbers, sailmaker mark, crinkles, mildew, stains, repair patches) |
| `styles/` | The style JSON for each rendered boat |
| `render_j22_hero.py` | Cycles renders in views matched by eye to the lesson photos |
| `bake_j22_hero.py` | Bakes the procedural materials to base colour, roughness and normal maps and exports FBX per part plus a web GLB |
| `renders/` | The proof-of-concept renders (close-ups, the three styled boats, views matched to the lesson photos) |
| `web/j22_hero.glb` | A lighter copy (decimated, 2K JPEG) for web viewers |
| `textures/` | Baked maps at 2048 (rebuild at 4096 with `--res 4096`) and the sail textures |
| `fbx/` | `SM_J22H_Hull`, `_Mast`, `_Boom`, `_Rudder` for the game (about their pivots, Unreal frame, cm), plus `SM_J22H_RiggingStill` and `SM_J22H_SailsStill` for cinematics only |
| `J22H_sockets.json` | The game's rig sockets measured off the hero fittings (same names and layout as `J22_sockets.json`), plus crew attach points: `TillerExtTip`, `TillerExtUJ`, `MainsheetCam`, `JibCam0/1_S/P`, `HandholdCabin_S/P`, `HandholdCoaming_S/P`, `Seat_S/P`, `FootBrace_S/P`, `SideDeck_S/P`, `CockpitSole`, `Boom_LowOverCockpit` (no lifelines on this boat) |
| `materials.json` | Which maps go with which part, and flat values for the hardware materials |

The PNG, FBX and GLB files are plain git blobs (see `.gitattributes`), because cloud sessions cannot upload to LFS.

## Rebuild

Blender 4.2 or later (tested with the bpy 5.2 module):

```
blender -b --factory-startup -P build_j22_hero.py -- out --sails                      # TX 7295 EC (club, seed 7295)
blender -b --factory-startup -P build_j22_hero.py -- out_b --sails --seed 22 --preset race   # any other boat
blender -b --factory-startup -P build_j22_hero.py -- out_c --sails --style styles/mine.json  # a saved style
blender -b -P render_j22_hero.py -- out/j22_hero.blend out/renders
blender -b -P bake_j22_hero.py -- out/j22_hero.blend out --res 4096
J22H_SOCKETS_ONLY=1 blender -b -P bake_j22_hero.py -- out/j22_hero.blend out   # sockets JSON only, in seconds
```

The `j22_*.py` modules must sit next to `build_j22_hero.py`. Set `J22H_TEX` to choose where the sail textures go
(one folder per boat). `python3 j22_style.py --seed 9 --preset neglected` prints a style without Blender, so a fleet
can be planned first and the same JSON reused for the other classes (only the defaults are J/22 specific). Set `J22H_SAMPLES` and `J22H_RES` to change render quality.

## Ropes and sails in the game

Ropes and sails must move like rope and cloth, so the game parts carry no frozen rope or sail geometry:

- Running and standing rigging stay the game's live lines (`FRigLine` in `BoatModelVisuals.cpp`): each line hangs
  between sockets with sag from its load, so a slack sheet droops and a loaded one goes straight. The hero model
  supplies the sockets (`J22H_sockets.json`, same names as the current J/22) and the rope look (`RopeJibPort`,
  `RopeMain` and the other rope entries in `materials.json`, braid and fleck colours from the style).
- Sails stay the cloth simulation (`FSailCloth`): the hero sail maps (`T_J22H_Mainsail_D/H`, `T_J22H_Jib_D/H`) are
  drawn in the sail's normalized planform, chord across and luff up, which is the cloth's UV1, so they drop into
  `M_SailCloth` and ride on the moving cloth (numbers, sailmaker mark, stains, patches, crinkle height for normals).
- Importing: copy `fbx/SM_J22H_*.fbx` and `J22H_sockets.json` to `Artifacts/models/` and run `import_boat("J22H", ...)`
  from `scripts/import_boats.py`; the hero material slots need their own instances (see `materials.json`).

## Checks

- Canoe body below the design waterline: 1.08 m^3 against the physics' 1.052 m^3 (+3%), centre of buoyancy
  x -0.22 m, z -0.07 m against the physics' -0.195 m, -0.080 m. The physics stays the source of truth.
- About 380,000 triangles for the whole boat with sails and every fitting (the fittings are small and suit Nanite or a lower LOD); hull, deck and hardware are meant for Nanite.
- Normal maps are baked OpenGL style (green up); tick "Flip Green Channel" on import in Unreal.

## What is guessed

Marked `GUESS` in the script: cabin trunk length, height and window outline; cockpit seat and floor heights; keel
and rudder plan forms; spreader height and hounds; boom length; outboard size; fitting sizes (from typical small-boat
hardware, not measured). The bottom is grey (Bean). A later walk-around with a tape and phone LiDAR would replace
the guesses; there is no shoot planned for now.

## Known gaps

Sails and ropes in the stills are one pose; in the game they stay live (see above). No spinnaker gear, no interior
below decks, no LODs yet (Nanite covers the rigid parts). The cabin trunk is narrower and boxier than TX 7295 EC's
low, wide trunk in the dock photo; the rudder head is a plain box. The hero material slots have no Unreal
instances yet.
