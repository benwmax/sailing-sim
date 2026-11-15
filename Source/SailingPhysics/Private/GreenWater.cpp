#include "GreenWater.h"

#include <algorithm>

namespace Sailing
{
	FGreenWater GreenWaterOn(const FBoatModel& Boat, const FWaveField* Waves, double Time)
	{
		FGreenWater G;
		const FBoatConfig& Config = Boat.GetConfig();
		if (Config.Hulls.empty()) return G;
		const FHullShape& Hull = Config.Hulls[0];
		double Sum = 0.0, SideSum = 0.0;
		for (int I = 0; I < FGreenWater::kStations; ++I)
		{
			// From 0.9 of the way aft to 0.92 of the way forward: the very ends' deck edge is a point.
			const double F = double(I) / double(FGreenWater::kStations - 1);
			const double X = 0.9 * Hull.SternX + F * (0.92 * Hull.BowX - 0.9 * Hull.SternX);
			const double HalfBeam = Hull.DeckHalfBeam(X), SheerZ = Hull.SheerHeight(X);
			for (const double S : { -1.0, 1.0 })
			{
				const Vec3 P = Boat.BodyToWorld(Vec3(X, Hull.CenterY + S * HalfBeam, SheerZ));
				const double Water = Waves ? Waves->Height(P.X, P.Y, Time) : 0.0;
				const double D = Water - P.Z;
				if (D <= 0.0) continue;
				++G.Points;
				Sum += D;
				SideSum += S * D;
				if (D > G.DepthM)
				{
					G.DepthM = D;
					G.X = X;
					G.At = P;
				}
			}
		}
		G.Side = Sum > 0.0 ? std::clamp(SideSum / Sum, -1.0, 1.0) : 0.0;
		return G;
	}
}
