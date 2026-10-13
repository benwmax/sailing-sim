#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MarinaActor.generated.h"

class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UMaterialInterface;
struct FMarina;
struct FKitGeometry;
namespace Sailing { class FLakeTerrain; }

/**
 * Visual V6: draws the club's marina from its layout (FMarina, FLakeData::Marina): floating dock rows on their floats,
 * finger piers, pilings, cleats, dock boxes, power pedestals and dock lights; the shore walkway and fixed piers; the
 * rock breakwater; the clubhouse and pool; and J/22s berthed in the occupied slips (the home slip kept free).
 * Generated from code with UVs in metres (WorldKit.h: baked to Nanite tiles in the editor, procedural otherwise). Each structure has an id: a scan listed in
 * Content/World/Scans.json (id -> static mesh, authored in the map frame) replaces the generated one.
 */
UCLASS()
class SAILINGSIM_API AMarinaActor : public AActor
{
	GENERATED_BODY()

public:
	AMarinaActor();
	virtual void BeginPlay() override;

	/** The generated structures (all but the rocks and boats), for drawing and for the editor's Nanite bake. */
	static void BuildGeometry(const FMarina& Marina, const Sailing::FLakeTerrain* Terrain, TFunctionRef<bool(const FString&)> Generated, FKitGeometry& Out);

	/** Where the generated docks' decks are (m above the water), for tests. */
	static constexpr float FloatingDeckHeight = 0.45f;

private:
	void Build(const FMarina& Marina);
	UMaterialInterface* Surface(const FLinearColor& Color, float Roughness, float Pattern, float Windows = 0.f, float Metallic = 0.f);

	UPROPERTY(Transient) TArray<TObjectPtr<UPrimitiveComponent>> Tiled;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Rocks;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Boats;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Scans;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> SurfaceMaterial;
};
