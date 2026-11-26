# W20b "pelicans lift off": scouting so far (PC, Nov 26 2026). No final take yet

**Package and setup:**
- Package `Packaged\Windows-a3f81854`. No code changes.
- The game's default date, Nov 26 2026, which is inside the white pelicans' Oct-Apr window. The lake table weights
  November at 1.0, with typical flocks of 24 and a flush range of 80 m.
- Every run: 16:30, AfternoonBreeze at 6 kn, crew and traffic off, `-SailingWildlifeScale=1.5`.

## What I've learned

1. **The log names only the single nearest bird.**
   - Parked 90 s runs at 5 lake starts (off Rush Creek, the dam, 3 km, 4.5 km, off Chandlers) logged 1,450-1,750 birds,
     350-620 of them resting.
   - The nearest bird was always a gull, tern, cormorant or osprey, never a pelican, so the log can't find a raft.
2. **The first fill is laid relative to the start.** The first lines at different starts repeat the same pattern
   (cormorants about 95-110 m to the north-north-east).
3. **From the air (`scout/`), with `-SailingDebugBirds=4` from 350 m up, rafts show.**
   - At the 3 km start (`trial-overhead-heading320.webp`, the boat heading 320, looking ahead):
     - a raft of large grey birds to the upper left;
     - two white gull flocks in the middle;
     - lines of dark cormorants and a cluster of large white birds, likely the pelicans, to the upper right, about
       330 m to her right and 190 m ahead. That's roughly 380 m to the north-north-east.
   - Off Rush Creek (`w20s2-offrush-y180.webp`) there are grey rafts near the point.
4. **The tripod rig works** (`trial-tripod.webp`): `-SailingCapture=Tripod "-SailingTripod=380,1.5,25"
   -SailingCaptureBearing=-8`. That's a low, long-lens view with the J/22 about 380 m off, a line of pale, pelican-like
   birds low over the water across the frame and a flock overhead. Nothing flushed: she didn't pass within range of a
   raft.

## Next

- From the 3 km start, steer her through the white cluster to the north-north-east (heading about 20, a dead run in the
  southerly, so use the demo at TWA about 160), with the tripod placed to frame the raft at 150-250 m.
- Check each pass's flush count and species in the log, then record about 20 s.
- **Fallback:** the cormorant lines in the same view. Frame wider, since their flush range is 50 m.

## Passes A and B (evening, Nov 26): still no flush

**Setup:** from the 3 km start she sails at heading 20 (demo TWA 160) toward the rafts seen ahead, under the scout's
seeded conditions (16:30, 6 kn, `-SailingWildlifeScale=1.5`). At 6 kn she makes about 1.3 m/s.

**Pass A** (260 s, chase and from 160 m up): **0 flushes.** At 260 s a dark raft (cormorants by the look) is about
100-150 m ahead of her (`scout/passA-end-260s.webp`).

**Pass B1** (420 s from 160 m up): **still 0 flushes.**
- At 420 s a raft is again about 150 m ahead (`scout/passB1-end-420s.webp`), after she's covered about 550 m.
- The rafts ahead keep their distance as she sails. My guess is the flocks are kept round the camera (spawned and retired
  to hold the expected count in the bands), so there's always a raft "ahead" but she never reaches one.

**Not filmed:** the B2 take was set to time itself from B1's first flush. There wasn't one, and the script stopped there
(a parse error on the missing flush, also mine).

## What would get the take

- A raft that stays put while she closes on it. That means finding a resting flock that's fixed in place (a roost or
  point habitat) rather than one the bands keep re-spawning.
- Or an approach fast enough to reach it before it's retired, such as more wind or a powerboat.
- The wildlife thread knows which; it may need a debug aid that places a raft, which would be a code change, so not mine
  to make.
