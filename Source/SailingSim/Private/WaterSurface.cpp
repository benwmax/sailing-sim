#include "WaterSurface.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Async/ParallelFor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "Waves.h"
#include "Wind.h"

using namespace Sailing;

namespace
{
	constexpr int32 kGustRes = 64;
	constexpr float kGustSizeM = 1600.f;
	constexpr int32 kWakeRes = 128;
	constexpr float kWakeSizeM = 64.f;
	constexpr int32 kRingQuads = 128;     // quads across each ring
	constexpr float kFinestSpacingM = 0.5f;
	constexpr float kTrailSeconds = 15.f;

	UTexture2D* MakeMap(int32 Size)
	{
		UTexture2D* Tex = UTexture2D::CreateTransient(Size, Size, PF_B8G8R8A8);
		Tex->SRGB = false;
		Tex->Filter = TF_Bilinear;
		Tex->AddressX = TA_Clamp;
		Tex->AddressY = TA_Clamp;
		Tex->UpdateResource();
		return Tex;
	}

	void Upload(UTexture2D* Tex, const TArray<uint8>& Pixels, int32 Size)
	{
		uint8* Copy = new uint8[Pixels.Num()];
		FMemory::Memcpy(Copy, Pixels.GetData(), Pixels.Num());
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, Size, Size);
		Tex->UpdateTextureRegions(0, 1, Region, Size * 4, 4, Copy, [](uint8* Data, const FUpdateTextureRegion2D* R)
		{
			delete[] Data;
			delete R;
		});
	}
}

AWaterSurface::AWaterSurface()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics; // after the boat has stepped, so the wake is current

	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Water(TEXT("/Game/Materials/M_Water.M_Water"));

	FarPlane = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FarPlane"));
	FarPlane->SetupAttachment(RootComponent);
	FarPlane->SetStaticMesh(PlaneMesh.Object);
	FarPlane->SetMaterial(0, Water.Object);
	FarPlane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	FarPlane->SetCastShadow(false);
	// Just below the rings: hidden under them up close, the horizon beyond them.
	FarPlane->SetRelativeLocation(FVector(0.f, 0.f, -6.f));
	FarPlane->SetRelativeScale3D(FVector(FarPlaneSizeMeters, FarPlaneSizeMeters, 1.f));
}

const FWaveField* AWaterSurface::GetWaves() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM ? &GM->GetWaves() : nullptr;
}

const FWindField* AWaterSurface::GetWind() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM ? &GM->GetWind() : nullptr;
}

double AWaterSurface::GetSimTime() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM ? GM->GetSimTime() : GetWorld()->GetTimeSeconds();
}

void AWaterSurface::BeginPlay()
{
	Super::BeginPlay();
	FarPlane->SetRelativeScale3D(FVector(FarPlaneSizeMeters, FarPlaneSizeMeters, 1.f));
	WaterMaterial = FarPlane->CreateAndSetMaterialInstanceDynamic(0);
	GustMap = MakeMap(kGustRes);
	WakeMap = MakeMap(kWakeRes);
	GustPixels.SetNumZeroed(kGustRes * kGustRes * 4);
	WakePixels.SetNumZeroed(kWakeRes * kWakeRes * 4);
	if (WaterMaterial)
	{
		WaterMaterial->SetTextureParameterValue(TEXT("GustMap"), GustMap);
		WaterMaterial->SetTextureParameterValue(TEXT("WakeMap"), WakeMap);
	}
	BuildRings();
}

void AWaterSurface::SetRingCount(int32 Count)
{
	RingCount = FMath::Clamp(Count, 2, 7);
	if (HasActorBegunPlay())
	{
		BuildRings();
	}
}

void AWaterSurface::BuildRings()
{
	for (UProceduralMeshComponent* Ring : Rings)
	{
		if (Ring) Ring->DestroyComponent();
	}
	Rings.Reset();
	RingSpacing.Reset();

	for (int32 Level = 0; Level < RingCount; ++Level)
	{
		const float Spacing = kFinestSpacingM * float(1 << Level);
		const int32 N = kRingQuads;
		// Inner hole for every ring but the first: the next finer ring fills it (one coarse cell of overlap).
		const int32 Hole = Level == 0 ? 0 : N / 4 - 1;

		TArray<FVector> Verts;
		TArray<int32> Tris;
		TArray<FVector> Normals;
		Verts.Reserve((N + 1) * (N + 1));
		for (int32 Y = 0; Y <= N; ++Y)
		{
			for (int32 X = 0; X <= N; ++X)
			{
				Verts.Add(FVector((X - N / 2) * Spacing, (Y - N / 2) * Spacing, 0.f) * CmPerMeter);
				Normals.Add(FVector::UpVector);
			}
		}
		for (int32 Y = 0; Y < N; ++Y)
		{
			for (int32 X = 0; X < N; ++X)
			{
				const bool bInHole = Hole > 0 && X >= N / 2 - Hole && X < N / 2 + Hole && Y >= N / 2 - Hole && Y < N / 2 + Hole;
				if (bInHole) continue;
				const int32 V0 = Y * (N + 1) + X, V1 = V0 + 1, V2 = V0 + N + 1, V3 = V2 + 1;
				Tris.Append({ V0, V2, V1, V1, V2, V3 });
			}
		}

		UProceduralMeshComponent* Ring = NewObject<UProceduralMeshComponent>(this, *FString::Printf(TEXT("WaterRing%d"), Level));
		Ring->SetupAttachment(RootComponent);
		Ring->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Ring->SetCastShadow(false);
		Ring->bUseAsyncCooking = true;
		Ring->CreateMeshSection_LinearColor(0, Verts, Tris, Normals, {}, {}, {}, false);
		// Waves can lift the surface about a meter; keep the ring from being culled.
		Ring->SetBoundsScale(1.5f);
		Ring->RegisterComponent();
		Ring->SetMaterial(0, WaterMaterial);
		Rings.Add(Ring);
		RingSpacing.Add(Spacing);
	}
}

