#include "Drills.h"

using namespace Sailing;

const TCHAR* DrillName(ESailingDrill Drill)
{
	switch (Drill)
	{
	case ESailingDrill::LeaveTheDock: return TEXT("Leave the dock");
	case ESailingDrill::SailATriangle: return TEXT("Sail a triangle");
	case ESailingDrill::HeaveTo: return TEXT("Heave to");
	case ESailingDrill::CrewOverboardFigureEight: return TEXT("Crew overboard: figure-eight");
	case ESailingDrill::CrewOverboardQuickStop: return TEXT("Crew overboard: quick-stop");
	case ESailingDrill::ReturnAndDock: return TEXT("Return and dock");
	default: return TEXT("Free sail");
	}
}

namespace
{
	FVector2D BoatXY(const FBoatModel& Boat) { const Vec3 O = Boat.OriginPosition(); return FVector2D(O.X, O.Y); }
}

void FDrillRunner::Start(ESailingDrill InDrill, const FBoatModel& Boat, double WindFromRad)
{
	Drill = InDrill;
	Steps.Reset();
	Marks.Reset();
	Step = 0;
	bComplete = false;
	Elapsed = Hold = MaxDistance = 0.0;
	NextMark = 0;
	bDummy = false;
	TacksOrGybes = 0;
	LastSide = Boat.GetTelemetry().TrueWindAngle >= 0.0 ? 1 : -1;
	Start2D = BoatXY(Boat);
	const FVector2D Up(FMath::Cos(WindFromRad), FMath::Sin(WindFromRad)); // toward where the wind comes from
	const FVector2D Across(-Up.Y, Up.X);

	switch (Drill)
	{
	case ESailingDrill::LeaveTheDock:
		Steps = { TEXT("Check the wind and plan which way you will leave"), TEXT("Cast off the dock lines (T)"),
			TEXT("Sail out without touching the docks or other boats"), TEXT("Get 100 m clear of the marina") };
		Status = TEXT("You are tied up. Look at the wind arrow before you cast off.");
		break;
	case ESailingDrill::SailATriangle:
		Marks = { Start2D + Up * 250.0, Start2D + Up * 125.0 + Across * 180.0, Start2D };
		Steps = { TEXT("Beat to the windward mark, tacking as needed (close-hauled)"), TEXT("Bear away and reach to the wing mark"),
			TEXT("Reach back to the start mark") };
		Status = TEXT("Sail close-hauled toward the windward mark. Keep the jib telltales streaming.");
		break;
	case ESailingDrill::HeaveTo:
		Steps = { TEXT("Sail close-hauled"), TEXT("Back the jib: tack without releasing it, or hold it to windward (B)"),
			TEXT("Ease the main until it luffs"), TEXT("Put the tiller to leeward and hold it"), TEXT("Stay hove to for 20 seconds") };
		Status = TEXT("Heaving to parks the boat: the backed jib and the rudder balance each other.");
		break;
	case ESailingDrill::CrewOverboardFigureEight:
	case ESailingDrill::CrewOverboardQuickStop:
	{
		bDummy = true;
		const Vec3 F = Boat.GetState().Orientation.Forward();
		Dummy = Start2D - FVector2D(F.X, F.Y) * 8.0;
		DummyDrift = -Up * 0.25; // a person in the water drifts slowly downwind
		if (Drill == ESailingDrill::CrewOverboardFigureEight)
		{
			Steps = { TEXT("Shout \"Crew overboard!\", point, and keep pointing"), TEXT("Sail away on a beam reach, about five boat lengths"),
				TEXT("Tack, then bear away to a broad reach back toward them"), TEXT("Approach on a close reach and luff to stop alongside, to windward of them") };
		}
		else
		{
			Steps = { TEXT("Shout \"Crew overboard!\" and head up into the wind at once"), TEXT("Keep turning: tack, leave the jib backed, and circle the person"),
				TEXT("Approach slowly and stop alongside them") };
		}
		Status = TEXT("Someone is in the water! Keep them in sight.");
		break;
	}
	case ESailingDrill::ReturnAndDock:
		Steps = { TEXT("Approach the dock on a close reach or heading into the wind"), TEXT("Luff the sails to slow down well before the dock"),
			TEXT("Come alongside under 1 knot and get the lines on (T)") };
		Status = TEXT("Plan your approach so you can stop by luffing.");
		break;
	default:
		break;
	}
}

