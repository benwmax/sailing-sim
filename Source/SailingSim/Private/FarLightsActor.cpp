#include "FarLightsActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "TrafficManager.h"
#include "FarLights.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace FarLightsLocal
{
	constexpr double kEarthR = 7.433e6;   // the curvature code's refracted radius (WorldKit CurvatureDrop)

	FLinearColor LightColour(int32 Colour)
	{
		return Colour == 3 ? FLinearColor(1.f, 0.05f, 0.03f) : (Colour == 4 ? FLinearColor(0.05f, 1.f, 0.25f)
			: (Colour == 6 ? FLinearColor(1.f, 0.8f, 0.1f) : FLinearColor(1.f, 0.92f, 0.75f)));
	}

	/** A point along a lane, Distance metres from its start (wrapping), and the lane's heading there (rad, X north). */
	FVector2D AlongLane(const FFarLightsData::FLane& Lane, double Distance, double& OutHeading)
	{
		double Total = 0.0;
		for (int32 I = 1; I < Lane.Points.Num(); ++I) Total += FVector2D::Distance(Lane.Points[I - 1], Lane.Points[I]);
		double D = FMath::Fmod(Distance, FMath::Max(Total, 1.0));
		if (D < 0.0) D += Total;
		for (int32 I = 1; I < Lane.Points.Num(); ++I)
		{
			const FVector2D A = Lane.Points[I - 1], B = Lane.Points[I];
			const double L = FVector2D::Distance(A, B);
			if (D <= L || I == Lane.Points.Num() - 1)
			{
				OutHeading = FMath::Atan2(B.Y - A.Y, B.X - A.X);
				return A + (B - A) * FMath::Clamp(D / FMath::Max(L, 1.0), 0.0, 1.0);
			}
			D -= L;
		}
		OutHeading = 0.0;
		return Lane.Points[0];
	}
}

