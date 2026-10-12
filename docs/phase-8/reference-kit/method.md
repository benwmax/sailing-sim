# Phase 8 method: reference realism pass

Written Oct 12 2026 as pre-work for the sailing-sim thread. Companion files in this folder: `references-boats.md` (J/22, Sunfish, ILCA 7, Catalina 22, Catalina 30), `references-multihulls-environment.md` (Hobie 16, Corsair 880, Lagoon 42, Texas lake and Gulf water, sky, storms, webcams), `calibration-sources.md` (weather stations, polars, ratings, wave and wake physics, tools), `reference-links.csv` (every URL in one list).

**Status of the links.** Nobody has watched the videos yet. YouTube blocked playback from the research environment, so each "shows" note is inferred from the title, channel and event reports. Entries marked [V] had their title and channel confirmed; [S] came from search results only. The first job in Phase 8 is to scrub each clip and grade it (step 1).

## Principles

1. **Physics truth and look truth are different jobs.** Physics gets measured against numbers with a tolerance. Looks get judged side by side and then blind. Don't let a pretty frame hide a wrong number, or a right number excuse an ugly frame.
2. **Every reference carries its conditions.** Wind speed and direction, sun position, sea state, camera and lens. A clip without known wind is mood reference only.
3. **Reproduce, then compare.** A game shot is only compared with a real shot taken under the same conditions and camera.
4. **J/22 on Lake Ray Hubbard is the anchor.** It is the boat and lake Bean actually sails, and Bean confirmed going deep on it first. The other seven boats get a lighter pass, focused on the known gaps.
5. **Wrong habits outrank wrong pixels.** A gap that would teach Bean something false on the water (helm feel, heel, when to reef) ranks above a cosmetic one.

## Step 1: Grade the reference library

For each clip, scrub it and fill in a row in `reference-log.csv` (to create in Phase 8):

| Field | Example |
|---|---|
| id | J22-H-019 (boat, wind band, entry number) |
| url and useful time ranges | 02:10-02:45 upwind chase-boat shot |
| venue type | TX reservoir, shallow bay, open Gulf, other |
| wind | stated or from a regatta report or station data; else inferred from Beaufort cues |
| sea state | flat, chop with height estimate, swell |
| sun | date, local time, rough elevation from shadows |
| camera | onboard helm, onboard bow, chase boat, shore, drone; lens (action cam wide, normal, tele) |
| measurable | heel, speed, tack angle, wake angle, roll period, sail shape |
| grade | A: wind known, steady camera, boat clearly visible. B: one of those missing. C: mood only |

Selection rules:
- Prefer clips with stated wind, or races where a day report gives the wind (the 2024 J/22 Worlds days are ideal).
- For motion measurement, avoid gimbal-stabilised or warped (fisheye, horizon-leveled) footage. An unstabilised action cam on a rigid mount is best.
- For colour, avoid graded, slow-motion or sunset-filtered footage. Use webcams and Bean's own phone photos.
- When wind is not stated, estimate it from the water using the NOAA Beaufort descriptions: scattered whitecaps start at Force 3 (7-10 kn), many whitecaps at Force 4 (11-16 kn). Mark it as estimated.
- Pair Bean's own photos and clips with station wind at the same minute: Mesquite (KHQZ, 5.6 mi from the club) and Rockwall (F46, 8.2 mi) through the Iowa Environmental Mesonet ASOS download.

## Step 2: Build a "reference capture" mode in the game

A debug panel or console command that sets everything needed to reproduce a real shot:
- date, time, latitude and longitude (sun and moon position)
- true wind speed, direction, gust factor; sea-state seed
- boat, sail plan (reef, spinnaker), crew weight and position
- camera preset, with exposure locked (fixed EV100), motion blur and depth of field off for stills

Camera presets to match common reference cameras:

