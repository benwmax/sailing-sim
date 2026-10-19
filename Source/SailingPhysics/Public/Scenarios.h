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
	/** The same for any boat, with reefs in (the heavy-air tack of the maxi). */
	SAILINGPHYSICS_API FTackResult RunTack(const FBoatConfig& Config, double TrueWindKnots, int Reefs, double CloseHauledTWADeg = 42.0,
		double TackTiller = 0.8);

	struct FGustReachResult
	{
		double MaxHeelDeg = 0.0;      // tilt, toward either side
		double SpeedBeforeKnots = 0.0;
		double MaxSpeedKnots = 0.0;
		double MinTwaDeg = 180.0;     // the closest she came to the wind (a broach rounds her up toward it)
		double MaxCourseErrorDeg = 0.0; // heading off the course she held before the gust
		bool bCapsized = false;
	};
	/**
	 * Reaching at TwaDeg in a steady MeanKnots with Reefs in, trimmed and steered by a good crew (FAutoTrim, FAutopilot);
	 * then a gust: the wind builds to GustKnots over 3 s and holds HoldSeconds, the sheets held where they were (the crew
	 * have not reacted), the helm still steering. bLimits applies FSceneLimits (the prologue's).
	 */
	SAILINGPHYSICS_API FGustReachResult RunGustReach(const FBoatConfig& Config, double MeanKnots, double GustKnots, double TwaDeg, int Reefs,
		bool bLimits, double HoldSeconds = 20.0);

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
