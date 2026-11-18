#include "ChaseCamera.h"
#include "ReferenceCapture.h"

namespace ChaseCamera
{
	FRig RigFor(ERig Rig, double LengthOverallM, double MastheadZM, double BoomZM)
	{
		const float Loa = float(FMath::Max(LengthOverallM, 1.0));
		FRig R;
		switch (Rig)
		{
		case ERig::Chase:
			// At boom height (the gooseneck: the cockpit, the crew, the foot of the sails), 4 deg down, the pivot 3.4 deg under
			// the middle of the frame, and far enough back that the masthead is in a 16:9 frame at 90 deg (1.55 masthead
			// heights, at least 1.8 boat lengths): the J/22's lens is about 3 m over the water, 14 m astern.
			R.PivotUpCm = FMath::Clamp(float(BoomZM), 0.6f, 4.f) * 100.f;
			R.ArmCm = FMath::Clamp(FMath::Max(Loa * 1.8f, float(MastheadZM) * 1.55f), 7.f, 75.f) * 100.f;
			R.MinArmCm = FMath::Clamp(Loa * 0.6f, 3.f, 20.f) * 100.f;
			R.MaxArmCm = FMath::Clamp(Loa * 6.f, 30.f, 150.f) * 100.f;
			R.SocketPerArm = 0.06f;
			R.PitchDeg = -4.f;
			R.bSmoothYaw = true;
			break;
		case ERig::Overview:
		case ERig::Classic:
		default:
		{
			// The view the game had: two and a half boat lengths off, looking at a third of the mast's height.
			R.PivotUpCm = 0.f;
			const float LookUpCm = float(MastheadZM) * 0.33f * 100.f;
			// (docs/jclass-14/: from the old 40 m cap, Bluebonnet's 48 m rig looks up so steeply that her hull leaves the frame's
			// bottom 8 deg; the arm keeps that look-up within 21.2 deg. Every other boat, the maxi's 46.7 m too, keeps the old arm.)
			R.ArmCm = FMath::Max(FMath::Clamp(Loa * 2.4f, 9.f, 40.f) * 100.f, LookUpCm / FMath::Tan(FMath::DegreesToRadians(21.2f)));
			R.PitchDeg = -14.f;
			if (Rig == ERig::Classic)
			{
				R.MinArmCm = 400.f;
				R.MaxArmCm = FMath::Max(4000.f, R.ArmCm);
				R.SocketFixedCm = LookUpCm;
				R.bSmoothYaw = false;
			}
			else
			{
				R.MinArmCm = FMath::Clamp(Loa * 0.6f, 4.f, 20.f) * 100.f;
				R.MaxArmCm = FMath::Clamp(Loa * 6.f, 40.f, 150.f) * 100.f;
				R.SocketPerArm = LookUpCm / R.ArmCm;
				R.bSmoothYaw = true;
			}
			break;
		}
		}
		if (Loa >= ShipLoaM) ScaleForShip(R, Rig, Loa, float(MastheadZM), float(BoomZM));
		return R;
	}

	void ScaleForShip(FRig& R, ERig Rig, float Loa, float MastheadZM, float BoomZM)
	{
		// A ship (the frigate, 62 m over her jib boom, her main truck about 60 m up: docs/ship-walk/): the small boats'
		// clamps would park the lens inside her rigging. The same framing rules without them: the arm's origin at her
		// quarterdeck's height (the spanker boom's, at most 9 m), far enough back for the trucks, never in closer than
		// 0.6 of her length. The classic view keeps its fixed lift (a third of the masthead) on the longer arm.
		R.MinArmCm = Loa * 0.6f * 100.f;
		R.MaxArmCm = FMath::Min(Loa * 6.f, 450.f) * 100.f;
		if (Rig == ERig::Chase)
		{
			R.PivotUpCm = FMath::Clamp(BoomZM, 0.6f, 9.f) * 100.f;
			R.ArmCm = FMath::Max(Loa * 1.8f, MastheadZM * 1.55f) * 100.f;
		}
		else
		{
			R.ArmCm = Loa * 2.4f * 100.f;
			if (Rig != ERig::Classic) R.SocketPerArm = MastheadZM * 0.33f * 100.f / R.ArmCm;
		}
		R.ArmCm = FMath::Clamp(R.ArmCm, R.MinArmCm, R.MaxArmCm);
	}

