# J/22 close-up rebuild (boat fidelity phase 3)

The player's hero J/22 (`Inputs/j22-hero`, `/Game/Boats/J22Hero`), corrected against Bean's reference photos: 62 photos
of J/22s and their deck hardware, plus the class drawing.

The photos stay in git-ignored `Data/Reference/raw/boats/J22/`, with a catalogue and gap list in `notes.md` there. Most
of the first batch are a dealer's watermarked product photos, and several show people. They are used for shapes,
layout and colours only: nothing was traced or sampled into a texture, and no real brand or sail number is reproduced.

Everything is made by scripts (`build_j22_hero.py`, `j22_materials.py`, `j22_interior.py`, `bake_j22_hero.py`) and
reimported with `scripts/import_j22_hero.py`. No asset is hand-edited.

## What changed, and which photo it comes from

| Change | Photos |
| --- | --- |
| **Bow:** two small horn cleats abreast, 0.42 m aft of the stem, replace the single centreline cleat | `bow-hardware*` |
| **Transom:** the cockpit drains' outlets, white flanges round a dark bore, low at the transom's corners | `aft-drainholes-on-transom`, `transom-worn`, `aft-transom` |
| **Rudder fittings:** each pintle on a long polished strap down both faces of the blade with four through-bolts, into a gudgeon of two lugs bolted to the transom | `tiller-transom-attachemnt*`, `transom-worn` |
| **Tiller:** a laminated tiller that sweeps up out of the rudder head and runs nearly level to the grip, with a cam cleat on top. It is one lofted tube; the earlier joined capped cylinders showed dark rings at every joint. | `tiller`, `tiller-2`, `cockpit-portlooking` |
| **Mast step:** six turning blocks fanning round the step (was four) | `mast-bottom-closeup`, `mast-sheetsandhardware*` |
| **Cabin top:** the halyard cam cleats 4.5 cm apart (were 5.5 cm). The outer cam overlapped the cabin handrail. | `sheets-hardware-3` |
| **Side decks:** spinnaker sheet leads abreast of the cockpit's forward end, a block on a spring stand with a cam cleat behind it | `deck-hardware*`, `port-jib-sheet` |
| **Cabin sole:** varnished wood instead of moulded liner (all three cabins photographed) | `interior-1..3`, `companionway-lookinto` |

## Sockets (approved by the coordinator before the bake)

`J22H_sockets.json`: 52 sockets. Everything else is identical to 0.05 cm.

- **`TillerEnd`** moved from (-215.74, 0, 84.59) to (-215.97, 0, 83.90): 7 mm lower and 2 mm aft. The new tiller keeps
  its end points, and the bake now reads its bounds in world axes. `ASailboatPawn::TillerEndCm` uses it for the
  extension's start and the helm's aft-hand grip. The helm close-up (`tiller-before-after.jpg`) shows the hand still
  on the extension.
- **`BowCleat`** is now the starboard of the two cleats, moved from (270, 0, 84.9) to (303, 13, 84.7). The new
  **`BowCleatPort`** is the port one. `Tools/boatkit/layouts/j22.json` places a horn cleat at each (both 0.13 m, as on
  the hero). Nothing in `Source` reads `BowCleat`. No saved photo-match solve picked it; only the docstring example in
  `Tools/boatkit/photomatch/solve_camera.py` names it, and that still works.
- **`build_berthed.py`** reads the AI J/22's own sockets (`J22_sockets.json` from `Tools/blender/build_j22.py`), not
  the hero's. The berthed dresses' tiller cover is unaffected, so they aren't rebuilt.

The physics hull, keel, mast and rig are untouched. `SailingSim.Visual.J22Mesh` measures the AI model (`SM_J22_Hull`),
which this doesn't change.

## Bake notes

