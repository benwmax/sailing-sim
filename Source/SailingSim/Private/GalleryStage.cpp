#include "GalleryStage.h"
#include "FreeCamera.h"
#include "SailboatPawn.h"
#include "SailingFrame.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "Camera/CameraComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "Rendering/NaniteResources.h"
#include "StaticMeshResources.h"
#include "UnrealClient.h"
#include "BenchRunner.h"
#include "EngineGlobals.h"
#include "ImageUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "TimerManager.h"

namespace
{
	constexpr float kStudioUpCm = 100000.f;   // 1 km over the water: nobody sails there, and the set hides the sky
	constexpr float kCameraFovDeg = 60.f;

	FSailConditions LightConditions(EGalleryLight L)
	{
		// Inputs/gallery/brief.md section 4: noon fair, golden hour clear, overcast at three.
		FSailConditions C;
		C.PresetId = NAME_None;
		C.WindKn = 8.f;
		C.GustKn = 11.f;
		C.LocalHour = L == EGalleryLight::GoldenHour ? 19.f : L == EGalleryLight::Overcast ? 15.f : 12.f;
		C.Sky = L == EGalleryLight::GoldenHour ? ESailSky::Clear : L == EGalleryLight::Overcast ? ESailSky::Overcast : ESailSky::Fair;
		return C;
	}

	URectLightComponent* MakeLight(AActor* Owner, USceneComponent* Parent, const TCHAR* Name)
	{
		URectLightComponent* L = Owner->CreateDefaultSubobject<URectLightComponent>(Name);
		L->SetupAttachment(Parent);
		L->SetMobility(EComponentMobility::Movable);
		// A channel the world doesn't use: the studio's lights light the studio only.
		L->LightingChannels.bChannel0 = false;
		L->LightingChannels.bChannel1 = true;
		L->SetIntensityUnits(ELightUnits::Lumens);
		L->bAffectsWorld = true;
		L->SetCastShadows(true);
		return L;
	}
}

AGalleryStage::AGalleryStage()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = true;
	SetReplicates(false);
	Turntable = CreateDefaultSubobject<USceneComponent>(TEXT("Turntable"));
	RootComponent = Turntable;
	Turntable->SetMobility(EComponentMobility::Movable);
	Display = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Display"));
	Display->SetupAttachment(Turntable);
	Display->SetMobility(EComponentMobility::Movable);
	Display->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Display->bCastDynamicShadow = true;
	Cyclorama = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Cyclorama"));
	Cyclorama->SetupAttachment(Turntable);
	Cyclorama->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Cyclorama->SetCanEverAffectNavigation(false);
	Key = MakeLight(this, Turntable, TEXT("Key"));
	Fill = MakeLight(this, Turntable, TEXT("Fill"));
	Rim = MakeLight(this, Turntable, TEXT("Rim"));
}

float AGalleryStage::FramingDistanceCm(float RadiusCm, float VerticalFovDeg, float FillShare)
{
	// The bounding sphere's angular radius is half of Fill of the view's height.
	const float Half = FMath::DegreesToRadians(FMath::Clamp(VerticalFovDeg, 5.f, 170.f)) * 0.5f * FMath::Clamp(FillShare, 0.05f, 1.f);
	return FMath::Max(RadiusCm, 1.f) / FMath::Sin(Half);
}

bool AGalleryStage::Floats(const FGalleryItem& I)
{
	return I.Category == TEXT("Buoys & marks") || I.Category == TEXT("Other vessels");
}

