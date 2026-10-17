#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MarinaActor.generated.h"

class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UMaterialInterface;
struct FMarina;
struct FMarinaSlip;
struct FKitGeometry;
enum class EWearSite : uint8;
namespace Sailing { class FLakeTerrain; }

/** Graphics G7: a neighbour boat in her berth: the marina's slips, the coast's moored boats (Type: Sailing::EBoatType, or
 *  PowerBoat for the runabout, PowerYacht for the trawler yacht; Mac polish: PowerExpress, PowerSport and PowerMotorYacht,
 *  hull paint per instance; Scale to her measured length). Environment E1: every part carries her FWearSeed (Site) from
 *  custom data slot FWearSeed::Slot. */
struct FBerthedBoat
{
	static constexpr uint8 PowerBoat = 255;
	static constexpr uint8 PowerYacht = 254;
	static constexpr uint8 PowerExpress = 253;
	static constexpr uint8 PowerSport = 252;
	static constexpr uint8 PowerMotorYacht = 251;
	static bool IsPower(uint8 Type) { return Type >= PowerMotorYacht; }
	/** Whether the class's hull is painted per instance (M_VehiclePaint: custom data 0..2). */
	static bool IsPainted(uint8 Type) { return Type >= PowerMotorYacht && Type <= PowerExpress; }
	/** A painted hull's colour (linear): mostly white gelcoat, then the dark blues, ivory, greys and the odd green. */
	static SAILINGSIM_API FLinearColor PowerHullColour(uint32 Seed);
	FVector2D Center = FVector2D::ZeroVector;
	float HeadingDeg = 0.f;
	uint8 Type = 0;
	float Scale = 1.f;
	/** Environment E1: the berthed dress (0-5) and cover (FSlipLook) picked for her slip; -1 hashes them from her place. */
	int32 Dress = -1, Cover = -1;
};
/** Environment E1: what a slip wears: the boat's berthed dress, the slip's dock clutter set (E2's props) and the cover
 *  (the wear seed's variant on the boat). No slip shares any of the three with a neighbour (AreNeighbourSlips). */
struct FSlipLook
{
	static constexpr int32 NumDress = 6;
	static constexpr int32 NumClutter = 4;
	static constexpr int32 NumCover = 5;
	int32 Dress = 0, Clutter = 0, Cover = 0;
};
/** Side by side along a row (the finger between them), or bow to bow across the row's dock. */
SAILINGSIM_API bool AreNeighbourSlips(const FMarinaSlip& A, const FMarinaSlip& B);
/** One look per slip of Marina.Slips, hashed from the slip's id, stepped off any value a neighbour already has. */
SAILINGSIM_API void AssignSlipLooks(const FMarina& Marina, TArray<FSlipLook>& Out);
/** Draws berthed boats as instanced meshes on Root: each class's hull (livery per instance), boom, rudder and one of six
 *  berthed dresses (build_berthed.py). CullScale stretches the cull distances (1: the club's 900 m dress, 1.5 km hull). */
SAILINGSIM_API void SpawnBerthedBoats(AActor* Owner, USceneComponent* Root, TConstArrayView<FBerthedBoat> Boats, float CullScale, EComponentMobility::Type Mobility,
	TArray<TObjectPtr<UInstancedStaticMeshComponent>>& Out, EWearSite Site);

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
	virtual void Tick(float DeltaSeconds) override;

	/** The generated structures (all but the rocks and boats), for drawing and for the editor's Nanite bake. */
	static void BuildGeometry(const FMarina& Marina, const Sailing::FLakeTerrain* Terrain, TFunctionRef<bool(const FString&)> Generated, FKitGeometry& Out);

	/** Where the generated docks' decks are (m above the water), for tests. */
	static constexpr float FloatingDeckHeight = 0.45f;

private:
	void Build(const FMarina& Marina);

	UPROPERTY(Transient) TArray<TObjectPtr<UPrimitiveComponent>> Tiled;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Rocks;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Boats;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Scans;
	/** Visual V7: the halyards clanking on the dock rows and the gulls over the harbour, spatialised. */
	UPROPERTY(Transient) TArray<TObjectPtr<class USailingWorldSynth>> Voices;
	UPROPERTY(Transient) TArray<TObjectPtr<USceneComponent>> GullPoints;
	float GullClock = 0.f;
};
