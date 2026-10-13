#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WorldKit.h"
#include "NightLightsActor.generated.h"

class UPointLightComponent;

/**
 * Visual V6: real lights at night from the world kit's fixtures: the bridges' street lamps, the marina's dock lamps and
 * the clubhouse floodlights, and the waterfront businesses (the big OSM blocks by the water: Kemah's boardwalk, marinas,
 * restaurants). A pool of point lights goes to the fixtures nearest the camera: 48 unshadowed on Medium; on High 160,
 * shadowed through MegaLights (stochastic, a fixed cost however many). Lumens are real, scaled into the scene's
 * photometry like the sun (VisualPipeline: SceneEVOffset).
 */
UCLASS()
class SAILINGSIM_API ANightLightsActor : public AActor
{
	GENERATED_BODY()

public:
	ANightLightsActor();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	int32 NumFixtures() const { return Fixtures.Num(); }
	int32 NumLit() const { return Lit; }

private:
	TArray<FKitLight> Fixtures;
	UPROPERTY(Transient) TArray<TObjectPtr<UPointLightComponent>> Pool;
	int32 Lit = 0;
	bool bTidal = false;
};
