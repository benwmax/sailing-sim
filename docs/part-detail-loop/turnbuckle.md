# Part detail loop: the turnbuckle (Nov 8 2026)

Bean's ask (Nov 8): model each part on his sailboat hardware reference sheet, one part per session, with the
[part detail loop](README.md). This page is the turnbuckle, the sheet's bottom row: an open-body turnbuckle with a jaw
fitting and a swage stud.

The kit's `Turnbuckle` is now built in its own file, `Tools/boatkit/bk_part_turnbuckle.py`, so several parts can go through
the loop at once without touching the same lines: `bk_parts.py` imports every `bk_part_*.py` at its end, and each of those
registers its part with `@part`. The old builder is gone from `bk_parts.py`.

Card: `Tools/boatkit/partloop/parts/turnbuckle.json`, with `turnbuckle_photo.json` for the outline (below).

## What it is now

An open-body turnbuckle for 3/16 in (5 mm) wire, as small keelboats use on their shrouds:

- a forged jaw whose two prongs straddle the chainplate strap (7 mm gap for the kit Chainplate's 6 mm strap), with a 1/4 in
  clevis pin, a domed pin head and a split ring through its far end;
- a threaded 1/4-28 stud from the jaw's forged neck up into the body;
- a forged open body: lens-shaped, round end bosses, two long windows with a centre bridge, their edges flared out to the
  faces like a forging's chamfer, the bore through it;
- cotter pins through both studs' ends inside the windows;
- a threaded swage stud up out of the body into the swage sleeve, with a shoulder off the thread, a rolled band and a
  tapered end where the wire goes in.

All stainless, one material slot, 18,060 triangles (the light copy 4,514). Frame: the jaw's pin is the origin (the
chainplate's `Pin` socket), the pin along Y, the wire up +Z. Sockets keep their names: `Toggle` is now exactly on the pin
(it was 4 mm above it) and `Wire` stays 216 mm above the origin, so the Catalina 22's shrouds (build_fleet.py's
`C22_TURNBUCKLE_TOP`) still end on the turnbuckle's eye. `exposed` (the thread showing at each end) sets how far it is
opened; the kit always builds the default, which puts the sleeve's end at 216 mm.

## Rounds

| Round | Length | Outline (photo's setting) | Features | Triangles | Blind review |
|---|---|---|---|---|---|
| Before | 216 mm (-4%) | 54.8% | 3/9 | 6,732 | lost 2 of 3 to r3; two reviewers called it the wrong part ("bottle-screw or lantern tensioner", "barrel or telescoping tensioner") |
| r1 | 227 mm | 88.8% | 7/9 | 16,216 | |
| r2 | 227 mm | 89.1% | | 18,026 | (flared windows, square-shouldered jaw) |
| r3 | 227 mm | 90.7% | 8/9 | 18,060 | won 2 of 3 against before (confidence 5, 5; lost one at 4 on threads) and 2 of 3 against r1 (3, 3) |
| r4 | 227 mm | 91.7% | | 18,456 | **lost** 1 of 3 to r3: a longer body, wider windows, taller jaw and shorter sleeve read as less clean; dropped |
| r5 | 227 mm | 90.7% | 8/9 | 18,060 | won 3 of 3 against r3 (confidence 2, 2, 2): r3 with r4's deeper thread and thicker cotter pins |

Sizes on r5: 226.8 mm from the jaw's end to the sleeve's end at the kit setting (target 225.5, +0.6%), the jaw's head
20.8 mm across (target 20.5, from the photo's proportions), and 176.8 mm set as the photo (catalogue closed length 177.5,
-0.4%).

The one feature that doesn't pass is the cotter pins: they are modelled (0.8 mm wire through each stud's end) but at the
loop's 900 px stills of a 227 mm part they read as "a small round feature" at best. The thread has the same problem in a
smaller way. Both are real-size details that only show in a close camera; they cost few triangles, so they stay.

### Why there are two cards

