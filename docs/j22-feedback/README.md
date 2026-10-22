# Bean's J/22 feedback (pc/j22-feedback)

Bean's review of the rebuilt J/22, item by item, grouped by assembly. The side-by-sides with Bean's photos are kept
local in `docs/j22-detail/compare/F<n>-*.jpg`, never committed. The renders here are the game at Ultra.

## 1. Traveler and mainsheet

Bean: "the traveler for the boom does not sit on the cockpit floor in j22's. It spans from seat to seat across the
width of the cockpit, and has a cutout in the seats for it to run in. And as part of that, the main sheet and its
block and tackle do not look right either." From Bean's cockpit photo, `traveler-deck-mount` and
`mainsail-sheet-traveler`, and the Harken J/22 layout (end-boom sheeting).

- **Traveler** (hero: `Inputs/j22-hero/j22_mainsheet.py`): a dark 32 mm track across the whole cockpit from seat to
  seat, at x -2.06 under the boom's end, open over the well.
  - It sits in a channel across each seat top, its top 4 mm proud.
  - A screwed end cap on each seat, with its control sheave.
  - Blue control lines from the car round the end sheaves to cam cleats on the seats.
  - The car in the middle.
- **Mainsheet's lower block:** on the car, a spring over a swivel, then a fiddle (57 mm over 40 mm) with perforated
  stainless side plates and a becket, and the cam cleat on its arm.
- **Upper block:** over the traveler, at the boom's end bail.
- **The floor traveler is gone,** with its blocks and cam.
- **Light J/22** (`Tools/blender/build_j22.py`): the gelcoat bridge is gone. A dark track runs seat to seat at the same x
  (TRAV_X -1.75 to -2.06), with end caps on the seats. Its boom block follows.

The game:
- The live 4:1 tackle ends at the fiddle's sheave (the new `MainsheetBlock` socket) and moves with the car.
- The drawn car is placed by the angle the physics gives the boom (`TravelerRangeDeg` about the gooseneck: about
  ±0.42 m at full travel on the hero), not by the track's length.

Sockets moved (old to new, cm):

| Socket | Old | New |
| --- | --- | --- |
| Hero `Traveler_C` | (-195, 0, 18) | (-206, 0, 42.4) |
| Hero `Traveler_S` | (-195, 33, 18) | (-206, 80.29, 42.4) |
| Hero `Traveler_P` | (-195, -33, 18) | (-206, -80.29, 42.4) |
| Hero `MainsheetCam` | (-197.6, -9, 22) | (-214.16, 0, 52.63) |
| Hero `Boom_Mainsheet` | (-194.02, 0, 135) | (-206, 0, 137.91) |
| Hero `MainsheetBlock` | none | (-206, 0, 51.5) |
| Light `Traveler_C/S/P`, `Boom_Mainsheet` | x -175 | x -206 |

The crew's legs against the new bar are the Mac's (`j22-feedback-crew`).

Renders: `1-trav-photo.jpg`, `1-trav-block.jpg`, `1-trav-seat.jpg`.

## 2. Mast base, to the stock layout

Bean: remove the deck hardware a stock J/22 doesn't carry, such as the several little blocks near the mast. The baseline
is the Harken J/22 layout. Anything not in it goes, unless it's structural.

- **Turning blocks:** two beside the step, one a side, for the control lines (it had been six fanned round it). The
  halyards turn aft on the step casting's own two sheaves.
- **Mast:** the three halyard exit boxes up the mast are gone.
- **Halyards:** they run aft along the cabin top through the organisers to two cam cleats a side, just forward of the
  cabin-top winches at the aft corners (it had been three cams a side beside the hatch). The winches are the
  halyards' (the layout's B6).
- **Light J/22:** the same set. Two turning blocks at the step, two cams a side forward of the winch (it had been three
  clutches), and the winch moved from the side deck to the cabin top's aft corner.

No socket moved. Renders: `23-mastbase.jpg`, `23-cabintop.jpg`.

## 3. Jib sheets

Bean: improve the positioning and routing of the sheets to match the Harken layout and the cockpit photo.

- **Lead:** the sheet runs from the clew aft along the side deck to a block on a 0.6 m track beside the cockpit's
  forward end (car at x -0.55).
- **Cam:** from the lead it goes over the coaming to one cam with its fairlead on the cockpit's side wall, just aft
  of the track (x -1.05). It ends there, not at a winch.
- **Gone:** the cabin-top jib track and the second coaming cam with its fairlead blocks.
- **Light J/22:** the same. Its track moves from by the shrouds to the side deck beside the cockpit, and the sheet ends
  at a cam on the coaming wall.

The game draws the sheet live from the clew through `JibLead` to `JibWinch`, so moving those sockets reroutes it. The
trimmer's tail runs from `JibTailer`.

| Socket | Old | New |
| --- | --- | --- |
| Hero `JibLead_S/P` | (16.13, ±62.13, 100.36) | (-54.06, ±111.3, 66.99) |
| Hero `JibWinch_S/P` (the cam's fairlead) | (-42.84, ±74.29, 106.72) | (-102.45, ±91.82, 56.64) |
| Hero `JibTailer_S/P` (the cam's jaws) | (-42.84, ±74.29, 110.72) | (-105.6, ±91.74, 56.64) |
| Hero `JibTailRest_S/P` | (-17.84, ±54.29, 97.94) | (-145, ±58, 40.8) |
| Hero `JibCam1_S/P` (now the same cam as `JibCam0`) | (-155.6, ±89.06, 56.26) | (-105.6, ±91.74, 56.64) |
| Light `JibLead_S/P` | (12, ±96.76, 68.78) | (-55, ±110.93, 67.86) |
| Light `JibWinch_S/P` | (-100, ±100.92, 70.52) | (-101.8, ±81.73, 58.77) |
| Light `JibTailer_S/P` | (-100, ±100.92, 74.52) | (-105.6, ±81.73, 58.77) |

Renders: `23-jiblead.jpg`, `23-cockpitfwd.jpg`.

## 4. Spinnaker gear

Bean kept the spinnaker hardware, fitted to the Harken J/22 layout's positions.

- **Aft quarters:** the sheets' turning blocks near the stern corners, perforated blocks on padeyes (the layout's
  2636).
- **Beside the cockpit:** a ratchet block on a spring stand with its cam cleat on a pad just forward of it (2625).
  The sheet comes forward along the side deck from the quarter block. These had been at the cockpit's forward end,
  where the jib's track now runs.
- **By the shrouds:** small blocks on padeyes on the side decks, for the twinger lines (237).
- **Foredeck:** the pole downhaul's padeye and block, forward of the cabin (2146; the fore hatch fills the cabin top
  ahead of the mast).
- **Light J/22:** the same blocks and cams, from its own block and cam helpers.

No socket moved for the spinnaker gear. `JibCam0_S/P` and `JibCam1_S/P` are dropped in the same push, since nothing in
the game read them. Renders: `4-spin-aft.jpg`, `4-pole-dh.jpg`.
