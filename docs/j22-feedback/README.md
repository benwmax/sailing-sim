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
