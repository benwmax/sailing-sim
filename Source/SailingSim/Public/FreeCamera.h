#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FreeCameraMath.h"
#include "FreeCamera.generated.h"

class UCameraComponent;

UENUM()
enum class EFreeCameraMode : uint8
{
	Fly,     // a drone: moves on its level heading, looks anywhere
	Orbit,   // turns about the anchor, the wheel in and out
};

/**
 * Orbit parameters set from code (the menus' showroom and weather framings, docs/showroom-wiring/): where it turns,
 * how far, its limits, and an idle auto-spin. Pitch is the camera's (negative looks down on the pivot).
 */
struct FFreeCameraOrbit
{
	float YawDeg = 0.f, PitchDeg = -12.f;
	float DistanceCm = 1200.f, MinDistanceCm = 150.f, MaxDistanceCm = 30000.f;
	float MinPitchDeg = -89.f, MaxPitchDeg = 60.f;
	/** The pivot moved right (+) of the view, and up, so the subject sits off centre (a side panel covers part). */
	float LateralOffsetCm = 0.f, UpOffsetCm = 0.f;
	/** Turns about the pivot at this rate once SpinIdleSeconds pass without a look (0: never). */
	float SpinDegPerSec = 0.f, SpinIdleSeconds = 4.f;
	/** How long the camera takes to get to a new place (95%). */
	float EaseSeconds = 0.25f;
};

/** One frame's held input (axes -1..1). Looks arrive as they come (AddLook). */
struct FFreeCameraInput
{
	FVector2D Move = FVector2D::ZeroVector;  // X right, Y forward
	float Vertical = 0.f;                    // up
	float Roll = 0.f;                        // clockwise
	bool bBoost = false, bSlow = false;
};

/**
 * A free camera: fly, look and orbit, with a leash to an anchor, a floor over the water and the ground, a ceiling, and
 * a swept sphere so it stops at things it would enter. No photo logic: photo mode puts its lens on GetCamera() and
 * feeds the input; a replay's free camera can anchor it to the replayed boat. Client-only: it reads the world and never
 * touches a boat. The owner calls Update each frame (it does not tick itself), so it moves while the world is held.
 */
UCLASS(NotBlueprintable)
class SAILINGSIM_API AFreeCamera : public AActor
{
	GENERATED_BODY()

public:
	AFreeCamera();

	UCameraComponent* GetCamera() const { return Camera; }

	/** What the leash and the orbit are about; the orbit turns about its location plus PivotOffsetCm. */
	void SetAnchor(AActor* InAnchor, const FVector& InPivotOffsetCm = FVector::ZeroVector);
	AActor* GetAnchor() const { return Anchor.Get(); }
	FFreeCameraLimits Limits;

	/** Puts the camera here, still (entering from another camera, or back to the boat). */
	void SnapTo(const FVector& LocationCm, const FRotator& Rotation);
	/** Asks for a place (a still's, from the command line): through the leash, floor and ceiling, without the sweep. */
	void PlaceAt(const FVector& LocationCm, const FRotator& Rotation);
	void SetMode(EFreeCameraMode InMode);
	/** Orbit with these parameters, easing over from wherever the camera is (no jump). */
	void SetOrbit(const FFreeCameraOrbit& InOrbit);
	const FFreeCameraOrbit& GetOrbit() const { return Orbit; }
	/** The orbit's pivot right now (the anchor plus offsets), world cm. */
	FVector GetPivot() const { return Pivot(); }
	EFreeCameraMode GetMode() const { return Mode; }

	/** Mouse or right stick, in degrees: yaw right, pitch up. */
	void AddLook(const FVector2D& DeltaDeg);
	/** Wheel notches: in fly mode they step the base speed, in orbit mode the distance. */
	void StepSpeed(int32 Steps);
	void ResetRoll() { Roll = 0.f; }
	float GetRollDeg() const { return Roll; }
	void SetRollDeg(float Deg) { Roll = FMath::Clamp(Deg, -45.f, 45.f); }
	void Update(float DeltaSeconds, const FFreeCameraInput& Input);

	int32 GetSpeedIndex() const { return SpeedIndex; }
	double GetBaseSpeed() const { return FreeCameraMath::SpeedStep(SpeedIndex); }
	/** Horizontal distance from the anchor (m), and whether the leash is slowing the camera. */
	double GetLeashDistanceM() const;
	bool IsAtLeash() const { return GetLeashDistanceM() > Limits.LeashM - Limits.LeashSoftM; }

	/** The water's height under a world point (m, physics frame) and the ground's: the world's own when there is a game
	 *  mode, else flat water and no ground. Public for the tests. */
	double WaveHeightAt(const FVector& WorldCm) const;
	double GroundHeightAt(const FVector& WorldCm) const;

private:
	UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
	TWeakObjectPtr<AActor> Anchor;
	FVector PivotOffsetCm = FVector::ZeroVector;
	EFreeCameraMode Mode = EFreeCameraMode::Fly;
	float Yaw = 0.f, Pitch = 0.f, Roll = 0.f;
	FFreeCameraOrbit Orbit;
	double SinceLookSeconds = 1e9;
	int32 SpeedIndex = 1;
	FVector VelocityMps = FVector::ZeroVector;

	FVector Pivot() const;
	/** The limits on a wanted move from the current location: leash, sweep, floor and ceiling. */
	FVector Constrain(const FVector& From, const FVector& To, bool bIgnoreAnchor, bool bSweep = true) const;
};
