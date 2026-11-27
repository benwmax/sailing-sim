#include "Misc/AutomationTest.h"
#include "ObjectTiles.h"
#include "ObjectStreaming.h"
#include "LakeData.h"
#include "LakeTerrainActor.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

#include <set>
#include <vector>

#if WITH_DEV_AUTOMATION_TESTS

namespace ObjectTilesTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** A coast of objects: one every 50 m along a 200 km line running north and a little east. */
	FVector2D CoastAt(double North) { return FVector2D(North, 3000.0 + 0.1 * North); }

	/** Every made cell is within the keep radius, and every cell within the load radius is made. */
	bool RingHolds(const Sailing::FObjectCells& Cells, const std::vector<uint8_t>& Made, const FVector2D& At, const Sailing::FObjectRing& Ring, FString& Why)
	{
		for (int32 K = 0; K < Cells.Num(); ++K)
		{
			const double D = Cells.DistanceTo(K, At.X, At.Y);
			const bool bMade = size_t(K) < Made.size() && Made[size_t(K)] != 0;
			if (bMade && D > Ring.KeepM) { Why = FString::Printf(TEXT("cell %d made %.0f m away"), K, D); return false; }
			if (!bMade && D <= Ring.LoadM) { Why = FString::Printf(TEXT("cell %d not made %.0f m away"), K, D); return false; }
		}
		return true;
	}
}

