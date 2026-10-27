#include "WaterSurface.h"
#include "SailingFrame.h"
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
#include "CrewPose.h"
#include "SailingSettings.h"
#include "VisualPipeline.h"
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
	constexpr float kDetailFadeM = 300.f;
	// docs/near-water/: the capillary wavelets (1 cm texels) are drawn in full to this far and faded out by the next: a pixel
	// there covers a centimetre or so at 1440p (and the mips' slope variance takes over before it).
	constexpr float kCapillaryNearM = 12.f;
	constexpr float kCapillaryFarM = 24.f;       // distance they fade over (past it their slopes become roughness)
	// docs/spray/: the pool of spray quads on High (drops, sheets and mist share it).
	constexpr int32 kMaxDroplets = 1200;
	// Graphics G8 Ultra showcase: two and a half times the bow spray on Ultra (the 4090 has the room; still CPU droplets in
	// the same ISM, so High's look and cost don't move).
	int32 MaxDroplets() { return USailingSettings::Get()->Quality == ESailingQuality::Ultra ? 3000 : kMaxDroplets; }
	// docs/spray/: what one spray instance is (FDroplet::Kind).
	enum class ESprayKind : uint8 { Drops, Sheet, Mist };
	constexpr int32 kShoreRes = 512;            // shore map: 512 m around the boat at 1 m
	constexpr float kShoreCellM = 1.f;

	/** Water bodies (Single Layer Water: scattering albedo and extinction per metre, red/green/blue). */
	struct FWaterBody { FLinearColor Albedo, Extinction; };
	FWaterBody WaterBodyFor(int32 World)
	{
		switch (World)
		{
		// Galveston Bay: shallow, silty, grey-green; about 0.6 m of Secchi depth. The streamed Texas coast (4) is the bay's
		// water, with the Gulf's where the swell mask lets the open sea in (WaterAlbedoSea).
		case 1:
		case 4: return { FLinearColor(0.15f, 0.20f, 0.14f), FLinearColor(2.3f, 1.8f, 2.4f) };
		// The Gulf off Galveston: green, a few metres of visibility (river silt and plankton); red goes first. Graphics G6:
		// greener and less saturated than the V4 teal (0.04, 0.20, 0.21), which read as tropical under an overcast.
		case 2: return { FLinearColor(0.08f, 0.16f, 0.13f), FLinearColor(0.62f, 0.32f, 0.42f) };
		// world-marseille: the Mediterranean off Marseille, clear blue (Secchi depths of 20 m and more offshore): nearly pure
		// water's absorption (red gone in a few metres, blue last), little scattering, and that blue.
		case 3: return { FLinearColor(0.02f, 0.09f, 0.16f), FLinearColor(0.40f, 0.075f, 0.045f) };
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

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Water(TEXT("/Game/Materials/M_Water.M_Water"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> WaterV4(TEXT("/Game/Materials/M_WaterV4.M_WaterV4"));
	ClassicMaterial = Water.Object;
	DetailedMaterial = WaterV4.Object;
	// Spray: camera-facing quads (the engine's 1 m plane), stretched along their motion (UpdateSpray).
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Quad(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SprayMat(TEXT("/Game/Materials/M_Spray.M_Spray"));
	DropletMesh = Quad.Object;
	SprayMaterial = SprayMat.Object;
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> FarCapMat(TEXT("/Game/Materials/M_FarCap.M_FarCap"));
	FarCapMaterial = FarCapMat.Object;

	// The far water past the rings, out to the horizon: built with the rings (BuildRings).
	FarPlane = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("FarPlane"));
	FarPlane->SetupAttachment(RootComponent);
	FarPlane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	FarPlane->SetCastShadow(false);
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

FWaveDetail::FCascadeSpec AWaterSurface::DrawnChop() const
{
	FWaveDetail::FCascadeSpec S = FWaveDetail::ChopCascade();
	if (bUltraDetail) { S.N *= 2; S.Tile *= 2.0; }
	return S;
}

FWaveDetail::FCascadeSpec AWaterSurface::DrawnCapillary() const
{
	return FWaveDetail::CapillaryCascade();
}

FWaveDetail::FCascadeSpec AWaterSurface::DrawnRipple() const
{
	FWaveDetail::FCascadeSpec S = FWaveDetail::RippleCascade();
	if (bUltraDetail) { S.N *= 2; S.Tile *= 2.0; }
	return S;
}

void AWaterSurface::SetQualityTier(int32 InTier)
{
	const int32 Clamped = FMath::Clamp(InTier, 0, 2);
	const bool bUltra = USailingSettings::Get()->Quality == ESailingQuality::Ultra && FParse::Param(SailingArgs::Dev(), TEXT("SailingUltraDetail")); // as CreateWaterMaterial sets bUltraDetail
	if (Clamped == Tier && bUltra == bUltraDetail && (WaterMaterial || !HasActorBegunPlay())) return;
	Tier = Clamped;
	if (HasActorBegunPlay())
	{
		CreateWaterMaterial();
	}
}

void AWaterSurface::CreateWaterMaterial()
{
	// -SailingClassicWater: M_Water on every tier (measuring the V4 water's cost).
	bV4 = Tier >= 1 && DetailedMaterial != nullptr && !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicWater"));
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
	FParse::Value(SailingArgs::Dev(), TEXT("SailingDebugGust="), DebugGust);
	WaterMaterial->SetScalarParameterValue(TEXT("DebugGust"), DebugGust);
	// W8: -SailingDebugFoam: M_WaterV4 draws the whitecaps alone (white on black) for counting on a screenshot.
	// (=2 the crests alone, =3 where the fold is under the threshold; -SailingDebugCaps logs the solved thresholds.)
	float DebugFoam = FParse::Param(SailingArgs::Dev(), TEXT("SailingDebugFoam")) ? 1.f : 0.f;
	FParse::Value(SailingArgs::Dev(), TEXT("SailingDebugFoam="), DebugFoam);
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
		bUltraDetail = USailingSettings::Get()->Quality == ESailingQuality::Ultra && FParse::Param(SailingArgs::Dev(), TEXT("SailingUltraDetail"));
		const FWaveDetail::FCascadeSpec Chop = DrawnChop(), Ripple = DrawnRipple();
		const FWaveDetail::FCascadeSpec Capillary = DrawnCapillary();
		if (!DetailAMap || DetailAMap->GetSizeX() != Chop.N || RippleBMap->GetSizeX() != Ripple.N || !CapillaryBMap)
		{
			DetailAMap = MakeFloatMapMips(Chop.N);
			DetailBMap = MakeFloatMapMips(Chop.N);
			DetailCMap = MakeFloatMapMips(Chop.N);
			RippleBMap = MakeFloatMapMips(Ripple.N);
			CapillaryBMap = MakeFloatMapMips(Capillary.N);
		}
		// The wake grid: 38 m around the boat on Medium (128 cells of 0.3 m), 64 m on High (256 of 0.25 m).
		// Graphics G8 Ultra showcase: 128 m (512 of 0.25 m), so a wake trails four boat lengths further before the grid's edge.
		const int32 WakeN = bUltraDetail ? 512 : Tier >= 2 ? 256 : 128;
		if (Wake.Size() != WakeN)
		{
			WaitForWorkers();
			Wake.Init(WakeN, Tier >= 2 ? 0.25f : 0.3f);
			WakeGridMap = MakeFloatMap(WakeN, WakeN, PF_A32B32G32R32F, false);
		}
		WaterMaterial->SetTextureParameterValue(TEXT("DetailA"), DetailAMap);
		WaterMaterial->SetTextureParameterValue(TEXT("DetailB"), DetailBMap);
		WaterMaterial->SetTextureParameterValue(TEXT("DetailC"), DetailCMap);
		WaterMaterial->SetTextureParameterValue(TEXT("RippleB"), RippleBMap);
		WaterMaterial->SetTextureParameterValue(TEXT("CapillaryB"), CapillaryBMap);
		// docs/near-water/: the capillaries' tile and the distances they are drawn to (High and Ultra).
		WaterMaterial->SetVectorParameterValue(TEXT("CapillaryP"), FLinearColor(float(Capillary.Tile), kCapillaryNearM, kCapillaryFarM, Tier >= 2 ? 1.f : 0.f));
		WaterMaterial->SetTextureParameterValue(TEXT("WakeGrid"), WakeGridMap);
		if (ShoreMap && bShoreValid)
		{
			WaterMaterial->SetTextureParameterValue(TEXT("ShoreMap"), ShoreMap);
			WaterMaterial->SetVectorParameterValue(TEXT("ShoreRect"), FLinearColor(float(ShoreOrigin.X), float(ShoreOrigin.Y), kShoreRes * kShoreCellM, 1.f));
		}
		WaterMaterial->SetVectorParameterValue(TEXT("DetailParams"), FLinearColor(float(Chop.Tile), float(Ripple.Tile), kDetailFadeM, Tier >= 2 ? 1.f : 0.f));
		WaterMaterial->SetScalarParameterValue(TEXT("Choppiness"), Choppiness);
		WaterMaterial->SetScalarParameterValue(TEXT("SplitOmega"), float(2.0 * UE_DOUBLE_PI * SplitHz));
		FWaterBody Body = WaterBodyFor(USailingSettings::Get()->World);
		// Measuring (docs/grazing-reflection/): -SailingWaterAlbedo=<r>,<g>,<b> and -SailingWaterExtinction=<r>,<g>,<b> (1/m)
		// replace the body's (albedo 0 and extinction 100 leave the surface's reflection alone).
		for (int32 K = 0; K < 2; ++K)
		{
			FString Arg;
			if (!FParse::Value(SailingArgs::Dev(), K == 0 ? TEXT("SailingWaterAlbedo=") : TEXT("SailingWaterExtinction="), Arg, false)) continue;
			TArray<FString> Parts;
			Arg.ParseIntoArray(Parts, TEXT(","));
			if (Parts.Num() != 3) continue;
			(K == 0 ? Body.Albedo : Body.Extinction) = FLinearColor(FCString::Atof(*Parts[0]), FCString::Atof(*Parts[1]), FCString::Atof(*Parts[2]));
		}
		// docs/lake-body/: -SailingNoBodyTransmission draws the body's light without the surface's transmission (as before).
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingNoBodyTransmission"))) WaterMaterial->SetScalarParameterValue(TEXT("BodyTransmission"), 0.f);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterAlbedo"), Body.Albedo);
		WaterMaterial->SetVectorParameterValue(TEXT("WaterExtinction"), Body.Extinction);
		// W2 (the gulf-swell handoff): where the swell mask lets the open sea in, the Gulf's body (the material blends by
		// the mask; in the Gulf world both are the Gulf's, on the lake there is no mask).
		const FWaterBody Sea = WaterBodyFor(USailingSettings::Get()->World == 3 ? 3 : 2);
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
	case 4: return 0.7f; // the streamed Texas coast: the bay's, and the Gulf's beyond the jetties (WhitecapScaleHere)
	case 2: return 1.f;  // the Gulf: sea water, Monahan's law as measured
	case 3: return 1.f;  // the Mediterranean: sea water
	default: return 0.4f; // fresh water: bubbles coalesce and burst sooner, so caps are fewer and fade faster
	}
}

float AWaterSurface::WhitecapScaleHere() const
{
	// World streaming: on the Texas coast the water is the bay's inside and the Gulf's outside, so the caps scale with
	// the open sea's share where the boat is (the ocean mask: 0 in the bay, 1 offshore).
	const int32 World = USailingSettings::Get()->World;
	if (World != 4) return WhitecapScaleFor(World);
	const FWaveField* W = GetWaves();
	const FOcean* O = W ? W->GetOcean() : nullptr;
	const float Open = O ? float(FMath::Clamp(O->MaskAt(BoatPos.X, BoatPos.Y), 0.0, 1.0)) : 0.f;
	return FMath::Lerp(WhitecapScaleFor(1), WhitecapScaleFor(2), Open);
}

float AWaterSurface::DrawnFoldScaleAt(float MeanKnots)
{
	return FMath::Clamp(0.94f - 0.0075f * (MeanKnots - 12.f), 0.85f, 0.94f);
}

float AWaterSurface::BodyTransmission(float CosView)
{
	const float C = FMath::Clamp(CosView, 0.f, 1.f);
	const float St = FMath::Sqrt(FMath::Max(1.f - C * C, 0.f)) / 1.333f, Ct = FMath::Sqrt(FMath::Max(1.f - St * St, 0.f));
	const float Rs = (C - 1.333f * Ct) / FMath::Max(C + 1.333f * Ct, 1e-5f), Rp = (1.333f * C - Ct) / FMath::Max(1.333f * C + Ct, 1e-5f);
	return FMath::Clamp((1.f - 0.5f * (Rs * Rs + Rp * Rp)) / 0.98f, 0.f, 1.f);
}

float AWaterSurface::WhitecapOnset(float MeanKnots)
{
	constexpr float OnsetMs = 3.7f, FullMs = 12.f * float(kKnot);
	const float U = FMath::Clamp((MeanKnots * float(kKnot) - OnsetMs) / (FullMs - OnsetMs), 0.f, 1.f);
	return U * U * U;
}

double AWaterSurface::FarCapCover(double WindMs, double Scale, double Onset)
{
	// As the renderer's cap target (UpdateDetail: CapTarget), for the local wind: the caps gather in puffs (M_WaterV4's
	// capGain, (U_local / U_mean)^3.41).
	return 3.84e-6 * FMath::Pow(FMath::Max(WindMs, 0.0), 3.41) * Scale * Onset;
}

void AWaterSurface::FarCapTilePlan(double Cover, double TileArea, int32& OutSlots, float& OutProb, double CapArea)
{
	// The caps live at once: the tile's foam over one cap's, over the mean of a life (M_FarCap: 1.6 sin, clamped at 1).
	const double Live = Cover * TileArea / (CapArea * 0.7937);
	OutSlots = Live < 0.05 ? 0 : FMath::Min(FMath::CeilToInt(Live * 1.3) + 1, 6000);
	OutProb = OutSlots > 0 ? float(FMath::Min(Live / OutSlots, 1.0)) : 0.f;
}

float AWaterSurface::FarCapSpriteWeight(double DistM, double HeightM)
{
	// (Keep in step with M_WaterV4's FCS_W and M_FarCap.)
	const double D = FMath::Max(DistM, 1.0);
	return float(FMath::SmoothStep(300.0, 400.0, D) * (1.0 - FMath::SmoothStep(1100.0, 1250.0, D)) * (1.0 - FMath::SmoothStep(0.05, 0.14, HeightM / D)));
}

float AWaterSurface::ShoalFoldScale(float MeanKnots)
{
	return FMath::SmoothStep(3.7f, 8.2f, MeanKnots * float(kKnot));
}

float AWaterSurface::FoamThresholdAt(float MeanKnots)
{
	// Under 10 kn the crests stop breaking (Beaufort 2-3): the threshold falls 0.03 a knot instead of rising on.
	// Whitecap mask (docs/water-8/capshape-mac): the cap blur shrinks with the wind (FWaveDetail::CapBlurMeters), and the
	// finer blur folds deeper: 0.042 lower at 10 kn (3.9x Monahan at the old threshold), easing out by 16 kn.
	const float K = FMath::Clamp(MeanKnots, 4.f, 40.f);
	return 0.63f + 0.083f * FMath::Exp(-(FMath::Max(K, 10.f) - 10.f) / 5.f) - 0.042f * FMath::Exp(-(FMath::Max(K, 10.f) - 10.f) / 2.f)
		- 0.03f * FMath::Max(10.f - K, 0.f);
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
	FParse::Value(SailingArgs::Dev(), TEXT("SailingWaterRings="), RingCount); // measuring
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

	// The far water starts one outer-ring cell inside the outer ring (the rings overlap the same way) and follows its snap.
	// It used to be the engine's plane scaled to 40 km: one quad whose corners, 20 to 28 km out, carried the curvature's 27
	// to 53 m drop across the whole quad, so past the rings the water lay tens of metres down and the shallow bay bed
	// showed above it (docs/water-8/edge-mac).
	TArray<FVector> Verts;
	TArray<int32> Tris;
	// Wide World Rendering PR 4: the far plane's size is the world's (40 km on the Texas coast, 60 km at Marseille, where
	// the sea must meet the far ring's mountains), with as many vertices per kilometre so it follows the curvature as well.
	if (const ASailingGameMode* GameMode = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr)
	{
		if (GameMode->GetLake().IsLoaded()) FarPlaneSizeMeters = float(FMath::Clamp(GameMode->GetLake().FarPlaneKm, 20.0, 120.0) * 1000.0);
	}
	int32 PerSide = FMath::RoundToInt(FarGridPerSide * FarPlaneSizeMeters / 40000.f);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingFarGrid="), PerSide); // measuring
	BuildFarGrid(FarGridInnerHalfMeters(RingCount), 0.5f * FarPlaneSizeMeters, PerSide, Verts, Tris);
	TArray<FVector> Normals;
	Normals.Init(FVector::UpVector, Verts.Num());
	TArray<FProcMeshTangent> Tangents;
	Tangents.Init(FProcMeshTangent(FVector(1.0, 0.0, 0.0), false), Verts.Num());
	FarPlane->ClearAllMeshSections();
	FarPlane->CreateMeshSection_LinearColor(0, Verts, Tris, Normals, {}, {}, Tangents, false);
	if (WaterMaterial) FarPlane->SetMaterial(0, WaterMaterial);
}

float AWaterSurface::FarGridInnerHalfMeters(int32 InRingCount)
{
	const float OuterSpacing = kFinestSpacingM * float(1 << (FMath::Max(InRingCount, 1) - 1));
	return (0.5f * float(kRingQuads) - 1.f) * OuterSpacing;
}

void AWaterSurface::BuildFarGrid(float InnerHalfM, float OuterHalfM, int32 PerSide, TArray<FVector>& OutVerts, TArray<int32>& OutTris)
{
	OutVerts.Reset();
	OutTris.Reset();
	PerSide = FMath::Max(PerSide, 4);
	const int32 Around = 4 * PerSide;
	// Squares growing by about one cell (2 r / PerSide) each step, evenly in log distance so the last lands on the far
	// edge: the cells stay about square and grow with the distance, as the rings' do. The curvature's interpolation error
	// goes as the cell's size squared over 4R (2.5 cm at PerSide 44, 1.2 at 64), and the grid's cost with its vertices.
	const int32 Steps = FMath::Max(1, FMath::CeilToInt(FMath::Loge(OuterHalfM / InnerHalfM) / FMath::Loge(1.f + 2.f / float(PerSide))));
	const double Ratio = FMath::Pow(double(OuterHalfM) / double(InnerHalfM), 1.0 / double(Steps));
	TArray<float> Halves;
	for (int32 K = 0; K <= Steps; ++K)
	{
		Halves.Add(K == Steps ? OuterHalfM : float(InnerHalfM * FMath::Pow(Ratio, double(K))));
	}
	OutVerts.Reserve(Halves.Num() * Around);
	for (const float R : Halves)
	{
		for (int32 P = 0; P < Around; ++P)
		{
			// Around the square from its (-, -) corner.
			const float U = -1.f + 2.f * float(P % PerSide) / float(PerSide);
			const int32 Side = P / PerSide;
			const FVector2D Q = Side == 0 ? FVector2D(U, -1.f) : Side == 1 ? FVector2D(1.f, U) : Side == 2 ? FVector2D(-U, 1.f) : FVector2D(-1.f, -U);
			OutVerts.Add(FVector(Q.X * R, Q.Y * R, 0.f) * CmPerMeter);
		}
	}
	OutTris.Reserve((Halves.Num() - 1) * Around * 6);
	for (int32 K = 0; K + 1 < Halves.Num(); ++K)
	{
		for (int32 P = 0; P < Around; ++P)
		{
			const int32 A = K * Around + P, B = K * Around + (P + 1) % Around, C = A + Around, D = B + Around;
			// Split along the shorter diagonal (at the corners the other one is half again as long, and the curvature's
			// interpolation error grows as its square).
			const bool bAD = FVector::DistSquared(OutVerts[A], OutVerts[D]) < FVector::DistSquared(OutVerts[B], OutVerts[C]);
			const FIntVector Split[2] = { bAD ? FIntVector(A, B, D) : FIntVector(A, B, C), bAD ? FIntVector(A, D, C) : FIntVector(B, D, C) };
			for (const FIntVector& T : Split)
			{
				// Wound as the rings' triangles are ((b - a) x (c - a) points down).
				const bool bDown = FVector::CrossProduct(OutVerts[T.Y] - OutVerts[T.X], OutVerts[T.Z] - OutVerts[T.X]).Z < 0.0;
				OutTris.Add(T.X);
				OutTris.Add(bDown ? T.Y : T.Z);
				OutTris.Add(bDown ? T.Z : T.Y);
			}
		}
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
	// The far grid on the outer ring's snap, 10 cm down so the ring wins where they overlap.
	if (Rings.Num() > 0)
	{
		FarPlane->SetWorldLocation(Rings.Last()->GetComponentLocation() - FVector(0.f, 0.f, 10.f));
	}
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
		const double FarCapStart = FPlatformTime::Seconds();
		UpdateFarCaps(DeltaSeconds);
		FarCapCpuSeconds += FPlatformTime::Seconds() - FarCapStart;
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
	const bool bReconfigure = !Detail || Detail->Spec(0).N != DrawnChop().N || FMath::Abs(P.WindMs - Q.WindMs) > 0.25 || FMath::Abs(FMath::FindDeltaAngleRadians(P.TravelDirRad, Q.TravelDirRad)) > 0.05
		|| FMath::Abs(P.FetchMeters / Q.FetchMeters - 1.0) > 0.1 || FMath::Abs(P.Development / Q.Development - 1.0) > 0.3;
	if (bReconfigure)
	{
		if (bFramePending) { PendingFrame.Wait(); bFramePending = false; }
		TSharedPtr<FWaveDetail, ESPMode::ThreadSafe> New = MakeShared<FWaveDetail, ESPMode::ThreadSafe>();
		std::vector<FWaveDetail::FCascadeSpec> Specs = { DrawnChop() };
		if (Tier >= 2) { Specs.push_back(DrawnRipple()); Specs.push_back(DrawnCapillary()); }
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
		if (D->NumCascades() > 2) D->Evaluate(2, At, F->Capillary, Scale);
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
			for (int32 K = 0; K < 4; ++K) CapsLast[K] = Done->CapThr[K];
			CapsLastSlope = Done->CapSlope;
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
			if (Done->CapillaryN > 0) UploadPackedMips(CapillaryBMap, Done->Capillary, Done->CapillaryN);
			UpdateFoamGrid(Done);
		}
	}
	if (bUploadPending) return;

	// Blend the two frames to the next frame's instant (this one plus this frame's length): A = height, displacement,
	// Jacobian; B = slopes and their squares.
	const double Ahead = T + FMath::Clamp(double(GetWorld()->GetDeltaSeconds()), 0.0, kDetailStep);
	const float W = float(FMath::Clamp((Ahead - FramePrev->Time) / kDetailStep, 0.0, 1.0));
	const FDetailFramePtr Prev = FramePrev, Next = FrameNext;
	const bool bRipple = Prev->Ripple.N > 0 && Next->Ripple.N == Prev->Ripple.N;
	const bool bCapillary = Prev->Capillary.N > 0 && Next->Capillary.N == Prev->Capillary.N;
	// W8: Monahan's whitecap cover for the sea's mean wind times the water body's share: the renderer solves the fold
	// threshold that caps it on the sea it draws (the long trains here, the chop's whitecap Jacobian there). Below 12 kn
	// only the share that breaks (WhitecapOnset); never quite zero, so the threshold is extrapolated below every sample.
	const double MeanMs = Waves->GetParams().WindSpeedKnots * kKnot;
	const double CapTarget = FMath::Max(3.84e-6 * FMath::Pow(FMath::Max(MeanMs, 0.0), 3.41) * WhitecapScaleHere()
		* WhitecapOnset(float(Waves->GetParams().WindSpeedKnots)), 1e-7);
	const double CapTime = Ahead;
	TArray<FWaveComponent> Long(Waves->GetComponents(), kWaveComponents);
	// As M_WaterV4 draws them around the camera: each long train scaled by the sea map's ratio there (W3), the chop by
	// its short scale.
	float CapShort = 1.f;
	if (const FSeaMap* Sea = Waves->GetSeaMap(); Sea && Sea->IsValid())
	{
		const FVector2D Cam = SailingFrame::ToMap(GetWorld(), UGameplayStatics::GetPlayerCameraManager(this, 0) ? UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraLocation() : GetActorLocation());
		float Ratio[kSeaChannels];
		Sea->Sample(Cam.X, Cam.Y, Ratio);
		for (int32 I = 0; I < kSeaLongComponents && I < Long.Num(); ++I) Long[I].Amplitude *= Ratio[I];
		CapShort = Ratio[kSeaLongComponents];
	}
	const float FoldScale = DrawnFoldScaleAt(float(Waves->GetParams().WindSpeedKnots));
	// The cap thresholds are solved at the short waves' rate (each solve is eased into what is drawn over about 12 frames,
	// CapThrSmooth); between solves the blend reuses the last.
	const bool bSolveCaps = CapsSolvedAt < 0.0 || CapsLastSlope <= 0.f || Ahead < CapsSolvedAt || Ahead - CapsSolvedAt >= 0.999 * kDetailStep;
	if (bSolveCaps) CapsSolvedAt = Ahead;
	const double LastThr[4] = { CapsLast[0], CapsLast[1], CapsLast[2], CapsLast[3] };
	const double LastSlope = CapsLastSlope;
	PendingUpload = Async(EAsyncExecution::ThreadPool, [Prev, Next, W, bRipple, bCapillary, CapTarget, CapTime, CapShort, FoldScale, Long = MoveTemp(Long), bSolveCaps, LastThr0 = LastThr[0], LastThr1 = LastThr[1], LastThr2 = LastThr[2], LastThr3 = LastThr[3], LastSlope]() -> FDetailUploadPtr
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
			double CapThr[4] = { LastThr0, LastThr1, LastThr2, LastThr3 }, CapSlope = LastSlope;
			if (bSolveCaps)
			{
				// The four spacings sample the same points: each train's terms once, its sine once per point for all four
				// (FWaveDetail::FLongJacobians; the PC's Ultra trace had this blend at 6-8 ms of worker time a frame, most of it
				// these sines).
				double Spacings[4], Fades[4];
				std::vector<float> Samples[4];
				for (int32 K = 0; K < 4; ++K)
				{
					Spacings[K] = 0.5 * double(1 << K);
					Fades[K] = FMath::Clamp(1.0 - 64.0 * Spacings[K] / 900.0, 0.0, 1.0);
					Samples[K].reserve(NN / 4);
				}
				const FWaveDetail::FLongJacobians LongJ(Long.GetData(), Long.Num(), OmegaMax, Choppiness, Spacings, Fades, 4);
				for (int32 R = 0; R < A.N; R += 2)
					for (int32 Cc = 0; Cc < A.N; Cc += 2)
					{
						const int32 I = R * A.N + Cc;
						const double Chop = 1.0 - FMath::Min(CapShort, 2.f) * (1.0 - JCap[I]); // the shader's jd
						// The long trains sampled over about 170 m (the chop's 23 m tile holds about one of their wavelengths, so a
						// frame's sample sat on whatever crests crossed it), the chop at its own texel.
						double Jl[4];
						LongJ.Evaluate(R * Cell * 7.31, Cc * Cell * 7.37, CapTime, Jl);
						for (int32 K = 0; K < 4; ++K) Samples[K].push_back(float(1.0 - FoldScale * (1.0 - Jl[K] * Chop)));
					}
				for (int32 K = 0; K < 4; ++K)
				{
					double Slope = 0.0;
					FWaveDetail::CapThreshold(MoveTemp(Samples[K]), CapTarget, CapThr[K], Slope);
					if (K == 0) CapSlope = Slope;
				}
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
			Out->JCap = JCap; // W4: the foam grid reads the caps from it
			Out->Tile = float(A.Tile);
			Out->CapShort = CapShort;
			Out->FoldScale = FoldScale;
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
		if (bCapillary)
		{
			// docs/near-water/: the capillary wavelets as the ripples: slopes and their squares (LEAN).
			const FWaveDetail::FGrid& A = Prev->Capillary;
			const FWaveDetail::FGrid& B = Next->Capillary;
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
			Out->CapillaryN = A.N;
			PackMips(MoveTemp(Pix), A.N, Out->Capillary);
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
		const Quat& Q = M.GetState().Orientation;
		const Vec3 Ax = Q.Rotate(Vec3(1.0, 0.0, 0.0)), Ay = Q.Rotate(Vec3(0.0, 1.0, 0.0)), Az = Q.Rotate(Vec3(0.0, 0.0, 1.0));
		// Every hull on one map in her frame (a catamaran's two, a trimaran's amas, the maxi's sections), built once
		// per boat and canoe depth.
		const int32 Type = int32(M.GetConfig().Type);
		if (!HullClipTexture || Type != HullClipBoatType || FMath::Abs(HullClip.MainDepth - M.HullDepth()) > 0.005)
		{
			HullClip.Build(Hulls, M.HullDepth());
			HullClipBoatType = Type;
			if (!HullClipTexture)
			{
				HullClipTexture = MakeFloatMap(FHullClipMap::Cols, FHullClipMap::Rows, PF_A32B32G32R32F, false);
			}
			const std::vector<float> Pixels = HullClip.Pixels();
			UploadFloats(HullClipTexture, TArray<float>(Pixels.data(), int32(Pixels.size())), FHullClipMap::Cols, FHullClipMap::Rows, 4);
		}
		WaterMaterial->SetTextureParameterValue(TEXT("HullClipMap"), HullClipTexture);
		// docs/spray/: her velocity and speed for the white water she makes (M_WaterV4's hullFoam).
		const Vec3 Vel = M.GetState().Velocity;
		WaterMaterial->SetVectorParameterValue(TEXT("HullClipV"), FLinearColor(float(Vel.X), float(Vel.Y), float(FMath::Sqrt(Vel.X * Vel.X + Vel.Y * Vel.Y)), 1.f));
		WaterMaterial->SetVectorParameterValue(TEXT("HullClipRect"),
			FLinearColor(float(HullClip.X0), float(HullClip.Y0), float(HullClip.SizeX), float(HullClip.SizeY)));
		// -SailingClassicHullClip: V7's flat 2 m drop over 80% of the deck plan (compare the pit it opened at the bow).
		static SailingArgs::FCachedFlag ClassicArg(TEXT("SailingClassicHullClip"));
		auto Set = [this](const TCHAR* Name, double X, double Y, double Z, double W)
		{
			WaterMaterial->SetVectorParameterValue(Name, FLinearColor(float(X), float(Y), float(Z), float(W)));
		};
		// The material drops the water below her bottom (FHullClipMap) wherever it is inside a hull; the main hull's
		// shape is only for the V7 clip.
		// -SailingNoHullClip: the sea drawn through every hull (compare what the clip hides, with -SailingHideBoat).
		static SailingArgs::FCachedFlag NoClipArg(TEXT("SailingNoHullClip"));
		Set(TEXT("HullClipA"), O.X, O.Y, O.Z, NoClipArg.Get() ? 0.0 : 1.0);
		Set(TEXT("HullClipB"), Ax.X, Ax.Y, Ax.Z, S.SheerZ);
		Set(TEXT("HullClipC"), Ay.X, Ay.Y, Ay.Z, S.SheerRise);
		Set(TEXT("HullClipD"), Az.X, Az.Y, Az.Z, S.SheerRiseFromX);
		Set(TEXT("HullClipE"), S.BowX, S.SternX, S.MaxBeamX, S.MaxHalfBeam);
		Set(TEXT("HullClipF"), S.AftLength, S.TransomBeamLoss, S.CenterY, S.BilgePower);
		Set(TEXT("HullClipG"), S.WaterlineMidX, S.WaterlineHalfLength, M.HullDepth() * S.DepthScale, S.DepthOffset);
		Set(TEXT("HullClipH"), S.BowOverhangSlope, S.SternOverhangSlope, ClassicArg.Get() ? 1.0 : 0.0, 0.0);
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
		FWakeFrame Done = PendingWake.Consume();
		bWakePending = false;
		UploadFloats(WakeGridMap, Done.Pixels, Done.N, Done.N, 4);
		// W4: keep its foam channel for the foam grid.
		WakeFoamN = Done.N;
		WakeFoamOrigin = Done.Origin;
		WakeFoamCell = Done.Cell;
		WakeFoamPixels = MakeShared<const TArray<float>, ESPMode::ThreadSafe>(MoveTemp(Done.Pixels));
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
		const TArray<float>& Sl = Grid->Slick();
		// RGBA: height, foam, the wake's smooth lane (docs/wake-slick/), unused.
		Out.Pixels.SetNumUninitialized(Out.N * Out.N * 4);
		for (int32 I = 0; I < Out.N * Out.N; ++I)
		{
			Out.Pixels[4 * I] = H[I];
			Out.Pixels[4 * I + 1] = F[I];
			Out.Pixels[4 * I + 2] = Sl[I];
			Out.Pixels[4 * I + 3] = 0.f;
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
	// World streaming: a copy of the terrain (it shares the heights): the tiles may be swapped while the worker reads.
	PendingShore = Async(EAsyncExecution::ThreadPool, [Lake, Terrain = Lake->Terrain, Origin, Level]()
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
				Out.Depth[R * kShoreRes + C] = float(Terrain.DepthAt(Origin.X + (R + 0.5) * kShoreCellM, Origin.Y + (C + 0.5) * kShoreCellM));
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

void AWaterSurface::UpdateFarCaps(float DeltaSeconds)
{
	// docs/far-cap-sprites/: High and Ultra (Medium keeps M_WaterV4's flecks alone). -SailingNoFarCaps compares.
	static SailingArgs::FCachedFlag NoFarCapsArg(TEXT("SailingNoFarCaps"));
	const bool bOn = Tier >= 2 && FarCapMaterial && DropletMesh && WaterMaterial && !NoFarCapsArg.Get();
	if (bOn != bFarCaps)
	{
		bFarCaps = bOn;
		if (WaterMaterial) WaterMaterial->SetScalarParameterValue(TEXT("FarCapSprites"), bOn ? 1.f : 0.f);
		if (!bOn)
		{
			for (TPair<FIntPoint, FFarCapTile>& T : FarCapTiles) if (T.Value.Mesh) T.Value.Mesh->DestroyComponent();
			FarCapTiles.Reset();
			FarCapKeep.Reset();
		}
	}
	if (!bOn) return;
	const FWaveField* Waves = GetWaves();
	const FWindField* Wind = GetWind();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!Waves || !Wind) return;
	APlayerCameraManager* CamMgr = UGameplayStatics::GetPlayerCameraManager(this, 0);
	const FVector CamW = CamMgr ? CamMgr->GetCameraLocation() : GetActorLocation();
	// Planned every half second, and at once when the view turns (only the tiles in view are held).
	const float Yaw = CamMgr ? float(CamMgr->GetCameraRotation().Yaw) : 0.f;
	FarCapTimer -= DeltaSeconds;
	if (FarCapTimer > 0.f && FMath::Abs(FMath::FindDeltaAngleDegrees(Yaw, FarCapYaw)) < 8.f) return;
	FarCapTimer = 0.5f;
	FarCapYaw = Yaw;
	const FVector2D Cam = SailingFrame::ToMap(GetWorld(), CamW);
	const double CamH = (CamW.Z - SailingFrame::MapAnchor(GetWorld()).Z) / CmPerMeter;
	const double T = GetSimTime();
	const double Scale = WhitecapScaleHere(), Onset = WhitecapOnset(float(Waves->GetParams().WindSpeedKnots));
	const Sailing::FLakeTerrain* Terrain = GM && GM->GetLake().IsLoaded() ? &GM->GetLake().Terrain : nullptr;
	const double WaterZ = Terrain ? -Terrain->GetLevelBelowPool() : 0.0;
	constexpr double Near = 300.0, Far = 1250.0;
	const double TileM = FarCapTileM, Area = TileM * TileM;
	const int32 Reach = FMath::CeilToInt(Far / TileM) + 1;
	const FIntPoint Here(FMath::FloorToInt(Cam.X / TileM), FMath::FloorToInt(Cam.Y / TileM));
	// The view's cone on the map (map +X north, +Y east; Unreal's yaw is the same bearing): a tile is wanted when it
	// reaches inside the half field of view plus 25 deg, and kept until it is 40 deg out (no churn at the edge).
	const double HalfFov = 0.5 * (CamMgr ? CamMgr->GetFOVAngle() : 90.0);
	const FVector2D Fwd = SailingFrame::ToMap(GetWorld(), CamW + FRotator(0.0, Yaw, 0.0).Vector() * 100.0) - Cam;
	const double Bearing = FMath::RadiansToDegrees(FMath::Atan2(Fwd.Y, Fwd.X));
	struct FPlan { FIntPoint Key; double Cover, CX, CY; int32 Slots; };
	TArray<FPlan> Plans;
	TSet<FIntPoint> Want;
	int32 Total = 0;
	for (int32 I = -Reach; I <= Reach; ++I)
	{
		for (int32 J = -Reach; J <= Reach; ++J)
		{
			const FIntPoint Key(Here.X + I, Here.Y + J);
			const double X0 = Key.X * TileM, Y0 = Key.Y * TileM;
			const double NX = FMath::Clamp(Cam.X, X0, X0 + TileM) - Cam.X, NY = FMath::Clamp(Cam.Y, Y0, Y0 + TileM) - Cam.Y;
			const double FX = FMath::Max(FMath::Abs(X0 - Cam.X), FMath::Abs(X0 + TileM - Cam.X)), FY = FMath::Max(FMath::Abs(Y0 - Cam.Y), FMath::Abs(Y0 + TileM - Cam.Y));
			const double DNear = FMath::Sqrt(NX * NX + NY * NY), DFar = FMath::Sqrt(FX * FX + FY * FY);
			// (Only where the sprites can have a share: in the ring, and with the view low enough over its far side.)
			if (DNear > Far || DFar < Near || CamH > 0.14 * DFar) continue;
			double Lo = 180.0, Hi = -180.0;
			for (int32 K = 0; K < 4; ++K)
			{
				const double A = FMath::FindDeltaAngleDegrees(Bearing, FMath::RadiansToDegrees(FMath::Atan2(Y0 + (K & 1) * TileM - Cam.Y, X0 + (K >> 1) * TileM - Cam.X)));
				Lo = FMath::Min(Lo, A); Hi = FMath::Max(Hi, A);
			}
			const double Edge = HalfFov + (FarCapTiles.Contains(Key) ? 40.0 : 25.0);
			if ((Hi - Lo) < 180.0 && (Lo > Edge || Hi < -Edge)) continue;
			const double CX = X0 + 0.5 * TileM, CY = Y0 + 0.5 * TileM;
			double From = 0.0, Factor = 1.0;
			Wind->ReadableAt(CX, CY, T, From, Factor);
			FPlan P{Key, FarCapCover(Wind->MeanSurfaceRoughnessAt(CX, CY, T) * 8.0 * Factor, Scale, Onset), CX, CY, 0};
			float Prob0 = 0.f;
			FarCapTilePlan(P.Cover, Area, P.Slots, Prob0);
			Total += P.Slots;
			Plans.Add(P);
			Want.Add(Key);
		}
	}
	// Over the budget (a storm), fewer and bigger caps: the same foam. Stepped by quarters so the tiles aren't rebuilt as it wanders.
	const double SizeStep = Total > FarCapBudget ? FMath::CeilToDouble(4.0 * double(Total) / FarCapBudget) / 4.0 : 1.0;
	const double CapArea = FarCapArea * SizeStep;
	for (FPlan& P : Plans)
	{
		{
			const FIntPoint Key = P.Key;
			const double X0 = Key.X * TileM, Y0 = Key.Y * TileM, CX = P.CX, CY = P.CY, Cover = P.Cover;
			int32 Slots = 0;
			float Prob = 0.f;
			FarCapTilePlan(Cover, Area, Slots, Prob, CapArea);
			FFarCapTile* Tile = FarCapTiles.Find(Key);
			// Rebuilt only when the cover needs more slots than it holds (or the caps' size steps). Not shrunk in place: the
			// slots past the new count would vanish mid-life; a tile is dropped when it leaves the view or the ring instead.
			const bool bRebuild = !Tile || Slots > Tile->Slots || Tile->Size != SizeStep;
			// The probability in effect before (a cap's life is decided at its start, M_FarCap's ProbA and ProbB), and the
			// slots that already stood (the rest stay dark until their next life).
			const float ProbBefore = Tile ? Tile->Prob : -1.f;
			const int32 SlotsBefore = Tile && Tile->Size == SizeStep ? Tile->Slots : 0;
			if (bRebuild)
			{
				if (Tile && Tile->Mesh) { FarCapKeep.Remove(Tile->Mesh); FarCapKeep.Remove(Tile->Mid); Tile->Mesh->DestroyComponent(); }
				FFarCapTile& New = FarCapTiles.FindOrAdd(Key);
				New = FFarCapTile();
				New.Slots = Slots;
				New.Size = SizeStep;
				New.Prob = ProbBefore;
				if (Slots > 0)
				{
					UInstancedStaticMeshComponent* Mesh = NewObject<UInstancedStaticMeshComponent>(this);
					Mesh->SetMobility(EComponentMobility::Static);
					Mesh->SetupAttachment(RootComponent);
					Mesh->SetUsingAbsoluteLocation(true);
					Mesh->SetUsingAbsoluteRotation(true);
					Mesh->SetStaticMesh(DropletMesh);
					Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					Mesh->SetCastShadow(false);
					Mesh->bAffectDistanceFieldLighting = false;
					// (Out of ray tracing and the captures: their moving vertices made each tile dynamic ray-tracing geometry, 0.5 ms
					// of render thread on High for no visible light.)
					Mesh->bVisibleInRayTracing = false;
					Mesh->bAffectDynamicIndirectLighting = false;
					Mesh->bVisibleInReflectionCaptures = false;
					Mesh->bVisibleInRealTimeSkyCaptures = false;
					Mesh->SetCanEverAffectNavigation(false);
					Mesh->BoundsScale = 3.f; // the material stands each quad up and moves it a few metres a life
					Mesh->NumCustomDataFloats = 2; // the seed, and 1 on a slot added by a rebuild
					UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(FarCapMaterial, this);
					Mesh->SetMaterial(0, Mid);
					Mesh->RegisterComponent();
					// Slots over the tile from its own seed (a tile rebuilt keeps its places), none on land.
					FRandomStream Rng(int32(uint32(Key.X) * 73856093u ^ uint32(Key.Y) * 19349663u));
					TArray<FTransform> Xf;
					TArray<float> Seeds, Born;
					Xf.Reserve(Slots);
					for (int32 K = 0; K < Slots; ++K)
					{
						const double PX = X0 + Rng.FRand() * TileM, PY = Y0 + Rng.FRand() * TileM;
						const float Seed = Rng.FRand();
						// (Off the shore by more than a life's hop, in a metre of water: at the water's edge they hopped onto the beach.)
						if (Terrain)
						{
							bool bDry = Terrain->HeightAt(PX, PY) > WaterZ - 1.0;
							for (int32 A = 0; A < 4 && !bDry; ++A) bDry = Terrain->HeightAt(PX + (A < 2 ? (A ? 7.0 : -7.0) : 0.0), PY + (A >= 2 ? (A == 3 ? 7.0 : -7.0) : 0.0)) > WaterZ - 0.5;
							if (bDry) continue;
						}
						// (Stood on end: flat at the water, a tile's bounds were a thin box the water occluded, so the GPU culled all
						// but the tiles reaching onto land. M_FarCap places every vertex from the pivot, so this changes nothing else.)
						Xf.Add(FTransform(FRotator(0.0, 0.0, 90.0).Quaternion(), SailingFrame::ToWorld(GetWorld(), PX, PY, WaterZ + 0.5), FVector::OneVector));
						Seeds.Add(Seed);
						Born.Add(Tile && K >= SlotsBefore ? 1.f : 0.f);
					}
					Mesh->AddInstances(Xf, false, true);
					for (int32 K = 0; K < Seeds.Num(); ++K)
					{
						Mesh->SetCustomDataValue(K, 0, Seeds[K], false);
						Mesh->SetCustomDataValue(K, 1, Born[K], false);
					}
					Mesh->MarkRenderStateDirty();
					New.Mesh = Mesh;
					New.Mid = Mid;
					FarCapKeep.Add(Mesh);
					FarCapKeep.Add(Mid);
				}
				Tile = &New;
			}
			Tile->Cover = Cover;
			if (Tile->Mid)
			{
				// (The live probability carries what the slots planned for now: slots fixed, probability moving.)
				// -SailingDebugFarCaps: every slot live and ten times as tall, to see where they stand.
				static SailingArgs::FCachedFlag DebugFarCapsArg(TEXT("SailingDebugFarCaps"));
				const bool bDebug = DebugFarCapsArg.Get();
				Tile->Mid->SetScalarParameterValue(TEXT("DebugAll"), bDebug ? 1.f : 0.f);
				// A cap's life is decided as it starts: lives begun before SwitchT keep ProbA (the slots a rebuild added none),
				// later ones take ProbB. Changing the probability under a living cap made it blink out (or in) mid-life.
				const float NewProb = bDebug ? 1.f : Tile->Slots > 0 ? float(FMath::Min(Cover * Area / (CapArea * 0.7937) / Tile->Slots, 1.0)) : 0.f;
				if (bRebuild || FMath::Abs(NewProb - Tile->Prob) > 0.01f)
				{
					Tile->Mid->SetScalarParameterValue(TEXT("ProbA"), Tile->Prob < 0.f ? NewProb : Tile->Prob);
					Tile->Mid->SetScalarParameterValue(TEXT("ProbB"), NewProb);
					Tile->Mid->SetScalarParameterValue(TEXT("SwitchT"), GetWorld()->GetTimeSeconds());
					Tile->Prob = NewProb;
				}
				Tile->Mid->SetScalarParameterValue(TEXT("Size"), float(FMath::Sqrt(SizeStep)));
				Tile->Mid->SetScalarParameterValue(TEXT("CapH"), float(FMath::Lerp(0.2, 0.45, FMath::Clamp((Waves->GetParams().WindSpeedKnots - 12.0) / 10.0, 0.0, 1.0))) * (bDebug ? 10.f : 1.f));
				// A cap rides a crest: stood at the mean level, the crests between it and a low eye hid it.
				Tile->Mid->SetScalarParameterValue(TEXT("Lift"), float(0.6 * Waves->SignificantHeightAt(CX, CY) * CmPerMeter));
			}
		}
	}
	FarCapSlotsHeld = 0;
	for (const FPlan& P : Plans) if (const FFarCapTile* Tl = FarCapTiles.Find(P.Key)) FarCapSlotsHeld += Tl->Slots;
	static SailingArgs::FCachedFlag DebugFarCapsLog(TEXT("SailingDebugFarCaps"));
	if (DebugFarCapsLog.Get())
	{
		int32 Placed = 0;
		for (const TPair<FIntPoint, FFarCapTile>& Tl : FarCapTiles) Placed += Tl.Value.Mesh ? Tl.Value.Mesh->GetInstanceCount() : 0;
		UE_LOG(LogSailing, Display, TEXT("FarCaps: cam (%.0f, %.0f) h %.1f m, %d tiles wanted, %d held, %d sprites, water %.2f, cover at cam %.5f"), Cam.X, Cam.Y, CamH, Want.Num(), FarCapTiles.Num(), Placed, WaterZ,
			FarCapCover(Wind->MeanSurfaceRoughnessAt(Cam.X, Cam.Y, T) * 8.0, Scale, Onset));
	}
	for (auto It = FarCapTiles.CreateIterator(); It; ++It)
	{
		if (Want.Contains(It.Key())) continue;
		if (It.Value().Mesh) { FarCapKeep.Remove(It.Value().Mesh); FarCapKeep.Remove(It.Value().Mid); It.Value().Mesh->DestroyComponent(); }
		It.RemoveCurrent();
	}
}

void AWaterSurface::UpdateSpray(float DeltaSeconds)
{
	const FWaveField* Waves = GetWaves();
	const FWindField* Wind = GetWind();
	if (!Waves || !DropletMesh) return;
	const FVector Cam = UGameplayStatics::GetPlayerCameraManager(this, 0) ? UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraLocation() : GetActorLocation();
	if (!Spray)
	{
		Spray = NewObject<UInstancedStaticMeshComponent>(this, TEXT("Spray"));
		Spray->SetupAttachment(RootComponent);
		Spray->SetStaticMesh(DropletMesh);
		if (SprayMaterial) Spray->SetMaterial(0, SprayMaterial);
		// pc/ultra-spray (docs/ultra-spray): Ultra's spray close up, mist torn into wisps and sheets beading into drops (M_Spray's
		// Fine; 0, as it was, on the other tiers). -SailingNoUltraSpray compares.
		if (SprayMaterial && USailingSettings::Get()->Quality == ESailingQuality::Ultra && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoUltraSpray")))
		{
			if (UMaterialInstanceDynamic* Fine = Spray->CreateDynamicMaterialInstance(0, SprayMaterial)) Fine->SetScalarParameterValue(TEXT("Fine"), 1.f);
		}
		Spray->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Spray->SetCastShadow(false);
		Spray->SetUsingAbsoluteLocation(true);
		Spray->SetUsingAbsoluteRotation(true);
		// M_Spray's per-instance data: opacity, grain (1 a clump of droplets, 0 smooth mist), a seed for the speckle.
		Spray->NumCustomDataFloats = 3;
		Spray->RegisterComponent();
		TArray<FTransform> Hidden;
		// (Unused instances are parked at the camera, at zero scale: parked 10 km down at the world's origin they stretched the
		// component's bounds to a 5 km sphere under the lake, the PC's finding.)
		Hidden.Init(FTransform(FQuat::Identity, Cam, FVector::ZeroVector), MaxDroplets());
		Spray->AddInstances(Hidden, false, true);
	}
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	const double T = GetSimTime();
	const FVector2D CamM = SailingFrame::ToMap(GetWorld(), Cam);   // droplets fly in the map frame
	const Vec3 WindV = Wind ? Wind->VelocityAt(Vec3(CamM.X, CamM.Y, 2.0), T) : Vec3();
	const FVector WindAt2m(WindV.X, WindV.Y, 0.0);
	auto Emit = [&](const FVector& P, const FVector& V, float Size, ESprayKind Kind, float Life)
	{
		if (Droplets.Num() >= Spray->GetInstanceCount()) return;
		FDroplet D;
		D.P = P;
		D.V = V;
		D.Life = Life;
		D.Size = Size;
		D.Kind = uint8(Kind);
		D.Seed = SprayRng.FRand();
		Droplets.Add(D);
	};

	// Bows slamming into the waves: the closing speed between the bow and the water surface throws up spray to each side,
	// carried forward with the boat: a sheet off the bow wave first, which tears into clumps of droplets, and the mist
	// they leave drifting downwind. How much and how high follow the slam and the speed.
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
		const float Dense = float(MaxDroplets()) / float(kMaxDroplets); // Ultra: a fuller sheet, the same shape
		const FVector Fwd = FVector(BowV.X, BowV.Y, 0.0).GetSafeNormal();
		const FVector Side(-Fwd.Y, Fwd.X, 0.0);
		// Hull size: a dinghy's bow throws less and lower than a keelboat's.
		const float Scale = FMath::Clamp(float(Hull.MaxHalfBeam) / 1.2f, 0.5f, 1.5f);
		// The bow wave: at speed a thin sheet of water peels off each side of the bow where it meets the water and breaks
		// into drops, slam or no slam (it grows with the speed past 2 m/s, about 4 kn).
		if (Speed > 2.0)
		{
			const float Rate = Dense * float(Speed - 2.0) * 14.f * Scale;
			const int32 Peel = FMath::Min(int32(Rate * Dt + SprayRng.FRand()), FMath::RoundToInt(6.f * Dense));
			for (int32 I = 0; I < Peel; ++I)
			{
				const float S = SprayRng.FRand() < 0.5f ? -1.f : 1.f;
				const double X = Hull.BowX * SprayRng.FRandRange(0.55f, 0.8f);
				const Vec3 W = M.BodyToWorld(Vec3(X, Hull.CenterY + S * 0.9 * Hull.DeckHalfBeam(X), 0.0));
				const FVector P(W.X, W.Y, Waves->Height(W.X, W.Y, T) + 0.02);
				const FVector V = FVector(BowV.X, BowV.Y, 0.0) * 0.85f + Side * S * float(Speed) * SprayRng.FRandRange(0.15f, 0.3f)
					+ FVector(0, 0, SprayRng.FRandRange(0.3f, 0.9f) * FMath::Sqrt(float(Speed) / 3.f));
				Emit(P, V, SprayRng.FRandRange(0.15f, 0.35f) * Scale, ESprayKind::Sheet, SprayRng.FRandRange(0.25f, 0.45f));
				if (SprayRng.FRand() < 0.5f) Emit(P, V * 1.1f, SprayRng.FRandRange(0.08f, 0.18f) * Scale, ESprayKind::Drops, SprayRng.FRandRange(0.4f, 0.8f));
			}
		}
		if (Bow.Z > H + 0.15 || Closing < 0.45 || Speed < 1.5) continue;
		const float Slam = float(FMath::Min(Closing, 2.5));
		const float Fast = FMath::Min(float(Speed) / 3.f, 1.5f);
		const int32 Count = FMath::Clamp(FMath::RoundToInt(Dense * Dt * 1800.f * float(Closing - 0.45) * Fast), 0, FMath::RoundToInt(80.f * Dense));
		// A hard slam (the bow falling onto a wave faster than 1.2 m/s): a splash, a burst of mist and torn sheets that
		// hangs over the bow and blows aft.
		if (Closing > 1.2)
		{
			const int32 Burst = FMath::Min(FMath::RoundToInt(Dense * Dt * 60.f * float(Closing - 1.2) * Fast * 4.f), FMath::RoundToInt(6.f * Dense));
			for (int32 I = 0; I < Burst; ++I)
			{
				const FVector P = FVector(Bow.X, Bow.Y, H) + Side * SprayRng.FRandRange(-0.5f, 0.5f) * Scale + FVector(0, 0, 0.2f);
				const FVector V = FVector(BowV.X, BowV.Y, 0.0) * 0.4f + Side * SprayRng.FRandRange(-1.5f, 1.5f)
					+ FVector(0, 0, SprayRng.FRandRange(1.5f, 3.f) * Slam / 2.5f);
				Emit(P, V, SprayRng.FRandRange(0.6f, 1.2f) * Scale, ESprayKind::Mist, SprayRng.FRandRange(1.5f, 2.8f));
				Emit(P, V * 1.3f, SprayRng.FRandRange(0.3f, 0.6f) * Scale, ESprayKind::Sheet, SprayRng.FRandRange(0.3f, 0.5f));
			}
		}
		for (int32 I = 0; I < Count; ++I)
		{
			const float S = SprayRng.FRand() < 0.5f ? -1.f : 1.f;
			const FVector P = FVector(Bow.X, Bow.Y, H) + Side * S * SprayRng.FRandRange(0.2f, 0.6f) * Scale - Fwd * SprayRng.FRandRange(0.f, 0.8f);
			const FVector V = FVector(BowV.X, BowV.Y, 0.0) * 0.6f + Side * S * SprayRng.FRandRange(0.8f, 2.6f)
				+ FVector(0, 0, SprayRng.FRandRange(0.8f, 2.2f) * Slam * FMath::Sqrt(Scale));
			Emit(P, V, SprayRng.FRandRange(0.1f, 0.25f) * Scale * (0.7f + 0.3f * Slam / 2.5f), ESprayKind::Drops, SprayRng.FRandRange(0.6f, 1.4f));
			// One in four leaves mist; one in six starts as a sheet of the bow wave, wide and short-lived.
			if (SprayRng.FRand() < 0.25f)
			{
				Emit(P + FVector(0, 0, 0.2f), V * 0.35f, SprayRng.FRandRange(0.35f, 0.8f) * Scale, ESprayKind::Mist, SprayRng.FRandRange(1.2f, 2.4f));
			}
			if (SprayRng.FRand() < 0.16f)
			{
				Emit(P, V * 0.8f, SprayRng.FRandRange(0.25f, 0.5f) * Scale, ESprayKind::Sheet, SprayRng.FRandRange(0.25f, 0.4f));
			}
		}
	}

	// -SailingDebugSpray (stills and tuning): a steady fountain of every kind 3 m ahead of the camera.
	static SailingArgs::FCachedFlag DebugSprayArg(TEXT("SailingDebugSpray"));
	if (DebugSprayArg.Get() && UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		const FVector Ahead = UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraRotation().Vector() * 300.0 + Cam;
		const FVector2D AM = SailingFrame::ToMap(GetWorld(), Ahead);
		const FVector P(AM.X, AM.Y, Waves->Height(AM.X, AM.Y, T));
		for (int32 I = 0; I < 6; ++I)
		{
			const FVector V(SprayRng.FRandRange(-1.5f, 1.5f), SprayRng.FRandRange(-1.5f, 1.5f), SprayRng.FRandRange(2.f, 4.f));
			Emit(P, V, SprayRng.FRandRange(0.1f, 0.25f), ESprayKind::Drops, SprayRng.FRandRange(0.6f, 1.4f));
			if (I == 0) Emit(P, V * 0.35f, 0.6f, ESprayKind::Mist, 2.f);
			if (I == 1) Emit(P, V * 0.8f, 0.4f, ESprayKind::Sheet, 0.35f);
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
				Emit(P, V, SprayRng.FRandRange(0.08f, 0.2f), ESprayKind::Drops, SprayRng.FRandRange(0.6f, 1.4f));
				if (I == 0) Emit(P, V * 0.5f, SprayRng.FRandRange(0.6f, 1.2f), ESprayKind::Mist, SprayRng.FRandRange(1.5f, 2.5f));
			}
		}
	}

	// Spray reaching the camera's glass (lens drops on High, SailingEnvironment).
	LensSpray = FMath::Max(0.f, LensSpray - 0.35f * Dt);
	const FVector CamM3(CamM.X, CamM.Y, (Cam.Z - GetActorLocation().Z) / CmPerMeter);
	for (const FDroplet& D : Droplets)
	{
		if (D.Kind == uint8(ESprayKind::Drops) && D.Age < 0.6f && FVector::DistSquared(D.P, CamM3) < 4.f) { LensSpray = 1.f; break; }
	}
	// docs/hull-spray/: the boats near the camera. Spray that blows into one (the cabin, the hull below the deck) stops
	// there: the crests' mist drifted downwind straight through the hull and hung in the cabin, a milky haze with drops
	// in it under the companionway (Bean's playtest, rough seas). Spray over the deck and into the cockpit well stays.
	struct FSprayBoat { const FBoatConfig* Config; Vec3 Origin; Quat Orientation; double Reach2, Depth; };
	TArray<FSprayBoat, TInlineAllocator<8>> SprayBoats;
	for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
	{
		const FBoatModel& M = It->GetBoatModel();
		const Vec3 O = M.OriginPosition();
		if (FVector2D::Distance(FVector2D(O.X, O.Y), CamM) > 80.0) continue;
		double Reach = 0.0;
		for (const FHullShape& H : M.GetConfig().Hulls) Reach = FMath::Max(Reach, FMath::Max(H.BowX, -H.SternX) + FMath::Abs(H.CenterY) + H.MaxHalfBeam);
		SprayBoats.Add({ &M.GetConfig(), O, M.GetState().Orientation, FMath::Square(Reach + 1.0), M.HullDepth() });
	}
	auto InsideABoat = [&SprayBoats](const FVector& P)
	{
		for (const FSprayBoat& B : SprayBoats)
		{
			const Vec3 R(P.X - B.Origin.X, P.Y - B.Origin.Y, P.Z - B.Origin.Z);
			if (R.X * R.X + R.Y * R.Y + R.Z * R.Z > B.Reach2) continue;
			const Vec3 L = B.Orientation.Unrotate(R);
			if (CrewInsideBoat(*B.Config, B.Depth, FVector(L.X, L.Y, L.Z))) return true;
		}
		return false;
	};
	// Fly: gravity, the air dragging them toward the wind's speed; gone when they fall back into the water, or into a
	// boat (after their first 0.15 s: the bow wave's sheets start at her skin). Mist hangs: it barely falls and follows
	// the wind closely.
	const FVector G(0, 0, -9.81);
	for (int32 I = Droplets.Num() - 1; I >= 0; --I)
	{
		FDroplet& D = Droplets[I];
		const bool bMist = D.Kind == uint8(ESprayKind::Mist);
		D.V += ((bMist ? G * 0.05f : G) + (WindAt2m - D.V) * (bMist ? 2.5f : 1.2f)) * Dt;
		D.P += D.V * Dt;
		D.Age += Dt;
		if (D.Age > D.Life || (!bMist && D.P.Z < Waves->Height(D.P.X, D.P.Y, T) - 0.05) || (D.Age > 0.15f && InsideABoat(D.P))) Droplets.RemoveAtSwap(I);
	}
	// Draw: each a quad facing the camera, stretched along its motion across the view (the blur of a 1/60 s exposure),
	// fading with age and as it falls back. Past 25 m the droplets read as mist (no grain, wider, fainter).
	TArray<FTransform> Xf;
	const int32 Pool = Spray->GetInstanceCount();
	Xf.SetNumUninitialized(Pool);
	const double Z0 = GetActorLocation().Z;
	float Data[3];
	for (int32 I = 0; I < Pool; ++I)
	{
		if (I < Droplets.Num())
		{
			const FDroplet& D = Droplets[I];
			const FVector W = SailingFrame::ToWorld(GetWorld(), D.P.X, D.P.Y, D.P.Z) + FVector(0.0, 0.0, Z0);
			const FVector ToCam = Cam - W;
			const float Dist = float(ToCam.Size()) / CmPerMeter;
			const FVector N = ToCam.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
			FVector Across = D.V - FVector::DotProduct(D.V, N) * N; // its motion across the view (m/s)
			const float Smear = float(Across.Size());
			if (Smear < 1e-3f) Across = FVector::CrossProduct(N, FVector::UpVector);
			const FVector X = Across.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
			const FVector Y = FVector::CrossProduct(N, X);
			const FQuat Q = FMatrix(X, Y, N, FVector::ZeroVector).ToQuat();
			const float Life = D.Age / D.Life;
			const float Far = FMath::Clamp((Dist - 25.f) / 25.f, 0.f, 1.f);
			float Size = D.Size, Alpha = 0.f, Grain = 1.f;
			switch (ESprayKind(D.Kind))
			{
			case ESprayKind::Mist:
				Size *= 1.f + 1.5f * Life;                                   // spreading as it drifts
				Alpha = 0.22f * FMath::Sin(UE_PI * FMath::Min(Life * 1.4f, 1.f)) * (1.f - Life);
				Grain = 0.f;
				break;
			case ESprayKind::Sheet:
				Size *= 1.f + 0.8f * Life;
				Alpha = 0.45f * (1.f - Life);
				Grain = 0.6f;
				break;
			default:
				Alpha = 0.85f * (1.f - Life * Life) * (D.V.Z < 0.f ? FMath::Clamp(1.f + float(D.V.Z) * 0.12f, 0.5f, 1.f) : 1.f);
				Size *= 1.f + 1.5f * Far;
				Alpha *= 1.f - 0.6f * Far;
				Grain = 1.f - Far;
				break;
			}
			const float Length = Size + Smear / 60.f;
			Xf[I] = FTransform(Q, W, FVector(Length, Size, 1.f));
			Data[0] = Alpha;
			Data[1] = Grain;
			Data[2] = D.Seed;
			Spray->SetCustomData(I, MakeArrayView(Data, 3), false);
		}
		else
		{
			Xf[I] = FTransform(FQuat::Identity, Cam, FVector::ZeroVector);
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
	if (bFoamPending) { PendingFoam.Wait(); bFoamPending = false; }
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
	if (!bStaticParamsSet || UploadedDirections != Waves->GetDirectionGeneration())
	{
		UploadedDirections = Waves->GetDirectionGeneration();
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
	{
		// Graphics G8 cinematic look: a sharper glitter lobe on High and Ultra (M_WaterV4's Glitter; a constant, no cost).
		const USailingSettings* S = USailingSettings::Get();
		const ASailboatPawn* Pawn = Cast<ASailboatPawn>(UGameplayStatics::GetPlayerPawn(this, 0));
		const bool bGlitter = S->Quality >= ESailingQuality::High && UsesCinematicLook(S->Quality, S->bCinematicLook, Pawn && Pawn->IsPhotoMode(), Pawn && Pawn->IsCaptureMode());
		WaterMaterial->SetScalarParameterValue(TEXT("Glitter"), bGlitter ? 1.f : 0.f);
	}
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
			WhitecapScaleHere()));
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
	if (!Dumped.Taken() && T > 4.0 && FParse::Param(SailingArgs::Dev(), TEXT("SailingDumpGust")))
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
double AWaterSurface::FarCapCpuSeconds = 0.0;
int32 AWaterSurface::FarCapSlotsHeld = 0;

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

void AWaterSurface::UpdateFoamGrid(const FDetailUploadPtr& Done)
{
	// W4 (docs/water-4). Upload the last step if it is done; then step again from this detail frame.
	if (bFoamPending && PendingFoam.IsReady())
	{
		FFoamFrame Frame = PendingFoam.Consume();
		bFoamPending = false;
		if (Frame.N > 0 && WaterMaterial)
		{
			if (!FoamGridMap || FoamGridMap->GetSizeX() != Frame.N)
			{
				FoamGridMap = MakeFloatMap(Frame.N, Frame.N, PF_R32_FLOAT, false);
				WaterMaterial->SetTextureParameterValue(TEXT("FoamGrid"), FoamGridMap);
			}
			UploadFloats(FoamGridMap, Frame.Pixels, Frame.N, Frame.N, 1);
			WaterMaterial->SetVectorParameterValue(TEXT("FoamGridRect"), FLinearColor(Frame.X0, Frame.Y0, Frame.Size, 1.f));
		}
	}
	static SailingArgs::FCachedFlag NoFoamGridArg(TEXT("SailingNoFoamGrid"));
	if (NoFoamGridArg.Get() || Tier < 1)
	{
		if (WaterMaterial) WaterMaterial->SetVectorParameterValue(TEXT("FoamGridRect"), FLinearColor(0.f, 0.f, 64.f, 0.f));
		return;
	}
	if (bFoamPending || !Done || Done->JCap.empty() || Done->N <= 0) return;
	// At the short waves' 30 Hz (the caps it takes in change at that rate; the residual foam fades and drifts over seconds).
	const double FoamNow = GetSimTime();
	if (FoamStepAt >= 0.0 && FoamNow >= FoamStepAt && FoamNow - FoamStepAt < 0.999 * kDetailStep) return;
	FoamStepAt = FoamNow;
	if (!FoamState) FoamState = MakeShared<FFoamGrid, ESPMode::ThreadSafe>();
	const FVector CamCm = UGameplayStatics::GetPlayerCameraManager(this, 0) ? UGameplayStatics::GetPlayerCameraManager(this, 0)->GetCameraLocation() : GetActorLocation();
	const FVector2D Cam = SailingFrame::ToMap(GetWorld(), CamCm);
	const double T = GetSimTime();
	FVector2D Drift = FVector2D::ZeroVector;
	if (const FWindField* Wind = GetWind())
	{
		// Foam drifts with the surface: the wind drift is about 3% of the wind speed (Wu 1975), plus the Stokes drift the
		// small waves add; 3.5% here.
		const Vec3 V = Wind->VelocityAt(Vec3(Cam.X, Cam.Y, 10.0), T);
		Drift = FVector2D(V.X, V.Y) * 0.035;
	}
	TSharedPtr<FFoamGrid, ESPMode::ThreadSafe> G = FoamState;
	const FDetailUploadPtr D = Done;
	const float Thr = Done->CapThr[0];
	bFoamPending = true;
	TSharedPtr<const TArray<float>, ESPMode::ThreadSafe> WakeF = WakeFoamPixels;
	const FVector2D WakeO = WakeFoamOrigin;
	const float WakeC = WakeFoamCell;
	const int32 WakeN = WakeFoamN;
	PendingFoam = Async(EAsyncExecution::ThreadPool, [G, D, Cam, T, Drift, Thr, WakeF, WakeO, WakeC, WakeN]() -> FFoamFrame
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(Sailing_WaterFoamGrid);
		FFoamGrid& F = *G;
		const int32 N = F.N;
		if (F.F.Num() != N * N) F.F.Init(0.f, N * N);
		const double Dt = F.LastTime < 0.0 ? 0.0 : FMath::Clamp(T - F.LastTime, 0.0, 0.25);
		F.LastTime = T;
		// Recentre on the camera in whole cells (the foam stays put in the world).
		const int32 NX = FMath::FloorToInt(Cam.X / F.Cell) - N / 2, NY = FMath::FloorToInt(Cam.Y / F.Cell) - N / 2;
		const int32 SX = NX - F.OX, SY = NY - F.OY;
		TArray<float> Next;
		Next.Init(0.f, N * N);
		// Residual foam fades with an e-folding time of about 4 s (Monahan and Lu 1990: stage-B whitecaps; Callaghan,
		// de Leeuw, Cohen and O'Dowd 2008 give 2-6 s from video, longer for bigger breakers).
		const float Keep = float(FMath::Exp(-Dt / 4.0));
		// Moved with the drift (semi-Lagrangian: each cell takes the foam from upwind, bilinear): a cap's patch trails off
		// downwind as it fades, and M_WaterV4 draws it through the streak pattern along the wind.
		const float BX = float(-Drift.X * Dt / F.Cell), BY = float(-Drift.Y * Dt / F.Cell);
		auto Old = [&F, N](int32 R, int32 C) { return (R >= 0 && R < N && C >= 0 && C < N) ? F.F[R * N + C] : 0.f; };
		for (int32 R = 0; R < N; ++R)
			for (int32 C = 0; C < N; ++C)
			{
				const float SR = float(R + SX) + BX, SC = float(C + SY) + BY;
				const int32 R0 = FMath::FloorToInt(SR), C0 = FMath::FloorToInt(SC);
				const float FR = SR - R0, FC = SC - C0;
				const float V = FMath::Lerp(FMath::Lerp(Old(R0, C0), Old(R0, C0 + 1), FC), FMath::Lerp(Old(R0 + 1, C0), Old(R0 + 1, C0 + 1), FC), FR);
				Next[R * N + C] = V * Keep;
			}
		F.OX = NX;
		F.OY = NY;
		// The caps feed it: the whitecap Jacobian of the chop (as M_WaterV4's jd, with the drawn fold scale) against the
		// nearest solved threshold, the long trains' fold left out (they fold in tens of metres, the grid holds 64).
		const int32 DN = D->N;
		const float Tile = D->Tile;
		const float Ks = FMath::Min(D->CapShort, 2.f);
		// Each column's detail and wake columns, worked out once for every row.
		TArray<int32> DCs, WCs;
		DCs.SetNumUninitialized(N);
		WCs.SetNumUninitialized(N);
		for (int32 C = 0; C < N; ++C)
		{
			const double Y = (F.OY + C + 0.5) * F.Cell;
			DCs[C] = ((FMath::FloorToInt(float(Y / Tile * DN)) % DN) + DN) % DN;
			WCs[C] = WakeN > 0 ? FMath::FloorToInt(float((Y - WakeO.Y) / WakeC)) : -1;
		}
		for (int32 R = 0; R < N; ++R)
		{
			const double X = (F.OX + R + 0.5) * F.Cell;
			const int32 DR = ((FMath::FloorToInt(float(X / Tile * DN)) % DN) + DN) % DN;
			const int32 WR = WakeN > 0 ? FMath::FloorToInt(float((X - WakeO.X) / WakeC)) : -1;
			const bool bWakeRow = WakeF && WR >= 0 && WR < WakeN;
			for (int32 C = 0; C < N; ++C)
			{
				const float Jd = 1.f - Ks * (1.f - D->JCap[DR * DN + DCs[C]]);
				const float Jt = 1.f - D->FoldScale * (1.f - Jd);
				float Src = FMath::Clamp((Thr - Jt) / 0.05f + 0.5f, 0.f, 1.f);
				// The boats' wash (the wake grid's foam, as M_WaterV4's wakeBreak without its bubble pattern).
				const int32 WC = WCs[C];
				if (bWakeRow && WC >= 0 && WC < WakeN) Src = FMath::Max(Src, FMath::Clamp((*WakeF)[4 * (WR * WakeN + WC) + 1] * 2.f - 0.4f, 0.f, 1.f) * 0.85f);
				float& V = Next[R * N + C];
				V = FMath::Max(V, Src);
			}
		}
		F.F = Next;
		FFoamFrame Out;
		Out.Pixels = MoveTemp(Next);
		Out.N = N;
		Out.X0 = float(F.OX * F.Cell);
		Out.Y0 = float(F.OY * F.Cell);
		Out.Size = N * F.Cell;
		return Out;
	});
}