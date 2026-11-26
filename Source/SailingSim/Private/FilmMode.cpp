#include "FilmMode.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "HAL/IConsoleManager.h"
#include "RenderUtils.h"
#include "ShowFlags.h"
#include "Dom/JsonValue.h"
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

FFilmFrameClock FFilmFrameClock::Make(double FrameSeconds, double WarmupSeconds, double RecordSeconds, double IntervalSeconds)
{
	FFilmFrameClock C;
	C.FrameSeconds = FrameSeconds > 0.0 ? FrameSeconds : 1.0 / 60.0;
	// (A whisker under, so 10 s at 1/60 is 600 frames however the division rounds.)
	C.WarmupFrames = FMath::Max(0, FMath::CeilToInt(WarmupSeconds / C.FrameSeconds - 1e-6));
	C.Stride = FMath::Max(1, FMath::RoundToInt(IntervalSeconds / C.FrameSeconds));
	// The frames the run asked for: 8 s at an interval of 0.0166667 is 480, never 481 (the timed loop's extra frame came
	// from adding the rounded interval up against the end: Inputs/reel-test/README.md).
	C.Count = IntervalSeconds > 0.0 ? FMath::Max(0, FMath::RoundToInt(RecordSeconds / IntervalSeconds)) : 0;
	return C;
}

int32 FFilmFrameClock::CaptureIndexAt(int64 Frame) const
{
	const int64 D = Frame - WarmupFrames;
	if (D < 0 || D % Stride != 0) return -1;
	const int64 I = D / Stride;
	return I < Count ? int32(I) : -1;
}

double FilmEase(EFilmEase Ease, double U)
{
	U = FMath::Clamp(U, 0.0, 1.0);
	switch (Ease)
	{
	case EFilmEase::In: return U * U;
	case EFilmEase::Out: return 1.0 - (1.0 - U) * (1.0 - U);
	case EFilmEase::InOut: return U * U * (3.0 - 2.0 * U);
	default: return U;
	}
}

namespace FilmModeLocal
{
	bool ReadVector(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, FVector& Out, FString& OutError)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (!O->TryGetArrayField(Field, A)) return false;
		if (A->Num() != 3)
		{
			OutError = FString::Printf(TEXT("\"%s\" needs three numbers"), Field);
			return false;
		}
		Out = FVector((*A)[0]->AsNumber(), (*A)[1]->AsNumber(), (*A)[2]->AsNumber());
		return true;
	}

	bool ParseEase(const FString& S, EFilmEase& Out)
	{
		if (S.Equals(TEXT("linear"), ESearchCase::IgnoreCase)) Out = EFilmEase::Linear;
		else if (S.Equals(TEXT("in"), ESearchCase::IgnoreCase)) Out = EFilmEase::In;
		else if (S.Equals(TEXT("out"), ESearchCase::IgnoreCase)) Out = EFilmEase::Out;
		else if (S.Equals(TEXT("inout"), ESearchCase::IgnoreCase) || S.Equals(TEXT("in-out"), ESearchCase::IgnoreCase)) Out = EFilmEase::InOut;
		else return false;
		return true;
	}

	FVector CatmullRom(const FVector& P0, const FVector& P1, const FVector& P2, const FVector& P3, double U)
	{
		const double U2 = U * U, U3 = U2 * U;
		return 0.5 * ((2.0 * P1) + (P2 - P0) * U + (2.0 * P0 - 5.0 * P1 + 4.0 * P2 - P3) * U2 + (3.0 * P1 - P0 - 3.0 * P2 + P3) * U3);
	}
}

