#pragma once

#include "CoreMinimal.h"

/** Testers' bug and idea reports (docs/sentry, #410): the report, the last minute of the boat, and how they are packed.
 *  Plain logic so the tests can drive it; SailCrashReports::SendFeedback sends one, the front end's Feedback screen
 *  fills one. */

enum class EFeedbackKind : uint8 { Bug, Idea };

/** One look at the player's boat, twice a second. Map frame (+X north, +Y east), degrees and knots. */
struct FFeedbackSample
{
	double T = 0.0;          // s on the boat's clock
	double North = 0.0, East = 0.0;
	double HeadingDeg = 0.0;
	double SpeedKn = 0.0;
	double HeelDeg = 0.0;    // positive = heeled to port
	double TwaDeg = 0.0;     // + = wind from starboard
	double TwsKn = 0.0;
	double Fps = 0.0;
};

/** The last KeepSeconds of samples, taken every IntervalSeconds of the boat's clock. */
class SAILINGSIM_API FFeedbackRecorder
{
public:
	static constexpr double IntervalSeconds = 0.5;
	static constexpr double KeepSeconds = 60.0;

	/** Keeps the sample if IntervalSeconds have passed since the last kept one (or the clock went back: a restart). */
	void Offer(const FFeedbackSample& Sample);
	const TArray<FFeedbackSample>& GetSamples() const { return Samples; }
	bool IsEmpty() const { return Samples.Num() == 0; }
	const FFeedbackSample& Latest() const { return Samples.Last(); }
	void Reset() { Samples.Reset(); }
	/** One row per sample with a header, oldest first. */
	FString ToCsv() const;

private:
	TArray<FFeedbackSample> Samples;
};

struct SAILINGSIM_API FFeedbackReport
{
	EFeedbackKind Kind = EFeedbackKind::Bug;
	FString Title;
	FString WhatHappened;    // a bug's "what happened", an idea's text
	FString Expected;        // bugs only
	/** Ideas carry where the player is only when asked; bugs always do. */
	bool bAttachPlace = false;
	/** Build stamp, world, boat, weather, quality, GPU...: shown in the message, sent as tags where short. */
	TArray<TPair<FString, FString>> Context;
	FString SamplesCsv;      // FFeedbackRecorder::ToCsv
	FString Repro;           // command-line args that start a session near the same place (SailFeedback::ReproArgs)
	FString LogTail;
	TArray<FString> ShotPaths; // PNGs on disk

	bool CarriesPlace() const { return Kind == EFeedbackKind::Bug || bAttachPlace; }
};

namespace SailFeedback
{
	SAILINGSIM_API const TCHAR* KindId(EFeedbackKind Kind); // "bug", "idea"

	/** Replaces the user's home folder in paths (/Users/<name>, C:\Users\<name>, /home/<name>) with "~". */
	SAILINGSIM_API FString ScrubPaths(const FString& Text);

	/** Game args that start a session at the same spot: world, boat, place and heading, wind. */
	SAILINGSIM_API FString ReproArgs(const FString& WorldId, const FString& BoatId, const FFeedbackSample& At, double WindKn);

	/** The report as one readable message: title, the player's words, then the context lines (place only if it carries it). */
	SAILINGSIM_API FString ComposeMessage(const FFeedbackReport& Report);

	/** The last MaxLines lines of the game's log, scrubbed. */
	SAILINGSIM_API FString LogTail(int32 MaxLines = 200);

	/** Writes the report under Dir/<UTC stamp>-<kind>/ (report.txt, samples.csv, log.txt, shots), scrubbed; returns the
	 *  folder, empty on failure. Testers keep a copy whether or not it was sent. */
	SAILINGSIM_API FString WriteLocal(const FFeedbackReport& Report, const FString& Dir);

	/** Where WriteLocal puts reports in the game: Saved/Feedback. */
	SAILINGSIM_API FString LocalDir();
}
