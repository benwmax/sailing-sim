# Sound samples (the sample layer)

Drop a recording here named after a cue and run `scripts/import-audio.sh`, then repackage. The game plays it, looping, in place of
the synthesized voice of the same name, at the level the physics gives that voice (`ASailboatPawn::UpdateSound`). Anything not
here stays synthesized (`USailingSynthWave`), so the set can grow one clip at a time.

| File | What it should be | Level follows |
| --- | --- | --- |
| `Wind.wav` | wind in the ears and the rig, steady, no gusts | apparent wind (hushed in a wind shadow) |
| `GustRumble.wav` | low buffeting of a gust on the ears | gust over the mean |
| `SailFlog.wav` | a sail luffing and flogging | strips luffing x wind |
| `Telltales.wav` | telltale yarn fluttering | streaming telltales x wind |
| `BowWave.wav` | water past the hull under way | boat speed |
| `HullSlap.wav` | wavelets slapping a hull at rest / the bow meeting waves | at rest, or pitching under way |
| `Winch.wav` | a winch clicking while trimming | trimming in |
| `SheetBlock.wav` | a sheet running out through a block | easing |
| `HalyardSlap.wav` | a halyard slapping an aluminium mast | at rest x wind |
| `RainDeck.wav` | rain on deck and sails | rain |
| `RainWater.wav` | rain hissing on water | rain |
| `SquallHiss.wav` | a squall's wind and rain coming across the water | the gust front's distance |
| `Thunder.wav` | rolling thunder (delayed by the strike's distance) | thunder |

Mono 48 kHz WAV, a seamless loop of 10 s or more. Bean's own recordings are best (the J/22 at Rush Creek). Freesound clips must be
CC0 (Creative Commons 0), credited in `CREDITS.md` anyway.

The world's spatialised sources (marina halyards, gulls, outboards, diesels) are synthesized in `USailingWorldSynth`.

Graphics G7: the sample pack in `Inputs/audio/Samples` (48 kHz, CC0 / CC BY / public domain, see `CREDITS.md`) is imported by the
same script to `/Game/Audio/Pack/<Folder>/<name>`. `SailingSound::PackLoops` crossfades its loops by the manifest's game
parameter (wind 3 bands by apparent wind, luff and flog by luff, hull wash 4 bands by speed, lapping at rest / in the slip / in
chop, winch by trim rate, sheet, rain on deck); `PackShots` are one-shots (halyard slaps at rest, the sail filling after a tack,
winch clicks, a sheet easing, dock creaks and fender squeaks in the slip); `USailingWorldSamples` plays the marina's halyards,
gulls (laughing gulls on the coast) and outboards. A `<Cue>.wav` here still wins over the pack for its cue.
