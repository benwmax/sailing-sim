#include "PhotoSettings.h"

namespace PhotoMath
{
	float Aperture(int32 Stop)
	{
		static const float Stops[NumApertures] = { 1.4f, 2.f, 2.8f, 4.f, 5.6f, 8.f, 11.f, 16.f, 22.f };
		return Stops[FMath::Clamp(Stop, 0, NumApertures - 1)];
	}

	const TArray<float>& FocalMarks()
	{
		static const TArray<float> Marks = { 14.f, 18.f, 24.f, 28.f, 35.f, 50.f, 70.f, 85.f, 105.f, 135.f, 200.f };
		return Marks;
	}

	float FovForFocal(float FocalMm)
	{
		return FMath::RadiansToDegrees(2.f * FMath::Atan(18.f / FMath::Max(FocalMm, 1.f)));
	}

	float FocalForFov(float FovDeg)
	{
		return 18.f / FMath::Tan(FMath::DegreesToRadians(FMath::Clamp(FovDeg, 1.f, 170.f)) * 0.5f);
	}

	float StepFocal(float FocalMm, int32 Dir)
	{
		const TArray<float>& M = FocalMarks();
		if (Dir > 0)
		{
			for (float F : M) if (F > FocalMm * 1.02f) return F;
			return M.Last();
		}
		for (int32 I = M.Num() - 1; I >= 0; --I) if (M[I] < FocalMm * 0.98f) return M[I];
		return M[0];
	}

	int32 PageOf(EPhotoRow Row)
	{
		switch (Row)
		{
		case EPhotoRow::Focal: case EPhotoRow::Roll: return 0;
		case EPhotoRow::FocusMode: case EPhotoRow::FocusDistance: case EPhotoRow::Aperture: return 1;
		case EPhotoRow::Exposure: case EPhotoRow::Vignette: case EPhotoRow::Grain: case EPhotoRow::Look: return 2;
		case EPhotoRow::HideBoat: case EPhotoRow::HideOthers: case EPhotoRow::HideCrew: case EPhotoRow::SunHour: return 3;
		default: return 4;
		}
	}

	const TCHAR* PageName(int32 Page)
	{
		static const TCHAR* Names[NumPages] = { TEXT("Camera"), TEXT("Focus"), TEXT("Exposure"), TEXT("Scene"), TEXT("Frame") };
		return Names[FMath::Clamp(Page, 0, NumPages - 1)];
	}

	EPhotoRow FirstRowOf(int32 Page)
	{
		for (int32 R = 0; R < int32(EPhotoRow::Count); ++R) if (PageOf(EPhotoRow(R)) == Page) return EPhotoRow(R);
		return EPhotoRow::Focal;
	}

	const TCHAR* RowLabel(EPhotoRow Row)
	{
		switch (Row)
		{
		case EPhotoRow::Focal: return TEXT("Focal length");
		case EPhotoRow::Roll: return TEXT("Tilt");
		case EPhotoRow::FocusMode: return TEXT("Focus");
		case EPhotoRow::FocusDistance: return TEXT("Distance");
		case EPhotoRow::Aperture: return TEXT("Aperture");
		case EPhotoRow::Exposure: return TEXT("Exposure");
		case EPhotoRow::Vignette: return TEXT("Vignette");
		case EPhotoRow::Grain: return TEXT("Grain");
		case EPhotoRow::Look: return TEXT("Look");
		case EPhotoRow::HideBoat: return TEXT("My boat");
		case EPhotoRow::HideOthers: return TEXT("Other boats");
		case EPhotoRow::HideCrew: return TEXT("Crew");
		case EPhotoRow::SunHour: return TEXT("Time of day");
		case EPhotoRow::Grid: return TEXT("Thirds grid");
		case EPhotoRow::Crop: return TEXT("Crop guide");
		case EPhotoRow::Capture: return TEXT("Capture size");
		default: return TEXT("");
		}
	}

