#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BridgesActor.generated.h"

class UInstancedStaticMeshComponent;
class UPrimitiveComponent;

/**
 * Visual V6: the world's bridges from the lake or coast data (BuildBridgeGeometry in WorldKit.h, baked to Nanite tiles) and
 * sparse traffic on the road decks: sedans, pickups and semis at highway speed in their lanes, painted per instance,
 * with head and tail lights at night. Also the shore kit (BuildShoreGeometry: riprap, a lake's piers). Medium and High;
 * Low keeps the plain shapes of ALakeTerrainActor. On a coast everything follows the terrain's tide offset.
 */
UCLASS()
class SAILINGSIM_API ABridgesActor : public AActor
{
	GENERATED_BODY()

public:
	ABridgesActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	int32 NumVehicles() const { return Vehicles.Num(); }

private:
	struct FLane
	{
		TArray<FVector> Points;    // cm, at road height, in the direction of travel
		TArray<double> Cum;        // cm along
		float Speed = 25.f;        // m/s
	};
	struct FVehicle
	{
		int32 Lane = 0;
		double S = 0.0;            // cm along the lane
		int32 Kind = 0;            // mesh
	};
	void BuildTraffic();

	bool bTidal = false;
	TArray<FLane> Lanes;
	TArray<FVehicle> Vehicles;
	TArray<TArray<int32>> KindVehicles; // per mesh: vehicle indices in instance order
	UPROPERTY(Transient) TArray<TObjectPtr<UPrimitiveComponent>> Tiled;
	UPROPERTY(Transient) TArray<TObjectPtr<UInstancedStaticMeshComponent>> VehicleMeshes;
};
