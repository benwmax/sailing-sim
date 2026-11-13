# Natural sound: winch clicks and storm variety (feedback #18, #19)

Two playtest notes from the Nov 13 2026 thunderstorm run on Ray Hubbard (J/22, 13 kn): a constant winch-like
clicking, and a storm that sounded like one steady wind into a microphone.

## What changed

**Winch clicks only when you winch (feedback #18).** The trim sound used to follow every change of the sheets,
including the trim assist's and the crew's small, frequent trims, so on a winch boat the ratchet clicked all the
time. `SailingSound::AudibleTrimRate` now silences the crew's trims and small eases on a winch boat unless the
player's own hand is on a sheet (`SailingSound::IsPlayerTrimming`, filled by `ASailboatPawn::IsPlayerTrimming`: a
sheet key moved a sheet in the last 0.25 s; at a crew station only that station's keys, the jib trimmer's grinder
taps included). A sheet the crew let run (under -0.3) is still heard; a dinghy's sheet still runs through its
blocks. The click one-shot is a little quieter (0.45 of the boat group, was 0.6).

**Water at the hull under way (feedback #18).** A new synth layer in `USailingSynthWave`: wavelets slapping and
knocking the hull at random, a soft one now and then in a light breeze (about 0.4 a second) and more often and
harder in a chop (up to about 1.8 a second), from `FSailingSoundParams::Chop` (`SailingSound::ChopFor`, the true
wind). The pack's choppy lapping loop now also plays under way in a chop, not only at rest.

**A storm that moves (feedback #19).**
- The wind roars and lulls: `SailingSound::WindBuffet` (four slow waves at rates with no common period, surges a
  few seconds apart) scales the wind's level (0.55 to 1.45) and the pack wind loops' pitch (0.94 to 1.08) by
  `SailingSound::Storminess` (apparent wind over about 17 kn, rain, or a squall coming). An ordinary afternoon's
  beat without rain is unchanged. The synth wind takes it linearly, like the recorded loops.
- The low gust rumble (ear buffeting) is at half its old level: it was the "wind into a microphone".
- Rain comes in waves (`SailingSound::RainSwell`, 0.6 to 1.3 over 5 to 20 s, capped at 1.2 of the old full rain) on
  the deck and the water, and a new layer drums drops on the sails (not with the sails stowed).
- Distant thunder between the strikes: while a cell is within about 20 km, `ASailingEnvironment::UpdateLightning`
  adds unseen rumbles toward the cell, at least 8 km off and never nearer than the cell, every 7 to 21 s under it
  (14 to 42 s at the edge), lasting 6 to 10 s with a slow swell-in (`FThunder::Rise`), from their own random
  stream (benches stay reproducible). One "Thunder, distant" caption at most every 25 s. They have no flash or
  bolt (in the rain and gloom you hear them, you don't see them), so the visible lightning is unchanged.
  `-SailingNoLightning` turns them off too.

Birds: shore life already goes quiet in rain (`ShoreLifeFor`), so a thunderstorm has none by design; in fair
weather they sing as before.

No new sound files: everything is synthesized or reuses the CC0 pack.

## Tests

`SailingSim.Audio.CrewTrimSilent`, `SailingSim.Audio.StormVariety`, `SailingSim.Audio.NaturalLayers`.

## Listening check

`scripts/loudness-check.sh 20 storm breeze` before and after (target -18 LUFS +-3, -1 dBTP), and by ear:
`-SailingWorld=ray-hubbard -SailingBoat=J22 -SailingWeather=Thunderstorm -SailingWind=13 -SailingTWA=-90`.
