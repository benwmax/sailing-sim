# Shipping smoke on the Mac (Oct 17 2026)

PR #115 (`shipping-guards` 9d5e5a05, with origin/main 1dba6ce3 merged in: docs only), on Bean's Mac (Apple M5 Pro).

- `scripts/build.sh` clean. `scripts/test.sh SailingSim`: 152/152, including `SailingSim.Smoke.ShippingSmokeArgs`.
- `scripts/gate.sh --scope all`: pass. Lowest Medium is storm, 70.3 fps; lowest High is crew, 50.6 fps (gates 60 / 45).
- `scripts/package-mac.sh Shipping`: 105 s, to `Packaged/Mac/SailingSim-Mac-Shipping.app`.

Each world launched through `open -n -a <app> --args -windowed -ResX=1920 -ResY=1080 -SailingShippingSmoke
-SailingWorld=<w> -SailingShot=<shot> -SailingBench=20`, the window visible. Shipping writes no log. The bench.json and
screenshot go to the sandbox, `~/Library/Containers/com.benwmax.SailingSim/Data/Library/Application Support/Epic/SailingSim/Saved/Bench`.

| world | screenshot | measured | fps (Medium) |
|---|---|---|---|
| `-SailingWorld=0` (lake) | `mac-shipping-smoke-lake.jpg` | 20.0 s | 85.2 |
| `-SailingWorld=1` (Galveston Bay) | `mac-shipping-smoke-bay.jpg` | 20.0 s | 79.4 |
| `-SailingWorld=Gulf` | `mac-shipping-smoke-gulf.jpg` | 20.0 s | 91.8 |

Each run measured its full window, wrote bench.json and the screenshot, and quit by itself about 30 s after launch.
There was no crash report (no `Saved/Crashes`, no `.ips` in `~/Library/Logs/DiagnosticReports`). `open` doesn't pass on
the game's exit code, and on this Mac neither kqueue nor the unified log gave it for a process launched through
LaunchServices. So "exits 0" here means it exited cleanly through the bench's own exit path, not a read status code.

**Allowlist.** On the lake with `-SailingQuality=Low -SailingHour=6 -SailingBench=90` added
(`mac-shipping-smoke-ignored.jpg`), it ran on Medium at 15:00 and measured 60.0 s. The quality and hour switches were
ignored, and the bench was clamped to 60 s.

**Crash reports.** The Mac Shipping .app stages no CrashReportClient at all (nothing named `*crash*` in the bundle). The
game's `Saved/Config/CrashReportClient/.../CrashReportClient.ini` reads `DataRouterUrl=` (empty) and
`bAgreeToCrashUpload=false`, so nothing can be uploaded. Reports would stay local.
