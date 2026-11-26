#include "WildlifeActor.h"
#include "BenchRunner.h"
#include "LakeData.h"
#include "PowerVesselActor.h"
#include "SailboatPawn.h"
#include "SailingEnvironment.h"
#include "SailingFrame.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "Async/Async.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/StaticMesh.h"
#include "Materials/Material.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include <cmath>
#include <string>

namespace WildlifeActorLocal
{
	constexpr double kHarbourCellM = 100.0;
	constexpr double kKnotsPerMs = 1.943844;
	constexpr double kRainMmHAtDownpour = 50.0;   // FWeatherState::Rain 1 is a downpour (about 50 mm/h)
	constexpr const TCHAR* kBirdFolder = TEXT("/Game/Wildlife/Birds");

	int32 MonthOfDay(int32 DayOfYear)
	{
		static const int32 Ends[12] = { 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 366 };
		for (int32 M = 0; M < 12; ++M) if (DayOfYear <= Ends[M]) return M + 1;
		return 12;
	}

	int32 TierOf(ESailingQuality Q)
	{
		switch (Q)
		{
		case ESailingQuality::Low: return 0;
		case ESailingQuality::Medium: return 1;
		case ESailingQuality::High: return 2;
		default: return 3;
		}
	}

	/** The style's resting wing shape for M_BirdFar: dihedral (rad, up positive) and crank (the gull's bent wing). */
	void WingShape(Sailing::EBirdStyle S, float& Dihedral, float& Crank)
	{
		Dihedral = 0.05f;
		Crank = 0.f;
		switch (S)
		{
		case Sailing::EBirdStyle::FlapHang: Dihedral = 0.12f; Crank = 0.35f; break;      // the gull's M
		case Sailing::EBirdStyle::HoverPlunge: Dihedral = 0.1f; Crank = 0.3f; break;     // terns and the osprey's crooked wing
		case Sailing::EBirdStyle::Soaring: Dihedral = 0.22f; Crank = 0.f; break;         // a vulture's shallow V
		case Sailing::EBirdStyle::Shearing: Dihedral = -0.04f; Crank = 0.f; break;       // stiff, flat, a little drooped
		case Sailing::EBirdStyle::HeavyGlider: Dihedral = 0.02f; Crank = 0.1f; break;    // pelicans: flat, the hand drooped
		case Sailing::EBirdStyle::Wading: Dihedral = -0.08f; Crank = 0.1f; break;        // herons: bowed down
		default: break;
		}
	}
}

AWildlifeActor::AWildlifeActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

const TCHAR* AWildlifeActor::StyleMeshName(Sailing::EBirdStyle Style)
{
	switch (Style)
	{
	case Sailing::EBirdStyle::HeavyGlider: return TEXT("HeavyGlider");
	case Sailing::EBirdStyle::FlapHang: return TEXT("FlapHang");
	case Sailing::EBirdStyle::HoverPlunge: return TEXT("HoverPlunge");
	case Sailing::EBirdStyle::FastLow: return TEXT("FastLow");
	case Sailing::EBirdStyle::Shearing: return TEXT("Shearing");
	case Sailing::EBirdStyle::Soaring: return TEXT("Soaring");
	case Sailing::EBirdStyle::Wading: return TEXT("Wading");
	case Sailing::EBirdStyle::Insect: return TEXT("Insect");
	case Sailing::EBirdStyle::Raft: return TEXT("Raft");
	default: return TEXT("FlapHang");
	}
}

UInstancedStaticMeshComponent* AWildlifeActor::MakeIsm(const TCHAR* Name, UStaticMesh* Mesh, UMaterialInterface* Material, int32 Count, int32 Floats)
{
	UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(this, Name);
	Ism->SetupAttachment(RootComponent);
	Ism->SetStaticMesh(Mesh);
	if (Material) Ism->SetMaterial(0, Material);
	Ism->SetMobility(EComponentMobility::Movable);
	// The pools' pattern (spray, drips, the bow wave, the cannon smoke, the bridges' vehicles): the component stays at an
	// identity transform in the render's world and every instance is placed in world space, each frame. (The first build
	// kept the instances in the actor's map frame and nothing drew, even ten times the size: docs/wildlife-1.)
	Ism->SetUsingAbsoluteLocation(true);
	Ism->SetUsingAbsoluteRotation(true);
	Ism->SetUsingAbsoluteScale(true);
	Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Ism->SetCastShadow(false);
	Ism->SetCanEverAffectNavigation(false);
	// Out of the distance-field and Lumen scenes, and out of ray tracing (docs/recentre-hitch, docs/far-cap-sprites): every
	// instance moves every frame.
	Ism->bAffectDistanceFieldLighting = false;
	Ism->SetAffectDynamicIndirectLighting(false);
	Ism->bVisibleInRayTracing = false;
	Ism->NumCustomDataFloats = Floats;
	Ism->RegisterComponent();
	// Hidden instances wait at the camera at zero scale, and Tick parks them there again (docs/rain-deck: parked far away
	// they stretched the bounds under the lake and nothing drew).
	FVector Here = GetActorLocation();
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) Here = Cam->GetCameraLocation();
	TArray<FTransform> Hidden;
	Hidden.Init(FTransform(FQuat::Identity, Here, FVector::ZeroVector), Count);
	Ism->AddInstances(Hidden, false, true);
	return Ism;
}

void AWildlifeActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsLoaded())
	{
		SetActorTickEnabled(false);
		return;
	}
	const FLakeData& Lake = GM->GetLake();
	FString Text;
	const FString Path = FLakeData::DefaultDirectory() / Lake.FileName + TEXT(".wildlife.json");
	std::string Error;
	if (!FFileHelper::LoadFileToString(Text, *Path) || !Table.LoadText(TCHAR_TO_UTF8(*Text), &Error))
	{
		SAIL_LOG(Warning, TEXT("Wildlife: no table for %s (%s): no birds"), *Lake.FileName, UTF8_TO_TCHAR(Error.c_str()));
		SetActorTickEnabled(false);
		return;
	}
	Tier = WildlifeActorLocal::TierOf(USailingSettings::Get()->Quality);
	const Sailing::FBirdBudget Budget = Sailing::BirdBudgetForTier(Tier);
	Flocks.Reset(Table, 0x5eedb1dULL ^ uint64(GetTypeHash(Lake.FileName)));
	Flocks.SetBudget(Budget);
	float Scale = 1.f;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingWildlifeScale="), Scale)) Flocks.SetDensityScale(FMath::Max(0.0, double(Scale)));
	float DebugK = 10.f;
	// (FParse::Param takes the bare flag only: -SailingDebugBirds=4 is read by the Value.)
	const bool bDebugValue = FParse::Value(SailingArgs::Dev(), TEXT("SailingDebugBirds="), DebugK);
	if (bDebugValue || FParse::Param(SailingArgs::Dev(), TEXT("SailingDebugBirds")))
	{
		DebugSize = FMath::Max(1.0, double(DebugK));
		// And a few birds pinned in the view (30 to 160 m ahead): if those don't show, the drawing is at fault, not the
		// flocks or the aim.
		Markers = 3;
	}
	// -SailingDebugBirdsPlain: every bird drawn with the engine's default material (no silhouette, no per-instance data, no
	// dither): a grey square or body wherever an instance is, to tell the drawing from the bird materials.
	bPlainDebug = FParse::Param(SailingArgs::Dev(), TEXT("SailingDebugBirdsPlain"));
	for (const Sailing::FWildBird& B : Table.Birds) Looks.Add(Sailing::BirdLookFor(B.Id, B.Style));

	// The harbours the tables' marina, docks and boats habitats mean: 100 m cells round every dock, deck, moored boat and the
	// club's marina (the shore bake's own words for them).
	auto Mark = [this](const FVector2D& P)
	{
		const int32 I = FMath::FloorToInt32(P.X / WildlifeActorLocal::kHarbourCellM), J = FMath::FloorToInt32(P.Y / WildlifeActorLocal::kHarbourCellM);
		for (int32 A = -1; A <= 1; ++A) for (int32 B = -1; B <= 1; ++B) HarbourCells.Add(FIntPoint(I + A, J + B));
	};
	for (const FLakeDock& D : Lake.Docks) for (const FVector2D& P : D.Points) Mark(P);
	for (const FLakeDeck& D : Lake.Decks) for (const FVector2D& P : D.Outline) Mark(P);
	for (const FMooredBoat& B : Lake.MooredBoats) Mark(B.Center);
	if (Lake.Marina.IsLoaded())
	{
		const FBox2D Box = Lake.Marina.Bounds();
		for (double X = Box.Min.X; X <= Box.Max.X; X += WildlifeActorLocal::kHarbourCellM)
			for (double Y = Box.Min.Y; Y <= Box.Max.Y; Y += WildlifeActorLocal::kHarbourCellM) Mark(FVector2D(X, Y));
	}

	// The quads (every band until the bodies are imported) and a body component per flight style that has its mesh.
	QuadMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	FarMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Wildlife/Birds/M_BirdFar.M_BirdFar"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	MidMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Wildlife/Birds/M_BirdMid.M_BirdMid"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (bPlainDebug)
	{
		FarMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
		if (MidMaterial) MidMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
	}
	if (!FarMaterial || !QuadMesh)
	{
		SAIL_LOG(Warning, TEXT("Wildlife: M_BirdFar is not built yet (scripts/make-birds.sh): no birds drawn"));
		SetActorTickEnabled(false);
		return;
	}
	const int32 Bodies = Budget.Mid + Budget.Near;
	const bool bBodies = Tier > 0;   // Low draws every bird as a quad
	StyleIsms.SetNum(int32(Sailing::EBirdStyle::Count));
	StylePool.Init(0, int32(Sailing::EBirdStyle::Count));
	int32 Missing = 0;
	for (int32 S = 0; S < int32(Sailing::EBirdStyle::Count); ++S)
	{
		bool bUsed = false;
		for (const Sailing::FWildBird& B : Table.Birds) bUsed |= int32(B.Style) == S;
		if (!bUsed || Bodies == 0 || !MidMaterial || !bBodies) continue;
		const FString Name = FString::Printf(TEXT("SM_Bird_%s"), StyleMeshName(Sailing::EBirdStyle(S)));
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("%s/%s.%s"), WildlifeActorLocal::kBirdFolder, *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (!Mesh) { ++Missing; continue; }
		StylePool[S] = Bodies + Markers;
		StyleIsms[S] = MakeIsm(*Name, Mesh, MidMaterial, Bodies + Markers, MidFloats);
	}
	// Every bird can end up a quad: past the bodies' budget, too small on screen for a body, or with no body for its style.
	FarPool = Budget.Far + Bodies + Markers;
	FarIsm = MakeIsm(TEXT("BirdQuads"), QuadMesh, FarMaterial, FarPool, FarFloats);

	FVector Cam = FVector::ZeroVector;
	FLaunchSpot Spot;
	if (GM->GetLaunchSpot(Spot)) Cam = FVector(Spot.X * 100.0, Spot.Y * 100.0, 200.0);
	StartMapBuild(Cam.X / 100.0, Cam.Y / 100.0, true);
	FString DebugNote = DebugSize > 0.0 ? FString::Printf(TEXT(", debug: every bird %.0fx its size and %d pinned in view"), DebugSize, Markers) : FString();
	if (bPlainDebug) DebugNote += TEXT(", debug: the engine's default material");
	SAIL_LOG(Display, TEXT("Wildlife: %s, %d birds in the table, tier %d budget far %d mid %d near %d, %d styles without a body mesh, %d harbour cells%s"),
		*Lake.FileName, int32(Table.Birds.size()), Tier, Budget.Far, Budget.Mid, Budget.Near, Missing, HarbourCells.Num(), *DebugNote);
}