| Preset | Placement | Lens |
|---|---|---|
| Helm eye | 1.0 m above cockpit sole at the tiller, looking forward | 70° horizontal FOV (phone main camera) |
| Action cam stern | stern pulpit or transom mount, looking forward | about 118° horizontal (GoPro wide), with lens distortion on |
| Chase boat | 15 m abeam, 2 m above water | 50° |
| Drone | 30 m up, 45° down, 40 m off | 80° |
| Shore tele | 200 m off, 3 m above water | 15° |

Each capture saves a PNG still (plus EXR if cheap), the camera settings, and a telemetry CSV at frame rate: time, speed through water, speed over ground, heel, pitch, roll rate, rudder angle, sheet positions, true and apparent wind, wave height under the boat. Clips go through the Movie Render Queue at the source clip's frame rate.

## Step 3: Compare

### Physics, measured against numbers

| Check | Reference | Tolerance |
|---|---|---|
| J/22 speed vs wind and angle | ORC one-design certificate (calibration-sources §3.2) and keelindex polar | 5% |
| Catalina 30 speed | keelindex/ORC table | 5% |
| Other six boats | US Sailing Portsmouth numbers by wind band, as lap-time ratios on the same course | 8% on ratio |
| J/22 heel | North Sails: 3-4° in 6-8 kn; crew hiking, flat upwind to about 14 kn | 3° |
| Catalina 30 heel | owner table: 4° at 6 kn, 15° at 10, 17° at 12, 21° at 16, 22° at 20 with one reef | 3° |
| Tacking angle | J/22 about 75-90° between tacks; Hobie 16 about 90-100°; ILCA best TWA 40-46° | 3° |
| Roll period | J/22 about 2 s estimated from ORC righting moment; check with Bean's phone roll-decay test | 15% |
| Wave height and period, Ray Hubbard | fetch-limited tables in calibration-sources §4.1; 15 kn over 8 mi gives about 0.45 m at 2.2-2.6 s | 20% |
| Whitecaps | none below about 7 kn, scattered 7-10, numerous 11-16, everywhere 22+ | by eye |
| Wake | Kelvin half-angle 19.5° for displacement boats; narrower for planing dinghies and cats | 2° |
| Capsize | Sunfish, ILCA, Hobie 16 stay down (and can turtle) until righted; keelboats self-right; Corsair and Lagoon can't be righted by crew | behaviour |
| Top speeds | J/22 about 9 kn on a 20 kn spinnaker reach, record anecdote 16 kn; ILCA about 15 kn GPS in a big gust | ceiling |

Measure heel and angles from video with Tracker (free video analysis), using the horizon and the mast as lines. Frame-step with ffmpeg.

### Looks, judged side by side

