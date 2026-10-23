# Crew idles that don't loop

The realism audit (`docs/realism-audit-1022/`, "also seen") found the crew's hands-on-knees idle visibly repeating. The
idle is C1b's clip layer (`CrewClips.h`): eight short CMU clips about the stance, picked per sailor from a seed.

## Cause

Each pick played its clip from a random start to the end, at full size and at the same speed for everyone, and only
the clip just played was ruled out next. With eight clips of 5–14 s, a sailor soon made the same motion again.

The new test `SailingSim.Visual.CrewClipVariety` measures it. Three sailors idle side by side for three minutes, and
each one's motion (the clip layer's trunk lean both ways, and the gaze) is cut into 4 s windows. A window repeats when
an earlier one, at least 5 s before it, matches it to within a fifth of the motion's spread (RMS).

| | sailor 0 | sailor 1 | sailor 2 | sync (largest correlation) |
|---|---|---|---|---|
| main | 17% | 10% | 12% | 0.13 |
| this branch | 1% | 2% | 2% | 0.22 |

The sailors were never in step with each other. Each one repeated themselves.

## Fix

In `CrewClipStep` / `Pick`:
- **Pace.** Each sailor has a pace from their seed (0.85–1.1), and each pick has its own on top (0.9–1.1). A segment
  replayed later no longer matches. The product stays at about 1.2 or under: at 1.3 the helm's planted foot slid 3.4 cm
  in `CrewClipLimits` (limit 3; it is 2.1 cm now).
- **Segments.** A pick plays 3–8 s of its clip, not always to the end.
- **Amplitude.** A pick plays at 0.75–1 of the clip's size. Below 1 it stays inside every joint's limit.
- **Crossfades** run 0.8–1.6 s, not always 1 s.
- **History.** The last two clips are avoided, not just the last one.

Weight shifts started by a change of heel keep full size, normal pace and the whole clip, so `CrewClipTack` holds.
`CrewClipLimits`, `CrewClipTack` and the other crew visual tests pass (12 of 12).
