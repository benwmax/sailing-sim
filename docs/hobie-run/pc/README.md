# Hobie 16 deep run: the PC's capsizes (Oct 28 2026)

Telemetry for the Mac's autopilot fix (docs/hobie-run/README.md on hobie-run). Main f91c8660, the uncooked editor build on
Bean's RTX 4090 PC, `scripts/windows/run-game.ps1 -Seconds 25 -ResX 1920 -ResY 1080 -Shot hobie-<run>` (it adds
`-SailingDemo`, `-SailingBench=25`, `-NoCrashReporter`), with:

    -SailingWorld=Lake -SailingStartAt=6400,877,0 -SailingBoat=Hobie16 -SailingLiverySeed=0 -SailingWeather=AfternoonBreeze
    -SailingWind=14 -SailingHour=13 -SailingTWA=170 -SailingHoldTWA=170 -SailingNoHud -SailingTraffic=0 -SailingCapture=Chase

plus, per run:

| Run | Extra args | Max heel | Avg fps | p99 frame | Capsized from |
| --- | --- | --- | --- | --- | --- |
| `hobie-ultra` | `-SailingQuality=Ultra` | 87.6 deg | 66.4 | 21.4 ms | 15.4 s |
| `hobie-ultra-nofalls` | `-SailingQuality=Ultra -SailingCrewFalls=0` | 87.7 deg | 67.1 | 19.7 ms | about 15 s |
| `hobie-high` | `-SailingQuality=High` | 87.7 deg | 68.8 | 19.6 ms | about 15 s |
| `hobie-ultra-2` | `-SailingQuality=Ultra` (repeat) | 87.7 deg | 68.3 | 20.7 ms | about 15 s |

The quality tier, the crew ragdolls and the frame rate don't change it: at about 67 fps the physics is far from its
12-steps-a-frame cap.

What tips her is a gybe. She runs at TWA -165 to -173, 7-9 kn with 2-9 deg of heel, until about 12 s. Then, in a gust
(the true wind 14-18 kn on AfternoonBreeze), the demo autopilot lets her pass dead downwind. The TWA goes from -169.6 to
+177 deg, the heel 20 to 57 to 79 deg within two seconds, and she is capsized from 15.4 s.

The Mac's runs started at the lake's launch spot. These start off the I-30 bridge (`-SailingStartAt=6400,877,0`), in
AfternoonBreeze at 13:00, which is gustier.

The CSVs are `FCaptureTelemetry`'s columns (time_s ... capsized), one row per frame.