void AGalleryStage::Open(APlayerController* PC)
{
	if (bOpen || !PC) return;
	bOpen = true;
	Player = PC;
	PreviousView = PC->GetViewTarget();
	GraphicsOnOpen = SailGallery::FGraphicsSnapshot::Capture();
	// A 6 cm deck plate needs the near plane in close.
	SavedNearClip = GNearClippingPlane;
	GNearClippingPlane = 1.f;
	EnsureMaterials();
	// The studio 1 km over the player's boat; the lake presets on open water near her.
	const APawn* Boat = PC->GetPawn();
	const FVector At = Boat ? Boat->GetActorLocation() : FVector::ZeroVector;
	const FVector2D Map = SailingFrame::ToMap(GetWorld(), At);
	FVector2D Open(Map.X + 150.0, Map.Y);
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>(); GM && GM->GetLake().IsLoaded())
	{
		const Sailing::FLakeTerrain& Terrain = GM->GetLake().Terrain;
		Open = SailShowroom::FindOpenWater([&Terrain](double X, double Y) { return Terrain.HeightAt(X, Y); }, Open.X, Open.Y, 3.0, 40.0);
	}
	LakeCentre = SailingFrame::ToWorld(GetWorld(), Open.X, Open.Y, 0.0);
	StudioCentre = FVector(At.X, At.Y, LakeCentre.Z + kStudioUpCm);
	FActorSpawnParameters P;
	P.ObjectFlags |= RF_Transient;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Camera = GetWorld()->SpawnActor<AFreeCamera>(StudioCentre + FVector(-1000.f, 0.f, 300.f), FRotator::ZeroRotator, P);
	if (Camera)
	{
		Camera->GetCamera()->SetFieldOfView(kCameraFovDeg);
		Camera->Limits.LeashM = 1e6;           // the stage is the anchor; the camera only orbits it
		Camera->Limits.CeilingM = 5000.0;
		Camera->Limits.WaterClearM = 0.3;
		Camera->SetAnchor(this);
		PC->SetViewTargetWithBlend(Camera, 0.4f, VTBlend_EaseInOut, 2.f);
	}
	SetLight(EGalleryLight::Studio);
	UE_LOG(LogSailing, Display, TEXT("Gallery: open, studio at %.0f m over the water, the lake presets at (%.0f, %.0f)"), kStudioUpCm / 100.f, Open.X, Open.Y);
}

void AGalleryStage::Close()
{
	if (!bOpen) return;
	bOpen = false;
	if (ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr; GM && bPreviewed) GM->EndPreview(false);
	bPreviewed = false;
	GNearClippingPlane = SavedNearClip;
	if (APlayerController* PC = Player.Get())
	{
		AActor* Back = PreviousView.IsValid() ? PreviousView.Get() : PC->GetPawn();
		if (Back) PC->SetViewTargetWithBlend(Back, 0.4f, VTBlend_EaseInOut, 2.f);
	}
	if (Load.IsValid()) Load->CancelHandle();
	Load.Reset();
	Shown.Reset();
	if (Camera) Camera->Destroy();
	Camera = nullptr;
	if (BoatDisplay) BoatDisplay->Destroy();
	BoatDisplay = nullptr;
	CompareStep = 0;
}

void AGalleryStage::EndPlay(const EEndPlayReason::Type Reason)
{
	if (bCaptureWaiting) UGameViewportClient::OnScreenshotCaptured().Remove(CaptureHandle);
	if (bOpen && Reason != EEndPlayReason::EndPlayInEditor && Reason != EEndPlayReason::Quit) Close();
	else if (bOpen) GNearClippingPlane = SavedNearClip;
	Super::EndPlay(Reason);
}

void AGalleryStage::RestoreGraphics()
{
	GraphicsOnOpen.Restore(GetWorld(), true);
}

void AGalleryStage::Select(const FGalleryItem& InItem)
{
	Pending = InItem;
	SelectDebounce.DelaySeconds = 0.2;
	SelectDebounce.Changed(FPlatformTime::Seconds());
}

void AGalleryStage::Show(const FGalleryItem& InItem)
{
	Item = InItem;
	PanCm = FVector2D::ZeroVector;
	if (Item.BoatType >= 0)
	{
		Display->SetStaticMesh(nullptr);
		ShowBoat();
		return;
	}
	if (BoatDisplay) { BoatDisplay->Destroy(); BoatDisplay = nullptr; }
	TArray<FSoftObjectPath> Paths = { Item.Mesh };
	if (Item.Light.IsValid()) Paths.Add(Item.Light);
	if (Item.Far.IsValid()) Paths.Add(Item.Far);
	if (Load.IsValid()) Load->CancelHandle();
	LoadStart = FPlatformTime::Seconds();
	Load = UAssetManager::GetStreamableManager().RequestAsyncLoad(Paths, FStreamableDelegate());
	if (!Load.IsValid() || Load->HasLoadCompleted()) FinishLoad();
}

void AGalleryStage::FinishLoad()
{
	const double Ms = (FPlatformTime::Seconds() - LoadStart) * 1000.0;
	// The shown asset stays resident; the one before is let go.
	Shown = Load;
	Load.Reset();
	ApplyMesh();
	ApplyFraming(false);
	const FGalleryStats S = GetStats();
	UE_LOG(LogSailing, Display, TEXT("Gallery show %s: load %.0f ms; %d triangles%s, %d LODs, %d materials, %.2f x %.2f x %.2f m"), *Item.Name, Ms,
		S.Triangles, S.bNanite ? TEXT(" (Nanite)") : TEXT(""), S.Lods, S.Materials, S.SizeM.X, S.SizeM.Y, S.SizeM.Z);
}

