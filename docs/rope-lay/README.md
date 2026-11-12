# Rope lay (rope realism, phase 1)

Plan: the "Rope realism" artifact (Nov 11 2026). Bean lifted the freeze for phases 1 and 2 on Nov 11 (23:42 UTC); merge only
while the High crew view holds 45 fps. Ropes are still drawn, not simulated: the same inputs always give the same rope.

## What changed

Before: each line was a chord plus a parabola sag, 10 segments and 8 sides. Where it touched the boat, each ring was
lifted straight up in 2 cm steps and the spans were then checked six times. A lazy sheet over the cabin trunk floated up
to 5 cm above the roof, stepped 1.36 to 1 between neighbouring rings, and its rings flicked by up to 2 cm as the clew moved
a millimetre (the 2 cm steps).

Now, on the player's boat (`RopeLay.h`, plain C++ in SailingPhysics; `LayFineRopes` in `BoatModelVisuals.cpp`):

1. **Lay**: the free curve sampled at least every 6 cm; each sample lifted by exactly what it needs (an exponential search,
   then bisection to 0.1 mm) and the samples refined where the lift changes; the rope then rests on the upper hull of the
   lifts, so free spans keep their curve and the rope bridges the gaps an edge leaves.
2. **Round**: each bend (an edge it lies over, a block it turns on) becomes a circular arc, at most a third of the rope's
   radius deeper than the lay found it must be; a rope drawn as several lines (clew to block to winch to tail) is rounded
   as one, so it meets each block on its tangent.
3. **Rings**: 24 rings (12 sides), the ends and each bend's arc taking rings of their own, the rest spread by length plus
   turn. Then each span is checked at its quarters and lifted if it still cuts the boat.
4. **Braid**: U runs on along the whole rope from its tied end (the clew), so the cover scrolls through a lead as it is
   trimmed and stays put at the clew.
5. **Winch**: on boats with a jib winch (Catalina 22, Corsair 880, Catalina 30, Lagoon 42) the working sheet goes in on the
   drum's tangent, three turns clockwise seen from above up the drum, and off the top to a tail on the deck.
   **The J/22 has no jib winch**: its `JibWinch` socket is the cam cleat's fairlead and `JibTailer` its jaws (Bean's
   feedback 3, the Harken layout). There the sheet runs smoothly through the fairlead into the tail.

AI boats and the ghost keep the old drape (their ropes are far away and many). `-SailingClassicRopes` draws the player's
boat the old way, to compare.

## Checks

`scripts/rope-check.sh` (standalone, about a second) and `SailingSim.Visual.RopeLay.*` run the same checks
(`RopeLayChecks.h`): a free line on its parabola, the lazy sheet over a model trunk (resting on the roof, no steep step, no
tight bend), no shimmer as the clew moves a millimetre at a time, determinism to the bit, the tangent round a block, the
winch turns from either side, 2,592 lays all round the trunk, 2,520 lays of a sheet under and over a sitting sailor and 432 of a
mainsheet across a lifeline's wires. Results on Nov 12:

| Check | New | Old drape |
|---|---|---|
| Rings above the roof | 0.24 cm | 5.22 cm |
| Steepest step between rings | 0.67 | 1.36 |
| Shimmer, clew moved 1 mm | 0.09 cm | 1.95 cm |
| Deepest centre into the trunk, 2,592 lays | 0.44 cm | 0.33 cm |
| Deepest centre into a sailor, 2,520 lays | 0.00 cm | |
| Lays with a point in a lifeline wire, 432 | 0 | |

`SailingSim.Visual.RigClearance` still holds the boat's own lines against the hull, crew and lifelines. Two things it
found on the first Mac run (a Catalina 22): the lay's sailors had their back as one straight piece from pelvis to chest,
and a lazy sheet laid over it went 2.8 cm into the curved spine; they now have the MetaHuman's trunk bone by bone, its
neck, head and collarbones, as the test does. And a mainsheet crossed a lifeline's wire at its corner between two of a
span's quarter checks: a line that reaches the lifelines now has its spans checked every 0.9 cm against the wires grown
by 0.5 cm, so no piece between two checks can reach the wire itself (`OverALifeline`). On the second run the lazy
sheet was still 3.3 cm into the sailor's back: a steep span over the shoulders was lifted by what its first blocked point
needed, a few millimetres a pass, and six passes ran out. A span now goes up by the most any of its points needs, a line
near a sailor has its spans checked every 2 cm, and the passes run on to 24 (they stop as soon as nothing moves).

## Known limits

- The lift is straight up (in the boat's frame). A rope climbing a vertical face can come up to its radius from the face
  (the 0.44 cm above, inside the rope's 0.45 cm radius); the old drape had the same limit.
- Phase 2 (knots at the sockets) is separate; phase 3 (rope physics) is after the slice.