/**
 * World objects in tiles (docs/world-object-tiles): the rules, without a world. Cells are made nearest first within the
 * load radius and let go only past the keep radius; a 200 km sail out and back ends with the ring it started with; the
 * pool's slots stop growing once the ring is full and are reused from then on.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingObjectTilesRulesTest, "SailingSim.World.ObjectTiles.Rules", ObjectTilesTestsLocal::Flags)
bool FSailingObjectTilesRulesTest::RunTest(const FString&)
{
	using namespace Sailing;
	const FObjectRing Cull8 = ObjectRingForCull(8000.0);
	TestEqual(TEXT("A mesh culled at 8 km is made within 9 km"), Cull8.LoadM, 9000.0);
	TestEqual(TEXT("... and let go past 11 km"), Cull8.KeepM, 11000.0);
	TestEqual(TEXT("A mesh with no cull distance takes the default ring (12 km)"), ObjectRingForCull(0.0).LoadM, 12000.0);

	FObjectCells Cells;
	TestEqual(TEXT("The cells are the height tiles' 6.4 km"), Cells.GetCellM(), 6400.0);
	TestEqual(TEXT("Two points in one cell share it"), Cells.Add(10.0, 10.0), Cells.Add(6390.0, 6390.0));
	TestNotEqual(TEXT("The next cell north is another"), Cells.Add(6410.0, 10.0), Cells.Add(10.0, 10.0));
	TestEqual(TEXT("A point inside its cell is 0 m from it"), Cells.DistanceTo(Cells.Add(10.0, 10.0), 3000.0, 3000.0), 0.0);
	TestEqual(TEXT("A cell south of a point is measured to its nearest edge"), Cells.DistanceTo(Cells.Add(10.0, 10.0), 10000.0, 3000.0), 3600.0);
	Cells.Reset();
	for (double X = 0.0; X < 200000.0; X += 50.0) { const FVector2D P = ObjectTilesTestsLocal::CoastAt(X); Cells.Add(P.X, P.Y); }
	AddInfo(FString::Printf(TEXT("%d cells along 200 km of coast"), Cells.Num()));

	// Nearest first, and nothing dropped that was never made.
	const FObjectRing Ring;
	std::vector<uint8_t> None(size_t(Cells.Num()), 0);
	std::vector<int> Make, Drop;
	const FVector2D Mid = ObjectTilesTestsLocal::CoastAt(100000.0);
	PlanObjectCells(Cells, None, Mid.X, Mid.Y, Ring, -1, Make, Drop);
	bool bOrdered = true;
	for (size_t I = 1; I < Make.size(); ++I) bOrdered &= Cells.DistanceTo(Make[I], Mid.X, Mid.Y) >= Cells.DistanceTo(Make[I - 1], Mid.X, Mid.Y);
	TestTrue(TEXT("The plan makes the cells within the ring, nearest first"), Make.size() > 0 && bOrdered && Drop.empty());
	PlanObjectCells(Cells, None, Mid.X, Mid.Y, Ring, 2, Make, Drop);
	TestEqual(TEXT("... at most the number asked for"), int32(Make.size()), 2);

	// The sail: 10 m a step (two cells at most made a step), out to 200 km and back.
	std::vector<uint8_t> Made(size_t(Cells.Num()), 0);
	std::vector<int> SlotOf(size_t(Cells.Num()), -1);
	FSlotPool Pool;
	int32 Makes = 0, Drops = 0, MostLive = 0;
	auto Step = [&](const FVector2D& At)
	{
		PlanObjectCells(Cells, Made, At.X, At.Y, Ring, 2, Make, Drop);
		for (const int D : Drop) { Made[size_t(D)] = 0; Pool.Release(SlotOf[size_t(D)]); SlotOf[size_t(D)] = -1; ++Drops; }
		for (const int M : Make) { bool bReused = false; SlotOf[size_t(M)] = Pool.Acquire(bReused); Made[size_t(M)] = 1; ++Makes; }
		MostLive = FMath::Max(MostLive, Pool.NumInUse());
	};
	const FVector2D Start = ObjectTilesTestsLocal::CoastAt(0.0);
	for (int32 I = 0; I < 10; ++I) Step(Start);
	FString Why;
	TestTrue(TEXT("At the start the ring holds"), ObjectTilesTestsLocal::RingHolds(Cells, Made, Start, Ring, Why));
	bool bHeld = true;
	for (double X = 0.0; X <= 200000.0; X += 10.0)
	{
		const FVector2D At = ObjectTilesTestsLocal::CoastAt(X);
		Step(At);
		Step(At);   // a second look: the two a step have caught up
		if (bHeld && !ObjectTilesTestsLocal::RingHolds(Cells, Made, At, Ring, Why)) { bHeld = false; AddError(FString::Printf(TEXT("Out at %.0f m: %s"), X, *Why)); }
	}
	for (double X = 200000.0; X >= 0.0; X -= 10.0) Step(ObjectTilesTestsLocal::CoastAt(X));
	for (int32 I = 0; I < 10; ++I) Step(Start);
	TestTrue(TEXT("All the way out the ring held (made within 12 km, none past 14 km)"), bHeld);
	TestTrue(FString::Printf(TEXT("Back at the start the ring holds (%s)"), *Why), ObjectTilesTestsLocal::RingHolds(Cells, Made, Start, Ring, Why));
	AddInfo(FString::Printf(TEXT("%d makes, %d drops, at most %d cells at once, %d slots, %d reused"), Makes, Drops, MostLive, Pool.NumSlots(), Pool.NumReused()));
	TestTrue(TEXT("Every cell came and went (all 200 km of it was sailed)"), Makes >= Cells.Num() && Drops >= Cells.Num() - MostLive);
	TestEqual(TEXT("The pool never grew past the most cells drawn at once"), Pool.NumSlots(), MostLive);
	TestTrue(TEXT("... so almost every make reused a slot"), Pool.NumReused() == Makes - Pool.NumSlots());
	TestTrue(TEXT("A handful of cells at once, not the coast"), MostLive <= 8);

	// A slot given back twice is given back once.
	FSlotPool P2;
	bool bR = false;
	const int32 S0 = P2.Acquire(bR);
	P2.Release(S0);
	P2.Release(S0);
	TestEqual(TEXT("A double release frees one slot"), P2.NumInUse(), 0);
	TestEqual(TEXT("... and the next acquire takes it"), P2.Acquire(bR), S0);
	TestTrue(TEXT("... as a reuse"), bR);
	return true;
}

/**
 * World objects in tiles on the terrain actor (docs/world-object-tiles): FTiledInstances clones a kind's template for a cell
 * as it comes near and empties it back into the pool behind; a cell made late in the sail stands where the old start-up add
 * put it, on a tide-moved actor too; the component count stops growing.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingObjectTilesInstancesTest, "SailingSim.World.ObjectTiles.Instances", ObjectTilesTestsLocal::Flags)
bool FSailingObjectTilesInstancesTest::RunTest(const FString&)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingObjectTilesWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	ALakeTerrainActor* Terrain = World->SpawnActor<ALakeTerrainActor>(FVector(0.0, 0.0, -30.0), FRotator::ZeroRotator);   // a 30 cm tide
	if (TestNotNull(TEXT("Terrain actor"), Terrain))
	{
		UInstancedStaticMeshComponent* Template = NewObject<UInstancedStaticMeshComponent>(Terrain);
		Template->SetMobility(EComponentMobility::Static);
		Template->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		Template->SetCullDistances(0, 8000 * 100);   // 8 km, as the houses' archetypes
		Template->NumCustomDataFloats = 2;
		Terrain->KeepWithActor(Template);
		Template->RegisterComponent();
		TArray<TObjectPtr<UPrimitiveComponent>> Holder;
		FTiledInstances Cells;
		Cells.Init(Terrain, [Terrain](USceneComponent* C) { Terrain->KeepWithActor(C); }, &Holder);
		const int32 Kind = Cells.AddKind(Template);
		// A house every 50 m along 100 km of coast, its floats its own index and the coast's distance.
		int32 N = 0;
		for (double X = 0.0; X < 100000.0; X += 50.0, ++N)
		{
			const FVector2D P = ObjectTilesTestsLocal::CoastAt(X);
			const float Floats[2] = { float(N), float(X) };
			Cells.Add(Kind, FTransform(FRotator(0.0, 30.0, 0.0), FVector(P.X, P.Y, 4.0) * 100.0, FVector(12.0, 9.0, 5.0)), TConstArrayView<float>(Floats, 2));
		}
		TestEqual(TEXT("Every house is held"), Cells.NumObjects(), int64(N));
		Cells.Start(ObjectTilesTestsLocal::CoastAt(0.0));
		const int32 AtStart = Cells.NumCellsLive();
		AddInfo(FString::Printf(TEXT("Start: %d of %d cells drawn, %lld of %d houses"), AtStart, Cells.CellsOf(Kind)->Num(), Cells.NumInstancesLive(), N));
		TestTrue(TEXT("Only the cells near the start are drawn"), AtStart > 0 && AtStart < Cells.CellsOf(Kind)->Num() / 4);
		TestEqual(TEXT("The template stays empty"), Template->GetInstanceCount(), 0);

		// A house in a drawn cell: where the start-up add put it (the map frame on the actor, so 30 cm down with the tide).
		const FVector2D P0 = ObjectTilesTestsLocal::CoastAt(1000.0);
		const Sailing::FObjectCells& All = *Cells.CellsOf(Kind);
		int32 R0 = 0, C0 = 0;
		All.CellOf(P0.X, P0.Y, R0, C0);
		UInstancedStaticMeshComponent* Comp = Cells.ComponentOf(Kind, All.Find(R0, C0));
		if (TestNotNull(TEXT("The start's cell has a component"), Comp))
		{
			bool bFound = false;
			for (int32 I = 0; I < Comp->GetInstanceCount() && !bFound; ++I)
			{
				FTransform W;
				Comp->GetInstanceTransform(I, W, true);
				if (!W.GetTranslation().Equals(FVector(P0.X * 100.0, P0.Y * 100.0, 400.0 - 30.0), 0.5)) continue;
				bFound = true;
				TestTrue(TEXT("... turned and sized as given"), W.GetScale3D().Equals(FVector(12.0, 9.0, 5.0), 1e-3) && FMath::IsNearlyEqual(W.Rotator().Yaw, 30.0, 1e-3));
				const int32 F = Comp->NumCustomDataFloats;
				TestTrue(TEXT("... with its own floats"), F == 2 && Comp->PerInstanceSMCustomData.IsValidIndex(I * F + 1) && Comp->PerInstanceSMCustomData[I * F + 1] == 1000.f);
			}
			TestTrue(TEXT("A house 1 km up the coast stands at its map position, 30 cm down with the tide"), bFound);
		}

		// Sail the coast and back, the cells caught up at each point.
		int32 MostComps = 0;
		bool bHeld = true;
		auto Sail = [&](double From, double To, double Step)
		{
			for (double X = From; Step > 0.0 ? X <= To : X >= To; X += Step)
			{
				for (int32 K = 0; K < 8 && Cells.Update(ObjectTilesTestsLocal::CoastAt(X), 2) > 0; ++K) {}
				MostComps = FMath::Max(MostComps, Cells.NumComponents());
				// Never a house drawn past the keep radius.
				const FVector2D At = ObjectTilesTestsLocal::CoastAt(X);
				for (int32 C = 0; C < All.Num(); ++C) if (Cells.IsMade(Kind, C) && All.DistanceTo(C, At.X, At.Y) > Sailing::ObjectRingForCull(8000.0).KeepM) bHeld = false;
			}
		};
		Sail(0.0, 100000.0, 300.0);
		// A cell made far along: its houses stand as the start's do, after another 2 cm of tide.
		Terrain->SetActorLocation(FVector(0.0, 0.0, -32.0));
		Terrain->FollowActor();
		Sail(100000.0, 0.0, -300.0);
		TestTrue(TEXT("No cell was drawn past its keep radius"), bHeld);
		AddInfo(FString::Printf(TEXT("%d cells made and %d dropped, at most %d components, %d now"), Cells.NumCellsMade(), Cells.NumCellsDropped(), MostComps, Cells.NumComponents()));
		TestTrue(TEXT("Cells were dropped behind the boat"), Cells.NumCellsDropped() > Cells.CellsOf(Kind)->Num() / 2);
		TestTrue(TEXT("The components were reused, not made per cell"), Cells.NumComponents() <= MostComps && Cells.NumComponents() < Cells.NumCellsMade() / 3);
		TestEqual(TEXT("... the owner holds just those"), Holder.Num(), Cells.NumComponents());
		TestEqual(TEXT("Back at the start the same cells are drawn"), Cells.NumCellsLive(), AtStart);
		if (UInstancedStaticMeshComponent* Again = Cells.ComponentOf(Kind, All.Find(R0, C0)))
		{
			bool bFound = false;
			for (int32 I = 0; I < Again->GetInstanceCount() && !bFound; ++I)
			{
				FTransform W;
				Again->GetInstanceTransform(I, W, true);
				bFound = W.GetTranslation().Equals(FVector(P0.X * 100.0, P0.Y * 100.0, 400.0 - 32.0), 0.5);
			}
			TestTrue(TEXT("The start's house, made again, follows the tide (32 cm down)"), bFound);
		}
		else AddError(TEXT("The start's cell is drawn again"));
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

/**
 * The G2 houses' baked tiles stream (docs/world-object-tiles): on the two worlds with the most houses, how many 500 m tiles
 * fall in the ring at their first launch spot (what the start loads now) against all of them (what it loaded before).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingObjectTilesHouseRingTest, "SailingSim.World.ObjectTiles.HouseRing", ObjectTilesTestsLocal::Flags)
bool FSailingObjectTilesHouseRingTest::RunTest(const FString&)
{
	for (const TCHAR* Name : { TEXT("RayHubbard"), TEXT("GalvestonBay") })
	{
		FLakeData Lake;
		if (!TestTrue(FString::Printf(TEXT("%s loads"), Name), Lake.Load(FLakeData::DefaultDirectory(), Name))) continue;
		TMap<FIntPoint, TArray<int32>> Tiles;
		HouseTiles(Lake, Tiles);
		if (!TestTrue(FString::Printf(TEXT("%s has G2 houses"), Name), Tiles.Num() > 0)) continue;
		Sailing::FObjectCells Cells(UWorldKitLibrary::HouseTileM);
		for (const auto& KV : Tiles) Cells.Add((KV.Key.X + 0.5) * UWorldKitLibrary::HouseTileM, (KV.Key.Y + 0.5) * UWorldKitLibrary::HouseTileM);
		TestEqual(FString::Printf(TEXT("%s: a cell per kit tile"), Name), Cells.Num(), Tiles.Num());
		const FVector2D At = Lake.LaunchSpots.Num() > 0 ? FVector2D(Lake.LaunchSpots[0].X, Lake.LaunchSpots[0].Y) : FVector2D::ZeroVector;
		std::vector<uint8_t> None(size_t(Cells.Num()), 0);
		std::vector<int> Make, Drop;
		Sailing::PlanObjectCells(Cells, None, At.X, At.Y, SailingObjects::NoCullRing(), -1, Make, Drop);
		int32 Houses = 0, InRing = 0;
		for (const auto& KV : Tiles) Houses += KV.Value.Num();
		for (const int M : Make)
		{
			const FIntPoint Key(Cells.Row(M), Cells.Col(M));
			if (const TArray<int32>* H = Tiles.Find(Key)) InRing += H->Num();
		}
		AddInfo(FString::Printf(TEXT("%s from %s: %d of %d house tiles (%d of %d houses) within 12 km"), Name, Lake.LaunchSpots.Num() > 0 ? *Lake.LaunchSpots[0].Name : TEXT("the origin"),
			int32(Make.size()), Tiles.Num(), InRing, Houses));
		TestTrue(FString::Printf(TEXT("%s: the start draws some of them"), Name), Make.size() > 0);
	}
	return true;
}

#endif
