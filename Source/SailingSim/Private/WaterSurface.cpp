#include "WaterSurface.h"
#include "SeaState.h"
#include "BenchRunner.h"
#include "PerfScopes.h"
#include "Ocean.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Async/Async.h"
#include "Async/ParallelFor.h"
#include "EngineUtils.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "TrafficManager.h"
#include "Components/InstancedStaticMeshComponent.h"
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
#include "HAL/IConsoleManager.h"
#include "EngineUtils.h"
#include "LakeTerrainActor.h"
#include "Components/InstancedStaticMeshComponent.h"

using namespace Sailing;

namespace
{
	// W2: the two-level wind map (was one 64 x 64 map over 1.6 km): near 256 x 256 over 3.2 km (12.5 m texels; 512 on
	// Ultra), far 128 x 128 over 16 km (125 m). Each texel's roughness rises over kRiseSeconds and settles over
	// kFallSeconds (the water ruffles within seconds of a puff and smooths over ten); the slow speed (slicks, windrows)
	// follows over kSlowSeconds.
	constexpr float kNearSizeM = 3200.f;
	constexpr float kFarSizeM = 16000.f;
	constexpr int32 kFarRes = 128;
	constexpr double kRiseSeconds = 2.0, kFallSeconds = 10.0, kSlowSeconds = 30.0, kWindrowSeconds = 120.0;
	constexpr int32 kWakeRes = 128;
	constexpr float kWakeSizeM = 64.f;
	constexpr int32 kRingQuads = 128;     // quads across each ring
	constexpr float kFinestSpacingM = 0.5f;
	constexpr float kTrailSeconds = 8.f;
	constexpr double kDetailStep = 1.0 / 30.0;  // FFT short waves: evaluated at 30 Hz, blended between
	constexpr float kDetailFadeM = 300.f;       // distance they fade over (past it their slopes become roughness)
	constexpr int32 kMaxDroplets = 600;
	constexpr int32 kShoreRes = 512;            // shore map: 512 m around the boat at 1 m
	constexpr float kShoreCellM = 1.f;

	/** Water bodies (Single Layer Water: scattering albedo and extinction per metre, red/green/blue). */
	struct FWaterBody { FLinearColor Albedo, Extinction; };
	FWaterBody WaterBodyFor(int32 World)
	{
		switch (World)
		{
		// Galveston Bay: shallow, silty, grey-green; about 0.6 m of Secchi depth.
		case 1: return { FLinearColor(0.15f, 0.20f, 0.14f), FLinearColor(2.3f, 1.8f, 2.4f) };
		// The Gulf off Galveston: green, a few metres of visibility (river silt and plankton); red goes first. Graphics G6:
		// greener and less saturated than the V4 teal (0.04, 0.20, 0.21), which read as tropical under an overcast.
		case 2: return { FLinearColor(0.08f, 0.16f, 0.13f), FLinearColor(0.62f, 0.32f, 0.42f) };
		// Lake Ray Hubbard: olive grey-green, about half a metre of visibility, blue absorbed most. (Seen from a boat the
		// sky's reflection dominates; the body only tints it: the drone and chase references.)
		default: return { FLinearColor(0.16f, 0.18f, 0.11f), FLinearColor(2.4f, 2.0f, 2.8f) };
		}
	}

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

