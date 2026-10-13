#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NavaidsActor.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
struct FNavaid;

/**
 * The chart's aids to navigation in the world: can and nun buoys, lighted pillar buoys, beacons with their dayboards,
 * and light structures, each where the NOAA chart puts it. Buoys ride the water; beacons and lights stand on the
 * bottom (they move with the tide's terrain offset). After dark every light shows its charted character: color,
 * rhythm and period, visible out to its nominal range and drawn big enough to see as a point at any distance.
 */
UCLASS()
class SAILINGSIM_API ANavaidsActor : public AActor
{
	GENERATED_BODY()

public:
	ANavaidsActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Number of lights currently showing (for tests and the HUD). */
	int32 GetLitCount() const { return LitCount; }

private:
	UInstancedStaticMeshComponent* MakeIsm(UStaticMesh* Mesh, const FLinearColor& Color, USceneComponent* Parent, bool bEmissive = false);
	void Build();
	/** Visual V6 (Medium and High): the Blender-built buoys and beacons (Tools/blender/build_navaids.py), painted per instance. */
	bool BuildModels();
	UInstancedStaticMeshComponent* ModelIsm(const TCHAR* Name, bool bFloating);

	UPROPERTY(Transient) TObjectPtr<USceneComponent> FloatingRoot; // buoys: at the water surface
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FixedRoot;    // beacons and lights: on the bottom, moving with the tide
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Meshes;
	UPROPERTY(Transient) TMap<int32, TObjectPtr<UInstancedStaticMeshComponent>> LightMeshes; // by S-57 colour
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EmissiveMaterial;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cube;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cylinder;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cone;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Sphere;

	struct FLightInstance
	{
		int32 Navaid = 0;
		int32 Colour = 1;
		int32 Instance = 0;
		bool bFloating = true;
		FVector Position;    // relative to its root, cm
		double Phase = 0.0;  // s, so lights with the same character don't flash in step
	};
	TArray<FLightInstance> Lights;

	struct FBuoy
	{
		UInstancedStaticMeshComponent* Ism = nullptr;
		int32 Instance = 0;
		double X = 0.0, Y = 0.0;   // m
		float Yaw = 0.f;
	};
	TArray<FBuoy> Buoys;                  // floating models, bobbing on the waves
	TMap<int32, int32> LightBuoy;         // light index -> buoy index
	TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> Models;
	int32 LitCount = 0;
	bool bBuilt = false;
};
