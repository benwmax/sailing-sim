#include "ReferenceCapture.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "SailingSim.h"

using namespace Sailing;

namespace
{
	// The method's camera table (docs/phase-8/reference-kit/method.md, step 2).
	const FCapturePresetInfo CapturePresets[] =
	{
		{ TEXT("None"), 90.f, false, false, 0.f },
		{ TEXT("HelmEye"), 70.f, true, false, 0.f },
		{ TEXT("ActionCam"), 118.f, true, true, 0.f },
		{ TEXT("Chase"), 50.f, false, false, NAN },
		{ TEXT("Drone"), 80.f, false, false, NAN },
		{ TEXT("ShoreTele"), 15.f, false, false, NAN },
	};
	static_assert(UE_ARRAY_COUNT(CapturePresets) == int32(ECapturePreset::Count), "one entry per preset");

	double CapDeg(double Rad) { return FMath::RadiansToDegrees(Rad); }
	double CapKn(double Ms) { return Ms / kKnot; }
	double CapCompass(double Rad) { double D = FMath::Fmod(CapDeg(Rad), 360.0); return D < 0.0 ? D + 360.0 : D; }
}

const FCapturePresetInfo& CapturePresetInfo(ECapturePreset Preset)
{
	return CapturePresets[FMath::Clamp(int32(Preset), 0, int32(ECapturePreset::Count) - 1)];
}

ECapturePreset ParseCapturePreset(const FString& Name)
{
	for (int32 I = 1; I < int32(ECapturePreset::Count); ++I)
	{
		if (Name.Equals(CapturePresets[I].Name, ESearchCase::IgnoreCase)) return ECapturePreset(I);
	}
	// The method's own names work too.
	if (Name.Contains(TEXT("action"), ESearchCase::IgnoreCase) || Name.Contains(TEXT("stern"), ESearchCase::IgnoreCase)) return ECapturePreset::ActionCam;
	if (Name.Contains(TEXT("helm"), ESearchCase::IgnoreCase)) return ECapturePreset::HelmEye;
	if (Name.Contains(TEXT("chase"), ESearchCase::IgnoreCase)) return ECapturePreset::Chase;
	if (Name.Contains(TEXT("shore"), ESearchCase::IgnoreCase) || Name.Contains(TEXT("tele"), ESearchCase::IgnoreCase)) return ECapturePreset::ShoreTele;
	if (Name.Contains(TEXT("drone"), ESearchCase::IgnoreCase)) return ECapturePreset::Drone;
	return ECapturePreset::None;
}

void OnboardCameraMount(ECapturePreset Preset, const FBoatConfig& Config, float Side, FVector& OutLocation, FRotator& OutRotation)
{
	const FHullShape& Hull = Config.Hulls.empty() ? FHullShape() : Config.Hulls[0];
	if (Preset == ECapturePreset::ActionCam)
	{
		// A transom or pulpit mount: higher on a keelboat's pulpit, just above the deck on a dinghy.
		const double X = Hull.SternX + 0.15;
		const double MountHeight = FMath::Clamp(0.12 * Config.LengthOverall, 0.25, 0.8);
		const double Z = (Config.bMultihull ? Hull.SheerZ : Hull.SheerHeight(X)) + MountHeight;
		OutLocation = FVector(X, 0.0, Z) * CmPerMeter;
		OutRotation = FRotator(-6.f, 0.f, 0.f);
		return;
	}
	// Helm eye: the helmsman's head, sitting on the windward side deck at the tiller extension, as in the onboard
	// clips (J22-M-007): 0.85 m above the deck at the rail (0.75 m above the waterline at least, on a dinghy), at the
	// aftmost crew place. The aftmost crew place is the helmsman's (the crew sit 0.55 m apart about their CG).
	const double X = FMath::Max(Hull.SternX + 0.6, Config.CrewCG.X - 0.55 * 0.5 * (Config.CrewCount - 1) + 0.1);
	const double Sheer = Config.bMultihull ? Hull.SheerZ : Hull.SheerHeight(X);
	const double Y = Config.bMultihull ? Hull.CenterY : FMath::Max(Hull.DeckHalfBeam(X) - 0.1, 0.0) * FMath::Sign(Side);
	OutLocation = FVector(X, Y, FMath::Max(Sheer + 0.85, 0.75)) * CmPerMeter;
	// Forward and a little to leeward, toward the jib luff and its telltales (what a helmsman watches).
	OutRotation = FRotator(-7.f, Config.bMultihull ? 0.f : -12.f * FMath::Sign(Side), 0.f);
}

