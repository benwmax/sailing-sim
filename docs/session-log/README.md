# The session log

The game's own log, written by our code into `Saved/Logs/session.txt` (on the Mac, inside the sandbox container's
`Saved/Logs`; on Windows, `%LOCALAPPDATA%\SailingSim\Saved\Logs`). We need it because a Shipping build has no engine log.
`bUseLoggingInShipping` needs a unique build environment, which the installed engine refuses, and its precompiled Shipping
Core is `NO_LOGGING`. Without our own log, a tester's bug report (`SailFeedback::LogTail`) and crash report (the scrubbed
log attachment) would carry nothing.

## What goes in

- **The header:** the game, the UTC start time, the build stamp (`Content/BuildStamp/version.txt`, or `dev`), the build
  configuration, the engine version, the platform and the OS version.
- **Every `SAIL_LOG` line** (`SailingSim.h`): LogSailing's Display, Warning and Error lines. The macro writes the engine
  log where the build has one, and the session log always. Log and Verbose lines stay `UE_LOG` only.
- **At each map load, `Session:`** the world, launch spot, boat, mode (and scene), weather preset, hour and seed, Easy or
  Realistic, Career or Free Sail, the quality tier, the resolution and window mode, the RHI and the GPU.
- **Events:**
  - `Drill:` starts and finishes, with the outcome, time, contacts and infractions;
  - `Career:` medals, lesson quizzes, checkride quizzes and certificates;
  - the scenes (first job, prologue);
  - `Conditions:` kept or put back;
  - `Save:` loads, migrations and refusals;
  - the world's loads (lake, marina, trees, streaming).

One line per event, `[+seconds since launch] Level: text` (no level shown for Display), flushed as it's written.

## Rules

- Every line goes through `SailCrashReports::ScrubPaths` (a home folder becomes `~`) and loses e-mail addresses
  (`SailSessionLog::ScrubLine`). No player names, tokens or DSNs are ever written.
- Each launch rotates the log: `session.txt` becomes `session-1.txt`, and the last `KeepLaunches` (5) are kept.
- A launch's log stops at `MaxBytes` (2 MB) with a note.
- Reports read `SailSessionLog::ReportLogPath()`: the engine log where it exists (editor, Development), else this log.

`SailingSim.Feedback.SessionLog` checks the lines, the tail, the scrub, the rotation and the cap.
