#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Engine/DirectionalLight.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "FlatWater.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags SmokeTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	const TCHAR* LakeMapPath = TEXT("/Game/Maps/Lake.Lake");

}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLakeMapLoadsTest, "SailingSim.Smoke.LakeMapLoads", SmokeTestFlags)
bool FSailingLakeMapLoadsTest::RunTest(const FString& Parameters)
{
	UWorld* World = LoadObject<UWorld>(nullptr, LakeMapPath);
	if (!TestNotNull(TEXT("Lake map loads"), World))
	{
		return false;
	}

	// Inspect the level's actors directly; the map is loaded as an asset, not played.
	int32 Water = 0, Lights = 0, Starts = 0;
	for (AActor* Actor : World->PersistentLevel->Actors)
	{
		Water += Actor && Actor->IsA<AFlatWater>();
		Lights += Actor && Actor->IsA<ADirectionalLight>();
		Starts += Actor && Actor->IsA<APlayerStart>();
	}
	TestEqual(TEXT("One water surface"), Water, 1);
	TestTrue(TEXT("Has a sun"), Lights >= 1);
	TestTrue(TEXT("Has a player start"), Starts >= 1);

	const AWorldSettings* Settings = World->PersistentLevel->GetWorldSettings();
	TestTrue(TEXT("Map uses the sailing game mode"), Settings && Settings->DefaultGameMode == ASailingGameMode::StaticClass());
	TestTrue(TEXT("Game mode spawns the boat as the player's pawn"),
		GetDefault<ASailingGameMode>()->DefaultPawnClass == ASailboatPawn::StaticClass());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBoatSpawnsAndFloatsTest, "SailingSim.Smoke.BoatSpawnsAndFloats", SmokeTestFlags)
bool FSailingBoatSpawnsAndFloatsTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingSmokeWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	// No game mode in this bare world, so start play the way AGameModeBase::StartPlay would.
	World->GetWorldSettings()->NotifyBeginPlay();

	const double WaterZ = 50.0;
	AFlatWater* Water = World->SpawnActor<AFlatWater>(FVector(0.f, 0.f, WaterZ), FRotator::ZeroRotator);
	ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	TestNotNull(TEXT("Water spawns"), Water);
	const bool bSpawned = TestNotNull(TEXT("Boat spawns"), Boat);

	if (bSpawned)
	{
		const UMaterialInstanceDynamic* HullMaterial = Cast<UMaterialInstanceDynamic>(Boat->Hull->GetMaterial(0));
		FLinearColor HullColor = FLinearColor::Black;
		TestTrue(TEXT("Hull has a colorable material"), HullMaterial && HullMaterial->GetVectorParameterValue(TEXT("Color"), HullColor));
		TestTrue(TEXT("Hull is painted red"), HullColor.R > 0.5f && HullColor.G < 0.2f);

		TestTrue(TEXT("Boat starts above the water (drop test)"), Boat->GetActorLocation().Z > WaterZ + 10.0);

		// 5 seconds at 60 fps through the real world tick.
		for (int32 Frame = 0; Frame < 300; ++Frame)
		{
			// Tick functions run at most once per engine frame, so advance the frame counter too.
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 60.f);
		}

		TestEqual(TEXT("Boat floats at the water surface (within 1 cm)"), Boat->GetActorLocation().Z, WaterZ, 1.0);
		TestEqual(TEXT("Boat is upright"), Boat->GetActorRotation().Roll, 0.0, 0.5);
		TestEqual(TEXT("Boat keeps its heading"), Boat->GetActorRotation().Yaw, 90.0, 0.01);
		TestEqual(TEXT("Boat stays where it was put"), Boat->GetActorLocation().X, 1000.0, 0.1);
	}

	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