void WorldCameraPose(ECapturePreset Preset, const FVector& BoatOrigin, float HeadingDeg, float BearingDeg,
	float MastheadMeters, float WaterZ, FVector& OutLocation, FRotator& OutRotation)
{
	// A chase boat stands off far enough to frame the whole rig (15 m for a J/22, more for the bigger boats).
	float Range = FMath::Max(15.f, 1.9f * MastheadMeters), Height = 2.f, AimFraction = 0.42f;
	switch (Preset)
	{
	case ECapturePreset::Drone: Range = 30.f; Height = 30.f; AimFraction = 0.2f; break;
	case ECapturePreset::ShoreTele: Range = 200.f; Height = 3.f; AimFraction = 0.33f; break;
	default: break;
	}
	const float Bearing = FMath::DegreesToRadians(HeadingDeg + BearingDeg);
	OutLocation = FVector(BoatOrigin.X + Range * CmPerMeter * FMath::Cos(Bearing), BoatOrigin.Y + Range * CmPerMeter * FMath::Sin(Bearing), WaterZ + Height * CmPerMeter);
	const FVector Aim(BoatOrigin.X, BoatOrigin.Y, WaterZ + AimFraction * MastheadMeters * CmPerMeter);
	OutRotation = (Aim - OutLocation).Rotation();
	OutRotation.Roll = 0.f;
}

FCaptureTelemetryRow FCaptureTelemetryRow::FromBoat(double Time, const FBoatModel& Boat, const FBoatControls& Controls, double WaveHeight)
{
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FBoatState& S = Boat.GetState();
	FCaptureTelemetryRow R;
	R.Time = Time;
	R.SpeedThroughWaterKn = CapKn(T.SpeedThroughWater);
	R.SpeedOverGroundKn = CapKn(T.BoatSpeed);
	R.HeadingDeg = CapCompass(T.Heading);
	R.CourseOverGroundDeg = CapCompass(T.CourseOverGround);
	R.HeelDeg = CapDeg(T.Heel);
	R.PitchDeg = CapDeg(T.Pitch);
	R.RollRateDegS = CapDeg(S.AngularVelocity.X);
	R.RudderDeg = CapDeg(S.RudderAngle);
	R.Tiller = Controls.Tiller;
	R.MainSheet = Controls.MainSheet;
	R.JibSheet = Controls.JibSheet;
	R.Hike = Controls.Hike;
	R.TrueWindKn = CapKn(T.TrueWindSpeed);
	R.TrueWindAngleDeg = CapDeg(T.TrueWindAngle);
	R.TrueWindFromDeg = CapCompass(T.Heading + T.TrueWindAngle);
	R.ApparentWindKn = CapKn(T.ApparentWindSpeed);
	R.ApparentWindAngleDeg = CapDeg(T.ApparentWindAngle);
	R.WaveHeightM = WaveHeight;
	R.HelmForceN = T.HelmForce;
	R.bCapsized = T.bCapsized;
	return R;
}

FString FCaptureTelemetry::Header()
{
	return TEXT("time_s,stw_kn,sog_kn,heading_deg,cog_deg,heel_deg,pitch_deg,roll_rate_dps,rudder_deg,tiller,main_sheet,jib_sheet,hike,")
		TEXT("tws_kn,twd_deg,twa_deg,aws_kn,awa_deg,wave_m,helm_force_n,capsized");
}

FString FCaptureTelemetry::Format(const FCaptureTelemetryRow& R)
{
	return FString::Printf(TEXT("%.3f,%.2f,%.2f,%.1f,%.1f,%.2f,%.2f,%.2f,%.2f,%.3f,%.3f,%.3f,%.3f,%.2f,%.1f,%.1f,%.2f,%.1f,%.3f,%.1f,%d"),
		R.Time, R.SpeedThroughWaterKn, R.SpeedOverGroundKn, R.HeadingDeg, R.CourseOverGroundDeg, R.HeelDeg, R.PitchDeg,
		R.RollRateDegS, R.RudderDeg, R.Tiller, R.MainSheet, R.JibSheet, R.Hike, R.TrueWindKn, R.TrueWindFromDeg,
		R.TrueWindAngleDeg, R.ApparentWindKn, R.ApparentWindAngleDeg, R.WaveHeightM, R.HelmForceN, R.bCapsized ? 1 : 0);
}

bool FCaptureTelemetry::Open(const FString& Path)
{
	Close();
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
	File.Reset(IFileManager::Get().CreateFileWriter(*Path));
	if (!File) return false;
	const FTCHARToUTF8 Line(*(Header() + TEXT("\n")));
	File->Serialize(const_cast<ANSICHAR*>(Line.Get()), Line.Length());
	Count = 0;
	return true;
}

void FCaptureTelemetry::Add(const FCaptureTelemetryRow& Row)
{
	if (!File) return;
	const FTCHARToUTF8 Line(*(Format(Row) + TEXT("\n")));
	File->Serialize(const_cast<ANSICHAR*>(Line.Get()), Line.Length());
	if (++Count % 120 == 0) File->Flush();
}

void FCaptureTelemetry::Close()
{
	if (File)
	{
		File->Close();
		File.Reset();
	}
}
