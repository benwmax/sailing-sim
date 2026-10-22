# Tied up in the slip: she lies still

**The symptom:** the first lesson (Leave the dock) starts in the J/22's home slip. Tied up in 6 kn, she rolled about
4 deg every 1.4 s (heel 0 to -4.4 deg, `-SailingCapture=Chase` telemetry). From the cockpit the whole marina rocked. The
same roll went on after the lines were off, while she drifted or backed out at under a knot.

**Why:** two things, both in the physics.

1. **The crew chased "leeward" round her stern.** `FAutoTrim`'s hiking moves the crew to keep about 4 deg of leeward
   heel in light air. With no way on and the wind abaft the beam, the apparent wind swung through the stern as she
   rolled, so "leeward" changed sides every roll. The crew (hike -1 to -0.6) shuttled across the cockpit at her roll
   period: a limit cycle.
2. **Stowed sails still flew.** `bSailsStowed` (Graphics G6: covered and furled) was visual only. The physics still had
   both sails up and flogging, heeling her about 3 deg and kicking the roll in the gusts.

**Fix:**
- `FAutoTrim`: tied up, or with no way on (under 0.8 kn through the water) and not pressed (under 8 deg of heel), the
  crew sit on the centreline (hike -0.5, which is offset 0 whichever side is windward).
- `FBoatControls::bSailsDown` (furled and covered): the sails give no force, through their `Dry` factor, as a sail in the
  water has none. The rig's and hull's windage stay. The pawn sets it while the sails are drawn stowed
  (`bSailsStowed && StowedDress && IsTiedUp()`).

**Now:**
- `SailingSim.Lake.TiedUpSitsStill` puts the J/22 in the home slip in 6 kn of gusty wind from ahead, abeam, astern and
  either quarter, with `FAutoTrim` running. She lies within 0.3 deg (it was up to 2.3 deg of roll at 3.4 deg/s, and
  4 deg of lean). Alongside a plain dock she lies still too.
- In the game, the tied-up and casting-off roll is about +-1 deg. That is what is left: the marina's 1.6 cm chop at her
  roll period, a gentle rock. The crew hold the centreline.
- The polar and scenarios are unchanged. One reference check moved within its band: the J/22's peak running in 30 kn,
  reefed, from 13.55 to 11.97 kn (9-16 kn). That run starts from rest, so the crew sit centred for its first seconds.

**New measuring arg:** `-SailingCastOffAt=<s>[,<throttle>]` casts off at that sim time and holds the outboard (-0.4
astern by default), for stills of the boat leaving the slip.