	float SocketUpCm(const FRig& Rig, float ArmCm)
	{
		return Rig.SocketPerArm > 0.f ? Rig.SocketPerArm * ArmCm : Rig.SocketFixedCm;
	}

	float PivotBelowCentreDeg(const FRig& Rig, float ArmCm)
	{
		return FMath::RadiansToDegrees(FMath::Atan2(SocketUpCm(Rig, ArmCm), FMath::Max(ArmCm, 1.f)));
	}

	float Zoom(const FRig& Rig, float ArmCm, float Notches)
	{
		return FMath::Clamp(ArmCm * FMath::Pow(ZoomRatio, Notches), Rig.MinArmCm, Rig.MaxArmCm);
	}

	float RecentreYaw(float YawDeg, float DeltaS, float SinceLookS)
	{
		if (SinceLookS < RecentreAfterS || DeltaS <= 0.f) return YawDeg;
		const float Wrapped = FMath::UnwindDegrees(YawDeg);
		const float Back = Wrapped * FMath::Exp(-DeltaS / RecentreTauS);
		return FMath::Abs(Back) < 0.05f ? 0.f : Back;
	}

	namespace
	{
		// Far outside to aboard (slice 4), the order racing games keep: chase, far chase, helicopter, TV side camera, then
		// the cameras on the boat, the cockpit last.
		constexpr EView kCycle[] = { EView::Chase, EView::Overview, EView::Drone, EView::ChaseBoat, EView::Masthead, EView::Transom, EView::Bow, EView::Helm };
		static_assert(UE_ARRAY_COUNT(kCycle) == size_t(EView::Count), "every view is in the cycle");
	}

	TArrayView<const EView> CycleOrder()
	{
		return TArrayView<const EView>(kCycle, UE_ARRAY_COUNT(kCycle));
	}

	int32 CycleIndex(EView View)
	{
		for (int32 I = 0; I < int32(UE_ARRAY_COUNT(kCycle)); ++I)
		{
			if (kCycle[I] == View) return I;
		}
		return 0;
	}

	EView Next(EView View)
	{
		return kCycle[(CycleIndex(View) + 1) % int32(UE_ARRAY_COUNT(kCycle))];
	}

	const TCHAR* Name(EView View)
	{
		switch (View)
		{
		case EView::Chase: return TEXT("Chase");
		case EView::Overview: return TEXT("Overview");
		case EView::Helm: return TEXT("Helm");
		case EView::Drone: return TEXT("Drone");
		case EView::ChaseBoat: return TEXT("ChaseBoat");
		case EView::Masthead: return TEXT("Masthead");
		case EView::Transom: return TEXT("Transom");
		case EView::Bow: return TEXT("Bow");
		default: return TEXT("Chase");
		}
	}

	const TCHAR* DisplayName(EView View)
	{
		switch (View)
		{
		case EView::ChaseBoat: return TEXT("Chase boat");
		case EView::Transom: return TEXT("Transom cam");
		default: return Name(View);
		}
	}

	bool Parse(const FString& Text, EView& Out)
	{
		const FString Key = Text.Replace(TEXT(" "), TEXT(""));
		for (uint8 I = 0; I < uint8(EView::Count); ++I)
		{
			const FString Display = FString(DisplayName(EView(I))).Replace(TEXT(" "), TEXT(""));
			if (Key.Equals(Name(EView(I)), ESearchCase::IgnoreCase) || Key.Equals(Display, ESearchCase::IgnoreCase)) { Out = EView(I); return true; }
		}
		return false;
	}

	bool IsMounted(EView View)
	{
		return View != EView::Chase && View != EView::Overview && View != EView::Helm && View < EView::Count;
	}

