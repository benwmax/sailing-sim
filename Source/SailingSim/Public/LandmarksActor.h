#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LandmarksActor.generated.h"

class UInstancedStaticMeshComponent;

/**
 * Visual V6: the chart's landmarks standing in the world (Tools/blender/build_landmarks.py): the bay's gas-well platforms,
 * water towers, radio masts, windpumps, refinery stacks, church spires and flagstaffs, each where the chart puts it and
 * scaled to its charted height when there is one. They are what a navigator takes bearings on (SailboatPawn's bearing
 * tool already uses their positions). Medium and High; on a coast they follow the terrain's tide offset.
 */
UCLASS()
class SAILINGSIM_API ALandmarksActor : public AActor
{
	GENERATED_BODY()

public:
	ALandmarksActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	int32 NumPlaced() const { return Placed; }

private:
	UPROPERTY(Transient) TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> Meshes;
	struct FInstance
	{
		UInstancedStaticMeshComponent* Ism = nullptr;
		int32 Index = 0;
		FVector Base;   // m
		float Yaw = 0.f, Scale = 1.f;
	};
	TArray<FInstance> Instances;
	FVector2D CurvedFrom = FVector2D(1e12, 1e12);
	int32 Placed = 0;
	bool bTidal = false;
};
