#include "FreeCamera.h"
#include "SailingFrame.h"
#include "SailingGameMode.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Engine/World.h"

namespace FreeCameraMath
{
	double SpeedStep(int32 Index)
	{
		static const double Steps[NumSpeeds] = { 0.5, 2.0, 8.0, 30.0, 120.0 };
		return Steps[FMath::Clamp(Index, 0, NumSpeeds - 1)];
	}

	double Speed(int32 Index, bool bBoost, bool bSlow)
	{
		return SpeedStep(Index) * (bBoost ? 5.0 : 1.0) * (bSlow ? 0.2 : 1.0);
	}

	double EaseAlpha(double Dt, double EaseSeconds)
	{
		// A first-order lag whose time constant is a third of the ease: 95% of the way there after EaseSeconds.
		return EaseSeconds > 0.0 ? 1.0 - FMath::Exp(-3.0 * FMath::Max(Dt, 0.0) / EaseSeconds) : 1.0;
	}

	double LeashScale(double DistM, const FFreeCameraLimits& L)
	{
		return FMath::Clamp((L.LeashM - DistM) / FMath::Max(L.LeashSoftM, 1e-3), 0.0, 1.0);
	}

	FVector2D LeashVelocity(const FVector2D& OffsetM, const FVector2D& VelocityMps, const FFreeCameraLimits& L)
	{
		const double Dist = OffsetM.Size();
		if (Dist < 1e-6) return VelocityMps;
		const FVector2D Out = OffsetM / Dist;
		const double Along = FVector2D::DotProduct(VelocityMps, Out);
		if (Along <= 0.0) return VelocityMps; // back toward the anchor, or along the circle: free
		return VelocityMps - Out * Along * (1.0 - LeashScale(Dist, L));
	}

	FVector2D ClampToLeash(const FVector2D& OffsetM, const FFreeCameraLimits& L)
	{
		const double Dist = OffsetM.Size();
		return Dist > L.LeashM ? OffsetM * (L.LeashM / Dist) : OffsetM;
	}

	double FloorM(double WaveM, double GroundM, const FFreeCameraLimits& L)
	{
		return FMath::Max(WaveM + L.WaterClearM, GroundM + L.TerrainClearM);
	}

	double ClampHeightM(double ZM, double WaveM, double GroundM, const FFreeCameraLimits& L)
	{
		return FMath::Max(FMath::Min(ZM, L.CeilingM), FloorM(WaveM, GroundM, L));
	}
}

AFreeCamera::AFreeCamera()
{
	PrimaryActorTick.bCanEverTick = false;
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	RootComponent = Camera;
	SetReplicates(false);
}

void AFreeCamera::SetAnchor(AActor* InAnchor, const FVector& InPivotOffsetCm)
{
	Anchor = InAnchor;
	PivotOffsetCm = InPivotOffsetCm;
}

void AFreeCamera::SnapTo(const FVector& LocationCm, const FRotator& Rotation)
{
	SetActorLocationAndRotation(LocationCm, Rotation);
	Yaw = float(Rotation.Yaw);
	Pitch = float(FMath::Clamp(Rotation.Pitch, -89.0, 89.0));
	Roll = 0.f;
	VelocityMps = FVector::ZeroVector;
	if (Mode == EFreeCameraMode::Orbit) SetMode(EFreeCameraMode::Orbit);
}

void AFreeCamera::SetMode(EFreeCameraMode InMode)
{
	Mode = InMode;
	VelocityMps = FVector::ZeroVector;
	if (Mode == EFreeCameraMode::Orbit)
	{
		// Orbit from where the camera is: its distance and bearing from the pivot (it then turns to face it).
		const FVector Off = GetActorLocation() - Pivot();
		OrbitDistanceCm = FMath::Clamp(float(Off.Size()), 150.f, 30000.f);
		const FRotator Toward = (-Off).Rotation();
		Yaw = float(Toward.Yaw);
		Pitch = float(FMath::Clamp(Toward.Pitch, -89.0, 60.0));
	}
	else
	{
		const FRotator R = GetActorRotation();
		Yaw = float(R.Yaw);
		Pitch = float(FMath::Clamp(R.Pitch, -89.0, 89.0));
	}
}

void AFreeCamera::AddLook(const FVector2D& DeltaDeg)
{
	Yaw = FMath::UnwindDegrees(Yaw + float(DeltaDeg.X));
	Pitch = FMath::Clamp(Pitch + float(DeltaDeg.Y), -89.f, Mode == EFreeCameraMode::Orbit ? 60.f : 89.f);
}

void AFreeCamera::StepSpeed(int32 Steps)
{
	if (Mode == EFreeCameraMode::Orbit) OrbitDistanceCm = FMath::Clamp(OrbitDistanceCm * FMath::Pow(0.85f, float(Steps)), 150.f, 30000.f);
	else SpeedIndex = FMath::Clamp(SpeedIndex + Steps, 0, FreeCameraMath::NumSpeeds - 1);
}

FVector AFreeCamera::Pivot() const
{
	const AActor* A = Anchor.Get();
	return A ? A->GetActorLocation() + PivotOffsetCm : GetActorLocation();
}

double AFreeCamera::GetLeashDistanceM() const
{
	const AActor* A = Anchor.Get();
	return A ? FVector::Dist2D(GetActorLocation(), A->GetActorLocation()) / 100.0 : 0.0;
}

