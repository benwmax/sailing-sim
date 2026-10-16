# Crew on the rail facing inboard: the Mac gate (PR #86, merged with main ecdd13d2)

- `scripts/build.sh` ok; `scripts/test.sh SailingSim.Visual` 31/31 (the crew tests live there; there is no `SailingSim.Crew`).
- `scripts/gate.sh --scope crew`: 147/147 tests, pass.

| view | tier | fps | p99 ms |
|---|---|---|---|
| beat15 | Medium / High | 86.0 / 56.0 | 12.7 / 20.2 |
| crew | Medium / High | 72.3 / 51.8 | 14.7 / 21.8 |
| helm-eye | Medium / High | 87.6 / 55.9 | 12.4 / 20.6 |
| slip | Medium / High | 82.3 / 52.2 | 12.9 / 20.1 |
| coast-day | Medium / High | 84.1 / 54.2 | 12.3 / 20.4 |

A/B against main, run in the same session (crew and beat15, Medium / High): main 71.7 / 51.5 and 86.2 / 55.8, this branch
72.3 / 52.1 and 86.1 / 55.9. Nothing moved by more than 0.6 fps.

## Stills (High, `scenes.csv`, `scripts/capture-scenes.sh`)

- `r11-bay-storm.jpg`: round 11's tell, recaptured. No legs over the side now.
- `beat12-{stbd,port}-{helm,chase}.jpg`: a 12 kn beat on both tacks. In the port chase the crew sit on the near rail,
  facing inboard with their knees over the well. The helm-eye capture looks forward, so it doesn't show the crew.
- The bow and trimmer overlapped at the shoulders when they sat 0.36 m apart (`beat12-port-chase-trimmer-unmoved.jpg`).
  The trimmer is now 0.1 m further aft (`CrewPlacement`, keelboats only, so 0.46 m apart). They still just touch in the
  port chase. Another 0.05 to 0.1 m would clear them, but the helm is then 0.45 m behind.
