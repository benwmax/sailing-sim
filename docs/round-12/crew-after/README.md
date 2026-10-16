# Round 12 crew fix on the Mac

Captured from this branch merged with main 13bd81d6, uncooked (`run-game.sh`), High:
`SCENES=docs/round-12/game/scenes.csv OUT=docs/round-12/crew-after scripts/capture-scenes.sh 14`.
Compare with the before stills in `../crew/`.

Recaptured Oct 16 on 71671047 merged with main 88a5cee0: 149/149 tests, crew gate passes (stills replace the 5e1aa53b ones; the helm's forward shoe still rests on the traveler bridge and the thumb still stands straight up).

Recaptured Oct 16 (mainsheet only) on e2ab89a5 (main af8de58c merged): 148/149 tests (only MetaHumanCrew's thumb-wrap check fails: the thumb tip moves 6.1 -> 6.1..6.3 cm from the index on the helm and bow, 6.0 -> 5.7 on the trimmer), crew gate passes on fps. Light SM_J22 model (no `-SailingJ22Hero`). The helm's forward shoe rests on the traveler bridge; the helm's thumb on the tiller extension still stands straight up, not wrapped.

## Tests: 145 of 149, four fail

All four pass on main (149/149 on the same machine the same day). One line from each:

- `SailingSim.Visual.CrewFeet` (80 errors): "J/22, Bow crew 0 (stance 2, starboard tack, hike 0.0): right foot stands on
  the floor tilted: heel 0.64 m, toe 0.59 m" and "... right toe at (-0.47, -0.12, 0.59) m is inside the boat". Also
  Catalina 22 and Catalina 30 bow (stance 2), every Catalina 30 crew (heel 0.91, toe 0.95 to 1.08), Corsair 880, Lagoon
  42 helm and ILCA 7 hiking ("heel 0.09 m, toe 0.18 m").
- `SailingSim.Visual.CrewMotionFeet` (214 errors): "J/22, Bow crew 0 (starboard rail, stance 2): right toe inside the
  boat at (-0.47, 0.07, 0.59) m". Same boats: J/22 and Catalina 22 stance 2, Catalina 30 and Corsair 880 stance 0.
- `SailingSim.Visual.CrewClipLimits` (4 errors): "J/22, SK_Sailor crew 0 (stance 0, hike 1.0, side +1): the right foot
  moves 14.5 cm at most (within 3)"; Bow 6.5 cm, Trimmer 6.8 cm.
- `SailingSim.Smoke.CrewAnimation` (1 error): "SkeletalMeshComponent_0 sits (thigh to knee -31 cm up)".

What they point to: after `LevelFeet` the toe ends about 5 cm below the heel and inside the deck, where the heel is on
one floor level and the toe over another (the tests read the sole against the hull, `LevelFeet` against
`max(CrewFloorZ(heel), CrewFloorZ(toe))`). The new 1 to 15 cm drop for seated feet makes a hiked foot jump as the clips
move it in and out of that band (CrewClipLimits), and probably pulls the knee below the thigh in the smoke test.

## Against the "Watch for" list

- **Mainsheet arm stretch** (`r12-j22-mainsheet`, `r12-j22-cockpit`): not stretched. The helm sits aft of the traveler
  with the tail running back to the lap; the tiller hand holds the extension with the thumb up.
- **A foot on the traveler bridge** (`r12-j22-mainsheet`): yes. The helm's forward shoe rests on the bridge, over the end of
  the track (`CrewFloorZ` doesn't know the bridge is there, as the README feared). The other foot lies flat on the sole (the heel-down, toe-up foot of still03 is gone).
- **An over-bent wrist** (`r12-j22-mainsheet`): not over-bent. The fingers now close round the extension (a fist, no
  longer an open hand beside it) with the wrist cocked a little. The thumb stands straight up off the stick instead of
  wrapping it, which reads as a thumbs-up; that is the finger curl, not `MaxRad`.
- **Bunching** (`r12-j22-cockpit`, `r12-crew-idle`): fixed. The helm sits level with the tiller's end and the after half
  of the cockpit is used.

## Crew gate (`scripts/gate.sh --scope crew --no-tests`, the tests fail above)

Packaged, fps / p99 ms / GPU ms, Medium then High; all over 60/45 and level with #87's boats gate the same day:
beat15 85.9 / 12.69 / 10.97, 55.7 / 19.93 / 17.89; coast-day 84.6 / 12.27 / 11.46, 53.6 / 19.53 / 16.8;
helm-eye 88.1 / 12.29 / 10.77, 55.2 / 20.84 / 17.51; slip 82.4 / 12.84 / 12.38, 52.2 / 20.06 / 18.23;
crew 72.0 / 14.76 / 13.4, 52.4 / 21.44 / 17.76.
