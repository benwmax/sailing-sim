#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include "PolarReference.h"
#include <functional>

namespace Sailing
{
	/**
	 * docs/frigate-physics/: a square-rigged ship's sail plans, from all plain sail down, as her officers took sail in
	 * while the wind rose (the light sails first, then reefs in the topsails, then the courses). The reference polar, the
	 * trial (Tools/shipkit/frigate/trial) and the game pick the fastest plan she carries under her heel cap.
	 */
	struct FShipSailPlan
	{
		const char* Name;
		bool bRoyals, bTopgallants;
		int TopsailReef;         // reefs taken in the topsails (clamped to the sail's own)
		bool bCourses, bJib, bStaysails, bSpanker;
	};

	SAILINGPHYSICS_API int NumShipSailPlans();
	SAILINGPHYSICS_API const FShipSailPlan& ShipSailPlan(int Plan);

	/** Sets the plan's sails on the controls (square sails Set or Clewed, topsail reefs, the fore-and-aft sails). Before
	 *  the wind (bRunning) the spanker is brailed up: it only blankets the main and makes her gripe. */
	SAILINGPHYSICS_API void ApplyShipSailPlan(const FBoatConfig& C, int Plan, FBoatControls& Controls, bool bRunning);

	/** The heel her officers sailed her to (deg): past it the light sails came in. */
	inline double ShipHeelCapDeg(const FBoatConfig& C) { return C.TrimHeelLimitDeg + 2.0; }

	struct FShipSteadyResult
	{
		FSteadyResult R;
		int Plan = 0;
		double YardDeg[kMaxMasts] = { 0.0, 0.0, 0.0 };  // each mast's lowest set yard, averaged
		double AlphaDeg[kMaxMasts] = { 0.0, 0.0, 0.0 }; // and its sail's angle of attack
	};

	/** Sails her steadily under one plan the way the fleet's polars are sailed (the polar's lake chop, the autopilot, the
	 *  ideal trimmer bracing the yards): SettleSeconds, then averaged over AverageSeconds. OnStep, if given, sees every
	 *  physics step (the trial's trace). */
	SAILINGPHYSICS_API FShipSteadyResult SailShipPlan(const FBoatConfig& C, double TrueWindKnots, double TrueWindAngleDeg, int Plan,
		double SettleSeconds, double AverageSeconds, const std::function<void(const FBoatModel&)>& OnStep = nullptr);

	/** The fastest plan she carries under the heel cap at a point of sail (the most canvas first; or, if none is under it,
	 *  the one that heels her least). */
	SAILINGPHYSICS_API FShipSteadyResult SailShipSteady(const FBoatConfig& C, double TrueWindKnots, double TrueWindAngleDeg,
		double SettleSeconds = 180.0, double AverageSeconds = 40.0);
}