- **Blender version.** The PC's Blender 4.2 has no Pillow in its Python, so `j22_materials.draw_sail_textures` now
  falls back to the committed sail maps (which the game's live cloth reads). Nothing was installed. Run unchanged, the
  script rebuilt all 51 of main's sockets identically.
- **Resolution: 2048, as committed.** A 4096 deck bake would roughly quadruple its memory and take the hero past
  High's 48 MB budget. Close-up sharpness stays with the true-scale detail layer.
- **Maps kept from main.** Blender 4.2 bakes the procedural non-skid with a wavy moiré where main's maps (from a newer
  Blender) are finely speckled. The deck-mould, teak and rudder groups' UV layouts came out the same as main's (their
  detail masks match to within 2 grey levels of 255), so those groups keep main's maps.
- **New bakes.** The hull's UV layout changed (`uv_m` 6.90 to 7.16 m), so the hull's maps are new. The interior's are
  new too, for the wood sole (`uv_m` 8.30 to 8.45 m).
- **Left alone.** `J22H_coils.json` isn't re-committed: today's script also lists the anchor rode, which lives in the
  interior mesh and would then be drawn twice. `web/j22_hero.glb` is left as it was (web viewer only).

## Stills (Ultra, 3 kn, uncooked, before at left)

| Still | View |
| --- | --- |
| `broadside-before-after.jpg` | The whole boat from abeam |
| `cockpit-before-after.jpg` | The cockpit from the companionway |
| `cabintop-before-after.jpg` | The cabin top and the halyard cams |
| `transom-before-after.jpg` | Astern: the drains, the rudder fittings |
| `bow-before-after.jpg` | The foredeck and the two bow cleats |
| `tiller-before-after.jpg` | The helm and the new tiller |
| `companionway-before-after.jpg` | Into the cabin: the wood sole |
| `maststep-before-after.jpg` | The mast step's turning blocks |

## Still open

The gaps from `notes.md` that the photos haven't closed:

- The keel and rudder side-on out of the water.
- A level broadside with a scale object, to check the sheer and freeboard.
- A winch close-up with scale.

## Gaps closed from the photos in hand (#235 follow-up)

Three things the second batch of photos shows that the hero didn't have:

| Change | Photos |
| --- | --- |
| **Sliding hatch:** varnished marine plywood (`PlywoodVarnish`), not moulded gelcoat | `companionway-1` |
| **Companionway trims:** teak strips beside the closed hatch, and posts framing the aft face either side of the drop board (clear of the halyard cams) | `companionway-1`, `companionway-lookinto`, `companionway-rail-port` |
| **Transom:** a teak strip along the top, just under the deck edge, short of the corners | `transom-worn` |

The parts are flat-material objects outside the baked groups. The rebake left every group's UVs as they were (`uv_m`
identical), so main's maps stay, except as below; the hull fbx and `PlywoodVarnish`'s values in `materials.json` are new. The
two wood flats share a new pack, `J22H_PackWood`, because `J22H_PackPlastic` already has 7 of `M_BoatPacked`'s 8
entries. The hero hull is at 6 slots, and `BoatBudget` holds it there. Sockets are unchanged.

**The dark aft face.** To starboard of the companionway, the cabin's aft wall drew as a dark, mirror-glossy panel in
every cockpit and helm view. The mesh, normals and materials are symmetric. The fault was in the committed
DeckMould maps: a stale bake had that face at base colour 0.16 and roughness 0.08, where the port side is 0.89 and 0.20.
A fresh bake is right there, but Blender 4.2 washes out the non-skid's speckle. `patch_deckmould.py` keeps the
committed maps and takes only the cabin trunk's walls (inside and out, not the non-skid top) from the fresh bake,
face by face in UV space. Every other pixel is unchanged.

Stills (Ultra, before at left): `gaps-cockpit-before-after.jpg` (the aft face), `gaps-companion-before-after.jpg`,
`gaps-hatchside-before-after.jpg`, `gaps-transom-before-after.jpg`.