AFarLightsActor::AFarLightsActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Emissive(TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Basic(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	Sphere = SphereMesh.Object;
	Cube = CubeMesh.Object;
	EmissiveMaterial = Emissive.Object;
	ShapeMaterial = Basic.Object;
}

UInstancedStaticMeshComponent* AFarLightsActor::MakeIsm(UStaticMesh* Mesh, const FLinearColor& Color, float Intensity, bool bEmissive)
{
	UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(this);
	Ism->SetupAttachment(RootComponent);
	Ism->SetStaticMesh(Mesh);
	Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ism->SetCastShadow(false);
	Ism->bAffectDistanceFieldLighting = false;
	Ism->SetAffectDynamicIndirectLighting(false);
	Ism->SetMobility(EComponentMobility::Movable);
	UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(bEmissive ? EmissiveMaterial.Get() : ShapeMaterial.Get(), this);
	Mid->SetVectorParameterValue(TEXT("Color"), Color);
	if (bEmissive) Mid->SetScalarParameterValue(TEXT("Intensity"), Intensity);
	Ism->SetMaterial(0, Mid);
	Ism->RegisterComponent();
	return Ism;
}

void AFarLightsActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FFarLightsData& Data = GM->GetLake().FarLights;
	// Lights: one instance each in its colour's component (and one in the loom component), all starting hidden (scale 0).
	LoomIsm = MakeIsm(Sphere, FLinearColor(1.f, 0.85f, 0.65f), 6.f, true);
	for (int32 I = 0; I < Data.Lights.Num(); ++I)
	{
		FShownLight S;
		S.Colour = Data.Lights[I].Light.Colours.empty() ? 1 : Data.Lights[I].Light.Colours[0];
		TObjectPtr<UInstancedStaticMeshComponent>& Ism = LightIsms.FindOrAdd(S.Colour);
		if (!Ism) Ism = MakeIsm(Sphere, FarLightsLocal::LightColour(S.Colour), 250.f, true);
		const FVector At(Data.Lights[I].XY.X * 100.0, Data.Lights[I].XY.Y * 100.0, Data.Lights[I].Z * 100.0);
		// Start full size so the instance bounds are real (as ANavaidsActor): Tick hides them by scaling down.
		S.Instance = Ism->AddInstance(FTransform(FQuat::Identity, At, FVector(1.0)));
		S.Loom = LoomIsm->AddInstance(FTransform(FQuat::Identity, At, FVector(1.0)));
		// Lights with the same character don't flash in step (as ANavaidsActor).
		S.Phase = FMath::Frac(FMath::Sin(I * 12.9898) * 43758.5453) * 30.0;
		LightState.Add(S);
	}
	// The lit shore: warm points, few per instance component (one component; hidden by day).
	if (Data.Shore.Num() > 0)
	{
		// A 12-triangle cube per sprite: at a few pixels a point (the engine sphere is a thousand triangles: 4,500 of them cost 20 fps).
		ShoreIsm = MakeIsm(Cube, FLinearColor(1.f, 0.62f, 0.32f), 60.f, true);
		TArray<FTransform> Xf;
		Xf.Reserve(Data.Shore.Num());
		for (const FFarLightsData::FShore& S : Data.Shore) Xf.Add(FTransform(FQuat::Identity, FVector(S.XY.X * 100.0, S.XY.Y * 100.0, S.Z * 100.0), FVector(1.0)));
		ShoreIsm->AddInstances(Xf, false);
		ShoreIsm->SetVisibility(false);
	}
	// Horizon ships: evenly spaced along each lane, a hull and a masthead light each.
	if (Data.Lanes.Num() > 0)
	{
		HullIsm = MakeIsm(Cube, FLinearColor(0.08f, 0.09f, 0.1f), 0.f, false);
		ShipLightIsm = MakeIsm(Sphere, FLinearColor(1.f, 0.95f, 0.85f), 250.f, true);
		for (int32 L = 0; L < Data.Lanes.Num(); ++L)
		{
			double Total = 0.0;
			for (int32 I = 1; I < Data.Lanes[L].Points.Num(); ++I) Total += FVector2D::Distance(Data.Lanes[L].Points[I - 1], Data.Lanes[L].Points[I]);
			for (int32 K = 0; K < Data.Lanes[L].Ships; ++K)
			{
				FShip S;
				S.Lane = L;
				S.Offset = Total * (K + 0.37 * L) / FMath::Max(Data.Lanes[L].Ships, 1);
				S.Hull = HullIsm->AddInstance(FTransform(FQuat::Identity, FVector::ZeroVector, FVector(1.0)));
				S.Light = ShipLightIsm->AddInstance(FTransform(FQuat::Identity, FVector::ZeroVector, FVector(1.0)));
				Ships.Add(S);
			}
		}
	}
	UE_LOG(LogSailing, Display, TEXT("Far lights: %d lights (%d colours), %d shore sprites, %d horizon ships on %d lanes, %d city domes"),
		Data.Lights.Num(), LightIsms.Num(), Data.Shore.Num(), Ships.Num(), Data.Lanes.Num(), Data.Cities.Num());
}

bool AFarLightsActor::IsLightShown(const FFarLightsData& Data, int32 Index, const FVector& CameraCm, bool bDark, double VisibilityKm, double UnixTime,
	double* OutBrightness, bool* OutLoom)
{
	using Sailing::FFarLightMath;
	if (OutBrightness) *OutBrightness = 0.0;
	if (OutLoom) *OutLoom = false;
	if (!Data.Lights.IsValidIndex(Index) || !bDark) return false;
	const FFarLightsData::FLight& L = Data.Lights[Index];
	const double Distance = FVector2D::Distance(L.XY, FVector2D(CameraCm.X, CameraCm.Y) / 100.0);
	// Within the near pool a world's own navaid is ANavaidsActor's (with its buoy's heave): never both.
	if (L.Navaid != INDEX_NONE && Distance < NearPoolM) return false;
	const double Intensity = FFarLightMath::IntensityForNominalRange(L.Light.RangeNm > 0.0 ? L.Light.RangeNm : 3.0);
	const double Lux = FFarLightMath::IlluminanceLux(Intensity, Distance, VisibilityKm);
	const double Brightness = FFarLightMath::Brightness(Lux, true);
	if (Brightness <= 0.0) return false;
	if (!L.Light.IsOn(UnixTime)) return false;
	const double Eye = FMath::Max(CameraCm.Z / 100.0, 1.0);
	const bool bBelow = Distance > FFarLightMath::GeographicRangeM(L.Z, Eye);
	if (OutLoom) *OutLoom = bBelow;
	if (OutBrightness) *OutBrightness = bBelow ? Brightness * 0.25 : Brightness;
	return true;
}