	/** W2: a wind map stored wrap-around (a texel at world index i lives at i mod Res): the sampler wraps too. */
	UTexture2D* MakeWrapMap(int32 Size)
	{
		UTexture2D* Tex = UTexture2D::CreateTransient(Size, Size, PF_B8G8R8A8);
		Tex->SRGB = true; // the material's Color sampler; RGB are gamma-encoded on the CPU, alpha stays linear
		Tex->Filter = TF_Bilinear;
		Tex->AddressX = TA_Wrap;
		Tex->AddressY = TA_Wrap;
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

	/** A wrapping RGBA half-float texture with a full mip chain: the pixel shader filters it (trilinear), so distant
	 *  short waves average out instead of sparkling. Half floats halve what the anisotropic
	 *  taps fetch; centimetre heights and slopes keep three significant digits. */
	UTexture2D* MakeFloatMapMips(int32 Size)
	{
		UTexture2D* Tex = NewObject<UTexture2D>(GetTransientPackage(), NAME_None, RF_Transient);
		FTexturePlatformData* Data = new FTexturePlatformData();
		Data->SizeX = Size;
		Data->SizeY = Size;
		Data->PixelFormat = PF_FloatRGBA;
		for (int32 S = Size; S >= 1; S /= 2)
		{
			FTexture2DMipMap* Mip = new FTexture2DMipMap(S, S, 1);
			Data->Mips.Add(Mip);
			Mip->BulkData.Lock(LOCK_READ_WRITE);
			FMemory::Memzero(Mip->BulkData.Realloc(int64(S) * S * 8), int64(S) * S * 8);
			Mip->BulkData.Unlock();
		}
		Tex->SetPlatformData(Data);
		Tex->SRGB = false;
		Tex->Filter = TF_Trilinear; // no anisotropy: what a mip averages away comes back as roughness (LEAN)
		Tex->AddressX = TA_Wrap;
		Tex->AddressY = TA_Wrap;
		Tex->CompressionSettings = TC_HDR;
		Tex->NeverStream = true;
		Tex->UpdateResource();
		return Tex;
	}

	/** Level 0 (RGBA floats) and its box-filtered mips, packed to half floats: one new[] block per mip, which
	 *  UploadPackedMips hands to the render thread (Perf 1: built on a worker). */
	void PackMips(TArray<float> Level, int32 Size, TArray<uint8*>& Out)
	{
		for (int32 S = Size;;)
		{
			uint8* Bytes = new uint8[Level.Num() * sizeof(FFloat16)];
			FFloat16* Halfs = reinterpret_cast<FFloat16*>(Bytes);
			for (int32 I = 0; I < Level.Num(); ++I) Halfs[I] = FFloat16(Level[I]);
			Out.Add(Bytes);
			if (S == 1) break;
			const int32 Half = S / 2;
			TArray<float> Next;
			Next.SetNumUninitialized(Half * Half * 4);
			for (int32 R = 0; R < Half; ++R)
			{
				for (int32 C = 0; C < Half; ++C)
				{
					for (int32 K = 0; K < 4; ++K)
					{
						Next[(R * Half + C) * 4 + K] = 0.25f * (Level[((2 * R) * S + 2 * C) * 4 + K] + Level[((2 * R) * S + 2 * C + 1) * 4 + K]
							+ Level[((2 * R + 1) * S + 2 * C) * 4 + K] + Level[((2 * R + 1) * S + 2 * C + 1) * 4 + K]);
					}
				}
			}
			Level = MoveTemp(Next);
			S = Half;
		}
	}

	/** Enqueues the packed mips' upload (the render thread frees each block when done). */
	void UploadPackedMips(UTexture2D* Tex, TArray<uint8*>& Mips, int32 Size)
	{
		for (int32 Mip = 0, S = Size; Mip < Mips.Num(); ++Mip, S = FMath::Max(1, S / 2))
		{
			FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, S, S);
			Tex->UpdateTextureRegions(Mip, 1, Region, S * 4 * sizeof(FFloat16), 4 * sizeof(FFloat16), Mips[Mip], [](uint8* Data, const FUpdateTextureRegion2D* R)
			{
				delete[] Data;
				delete R;
			});
		}
		Mips.Reset();
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

double AWaterSurface::WaterCpuSeconds = 0.0;

namespace
{
	// W2: polarized sunglasses on the water (they cut the sky's glare, so puffs, lulls and slicks stand out):
	// -SailingPolarized, or the console's sailing.Polarized 1.
	int32 GPolarized = 0;
	FAutoConsoleVariableRef CVarPolarized(TEXT("sailing.Polarized"), GPolarized,
		TEXT("Polarized sunglasses on the water (1 on, 0 off): the sky's glare cut near Brewster's angle."));
}

AWaterSurface::AWaterSurface()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics; // after the boat has stepped, so the wake is current

	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Water(TEXT("/Game/Materials/M_Water.M_Water"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> WaterV4(TEXT("/Game/Materials/M_WaterV4.M_WaterV4"));
	ClassicMaterial = Water.Object;
	DetailedMaterial = WaterV4.Object;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SprayMat(TEXT("/Game/Materials/M_Spray.M_Spray"));
	DropletMesh = Sphere.Object;
	SprayMaterial = SprayMat.Object;

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
	// W2: the near wind map is 512 x 512 on Ultra, 256 x 256 otherwise; each tick refreshes one strip of rows (every
	// texel each 0.8 s).
	const bool bUltra = USailingSettings::Get()->Quality == ESailingQuality::Ultra;
	NearWind.Res = bUltra ? 512 : 256;
	NearWind.Strips = bUltra ? 16 : 8;
	NearWind.SizeM = kNearSizeM;
	FarWind.Res = kFarRes;
	FarWind.Strips = 8;
	FarWind.SizeM = kFarSizeM;
	for (FWindLevel* L : { &NearWind, &FarWind })
	{
		L->Texels.SetNum(L->Res * L->Res);
		L->Pixels.SetNumZeroed(L->Res * L->Res * 4);
	}
	GustMap = MakeWrapMap(NearWind.Res);
	WindFarMap = MakeWrapMap(FarWind.Res);
	WakeMap = MakeMap(kWakeRes);
	WakePixels.SetNumZeroed(kWakeRes * kWakeRes * 4);
	CreateWaterMaterial();
	BuildRings();
}

void AWaterSurface::SetQualityTier(int32 InTier)
{
	const int32 Clamped = FMath::Clamp(InTier, 0, 2);
	if (Clamped == Tier && (WaterMaterial || !HasActorBegunPlay())) return;
	Tier = Clamped;
	if (HasActorBegunPlay())
	{
		CreateWaterMaterial();
	}
}

void AWaterSurface::CreateWaterMaterial()
{
	// -SailingClassicWater: M_Water on every tier (measuring the V4 water's cost).
	bV4 = Tier >= 1 && DetailedMaterial != nullptr && !FParse::Param(FCommandLine::Get(), TEXT("SailingClassicWater"));
	UMaterialInterface* Parent = bV4 ? DetailedMaterial.Get() : ClassicMaterial.Get();
	if (!Parent) return;
	WaterMaterial = UMaterialInstanceDynamic::Create(Parent, this);
	FarPlane->SetMaterial(0, WaterMaterial);
	for (UProceduralMeshComponent* Ring : Rings)
	{
		if (Ring) Ring->SetMaterial(0, WaterMaterial);
	}
	bStaticParamsSet = false;
	UploadedSeaGeneration = UINT32_MAX; // W3: bind the sea atlas to the new instance
	float DebugGust = 0.f;
	FParse::Value(FCommandLine::Get(), TEXT("SailingDebugGust="), DebugGust);
	WaterMaterial->SetScalarParameterValue(TEXT("DebugGust"), DebugGust);
	// W8: -SailingDebugFoam: M_WaterV4 draws the whitecaps alone (white on black) for counting on a screenshot.
	// (=2 the crests alone, =3 where the fold is under the threshold; -SailingDebugCaps logs the solved thresholds.)
	float DebugFoam = FParse::Param(FCommandLine::Get(), TEXT("SailingDebugFoam")) ? 1.f : 0.f;
	FParse::Value(FCommandLine::Get(), TEXT("SailingDebugFoam="), DebugFoam);
	WaterMaterial->SetScalarParameterValue(TEXT("DebugFoam"), DebugFoam);
	WaterMaterial->SetTextureParameterValue(TEXT("GustMap"), GustMap);
	WaterMaterial->SetTextureParameterValue(TEXT("WindFar"), WindFarMap);
	WaterMaterial->SetTextureParameterValue(TEXT("WakeMap"), WakeMap);
	if (OceanMaps.Num() == 2)
	{
		WaterMaterial->SetTextureParameterValue(TEXT("OceanA"), OceanMaps[0]);
		WaterMaterial->SetTextureParameterValue(TEXT("OceanB"), OceanMaps[1]);
		WaterMaterial->SetVectorParameterValue(TEXT("OceanColor"), FLinearColor(0.012f, 0.05f, 0.06f)); // W2: blended by the swell mask
	}
	UploadedMask = nullptr; // binds the mask again on the next ocean update
	OceanMaskMap = nullptr;

	if (bV4)
	{
		const FWaveDetail::FCascadeSpec Chop = FWaveDetail::ChopCascade(), Ripple = FWaveDetail::RippleCascade();
		if (!DetailAMap)
		{
			DetailAMap = MakeFloatMapMips(Chop.N);
			DetailBMap = MakeFloatMapMips(Chop.N);
			DetailCMap = MakeFloatMapMips(Chop.N);
			RippleBMap = MakeFloatMapMips(Ripple.N);
		}
		// The wake grid: 38 m around the boat on Medium (128 cells of 0.3 m), 64 m on High (256 of 0.25 m).
		const int32 WakeN = Tier >= 2 ? 256 : 128;
		if (Wake.Size() != WakeN)
		{
			WaitForWorkers();
			Wake.Init(WakeN, Tier >= 2 ? 0.25f : 0.3f);
			WakeGridMap = MakeFloatMap(WakeN, WakeN, PF_G32R32F, false);
		}
		WaterMaterial->SetTextureParameterValue(TEXT("DetailA"), DetailAMap);
		WaterMaterial->SetTextureParameterValue(TEXT("DetailB"), DetailBMap);
		WaterMaterial->SetTextureParameterValue(TEXT("DetailC"), DetailCMap);
		WaterMaterial->SetTextureParameterValue(TEXT("RippleB"), RippleBMap);
		WaterMaterial->SetTextureParameterValue(TEXT("WakeGrid"), WakeGridMap);
		if (ShoreMap && bShoreValid)
		{
			WaterMaterial->SetTextureParameterValue(TEXT("ShoreMap"), ShoreMap);
			WaterMaterial->SetVectorParameterValue(TEXT("ShoreRect"), FLinearColor(float(ShoreOrigin.X), float(ShoreOrigin.Y), kShoreRes * kShoreCellM, 1.f));
		}
		WaterMaterial->SetVectorParameterValue(TEXT("DetailParams"), FLinearColor(float(Chop.Tile), float(Ripple.Tile), kDetailFadeM, Tier >= 2 ? 1.f : 0.f));
		WaterMaterial->SetScalarParameterValue(TEXT("Choppiness"), Choppiness);
		WaterMaterial->SetScalarParameterValue(TEXT("SplitOmega"), float(2.0 * UE_DOUBLE_PI * SplitHz));
		const FWaterBody Body = WaterBodyFor(USailingSettings::Get()->World);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterAlbedo"), Body.Albedo);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterExtinction"), Body.Extinction);
		// W2 (the gulf-swell handoff): where the swell mask lets the open sea in, the Gulf's body (the material blends by
		// the mask; in the Gulf world both are the Gulf's, on the lake there is no mask).
		const FWaterBody Sea = WaterBodyFor(2);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterAlbedoSea"), Sea.Albedo);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterExtinctionSea"), Sea.Extinction);
		Detail.Reset(); // reconfigures (the ripples come and go with the tier)
		FramePrev.Reset();
		FrameNext.Reset();
	}
	UE_LOG(LogSailing, Display, TEXT("Water: tier %d, %s"), Tier, *Parent->GetName());
}

float AWaterSurface::WhitecapScaleFor(int32 World)
{
	switch (World)
	{
	case 1: return 0.7f; // Galveston Bay: brackish
	case 2: return 1.f;  // the Gulf: sea water, Monahan's law as measured
	default: return 0.4f; // fresh water: bubbles coalesce and burst sooner, so caps are fewer and fade faster
	}
}

float AWaterSurface::WhitecapOnset(float MeanKnots)
{
	constexpr float OnsetMs = 3.7f, FullMs = 12.f * float(kKnot);
	const float U = FMath::Clamp((MeanKnots * float(kKnot) - OnsetMs) / (FullMs - OnsetMs), 0.f, 1.f);
	return U * U * U;
}

float AWaterSurface::FoamThresholdAt(float MeanKnots)
{
	// Under 10 kn the crests stop breaking (Beaufort 2-3): the threshold falls 0.03 a knot instead of rising on.
	const float K = FMath::Clamp(MeanKnots, 4.f, 40.f);
	return 0.63f + 0.083f * FMath::Exp(-(FMath::Max(K, 10.f) - 10.f) / 5.f) - 0.03f * FMath::Max(10.f - K, 0.f);
}

float AWaterSurface::CapSlopeAt(float MeanKnots)
{
	return 0.018f * FMath::Pow(FMath::Clamp(MeanKnots, 4.f, 40.f) / 10.f, 1.25f);
}

void AWaterSurface::CapTable(float MeanKnots, float WaterScale, float& OutFirst, float& OutStep)
{
	OutStep = FMath::Max(CapSlopeAt(MeanKnots), 0.03f);
	OutFirst = WhitecapThreshold(1.f, WaterScale, MeanKnots) - 1.5f * OutStep;
}

float AWaterSurface::CapTableEntry(float J, int32 K, float First, float Step)
{
	return FMath::Clamp((First + K * Step - J) / CapRamp + 0.5f, 0.f, 1.f);
}