void AWaterSurface::SetBoatForWake(const FVector2D& PositionM, float HeadingRad, float SpeedMs, float HeelRad)
{
	BoatPos = PositionM;
	BoatHeading = HeadingRad;
	BoatSpeed = SpeedMs;
	BoatHeel = HeelRad;
}

void AWaterSurface::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Rings follow the camera, each snapped to twice its spacing so vertices don't swim.
	FVector CamPos = GetActorLocation();
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		CamPos = Cam->GetCameraLocation();
	}
	for (int32 I = 0; I < Rings.Num(); ++I)
	{
		const float Snap = 2.f * RingSpacing[I] * CmPerMeter;
		Rings[I]->SetWorldLocation(FVector(FMath::GridSnap(CamPos.X, Snap), FMath::GridSnap(CamPos.Y, Snap), GetActorLocation().Z));
	}
	FarPlane->SetWorldLocation(FVector(CamPos.X, CamPos.Y, GetActorLocation().Z - 6.f));

	GustTimer -= DeltaSeconds;
	if (GustTimer <= 0.f)
	{
		UpdateGustMap();
		GustTimer = 0.1f;
	}
	UpdateWakeMap(DeltaSeconds);
	UpdateMaterial();
}

void AWaterSurface::UpdateMaterial()
{
	const FWaveField* Waves = GetWaves();
	if (!WaterMaterial || !Waves)
	{
		return;
	}
	const FWaveComponent* C = Waves->GetComponents();
	if (!bStaticParamsSet)
	{
		for (int32 I = 0; I < kWaveComponents; ++I)
		{
			WaterMaterial->SetVectorParameterValue(*FString::Printf(TEXT("Wave%02d"), I), FLinearColor(C[I].Kx, C[I].Ky, C[I].Omega, C[I].Phase));
		}
		bStaticParamsSet = true;
	}
	for (int32 I = 0; I < kWaveComponents / 4; ++I)
	{
		WaterMaterial->SetVectorParameterValue(*FString::Printf(TEXT("WaveAmp%02d"), I),
			FLinearColor(C[4 * I].Amplitude, C[4 * I + 1].Amplitude, C[4 * I + 2].Amplitude, C[4 * I + 3].Amplitude));
	}
	WaterMaterial->SetScalarParameterValue(TEXT("WaveTime"), float(GetSimTime()));
	WaterMaterial->SetVectorParameterValue(TEXT("GustRect"), FLinearColor(GustCenter.X, GustCenter.Y, kGustSizeM, 0.f));
	WaterMaterial->SetVectorParameterValue(TEXT("WakeRect"), FLinearColor(WakeCenter.X, WakeCenter.Y, kWakeSizeM, 0.f));

	if (const FWindField* Wind = GetWind())
	{
		const FWindParams& P = Wind->GetParams();
		const float From = FMath::DegreesToRadians(P.FromDegrees);
		const float Knots = Wind->VelocityAt(Vec3(BoatPos.X, BoatPos.Y, 10.0), GetSimTime()).LengthXY() / kKnot;
		// Whitecaps start around 11 kn and are common by 18.
		const float Caps = FMath::Clamp((Knots - 11.f) / 7.f, 0.f, 1.f);
		WaterMaterial->SetVectorParameterValue(TEXT("WindParams"), FLinearColor(-FMath::Cos(From), -FMath::Sin(From), Knots * kKnot, Caps));
	}
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		WaterMaterial->SetScalarParameterValue(TEXT("Rain"), float(GM->GetWeatherState().Rain));
	}
}

