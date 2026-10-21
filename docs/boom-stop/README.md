# The boom stops at the shroud

On a run the J/22's and the Catalinas' booms went out to 85°, past their aft shrouds, and the eased main lay through
the wires. RigClearance listed this as a known gap. On a real boat you ease until the boom touches the shroud. Now
each boat's `MainMaxEaseDeg` is that angle, from its own geometry.

## The stop, boat by boat

The stop is where the boom's side meets the aftmost shroud leg at boom height. It is measured from the gooseneck
(`MainLuffX` at `BoomZ`), with the shroud running from its chainplate (the boat's `_sockets.json`) to its mast tang or
spreader tip.

| boat | was | now | the leg that stops it |
| --- | --- | --- | --- |
| J/22 | 85 | **80** | the upper shroud's lower leg, 1.02 m from the gooseneck (her uppers are 4 cm aft of her lowers) |
| Catalina 22 | 85 | **70** | the aft lowers, chainplates 0.31 m aft of the gooseneck, 0.83 m from it at boom height |
| Catalina 30 | 85 | **76** | the aft lowers, 1.22 m from the gooseneck |
| Lagoon 42 | 65 | 65 | her lowers would stop it at about 81: her mainsheet's 65 comes first |
| Maxi 100 | 72 | 72 | her upper shroud's lower leg would stop it at about 76: 72 is inside it |
| Corsair 880, Hobie 16 | 75, 70 | kept | rotating masts |
| Sunfish, ILCA 7 | 100 | kept | unstayed |

The drawn boom already follows the physics boom (`BoomPivot`), so it now rests on the shroud.

## The polars

`scripts/polar.sh`, before and after:

- **J/22:** 0 of 39 points outside tolerance, as before (worst 8.1% before, 8.0% after). Her run and broad-reach
  points move by 0.04 kn at most; the biggest is 15 kn at 150° with the spinnaker, 6.67 to 6.71.
- **Catalina 22:** 0 of 15 outside, as before. 10 kn at 150° goes from 5.23 to 5.26.
- **Catalina 30:** 0 of 15 outside, as before. 10 kn at 150° goes from 5.61 to 5.35 against a 5.38 target, so
  +4.3% becomes −0.6%.
- **Scenarios:** unchanged, except one tack's speed 10 s after the tack, 5.40 to 5.39.

## The sail near the mast

Up high, a shroud closes in on the mast toward its tang. The eased main still pressed on it there, in the first two
columns from the luff, whatever the boom angle. `FSailCloth::KeepClear` now dents the main's target shape round the
wire after its turn: fully within 15 cm of the wire's distance from the luff, easing out over 45 cm. The cloth follows
the target. Denting the simulated cloth itself kinked it across the spreaders, so only the target is dented.

## RigClearance

Running-main entries, the samples summed across the listed kinds:

- main: 104
- the boom stop alone: 104. The boom is out of the wires, but the cloth near the mast still crosses them.
- the boom stop plus the dent: **63**.

All of the Catalina 22's entries are gone, as are the Catalina 30's and the J/22's lower shrouds and the Corsair's
shrouds. What is left:

- the main draped over a spreader, on the Catalina 30, the Corsair and the Maxi;
- the J/22's and the Maxi's main against the lower leg of the upper shroud, near the spreader tip;
- the Hobie's trapeze wire.

A running main lies on the spreaders and their tips on a real boat too. These stay listed, not failed.