float AWaterSurface::CapCover(const float Table[4], float Threshold, float MeanKnots, float Mip, float First, float Step)
{
	// Mirrors M_WaterV4: in log between the two entries about the threshold (cover is about exponential in it); under
	// the first, an e-fold per CapSlopeAt.
	const float U = (Threshold - First) / Step;
	const int32 I = FMath::Clamp(FMath::FloorToInt(U), 0, 2);
	const float Wt = FMath::Clamp(U - I, 0.f, 1.f);
	const float La = FMath::Loge(FMath::Max(Table[I], 1e-6f)), Lb = FMath::Loge(FMath::Max(Table[I + 1], 1e-6f));
	const float Lin = FMath::Lerp(Table[I], Table[I + 1], Wt);
	const float Log = Table[I + 1] > 1.5e-6f ? FMath::Exp(FMath::Lerp(La, Lb, Wt)) : 0.f;
	float Cover = FMath::Lerp(Lin, Log, FMath::Clamp(Mip / CapLogMip, 0.f, 1.f));
	if (U < 0.f) Cover *= FMath::Exp(U * Step / FMath::Max(CapSlopeAt(MeanKnots), 0.02f));
	return Cover;
}

float AWaterSurface::WhitecapThreshold(float LocalOverMean, float WaterScale, float MeanKnots)
{
	const float Gain = WaterScale * FMath::Pow(FMath::Clamp(LocalOverMean, 0.05f, 4.f), 3.41f);
	return FMath::Clamp(FoamThresholdAt(MeanKnots) + CapSlopeAt(MeanKnots) * FMath::Loge(FMath::Max(Gain, 1e-4f)), 0.3f, 0.85f);
}

void AWaterSurface::SetRingCount(int32 Count)
{
	RingCount = FMath::Clamp(Count, 2, 7);
	FParse::Value(FCommandLine::Get(), TEXT("SailingWaterRings="), RingCount); // measuring
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
		// Tangents along +X: Single Layer Water takes its normal in tangent space.
		TArray<FProcMeshTangent> Tangents;
		Tangents.Init(FProcMeshTangent(FVector(1.0, 0.0, 0.0), false), Verts.Num());
		Ring->CreateMeshSection_LinearColor(0, Verts, Tris, Normals, {}, {}, Tangents, false);
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
	SAILING_PERF_SCOPE(Water);

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
	UpdateHullClip();

	GustTimer -= DeltaSeconds;
	if (GustTimer <= 0.f)
	{
		UpdateGustMap();
		GustTimer = 0.1f;
	}
	TreeScanTimer -= DeltaSeconds;
	static SailingArgs::FCachedFlag NoTreeWindArg(TEXT("SailingNoTreeWind")); // measuring: trees on the global wind
	const bool bNoTreeWind = NoTreeWindArg.Get();
	if (TreeScanTimer <= 0.f && !bNoTreeWind)
	{
		BindTreeWind();
		TreeScanTimer = 3.f;
	}
	WakeTimer -= DeltaSeconds;
	if (WakeTimer <= 0.f)
	{
		if (!bV4) UpdateWakeMap(FMath::Max(DeltaSeconds, 1.f / 30.f));
		WakeTimer = 1.f / 30.f;
	}
	const double Start = FPlatformTime::Seconds();
	UpdateMaterial();
	UpdateOcean();
	if (bV4)
	{
		{ SAILING_PERF_SCOPE(WaterUploads); UpdateDetail(); }
		UpdateWakeGrid(DeltaSeconds);
		UpdateShoreMap();
		if (Tier >= 2) UpdateSpray(DeltaSeconds);
	}
	WaterCpuSeconds += FPlatformTime::Seconds() - Start;
}

