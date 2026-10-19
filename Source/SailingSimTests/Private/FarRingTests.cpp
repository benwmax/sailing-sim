#include "Misc/AutomationTest.h"
#include "FarRing.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "WorldKit.h"
#include "Engine/StaticMesh.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UObject/UObjectGlobals.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags FarFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** The near terrain as ALakeTerrainActor draws it at 5 km and beyond: every 8th grid node, two triangles a cell. */
	double NearDrawnHeight(const Sailing::FLakeTerrain& T, double X, double Y)
	{
		constexpr int32 Step = 8;
		const double R = (X - T.GetOriginX()) / T.GetCell() / Step, C = (Y - T.GetOriginY()) / T.GetCell() / Step;
		const int32 R0 = FMath::FloorToInt32(R), C0 = FMath::FloorToInt32(C);
		const double FR = R - R0, FC = C - C0;
		const double H00 = T.NodeHeight(R0 * Step, C0 * Step), H01 = T.NodeHeight(R0 * Step, (C0 + 1) * Step);
		const double H10 = T.NodeHeight((R0 + 1) * Step, C0 * Step), H11 = T.NodeHeight((R0 + 1) * Step, (C0 + 1) * Step);
		return FR + FC <= 1.0 ? H00 + FC * (H01 - H00) + FR * (H10 - H00) : H11 + (1.0 - FC) * (H10 - H11) + (1.0 - FR) * (H01 - H11);
	}
}

