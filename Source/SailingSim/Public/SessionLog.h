#pragma once

#include "CoreMinimal.h"

/**
 * The game's own session log (docs/session-log/): Saved/Logs/session.txt, one line per event with the time since launch,
 * written by our code because a Shipping build has no engine log (the precompiled Shipping engine is NO_LOGGING), so a
 * tester's bug report and crash report still carry what happened. Every SAIL_LOG line (SailingSim.h: Display, Warning
 * and Error on LogSailing) goes here, plus a header (build, engine, platform) and the session line (world, boat, mode,
 * quality, resolution, RHI, GPU). Rotated per launch (session-1.txt ... the last KeepLaunches), capped at MaxBytes per
 * launch. Lines are buffered and written by the log's own thread every FlushSeconds, never on the caller's (a flush to a
 * busy disk took up to 100 ms of the game thread); an Error line is on disk before Write returns, a Warning wakes the
 * writer, and the buffer is written at exit, on a crash and before anything reads the file (Tail, ReportLogPath). Every line goes through SailCrashReports::ScrubPaths and loses e-mail addresses:
 * no user names, paths with them, tokens or DSNs.
 */
namespace SailSessionLog
{
	inline constexpr int32 KeepLaunches = 5;
	inline constexpr int64 MaxBytes = 2 * 1024 * 1024;
	inline constexpr double FlushSeconds = 1.0;

	/** One line: "[+12.345] Warning: Save: could not write ...". Opens the log on first use. Thread-safe. */
	SAILINGSIM_API void Write(const TCHAR* Level, const FString& Line);
	/** Writes what is buffered to the file now, on the calling thread (it may wait on the disk: not per frame). */
	SAILINGSIM_API void Flush();
	/** The log's file (Saved/Logs/session.txt, or the folder a test opened). */
	SAILINGSIM_API FString Path();
	/** The last lines of this launch's log. */
	SAILINGSIM_API FString Tail(int32 MaxLines);
	/** The log a report attaches: the engine's when this build writes one, else this one. */
	SAILINGSIM_API FString ReportLogPath();
	/** Opens the log in Directory (rotating the old ones when bRotate) and returns the folder it had: tests. */
	SAILINGSIM_API FString OpenIn(const FString& Directory, bool bRotate);
	/** E-mail addresses become <email> (paths go through SailCrashReports::ScrubPaths). */
	SAILINGSIM_API FString ScrubLine(const FString& Line);
}