bool FFilmShot::Parse(const FString& Json, FString& OutError)
{
	Keys.Reset();
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) || !Root.IsValid())
	{
		OutError = TEXT("not JSON");
		return false;
	}
	FString S;
	Frame = EFilmFrame::Boat;
	if (Root->TryGetStringField(TEXT("frame"), S))
	{
		if (S.Equals(TEXT("boat"), ESearchCase::IgnoreCase)) Frame = EFilmFrame::Boat;
		else if (S.Equals(TEXT("world"), ESearchCase::IgnoreCase)) Frame = EFilmFrame::World;
		else if (S.Equals(TEXT("mount"), ESearchCase::IgnoreCase)) Frame = EFilmFrame::Mount;
		else { OutError = FString::Printf(TEXT("unknown frame \"%s\" (boat, world or mount)"), *S); return false; }
	}
	bSmooth = Root->TryGetStringField(TEXT("path"), S) && S.Equals(TEXT("smooth"), ESearchCase::IgnoreCase);
	double ShotFov = 40.0;
	Root->TryGetNumberField(TEXT("fov"), ShotFov);

	const TArray<TSharedPtr<FJsonValue>>* KeyValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("keys"), KeyValues) || KeyValues->Num() == 0)
	{
		OutError = TEXT("no \"keys\"");
		return false;
	}
	for (int32 I = 0; I < KeyValues->Num(); ++I)
	{
		const TSharedPtr<FJsonObject>* KO = nullptr;
		if (!(*KeyValues)[I]->TryGetObject(KO))
		{
			OutError = FString::Printf(TEXT("key %d is not an object"), I);
			return false;
		}
		const TSharedPtr<FJsonObject>& O = *KO;
		FFilmKey K;
		K.HFovDeg = ShotFov;
		if (!O->TryGetNumberField(TEXT("t"), K.T))
		{
			OutError = FString::Printf(TEXT("key %d has no \"t\""), I);
			return false;
		}
		if (I > 0 && K.T <= Keys.Last().T)
		{
			OutError = FString::Printf(TEXT("key %d: times must increase (%.3f after %.3f)"), I, K.T, Keys.Last().T);
			return false;
		}
		FVector V;
		FString Err;
		if (FilmModeLocal::ReadVector(O, TEXT("orbit"), V, Err))
		{
			if (Frame == EFilmFrame::Mount)
			{
				OutError = FString::Printf(TEXT("key %d: a mount is fixed on the hull, it has no orbit"), I);
				return false;
			}
			K.bOrbit = true;
			K.OrbitBearingDeg = V.X;
			K.OrbitDistanceM = V.Y;
			K.OrbitHeightM = V.Z;
		}
		else if (!Err.IsEmpty()) { OutError = FString::Printf(TEXT("key %d: %s"), I, *Err); return false; }
		else if (FilmModeLocal::ReadVector(O, TEXT("pos"), V, Err)) K.Pos = V;
		else if (!Err.IsEmpty()) { OutError = FString::Printf(TEXT("key %d: %s"), I, *Err); return false; }
		else { OutError = FString::Printf(TEXT("key %d needs \"pos\" or \"orbit\""), I); return false; }

		// The look: "boat" (the default), or [pitch, yaw, roll]. "aim_offset": [pitch, yaw, roll] frames the boat off centre.
		K.bLookAtBoat = true;
		if (O->TryGetStringField(TEXT("look"), S))
		{
			if (!S.Equals(TEXT("boat"), ESearchCase::IgnoreCase)) { OutError = FString::Printf(TEXT("key %d: look is \"boat\" or [pitch, yaw, roll]"), I); return false; }
		}
		else if (FilmModeLocal::ReadVector(O, TEXT("look"), V, Err))
		{
			K.bLookAtBoat = false;
			K.Look = FRotator(V.X, V.Y, V.Z);
		}
		else if (!Err.IsEmpty()) { OutError = FString::Printf(TEXT("key %d: %s"), I, *Err); return false; }
		if (K.bLookAtBoat)
		{
			if (FilmModeLocal::ReadVector(O, TEXT("aim_offset"), V, Err)) K.Look = FRotator(V.X, V.Y, V.Z);
			else if (!Err.IsEmpty()) { OutError = FString::Printf(TEXT("key %d: %s"), I, *Err); return false; }
			O->TryGetNumberField(TEXT("aim_up"), K.AimUpM);
		}
		O->TryGetNumberField(TEXT("fov"), K.HFovDeg);
		if (K.HFovDeg < 1.0 || K.HFovDeg > 170.0) { OutError = FString::Printf(TEXT("key %d: fov %.1f out of 1..170"), I, K.HFovDeg); return false; }
		if (O->TryGetStringField(TEXT("ease"), S) && !FilmModeLocal::ParseEase(S, K.Ease))
		{
			OutError = FString::Printf(TEXT("key %d: unknown ease \"%s\" (linear, in, out, inout)"), I, *S);
			return false;
		}
		Keys.Add(K);
	}
	return true;
}

