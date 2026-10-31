#pragma once

#include "CoreMinimal.h"

struct FFeedbackReport;

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

	/** Sends a tester's bug or idea as Sentry user feedback, tagged kind:bug or kind:idea, with its samples, log tail and
	 *  shots attached when it carries the place. False when nothing could be sent (no SDK); the caller checks consent. */
	SAILINGSIM_API bool SendFeedback(const FFeedbackReport& Report);
}
