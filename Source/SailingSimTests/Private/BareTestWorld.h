#pragma once

#include "CoreMinimal.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "UObject/Package.h"

/**
 * A bare game world for the tests that spawn and tick actors in one, torn down the way the game tears its own down.
 *
 * The one-process suite crashed in garbage collection (FObjectPurge::DestroyObjects, as a later test started; Nov 5
 * 2026): SailingSim.Smoke.CameraAboveWater gave its world a game instance outered to GEngine, never shut down, and the
 * photo-mode copy of this helper destroyed the world without EndPlay, so a game mode and a ticked player pawn were left
 * for a later purge. Every such test goes through this one helper now: EndPlay first, and a game instance a test asks
 * for (UseGameInstance, in the transient package) is released with the world.
 */
struct FBareTestWorld
{
	UWorld* World = nullptr;

	explicit FBareTestWorld(const TCHAR* Name)
	{
		World = UWorld::CreateWorld(EWorldType::Game, false, Name);
		FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
		Context.SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		World->GetWorldSettings()->NotifyBeginPlay();
	}
	~FBareTestWorld()
	{
		World->EndPlay(EEndPlayReason::Quit);
		if (UGameInstance* Instance = World->GetGameInstance())
		{
			World->SetGameInstance(nullptr);
			Instance->MarkAsGarbage();
		}
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	}
	FBareTestWorld(const FBareTestWorld&) = delete;
	FBareTestWorld& operator=(const FBareTestWorld&) = delete;

	/** The world's game instance (an authority game mode reads it): one for this world only. */
	UGameInstance* UseGameInstance()
	{
		UGameInstance* Instance = NewObject<UGameInstance>(GetTransientPackage());
		World->SetGameInstance(Instance);
		return Instance;
	}
	void Tick(int32 Frames)
	{
		for (int32 I = 0; I < Frames; ++I)
		{
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 60.f);
		}
	}
};
