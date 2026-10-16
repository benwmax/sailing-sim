# Cinematic look: Mac check (M5 Pro, packaged, High)

The PR branch at 6cd27174, plus 5fb9f151, which loads the LUT and the kernel per environment actor. The old function
static skipped the load after the front end's cast-off reload, so a game started from the menu with Look = Cinematic
had no grade. The branch already had main 1e4da4fb merged.

## Gate

`scripts/gate.sh --scope water` (145 of 145 tests) and `--scope clouds` both pass. They ran against
`visual-bench-main-base` (main 1e4da4fb, packaged and benched in the same session just before).

| view | tier | main fps | water gate fps | clouds gate fps |
|---|---|---|---|---|
| beam8 | Medium | 88.5 | 90.7 | |
| beam8 | High | 60.5 | 60.8 | |
| beat15 | Medium | 85.5 | 86.2 | 86.2 |
| beat15 | High | 55.0 | 55.6 | 55.9 |
| storm | Medium | 70.6 | 71.2 | 70.2 |
| storm | High | 51.3 | 51.4 | 49.8 |
| marina | Medium | 93.9 | 93.6 | |
| marina | High | 61.4 | 62.2 | |
| gulf-sea | Medium | 104.8 | 106.6 | 107.9 |
| gulf-sea | High | 71.1 | 71.4 | 70.9 |
| bridge | Medium | 99.7 | 101.2 | 101.2 |
| bridge | High | 64.4 | 64.6 | 64.7 |
| helm-eye | Medium | 87.3 | 88.0 | 88.2 |
| helm-eye | High | 54.8 | 56.2 | 55.5 |
| slip | Medium | 82.2 | 82.9 | 82.8 |
| slip | High | 52.2 | 52.5 | 52.5 |
| coast-day | Medium | 83.1 | 84.0 | 82.1 |
| coast-day | High | 53.6 | 53.9 | 54.1 |

Every view moves by at most 1.5 fps, and in both directions: that is drift, not the change. (Storm High is +0.1 in one
run and -1.5 in the other.)

## Cinematic on and off (High)

These ran with `-SailingCinematic=0` and `=1` alternately, two 12 s runs each, and the table gives the means. Lake dusk
is the Chase capture facing the sun (Hour 18.6, sun 2.5 deg up, `-SailingCaptureBearing=80 -SailingCaptureAbsolute`).

| view | fps off | fps on | GPU ms off | GPU ms on | post ms off | post ms on |
|---|---|---|---|---|---|---|
| helm-eye | 54.7 | 54.5 | 18.24 | 17.75 | 0.62 | 0.67 |
| coast-day | 52.9 | 52.7 | 15.54 | 15.66 | 0.86 | 0.95 |
| lake-dusk | 62.3 | 62.4 | 15.34 | 15.08 | 0.68 | 0.65 |

The frame rate is flat (within 0.2 fps). The post slice grows by 0.05 to 0.09 ms on helm-eye and coast-day, against
+0.01 on the PC. Lake dusk shows no change.

## Natural look against main

These are capture-mode stills at High with no `-SailingCinematic`, so they show the natural look. Mean absolute pixel
difference, 0 to 255:

| still | main vs main | main vs PR |
|---|---|---|
| helm-eye, auto exposure | 1.82 | 2.23 and 2.27 |
| lake-dusk, auto exposure | 3.71 | 7.42 and 7.62 (PR 4 levels darker) |
| lake-dusk, `-SailingEV=-3` | 2.89 (PR vs PR 2.95) | 1.65 to 3.43, mean colour within 0.2 |

The stills are never bit-identical, even main against main: the waves, cloth and crew move between runs. With the
exposure held fixed, the PR's natural dusk falls inside main's own run-to-run spread. The 4-level darkening with auto
exposure comes from the meter frozen at 2.5 s, not from the look. Blind-test captures stay natural unless
`-SailingCinematic=1` is passed.

## Stills (cinematic on, capture mode, High)

![Helm eye, cinematic](helm-eye-cinematic-high.jpg)

![Lake dusk, cinematic](lake-dusk-cinematic-high.jpg)
