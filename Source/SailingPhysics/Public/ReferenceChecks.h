#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * Phase 8 physics checks against real numbers (docs/phase-8/reference-kit/method.md, step 3): heel tables, tacking
	 * angles, roll period, lake waves, capsize behaviour, speed ceilings and Portsmouth lap-time ratios. Each check
	 * carries its target, its tolerance and where the number comes from.
	 */
	struct FReferenceCheck
	{
		std::string Group;   // "Heel", "Tacking", ...
		std::string Name;    // "J/22 close-hauled, 8 kn"
		double Value = 0.0;  // what the model does
		double Low = 0.0, High = 0.0; // the accepted range (target plus tolerance)
		std::string Unit;
		std::string Source;  // the reference
		bool Pass() const { return Value >= Low && Value <= High; }
	};

	/** Best upwind VMG: heading-based true wind angle (deg), boat speed (kn) and VMG (kn). Sweeps the angle in 2 degree steps. */
	struct FVmgResult { double TwaDeg = 0.0, SpeedKnots = 0.0, VmgKnots = 0.0, HeelDeg = 0.0; };
	SAILINGPHYSICS_API FVmgResult BestUpwind(const FBoatConfig& Config, double TrueWindKnots);
	SAILINGPHYSICS_API FVmgResult BestDownwind(const FBoatConfig& Config, double TrueWindKnots);

	/** Free roll decay at rest in still water from a small heel: the natural roll period (s). */
	SAILINGPHYSICS_API double RollPeriodSeconds(const FBoatConfig& Config, double StartHeelDeg = 8.0);

	/** Tilt from upright (deg, 0..180; 180 = turtled) after Seconds lying capsized at StartHeelDeg in a breeze with the sheets free and nobody righting her. */
	SAILINGPHYSICS_API double HeelAfterCapsize(const FBoatConfig& Config, double StartHeelDeg, double TrueWindKnots, double Seconds);

	/** Peak and mean boat speed (kn) over Seconds on a set point of sail in gusty wind and lake waves. */
	struct FSpeedRun { double PeakKnots = 0.0, MeanKnots = 0.0; };
	SAILINGPHYSICS_API FSpeedRun SpeedRun(const FBoatConfig& Config, double TrueWindKnots, double TwaDeg, bool bSpinnaker,
		double GustIntensity, double FetchMeters, double Seconds, int Reefs = 0);

	/** Runs every check; bQuick skips the slowest (fleet lap-time ratios in the light band). */
	SAILINGPHYSICS_API std::vector<FReferenceCheck> RunReferenceChecks(bool bQuick = false);
}