double AFreeCamera::WaveHeightAt(const FVector& WorldCm) const
{
	const UWorld* World = GetWorld();
	const ASailingGameMode* GM = World ? World->GetAuthGameMode<ASailingGameMode>() : nullptr;
	if (!GM) return 0.0;
	const FVector2D At = SailingFrame::ToMap(World, WorldCm);
	return GM->GetWaves().Height(At.X, At.Y, GM->GetSimTime());
}

double AFreeCamera::GroundHeightAt(const FVector& WorldCm) const
{
	const UWorld* World = GetWorld();
	const ASailingGameMode* GM = World ? World->GetAuthGameMode<ASailingGameMode>() : nullptr;
	if (!GM || !GM->GetLake().IsLoaded()) return -1e6;
	const FVector2D At = SailingFrame::ToMap(World, WorldCm);
	return GM->GetLake().Terrain.HeightAt(At.X, At.Y);
}

void AFreeCamera::PlaceAt(const FVector& LocationCm, const FRotator& Rotation)
{
	SnapTo(Constrain(GetActorLocation(), LocationCm, false, false), Rotation);
}

FVector AFreeCamera::Constrain(const FVector& From, const FVector& To, bool bIgnoreAnchor, bool bSweep) const
{
	UWorld* World = GetWorld();
	FVector P = To;
	// The leash, about the anchor.
	if (const AActor* A = Anchor.Get())
	{
		const FVector C = A->GetActorLocation();
		const FVector2D Off = FreeCameraMath::ClampToLeash(FVector2D(P.X - C.X, P.Y - C.Y) / 100.0, Limits) * 100.0;
		P.X = C.X + Off.X;
		P.Y = C.Y + Off.Y;
	}
	// The sweep: stop at what it would enter. A start inside something (a mesh with no collision outside it) moves freely.
	if (World && bSweep && !From.Equals(P, 0.1))
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(FreeCameraSweep), false, this);
		if (bIgnoreAnchor && Anchor.IsValid()) Params.AddIgnoredActor(Anchor.Get());
		FHitResult Hit;
		if (World->SweepSingleByChannel(Hit, From, P, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(float(Limits.SweepRadiusM * 100.0)), Params)
			&& !Hit.bStartPenetrating)
		{
			P = Hit.Location;
		}
	}
	// The floor over the wave and the ground, the ceiling; in the physics frame (water at rest at 0).
	if (World)
	{
		const double ZM = SailingFrame::ToMapCm(World, P).Z / 100.0;
		const double Clamped = FreeCameraMath::ClampHeightM(ZM, WaveHeightAt(P), GroundHeightAt(P), Limits);
		P.Z += (Clamped - ZM) * 100.0;
	}
	return P;
}

void AFreeCamera::Update(float DeltaSeconds, const FFreeCameraInput& Input)
{
	const double Dt = FMath::Clamp(double(DeltaSeconds), 0.0, 0.1);
	const double Alpha = FreeCameraMath::EaseAlpha(Dt);
	Roll = FMath::Clamp(Roll + Input.Roll * 45.f * float(Dt), -45.f, 45.f);
	const FVector From = GetActorLocation();
	if (Mode == EFreeCameraMode::Fly)
	{
		// A drone: the stick moves it on its level heading, the triggers up and down.
		const double YawRad = FMath::DegreesToRadians(double(Yaw));
		const FVector Forward(FMath::Cos(YawRad), FMath::Sin(YawRad), 0.0), Right(-FMath::Sin(YawRad), FMath::Cos(YawRad), 0.0);
		FVector Want = Forward * Input.Move.Y + Right * Input.Move.X;
		if (Want.SizeSquared() > 1.0) Want.Normalize();
		Want += FVector::UpVector * FMath::Clamp(Input.Vertical, -1.f, 1.f);
		const FVector Target = Want * FreeCameraMath::Speed(SpeedIndex, Input.bBoost, Input.bSlow);
		VelocityMps += (Target - VelocityMps) * Alpha;
		if (const AActor* A = Anchor.Get())
		{
			const FVector2D Off = FVector2D(From.X - A->GetActorLocation().X, From.Y - A->GetActorLocation().Y) / 100.0;
			const FVector2D V = FreeCameraMath::LeashVelocity(Off, FVector2D(VelocityMps.X, VelocityMps.Y), Limits);
			VelocityMps.X = V.X;
			VelocityMps.Y = V.Y;
		}
		const FVector To = Constrain(From, From + VelocityMps * Dt * 100.0, false);
		SetActorLocationAndRotation(To, FRotator(Pitch, Yaw, Roll));
		return;
	}
	// Orbit: the camera eases to its place on the sphere about the pivot and faces it.
	const FVector P = Pivot();
	const FVector Want = P - FRotator(Pitch, Yaw, 0.f).Vector() * OrbitDistanceCm;
	const FVector To = Constrain(From, FMath::Lerp(From, Want, Alpha), true);
	FRotator Face = (P - To).Rotation();
	Face.Roll = Roll;
	const FQuat Q = FQuat::Slerp(GetActorQuat(), Face.Quaternion(), Alpha);
	SetActorLocationAndRotation(To, Q);
}
