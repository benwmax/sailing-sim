# Hydrofoil moth, Milestone B: the whole boat with her hardware against the photos

![The boat after Milestone B in clay: flying from the bow quarter, afloat at rest, on her side ashore, and from the
camera solved on the flying photo](sheet.jpg)

Milestone B checks slices 1 to 5 together (hull, wings, foils, rig and hardware) the same two ways as Milestone A
(`docs/moth-6`): a camera solved on the flying photo, and blind reviewers. The photos show people, so they and the
compare images stay out of the repo; only the picked pixel numbers are here (`Tools/shipkit/moth/matches/`).

## Blind review

Each round had three fresh reviewers and five rows, each pairing a photo with a clay render from about the same view:

- the camera-matched flying view;
- a bow quarter while flying;
- afloat at rest;
- broadside on a trolley;
- on her side ashore.

Left and right were shuffled for each reviewer. Reviewers described both pictures before listing the differences.

| Round | Scores (out of 10) | What most reviewers saw |
| --- | --- | --- |
| 1 (slices 1 to 5) | 6, 6, 6 | the hull 25-50% too deep, most of it aft; the wand raked forward where the photos' trail aft; flat wings at deck level; the sail's head too narrow; a short gantry |
| 2 | 6, 6, 6 | the hull still too deep; the wand; flat wings; the gantry; two asked for 3-5° more mast rake |
| 3 | 6, 6, 6 | the hull too deep aft; the wand short and leaving the hull's bottom; no raised foredeck; wings without braces; a light gantry |
| 4 (this state) | 6, 6, 6 | short rods standing up from the wings (fixed after the round, below); a short tiller extension; no vang strut seen; split on the wand's angle and the sail's head |

The score held at 6 through all four rounds. The faults the reviewers named changed from round to round, and each round
named fewer of the earlier ones. The hull's depth was the one fault named in every round. In round 4 one reviewer
called it "about right overall" and blamed the shape aft instead. The other two still called it too deep, one of them
"especially forward".

## Settling the hull's depth by the photo, not by eye

The reviewers disagreed with one another on the hull's depth: "too deep forward", "even depth, no rocker" and "about
right". Each judged the ratio by eye on photos taken from different heights and of different boats. So the depth was
settled on the one photo with a solved camera. I drew the hull's outline alone from that camera and laid it over the
photo. The old outline stood proud of the photo's hull, aft most of all. The new one sits on its top and bottom.

## What changed

| Part | Milestone A | Milestone B | Why |
| --- | --- | --- | --- |
| Hull depth | 0.45 m (sheer 0.45 bow, 0.40 transom) | **0.40 m** (sheer 0.405 bow, 0.27 transom) | every reviewer in rounds 1 and 2; the overlay agrees |
| Sections | V powers 0.32 / 0.40 / 0.62 (aft / mid / bow) | **0.16 / 0.22 / 0.45**, the transom 0.30 m wide | fuller sections float the shallower stern |
| Sailor at rest | x -0.55 (the old wings' front bar) | **x -0.30** (the middle of today's wings) | the transom sat 6 cm out of the water; now the bow has 0.23 m of freeboard and the transom 0.12 m, close to level as the afloat photo shows |
| Wand | 1.02 m from a fitting 0.03 m ahead of the stem, 13° forward | **0.88 m from a fitting 0.10 m ahead, trailing slightly aft** | the photos' wands trail behind their pivot; with the old fitting, a trailing wand went through the plumb stem |
| Gantry | 0.45 m, two tubes | **0.50 m** (the rule's limit) **with a lower pair of tubes** from the transom's foot | rounds 1 to 3 asked for 30-100% longer; the rule stops it at 0.5 m, so the lower tubes give the braced truss instead |
| Main foil | span 1.0 m, chords 0.155 / 0.085 | **1.1 m, 0.145 / 0.07** (area unchanged, 0.12 m²) | four reviewers over rounds 1 to 3: wider spans, thinner chords |
| Elevator | span 0.72 m | **0.80 m**, slimmer (0.064 m²) | as the main foil |
| Sail head | 0.65 m | **0.85 m** (the roach re-solved to keep 8.25 m²) | rounds 1 and 2; rounds 3 and 4 each had one reviewer wanting it narrower, so 0.85 stays |
| Wings | bars and rail only | **a diagonal brace under each bar** from halfway down the hull's side, out along the swept bar | the photos' wings stand on braces; round 4 saw the front brace's end standing in the air ahead of the swept bar, now fixed |
| Foredeck | flat | **a low fairing round the mast's foot** (x 0.5 to 1.15) | the photos show a raised deck forward of the wings |
| Vang | a rope cascade | **plus a rigid strut** from the mast's foot to the boom | the flying photo shows one |
| Tiller extension | on the centreline, 18° up | **swung 35° out over the port wing, 16° up** | drawn on the centreline it read as a bar over the deck |

The size check (`moth_check.py --slice 5`) passes: 117,878 triangles. The fittings reach exactly 0.5 m past the hull,
the rule's limit (the gantry).

## The camera match

| | Milestone A | Milestone B |
| --- | --- | --- |
| Error over the seven solve points (rms, on a 1,280 px photo) | 7.7 px | **4.9 px** |
| Worst points | | the wand's pivot 7.9 px, the mast's foot 6.4, the transom's foot 5.3 |
| Checks (not solved on) | | the main strut at the flying waterline 9.8 px, the rudder 12.5, the wand's tip 18.1 |

About 130 px is one metre in this view, so the wand's tip is about 14 cm from the photo's. The real wand swings with ride
height; the model's is drawn at one angle.

I re-ran the solve after every change, and it rejected two of them:

- **Lowering the foredeck.** The mast's foot moved from 6 to 10 px off, so I kept the sheer and added the fairing instead.
- **Raising the wings' dihedral from 14° to 20°.** The wing's front corner moved from 2 to 6 px off. The near wing in the
  photos looks higher because the boat heels to windward.

## Left as they are

- **Mast rake.** Two reviewers wanted 3 to 5° more rake. The solve puts the masthead within a few pixels at 12°.
- **Freeboard afloat.** The afloat photo shows an older, higher-sided boat; her waterline is solved for 115 kg.
- **The wings look like flat plates.** Part of this is the clay render: the mesh deck and tube frame look the same
  colour. Slice 6's textures (black mesh, carbon tubes) should separate them.
- **The wand's angle.** Round 4 split on it. One reviewer wanted 30-40° of trail. On the matched photo the model's tip is
  14 cm from the photo's. In the game the wand will swing with ride height (slice 8), so the model draws it at one pose.

## For the physics (slice 8)

- The main foil's area is unchanged, but its aspect ratio rose from about 8.3 to 10.3.
- The elevator moved 5 cm further aft with the gantry.
- The sailor's resting place moved forward to x -0.30. This changes only her trim at rest.

## How to rebuild

As `docs/moth-2`, then:

```
python3 -I Tools/shipkit/moth/moth_check.py <work>/m/stats.json <work>/Moth_sockets.json --slice 5
python3 Tools/boatkit/photomatch/solve_camera.py Tools/shipkit/moth/matches/sunday_flying.json <work>/Moth_sockets.json
blender -b -P Tools/boatkit/photomatch/match_blend.py -- <work>/moth.blend Tools/shipkit/moth/matches/sunday_flying.camera.json <photo> <out>
```

The `xyz` values in `sunday_flying.json` are the model's points (wand pivot, mast foot and head, strut and rudder at the
hull, transom foot, wing corner). Refresh them from the sockets after a change before solving again. The photo is the
Commons thumbnail, 1,280 px wide (`refs.json`): download it locally and never commit it.