bool FFilmShot::Load(const FString& Path, FString& OutError)
{
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		OutError = FString::Printf(TEXT("can't read %s"), *Path);
		return false;
	}
	return Parse(Json, OutError);
}

FVector FFilmShot::ToCm(const FVector& P, const FFilmBoatPose& Boat) const
{
	switch (Frame)
	{
	case EFilmFrame::World:
		return Boat.WorldAnchor + P * 100.0;
	case EFilmFrame::Mount:
		return P * 100.0;
	default:
	{
		const double H = FMath::DegreesToRadians(Boat.HeadingDeg);
		const FVector Fwd(FMath::Cos(H), FMath::Sin(H), 0.0), Right(-FMath::Sin(H), FMath::Cos(H), 0.0);
		return Boat.Origin + (Fwd * P.X + Right * P.Y + FVector(0.0, 0.0, P.Z)) * 100.0;
	}
	}
}

FVector FFilmShot::KeyLocation(const FFilmKey& Key, const FFilmBoatPose& Boat) const
{
	if (!Key.bOrbit) return ToCm(Key.Pos, Boat);
	// Round the boat where she is now: off her bow (Boat) or on a compass bearing from her (World).
	const double B = FMath::DegreesToRadians(Key.OrbitBearingDeg + (Frame == EFilmFrame::Boat ? Boat.HeadingDeg : 0.0));
	return Boat.Origin + FVector(FMath::Cos(B) * Key.OrbitDistanceM, FMath::Sin(B) * Key.OrbitDistanceM, Key.OrbitHeightM) * 100.0;
}

FQuat FFilmShot::KeyRotation(const FFilmKey& Key, const FVector& Location, const FFilmBoatPose& Boat) const
{
	if (Key.bLookAtBoat)
	{
		const double AimUp = Key.AimUpM >= 0.0 ? Key.AimUpM : 0.33 * Boat.MastheadM;
		const FVector Target = Frame == EFilmFrame::Mount ? FVector(0.0, 0.0, AimUp * 100.0) : Boat.Origin + FVector(0.0, 0.0, AimUp * 100.0);
		FRotator R = (Target - Location).Rotation();
		R.Pitch += Key.Look.Pitch;
		R.Yaw += Key.Look.Yaw;
		R.Roll = Key.Look.Roll;
		return R.Quaternion();
	}
	FRotator R = Key.Look;
	if (Frame == EFilmFrame::Boat) R.Yaw += Boat.HeadingDeg;   // level, turning with her
	return R.Quaternion();
}

FFilmCameraPose FFilmShot::Evaluate(double T, const FFilmBoatPose& Boat) const
{
	FFilmCameraPose Pose;
	Pose.bRelativeToHull = Frame == EFilmFrame::Mount;
	if (Keys.Num() == 0) return Pose;
	// Before the first key and after the last the camera holds.
	int32 I = 0;
	double U = 0.0;
	if (T >= Keys.Last().T) I = Keys.Num() - 1;
	else if (T > Keys[0].T)
	{
		while (I + 1 < Keys.Num() && Keys[I + 1].T <= T) ++I;
		U = FilmEase(Keys[I].Ease, (T - Keys[I].T) / (Keys[I + 1].T - Keys[I].T));
	}
	const FFilmKey& A = Keys[I];
	if (I == Keys.Num() - 1 || U <= 0.0)
	{
		Pose.Location = KeyLocation(A, Boat);
		Pose.Rotation = KeyRotation(A, Pose.Location, Boat).Rotator();
		Pose.HFovDeg = A.HFovDeg;
		return Pose;
	}
	const FFilmKey& B = Keys[I + 1];
	if (bSmooth)
	{
		const FFilmKey& P0 = Keys[FMath::Max(I - 1, 0)];
		const FFilmKey& P3 = Keys[FMath::Min(I + 2, Keys.Num() - 1)];
		Pose.Location = FilmModeLocal::CatmullRom(KeyLocation(P0, Boat), KeyLocation(A, Boat), KeyLocation(B, Boat), KeyLocation(P3, Boat), U);
	}
	else if (A.bOrbit && B.bOrbit)
	{
		// Round the boat: bearing the short way, distance and height straight.
		FFilmKey Mid = A;
		Mid.OrbitBearingDeg = A.OrbitBearingDeg + U * FMath::FindDeltaAngleDegrees(A.OrbitBearingDeg, B.OrbitBearingDeg);
		Mid.OrbitDistanceM = FMath::Lerp(A.OrbitDistanceM, B.OrbitDistanceM, U);
		Mid.OrbitHeightM = FMath::Lerp(A.OrbitHeightM, B.OrbitHeightM, U);
		Pose.Location = KeyLocation(Mid, Boat);
	}
	else
	{
		Pose.Location = FMath::Lerp(KeyLocation(A, Boat), KeyLocation(B, Boat), U);
	}
	Pose.Rotation = FQuat::Slerp(KeyRotation(A, Pose.Location, Boat), KeyRotation(B, Pose.Location, Boat), U).GetNormalized().Rotator();
	Pose.HFovDeg = FMath::Lerp(A.HFovDeg, B.HFovDeg, U);
	return Pose;
}