UStaticMesh* AGalleryStage::MeshForDetail() const
{
	UStaticMesh* Base = Cast<UStaticMesh>(Item.Mesh.ResolveObject());
	if (DetailMode == EGalleryDetail::LightTwin && Item.Light.IsValid()) if (UStaticMesh* L = Cast<UStaticMesh>(Item.Light.ResolveObject())) return L;
	if (DetailMode == EGalleryDetail::FarTwin && Item.Far.IsValid()) if (UStaticMesh* F = Cast<UStaticMesh>(Item.Far.ResolveObject())) return F;
	return Base;
}

bool AGalleryStage::IsBoatShown() const
{
	return Item.BoatType >= 0 && BoatDisplay != nullptr;
}

void AGalleryStage::ShowBoat()
{
	// G3 (Inputs/gallery/brief.md section 7): the boat whole, as the player's: a traffic-mode pawn (the ghost's path, so the
	// hull, rig, sails, crew and livery are the same assembly) that nothing steps, posed still on the turntable.
	const double Start = FPlatformTime::Seconds();
	if (BoatDisplay && BoatDisplay->GetBoatTypeIndex() != Item.BoatType) { BoatDisplay->Destroy(); BoatDisplay = nullptr; }
	if (!BoatDisplay)
	{
		const FTransform At(GetActorRotation(), GetActorLocation());
		BoatDisplay = GetWorld()->SpawnActorDeferred<ASailboatPawn>(ASailboatPawn::StaticClass(), At, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (!BoatDisplay) return;
		BoatDisplay->bTrafficBoat = true;
		BoatDisplay->bGalleryDisplay = true; // the player's models (the hero J/22), not the AI boats' lighter ones
		BoatDisplay->AutoPossessPlayer = EAutoReceiveInput::Disabled;
		BoatDisplay->AutoPossessAI = EAutoPossessAI::Disabled;
		BoatDisplay->FinishSpawning(At);
		BoatDisplay->InitTraffic(Item.BoatType, 0.0, 0.0, 0.0);
	}
	ApplyMesh();
	ApplyFraming(false);
	const FGalleryStats S = GetStats();
	UE_LOG(LogSailing, Display, TEXT("Gallery show %s (whole boat): built in %.0f ms; %d triangles in %d parts, %.2f x %.2f x %.2f m"), *Item.Name,
		(FPlatformTime::Seconds() - Start) * 1000.0, S.Triangles, S.Lods, S.SizeM.X, S.SizeM.Y, S.SizeM.Z);
}

void AGalleryStage::PoseBoat()
{
	if (!BoatDisplay) return;
	// In the studio her keel stands on the floor (her waterline her draft above it); on the lake she floats.
	const bool bStudio = LightPreset == EGalleryLight::Studio;
	const FVector Map = SailingFrame::ToMapCm(GetWorld(), GetActorLocation()) / 100.0;
	const double Draft = BoatDisplay->GetBoatModel().GetConfig().Draft;
	BoatDisplay->PoseForDisplay(Map.X, Map.Y, bStudio ? Map.Z + Draft : 0.0, FMath::DegreesToRadians(GetActorRotation().Yaw));
	TInlineComponentArray<UPrimitiveComponent*> Parts(BoatDisplay.Get());
	for (UPrimitiveComponent* P : Parts) P->SetLightingChannels(!bStudio, bStudio, false);
}

FBoxSphereBounds AGalleryStage::SubjectBounds() const
{
	if (IsBoatShown())
	{
		// The boat's own parts (not her camera boom or the cloth's invisible helpers): her static and procedural meshes.
		FBox Box(ForceInit);
		TInlineComponentArray<UMeshComponent*> Parts(BoatDisplay.Get());
		for (const UMeshComponent* P : Parts) if (P->IsVisible() && P->IsRegistered()) Box += P->Bounds.GetBox();
		if (Box.IsValid) return FBoxSphereBounds(Box);
	}
	return Display->Bounds;
}

void AGalleryStage::ApplyMesh()
{
	if (Item.BoatType >= 0)
	{
		PoseBoat();
		ApplyView();
		if (LightPreset == EGalleryLight::Studio) BuildCyclorama(FMath::Max(1500.f, float(SubjectBounds().SphereRadius) * 3.f));
		return;
	}
	UStaticMesh* Mesh = MeshForDetail();
	Display->SetStaticMesh(Mesh);
	if (!Mesh) return;
	const bool bNanite = Mesh->HasValidNaniteData();
	// The wireframe material can't draw Nanite: wire views and the fallback show the fallback mesh.
	Display->SetForceDisableNanite(bNanite && (DetailMode == EGalleryDetail::Fallback || ViewMode != EGalleryView::Lit));
	Display->SetForcedLodModel(DetailMode == EGalleryDetail::Lod && (!bNanite || Display->IsForceDisableNanite()) ? FMath::Clamp(DetailLod, 0, Mesh->GetNumLODs() - 1) + 1 : 0);
	ApplyView();
	// On the stage the mesh stands centred on the turntable, its lowest point on the floor (or, floating, its pivot at
	// the waterline on the lake).
	const FBoxSphereBounds B = Mesh->GetBounds();
	const bool bLake = LightPreset != EGalleryLight::Studio;
	const double Z = bLake && Floats(Item) ? 0.0 : -(B.Origin.Z - B.BoxExtent.Z);
	Display->SetRelativeLocation(FVector(-B.Origin.X, -B.Origin.Y, Z));
	if (!bLake) BuildCyclorama(FMath::Max(1500.f, float(B.SphereRadius) * 3.f));
}

void AGalleryStage::EnsureMaterials()
{
	if (!WireMaterial) WireMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_GalleryWire.M_GalleryWire"));
	if (!StudioMaterial) StudioMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_GalleryStudio.M_GalleryStudio"));
	if (!StudioMaterial) StudioMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
}

void AGalleryStage::ApplyView()
{
	EnsureMaterials();
	if (IsBoatShown())
	{
		// A whole boat's wire views are an overlay (her parts keep their liveries: overriding them would lose those).
		TInlineComponentArray<UMeshComponent*> Parts(BoatDisplay.Get());
		for (UMeshComponent* P : Parts) P->SetOverlayMaterial(ViewMode != EGalleryView::Lit ? WireMaterial.Get() : nullptr);
		return;
	}
	Display->EmptyOverrideMaterials();
	Display->SetOverlayMaterial(nullptr);
	if (!WireMaterial || ViewMode == EGalleryView::Lit) return;
	if (ViewMode == EGalleryView::Wireframe)
	{
		for (int32 I = 0; I < Display->GetNumMaterials(); ++I) Display->SetMaterial(I, WireMaterial);
	}
	else
	{
		Display->SetOverlayMaterial(WireMaterial);
	}
}

void AGalleryStage::SetView(EGalleryView View)
{
	ViewMode = View;
	ApplyMesh();
}

void AGalleryStage::SetDetail(EGalleryDetail Detail, int32 Lod)
{
	DetailMode = Detail;
	DetailLod = Lod;
	ApplyMesh();
}

FGalleryStats AGalleryStage::GetStats() const
{
	FGalleryStats S;
	if (IsBoatShown())
	{
		// A whole boat: her parts' triangles (Nanite's input, or LOD 0), their count (shown as LODs' place) and materials.
		S.Path = FString::Printf(TEXT("Boat %s (%d)"), *Item.Name, Item.BoatType);
		TInlineComponentArray<UStaticMeshComponent*> Parts(BoatDisplay.Get());
		for (const UStaticMeshComponent* P : Parts)
		{
			const UStaticMesh* M = P->GetStaticMesh();
			const FStaticMeshRenderData* R = M ? M->GetRenderData() : nullptr;
			if (!R || !P->IsVisible()) continue;
			++S.Lods;
			S.Materials += M->GetStaticMaterials().Num();
			if (M->HasValidNaniteData() && R->HasValidNaniteData()) { S.Triangles += int32(R->NaniteResourcesPtr->NumInputTriangles); S.bNanite = true; }
			else if (R->LODResources.Num() > 0) S.Triangles += R->LODResources[0].GetNumTriangles();
		}
		S.SizeM = SubjectBounds().BoxExtent * 2.0 / 100.0;
		if (const IConsoleVariable* SP = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))) S.ScreenPercentage = SP->GetFloat();
		return S;
	}
	const UStaticMesh* Mesh = Display->GetStaticMesh();
	if (!Mesh) return S;
	S.Path = Mesh->GetPathName();
	S.Lods = Mesh->GetNumLODs();
	S.Materials = Mesh->GetStaticMaterials().Num();
	S.SizeM = Mesh->GetBounds().BoxExtent * 2.0 / 100.0;
	S.bNanite = Mesh->HasValidNaniteData() && !Display->IsForceDisableNanite();
	S.ShownLod = FMath::Max(Display->ForcedLodModel - 1, 0);
	if (const FStaticMeshRenderData* R = Mesh->GetRenderData())
	{
		if (S.bNanite && R->HasValidNaniteData()) S.Triangles = int32(R->NaniteResourcesPtr->NumInputTriangles);
		else if (R->LODResources.IsValidIndex(S.ShownLod)) S.Triangles = R->LODResources[S.ShownLod].GetNumTriangles();
	}
	if (const IConsoleVariable* SP = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"))) S.ScreenPercentage = SP->GetFloat();
	return S;
}

