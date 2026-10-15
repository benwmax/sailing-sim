#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CoastMarinasActor.generated.h"

class UInstancedStaticMeshComponent;
class UPrimitiveComponent;
struct FLakeData;
struct FBerthedBoat;

/**
 * Graphics G7: the coast's marinas from the G2 piers pack (FLakeData::MooredBoats, the "floating" docks): every boat the
 * 2018 lidar saw where the map has water, as a marina neighbour in one of the berthed dresses (a sailboat by her length,
 * a power boat by hers: runabout, express cruiser, trawler yacht, sportfisherman or motor yacht), and the floating
 * walkways inferred between their rows. Both float: they stay at the water's level while the coast's terrain follows the
 * tide. Medium and High.
 */
UCLASS()
class SAILINGSIM_API ACoastMarinasActor : public AActor
{
	GENERATED_BODY()

public:
	ACoastMarinasActor();
	virtual void BeginPlay() override;

	/** The neighbour each moored boat becomes (class by length and mast, scale to her length), for drawing and tests. */
	static void PlaceBoats(const FLakeData& Lake, TArray<FBerthedBoat>& Out);

private:
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> Boats;
	UPROPERTY(Transient) TArray<TObjectPtr<UPrimitiveComponent>> Walkways;
};