bool FDrillRunner::Update(const FBoatModel& Boat, const FDrillContext& Context, double Dt)
{
	if (!IsActive()) return false;
	Elapsed += Dt;
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FVector2D P = BoatXY(Boat);
	const double Knots = T.BoatSpeed / kKnot;
	const double TwaDeg = FMath::RadiansToDegrees(T.TrueWindAngle);
	const int32 Side = TwaDeg >= 0.0 ? 1 : -1;
	if (Side != LastSide && FMath::Abs(TwaDeg) > 10.0) { ++TacksOrGybes; LastSide = Side; }

	switch (Drill)
	{
	case ESailingDrill::LeaveTheDock:
	{
		const double Clear = FVector2D::Distance(P, Start2D);
		Step = Context.bTiedUp ? 1 : (Clear < 30.0 ? 2 : 3);
		Status = FString::Printf(TEXT("%.0f m from where you started"), Clear);
		if (!Context.bTiedUp && Clear > 100.0)
		{
			bComplete = true;
			Status = Context.MaxContactSpeed > 1.0 ? FString::Printf(TEXT("Clear, but you touched a dock at %.1f kn. Try again without touching."), Context.MaxContactSpeed)
				: TEXT("Clean departure: well done.");
		}
		break;
	}
	case ESailingDrill::SailATriangle:
	{
		const double D = FVector2D::Distance(P, Marks[NextMark]);
		if (D < 20.0 && Elapsed > 5.0)
		{
			++NextMark;
			if (NextMark >= Marks.Num()) { bComplete = true; Status = FString::Printf(TEXT("Triangle done in %d:%02d."), int32(Elapsed) / 60, int32(Elapsed) % 60); break; }
		}
		Step = NextMark;
		Status = FString::Printf(TEXT("Next mark %.0f m away"), FVector2D::Distance(P, Marks[NextMark]));
		break;
	}
	case ESailingDrill::HeaveTo:
	{
		const bool bAbackAndSlow = Context.bBackJib && Knots < 3.0 && FMath::Abs(TwaDeg) > 35.0 && FMath::Abs(TwaDeg) < 100.0;
		Hold = bAbackAndSlow ? Hold + Dt : 0.0;
		Step = !Context.bBackJib ? (FMath::Abs(TwaDeg) < 60.0 ? 1 : 0) : (Knots > 3.0 ? 2 : (Hold > 0.0 ? 4 : 3));
		Status = bAbackAndSlow ? FString::Printf(TEXT("Hove to: %.0f of 20 seconds, %.1f kn"), Hold, Knots) : FString::Printf(TEXT("%.1f kn, wind %.0f degrees off the bow"), Knots, FMath::Abs(TwaDeg));
		if (Hold >= 20.0) { bComplete = true; Status = TEXT("Hove to. This is how you stop to reef, rest or wait out a squall."); }
		break;
	}
	case ESailingDrill::CrewOverboardFigureEight:
	case ESailingDrill::CrewOverboardQuickStop:
	{
		Dummy += DummyDrift * Dt;
		const double D = FVector2D::Distance(P, Dummy);
		MaxDistance = FMath::Max(MaxDistance, D);
		const bool bFigure8 = Drill == ESailingDrill::CrewOverboardFigureEight;
		if (bFigure8) Step = MaxDistance < 30.0 ? (Elapsed < 3.0 ? 0 : 1) : (TacksOrGybes == 0 ? 2 : 3);
		else Step = TacksOrGybes == 0 ? 0 : (D > 15.0 ? 1 : 2);
		Status = FString::Printf(TEXT("Person in the water %.0f m away, you are making %.1f kn"), D, Knots);
		if (D < 3.0 && Knots < 1.2 && Elapsed > 10.0)
		{
			const bool bProper = bFigure8 ? (MaxDistance > 30.0 && TacksOrGybes >= 1) : (MaxDistance < 80.0);
			bComplete = true;
			Status = bProper ? FString::Printf(TEXT("Recovered in %d:%02d. Get them aboard on the windward side."), int32(Elapsed) / 60, int32(Elapsed) % 60)
				: TEXT("Recovered, but not with this maneuver. Try the steps in order.");
		}
		break;
	}
	case ESailingDrill::ReturnAndDock:
	{
		Step = Context.bTiedUp ? 2 : (Knots > 1.5 ? 0 : 1);
		Status = FString::Printf(TEXT("%.1f kn"), Knots);
		if (Context.bTiedUp)
		{
			bComplete = true;
			Status = Context.MaxContactSpeed > 1.5 ? FString::Printf(TEXT("Docked, but you hit at %.1f kn. Slow down earlier."), Context.MaxContactSpeed)
				: TEXT("Docked gently. Well done.");
		}
		break;
	}
	default:
		break;
	}
	return !bComplete;
}

