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
	/** {"interval_s", "samples": [{t_s, north_m, east_m, heading_deg, speed_kn, heel_deg, twa_deg, tws_kn, fps}]}, oldest first. */
	FString ToJson() const;
	/** The mean frame rate over the kept samples (0 when empty). */
	double MeanFps() const;

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
	/** Build stamp, world, boat, weather, quality, GPU...: lines in the message. */
	TArray<TPair<FString, FString>> Context;
	/** Short values to filter reports by (#410's bundle: feedback_kind, boat, world, lesson, game_mode, wind_kts,
	 *  quality, input, fps): Sentry tags, and tags.json in the local copy. No personal ids. */
	TMap<FString, FString> Tags;
	FString TelemetryJson;   // FFeedbackRecorder::ToJson
	FString Repro;           // command-line args that start a session near the same place (SailFeedback::ReproArgs)
	FString LogTail;
	TArray<FString> ShotPaths; // JPEGs (or PNGs) on disk

	bool CarriesPlace() const { return Kind == EFeedbackKind::Bug || bAttachPlace; }
};

/** What became of a report after Send (pc/feedback-send): kept here only, handed to the crash reporter, or on its way by
 *  itself (a copy waits in Saved/Feedback/Pending until the endpoint takes it, and goes again at the next launch). */
enum class EFeedbackSend : uint8 { Saved, Sent, Sending };

namespace SailFeedback
{
	SAILINGSIM_API const TCHAR* KindId(EFeedbackKind Kind); // "bug", "idea"
	/** The Feedback screen's answer after Send. It never asks for Send crash reports: a report goes either way. */
	SAILINGSIM_API FString ResultLine(EFeedbackSend Result);
	/** Whether Send tries to send at all: whenever the build has a crash reporter, Send crash reports on or off (a report is
	 *  the player's own deliberate send; the setting is for crashes). */
	SAILINGSIM_API bool SendsReport(bool bCrashReportsOn, bool bReporterRunning);
	/** Where a report sent by itself waits until the endpoint has taken it: Saved/Feedback/Pending/<event id>.envelope. */
	SAILINGSIM_API FString PendingDir();

	/**
	 * pc/feedback-send: the report sent on its own when Send crash reports is off. The SDK can't be used then: without
	 * consent it caches every envelope and sends that whole cache once consent is given, so a report would carry what the
	 * player said no to. Instead the report goes to the project's envelope endpoint by itself (Sentry's envelope format:
	 * a header line, then one feedback item and an item per attachment, each a JSON header line and its bytes).
	 */
	struct FSentryDsn
	{
		FString Scheme, Host, PublicKey, ProjectId;   // scheme://key@host/project
		/** False when the text isn't a DSN (no key, host or project). */
		SAILINGSIM_API bool Parse(const FString& Dsn);
		SAILINGSIM_API FString EnvelopeUrl() const;   // scheme://host/api/<project>/envelope/
		SAILINGSIM_API FString AuthHeader() const;    // X-Sentry-Auth's value
	};
	struct FEnvelopeAttachment { FString Name, ContentType; TArray<uint8> Bytes; };
	/** The envelope for one report: Message (ComposeMessage) as user feedback with Tags, Release and Environment, and the
	 *  attachments; TimestampUnix the send time, EventId 32 lower-case hex digits. */
	SAILINGSIM_API TArray<uint8> FeedbackEnvelope(const FString& EventId, double TimestampUnix, const FString& Message, const TMap<FString, FString>& Tags,
		const FString& Release, const FString& Environment, const TArray<FEnvelopeAttachment>& Attachments);

	/** Game args that start a session at the same spot: world, boat, place and heading, wind. */
	SAILINGSIM_API FString ReproArgs(const FString& WorldId, const FString& BoatId, const FFeedbackSample& At, double WindKn);

	/** The title a report goes out under: the player's own, else the first line of what they wrote (cut at about 80
	 *  characters, on a word when there is one), else "Bug report <local time>" ("Idea <local time>" for an idea).
	 *  LocalNow is the player's local time on purpose (the title is for them); WriteLocal's folder stamp stays UTC. */
	SAILINGSIM_API FString DefaultTitle(const FFeedbackReport& Report, const FDateTime& LocalNow);

	/** The report as one readable message: title, the player's words, then the context lines (place only if it carries it). */
	SAILINGSIM_API FString ComposeMessage(const FFeedbackReport& Report);

	/** The last MaxLines lines of the game's log, scrubbed. */
	SAILINGSIM_API FString LogTail(int32 MaxLines = 200);

	/** Writes the report under Dir/<UTC stamp>-<kind>/ (report.txt, tags.json, telemetry.json, log.txt, shots), scrubbed; returns the
	 *  folder, empty on failure. Testers keep a copy whether or not it was sent. */
	SAILINGSIM_API FString WriteLocal(const FFeedbackReport& Report, const FString& Dir);

	/** Where WriteLocal puts reports in the game: Saved/Feedback. */
	SAILINGSIM_API FString LocalDir();

	/** Re-encodes a PNG shot as a JPEG under MaxBytes (quality stepped down, then halved in size); false on failure. */
	SAILINGSIM_API bool ShotToJpeg(const FString& PngPath, const FString& JpegPath, int64 MaxBytes = 8 * 1024 * 1024);
}
