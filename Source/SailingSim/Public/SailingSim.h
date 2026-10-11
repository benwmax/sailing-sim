#pragma once

#include "CoreMinimal.h"

DECLARE_LOG_CATEGORY_EXTERN(LogSailing, Log, All);

namespace Sailing
{
	/** Unreal units are centimeters; the physics works in meters. */
	constexpr double CmPerMeter = 100.0;
}
