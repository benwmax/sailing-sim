#include "Misc/AutomationTest.h"
#include "DemoHelm.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "SeaTrials.h"
#include "WindClimate.h"
#include <algorithm>
#include <cmath>

#if WITH_DEV_AUTOMATION_TESTS

// docs/demo-shoal-guard/ (sailing-feedback #31): the demo autopilot (-SailingDemo) beat upwind until it met the shore and
// sat there aground (Galveston from launch 1 at minute 11, Ray Hubbard's south shore at minute 50), spoiling the soaks.
// FDemoShoalGuard reads the chart ahead and bears away.

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags DemoGuardFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double kJ22Draft = 1.16;

	// The demo's own course: close-hauled, tacking at 9 s and every 12 s after (ASailboatPawn::Tick).
	double DemoBaseTwa(double T) { const int32 Leg = T < 9.0 ? 0 : 1 + int32((T - 9.0) / 12.0); return Leg % 2 == 0 ? 45.0 : -45.0; }

	// A J/22's speed through the water by wind angle in a moderate breeze (her polar, rounded).
	double KinematicSpeed(double TwaDeg) { const double A = std::fabs(TwaDeg); return A < 50.0 ? 2.0 : A < 75.0 ? 2.4 : A < 135.0 ? 2.7 : 2.3; }

	struct FKinematicRun
	{
		double AgroundAt = -1.0;      // s, the first time the keel would touch (-1: never)
		double LeastUnderKeel = 1e9;  // m
		double FarthestM = 0.0;       // from the start
		int32 Avoidances = 0;
		int32 ObstacleTouches = 0;    // steps inside a dock, pier or bridge's capsule she did not start in
	};

	/**
	 * The demo's course sailed as a point (her speed by the wind angle, turning at once) for Seconds on a lake, with the guard
	 * or without it. Fast enough to sail every launch spot in eight winds for two hours.
	 */
	FKinematicRun SailKinematic(const FLakeData& Lake, double X, double Y, double WindFromDeg, double Seconds, bool bGuard)
	{
		FDemoShoalGuard Guard;
		Guard.Terrain = &Lake.Terrain;
		Guard.Obstacles = &Lake.Obstacles;
		Guard.Draft = kJ22Draft;
		FKinematicRun R;
		const double X0 = X, Y0 = Y, From = WindFromDeg * kDegToRad, Dt = 0.5;
		TSet<int32> Beside;   // obstacles she starts within the guard's margin of (the marina)
		if (const TArray<int32>* Near = Lake.ObstaclesNear(X, Y)) Beside.Append(*Near);
		double Speed = 0.0;
		for (double T = 0.0; T < Seconds; T += Dt)
		{
			const double Twa = bGuard ? Guard.Update(T, X, Y, From, Speed, DemoBaseTwa(T), true) : DemoBaseTwa(T);
			Speed = KinematicSpeed(Twa);
			const double H = From - Twa * kDegToRad;
			X += std::cos(H) * Speed * Dt;
			Y += std::sin(H) * Speed * Dt;
			const double UnderKeel = Lake.Terrain.DepthAt(X, Y) - kJ22Draft;
			R.LeastUnderKeel = std::min(R.LeastUnderKeel, UnderKeel);
			R.FarthestM = std::max(R.FarthestM, std::hypot(X - X0, Y - Y0));
			if (UnderKeel < 0.0) { R.AgroundAt = T; break; }
			if (const TArray<int32>* Near = Lake.ObstaclesNear(X, Y))
			{
				for (const int32 I : *Near)
				{
					if (Beside.Contains(I)) continue;
					const FObstacleSegment& O = Lake.Obstacles[I];
					if (O.Bottom > 12.0) continue;   // a bridge deck she passes under
					const double SX = O.BX - O.AX, SY = O.BY - O.AY, L2 = SX * SX + SY * SY;
					const double U = L2 > 1e-9 ? FMath::Clamp(((X - O.AX) * SX + (Y - O.AY) * SY) / L2, 0.0, 1.0) : 0.0;
					if (std::hypot(X - (O.AX + SX * U), Y - (O.AY + SY * U)) < O.Radius + 1.2) { ++R.ObstacleTouches; break; }
				}
			}
		}
		R.Avoidances = Guard.Avoidances();
		return R;
	}

	FLakeTerrain SyntheticLake(bool bShoreNorth)
	{
		// 4 km square, 10 m deep; with bShoreNorth the bed rises to a shore 1.5 km north of the middle (X = 3500).
		const int Rows = 401, Cols = 401;
		std::vector<float> H(size_t(Rows) * Cols);
		for (int Rr = 0; Rr < Rows; ++Rr)
			for (int C = 0; C < Cols; ++C)
			{
				const double X = Rr * 10.0;
				H[size_t(Rr) * Cols + C] = float(!bShoreNorth || X < 3000.0 ? -10.0 : -10.0 + 10.0 * (X - 3000.0) / 500.0);
			}
		FLakeTerrain T;
		T.InitSynthetic(Rows, Cols, 10.0, 0.0, -2000.0, H);
		return T;
	}
}

