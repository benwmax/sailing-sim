#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "AutoTrim.h"
#include "Drills.h"
#include "FixedStepper.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "Marina.h"
#include "WorldKit.h"

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

// Graphics G2: the 1 m lidar shore detail loads, covers the shore near the club, agrees with the 5 m grid away from the
// water's edge (same survey, finer), and has no steps: along transects, neighbouring 1 m samples never jump more than
// the steepest real bank does.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShoreDetailTest, "SailingSim.Lake.ShoreDetail", Flags)
bool FSailingShoreDetailTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	if (!TestTrue(TEXT("Shore detail loaded"), T.HasDetail())) return false;
	TestTrue(TEXT("Detail covers the shore within 2 km of the club"), T.HasDetailIn(-2000.0, -2000.0, 2000.0, 2000.0));
	TArray<double> LandDiff;
	int32 Steps = 0, BigSteps = 0, Edges = 0;
	double WorstSeam = 0.0;
	FRandomStream Rng(7);
	const double Span = 64.0 * T.GetDetailCell();
	for (int32 K = 0; K < 3000; ++K)
	{
		const double X = Rng.FRandRange(-6000.0, 6000.0), Y = Rng.FRandRange(-6000.0, 6000.0);
		double Fine;
		if (!T.DetailHeightAt(X, Y, Fine)) continue;
		// The grid's own value, by its nodes (HeightAt prefers the detail).
		const double R = (X - T.GetOriginX()) / T.GetCell(), C = (Y - T.GetOriginY()) / T.GetCell();
		const int32 R0 = FMath::FloorToInt(R), C0 = FMath::FloorToInt(C);
		const double Coarse = FMath::Lerp(FMath::Lerp(T.NodeHeight(R0, C0), T.NodeHeight(R0, C0 + 1), C - C0), FMath::Lerp(T.NodeHeight(R0 + 1, C0), T.NodeHeight(R0 + 1, C0 + 1), C - C0), R - R0);
		if (Coarse > 2.0 && Fine > 2.0) LandDiff.Add(FMath::Abs(Fine - Coarse));
		// A transect across tiles and the band's edge: steps over 1.5 m per metre are walls (bulkheads, the dam), rare.
		double Prev = T.HeightAt(X, Y);
		for (int32 S = 1; S <= 80; ++S)
		{
			const double H = T.HeightAt(X + S, Y + 0.5 * S);
			++Steps;
			BigSteps += FMath::Abs(H - Prev) > 1.5 * FMath::Sqrt(1.25);
			Prev = H;
		}
		// The next tile edge north: both sides of it give the same height.
		const double Edge = T.GetOriginX() + FMath::CeilToDouble((X - T.GetOriginX()) / Span) * Span;
		double A, B;
		if (T.DetailHeightAt(Edge - 1e-6, Y, A) && T.DetailHeightAt(Edge + 1e-6, Y, B)) { WorstSeam = FMath::Max(WorstSeam, FMath::Abs(A - B)); ++Edges; }
	}
	LandDiff.Sort();
	const double Median = LandDiff.Num() ? LandDiff[LandDiff.Num() / 2] : 99.0;
	const double WallShare = Steps ? double(BigSteps) / Steps : 1.0;
	AddInfo(FString::Printf(TEXT("%d detail points; land |1 m - 5 m| median %.2f m; steps over 1.5 m %.3f%%; %d tile edges, worst seam %.3f m"),
		LandDiff.Num(), Median, WallShare * 100.0, Edges, WorstSeam));
	TestTrue(TEXT("Some of the sample points are in the shore band"), Steps > 8000);
	TestTrue(FString::Printf(TEXT("Land agrees with the 5 m grid (median %.2f m)"), Median), Median < 0.35);
	TestTrue(FString::Printf(TEXT("Walls are rare (%.3f%% of 1 m steps)"), WallShare * 100.0), WallShare < 0.002);
	TestTrue(FString::Printf(TEXT("Tiles meet without a seam (%.3f m)"), WorstSeam), Edges > 20 && WorstSeam < 0.02);
	return true;
}

