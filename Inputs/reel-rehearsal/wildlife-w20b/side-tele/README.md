# W20b side-tele: the lift on a long lens, fov 13 and 20 (PC, Nov 27 2026)

**Same take as `../side/`** (Windows-95220b32, film mode, 1080p Ultra; take 3's start, raft and 16:30), recorded 58 to
92 s. The camera is the shot-file path (`-SailingCapture=Path`, `shot.json`) in the world frame:
- **Place:** `pos [233,-392,4]` from her start, so map (3233,-942), 4 m up, 450 m due west of the raft.
- **Aim:** yaw 91.5, pitch -1.2. The raft sits about 1.7 deg left of centre and the shoreline at about a third down
  (`framing-still-fov13.webp`, the 2 s check still).
- **Pan:** held to t = 13.5 s (71.5 s), then eased 7 deg left to yaw 84.5 by t = 18.5 s (76.5 s), and held there.
- **Lens:** `tele13/` fov 13 (a pelican about 51 px across the wings at 450 m); `tele20/` fov 20 (about 33 px).

Each folder has four stills, the 720p mp4 (34 s, 30 fps; the 1080p frames are on the PC at
`D:\dev\reel\w20side-95220b32\W20b-side-tele13|20\rec`), `args.txt`, `shot.json` and `camera.json` (its first frame).

**What they show:** the raft in a line, the first birds running (71 s), the flock up (73 to 74 s), and the flock leaving
frame left by about 77 s (fov 13) or 79 s (fov 20). The circling flock is in the top edge of the fov 20 frames.

## Her sail never comes on

In neither take does her sail reach the frame. The pan goes left, away from her:
- she sails up the right side, on bearings of about 103 at 66 s, 96 at 88 s, 95 at 92 s from this camera (from
  `../side/`, 40 deg);
- after the pan the right edge is at 91 (fov 13) or 94.5 (fov 20).

Without the pan (yaw 91.5) the right edge would be at 98 (fov 13) and 101.5 (fov 20), and she'd come on from about 84 s
(13) or 70 s (20).

**A retake that would give the beat:** the same keys, plus a pan back right after the flock has gone, from t = 22 to
30 s (80 to 88 s), to yaw 90 (fov 13: right edge 96.5) or 88 (fov 20: right edge 98). Her sail then comes on at the
right edge for the last few seconds. Not shot; waiting on the reel thread.

## r2 (`tele13-r2/`, `tele20-r2/`): with a pan back right for her sail

The same keys, plus a hold at yaw 84.5 to t = 22 s and an eased pan back right to t = 30 s (80 to 88 s game time): to yaw
90 at fov 13 (right edge 96.5), 88 at fov 20 (right edge 98) (`shot.json`). Same stills plus `4-sail-on`.

- **fov 13:** her sail reaches the right edge at about frame 900 (88 s) and is fully in by 960 (90 s), about 2 s later
  than the 86 s asked for.
- **fov 20:** her sail enters at about frame 840 (86 s) and is in by 870 (87 s).

I checked this from the frames: `camera.json` holds only the first frame's pose.