void AFarLightsActor::UpdateLights(const FVector& Camera, bool bDark, double Visibility, double Now)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FFarLightsData& Data = GM->GetLake().FarLights;
	const double Eye = FMath::Max(Camera.Z / 100.0, 1.0);
	Shown = Looms = 0;
	for (int32 I = 0; I < LightState.Num(); ++I)
	{
		FShownLight& S = LightState[I];
		double Brightness = 0.0;
		bool bLoom = false;
		const bool bOn = IsLightShown(Data, I, Camera, bDark, Visibility, Now + S.Phase, &Brightness, &bLoom);
		const FFarLightsData::FLight& L = Data.Lights[I];
		const double Distance = FVector2D::Distance(L.XY, FVector2D(Camera.X, Camera.Y) / 100.0);
		// A point about two pixels across, a little bigger for a bold light; on the curve (the curvature code's drop).
		const float Size = (bOn && !bLoom) ? float(FMath::Max(0.3, Distance * 0.0022 * (0.6 + 0.8 * Brightness))) : 0.f;
		// The loom: a soft glow just over the horizon toward the light (its beam sweeping the haze).
		const float LoomSize = (bOn && bLoom) ? float(Distance * 0.012 * Brightness) : 0.f;
		const double Drop = CurvatureDrop(Distance);
		UInstancedStaticMeshComponent* Ism = LightIsms[S.Colour];
		if (Size > 0.f || S.Size != 0.f)
		{
			Ism->UpdateInstanceTransform(S.Instance, FTransform(FQuat::Identity, FVector(L.XY.X * 100.0, L.XY.Y * 100.0, (L.Z - Drop) * 100.0), FVector(Size)), true, false, true);
			S.Size = Size;
		}
		if (LoomSize > 0.f || S.LoomSize != 0.f)
		{
			const double Dip = FMath::Sqrt(2.0 * Eye / FarLightsLocal::kEarthR);
			const double Z = Eye - Distance * Dip + Distance * 0.003;
			LoomIsm->UpdateInstanceTransform(S.Loom, FTransform(FQuat::Identity, FVector(L.XY.X * 100.0, L.XY.Y * 100.0, Z * 100.0), FVector(LoomSize)), true, false, true);
			S.LoomSize = LoomSize;
		}
		Shown += bOn && !bLoom;
		Looms += bOn && bLoom;
	}
}

void AFarLightsActor::UpdateShore(const FVector& Camera, bool bDark)
{
	if (!ShoreIsm) return;
	if (!bDark)
	{
		if (bShoreLit) { ShoreIsm->SetVisibility(false); bShoreLit = false; }
		return;
	}
	// Re-placed when the camera has moved 150 m (the curvature drop and the near pool move with it), not every frame.
	if (bShoreLit && FVector::Dist2D(Camera, LastShoreCamera) < 15000.0) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FFarLightsData& Data = GM->GetLake().FarLights;
	TArray<FTransform> Xf;
	Xf.SetNum(Data.Shore.Num());
	for (int32 I = 0; I < Data.Shore.Num(); ++I)
	{
		const FFarLightsData::FShore& S = Data.Shore[I];
		const double Distance = FVector2D::Distance(S.XY, FVector2D(Camera.X, Camera.Y) / 100.0);
		const bool bShow = Distance > ShoreFromM && Distance < ShoreToM;
		// A town reads by its density: the cell's houses widen its glow (square root: their windows overlap at range).
		const double Size = bShow ? Distance * 0.0011 * FMath::Sqrt(double(S.Houses)) * 0.8 : 0.0;   // the cube is 1 m across, the sphere 1 m: a little smaller
		Xf[I] = FTransform(FQuat::Identity, FVector(S.XY.X * 100.0, S.XY.Y * 100.0, (S.Z - CurvatureDrop(Distance)) * 100.0), FVector(Size));
	}
	ShoreIsm->BatchUpdateInstancesTransforms(0, Xf, false, true, true);
	ShoreIsm->SetVisibility(true);
	LastShoreCamera = Camera;
	bShoreLit = true;
}