void AGalleryStage::ApplyFraming(bool bKeepAngle)
{
	if (!Camera) return;
	const FBoxSphereBounds B = SubjectBounds();
	const float R = FMath::Max(float(B.SphereRadius), 2.f);
	Camera->SetAnchor(this, B.Origin - GetActorLocation());
	const float VFov = FMath::RadiansToDegrees(2.f * FMath::Atan(FMath::Tan(FMath::DegreesToRadians(kCameraFovDeg * 0.5f)) * 1080.f / 1440.f));
	const float D = FramingDistanceCm(R, VFov, 0.7f);
	FFreeCameraOrbit O;
	O.DistanceCm = D;
	O.MinDistanceCm = D / 6.f;     // zoom 0.35x to 6x
	O.MaxDistanceCm = D / 0.35f;
	O.PitchDeg = -20.f;            // 20 deg above: pitch -10 (under) to 80 deg (over)
	O.MinPitchDeg = -80.f;
	O.MaxPitchDeg = 10.f;
	O.YawDeg = 135.f + 180.f;      // the three-quarter view
	O.SpinDegPerSec = bAutoSpin ? 6.f : 0.f;   // the screen's Auto spin
	O.SpinIdleSeconds = 4.f;
	O.EaseSeconds = 0.4f;
	// The left panel takes a quarter of the screen (PanelShare): the asset sits in the middle of the rest (pivot left of
	// the view); full screen, in the middle.
	O.LateralOffsetCm = -PanelShare * D * FMath::Tan(FMath::DegreesToRadians(kCameraFovDeg * 0.5f)) + float(PanCm.X);
	O.UpOffsetCm = float(PanCm.Y);
	if (bKeepAngle)
	{
		const FFreeCameraOrbit& Was = Camera->GetOrbit();
		O.DistanceCm = FMath::Clamp(Was.DistanceCm, O.MinDistanceCm, O.MaxDistanceCm);
		O.YawDeg = float(Camera->GetActorRotation().Yaw);
		O.PitchDeg = float(Camera->GetActorRotation().Pitch);
	}
	Camera->SetOrbit(O);
	// The studio's lights about the asset: key high on the right, fill low on the left, rim behind.
	if (LightPreset == EGalleryLight::Studio)
	{
		const FVector T = B.Origin;
		auto Place = [&](URectLightComponent* L, float YawDeg, float ElevDeg, float DistR, float Lumens)
		{
			const FVector Dir = FRotator(ElevDeg, YawDeg, 0.f).Vector();
			const FVector At = T - Dir * (DistR * R);
			L->SetWorldLocationAndRotation(At, (T - At).Rotation());
			L->SetSourceWidth(R * 1.5f);
			L->SetSourceHeight(R * 1.5f);
			L->SetAttenuationRadius(R * 12.f);
			L->SetIntensity(Lumens * FMath::Square(DistR * R / 300.f));
		};
		Place(Key, 135.f + 180.f + 45.f, -35.f, 3.f, 6000.f);
		Place(Fill, 135.f + 180.f - 70.f, -12.f, 3.5f, 1800.f);
		Place(Rim, 135.f, -40.f, 3.f, 4000.f);
	}
}