	FMount MountFor(EView View, const Sailing::FBoatConfig& C)
	{
		static const Sailing::FHullShape NoHull;
		const Sailing::FHullShape& Hull = C.Hulls.empty() ? NoHull : C.Hulls[0];
		auto SheerAt = [&](double X) { return C.bMultihull ? Hull.SheerZ : Hull.SheerHeight(X); };
		const float Mast = float(FMath::Max(C.MastheadZ, 2.0));
		FMount M;
		switch (View)
		{
		case EView::Bow:
		{
			// The bumper camera: on the stem head, ahead of the jib's tack (behind it the lens would be inside the jib's foot),
			// a little over the deck, looking forward and a little down at the waves. On a multihull, between the bows.
			const double X = Hull.BowX - 0.05;
			M.LocationM = FVector(X, 0.0, SheerAt(X) + FMath::Clamp(0.04 * C.LengthOverall, 0.25, 0.9));
			M.MountPitchDeg = -8.f;
			M.FovDeg = 95.f;
			break;
		}
		case EView::Transom:
		{
			// The reference captures' action camera (OnboardCameraMount), looking forward over the cockpit at crew and sails.
			FVector L; FRotator R;
			OnboardCameraMount(ECapturePreset::ActionCam, C, 1.f, L, R);
			M.LocationM = L / 100.0;   // (cm to m)
			M.MountPitchDeg = float(R.Pitch);
			M.FovDeg = 100.f;
			break;
		}
		case EView::Masthead:
		{
			// The TV shot: just over the masthead, a little aft of the mast (clear of its section and the main's head), looking
			// down at her deck halfway between the mast and the stern, so the boom, the cockpit and the crew are in the middle.
			const double AimX = 0.5 * (C.MastX + Hull.SternX);
			M.LocationM = FVector(C.MastX - 0.35, 0.0, C.MastheadZ + 0.35);
			M.bAim = true;
			M.AimM = FVector(AimX, 0.0, SheerAt(AimX));
			M.FovDeg = 80.f;
			break;
		}
		case EView::ChaseBoat:
		{
			// A camera boat to leeward just ahead of abeam, 1.5 m over the water (a RIB's camera), far enough off to frame her
			// rig: the reference captures' chase range, aimed a little under half the mast so the masthead and the waterline fit.
			M.bOnboard = false;
			M.RangeM = FMath::Max(15.f, 1.9f * Mast);
			M.HeightM = 1.5f;
			M.BearingDeg = 80.f;
			M.AimUpM = 0.45f * Mast;
			M.FollowTauS = 1.f;
			M.FovDeg = 65.f;
			break;
		}
		case EView::Drone:
		default:
		{
			// The reference captures' drone, on her leeward quarter: 30 m up and 30 m off (more for a big boat), following slowly.
			M.bOnboard = false;
			M.RangeM = FMath::Max(30.f, 3.f * float(C.LengthOverall));
			M.HeightM = FMath::Max(30.f, 2.f * Mast);
			M.BearingDeg = 135.f;
			M.AimUpM = 0.2f * Mast;
			M.FollowTauS = 2.f;
			M.FovDeg = 70.f;
			break;
		}
		}
		return M;
	}

	float ZoomFov(float FovDeg, float Notches)
	{
		return FMath::Clamp(FovDeg * FMath::Pow(ZoomRatio, Notches), MountMinFovDeg, MountMaxFovDeg);
	}

	float SideBearingDeg(const FMount& Mount, float LeewardSign)
	{
		return LeewardSign >= 0.f ? Mount.BearingDeg : 360.f - Mount.BearingDeg;
	}

	float EaseBearing(float BearingDeg, float TargetDeg, float DeltaS, float TauS)
	{
		// (both on 0..360 measured from the bow: the straight line between them passes the stern, never the bow)
		if (DeltaS <= 0.f) return BearingDeg;
		const float K = 1.f - FMath::Exp(-DeltaS / FMath::Max(TauS, 1e-3f));
		const float B = BearingDeg + (TargetDeg - BearingDeg) * K;
		return FMath::Abs(TargetDeg - B) < 0.05f ? TargetDeg : B;
	}
}
