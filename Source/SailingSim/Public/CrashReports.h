#pragma once

#include "CoreMinimal.h"

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
}
