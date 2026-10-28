# Wave physics: added resistance by size, and surfing

Physics only (SailingPhysics, the crew helper, tests and tools). Nothing here touches the water's rendering.

## In plain English

The prologue's gale found two holes in how boats meet waves. Both are fixed for every boat.

1. **Waves slowed big boats far too much.** Every boat paid the same price for pitching into waves, scaled from the J/22.
   But a long boat rides over waves that a short one has to climb, so the 100 ft maxi was charged as if she were a
   giant J/22. In the gale's 3.5 m sea she slowed from 11.6 kn to 6.5 upwind and never once got through a tack. Now each
   boat's cost comes from her own length against the waves' length, plus her own coefficient: from her polar where
   the lake's chop loads her, and from ORC's own scaling between yacht sizes where it doesn't. The maxi now beats at
   10.7 kn in that sea and tacks 6 times in 6 (10.2 kn since her boom went up to the deck's height, `docs/prologue/`). The lake boats' polars are where they were.
2. **Boats could not surf.** The water pushed boats straight up and never along. Now a wave's slope pushes the hull
   along it, as real water does. Running on the Gulf swell the J/22 peaks at 7.9 kn instead of 5.6. The maxi running in the
   gale peaks at 25 kn instead of 22, and averages 19.3 kn against 17.8 on flat water. On flat water the push is exactly
   zero, and a boat that isn't riding a wave gets nothing from it on average.

One knock-on fix to the crew: the autopilot now reverses the helm when the boat makes sternway (a wave knocked the maxi
back in a tack and the wheel stayed hard over, steering her the wrong way).

What still isn't right is under [Known gaps](#known-gaps).

## 1. Added resistance in waves

`FBoatConfig::AddedResistanceCoef` x R(lambda/LWL) x rho g 2 m0 B^2 / LWL, summed over the sea's bands
(`FBoatModel::Step`). Four changes:

| | Before | Now | Why |
|---|---|---|---|
| Spectral sum | 4 x each band's variance ((Hs/2)^2) | 2 x (ORC VPP 2023 eq. 6.61, 2 x the integral) | the correct spectral form; every coefficient doubled with it, so this alone moves nothing |
| Speed | linear to 2 m/s, then flat | Froude number^1.5 to Fn 0.265, then flat (multihulls keep growing linearly to their cap) | by Froude number, a 30 m boat at 4 kn is barely moving through her waves; 1.5 is Jinkine & Ferdinande's amplitude law; Fn 0.265 is the J/22's old 2 m/s, so her saturated beat is unchanged |
| Response past the peak | a Lorentzian: a third of the peak left at 2.6 waterlines | Jinkine & Ferdinande's long-wave form (1974; carried into STAwave-2 and ITTC 7.5-04-01-01.2): ~20% at 1.5 x the peak wavelength, 5% at 2 x | a hull rides waves much longer than she is; the Delft yachts' measured curves fall this way (Gerritsma & Keuning) |
| Coefficients | one number (the J/22's) for most boats | per boat, from the best real number for each | see below |

**How each coefficient was set.** The J/22's is unchanged (her ORC polar). For boats the lake's chop loads, the polar
still decides. For boats it doesn't, ORC's added-resistance formula (VPP Documentation 2023, section 6.8, eq. 6.62 with
its length baselines and f(L30)) gives the ratio to the J/22 in ORC's own sea (a 5 s wind sea; `scripts/polar.sh --sea
orc <hs> <tws>` sails it). ORC writes `log` in f(L30) without saying which base, so its ratios are given as a range.

| Boat | Coefficient | From | Added resistance in ORC's 16 kn sea vs the J/22's (ORC's) |
|---|---|---|---|
| J/22 | 2.6 (was 1.3 on the old sum) | her ORC polar (`PolarGate`) | 1.00 |
| Catalina 22 | 2.6 | her polar; ORC agrees | 0.85 (0.79) |
| Catalina 30 | 1.57 | ORC's scaling; her ORC certificate's 16 kn beat improves from -6.1% to -4.9% | 1.30 (1.23 to 1.36) |
| Maxi 100 | 0.47 (0.38 to 0.57 across the log reading) | ORC's scaling (the lake's chop is far shorter than her) | 3.38 (2.78 to 4.12) |
| Sunfish | 3.0 | her polar: the new tail took a little off her 15 kn beat; 3.0 puts it back (+14.9% against +14.5%) | |
| ILCA 7, Lagoon 42 | 2.6 | their polars, unchanged | |
| Hobie 16, Corsair 880 | 18, 6 (9 and 3 on the old sum) | their polars and Portsmouth, unchanged | |

Before these changes the model put the maxi at 10.3 x the J/22 in ORC's sea, and the Catalina 30 at 2.1 x.

## 2. Surfing: the slope's push

Under a wave the water's pressure falls along the surface's slope (rho x the water's own acceleration, -g grad eta at
the surface). Each hull column now feels rho g V (-slope) sideways as well as rho g V up. That is the linear
Froude-Krylov force, filtered by the hull's own sectional areas: waves near her length and longer push her, and chop much
shorter than her cancels along her. Two details keep it first order, so it gives no free energy:

- **V is the column's immersion below her mean waterplane**, the plane fitted through the water along her hull, averaged
  over 8 s, starting from her design immersion after a reset (seeding it with a reset's first step, which can land her
  deep in a crest, shoved her down the wave for seconds). On a long wave she keeps her own trim and immersion; the chop
  slapping her bow and stern doesn't count. With
  the instant immersion instead, the bow lifting clear of short chop rectified the push into a drag that cost the J/22
  12% upwind in 6 kn of wind, in 10 cm chop. That second-order drift is what the calibrated added resistance already
  carries.
- **The 8 s average is longer than the encounter period** of the waves that slope her (the maxi meets the gale's 7 s sea
  every 5 s upwind). From 6 s up the maxi's numbers stop changing. The J/22's mean push is under 1 N beating in 15 kn and
  running in 6.

What the push does:

| Case | Without the push | With it |
|---|---|---|
| Flat water | 0 | exactly 0 (every step) |
| J/22 adrift on a 1.2 m, 9 s swell, no wind: mean push | | about -1 N (it averages out) |
| J/22 running at TWA 150 on the Gulf swell (12 kn): mean, best second | 5.24, 5.62 kn | 5.43, 7.85 kn; faster on a face, slower on a back |
| ILCA running in 20 kn of lake chop: mean, best second | 8.79, 9.10 kn | 8.60, 9.77 kn |
| Maxi running in the gale (TWA 150, two reefs): mean, seconds | 17.89, 14.4 to 22.3 kn | 19.26, 14.6 to 25.2 kn (flat water 17.84) |

Real anchors: Wild Oats XI (30 m) surfed to 33 kn in a 30-35 kn south-easterly and big seas (charterworld, 2014). The
ILCA class's GPS logs reach 21.6 kn running in a 40 kn gust and 22.2 reaching (ilcasailing.org, "Australian speed
rivalry"), so the reference check's ILCA peak at 22 kn now allows 18 kn (was 16); she reaches 16.3.

**Phase-locking.** A displacement boat running in waves near her own speed locks onto them. The lake's chop of her own
length travels at her hull speed. So the ILCA at TWA 150 makes 5.8 kn in anything from 12 to 15 kn of wind: she rides the
chop below that (+17% at 11 kn) and is held behind it above (-11% at 16 kn) until she breaks through near 18 kn. Racers
steer and pump off it; the crew here hold their course. Her reference rows at 140 deg and deeper, already "x0.85, no
surfing" estimates, now allow 25% (her 15 kn run is 18% under).

## 3. The maxi in the gale

The prologue's gale (mistral preset, Hs 3.5 m at 7 s on the Gulf stand-in, 32 kn, two reefs, the scene's limits, the
game's fine turbulence), `scripts/polar.sh --boat maxi --sea gale`:

| | Before | Now | Flat water |
|---|---|---|---|
| Tacks on the wheel (seeds 1-6) | 0 of 6 | 6 of 6 (9.4 to 35 s) | 6 of 6 (10.5 to 24.6 s) |
| Beat, TWA 50 | 6.47 kn (added resistance 14.0 kN) | 10.75 kn (1.6 kN) | 11.64 kn |
| Reach, TWA 100 | 17.52 kn | 19.76 kn | 20.41 kn |
| Run, TWA 150 | 17.89 kn | 19.26 kn | 17.84 kn |

In the whole prologue scene (`SailingSim.Prologue.Gale`) the crew member now answers all seven calls, the tack 37 s from
its call. Beating at 10 kn instead of 6 she meets the sea harder: that test now holds pitch under 15 deg (the steepest
faces of this sea) and the bow under 4 g (a slam goes as the encounter frequency squared, 1.34 x); the centre's 2.5 g stands.

What decided the tacks, coefficient by coefficient (before the helm fix below): added resistance 0.47 with the push, 4
of 6; 0 with the push, 5; 0.47 without the push, 6; neither, 6. So with size-aware added resistance it is the waves' push
that stops her. A face meets her head to wind at 1 to 5 kn and knocks her back, which is real. What wasn't real was the
helm: `FAutopilot` kept the wheel hard over while she made sternway, steering her the wrong way. It now reverses the
helm from 0.3 m/s astern to fully reversed by 0.8. Not sooner: the ILCA stuffing her bow into a wave makes 0.5 kn astern
for an instant, and reversing on that capsized her on the 22 kn reach check. With the reversal she tacks 6 of 6 at 0.47
and 0.57, and 5 of 6 at 0.38 (measured before the reset fix below; at 0.47 still 6 of 6 after it).

On main ff875117 (Oct 28 2026, after the boom's rise, the orbital flow of `docs/surfing/` and the timed tacks of
`docs/gale-tack/`), `scripts/polar.sh --boat maxi --sea gale`: 6 of 6 in the sea (6.7 to 32 s, 15.3 s mean; the slowest
two, seeds 2 and 5, fall to 27% and 13% of her upwind speed) and 6 of 6 on flat water (7.1 to 12.2 s). Beat 10.54 kn in the
sea (added resistance 1.7 kN) against 11.19 flat; reach 17.85 against 19.72; run 19.74 against 17.94.

## Before and after, every boat

Polars (`scripts/polar.sh --boat <b>`; the J/22's is `SailingSim.Physics.PolarGate`, each boat's
`SailingSim.Fleet.Polar.*`). Mean error over all points, worst point, and the mean shift of the upwind points:

| Boat | Mean error before / after | Worst before / after | Upwind shift |
|---|---|---|---|
| J/22 | -0.7 / +0.6% | 6.2 / 8.1% | -0.2% |
| Sunfish | +5.5 / +4.3% | 14.5 / 14.9% | -0.8% |
| ILCA 7 | +3.4 / +3.5% | 12.7 / 18.3% (15 kn run, tolerance 25%) | +0.6% |
| Catalina 22 | -0.9 / -0.0% | 10.0 / 11.2% (tolerance now 15%, the handicap estimate's) | -0.3% |
| Catalina 30 | -2.0 / -1.1% | 5.7 / 5.4% | +0.5% |
| Hobie 16 | -9.1 / -8.8% | 19.7 / 18.1% | -0.8% |
| Corsair 880 | -1.0 / -0.7% | 17.5 / 16.9% | +0.8% |
| Lagoon 42 | +3.9 / +4.1% | 19.5 / 19.2% | +0.0% |
| Maxi 100 | +11.1 / +11.1% | 26.7 / 26.8% | -0.0% |

In the polar's sea (5 km fetch), the polar's crew at fixed settings (`scripts/polar.sh --boat <b> --sea`): beating in
20 kn and running at TWA 150 in 16 kn:

| Boat | Beat 20 kn | Added resistance | Run 16 kn, mean | Best second |
|---|---|---|---|---|
| J/22 | 4.97 -> 4.97 kn | 248 -> 233 N | 7.11 -> 7.08 kn | 7.32 -> 7.73 kn |
| Sunfish | 4.71 -> 5.10 | 70 -> 56 | 6.63 -> 6.19 | 6.82 -> 7.49 |
| ILCA 7 | 4.92 -> 5.38 | 83 -> 58 | 6.77 -> 6.11 | 6.98 -> 7.62 |
| Catalina 22 | 4.44 -> 4.45 | 221 -> 207 | 6.40 -> 6.48 | 6.56 -> 7.01 |
| Catalina 30 | 5.46 -> 5.75 | 331 -> 206 | 7.00 -> 7.00 | 7.13 -> 7.34 |
| Hobie 16 | 9.54 -> 9.21 | 351 -> 368 | 9.03 -> 9.06 | 9.23 -> 9.99 |
| Corsair 880 | 9.45 -> 9.62 | 600 -> 526 | 12.00 -> 12.06 | 12.28 -> 12.55 |
| Lagoon 42 | 6.69 -> 6.69 | 74 -> 73 | 7.80 -> 7.81 | 7.83 -> 7.96 |
| Maxi 100 | 11.88 -> 11.89 | 20 -> 4 | 15.30 -> 15.27 | 15.38 -> 15.56 |

Reference checks (`scripts/reference-checks.sh`): 52 of 52 in range before and after. The ones that moved: J/22
running reefed in 30 kn peak 12.3 -> 13.7 kn; maxi broad reach in 30 kn peak 30.3 -> 30.7 kn; ILCA 22 kn reach peak
15.5 -> 16.3 kn (most heel 50 -> 37 deg), and in 16 gusting 22 15.1 -> 15.5 kn; Portsmouth ratios within 0.03 (Catalina
22 at 12+ kn 1.13 -> 1.16 of its 0.99-1.16). Scenarios (`--scenarios`): the J/22's and the maxi's tacks within 0.4 s.

AI races (`scripts/traffic.sh 98`, 16 steady and 16 shifty): unchanged to the line, because those races sail without a
wave field. In the game, traffic sails on the sea and gets all of this.

## Tests

- `SailingSim.Physics.WaveAddedResistanceScaling`: in ORC's sea the Catalina 22 (0.6-1.05), Catalina 30 (1.1-1.5) and maxi
  (2.5-4.5) against the J/22; on flat water no added resistance and no push, step by step.
- `SailingSim.Prologue.Gale`: the scene's motion bounds in the sea (pitch under 15 deg, bow under 4 g; see above).
- `SailingSim.Physics.TaskStep`: its not-frozen guard is 10 m (she rounds up on a fixed tiller; 20 m was the edge).
- `SailingSim.Physics.GaleTack`: the maxi tacks at least 5 of 6 in the gale's sea and 6 of 6 on flat water, and beats
  5-25% slower in the sea.
- `SailingSim.Physics.Surfing`: the J/22 on the Gulf swell (faster on a face, slower on a back, best second 1.5 kn
  over, mean -2% to +15%), the maxi running in the gale (faster than flat water, past 23 kn), the ILCA in 20 kn chop
  (higher peak), and adrift on the swell the mean push under 5 N.
- `SailingSim.Physics.LaserPlaningDrag` / `LaserPuffHandling`: the ILCA's ceiling 16 -> 18 kn (the class's GPS logs).
  `LaserPlaningDrag` used to sail four angles (100, 110, 120, 130) in a steady 22 kn and ask that she stay up at all of
  them. Swept every 2 deg, main capsized at 3 of the 16 (112, 116, 118: she rounds up on a wave, lifts clear over its
  crest and crash-gybes as she lands); the four just missed them. With this change she goes over at 2 (114, 120), and
  heels less at most of the rest (37 deg at most at 110, where main reached 50). The test now sails all 16 and allows
  main's 3.

The standalone harness is `SeaTrials.h` (`FTrialSea`, `RunInSea`, `RunGaleTack`: the prologue test's gale and helm,
plain C++). `FBoatTelemetry` now carries `CalmResistance`, `WaveResistance` and `WaveSlopeSurge`. The sea modes load the
game's fine turbulence (`Wind.mann`), as the module does; without it the gale's numbers differ from the editor's.

## Known gaps

- **Keels and rudders meet the water as if it were still.** Foils get no orbital flow and no wave inertia. In a beam sea
  the sideways push shoves the hull while the keel holds, and she sculls herself along: the J/22 adrift beam-on to a 1.2 m
  swell, no wind, creeps at 1.3 kn (0.25 to 0.7 before, from the same keel flapping as she rolls). I tried giving the
  hulls and foils the waves' orbital velocity (two more FFTs per ocean cascade). It made the keel scull harder
  (0.85-1.4 kn), because the foils still have no added-mass forces. Next: orbital flow plus Morison inertia on the foils.
  Then the push can surf the hull on the orbits too (near a crest the water runs with her and drag falls).
- **No wave technique.** The crew hold their course: no steering down a face, no pumping. Dinghies lock onto the lake's
  chop downwind (above). The chop in the model may also be more long-crested than a real lake's.
- **Big head seas.** The maxi's mean push beating in the gale is -1.3 kN (the time she spends climbing faces at
  varying speed, plus what the 8 s average still lets through). It adds to her calibrated added resistance.
- **The ILCA on a steady 22 kn reach** goes over at a couple of angles between 110 and 120 deg (main too, at others):
  a broach off a wave, a moment clear of the water and a crash gybe when she lands. The helm's tiller has no rate limit
  while she is airborne; a sailor's would.
- **The maxi's tacks in the gale** were slow here (9 to 46 s against 10 to 25 on flat water). `docs/gale-tack/` has the
  crew time them on a back; on main ff875117 two of six still take 24 and 32 s and drop under 30% of her upwind speed
  (above).
- **The coefficients from ORC are estimates.** ORC's formula is a handicapping fit (its length baselines were tuned so
  light-air races were fair), and its log base is ambiguous: the maxi's 0.47 sits in 0.38-0.57.

## Gate

`scripts/gate.sh --scope boats --no-tests` (the full `scripts/test.sh` ran on the same physics: 190 of 190): pass.

| View (High) | fps | p99 ms | GPU ms | Game thread ms |
|---|---|---|---|---|
| beam8 | 65.0 | 18.0 | 14.6 | 2.61 |
| beat15 | 63.5 | 19.7 | 14.9 | 2.62 |
| marina | 62.1 | 16.9 | 15.3 | 2.71 |
| helm-eye | 60.3 | 21.0 | 15.4 | 2.62 |
| slip | 53.6 | 20.5 | 17.9 | 2.80 |
| crew | 53.2 | 21.7 | 18.1 | 2.88 |

Physics cost per boat (one step with the lake chop and an ocean, standalone, M5 Pro), main -> now: J/22 172.7 -> 170.3
us, ILCA 172.8 -> 169.7, Lagoon 42 221.7 -> 214.5, maxi 171.9 -> 168.9. The second pass over the hull columns and the
waterplane fit cost nothing measurable beside the wave sampling, which was already there.

## Sources

- ORC VPP Documentation 2023, section 6.8 (eq. 6.61-6.69, table 6.2, figure 6.13): https://orc2.orc.org/rules/ORC%20VPP%20Documentation%202023.pdf
- Jinkine, V. and Ferdinande, V. (1974), "A method for predicting the added resistance of fast cargo ships in head waves",
  International Shipbuilding Progress 21 (238); its long-wave form as used in STAwave-2 and ITTC 7.5-04-01-01.2.
- Gerritsma, J. and Keuning, J. A. (1988-89), "Performance of light- and heavy-displacement sailing yachts in waves" and the
  Delft series in waves (Marine Technology); Keuning, Vermeulen and ten Have (2006), "An approximation method for the added
  resistance in waves of a sailing yacht".
- ILCA class, "Australian speed rivalry" (GPS 21.6 and 22.2 kn): https://ilcasailing.org/australian-speed-rivalry/
- Wild Oats XI surfing to 33 kn in 30-35 kn and big seas: https://www.charterworld.com/news/?p=171407
