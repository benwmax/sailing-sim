#include "WaterSurface.h"
#include "Ocean.h"
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
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
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
	constexpr float kTrailSeconds = 8.f;

	UTexture2D* MakeMap(int32 Size)
	{
		UTexture2D* Tex = UTexture2D::CreateTransient(Size, Size, PF_B8G8R8A8);
		// sRGB to match the material's Color sampler (a mismatch makes the renderer fall back to the default
		// texture); values are gamma-encoded on the CPU so the GPU decodes them back to linear.
		Tex->SRGB = true;
		Tex->Filter = TF_Bilinear;
		Tex->AddressX = TA_Clamp;
		Tex->AddressY = TA_Clamp;
		Tex->UpdateResource();
		return Tex;
	}

	uint8 EncodeSrgb(float Linear)
	{
		const float C = FMath::Clamp(Linear, 0.f, 1.f);
		const float S = C <= 0.0031308f ? 12.92f * C : 1.055f * FMath::Pow(C, 1.f / 2.4f) - 0.055f;
		return uint8(FMath::RoundToInt(S * 255.f));
	}

	/** A float texture (data, not colour: no sRGB), wrapping or clamped. */
	UTexture2D* MakeFloatMap(int32 Width, int32 Height, EPixelFormat Format, bool bWrap)
	{
		UTexture2D* Tex = UTexture2D::CreateTransient(Width, Height, Format);
		Tex->SRGB = false;
		Tex->Filter = TF_Bilinear;
		Tex->AddressX = bWrap ? TA_Wrap : TA_Clamp;
		Tex->AddressY = bWrap ? TA_Wrap : TA_Clamp;
		Tex->CompressionSettings = TC_HDR;
		Tex->UpdateResource();
		return Tex;
	}

	void UploadFloats(UTexture2D* Tex, const TArray<float>& Values, int32 Width, int32 Height, int32 Channels)
	{
		const int32 Bytes = Values.Num() * sizeof(float);
		uint8* Copy = new uint8[Bytes];
		FMemory::Memcpy(Copy, Values.GetData(), Bytes);
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, Width, Height);
		Tex->UpdateTextureRegions(0, 1, Region, Width * Channels * sizeof(float), Channels * sizeof(float), Copy, [](uint8* Data, const FUpdateTextureRegion2D* R)
		{
			delete[] Data;
			delete R;
		});
	}

	void Upload(UTexture2D* Tex, const TArray<uint8>& Pixels, int32 Size)
	{
		// Copy the pixels for the render thread; it frees them when the upload is done.
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
		float DebugGust = 0.f;
		FParse::Value(FCommandLine::Get(), TEXT("SailingDebugGust="), DebugGust);
		WaterMaterial->SetScalarParameterValue(TEXT("DebugGust"), DebugGust);
		WaterMaterial->SetTextureParameterValue(TEXT("GustMap"), GustMap);
		WaterMaterial->SetTextureParameterValue(TEXT("WakeMap"), WakeMap);
		UTexture* Bound = nullptr;
		const bool bFound = WaterMaterial->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("GustMap")), Bound);
		UE_LOG(LogSailing, Display, TEXT("Water material %s: GustMap parameter %s, bound to %s"), *WaterMaterial->GetName(),
			bFound ? TEXT("found") : TEXT("MISSING"), Bound ? *Bound->GetName() : TEXT("nothing"));
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
	WakeTimer -= DeltaSeconds;
	if (WakeTimer <= 0.f)
	{
		UpdateWakeMap(FMath::Max(DeltaSeconds, 1.f / 30.f));
		WakeTimer = 1.f / 30.f;
	}
	UpdateMaterial();
	UpdateOcean();
}

