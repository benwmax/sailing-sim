# Storm look 2: green water over the rail

"Green water" is solid sea coming aboard, as opposed to spray. On a small keelboat it happens when the bow buries in a
steep sea, or when a knockdown drags the lee rail under.

## Where (`GreenWaterOn`, `Source/SailingPhysics/Public/GreenWater.h`)

Plain logic in SailingPhysics, used only for visuals. Buoyancy already counts the water's height, so nothing about the
boat's motion changes.

- It samples her main hull's sheer (`FHullShape::SheerHeight`, `DeckHalfBeam`) on both rails at 9 stations, from near
  the transom (0.9 of `SternX`) to near the bow (0.92 of `BowX`).
- It returns:
  - the deepest water over the rail;
  - which rail, weighted by depth (-1 port, +1 starboard, near 0 when both are under: a sea over the bow);
  - the body-frame x of the deepest point and its world position.
- The J/22 has 0.62 m of freeboard over a 1.18 m half beam, so flat water reaches her rail at about 28 degrees of heel.
- `SailingSim.Physics.GreenWater` checks:
  - dry afloat and at 20 degrees;
  - lee rail under at 40 degrees, on either side, equally deep;
  - deeper at 55 degrees;
  - pitched 15 degrees bow down, a sea over both rails forward.

## What it draws

- **Sheets and drops** (`AWaterSurface::UpdateSpray`, every boat within 120 m of the camera). Sheets of water and drops
  are thrown up off the rail where it is deepest:
  - as many as the depth allows, at most 10 a frame (scaled by Ultra's pool);
  - pushed inboard, off the rail they came over;
  - carried at only 15% of the boat's speed, so they sweep aft across her deck.
  The hull-spray kill (`InsideABoat`) stops any that blow into the cabin.
- **A film over the deck** (`MPC_Boat` `Wash` and `WashSide`, set by `ASailboatPawn::UpdateBoatWetness` for the player's
  boat). `Wash` rises with the depth (full at 12 cm) and drains over 1.8 s. It also:
  - soaks the deck (`DeckWet` 1);
  - raises the topsides' spray band;
  - tops up the puddles.
  In `BOAT_CODE` (M_BoatSurface) and the hero's `DETAIL_CODE` it is a dark, glossy sheet on upward-facing surfaces. On a
  rail sea it covers that half of the deck. Ripples run aft at about a metre a second and fade out from 3 to 6 m. Nothing
  is computed without a sea aboard (a branch on `Wash`).
- **A kick to the camera** (see [../camera-buffet/](../camera-buffet/)).
