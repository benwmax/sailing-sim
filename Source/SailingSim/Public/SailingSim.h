#pragma once

#include "CoreMinimal.h"

DECLARE_LOG_CATEGORY_EXTERN(LogSailing, Log, All);

/** Writes a line to the game's session log (SessionLog.h), which every build keeps, Shipping too. */
SAILINGSIM_API void SailSessionLogLine(const TCHAR* Level, const FString& Line);

/**
 * LogSailing's Display, Warning and Error lines: to the engine log where the build has one, and to the session log
 * always (a Shipping build compiles UE_LOG out). Log and Verbose lines stay UE_LOG only.
 */
#define SAIL_LOG(Verbosity, Format, ...) \
	do { UE_LOG(LogSailing, Verbosity, Format, ##__VA_ARGS__); SailSessionLogLine(TEXT(#Verbosity), FString::Printf(Format, ##__VA_ARGS__)); } while (0)

namespace Sailing
{
	/** Unreal units are centimeters; the physics works in meters. */
	constexpr double CmPerMeter = 100.0;
}
