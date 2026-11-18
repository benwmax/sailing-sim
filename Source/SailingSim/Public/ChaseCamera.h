#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"

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
 *
 * Slice 4 adds five mounted cameras (FMount, MountFor): the drone and the chase boat stand off in the world and aim at her;
 * the masthead, transom and bow cameras ride on her, their horizon steadied (they roll and pitch a third as much as she
 * does). The cycle runs from far outside to aboard: Chase, Overview, Drone, Chase boat, Masthead, Transom, Bow, Helm. The
 * enum keeps its first three values, so saved views stay valid; the save writes names.
 */
namespace ChaseCamera
{
	// (new views go on the end: Settings holds the number, the save the name)
	enum class EView : uint8 { Chase, Overview, Helm, Drone, ChaseBoat, Masthead, Transom, Bow, Count };
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
	/** Boats this long or longer (m) are ships: RigFor drops the small boats' clamps (ScaleForShip). Every boat before the
	 *  frigate is under it, so their rigs are unchanged. */
	static constexpr float ShipLoaM = 45.f;
	/** A ship's rigs: Chase and Overview rescaled; Classic keeps its fixed lift on an arm long enough to frame her. */
	SAILINGSIM_API void ScaleForShip(FRig& R, ERig Rig, float LoaM, float MastheadZM, float BoomZM);
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

	/** The next view in the cycle (far outside to aboard, then round again). */
	SAILINGSIM_API EView Next(EView View);
	/** Every view, in the cycle's order (Settings > Camera lists them so). */
	SAILINGSIM_API TArrayView<const EView> CycleOrder();
	/** Where View sits in CycleOrder (0 for an unknown value). */
	SAILINGSIM_API int32 CycleIndex(EView View);
	/** The view's id: "Chase", "Overview", "Helm", "Drone", "ChaseBoat", "Masthead", "Transom", "Bow" (the save and -SailingView). */
	SAILINGSIM_API const TCHAR* Name(EView View);
	/** The view's name for people: "Chase boat", "Transom cam" ... */
	SAILINGSIM_API const TCHAR* DisplayName(EView View);
	/** An id or a display name (any case, spaces ignored); false otherwise. */
	SAILINGSIM_API bool Parse(const FString& Text, EView& Out);
	/** The mounted cameras (MountFor): every view but Chase, Overview and Helm. */
	SAILINGSIM_API bool IsMounted(EView View);

	/**
	 * A mounted camera (slice 4). Onboard (masthead, transom, bow): a lens fixed in her frame (metres, X forward, Y starboard,
	 * Z up from her waterline), looking along MountPitch/MountYaw or at AimM, also in her frame; the lens follows RollShare of
	 * her heel and pitch (the rest is steadied, as the helm view's head is). In the world (drone, chase boat): RangeM from her
	 * at HeightM over her mean waterline, BearingDeg off her bow on the leeward side (+ to starboard when she is on port tack),
	 * aimed AimUpM up her middle; her heading is followed with FollowTauS of lag.
	 */
	struct FMount
	{
		bool bOnboard = true;
		FVector LocationM = FVector::ZeroVector;
		bool bAim = false;
		FVector AimM = FVector::ZeroVector;
		float MountPitchDeg = 0.f, MountYawDeg = 0.f;
		float RollShare = 1.f / 3.f;
		float RangeM = 0.f, HeightM = 0.f, BearingDeg = 0.f, AimUpM = 0.f, FollowTauS = 1.f;
		float FovDeg = 90.f;
	};
	/** View's mount on boat C (View must be IsMounted). */
	SAILINGSIM_API FMount MountFor(EView View, const Sailing::FBoatConfig& C);
	/** The mounted views' zoom: the field of view a notch (ZoomRatio) at a time, 30 to 110 deg. */
	static constexpr float MountMinFovDeg = 30.f;
	static constexpr float MountMaxFovDeg = 110.f;
	SAILINGSIM_API float ZoomFov(float FovDeg, float Notches);

	/**
	 * A world camera's bearing on the stern-side circle: 0 is her bow, 180 her stern, 0..360 (port bearings are 360 - b), so
	 * easing from one side to the other always swings round her stern, never across her bow. Starboard is +1 for the
	 * leeward side to starboard (she is on port tack).
	 */
	SAILINGSIM_API float SideBearingDeg(const FMount& Mount, float LeewardSign);
	/** One frame's ease of a stern-side bearing toward Target (time constant TauS). */
	SAILINGSIM_API float EaseBearing(float BearingDeg, float TargetDeg, float DeltaS, float TauS);
	/** A world camera changes sides only after she has held her new tack this long (s): a quick tack and back stays put. */
	static constexpr float SideHoldS = 4.f;
	/** The swing to the new side's time constant (s). */
	static constexpr float SideSwingTauS = 2.5f;
}
