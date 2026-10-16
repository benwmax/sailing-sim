#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Engine/DirectionalLight.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "WaterSurface.h"
#include "SailingEnvironment.h"
#include "Components/VolumetricCloudComponent.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "BoatModel.h"
#include "ProceduralMeshComponent.h"

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
	int32 Water = 0, Lights = 0, Starts = 0, Environment = 0, Clouds = 0;
	for (AActor* Actor : World->PersistentLevel->Actors)
	{
		Water += Actor && Actor->IsA<AWaterSurface>();
		Environment += Actor && Actor->IsA<ASailingEnvironment>();
		Clouds += Actor && Actor->IsA<AVolumetricCloud>();
		Lights += Actor && Actor->IsA<ADirectionalLight>();
		Starts += Actor && Actor->IsA<APlayerStart>();
	}
	TestEqual(TEXT("One water surface"), Water, 1);
	TestEqual(TEXT("One weather environment"), Environment, 1);
	TestEqual(TEXT("Volumetric clouds"), Clouds, 1);
	TestTrue(TEXT("Has a sun"), Lights >= 1);
	TestTrue(TEXT("Has a player start"), Starts >= 1);

	const AWorldSettings* Settings = World->PersistentLevel->GetWorldSettings();
	TestTrue(TEXT("Map uses the sailing game mode"), Settings && Settings->DefaultGameMode == ASailingGameMode::StaticClass());
	TestTrue(TEXT("Game mode spawns the boat as the player's pawn"),
		GetDefault<ASailingGameMode>()->DefaultPawnClass == ASailboatPawn::StaticClass());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBoatSpawnsAndFloatsTest, "SailingSim.Smoke.BoatSpawnsFloatsAndSails", SmokeTestFlags)
bool FSailingBoatSpawnsAndFloatsTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingSmokeWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	// No game mode in this bare world, so start play the way AGameModeBase::StartPlay would.
	World->GetWorldSettings()->NotifyBeginPlay();

	const double WaterZ = 50.0;
	AWaterSurface* Water = World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, WaterZ), FRotator::ZeroRotator);
	ASailboatPawn* Boat = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	TestNotNull(TEXT("Water spawns"), Water);
	const bool bSpawned = TestNotNull(TEXT("Boat spawns"), Boat);

	if (bSpawned)
	{
		// Visual V2: the J/22 is the modelled boat (white gelcoat), not the procedural hull. Since round 12 the player's
		// J/22 is the hero (SM_J22H_Hull, its topsides a baked texture); -SailingClassicJ22 keeps SM_J22_Hull.
		const UStaticMeshComponent* ModelHull = nullptr;
		Boat->ForEachComponent<UStaticMeshComponent>(false, [&](UStaticMeshComponent* C)
		{
			const FString Name = C->GetStaticMesh() ? C->GetStaticMesh()->GetName() : FString();
			if (Name == TEXT("SM_J22H_Hull") || Name == TEXT("SM_J22_Hull")) ModelHull = C;
		});
		TestNotNull(TEXT("The J/22 shows its model"), ModelHull);
		TestEqual(TEXT("The procedural hull is cleared"), Boat->HullMesh->GetNumSections(), 0);
		if (ModelHull && ModelHull->GetStaticMesh()->GetName() == TEXT("SM_J22H_Hull"))
		{
			const UMaterialInterface* Topsides = ModelHull->GetMaterial(ModelHull->GetMaterialIndex(TEXT("J22H_Hull")));
			UTexture* BaseColor = nullptr;
			TestTrue(TEXT("Topsides have the baked gelcoat"), Topsides && Topsides->GetTextureParameterValue(TEXT("BaseColor"), BaseColor) && BaseColor
				&& BaseColor->GetName() == TEXT("T_J22H_Hull_D"));
		}
		else if (ModelHull)
		{
			const UMaterialInterface* Topsides = ModelHull->GetMaterial(ModelHull->GetMaterialIndex(TEXT("Topsides")));
			FLinearColor HullColor = FLinearColor::Black;
			TestTrue(TEXT("Topsides have a gelcoat colour"), Topsides && Topsides->GetVectorParameterValue(TEXT("Color"), HullColor));
			TestTrue(TEXT("White gelcoat topsides"), HullColor.R > 0.6f && HullColor.G > 0.6f && HullColor.B > 0.6f);
		}

		const FVector Start = Boat->GetActorLocation();
		TestEqual(TEXT("Boat starts at the water surface"), Start.Z, WaterZ, 2.0);

		// 10 seconds at 60 fps through the real world tick. The bare world has no game mode, so the boat uses
		// its fallback wind: 10 kn from +X, a beam reach for a boat heading +Y.
		for (int32 Frame = 0; Frame < 600; ++Frame)
		{
			// Tick functions run at most once per engine frame, so advance the frame counter too.
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 60.f);
		}

		const FVector End = Boat->GetActorLocation();
		AddInfo(FString::Printf(TEXT("After 10 s: moved %.1f m, z %.1f cm, heel %.1f deg, speed %.2f kn"), (End - Start).Size2D() / 100.0, End.Z,
			FMath::RadiansToDegrees(Boat->GetBoatModel().GetTelemetry().Heel), Boat->GetBoatModel().GetTelemetry().BoatSpeed / Sailing::kKnot));
		TestEqual(TEXT("Boat floats at the water surface (within 5 cm)"), End.Z, WaterZ, 5.0);
		TestTrue(TEXT("Boat heels a little, not over"), FMath::Abs(Boat->GetActorRotation().Roll) < 25.0);
		TestTrue(TEXT("Boat sails: moved more than 15 m in 10 s"), (End - Start).Size2D() > 1500.0);
		int32 Built = 0;
		Boat->ForEachComponent<UProceduralMeshComponent>(false, [&](UProceduralMeshComponent* C) { Built += C->GetNumSections() > 0; });
		TestTrue(TEXT("Sail and rig meshes were built"), Built >= 3); // main, jib, rig lines
	}

	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

// Bench-fix: -SailingBoat=<prefix> ignores case, spaces and slashes, so the bench scripts' J22 sails the J/22.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBoatNameMatchTest, "SailingSim.Smoke.BoatNameMatch", SmokeTestFlags)
bool FSailingBoatNameMatchTest::RunTest(const FString&)
{
	const int32 J22 = int32(Sailing::EBoatType::J22);
	TestEqual(TEXT("J22 is the J/22"), USailingSettings::MatchBoatName(TEXT("J22")), J22);
	TestEqual(TEXT("j/22 is the J/22"), USailingSettings::MatchBoatName(TEXT("j/22")), J22);
	TestEqual(TEXT("J/22 is the J/22"), USailingSettings::MatchBoatName(TEXT("J/22")), J22);
	TestEqual(TEXT("J matches the J/22 by prefix"), USailingSettings::MatchBoatName(TEXT("J")), J22);
	TestEqual(TEXT("J24 matches nothing"), USailingSettings::MatchBoatName(TEXT("J24")), -1);
	TestEqual(TEXT("An empty name matches nothing"), USailingSettings::MatchBoatName(TEXT("")), -1);
	TestEqual(TEXT("hobie prefix"), USailingSettings::MatchBoatName(TEXT("hobie")), int32(Sailing::EBoatType::Hobie16));
	TestEqual(TEXT("Catalina 30 with its space"), USailingSettings::MatchBoatName(TEXT("Catalina 30")), int32(Sailing::EBoatType::Catalina30));
	TestEqual(TEXT("Lagoon"), USailingSettings::MatchBoatName(TEXT("Lagoon")), int32(Sailing::EBoatType::Lagoon42));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