void AWaterSurface::UpdateOcean()
{
	const FWaveField* Waves = GetWaves();
	const FOcean* Ocean = Waves ? Waves->GetOcean() : nullptr;
	if (!WaterMaterial) return;
	if (!Ocean)
	{
		WaterMaterial->SetVectorParameterValue(TEXT("OceanParams"), FLinearColor(480.f, 60.f, 0.f, 6000.f));
		return;
	}
	if (OceanMaps.Num() == 0)
	{
		for (int32 C = 0; C < FOcean::NumCascades; ++C) OceanMaps.Add(MakeFloatMap(FOcean::N, FOcean::N, PF_A32B32G32R32F, true));
		WaterMaterial->SetTextureParameterValue(TEXT("OceanA"), OceanMaps[0]);
		WaterMaterial->SetTextureParameterValue(TEXT("OceanB"), OceanMaps[1]);
		// Open Gulf water: bluer and clearer than the bay.
		WaterMaterial->SetVectorParameterValue(TEXT("WaterColor"), FLinearColor(0.012f, 0.05f, 0.06f));
	}
	// The grids at the frame's time, blended between the ocean's 30 Hz evaluations exactly as the physics does.
	const double T = GetSimTime();
	const double T0 = FMath::FloorToDouble(T * 30.0) / 30.0, W = (T - T0) * 30.0;
	TArray<float> Pixels;
	Pixels.SetNumUninitialized(FOcean::N * FOcean::N * 4);
	for (int32 C = 0; C < FOcean::NumCascades; ++C)
	{
		const FOcean::FGrid& A = Ocean->Evaluate(C, T0);
		const FOcean::FGrid& B = Ocean->Evaluate(C, T0 + 1.0 / 30.0);
		for (int32 I = 0; I < FOcean::N * FOcean::N; ++I)
		{
			Pixels[4 * I + 0] = float((1.0 - W) * A.H[I] + W * B.H[I]);
			Pixels[4 * I + 1] = float((1.0 - W) * A.Sx[I] + W * B.Sx[I]);
			Pixels[4 * I + 2] = float((1.0 - W) * A.Sy[I] + W * B.Sy[I]);
			Pixels[4 * I + 3] = 0.f;
		}
		UploadFloats(OceanMaps[C], Pixels, FOcean::N, FOcean::N, 4);
	}
	// The mask (where the open sea reaches), uploaded again only when the ocean rebuilt it.
	const FOcean::FMask& M = Ocean->GetMask();
	const size_t Hash = M.Values.size() ^ (M.Values.empty() ? 0 : size_t(M.Values[M.Values.size() / 2] * 1e6f + M.Values[M.Values.size() / 3] * 1e3f));
	if (M.Rows > 0 && (UploadedMask != M.Values.data() || Hash != UploadedMaskHash))
	{
		if (!OceanMaskMap || OceanMaskMap->GetSizeX() != M.Cols || OceanMaskMap->GetSizeY() != M.Rows)
		{
			OceanMaskMap = MakeFloatMap(M.Cols, M.Rows, PF_R32_FLOAT, false);
			WaterMaterial->SetTextureParameterValue(TEXT("OceanMask"), OceanMaskMap);
		}
		TArray<float> Mask(M.Values.data(), int32(M.Values.size()));
		UploadFloats(OceanMaskMap, Mask, M.Cols, M.Rows, 1);
		WaterMaterial->SetVectorParameterValue(TEXT("OceanMaskRect"), FLinearColor(M.X0, M.Y0, (M.Rows - 1) * M.Cell, (M.Cols - 1) * M.Cell));
		UploadedMask = M.Values.data();
		UploadedMaskHash = Hash;
	}
	// The sea runs out to the horizon: fade it only far away.
	WaterMaterial->SetVectorParameterValue(TEXT("OceanParams"), FLinearColor(float(FOcean::Tile[0]), float(FOcean::Tile[1]), 1.f, 8000.f));
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
		// Whitecaps by the Beaufort scale: scattered from 7-10 kn, numerous by 11-16, everywhere from 22 (as in M_Water).
		const float Caps = FMath::Pow(FMath::Clamp((Knots - 7.f) / 15.f, 0.f, 1.f), 1.2f);
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
			const uint8 V = EncodeSrgb(float(R / 2.5));
			// Texture rows run along +V; the material uses u = world X, v = world Y.
			uint8* Px = &GustPixels[(Y * kGustRes + X) * 4];
			Px[0] = V; Px[1] = V; Px[2] = V; Px[3] = 255; // B, G, R, A
		}
	});
	Upload(GustMap, GustPixels, kGustRes);

	// -SailingDumpGust: write the cat's-paw map as a PGM image once, to check what the water is shown.
	static bool bDumped = false;
	if (!bDumped && T > 4.0 && FParse::Param(FCommandLine::Get(), TEXT("SailingDumpGust")))
	{
		bDumped = true;
		FString Pgm = FString::Printf(TEXT("P2\n%d %d\n255\n"), kGustRes, kGustRes);
		for (int32 Y = kGustRes - 1; Y >= 0; --Y)
		{
			for (int32 X = 0; X < kGustRes; ++X) Pgm += FString::Printf(TEXT("%d "), GustPixels[(Y * kGustRes + X) * 4]);
			Pgm += TEXT("\n");
		}
		FFileHelper::SaveStringToFile(Pgm, *(FPaths::ProjectSavedDir() / TEXT("Bench/gust.pgm")));
	}
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
	const FVector2D Origin = Center - FVector2D(kWakeSizeM * 0.5f, kWakeSizeM * 0.5f);

	// Turbulent wake: stamp each trail segment into the texels it can reach (a widening, fading band).
	TArray<float> Foam;
	Foam.SetNumZeroed(kWakeRes * kWakeRes);
	for (int32 I = 1; I < WakeTrail.Num(); ++I)
	{
		const FWakePoint& PA = WakeTrail[I - 1];
		const FWakePoint& PB = WakeTrail[I];
		const float Speed = 0.5f * (PA.Speed + PB.Speed);
		const float Age = 0.5f * (PA.Age + PB.Age);
		// A small boat's wake is a faint, broken trail of bubbles that is gone a few lengths astern; what lasts is a
		// smooth slick, not foam (Phase 8: RH-004, TXL-005, J22-H-006 from a drone; the blind test's ILCA frame).
		const float Strength = FMath::Clamp((Speed - 0.5f) / 3.f, 0.f, 1.f) * FMath::Exp(-Age / 2.f) * 0.3f;
		if (Strength < 0.01f) continue;
		const float Width = 0.35f + 0.06f * Age * FMath::Max(Speed, 0.5f);
		const float Reach = 2.5f * Width;
		const FVector2D A = PA.Pos, AB = PB.Pos - PA.Pos;
		const float Len2 = AB.SizeSquared();
		const int32 X0 = FMath::Max(0, FMath::FloorToInt((FMath::Min(A.X, PB.Pos.X) - Reach - Origin.X) / Texel));
		const int32 X1 = FMath::Min(kWakeRes - 1, FMath::CeilToInt((FMath::Max(A.X, PB.Pos.X) + Reach - Origin.X) / Texel));
		const int32 Y0 = FMath::Max(0, FMath::FloorToInt((FMath::Min(A.Y, PB.Pos.Y) - Reach - Origin.Y) / Texel));
		const int32 Y1 = FMath::Min(kWakeRes - 1, FMath::CeilToInt((FMath::Max(A.Y, PB.Pos.Y) + Reach - Origin.Y) / Texel));
		for (int32 Y = Y0; Y <= Y1; ++Y)
		{
			for (int32 X = X0; X <= X1; ++X)
			{
				const FVector2D P(Origin.X + (X + 0.5f) * Texel, Origin.Y + (Y + 0.5f) * Texel);
				const float T = Len2 > 1e-6f ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / Len2, 0.f, 1.f) : 0.f;
				const float D2 = FVector2D::DistSquared(P, A + AB * T);
				float& F = Foam[Y * kWakeRes + X];
				F = FMath::Max(F, Strength * FMath::Exp(-D2 / (Width * Width)));
			}
		}
	}

	// Kelvin wake arms (19.5 degrees each side) and the bow wave, near the bow only.
	if (SpeedFactor > 0.f)
	{
		const float Range = 22.f;
		const int32 X0 = FMath::Max(0, FMath::FloorToInt((Bow.X - Range - Origin.X) / Texel)), X1 = FMath::Min(kWakeRes - 1, FMath::CeilToInt((Bow.X + Range - Origin.X) / Texel));
		const int32 Y0 = FMath::Max(0, FMath::FloorToInt((Bow.Y - Range - Origin.Y) / Texel)), Y1 = FMath::Min(kWakeRes - 1, FMath::CeilToInt((Bow.Y + Range - Origin.Y) / Texel));
		for (int32 Y = Y0; Y <= Y1; ++Y)
		{
			for (int32 X = X0; X <= X1; ++X)
			{
				const FVector2D R(Origin.X + (X + 0.5f) * Texel - Bow.X, Origin.Y + (Y + 0.5f) * Texel - Bow.Y);
				const float Along = FVector2D::DotProduct(R, Fwd);
				const float Across = FMath::Abs(FVector2D::DotProduct(R, Side));
				float& F = Foam[Y * kWakeRes + X];
				if (Along < 0.f)
				{
					const float Behind = -Along;
					const float Arm = Behind * 0.3536f + 0.9f; // tan(19.47 deg), starting at the beam
					const float Band = (Across - Arm) / (0.25f + 0.02f * Behind);
					F = FMath::Max(F, SpeedFactor * SpeedFactor * 0.35f * FMath::Exp(-Band * Band) * FMath::Exp(-Behind / 10.f));
				}
				const float BowBand = (Along + 0.6f) / 0.9f;
				const float SideBand = (Across - 1.05f) / 0.45f;
				F = FMath::Max(F, SpeedFactor * 0.5f * FMath::Exp(-BowBand * BowBand - SideBand * SideBand));
			}
		}
	}

	for (int32 I = 0; I < kWakeRes * kWakeRes; ++I)
	{
		const uint8 V = EncodeSrgb(Foam[I]);
		uint8* Px = &WakePixels[I * 4];
		Px[0] = V; Px[1] = V; Px[2] = V; Px[3] = 255;
	}
	Upload(WakeMap, WakePixels, kWakeRes);
}