void AGalleryStage::Orbit(const FVector2D& DeltaDeg)
{
	if (Camera) Camera->AddLook(DeltaDeg);
}

void AGalleryStage::Zoom(float Steps)
{
	if (Camera) Camera->StepSpeed(FMath::RoundToInt32(Steps));
}

void AGalleryStage::Pan(const FVector2D& DeltaCm)
{
	const float R = FMath::Max(float(SubjectBounds().SphereRadius), 2.f);
	PanCm.X = FMath::Clamp(PanCm.X + DeltaCm.X, -R, R);
	PanCm.Y = FMath::Clamp(PanCm.Y + DeltaCm.Y, -R, R);
	ApplyFraming(true);
}

void AGalleryStage::ResetView()
{
	PanCm = FVector2D::ZeroVector;
	ApplyFraming(false);
}

void AGalleryStage::SetAutoSpin(bool bOn)
{
	bAutoSpin = bOn;
	ApplyFraming(true);
}

void AGalleryStage::SetPanelShare(float Share)
{
	PanelShare = Share;
	ApplyFraming(true);
}

float AGalleryStage::GetZoom() const
{
	if (!Camera) return 1.f;
	const FFreeCameraOrbit& O = Camera->GetOrbit();
	return O.DistanceCm > 0.f ? O.MinDistanceCm * 6.f / O.DistanceCm : 1.f;
}

void AGalleryStage::SetLight(EGalleryLight Light)
{
	LightPreset = Light;
	PlaceForLight();
	ApplyMesh();
	ApplyFraming(true);
}

