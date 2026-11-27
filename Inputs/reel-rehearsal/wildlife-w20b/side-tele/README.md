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

## r3 and r3b (`tele13-r3/`): the set-up moved to open water; the lift is missed

**r3 (not pushed):** the whole set-up moved 500 m north and 3 km west (her start 3500,-3550; raft 3733,-3492; camera
3733,-3942, 1.5 m, pitch +1, fov 13), where the RayHubbard bake has 4.6 to 5.6 km of open water east of the camera. The
framing worked, but she sails slower there (3.1-3.4 kn, wind about 185 against 168), so she came within 80 m of the
raft only at about 92 s, the end of the window, and her sail stayed outside the right edge.

**r3b (this folder):** her start kept; raft and camera moved to (3675,-3461) and (3675,-3911) (shot pos `[175,-361,1.5]`)
to bring the flush to about 66 s, with the left pan moved to 67-72 s and the pan back right to 75-82 s (`shot.json`).
`framing-still.webp` was checked first: the raft line left of centre on the lower third, a thin hazy shore 4.8 km
behind.

- **The lift is missed:** at frame 0 (58 s) the raft line is already gone. The log's first flush is in its 7th 10 s
  sample, but she came within 80 m earlier than my estimate from r3's telemetry, so the flush came just before the
  recording.
- **Her sail comes on at the right edge** from about frame 720 (82 s) to the end (`4-sail-on`).
- Not retaken, as asked. Another pass needs the window starting earlier (warm-up about 48 s) or the raft about 20 m
  further along her track.
