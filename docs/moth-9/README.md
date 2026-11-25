# Hydrofoil moth, detail pass: the parts a camera a metre away sees

![Before and after, in clay, from about a metre: the bow and wand fitting, the main strut's head, the rudder's head,
the mast foot, the main foil from aft, the twist grip](sheet.jpg)

Bean asked on Nov 25 to "hone in on detailed elements and make sure to model them well". After Milestone B
(`docs/moth-8`) the boat read right from a few metres away. Closer in, most fittings were stand-ins: a pod for every
block, a pod for the bellcrank, a pod for the rudder's head, and a bare tube for the wand's fitting.

## How it was checked

The reference photos (`refs.json`, 1,280 px) are too small to show fittings. So this pass was checked by close-range
review instead of a photo match. I rendered the same close-ups (`close_views.json`) (0.5 to 1.5 m away) before and after each change.
Fresh reviewers looked at twelve of them and listed what real moths carry there that looked wrong or missing. There
were two rounds of two reviewers. Round 2's reviewers were told which part each close-up shows, because round 1's
misread some of them (the shock cord as a pushrod, a spreader as one sideways strut).

| Round | Scores (out of 10, shape only) | What both reviewers named |
| --- | --- | --- |
| 1 (first details) | 4, 5 | the wand hanging straight down; no flap line on the main foil and cut-off tips; plain boxes at the rudder's head; the mast-foot fairing; no luff sleeve |
| 2 (after the fixes below) | 5, 5 | the bow and stern shapes (see below); the mast-foot fairing, still; a plain wand fitting; no flap line seen |

After round 2 the fairing came off, the wand fitting became one compact head, and the hinge gap was widened. The close-ups
on the sheet are from after those changes, which no reviewer has seen yet.

## What was added

Everything is in `Tools/shipkit/moth/detail_moth.py` and its json. A part joins the object it belongs to, so it moves with
that part in the game (the wand's lever turns with the wand, the rudder's stock and bulb with the rudder). New objects:
`MOTH_WandFitting`, `MOTH_Blocks`, `MOTH_RigFittings`, `MOTH_Lacing` and `MOTH_LuffSleeve`. `build_moth.py` gained bevelled
boxes, rings and lofts as parts.

| Where | Now |
| --- | --- |
| Wand | a compact head round the pivot on a short carbon bowsprit, the axle's ends, the ride-height knob on top, a lever above the pivot driving the pushrod aft along the deck, the shock cord from a horn on the head to the wand, the two-piece wand's ferrule, a paddle 8 by 4 cm with rounded corners |
| Main strut's head | the case's flange on the deck, the bellcrank's housing on top of the strut (the pushrod now ends in it), and the gearing adjuster: a slotted arm with its knob |
| Foils | elliptical tips raked back over the last 12% of the span; the flap behind a real hinge gap (5 mm at the root) instead of a copy drawn over the foil; a smaller junction pod; a bulb where the elevator meets the rudder |
| Rudder and gantry | an end block taking the four tubes, upper and lower gudgeons on a pin, the rudder's own stock, a saddle under each tube's foot |
| Tiller | a clamp on the rudder's stock, a moulded rubber universal joint, a 25 cm twist grip with 14 ribs and a rubber end |
| Blocks | every block has cheeks, sheaves, axle caps and a shackle: the mainsheet's doubles on the boom and the aft deck, the ratchet on its base, the vang's doubles, the cunningham's |
| Rig | a step plate, the gooseneck's clamp, toggle and pin, spreader brackets and tip caps, the hounds' band, a masthead cap, swaged ends on every wire, a tang and shackle at each wire's foot (a saddle on the wing bar for the shrouds), the boom's end cap and clew car |
| Sail | a luff sleeve round the mast from tack to head. The other sail details (batten pockets, corner patches, stitching) belong to the game's sail material, drawn on the live cloth |
| Wings | brackets on the deck edge where the bars plug in, and the mesh laced round the frame every 4 cm |

## Changes beyond fittings

- **The wand.** Reviewers in every round asked for a longer wand that trails aft. The fitting now stands 0.16 m ahead of
  the stem, and the wand is 0.93 m long, trailing about 19° at flying height. I tried 24° and 33° (fittings 0.20 and
  0.33 m ahead), but both moved the pivot off the camera-matched photo. At 0.16 m the paddle's tip lands 6 px from the
  photo's, where it was 18 px before. The cost is 0.6 px more error at the pivot: the solve's rms went from 4.9 to 5.3 px.
  The wand clears the stem by 4 cm.
- **The mast-foot fairing is gone.** Milestone B added it after reviewers asked for a raised foredeck. At close range,
  three of four reviewers read it as a hump that real moths don't have, even after it was made smaller. It was not a point
  of the camera solve.
- **The foils' root chords grew** by 5 mm (main) and 3 mm (elevator). This keeps the card's areas with the rounder tips:
  0.119 and 0.065 m².

The size check passes (`moth_check.py --slice 5`) at 144,282 triangles, against a budget of 450,000.

## Left open

- **The hull's ends.** All four reviewers called the bow a flat, blunt face and the stern a rounded tub. A real moth has
  a fine V entry and a narrow, flat transom about 15-20 cm wide. The hull matches the camera-matched outline in profile,
  but its sections are full aft so she floats level at rest (Milestone B), and its transom is 0.30 m wide. Narrowing the
  ends would cost buoyancy aft. That is a hull change, not a detail, and needs its own round against the photos.
- **The elevator's size.** Round 2 put it at 0.6-0.7 m. Milestone B widened it to 0.8 m after earlier reviewers asked.
  It stays.
- **The mainsheet's purchase.** It is drawn as two parts. Real boats differ.

## How to rebuild

As `docs/moth-2`, then the close-ups (the 16 views in `Tools/shipkit/moth/close_views.json`):

```
CLOSE="$(cat Tools/shipkit/moth/close_views.json)" blender -b -P Tools/shipkit/moth/render_close.py -- <work>/moth.blend Tools/shapeloop/sections_moth.json <out> --res 600
```
