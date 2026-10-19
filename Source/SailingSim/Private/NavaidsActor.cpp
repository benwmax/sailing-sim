#include "NavaidsActor.h"
#include "SailingFrame.h"
#include "FarLightsActor.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingEnvironment.h"
#include "SailingSettings.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

using namespace Sailing;

ANavaidsActor::ANavaidsActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(TEXT("/Engine/BasicShapes/Cone.Cone"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BasicMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Emissive(TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	Cube = CubeMesh.Object;
	Cylinder = CylinderMesh.Object;
	Cone = ConeMesh.Object;
	Sphere = SphereMesh.Object;
	ShapeMaterial = BasicMaterial.Object;
	EmissiveMaterial = Emissive.Object;
}

void ANavaidsActor::BeginPlay()
{
	Super::BeginPlay();
	Build();
}

UInstancedStaticMeshComponent* ANavaidsActor::MakeIsm(UStaticMesh* Mesh, const FLinearColor& Color, USceneComponent* Parent, bool bEmissive)
{
	UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(this);
	Ism->SetupAttachment(Parent);
	Ism->SetStaticMesh(Mesh);
	Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ism->SetCastShadow(!bEmissive);
	Ism->SetCullDistances(0, bEmissive ? 0 : 600000); // marks fade beyond 6 km; lights are culled by range in Tick
	UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(bEmissive ? EmissiveMaterial.Get() : ShapeMaterial.Get(), this);
	Mid->SetVectorParameterValue(TEXT("Color"), Color);
	if (bEmissive) Mid->SetScalarParameterValue(TEXT("Intensity"), 250.f);
	Ism->SetMaterial(0, Mid);
	Ism->RegisterComponent();
	Meshes.Add(Ism);
	return Ism;
}

UInstancedStaticMeshComponent* ANavaidsActor::ModelIsm(const TCHAR* Name, bool bFloating)
{
	const FString Key = FString::Printf(TEXT("%s_%d"), Name, bFloating);
	if (TObjectPtr<UInstancedStaticMeshComponent>* Found = Models.Find(Key)) return *Found;
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Navaids/%s.%s"), Name, Name));
	if (!Mesh) return nullptr;
	UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(this);
	Ism->SetupAttachment(bFloating ? FloatingRoot.Get() : FixedRoot.Get());
	Ism->SetStaticMesh(Mesh);
	Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ism->SetCullDistances(0, 600000);
	Ism->NumCustomDataFloats = 3;
	Ism->RegisterComponent();
	Meshes.Add(Ism);
	Models.Add(Key, Ism);
	return Ism;
}

bool ANavaidsActor::BuildModels()
{
	if (USailingSettings::Get()->Quality == ESailingQuality::Low || !LoadObject<UStaticMesh>(nullptr, TEXT("/Game/World/Navaids/SM_Buoy_Can.SM_Buoy_Can"))) return false;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const TArray<FNavaid>& Navaids = GM->GetLake().Navaids;
	auto Paint = [](UInstancedStaticMeshComponent* Ism, int32 Instance, const FLinearColor& C)
	{
		const float D[3] = { C.R, C.G, C.B };
		Ism->SetCustomData(Instance, TArrayView<const float>(D, 3), false);
	};
	// Marine paint (linear albedo), not the chart's display tints: USCG red and green are deep, the yellow is chrome yellow.
	auto PaintOf = [](int32 S57) -> FLinearColor
	{
		switch (S57)
		{
		case 1: return FLinearColor(0.72f, 0.72f, 0.68f);
		case 2: return FLinearColor(0.02f, 0.02f, 0.02f);
		case 3: return FLinearColor(0.42f, 0.025f, 0.018f);
		case 4: return FLinearColor(0.012f, 0.11f, 0.045f);
		case 6: return FLinearColor(0.72f, 0.48f, 0.02f);
		default: return FLinearColor(0.4f, 0.4f, 0.38f);
		}
	};
	for (int32 I = 0; I < Navaids.Num(); ++I)
	{
		const FNavaid& N = Navaids[I];
		const FLinearColor Col = N.Colours.Num() > 0 ? PaintOf(N.Colours[0]) : (N.CatLam == 1 ? PaintOf(4) : (N.CatLam == 2 ? PaintOf(3) : PaintOf(0)));
		const bool bFloating = N.Kind == TEXT("buoy");
		const float Yaw = FMath::Frac(FMath::Sin(I * 78.233) * 43758.5453) * 360.f;
		double LightZ = 0.0;
		if (bFloating)
		{
			// Lighted buoys are pillar buoys (lantern at 3.4 m); unlighted ones are cans (green, odd) and nuns (red, even).
			const bool bPillar = N.bLit || N.Shape == 4 || N.Shape == 5;
			const TCHAR* Name = bPillar ? TEXT("SM_Buoy_Pillar") : (N.Shape == 1 ? TEXT("SM_Buoy_Nun") : (N.Shape == 3 ? TEXT("SM_Buoy_Sphere") : TEXT("SM_Buoy_Can")));
			UInstancedStaticMeshComponent* Ism = ModelIsm(Name, true);
			if (!Ism) return false;
			FBuoy B;
			B.Ism = Ism;
			B.X = N.X;
			B.Y = N.Y;
			B.Yaw = Yaw;
			B.Instance = Ism->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), FVector(N.X, N.Y, 0.0) * CmPerMeter));
			Paint(Ism, B.Instance, Col);
			if (N.bLit) LightBuoy.Add(Lights.Num(), Buoys.Num());
			Buoys.Add(B);
			LightZ = bPillar ? 3.45 : 1.6;
		}
		else
		{
			// Beacons: a three-pile dolphin standing on the bottom with its dayboard; a light structure is a steel tower.
			const bool bTower = N.Kind == TEXT("light");
			const double Top = bTower ? FMath::Max(N.Light.HeightM, 6.0) : FMath::Max(N.Light.HeightM, 4.5);
			if (bTower)
			{
				UInstancedStaticMeshComponent* Ism = ModelIsm(TEXT("SM_Light_Tower"), false);
				if (!Ism) return false;
				Paint(Ism, Ism->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), FVector(N.X, N.Y, 0.0) * CmPerMeter, FVector(1.0, 1.0, Top / 9.68))), Col);
			}
			else
			{
				UInstancedStaticMeshComponent* Pile = ModelIsm(TEXT("SM_Beacon_Pile"), false);
				const bool bTriangle = N.CatLam == 2 || (N.DaymarkColours.Num() > 0 && N.DaymarkColours[0] == 3);
				UInstancedStaticMeshComponent* Board = ModelIsm(bTriangle ? TEXT("SM_Dayboard_Triangle") : TEXT("SM_Dayboard_Square"), false);
				if (!Pile || !Board) return false;
				const double Z0 = -1.0;
				Paint(Pile, Pile->AddInstance(FTransform(FRotator(0.f, Yaw, 0.f), FVector(N.X, N.Y, Z0) * CmPerMeter, FVector(1.0, 1.0, (Top - Z0) / 6.1))), Col);
				const FRotator R(0.f, Yaw, 0.f);
				const FVector At = FVector(N.X, N.Y, Top - 1.3) * CmPerMeter + R.RotateVector(FVector(45.0, 0.0, 0.0));
				Paint(Board, Board->AddInstance(FTransform(R, At)), N.CatLam == 1 ? PaintOf(4) : (N.DaymarkColours.Num() > 0 ? PaintOf(N.DaymarkColours[0]) : Col));
			}
			LightZ = Top + (bTower ? 0.0 : 0.2);
		}
		if (N.bLit)
		{
			const int32 Colour = N.Light.Colours.size() > 0 ? N.Light.Colours[0] : 1;
			TObjectPtr<UInstancedStaticMeshComponent>& LightIsm = LightMeshes.FindOrAdd(Colour * 2 + (bFloating ? 1 : 0));
			if (!LightIsm)
			{
				const FLinearColor LightColor = Colour == 3 ? FLinearColor(1.f, 0.05f, 0.03f) : (Colour == 4 ? FLinearColor(0.05f, 1.f, 0.25f)
					: (Colour == 6 ? FLinearColor(1.f, 0.75f, 0.1f) : FLinearColor(1.f, 0.95f, 0.8f)));
				LightIsm = MakeIsm(Sphere, LightColor, bFloating ? FloatingRoot.Get() : FixedRoot.Get(), true);
			}
			FLightInstance L;
			L.Navaid = I;
			L.Colour = Colour * 2 + (bFloating ? 1 : 0);
			L.bFloating = bFloating;
			L.Position = FVector(N.X * CmPerMeter, N.Y * CmPerMeter, LightZ * CmPerMeter);
			L.Phase = FMath::Frac(FMath::Sin(I * 12.9898) * 43758.5453) * 10.0;
			L.Instance = LightIsm->AddInstance(FTransform(FQuat::Identity, L.Position, FVector(1.0)));
			Lights.Add(L);
		}
	}
	return true;
}

