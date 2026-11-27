# W20b-side: the pelicans lifting, seen from her west beam (PC, Nov 27 2026)

**Package:** `Windows-95220b32`, film mode (rec.ps1), 1080p Ultra, crew and traffic off. Take 3's conditions exactly
(`../take/`): her start `"-SailingStartAt=3000,-550,20"`, demo at TWA 160, 10 kn AfternoonBreeze, 16:30, the raft
`"-SailingBirdRaft=american_white_pelican,3233,-492,24"`, recording 58 to 90 s of game time (`args.txt`).

**Camera:** on her west beam with the low sun behind it (sun azimuth 238, elevation 8 deg), so the birds show their lit
side. `"-SailingCamWorld=233,-392,4,85,0"` fixes it at map (3233,-942), 450 m due west of the raft, 4 m up, looking
east-north-east (85 deg), with the tripod's 40 deg lens. The 2 s check still put it there (`camera.json`: 3233.00,
-942.00, yaw 85). A pelican is about 16 px.

**Files:**
- `W20b-side-1-rafted.webp` (frame 240, 66 s): the raft in a white line just right of centre, her sail coming in on the
  right;
- `W20b-side-2-first-runner.webp` (frame 400, 71 s): the first birds running and opening their wings;
- `W20b-side-3-flock-airborne.webp` (frame 520, 75 s): the flock low over the water heading north (left), wings out;
- `W20b-side-4-boat-passing.webp` (frame 900, 88 s): her sail past the empty water where they sat;
- `W20b-side-720p.mp4` (32 s, 30 fps; the 1080p frames are on the PC at
  `D:\dev\reel\w20side-95220b32\W20b-side-fixed\rec`);
- `args.txt` (the exact command line).

**Notes:**
- **The first attempt panned with the boat** (film mode's tripod, `-SailingTripod=456,4,40 -SailingCaptureBearing=-79`).
  That kept her centred and the raft at the frame's left edge, about 15 deg off her, and the flock flew out of frame within
  4 s. This take fixes the camera on the raft instead.
- **Land:** the lake's east shore, its houses and trees, stands behind the whole scene, about 1 km past the raft. No sun
  in frame. So the coordinator's earlier-hour east-side fallback wasn't used.
- **She stays small and right of the raft:** she is about 115 m south of it when it flushes (the flush range is 80 m).
- **In flight the wings turn tan and smear a little (TSR):** see `../aa-test/`.
