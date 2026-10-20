#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "Ocean.h"
#include "SeaState.h"
#include "SailboatPawn.h"
#include "SailingFrame.h"
#include "WaterSurface.h"
#include "WorldStream.h"
#include "WorldStreaming.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace WorldStreamingTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** A world's lat/lon to its map frame. */
	FVector2D MapOf(const FLakeData& Lake, double LatDeg, double LonDeg)
	{
		const Sailing::FMapPoint P = Lake.Anchor.ToMap({ LatDeg, LonDeg });
		return FVector2D(P.North, P.East);
	}

	/** A whole-grid world's terrain on its own (no json, no houses). */
	bool LoadGrid(const FString& Name, Sailing::FLakeTerrain& Out)
	{
		TArray<uint8> Bytes;
		return FFileHelper::LoadFileToArray(Bytes, *(FLakeData::DefaultDirectory() / (Name + TEXT(".height")))) && Out.LoadHeight(Bytes.GetData(), Bytes.Num());
	}
}

/**
 * World streaming (docs/world-streaming): the rules, without a world. The render origin moves on its 19.2 km lattice once the
 * boat is 20 km from it; the streaming plan loads nearest first and drops only past the keep radius; an index over a whole
 * grid covers it; a window shares its terrain's heights.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWorldStreamingRulesTest, "SailingSim.World.Streaming.Rules", WorldStreamingTestsLocal::Flags)
bool FSailingWorldStreamingRulesTest::RunTest(const FString&)
{
	using namespace Sailing;
	double NX = 0.0, NY = 0.0;
	TestFalse(TEXT("No re-centre within 20 km"), NeedsRecentre(0.0, 0.0, 14000.0, 14000.0, NX, NY));
	TestTrue(TEXT("A re-centre past it"), NeedsRecentre(0.0, 0.0, -20990.0, 24210.0, NX, NY));
	TestEqual(TEXT("... to the lattice point nearest the boat (north)"), NX, -19200.0);
	TestEqual(TEXT("... (east)"), NY, 19200.0);
	TestTrue(TEXT("The lattice is a whole number of tiles and of the water's 480 m and 60 m detail tiles"),
		FMath::IsNearlyZero(FMath::Fmod(kRecentreLatticeM, FTileIndex::kTileM)) && FMath::IsNearlyZero(FMath::Fmod(kRecentreLatticeM, 480.0)) && FMath::IsNearlyZero(FMath::Fmod(kRecentreLatticeM, 60.0)));

	Sailing::FLakeTerrain Bay;
	if (!TestTrue(TEXT("Galveston Bay's grid loads"), WorldStreamingTestsLocal::LoadGrid(TEXT("GalvestonBay"), Bay))) return false;
	const FTileIndex Index = FTileIndex::ForGrid(Bay, FTileIndex::kTileM);
	double MinX, MinY, MaxX, MaxY;
	Index.Bounds(MinX, MinY, MaxX, MaxY);
	TestTrue(TEXT("The index over a whole grid covers it"), MinX <= Bay.GetOriginX() && MinY <= Bay.GetOriginY()
		&& MaxX >= Bay.GetOriginX() + (Bay.GetRows() - 1) * Bay.GetCell() && MaxY >= Bay.GetOriginY() + (Bay.GetCols() - 1) * Bay.GetCell());
	TestEqual(TEXT("... in tiles of 640 cells of 10 m"), Index.GetTiles()[0].Cells, 640);
	// A tile cut from the grid holds the grid's nodes.
	const FTileEntry& E = Index.GetTiles()[Index.Find(3, 2)];
	const std::shared_ptr<const FTerrainTile> Tile = Index.CutTile(E, Bay);
	double MaxErr = 0.0;
	for (int32 K = 0; K < 50; ++K)
	{
		const double X = Tile->OriginX + (K * 37 % 640) * 10.0 + 3.0, Y = Tile->OriginY + (K * 91 % 640) * 10.0 + 7.0;
		MaxErr = FMath::Max(MaxErr, FMath::Abs(Tile->HeightAt(X, Y) - Bay.HeightAt(X, Y)));
	}
	TestTrue(TEXT("A tile cut from the grid is the grid (within 1 cm)"), MaxErr < 0.01);

	// The plan: nearest first; nothing dropped inside the keep radius.
	std::vector<uint8_t> Resident(Index.GetTiles().size(), 0), InFlight(Index.GetTiles().size(), 0);
	std::vector<int> Load, Drop;
	FStreamRadii Radii;
	PlanStreaming(Index, 0.0, 0.0, Radii, Resident, InFlight, Load, Drop);
	TestTrue(TEXT("The plan loads something and drops nothing at the start"), Load.size() > 0 && Drop.empty());
	bool bOrdered = true;
	for (size_t K = 1; K < Load.size(); ++K) bOrdered &= Index.DistanceTo(Index.GetTiles()[Load[K - 1]], 0.0, 0.0) <= Index.DistanceTo(Index.GetTiles()[Load[K]], 0.0, 0.0);
	TestTrue(TEXT("... nearest first"), bOrdered && Index.DistanceTo(Index.GetTiles()[Load[0]], 0.0, 0.0) == 0.0);
	for (const int L : Load) Resident[L] = 1;
	PlanStreaming(Index, 0.0, 0.0, Radii, Resident, InFlight, Load, Drop);
	TestTrue(TEXT("... and nothing more once they are in"), Load.empty() && Drop.empty());

	// A window shares the heights and answers as the whole grid does.
	const FLakeTerrain Window = Bay.WindowAround(-5000.0, 10000.0, 6000.0);
	TestTrue(TEXT("A window is smaller than its terrain"), Window.GetRows() < Bay.GetRows() && Window.GetCols() < Bay.GetCols());
	TestEqual(TEXT("... and reads the same heights"), Window.HeightAt(-4321.0, 9876.0), Bay.HeightAt(-4321.0, 9876.0));
	const int32 R = FMath::RoundToInt32((-4000.0 - Window.GetOriginX()) / Window.GetCell()), C = FMath::RoundToInt32((11000.0 - Window.GetOriginY()) / Window.GetCell());
	TestEqual(TEXT("... its nodes are the grid's"), Window.NodeHeight(R, C), Bay.HeightAt(Window.GetOriginX() + R * Window.GetCell(), Window.GetOriginY() + C * Window.GetCell()), 1e-6);
	return true;
}

/**
 * The Texas coast (Tools/coast/compose_world.py): Galveston Bay's heights unchanged inside its grid, the Gulf passage's
 * reprojected beyond, streamed a tile at a time. A scripted sail from Kemah out through Bolivar Roads into the Gulf and back
 * (60 km each way), forty times faster than a boat, the worker keeping up a read a frame: the tiles under her and around
 * her are always resident, the loader's game-thread side stays under 2 ms a frame, tiles are dropped behind her, and back
 * at the start what is resident is what was resident when she left (within 10%: nothing accumulates).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWorldStreamingSailTest, "SailingSim.World.Streaming.Sail", WorldStreamingTestsLocal::Flags)
bool FSailingWorldStreamingSailTest::RunTest(const FString&)
{
	using namespace WorldStreamingTestsLocal;
	FLakeData Coast;
	if (!TestTrue(TEXT("The Texas coast loads"), Coast.Load(FLakeData::DefaultDirectory(), TEXT("TexasCoast")))) return false;
	TestTrue(TEXT("... as a streamed world"), Coast.bStreamed && !Coast.IsLoaded());
	FWorldStreamer Streamer;
	if (!TestTrue(TEXT("Its tile index reads"), Streamer.Start(Coast, FLakeData::DefaultDirectory(), TEXT("TexasCoast")))) return false;
	TestTrue(TEXT("... streamed, 10 m at its finest"), Streamer.IsStreamed() && Streamer.GetIndex().GetFinestCell() == 10.0);
	const FVector2D Kemah(-310.0, 1100.0);
	const double LoadStart = FPlatformTime::Seconds();
	Streamer.LoadAround(Kemah.X, Kemah.Y, Streamer.Radii.LoadM);
	const double LoadMs = (FPlatformTime::Seconds() - LoadStart) * 1000.0;
	if (!TestTrue(TEXT("The tiles around the start are in"), Coast.IsLoaded())) return false;

	// The bay inside its grid is the bay's bake; the Gulf beyond it the passage's, reprojected.
	Sailing::FLakeTerrain Bay, Gulf;
	if (!LoadGrid(TEXT("GalvestonBay"), Bay) || !LoadGrid(TEXT("GulfPassage"), Gulf)) return false;
	double BayErr = 0.0;
	for (int32 K = 0; K < 200; ++K)
	{
		const double X = -12000.0 + (K * 7919 % 20000), Y = -4000.0 + (K * 104729 % 26000);
		BayErr = FMath::Max(BayErr, FMath::Abs(Coast.Terrain.HeightAt(X, Y) - Bay.HeightAt(X, Y)));
	}
	TestTrue(TEXT("Inside Galveston Bay's grid the heights are its own (within 1 cm)"), BayErr < 0.01);

	// The sail: Kemah, down the ship channel, out through Bolivar Roads and the jetties, then southwest along the beach to
	// San Luis Pass, and back.
	FLakeData GulfData;
	GulfData.Anchor = Sailing::FGeoAnchor(29.33, -94.69);
	const TArray<FVector2D> Out = { Kemah, FVector2D(-5490.0, 13990.0), FVector2D(-20990.0, 24210.0), MapOf(Coast, 29.315, -94.665),
		MapOf(Coast, 29.285, -94.62), MapOf(Coast, 29.10, -94.85), MapOf(Coast, 28.99, -95.06) };
	TArray<FVector2D> Legs = Out;
	for (int32 K = Out.Num() - 2; K >= 0; --K) Legs.Add(Out[K]);   // and back
	const double BayX0 = Bay.GetOriginX(), BayY0 = Bay.GetOriginY();
	const double BayX1 = BayX0 + (Bay.GetRows() - 1) * Bay.GetCell(), BayY1 = BayY0 + (Bay.GetCols() - 1) * Bay.GetCell();
	const Sailing::FTileIndex& Index = Streamer.GetIndex();
	const int64 StartBytes = Streamer.ResidentBytes();
	const int32 StartTiles = Streamer.NumResident();
	int64 MaxBytes = StartBytes;
	double Sailed = 0.0, WorstTickMs = 0.0, GulfErr = 0.0;
	int32 Frames = 0, Missing = 0, NearMissing = 0, GulfSamples = 0;
	Streamer.ResetLongest();
	double OffshoreKm = 0.0;
	for (int32 L = 1; L < Legs.Num(); ++L)
	{
		const FVector2D A = Legs[L - 1], B = Legs[L];
		const double Len = FVector2D::Distance(A, B);
		for (double S = 0.0; S < Len; S += 10.0, Sailed += 10.0, ++Frames)
		{
			const FVector2D P = A + (B - A) * (S / Len);
			Streamer.Tick(P.X, P.Y);
			WorstTickMs = FMath::Max(WorstTickMs, Streamer.LastTickMs());
			Streamer.WaitForWorker();
			MaxBytes = FMath::Max(MaxBytes, Streamer.ResidentBytes());
			// The tile under her and every tile within 2 km of her.
			for (int32 K = 0; K < int32(Index.GetTiles().size()); ++K)
			{
				const double D = Index.DistanceTo(Index.GetTiles()[K], P.X, P.Y);
				if (D == 0.0 && !Streamer.IsResident(K)) ++Missing;
				else if (D < 2000.0 && !Streamer.IsResident(K)) ++NearMissing;
			}
			// Offshore, beyond the bay's grid (and its kilometre of blend): the passage's heights, at the same lat/lon.
			const bool bOffshore = P.X < BayX0 - 1000.0 || P.X > BayX1 + 1000.0 || P.Y < BayY0 - 1000.0 || P.Y > BayY1 + 1000.0;
			if (bOffshore) OffshoreKm += 0.01;
			if (bOffshore && Frames % 50 == 0)
			{
				const Sailing::FLatLon Geo = Coast.Anchor.ToLatLon({ P.X, P.Y });
				const Sailing::FMapPoint G = GulfData.Anchor.ToMap(Geo);
				GulfErr = FMath::Max(GulfErr, FMath::Abs(Coast.Terrain.HeightAt(P.X, P.Y) - Gulf.HeightAt(G.North, G.East)));
				++GulfSamples;
			}
		}
	}
	AddInfo(FString::Printf(TEXT("Start: %d tiles in %.0f ms (%.1f MB). Sailed %.1f km out and back (%.1f km beyond the bay's grid) in %d frames: %d loads, %d drops; back at the start %d tiles (%.1f MB; most on the way %.1f MB); worst game-thread tick %.3f ms; Gulf heights against the passage's within %.2f m (%d points)"),
		StartTiles, LoadMs, StartBytes / 1e6, Sailed / 1000.0, OffshoreKm, Frames, Streamer.NumLoads(), Streamer.NumDrops(), Streamer.NumResident(),
		Streamer.ResidentBytes() / 1e6, MaxBytes / 1e6, WorstTickMs, GulfErr, GulfSamples));
	TestTrue(TEXT("A sail of more than 30 km each way, into the Gulf beyond the bay's grid"), Sailed >= 60000.0 && OffshoreKm > 10.0);
	TestEqual(TEXT("The tile under the boat is always resident"), Missing, 0);
	TestEqual(TEXT("... and every tile within 2 km"), NearMissing, 0);
	TestTrue(TEXT("Tiles came and went on the way"), Streamer.NumLoads() > 0 && Streamer.NumDrops() > 0);
	TestTrue(TEXT("No game-thread hitch over 2 ms from the loader"), WorstTickMs < 2.0);
	// Back at the start (the reads queued on the way in finished): everything within the load radius is in, nothing past
	// the keep radius is (the tiles between the two stay from the way out: the gap that stops a tile on the edge coming and
	// going), and no more than all of that. The plan is made every tenth of a tile, hence that much slack.
	for (int32 K = 0; K < 200; ++K) { Streamer.Tick(Kemah.X, Kemah.Y); Streamer.WaitForWorker(); }
	const double Slack = 0.1 * Index.GetTileM();
	int32 Beyond = 0, Unloaded = 0;
	int64 KeepBytes = 0;
	for (int32 K = 0; K < int32(Index.GetTiles().size()); ++K)
	{
		const Sailing::FTileEntry& E = Index.GetTiles()[K];
		const double D = Index.DistanceTo(E, Kemah.X, Kemah.Y);
		if (D <= Streamer.Radii.KeepM + Slack) KeepBytes += int64(E.Cells + 1) * (E.Cells + 1) * 2;
		if (D > Streamer.Radii.KeepM + Slack && Streamer.IsResident(K)) ++Beyond;
		if (D <= Streamer.Radii.LoadM - Slack && !Streamer.IsResident(K)) ++Unloaded;
	}
	TestTrue(TEXT("Back at the start nothing beyond the keep radius is resident and everything within the load radius is"), Beyond == 0 && Unloaded == 0);
	TestTrue(TEXT("... so what is resident is bounded by the keep radius (nothing accumulates)"), Streamer.ResidentBytes() <= KeepBytes);
	TestTrue(TEXT("Offshore the heights are the Gulf passage's (within 0.5 m, resampled)"), GulfSamples > 0 && GulfErr < 0.5);
	Streamer.Stop();
	return true;
}

/**
 * The physics' windows (the sea fetch, the ocean mask, the shelter map, marched over 48 km around the boat on a streamed
 * world) give the whole world's answers near the boat: inside the window's core every march reaches its end inside it.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWorldStreamingWindowsTest, "SailingSim.World.Streaming.Windows", WorldStreamingTestsLocal::Flags)
bool FSailingWorldStreamingWindowsTest::RunTest(const FString&)
{
	using namespace Sailing;
	FLakeData Coast;
	if (!Coast.Load(FLakeData::DefaultDirectory(), TEXT("TexasCoast"))) return false;
	FWorldStreamer Streamer;
	if (!Streamer.Start(Coast, FLakeData::DefaultDirectory(), TEXT("TexasCoast"))) return false;
	Streamer.LoadAround(0.0, 0.0, 1e7);   // the whole world, for the whole world's answers
	const FPhysicsWindow Window;
	const FVector2D Center(-20990.0, 24210.0);   // Bolivar Roads: the bay, the jetties and the open Gulf within the core
	const FLakeTerrain& Whole = Coast.Terrain;
	const FLakeTerrain Win = Whole.WindowAround(Center.X, Center.Y, Window.HalfM);
	TestTrue(TEXT("The window is a part of the world"), Win.GetRows() < Whole.GetRows() && Win.GetCols() < Whole.GetCols());

	const double StartFetch = FPlatformTime::Seconds();
	FSeaFetch FetchWhole, FetchWin;
	FetchWhole.Build(Whole, 100.0);
	const double WholeMs = (FPlatformTime::Seconds() - StartFetch) * 1000.0;
	const double StartWin = FPlatformTime::Seconds();
	FetchWin.Build(Win, 100.0);
	const double WinMs = (FPlatformTime::Seconds() - StartWin) * 1000.0;
	const FOcean::FMask MaskWhole = FOcean::MakeMask(Whole, 135.0 * kDegToRad, 1.2), MaskWin = FOcean::MakeMask(Win, 135.0 * kDegToRad, 1.2);
	FOcean OceanWhole, OceanWin;
	OceanWhole.SetMask(FOcean::FMask(MaskWhole));
	OceanWin.SetMask(FOcean::FMask(MaskWin));
	FShelterMap ShelterWhole, ShelterWin;
	ShelterWhole.Build(Whole, 160.0 * kDegToRad, 40.0);
	ShelterWin.Build(Win, 160.0 * kDegToRad, 40.0);

	double FetchErr = 0.0, MaskErr = 0.0, ShelterErr = 0.0;
	FString WorstMask, WorstShelter;
	int32 Points = 0;
	for (int32 K = 0; K < 400; ++K)
	{
		const double X = Center.X + ((K * 7919) % 16000) - 8000.0, Y = Center.Y + ((K * 104729) % 16000) - 8000.0;
		if (Whole.HeightAt(X, Y) > -0.5) continue;   // on the water
		++Points;
		for (int32 Bin = 0; Bin < kSeaBins; Bin += 3)
		{
			const double A = Bin * 22.5 * kDegToRad;
			const double FW = FetchWhole.FetchToward(X, Y, A), FN = FetchWin.FetchToward(X, Y, A);
			FetchErr = FMath::Max(FetchErr, FMath::Abs(FW - FN) / FMath::Max(FW, 1000.0));
		}
		const double ME = FMath::Abs(OceanWhole.MaskAt(X, Y) - OceanWin.MaskAt(X, Y));
		if (ME > MaskErr) { MaskErr = ME; WorstMask = FString::Printf(TEXT("mask at %.0f, %.0f: %.3f whole, %.3f window"), X, Y, OceanWhole.MaskAt(X, Y), OceanWin.MaskAt(X, Y)); }
		const double SE = FMath::Abs(ShelterWhole.FactorAt(X, Y) - ShelterWin.FactorAt(X, Y));
		if (SE > ShelterErr) { ShelterErr = SE; WorstShelter = FString::Printf(TEXT("shelter at %.0f, %.0f: %.3f whole (lee %.3f build %.3f), %.3f window (lee %.3f build %.3f)"), X, Y,
			ShelterWhole.FactorAt(X, Y), ShelterWhole.LeeAt(X, Y), ShelterWhole.BuildAt(X, Y), ShelterWin.FactorAt(X, Y), ShelterWin.LeeAt(X, Y), ShelterWin.BuildAt(X, Y)); }
	}
	AddInfo(FString::Printf(TEXT("Window %d x %d nodes of the world's %d x %d; sea fetch %.0f ms whole, %.0f ms windowed; over %d water points in the core: fetch within %.1f%%, ocean mask within %.3f, shelter within %.3f"),
		Win.GetRows(), Win.GetCols(), Whole.GetRows(), Whole.GetCols(), WholeMs, WinMs, Points, FetchErr * 100.0, MaskErr, ShelterErr));
	AddInfo(WorstMask + TEXT("; ") + WorstShelter);
	TestTrue(TEXT("Points on the water in the core"), Points > 50);
	// The fetch's semi-Lagrangian march interpolates across its rays, so a trace of the window's edge reaches the core
	// (2.8% at worst at Bolivar Roads); the mask and the shelter are marched ray by ray and match exactly.
	TestTrue(TEXT("The window's sea fetch is the world's (within 5%)"), FetchErr < 0.05);
	TestTrue(TEXT("... its ocean mask (within 0.01)"), MaskErr < 0.01);
	TestTrue(TEXT("... its shelter (within 0.01)"), ShelterErr < 0.01);
	TestTrue(TEXT("... and the window marches faster"), WinMs < WholeMs);
	Streamer.Stop();
	return true;
}

/**
 * The render frame's re-centre: a boat sailing in a world whose origin moves 19.2 km north and east mid-sail keeps her
 * place on the earth and her velocity (within 1 mm and 1 mm/s of the same sail without the re-centre), and her actor is
 * where her physics is, in the new frame.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWorldStreamingRecentreTest, "SailingSim.World.Streaming.Recentre", WorldStreamingTestsLocal::Flags)
bool FSailingWorldStreamingRecentreTest::RunTest(const FString&)
{
	const Sailing::FGeoAnchor Anchor(29.5446, -95.0193);   // Galveston Bay's frame (the Texas coast's)
	struct FRun { Sailing::Vec3 Position, Velocity; FVector Actor; FVector2D ActorMap; FVector Origin; };
	auto Sail = [&](bool bRecentre) -> FRun
	{
		FRun Out;
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, bRecentre ? TEXT("SailingRecentreWorld") : TEXT("SailingFixedWorld"));
		FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
		Context.SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		World->GetWorldSettings()->NotifyBeginPlay();
		World->SpawnActor<AWaterSurface>(FVector::ZeroVector, FRotator::ZeroRotator);
		ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
		if (Boat)
		{
			for (int32 Frame = 0; Frame < 240; ++Frame)
			{
				if (bRecentre && Frame == 120) World->SetNewWorldOrigin(FIntVector(1920000, 1920000, 0));
				++GFrameCounter;
				World->Tick(LEVELTICK_All, 1.f / 60.f);
			}
			Out.Position = Boat->GetBoatModel().OriginPosition();
			Out.Velocity = Boat->GetBoatModel().GetState().Velocity;
			Out.Actor = Boat->GetActorLocation();
			Out.ActorMap = SailingFrame::ToMap(World, Out.Actor);
			Out.Origin = SailingFrame::OriginCm(World);
		}
		World->EndPlay(EEndPlayReason::Quit);
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
		return Out;
	};
	const FRun Fixed = Sail(false), Moved = Sail(true);
	const Sailing::FLatLon A = Anchor.ToLatLon({ Fixed.Position.X, Fixed.Position.Y }), B = Anchor.ToLatLon({ Moved.Position.X, Moved.Position.Y });
	const double Apart = Sailing::FGeoAnchor::Distance(Anchor.ToMap(A), Anchor.ToMap(B));
	const double DV = (Fixed.Velocity - Moved.Velocity).Length();
	AddInfo(FString::Printf(TEXT("After 4 s, the origin moved at 2 s: %.6f m apart, velocities %.6f m/s apart; the actor %.0f, %.0f cm in the frame at %.0f, %.0f cm"),
		Apart, DV, Moved.Actor.X, Moved.Actor.Y, Moved.Origin.X, Moved.Origin.Y));
	TestTrue(TEXT("The origin moved"), Moved.Origin.X == 1920000.0 && Moved.Origin.Y == 1920000.0);
	TestTrue(TEXT("Her lat/lon is the same as without the re-centre (within 1 mm)"), Apart < 0.001);
	TestTrue(TEXT("... and her velocity (within 1 mm/s)"), DV < 0.001);
	TestTrue(TEXT("Her actor is where her physics is, in the new frame (within 1 mm)"),
		FVector2D::Distance(Moved.ActorMap, FVector2D(Moved.Position.X, Moved.Position.Y)) < 0.001);
	TestTrue(TEXT("... which is 19.2 km from where it was drawn"), FMath::Abs(Moved.Actor.X - (Fixed.Actor.X - 1920000.0)) < 0.1);
	return true;
}

#endif
