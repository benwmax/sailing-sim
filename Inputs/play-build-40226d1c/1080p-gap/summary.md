# The 1080p gap between 75ed143f and 40226d1c: it does not hold

**Setup:** friday.ps1's bench as it runs it: Shipping, `-SailingShippingSmoke -SailingWorld=Lake -SailingLaunch=1
-SailingBench=30`, 1920x1080 windowed, Ultra. The builds are `Packaged\Shipping-75ed143f` and
`Packaged\Shipping-40226d1c`. Each was warmed once, then run A/B/A/B back to back. Bean's Saved was held aside and
restored (F6458EAB); nothing else was running.

| run | build | fps | p99 ms | GPU ms | game ms | render ms | RHI ms |
|---|---|---|---|---|---|---|---|
| warm | 75ed143f | 70.0 | 21.3 | 8.53 | 12.84 | 12.96 | 7.34 |
| warm | 40226d1c | 78.8 | 18.2 | 8.51 | 11.12 | 11.80 | 6.79 |
| a1 | 75ed143f | 80.6 | 18.2 | 8.50 | 10.88 | 11.43 | 6.35 |
| b1 | 40226d1c | 84.1 | 17.6 | 8.46 | 10.36 | 11.11 | 6.35 |
| a2 | 75ed143f | 85.5 | 16.6 | 8.45 | 10.11 | 10.98 | 6.35 |
| b2 | 40226d1c | 84.6 | 18.1 | 8.44 | 10.14 | 11.04 | 6.43 |

**40226d1c runs at 84.1 and 84.6 fps, inside 75ed143f's own spread of 80.6 to 85.5.** It is not below it, and the game
thread is the same (10.1-10.4 ms against 10.1-10.9 ms).

These runs are CPU-bound at about 80-90 fps with the GPU at 8.5 ms, and they drift up over the session as the PC warms
its caches: 70 to 85.5 fps on the same build. Today's single readings were each one such run: friday.ps1's 77.3 fps for
40226d1c and the dry run's 89.7 for 75ed143f. **#707 costs nothing measurable here.** I skipped step 2, the traced A/B
on Development packages, as the brief says.

A single friday.ps1 bench number at 1080p is only good to about ±8 fps. Compare 4K numbers (GPU-bound), or several
back-to-back runs, instead.
