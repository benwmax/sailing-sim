#pragma once

#include "SailingPhysicsApi.h"
#include "PolarReference.h"

namespace Sailing
{
	struct FTackResult
	{
		double TackSeconds = -1.0;     // from putting the helm over until close-hauled on the new tack (within 5 degrees)
		double SpeedBeforeKnots = 0.0;
		double MinSpeedKnots = 0.0;
		double SpeedAfter10sKnots = 0.0;
		bool bCompleted = false;
	};

	/** Sails close-hauled on starboard, then tacks with the autopilot and auto-trim (a competent crew). */
	SAILINGPHYSICS_API FTackResult RunTack(double TrueWindKnots, double CloseHauledTWADeg = 42.0, double TackTiller = 0.8);

	struct FIronsResult
	{
		double FinalTWADeg = 0.0;
		double FinalForwardSpeedKnots = 0.0;
		double MaxForwardSpeedKnots = 0.0;
		bool bInIronsAtEnd = false;
	};

	/** Starts head to wind with no way on, sheets eased, tiller centered, and watches for Seconds. */
	SAILINGPHYSICS_API FIronsResult RunIrons(double TrueWindKnots, double Seconds, double TillerInput = 0.0);
}
