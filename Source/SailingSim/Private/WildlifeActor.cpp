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
	// Hidden instances wait at the actor (the map's origin) at zero scale; Tick parks them at the camera (docs/rain-deck:
	// parked far away they stretched the bounds under the lake and nothing drew).
	TArray<FTransform> Hidden;
	Hidden.Init(FTransform(FQuat::Identity, FVector::ZeroVector, FVector::ZeroVector), Count);
	Ism->AddInstances(Hidden, false, false);
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
		StylePool[S] = Bodies;
		StyleIsms[S] = MakeIsm(*Name, Mesh, MidMaterial, Bodies, MidFloats);
	}
	FarPool = Budget.Far + (Missing > 0 || !MidMaterial || !bBodies ? Bodies : 0);
	FarIsm = MakeIsm(TEXT("BirdQuads"), QuadMesh, FarMaterial, FarPool, FarFloats);

	FVector Cam = FVector::ZeroVector;
	FLaunchSpot Spot;
	if (GM->GetLaunchSpot(Spot)) Cam = FVector(Spot.X * 100.0, Spot.Y * 100.0, 200.0);
	StartMapBuild(Cam.X / 100.0, Cam.Y / 100.0, true);
	SAIL_LOG(Display, TEXT("Wildlife: %s, %d birds in the table, tier %d budget far %d mid %d near %d, %d styles without a body mesh, %d harbour cells"),
		*Lake.FileName, int32(Table.Birds.size()), Tier, Budget.Far, Budget.Mid, Budget.Near, Missing, HarbourCells.Num());
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
}

FTransform AWildlifeActor::FarQuad(const FVector& BirdCm, const FVector& CameraCm, double HeadingRad, double BankRad, double SpanM,
	double PixelAngle, double& OutSpanScale, double& OutCover)
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
	const FQuat Q = FMatrix(X, Y, N, FVector::ZeroVector).ToQuat();
	return FTransform(Q, BirdCm, FVector(Drawn * OutSpanScale, Drawn, 1.0));
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
	// The instances live in the actor's space, the map frame (it sits at SailingFrame::MapAnchor): the camera's map place.
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
	for (const Sailing::FBirdDraw& D : Draw)
	{
		const Sailing::FBirdLook& L = Looks.IsValidIndex(D.Bird) ? Looks[D.Bird] : Sailing::FBirdLook();
		const FVector At(D.North * 100.0, D.East * 100.0, D.Up * 100.0);
		const bool bFar = D.DistanceM >= Sailing::FBirdFlocks::MidM;
		const int32 S = int32(D.Style);
		const bool bBody = !bFar && StyleIsms.IsValidIndex(S) && StyleIsms[S] && BodyCount[S] < StylePool[S];
		if (bBody)
		{
			const int32 K = BodyCount[S]++;
			BodyXf[S][K] = BodyTransform(At, D.HeadingRad, D.PitchRad, D.BankRad, D.SizeM);
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
		if (Quads >= FarPool) continue;
		double SpanScale = 1.0, Cover = 1.0;
		FarXf[Quads] = FarQuad(At, CameraMapCm, D.HeadingRad, D.BankRad, D.SizeM, PixelAngle, SpanScale, Cover);
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
		FarIsm->SetCustomData(Quads, MakeArrayView(Data, FarFloats), false);
		++Quads;
	}
	FarIsm->BatchUpdateInstancesTransforms(0, FarXf, false, true, true);
	DrawnQuads = Quads;
	DrawnBodies = 0;
	for (int32 S = 0; S < StyleIsms.Num(); ++S)
	{
		if (!StyleIsms[S]) continue;
		StyleIsms[S]->BatchUpdateInstancesTransforms(0, BodyXf[S], false, true, true);
		DrawnBodies += BodyCount[S];
	}
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
		UE_LOG(LogSailing, Log, TEXT("Wildlife: %d flocks, %d birds (%d resting), drawn %d quads %d bodies, %d flushes, update %.3f ms"),
			St.Flocks, St.Birds, St.Resting, DrawnQuads, DrawnBodies, St.Flushes, UpdateMs);
	}
}
