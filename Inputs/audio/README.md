# Sailing sim sound sample pack

Recorded and script-built sounds for the layers in `USailingSynthWave` (`Source/SailingSim/Private/SailingAudio.cpp`).
Everything is 48 kHz 16-bit PCM WAV. Mono unless the table says 2 channels (stereo beds for ambience, rain, shore surf and storm wind).

## Levels and loops

- Loops are set to -20 dBFS RMS (peak capped at -1 dBFS) so they mix at matching loudness; one-shots peak at -1 dBFS.
- Every loop loops on the whole file: loop start is sample 0 and loop end is the last sample. Script-built loops are
  generated periodic (no seam at all); recorded loops have a 1 s equal-power crossfade baked into the head.
- In Unreal set `Looping` on the Sound Wave (or loop in MetaSound Wave Player). No loop region markers are needed.
- One-shots with numbered variants (`_01`, `_02`...) are meant for random selection, with a +-5 % pitch spread.

## Import on the Mac

1. Copy `Samples/` into `Content/Audio/Samples/` keeping the subfolders (or drag the folders into the Content Browser).
2. Unreal creates one Sound Wave per WAV. Batch-set `Looping` on every `*_loop` asset.
3. The `Game parameter` column suggests which `FSailingSoundParams` value drives each file. Recorded layers can sit under
   or replace the synthesized ones; the synth keeps working with no samples present.
4. Update `CREDITS.md` in the repo root: the Sound section says no recorded samples are used. Copy the
   attribution lines from `CREDITS.md` here when any recorded file ships in a build (CC BY and CC BY-SA need credit).

## Sources

- Only Wikimedia Commons is reachable from the cloud environment that built this. Freesound, archive.org, Pixabay,
  BigSoundBank and Sonniss were blocked, so sailing-specific sounds Commons does not have (rigging, halyards, luffing,
  winches, blocks, hull wash, outboard) are script-built by `scripts/synth.py` (seeded, reproducible: `python3 synth.py OUT`).
- Recorded clips are cut by `scripts/process.py` from the Commons files listed in `CREDITS.md`.
- CC BY-SA clips: the derived WAVs here are CC BY-SA too. Shipping them in a game build is fine with credit; the licence
  covers the sound files themselves, not the rest of the game.

## Files