	float StepSunHour(float SunHour, int32 Dir, float ClockHour)
	{
		const float Clock = FMath::RoundToFloat(FMath::Fmod(FMath::Max(ClockHour, 0.f), 24.f) * 2.f) * 0.5f;
		if (SunHour < 0.f) return FMath::Clamp(Clock + 0.5f * Dir, 0.f, 23.5f);
		const float Next = FMath::Clamp(SunHour + 0.5f * Dir, 0.f, 23.5f);
		// Passing (or reaching) the clock's half hour goes back to the clock.
		if (Next == SunHour) return SunHour;
		if (FMath::IsNearlyEqual(Next, Clock) || (SunHour - Clock) * (Next - Clock) < 0.f) return -1.f;
		return Next;
	}

	void StepRow(FPhotoSettings& S, EPhotoRow Row, int32 Dir, float& FovDeg, float& RollDeg, bool bHighTier, float ClockHour)
	{
		Dir = Dir > 0 ? 1 : -1;
		auto Cycle = [Dir](uint8 V, int32 N) { return uint8((int32(V) + Dir + N) % N); };
		switch (Row)
		{
		case EPhotoRow::Focal: FovDeg = FovForFocal(StepFocal(FocalForFov(FovDeg), Dir)); break;
		case EPhotoRow::Roll: RollDeg = FMath::Clamp(FMath::RoundToFloat(RollDeg / 5.f) * 5.f + 5.f * Dir, -45.f, 45.f); break;
		case EPhotoRow::FocusMode: S.Focus = EPhotoFocus(Cycle(uint8(S.Focus), 3)); break;
		case EPhotoRow::FocusDistance: S.ManualFocusM = FMath::Clamp(S.ManualFocusM * (Dir > 0 ? 1.25f : 0.8f), 0.5f, 2000.f); break;
		case EPhotoRow::Aperture: S.ApertureStop = FMath::Clamp(S.ApertureStop + Dir, 0, NumApertures); break;
		case EPhotoRow::Exposure: S.ExposureEV = FMath::Clamp(FMath::RoundToFloat((S.ExposureEV + 0.5f * Dir) * 2.f) * 0.5f, -3.f, 3.f); break;
		case EPhotoRow::Vignette: S.Vignette = FMath::Clamp(FMath::RoundToFloat((S.Vignette + 0.1f * Dir) * 10.f) * 0.1f, 0.f, 1.f); break;
		case EPhotoRow::Grain: S.Grain = FMath::Clamp(FMath::RoundToFloat((S.Grain + 0.1f * Dir) * 10.f) * 0.1f, 0.f, 1.f); break;
		case EPhotoRow::Look: S.Look = EPhotoLook(Cycle(uint8(S.Look), 3)); break;
		case EPhotoRow::HideBoat: S.bHideMyBoat = !S.bHideMyBoat; break;
		case EPhotoRow::HideOthers: S.bHideOthers = !S.bHideOthers; break;
		case EPhotoRow::HideCrew: S.bHideCrew = !S.bHideCrew; break;
		case EPhotoRow::SunHour: S.SunHour = StepSunHour(S.SunHour, Dir, ClockHour); break;
		case EPhotoRow::Grid: S.bGrid = !S.bGrid; break;
		case EPhotoRow::Crop: S.Crop = EPhotoCrop(Cycle(uint8(S.Crop), 5)); break;
		case EPhotoRow::Capture: S.CaptureScale = bHighTier && S.CaptureScale == 1 ? 2 : 1; break;
		default: break;
		}
	}

