# R08b logbook on main 8ae5a0b1 (#835: logbook local time), PC, Nov 26 2026

**Package:** new Development package `Packaged\Windows-8ae5a0b1`. MSVC succeeded, 0 project warnings.

**The seeded throwaway logbook:**
- **Problem:** R08b's four seeded sails were named by UTC (`2026-11-07 1815 ...`), the name a pre-#835 build gives a file.
  #835 names a sail by the world's local clock, and the list reads the name as local time.
- **New seed:** `seed\logbook-local` (also `../saturday-script/test-logbook-local/`).
  - The same four files with the same contents.
  - Each is named the way #835's `FLogbook::LocalStamp` names a file: the first entry's Unix time plus the lake's UTC
    offset (-6, CST in November).
  - The names are 12:15, 14:30, 13:40 and 11:05. They match each file's own `clock` field.
- **The old UTC-named seed is kept.** Older saves keep their UTC names, as #835 says.
- **The script change:** `reel-saturday.ps1`'s R08b `cleanlog` step copies `seed\logbook-local` instead of
  `seed\logbook-clean`.

**Check:** `reel-saturday.ps1 -Package Windows-8ae5a0b1 -Only R08b-checkride -Res 1080p`, 960 of 960 frames. The still is
the last frame, the logbook.

**What the logbook shows:**
- **Sails in the book:**
  - 26 Nov 2026, 14:00 (the checkride just sailed);
  - 21 Nov, 11:05;
  - 16 Nov, 13:40;
  - 12 Nov, 14:30;
  - 7 Nov, 12:15.
- **All in local time.** The checkride's own entries read 14:00, the same as its name. Before, it would have listed as
  20:00.
- **Totals:** 5 sails, 29.9 miles, 8.0 hours, 6 medals, 1 certificate.

Bean's Saved was held aside and restored (7B5CA7BE). The package's own Logbook folder was moved aside for the take; the
seeded book used is kept at `D:\dev\reel\saturday-Windows-8ae5a0b1\R08b-checkride-logbook`.
