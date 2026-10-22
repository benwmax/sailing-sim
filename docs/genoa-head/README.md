# The Catalina 30's genoa head

RigClearance listed the Catalina 30's upper shroud through her genoa close-hauled (15 samples, rows 23 and up, just
under the head).

## The cause

The genoa's head was in the wrong place. `SetSail(C.Jib, ...)` put it at 13.2 m with its luff at x 1.15: the mast's
front face, since the mast is at 1.05 and 0.16 thick. Her forestay runs from the tack (x 4.45, z 1.3) to the masthead
(about 1.13, 13.99), so at 13.2 m it is at x 1.34. The head sat 19 cm aft of the forestay, inside the mast. With its
15 cm head chord, the leech was there too, a hand's width from the upper shrouds where they meet the mast. No turn of
the cloth (`FSailCloth::KeepClear`) could take it outside them.

## The fix

The head is on the forestay now: `LuffXHead` 1.34, commented with the line it comes from. The cloth follows the
physics strips, so the drawn luff now lies along the drawn forestay up to the head.

- **Polar:** `scripts/polar.sh --boat "Catalina 30"`: 0 of 15 points outside tolerance, as before. The close-hauled
  points move up to +0.02 kn (16 kn at 60°: 6.22 to 6.24); everything else is unchanged.
- **RigClearance:** her genoa entry is gone. 17–18 kinds of clip remain, depending on the run's crew contacts. All
  are spreaders under running mains, lines on the deck, and the Hobie's one jib sample.

## Stills

`head-before` and `head-after`: High, 7 kn, close-hauled, looking up the mast. Before, the head is pressed into the
mast; after, it is forward on the forestay.

## Tried and dropped

I first allowed the top rows a bigger turn, included the head row, and checked every place where the cloth meets the
wire. It helped (15 samples to 8) but couldn't clear a head sitting inside the mast. With the head on the forestay
none of that is needed, so it isn't in this change.