FFilmTripod FFilmTripod::Parse(const FString& Arg)
{
	FFilmTripod T;
	TArray<FString> P;
	Arg.ParseIntoArray(P, TEXT(","));
	if (P.Num() > 0 && !P[0].IsEmpty()) T.DistanceM = FMath::Max(1.0, FCString::Atod(*P[0]));
	if (P.Num() > 1 && !P[1].IsEmpty()) T.HeightM = FCString::Atod(*P[1]);
	if (P.Num() > 2 && !P[2].IsEmpty()) T.HFovDeg = FMath::Clamp(FCString::Atod(*P[2]), 1.0, 170.0);
	if (P.Num() > 3 && !P[3].IsEmpty()) T.AimFraction = FMath::Clamp(FCString::Atod(*P[3]), 0.0, 1.5);
	return T;
}

bool FilmUsesFrameClock()
{
	return FApp::IsBenchmarking() || FApp::UseFixedTimeStep();
}

float CaptureMotionBlurAmount(const TCHAR* CommandLine)
{
	float Amount = 0.f;
	if (FParse::Value(CommandLine, TEXT("SailingMotionBlur="), Amount)) return FMath::Clamp(Amount, 0.f, 1.f);
	// A film's 180 degree shutter (the game's own look uses 90: ASailingEnvironment::ApplyCameraLook's 0.25).
	return FParse::Param(CommandLine, TEXT("SailingFilm")) ? 0.5f : 0.f;
}

TArray<FQualityCVar> FilmQualityCVars()
{
	TArray<FQualityCVar> V;
	// Clouds by mode 0 (a quarter-resolution trace rebuilt over frames) with more samples. Mode 3 (full resolution, the
	// engine's cinematic mode) left dark stipple in the shaded cloud bases on the film tripod and mode 1 was worse; mode 0
	// softened most of it at the same 1.19 s a frame (Inputs/bench/cloud-blocks/followup/, the PC on #818).
	V.Add({ TEXT("r.VolumetricRenderTarget.Mode"), 0.f });
	V.Add({ TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), 512.f });
	// The water's reflections at full resolution (the tiers trace them at half and denoise): the combed, dithered stripes
	// in the tripod run's reflection under the boat. Lumen's own reflections at full resolution too.
	V.Add({ TEXT("r.Water.SingleLayer.Reflection.DownsampleFactor"), 1.f });
	V.Add({ TEXT("r.Lumen.Reflections.DownsampleFactor"), 1.f });
	// TSR keeps a history at twice the output resolution: steadier thin lines (rigging) and less shimmer frame to frame.
	V.Add({ TEXT("r.TSR.History.ScreenPercentage"), 200.f });
	return V;
}

bool CaptureShowsHud(const TCHAR* CommandLine)
{
	return CommandLine && FParse::Param(CommandLine, TEXT("SailingCaptureHud"));
}

bool CaptureShowsHud()
{
	static SailingArgs::FCachedFlag HudArg(TEXT("SailingCaptureHud"));
	return HudArg.Get();
}

bool CaptureHidesHud(bool bCaptureMode, bool bCaptureHud)
{
	return bCaptureMode && !bCaptureHud;
}

int32 StartingHudMode(bool bMeasuring, bool bCaptureHud, int32 ChosenMode)
{
	return bMeasuring && !bCaptureHud ? 0 : FMath::Clamp(ChosenMode, 0, 2);
}

