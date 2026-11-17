# Frigate physics: *Commonwealth* under square sail (the physics sheet and the square rig)

*Commonwealth*, our heavy frigate of 1797 (plan: <https://claude.ai/artifact/8y6hW8vHjjUPJRovJEuxY7>), joins the
vertical slice (Bean, Nov 16: the frigate in the slice at full quality, the date moves). This page covers the first
step of making her a ship to sail: square sails in the game's physics, her physics sheet measured from the model, an
estimated speed polar from the period's logs, and a trial sail of her in the game's own physics, built standalone
without Unreal. Her boat type, reference polar and tacking and wearing by orders come next (by Nov 25); the walking
decks, cameras, crew and orders panel are their own thread.

**In short:** she floats on her lines (2,131 t, 5.86 m canoe body against the sections' 5.87, trimmed level), with a GM
of 0.9 m and a 17 s roll; she holds every point of her course on her own helm with 1 to 7 degrees of weather helm; and
all 35 points of the trial fall within the estimate's tolerance (worst 19.6%). Close-hauled she makes her six points
(5.5 kn at 68 degrees in 12 kn of wind), quartering and running match the logs within 10%, and on a beam or broad
reach she is 12 to 20% faster than the estimate (listed below as the known gap).

## Square sails in the physics (Source/SailingPhysics)

The physics had a main, a jib and a spinnaker. A square sail is new in kind: it hangs from a yard across the mast,
either yardarm can lead, it is full with the wind on its after face and **aback** with it on the fore face (pressed
against the mast, driving her astern: how a square-rigger tacks, heaves to and backs off a lee shore).

- `SquareRig.h`: `FSquareRig` (the rig's coefficients and the crew's pace) and `FSquareSailDef` (each sail: its mast,
  yard pivot, height, widths, area, brace limit, how much squarer than the mast's lowest yard it is braced, how far it
  sets past its yard, its reefs). `SquareSailCoefficients` gives lift and drag against the angle between the wind and
  the yard (0 to 90 degrees): Helmbold's lift slope for an effective aspect ratio of 1.6 from a zero-lift angle set by
  a tenth of belly, up to a CL of 1.15 at 22 degrees, then falling to nothing square to the wind, where the sail is a
  bluff plate of CD 1.3 (Marchaj's square-sail tests). Aback a sail keeps 0.6 of its lift and 0.85 of its drag.
- Yard convention: positive turns the starboard yardarm **forward** (braced up for a wind from starboard), radians in
  `FBoatState::YardAngle`, the same sign as `FBoatControls::Brace`. The model's rig.json uses the opposite sign.
- Controls (`FBoatControls`): `Brace[mast]` (-1..1 of the mast's lowest yard's limit; the upper yards follow, squarer
  by their offset), `SquareSet[sail]` (furled, clewed up, set), `SquareReef[sail]`, and `bMainDown`, `bJibDown`,
  `bStaysailDown` for the spanker, jibs and staysails. The yards swing at 2 degrees a second, a sail sets in a minute
  and clews up in 20 s. `FBoatState::SquareOut` is how far each sail is drawing (what the model draws from).
- Interference: running, the masts abaft a sail blanket it (each takes 0.3 of the wind's speed off it at a dead run); close-hauled, each mast
  ahead heads the wind of the masts aft by 2 degrees.
- **Setting past the yard:** braced up, the cloth sets sharper than its yard: a course's tack is hauled forward and
  down to the chesstree, a topsail's weather leech is hauled forward on its bowline. The working chord turns past the
  yard by 8 degrees for a course, 5 for a topsail, 3 and 2 for the light sails, in proportion to the brace. This is how
  the period's frigates made six points with their yards at 35 to 40 degrees (the model thread's measured limits and
  advice). The trimmer braces that chord, not the yard.
- A staysail group beside the jib (`FBoatConfig::Staysail`, trimmed with the jib sheet).
- `FAutoTrim` braces each mast's yards so its lowest set sail meets its own wind at the stall less the margin (square
  before the wind). Which sails are set is the officer's order, not the trimmer's.
- Two fixes found on the way: the canoe-depth search stopped at 3 m (the frigate floated on a third of her volume; it
  now searches to 1.5 times the deepest section, the same search for every boat under 2 m), and a boom with no
  traveller no longer divides by zero in the trimmer.
- Boats without a square rig are untouched: `scripts/polar.sh --quick` is identical to main's.
- Tests (`SquareRigTests.cpp`): `SailingSim.Physics.SquareSailCoefficients`, `SquareBracing`, `SquareRigForces`
  (before the wind she is driven ahead, braced up she drives and heels to leeward, braced for the other tack the sail
  is aback and drives her astern, clewed up it is windage, set past its yard it drives more), `SquareTrim`.

## Her physics sheet (Tools/shipkit/frigate/physics.py)

`python Tools/shipkit/frigate/physics.py <build dir> [out dir] [--limits limits.json]` reads the model's build
(`rig.json`, `sails.json`, the lines through `loft.py`) and `physics_frigate.json` (the estimates, each with its
source), and writes `physics.json`, `CommonwealthHullData.inl` (41 half sections) and `commonwealth_trial.inl` (her
whole `FBoatConfig`). Run on build b4 with the brace limits measured Nov 17:

| | |
|---|---|
| Displacement | 2,115 m^3 (2,131 t with crew; fresh water) |
| Waterline | 52.1 m long, 13.4 m beam; draft 6.54 m at the heel |
| Wetted area | 837 m^2 |
| Centre of buoyancy | 1.20 m before midships, 2.09 m below the load line |
| KM, GM | 1.17 m above the load line; GM 0.89 m (KG 0.28 m above it) |
| Roll | radius 7.9 m (the rig is half of it), period about 17 s |
| Sails | square 1,901 m^2, headsails 309, staysails 303, spanker 226 |

**Weights** (nothing on the model weighs her; each row reasoned from the part's own size, `physics_frigate.json`):
hull 1,050 t (live oak frames, oak plank, four decks, fastenings, copper), 28 long 24-pounders and 22 carronades
128 t, six months' stores 501 t (water 184 t, provisions 150 t, shot, powder, cables), rig 110 t, fittings 27 t, crew
450 at 100 kg. The ballast makes up her displacement: **270 t**, near the 100 to 200 t of iron and shingle these ships
carried, which says the rest is about right. At first the hull was 1,150 t and she came out crank (GM 0.66 m,
heeling 16 degrees close-hauled under all plain sail in 20 kn); at 1,050 t she heels 8. The ballast is stowed from 2 m
abaft to 18 m before midships to trim her level (the period's way: the ballast was the trim).

**Keel and rudder:** her whole lateral plane less the rudder is one low foil (aspect ratio 0.4: 0.14 geometric,
doubled by the surface over it); the rudder is that plane's flap (`rudder_as_flap`): 16 m^2 of lift, 35 degrees
either way, 12 s hard over to hard over by the wheel and tiller ropes.

**Resistance:** ITTC-57 friction with a form factor of 1.15, and a residuary table for a full ship hull (L/B 4,
prismatic about 0.62), Cr about 0.005 at Fn 0.30 (Taylor's series as the ship texts quote it, raised for her short,
beamy hull). The first estimate (0.0035) left her a fifth fast on a reach.

**Munk moment** 0.8e6 kg: slender-body theory gives about 2.1e6 for her canoe body, ships' measured yaw moments run
about half of it, and her deadwood aft takes more back. At 3.8e6 and 1.5e6 she rounded up into the wind with the
rudder hard over on a reach; at 0.8e6 she holds her course with a few degrees of weather helm, as a good frigate
steered with a few spokes.

## Brace limits

The build's limits held her well off the wind: close-hauled at six points in 12 kn her lower sails were aback and she
made 3.6 kn, and the mizzen topsail (22.5 degrees) was aback even at 110 degrees. The model thread measured each
yard's stop on the slice 12 rig and opened them with catharpins (the fore yard from 33.5 to 37 degrees, the main from
36 to 39.5) and easier topsail parrels (`/mnt/project-files/tall-ship/brace-limits/limits.json`; the final build
writes the same into build.json). With those stops and the sails setting past their yards she makes her six points.

## The estimated polar (Tools/shipkit/frigate/polar_commonwealth.py)

No VPP or tank data exists for these ships, so the table is read from the accounts, at 0.9 of the log-line speeds
(logs read about a tenth high), with their spread (a fifth) as the tolerance:

- Constitution: "13 knots and more" large, 13.5 in her logs, 11 close to the wind in the chase of July 1812.
- Endymion (1797): 14.4 kn large, about 11 close-hauled, the fastest frigate of her day.
- Leda class: 13 large, 10 close-hauled; Aigle class: 10 close-hauled under topgallants, 12 quartering.
- Gardiner (*Frigates of the Napoleonic Wars*): by 1800 a good frigate made 13 kn quartering and 10 or more
  close-hauled in a fresh breeze.
- Hermione (the 2014 replica): 65 to 75% of the wind's speed on a beam reach, 13.3 kn at most.
- A square-rigger sails no closer than about six points (67.5 degrees).

| TWA | 8 kn | 12 | 16 | 20 | 24 |
|---|---|---|---|---|---|
| 67.5 | 3.8 | 5.8 | 7.4 | 8.6 | 8.8 |
| 80 | 4.6 | 7.0 | 8.9 | 10.2 | 10.6 |
| 90 | 5.3 | 7.9 | 10.0 | 11.4 | 11.9 |
| 110 | 5.6 | 8.3 | 10.6 | 12.0 | 12.6 |
| 135 | 5.4 | 8.1 | 10.6 | 12.2 | 13.0 |
| 160 | 4.8 | 7.3 | 9.6 | 11.2 | 12.2 |
| 180 | 4.2 | 6.5 | 8.7 | 10.3 | 11.4 |

## The trial (Tools/shipkit/frigate/trial)

`Tools/shipkit/frigate/trial/trial.sh <dir> [--quick | --point <tws> <twa> [plan]]` builds `Source/SailingPhysics`
with clang and the sheet's `.inl` files and sails her the way the fleet's reference polars are sailed (the polar's lake
chop, the autopilot, ideal trim with the yards braced by `FAutoTrim`), 180 s to settle and 40 s measured, under each
of six sail plans from all plain sail down to close-reefed topsails, keeping the fastest she carries under 14 degrees
of heel (the officers took in the light sails past 10 to 12). `TRIAL_SET="name=value,..."` turns a knob without
rebuilding the sheet. `python polar_commonwealth.py --compare <dir>/trial.json` holds it to the table.

At rest she floats level (pitch 0.01 degrees) on her lines. Against the estimate (her speed, the estimate at the angle
she sailed, her heel, the plan):

| TWA | 8 kn | 12 | 16 | 20 | 24 |
|---|---|---|---|---|---|
| ~68 | 3.9 (-0%) | 5.5 (-5%) | 7.2 (-4%), 5 deg | 8.7 (+1%), 8 deg | 9.9 (+13%), 11 deg |
| ~78 | 4.7 (+4%) | 7.3 (+7%) | 9.4 (+9%) | 11.2 (+12%) | 12.2 (+19%), 14 deg |
| ~89 | 5.8 (+11%) | 8.7 (+12%) | 11.0 (+12%) | 12.5 (+12%) | 13.1 (+12%), reefed |
| ~108 | 6.5 (+17%) | 9.9 (+20%) | 12.1 (+15%), 7 deg | 13.4 (+12%) | 14.3 (+14%), 13 deg |
| ~134 | 5.4 (-0%) | 8.0 (-2%) | 11.0 (+3%) | 12.5 (+3%) | 13.7 (+6%) |
| ~160 | 4.5 (-6%) | 7.0 (-4%) | 9.2 (-4%) | 11.2 (-0%) | 12.3 (+1%) |
| 180 | 3.9 (-7%) | 5.9 (-9%) | 7.8 (-10%) | 9.5 (-8%) | 11.1 (-3%) |

Close-hauled she carries courses, topsails, jibs, staysails and spanker (topgallants in), her lower sails 3 to 5
degrees into the wind on their working chords; her best beat is about 62 to 66 degrees true, 2.1 kn made good in
12 kn of wind and 3.2 in 20.

**Known gaps** for the next step:

- On a beam or broad reach (80 to 110 degrees) she is 12 to 20% faster than the estimate, and faster there than
  quartering, where the period's ships were at their best. The likely cause is the ideal trimmer holding every square
  sail at its best angle on a reach, where a real crew braced all the yards of a mast together and the upper sails
  stood in the lower ones' wash. The knobs: `FSquareRig::AspectRatio` and `Camber`, a reach-dependent interference, or
  the heel cap (she carries all plain sail at 13 degrees in 24 kn).
- In 8 kn her best beat sits at the search's edge with the least canvas (the trial's light-air search, not a speed she
  makes); the reference polar's beat will be read at fixed angles.
- The water is fresh (the physics' 1000 kg/m^3); at sea she would float 2.5% higher.
- The waves' slope push is off for her. Each hull column's push is its immersion averaged over 8 s times the slope,
  and the lagged average leaks a second-order force in quadrature with the slope (about 1/(omega tau) of it, largest
  when she drifts with the waves and meets them slowly). On her long, deep columns, drifting astern after a tack in
  the lake's chop, it pinned her 19 degrees past the wind with a 110 to 360 kN m turning moment, as much as her
  rudder's; with the hull held still it averages to nothing. A 52 m ship does not surf the lake's chop; the push comes
  back for the Gulf's swell with a filter that does not leak (the long boats, the maxi and the J-Class, may want it).
- The tack in 8 to 10 kn falls back and wears slowly (she is near stopped head to wind); the officers wore her in
  light air instead of tacking.

## Tacking, wearing and heaving to by orders (Source/SailingPhysics/Public/ShipHandling.h)

`FShipHandling` gives a square-rigged ship's manoeuvres as her officers ordered them, step by step on the helm,
braces, sheets and the courses' clews (`FBoatControls`), after the trimmer each physics step (the orders panel starts
one; `Update` returns true while it holds the helm, and after it the helmsman steers `CourseAfterDeg`):

- **Tack.** "Helm's a-lee": the wheel over at its pace (12 s hard over), headsheets let fly, spanker amidships; "rise
  tacks and sheets" at 35 degrees (the courses clewed up so they don't hold her back). "Mainsail haul" at 15 degrees:
  the main and mizzen yards round for the new tack, the fore yards held aback to pay her head off; she gathers
  sternway and the helm is shifted for it. "Let go and haul" once she is 12 degrees past the wind with the main yards
  drawing (or 25 past whatever they do): the fore yards round, the courses set, the spanker brailed and her head kept
  15 degrees free until she is back to 60% of her speed, then up to close-hauled. Still on the old side 150 s after the
  helm went over, she has missed stays and wears instead.
- **Wear.** The spanker brailed, the course ordered round at 1.5 degrees a second (never more than 30 ahead of her)
  through the run and up to close-hauled on the new tack, the trimmer squaring and bracing the yards as she turns.
- **Heave to.** The main yards laid square and aback, the fore and mizzen braced up and drawing, the spanker's sheet
  eased, the helm keeping her about five points (60 degrees) off the wind.

`trial.sh <dir> --manoeuvre <tack|wear|heaveto> <tws> [plan]` sails one from close-hauled on the starboard tack after
three minutes settled (every 5 s printed; `TRIAL_SET` takes the settings by name). Under all plain sail in the lake's
chop (the time to "done" is from the order until she is close-hauled again with way on):

| Wind | Tack: head to wind, through, done | after a minute | Wear: done, to leeward | Hove to |
|---|---|---|---|---|
| 8 kn | misses stays, wears (15 min and more) | | 4.8 min, 190 m | 0.8 kn |
| 10 kn | 2.7 min, misses stays, wears: 13.8 min | 4.1 kn | 3.5 min, 150 m | 0.4 kn |
| 12 kn | 1.9 min, 3.2, 7.6 min | 4.0 kn of 4.8 | 2.8 min, 125 m | 0.5 kn |
| 16 kn | 1.2 min, 2.0, 5.1 min | 5.2 of 6.2 | 2.5 min, 180 m | 1.0 kn |
| 20 kn | 0.8 min, 1.3, 4.0 min | 6.4 of 7.6 | 2.5 min, 250 m | 1.6 kn |
| 24 kn | 0.7 min, 0.9, 3.4 min | 7.6 of 8.9 | 2.5 min, 310 m | 1.5 kn |

That is the period's picture: a frigate tacked surely in a working breeze and lost little ground doing it, missed
stays in light air (the officers wore her instead), and wearing cost her a few hundred metres to leeward. Hove to she
forereaches a knot or so, five points off the wind.

Two physics changes came with it. A square rig's windage is now spread over its masts by their canvas (it sat at the
main mast alone), so the centre of windage is near her centre of effort; no fore-and-aft boat changes (the J/22's
quick polar is byte-identical). And her sheet turns the waves' slope push off (`wave_slope: 0`, below).

## Next

Her `EBoatType::Commonwealth` in `Fleet.cpp` from the two generated files (after the J-Class's boat type merges, so
the two don't collide), her reference polar from this table and its tests (the manoeuvres among them), the orders panel's
calls into `FShipHandling`, and her deep-water start spots and Boat screen entry. The Mac runs the tests Nov 25 to 27 through the main sim thread.