void AWildlifeActor::EndPlay(const EEndPlayReason::Type Reason)
{
	if (bMapBuilding) PendingMap.Wait();
	Super::EndPlay(Reason);
}

void AWildlifeActor::BuildWorld(Sailing::FWildlifeWorld& Out, double CenterN, double CenterE) const
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FLakeData& Lake = GM->GetLake();
	// A worker reads its own copy of the terrain (it shares the heights; a streamed world's window holds its tiles), never
	// the lake's (tiles are swapped under it). Heights over the water: on the coast the terrain is over the datum and the
	// water stands at the tide.
	auto Terrain = std::make_shared<const Sailing::FLakeTerrain>(Lake.bStreamed ? Lake.Terrain.WindowAround(CenterN, CenterE, MapHalfM + 500.0) : Lake.Terrain);
	const double Tide = GM->GetTideHeight();
	Out.HeightAt = [Terrain, Tide](double N, double E) { return Terrain->HeightAt(N, E) - Tide; };
	Out.CanopyAt = [Terrain](double N, double E) { return Terrain->CanopyAt(N, E); };
	if (HarbourCells.Num() > 0)
	{
		TSet<FIntPoint> Cells = HarbourCells;
		Out.IsHarbour = [Cells = MoveTemp(Cells)](double N, double E)
		{
			return Cells.Contains(FIntPoint(FMath::FloorToInt32(N / WildlifeActorLocal::kHarbourCellM), FMath::FloorToInt32(E / WildlifeActorLocal::kHarbourCellM)));
		};
	}
}

void AWildlifeActor::StartMapBuild(double CenterN, double CenterE, bool bWait)
{
	Sailing::FWildlifeWorld W;
	BuildWorld(W, CenterN, CenterE);
	MapTide = GetWorld()->GetAuthGameMode<ASailingGameMode>()->GetTideHeight();
	auto Build = [W = MoveTemp(W), CenterN, CenterE]()
	{
		auto M = std::make_shared<Sailing::FWildlifeHabitatMap>();
		M->Build(W, CenterN, CenterE, MapHalfM, MapCellM);
		return std::shared_ptr<const Sailing::FWildlifeHabitatMap>(M);
	};
	if (bWait)
	{
		const double T0 = FPlatformTime::Seconds();
		Map = Build();
		SAIL_LOG(Display, TEXT("Wildlife: habitat map at %.0f, %.0f in %.0f ms"), CenterN, CenterE, (FPlatformTime::Seconds() - T0) * 1000.0);
		return;
	}
	PendingMap = Async(EAsyncExecution::ThreadPool, MoveTemp(Build));
	bMapBuilding = true;
}