void AWaterSurface::UpdateDetail()
{
	const FWaveField* Waves = GetWaves();
	if (!Waves || !WaterMaterial || !DetailAMap) return;

	// The sea the short waves belong to: the physics' wind, fetch and how far the sea has grown toward its target.
	const FWaveParams& WP = Waves->GetParams();
	const double WindMs = WP.WindSpeedKnots * kKnot;
	double Variance = 0.0;
	const FWaveComponent* C = Waves->GetComponents();
	for (int32 I = 0; I < kWaveComponents; ++I) Variance += 0.5 * C[I].Amplitude * C[I].Amplitude;
	// W3: with a sea map the components grow toward the map's reference sea (15 km of fetch); each point scales the
	// short waves by the map's short channel (SShort in the shader).
	const double Fetch = Waves->ReferenceFetch();
	const double Target = FWaveField::TargetSignificantHeight(WindMs, Fetch);
	const double Development = Target > 1e-4 ? FMath::Clamp(4.0 * FMath::Sqrt(Variance) / Target, 0.0, 1.5) : 0.0;
	FWaveDetailParams P;
	P.WindMs = WindMs;
	P.TravelDirRad = FMath::DegreesToRadians(WP.WindFromDegrees) + UE_DOUBLE_PI;
	P.FetchMeters = Fetch;
	P.SplitHz = SplitHz;
	P.Development = FMath::Max(Development, 0.05);
	P.Choppiness = Choppiness;
	// Reconfigure when the sea changes (same seed: the same random field, rescaled and turned); the development in
	// between is an amplitude scale on the evaluation.
	const FWaveDetailParams& Q = DetailConfigured;
	const bool bReconfigure = !Detail || FMath::Abs(P.WindMs - Q.WindMs) > 0.25 || FMath::Abs(FMath::FindDeltaAngleRadians(P.TravelDirRad, Q.TravelDirRad)) > 0.05
		|| FMath::Abs(P.FetchMeters / Q.FetchMeters - 1.0) > 0.1 || FMath::Abs(P.Development / Q.Development - 1.0) > 0.3;
	if (bReconfigure)
	{
		if (bFramePending) { PendingFrame.Wait(); bFramePending = false; }
		TSharedPtr<FWaveDetail, ESPMode::ThreadSafe> New = MakeShared<FWaveDetail, ESPMode::ThreadSafe>();
		std::vector<FWaveDetail::FCascadeSpec> Specs = { FWaveDetail::ChopCascade() };
		if (Tier >= 2) Specs.push_back(FWaveDetail::RippleCascade());
		New->Configure(P, Specs);
		Detail = New;
		DetailConfigured = P;
		FramePrev.Reset();
		FrameNext.Reset();
	}
	const double Scale = P.Development / DetailConfigured.Development;

	TSharedPtr<FWaveDetail, ESPMode::ThreadSafe> D = Detail;
	auto Evaluate = [D, Scale](double At) -> FDetailFramePtr
	{
		FDetailFramePtr F = MakeShared<FDetailFrame, ESPMode::ThreadSafe>();
		F->Source = D.Get();
		F->Time = At;
		D->Evaluate(0, At, F->Chop, Scale);
		if (D->NumCascades() > 1) D->Evaluate(1, At, F->Ripple, Scale);
		return F;
	};
	auto Launch = [&](double At)
	{
		PendingFrame = Async(EAsyncExecution::ThreadPool, [Evaluate, At]() { return Evaluate(At); });
		bFramePending = true;
	};

	const double T = GetSimTime();
	if (!FramePrev || !FrameNext || T < FramePrev->Time - 1e-6 || T > FrameNext->Time + 3.0 * kDetailStep)
	{
		// Start (or a jump in time): the two frames around now on this thread, the next one in the background.
		if (bFramePending) { PendingFrame.Wait(); bFramePending = false; }
		const double T0 = FMath::FloorToDouble(T / kDetailStep) * kDetailStep;
		FramePrev = Evaluate(T0);
		FrameNext = Evaluate(T0 + kDetailStep);
		Launch(T0 + 2.0 * kDetailStep);
	}
	while (T >= FrameNext->Time && bFramePending && PendingFrame.IsReady())
	{
		FDetailFramePtr Ready = PendingFrame.Get();
		bFramePending = false;
		FramePrev = FrameNext;
		FrameNext = Ready->Source == Detail.Get() ? Ready : Evaluate(FramePrev->Time + kDetailStep);
		Launch(FrameNext->Time + kDetailStep);
	}

	// Perf 1 fix 5: hand last frame's blend (made on a worker for this frame's time) to the render thread, then start the
	// next one. A worker still busy (a long hitch) keeps what is drawn.
	if (bUploadPending && PendingUpload.IsReady())
	{
		bUploadPending = false;
		if (const FDetailUploadPtr Done = PendingUpload.Get())
		{
			UploadPackedMips(DetailAMap, Done->A, Done->N);
			UploadPackedMips(DetailBMap, Done->B, Done->N);
			UploadPackedMips(DetailCMap, Done->C, Done->N);
			WaterMaterial->SetVectorParameterValue(TEXT("CapTable"), FLinearColor(Done->CapFirst, Done->CapStep, 0.f, 0.f));
			// W8: the threshold for this sea's share of caps, eased (each frame's quantile is of 16k samples).
			if (Done->CapSlope > 0.f)
			{
				const float A = CapSlopeSmooth > 0.f ? 0.08f : 1.f;
				for (int32 K = 0; K < 4; ++K) CapThrSmooth[K] += A * (Done->CapThr[K] - CapThrSmooth[K]);
				CapSlopeSmooth += A * (Done->CapSlope - CapSlopeSmooth);
				WaterMaterial->SetVectorParameterValue(TEXT("CapCalib"), FLinearColor(CapThrSmooth[0], CapSlopeSmooth, 0.f, 0.f));
				WaterMaterial->SetVectorParameterValue(TEXT("CapCalibFar"), FLinearColor(CapThrSmooth[1], CapThrSmooth[2], CapThrSmooth[3], 0.f));
				static SailingArgs::FCachedFlag DebugCapsArg(TEXT("SailingDebugCaps"));
				static int32 Logged = 0;
				if (DebugCapsArg.Get() && (++Logged % 30) == 0)
					UE_LOG(LogSailing, Display, TEXT("Caps: thresholds %.3f %.3f %.3f %.3f, slope %.3f"), CapThrSmooth[0], CapThrSmooth[1], CapThrSmooth[2], CapThrSmooth[3], CapSlopeSmooth);
			}
			if (Done->RippleN > 0) UploadPackedMips(RippleBMap, Done->Ripple, Done->RippleN);
		}
	}
	if (bUploadPending) return;

	// Blend the two frames to the next frame's instant (this one plus this frame's length): A = height, displacement,
	// Jacobian; B = slopes and their squares.
	const double Ahead = T + FMath::Clamp(double(GetWorld()->GetDeltaSeconds()), 0.0, kDetailStep);
	const float W = float(FMath::Clamp((Ahead - FramePrev->Time) / kDetailStep, 0.0, 1.0));
	const FDetailFramePtr Prev = FramePrev, Next = FrameNext;
	const bool bRipple = Prev->Ripple.N > 0 && Next->Ripple.N == Prev->Ripple.N;
	// W8: Monahan's whitecap cover for the sea's mean wind times the water body's share: the renderer solves the fold
	// threshold that caps it on the sea it draws (the long trains here, the chop's whitecap Jacobian there). Below 12 kn
	// only the share that breaks (WhitecapOnset); never quite zero, so the threshold is extrapolated below every sample.
	const double MeanMs = Waves->GetParams().WindSpeedKnots * kKnot;
	const double CapTarget = FMath::Max(3.84e-6 * FMath::Pow(FMath::Max(MeanMs, 0.0), 3.41) * WhitecapScaleFor(USailingSettings::Get()->World)
		* WhitecapOnset(float(Waves->GetParams().WindSpeedKnots)), 1e-7);
	const double CapTime = Ahead;
	TArray<FWaveComponent> Long(Waves->GetComponents(), kWaveComponents);
	// As M_WaterV4 draws them around the camera: each long train scaled by the sea map's ratio there (W3), the chop by
	// its short scale.
	float CapShort = 1.f;
	if (const FSeaMap* Sea = Waves->GetSeaMap(); Sea && Sea->IsValid())
	{
		const FVector Cam = UGameplayStatics::GetPlayerCameraManager(this, 0) ? UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraLocation() : GetActorLocation();
		float Ratio[kSeaChannels];
		Sea->Sample(Cam.X / CmPerMeter, Cam.Y / CmPerMeter, Ratio);
		for (int32 I = 0; I < kSeaLongComponents && I < Long.Num(); ++I) Long[I].Amplitude *= Ratio[I];
		CapShort = Ratio[kSeaLongComponents];
	}
	PendingUpload = Async(EAsyncExecution::ThreadPool, [Prev, Next, W, bRipple, CapTarget, CapTime, CapShort, Long = MoveTemp(Long)]() -> FDetailUploadPtr
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(Sailing_WaterDetailBlend);
		auto Blend = [W](const std::vector<float>& A, const std::vector<float>& B, size_t I) { return A[I] + W * (B[I] - A[I]); };
		FDetailUploadPtr Out = MakeShared<FDetailUpload, ESPMode::ThreadSafe>();
		{
			const FWaveDetail::FGrid& A = Prev->Chop;
			const FWaveDetail::FGrid& B = Next->Chop;
			const int32 NN = A.N * A.N;
			TArray<float> PixA, PixB, PixC;
			PixA.SetNumUninitialized(NN * 4);
			PixB.SetNumUninitialized(NN * 4);
			PixC.SetNumUninitialized(NN * 4);
			// W8: the whitecap Jacobian of the drawn sea (long trains, as the mesh draws them, times the chop's) at every
			// other grid point, for the thresholds that cap CapTarget of it at four vertex spacings (0.5 m: within 32 m of
			// the camera; 1, 2, 4 m: about 64, 128, 256 m, M_WaterV4's dist / 64, with its distance fade over 900 m). The
			// fold table is centred on the nearest.
			std::vector<float> JCap(NN);
			for (int32 I = 0; I < NN; ++I) JCap[I] = Blend(A.JCap, B.JCap, I);
			const double Cell = A.Tile / A.N, OmegaMax = 2.0 * UE_DOUBLE_PI * SplitHz;
			double CapThr[4] = {}, CapSlope = 0.0;
			for (int32 K = 0; K < 4; ++K)
			{
				const double Spacing = 0.5 * double(1 << K), Fade = FMath::Clamp(1.0 - 64.0 * Spacing / 900.0, 0.0, 1.0);
				std::vector<float> Samples;
				Samples.reserve(NN / 4);
				for (int32 R = 0; R < A.N; R += 2)
					for (int32 Cc = 0; Cc < A.N; Cc += 2)
					{
						const int32 I = R * A.N + Cc;
						const double Chop = 1.0 - FMath::Min(CapShort, 2.f) * (1.0 - JCap[I]); // the shader's jd
						// The long trains sampled over about 170 m (the chop's 23 m tile holds about one of their wavelengths, so a
						// frame's sample sat on whatever crests crossed it), the chop at its own texel.
						const double Jt = FWaveDetail::LongJacobian(Long.GetData(), Long.Num(), OmegaMax, Choppiness, R * Cell * 7.31, Cc * Cell * 7.37, CapTime, Spacing, Fade) * Chop;
						Samples.push_back(float(1.0 - DrawnFoldScale * (1.0 - Jt)));
					}
				double Slope = 0.0;
				FWaveDetail::CapThreshold(MoveTemp(Samples), CapTarget, CapThr[K], Slope);
				if (K == 0) CapSlope = Slope;
			}
			// The table holds the chop's own J: centred on the nearest threshold.
			const float CapStep = FMath::Max(float(CapSlope), 0.03f), CapFirst = float(CapThr[0]) - 1.5f * CapStep;
			for (int32 I = 0; I < NN; ++I)
			{
				PixA[4 * I + 0] = Blend(A.H, B.H, I);
				PixA[4 * I + 1] = Blend(A.Dx, B.Dx, I);
				PixA[4 * I + 2] = Blend(A.Dy, B.Dy, I);
				// W8: the Jacobian the foam reads is the whitecaps' (FWaveDetail::CapBlurTexels: caps on whole crests).
				PixA[4 * I + 3] = JCap[I];
				// W8: the fold table (CapTableEntry): its mips are whitecap cover.
				for (int32 K = 0; K < 4; ++K) PixC[4 * I + K] = CapTableEntry(PixA[4 * I + 3], K, CapFirst, CapStep);
				// Slopes and their squares (LEAN mapping: a mip's mean square minus its squared mean is the slope variance
				// it averaged away, which the material turns into roughness).
				const float Sx = Blend(A.Sx, B.Sx, I), Sy = Blend(A.Sy, B.Sy, I);
				PixB[4 * I + 0] = Sx;
				PixB[4 * I + 1] = Sy;
				PixB[4 * I + 2] = Sx * Sx;
				PixB[4 * I + 3] = Sy * Sy;
			}
			Out->N = A.N;
			PackMips(MoveTemp(PixA), A.N, Out->A);
			PackMips(MoveTemp(PixB), A.N, Out->B);
			PackMips(MoveTemp(PixC), A.N, Out->C);
			Out->CapFirst = CapFirst;
			Out->CapStep = CapStep;
			for (int32 K = 0; K < 4; ++K) Out->CapThr[K] = float(CapThr[K]);
			Out->CapSlope = float(CapSlope);
		}
		if (bRipple)
		{
			const FWaveDetail::FGrid& A = Prev->Ripple;
			const FWaveDetail::FGrid& B = Next->Ripple;
			const int32 NN = A.N * A.N;
			TArray<float> Pix;
			Pix.SetNumUninitialized(NN * 4);
			for (int32 I = 0; I < NN; ++I)
			{
				const float Sx = Blend(A.Sx, B.Sx, I), Sy = Blend(A.Sy, B.Sy, I);
				Pix[4 * I + 0] = Sx;
				Pix[4 * I + 1] = Sy;
				Pix[4 * I + 2] = Sx * Sx;
				Pix[4 * I + 3] = Sy * Sy;
			}
			Out->RippleN = A.N;
			PackMips(MoveTemp(Pix), A.N, Out->Ripple);
		}
		return Out;
	});
	bUploadPending = true;
}