Bean's reference photo shows the turnbuckle screwed nearly closed (about 8 mm of thread showing each end); the kit's part
is set about two thirds open so its wire end stays where the old part's was. Comparing those two outlines would mostly
measure the setting, not the shape. So `turnbuckle.json` checks the kit's part (catalogue length, features, budget,
blind review) and `turnbuckle_photo.json` checks the outline and proportions against the photo with the part rendered at
the photo's setting by `partloop/render_kw.py` (render_views.py with builder options; the kit itself never uses them).

## Still different from the photos

The reviewers' shared notes on r5, for a later round:

- Threads and cotter pins are faint at this render size (above).
- The body could be a little fatter in the middle with brighter rolled rims round the windows; r4 tried a longer body and
  wider windows and lost, so a later round should change one of those at a time.
- The jaw reads boxy: real prongs are thinner plates with fully round ends.
- The preview materials make polished stainless white and flat (the same for before and after, as for every part).

## In the game (waits for the PC)

The whole kit builds in the cloud with the `bpy` module (44 parts); only `Turnbuckle` changes from this work
(`Block40`, `HornCleat`, `FiddleCam` and `Fiddle40` already differ from `Inputs/boat-kit/kit.json` from the earlier tests,
which leave kit.json for the PC's import). The kit turnbuckle is placed on the Catalina 22 today (build_fleet.py
`c22_hardware`); the J/22 hero has its own closed-body turnbuckles in boots (Inputs/j22-hero/j22_mastgear.py), which
matches the real J/22, so nothing changes there. On BEN-PC after Bean's "resume": `scripts\windows\make-boatkit.ps1 -Import`,
then a close-up of a Catalina 22 shroud base.

## Running it

    python3 Tools/boatkit/partloop/render_views.py Turnbuckle Artifacts/partloop/Turnbuckle/r5
    python3 Tools/boatkit/partloop/render_kw.py Turnbuckle Artifacts/partloop/Turnbuckle/r5/photo_setting exposed=0.008
    python3 Tools/boatkit/partloop/render_turnbuckle_in_use.py Artifacts/partloop/Turnbuckle/r5
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/turnbuckle.json Data/Reference/raw/parts/Turnbuckle Artifacts/partloop/Turnbuckle/r5
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/turnbuckle_photo.json Data/Reference/raw/parts/Turnbuckle Artifacts/partloop/Turnbuckle/r5/photo_setting

`render_turnbuckle_in_use.py` stands the turnbuckle on the kit Chainplate with a 3/16 in wire (render-only) for the
sheet's in-use row. The reference mask `bean.mask.png` was cut from Bean's sheet by thresholding the white background
and turning the part upright (its axis was 45 degrees off).

## References

None of these are in the repo; the git-ignored copies are in `Data/Reference/raw/parts/Turnbuckle/`.

| Reference | Used for | Licence |
|---|---|---|
| Bean's hardware reference sheet (Nov 8), bottom row | outline and proportions (a retailer's product shot) | measuring only |
| [Bootsmesse Berlin 2009, RalfR-38](https://commons.wikimedia.org/wiki/File:2009-11-28-bootsmesse-berlin-by-RalfR-38.jpg) (Ralf Roletschek) | forged open bodies close up: windows, bridge, cotter pins | CC BY-SA 3.0 |
| [RalfR-40](https://commons.wikimedia.org/wiki/File:2009-11-28-bootsmesse-berlin-by-RalfR-40.jpg) | square-on and three-quarter bodies, swage studs, toggles on deck | CC BY-SA 3.0 |
| [RalfR-37](https://commons.wikimedia.org/wiki/File:2009-11-28-bootsmesse-berlin-by-RalfR-37.jpg) | the same pair in place on the side deck | CC BY-SA 3.0 |
| [Hayn 3/16 in jaw-to-swage](https://www.westmarine.com/hayn-tubular-turnbuckle-jaw-to-swage-for-3-16inch-wire-1-4inch-pin-7415490.html) and similar listings | 1/4-28 thread, 1/4 in pin, 6-5/8 in closed to 9-3/8 in open | numbers only |

No commercial-OK 3D model of a marine turnbuckle turned up; nothing was bought ($0).
