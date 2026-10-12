#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Traffic.h"
#include "PowerVesselActor.generated.h"

class UStaticMeshComponent;
class UMaterialInterface;

/**
 * A power-driven vessel of the traffic, drawn from simple shapes: a runabout, a shrimp trawler with her outriggers,
 * a towboat pushing barges, a deep-draft ship, or the race committee boat. Each carries the lights of her status
 * (Rules 23 to 30: masthead, sidelights and sternlight over their arcs; all-round green over white trawling; red-
 * white-red restricted in ability to maneuver; three reds constrained by draft; a white anchor light) and her day
 * shape (two cones, ball-diamond-ball, a cylinder, a ball).
 */
UCLASS()
class SAILINGSIM_API APowerVesselActor : public AActor
{
	GENERATED_BODY()

public:
	APowerVesselActor();

	void Build(Sailing::ETrafficKind Kind);
	/** Moves her to the simulated vessel and lights her for the observer (lights show only over their arcs). */
	void UpdateFrom(const Sailing::FTrafficVessel& Vessel, bool bDark, const FVector& Observer, float Time);

private:
	UStaticMeshComponent* Part(UStaticMesh* Mesh, const FVector& LocationM, const FVector& SizeM, const FLinearColor& Color, const FRotator& Rotation = FRotator::ZeroRotator);
	/** A navigation light: shown when the observer's bearing from the bow (degrees) lies within [ArcFrom, ArcTo]. */
	void Light(const FVector& LocationM, const FLinearColor& Color, float ArcFrom, float ArcTo);

	struct FNavLight
	{
		TObjectPtr<UStaticMeshComponent> Mesh;
		FVector Local;
		float ArcFrom = -180.f, ArcTo = 180.f;
	};
	TArray<FNavLight> Lights;
	TArray<TObjectPtr<UStaticMeshComponent>> DayShapes;

	UPROPERTY(Transient) TObjectPtr<USceneComponent> Root;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cube;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cylinder;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cone;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Sphere;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EmissiveMaterial;
	Sailing::ETrafficKind Kind = Sailing::ETrafficKind::Powerboat;
};
