#include "NavaidsActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingEnvironment.h"
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
	// Fixed structures stand on the bottom: they move with the tide's offset like the terrain.
	FixedRoot->SetRelativeLocation(FVector(0, 0, -GM->GetTideHeight() * CmPerMeter));

	// Lights come on after sunset (a photocell) or when visibility closes in.
	double Elevation = 0.0, Azimuth = 0.0;
	ASailingEnvironment::SunPosition(GM->GetWeatherState().HourOfDay, GM->GetDayOfYear(), GM->GetLake().Latitude, Elevation, Azimuth);
	static const bool bForceOn = FParse::Param(FCommandLine::Get(), TEXT("SailingLightsOn")); // screenshots, debugging
	const bool bDark = bForceOn || Elevation < -1.0 || GM->GetWeatherState().VisibilityKm < 2.0;
	FVector Camera = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Camera = Cam->GetCameraLocation();
	const double Now = GM->GetUnixTime();
	const TArray<FNavaid>& Navaids = GM->GetLake().Navaids;
	LitCount = 0;
	TSet<UInstancedStaticMeshComponent*> Dirty;
	for (const FLightInstance& L : Lights)
	{
		const FNavaid& N = Navaids[L.Navaid];
		const FVector World = (L.bFloating ? FloatingRoot : FixedRoot)->GetComponentTransform().TransformPosition(L.Position);
		const double Distance = FVector::Distance(World, Camera) / CmPerMeter;
		const double Range = (N.Light.RangeNm > 0.0 ? N.Light.RangeNm : 3.0) * 1852.0;
		const bool bOn = bDark && Distance < Range && N.Light.IsOn(Now + L.Phase);
		// A light is a point: keep it about two pixels across however far away, never smaller than the lantern.
		const double Size = bOn ? FMath::Max(0.3, Distance * 0.003) : 0.0;
		UInstancedStaticMeshComponent* Ism = LightMeshes[L.Colour];
		Ism->UpdateInstanceTransform(L.Instance, FTransform(FQuat::Identity, L.Position, FVector(Size)), false, false, true);
		Dirty.Add(Ism);
		LitCount += bOn;
	}
	for (UInstancedStaticMeshComponent* Ism : Dirty) Ism->MarkRenderStateDirty();
	static double NextLog = 0.0;
	if (GetWorld()->GetTimeSeconds() > NextLog)
	{
		NextLog = GetWorld()->GetTimeSeconds() + 5.0;
		UE_LOG(LogSailing, Display, TEXT("Navaids: %d lights showing (dark %d)"), LitCount, bDark);
	}
}
