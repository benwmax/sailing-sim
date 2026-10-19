#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FarLightsActor.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;
struct FFarLightsData;

/**
 * Wide World Rendering PR 3 (docs/world-far-lights): the night beyond the near lights. Lighthouses and lit navaids past
 * the near pool as emissive points with their charted characters, seen as far as Allard's law carries their nominal
 * range through tonight's visibility and only above the sea horizon (below it, the loom: a dim glow on the horizon);
 * the lit shore as sprites from the houses bake; ships on the shipping lanes as impostors past 8 km, handed to the
 * traffic simulation when one closes inside it. Everything is instanced and unshadowed (budget 0.3 ms).
 */
UCLASS()
class SAILINGSIM_API AFarLightsActor : public AActor
{
	GENERATED_BODY()

public:
	/** Inside this, ANavaidsActor draws a world's own navaid lights (with their buoys' heave); beyond it this actor does. */
	static constexpr double NearPoolM = 6000.0;
	/** Lit shore sprites start here (inside, the houses' own windows and the night lights' pool show the town). */
	static constexpr double ShoreFromM = 2000.0;
	static constexpr double ShoreToM = 30000.0;
	/** Horizon ships are drawn from here out to ShipToM; inside it they join the traffic. */
	static constexpr double ShipHandOffM = 8000.0;
	static constexpr double ShipToM = 40000.0;

	AFarLightsActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Lights showing now (far and loom), for tests and the bench. */
	int32 GetShownCount() const { return Shown; }
	int32 GetLoomCount() const { return Looms; }
	/** Whether a far light (index into FFarLightsData::Lights) shows now for an eye at Camera (cm, world). Shared with the
	 *  tests: dark, beyond the near pool for a navaid of this world, above the horizon, bright enough by Allard's law. */
	static bool IsLightShown(const FFarLightsData& Data, int32 Index, const FVector& CameraCm, bool bDark, double VisibilityKm, double UnixTime,
		double* OutBrightness = nullptr, bool* OutLoom = nullptr);

private:
	UInstancedStaticMeshComponent* MakeIsm(UStaticMesh* Mesh, const FLinearColor& Color, float Intensity, bool bEmissive);
	void UpdateLights(const FVector& Camera, bool bDark, double Visibility, double Now);
	void UpdateShore(const FVector& Camera, bool bDark);
	void UpdateShips(const FVector& Camera, bool bDark, double SimTime);

	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Sphere;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cube;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EmissiveMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TMap<int32, TObjectPtr<UInstancedStaticMeshComponent>> LightIsms; // by S-57 colour
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> LoomIsm;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> ShoreIsm;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> HullIsm;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> ShipLightIsm;

	struct FShownLight { int32 Colour = 1; int32 Instance = 0; int32 Loom = 0; double Phase = 0.0; float Size = -1.f; float LoomSize = -1.f; };
	TArray<FShownLight> LightState;
	struct FShip { int32 Lane = 0; double Offset = 0.0; bool bHanded = false; int32 Hull = 0; int32 Light = 0; };
	TArray<FShip> Ships;
	FVector LastShoreCamera = FVector(1e12);
	bool bShoreLit = false;
	int32 Shown = 0, Looms = 0;
};