void AWaterSurface::UpdateHullClip()
{
	if (!WaterMaterial) return;
	for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
	{
		if (It->bGhost || It->bTrafficBoat) continue;
		const FBoatModel& M = It->GetBoatModel();
		const std::vector<FHullShape>& Hulls = M.GetConfig().Hulls;
		if (Hulls.empty()) return;
		const FHullShape& S = Hulls[0];
		const Vec3 O = M.OriginPosition();
		const double H = M.GetTelemetry().Heading;
		// Catamarans have no hull on the centreline (the water between the hulls stays); a trimaran's main hull does.
		const bool bOn = Hulls.size() != 2;
		WaterMaterial->SetVectorParameterValue(TEXT("HullClipA"), FLinearColor(float(O.X), float(O.Y), float(FMath::Cos(H)), float(FMath::Sin(H))));
		WaterMaterial->SetVectorParameterValue(TEXT("HullClipB"), FLinearColor(float(S.BowX), float(S.SternX), float(S.MaxBeamX), float(S.MaxHalfBeam)));
		WaterMaterial->SetVectorParameterValue(TEXT("HullClipC"), FLinearColor(float(S.AftLength), float(S.TransomBeamLoss), float(S.CenterY), bOn ? 1.f : 0.f));
		return;
	}
}

void AWaterSurface::UpdateWakeGrid(float DeltaSeconds)
{
	if (!Wake.IsValid() || !WakeGridMap || !WaterMaterial) return;
	WakeDtPending += DeltaSeconds;
	// The grid steps on a worker (two FFTs of up to 256^2 a step); the game thread only gathers the hulls and uploads
	// the last finished step, a frame behind.
	if (bWakePending)
	{
		if (!PendingWake.IsReady()) return;
		const FWakeFrame Done = PendingWake.Get();
		bWakePending = false;
		UploadFloats(WakeGridMap, Done.Pixels, Done.N, Done.N, 2);
		WaterMaterial->SetVectorParameterValue(TEXT("WakeGridRect"), FLinearColor(float(Done.Origin.X), float(Done.Origin.Y), Done.N * Done.Cell, float(Done.N)));
	}

	const FWaveField* Waves = GetWaves();
	const double T = GetSimTime();
	const float Reach = 0.75f * Wake.Size() * Wake.CellSize();

	// Every hull in range: the player's and the AI sailboats (their physics hulls, heeled and heaved on the waves) and
	// the power vessels (a hull of their length and beam). Shapes are copied: the step runs on another thread.
	TSharedPtr<TArray<FHullShape>, ESPMode::ThreadSafe> Shapes = MakeShared<TArray<FHullShape>, ESPMode::ThreadSafe>();
	TArray<FWakeGrid::FHull> Hulls;
	for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
	{
		if (It->bGhost) continue;
		const FBoatModel& M = It->GetBoatModel();
		const Vec3 O = M.OriginPosition();
		if (FVector2D::Distance(FVector2D(O.X, O.Y), BoatPos) > Reach) continue;
		const FBoatTelemetry& Tm = M.GetTelemetry();
		const double Surface = Waves ? Waves->Height(O.X, O.Y, T) : 0.0;
		for (const FHullShape& S : M.GetConfig().Hulls)
		{
			FWakeGrid::FHull H;
			H.Position = FVector2D(O.X, O.Y);
			H.Heading = float(Tm.Heading);
			H.Heel = float(Tm.Heel);
			H.Sink = float(Surface - O.Z);
			H.CanoeDepth = float(M.HullDepth());
			H.Speed = float(Tm.SpeedThroughWater);
			Shapes->Add(S);
			Hulls.Add(H);
		}
	}
	for (TActorIterator<ATrafficManager> It(GetWorld()); It; ++It)
	{
		for (const FTrafficVessel& V : It->GetSim().GetVessels())
		{
			if (V.IsSail() || FVector2D::Distance(FVector2D(V.Power.X, V.Power.Y), BoatPos) > Reach + 0.5f * float(V.Length())) continue;
			FHullShape S;
			const double L = V.Length(), B = V.Beam();
			S.BowX = 0.5 * L;
			S.SternX = -0.5 * L;
			S.WaterlineMidX = 0.0;
			S.WaterlineHalfLength = 0.47 * L;
			S.MaxHalfBeam = 0.5 * B;
			S.MaxBeamX = -0.1 * L;
			S.AftLength = 0.4 * L;
			S.TransomBeamLoss = 0.1 * B;
			S.BilgePower = 3.0;
			FWakeGrid::FHull H;
			H.Position = FVector2D(V.Power.X, V.Power.Y);
			H.Heading = float(V.Power.Heading);
			H.CanoeDepth = float(0.6 * V.Draft());
			H.Speed = float(V.Power.Speed);
			Shapes->Add(S);
			Hulls.Add(H);
		}
	}
	for (int32 I = 0; I < Hulls.Num(); ++I) Hulls[I].Shape = &(*Shapes)[I];

	FWakeGrid* Grid = &Wake;
	const FVector2D Centre = BoatPos;
	const float Dt = WakeDtPending;
	WakeDtPending = 0.f;
	PendingWake = Async(EAsyncExecution::ThreadPool, [Grid, Shapes, Hulls, Centre, Dt]()
	{
		Grid->Follow(Centre);
		Grid->Step(Dt, Hulls);
		FWakeFrame Out;
		Out.N = Grid->Size();
		Out.Cell = Grid->CellSize();
		Out.Origin = Grid->Origin();
		const TArray<float>& H = Grid->Heights();
		const TArray<float>& F = Grid->Foam();
		Out.Pixels.SetNumUninitialized(Out.N * Out.N * 2);
		for (int32 I = 0; I < Out.N * Out.N; ++I)
		{
			Out.Pixels[2 * I] = H[I];
			Out.Pixels[2 * I + 1] = F[I];
		}
		return Out;
	});
	bWakePending = true;
}

void AWaterSurface::UpdateShoreMap()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsLoaded() || !WaterMaterial) return;
	if (bShorePending)
	{
		if (!PendingShore.IsReady()) return;
		const FShoreFrame Done = PendingShore.Get();
		bShorePending = false;
		if (!ShoreMap) ShoreMap = MakeFloatMap(kShoreRes, kShoreRes, PF_R32_FLOAT, false);
		UploadFloats(ShoreMap, Done.Depth, kShoreRes, kShoreRes, 1);
		WaterMaterial->SetTextureParameterValue(TEXT("ShoreMap"), ShoreMap);
		WaterMaterial->SetVectorParameterValue(TEXT("ShoreRect"), FLinearColor(float(Done.Origin.X), float(Done.Origin.Y), kShoreRes * kShoreCellM, 1.f));
		bShoreValid = true;
		ShoreOrigin = Done.Origin;
		ShoreLevel = Done.Level;
		return;
	}
	// Rebuilt when the boat is a quarter of the map from its centre, or the water has risen or fallen (the tide).
	const FLakeData* Lake = &GM->GetLake();
	const double Level = Lake->Terrain.GetLevelBelowPool();
	const float Half = 0.5f * kShoreRes * kShoreCellM;
	const FVector2D Centre = ShoreOrigin + FVector2D(Half, Half);
	if (bShoreValid && FMath::Abs(BoatPos.X - Centre.X) < 0.25f * Half * 2.f && FMath::Abs(BoatPos.Y - Centre.Y) < 0.25f * Half * 2.f
		&& FMath::Abs(Level - ShoreLevel) < 0.05)
	{
		return;
	}
	const FVector2D Origin(FMath::GridSnap(BoatPos.X - Half, 16.f), FMath::GridSnap(BoatPos.Y - Half, 16.f));
	PendingShore = Async(EAsyncExecution::ThreadPool, [Lake, Origin, Level]()
	{
		// Reads only data the game thread doesn't change while sailing (the tide moves the level, read once here).
		FShoreFrame Out;
		Out.Origin = Origin;
		Out.Level = Level;
		Out.Depth.SetNumUninitialized(kShoreRes * kShoreRes);
		ParallelFor(kShoreRes, [&](int32 R)
		{
			for (int32 C = 0; C < kShoreRes; ++C)
			{
				Out.Depth[R * kShoreRes + C] = float(Lake->Terrain.DepthAt(Origin.X + (R + 0.5) * kShoreCellM, Origin.Y + (C + 0.5) * kShoreCellM));
			}
		});
		// Docks, piers and breakwaters standing in the water: the waves lap against them too.
		for (const FObstacleSegment& S : Lake->Obstacles)
		{
			if (S.Bottom > 0.0) continue; // bridge decks overhead
			const FVector2D A(S.AX, S.AY), B(S.BX, S.BY);
			const FVector2D Lo(FMath::Min(A.X, B.X) - 2.0, FMath::Min(A.Y, B.Y) - 2.0), Hi(FMath::Max(A.X, B.X) + 2.0, FMath::Max(A.Y, B.Y) + 2.0);
			const int32 R0 = FMath::Max(0, FMath::FloorToInt((Lo.X - Origin.X) / kShoreCellM)), R1 = FMath::Min(kShoreRes - 1, FMath::CeilToInt((Hi.X - Origin.X) / kShoreCellM));
			const int32 C0 = FMath::Max(0, FMath::FloorToInt((Lo.Y - Origin.Y) / kShoreCellM)), C1 = FMath::Min(kShoreRes - 1, FMath::CeilToInt((Hi.Y - Origin.Y) / kShoreCellM));
			for (int32 R = R0; R <= R1; ++R)
			{
				for (int32 C = C0; C <= C1; ++C)
				{
					const FVector2D P(Origin.X + (R + 0.5) * kShoreCellM, Origin.Y + (C + 0.5) * kShoreCellM);
					const FVector2D AB = B - A;
					const double T = AB.SizeSquared() > 1e-6 ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / AB.SizeSquared(), 0.0, 1.0) : 0.0;
					const float Gap = float(FMath::Max(0.0, FVector2D::Distance(P, A + AB * T) - S.Radius));
					float& D = Out.Depth[R * kShoreRes + C];
					D = FMath::Min(D, 0.05f + 0.6f * Gap);
				}
			}
		}
		return Out;
	});
	bShorePending = true;
}

