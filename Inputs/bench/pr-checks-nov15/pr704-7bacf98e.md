# PR #704 (cook /Game/Materials and /Game/Audio), head 7bacf98e, on the PC

7bacf98e is main 6f44708f plus `Config/DefaultGame.ini` only (two `DirectoriesToAlwaysCook` lines).

**Build.** I rebuilt anyway, because the editor binaries were last built on #703: Succeeded, 0 errors, 0 warnings in our
Source.

**Package `Packaged\Windows-7bacf98e-704`:** 4 min.

**What got cooked.** The cook writes to the zen project store (`Saved\Cooked\Windows\ue.projectstore`), not loose files,
so there was no per-file listing to search. These show what was added:
- **The game's own load.** Its log has no SkipPackage for `/Game/Materials/M_BowWave` or any `/Game/Audio/Pack` sound.
  Packages da3e74b0 to 6f44708f each logged M_BowWave and 45 pack sounds as skipped.
- **The pack.** It now loads: `LogSailing: Display: Sound: sample pack, 17 loops and 23 one-shots`. 6f44708f's package
  logs no such line.
- **The container.** `SailingSim-Windows.ucas` grows by 5.5 MB (4,059,659,408 to 4,065,425,808 bytes) and the `.utoc` by
  11.5 KB. The pak itself is the same.

**Size.** Content grows from 3,999 to 4,005 MB, about +6 MB. The whole folder reads 43 MB smaller, but only because the
old package's `Saved` holds 49 MB of earlier bench output, against 12 MB here.

**What is still skipped (15).** These are all absent from git; cooking can't add them:
- the 13 optional `/Game/Audio/Samples/S_*`, never imported on this PC;
- the 2 Catalina tiller extensions.

**Launch.** One run: Ultra, lake, 15 kn reach, camera low abeam at the bow, 15 s. Saved was held aside and restored
(F6458EAB). In `pr704-7bacf98e-bow.png` the autopilot had luffed her into the no-go zone at 4.6 kn (wind 18 gusting 20),
so the bow throws no real wave and the curl is not visible in this frame. M_BowWave is loaded (no skip). Seeing the curl
needs a run held on a reach at speed, for example a broad reach in 15-20 kn.
