#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FlatWater.generated.h"

class UStaticMeshComponent;

/**
 * Phase 0 water: a large flat plane whose height is the water surface for the boat physics.
 * Phase 2 replaces it with the Water plugin (lake chop, then an FFT ocean).
 */
UCLASS()
class SAILINGSIM_API AFlatWater : public AActor
{
	GENERATED_BODY()

public:
	AFlatWater();

	virtual void OnConstruction(const FTransform& Transform) override;

	/** Water surface height in centimeters (world Z). */
	float GetSurfaceZ() const { return GetActorLocation().Z; }

	/** Side length of the square of water, in meters. */
	UPROPERTY(EditAnywhere, Category = "Water")
	float SizeMeters = 4000.f;

	UPROPERTY(EditAnywhere, Category = "Water")
	FLinearColor WaterColor = FLinearColor(0.02f, 0.10f, 0.14f);

	UPROPERTY(VisibleAnywhere, Category = "Water")
	TObjectPtr<UStaticMeshComponent> Surface;
};
