#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "AutoTrim.h"
#include "Drills.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "LakeTerrain.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** A synthetic lake: deep water for X < ShoalStart, rising linearly to Shore (height 0) and land beyond. */
	FLakeTerrain ShelvingLake(double ShoalStart, double Shore, double Depth = 5.0)
	{
		const int Rows = 200, Cols = 100;
		std::vector<float> H(Rows * Cols);
		for (int R = 0; R < Rows; ++R)
			for (int C = 0; C < Cols; ++C)
			{
				const double X = R * 2.0;
				H[R * Cols + C] = float(X < ShoalStart ? -Depth : -Depth + Depth * (X - ShoalStart) / (Shore - ShoalStart));
			}
		FLakeTerrain T;
		T.InitSynthetic(Rows, Cols, 2.0, 0.0, -100.0, H);
		return T;
	}

	void SailFor(FBoatModel& Boat, FBoatControls& C, const FWindField& Wind, double Seconds, FAutoTrim* Trim = nullptr, const TFunction<void()>& Each = nullptr)
	{
		for (int32 I = 0; I < int32(Seconds * PhysicsHz); ++I)
		{
			if (Trim)
			{
				const double Tiller = C.Tiller;
				C = Trim->Update(Boat, C, PhysicsDt);
				C.Tiller = Tiller;
			}
			if (Each) Each();
			Boat.Step(PhysicsDt, C, Wind);
		}
	}

	FWindField WindFrom(double Knots, double FromDeg)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = FromDeg;
		return FWindField(P);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShorelineTest, "SailingSim.Lake.ShorelineMatchesMapData", Flags)
bool FSailingShorelineTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard"))))
	{
		return false;
	}
	TestTrue(TEXT("At least three shoreline checkpoints"), Lake.Checkpoints.Num() >= 3);
	for (const TPair<FString, FVector2D>& Cp : Lake.Checkpoints)
	{
		// Distance from the OpenStreetMap shoreline vertex to the terrain's zero contour (the water's edge in game).
		double Best = 1e9;
		for (int32 A = 0; A < 72; ++A)
		{
			const double Ang = A * 5.0 * kDegToRad;
			double Prev = Lake.Terrain.HeightAt(Cp.Value.X, Cp.Value.Y);
			for (double D = 0.25; D <= 30.0; D += 0.25)
			{
				const double H = Lake.Terrain.HeightAt(Cp.Value.X + FMath::Cos(Ang) * D, Cp.Value.Y + FMath::Sin(Ang) * D);
				if ((H < 0.0) != (Prev < 0.0) || FMath::Abs(Prev) < 1e-6) { Best = FMath::Min(Best, D - 0.125); break; }
				Prev = H;
			}
		}
		if (FMath::Abs(Lake.Terrain.HeightAt(Cp.Value.X, Cp.Value.Y)) < 0.01) Best = 0.0;
		AddInfo(FString::Printf(TEXT("%s: water's edge %.1f m from the map shoreline"), *Cp.Key, Best));
		TestTrue(FString::Printf(TEXT("%s shoreline within 5 m of map data"), *Cp.Key), Best <= 5.0);
	}
	// Depths are lake-like: deepest water near the dam is 10 to 16 m (TWDB 2015 survey: about 40 ft).
	double Deepest = 0.0;
	for (int R = 0; R < Lake.Terrain.GetRows(); R += 4)
		for (int C = 0; C < Lake.Terrain.GetCols(); C += 4)
			Deepest = FMath::Min(Deepest, Lake.Terrain.NodeHeight(R, C));
	AddInfo(FString::Printf(TEXT("Deepest point %.1f m below the conservation pool"), -Deepest));
	TestTrue(TEXT("Deepest water 10 to 16 m"), Deepest < -10.0 && Deepest > -16.0);
	TestTrue(TEXT("Launch spots are in water"), Lake.LaunchSpots.Num() >= 3 && Lake.Terrain.DepthAt(Lake.LaunchSpots[1].X, Lake.LaunchSpots[1].Y) > 1.5);
	TestTrue(TEXT("Bridges and docks became obstacles"), Lake.Obstacles.size() > 100);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGroundingTest, "SailingSim.Lake.RunsAgroundInShallows", Flags)
