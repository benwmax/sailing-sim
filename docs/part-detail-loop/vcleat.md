# V-cleat with fairlead (Nov 8 2026)

Bean's hardware reference sheet (Nov 8) asked for each part on it to go through the part detail loop
([README](README.md)). This page is the V-cleat: the angled dark moulding with a V-shaped rope slot, bottom right on the
sheet. The kit had no V-cleat before this, so it is a new part, `VCleat`, rather than a rebuild.

The before/after sheet for Bean is `part-detail-loop/vcleat_before_after.jpg` in the project files. It stays out of the
repo because its reference crop is a retailer photo (for looking at only).

## What it is

A small one-piece composite cleat for 3-6 mm control lines (cunningham, outhaul, jib car adjusters, kicker tails on
dinghies and small keelboats). The line comes over the nose, is pulled down into the V, where raked ridges on both walls
grip it, and leads out aft through a fairlead eye, so it can't jump out of the jaw. From the tail:

- a shallow pocket inside a rim, with the aft screw countersunk in its floor;
- a raked bulkhead with an oval fairlead eye through it and a solid bridge over it;
- the V jaw, open on top and narrowing to the bottom, with swirled ridges (steep at the bottom, raking back near the
  top) and the forward screw down at the bottom of the V; it runs open right out through the nose end, so the loaded
  line comes straight in through the end of the body (Bean's review).

## Card, sizes and references

Card: `Tools/boatkit/partloop/parts/vcleat.json`. Builder: `Tools/boatkit/bk_part_vcleat.py` (its own file, so the
threads doing the other parts on Bean's sheet don't edit the same lines; `bk_parts.py` now imports every
`bk_part_*.py` at its end).

| Size | Target | Source |
|---|---|---|
| Screw hole centres | 48 mm (2%) | catalogue: small V-cleat with fairlead, 4 mm fasteners, 48 mm centres, 11 g (Premium Ropes and Eastmarine Asia listings; the open version is 36 mm, 9 g) |
| Overall length | 70 mm (8%) | read off the photo against the 48 mm centres: no listing gives a length |
| Height, width | reported only (21.4 mm, 18.1 mm) | no square-on or end-on photo |

There is no square-on photo, so the card has `"outline": null` (like the vang's fiddles). Wikimedia Commons has no V-cleat
photo in its cleat category ("Jamming cleat.jpg" is a different, wooden kind), and the cloud's shared address was being
rate-limited there in any case; manufacturer pages are outside the cloud's network allowlist.

| Reference | Used for | Licence |
|---|---|---|
| Bean's hardware sheet, "V Cleat" (project upload, Nov 8) | shape, pocket, eye, ridges, nose (three-quarter from above the tail) | retailer photo: for looking at only, not shipped |
| [Premium Ropes RF5101 listing](https://www.premiumropes.com/v-cleat-3-6mm-1-8-1-4-fairlead-rf5101) | 48 mm hole centres, 4 mm screws, 11 g | numbers only |

## Rounds

| Round | Fixings | Length | Features | Triangles | Blind review |
|---|---|---|---|---|---|
| r1 | 48 mm | 70 mm | 5/10 | 17,870, 3 slots (one empty) | first build: a stepped wedge with a rectangular slot and a hidden eye |
| r5 | 48 mm | 70 mm | | 17,872, 2 slots | **lost**: won 1 of 3 against r1 (straight ridges, eye unreadable, rectangular jaw) |
| r7 | 48 mm | 70 mm | 10/10 | 17,870, 2 slots | won 3 of 3 against r1 (confidence 5, 4, 4); nobody called it the wrong part |
| r9 | 48 mm | 70 mm | 10/10 | 17,872, 2 slots | r7 with Bean's one fix (Nov 8, marked-up screenshot): the V jaw runs open right out through the nose end instead of stopping at a nose wall (r8 tried a side window through the eye, which was the wrong place, and is gone); no new blind vote for a change Bean asked for by eye |

(r2 to r4 and r6 were working renders between scored rounds.) What r6/r7 changed after r5 lost: the ridges sweep back
as they rise instead of being straight slats, the jaw opening is an oval in plan, the eye is bigger and its bulkhead
raked so you can see it from behind, the sides have a little draft so the shoulders roll over, the outer edges are
rounder, and the maker's plate is smaller.

The loop also gained two small, generic hooks other parts can use:

- `render_views.py`: a builder can carry `render_rope` (how its line runs, from its sockets) for the in-use stills, and
  `photo_view` (the angle its reference photo was taken from) for one more still, `photo.png`. The V-cleat's photo was
  taken from above the tail, which none of the six fixed views shows.
- `score.py`: a `fixings` size, the distance between the `FixAft` and `FixFwd` sockets (screw hole centres).

Still different from the photo (the reviewers' shared notes on r7, for a later round):

- The bridge over the eye reads as a flat strip; on the real one it blends into the moulding with a thicker rounded top.
- The eye reads as a dark recess more than a clear oval hole from most angles.
- The tail pocket is a little long; the real one is more compact.
- The rim round the jaw is thin; the real one has a thicker moulded lip, and the nose is fuller.
- The in-use line rides high over the nose; it should drop more clearly into the V.

## Sockets

`LineIn` (over the nose, where the loaded line arrives), `Jaw` (the centre of a 6 mm line held in the V), `Eye`,
`LineOut` (the tail end, toward the sailor), `FixAft`, `FixFwd` (the screws). Origin on the deck at the middle of the
base, +X toward the nose. Sizes: `3-6` (default) and `6-10` (scaled 1.33, the medium size's 64 mm centres).

## Where it goes on the boats (not placed yet)

Layouts are shared files and the game can't import until the PC resumes, so this PR adds the part only. Places it fits:

- Sunfish: the outhaul and cunningham tails on the boom and deck, where small dinghies usually have V-cleats or small
  cam cleats.
- J/22: small control-line tails (cunningham, jib car adjusters), where a 75 mm cam cleat is bigger than the real fitting.

Placing it is a later step, one layout at a time, with a photo of the real boat's fitting.

## In the game (waits for the PC)

The cloud built the whole kit (45 parts) with the `bpy` module: `VCleat` is new (17,870 triangles, light copy 4,466) and
nothing else changed beyond the earlier loop parts already waiting for the PC's import (Block40, HornCleat, FiddleCam,
Fiddle40). `Inputs/boat-kit/kit.json` is left alone, as before: the PC's import copies the new one. On
BEN-PC after Bean's "resume": `scripts\windows\make-boatkit.ps1 -Import`, then
`scripts\windows\test.ps1 -Filter SailingSim.Visual.HardwareKit`, then a gallery close-up (`-SailingGallery=SM_Kit_VCleat`).

## Running it

    python3 Tools/boatkit/partloop/render_views.py VCleat Artifacts/partloop/VCleat/r9
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/vcleat.json Data/Reference/raw/parts/VCleat Artifacts/partloop/VCleat/r9
    python3 Tools/boatkit/partloop/make_sheet.py <reference crop> Artifacts/partloop/VCleat/r1 Artifacts/partloop/VCleat/r9 vcleat_before_after.jpg \
        --title "V-cleat with fairlead" --in-use Artifacts/partloop/VCleat/r9/photo.png --in-use-label "Round 7 from the photo's angle" \
        --line "6 mm line" --zoom 0.7