void AWaterSurface::UpdateSpray(float DeltaSeconds)
{
	const FWaveField* Waves = GetWaves();
	const FWindField* Wind = GetWind();
	if (!Waves || !DropletMesh) return;
	if (!Spray)
	{
		Spray = NewObject<UInstancedStaticMeshComponent>(this, TEXT("Spray"));
		Spray->SetupAttachment(RootComponent);
		Spray->SetStaticMesh(DropletMesh);
		if (SprayMaterial) Spray->SetMaterial(0, SprayMaterial);
		Spray->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Spray->SetCastShadow(false);
		Spray->SetUsingAbsoluteLocation(true);
		Spray->SetUsingAbsoluteRotation(true);
		Spray->RegisterComponent();
		TArray<FTransform> Hidden;
		Hidden.Init(FTransform(FQuat::Identity, FVector(0, 0, -1e6), FVector::ZeroVector), kMaxDroplets);
		Spray->AddInstances(Hidden, false, true);
	}
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	const double T = GetSimTime();
	const FVector Cam = UGameplayStatics::GetPlayerCameraManager(this, 0) ? UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraLocation() : GetActorLocation();
	const FVector2D CamM(Cam.X / CmPerMeter, Cam.Y / CmPerMeter);
	const Vec3 WindV = Wind ? Wind->VelocityAt(Vec3(CamM.X, CamM.Y, 2.0), T) : Vec3();
	const FVector WindAt2m(WindV.X, WindV.Y, 0.0);
	auto Emit = [&](const FVector& P, const FVector& V, float Size)
	{
		if (Droplets.Num() >= kMaxDroplets) return;
		FDroplet D;
		D.P = P;
		D.V = V;
		D.Life = SprayRng.FRandRange(0.6f, 1.6f);
		D.Size = Size;
		Droplets.Add(D);
	};

	// Bows slamming into the waves: the closing speed between the bow and the water surface throws up a sheet of spray
	// to each side, carried forward with the boat.
	for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
	{
		if (It->bGhost) continue;
		const FBoatModel& M = It->GetBoatModel();
		const FHullShape& Hull = M.GetConfig().Hulls[0];
		const Vec3 B = M.BodyToWorld(Vec3(0.85 * Hull.BowX, 0.0, 0.0));
		const FVector Bow(B.X, B.Y, B.Z);
		if (FVector2D::Distance(FVector2D(Bow.X, Bow.Y), CamM) > 120.0) { LastBow.Remove(*It); continue; }
		FVector* Last = LastBow.Find(*It);
		const FVector BowV = Last && Dt > 0.f ? (Bow - *Last) / Dt : FVector::ZeroVector;
		LastBow.Add(*It, Bow);
		if (!Last) continue;
		double H, Vz, Sx, Sy;
		Waves->Sample(Bow.X, Bow.Y, T, H, Vz, Sx, Sy);
		const double Closing = Vz - BowV.Z; // water rising past the bow, or the bow plunging into it
		const double Speed = FVector2D(BowV.X, BowV.Y).Size();
		if (Bow.Z > H + 0.15 || Closing < 0.45 || Speed < 1.5) continue;
		const int32 Count = FMath::Clamp(FMath::RoundToInt(Dt * 900.f * float(Closing - 0.45) * FMath::Min(float(Speed) / 3.f, 1.5f)), 0, 40);
		const FVector Fwd = FVector(BowV.X, BowV.Y, 0.0).GetSafeNormal();
		const FVector Side(-Fwd.Y, Fwd.X, 0.0);
		for (int32 I = 0; I < Count; ++I)
		{
			const float S = SprayRng.FRand() < 0.5f ? -1.f : 1.f;
			const FVector P = FVector(Bow.X, Bow.Y, H) + Side * S * SprayRng.FRandRange(0.2f, 0.6f) - Fwd * SprayRng.FRandRange(0.f, 0.8f);
			const FVector V = FVector(BowV.X, BowV.Y, 0.0) * 0.6f + Side * S * SprayRng.FRandRange(0.8f, 2.6f)
				+ FVector(0, 0, SprayRng.FRandRange(0.8f, 2.2f) * float(FMath::Min(Closing, 2.5)));
			Emit(P, V, SprayRng.FRandRange(0.04f, 0.12f)); // clumps of droplets (sizes in m)
		}
	}

	// Breaking crests in a breeze (where the drawn waves fold, as the whitecaps): the wind tears spray off them.
	const double WindMs = FVector2D(WindAt2m.X, WindAt2m.Y).Size();
	if (WindMs > 6.5 && FramePrev)
	{
		const FWaveComponent* C = Waves->GetComponents();
		for (int32 K = 0; K < 24; ++K)
		{
			const float R = SprayRng.FRandRange(4.f, 60.f), A = SprayRng.FRandRange(0.f, 2.f * UE_PI);
			const double X = CamM.X + R * FMath::Cos(A), Y = CamM.Y + R * FMath::Sin(A);
			double Jxx = 1.0, Jyy = 1.0, Jxy = 0.0;
			for (int32 I = 0; I < LongComponents; ++I)
			{
				const double Kk = FMath::Sqrt(C[I].Kx * C[I].Kx + C[I].Ky * C[I].Ky);
				const double Q = Choppiness * C[I].Amplitude * FMath::Sin(C[I].Kx * X + C[I].Ky * Y - C[I].Omega * T + C[I].Phase) / Kk;
				Jxx -= Q * C[I].Kx * C[I].Kx;
				Jyy -= Q * C[I].Ky * C[I].Ky;
				Jxy -= Q * C[I].Kx * C[I].Ky;
			}
			double Hd, Dx, Dy, Jd;
			FWaveDetail::Sample(FramePrev->Chop, X, Y, Hd, Dx, Dy, Jd);
			if ((Jxx * Jyy - Jxy * Jxy) * Jd > 0.45) continue;
			const double H = Waves->Height(X, Y, T) + Hd;
			const int32 Count = FMath::RoundToInt(FMath::Clamp(float(WindMs - 6.5) * 2.f, 2.f, 14.f));
			for (int32 I = 0; I < Count; ++I)
			{
				const FVector P(X + SprayRng.FRandRange(-0.4f, 0.4f), Y + SprayRng.FRandRange(-0.4f, 0.4f), H);
				const FVector V = WindAt2m * SprayRng.FRandRange(0.3f, 0.7f) + FVector(0, 0, SprayRng.FRandRange(0.5f, 1.6f));
				Emit(P, V, SprayRng.FRandRange(0.03f, 0.08f));
			}
		}
	}

	// Spray reaching the camera's glass (lens drops on High, SailingEnvironment).
	LensSpray = FMath::Max(0.f, LensSpray - 0.35f * Dt);
	const FVector CamM3(Cam.X / CmPerMeter, Cam.Y / CmPerMeter, (Cam.Z - GetActorLocation().Z) / CmPerMeter);
	for (const FDroplet& D : Droplets)
	{
		if (D.Age < 0.6f && FVector::DistSquared(D.P, CamM3) < 4.f) { LensSpray = 1.f; break; }
	}
	// Fly: gravity, the air dragging them toward the wind's speed; gone when they fall back into the water.
	const FVector G(0, 0, -9.81);
	for (int32 I = Droplets.Num() - 1; I >= 0; --I)
	{
		FDroplet& D = Droplets[I];
		D.V += (G + (WindAt2m - D.V) * 1.2f) * Dt;
		D.P += D.V * Dt;
		D.Age += Dt;
		if (D.Age > D.Life || D.P.Z < Waves->Height(D.P.X, D.P.Y, T) - 0.05) Droplets.RemoveAtSwap(I);
	}
	TArray<FTransform> Xf;
	Xf.SetNumUninitialized(kMaxDroplets);
	const double Z0 = GetActorLocation().Z;
	for (int32 I = 0; I < kMaxDroplets; ++I)
	{
		if (I < Droplets.Num())
		{
			const FDroplet& D = Droplets[I];
			const float Fade = 1.f - FMath::Square(D.Age / D.Life);
			Xf[I] = FTransform(FQuat::Identity, FVector(D.P.X * CmPerMeter, D.P.Y * CmPerMeter, D.P.Z * CmPerMeter + Z0), FVector(D.Size * Fade));
		}
		else
		{
			Xf[I] = FTransform(FQuat::Identity, FVector(0, 0, -1e6), FVector::ZeroVector);
		}
	}
	Spray->BatchUpdateInstancesTransforms(0, Xf, true, true, true);
}