/**
 * Wide World Rendering PR 1 (docs/world-far): the far coast ring on Galveston Bay and the Gulf. The tiles cover the band
 * from the hand-over to the outer edge around any camera in the grid; inside the grid the ring's heights are the grid's
 * (within 1 m at the 8 km hand-over); its curvature is the water's; nothing of it shows inside the hand-over (buried under
 * the water, whole tiles hidden) and the near chunks stop there; its tiles load without blocking the game thread.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFarRingTest, "SailingSim.World.FarRing", FarFlags)
bool FSailingFarRingTest::RunTest(const FString& Parameters)
{
	for (const TCHAR* World : { TEXT("GalvestonBay"), TEXT("GulfPassage"), TEXT("Marseille") })
	{
		FLakeData Lake;
		FFarRingData Ring;
		if (!TestTrue(FString::Printf(TEXT("%s loads"), World), Lake.Load(FLakeData::DefaultDirectory(), World))) return false;
		if (!TestTrue(FString::Printf(TEXT("%s.far loads"), World), Ring.Load(FFarRingData::PathFor(World), true))) return false;
		const Sailing::FLakeTerrain& T = Lake.Terrain;
		TestEqual(FString::Printf(TEXT("%s hands over at 8 km"), World), Ring.InnerM, 8000.0);
		const bool bMarseille = FCString::Strcmp(World, TEXT("Marseille")) == 0;
		TestEqual(FString::Printf(TEXT("%s reaches its outer edge (40 km on the Texas coast, Marseille's 60)"), World), Ring.OuterM, bMarseille ? 60000.0 : 40000.0);
		const double X0 = T.GetOriginX(), Y0 = T.GetOriginY();
		const double X1 = X0 + (T.GetRows() - 1) * T.GetCell(), Y1 = Y0 + (T.GetCols() - 1) * T.GetCell();

		// Coverage: from cameras across the grid, points in the band. A point on land (the grid's, where it has one) lies in
		// a tile, and every tile a band point falls in is drawn for that camera.
		FRandomStream Rng(31);
		int32 Points = 0, LandPoints = 0, Uncovered = 0, Hidden = 0;
		for (int32 K = 0; K < 4000; ++K)
		{
			const FVector2D Cam(Rng.FRandRange(X0, X1), Rng.FRandRange(Y0, Y1));
			const double R = Rng.FRandRange(Ring.InnerM + 50.0, Ring.OuterM - 50.0), A = Rng.FRandRange(0.0, 2.0 * UE_DOUBLE_PI);
			const FVector2D P = Cam + R * FVector2D(FMath::Cos(A), FMath::Sin(A));
			++Points;
			const int32 Tile = Ring.FindTile(FMath::FloorToInt32(P.X / Ring.TileM), FMath::FloorToInt32(P.Y / Ring.TileM));
			const bool bInGrid = P.X > X0 && P.X < X1 && P.Y > Y0 && P.Y < Y1;
			if (bInGrid && T.HeightAt(P.X, P.Y) > 0.5)
			{
				++LandPoints;
				Uncovered += Tile == INDEX_NONE;
			}
			if (Tile != INDEX_NONE) Hidden += !FarRing::TileVisible(Ring, Ring.Tiles[Tile], Cam);
		}
		AddInfo(FString::Printf(TEXT("%s: %d tiles; %d band points (%d on the grid's land): %d uncovered, %d in hidden tiles"), World, Ring.Tiles.Num(), Points, LandPoints, Uncovered, Hidden));
		TestEqual(FString::Printf(TEXT("%s: the grid's land in the band lies in a tile"), World), Uncovered, 0);
		TestEqual(FString::Printf(TEXT("%s: every band point's tile is drawn"), World), Hidden, 0);

		// Seams: at the hand-over (8 km from a camera), inside the grid, the ring's nodes carry the grid's heights and its
		// mesh between them stays within 1 m of the near terrain (95%; the near terrain at 8 km is meshed every 80 m on the
		// bay, 400 m in the Gulf).
		double WorstNode = 0.0;
		TArray<double> Between, Drawn;
		for (int32 K = 0; K < 3000; ++K)
		{
			const FVector2D Cam(Rng.FRandRange(X0, X1), Rng.FRandRange(Y0, Y1));
			const double A = Rng.FRandRange(0.0, 2.0 * UE_DOUBLE_PI);
			const FVector2D P = Cam + Ring.InnerM * FVector2D(FMath::Cos(A), FMath::Sin(A));
			if (P.X < X0 + 1000.0 || P.X > X1 - 1000.0 || P.Y < Y0 + 1000.0 || P.Y > Y1 - 1000.0) continue;
			const int32 Tile = Ring.FindTile(FMath::FloorToInt32(P.X / Ring.TileM), FMath::FloorToInt32(P.Y / Ring.TileM));
			if (Tile == INDEX_NONE) continue;
			const FFarRingTile& FT = Ring.Tiles[Tile];
			const double Step = Ring.TileM / FT.Cells;
			const int32 NR = FMath::RoundToInt32((P.X - FT.Row * Ring.TileM) / Step), NC = FMath::RoundToInt32((P.Y - FT.Col * Ring.TileM) / Step);
			if (NR <= 0 || NC <= 0 || NR >= FT.Cells || NC >= FT.Cells) continue;   // edges of a fine tile follow a coarse neighbour
			const double NX = FT.Row * Ring.TileM + NR * Step, NY = FT.Col * Ring.TileM + NC * Step;
			const double Grid = T.HeightAt(NX, NY);
			if (Grid < -1.0) continue;   // the bed under the water is never seen
			WorstNode = FMath::Max(WorstNode, FMath::Abs(Ring.NodeHeight(Tile, NR, NC) - Grid));
			double Far;
			if (Ring.HeightAt(P.X, P.Y, Far))
			{
				Between.Add(FMath::Abs(Far - T.HeightAt(P.X, P.Y)));
				Drawn.Add(FMath::Abs(Far - NearDrawnHeight(T, P.X, P.Y)));
			}
		}
		Between.Sort();
		Drawn.Sort();
		const double P95 = Between.Num() ? Between[Between.Num() * 95 / 100] : 99.0;
		const double DrawnP95 = Drawn.Num() ? Drawn[Drawn.Num() * 95 / 100] : 99.0;
		AddInfo(FString::Printf(TEXT("%s seams at 8 km: worst node %.3f m; between nodes against the 10 m grid median %.2f m, 95%% %.2f m; against the near terrain as drawn there (80 m) 95%% %.2f m (%d points)"),
			World, WorstNode, Between.Num() ? Between[Between.Num() / 2] : 99.0, P95, DrawnP95, Between.Num()));
		TestTrue(FString::Printf(TEXT("%s: the ring's nodes are the grid's heights"), World), WorstNode < Ring.Unit + 0.01);
		// The Texas coasts are flat: the 90 m mesh is within 1 m of the 10 m grid. Marseille's hills are not (a 90 m mesh can't
		// follow a 10 m ridge): there the ring is held to what the near terrain itself draws at 8 km.
		TestTrue(FString::Printf(TEXT("%s: the ring meets the near terrain within 1 m"), World), Between.Num() > 100 && (bMarseille ? DrawnP95 : P95) < (bMarseille ? 12.0 : 1.0));
	}

	// Curvature: the far land drops as the water and every other far thing does (CurvatureDrop; the water's CURVATURE_CODE).
	FString Script;
	if (TestTrue(TEXT("make_materials.py readable"), FFileHelper::LoadFileToString(Script, *FPaths::Combine(FPaths::ProjectDir(), TEXT("scripts/make_materials.py")))))
	{
		auto Block = [&](const TCHAR* Name)
		{
			const int32 At = Script.Find(FString(Name) + TEXT(" = \"\"\""));
			if (At == INDEX_NONE) return FString();
			const int32 End = Script.Find(TEXT("\"\"\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, At + FCString::Strlen(Name) + 6);
			return Script.Mid(At, End - At);
		};
		const FString Water = Block(TEXT("CURVATURE_CODE")), Far = Block(TEXT("FAR_LAND_WPO"));
		TestTrue(TEXT("The water's curvature is d^2 / (2 x 7.433e8 cm)"), Water.Contains(TEXT("dot(d, d) / (2.0 * 7.433e8)")));
		TestTrue(TEXT("The far land's curvature is the water's"), Far.Contains(TEXT("dot(d2, d2) / (2.0 * 7.433e8)")));
		TestTrue(TEXT("M_FarLand buries at FarRing::BuryZ"), Far.Contains(FString::Printf(TEXT("(%.1f)"), FarRing::BuryZ * 100.0)));
		TestTrue(TEXT("M_FarLand sinks FarRing::UnderM"), Far.Contains(FString::Printf(TEXT("%.1f * (1.0 - smoothstep(BandCm, BandCm + %.1f, d))"), FarRing::UnderM * 100.0, FarRing::RiseM * 100.0)));
		TestTrue(TEXT("M_FarLand buries inside InnerCm less FarRing::SinkMarginM"), Far.Contains(FString::Printf(TEXT("InnerCm - %.1f"), FarRing::SinkMarginM * 100.0)));
	}
	for (const double D : { 9000.0, 15000.0, 30000.0, 45000.0 })
	{
		const double Off = FarRing::OffsetZ(D, 5.0, 8000.0, FarRing::BandEndM(8000.0, 1280.0));
		TestTrue(FString::Printf(TEXT("Curvature at %.0f km"), D / 1000.0), FMath::Abs(Off + CurvatureDrop(D)) <= FarRing::UnderM + 1e-9);
	}
	TestEqual(TEXT("Past the band only the curvature"), FarRing::OffsetZ(30000.0, 5.0, 8000.0, 9810.0), -CurvatureDrop(30000.0), 1e-9);

	// Nothing inside 8 km: any far vertex there (up to the Gulf coast's 300 m bluffs and well past) ends under the water, below
	// what light comes back from; a tile wholly inside is not drawn; and the near chunks stop at 8 km.
	bool bBuried = true;
	for (double D = 0.0; D < 8000.0 - FarRing::SinkMarginM; D += 97.0)
	{
		for (const double Z : { -1.0, 0.0, 12.0, 80.0, 300.0 }) bBuried &= Z + FarRing::OffsetZ(D, Z, 8000.0, 9810.0) <= FarRing::BuryZ + 1e-9;
	}
	TestTrue(TEXT("The far land is buried inside the hand-over"), bBuried);
	FFarRingData Square;
	Square.TileM = 8000.0;
	Square.InnerM = 8000.0;
	FFarRingTile Inside;
	Inside.Row = 0;
	Inside.Col = 0;
	TestFalse(TEXT("A tile within 7.8 km of the camera everywhere is hidden"), FarRing::TileVisible(Square, Inside, FVector2D(4000.0, 4000.0)));
	TestTrue(TEXT("A tile reaching past the hand-over is drawn"), FarRing::TileVisible(Square, Inside, FVector2D(1000.0, 1000.0)));
	TestTrue(TEXT("Near chunks within 8 km are drawn"), FarRing::NearChunkDrawn(7999.0, 8000.0));
	TestFalse(TEXT("Near chunks past 8 km are not"), FarRing::NearChunkDrawn(8000.0, 8000.0));

	// The tiles load without blocking: Start and Poll return at once, the meshes arrive by asynchronous loads.
	FFarRingLoader Loader;
	const double T0 = FPlatformTime::Seconds();
	if (!TestTrue(TEXT("The loader starts on Galveston Bay"), Loader.Start(TEXT("GalvestonBay")))) return false;
	const double StartMs = (FPlatformTime::Seconds() - T0) * 1000.0;
	TArray<TPair<int32, UStaticMesh*>> Arrived;
	const double Deadline = FPlatformTime::Seconds() + 120.0;
	while (!Loader.IsDone() && FPlatformTime::Seconds() < Deadline)
	{
		Loader.Poll();
		Loader.TakeArrived(Arrived);
		if (Loader.NumRequested() > 0) FlushAsyncLoading();
		else FPlatformProcess::Sleep(0.001f);
	}
	Loader.TakeArrived(Arrived);
	AddInfo(FString::Printf(TEXT("Loader: start %.2f ms, longest game-thread call %.2f ms; %d of %d tiles arrived, %d failed"), StartMs, Loader.LongestCallMs(),
		Arrived.Num(), Loader.NumRequested(), Loader.NumFailed()));
	TestTrue(TEXT("Every tile's request answered"), Loader.IsDone());
	TestTrue(TEXT("Every tile's mesh arrived"), Loader.NumRequested() > 0 && Arrived.Num() == Loader.NumRequested());
	TestTrue(TEXT("The game thread never waits more than 4 ms on the loader"), Loader.LongestCallMs() < 4.0);
	bool bNanite = Arrived.Num() > 0;
	for (const TPair<int32, UStaticMesh*>& A : Arrived) bNanite &= A.Value && A.Value->IsNaniteEnabled();
	TestTrue(TEXT("The tiles are Nanite meshes"), bNanite);
	Loader.Reset();
	return true;
}

#endif
