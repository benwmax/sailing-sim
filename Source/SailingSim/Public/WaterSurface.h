#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WaterSurface.generated.h"

class UProceduralMeshComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UTexture2D;
namespace Sailing { class FWaveField; class FWindField; }

/**
 * The lake surface. Nested rings of mesh follow the camera (fine near, coarse far, like a geometry clipmap);
 * M_Water displaces them on the GPU with exactly the wave components the physics floats the boat on.
 * The actor also feeds the material a cat's-paw map from the wind field and a foam map for the boat's wake.
 * Its Z is the still-water level.
 */
UCLASS()
class SAILINGSIM_API AWaterSurface : public AActor
{
	GENERATED_BODY()

public:
	AWaterSurface();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Still-water height in centimeters (world Z). */
	float GetSurfaceZ() const { return GetActorLocation().Z; }

	/** Number of mesh rings (quality tier): 3 low, 5 medium, 6 high. */
	void SetRingCount(int32 Count);

	/** Records the boat's stern/bow positions for wake foam (world meters), called by the boat each frame. */
	void SetBoatForWake(const FVector2D& PositionM, float HeadingRad, float SpeedMs, float HeelRad);

	UPROPERTY(EditAnywhere, Category = "Water")
	float FarPlaneSizeMeters = 20000.f;

private:
	void BuildRings();
	void UpdateMaterial();
	void UpdateGustMap();
	void UpdateWakeMap(float DeltaSeconds);
	const Sailing::FWaveField* GetWaves() const;
	const Sailing::FWindField* GetWind() const;
	double GetSimTime() const;

	UPROPERTY(Transient) TArray<TObjectPtr<UProceduralMeshComponent>> Rings;
	UPROPERTY(VisibleAnywhere, Category = "Water") TObjectPtr<UStaticMeshComponent> FarPlane;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> WaterMaterial;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> GustMap;
	UPROPERTY(Transient) TObjectPtr<UTexture2D> WakeMap;

	TArray<float> RingSpacing;
	int32 RingCount = 6;
	FVector2D GustCenter = FVector2D::ZeroVector;
	float GustTimer = 0.f;
	float WakeTimer = 0.f;
	TArray<uint8> GustPixels;
	TArray<uint8> WakePixels;
	FVector2D WakeCenter = FVector2D::ZeroVector;

	struct FWakePoint { FVector2D Pos; float Age; float Speed; };
	TArray<FWakePoint> WakeTrail;
	FVector2D BoatPos = FVector2D::ZeroVector;
	float BoatHeading = 0.f, BoatSpeed = 0.f, BoatHeel = 0.f;
	float TrailTimer = 0.f;
	bool bStaticParamsSet = false;
};