/** In open water the guard leaves the demo's course alone; with a shore upwind it bears away short of it. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDemoShoalGuardLogicTest, "SailingSim.Physics.DemoShoalGuard.Logic", DemoGuardFlags)
bool FDemoShoalGuardLogicTest::RunTest(const FString& Parameters)
{
	for (const bool bShore : { false, true })
	{
		const FLakeTerrain T = SyntheticLake(bShore);
		FDemoShoalGuard Guard;
		Guard.Terrain = &T;
		// Wind from the north (+X): beating, the demo makes good straight toward the shore.
		double X = 2000.0, Y = 0.0, Speed = 0.0, MaxX = X;
		int32 Changed = 0;
		for (double Tm = 0.0; Tm < 3600.0; Tm += 0.5)
		{
			const double Twa = Guard.Update(Tm, X, Y, 0.0, Speed, DemoBaseTwa(Tm), true);
			Changed += Twa != DemoBaseTwa(Tm) ? 1 : 0;
			Speed = KinematicSpeed(Twa);
			X += std::cos(-Twa * kDegToRad) * Speed * 0.5;
			Y += std::sin(-Twa * kDegToRad) * Speed * 0.5;
			MaxX = std::max(MaxX, X);
			if (!bShore && X > 3600.0) break;   // across the open lake: the guard never had cause to act
		}
		if (!bShore)
		{
			TestEqual(TEXT("Open water: the demo's course untouched"), Changed, 0);
			TestEqual(TEXT("Open water: no bear-aways"), Guard.Avoidances(), 0);
		}
		else
		{
			// The bed reaches the keel plus the margin (1.76 m) at X = 3412.
			AddInfo(FString::Printf(TEXT("Shore upwind: furthest north %.0f m (keel at 3442), %d bear-aways"), MaxX, Guard.Avoidances()));
			TestTrue(TEXT("Shore upwind: she bears away"), Guard.Avoidances() > 0);
			TestTrue(TEXT("Shore upwind: she never reaches water shallower than her keel and the margin"), MaxX < 3412.0);
		}
	}
	// She starts beside a dock (the marina): that dock does not block her way out; a pier across her course does.
	std::vector<FObstacleSegment> Docks(2);
	Docks[0].AX = -5.0; Docks[0].AY = 3.0; Docks[0].BX = 30.0; Docks[0].BY = 3.0;
	Docks[1].AX = 100.0; Docks[1].AY = -50.0; Docks[1].BX = 100.0; Docks[1].BY = 50.0;
	FDemoShoalGuard Guard;
	Guard.Obstacles = &Docks;
	TestTrue(TEXT("A dock alongside does not block"), Guard.ClearAhead(0.0, 0.0, 0.0, 60.0) >= 60.0);
	const double ToPier = Guard.ClearAhead(0.0, 0.0, 0.0, 500.0);
	TestTrue(TEXT("A pier across her course stops the clear water short of it"), ToPier > 70.0 && ToPier < 100.0 - Docks[1].Radius);
	return true;
}

/**
 * Every launch spot of the lake, the bay and Marseille, in eight winds, two hours of the demo's course: with the guard she
 * never reaches water shallower than her keel; without it most runs end on the shore upwind (the test bites).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDemoShoalGuardChartsTest, "SailingSim.Physics.DemoShoalGuard.Charts", DemoGuardFlags)
bool FDemoShoalGuardChartsTest::RunTest(const FString& Parameters)
{
	for (const TCHAR* World : { TEXT("RayHubbard"), TEXT("GalvestonBay"), TEXT("Marseille") })
	{
		FLakeData Lake;
		if (!TestTrue(FString::Printf(TEXT("%s loads"), World), Lake.Load(FLakeData::DefaultDirectory(), World))) continue;
		int32 Runs = 0, ControlAground = 0, Aground = 0, Touches = 0;
		double Least = 1e9;
		for (int32 S = 0; S < Lake.LaunchSpots.Num(); ++S)
		{
			const FLaunchSpot& Spot = Lake.LaunchSpots[S];
			// Spots too shallow for a J/22 to start in at all are not the demo's.
			if (Lake.Terrain.DepthAt(Spot.X, Spot.Y) < kJ22Draft + 0.3) continue;
			for (int32 F = 0; F < 360; F += 45)
			{
				const FKinematicRun Off = SailKinematic(Lake, Spot.X, Spot.Y, F, 7200.0, false);
				const FKinematicRun On = SailKinematic(Lake, Spot.X, Spot.Y, F, 7200.0, true);
				++Runs;
				ControlAground += Off.AgroundAt >= 0.0;
				Least = std::min(Least, On.LeastUnderKeel);
				Touches += On.ObstacleTouches > 0;
				if (On.AgroundAt >= 0.0)
				{
					++Aground;
					AddError(FString::Printf(TEXT("%s spot %d (%s), wind from %d: aground at %.0f s"), World, S, *Spot.Name, F, On.AgroundAt));
				}
				if (On.ObstacleTouches > 0)
				{
					AddInfo(FString::Printf(TEXT("%s spot %d, wind from %d: %d steps inside a dock or pier's capsule"), World, S, F, On.ObstacleTouches));
				}
			}
		}
		AddInfo(FString::Printf(TEXT("%s: %d runs; without the guard %d end aground, with it %d (least water under the keel %.2f m); %d runs touched a dock or pier"),
			World, Runs, ControlAground, Aground, Least, Touches));
		TestTrue(FString::Printf(TEXT("%s: the spots were sailed"), World), Runs >= 8);
		TestTrue(FString::Printf(TEXT("%s: without the guard most runs end aground (the check bites)"), World), ControlAground * 2 > Runs);
	}
	return true;
}

/**
 * The real boat (physics, trimmer, autopilot) on the course of the PC's Galveston soak (#31): beating south from the Kemah
 * channel into a 6 kn southerly, from the point 300 m short of where it went aground. With the guard she bears away and
 * keeps sailing; the same run without it is aground inside five minutes (scratch runs on main: 258 s).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDemoShoalGuardGalvestonTest, "SailingSim.Physics.DemoShoalGuard.Galveston", DemoGuardFlags)
bool FDemoShoalGuardGalvestonTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Galveston Bay loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("GalvestonBay")))) return false;
	FTrialSeaSpec Spec;
	Spec.WindKnots = 6.0;
	Spec.WindFromDeg = 180.0;
	Spec.GustIntensity = GustIntensityForFactor(1.3);
	Spec.FetchMeters = 3000.0;
	FTrialSea Sea(Spec);
	FBoatModel Boat(FBoatConfig::Make(EBoatType::J22));
	Boat.SetTerrain(&Lake.Terrain);
	Boat.SetObstacles(&Lake.Obstacles);
	Boat.Reset(-1150.0, 1120.0, Sea.HeadingFor(45.0), 0.0);
	FAutoTrim Trim;
	FAutopilot Pilot;
	Pilot.MaxTiller = 0.8;
	Pilot.Wind = &Sea.GetWind();
	FDemoShoalGuard Guard;
	Guard.Terrain = &Lake.Terrain;
	Guard.Obstacles = &Lake.Obstacles;
	Guard.Draft = Boat.GetConfig().Draft;
	FBoatControls C;
	double T = 0.0, Least = 1e9, AgroundFor = 0.0;
	const Vec3 Start = Boat.OriginPosition();
	for (int32 I = 0; I < int32(360.0 * PhysicsHz); ++I, T += PhysicsDt)
	{
		const Vec3 O = Boat.OriginPosition();
		Sea.Update(T, O.X, O.Y);
		if (I % 12 == 0)
		{
			double FromRad = 0.0, Factor = 1.0;
			Sea.GetWind().ReadableAt(O.X, O.Y, T, FromRad, Factor);
			Pilot.TargetTWADeg = Guard.Update(T, O.X, O.Y, FromRad, Boat.GetTelemetry().BoatSpeed, DemoBaseTwa(T), true);
		}
		C = Trim.Update(Boat, C, PhysicsDt);
		C.Tiller = Pilot.Update(Boat);
		Boat.Step(PhysicsDt, C, Sea.GetWind(), Sea.GetWaves());
		const FBoatTelemetry& Tm = Boat.GetTelemetry();
		if (T > 2.0) Least = std::min(Least, Tm.DepthUnderKeel);
		if (Tm.bAground) AgroundFor += PhysicsDt;
	}
	const Vec3 End = Boat.OriginPosition();
	AddInfo(FString::Printf(TEXT("360 s: %d bear-aways, least water under the keel %.2f m, aground %.1f s, ended %.0f m from the start at %.0f N %.0f E"),
		Guard.Avoidances(), Least, AgroundFor, std::hypot(End.X - Start.X, End.Y - Start.Y), End.X, End.Y));
	TestTrue(TEXT("She bore away from the shoal"), Guard.Avoidances() > 0);
	TestEqual(TEXT("She never touched the bottom"), AgroundFor, 0.0);
	TestTrue(TEXT("She is still sailing (not stopped short of the shoal)"), Boat.GetTelemetry().BoatSpeed > 0.5);
	return true;
}

#endif