| File | Type | Seconds | Ch | Use | Game parameter | Source |
|---|---|---|---|---|---|---|
| `Birds/gull_call_01.wav` | one-shot | 1.97 | 1 | Gull calls over the water and marina (both lakes) | Random one-shots from shore positions, by place and time of day | [Public domain](https://commons.wikimedia.org/wiki/File:Gull_1.ogg) |
| `Birds/gull_call_02.wav` | one-shot | 0.54 | 1 | Gull calls over the water and marina (both lakes) | Random one-shots from shore positions, by place and time of day | [Public domain](https://commons.wikimedia.org/wiki/File:Gull_1.ogg) |
| `Birds/gull_call_03.wav` | one-shot | 1.35 | 1 | Gull calls over the water and marina (both lakes) | Random one-shots from shore positions, by place and time of day | [Public domain](https://commons.wikimedia.org/wiki/File:Gull_1.ogg) |
| `Birds/laughing_gull_01.wav` | one-shot | 3.0 | 1 | Laughing gull, the common gull of Galveston Bay | Random one-shots from shore positions, by place and time of day | [CC BY 3.0](https://commons.wikimedia.org/wiki/File:Larus_atricilla.ogg) |
| `Dock/dock_creak_01.wav` | one-shot | 0.625 | 1 | Dock line or wooden dock creaking as the boat surges in the slip | In the slip: dock line load and fender contact | script |
| `Dock/dock_creak_02.wav` | one-shot | 0.806 | 1 | Dock line or wooden dock creaking as the boat surges in the slip | In the slip: dock line load and fender contact | script |
| `Dock/dock_creak_03.wav` | one-shot | 0.684 | 1 | Dock line or wooden dock creaking as the boat surges in the slip | In the slip: dock line load and fender contact | script |
| `Dock/dock_creak_04.wav` | one-shot | 0.572 | 1 | Dock line or wooden dock creaking as the boat surges in the slip | In the slip: dock line load and fender contact | script |
| `Dock/dock_creak_05.wav` | one-shot | 0.726 | 1 | Dock line or wooden dock creaking as the boat surges in the slip | In the slip: dock line load and fender contact | script |
| `Dock/fender_squeak_01.wav` | one-shot | 0.83 | 1 | Fender squeezed between hull and dock | In the slip: dock line load and fender contact | script |
| `Dock/fender_squeak_02.wav` | one-shot | 0.64 | 1 | Fender squeezed between hull and dock | In the slip: dock line load and fender contact | script |
| `Dock/fender_squeak_03.wav` | one-shot | 0.832 | 1 | Fender squeezed between hull and dock | In the slip: dock line load and fender contact | script |
| `Engines/outboard_idle_loop.wav` | loop | 8.0 | 1 | Small 2-stroke outboard idling in neutral (instructor or club launch) | AI motor vessels and the instructor launch, by distance | script |
| `Engines/outboard_lowspeed_loop.wav` | loop | 8.0 | 1 | Outboard in gear at low speed, motoring out of the slip | AI motor vessels and the instructor launch, by distance | script |
| `Engines/outboard_running_loop.wav` | loop | 8.0 | 1 | Outboard near full throttle (passing ski boats and launches) | AI motor vessels and the instructor launch, by distance | script |
| `Rigging/halyard_slap_01.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/halyard_slap_02.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/halyard_slap_03.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/halyard_slap_04.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/halyard_slap_05.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/halyard_slap_06.wav` | one-shot | 1.6 | 1 | Halyard or wire slapping an aluminium mast (randomise, pitch +-5%) | ApparentWind with the boat in the slip or head to wind | script |
| `Rigging/marina_halyards_distant_loop.wav` | loop | 24.0 | 1 | Marina ambience: many masts tinkling in the breeze (layer under marina bed) | Near the marina (Rush Creek slip, Galveston marinas) | script |
| `Rigging/sheet_ease_through_block_01.wav` | one-shot | 1.6 | 1 | Sheet eased quickly through a block | TrimRate < 0 (easing) | script |
| `Rigging/sheet_ease_through_block_02.wav` | one-shot | 2.4 | 1 | Sheet eased slowly through a block | TrimRate < 0 (easing) | script |
| `Rigging/sheet_running_block_loop.wav` | loop | 6.0 | 1 | Sheet running continuously through a block (gybe, letting fly) | TrimRate < 0 (easing) | script |
| `Sails/sail_fill_snap_01.wav` | one-shot | 0.35 | 1 | Sail filling with a snap after a tack or gybe | Luff falling from > 0.6 to < 0.2 (tack or gybe completes) | script |
| `Sails/sail_fill_snap_02.wav` | one-shot | 0.35 | 1 | Sail filling with a snap after a tack or gybe | Luff falling from > 0.6 to < 0.2 (tack or gybe completes) | script |
| `Sails/sail_fill_snap_03.wav` | one-shot | 0.35 | 1 | Sail filling with a snap after a tack or gybe | Luff falling from > 0.6 to < 0.2 (tack or gybe completes) | script |
| `Sails/sail_flog_strong_loop.wav` | loop | 12.0 | 1 | Violent flogging: tacking through the wind or sheet let fly in a breeze | Luff > 0.7 with ApparentWind > 7 m/s | script |
| `Sails/sail_luff_light_loop.wav` | loop | 12.0 | 1 | Luffing sail, light air or slightly pinched (blend with trim error) | Luff (0.1-0.4 light, 0.4-0.7 moderate) | script |
| `Sails/sail_luff_moderate_loop.wav` | loop | 12.0 | 1 | Luffing sail in 10-15 kn, head to wind or eased too far | Luff (0.1-0.4 light, 0.4-0.7 moderate) | script |
| `Water/hull_wash_1kn_loop.wav` | loop | 16.0 | 1 | Hull wash / bow wave at about 1 kn boat speed (crossfade between speeds) | BoatSpeed (1 kn ~0.5 m/s, 3 kn 1.5, 5 kn 2.6, 7 kn 3.6); raise 7 kn layer as HullSpeedRatio > 0.9 | script |
| `Water/hull_wash_3kn_loop.wav` | loop | 16.0 | 1 | Hull wash / bow wave at about 3 kn boat speed (crossfade between speeds) | BoatSpeed (1 kn ~0.5 m/s, 3 kn 1.5, 5 kn 2.6, 7 kn 3.6); raise 7 kn layer as HullSpeedRatio > 0.9 | script |
| `Water/hull_wash_5kn_loop.wav` | loop | 16.0 | 1 | Hull wash / bow wave at about 5 kn boat speed (crossfade between speeds) | BoatSpeed (1 kn ~0.5 m/s, 3 kn 1.5, 5 kn 2.6, 7 kn 3.6); raise 7 kn layer as HullSpeedRatio > 0.9 | script |
| `Water/hull_wash_7kn_loop.wav` | loop | 16.0 | 1 | Hull wash / bow wave at about 7 kn boat speed (crossfade between speeds) | BoatSpeed (1 kn ~0.5 m/s, 3 kn 1.5, 5 kn 2.6, 7 kn 3.6); raise 7 kn layer as HullSpeedRatio > 0.9 | script |
| `Water/water_lapping_dock_loop.wav` | loop | 20.0 | 1 | Water lapping pilings and the dock at Rush Creek | BoatSpeed < 0.3 m/s | script |
| `Water/water_lapping_hull_calm_loop.wav` | loop | 20.0 | 1 | Boat at rest or in the slip: small wavelets lapping the hull | BoatSpeed < 0.3 m/s | script |
| `Water/water_lapping_hull_choppy_loop.wav` | loop | 20.0 | 1 | Drifting or hove-to in chop: frequent slaps under the bow | BowSlam or low BoatSpeed in chop | script |
| `Weather/rain_on_roof_light_loop.wav` | loop | 16.0 | 2 | Light rain on a hard surface: layer for rain on deck and cabin top | Rain (light < 0.5, heavy > 0.5) | [Public domain](https://commons.wikimedia.org/wiki/File:Rain_on_a_veranda_and_t.ogg) |
| `Winch/winch_click_01.wav` | one-shot | 0.08 | 1 | Single winch pawl click | TrimRate > 0, small adjustments | script |
| `Winch/winch_click_02.wav` | one-shot | 0.08 | 1 | Single winch pawl click | TrimRate > 0, small adjustments | script |
| `Winch/winch_click_03.wav` | one-shot | 0.08 | 1 | Single winch pawl click | TrimRate > 0, small adjustments | script |
| `Winch/winch_click_04.wav` | one-shot | 0.08 | 1 | Single winch pawl click | TrimRate > 0, small adjustments | script |
| `Winch/winch_ratchet_slow_loop.wav` | loop | 4.0 | 1 | Winch turned slowly with a handle under load | TrimRate > 0 (rate scales pitch/playback) | script |
| `Winch/winch_ratchet_tailing_loop.wav` | loop | 4.0 | 1 | Winch turning while tailing a sheet (pitch/rate up with speed) | TrimRate > 0 (rate scales pitch/playback) | script |
| `Wind/wind_rigging_light_loop.wav` | loop | 20.0 | 1 | Apparent wind 5-10 kn: soft wind with faint shroud hum | ApparentWind (crossfade light < 5 m/s, moderate 5-9, strong > 9; howl layer on gusts) | script |
| `Wind/wind_rigging_moderate_loop.wav` | loop | 20.0 | 1 | Apparent wind 10-18 kn: steady wind, audible shroud and stay whistle | ApparentWind (crossfade light < 5 m/s, moderate 5-9, strong > 9; howl layer on gusts) | script |
| `Wind/wind_rigging_strong_loop.wav` | loop | 20.0 | 1 | Apparent wind 18 kn+: gusty roar with singing rigging | ApparentWind (crossfade light < 5 m/s, moderate 5-9, strong > 9; howl layer on gusts) | script |