Sailing::FWildlifeConditions AWildlifeActor::Conditions(const FVector& CameraMapCm) const
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FLakeData& Lake = GM->GetLake();
	Sailing::FWildlifeConditions C;
	C.Month = WildlifeActorLocal::MonthOfDay(GM->GetDayOfYear());
	C.LocalHour = GM->GetLocalHour();
	double Elevation = 0.0, Azimuth = 0.0;
	ASailingEnvironment::SunPosition(C.LocalHour, GM->GetDayOfYear(), Lake.Latitude, Lake.Longitude, GM->GetUtcOffsetHours(), Elevation, Azimuth);
	C.SunElevationDeg = Elevation;
	const double N = CameraMapCm.X / 100.0, E = CameraMapCm.Y / 100.0;
	C.RainMmH = FMath::Clamp(GM->GetRainAt(N, E), 0.0, 1.0) * WildlifeActorLocal::kRainMmHAtDownpour;
	double From = 0.0, Factor = 1.0;
	GM->GetWind().ReadableAt(N, E, GM->GetSimTime(), From, Factor);
	C.WindKn = GM->GetWind().MeanSpeedAtHeight(10.0) * Factor * WildlifeActorLocal::kKnotsPerMs;
	C.WindFromDeg = FMath::RadiansToDegrees(From);
	return C;
}

void AWildlifeActor::GatherObservers(const FVector& CameraMapCm, Sailing::FBirdObservers& Out, double Dt)
{
	Out.CamNorth = CameraMapCm.X / 100.0;
	Out.CamEast = CameraMapCm.Y / 100.0;
	Out.CamUp = CameraMapCm.Z / 100.0;
	Out.Boats.clear();
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const APawn* Player = PC ? PC->GetPawn() : nullptr;
	for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
	{
		if (It->bGhost) continue;   // the ghost is a memory, not a boat
		const Sailing::FBoatTelemetry& T = It->GetBoatModel().GetTelemetry();
		const Sailing::Vec3 O = It->GetBoatModel().OriginPosition();
		Sailing::FBirdObservers::FBoat B;
		B.North = O.X;
		B.East = O.Y;
		B.HeadingRad = T.Heading;
		B.SpeedMs = T.BoatSpeed;
		B.bPlayer = *It == Player;
		Out.Boats.push_back(B);
	}
	// Power vessels: their speed from how far they moved since the last update.
	for (TActorIterator<APowerVesselActor> It(GetWorld()); It; ++It)
	{
		const FVector P = SailingFrame::ToMapCm(GetWorld(), It->GetActorLocation());
		FVector& Last = LastVessel.FindOrAdd(TWeakObjectPtr<AActor>(*It), P);
		const FVector V = Dt > 1e-3 ? (P - Last) / Dt : FVector::ZeroVector;
		Last = P;
		Sailing::FBirdObservers::FBoat B;
		B.North = P.X / 100.0;
		B.East = P.Y / 100.0;
		B.SpeedMs = V.Size2D() / 100.0;
		B.HeadingRad = B.SpeedMs > 0.2 ? FMath::Atan2(V.Y, V.X) : FMath::DegreesToRadians(It->GetActorRotation().Yaw);
		Out.Boats.push_back(B);
	}
	for (auto It = LastVessel.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();

	// The view: birds on screen (and just off it) take the drawing budget first.
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		const FVector F = Cam->GetCameraRotation().Vector();   // the map frame's axes are Unreal's (north x, east y, up z)
		double Aspect = 16.0 / 9.0;
		if (GEngine && GEngine->GameViewport)
		{
			FVector2D Size;
			GEngine->GameViewport->GetViewportSize(Size);
			if (Size.X > 16.0 && Size.Y > 16.0) Aspect = Size.X / Size.Y;
		}
		const double TanH = FMath::Tan(0.5 * FMath::DegreesToRadians(double(Cam->GetFOVAngle())));
		const double Corner = FMath::Atan(TanH * FMath::Sqrt(1.0 + 1.0 / (Aspect * Aspect))) + FMath::DegreesToRadians(ViewMarginDeg);
		Out.bHasView = true;
		Out.ViewNorth = F.X;
		Out.ViewEast = F.Y;
		Out.ViewUp = F.Z;
		Out.ViewCosHalf = FMath::Cos(FMath::Min(Corner, 0.5 * UE_DOUBLE_PI - 0.01));
	}
}