Put each matched pair in one image (real left, game right) and score these from 1 (same) to 5 (obviously wrong):
- **Water:** colour for the venue (Ray Hubbard and Galveston Bay are turbid olive-green to tan; Gulf offshore bluer), chop scale and steepness, foam and whitecap coverage, sun glint, cat's paws, reflections.
- **Sky:** haze near the horizon, cloud types, storm darkness (shelf cloud and rain curtain), sun disc and glare, night sky and moon.
- **Sails:** depth, twist, telltales, luffing, wrinkles, leech flutter, translucency against the sun.
- **Boat:** heel posture, crew position, waterline, bow wave, spray, wake.
- **Motion:** camera shake and horizon roll for onboard views; pitching in chop.
- **Sound** (from Bean's recordings): luff flutter, water along the hull, wind noise against speed, winches, halyard slap at the dock.

Also run NVIDIA FLIP on matched stills as a rough difference number. It is only a trend signal, because real and game frames will never align pixel for pixel.

## Step 4: Turn differences into a ranked fix list

Score every gap:

**Priority = Severity (1-5) × Visibility (1-5) × Teaching impact (1-3) ÷ Cost (1-5)**

- Severity: how far off it is (5 = clearly wrong to a sailor).
- Visibility: how often it shows up in a normal session on the home lake.
- Teaching impact: 3 if it would teach a wrong habit or wrong expectation, 1 if purely cosmetic.
- Cost: rough effort to fix.

Work the list top down. After each fix, recapture the same reference scenes, rescore, and save the new frame as a "golden" screenshot so later changes can't quietly undo it.

## Step 5: Blind test

Make 20 stills (10 real, 10 game, matched conditions), shuffled. Bean (and anyone else who sails) marks each real or game and write one line on why. Every "why" for a correctly spotted game frame becomes a fix-list item. Goal: game frames spotted under 70% of the time by the end of Phase 8. Repeat once after fixes.

## Step 6: Bean's own data (best references)

Bean has no lesson media yet, so these start from the next lesson. With the instructor's OK:
- **Phone logger.** Mount the phone rigidly (cockpit bulkhead, not a pocket). Run Sensor Logger or phyphox at 10 Hz or more: GPS, accelerometer, gyroscope, orientation. Note crew, sail plan, start and stop times. This gives real heel, roll period, tacking angle and speed at known wind.
- **Roll-decay test** at the dock: rock the boat sharply once, let it settle, log it. Gives the real roll period and damping.
- **Helm feel.** Tape a phone to the tiller or film the tiller from above for a minute upwind in steady wind. Gives real weather-helm angle for the light weather helm gap.
- **Shot list:** helm view upwind and downwind; boat from the dock at the slip; sky every hour; water close-up; the marina from the end of the dock; 30-second sound clips (luffing, sailing upwind, at the dock).
- **Scans.** J/22 and Rush Creek docks, 150-250 overlapping photos in rings at two heights, overcast light if possible. Process with Apple Object Capture on the Mac or RealityScan. Bean's iPhone is a Pro, so use a LiDAR scan app (for example Polycam or RealityScan's LiDAR mode) for the docks and the photo method for the hull.
- **Colour.** One photo per session that includes something of known colour (white sail, a grey card if Bean has one).

## Step 7: Sailor review

Bean's answers (Oct 12 2026): no lesson photos or video yet; will log GPS and heel on future lessons; instructor probably won't play the sim; go deep on J/22 first; iPhone is a Pro (LiDAR available).

So the instructor review is optional. Instead:
- **Bean replays the same drill on the water and in the sim** within a day or two: tacks, gybes, heave-to, docking at Rush Creek, using the same wind from station data. Bean notes what felt different (helm, heel, how fast the boat stops, how it turns), and each note becomes a fix-list item with Teaching impact 3.
- **Compare the phone logs** from that lesson with the sim telemetry for the same drill: tack duration, speed lost, heel, turning rate.
- If the instructor is willing later, even a 2-minute look at side-by-side stills or the blind test is useful, without needing to play.

## Known gaps and where to start

| Gap from Phases 2-7 | Reference to check against | Target |
|---|---|---|
| Light weather helm | Quantum and North J/22 tuning guides; J/22 Worlds Thursday 16-18 kn onboard and chase; Bean's tiller video | a few degrees of weather helm at 10-15 kn, rising with heel; rounds up if over-pressed |
| Storm sky too light | DFW storm timelapse over a lake; North Texas shelf cloud and microburst; Commons shelf cloud category; NBC DFW Ray Hubbard storm, Sept 3 2023 | ground light falls sharply under a shelf cloud; rain curtain visible; chop builds within minutes |
| Boat surfs too fast in 30 kn gusts | J/22 polar (9.2 kn at 120° in 20 kn); Geronimo J/22 16 kn record; ILCA 15 kn GPS | J/22 bursts of about 9-12 kn on waves, rare peaks near 16 |
| Sunfish self-rights | Sunfish capsize and righting clips (four), Sail Safer turtling clip | lies at about 90°, can turtle; needs the sailor on the daggerboard |
| Hobie 16 fast upwind | Portsmouth numbers per wind band; onboard Midwinters 2024 clip | tacks through about 90-100°; course time ratio vs ILCA per band |
| Sounds not tuned | Bean's recordings; onboard night storm clip | by ear, by Bean |
| Simple docks, buildings, trees | Bean's photos and scans of Rush Creek; drone footage of the lake | silhouettes and materials match photos |
| No moon phases | USNO API, SunCalc or Meeus | phase and position correct for date and place |
