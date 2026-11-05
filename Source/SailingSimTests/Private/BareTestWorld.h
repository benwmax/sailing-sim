#pragma once

#include "CoreMinimal.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"

/**
 * A bare game world for the tests that spawn and tick actors in one, torn down the way the game tears its own down.
 *
 * The one-process suite crashed in garbage collection (FObjectPurge::DestroyObjects inside a later test's World->Tick,
 * Visual.RigClearance, with the engine Water plugin's frames on the stack; Mac and Windows; Nov 5 2026). The photo-mode
 * copy of this helper destroyed its world without EndPlay, and SailingSim.Smoke.CameraAboveWater had ticked a game mode
 * and a player pawn in it. On main, CameraAboveWater + Visual in one process: EndPlay added alone, 74/74 pass; the game
 * instance released alone (no EndPlay), it still crashes. So EndPlay is the change that matters; which object the purge
 * fell over is not identified. EndPlay runs first here; a game instance a test asks for (UseGameInstance) is released
 * with the world too. The tests built on this helper and the ones that hand-roll a world end play the same way.
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
		if (!World) return;
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

	/** The world's game instance (an authority game mode reads it), released with the world. Outered to the engine:
	 *  UGameInstance::GetEngine() is CastChecked<UEngine>(GetOuter()). */
	UGameInstance* UseGameInstance()
	{
		UGameInstance* Instance = NewObject<UGameInstance>(GEngine);
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
