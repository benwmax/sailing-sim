# Visual V2: the J/22 model

The J/22 is now a modelled boat. A Blender script builds it from code like the rest of the game's content: the hull,
deck and fittings, the mast, boom and rudder, standing and running rigging drawn from the physics each frame, and a
Substrate material library with wet and dry surfaces. The other seven boats keep their procedural visuals until V7;
the code picks a model per class (`ASailboatPawn::ModelMeshesFor`).

![The model](j22_stbd_bow.png)

## How it is built

`scripts/make-boat-models.sh` runs three steps:

1. **Physics export.** `Tools/BoatExport` (standalone C++, the same `FBoatConfig` and `FBoatModel` the simulation uses) writes the J/22's geometry to JSON. That covers the hull shape parameters, the computed canoe-body depth (0.217 m), the design displacement (1.052 m³) and centre of buoyancy, the foils, the rig and the sail strips.
2. **The model.** `Tools/blender/build_j22.py` runs in Blender 5.2 headless. Below the waterline the canoe body *is* the physics hull surface (`FHullShape::BottomZ` at the canoe depth). Above it, the stem and sheer sharpen toward the real boat's fine entry. Rows are split at the paint lines, so the antifouling, boot stripe and cove stripe are crisp. It writes four FBX meshes and the rig's attachment points.
3. **Import.** `scripts/import_boats.py` imports into `/Game/Boats/J22`:
   - Nanite on the hull, boom and rudder. The mast stays non-Nanite because it bends with a world position offset.
   - The `MI_Boat_*` material for each slot.
   - The rig points as mesh sockets.

What the model carries:
- **Hull:**
  - sheer, rubrail, cove stripe, navy boot stripe, ablative bottom paint;
  - "J/22" on both bows;
  - swept NACA 0012 fin keel to the class draft;
  - pintles on the transom.
- **Deck:**
  - crowned deck with non-skid inside smooth margins;
  - cabin trunk with long smoked windows and a raked front;
  - companionway slide and washboards; forehatch;
  - cockpit with coamings, seats, sole, bridge deck and the traveler on its bridge.
- **Hardware:**
  - jib winches and cam cleats;
  - jib tracks with cars and blocks;
  - bow and stern cleats, chainplates, stem fitting, backstay plate;
  - bow pulpit, split stern pulpits, four stanchions a side and the lifeline.
- **Spars:** mast with swept spreaders, hounds fitting and masthead crane; boom with end fitting, vang and mainsheet bails.
- **Rudder:** transom-hung, NACA section, with its head, a varnished ash tiller and the extension.

## Held to the physics

`SailingSim.Visual.J22Mesh` reads the imported mesh's source geometry and checks it against `FBoatConfig`:

| | Model | Physics |
| --- | --- | --- |
| Length overall | 6.860 m | 6.86 m |
| Beam | 2.440 m | 2.44 m |
| Draft | 1.160 m | 1.16 m |
| Canoe body volume | 1.046 m³ | 1.052 m³ |
| Centre of buoyancy | (-0.196, 0.000, -0.080) | (-0.195, 0.000, -0.080) |

The test cuts the hull triangles at the design waterline and sums tetrahedra. The tolerance is 2 cm (2% for the
volume). The test also checks:
- starboard sockets sit on +Y;
- the hull is Nanite;
- every slot has a boat material.

The J/22 polar gate is unchanged (0 of 39 points out). The only physics change is a new accessor for the design centre
of buoyancy.

## Rigging from the physics (`BoatModelVisuals.cpp`)

Every line is drawn each frame between the meshes' sockets. Each one sags by its slack (a parabola, with
e = 8/3 (s/L)²) under gravity in the boat's frame:

- **Standing rigging:**
  - forestay;
  - uppers through the spreader tips;
  - lowers;
  - backstay.

  The leeward shrouds go slack as the breeze builds and she heels, and the backstay eases when let off.
- **Jib sheets:** the working sheet runs clew → lead → winch and goes straight under load. The lazy sheet runs over the cabin top in front of the mast to the windward lead, drooping.
- **Mainsheet:** a 4:1 tackle from the boom bail to the traveler car. The car slides along the bar with the traveler control.
- **Vang:** a 3:1 tackle, slack when eased off.

The mast bends with the backstay and the breeze (`M_BoatMast`: a half-sine forward, a little aft at the head), and the rig points on it follow the same curve.

## Materials (`scripts/make_materials.py`)

`M_BoatSurface` is a Substrate slab. Its second, glossier specular lobe is the gelcoat's clear coat, and it grows on wet
surfaces. 16 `MI_Boat_*` instances set the colours, roughness, metal, coat, non-skid and porosity:
- white gelcoat and navy stripes;
- antifouling and keel;
- non-skid, smoked acrylic;
- stainless, clear anodized aluminium, black plastic;
- varnished wood, graphics red, rubrail, rope.

Wetness comes through `MPC_Boat`, which the player's boat sets every frame:
- **Hull:** wet up to the highest recent water around it, plus a splash band that grows with the sea and the speed. It dries back at about 3 cm a minute, has a ragged edge, and rises on the low side when she heels.
- **Deck:** rain soaks it in about a minute and spray comes aboard upwind in a sea. It darkens with porosity, glosses up and carries droplets, then dries in about five minutes.

## Frame rate (packaged build, `bench.csv`)

| View | Medium V1 | Medium V2 | High V1 | High V2 |
| --- | --- | --- | --- | --- |
| beam8 | 85.2 | 83.3 | 48.2 | 46.2 |
| beat15 | 88.2 | 85.8 | 49.3 | 47.6 |
| storm | 119.0 | 118.8 | 74.1 | 70.9 |
| marina | 91.8 | 89.6 | 58.0 | 56.1 |
| coast-day | 79.7 | 82.1 | 50.6 | 47.6 |
| coast-night | 100.3 | 99.7 | 60.2 | 61.2 |
| gulf-sea | 104.2 | 101.0 | 62.7 | 59.7 |
| helm-eye | 94.4 | 88.2 | 54.3 | 47.7 |

Low is unchanged (118–120).

The model costs 0.3–0.6 ms on Medium and up to 2 ms on High close up (the helm eye).
- **Base slice on Medium:** 3.4–5.2 ms against the 4.0 budget. It is over by 0.4–1.2 ms in the lake and helm views; the total is under 12 ms everywhere.
- **Why Nanite did not cut the shadow cost:** the sails, the rig lines and the bending mast still redraw their shadows every frame. Nanite on the hull alone did not lower the virtual-shadow-map cost.

## Comparison (`compare/index.html`)

The 12 reference scenes were recaptured (`captures/`), next to V1 and the reference clip.

| Scenes | Boat score | Why |
| --- | --- | --- |
| Helm eye (no crew in frame) | 4 → 2 | The hull, deck and rig read as a J/22. |
| The other J/22 scenes | 4 → 3 | The hull, deck and rig would score 2, but the yellow cylinder crew still give the boat away. |

The crew are V3, with the sails, so the gate's "boat 2 or less" is met where no crew figure is in frame and waits on
V3 elsewhere.
