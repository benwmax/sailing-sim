#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"

namespace Sailing
{
	struct FAutoTrimSettings
	{
		double AlphaMarginDeg = 2.0;   // aim this far below each sail's stall angle
		double HeelLimitDeg = 22.0;    // start depowering above this heel
		double FlattenFromKnots = 9.0; // start flattening sails above this true wind
		double FlattenRangeKnots = 6.0;
		bool bTrimMain = true;
		bool bTrimJib = true;
		bool bHike = true;
		bool bShape = true;            // vang, outhaul, cunningham, backstay
	};

	/**
	 * Trims the sails to the apparent wind the way a good crew would: each sail at a target angle of attack,
	 * flattened as the breeze builds, eased and feathered when heel passes a limit, crew hiking.
	 * Used by the polar tests and by the easy difficulty's trim assist.
	 */
	class SAILINGPHYSICS_API FAutoTrim
	{
	public:
		FAutoTrimSettings Settings;

		/** Returns new controls; Tiller and anything not enabled in the settings pass through unchanged. */
		FBoatControls Update(const FBoatModel& Boat, const FBoatControls& Current, double Dt);

		void Reset() { MainEase = 0.0; }

	private:
		double MainEase = 0.0; // rad, extra ease from heel feedback
	};

	/** Holds a true wind angle with the tiller. For tests and the AI later. */
	struct SAILINGPHYSICS_API FAutopilot
	{
		double TargetTWADeg = 45.0; // signed: + = wind from starboard
		double Gain = 2.5;          // tiller per radian of heading error
		double RateGain = 1.2;      // tiller per rad/s of yaw rate
		double MaxTiller = 0.6;     // a good helmsman keeps the rudder short of stalling (about 18 degrees)

		double Update(const FBoatModel& Boat) const;
	};
}
