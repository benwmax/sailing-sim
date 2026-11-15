#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include "Waves.h"

namespace Sailing
{
	/**
	 * Storm look 2 (docs/storm-look/green-water/): where the sea stands over a boat's sheer, so solid water comes aboard
	 * ("green water"): the bow buried in a steep sea, or the lee rail dragged under in a knockdown. Sampled along both rails
	 * of her main hull from near the transom to near the bow. Visual only: the buoyancy already counts the water's height;
	 * the pawn's deck film (MPC_Boat Wash, WashSide) and AWaterSurface's sheets of water over the deck follow it.
	 */
	struct FGreenWater
	{
		double DepthM = 0.0;   // the deepest water over the rail (m; 0 = none aboard)
		double Side = 0.0;     // which rail, weighted by depth: -1 port, +1 starboard, near 0 both (a sea over the bow)
		double X = 0.0;        // body frame x of the deepest point (m, + forward)
		Vec3 At;               // world position of that point on the rail
		int Points = 0;        // rail points under water (of 2 x kStations)

		static constexpr int kStations = 9;
	};

	SAILINGPHYSICS_API FGreenWater GreenWaterOn(const FBoatModel& Boat, const FWaveField* Waves, double Time);
}