void AWaterSurface::WaitForWorkers()
{
	if (bShorePending) { PendingShore.Wait(); bShorePending = false; }
	if (bWakePending) { PendingWake.Wait(); bWakePending = false; }
	if (bFramePending) { PendingFrame.Wait(); bFramePending = false; }
	if (bUploadPending) { PendingUpload.Wait(); bUploadPending = false; }
}

void AWaterSurface::EndPlay(const EEndPlayReason::Type Reason)
{
	WaitForWorkers();
	Super::EndPlay(Reason);
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
		// M_Water's tint; M_WaterV4 colours the Gulf by its water body (WaterBodyFor).
		WaterMaterial->SetTextureParameterValue(TEXT("OceanA"), OceanMaps[0]);
		WaterMaterial->SetTextureParameterValue(TEXT("OceanB"), OceanMaps[1]);
		// Open Gulf water: bluer and clearer than the bay.
		WaterMaterial->SetVectorParameterValue(TEXT("OceanColor"), FLinearColor(0.012f, 0.05f, 0.06f)); // W2: blended by the swell mask
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

void AWaterSurface::UpdateSeaMap()
{
	// W3: each long wave train scaled by its own direction's fetch and the depth where it is (SeaState.h). The atlas is
	// rebuilt only when the game mode gave the field a new map (the mean wind changed); between maps the shader reads the
	// same texels as FSeaMap::Sample. The packing runs on a worker; the field switches to the new map at once and the
	// water a frame or two later.
	const FWaveField* Waves = GetWaves();
	if (bSeaPending && PendingSea.IsReady())
	{
		bSeaPending = false;
		const TSharedPtr<FSeaPixels, ESPMode::ThreadSafe> P = PendingSea.Get();
		if (!SeaAtlas || SeaAtlas->GetSizeX() != P->Width || SeaAtlas->GetSizeY() != P->Rows)
		{
			SeaAtlas = MakeFloatMap(P->Width, P->Rows, PF_FloatRGBA, false);
		}
		const int32 Bytes = P->Pixels.Num() * int32(sizeof(FFloat16));
		uint8* Copy = new uint8[Bytes];
		FMemory::Memcpy(Copy, P->Pixels.GetData(), Bytes);
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, P->Width, P->Rows);
		SeaAtlas->UpdateTextureRegions(0, 1, Region, P->Width * 4 * sizeof(FFloat16), 4 * sizeof(FFloat16), Copy,
			[](uint8* Data, const FUpdateTextureRegion2D* Rg)
			{
				delete[] Data;
				delete Rg;
			});
		WaterMaterial->SetTextureParameterValue(TEXT("SeaMap"), SeaAtlas);
		WaterMaterial->SetVectorParameterValue(TEXT("SeaRect"), FLinearColor(float(P->OriginX), float(P->OriginY), float(P->Cell), float(P->Rows)));
		WaterMaterial->SetVectorParameterValue(TEXT("SeaParams"), FLinearColor(float(P->Cols), float(P->Width), float(P->Rows), 1.f));
	}
	const uint32 Generation = Waves ? Waves->GetSeaMapGeneration() : 0;
	if (Generation == UploadedSeaGeneration || bSeaPending)
	{
		return;
	}
	UploadedSeaGeneration = Generation;
	std::shared_ptr<const FSeaMap> Map = Waves ? Waves->GetSeaMapShared() : nullptr;
	if (!Map || !Map->IsValid())
	{
		WaterMaterial->SetVectorParameterValue(TEXT("SeaParams"), FLinearColor(1.f, 7.f, 1.f, 0.f));
		return;
	}
	bSeaPending = true;
	PendingSea = Async(EAsyncExecution::ThreadPool, [Map, Generation]()
	{
		// Texel (tile t, column c, row r) holds channels 4t..4t+3 of cell (r, c); the short scale is tile 6's R.
		constexpr int32 Tiles = 7;
		TSharedPtr<FSeaPixels, ESPMode::ThreadSafe> P = MakeShared<FSeaPixels, ESPMode::ThreadSafe>();
		P->Rows = Map->GetRows();
		P->Cols = Map->GetCols();
		P->Width = Tiles * P->Cols;
		P->OriginX = Map->GetOriginX();
		P->OriginY = Map->GetOriginY();
		P->Cell = Map->GetCell();
		P->Generation = Generation;
		P->Pixels.SetNumUninitialized(P->Width * P->Rows * 4);
		for (int32 R = 0; R < P->Rows; ++R)
		{
			for (int32 C = 0; C < P->Cols; ++C)
			{
				const float* Cell = Map->CellAt(R, C);
				for (int32 T = 0; T < Tiles; ++T)
				{
					FFloat16* Out = P->Pixels.GetData() + (size_t(R) * P->Width + size_t(T) * P->Cols + C) * 4;
					for (int32 K = 0; K < 4; ++K)
					{
						const int32 Channel = 4 * T + K;
						Out[K] = FFloat16(Channel < kSeaChannels ? Cell[Channel] : 0.f);
					}
				}
			}
		}
		return P;
	});
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
	UpdateSeaMap();
	for (int32 I = 0; I < kWaveComponents / 4; ++I)
	{
		WaterMaterial->SetVectorParameterValue(*FString::Printf(TEXT("WaveAmp%02d"), I),
			FLinearColor(C[4 * I].Amplitude, C[4 * I + 1].Amplitude, C[4 * I + 2].Amplitude, C[4 * I + 3].Amplitude));
	}
	WaterMaterial->SetScalarParameterValue(TEXT("WaveTime"), float(GetSimTime()));
	// W2: the near and far wind maps (centre, size; both wrap-around, sampled at world position / size) and the
	// windrows' slow downwind direction.
	WaterMaterial->SetVectorParameterValue(TEXT("GustRect"), FLinearColor(NearWind.Center.X, NearWind.Center.Y, NearWind.SizeM, 1.f));
	WaterMaterial->SetVectorParameterValue(TEXT("WindFarRect"), FLinearColor(FarWind.Center.X, FarWind.Center.Y, FarWind.SizeM, 1.f));
	WaterMaterial->SetVectorParameterValue(TEXT("WindSlow"), FLinearColor(WindrowDir.X, WindrowDir.Y, 0.f, 0.f));
	for (const TPair<TObjectPtr<UMaterialInterface>, TObjectPtr<UMaterialInstanceDynamic>>& Tree : TreeWindMids)
	{
		if (Tree.Value) Tree.Value->SetVectorParameterValue(TEXT("WindFarRect"), FLinearColor(FarWind.Center.X, FarWind.Center.Y, FarWind.SizeM, 1.f));
	}
	static SailingArgs::FCachedFlag PolarizedArg(TEXT("SailingPolarized"));
	const bool bPolarizedArg = PolarizedArg.Get();
	WaterMaterial->SetScalarParameterValue(TEXT("Polarized"), (GPolarized != 0 || bPolarizedArg) ? 1.f : 0.f);
	WaterMaterial->SetVectorParameterValue(TEXT("WakeRect"), FLinearColor(WakeCenter.X, WakeCenter.Y, kWakeSizeM, 0.f));

	if (const FWindField* Wind = GetWind())
	{
		const FWindParams& P = Wind->GetParams();
		const float From = FMath::DegreesToRadians(P.FromDegrees);
		// W0: the sea's mean wind (what the drawn waves were grown for), not the wind at the boat: cat's paws darken and
		// whitecaps gather against it, so a puff at the boat no longer turns the whole lake to a lull. W is the water
		// body's whitecap scale.
		const float MeanMs = float(Waves->GetParams().WindSpeedKnots * kKnot);
		WaterMaterial->SetVectorParameterValue(TEXT("WindParams"), FLinearColor(-FMath::Cos(From), -FMath::Sin(From), MeanMs,
			WhitecapScaleFor(USailingSettings::Get()->World)));
	}
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		WaterMaterial->SetScalarParameterValue(TEXT("Rain"), float(GM->GetWeatherState().Rain));
	}
}