	FString RowValue(const FPhotoSettings& S, EPhotoRow Row, float FovDeg, float RollDeg, float FocusM, bool bHighTier)
	{
		auto Dist = [](float M) { return M < 10.f ? FString::Printf(TEXT("%.1f m"), M) : M < 1000.f ? FString::Printf(TEXT("%.0f m"), M) : FString::Printf(TEXT("%.1f km"), M / 1000.f); };
		auto Shown = [](bool bHidden) { return FString(bHidden ? TEXT("Hidden") : TEXT("Shown")); };
		switch (Row)
		{
		case EPhotoRow::Focal: return FString::Printf(TEXT("%.0f mm"), FocalForFov(FovDeg));
		case EPhotoRow::Roll: return FMath::Abs(RollDeg) < 0.5f ? FString(TEXT("Level")) : FString::Printf(TEXT("%+.0f°"), RollDeg);
		case EPhotoRow::FocusMode:
		{
			const TCHAR* Mode = S.Focus == EPhotoFocus::Auto ? TEXT("Auto (centre)") : S.Focus == EPhotoFocus::Boat ? TEXT("My boat") : TEXT("Manual");
			return FString::Printf(TEXT("%s, %s"), Mode, *Dist(FocusM));
		}
		case EPhotoRow::FocusDistance: return Dist(S.ManualFocusM);
		case EPhotoRow::Aperture: return S.ApertureStop >= NumApertures ? FString(TEXT("Off (all sharp)")) : FString::Printf(TEXT("f/%g"), Aperture(S.ApertureStop));
		case EPhotoRow::Exposure: return FMath::Abs(S.ExposureEV) < 0.01f ? FString(TEXT("Metered")) : FString::Printf(TEXT("%+.1f EV"), S.ExposureEV);
		case EPhotoRow::Vignette: return FString::Printf(TEXT("%.1f"), S.Vignette);
		case EPhotoRow::Grain: return S.Grain < 0.01f ? FString(TEXT("None")) : FString::Printf(TEXT("%.1f"), S.Grain);
		case EPhotoRow::Look: return S.Look == EPhotoLook::Natural ? TEXT("Natural") : S.Look == EPhotoLook::Cinematic ? TEXT("Cinematic") : TEXT("Black & white");
		case EPhotoRow::HideBoat: return Shown(S.bHideMyBoat);
		case EPhotoRow::HideOthers: return Shown(S.bHideOthers);
		case EPhotoRow::HideCrew: return Shown(S.bHideCrew);
		case EPhotoRow::SunHour:
			return S.SunHour < 0.f ? FString(TEXT("The clock's"))
				: FString::Printf(TEXT("%02d:%02d (look only)"), int32(S.SunHour), int32(FMath::Fmod(S.SunHour, 1.f) * 60.f + 0.5f));
		case EPhotoRow::Grid: return S.bGrid ? TEXT("On") : TEXT("Off");
		case EPhotoRow::Crop:
		{
			static const TCHAR* Names[5] = { TEXT("Off"), TEXT("16:9"), TEXT("3:2"), TEXT("1:1"), TEXT("21:9") };
			return Names[FMath::Clamp(int32(S.Crop), 0, 4)];
		}
		case EPhotoRow::Capture: return !bHighTier ? FString(TEXT("1x (2x on High)")) : S.CaptureScale == 2 ? FString(TEXT("2x")) : FString(TEXT("1x"));
		default: return FString();
		}
	}

	bool RowIdle(const FPhotoSettings& S, EPhotoRow Row, bool bHighTier)
	{
		return (Row == EPhotoRow::FocusDistance && S.Focus != EPhotoFocus::Manual)
			|| ((Row == EPhotoRow::FocusMode || Row == EPhotoRow::FocusDistance) && S.ApertureStop >= NumApertures)
			|| (Row == EPhotoRow::Capture && !bHighTier);
	}

	float CropAspect(EPhotoCrop Crop)
	{
		switch (Crop)
		{
		case EPhotoCrop::Wide169: return 16.f / 9.f;
		case EPhotoCrop::Photo32: return 3.f / 2.f;
		case EPhotoCrop::Square: return 1.f;
		case EPhotoCrop::Cinema219: return 21.f / 9.f;
		default: return 0.f;
		}
	}

	FVector4f CropRect(EPhotoCrop Crop, float W, float H)
	{
		const float A = CropAspect(Crop);
		if (A <= 0.f || W <= 0.f || H <= 0.f) return FVector4f(0.f, 0.f, W, H);
		const float CW = FMath::Min(W, H * A), CH = CW / A;
		return FVector4f(0.5f * (W - CW), 0.5f * (H - CH), CW, CH);
	}
}