void AGalleryStage::PlaceForLight()
{
	const bool bStudio = LightPreset == EGalleryLight::Studio;
	SetActorLocation(bStudio ? StudioCentre : LakeCentre);
	Cyclorama->SetVisibility(bStudio);
	for (URectLightComponent* L : { Key.Get(), Fill.Get(), Rim.Get() }) L->SetVisibility(bStudio);
	// In the studio only the studio's lights (channel 1) and the sky light reach the asset; on the lake the sun does.
	Display->SetLightingChannels(!bStudio, bStudio, false);
	Cyclorama->SetLightingChannels(false, true, false);
	if (Camera)
	{
		Camera->Limits.WaterClearM = bStudio ? 0.0 : 0.3;
		// The game's exposure follows the outdoor light (an incident meter); the closed studio meters its own frame.
		FPostProcessSettings& PP = Camera->GetCamera()->PostProcessSettings;
		PP.bOverride_AutoExposureMethod = PP.bOverride_AutoExposureMinBrightness = PP.bOverride_AutoExposureMaxBrightness = bStudio;
		PP.bOverride_AutoExposureBias = bStudio;
		PP.AutoExposureMethod = AEM_Histogram;
		PP.AutoExposureMinBrightness = -6.f;
		PP.AutoExposureMaxBrightness = 20.f;
		PP.AutoExposureBias = 0.f;
	}
	ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	if (bStudio)
	{
		if (bPreviewed) GM->EndPreview(false);
		bPreviewed = false;
		return;
	}
	GM->PreviewConditions(LightConditions(LightPreset));
	bPreviewed = true;
}

void AGalleryStage::BuildCyclorama(float RadiusCm)
{
	if (FMath::IsNearlyEqual(RadiusCm, CycloramaRadiusCm, 1.f)) return;
	CycloramaRadiusCm = RadiusCm;
	// A closed room turned about the vertical: a flat floor, a cove curving up into the wall, the wall, and a dome over
	// it, so the asset is set against grey at any angle (and the sky is shut out).
	const float R0 = RadiusCm, Rf = 0.6f * RadiusCm, Rw = R0 + Rf, H = 1.5f * RadiusCm;
	TArray<FVector2D> Profile = { FVector2D(0.f, 0.f), FVector2D(R0 * 0.5f, 0.f), FVector2D(R0, 0.f) };
	for (int32 I = 1; I <= 8; ++I)
	{
		const float A = -0.5f * PI + 0.5f * PI * I / 8.f;
		Profile.Add(FVector2D(R0 + Rf * FMath::Cos(A), Rf + Rf * FMath::Sin(A)));
	}
	Profile.Add(FVector2D(Rw, H));
	for (int32 I = 1; I <= 12; ++I)
	{
		const float A = 0.5f * PI * I / 12.f;
		Profile.Add(FVector2D(Rw * FMath::Cos(A), H + Rw * FMath::Sin(A)));
	}
	constexpr int32 Segs = 48;
	TArray<FVector> V, N;
	TArray<FVector2D> UV;
	TArray<int32> T;
	for (int32 P = 0; P < Profile.Num(); ++P)
	{
		const FVector2D Tan = (Profile[FMath::Min(P + 1, Profile.Num() - 1)] - Profile[FMath::Max(P - 1, 0)]).GetSafeNormal();
		const FVector2D In(-Tan.Y, Tan.X); // the profile's inward normal (up on the floor, in on the wall, down under the dome)
		for (int32 S = 0; S <= Segs; ++S)
		{
			const float A = 2.f * PI * S / Segs;
			const FVector Radial(FMath::Cos(A), FMath::Sin(A), 0.f);
			V.Add(Radial * Profile[P].X + FVector(0.f, 0.f, Profile[P].Y));
			N.Add((Radial * In.X + FVector(0.f, 0.f, In.Y)).GetSafeNormal());
			UV.Add(FVector2D(float(S) / Segs, float(P) / (Profile.Num() - 1)));
		}
	}
	for (int32 P = 0; P + 1 < Profile.Num(); ++P)
	{
		for (int32 S = 0; S < Segs; ++S)
		{
			const int32 A = P * (Segs + 1) + S, B = A + 1, C = A + Segs + 1, D = C + 1;
			T.Append({ A, B, C, B, D, C });
		}
	}
	Cyclorama->CreateMeshSection(0, V, T, N, UV, TArray<FColor>(), TArray<FProcMeshTangent>(), false);
	if (StudioMaterial) Cyclorama->SetMaterial(0, StudioMaterial);
}

