# Shore-station stills, Nov 17 2026 (PC)

These are the 30 stations of `Tools/envloop/stations.csv` at main **687f777c**, with the same scene names and camera args as the Nov 16 set in `env-stations-nov16/`. Each file's full args are in `args.csv`.

- **Build:** a Development package of 687f777c (`Packaged/Windows-687f777c`), warmed once.
- **How each was run:** `bench-win.ps1 -Seconds 8 -ResX 1920 -ResY 1080 -Quality Ultra -Shot <scene>`, with the row's args plus `-SailingCapture=Drone`.
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).

**Not quite 1:1 with Nov 16.** The Nov 16 set ran uncooked from the editor (`run-game.ps1`) on main 00b43920, with its bulkhead rows retaken on acef56b0. This set runs the cooked Development package. The cameras, time, weather and resolution are the same.

**Compared with Nov 16** (a contact sheet of all 30, plus some at full size): the framing matches station for station.

- **Bulkhead:** the three bulkhead stills use the acef56b0 rows, as Nov 16's retake did. The boat-lift post is clear of the 15 m view.
- **Glow blob:** the soft white glow on the bank at the waterline is still there in `env-bridge-05m`, `env-bridge-15m` and `env-wooded-15m`.
- **Otherwise:** grass, lawns, trees, houses, docks and water read the same as Nov 16, with nothing new missing or broken. I saw no difference between the cooked and uncooked runs at this size.
