#include "DemoHelm.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		constexpr double kNoHeading = 1e9;   // PickEscape's AwayFrom at a first choice (not a NaN: fast-math builds)

		int64_t CellKey(int64_t X, int64_t Y) { return int64_t((uint64_t(X) << 32) ^ uint64_t(uint32_t(Y))); }

		/**
		 * Where along the ray from (X, Y) in direction (CX, CY) it first comes within R of the segment A-B (the capsule's
		 * edge), MaxS when it does not before; the start is outside the capsule. Closed form: the two end circles and the two
		 * sides.
		 */
		double RayCapsule(double X, double Y, double CX, double CY, const FObstacleSegment& O, double R, double MaxS)
		{
			double Best = MaxS;
			auto Circle = [&](double PX, double PY)
			{
				const double DX = X - PX, DY = Y - PY;
				const double B = DX * CX + DY * CY, C = DX * DX + DY * DY - R * R;
				const double Disc = B * B - C;
				if (Disc < 0.0) return;
				const double S = -B - std::sqrt(Disc);
				if (S >= 0.0 && S < Best) Best = S;
			};
			Circle(O.AX, O.AY);
			Circle(O.BX, O.BY);
			const double SX = O.BX - O.AX, SY = O.BY - O.AY, L = std::hypot(SX, SY);
			if (L > 1e-9)
			{
				const double UX = SX / L, UY = SY / L, NX = -UY, NY = UX;
				const double H0 = (X - O.AX) * NX + (Y - O.AY) * NY, DH = CX * NX + CY * NY;
				if (std::fabs(DH) > 1e-12)
				{
					for (const double Side : { R, -R })
					{
						const double S = (Side - H0) / DH;
						if (S < 0.0 || S >= Best) continue;
						const double T = (X + CX * S - O.AX) * UX + (Y + CY * S - O.AY) * UY;
						if (T >= 0.0 && T <= L) Best = S;
					}
				}
			}
			return Best;
		}

		double SegmentDistance(double X, double Y, const FObstacleSegment& O)
		{
			const double SX = O.BX - O.AX, SY = O.BY - O.AY, L2 = SX * SX + SY * SY;
			const double U = L2 > 1e-9 ? std::clamp(((X - O.AX) * SX + (Y - O.AY) * SY) / L2, 0.0, 1.0) : 0.0;
			return std::hypot(X - (O.AX + SX * U), Y - (O.AY + SY * U));
		}
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
			if (O.Bottom > MastClearM) continue;   // a high bridge deck: she passes under it
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

	double FDemoShoalGuard::NeedAt(double X, double Y) const
	{
		const double Full = Draft + KeelMarginM;
		if (!Terrain) return Full;
		const double Here = Terrain->DepthAt(X, Y);
		if (Here >= Full) return Full;
		// No shallower than the water she was in when she came into thin water (ThinRef, raised as she finds deeper), and
		// never under her keel plus 0.1 m unless she is already there: measured from each check's own depth instead, she
		// could creep a couple of centimetres shallower every second down a gently shelving bed (a low tide in Clear Lake).
		const double Floor = std::max(ThinRef > 0.0 ? ThinRef - 0.05 : Here - 0.02, Draft + 0.1);
		return std::min(Floor, Here - 0.02);
	}

	double FDemoShoalGuard::ClearAhead(double X, double Y, double Heading, double MaxM) const
	{
		const double CX = std::cos(Heading), CY = std::sin(Heading);
		double Clear = MaxM;
		// Obstacles first: the nearest capsule (plus the margin) along the ray, from the grid cells the ray crosses.
		if (Obstacles && !Obstacles->empty())
		{
			if (Indexed != Obstacles || IndexedCount != Obstacles->size()) IndexObstacles();
			++Ray;
			const double Reach = BucketM * 0.5;
			for (double D = 0.0; D <= Clear + Reach; D += Reach)
			{
				const double S0 = std::min(D, Clear);
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
						// Already within the margin (leaving the marina, beside a pier): she keeps CloseMarginM from it instead, so
						// she can get out but not into it; touching it already, it is not in her way.
						const double Here = SegmentDistance(X, Y, O);
						double R = O.Radius + ObstacleMarginM;
						if (Here < R) R = O.Radius + CloseMarginM;
						if (Here < R) continue;
						Clear = std::min(Clear, std::max(0.0, RayCapsule(X, Y, CX, CY, O, R, Clear)));
					}
				}
			}
		}
		if (!Terrain) return Clear;
		const double Need = NeedAt(X, Y);
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

	double FDemoShoalGuard::PickEscape(double X, double Y, double WindFromRad, double BaseTwaDeg, double AwayFrom) const
	{
		const double Side = BaseTwaDeg >= 0.0 ? 1.0 : -1.0;
		const bool bThin = Terrain && Terrain->DepthAt(X, Y) < Draft + KeelMarginM;
		double Best = 150.0 * Side, BestScore = -1e9, BestPref = -1e9;
		for (const double Twa : { 150.0, 120.0, 90.0, 60.0 })
		for (const double S : { Side, -Side })
		{
			const double Heading = WrapAngle(WindFromRad - S * Twa * kDegToRad);
			double Score = 0.0;
			if (bThin)
			{
				// In thin water already (a shallow start, or blown onto a shoal): toward the deepest water close by.
				const double CX = std::cos(Heading), CY = std::sin(Heading);
				Score = std::min(Terrain->DepthAt(X + CX * 25.0, Y + CY * 25.0), Terrain->DepthAt(X + CX * 50.0, Y + CY * 50.0));
				if (Obstacles && ClearAhead(X, Y, Heading, 25.0) < 20.0) Score -= 100.0;   // a dock that way
			}
			else
			{
				// The longest clear water; open water (ScanM clear) counts the same anywhere, and then the angle furthest from
				// the wind (away from the shore she was beating up to) wins, on the tack she is on.
				Score = std::min(ClearAhead(X, Y, Heading, ScanM), 0.95 * ScanM);
			}
			// Choosing again, the way back along the course she is giving up is the last resort: it only shuttles her
			// between the same two shores (an enclosed harbour or a small lake).
			if (AwayFrom < 100.0 && std::fabs(WrapAngle(Heading - (AwayFrom + kPi))) < 60.0 * kDegToRad) Score -= bThin ? 1.0 : 0.6 * std::fabs(Score);
			const double Pref = Twa + (S == Side ? 1.0 : 0.0);
			if (Score > BestScore + 1e-6 || (std::fabs(Score - BestScore) <= 1e-6 && Pref > BestPref))
			{
				Best = S * Twa;
				BestScore = Score;
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
		if (Terrain)
		{
			const double Here = Terrain->DepthAt(X, Y);
			ThinRef = Here >= Draft + KeelMarginM ? -1.0 : std::max(ThinRef, Here);
		}
		const double Look = LookFor(SpeedMs);
		if (!bAvoiding)
		{
			if (CourseClear(X, Y, WindFromRad, BaseTwaDeg, bBeating, Look)) return BaseTwaDeg;
			bAvoiding = true;
			AvoidSince = Time;
			PickedAt = Time;
			AvoidTwa = PickEscape(X, Y, WindFromRad, BaseTwaDeg, kNoHeading);
			++Count;
			return AvoidTwa;
		}
		// Back to the demo's own course once the bear-away has been held and the water that way is open well past the look
		// (after a long bear-away, in a harbour or a small lake where it never is, past the look alone).
		const double Held = Time - AvoidSince;
		const double Open = Held >= 4.0 * HoldSeconds ? Look : std::min(2.0 * Look, ScanM);
		if (Held >= HoldSeconds && CourseClear(X, Y, WindFromRad, BaseTwaDeg, bBeating, Open))
		{
			bAvoiding = false;
			return BaseTwaDeg;
		}
		// The bear-away's own course is running out of water (or she is in thin water and it is not getting deeper): choose
		// again, not back the way she came.
		const double Heading = WrapAngle(WindFromRad - AvoidTwa * kDegToRad);
		// Not more often than RepickSeconds unless the way is shut right ahead: in a crowded harbour every course is short,
		// and choosing every second only turns her back and forth on the spot.
		const double Need = std::min(Look, RepickM);
		const double Ahead = ClearAhead(X, Y, Heading, Need);
		if (Ahead < Need && (Time - PickedAt >= RepickSeconds || Ahead < StepM))
		{
			// Boxed in (a berth among moored boats), a new course no better than this one is not worth the turn.
			const double Next = PickEscape(X, Y, WindFromRad, AvoidTwa, Heading);
			if (ClearAhead(X, Y, WrapAngle(WindFromRad - Next * kDegToRad), Need) > Ahead + StepM) AvoidTwa = Next;
			PickedAt = Time;
		}
		return AvoidTwa;
	}
}