void AGalleryStage::SetTier(uint8 Tier)
{
	USailingSettings::Get()->Quality = ESailingQuality(FMath::Clamp(int32(Tier), 0, 3));
	if (ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>()) GM->ApplyQualitySettings();
}

void AGalleryStage::StartCompare(uint8 TierA, uint8 TierB)
{
	if (!Camera || CompareStep > 0) return;
	CompareTiers[0] = TierA;
	CompareTiers[1] = TierB;
	CompareRestoreTier = uint8(USailingSettings::Get()->Quality);
	// The camera holds still while the tiers settle (Lumen and the virtual shadow maps take about a second).
	FFreeCameraOrbit O = Camera->GetOrbit();
	O.SpinDegPerSec = 0.f;
	O.YawDeg = float(Camera->GetActorRotation().Yaw);
	O.PitchDeg = float(Camera->GetActorRotation().Pitch);
	Camera->SetOrbit(O);
	CompareStep = 1;
	CompareAt = FPlatformTime::Seconds();
	SetTier(TierA);
}

void AGalleryStage::RequestCapture()
{
	// Reading the viewport back directly gave black frames on Metal: the engine's own screenshot gives the shown frame.
	bCaptured = false;
	bCaptureWaiting = true;
	CaptureHandle = UGameViewportClient::OnScreenshotCaptured().AddUObject(this, &AGalleryStage::OnCaptured);
	FScreenshotRequest::RequestScreenshot(false);
}

void AGalleryStage::OnCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors)
{
	UGameViewportClient::OnScreenshotCaptured().Remove(CaptureHandle);
	CapturedNow = Colors;
	CapturedNowSize = FIntPoint(Width, Height);
	bCaptureWaiting = false;
	bCaptured = true;
}

UTexture2D* AGalleryStage::MakeTexture(const TArray<FColor>& Pixels, FIntPoint Size)
{
	if (Pixels.Num() != Size.X * Size.Y || Size.X <= 0) return nullptr;
	UTexture2D* Tex = UTexture2D::CreateTransient(Size.X, Size.Y, PF_B8G8R8A8);
	if (!Tex) return nullptr;
	void* Data = Tex->GetPlatformData()->Mips[0].BulkData.Lock(LOCK_READ_WRITE);
	FMemory::Memcpy(Data, Pixels.GetData(), Pixels.Num() * sizeof(FColor));
	Tex->GetPlatformData()->Mips[0].BulkData.Unlock();
	Tex->UpdateResource();
	return Tex;
}

void AGalleryStage::TickCompare()
{
	if (CompareStep == 0 || bCaptureWaiting) return;
	if (!bCaptured)
	{
		// Each tier settles 1.5 s, then its frame is captured.
		if (FPlatformTime::Seconds() - CompareAt >= 1.5) RequestCapture();
		return;
	}
	bCaptured = false;
	if (CompareStep == 1)
	{
		CapturedA = CapturedNow;
		CaptureSize = CapturedNowSize;
		SetTier(CompareTiers[1]);
		CompareStep = 2;
		CompareAt = FPlatformTime::Seconds();
		return;
	}
	CapturedB = CapturedNow;
	const FIntPoint SizeB = CapturedNowSize;
	SetTier(CompareRestoreTier);
	CompareStep = 0;
	CompareA = MakeTexture(CapturedA, CaptureSize);
	CompareB = SizeB == CaptureSize ? MakeTexture(CapturedB, SizeB) : nullptr;
	UE_LOG(LogSailing, Display, TEXT("Gallery compare: tiers %d and %d captured at %d x %d"), CompareTiers[0], CompareTiers[1], CaptureSize.X, CaptureSize.Y);
	if (OnCompareDone && CompareB) OnCompareDone(CapturedA, CapturedB, CaptureSize);
	// Back to turning.
	if (Camera)
	{
		FFreeCameraOrbit O = Camera->GetOrbit();
		O.SpinDegPerSec = 6.f;
		O.YawDeg = float(Camera->GetActorRotation().Yaw);
		O.PitchDeg = float(Camera->GetActorRotation().Pitch);
		Camera->SetOrbit(O);
	}
}

void AGalleryStage::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bOpen) return;
	if (SelectDebounce.Fire(FPlatformTime::Seconds())) Show(Pending);
	if (Load.IsValid() && Load->HasLoadCompleted()) FinishLoad();
	if (Camera) Camera->Update(DeltaSeconds, FFreeCameraInput());
	TickCompare();
}