bool FSailingGroundingTest::RunTest(const FString& Parameters)
{
	const FLakeTerrain Lake = ShelvingLake(100.0, 220.0); // 1.16 m keel touches about 192 m out
	FBoatModel Boat;
	Boat.SetTerrain(&Lake);
	Boat.Reset(30.0, 0.0, 0.0, 4.0 * kKnot); // heading north into the shallows
	const FWindField Wind = WindFrom(10.0, 90.0); // beam reach
	FBoatControls C;
	FAutoTrim Trim;
	bool bEverAground = false;
	SailFor(Boat, C, Wind, 90.0, &Trim, [&] { bEverAground |= Boat.GetTelemetry().bAground; });
	const double X = Boat.OriginPosition().X;
	AddInfo(FString::Printf(TEXT("Stopped at x = %.1f m, %.2f kn, depth under keel %.2f m"), X, Boat.GetTelemetry().BoatSpeed / kKnot, Boat.GetTelemetry().DepthUnderKeel));
	TestTrue(TEXT("Ran aground"), bEverAground);
	TestTrue(TEXT("Stopped by the bottom"), Boat.GetTelemetry().BoatSpeed < 0.6 * kKnot);
	TestTrue(TEXT("Stuck where the water is about as deep as the keel"), X > 170.0 && X < 215.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingObstacleTest, "SailingSim.Lake.DocksAndBridgesStopTheBoat", Flags)
bool FSailingObstacleTest::RunTest(const FString& Parameters)
{
	const FWindField Wind = WindFrom(10.0, 90.0);
	auto RunInto = [&](double Bottom, double Top, double Radius)
	{
		std::vector<FObstacleSegment> Obs(1);
		Obs[0].AX = 60.0; Obs[0].AY = -60.0; Obs[0].BX = 60.0; Obs[0].BY = 60.0;
		Obs[0].Bottom = Bottom; Obs[0].Top = Top; Obs[0].Radius = Radius;
		FBoatModel Boat;
		Boat.SetObstacles(&Obs);
		Boat.Reset(0.0, 0.0, 0.0, 4.0 * kKnot);
		FBoatControls C;
		FAutoTrim Trim;
		bool bHit = false;
		SailFor(Boat, C, Wind, 40.0, &Trim, [&] { bHit |= Boat.GetTelemetry().bCollision; });
		return TPair<double, bool>(Boat.OriginPosition().X, bHit);
	};
	const auto Dock = RunInto(-2.0, 0.8, 0.25);
	TestTrue(TEXT("A dock stops the hull"), Dock.Value && Dock.Key < 60.0);
	const auto LowBridge = RunInto(6.0, 10.0, 8.0);
	TestTrue(TEXT("A 6 m bridge stops the 9.2 m mast"), LowBridge.Value && LowBridge.Key < 62.0);
	const auto HighBridge = RunInto(12.0, 16.0, 8.0);
	AddInfo(FString::Printf(TEXT("Dock: stopped at %.1f m. Low bridge: %.1f m. High bridge: sailed on to %.1f m"), Dock.Key, LowBridge.Key, HighBridge.Key));
	TestTrue(TEXT("A 12 m bridge lets the boat pass under"), !HighBridge.Value && HighBridge.Key > 80.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMooringTest, "SailingSim.Lake.DockLinesHold", Flags)
bool FSailingMooringTest::RunTest(const FString& Parameters)
{
	std::vector<FObstacleSegment> Dock(1);
	Dock[0].AX = -20.0; Dock[0].AY = 2.0; Dock[0].BX = 20.0; Dock[0].BY = 2.0; // a dock along the starboard side
	FBoatModel Boat;
	Boat.SetObstacles(&Dock);
	Boat.Reset(0.0, 0.0, 0.0, 0.0);
	TestTrue(TEXT("Too far from a dock: no lines"), FindDockLines(Boat, Dock, 0.5).empty());
	Boat.GetMooringLines() = FindDockLines(Boat, Dock);
	TestTrue(TEXT("Alongside: lines to at least two cleats"), Boat.GetMooringLines().size() >= 2);
	// 15 kn blowing her off the dock with sails luffing.
	const FWindField Wind = WindFrom(15.0, 90.0);
	FBoatControls C;
	C.MainSheet = C.JibSheet = 1.0;
	double MaxMove = 0.0;
	SailFor(Boat, C, Wind, 60.0, nullptr, [&] { MaxMove = FMath::Max(MaxMove, Boat.OriginPosition().LengthXY()); });
	AddInfo(FString::Printf(TEXT("Moved at most %.2f m in 60 s"), MaxMove));
	TestTrue(TEXT("Stays at the dock"), MaxMove < 2.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShelterTest, "SailingSim.Lake.WindShadowAndFetch", Flags)
bool FSailingShelterTest::RunTest(const FString& Parameters)
{
	// A 15 m wooded bluff along the north shore (X > 600), water to the south, wind from the north.
	const int Rows = 400, Cols = 100;
	std::vector<float> H(Rows * Cols);
	for (int R = 0; R < Rows; ++R) for (int C = 0; C < Cols; ++C) H[R * Cols + C] = R * 2.0 > 600.0 ? 15.0f : -6.0f;
	FLakeTerrain Lake;
	Lake.InitSynthetic(Rows, Cols, 2.0, 0.0, 0.0, H);
	FShelterMap Shelter;
	Shelter.Build(Lake, 0.0, 10.0);
	const double Near = Shelter.FactorAt(560.0, 100.0), Mid = Shelter.FactorAt(400.0, 100.0), Far = Shelter.FactorAt(50.0, 100.0);
	AddInfo(FString::Printf(TEXT("Wind behind a 15 m bluff: %.0f%% at 40 m, %.0f%% at 200 m, %.0f%% at 550 m"), Near * 100, Mid * 100, Far * 100));
	TestTrue(TEXT("Sheltered right under the bluff"), Near < 0.5);
	TestTrue(TEXT("Recovering with distance"), Mid > Near && Far > Mid);
	TestTrue(TEXT("Full wind 35+ heights downwind"), Far > 0.95);

	FWindParams P;
	P.SpeedKnots = 12.0;
	FWindField Wind(P);
	Wind.SetShelter(&Shelter);
	TestTrue(TEXT("The sails feel the shadow"), Wind.VelocityAt(Vec3(560, 100, 5), 0.0).Length() < 0.6 * Wind.VelocityAt(Vec3(50, 100, 5), 0.0).Length());
	TestEqual(TEXT("Fetch to the north shore from 300 m out"), Lake.FetchToward(300.0, 100.0, 0.0), 300.0, 4.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHeaveToTest, "SailingSim.Drills.HeaveTo", Flags)
bool FSailingHeaveToTest::RunTest(const FString& Parameters)
{
	const FWindField Wind = WindFrom(12.0, 0.0);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 4.0 * kKnot);
	FAutopilot Pilot;
	Pilot.TargetTWADeg = 45.0;
	FAutoTrim Trim;
	FBoatControls C;
	C.MainSheet = C.JibSheet = 0.2;
	for (int32 I = 0; I < int32(30 * PhysicsHz); ++I) { C = Trim.Update(Boat, C, PhysicsDt); C.Tiller = Pilot.Update(Boat); Boat.Step(PhysicsDt, C, Wind); }

	FDrillRunner Drill;
	Drill.Start(ESailingDrill::HeaveTo, Boat, 0.0);
	// Back the jib, ease the main, tiller a little to leeward and hold it.
	C.bBackJib = true; C.JibSheet = 0.1; C.MainSheet = 0.8; C.Tiller = 0.5;
	FDrillContext Ctx;
	Ctx.bBackJib = true;
	for (int32 I = 0; I < int32(90 * PhysicsHz) && Drill.IsActive(); ++I) { Boat.Step(PhysicsDt, C, Wind); Drill.Update(Boat, Ctx, PhysicsDt); }
	AddInfo(Drill.GetStatus());
	TestTrue(TEXT("Hove to within 90 s and held it 20 s"), Drill.IsComplete());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingTriangleTest, "SailingSim.Drills.SailATriangle", Flags)
bool FSailingTriangleTest::RunTest(const FString& Parameters)
{
	const FWindField Wind = WindFrom(10.0, 0.0);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -60.0 * kDegToRad, 4.0 * kKnot);
	FDrillRunner Drill;
	Drill.Start(ESailingDrill::SailATriangle, Boat, 0.0);
	FAutoTrim Trim;
	FAutopilot Pilot;
	FBoatControls C;
	int32 Tack = 1;
	// A simple helmsman: steer for the mark; if it is in the no-go zone, sail close-hauled and tack on the layline.
	for (int32 I = 0; I < int32(900 * PhysicsHz) && Drill.IsActive(); ++I)
	{
		const Vec3 O = Boat.OriginPosition();
		const FVector2D M = Drill.GetMarks()[Drill.GetNextMark()];
		const double Bearing = FMath::Atan2(M.Y - O.Y, M.X - O.X);
		const double MarkTwa = FMath::RadiansToDegrees(WrapAngle(0.0 - Bearing));
		if (FMath::Abs(MarkTwa) < 46.0)
		{
			if (FMath::Abs(MarkTwa) > 2.0 && FMath::Sign(MarkTwa) != Tack && FMath::Abs(MarkTwa) > 44.0) Tack = -Tack;
			Pilot.TargetTWADeg = 45.0 * Tack;
		}
		else
		{
			Pilot.TargetTWADeg = MarkTwa;
			Tack = MarkTwa > 0.0 ? 1 : -1;
		}
		C = Trim.Update(Boat, C, PhysicsDt);
		C.Tiller = Pilot.Update(Boat);
		Boat.Step(PhysicsDt, C, Wind);
		Drill.Update(Boat, FDrillContext(), PhysicsDt);
	}
	AddInfo(Drill.GetStatus());
	TestTrue(TEXT("Rounded all three marks within 15 minutes"), Drill.IsComplete());
	return true;
}

namespace
{
	/** What a careful helmsman aims for on a final approach: slower the closer they get (m/s). */
	double ApproachSpeed(double Distance) { return FMath::Clamp(0.06 * Distance, 0.35, 2.0); }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingOverboardTest, "SailingSim.Drills.CrewOverboard", Flags)
bool FSailingOverboardTest::RunTest(const FString& Parameters)
{
	// Quick-stop: head up, circle back and stop alongside, steered by a scripted helmsman.
	const FWindField Wind = WindFrom(10.0, 0.0);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -100.0 * kDegToRad, 5.0 * kKnot);
	FDrillRunner Drill;
	Drill.Start(ESailingDrill::CrewOverboardQuickStop, Boat, 0.0);
	FAutoTrim Trim;
	FAutopilot Pilot;
	Pilot.MaxTiller = 0.7;
	FBoatControls C;
	bool bBelow = false;
	double T = 0.0;
	for (int32 I = 0; I < int32(240 * PhysicsHz) && Drill.IsActive(); ++I, T += PhysicsDt)
	{
		const Vec3 O = Boat.OriginPosition();
		const FVector2D Dmy = Drill.GetDummy();
		const double Dist = FVector2D::Distance(FVector2D(O.X, O.Y), Dmy);
		// Get well downwind of the person first, then come back up on a close reach so luffing can stop the boat.
		// (The wind blows from +X here.)
		if (!bBelow && O.X < Dmy.X - 25.0 && FMath::Abs(O.Y - Dmy.Y) < 25.0) bBelow = true;
		const FVector2D Aim = bBelow ? Dmy : Dmy - FVector2D(35.0, 0.0);
		const double Bearing = FMath::Atan2(Aim.Y - O.Y, Aim.X - O.X);
		const double MarkTwa = FMath::RadiansToDegrees(WrapAngle(0.0 - Bearing));
		if (T < 6.0)
		{
			Pilot.TargetTWADeg = -150.0; // keep going a moment, then circle
		}
		else
		{
			// Steer at the aim point, never higher than 50 degrees off the wind until the last few lengths, then shoot
			// up toward the wind so the luffing sails stop the boat.
			const double Sign = MarkTwa >= 0.0 ? 1.0 : -1.0;
			Pilot.TargetTWADeg = Sign * FMath::Max(FMath::Abs(MarkTwa), bBelow && Dist < 20.0 ? 0.0 : 50.0);
		}
		C = Trim.Update(Boat, C, PhysicsDt);
		// Final approach: luff to bleed speed, trimming in only to keep creeping toward them.
		if (bBelow && Dist < 40.0 && Boat.GetTelemetry().BoatSpeed > ApproachSpeed(Dist)) { C.MainSheet = 1.0; C.JibSheet = 1.0; }
		C.Tiller = Pilot.Update(Boat);
		Boat.Step(PhysicsDt, C, Wind);
		Drill.Update(Boat, FDrillContext(), PhysicsDt);
	}
	AddInfo(Drill.GetStatus());
	TestTrue(TEXT("Recovered the person overboard (stopped within 3 m)"), Drill.IsComplete());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingDockingTest, "SailingSim.Drills.ReturnAndDock", Flags)
bool FSailingDockingTest::RunTest(const FString& Parameters)
{
	// A dock 60 m ahead, wind from ahead-ish: approach on a close reach, luff to slow, get lines on.
	std::vector<FObstacleSegment> Dock(1);
	Dock[0].AX = 60.0; Dock[0].AY = -30.0; Dock[0].BX = 60.0; Dock[0].BY = 30.0;
	const FWindField Wind = WindFrom(8.0, 30.0);
	FBoatModel Boat;
	Boat.SetObstacles(&Dock);
	Boat.Reset(0.0, 0.0, -20.0 * kDegToRad, 3.0 * kKnot);
	FDrillRunner Drill;
	Drill.Start(ESailingDrill::ReturnAndDock, Boat, 30.0 * kDegToRad);
	FBoatControls C;
	FAutoTrim Trim;
	double MaxContact = 0.0;
	bool bTied = false;
	for (int32 I = 0; I < int32(180 * PhysicsHz) && Drill.IsActive(); ++I)
	{
		const Vec3 O = Boat.OriginPosition();
		const double ToDock = 60.0 - O.X;
		// Steer for the dock, luffing the sails as it gets close; turn alongside at the end.
		const double Heading = ToDock > 8.0 ? FMath::Atan2(0.0 - O.Y, ToDock) : 90.0 * kDegToRad;
		C.Tiller = Clamp(2.0 * WrapAngle(Heading - Boat.GetTelemetry().Heading) - 1.0 * Boat.GetState().AngularVelocity.Z, -0.6, 0.6);
		const double Tiller = C.Tiller;
		C = Trim.Update(Boat, C, PhysicsDt);
		C.Tiller = Tiller;
		if (ToDock < 60.0 && Boat.GetTelemetry().BoatSpeed > ApproachSpeed(ToDock)) { C.MainSheet = 1.0; C.JibSheet = 1.0; }
		Boat.Step(PhysicsDt, C, Wind);
		if (Boat.GetTelemetry().bCollision) MaxContact = FMath::Max(MaxContact, Boat.GetTelemetry().BoatSpeed / kKnot);
		if (!bTied && Boat.GetTelemetry().BoatSpeed < 1.0 * kKnot && ToDock < 4.0)
		{
			Boat.GetMooringLines() = FindDockLines(Boat, Dock);
			bTied = !Boat.GetMooringLines().empty();
		}
		FDrillContext Ctx;
		Ctx.bTiedUp = bTied;
		Ctx.MaxContactSpeed = MaxContact;
		Drill.Update(Boat, Ctx, PhysicsDt);
	}
	AddInfo(Drill.GetStatus());
	TestTrue(TEXT("Docked: lines on"), Drill.IsComplete() && bTied);
	TestTrue(TEXT("Gentle contact (under 1.5 kn)"), MaxContact < 1.5);
	return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLakeLevelTest, "SailingSim.Lake.GaugeLevel", Flags)
bool FSailingLakeLevelTest::RunTest(const FString& Parameters)
{
	// At the gauge reading the water is shallower everywhere by the deficit, and some shoals dry out.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	TestTrue(TEXT("A gauge reading is baked in"), !Lake.LevelDate.IsEmpty() && Lake.LevelFeet > 400.0 && Lake.LevelFeet < 440.0);
	const FLaunchSpot& Club = Lake.LaunchSpots[1];
	const double FullDepth = Lake.Terrain.DepthAt(Club.X, Club.Y);
	const double Low = (Lake.PoolFeet - Lake.LevelFeet) * 0.3048;
	Lake.Terrain.SetLevelBelowPool(Low);
	const double GaugeDepth = Lake.Terrain.DepthAt(Club.X, Club.Y);
	AddInfo(FString::Printf(TEXT("Gauge %s: %.2f ft, %.2f m low; depth off Rush Creek %.1f m at full pool, %.1f m today"), *Lake.LevelDate, Lake.LevelFeet, Low, FullDepth, GaugeDepth));
	TestTrue(TEXT("Depth drops by the deficit"), FMath::Abs((FullDepth - GaugeDepth) - Low) < 0.01);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingClubBerthTest, "SailingSim.Lake.ClubBerth", Flags)
bool FSailingClubBerthTest::RunTest(const FString& Parameters)
{
	// Leave-the-dock starts tied up at Rush Creek: the berth must float the boat, and the lines must reach.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	for (const double WindDeg : { 0.0, 90.0, 180.0, 270.0 })
	{
		FVector2D Berth;
		double Heading = 0.0;
		if (!TestTrue(TEXT("A berth near the club"), FindBerth(Lake.Terrain, Lake.Obstacles, FVector2D::ZeroVector, 600.0, WindDeg * kDegToRad, Berth, Heading))) return false;
		FBoatModel Boat;
		Boat.SetTerrain(&Lake.Terrain);
		Boat.SetObstacles(&Lake.Obstacles);
		Boat.Reset(Berth.X, Berth.Y, Heading, 0.0);
		Boat.GetMooringLines() = FindDockLines(Boat, Lake.Obstacles);
		FBoatControls C;
		C.MainSheet = C.JibSheet = 1.0;
		const FWindField Wind = WindFrom(12.0, WindDeg);
		bool bAground = false, bHit = false;
		for (int32 I = 0; I < int32(20 * PhysicsHz); ++I) { Boat.Step(PhysicsDt, C, Wind); bAground |= Boat.GetTelemetry().bAground; bHit |= Boat.GetTelemetry().BoatSpeed > 0.5 * kKnot && Boat.GetTelemetry().bCollision; }
		AddInfo(FString::Printf(TEXT("Wind from %.0f: berth at (%.0f, %.0f) m, %.1f m from the club, %d lines, %.1f m under the keel"), WindDeg, Berth.X, Berth.Y, Berth.Size(),
			int32(Boat.GetMooringLines().size()), Boat.GetTelemetry().DepthUnderKeel));
		TestTrue(TEXT("Lines reach the dock"), Boat.GetMooringLines().size() >= 2);
		TestFalse(TEXT("Afloat at the berth"), bAground);
		TestFalse(TEXT("Lies quietly against the dock"), bHit);
	}
	return true;
}

#endif
