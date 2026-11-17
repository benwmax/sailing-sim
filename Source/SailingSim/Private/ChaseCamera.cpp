#include "ChaseCamera.h"

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

	EView Next(EView View)
	{
		return EView((uint8(View) + 1) % uint8(EView::Count));
	}

	const TCHAR* Name(EView View)
	{
		switch (View)
		{
		case EView::Chase: return TEXT("Chase");
		case EView::Overview: return TEXT("Overview");
		case EView::Helm: return TEXT("Helm");
		default: return TEXT("Chase");
		}
	}

	bool Parse(const FString& Text, EView& Out)
	{
		for (uint8 I = 0; I < uint8(EView::Count); ++I)
		{
			if (Text.Equals(Name(EView(I)), ESearchCase::IgnoreCase)) { Out = EView(I); return true; }
		}
		return false;
	}
}