void AFarLightsActor::UpdateShips(const FVector& Camera, bool bDark, double SimTime)
{
	if (!HullIsm) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FFarLightsData& Data = GM->GetLake().FarLights;
	for (FShip& S : Ships)
	{
		const FFarLightsData::FLane& Lane = Data.Lanes[S.Lane];
		double Heading = 0.0;
		const FVector2D At = FarLightsLocal::AlongLane(Lane, S.Offset + SimTime * Lane.Knots * 0.514444, Heading);
		const double Distance = FVector2D::Distance(At, FVector2D(Camera.X, Camera.Y) / 100.0);
		if (Distance < ShipHandOffM && !S.bHanded)
		{
			// Closing inside 8 km: the real traffic takes her over (a ship on the rest of her lane), once.
			S.bHanded = true;
			if (ATrafficManager* Traffic = ATrafficManager::Find(GetWorld()))
			{
				std::vector<std::pair<double, double>> Route;
				for (const FVector2D& P : Lane.Points) Route.emplace_back(P.X, P.Y);
				Traffic->HandOffShip(At.X, At.Y, Heading, std::move(Route), Lane.Name);
			}
		}
		else if (Distance > ShipToM) S.bHanded = false;   // she has gone round the lane: a new ship next time
		const bool bDraw = !S.bHanded && Distance >= ShipHandOffM && Distance < ShipToM;
		const double Drop = CurvatureDrop(Distance);
		// A 180 m ship, 28 m beam, 20 m of hull and superstructure (a box impostor: under a pixel's detail at 8 km).
		const FTransform Hull(FRotator(0.0, FMath::RadiansToDegrees(Heading), 0.0), FVector(At.X * 100.0, At.Y * 100.0, (10.0 - Drop) * 100.0),
			bDraw ? FVector(180.0, 28.0, 20.0) : FVector::ZeroVector);
		HullIsm->UpdateInstanceTransform(S.Hull, Hull, true, false, true);
		const double LightSize = (bDraw && bDark) ? FMath::Max(0.5, Distance * 0.0018) : 0.0;
		ShipLightIsm->UpdateInstanceTransform(S.Light, FTransform(FQuat::Identity, FVector(At.X * 100.0, At.Y * 100.0, (32.0 - Drop) * 100.0), FVector(LightSize)), true, false, true);
	}
}

void AFarLightsActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	FVector Camera = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Camera = Cam->GetCameraLocation();
	const bool bDark = GM->IsDark();
	const double Visibility = GM->GetWeatherState().VisibilityKm;
	UpdateLights(Camera, bDark, Visibility, GM->GetUnixTime());
	UpdateShore(Camera, bDark);
	UpdateShips(Camera, bDark, GM->GetSimTime());
	static double NextLog = 0.0;
	if (GetWorld()->GetTimeSeconds() > NextLog)
	{
		NextLog = GetWorld()->GetTimeSeconds() + 5.0;
		UE_LOG(LogSailing, Display, TEXT("Far lights: %d showing, %d looms (dark %d, visibility %.0f km)"), Shown, Looms, bDark, Visibility);
	}
}