FTransform AWildlifeActor::FarQuad(const FVector& BirdCm, const FVector& CameraCm, double HeadingRad, double BankRad, double SpanM,
	double PixelAngle, double& OutSpanScale, double& OutCover, double* OutWiden)
{
	// Toward the camera (the quad's face, local +Z); the bird's right wing (heading north = 0 clockwise, banked).
	const FVector N = (CameraCm - BirdCm).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const FVector Fwd(FMath::Cos(HeadingRad), FMath::Sin(HeadingRad), 0.0);
	const FVector Right0(-FMath::Sin(HeadingRad), FMath::Cos(HeadingRad), 0.0);
	const FVector Span = (Right0 * FMath::Cos(BankRad) - FVector::UpVector * FMath::Sin(BankRad)).GetSafeNormal();
	// The span as the camera sees it: across the view. Seen end-on (flying across the view, wings toward the eye) the quad
	// keeps the screen's horizontal and a quarter of its width (the wings beat up and down in it).
	const FVector Across = Span - FVector::DotProduct(Span, N) * N;
	const double Seen = Across.Size();
	OutSpanScale = FMath::Clamp(Seen, 0.25, 1.0);
	// Nearly end-on the span's direction on screen is unreliable: blend to the screen's horizontal from a third seen down
	// to a tenth (no pop as the bird turns).
	const FVector Level = FVector::CrossProduct(FVector::UpVector, N).GetSafeNormal(UE_SMALL_NUMBER, Fwd);
	FVector X = Level;
	if (Seen > 1e-6)
	{
		FVector A = Across / Seen;
		if (FVector::DotProduct(A, Level) < 0.0) A = -A;
		X = FMath::Lerp(Level, A, FMath::Clamp((Seen - 0.1) / 0.23, 0.0, 1.0)).GetSafeNormal(UE_SMALL_NUMBER, Level);
	}
	FVector Y = FVector::CrossProduct(N, X);
	// The silhouette is the same both ways round: keep the quad's y up the screen (the wings' beat reads up).
	if (Y.Z < 0.0) { X = -X; Y = -Y; }
	const double Dist = FVector::Dist(CameraCm, BirdCm) / 100.0;
	const double MinSpan = MinPixels * PixelAngle * Dist;
	const double Drawn = FMath::Max(SpanM, MinSpan);
	OutCover = Drawn > 0.0 ? FMath::Clamp(SpanM / Drawn, 0.0, 1.0) : 0.0;
	// Across the screen the quad is held at MinPixels too (a bird crossing the view, wings end-on, was under a pixel wide):
	// M_BirdFar draws the bird in its middle 1 / Widen.
	const double Width = FMath::Max(Drawn * OutSpanScale, MinSpan);
	if (OutWiden) *OutWiden = Width / FMath::Max(Drawn * OutSpanScale, 1e-6);
	const FQuat Q = FMatrix(X, Y, N, FVector::ZeroVector).ToQuat();
	return FTransform(Q, BirdCm, FVector(Width, Drawn, 1.0));
}

FTransform AWildlifeActor::BodyTransform(const FVector& BirdCm, double HeadingRad, double PitchRad, double BankRad, double SpanM)
{
	// FRotator: yaw about +Z from +X (north) toward +Y (east) is the heading; pitch nose up; roll right wing down.
	const FRotator R(FMath::RadiansToDegrees(PitchRad), FMath::RadiansToDegrees(HeadingRad), FMath::RadiansToDegrees(BankRad));
	return FTransform(R, BirdCm, FVector(SpanM));
}

