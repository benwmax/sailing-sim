# Steering to the waves

Gap 3 from the Oct 28 list. The autopilot, the Easy helm and the AI held a course through a sea: nobody bore away down a
face to surf or headed up on a back, and nobody pumped.

## What the helm does now (`FAutopilot::bWaveSteering`, `AutoTrim.h/.cpp`)

**The signal.** In a sea, the helm reads the slope the hull feels along her bow: `FBoatTelemetry::WaveSlopeSurge` over
her weight, the waves' push forward down a face and back on a back. It is low-passed over 0.25 s and taken against its
own 20 s mean, so a steady push can't walk her course. The sea fades it in from Hs 0.3 m to full by 0.6 m.

**The swing.** The helm bears away while the slope pushes her downhill and heads up while she climbs, by `WaveSteerDeg`
times the slope over 0.03, at most `WaveSteerDeg`, on |TWA|. That rides a following sea's face for as long as it carries
her and heads up on its back for apparent wind. The run guard still caps how deep she goes.

**Where it is off:**
- the calibration sea and flat water (no slope), so every polar is byte-identical;
- upwind (it starts at 70 deg TWA);
- in a tack;
- by default: the polars, scenarios and sea trials sail a course.

**Who uses it:**
- **the AI's helm** (`FTrafficSim`);
- **Easy mode's helm** (`FEasyHelm`): with the player's tiller let go off the wind, half the autopilot's gain on the swing,
  as its bear-away guard nudges;
- the sea trials, as `FTrialSeaSpec::bWaveHelm` (`RunInSea`, `RunGaleTackDetail`).

## Per class (`FAutopilot::WaveSteerDegFor`), from what it gained

Measured with the wave helm off and on: three seeds each, 240 s after 30 s settling. The J/22 and Catalina 30 sail the
2 m, 6.5 s, 20 kn sea of `polar.sh --sea surf`; the ILCA and Hobie a 1.2 m, 5 s, 16 kn sea; the maxi the gale.

| Class | Swing | Why |
|---|---|---|
| Dinghy (the ILCA, the Sunfish) | 10 deg | surfs on every face she can catch |
| Multihull (Hobie 16, Corsair, Lagoon) | 2 deg | at 10 the Hobie, borne away down a face, buried her bows and went over in all three runs at 150 deg |
| Light keelboat under 7 m waterline (J/22, Catalina 22) | 6 deg, reaching | running under the kite at 6 deg it cost the J/22 2%, so the swing fades from 120 to 150 deg |
| Heavy keelboat (Catalina 30), the maxi | none | at 2 deg it cost the Catalina 30 1.6-1.9% and the maxi 2.2% reaching: they carry their way through |

**First version: upwind too.** It headed up into a face and bore away down its back at half the swing, and it cost every
boat 1-3.5% (J/22 -3.5%, Catalina 30 -1.7%, ILCA -1.4%, maxi -1.3%). The slope she feels comes too late to meet a face,
so it is off upwind. Without the 20 s mean, the Catalina 30's run walked from TWA 139 to 128.

## Before and after (mean speed, three seeds; off -> on)

| Boat, sea | Beat | Reach | Run |
|---|---|---|---|
| J/22, 2 m, 20 kn | 5.17 -> 5.17 (TWA 45) | 8.24 -> 8.43, **+2.3%** (TWA 100) | 9.48 -> 9.48 (TWA 150, kite) |
| Catalina 30, 2 m, 20 kn | 5.32 -> 5.32 | 7.30 -> 7.30 (TWA 120) | 7.12 -> 7.12 |
| ILCA, 1.2 m, 16 kn | 5.59 -> 5.59 | 8.06 -> 9.30, **+15.4%** (TWA 110; surfing 83 -> 99% of the time) | 7.11 -> 7.42, **+4.4%** |
| Hobie 16, 1.2 m, 16 kn | 9.77 -> 9.77 (TWA 50) | capsizes either way (TWA 110) | 10.80 -> 10.97, **+1.5%**, upright |
| Maxi, the gale | 10.25 -> 10.25 | 22.30 -> 22.30 | 19.36 -> 19.36 |

The ILCA's most tilt rises from 9-10 to 11-14 deg; nothing capsizes that didn't. The Hobie at TWA 110 in that sea goes
over in all three runs with or without the wave helm: a case of its own.

## The maxi's three slow gale tacks

They are not cleared. Seeds 14, 29 and 43 are 23.7 s at 38%, 21.5 s at 25% and 31.6 s at 35%, with or without; over 24
seeds the median is 12.8 s and p90 18.3 s, 23 keeping 40%, either way. The wave helm is off upwind and in a tack, and
those tacks are decided by the face that meets her head to wind (docs/maxi-tack-timing/, docs/foil-lag/), not by the
course she sails into it.

## Unchanged (byte-identical to main 658fb5dc)

- `scripts/polar.sh`, `--scenarios`, `--sea`, `--boat maxi --sea gale`, `--easy`;
- the ILCA's, Hobie's, Catalina's, Sunfish's, Corsair's and Lagoon's polars (`--boat`);
- `scripts/reference-checks.sh --quick`;
- the AI races: they sail without a wave field (`traffic.sh`).

## Not done

- **Pumping.** Racing Rule 42.3(c) allows one pump of the sheet per wave to start surfing; `FAutoTrim` doesn't pump.
- **A look at the sea ahead.** The waves are exactly predictable (`FWaveField::Height` at a later time, docs/maxi-tack-timing/),
  so a helm could pick its face before it arrives. Here it answers the slope under her.

## Test

`SailingSim.Physics.WaveSteering` checks:
- the ILCA reaching in the 1.2 m sea over three seeds, over 5% faster with the wave helm;
- the Hobie 16 running upright with it;
- the Catalina 30 and the maxi with no swing;
- the same run, step for step, in the calibration sea and on flat water.