void ANavaidsActor::Build()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || GM->GetLake().Navaids.Num() == 0 || bBuilt) return;
	bBuilt = true;
	FloatingRoot = NewObject<USceneComponent>(this, TEXT("Floating"));
	FloatingRoot->SetupAttachment(RootComponent);
	FloatingRoot->RegisterComponent();
	FixedRoot = NewObject<USceneComponent>(this, TEXT("Fixed"));
	FixedRoot->SetupAttachment(RootComponent);
	FixedRoot->RegisterComponent();
	if (BuildModels())
	{
		for (UInstancedStaticMeshComponent* M : Meshes) { M->UpdateBounds(); M->MarkRenderStateDirty(); }
		UE_LOG(LogSailing, Display, TEXT("Navaids: %d aids (models), %d buoys afloat, %d lights"), GM->GetLake().Navaids.Num(), Buoys.Num(), Lights.Num());
		return;
	}
	Lights.Reset();
	LightBuoy.Reset();

	// One instanced mesh per shape and colour.
	TMap<FString, UInstancedStaticMeshComponent*> Ism;
	auto Get = [&](UStaticMesh* Mesh, const FLinearColor& Color, bool bFloating) -> UInstancedStaticMeshComponent*
	{
		const FString Key = FString::Printf(TEXT("%s_%s_%d"), *Mesh->GetName(), *Color.ToString(), bFloating);
		if (UInstancedStaticMeshComponent** Found = Ism.Find(Key)) return *Found;
		UInstancedStaticMeshComponent* New = MakeIsm(Mesh, Color, bFloating ? FloatingRoot.Get() : FixedRoot.Get());
		Ism.Add(Key, New);
		return New;
	};
	auto Add = [&](UStaticMesh* Mesh, const FLinearColor& Color, bool bFloating, const FVector& Center, const FVector& SizeCm, const FRotator& Rot = FRotator::ZeroRotator)
	{
		Get(Mesh, Color, bFloating)->AddInstance(FTransform(Rot, Center, SizeCm / 100.f));
	};

	const FLinearColor Pile(0.32f, 0.27f, 0.22f), Steel(0.55f, 0.56f, 0.58f);
	const TArray<FNavaid>& Navaids = GM->GetLake().Navaids;
	for (int32 I = 0; I < Navaids.Num(); ++I)
	{
		const FNavaid& N = Navaids[I];
		const FVector Base(N.X * CmPerMeter, N.Y * CmPerMeter, 0.0);
		const FLinearColor Col = N.DisplayColour();
		const bool bFloating = N.Kind == TEXT("buoy");
		double LightZ = 0.0; // m above the water (buoys) or the datum (structures)
		if (bFloating)
		{
			// Lighted buoys are pillar buoys about 3.5 m tall; unlighted ones are cans (green, odd numbers) and nuns
			// (red, even), about 1.4 m above the water.
			if (N.bLit || N.Shape == 4 || N.Shape == 5)
			{
				Add(Cylinder, Col, true, Base + FVector(0, 0, 60), FVector(150, 150, 120));
				Add(Cube, Col, true, Base + FVector(0, 0, 220), FVector(50, 50, 200));
				LightZ = 3.4;
			}
			else if (N.Shape == 1)
			{
				Add(Cylinder, Col, true, Base + FVector(0, 0, 30), FVector(100, 100, 60));
				Add(Cone, Col, true, Base + FVector(0, 0, 60), FVector(100, 100, 90));
			}
			else if (N.Shape == 3)
			{
				Add(Sphere, Col, true, Base + FVector(0, 0, 40), FVector(110, 110, 110));
			}
			else
			{
				Add(Cylinder, Col, true, Base + FVector(0, 0, 60), FVector(90, 90, 140));
			}
		}
		else
		{
			// Beacons: a pile driven into the bottom with its dayboard (green square, red triangle); a light
			// structure is a taller steel tower.
			const double Top = N.Kind == TEXT("light") ? FMath::Max(N.Light.HeightM, 6.0) : FMath::Max(N.Light.HeightM, 4.5);
			const double Bottom = -3.0;
			Add(Cylinder, N.Kind == TEXT("light") ? Steel : Pile, false, Base + FVector(0, 0, 0.5 * (Top + Bottom) * CmPerMeter),
				FVector(35, 35, (Top - Bottom) * CmPerMeter));
			if (N.Kind != TEXT("light"))
			{
				const FVector Board = Base + FVector(0, 0, (Top - 1.4) * CmPerMeter);
				const bool bTriangle = N.CatLam == 2 || (N.DaymarkColours.Num() > 0 && N.DaymarkColours[0] == 3);
				if (bTriangle) Add(Cone, Col, false, Board, FVector(120, 6, 110), FRotator(0, 0, 0));
				else Add(Cube, N.CatLam == 1 ? FLinearColor(0.04f, 0.45f, 0.12f) : Col, false, Board, FVector(110, 6, 110));
			}
			LightZ = Top + 0.2;
		}
		if (N.bLit)
		{
			const int32 Colour = N.Light.Colours.size() > 0 ? N.Light.Colours[0] : 1;
			TObjectPtr<UInstancedStaticMeshComponent>& LightIsm = LightMeshes.FindOrAdd(Colour * 2 + (bFloating ? 1 : 0));
			if (!LightIsm)
			{
				const FLinearColor LightColor = Colour == 3 ? FLinearColor(1.f, 0.05f, 0.03f) : (Colour == 4 ? FLinearColor(0.05f, 1.f, 0.25f)
					: (Colour == 6 ? FLinearColor(1.f, 0.75f, 0.1f) : FLinearColor(1.f, 0.95f, 0.8f)));
				LightIsm = MakeIsm(Sphere, LightColor, bFloating ? FloatingRoot.Get() : FixedRoot.Get(), true);
			}
			FLightInstance L;
			L.Navaid = I;
			L.Colour = Colour * 2 + (bFloating ? 1 : 0);
			L.bFloating = bFloating;
			L.Position = Base + FVector(0, 0, LightZ * CmPerMeter);
			L.Phase = FMath::Frac(FMath::Sin(I * 12.9898) * 43758.5453) * 10.0;
			// Start full size so the instance bounds are real; Tick hides lights by scaling them down.
			L.Instance = LightIsm->AddInstance(FTransform(FQuat::Identity, L.Position, FVector(1.0)));
			Lights.Add(L);
		}
	}
	// The meshes were registered empty: recompute their bounds now that they hold instances, or they are culled.
	for (UInstancedStaticMeshComponent* M : Meshes)
	{
		M->UpdateBounds();
		M->MarkRenderStateDirty();
	}
	UE_LOG(LogSailing, Display, TEXT("Navaids: %d aids, %d lights, %d meshes"), Navaids.Num(), Lights.Num(), Meshes.Num());
}

void ANavaidsActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !bBuilt) return;
	// Fixed structures stand on the bottom: they move with the tide's offset like the terrain, in its 2 cm steps (perf-2:
	// moved every frame, every mark in the bay re-rendered its virtual shadow pages every frame).
	const FVector FixedAt(0.0, 0.0, -FMath::RoundToDouble(GM->GetTideHeight() / 0.02) * 0.02 * CmPerMeter);
	if (!FixedRoot->GetRelativeLocation().Equals(FixedAt, 0.1)) FixedRoot->SetRelativeLocation(FixedAt);

	// Lights come on after sunset (a photocell) or when visibility closes in.
	const bool bDark = GM->IsDark();
	FVector Camera = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Camera = Cam->GetCameraLocation();

	// Buoys ride the waves: heave with the surface and tilt with its slope (a float this size follows the long waves
	// and only partly the chop). Only those within 3 km move; the rest keep their last pose. Perf 2: each instance goes
	// up as a delta (UpdateInstanceTransform queues it); rebuilding the whole component each frame (MarkRenderStateDirty)
	// invalidated the shadow pages over all its buoys.
	const double T = GM->GetSimTime();
	TArray<double> Heave;
	Heave.SetNumZeroed(Buoys.Num());
	for (int32 I = 0; I < Buoys.Num(); ++I)
	{
		const FBuoy& B = Buoys[I];
		if (FVector2D::Distance(FVector2D(B.X, B.Y), SailingFrame::ToMap(GetWorld(), Camera)) > 3000.0) continue;
		const FWaveField& W = GM->GetWaves();
		const double H = W.Height(B.X, B.Y, T);
		const double Hx = (W.Height(B.X + 0.8, B.Y, T) - W.Height(B.X - 0.8, B.Y, T)) / 1.6;
		const double Hy = (W.Height(B.X, B.Y + 0.8, T) - W.Height(B.X, B.Y - 0.8, T)) / 1.6;
		Heave[I] = H;
		const FRotator Tilt(float(-FMath::RadiansToDegrees(FMath::Atan(Hx)) * 0.6), B.Yaw, float(FMath::RadiansToDegrees(FMath::Atan(Hy)) * 0.6));
		B.Ism->UpdateInstanceTransform(B.Instance, FTransform(Tilt, FVector(B.X, B.Y, H - 0.05) * CmPerMeter), false, false, true);
	}
	const double Now = GM->GetUnixTime();
	const TArray<FNavaid>& Navaids = GM->GetLake().Navaids;
	static SailingArgs::FCachedFlag NoFarLightsArg(TEXT("SailingNoFarLights"));
	const bool bFarLights = GM->GetLake().FarLights.Lights.Num() > 0 && !NoFarLightsArg.Get();
	LitCount = 0;
	for (FLightInstance& L : Lights)
	{
		const FNavaid& N = Navaids[L.Navaid];
		const FVector World = (L.bFloating ? FloatingRoot : FixedRoot)->GetComponentTransform().TransformPosition(L.Position);
		const double Distance = FVector::Distance(World, Camera) / CmPerMeter;
		// Wide World Rendering PR 3: past the near pool AFarLightsActor draws the light (Allard's law, the horizon), never both.
		const double Range = FMath::Min((N.Light.RangeNm > 0.0 ? N.Light.RangeNm : 3.0) * 1852.0,
			bFarLights ? AFarLightsActor::NearPoolM : TNumericLimits<double>::Max());
		const bool bOn = bDark && Distance < Range && N.Light.IsOn(Now + L.Phase);
		// A light is a point: keep it about two pixels across however far away, never smaller than the lantern.
		const double Size = bOn ? FMath::Max(0.3, Distance * 0.003) : 0.0;
		UInstancedStaticMeshComponent* Ism = LightMeshes[L.Colour];
		const int32* Buoy = LightBuoy.Find(int32(&L - Lights.GetData()));
		const FVector At = L.Position + FVector(0.0, 0.0, Buoy ? Heave[*Buoy] * CmPerMeter : 0.0);
		// Only lights that changed (by day, none).
		if (Size != L.ShownSize || (Size > 0.0 && !At.Equals(L.ShownAt, 0.5)))
		{
			Ism->UpdateInstanceTransform(L.Instance, FTransform(FQuat::Identity, At, FVector(Size)), false, false, true);
			L.ShownSize = Size;
			L.ShownAt = At;
		}
		LitCount += bOn;
	}
	static double NextLog = 0.0;
	if (GetWorld()->GetTimeSeconds() > NextLog)
	{
		NextLog = GetWorld()->GetTimeSeconds() + 5.0;
		UE_LOG(LogSailing, Display, TEXT("Navaids: %d lights showing (dark %d)"), LitCount, bDark);
	}
}
