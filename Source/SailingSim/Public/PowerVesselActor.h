#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Traffic.h"
#include "PowerVesselActor.generated.h"

class UStaticMeshComponent;
class UMaterialInterface;

/**
 * A power-driven vessel of the traffic, drawn from the Blender-built models (simple shapes on Low): a runabout, a shrimp trawler with her outriggers,
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

	/** bTanker: a Ship drawn as the tanker (the Gulf Pride) rather than the container ship. */
	void Build(Sailing::ETrafficKind Kind, bool bTanker = false);
	Sailing::ETrafficKind GetKind() const { return Kind; }
	/** Moves her to the simulated vessel and lights her for the observer (lights show only over their arcs). */
	void UpdateFrom(const Sailing::FTrafficVessel& Vessel, bool bDark, const FVector& Observer, float Time);

private:
	UStaticMeshComponent* Part(UStaticMesh* Mesh, const FVector& LocationM, const FVector& SizeM, const FLinearColor& Color, const FRotator& Rotation = FRotator::ZeroRotator);
	/** Adds a vessel model from /Game/World/Vessels; false (draw the boxes) on Low or when it is missing. */
	bool Model(const TCHAR* Name, const FVector& LocationM, const FVector& Scale = FVector::OneVector);
	/** The container ship's deck cargo. */
	void Containers(float Beam);
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
	/** Visual V7: her engine (an outboard's buzz, a diesel's throb) and, behind a shrimper, the gulls. */
	UPROPERTY(Transient) TArray<TObjectPtr<class USailingWorldSynth>> Voices;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cube;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cylinder;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Cone;
	UPROPERTY(Transient) TObjectPtr<UStaticMesh> Sphere;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EmissiveMaterial;
	Sailing::ETrafficKind Kind = Sailing::ETrafficKind::Powerboat;

	/** Graphics G8 Ultra showcase: her exhaust. A ship's, a towboat's or a shrimper's black diesel smoke from the stack, a
	 *  runabout's pale haze low at the stern: soft puffs (M_Smoke) emitted with the throttle, carried by the wind at the
	 *  stack (FWindField) and the vessel's own motion, rising, spreading and fading. Ultra only, within 3 km of the camera. */
	void UpdateExhaust(const Sailing::FTrafficVessel& Vessel, const FVector& Observer, float Time);
	struct FPuff { FVector P, V; float Age = 0.f, Life = 1.f, Size0 = 1.f, Size1 = 4.f, Shade = 0.1f, Alpha = 0.5f; };
	TArray<FPuff> Puffs;
	float LastExhaustTime = -1.f, EmitDebt = 0.f;
	FRandomStream ExhaustRng;
	UPROPERTY(Transient) TObjectPtr<class UInstancedStaticMeshComponent> Exhaust;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> SmokeMaterial;
};
