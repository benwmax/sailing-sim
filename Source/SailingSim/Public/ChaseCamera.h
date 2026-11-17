#pragma once

#include "CoreMinimal.h"

/**
 * Camera views slice 1 (docs/camera-views/, plan: the "Camera Views Plan" page, Bean Nov 16 2026: "go with your picks").
 * The chase camera's rig as plain numbers, so the tests hold every boat in frame at every zoom:
 *
 * - Chase (the players' default): the arm turns about a point at boom height over the boat's origin and its lens looks
 *   at it, a little low in the frame (the socket's push grows with the arm, so zooming never moves the boat on screen).
 *   About 3 m up on the J/22, far enough back (1.55 masthead heights, at least 1.8 boat lengths) that the masthead is in frame.
 * - Overview: the old high view (arm 2.4 boat lengths, a third of the masthead up, 14 deg down), with the push scaled the
 *   same way so zooming in keeps the hull in frame.
 * - Classic: the old rig exactly (fixed push). Measured runs and stills that name no view use it, so benches, gates and
 *   the bench views' screenshots don't move.
 * - Helm is the cockpit view (ASailboatPawn::UpdateCockpitCamera); it is in the cycle but has no arm.
 *
 * Zoom is by ratio (ZoomRatio a notch), and the view eases back behind the boat after the player stops looking.
 */
namespace ChaseCamera
{
	enum class EView : uint8 { Chase, Overview, Helm, Count };
	enum class ERig : uint8 { Chase, Overview, Classic };

	struct FRig
	{
		float PivotUpCm = 0.f;       // the arm's origin over the boat's origin (it turns and looks about here)
		float ArmCm = 1600.f;        // the default distance
		float MinArmCm = 400.f, MaxArmCm = 4000.f;
		float SocketPerArm = 0.f;    // the lens's push up, as a share of the arm (constant framing through zoom)
		float SocketFixedCm = 0.f;   // or a fixed push (Classic)
		float PitchDeg = -14.f;      // the default pitch (negative looks down)
		bool bSmoothYaw = false;     // the arm's direction follows the hull's with a lag (not Classic: measured runs)
	};

	/** The rig for a boat (metres: length overall, masthead and gooseneck heights over her origin). */
	SAILINGSIM_API FRig RigFor(ERig Rig, double LengthOverallM, double MastheadZM, double BoomZM);
	/** The lens's push up at the end of an arm of ArmCm. */
	SAILINGSIM_API float SocketUpCm(const FRig& Rig, float ArmCm);
	/** How far below the middle of the frame the arm's origin sits (deg), for an arm of ArmCm. */
	SAILINGSIM_API float PivotBelowCentreDeg(const FRig& Rig, float ArmCm);

	/** Each wheel notch moves the camera in (or out) by this ratio of its distance. */
	static constexpr float ZoomRatio = 0.88f;
	SAILINGSIM_API float Zoom(const FRig& Rig, float ArmCm, float Notches);

	/** The view eases back behind the boat this long after the player last turned it (s), ... */
	static constexpr float RecentreAfterS = 2.5f;
	/** ... with this time constant (s), keeping the pitch. */
	static constexpr float RecentreTauS = 0.8f;
	/** The yaw (deg, relative to the bow, 0 astern of her looking forward) one frame on: unchanged before RecentreAfterS. */
	SAILINGSIM_API float RecentreYaw(float YawDeg, float DeltaS, float SinceLookS);

	/** The arm's direction follows the hull's heading with this lag speed (UE spring arm units, 1/s) while nobody looks. */
	static constexpr float YawLagSpeed = 2.5f;

	SAILINGSIM_API EView Next(EView View);
	SAILINGSIM_API const TCHAR* Name(EView View);
	/** "Chase", "Overview", "Helm" (any case); false otherwise. */
	SAILINGSIM_API bool Parse(const FString& Text, EView& Out);
}
