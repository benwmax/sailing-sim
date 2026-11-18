#include "DemoHelm.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		int64_t CellKey(int64_t X, int64_t Y) { return int64_t((uint64_t(X) << 32) ^ uint64_t(uint32_t(Y))); }
	}

	double FDemoShoalGuard::LookFor(double SpeedMs) const
	{
		return std::clamp(LookSeconds * std::max(SpeedMs, 0.0), MinLookM, MaxLookM);
	}

	void FDemoShoalGuard::IndexObstacles() const
	{
		Indexed = Obstacles;
		IndexedCount = Obstacles->size();
		Buckets.clear();
		Seen.assign(IndexedCount, 0);
		Ray = 0;
		for (size_t I = 0; I < IndexedCount; ++I)
		{
			const FObstacleSegment& O = (*Obstacles)[I];
			// Every cell the segment's capsule (with the margin) touches: a ray looks in the cells around each point it passes.
			const double R = O.Radius + ObstacleMarginM;
			const int64_t X0 = int64_t(std::floor((std::min(O.AX, O.BX) - R) / BucketM)), X1 = int64_t(std::floor((std::max(O.AX, O.BX) + R) / BucketM));
			const int64_t Y0 = int64_t(std::floor((std::min(O.AY, O.BY) - R) / BucketM)), Y1 = int64_t(std::floor((std::max(O.AY, O.BY) + R) / BucketM));
			if ((X1 - X0 + 1) * (Y1 - Y0 + 1) > 4096) continue;   // a broken segment kilometres long: not a dock
			for (int64_t BX = X0; BX <= X1; ++BX)
			for (int64_t BY = Y0; BY <= Y1; ++BY)
			{
				Buckets[CellKey(BX, BY)].push_back(int(I));
			}
		}
	}

	double FDemoShoalGuard::ClearAhead(double X, double Y, double Heading, double MaxM) const
	{
		const double CX = std::cos(Heading), CY = std::sin(Heading);
		double Clear = MaxM;
		// Obstacles first: the nearest along the ray whose capsule (plus the margin) reaches it, from the grid cells the ray
		// crosses.
		if (Obstacles && !Obstacles->empty())
		{
			if (Indexed != Obstacles || IndexedCount != Obstacles->size()) IndexObstacles();
			++Ray;
			const double Reach = BucketM * 0.5;
			for (double D = 0.0; D <= MaxM + Reach; D += Reach)
			{
				const double S0 = std::min(D, MaxM);
				const int64_t BX = int64_t(std::floor((X + CX * S0) / BucketM)), BY = int64_t(std::floor((Y + CY * S0) / BucketM));
				for (int64_t DX = -1; DX <= 1; ++DX)
				for (int64_t DY = -1; DY <= 1; ++DY)
				{
					const auto It = Buckets.find(CellKey(BX + DX, BY + DY));
					if (It == Buckets.end()) continue;
					for (const int I : It->second)
					{
						if (Seen[size_t(I)] == Ray) continue;
						Seen[size_t(I)] = Ray;
						const FObstacleSegment& O = (*Obstacles)[size_t(I)];
						const double R = O.Radius + ObstacleMarginM;
						const double SX = O.BX - O.AX, SY = O.BY - O.AY, L2 = SX * SX + SY * SY;
						auto Dist = [&](double PX, double PY)
						{
							const double U = L2 > 1e-9 ? std::clamp(((PX - O.AX) * SX + (PY - O.AY) * SY) / L2, 0.0, 1.0) : 0.0;
							return std::hypot(PX - (O.AX + SX * U), PY - (O.AY + SY * U));
						};
						// Already within the margin (she starts beside a dock in the marina): that one does not block her way out.
						if (Dist(X, Y) < R) continue;
						for (double S = StepM; S < Clear; S += StepM)
						{
							if (Dist(X + CX * S, Y + CY * S) < R) { Clear = S - StepM; break; }
						}
					}
				}
			}
		}
		if (!Terrain) return Clear;
		// Already in thinner water than that (a shallow launch spot), she keeps to water no shallower than here.
		const double Here = Terrain->DepthAt(X, Y);
		const double Need = std::min(Draft + KeelMarginM, std::max(Here - 0.05, Draft + 0.1));
		for (double S = StepM; S <= Clear; S += StepM)
		{
			if (Terrain->DepthAt(X + CX * S, Y + CY * S) < Need) return S - StepM;
		}
		return Clear;
	}

	bool FDemoShoalGuard::CourseClear(double X, double Y, double WindFromRad, double BaseTwaDeg, bool bBeating, double Look) const
	{
		if (!bBeating) return ClearAhead(X, Y, WrapAngle(WindFromRad - BaseTwaDeg * kDegToRad), Look) >= Look;
		// Short tacks make good straight upwind; each leg runs a few boat lengths either side of that line.
		if (ClearAhead(X, Y, WindFromRad, Look) < Look) return false;
		for (const double Side : { 1.0, -1.0 })
		{
			if (ClearAhead(X, Y, WrapAngle(WindFromRad - Side * BeatTwaDeg * kDegToRad), TackLookM) < TackLookM) return false;
		}
		return true;
	}

	double FDemoShoalGuard::PickEscape(double X, double Y, double WindFromRad, double BaseTwaDeg) const
	{
		// The wind angle with the longest clear water; open water (ScanM clear) counts the same anywhere, and then the angle
		// furthest from the wind (away from the shore she was beating up to) wins, on the tack she is on.
		const double Side = BaseTwaDeg >= 0.0 ? 1.0 : -1.0;
		double Best = 150.0 * Side, BestClear = -1.0, BestPref = -1e9;
		for (const double Twa : { 150.0, 120.0, 90.0, 60.0 })
		for (const double S : { Side, -Side })
		{
			const double Clear = ClearAhead(X, Y, WrapAngle(WindFromRad - S * Twa * kDegToRad), ScanM);
			const double Score = std::min(Clear, 0.95 * ScanM);
			const double Pref = Twa + (S == Side ? 1.0 : 0.0);
			if (Score > BestClear + 1e-6 || (std::fabs(Score - BestClear) <= 1e-6 && Pref > BestPref))
			{
				Best = S * Twa;
				BestClear = Score;
				BestPref = Pref;
			}
		}
		return Best;
	}

	double FDemoShoalGuard::Update(double Time, double X, double Y, double WindFromRad, double SpeedMs, double BaseTwaDeg, bool bBeating)
	{
		if (Time < StartAfterSeconds || (!Terrain && (!Obstacles || Obstacles->empty()))) return BaseTwaDeg;
		if (Time < NextCheck) return bAvoiding ? AvoidTwa : BaseTwaDeg;
		NextCheck = Time + CheckEverySeconds;
		const double Look = LookFor(SpeedMs);
		if (!bAvoiding)
		{
			if (CourseClear(X, Y, WindFromRad, BaseTwaDeg, bBeating, Look)) return BaseTwaDeg;
			bAvoiding = true;
			AvoidSince = Time;
			AvoidTwa = PickEscape(X, Y, WindFromRad, BaseTwaDeg);
			++Count;
			return AvoidTwa;
		}
		// Back to the demo's own course once the bear-away has been held and the water that way is open well past the look.
		const double Open = std::min(2.0 * Look, ScanM);
		if (Time - AvoidSince >= HoldSeconds && CourseClear(X, Y, WindFromRad, BaseTwaDeg, bBeating, Open))
		{
			bAvoiding = false;
			return BaseTwaDeg;
		}
		// The bear-away's own course runs into shallows: choose again.
		if (ClearAhead(X, Y, WrapAngle(WindFromRad - AvoidTwa * kDegToRad), Look) < Look)
		{
			AvoidTwa = PickEscape(X, Y, WindFromRad, AvoidTwa);
		}
		return AvoidTwa;
	}
}
