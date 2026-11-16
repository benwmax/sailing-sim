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
			// The view the game had: two and a half boat lengths off, looking at a third of the mast's height.
			R.PivotUpCm = 0.f;
			R.ArmCm = FMath::Clamp(Loa * 2.4f, 9.f, 40.f) * 100.f;
			R.PitchDeg = -14.f;
			if (Rig == ERig::Classic)
			{
				R.MinArmCm = 400.f;
				R.MaxArmCm = 4000.f;
				R.SocketFixedCm = float(MastheadZM) * 0.33f * 100.f;
				R.bSmoothYaw = false;
			}
			else
			{
				R.MinArmCm = FMath::Clamp(Loa * 0.6f, 4.f, 20.f) * 100.f;
				R.MaxArmCm = FMath::Clamp(Loa * 6.f, 40.f, 150.f) * 100.f;
				R.SocketPerArm = float(MastheadZM) * 0.33f * 100.f / R.ArmCm;
				R.bSmoothYaw = true;
			}
			break;
		}
		return R;
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
