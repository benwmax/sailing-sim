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
| `j22_interior.py` | The cabin below decks (boats 11): hollowed trunk and deck, cream liner with dirt, water tracks under the chainplates and mildew, sole with a lift-out hatch over the sump, keel bolts with backing plates and nuts, a little bilge water, settee benches, V-berth with a lid, chainplate knees, compression post, companionway step and the aft bulkhead's locker cut-outs, smoked acrylic portlights; the style's `interior` keys add cushions, sail bag, spare vests, paddle, bucket, extinguisher and a Danforth with its rode |
| `j22_rope.py` | Rope that looks like rope (boats 11): every line becomes a mesh whose U is true arc length over one lay of the braid, with the braid textures from `Tools/rope` (tracer pattern, weave cavity, sun fade, dirt, fuzz) and 1x19 strand normals on the wire |
| `j22_materials.py` | Procedural materials driven by the style (gelcoat with rain streaks, chalking, chips, repairs and scum line, crosshatch non-skid with foot-wear paths, silvered or oiled teak, varnish with peel, worn anodising, tea-stained stainless, faded braided rope) and the sail textures drawn with PIL (crosscut Dacron or grey laminate, panels, numbers, sailmaker mark, crinkles, mildew, stains, repair patches) |
| `styles/` | The style JSON for each rendered boat |
| `render_j22_hero.py` | Cycles renders in views matched by eye to the lesson photos |
| `bake_j22_hero.py` | Bakes the procedural materials to base colour, roughness and normal maps and exports FBX per part plus a web GLB |
| `renders/` | The proof-of-concept renders (close-ups, the three styled boats, views matched to the lesson photos) |
| `web/j22_hero.glb` | A lighter copy (decimated, 2K JPEG) for web viewers |
| `textures/` | Baked maps at 2048 (rebuild at 4096 with `--res 4096`) and the sail textures |
| `fbx/` | `SM_J22H_Hull`, `_Mast`, `_Boom`, `_Rudder`, `_Interior` (Nanite) and `_Glass` (portlights, hatch acrylic, bilge water; translucent, so no Nanite) for the game (about their pivots, Unreal frame, cm), plus `SM_J22H_RiggingStill` and `SM_J22H_SailsStill` for cinematics only |
| `J22H_sockets.json` | The game's rig sockets measured off the hero fittings (same names and layout as `J22_sockets.json`), plus crew attach points: `TillerExtTip`, `TillerExtUJ`, `MainsheetCam`, `JibCam0/1_S/P`, `HandholdCabin_S/P`, `HandholdCoaming_S/P`, `Seat_S/P`, `FootBrace_S/P`, `SideDeck_S/P`, `CockpitSole`, `Boom_LowOverCockpit` (no lifelines on this boat) |
| `materials.json` | Which maps go with which part, flat values for the hardware materials, and each baked group's `uv_m` (metres per UV unit) for the close-up detail layer |

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

The `j22_*.py` modules must sit next to `build_j22_hero.py`; the rope textures are read from `../rope` (set
`J22H_ROPE` to move them; `python3 Tools/rope/make_rope_textures.py` rebuilds them). Set `J22H_TEX` to choose where the sail textures go
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
- The live lines carry the same braid as the stills (boats 11): `FRigLine` tubes get UV0 (U = arc length over 5
  diameters), a vertex colour whose red is the line's look (a column of `T_RopeColourways`) and tangents, and
  `M_RigRope` / `M_RigWire` from `scripts/import_boat_detail.py` draw them. `-SailingFlatRope` keeps the old flat look.
- Importing: `scripts/import_boat_detail.py` first (rope, wire and detail textures), then `scripts/import_j22_hero.py`.

## Checks

- Canoe body below the design waterline: 1.08 m^3 against the physics' 1.052 m^3 (+3%), centre of buoyancy
  x -0.22 m, z -0.07 m against the physics' -0.195 m, -0.080 m. The physics stays the source of truth.
- About 380,000 triangles for the whole boat with sails and every fitting (the fittings are small and suit Nanite or a lower LOD); hull, deck and hardware are meant for Nanite.
- Each textured group also bakes `T_J22H_<group>_X`, the detail mask (R non-skid, G teak, B smooth gelcoat), so
  `M_J22HeroSurface` can lay true-scale close-up texture (`Inputs/boat-detail`) on top within a few metres.
- Normal maps are baked OpenGL style (green up); tick "Flip Green Channel" on import in Unreal.

## What is guessed

Marked `GUESS` in the script: cabin trunk length, height and window outline; cockpit seat and floor heights; keel
and rudder plan forms; spreader height and hounds; boom length; outboard size; fitting sizes (from typical small-boat
hardware, not measured). The bottom is grey (Bean). A later walk-around with a tape and phone LiDAR would replace
the guesses; there is no shoot planned for now.

## Known gaps

Sails and ropes in the stills are one pose; in the game they stay live (see above). No spinnaker gear, no LODs yet (Nanite covers the rigid parts). The cabin trunk's front is rounder than the real one and its window
outline is estimated. The interior layout is from typical J/22 photos and the class plan, not measured on TX 7295 EC: a phone video of
its cabin would settle the berth heights, the sole and the locker openings.