int32 AGalleryStage::TierFromName(const FString& Name)
{
	static const TCHAR* Names[] = { TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") };
	for (int32 I = 0; I < 4; ++I) if (Name.Equals(Names[I], ESearchCase::IgnoreCase)) return I;
	return -1;
}

TArray<FColor> AGalleryStage::CompareSplit(const TArray<FColor>& A, const TArray<FColor>& B, FIntPoint Size)
{
	TArray<FColor> Out;
	if (A.Num() != Size.X * Size.Y || B.Num() != A.Num()) return Out;
	Out.SetNumUninitialized(A.Num());
	const int32 Mid = Size.X / 2;
	for (int32 Y = 0; Y < Size.Y; ++Y)
	{
		for (int32 X = 0; X < Size.X; ++X)
		{
			const int32 I = Y * Size.X + X;
			FColor C = FMath::Abs(X - Mid) <= 1 ? FColor::White : (X < Mid ? A[I] : B[I]);
			C.A = 255;
			Out[I] = C;
		}
	}
	return Out;
}

AGalleryStage* AGalleryStage::OpenFromArgs(APlayerController* PC)
{
	FString Want;
	if (!PC || !FParse::Value(SailingArgs::Dev(), TEXT("SailingGallery="), Want, false)) return nullptr;
	if (!USailingSettings::DeveloperTools())
	{
		UE_LOG(LogSailing, Warning, TEXT("Gallery: developer tools are off (bDeveloperTools in GameUserSettings.ini)"));
		return nullptr;
	}
	FActorSpawnParameters P;
	P.ObjectFlags |= RF_Transient;
	AGalleryStage* S = PC->GetWorld()->SpawnActor<AGalleryStage>(FVector::ZeroVector, FRotator::ZeroRotator, P);
	if (!S) return nullptr;
	S->Open(PC);
	const TArray<FGalleryItem> Items = SailGallery::ScanRegistry();
	const FGalleryItem* Item = SailGallery::Find(Items, Want);
	if (!Item)
	{
		UE_LOG(LogSailing, Warning, TEXT("Gallery: no asset %s; showing the first"), *Want);
		Item = Items.FindByPredicate([](const FGalleryItem& I) { return I.BoatType < 0; });
	}
	FString Arg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingGalleryLight="), Arg))
	{
		S->SetLight(Arg == TEXT("Noon") ? EGalleryLight::Noon : Arg == TEXT("GoldenHour") ? EGalleryLight::GoldenHour : Arg == TEXT("Overcast") ? EGalleryLight::Overcast : EGalleryLight::Studio);
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingGalleryView="), Arg))
	{
		S->ViewMode = Arg == TEXT("Wireframe") ? EGalleryView::Wireframe : Arg == TEXT("LitWire") ? EGalleryView::LitWire : EGalleryView::Lit;
	}
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingGalleryDetail="), Arg))
	{
		if (Arg.StartsWith(TEXT("Lod"))) { S->DetailMode = EGalleryDetail::Lod; S->DetailLod = FCString::Atoi(*Arg.Mid(3)); }
		else S->DetailMode = Arg == TEXT("Fallback") ? EGalleryDetail::Fallback : Arg == TEXT("Light") ? EGalleryDetail::LightTwin : Arg == TEXT("Far") ? EGalleryDetail::FarTwin : EGalleryDetail::Auto;
	}
	if (Item) S->Show(*Item);
	FString Cmp, A, B;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingGalleryCompare="), Cmp, false) && Cmp.Split(TEXT(","), &A, &B) && TierFromName(A) >= 0 && TierFromName(B) >= 0)
	{
		FString Shot = TEXT("gallery");
		FParse::Value(SailingArgs::Dev(), TEXT("SailingShot="), Shot);
		S->OnCompareDone = [Shot](const TArray<FColor>& CA, const TArray<FColor>& CB, FIntPoint Size)
		{
			TArray64<uint8> Png;
			const TArray<FColor> Split = CompareSplit(CA, CB, Size);
			if (Split.Num() == 0) return;
			FImageUtils::PNGCompressImageArray(Size.X, Size.Y, TArrayView64<const FColor>(Split.GetData(), Split.Num()), Png);
			const FString Path = FPaths::ProjectSavedDir() / TEXT("Bench") / (Shot + TEXT("-compare.png"));
			FFileHelper::SaveArrayToFile(Png, *Path);
			UE_LOG(LogSailing, Display, TEXT("Gallery compare saved to %s"), *Path);
		};
		const uint8 TA = uint8(TierFromName(A)), TB = uint8(TierFromName(B));
		TWeakObjectPtr<AGalleryStage> Weak = S;
		FTimerHandle Later;
		PC->GetWorldTimerManager().SetTimer(Later, FTimerDelegate::CreateWeakLambda(S, [Weak, TA, TB]() { if (Weak.IsValid()) Weak->StartCompare(TA, TB); }), 5.f, false);
	}
	return S;
}