void AWaterSurface::UpdateGustMap()
{
	const FWindField* Wind = GetWind();
	if (!Wind || !GustMap || !WindFarMap)
	{
		return;
	}
	const double Start = FPlatformTime::Seconds();
	const double T = GetSimTime();
	UpdateWindLevel(NearWind, true, T);
	UpdateWindLevel(FarWind, false, T);
	GustCenter = NearWind.Center;

	// The windrows' direction: the readable wind at the boat, smoothed over minutes (they realign slowly after a shift).
	double From = 0.0, Factor = 1.0;
	Wind->ReadableAt(BoatPos.X, BoatPos.Y, T, From, Factor);
	const FVector2D Down(-FMath::Cos(From), -FMath::Sin(From));
	if (!bWindrowDirSet)
	{
		WindrowDir = Down;
		bWindrowDirSet = true;
	}
	else
	{
		const double A = 1.0 - FMath::Exp(-FMath::Max(T - LastWindrowTime, 0.0) / kWindrowSeconds);
		const FVector2D Blend = WindrowDir + (Down - WindrowDir) * A;
		WindrowDir = Blend.IsNearlyZero() ? Down : Blend.GetSafeNormal();
	}
	LastWindrowTime = T;
	WindMapCpuSeconds += FPlatformTime::Seconds() - Start;

	// -SailingDumpGust: write the near map's roughness around the boat once as a PGM image, to check what the water shows.
	static SailingArgs::FOnce Dumped;
	if (!Dumped.Taken() && T > 4.0 && FParse::Param(FCommandLine::Get(), TEXT("SailingDumpGust")))
	{
		Dumped.Take();
		const int32 Res = NearWind.Res;
		const double Texel = NearWind.SizeM / Res;
		const int32 I0 = FMath::RoundToInt(NearWind.Center.X / Texel) - Res / 2, J0 = FMath::RoundToInt(NearWind.Center.Y / Texel) - Res / 2;
		FString Pgm = FString::Printf(TEXT("P2\n%d %d\n255\n"), Res, Res);
		for (int32 R = Res - 1; R >= 0; --R)
		{
			for (int32 C = 0; C < Res; ++C)
			{
				const int32 Slot = (((J0 + R) % Res + Res) % Res) * Res + ((I0 + C) % Res + Res) % Res;
				Pgm += FString::Printf(TEXT("%d "), FMath::Clamp(FMath::RoundToInt(NearWind.Texels[Slot].Rough / 20.f * 255.f), 0, 255));
			}
			Pgm += TEXT("\n");
		}
		FFileHelper::SaveStringToFile(Pgm, *(FPaths::ProjectSavedDir() / TEXT("Bench/gust.pgm")));
	}
}

double AWaterSurface::WindMapCpuSeconds = 0.0;

void AWaterSurface::BindTreeWind()
{
	if (!WindFarMap) return;
	for (TActorIterator<ALakeTerrainActor> It(GetWorld()); It; ++It)
	{
		TArray<UInstancedStaticMeshComponent*> Comps;
		It->GetComponents(Comps);
		for (UInstancedStaticMeshComponent* Comp : Comps)
		{
			for (int32 I = 0; I < Comp->GetNumMaterials(); ++I)
			{
				UMaterialInterface* M = Comp->GetMaterial(I);
				if (!M || Cast<UMaterialInstanceDynamic>(M)) continue;
				const UMaterial* Base = M->GetBaseMaterial();
				if (!Base || !Base->GetName().StartsWith(TEXT("M_Tree"))) continue;
				TObjectPtr<UMaterialInstanceDynamic>& Mid = TreeWindMids.FindOrAdd(M);
				if (!Mid)
				{
					Mid = UMaterialInstanceDynamic::Create(M, this);
					Mid->SetTextureParameterValue(TEXT("WindFar"), WindFarMap);
					Mid->SetVectorParameterValue(TEXT("WindFarRect"), FLinearColor(FarWind.Center.X, FarWind.Center.Y, FarWind.SizeM, 1.f));
					UE_LOG(LogSailing, Display, TEXT("Water: trees read the local wind (%s)"), *M->GetName());
				}
				Comp->SetMaterial(I, Mid);
			}
		}
	}
}

void AWaterSurface::UpdateWindLevel(FWindLevel& Level, bool bNear, double T)
{
	const FWindField* Wind = GetWind();
	const int32 Res = Level.Res;
	const double Texel = Level.SizeM / Res;
	const FVector2D Center(FMath::GridSnap(BoatPos.X, Texel), FMath::GridSnap(BoatPos.Y, Texel));
	// A jump of more than a quarter of the map (the start, a teleport) refreshes it all at once; otherwise one strip.
	const bool bAll = !Level.bStarted || FVector2D::Distance(Center, Level.Center) > 0.25 * Level.SizeM;
	Level.bStarted = true;
	Level.Center = Center;
	// World index of the window's first texel along X (u) and Y (v): the window is Res texels centred on the boat.
	const int32 I0 = FMath::RoundToInt(Center.X / Texel) - Res / 2, J0 = FMath::RoundToInt(Center.Y / Texel) - Res / 2;
	const int32 Rows = Res / Level.Strips;
	const int32 RowStart = bAll ? 0 : Level.NextStrip * Rows;
	const int32 RowCount = bAll ? Res : Rows;
	Level.NextStrip = (Level.NextStrip + 1) % Level.Strips;
	ParallelFor(RowCount, [&](int32 K)
	{
		const int32 IY = J0 + RowStart + K;
		const int32 SlotY = (IY % Res + Res) % Res;
		for (int32 C = 0; C < Res; ++C)
		{
			const int32 IX = I0 + C;
			const int32 SlotX = (IX % Res + Res) % Res;
			const double WX = (IX + 0.5) * Texel, WY = (IY + 0.5) * Texel;
			double Speed, DX, DY;
			if (bNear)
			{
				// The full wind at 10 m: puffs, cells, fine turbulence, shifts, lee, the gust front.
				const Vec3 V = Wind->VelocityAt(Vec3(WX, WY, 10.0), T);
				Speed = FMath::Sqrt(V.X * V.X + V.Y * V.Y);
				DX = Speed > 1e-3 ? V.X / Speed : 1.0;
				DY = Speed > 1e-3 ? V.Y / Speed : 0.0;
			}
			else
			{
				// Far off only what reads at that range: the puffs and slow shifts, the lee, the front's outflow.
				double From = 0.0, Factor = 1.0;
				Wind->ReadableAt(WX, WY, T, From, Factor);
				Speed = Wind->MeanSurfaceRoughnessAt(WX, WY, T) * 8.0 * Factor;
				DX = -FMath::Cos(From);
				DY = -FMath::Sin(From);
			}
			FWindTexel& X = Level.Texels[SlotY * Res + SlotX];
			if (X.IX != IX || X.IY != IY)
			{
				// Newly in view: it starts settled.
				X.IX = IX;
				X.IY = IY;
				X.Rough = float(Speed);
				X.Slow = float(Speed);
			}
			else
			{
				const double Dt = FMath::Max(T - X.T, 0.0);
				const double Tau = Speed > X.Rough ? kRiseSeconds : kFallSeconds;
				X.Rough += float((Speed - X.Rough) * (1.0 - FMath::Exp(-Dt / Tau)));
				X.Slow += float((Speed - X.Slow) * (1.0 - FMath::Exp(-Dt / kSlowSeconds)));
			}
			X.T = T;
			X.DirX = float(DX);
			X.DirY = float(DY);
			// BGRA: R the roughness the water shows (speed / 20 m/s, so 2.5 x it is the old speed / 8 scale), G and B the
			// local downwind direction (X, Y), A (linear in an sRGB texture) the slow speed / 20 m/s.
			uint8* Px = &Level.Pixels[(SlotY * Res + SlotX) * 4];
			Px[0] = EncodeSrgb(0.5f + 0.5f * X.DirY);
			Px[1] = EncodeSrgb(0.5f + 0.5f * X.DirX);
			Px[2] = EncodeSrgb(FMath::Clamp(X.Rough / 20.f, 0.f, 1.f));
			Px[3] = uint8(FMath::Clamp(FMath::RoundToInt(X.Slow / 20.f * 255.f), 0, 255));
		}
	});
	Upload(bNear ? GustMap.Get() : WindFarMap.Get(), Level.Pixels, Res);
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