/**
 * Graphics G6: the shore's houses from the G2 footprints (Tools/terrain/build_houses.py, HouseKit.cpp). They load with
 * the lake; the full-detail band is the houses within 400 m of the water; every wall faces out of its wing, every roof
 * plane faces up; a lidar ridge is kept; windows and doors only on the outside walls.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHousesTest, "SailingSim.Lake.Houses", Flags)
bool FSailingHousesTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	if (!TestTrue(TEXT("The G2 houses load (RayHubbard.houses)"), Lake.Houses.Num() > 30000)) return false;
	int32 Full = 0, Lidar = 0, Wings = 0;
	for (const FLakeHouse& H : Lake.Houses) { Full += H.bFullDetail; Lidar += H.bLidar; Wings += H.Wings.Num(); }
	AddInfo(FString::Printf(TEXT("%d houses, %d in the full-detail band, %d with lidar roofs, %d wings"), Lake.Houses.Num(), Full, Lidar, Wings));
	TestTrue(TEXT("About a third within 400 m of the water"), Full > Lake.Houses.Num() / 5 && Full < Lake.Houses.Num() / 2);
	TestTrue(TEXT("Most roofs measured by the lidar"), Lidar > Lake.Houses.Num() * 3 / 4);
	// The houses of one tile near the club, built as the game draws them.
	TMap<FIntPoint, TArray<int32>> Tiles;
	HouseTiles(Lake, Tiles);
	const TArray<int32>* Busiest = nullptr;
	for (const auto& KV : Tiles) if (FMath::Abs(KV.Key.X) <= 4 && FMath::Abs(KV.Key.Y) <= 4 && (!Busiest || KV.Value.Num() > Busiest->Num())) Busiest = &KV.Value;
	if (!TestNotNull(TEXT("A tile of houses near the club"), Busiest)) return false;
	FKitGeometry G;
	BuildHouseGeometry(Lake, *Busiest, G);
	const FKitSection& Wall = G[EKitLook::HouseWall];
	const FKitSection& Roof = G[EKitLook::HouseRoof];
	TestTrue(TEXT("Walls and roofs built"), Wall.V.Num() > 0 && Roof.V.Num() > 0);
	TestTrue(TEXT("Colour and tag per vertex"), Wall.Col.Num() == Wall.V.Num() && Wall.UV1.Num() == Wall.V.Num() && Roof.Col.Num() == Roof.V.Num());
	int32 RoofDown = 0;
	for (const FVector& N : Roof.N) RoofDown += N.Z < -0.01;
	TestEqual(TEXT("No roof plane faces down"), RoofDown, 0);
	// Each wing's four walls (the first quads per wing are its walls, in order): horizontal normals, facing out.
	int32 Inward = 0, Checked = 0, OpeningsInside = 0;
	for (const int32 K : *Busiest)
	{
		const FLakeHouse& H = Lake.Houses[K];
		for (const FLakeHouse::FWing& W : H.Wings)
		{
			const FVector2D C(W.X, W.Y);
			for (int32 Q = 0; Q + 3 < Wall.V.Num(); Q += 4)
			{
				const FVector Mid = 0.25 * (Wall.V[Q] + Wall.V[Q + 1] + Wall.V[Q + 2] + Wall.V[Q + 3]) / 100.0;
				const FVector2D D = FVector2D(Mid) - C;
				const double Yaw = FMath::DegreesToRadians(W.YawDeg);
				const double A = D.X * FMath::Cos(Yaw) + D.Y * FMath::Sin(Yaw), B = -D.X * FMath::Sin(Yaw) + D.Y * FMath::Cos(Yaw);
				// Quads on this wing's own wall planes (within 2 cm of one, inside its extent).
				const bool bOnLong = FMath::Abs(FMath::Abs(B) - W.HalfWidth) < 0.02 && FMath::Abs(A) < W.HalfLength - 0.1;
				const bool bOnEnd = FMath::Abs(FMath::Abs(A) - W.HalfLength) < 0.02 && FMath::Abs(B) < W.HalfWidth - 0.1;
				if (!bOnLong && !bOnEnd || FMath::Abs(Wall.N[Q].Z) > 0.01) continue;
				++Checked;
				Inward += FVector2D::DotProduct(FVector2D(Wall.N[Q]), D) < 0.0;
			}
		}
		// Glass (finish 3) and doors never inside another wing of the same house.
		for (int32 Q = 0; Q + 3 < Wall.V.Num(); Q += 4)
		{
			if (Wall.Col[Q].A < 3) continue;
			const FVector2D Mid = FVector2D(0.25 * (Wall.V[Q] + Wall.V[Q + 1] + Wall.V[Q + 2] + Wall.V[Q + 3]) / 100.0) + FVector2D(Wall.N[Q]) * 0.3;
			for (const FLakeHouse::FWing& W : H.Wings)
			{
				const double Yaw = FMath::DegreesToRadians(W.YawDeg);
				const FVector2D D = Mid - FVector2D(W.X, W.Y);
				if (FMath::Abs(D.X * FMath::Cos(Yaw) + D.Y * FMath::Sin(Yaw)) < W.HalfLength - 0.3 && FMath::Abs(-D.X * FMath::Sin(Yaw) + D.Y * FMath::Cos(Yaw)) < W.HalfWidth - 0.3) ++OpeningsInside;
			}
		}
	}
	AddInfo(FString::Printf(TEXT("Tile of %d houses: %d wall quads checked, %d facing in; %d roof quads"), Busiest->Num(), Checked, Inward, Roof.V.Num() / 4));
	TestTrue(TEXT("Walls checked"), Checked > 4 * Busiest->Num());
	TestEqual(TEXT("Every wall faces out of its wing"), Inward, 0);
	TestEqual(TEXT("No window or door inside another wing"), OpeningsInside, 0);
	// A lidar ridge: the main wing's highest roof vertex is the measured ridge (within the eave overhang's drop).
	int32 RidgeChecked = 0, RidgeOff = 0;
	for (const int32 K : *Busiest)
	{
		const FLakeHouse& H = Lake.Houses[K];
		if (!H.bLidar || H.Roof != FLakeHouse::Hip || H.Ridge <= H.Eave + 0.5f || H.Wings.Num() != 1) continue;
		FKitGeometry One;
		BuildHouseGeometry(Lake, TArray<int32>({ K }), One);
		double Top = -1e9, Ground = FMath::Max(double(Lake.Terrain.HeightAt(H.X, H.Y)), 0.15);
		for (const FVector& V : One[EKitLook::HouseRoof].V) Top = FMath::Max(Top, V.Z / 100.0);
		++RidgeChecked;
		RidgeOff += FMath::Abs(Top - Ground - H.Ridge) > 0.6;
	}
	AddInfo(FString::Printf(TEXT("%d lidar hip ridges checked, %d off by over 0.6 m"), RidgeChecked, RidgeOff));
	TestTrue(TEXT("Lidar ridges kept"), RidgeChecked > 3 && RidgeOff * 10 <= RidgeChecked);
	return true;
}

/**
 * Graphics G6: the shore's trees from the G2 lidar crowns (Tools/terrain/build_crowns.py). They load with the lake; every
 * placed crown keeps its measured height and a width near its crown radius; none stands in the water; the canopy-map
 * trees stay only outside the crowns' band; tall crowns are not all one species.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCrownsTest, "SailingSim.Lake.Crowns", Flags)
bool FSailingCrownsTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	if (!TestTrue(TEXT("The lidar crowns load (RayHubbard.crowns)"), Lake.Crowns.Num() > 100000)) return false;
	int32 Full = 0, Cedar = 0;
	for (const FLakeCrown& C : Lake.Crowns) { Full += C.bFullDetail; Cedar += C.bCedar; }
	AddInfo(FString::Printf(TEXT("%d crowns, %d within 400 m of the water, %d red cedar"), Lake.Crowns.Num(), Full, Cedar));
	TestTrue(TEXT("Most kept crowns are in the full-detail band"), Full > Lake.Crowns.Num() / 2);
	TArray<FTreeInstance> Trees;
	PlaceCrownTrees(Lake.Terrain, Lake.Crowns, 1.f, Trees);
	TSet<FIntPoint> CrownCells;
	for (const FLakeCrown& C : Lake.Crowns) CrownCells.Add(FIntPoint(FMath::FloorToInt32(C.X / 100.f), FMath::FloorToInt32(C.Y / 100.f)));
	int32 Placed = 0, InWater = 0, MapInBand = 0, TooTall = 0, Tall = 0;
	int32 TallSpecies[int32(ETreeSpecies::Count)] = {};
	for (const FTreeInstance& I : Trees)
	{
		InWater += Lake.Terrain.HeightAt(I.Position.X, I.Position.Y) < 0.0;
		if (I.Crown > 0.f)
		{
			++Placed;
			TooTall += I.Height > 30.f;
			if (I.Height > 14.f) { ++Tall; TallSpecies[int32(I.Species)]++; }
		}
		else MapInBand += CrownCells.Contains(FIntPoint(FMath::FloorToInt32(I.Position.X / 100.0), FMath::FloorToInt32(I.Position.Y / 100.0)));
	}
	AddInfo(FString::Printf(TEXT("%d trees: %d from crowns, %d tall (post oak %d, live oak %d, cedar elm %d)"), Trees.Num(), Placed, Tall,
		TallSpecies[int32(ETreeSpecies::PostOak)], TallSpecies[int32(ETreeSpecies::LiveOak)], TallSpecies[int32(ETreeSpecies::CedarElm)]));
	TestTrue(TEXT("Nearly every crown on land placed"), Placed > Lake.Crowns.Num() * 9 / 10);
	TestEqual(TEXT("No tree in the water"), InWater, 0);
	TestEqual(TEXT("No crown over 30 m"), TooTall, 0);
	TestEqual(TEXT("No canopy-map tree inside the crowns' band"), MapInBand, 0);
	TestTrue(TEXT("Tall crowns of more than one species"), TallSpecies[int32(ETreeSpecies::PostOak)] < Tall * 3 / 4 && TallSpecies[int32(ETreeSpecies::LiveOak)] > Tall / 10);
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
	FAutopilot Helm; // someone has to steer: she carries weather helm and rounds up if the tiller is let go
	Helm.TargetTWADeg = 90.0;
	bool bEverAground = false;
	SailFor(Boat, C, Wind, 90.0, &Trim, [&] { C.Tiller = Helm.Update(Boat); bEverAground |= Boat.GetTelemetry().bAground; });
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
		FAutopilot Helm; // steered on a beam reach (with the tiller let go she would round up)
		Helm.TargetTWADeg = 90.0;
		bool bHit = false;
		SailFor(Boat, C, Wind, 40.0, &Trim, [&] { C.Tiller = Helm.Update(Boat); bHit |= Boat.GetTelemetry().bCollision; });
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
	AddInfo(FString::Printf(TEXT("Wind behind a 15 m bluff: %.0f%% at 40 m, %.0f%% at 200 m, %.0f%% at 550 m (lee %.0f%%, open-water build %.0f%%)"),
		Near * 100, Mid * 100, Far * 100, Shelter.LeeAt(50.0, 100.0) * 100, Shelter.BuildAt(50.0, 100.0) * 100));
	TestTrue(TEXT("Sheltered right under the bluff"), Near < 0.5);
	TestTrue(TEXT("Recovering with distance"), Mid > Near && Far > Mid);
	// W1: the lee has gone 35 heights downwind; W3 (W6's LES): by 550 m of open water the wind has all but built.
	TestTrue(TEXT("No lee 35+ heights downwind"), Shelter.LeeAt(50.0, 100.0) > 0.98);
	TestTrue(TEXT("... the wind built from the shore"), Far > 0.97 && Far < 1.0);

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
	// Back the jib and ease the main, hold her course while the backed jib takes her way off, then put the tiller to
	// leeward and hold it. (With the tiller over at full speed she carries her way through the wind and tacks.)
	C.bBackJib = true; C.JibSheet = 0.1; C.MainSheet = 0.8; C.Tiller = 0.0;
	FDrillContext Ctx;
	Ctx.bBackJib = true;
	for (int32 I = 0; I < int32(90 * PhysicsHz) && Drill.IsActive(); ++I)
	{
		if (I == int32(6 * PhysicsHz)) C.Tiller = 0.3;
		Boat.Step(PhysicsDt, C, Wind);
		Drill.Update(Boat, Ctx, PhysicsDt);
	}
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


IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMarinaTest, "SailingSim.Lake.Marina", Flags)
bool FSailingMarinaTest::RunTest(const FString& Parameters)
{
	// Visual V6: the drawn marina (AMarinaActor) and the physics see the same docks; the home slip floats a J/22.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FMarina& M = Lake.Marina;
	if (!TestTrue(TEXT("Marina loads"), M.IsLoaded())) return false;
	TestTrue(TEXT("Over a hundred slips"), M.Slips.Num() > 100);
	if (!TestTrue(TEXT("Home slip"), M.HomeSlip != INDEX_NONE)) return false;
	const FMarinaSlip& Home = M.Slips[M.HomeSlip];
	TestFalse(TEXT("Home slip is free"), Home.bOccupied);
	auto Covered = [&](const FVector2D& P, double Clear)
	{
		for (const FObstacleSegment& O : Lake.Obstacles)
		{
			const FVector2D A(O.AX, O.AY), B(O.BX, O.BY);
			const FVector2D AB = B - A;
			const double T = FMath::Clamp(FVector2D::DotProduct(P - A, AB) / FMath::Max(AB.SizeSquared(), 1e-9), 0.0, 1.0);
			if (FVector2D::Distance(P, A + AB * T) <= O.Radius + Clear) return true;
		}
		return false;
	};
	int32 Missing = 0, Shallow = 0;
	M.ForEachObstacleLine([&](const TArray<FVector2D>& Pts, const FString&, float)
	{
		for (int32 I = 1; I < Pts.Num(); ++I)
			for (double T = 0.0; T <= 1.0; T += 0.1) Missing += Covered(FMath::Lerp(Pts[I - 1], Pts[I], T), 0.05) ? 0 : 1;
	});
	for (const FMarinaSlip& S : M.Slips) Shallow += Lake.Terrain.HeightAt(S.Center.X, S.Center.Y) > -1.2 ? 1 : 0;
	const double HomeDepth = -Lake.Terrain.HeightAt(Home.Center.X, Home.Center.Y);
	AddInfo(FString::Printf(TEXT("%d slips (%d occupied), home %s at (%.1f, %.1f) in %.1f m; %d slips under 1.2 m"), M.Slips.Num(),
		M.Slips.FilterByPredicate([](const FMarinaSlip& S) { return S.bOccupied; }).Num(), *Home.Id, Home.Center.X, Home.Center.Y, HomeDepth, Shallow));
	TestEqual(TEXT("Every drawn deck is an obstacle"), Missing, 0);
	TestTrue(TEXT("The home slip floats a J/22"), HomeDepth > 1.2);
	// Moored in the home slip, the boat lies between its fingers without touching them.
	FBoatModel Boat;
	Boat.SetTerrain(&Lake.Terrain);
	Boat.SetObstacles(&Lake.Obstacles);
	Boat.Reset(Home.Center.X, Home.Center.Y, FMath::DegreesToRadians(Home.HeadingDeg), 0.0);
	Boat.GetMooringLines() = FindDockLines(Boat, Lake.Obstacles);
	FBoatControls C;
	bool bHit = false;
	const FWindField Wind = WindFrom(8.0, 180.0);
	for (int32 I = 0; I < int32(20 * PhysicsHz); ++I)
	{
		Boat.Step(PhysicsDt, C, Wind);
		const bool bNow = Boat.GetTelemetry().BoatSpeed > 0.5 * kKnot && Boat.GetTelemetry().bCollision;
		if (bNow && !bHit)
		{
			AddInfo(FString::Printf(TEXT("Struck at %.2f s, (%.2f, %.2f) heading %.0f, speed %.2f m/s, %d lines"), I * PhysicsDt, Boat.GetState().Position.X, Boat.GetState().Position.Y,
				FMath::RadiansToDegrees(Boat.GetTelemetry().Heading), Boat.GetTelemetry().BoatSpeed, int32(Boat.GetMooringLines().size())));
		}
		bHit |= bNow;
	}
	TestTrue(TEXT("Lines reach the fingers"), Boat.GetMooringLines().size() >= 2);
	TestFalse(TEXT("Lies quietly in the home slip"), bHit);
	return true;
}

#endif