bool IsFilmMode()
{
	static SailingArgs::FCachedFlag FilmArg(TEXT("SailingFilm"));
	return FilmArg.Get();
}

bool FixedExposureArg(float& OutEV100)
{
	static uint32 Gen = MAX_uint32;
	static bool bHas = false;
	static float Value = 0.f;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		bHas = FParse::Value(SailingArgs::Dev(), TEXT("SailingEV="), Value);
	}
	if (bHas) OutEV100 = Value;
	return bHas;
}

EFilmViewMode ParseFilmViewMode(const FString& Name)
{
	const FString N = Name.TrimStartAndEnd().TrimQuotes();
	if (N.Equals(TEXT("wireframe"), ESearchCase::IgnoreCase)) return EFilmViewMode::Wireframe;
	if (N.Equals(TEXT("lightingonly"), ESearchCase::IgnoreCase) || N.Equals(TEXT("lighting"), ESearchCase::IgnoreCase)) return EFilmViewMode::LightingOnly;
	if (N.Equals(TEXT("unlit"), ESearchCase::IgnoreCase)) return EFilmViewMode::Unlit;
	return EFilmViewMode::Lit;
}

EFilmViewMode FilmViewMode()
{
	static uint32 Gen = MAX_uint32;
	static EFilmViewMode Mode = EFilmViewMode::Lit;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		FString Name;
		Mode = FParse::Value(SailingArgs::Dev(), TEXT("SailingViewMode="), Name) ? ParseFilmViewMode(Name) : EFilmViewMode::Lit;
		if (!Name.IsEmpty() && Mode == EFilmViewMode::Lit && !Name.Equals(TEXT("lit"), ESearchCase::IgnoreCase))
		{
			SAIL_LOG(Warning, TEXT("Film: -SailingViewMode=%s is not wireframe, lightingonly, unlit or lit: lit"), *Name);
		}
	}
	return Mode;
}

bool ApplyFilmViewMode(UGameViewportClient* Viewport, UWorld* World)
{
	const EFilmViewMode Mode = FilmViewMode();
	if (Mode == EFilmViewMode::Lit || !Viewport) return false;
	const TCHAR* Name = Mode == EFilmViewMode::Wireframe ? TEXT("wireframe") : Mode == EFilmViewMode::LightingOnly ? TEXT("lighting only") : TEXT("unlit");
	// The engine's own test: debug view modes need their shaders in the cook (r.ForceDebugViewModes 1 in the config when
	// cooking). Forcing them on at run time in a package cooked without them crashed on the first frame (a skeletal mesh's
	// dynamic elements) and the launch-arg route failed to find FDebugViewModePS (PC on #828 at 89ec83ed).
	if (AllowDebugViewmodes())
	{
		const EViewModeIndex Index = Mode == EFilmViewMode::Wireframe ? VMI_Wireframe
			: Mode == EFilmViewMode::LightingOnly ? VMI_LightingOnly : VMI_Unlit;
		Viewport->ViewModeIndex = Index;
		ApplyViewMode(Index, true, Viewport->EngineShowFlags);
		SAIL_LOG(Display, TEXT("Film view mode: %s (the engine's view mode)"), Name);
		return true;
	}
	// Without them, lighting only still works through its show flag (the normal shaders: the hull, deck and water go
	// grey; the sails' marks and colour are taken off by the pawn). Wireframe and unlit don't: the procedural and skinned
	// meshes would stay lit.
	if (Mode == EFilmViewMode::LightingOnly && World && GEngine)
	{
		GEngine->Exec(World, TEXT("ShowFlag.LightingOnlyOverride 1"));
		SAIL_LOG(Display, TEXT("Film view mode: lighting only (ShowFlag.LightingOnlyOverride: this package has no debug view modes)"));
		return true;
	}
	SAIL_LOG(Warning, TEXT("Film view mode: %s needs debug view modes: a Development package cooked with them "
		"(package-win.ps1's Development cook arg -DPCVars=r.ForceDebugViewModes=1, #829) and the same on the launch line "
		"(-DPCVars=r.ForceDebugViewModes=1); this run has none, so the frames stay lit"), Name);
	return false;
}