bool FindBerth(const FLakeTerrain& Terrain, const std::vector<FObstacleSegment>& Obstacles, FVector2D Near,
	double MaxRange, double WindFromRad, FVector2D& OutPosition, double& OutHeading, const FBoatConfig& Boat)
{
	auto DistToSegment = [](const FObstacleSegment& S, const FVector2D& P)
	{
		const FVector2D A(S.AX, S.AY), B(S.BX, S.BY);
		const FVector2D AB = B - A;
		const double Len2 = AB.SizeSquared();
		const double T = Len2 > 1e-9 ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / Len2, 0.0, 1.0) : 0.0;
		return FVector2D::Distance(P, A + AB * T) - S.Radius;
	};
	// Room for the whole boat with water under the keel (the J/22: 2.4 m beam, 6.9 m long, 1.2 m draft).
	const double HalfBeam = 0.5 * Boat.Beam + 0.05, HalfLength = 0.5 * Boat.LengthOverall + 0.07, MinDepth = Boat.Draft + 1.14;
	double Best = MaxRange;
	bool bFound = false;
	for (size_t I = 0; I < Obstacles.size(); ++I)
	{
		const FObstacleSegment& S = Obstacles[I];
		if (S.Top > 1.5) continue;
		const FVector2D A(S.AX, S.AY), B(S.BX, S.BY);
		const double Len = FVector2D::Distance(A, B);
		if (Len < 2.0 * HalfLength + 1.0) continue;
		const FVector2D Along = (B - A) / Len, Normal(-Along.Y, Along.X);
		// Slide along the face in 2 m steps, trying both sides.
		for (double T = HalfLength + 0.5; T <= Len - HalfLength - 0.5; T += 2.0)
		{
			for (int32 Side = -1; Side <= 1; Side += 2)
			{
				const FVector2D P = A + Along * T + Normal * (Side * (S.Radius + HalfBeam + 0.15));
				const double D = FVector2D::Distance(P, Near);
				if (D >= Best) continue;
				bool bOk = true;
				for (double U = -HalfLength; U <= HalfLength && bOk; U += HalfLength)
				{
					for (double V = -HalfBeam; V <= HalfBeam && bOk; V += HalfBeam)
					{
						const FVector2D Q = P + Along * U + Normal * V;
						if (Terrain.DepthAt(Q.X, Q.Y) < MinDepth) bOk = false;
						for (size_t J = 0; J < Obstacles.size() && bOk; ++J)
						{
							if (J != I && Obstacles[J].Bottom < 0.0 && DistToSegment(Obstacles[J], Q) < 0.3) bOk = false;
						}
					}
				}
				// Room to sail off: open water a few boat lengths out from the face.
				for (double Out = 6.0; Out <= 18.0 && bOk; Out += 6.0)
				{
					const FVector2D Q = P + Normal * (Side * Out);
					if (Terrain.DepthAt(Q.X, Q.Y) < MinDepth) bOk = false;
				}
				if (!bOk) continue;
				Best = D;
				bFound = true;
				OutPosition = P;
				const FVector2D Up(FMath::Cos(WindFromRad), FMath::Sin(WindFromRad));
				const FVector2D Bow = FVector2D::DotProduct(Along, Up) >= 0.0 ? Along : -Along;
				OutHeading = FMath::Atan2(Bow.Y, Bow.X);
			}
		}
	}
	return bFound;
}

std::vector<FMooringLine> FindDockLines(const FBoatModel& Boat, const std::vector<FObstacleSegment>& Obstacles, double Reach)
{
	std::vector<FMooringLine> Lines;
	// Bow, stern quarters and the midship spring cleats.
	for (const Vec3& Cleat : Boat.CleatPoints())
	{
		const Vec3 P = Boat.BodyToWorld(Cleat);
		double Best = Reach;
		Vec3 Anchor;
		for (const FObstacleSegment& S : Obstacles)
		{
			if (S.Top > 1.5) continue; // docks only, not bridges
			const double SX = S.BX - S.AX, SY = S.BY - S.AY, Len2 = SX * SX + SY * SY;
			const double T = Len2 > 1e-9 ? Clamp(((P.X - S.AX) * SX + (P.Y - S.AY) * SY) / Len2, 0.0, 1.0) : 0.0;
			const Vec3 C(S.AX + SX * T, S.AY + SY * T, 0.5);
			const double D = (C - P).LengthXY();
			if (D < Best) { Best = D; Anchor = C; }
		}
		if (Best < Reach)
		{
			Lines.push_back({ Cleat, Anchor, std::max(0.6, Best + 0.2) });
		}
	}
	if (Lines.size() < 2) Lines.clear();
	return Lines;
}