void AWildlifeActor::DrawBirds(const FVector& CameraMapCm)
{
	const std::vector<Sailing::FBirdDraw>& Draw = Flocks.Draw();
	const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0);
	double Width = 1920.0;
	if (GEngine && GEngine->GameViewport)
	{
		FVector2D Size;
		GEngine->GameViewport->GetViewportSize(Size);
		if (Size.X > 16.0) Width = Size.X;
	}
	const double Fov = FMath::DegreesToRadians(Cam ? double(Cam->GetFOVAngle()) : 90.0);
	const double PixelAngle = 2.0 * FMath::Tan(0.5 * Fov) / Width;
	// Built in the map frame (cm), put in the render's world just before they are sent (SailingFrame::ToWorldTransforms).
	// Unused instances wait at the camera at zero scale.
	const FTransform Parked(FQuat::Identity, CameraMapCm, FVector::ZeroVector);
	TArray<FTransform> FarXf;
	FarXf.Init(Parked, FarPool);
	TArray<TArray<FTransform>> BodyXf;
	BodyXf.SetNum(StyleIsms.Num());
	TArray<int32> BodyCount;
	BodyCount.Init(0, StyleIsms.Num());
	for (int32 S = 0; S < StyleIsms.Num(); ++S) if (StyleIsms[S]) BodyXf[S].Init(Parked, StylePool[S]);
	int32 Quads = 0;
	float Data[FarFloats];
	float Body[MidFloats];
	DrawnInView = 0;
	NearestInView.Reset();
	const double SizeScale = DebugSize > 0.0 ? DebugSize : 1.0;
	for (const Sailing::FBirdDraw& D : Draw)
	{
		const Sailing::FBirdLook& L = Looks.IsValidIndex(D.Bird) ? Looks[D.Bird] : Sailing::FBirdLook();
		const FVector At(D.North * 100.0, D.East * 100.0, D.Up * 100.0);
		// Far birds drawn bigger than life by the screen's coarse pixels (Sailing::BirdSeenScale; none close by), so a gull
		// 500 m off reads as a bird and not a speck; bodies and quads alike, so a bird keeps its size as it turns into a body.
		const double SizeM = D.SizeM * SizeScale * Sailing::BirdSeenScale(D.DistanceM, PixelAngle);
		const int32 S = int32(D.Style);
		// A body: within the near and mid budgets, with a mesh for its style, and big enough on screen for its wings to show.
		const bool bBody = D.bBody && StyleIsms.IsValidIndex(S) && StyleIsms[S] && BodyCount[S] < StylePool[S] - Markers &&
			SizeM >= BodyMinPixels * PixelAngle * FMath::Max(double(D.DistanceM), 1.0);
		if (D.bInView)
		{
			// (Draw is in view first, nearest first: the first one on screen is the nearest.)
			if (DrawnInView++ == 0 && Table.Birds.size() > size_t(D.Bird))
			{
				const FVector Rel = At - CameraMapCm;
				NearestInView = FString::Printf(TEXT("%s %.0f m bearing %.0f elevation %.1f deg"), UTF8_TO_TCHAR(Table.Birds[D.Bird].Id.c_str()),
					D.DistanceM, FMath::Fmod(FMath::RadiansToDegrees(FMath::Atan2(Rel.Y, Rel.X)) + 360.0, 360.0),
					FMath::RadiansToDegrees(FMath::Atan2(Rel.Z, Rel.Size2D())));
			}
		}
		if (bBody)
		{
			const int32 K = BodyCount[S]++;
			BodyXf[S][K] = BodyTransform(At, D.HeadingRad, D.PitchRad, D.BankRad, SizeM);
			Body[0] = D.WingPhase;
			Body[1] = D.WingAmp;
			Body[2] = D.Fold;
			Body[3] = D.Fade;
			Body[4] = L.Upper[0]; Body[5] = L.Upper[1]; Body[6] = L.Upper[2];
			Body[7] = L.Under[0]; Body[8] = L.Under[1]; Body[9] = L.Under[2];
			Body[10] = L.Tips;
			StyleIsms[S]->SetCustomData(K, MakeArrayView(Body, MidFloats), false);
			continue;
		}
		if (Quads >= FarPool - Markers) continue;
		double SpanScale = 1.0, Cover = 1.0, Widen = 1.0;
		FarXf[Quads] = FarQuad(At, CameraMapCm, D.HeadingRad, D.BankRad, SizeM, PixelAngle, SpanScale, Cover, &Widen);
		if (DebugSize > 0.0) Cover = 1.0;
		// The side the camera sees: from below the underside, from above the back.
		const float Below = float(FMath::Clamp(0.5 + (D.Up - CameraMapCm.Z / 100.0) / FMath::Max(double(D.DistanceM) * 0.1, 1.0), 0.0, 1.0));
		float Dihedral = 0.f, Crank = 0.f;
		WildlifeActorLocal::WingShape(D.Style, Dihedral, Crank);
		Data[0] = D.WingPhase;
		Data[1] = D.WingAmp;
		Data[2] = D.Fold;
		Data[3] = float(D.Fade * Cover);
		Data[4] = L.Tips;
		for (int32 C = 0; C < 3; ++C) Data[5 + C] = FMath::Lerp(L.Upper[C], L.Under[C], Below);
		Data[8] = Below;
		Data[9] = Dihedral;
		Data[10] = Crank;
		Data[11] = float(SpanScale);
		Data[12] = float(Widen);
		FarIsm->SetCustomData(Quads, MakeArrayView(Data, FarFloats), false);
		++Quads;
	}
	DrawnQuads = Quads;
	DrawnBodies = 0;
	for (int32 S = 0; S < StyleIsms.Num(); ++S) DrawnBodies += BodyCount[S];

	// -SailingDebugBirds: a few birds pinned in the view whatever the flocks do, dark backs and pale undersides, each about
	// 3.5 deg across: quads 30, 60 and 120 m ahead 3 deg over the horizon (12 deg apart), a body each 40, 80 and 160 m
	// ahead just over it (above the camera's height, so over the water).
	MarkerQuad = -1;
	if (Markers > 0 && Cam)
	{
		const FRotator View = Cam->GetCameraRotation();
		const int32 BodyStyle = StyleIsms.IndexOfByPredicate([](const TObjectPtr<UInstancedStaticMeshComponent>& C) { return C != nullptr; });
		for (int32 K = 0; K < Markers; ++K)
		{
			const double Ahead = 30.0 * double(1 << K);
			const FVector QuadDir = FRotator(3.0, View.Yaw + 12.0 * (K - 1), 0.0).Vector();
			const FVector QuadAt = CameraMapCm + QuadDir * Ahead * 100.0;
			double SpanScale = 1.0, Cover = 1.0, Widen = 1.0;
			const int32 Q = FarPool - Markers + K;
			FarXf[Q] = FarQuad(QuadAt, CameraMapCm, FMath::DegreesToRadians(View.Yaw), 0.0, 0.06 * Ahead, PixelAngle, SpanScale, Cover, &Widen);
			const float Marker[FarFloats] = { 0.f, 0.f, 0.f, 1.f, 0.5f, 0.05f, 0.05f, 0.05f, 0.f, 0.12f, 0.35f, float(SpanScale), float(Widen) };
			FarIsm->SetCustomData(Q, MakeArrayView(Marker, FarFloats), false);
			if (K == 0) MarkerQuad = Q;
			if (BodyStyle == INDEX_NONE) continue;
			const double BodyAhead = 40.0 * double(1 << K);
			const FVector BodyAt = CameraMapCm + FRotator(0.5, View.Yaw + 12.0 * K - 6.0, 0.0).Vector() * BodyAhead * 100.0;
			const int32 B = StylePool[BodyStyle] - Markers + K;
			BodyXf[BodyStyle][B] = BodyTransform(BodyAt, FMath::DegreesToRadians(View.Yaw + 30.0), 0.0, 0.2, 0.06 * BodyAhead);
			const float Look[MidFloats] = { 0.25f, 1.f, 0.f, 1.f, 0.05f, 0.05f, 0.05f, 0.85f, 0.85f, 0.85f, 0.f };
			StyleIsms[BodyStyle]->SetCustomData(B, MakeArrayView(Look, MidFloats), false);
		}
	}

	// Into the render's world (its origin follows the boat on a streamed world), and sent: only the instances drawn this
	// frame or the last (a style with no body either frame is left alone), every parked one again once the camera has
	// moved 500 m or the origin has. Sending every instance of every pool each frame cost up to 0.85 ms of game thread on
	// the PC at Ultra (Nov 26, 540 quads on the lake), the logic only 0.04 to 0.25 of it.
	const FVector RenderOrigin = SailingFrame::OriginCm(GetWorld());
	const bool bFullSend = Markers > 0 || !bParkedSent || FVector::Dist(CameraMapCm, ParkedAtCm) > 50000.0 || !RenderOrigin.Equals(ParkedOriginCm);
	if (bFullSend)
	{
		bParkedSent = true;
		ParkedAtCm = CameraMapCm;
		ParkedOriginCm = RenderOrigin;
	}
	SentBodies.SetNum(StyleIsms.Num());
	auto SendDrawn = [this, bFullSend](UInstancedStaticMeshComponent* Target, TArray<FTransform>& Out, int32 DrawnNow, int32& SentBefore)
	{
		const int32 Count = bFullSend ? Out.Num() : FMath::Min(Out.Num(), FMath::Max(DrawnNow, SentBefore));
		SentBefore = DrawnNow;
		if (Count <= 0) return;
		Out.SetNum(Count, EAllowShrinking::No);
		Target->BatchUpdateInstancesTransforms(0, SailingFrame::ToWorldTransforms(GetWorld(), Out), true, true, true);
	};
	SendDrawn(FarIsm, FarXf, Quads, SentQuads);
	for (int32 S = 0; S < StyleIsms.Num(); ++S)
	{
		if (StyleIsms[S]) SendDrawn(StyleIsms[S], BodyXf[S], BodyCount[S], SentBodies[S]);
	}
}

