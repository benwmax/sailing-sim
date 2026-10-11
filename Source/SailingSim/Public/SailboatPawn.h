#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BoatPhysicsStub.h"
#include "FixedStepper.h"
#include "InputActionValue.h"
#include "SailboatPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UInputAction;
class UInputMappingContext;

/**
 * Placeholder J/22: a simple box-and-cylinder mesh driven by the SailingPhysics stub at a fixed 120 Hz.
 * Keyboard: A/D steer, W/S motor, mouse orbits the chase camera.
 * Controller: left stick steers, triggers drive, right stick orbits the camera.
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

	const Sailing::FBoatState& GetBoatState() const { return Physics.State; }
	Sailing::FBoatControls Controls;

	/** Height offset of the initial drop above the waterline, in meters, so the float settles visibly. */
	UPROPERTY(EditAnywhere, Category = "Boat")
	float InitialDropMeters = 0.25f;

	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<USceneComponent> BoatRoot;

	UPROPERTY(VisibleAnywhere, Category = "Boat")
	TObjectPtr<UStaticMeshComponent> Hull;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> Camera;

private:
	UStaticMeshComponent* AddPart(FName Name, UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation = FRotator::ZeroRotator);
	void ApplyStateToTransform();
	void CreateInput();

	void OnSteer(const FInputActionValue& Value) { Controls.Rudder = Value.Get<float>(); }
	void OnSteerReleased(const FInputActionValue&) { Controls.Rudder = 0.0; }
	void OnThrottle(const FInputActionValue& Value) { Controls.Throttle = Value.Get<float>(); }
	void OnThrottleReleased(const FInputActionValue&) { Controls.Throttle = 0.0; }
	void OnLook(const FInputActionValue& Value);

	Sailing::FBoatPhysicsStub Physics;
	Sailing::FFixedStepper Stepper;
	double WaterSurfaceZMeters = 0.0;
	float CameraYaw = 0.f;
	float CameraPitch = -12.f;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> SteerAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> ThrottleAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookAction;
};
