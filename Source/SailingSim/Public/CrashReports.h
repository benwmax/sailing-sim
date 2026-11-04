#pragma once

#include "CoreMinimal.h"

struct FFeedbackReport;
enum class EFeedbackSend : uint8;

/** The game's edge to the Sentry plugin (docs/sentry, #410). Every call is safe without the plugin (platforms other than
 *  Mac and Win64) and without a DSN (the SDK stays off): it then does nothing. */
namespace SailCrashReports
{
	/** The player's answer to Settings > Gameplay > Send crash reports: nothing is sent before a yes. */
	SAILINGSIM_API void SetConsent(bool bSend);

	/** Tags every report with where the player is sailing (the save's ids, docs/save). */
	SAILINGSIM_API void SetPlace(const FString& WorldId, const FString& BoatId);

	/** True when the SDK is running (a build with a DSN). */
	SAILINGSIM_API bool IsEnabled();

	/** Replaces the player's home folder in paths (/Users/<name>, /home/<name>, C:\Users\<name>) with "~". */
	SAILINGSIM_API FString ScrubPaths(const FString& Text);

	/** The log every report carries instead of the raw file (the SDK's own log attachment is off in DefaultEngine.ini):
	 *  the last ScrubbedLogLines lines of the game's log, scrubbed, rewritten off the game thread every
	 *  ScrubbedLogRefreshSeconds once the player has said yes, so a crash uploads it too. In Shipping (no engine log) it is the session log's tail: SessionLog.h. */
	SAILINGSIM_API FString ScrubbedLogPath();
	inline constexpr float ScrubbedLogRefreshSeconds = 15.f;
	inline constexpr int32 ScrubbedLogLines = 400;

	/** Sends a tester's bug or idea as Sentry user feedback, tagged kind:bug or kind:idea, with its samples, log tail and
	 *  shots attached when it carries the place. Saved when nothing could be sent (no SDK, no DSN). With Send crash
	 *  reports off it still goes, on its own over HTTP (SendsOnItsOwn: Sending, its envelope kept in
	 *  SailFeedback::PendingDir until the endpoint takes it); the SDK's consent and cache are left alone. */
	SAILINGSIM_API EFeedbackSend SendFeedback(const FFeedbackReport& Report);

	/** Sends again the reports that went on their own and didn't get through (offline, a server error, rate-limited): once a
	 *  launch, from the game mode. A refused one (4xx but 429) or one a month old is dropped. */
	SAILINGSIM_API void ResendPendingFeedback();

	/** True when a report must skip the SDK (pc/feedback-send): consent is required and not given, so the SDK would cache it
	 *  with everything else the player said no to, and a later yes would send them all. */
	inline bool SendsOnItsOwn(bool bConsentRequired, bool bConsentGiven) { return bConsentRequired && !bConsentGiven; }
}
