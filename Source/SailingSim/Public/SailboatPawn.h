#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "InputActionValue.h"
#include "SailboatPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UProceduralMeshComponent;
class UInputAction;
class UInputMappingContext;
class UMaterialInterface;

/**
 * The player's J/22. Physics (Sailing::FBoatModel) steps at a fixed 120 Hz; this actor turns the boat's
 * state into visuals (hull, rig, sails shaped by the physics strips, telltales, masthead fly, crew) and
 * the player's input into tiller, sheets, traveler, sail shape and crew weight.
 */
UCLASS()
class SAILINGSIM_API ASailboatPawn : public APawn
{
	GENERATED_BODY()

public:
	ASailboatPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

	const Sailing::FBoatModel& GetBoatModel() const { return Boat; }
	const Sailing::FBoatControls& GetControls() const { return Controls; }
	const Sailing::FWindField& GetWind() const;
	bool IsTrimAssistActive() const;

	/** Puts the boat back at its start, on a beam reach with a little way on. */
	void ResetBoat();

	/** Applies the current difficulty to the physics (helm feel, damping). */
	void ApplyDifficulty();

	/** Initial speed through the water in knots. */
	UPROPERTY(EditAnywhere, Category = "Boat")
	float StartSpeedKnots = 3.f;

	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<USceneComponent> BoatRoot;

	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<UStaticMeshComponent> Hull;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> Camera;

private:
	UStaticMeshComponent* AddPart(FName Name, UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation = FRotator::ZeroRotator, USceneComponent* Parent = nullptr);
	void ApplyStateToTransform();
	void UpdateRigVisuals(float DeltaSeconds);
	void BuildSailMesh(UProceduralMeshComponent* Mesh, const Sailing::FSailGeometry& Geo, const Sailing::FSailStripState* Strips, int32 Side, bool bMain);
	void UpdateTelltales();
	void CreateInput();
	void ApplyHeldInputs(float DeltaSeconds);

	void OnAxis(const FInputActionValue& Value, FName Action);
	void OnAxisReleased(const FInputActionValue& Value, FName Action);
	void OnLook(const FInputActionValue& Value);
	void OnZoom(const FInputActionValue& Value);
	void OnButton(const FInputActionValue& Value, FName Action);

	Sailing::FBoatModel Boat;
	Sailing::FBoatControls Controls;
	Sailing::FFixedStepper Stepper;
	Sailing::FAutoTrim TrimAssist;
	/** -SailingDemo: the autopilot sails close-hauled and tacks every few seconds, for recordings and the QA gate. */
	bool bDemo = false;
	Sailing::FAutopilot DemoPilot;
	double DemoFirstSign = 1.0;
	Sailing::FWindField FallbackWind;
	double WaterSurfaceZ = 0.0; // cm
	FVector StartLocation = FVector::ZeroVector;
	float StartYaw = 0.f;

	/** Held axis values from the input system, applied each frame as rates. */
	TMap<FName, float> HeldAxes;
	float KeyboardTiller = 0.f;
	double LastManualTrimTime = -100.0;
	float CameraYaw = 0.f;
	float CameraPitch = -14.f;
	float CameraDistance = 1600.f;
	float VisualTime = 0.f;

	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> ShapeMaterial;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> MainSail;
	UPROPERTY(Transient) TObjectPtr<UProceduralMeshComponent> JibSail;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> BoomPivot;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RudderPivot;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> MastheadFly;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Crew;
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> JibTelltales;  // windward/leeward pairs at three heights
	UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> LeechTelltales; // main leech, three heights

	UPROPERTY(Transient) TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient) TMap<FName, TObjectPtr<UInputAction>> Actions;
};