FString AWildlifeActor::DebugState(const FVector& CameraMapCm) const
{
	// Where the components and a pinned bird are, as the engine holds them (map metres), and what they draw with.
	auto InMap = [this](const FVector& WorldCm) { const FVector P = SailingFrame::ToMapCm(GetWorld(), WorldCm) / 100.0; return FString::Printf(TEXT("%.0f, %.0f, %.1f"), P.X, P.Y, P.Z); };
	auto Describe = [&InMap](const UInstancedStaticMeshComponent* C)
	{
		if (!C) return FString(TEXT("none"));
		const UMaterialInterface* M = C->GetMaterial(0);
		// (The mesh's own half size, cm: a body is built 100 cm across, so about 50 x 50 x 10.)
		const FVector Mesh = C->GetStaticMesh() ? FVector(C->GetStaticMesh()->GetBounds().BoxExtent) : FVector::ZeroVector;
		return FString::Printf(TEXT("%s: %d instances, %s%s, bounds at %s m half %.0f x %.0f x %.0f m, mesh half %.1f x %.1f x %.1f cm, %s"), *C->GetName(),
			C->GetInstanceCount(), C->IsRegistered() ? TEXT("registered") : TEXT("NOT registered"), C->IsVisible() ? TEXT(" visible") : TEXT(" HIDDEN"),
			*InMap(C->Bounds.Origin), C->Bounds.BoxExtent.X / 100.0, C->Bounds.BoxExtent.Y / 100.0, C->Bounds.BoxExtent.Z / 100.0, Mesh.X, Mesh.Y, Mesh.Z,
			M ? *M->GetName() : TEXT("no material"));
	};
	FString Out = FString::Printf(TEXT("camera at %s m; %s"), *InMap(SailingFrame::FromMapCm(GetWorld(), CameraMapCm)), *Describe(FarIsm));
	FTransform Xf;
	if (FarIsm && MarkerQuad >= 0 && FarIsm->GetInstanceTransform(MarkerQuad, Xf, true))
	{
		Out += FString::Printf(TEXT("; pinned quad at %s m scale %.2f x %.2f"), *InMap(Xf.GetLocation()), Xf.GetScale3D().X, Xf.GetScale3D().Y);
	}
	for (const TObjectPtr<UInstancedStaticMeshComponent>& C : StyleIsms)
	{
		if (C) { Out += TEXT("; ") + Describe(C); break; }
	}
	return Out;
}

void AWildlifeActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!GM || !Cam || !Map) return;
	const FVector CameraWorld = Cam->GetCameraLocation();
	const FVector CameraMap = SailingFrame::ToMapCm(GetWorld(), CameraWorld);
	const double N = CameraMap.X / 100.0, E = CameraMap.Y / 100.0;

	// A new habitat map when the camera has gone 1.5 km from this one's centre or the tide has moved 0.3 m (on a worker;
	// the old map serves meanwhile, and its window still covers the far band).
	if (bMapBuilding && PendingMap.IsReady())
	{
		Map = PendingMap.Get();
		PendingMap = TFuture<std::shared_ptr<const Sailing::FWildlifeHabitatMap>>();
		bMapBuilding = false;
	}
	// A streamed world's tiles round the start may still be arriving when the first map is built: once more at 5 s.
	const bool bSecond = !bSecondMap && GM->GetLake().bStreamed && GetWorld()->GetTimeSeconds() > 5.0;
	if (!bMapBuilding && (bSecond || FMath::Max(FMath::Abs(N - Map->CenterNorth()), FMath::Abs(E - Map->CenterEast())) > RebuildM
		|| FMath::Abs(GM->GetTideHeight() - MapTide) > 0.3))
	{
		bSecondMap |= bSecond;
		StartMapBuild(N, E, false);
	}

	// On the sim clock: held (photo mode) the birds hold too.
	const double Now = GM->GetSimTime();
	const double Dt = LastSimTime < 0.0 ? 0.0 : FMath::Clamp(Now - LastSimTime, 0.0, 0.25);
	LastSimTime = Now;
	Sailing::FBirdObservers Obs;
	GatherObservers(CameraMap, Obs, Dt);
	const double T0 = FPlatformTime::Seconds();
	Flocks.Update(Dt, Conditions(CameraMap), Obs, *Map);
	const double UpdateMs = (FPlatformTime::Seconds() - T0) * 1000.0;
	DrawBirds(CameraMap);
	if (GetWorld()->GetTimeSeconds() > NextLog)
	{
		NextLog = GetWorld()->GetTimeSeconds() + 10.0;
		const Sailing::FBirdFlocks::FStats& St = Flocks.Stats();
		UE_LOG(LogSailing, Log, TEXT("Wildlife: %d flocks, %d birds (%d resting), drawn %d quads %d bodies, %d in view (nearest %s), %d flushes, update %.3f ms"),
			St.Flocks, St.Birds, St.Resting, DrawnQuads, DrawnBodies, DrawnInView, NearestInView.IsEmpty() ? TEXT("none") : *NearestInView,
			St.Flushes, UpdateMs);
		if (DebugSize > 0.0 || bPlainDebug) UE_LOG(LogSailing, Log, TEXT("Wildlife debug: %s"), *DebugState(CameraMap));
	}
}
