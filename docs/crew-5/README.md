# C5: crew falls

When the boat is knocked hard or laid over, the crew stop being posed by their animation and become active ragdolls:
every body of the MetaHuman's physics asset is simulated and pulled toward the animated pose by Unreal's Physics Control
plugin, with the pull weakened by how hard they were thrown. When the boat is steady again the pull climbs back to
full and the animation takes them back. On by default on Ultra (the PC first); `-SailingCrewFalls=0|1` overrides it on
any tier that has the MetaHuman crew. AI boats and Low (SK_Sailor, which has no physics asset) keep their animation.

![A J/22 laid over 80 deg and righting (Ultra, every 0.25 s)](knockdown-ultra.jpg)

## How it works

- **When:** `FCrewFalls` (`CrewFalls.h`, plain logic, one per boat) reads the boat's heel (`Quat::Tilt`), the
  acceleration the crew feel (`FBoatTelemetry::AccelBody`, across the deck and along the mast) and whether she is
  capsized.
  - **Thrown:** past 55 deg of heel, capsized, or more than 1 g across the deck or up and down (a collision, a grounding,
    a slam).
  - **Back:** after at least 0.8 s, once the boat has been under 30 deg and under 0.35 g for a second. The controls then
    climb back to full over a second and hold for 0.3 s, and the animation takes over.
  - A new knock while they gather throws them again.
- **How hard they hold on:** the controls run at 35% of full after a knock (braced, staggering) and 12% after a knockdown
  or capsize (hanging on, mostly limp).
  - Parent-space controls hold each joint toward its animated angle.
  - World-space controls hold the body to the boat, weakly.
  - Both are acceleration drives, so the bodies' masses don't matter.
- **The boat:** the hull has no collision, so `CrewDeck`, a box the size of the deck just under the sheer, moves with
  the boat as a kinematic body. The crew land on it, and the world-space controls work in its frame, so a thrown sailor
  is pulled along with the boat rather than left behind. Bodies that start a fall inside the box are eased out at
  40 cm/s, not thrown.
- **The water:** a body under the wave surface (`FWaveField::Height` under its centre of mass) is held up at 1.12 g at
  full immersion (a person floats; the life jacket is on the chest) and damped at 2.5/s.
- **Cost:** nothing until someone falls. While posed, the crew's bodies have no collision and the controls don't tick.
  With them active all the time it cost 1.6 ms of game thread on Ultra; switched like this the crew close-up measured
  the same with falls on and off (12.1 against 12.2 ms, within noise).

## Measuring and stills

- `-SailingKnockdownAt=<s>[,<deg>]` lays the player's boat over by that many degrees (80 by default) at that sim time.
  The physics takes it from there: a keelboat rights herself, a dinghy may stay capsized. A roll rate alone doesn't
  work: the J/22's roll damping took 7 rad/s down to 34 deg of heel within a tenth of a second.
- `-SailingRecord=<s> -SailingRecordInterval=0.25` saves frames for a sequence like the one above (taken with
  `-SailingWind=10 -SailingTWA=70 -SailingCamYaw=230 -SailingCamPitch=-12 -SailingCamDist=9 -SailingKnockdownAt=6,80`).
- The log says `Crew falls: thrown ...` and `back on their feet ...`.
- Test: `SailingSim.Visual.CrewFalls` covers when they fall and recover:
  - hard sailing never throws them;
  - a knock does, with grip left, and they are back in about 2.3 s;
  - a capsize keeps them falling until she is righted;
  - a slam while they gather throws them again.

## Left for later

- The control component ticks before physics, after the crew mesh, which ticks after the boat's own physics join. So
  the ragdoll is about a frame behind the boat. That doesn't show at these speeds, but would in a fast collision.
- The deck box is flat: there is no cockpit well, cabin top or lifeline to hold on to. Sockets on the hero J/22
  (`HandholdCabin`, `SideDeck`, `CockpitSole`) could give it a better shape and hand targets.
- Only the player's MetaHumans. SK_Sailor would need a physics asset (`import_boats.py` imports it without one).
- High on the Mac: not tried. Enabling it there means the Mac gate on a knockdown still.
- A sailor who goes over the side floats and is pulled back when the boat steadies. There is no man-overboard state
  or swimming yet.