void AWaterSurface::UpdateGustMap()
{
	const FWindField* Wind = GetWind();
	if (!Wind || !GustMap)
	{
		return;
	}
	const float Texel = kGustSizeM / kGustRes;
	GustCenter = FVector2D(FMath::GridSnap(BoatPos.X, Texel), FMath::GridSnap(BoatPos.Y, Texel));
	const double T = GetSimTime();
	const FVector2D Center = GustCenter;
	ParallelFor(kGustRes, [&](int32 Y)
	{
		for (int32 X = 0; X < kGustRes; ++X)
		{
			// Texel centers; the material maps UV (0..1) across GustRect.
			const double WX = Center.X + (X + 0.5 - kGustRes * 0.5) * Texel;
			const double WY = Center.Y + (Y + 0.5 - kGustRes * 0.5) * Texel;
			const double R = Wind->SurfaceRoughnessAt(WX, WY, T);
			const uint8 V = uint8(FMath::Clamp(R / 2.5, 0.0, 1.0) * 255.0);
			// Texture rows run along +V; the material uses u = world X, v = world Y.
			uint8* Px = &GustPixels[(Y * kGustRes + X) * 4];
			Px[0] = V; Px[1] = V; Px[2] = V; Px[3] = 255; // B, G, R, A
		}
	});
	Upload(GustMap, GustPixels, kGustRes);
}

void AWaterSurface::UpdateWakeMap(float DeltaSeconds)
{
	if (!WakeMap)
	{
		return;
	}
	// Trail of stern positions.
	for (FWakePoint& P : WakeTrail) P.Age += DeltaSeconds;
	WakeTrail.RemoveAll([](const FWakePoint& P) { return P.Age > kTrailSeconds; });
	const FVector2D Fwd(FMath::Cos(BoatHeading), FMath::Sin(BoatHeading));
	const FVector2D Stern = BoatPos - Fwd * 3.0f;
	TrailTimer -= DeltaSeconds;
	if (TrailTimer <= 0.f)
	{
		WakeTrail.Add({ Stern, 0.f, BoatSpeed });
		TrailTimer = 0.1f;
	}

	const float Texel = kWakeSizeM / kWakeRes;
	WakeCenter = FVector2D(FMath::GridSnap(BoatPos.X, Texel), FMath::GridSnap(BoatPos.Y, Texel));
	const FVector2D Center = WakeCenter;
	const FVector2D Side(-Fwd.Y, Fwd.X);
	const float SpeedFactor = FMath::Clamp((BoatSpeed - 0.5f) / 3.0f, 0.f, 1.f);
	const FVector2D Bow = BoatPos + Fwd * 3.3f;
	const TArray<FWakePoint> Trail = WakeTrail;

	ParallelFor(kWakeRes, [&](int32 Y)
	{
		for (int32 X = 0; X < kWakeRes; ++X)
		{
			const FVector2D P(Center.X + (X + 0.5f - kWakeRes * 0.5f) * Texel, Center.Y + (Y + 0.5f - kWakeRes * 0.5f) * Texel);
			float Foam = 0.f;

			// Turbulent wake: a widening, fading band along the stern's track.
			for (int32 I = 1; I < Trail.Num(); ++I)
			{
				const FVector2D A = Trail[I - 1].Pos, B = Trail[I].Pos;
				const FVector2D AB = B - A;
				const float Len2 = AB.SizeSquared();
				const float T = Len2 > 1e-6f ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / Len2, 0.f, 1.f) : 0.f;
				const float D = FVector2D::Distance(P, A + AB * T);
				const float Age = FMath::Lerp(Trail[I - 1].Age, Trail[I].Age, T);
				const float Speed = FMath::Lerp(Trail[I - 1].Speed, Trail[I].Speed, T);
				const float Width = 0.45f + 0.10f * Age * FMath::Max(Speed, 0.5f);
				if (D > 3.f * Width) continue;
				const float Strength = FMath::Clamp((Speed - 0.5f) / 3.f, 0.f, 1.f) * (1.f - Age / kTrailSeconds) * 0.75f;
				Foam = FMath::Max(Foam, Strength * FMath::Exp(-(D * D) / (Width * Width)));
			}

			// Kelvin wake arms (19.5 degrees each side) and the bow wave.
			const FVector2D R = P - Bow;
			const float Along = FVector2D::DotProduct(R, Fwd);
			const float Across = FMath::Abs(FVector2D::DotProduct(R, Side));
			if (Along < 0.f)
			{
				const float Behind = -Along;
				const float Arm = Behind * 0.3536f + 0.9f; // tan(19.47 deg), starting at the beam
				const float Band = (Across - Arm) / (0.25f + 0.02f * Behind);
				Foam = FMath::Max(Foam, SpeedFactor * SpeedFactor * 0.7f * FMath::Exp(-Band * Band) * FMath::Exp(-Behind / 14.f));
			}
			{
				const float BowBand = (Along + 0.6f) / 0.9f;
				const float SideBand = (Across - 1.05f) / 0.45f;
				Foam = FMath::Max(Foam, SpeedFactor * 0.8f * FMath::Exp(-BowBand * BowBand - SideBand * SideBand));
			}

			const uint8 V = uint8(FMath::Clamp(Foam, 0.f, 1.f) * 255.f);
			uint8* Px = &WakePixels[(Y * kWakeRes + X) * 4];
			Px[0] = V; Px[1] = V; Px[2] = V; Px[3] = 255;
		}
	});
	Upload(WakeMap, WakePixels, kWakeRes);
}
