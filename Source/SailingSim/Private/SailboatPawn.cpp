#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "UI/SailHud.h"
#include "SailSession.h"
#include "GroomComponent.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "PowerVesselActor.h"
#include "EngineUtils.h"
#include "Components/MeshComponent.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "UnrealClient.h"
#include "Engine/GameViewportClient.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "SailingAudio.h"
#include "SailingEnvironment.h"
#include "TrafficManager.h"
#include "Components/AudioComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "ProceduralMeshComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Materials/MaterialParameterCollection.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

using namespace Sailing;

namespace
{
	FVector ToCm(const Vec3& V) { return FVector(V.X, V.Y, V.Z) * CmPerMeter; }
	FVector ToCm(double X, double Y, double Z) { return FVector(X, Y, Z) * CmPerMeter; }

	const FName NAME_Tiller(TEXT("Tiller"));
	const FName NAME_MainSheet(TEXT("MainSheet"));
	const FName NAME_JibSheet(TEXT("JibSheet"));
	const FName NAME_Traveler(TEXT("Traveler"));
	const FName NAME_Hike(TEXT("Hike"));
	const FName NAME_Vang(TEXT("Vang"));
	const FName NAME_Cunningham(TEXT("Cunningham"));
	const FName NAME_Outhaul(TEXT("Outhaul"));
	const FName NAME_Backstay(TEXT("Backstay"));
	const FName NAME_Look(TEXT("Look"));
	const FName NAME_Zoom(TEXT("Zoom"));

	bool IsButtonAction(FName Action)
	{
		return Action == TEXT("WingOnWing") || Action == TEXT("ToggleLearning") || Action == TEXT("ToggleDifficulty")
			|| Action == TEXT("ToggleHud") || Action == TEXT("ResetBoat") || Action == TEXT("Menu") || Action == TEXT("ControlsCard") || Action == TEXT("DockLines") || Action == TEXT("BackJib")
			|| Action == TEXT("MenuUp") || Action == TEXT("MenuDown") || Action == TEXT("MenuLeft") || Action == TEXT("MenuRight")
			|| Action == TEXT("Spinnaker") || Action == TEXT("Reef") || Action == TEXT("Board") || Action == TEXT("Righting") || Action == TEXT("EngineNeutral")
			|| Action == TEXT("Chart") || Action == TEXT("Bearing") || Action == TEXT("Gps") || Action == TEXT("ClearPlot")
			|| Action == TEXT("Logbook") || Action == TEXT("Replay") || Action == TEXT("Photo") || Action == TEXT("PhotoShot")
			|| Action == TEXT("CockpitView");
	}

	/** Controls the crew handles in the Simple layout. */
	bool IsCrewHandled(FName Action)
	{
		return Action == NAME_Traveler || Action == NAME_Vang || Action == NAME_Cunningham || Action == NAME_Outhaul || Action == NAME_Backstay;
	}

	enum EMenuRow { RowWorld, RowBoat, RowDrill, RowRace, RowGhost, RowTraffic, RowLaunch, RowLakeLevel, RowWeather, RowHour, RowSeed, RowDifficulty, RowControls, RowTrimAssist, RowLearning, RowQuality, RowVolume, RowKeys, RowCount };

	constexpr double kTrimAssistIdleSeconds = 4.0;
}

ASailboatPawn::ASailboatPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	BoatRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoatRoot"));
	RootComponent = BoatRoot;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BasicMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	UStaticMesh* Cube = CubeFinder.Object;
	UStaticMesh* Cylinder = CylinderFinder.Object;
	ShapeMaterial = BasicMaterial.Object;

	CubeMesh = Cube;
	CylinderMesh = Cylinder;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereFinder(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> EmissiveFinder(TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	SphereMesh = SphereFinder.Object;
	EmissiveMaterial = EmissiveFinder.Object;
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GhostFinder(TEXT("/Game/Materials/M_Ghost.M_Ghost"));
	GhostMaterial = GhostFinder.Object;

	// The hull, foils, spars and crew are built at runtime from the boat's particulars (RebuildBoatVisuals), so any
	// boat in the fleet can be sailed. What stays fixed: the hull mesh component, the pivots and the sails.
	HullMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("HullMesh"));
	HullMesh->SetupAttachment(BoatRoot);
	HullMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	BoomPivot = CreateDefaultSubobject<USceneComponent>(TEXT("BoomPivot"));
	BoomPivot->SetupAttachment(BoatRoot);

	MastheadFly = CreateDefaultSubobject<USceneComponent>(TEXT("MastheadFly"));
	MastheadFly->SetupAttachment(BoatRoot);
	MastheadFly->SetRelativeLocation(FVector(100.f, 0.f, 935.f));
	AddPart(TEXT("FlyArrow"), Cube, FVector(18.f, 0.f, 0.f), FVector(45.f, 2.5f, 2.5f), FRotator::ZeroRotator, MastheadFly);
	AddPart(TEXT("FlyVane"), Cube, FVector(-8.f, 0.f, 0.f), FVector(12.f, 1.f, 10.f), FRotator::ZeroRotator, MastheadFly);

	MainSail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MainSail"));
	MainSail->SetupAttachment(BoatRoot);
	MainSail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	JibSail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("JibSail"));
	JibSail->SetupAttachment(BoatRoot);
	JibSail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SpinSail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("SpinSail"));
	SpinSail->SetupAttachment(BoatRoot);
	SpinSail->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	for (int32 I = 0; I < 6; ++I)
	{
		JibTelltales.Add(AddPart(*FString::Printf(TEXT("JibTelltale%d"), I), Cube, FVector::ZeroVector, FVector(18.f, 1.2f, 2.f)));
	}
	for (int32 I = 0; I < 3; ++I)
	{
		LeechTelltales.Add(AddPart(*FString::Printf(TEXT("LeechTelltale%d"), I), Cube, FVector::ZeroVector, FVector(22.f, 1.2f, 2.f)));
	}

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(BoatRoot);
	CameraBoom->TargetArmLength = CameraDistance;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, 300.f);
	CameraBoom->bDoCollisionTest = false;
	CameraBoom->bInheritPitch = false;
	CameraBoom->bInheritRoll = false;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 6.f;
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);

	CaptureCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("CaptureCamera"));
	CaptureCamera->SetupAttachment(BoatRoot);
	CaptureCamera->bAutoActivate = false;
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> LensFinder(TEXT("/Game/Materials/M_LensDistortion.M_LensDistortion"));
	LensDistortionAsset = LensFinder.Object;

	// Visual V2: the modelled boats (Tools/blender, scripts/make-boat-models.sh) and their material library.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> J22Hull(TEXT("/Game/Boats/J22/SM_J22_Hull.SM_J22_Hull"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> J22Mast(TEXT("/Game/Boats/J22/SM_J22_Mast.SM_J22_Mast"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> J22Boom(TEXT("/Game/Boats/J22/SM_J22_Boom.SM_J22_Boom"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> J22Rudder(TEXT("/Game/Boats/J22/SM_J22_Rudder.SM_J22_Rudder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Rope(TEXT("/Game/Boats/Materials/MI_Boat_Rope.MI_Boat_Rope"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Wire(TEXT("/Game/Boats/Materials/MI_Boat_Stainless.MI_Boat_Stainless"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Car(TEXT("/Game/Boats/Materials/MI_Boat_BlackPlastic.MI_Boat_BlackPlastic"));
	static ConstructorHelpers::FObjectFinder<UMaterialParameterCollection> BoatMpc(TEXT("/Game/Boats/MPC_Boat.MPC_Boat"));
	J22HullMesh = J22Hull.Object;
	J22MastMesh = J22Mast.Object;
	J22BoomMesh = J22Boom.Object;
	J22RudderMesh = J22Rudder.Object;
	RopeMaterial = Rope.Object;
	WireMaterial = Wire.Object;
	CarMaterial = Car.Object;
	BoatParameters = BoatMpc.Object;
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> Sailor(TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	SailorMesh = Sailor.Object;
	for (const TCHAR* Slot : { TEXT("Jacket"), TEXT("PFD"), TEXT("Trousers"), TEXT("Boots"), TEXT("Skin"), TEXT("Cap"), TEXT("Glasses") })
	{
		ConstructorHelpers::FObjectFinder<UMaterialInterface> Mat(*FString::Printf(TEXT("/Game/Boats/Materials/MI_Boat_Crew%s.MI_Boat_Crew%s"), Slot, Slot));
		if (Mat.Succeeded()) CrewMaterials.Add(Slot, Mat.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SailMain(TEXT("/Game/Materials/MI_Sail_Main.MI_Sail_Main"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SailJib(TEXT("/Game/Materials/MI_Sail_Jib.MI_Sail_Jib"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SailSpin(TEXT("/Game/Materials/MI_Sail_Spinnaker.MI_Sail_Spinnaker"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Telltale(TEXT("/Game/Materials/M_Telltale.M_Telltale"));
	SailMainMaterial = SailMain.Object;
	SailJibMaterial = SailJib.Object;
	SailSpinMaterial = SailSpin.Object;
	TelltaleMaterial = Telltale.Object;
	TelltaleRibbons = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("TelltaleRibbons"));
	TelltaleRibbons->SetupAttachment(BoatRoot);
	TelltaleRibbons->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	TelltaleRibbons->SetCastShadow(false);
	RigLines = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("RigLines"));
	RigLines->SetupAttachment(BoatRoot);
	RigLines->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RigLines->SetCastShadow(true);

	AutoPossessPlayer = EAutoReceiveInput::Disabled;
}

UStaticMeshComponent* ASailboatPawn::AddPart(FName Name, UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation, USceneComponent* Parent)
{
	UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
	Part->SetupAttachment(Parent ? Parent : BoatRoot.Get());
	Part->SetStaticMesh(Mesh);
	Part->SetMaterial(0, ShapeMaterial);
	Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Part->SetRelativeLocation(LocationCm);
	Part->SetRelativeRotation(Rotation);
	// Engine basic shapes are 100 cm across.
	Part->SetRelativeScale3D(SizeCm / 100.f);
	return Part;
}

UStaticMeshComponent* ASailboatPawn::AddBoatPart(UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FLinearColor& Color, const FRotator& Rotation, USceneComponent* Parent)
{
	UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
	Part->SetupAttachment(Parent ? Parent : BoatRoot.Get());
	Part->SetStaticMesh(Mesh);
	Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Part->SetRelativeLocation(LocationCm);
	Part->SetRelativeRotation(Rotation);
	Part->SetRelativeScale3D(SizeCm / 100.f); // engine basic shapes are 100 cm across
	Part->RegisterComponent();
	if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this))
	{
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		Part->SetMaterial(0, Mid);
	}
	BoatParts.Add(Part);
	return Part;
}

UStaticMeshComponent* ASailboatPawn::AddRod(const Vec3& A, const Vec3& B, double DiameterM, const FLinearColor& Color)
{
	const FVector From = ToCm(A), To = ToCm(B);
	const FVector Dir = To - From;
	// The engine cylinder stands along Z: rotate Z onto the rod's direction.
	const FRotator Rot = FRotationMatrix::MakeFromZ(Dir.GetSafeNormal()).Rotator();
	return AddBoatPart(CylinderMesh, 0.5f * (From + To), FVector(DiameterM * CmPerMeter, DiameterM * CmPerMeter, Dir.Size()), Color, Rot);
}

void ASailboatPawn::SetBoat(int32 Type)
{
	const double StartSeconds = FPlatformTime::Seconds();
	const EBoatType BoatType = EBoatType(FMath::Clamp(Type, 0, int32(EBoatType::Count) - 1));
	const double Time = Boat.GetState().Time;
	FBoatConfig Config = FBoatConfig::Make(BoatType);
	float CrewKg = 0.f;
	if (!bTrafficBoat && FParse::Value(FCommandLine::Get(), TEXT("SailingCrewKg="), CrewKg) && CrewKg > 0.f)
	{
		Config.CrewMass = CrewKg; // reference captures: the crew weight aboard the boat in the clip
	}
	Boat = FBoatModel(Config);
	Boat.GetMutableState().Time = Time; // the weather clock runs on
	if (const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr)
	{
		if (GM->GetLake().IsLoaded())
		{
			Boat.SetTerrain(&GM->GetLake().Terrain);
			Boat.SetObstacles(&GM->GetLake().Obstacles);
		}
	}
	ApplyDifficulty();
	RebuildBoatVisuals();
	// Frame the boat: the camera stands off about two and a half boat lengths, looking at the middle of the rig.
	const FBoatConfig& C = Boat.GetConfig();
	CameraDistance = FMath::Clamp(float(C.LengthOverall) * 2.4f, 9.f, 40.f) * CmPerMeter;
	CameraBoom->TargetArmLength = CameraDistance;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, float(C.MastheadZ) * 0.33f * CmPerMeter);
	ResetBoat();
	// The Phase 4 gate asks that every boat loads fast: building one is physics setup plus a few dozen meshes.
	UE_LOG(LogSailing, Log, TEXT("Boat ready: %hs in %.1f ms"), C.Name, (FPlatformTime::Seconds() - StartSeconds) * 1000.0);
}

void ASailboatPawn::BuildHullMesh()
{
	const FBoatConfig& C = Boat.GetConfig();
	const double Depth = Boat.HullDepth();
	TArray<FVector> ShellV, DeckV;
	TArray<int32> ShellT, DeckT;
	const int32 NX = 36, NY = 14;
	for (const FHullShape& H : C.Hulls)
	{
		const int32 Base = ShellV.Num(), DeckBase = DeckV.Num();
		for (int32 I = 0; I <= NX; ++I)
		{
			const double X = H.SternX + (H.BowX - H.SternX) * I / NX;
			const double B = H.DeckHalfBeam(X);
			const double Sheer = H.SheerHeight(X);
			for (int32 J = 0; J <= NY; ++J)
			{
				const double Y = -B + 2.0 * B * J / NY;
				ShellV.Add(ToCm(X, H.CenterY + Y, FMath::Min(H.BottomZ(X, Y, Depth), Sheer)));
				DeckV.Add(ToCm(X, H.CenterY + Y, Sheer));
			}
		}
		for (int32 I = 0; I < NX; ++I)
		{
			for (int32 J = 0; J < NY; ++J)
			{
				const int32 A = I * (NY + 1) + J, Bq = A + 1, Cq = A + NY + 1, D = Cq + 1;
				ShellT.Append({ Base + A, Base + Cq, Base + Bq, Base + Bq, Base + Cq, Base + D });   // facing down and out
				DeckT.Append({ DeckBase + A, DeckBase + Bq, DeckBase + Cq, DeckBase + Bq, DeckBase + D, DeckBase + Cq }); // facing up
			}
		}
		// Transom: close the stern between the shell and the deck.
		const int32 TBase = ShellV.Num();
		for (int32 J = 0; J <= NY; ++J)
		{
			const FVector Bottom = ShellV[Base + J]; // copy first: Add may reallocate the array it reads from
			ShellV.Add(Bottom);
			ShellV.Add(DeckV[DeckBase + J]);
		}
		for (int32 J = 0; J < NY; ++J)
		{
			const int32 A = TBase + 2 * J;
			ShellT.Append({ A, A + 2, A + 1, A + 1, A + 2, A + 3 });
		}
	}
	auto Normals = [](const TArray<FVector>& V, const TArray<int32>& T)
	{
		TArray<FVector> N;
		N.SetNumZeroed(V.Num());
		for (int32 I = 0; I + 2 < T.Num(); I += 3)
		{
			const FVector F = FVector::CrossProduct(V[T[I + 1]] - V[T[I]], V[T[I + 2]] - V[T[I]]) * -1.0;
			N[T[I]] += F; N[T[I + 1]] += F; N[T[I + 2]] += F;
		}
		for (FVector& X : N) X = X.GetSafeNormal();
		return N;
	};
	HullMesh->ClearAllMeshSections();
	HullMesh->CreateMeshSection_LinearColor(0, ShellV, ShellT, Normals(ShellV, ShellT), {}, {}, {}, false);
	HullMesh->CreateMeshSection_LinearColor(1, DeckV, DeckT, Normals(DeckV, DeckT), {}, {}, {}, false);
	FLinearColor HullColor(0.94f, 0.94f, 0.92f);
	switch (bTrafficBoat ? EBoatType::Count : C.Type)
	{
	case EBoatType::J22: HullColor = FLinearColor(0.75f, 0.06f, 0.06f); break;      // the lesson boat stays red
	case EBoatType::Sunfish: HullColor = FLinearColor(0.95f, 0.72f, 0.10f); break;
	case EBoatType::Catalina30: HullColor = FLinearColor(0.08f, 0.13f, 0.30f); break;
	case EBoatType::Hobie16: HullColor = FLinearColor(0.10f, 0.45f, 0.75f); break;
	default: if (bTrafficBoat) HullColor = TrafficHullColor; break;
	}
	for (int32 Section = 0; Section < 2; ++Section)
	{
		if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this))
		{
			Mid->SetVectorParameterValue(TEXT("Color"), Section == 0 ? HullColor : FLinearColor(0.86f, 0.86f, 0.83f));
			HullMesh->SetMaterial(Section, Mid);
		}
	}
}

void ASailboatPawn::RebuildBoatVisuals()
{
	for (USceneComponent* Part : BoatParts) if (Part) Part->DestroyComponent();
	BoatParts.Reset();
	RudderPivots.Reset();
	Crew.Reset();
	ModelHull = ModelMast = ModelBoom = ModelRudder = TravelerCar = nullptr;
	MastMaterial = nullptr;
	RigLines->ClearAllMeshSections();
	bRigLinesBuilt = false;
	// Graphics G3: the livery (BoatLivery.h). The player's (and its ghost's) is the class's most common scheme as a club
	// boat; each AI boat draws its own. -SailingLiverySeed=<n> picks one (stills).
	{
		uint32 Seed = bTrafficBoat && !bGhost ? GetUniqueID() * 7919u + 1u : 0u;
		FParse::Value(FCommandLine::Get(), TEXT("SailingLiverySeed="), Seed);
		Livery = SampleBoatLivery(int32(Boat.GetConfig().Type), Seed);
	}
	const FBoatModelMeshes Model = ModelMeshesFor(Boat.GetConfig().Type);
	if (Model.Hull)
	{
		HullMesh->ClearAllMeshSections();
		BuildModelVisuals(Model);
	}
	else
	{
		BuildHullMesh();
	}

	const FBoatConfig& C = Boat.GetConfig();
	const FHullShape& Main = C.Hulls[0];
	const FLinearColor Dark(0.05f, 0.05f, 0.06f), Spar(0.55f, 0.56f, 0.58f), Wood(0.45f, 0.28f, 0.12f), Grey(0.25f, 0.25f, 0.27f), White(0.92f, 0.92f, 0.9f);
	const double DeckZ = C.bMultihull ? Main.SheerZ : Main.SheerHeight(C.MastX);

	// Keels, boards and rudders (a slender cat hull's own lift has no part to show).
	for (const FFoilDef& F : C.Foils)
	{
		if (ModelHull) break; // the model has its own keel, rudder and tiller
		if (F.Role == EFoilRole::HullLateral) continue;
		const double Span = F.Span(), Chord = F.Params.Chord, Thick = 0.06 * Chord + 0.015;
		if (F.Role != EFoilRole::Rudder)
		{
			AddBoatPart(CubeMesh, ToCm(F.Params.Center), FVector(Chord, Thick, Span) * CmPerMeter, Dark);
			continue;
		}
		USceneComponent* Pivot = NewObject<USceneComponent>(this);
		Pivot->SetupAttachment(BoatRoot);
		Pivot->SetRelativeLocation(ToCm(F.Params.Center.X + 0.25 * Chord, F.Params.Center.Y, 0.0));
		Pivot->RegisterComponent();
		BoatParts.Add(Pivot);
		RudderPivots.Add(Pivot);
		AddBoatPart(CubeMesh, ToCm(-0.25 * Chord, 0.0, F.Params.Center.Z), FVector(Chord, Thick, Span) * CmPerMeter, Dark, FRotator::ZeroRotator, Pivot);
		if (C.TillerLength > 0.6) // tiller boats; wheel steering shows no tiller
		{
			const double Hz = (C.bMultihull ? Main.SheerZ : Main.SheerHeight(F.Params.Center.X)) + 0.1;
			AddBoatPart(CubeMesh, ToCm(0.5 * C.TillerLength, 0.0, Hz), FVector(C.TillerLength, 0.04, 0.04) * CmPerMeter, Wood, FRotator::ZeroRotator, Pivot);
		}
	}

	// Mast, boom, forestay.
	if (!ModelHull)
	{
	AddBoatPart(CylinderMesh, ToCm(C.MastX, 0.0, 0.5 * (DeckZ + C.MastheadZ)), FVector(C.MastDiameter, C.MastDiameter, C.MastheadZ - DeckZ) * CmPerMeter, Spar);
	BoomPivot->SetRelativeLocation(ToCm(C.MainLuffX, 0.0, C.BoomZ));
	AddBoatPart(CylinderMesh, ToCm(-0.5 * C.MainFootChord, 0.0, 0.0), FVector(0.7 * C.MastDiameter, 0.7 * C.MastDiameter, C.MainFootChord) * CmPerMeter, Spar, FRotator(90.f, 0.f, 0.f), BoomPivot);
	if (C.HasJib())
	{
		const FSailStripGeometry& Foot = C.Jib.Strips[0];
		const FSailStripGeometry& Head = C.Jib.Strips[C.Jib.NumStrips - 1];
		const double Slope = (Head.LuffX - Foot.LuffX) / FMath::Max(0.5 * (Head.ZBottom + Head.ZTop) - 0.5 * (Foot.ZBottom + Foot.ZTop), 0.1);
		const Vec3 Tack(Foot.LuffX - Slope * 0.5 * (Foot.ZTop - Foot.ZBottom), 0.0, Foot.ZBottom - 0.1);
		const Vec3 Hounds(Head.LuffX + Slope * 0.5 * (Head.ZTop - Head.ZBottom), 0.0, Head.ZTop + 0.1);
		AddRod(Tack, Hounds, 0.012, Spar);
	}
	}
	else
	{
		BoomPivot->SetRelativeLocation(ToCm(C.MainLuffX, 0.0, C.BoomZ));
	}
	MastheadFly->SetRelativeLocation(ToCm(C.MastX, 0.0, C.MastheadZ + 0.08));

	// Deck structure: a cabin on the keelboats; beams and trampolines on the cats; akas and nets on the trimaran.
	const double Loa = C.LengthOverall;
	switch (ModelHull ? EBoatType::Count : C.Type)
	{
	case EBoatType::J22: case EBoatType::Catalina22: case EBoatType::Catalina30:
	{
		const double Len = 0.33 * Loa, Width = 0.62 * C.Beam, Height = C.Type == EBoatType::J22 ? 0.25 : (C.Type == EBoatType::Catalina22 ? 0.4 : 0.55);
		const double X = C.MastX - 0.35 * Len;
		AddBoatPart(CubeMesh, ToCm(X, 0.0, Main.SheerHeight(X) + 0.5 * Height), FVector(Len, Width, Height) * CmPerMeter, White);
		// Cockpit sole, a step down aft.
		const double CX = Main.SternX + 0.17 * Loa;
		AddBoatPart(CubeMesh, ToCm(CX, 0.0, Main.SheerHeight(CX) + 0.01), FVector(0.25 * Loa, 0.55 * C.Beam, 0.02) * CmPerMeter, Grey);
		break;
	}
	case EBoatType::Hobie16:
	{
		const double Y = C.Hulls[1].CenterY - C.Hulls[0].CenterY, MidY = 0.5 * (C.Hulls[1].CenterY + C.Hulls[0].CenterY);
		for (double X : { C.MastX, -1.9 })
		{
			AddRod(Vec3(X, C.Hulls[0].CenterY, Main.SheerZ + 0.02), Vec3(X, C.Hulls[1].CenterY, Main.SheerZ + 0.02), 0.08, Spar);
		}
		AddBoatPart(CubeMesh, ToCm(0.5 * (C.MastX - 1.9), MidY, Main.SheerZ), FVector(C.MastX + 1.9, Y - 0.3, 0.01) * CmPerMeter, Grey);
		break;
	}
	case EBoatType::Lagoon42:
	{
		const double Inner = C.Hulls[1].CenterY - 0.6;
		AddBoatPart(CubeMesh, ToCm(-1.0, 0.0, 1.30), FVector(9.0, 2.0 * Inner, 0.5) * CmPerMeter, White);           // bridgedeck
		AddBoatPart(CubeMesh, ToCm(-0.6, 0.0, 2.45), FVector(6.2, 2.0 * C.Hulls[1].CenterY + 1.2, 1.8) * CmPerMeter, White); // saloon house
		AddBoatPart(CubeMesh, ToCm(1.5, 0.0, 2.80), FVector(0.1, 2.0 * C.Hulls[1].CenterY, 1.0) * CmPerMeter, Grey);     // windows
		AddBoatPart(CubeMesh, ToCm(-4.0, 0.0, 3.40), FVector(3.2, 4.0, 0.08) * CmPerMeter, Grey);                        // flybridge bimini
		AddBoatPart(CubeMesh, ToCm(4.3, 0.0, 1.20), FVector(4.0, 2.0 * Inner, 0.02) * CmPerMeter, Grey);                // forward trampoline
		break;
	}
	case EBoatType::Corsair880:
	{
		for (int32 H = 1; H <= 2; ++H)
		{
			const double Y = C.Hulls[H].CenterY;
			for (double X : { 1.2, -1.7 })
			{
				AddRod(Vec3(X, 0.6 * FMath::Sign(Y), Main.SheerZ - 0.1), Vec3(X, Y, C.Hulls[H].SheerZ), 0.14, White);
			}
			AddBoatPart(CubeMesh, ToCm(-0.25, 0.5 * (0.7 * FMath::Sign(Y) + Y), Main.SheerZ - 0.1), FVector(2.6, FMath::Abs(Y) - 0.9, 0.01) * CmPerMeter, Grey);
		}
		const double CX = Main.SternX + 1.3;
		AddBoatPart(CubeMesh, ToCm(C.MastX - 1.2, 0.0, Main.SheerZ + 0.2), FVector(2.4, 1.3, 0.4) * CmPerMeter, White);
		AddBoatPart(CubeMesh, ToCm(CX, 0.0, Main.SheerZ + 0.01), FVector(2.0, 1.0, 0.02) * CmPerMeter, Grey);
		break;
	}
	default:
		break;
	}

	// Outboards hang on the transom (inboards and saildrives are out of sight).
	for (const FEngineDef& E : C.Engines)
	{
		if (E.Position.X < Main.SternX + 0.2)
		{
			AddBoatPart(CubeMesh, ToCm(E.Position.X - 0.1, E.Position.Y, E.Position.Z + 0.55), FVector(0.3, 0.25, 1.1) * CmPerMeter, Grey);
		}
	}

	// Crew (Visual V3): posed sailors in foul-weather jackets of their own colours (CrewPose.h).
	CrewFigures.Reset();
	static const FLinearColor Jackets[] = { FLinearColor(0.45f, 0.03f, 0.03f), FLinearColor(0.02f, 0.05f, 0.16f), FLinearColor(0.55f, 0.42f, 0.02f), FLinearColor(0.12f, 0.13f, 0.14f) };
	// Visual V7: MetaHumans on the player's boat on Medium and High when they are built (scripts/make-metahumans.sh);
	// the helm is the last figure, the trimmer the one before, the rest work the bow. -SailingBlenderCrew opts out.
	const bool bMeta = !bTrafficBoat && USailingSettings::Get()->Quality != ESailingQuality::Low
		&& !FParse::Param(FCommandLine::Get(), TEXT("SailingBlenderCrew")) && LoadMetaCrew();
	for (int32 I = 0; I < C.CrewCount && bMeta; ++I)
	{
		const int32 CrewRole = I == C.CrewCount - 1 ? 0 : (I == C.CrewCount - 2 ? 1 : 2);
		if (UPoseableMeshComponent* Figure = AddMetaHumanFigure(CrewRole, I))
		{
			Crew.Add(Figure);
			CrewFigures.AddDefaulted_GetRef().Rig = CrewRole;
		}
	}
	for (int32 I = 0; I < C.CrewCount && SailorMesh && !bMeta; ++I)
	{
		UPoseableMeshComponent* Figure = NewObject<UPoseableMeshComponent>(this);
		Figure->SetupAttachment(BoatRoot);
		Figure->SetSkinnedAssetAndUpdate(SailorMesh);
		Figure->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Figure->RegisterComponent();
		for (const TPair<FName, TObjectPtr<UMaterialInterface>>& M : CrewMaterials) Figure->SetMaterialByName(M.Key, M.Value);
		const int32 JacketSlot = Figure->GetMaterialIndex(TEXT("Jacket"));
		if (JacketSlot >= 0)
		{
			if (UMaterialInstanceDynamic* Mid = Figure->CreateDynamicMaterialInstance(JacketSlot))
			{
				Mid->SetVectorParameterValue(TEXT("Color"), Jackets[(I + int32(C.Type)) % UE_ARRAY_COUNT(Jackets)]);
			}
		}
		BoatParts.Add(Figure);
		Crew.Add(Figure);
		CrewFigures.AddDefaulted();
	}

	// Sails as cloth (Visual V3); the telltales are ribbons drawn from it (the old cube telltales stay hidden).
	MainCloth.Init(C.Main, ESailKind::Main);
	JibCloth.Init(C.Jib, ESailKind::Jib);
	SpinCloth.Init(C.Spinnaker, ESailKind::Spinnaker);
	ClothMainHeadZ = C.Main.NumStrips > 0 ? C.Main.Strips[C.Main.NumStrips - 1].ZTop : -1.0;
	TelltaleRibbons->ClearAllMeshSections();
	bTelltalesBuilt = false;
	for (UStaticMeshComponent* T : JibTelltales) T->SetVisibility(false);
	for (UStaticMeshComponent* T : LeechTelltales) T->SetVisibility(false);
	// Per-class sail layouts (Visual V7): the Sunfish's striped sail, the Hobie's coloured panels and seven full battens,
	// tri-radial cruising and racing multihull mains with full battens, the ILCA's three short battens.
	struct FSailLayout { float Layout, Battens, Full; };
	auto LayoutFor = [](EBoatType T) -> FSailLayout
	{
		switch (T)
		{
		case EBoatType::Sunfish: return { 1.f, 0.f, 0.f };
		case EBoatType::ILCA7: return { 0.f, 3.f, 0.f };
		case EBoatType::Hobie16: return { 2.f, 7.f, 1.f };
		case EBoatType::Corsair880: return { 3.f, 5.f, 1.f };
		case EBoatType::Lagoon42: return { 3.f, 5.f, 1.f };
		case EBoatType::Catalina30: return { 0.f, 4.f, 0.f };
		default: return { 0.f, 4.f, 0.f };
		}
	};
	const FSailLayout Lay = LayoutFor(C.Type);
	if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(MainSail->GetMaterial(0)))
	{
		// The J/22's class insignia and number; the other classes' numbers only (where the class carries one). The number
		// is composed from a digit strip in the marks atlas (Graphics G3: each boat its own, from the livery).
		FString Digits;
		for (TCHAR Ch : Livery.SailNumber) if (FChar::IsDigit(Ch)) Digits.AppendChar(Ch);
		Digits = Digits.Right(6);
		Mid->SetScalarParameterValue(TEXT("Marks"), C.Type == EBoatType::J22 ? 1.f : (Digits.IsEmpty() ? 0.f : 2.f));
		Mid->SetScalarParameterValue(TEXT("SailDigits"), float(Digits.Len()));
		Mid->SetScalarParameterValue(TEXT("SailNum"), Digits.IsEmpty() ? 0.f : float(FCString::Atoi(*Digits)));
		Mid->SetScalarParameterValue(TEXT("Battens"), Lay.Battens > 0.f ? 1.f : 0.f);
		Mid->SetScalarParameterValue(TEXT("BattenCount"), Lay.Battens);
		Mid->SetScalarParameterValue(TEXT("FullBattens"), Lay.Full);
		Mid->SetScalarParameterValue(TEXT("Layout"), Lay.Layout);
		Mid->SetScalarParameterValue(TEXT("Height"), C.Main.NumStrips > 0 ? float(C.Main.Strips[C.Main.NumStrips - 1].ZTop - C.Main.Strips[0].ZBottom) : 1.f);
	}
	// Graphics G8 (round 8, the race start: "drab colors"): a club race fleet isn't all white Dacron. Keelboats sailing as
	// traffic with a race wear profile, and a third of the rest, carry laminate sails: smoky grey, grey Mylar or tan aramid
	// (light enough that the dark sail numbers still read). The player's boat keeps the club's Dacron.
	FLinearColor SailColor(0.70f, 0.68f, 0.63f);
	if (bTrafficBoat && !bGhost && Lay.Layout == 0.f && C.Type != EBoatType::ILCA7)
	{
		const uint32 H = (GetUniqueID() * 2654435761u) >> 8;
		if (Livery.Profile == 1 || (H % 100u) < 33u)
		{
			static const FLinearColor Laminates[] = { FLinearColor(0.30f, 0.30f, 0.31f), FLinearColor(0.42f, 0.42f, 0.41f), FLinearColor(0.40f, 0.29f, 0.13f) };
			SailColor = Laminates[(H / 100u) % UE_ARRAY_COUNT(Laminates)];
		}
	}
	if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(MainSail->GetMaterial(0))) Mid->SetVectorParameterValue(TEXT("Color"), SailColor);
	if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(JibSail->GetMaterial(0)))
	{
		Mid->SetVectorParameterValue(TEXT("Color"), SailColor);
		// The jibs match their mains' colours (no battens).
		Mid->SetScalarParameterValue(TEXT("Layout"), Lay.Layout == 2.f ? 2.f : (Lay.Layout == 3.f ? 3.f : 0.f));
		Mid->SetScalarParameterValue(TEXT("Height"), C.Jib.NumStrips > 0 ? float(C.Jib.Strips[C.Jib.NumStrips - 1].ZTop - C.Jib.Strips[0].ZBottom) : 1.f);
	}
	JibSail->SetVisibility(C.HasJib());
	if (C.HasJib()) JibSail->ClearAllMeshSections();
	MainSail->ClearAllMeshSections();
	SpinSail->ClearAllMeshSections();
	SpinSail->SetVisibility(false);

	// Navigation lights (COLREGS Rule 25): red to port and green to starboard at the bow, white at the stern, and the
	// masthead (steaming) light on the front of the mast for motoring. Shown from sunset to sunrise.
	NavLights.Reset();
	const double BowZ = (C.bMultihull ? Main.SheerZ : Main.SheerHeight(Main.BowX - 0.4)) + 0.12;
	const double SternZ = (C.bMultihull ? Main.SheerZ : Main.SheerHeight(Main.SternX + 0.1)) + 0.15;
	const double BowY = C.bMultihull ? 0.5 * C.Beam - 0.3 : 0.3;
	const struct { FVector Pos; FLinearColor Colour; } Specs[] = {
		{ ToCm(Main.BowX - 0.4, -BowY, BowZ), FLinearColor(1.f, 0.05f, 0.03f) },
		{ ToCm(Main.BowX - 0.4, BowY, BowZ), FLinearColor(0.05f, 1.f, 0.2f) },
		{ ToCm(Main.SternX + 0.1, 0.0, SternZ), FLinearColor(1.f, 0.95f, 0.85f) },
		{ ToCm(C.MastX + 0.08, 0.0, DeckZ + 0.6 * (C.MastheadZ - DeckZ)), FLinearColor(1.f, 0.95f, 0.85f) },
	};
	for (const auto& Spec : Specs)
	{
		UStaticMeshComponent* Light = AddBoatPart(SphereMesh, Spec.Pos, FVector(6.f), Spec.Colour);
		if (UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(EmissiveMaterial, this))
		{
			Mid->SetVectorParameterValue(TEXT("Color"), Spec.Colour);
			Mid->SetScalarParameterValue(TEXT("Intensity"), 30.f);
			Light->SetMaterial(0, Mid);
		}
		Light->SetCastShadow(false);
		Light->SetVisibility(false);
		NavLights.Add(Light);
	}
}

const FWindField& ASailboatPawn::GetWind() const
{
	if (const ASailingGameMode* GameMode = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr)
	{
		return GameMode->GetWind();
	}
	return FallbackWind;
}

bool ASailboatPawn::IsTrimAssistActive() const
{
	return USailingSettings::Get()->bTrimAssist && Boat.GetState().Time - LastManualTrimTime > kTrimAssistIdleSeconds;
}

void ASailboatPawn::BeginPlay()
{
	Super::BeginPlay();

	if (TActorIterator<AWaterSurface> It(GetWorld()); It)
	{
		Water = *It;
		WaterSurfaceZ = It->GetSurfaceZ();
	}
	StartLocation = GetActorLocation();
	StartYaw = GetActorRotation().Yaw;
	if (const ASailingGameMode* GM = bTrafficBoat ? nullptr : GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		FLaunchSpot Spot;
		if (GM->GetLaunchSpot(Spot))
		{
			StartLocation = FVector(Spot.X, Spot.Y, 0.0) * CmPerMeter;
			StartYaw = Spot.HeadingDeg;
		}
		if (GM->GetLake().IsLoaded())
		{
			Boat.SetTerrain(&GM->GetLake().Terrain);
			Boat.SetObstacles(&GM->GetLake().Obstacles);
		}
	}
	float StartTwa = 0.f;
	if (!bTrafficBoat && FParse::Value(FCommandLine::Get(), TEXT("SailingTWA="), StartTwa))
	{
		// Point the boat so the wind is StartTwa off the starboard bow (TWA = wind from - heading).
		StartYaw = GetWind().GetParams().FromDegrees - StartTwa;
	}

	TInlineComponentArray<UStaticMeshComponent*> Parts(this);
	for (UStaticMeshComponent* Part : Parts)
	{
		const FString PartName = Part->GetName();
		FLinearColor Color(0.88f, 0.89f, 0.90f);
		if (PartName == TEXT("FlyArrow") || PartName == TEXT("FlyVane")) Color = FLinearColor(0.02f, 0.02f, 0.02f);
		else if (PartName.StartsWith(TEXT("JibTelltale")) || PartName.StartsWith(TEXT("LeechTelltale")))
		{
			// Red on port, green on starboard, as on a real boat; leech telltales red.
			const bool bStarboard = PartName.StartsWith(TEXT("JibTelltale")) && (PartName.Right(1).IsNumeric() && FCString::Atoi(*PartName.Right(1)) % 2 == 1);
			Color = bStarboard ? FLinearColor(0.05f, 0.7f, 0.1f) : FLinearColor(0.85f, 0.05f, 0.05f);
		}
		if (UMaterialInstanceDynamic* Mid = Part->CreateAndSetMaterialInstanceDynamic(0))
		{
			Mid->SetVectorParameterValue(TEXT("Color"), Color);
		}
	}
	// Visual V3: Dacron cloth with seams, batten pockets and (on the J/22's main) the class insignia and sail number;
	// a red nylon spinnaker. Set per boat in RebuildBoatVisuals.
	MainSail->SetMaterial(0, UMaterialInstanceDynamic::Create(SailMainMaterial ? SailMainMaterial.Get() : ShapeMaterial.Get(), this));
	JibSail->SetMaterial(0, UMaterialInstanceDynamic::Create(SailJibMaterial ? SailJibMaterial.Get() : ShapeMaterial.Get(), this));
	SpinSail->SetMaterial(0, UMaterialInstanceDynamic::Create(SailSpinMaterial ? SailSpinMaterial.Get() : ShapeMaterial.Get(), this));
	for (UStaticMeshComponent* T : JibTelltales) T->SetVisibility(false);
	for (UStaticMeshComponent* T : LeechTelltales) T->SetVisibility(false);

	if (bTrafficBoat)
	{
		return; // the traffic manager picks her boat and puts her on the water (InitTraffic)
	}
	FString BoatArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingBoat="), BoatArg))
	{
		// -SailingBoat=Hobie (the first letters of a fleet boat's name, any case), for this run only.
		for (int32 I = 0; I < int32(EBoatType::Count); ++I)
		{
			if (FString(BoatTypeName(EBoatType(I))).Replace(TEXT(" "), TEXT("")).StartsWith(BoatArg.Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase))
			{
				USailingSettings::Get()->BoatType = I;
				break;
			}
		}
	}
	SetBoat(USailingSettings::Get()->BoatType);

	// Sound: one synthesized voice for everything on board.
	Synth = NewObject<USailingSynthWave>(this);
	SoundComponent = NewObject<UAudioComponent>(this, TEXT("Sound"));
	SoundComponent->SetupAttachment(BoatRoot);
	SoundComponent->bAutoActivate = false;
	SoundComponent->bAllowSpatialization = false;
	SoundComponent->SetSound(Synth);
	SoundComponent->RegisterComponent();
	SoundComponent->Play();
	StartSampleLayer();

	bDemo = FParse::Param(FCommandLine::Get(), TEXT("SailingDemo"));
	if (!bTrafficBoat && FParse::Param(FCommandLine::Get(), TEXT("SailingCockpit"))) SetCockpitView(true);
	float HoldTwa = 0.f;
	if (bDemo)
	{
		bDemoTacks = !FParse::Value(FCommandLine::Get(), TEXT("SailingHoldTWA="), HoldTwa);
		// Reset has not stepped the physics yet, so work out the starting tack from the wind and heading.
		const Vec3 W = GetWind().VelocityAt(Vec3(StartLocation.X / CmPerMeter, StartLocation.Y / CmPerMeter, 10.0), Boat.GetState().Time);
		DemoFirstSign = WrapAngle(std::atan2(-W.Y, -W.X) - FMath::DegreesToRadians(StartYaw)) >= 0.0 ? 1.0 : -1.0;
		DemoPilot.TargetTWADeg = bDemoTacks ? 45.0 * DemoFirstSign : HoldTwa * DemoFirstSign;
		DemoPilot.MaxTiller = 0.8;
		CameraYaw = bDemoTacks ? 150.f : 210.f;
		CameraPitch = -14.f;
	}
	// Benchmarks and screenshots: camera angle (degrees) and distance (meters), and a drill to start in.
	FParse::Value(FCommandLine::Get(), TEXT("SailingCamYaw="), CameraYaw);
	FParse::Value(FCommandLine::Get(), TEXT("SailingCamPitch="), CameraPitch);
	float CamMeters = 0.f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingCamDist="), CamMeters))
	{
		CameraDistance = CamMeters * CmPerMeter;
		CameraBoom->TargetArmLength = CameraDistance;
	}
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	// Clean stills outside the capture mode (the blind tests' marina views): no HUD, no on-screen engine messages.
	if (!bTrafficBoat && FParse::Param(FCommandLine::Get(), TEXT("SailingNoHud")))
	{
		USailingSettings::Get()->bShowHud = false;
		GAreScreenMessagesEnabled = false;
	}
	// Stills of the boat's details (crew, fittings): -SailingCamTarget=<forward>,<starboard>,<up> m in the boat frame is
	// what the camera turns about, instead of 3 m over the hull's origin.
	FString CamTarget;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingCamTarget="), CamTarget, false))
	{
		TArray<FString> P;
		CamTarget.ParseIntoArray(P, TEXT(","));
		if (P.Num() == 3)
		{
			CameraBoom->SetRelativeLocation(FVector(FCString::Atof(*P[0]), FCString::Atof(*P[1]), FCString::Atof(*P[2])) * CmPerMeter);
			CameraBoom->SocketOffset = FVector::ZeroVector;
			CameraBoom->bEnableCameraLag = false;
		}
	}
	FString CaptureArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingCapture="), CaptureArg))
	{
		CapturePreset = ParseCapturePreset(CaptureArg);
		SetupCapture();
		GAreScreenMessagesEnabled = false; // engine warnings (VSM overflow) would be burned into the still
	}
	FString DrillArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingDrill="), DrillArg))
	{
		for (int32 I = 1; I < int32(ESailingDrill::Count); ++I)
		{
			if (DrillArg.Equals(FString(DrillName(ESailingDrill(I))).Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase) || DrillArg == FLearningContent::DrillId(ESailingDrill(I)))
			{
				MenuDrill = ESailingDrill(I);
				StartDrill(MenuDrill);
			}
		}
	}
	// Graphics G4: a session from the front end starts its drill (the race starts with the traffic, TrafficManager.cpp).
	if (const USailSessionSubsystem* Session = USailSessionSubsystem::Get(this); Session && Session->bHasActive && !bTrafficBoat && DrillArg.IsEmpty()
		&& Session->Active.Mode == ESailMode::Drill)
	{
		MenuDrill = ESailingDrill(FMath::Clamp(Session->Active.DrillIndex + 1, 1, int32(ESailingDrill::Count) - 1));
		StartDrill(MenuDrill);
	}
	if (FParse::Param(FCommandLine::Get(), TEXT("SailingMenu"))) bMenuOpen = true; // screenshots of the settings menu
	if (FParse::Param(FCommandLine::Get(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker(); // start with it up
}

void ASailboatPawn::ApplyDifficulty()
{
	const bool bEasy = USailingSettings::Get()->Difficulty == ESailingDifficulty::Easy;
	FBoatConfig& Config = Boat.GetMutableConfig();
	const FBoatConfig Defaults = FBoatConfig::Make(Config.Type);
	// Easy: the helm holds the tiller rigidly (no weather-helm drift) and the boat rolls less in gusts.
	Config.HelmStiffness = bEasy ? 1.0e5 : Defaults.HelmStiffness;
	Config.ExtraRollDamping = bEasy ? 2500.0 * Boat.TotalMass() / 1052.0 : 0.0;
}

void ASailboatPawn::ResetBoat()
{
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		FLaunchSpot Spot;
		if (GM->GetLaunchSpot(Spot) && !FParse::Param(FCommandLine::Get(), TEXT("SailingKeepStart")))
		{
			StartLocation = FVector(Spot.X, Spot.Y, 0.0) * CmPerMeter;
			StartYaw = Spot.HeadingDeg;
		}
	}
	float StartTwa = 0.f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingTWA="), StartTwa))
	{
		StartYaw = GetWind().GetParams().FromDegrees - StartTwa; // recordings and benchmarks start on a set point of sail
	}
	Boat.GetMooringLines().clear();
	// Keep the clock running through a reset: the weather, wind and waves all run on it.
	const double Time = Boat.GetState().Time;
	Boat.Reset(StartLocation.X / CmPerMeter, StartLocation.Y / CmPerMeter, FMath::DegreesToRadians(StartYaw), StartSpeedKnots * kKnot);
	Boat.GetMutableState().Time = Time;
	Controls = FBoatControls();
	Controls.MainSheet = 0.45;
	Controls.JibSheet = 0.45;
	// -SailingSpinnaker: start with it up, whenever the boat is (re)started.
	if (!bTrafficBoat && FParse::Param(FCommandLine::Get(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker();
	int32 ReefArg = 0;
	if (!bTrafficBoat && FParse::Value(FCommandLine::Get(), TEXT("SailingReef="), ReefArg))
	{
		Controls.Reef = FMath::Clamp(ReefArg, 0, int32(Boat.GetConfig().ReefLuffFraction.size()));
	}
	TrimAssist.Reset();
	KeyboardTiller = 0.f;
	ApplyStateToTransform();
	Plot.Start(GetMapPosition(), Time); // the departure is a known position
	if (!bTrafficBoat) BeginRun(TEXT("Sail"));
}

void ASailboatPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bKeysOpen) PollKeyCapture();
	if (!bTrafficBoat && (bWatching || bPhoto))
	{
		// The world holds still (everything runs on the boat's clock); only the replay and the cameras move.
		if (bPhoto)
		{
			// The lens: [ and ] (the twin-engine pivot keys) zoom in and out.
			const float Zoom = HeldAxes.FindRef(TEXT("ThrottleSplit"));
			if (Zoom != 0.f) Camera->SetFieldOfView(FMath::Clamp(Camera->FieldOfView - Zoom * 30.f * DeltaSeconds, 10.f, 110.f));
			UpdatePhotoLens();
		}
		UpdateGhost(DeltaSeconds);
		return;
	}
	if (bTrafficBoat)
	{
		// The traffic simulation sails her; draw where she is, her rig and sails, and her lights.
		ApplyStateToTransform();
		UpdateRigVisuals(DeltaSeconds);
		UpdateNavLights();
		return;
	}
	ApplyHeldInputs(DeltaSeconds);
	if (Controls.bRighting && FMath::Abs(Boat.GetTelemetry().Heel) < 20.0 * kDegToRad && Boat.GetState().CrewOffsetZ > -0.05)
	{
		Controls.bRighting = false; // back aboard once she is up
	}
	if (bDemo)
	{
		// Close-hauled from the start, tack after 9 s and every 12 s after that; the camera drifts around the boat.
		const double T = Boat.GetState().Time;
		if (bDemoTacks)
		{
			const int32 Leg = T < 9.0 ? 0 : 1 + int32((T - 9.0) / 12.0);
			DemoPilot.TargetTWADeg = 45.0 * DemoFirstSign * (Leg % 2 == 0 ? 1.0 : -1.0);
		}
		Controls.Tiller = DemoPilot.Update(Boat);
		if (bDemoTacks)
		{
			CameraYaw = FMath::UnwindDegrees(CameraYaw + 4.f * DeltaSeconds);
		}
		CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	}

	const FWindField& Wind = GetWind();
	const ASailingGameMode* GameMode = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FWaveField* Waves = GameMode ? &GameMode->GetWaves() : nullptr;
	const bool bSimple = USailingSettings::Get()->UseSimpleControls();
	if (GameMode)
	{
		// The tidal current where the boat is (it changes over minutes and kilometers, so once a frame is plenty).
		const Vec3 O = Boat.OriginPosition();
		Boat.SetWaterCurrent(GameMode->GetCurrentAt(O.X, O.Y));
	}
	// Graphics G4: the front end and the loading screen hold the boat where it is (the world keeps moving behind them).
	const int32 Steps = bHeldByUI && !bTrafficBoat ? 0 : Stepper.Advance(DeltaSeconds);
	for (int32 I = 0; I < Steps; ++I)
	{
		const FBoatControls Before = Controls;
		if (IsTrimAssistActive() || bSimple)
		{
			const FBoatControls Assisted = TrimAssist.Update(Boat, Controls, Stepper.GetStepDt());
			if (IsTrimAssistActive())
			{
				Controls = Assisted;
			}
			else
			{
				// Simple layout: the crew handles traveler and sail shape; you keep the sheets and hiking.
				Controls.Traveler = Assisted.Traveler;
				Controls.Vang = Assisted.Vang;
				Controls.Cunningham = Assisted.Cunningham;
				Controls.Outhaul = Assisted.Outhaul;
				Controls.Backstay = Assisted.Backstay;
			}
			Controls.Tiller = Before.Tiller;
			Controls.bWingOnWing = Before.bWingOnWing;
		}
		Boat.Step(Stepper.GetStepDt(), Controls, Wind, Waves);
	}
	ApplyStateToTransform();
	UpdateRigVisuals(DeltaSeconds);
	if (IsCaptureMode() && !bTrafficBoat) UpdateCapture(DeltaSeconds);

	if (Water)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const Vec3 O = Boat.OriginPosition();
		Water->SetBoatForWake(FVector2D(O.X, O.Y), T.Heading, T.BoatSpeed, T.Heel);
	}
	UpdateSound(DeltaSeconds);
	if (bCockpit) UpdateCockpitCamera(DeltaSeconds);

	// Drills: follow the boat and the crew's actions.
	const FBoatTelemetry& Tel = Boat.GetTelemetry();
	if (Tel.bCollision) MaxContactKnots = FMath::Max(MaxContactKnots, Tel.BoatSpeed / kKnot);
	if (DrillRunner.IsActive())
	{
		FDrillContext Ctx;
		Ctx.bTiedUp = IsTiedUp();
		Ctx.bBackJib = Controls.bBackJib;
		Ctx.MaxContactSpeed = MaxContactKnots;
		DrillRunner.Update(Boat, Ctx, DeltaSeconds);
		// Graphics G4: a passed drill is remembered for the front end ("6 drills, N passed").
		if (DrillRunner.IsComplete() && !bTrafficBoat)
		{
			USailSessionSave* Save = USailSessionSave::Get();
			const int32 Index = int32(DrillRunner.GetDrill()) - 1;
			if (Index >= 0 && !Save->DrillsPassed.Contains(Index)) { Save->DrillsPassed.Add(Index); Save->SaveConfig(); }
		}
	}
	UpdateDrillVisuals();
	if (!bTrafficBoat && !bGhost) UpdateLearning();

	// Screenshots and the gate: -SailingChart=<m per pixel> opens the chart, -SailingPlotFix takes three bearings.
	if (!bChartArgsApplied && Boat.GetState().Time > 2.0 && GameMode)
	{
		bChartArgsApplied = true;
		if (FParse::Param(FCommandLine::Get(), TEXT("SailingPlotFix")))
		{
			// The three nearest charted aids within 3 nm that spread around the horizon.
			const FVector2D Me = GetMapPosition();
			TArray<const FNavaid*> Aids;
			for (const FNavaid& N : GameMode->GetLake().Navaids) if (FVector2D::Distance(Me, FVector2D(N.X, N.Y)) < 5556.0) Aids.Add(&N);
			Aids.Sort([&](const FNavaid& A, const FNavaid& B) { return FVector2D::Distance(Me, FVector2D(A.X, A.Y)) < FVector2D::Distance(Me, FVector2D(B.X, B.Y)); });
			TArray<double> Taken;
			for (const FNavaid* N : Aids)
			{
				const double Brg = SailingNav::BearingDeg(Me, FVector2D(N->X, N->Y));
				bool bSpread = true;
				for (double T : Taken) { const double Cut = FMath::Abs(FMath::Fmod(Brg - T + 360.0, 180.0)); if (Cut < 40.0 || Cut > 140.0) bSpread = false; }
				if (!bSpread) continue;
				Taken.Add(Brg);
				RecordBearing(N->Name, FVector2D(N->X, N->Y));
				if (Taken.Num() == 3) break;
			}
		}
		double ChartZoom = 0.0;
		if (FParse::Value(FCommandLine::Get(), TEXT("SailingChart="), ChartZoom) && GameMode->GetChart().IsLoaded())
		{
			SetChartOpen(true);
			ChartMetersPerPixel = ChartZoom;
			ChartCenter = GetMapPosition();
		}
		if (FParse::Param(FCommandLine::Get(), TEXT("SailingNoGps"))) bShowGps = false;
		if (FParse::Param(FCommandLine::Get(), TEXT("SailingLogOpen"))) bLogOpen = true;
		if (FParse::Param(FCommandLine::Get(), TEXT("SailingKeys"))) { BuildKeyRows(); bKeysOpen = true; KeysMessage = TEXT("Up / Down choose, Enter then press the new key, Backspace restores the default, Tab closes"); }
	}

	// Scripted debrief checks: -SailingGhostAt=<s> resets then sails beside the ghost of the run so far;
	// -SailingWatchAt=<s> starts watching it.
	{
		static float GhostAt = -1.f, WatchAt = -1.f;
		static bool bParsed = false;
		if (!bParsed)
		{
			bParsed = true;
			FParse::Value(FCommandLine::Get(), TEXT("SailingGhostAt="), GhostAt);
			FParse::Value(FCommandLine::Get(), TEXT("SailingWatchAt="), WatchAt);
		}
		if (GhostAt > 0.f && Boat.GetState().Time >= GhostAt)
		{
			GhostAt = -1.f;
			ResetBoat();
			bGhostOn = !LastRun.IsEmpty();
			// Start 15 m to port of the ghost; on the same autopilot course she would sail exactly inside it.
			Sailing::FBoatState& S = Boat.GetMutableState();
			S.Position = S.Position + S.Orientation.Rotate(Sailing::Vec3(0.0, -15.0, 0.0));
		}
		if (WatchAt > 0.f && Boat.GetState().Time >= WatchAt)
		{
			WatchAt = -1.f;
			BeginRun(TEXT("Sail"));
			if (!LastRun.IsEmpty()) { SetWatching(true); WatchTime = 0.5 * LastRun.Duration(); }
		}
	}

	// Dead reckoning on the compass heading and the log (speed through the water).
	Plot.Advance(GetHeadingTrueDeg(), Tel.SpeedThroughWater, DeltaSeconds, Boat.GetState().Time);
	UpdateNavLights();
	UpdateLogbook(DeltaSeconds);
	Recording.Record(Boat);
	UpdateGhost(DeltaSeconds);
}

Sailing::FBoatModel* ASailboatPawn::InitTraffic(int32 Type, double X, double Y, double HeadingRad)
{
	SetBoat(Type);
	const double Time = Boat.GetState().Time;
	Boat.Reset(X, Y, HeadingRad, 2.0);
	Boat.GetMutableState().Time = Time;
	ApplyStateToTransform();
	return &Boat;
}

void ASailboatPawn::SetHorn(float Level, float Hz)
{
	if (!Synth) return;
	Synth->Params.HornLevel.store(Level);
	Synth->Params.HornHz.store(Hz);
}

bool ASailboatPawn::IsMotoring() const
{
	return !Boat.GetConfig().Engines.empty() && FMath::Abs(Controls.Throttle) > 0.02;
}

void ASailboatPawn::SetChartOpen(bool bOpen)
{
	bChartOpen = bOpen;
	// The chart covers the screen: skip drawing the world under it (the boat keeps sailing).
	if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport()) Viewport->bDisableWorldRendering = bOpen;
}

FVector2D ASailboatPawn::GetMapPosition() const
{
	const Vec3 O = Boat.OriginPosition();
	return FVector2D(O.X, O.Y);
}

double ASailboatPawn::GetHeadingTrueDeg() const
{
	return SailingNav::NormalizeDeg(FMath::RadiansToDegrees(Boat.GetTelemetry().Heading));
}

bool ASailboatPawn::TakeBearing()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const double Now = Boat.GetState().Time;
	StatusUntil = Now + 4.0;
	if (!GM || GM->GetLake().Navaids.Num() == 0)
	{
		StatusMessage = TEXT("Nothing charted to take a bearing on here");
		return false;
	}
	// Sight along the camera: the charted object nearest the line of sight within 6 degrees, in sight range.
	const FLakeData& Lake = GM->GetLake();
	const FVector2D Me = GetMapPosition();
	const double Sight = SailingNav::NormalizeDeg(Camera->GetComponentRotation().Yaw);
	const bool bDark = GM->IsDark();
	const double Visibility = FMath::Min(GM->GetWeatherState().VisibilityKm * 1000.0, 15000.0);
	FString BestName;
	FVector2D BestPos;
	double BestError = 6.0;
	auto Consider = [&](const FString& Name, const FVector2D& Pos, double Range)
	{
		const double Dist = FVector2D::Distance(Me, Pos);
		if (Dist > FMath::Min(Range, Visibility) || Dist < 20.0) return;
		const double Error = FMath::Abs(FMath::UnwindDegrees(SailingNav::BearingDeg(Me, Pos) - Sight));
		if (Error < BestError) { BestError = Error; BestName = Name; BestPos = Pos; }
	};
	for (const FNavaid& N : Lake.Navaids)
	{
		// By day, aids are seen to a few miles; at night only the lights, out to their range.
		const double Range = bDark ? (N.bLit ? (N.Light.RangeNm > 0.0 ? N.Light.RangeNm : 3.0) * SailingNav::MetersPerNauticalMile : 0.0) : 3.0 * SailingNav::MetersPerNauticalMile;
		Consider(N.Name.IsEmpty() ? FString(TEXT("Aid")) : N.Name, FVector2D(N.X, N.Y), Range);
	}
	if (!bDark)
	{
		for (const FLandmark& L : Lake.Landmarks)
		{
			Consider(L.Name.IsEmpty() ? FString(TEXT("Landmark")) : L.Name, FVector2D(L.X, L.Y), (L.bConspicuous ? 8.0 : 4.0) * SailingNav::MetersPerNauticalMile);
		}
	}
	if (BestName.IsEmpty())
	{
		StatusMessage = TEXT("No charted mark in your line of sight: turn the camera onto a buoy, beacon, light or landmark and press U");
		return false;
	}
	return RecordBearing(BestName, BestPos);
}

bool ASailboatPawn::RecordBearing(const FString& Name, const FVector2D& Object)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const double Variation = GM ? GM->GetLake().VariationDeg : 0.0;
	const FVector2D Me = GetMapPosition();
	const double Now = Boat.GetState().Time;
	// The hand-bearing compass reads magnetic; on Realistic it carries the usual degree or two of error.
	double Magnetic = SailingNav::TrueToMagnetic(SailingNav::BearingDeg(Me, Object), Variation);
	if (USailingSettings::Get()->Difficulty == ESailingDifficulty::Realistic)
	{
		Magnetic += (FMath::FRand() + FMath::FRand() + FMath::FRand() - 1.5) * 2.0;
	}
	SailingNav::FBearing B;
	B.ObjectName = Name;
	B.Object = Object;
	B.MagneticDeg = SailingNav::NormalizeDeg(FMath::RoundToDouble(Magnetic));
	B.Time = Now;
	const bool bFix = Plot.AddBearing(B, Variation);
	if (bFix) AddLogEvent(FString::Printf(TEXT("Fix by bearings (last on %s, %03.0f M); cocked hat %.0f m"), *Name, B.MagneticDeg, Plot.FixSpread));
	StatusMessage = FString::Printf(TEXT("Bearing %03.0f M on %s%s"), B.MagneticDeg, *Name,
		bFix ? *FString::Printf(TEXT(": fix plotted (%s from the GPS position)"), *SailingNav::FormatDistance(FVector2D::Distance(Plot.Fix, Me)))
			: TEXT(" (take another at least 30 degrees away for a fix)"));
	StatusUntil = Now + 4.0;
	return true;
}

FLogEntry ASailboatPawn::MakeLogEntry(const TCHAR* Kind, const FString& Remarks) const
{
	FLogEntry E;
	E.Kind = Kind;
	E.Remarks = Remarks;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FVector2D P = GetMapPosition();
	if (GM)
	{
		E.UnixTime = GM->GetUnixTime();
		const int32 Minutes = int32(FMath::Fmod(GM->GetLocalHour(), 24.0) * 60.0);
		E.Clock = FString::Printf(TEXT("%02d:%02d"), Minutes / 60, Minutes % 60);
		// The map is a local projection about the area's origin: near enough for a log's position.
		const double Lat0 = GM->GetLake().Latitude, Lon0 = GM->GetLake().Longitude;
		E.Latitude = Lat0 + P.X / 111320.0;
		E.Longitude = Lon0 + P.Y / (111320.0 * FMath::Cos(FMath::DegreesToRadians(Lat0)));
		E.HeadingMagnetic = SailingNav::TrueToMagnetic(GetHeadingTrueDeg(), GM->GetLake().VariationDeg);
		E.WindFromDeg = SailingNav::NormalizeDeg(GM->GetWeatherState().Wind.FromDegrees);
		E.WindKnots = T.TrueWindSpeed / kKnot;
		E.SeaMeters = GM->GetWaves().SignificantHeight();
	}
	const Vec3 V = Boat.GetState().Velocity;
	E.SpeedKnots = FMath::Sqrt(V.X * V.X + V.Y * V.Y) / kKnot;
	E.CourseTrue = SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(V.Y, V.X)));
	E.LogNm = LogNm;
	return E;
}

namespace
{
	/** Plain words for each command (and its negative direction). */
	FString CommandLabel(FName Action, bool bNegative)
	{
		static const TMap<FString, TPair<FString, FString>> Names = {
			{ TEXT("Tiller"), { TEXT("Steer: bow to starboard"), TEXT("Steer: bow to port") } },
			{ TEXT("MainSheet"), { TEXT("Mainsheet: ease"), TEXT("Mainsheet: trim") } },
			{ TEXT("JibSheet"), { TEXT("Jib sheet: ease"), TEXT("Jib sheet: trim") } },
			{ TEXT("Traveler"), { TEXT("Traveler: to leeward"), TEXT("Traveler: to windward") } },
			{ TEXT("Hike"), { TEXT("Crew: hike out"), TEXT("Crew: move in") } },
			{ TEXT("Vang"), { TEXT("Vang: on"), TEXT("Vang: ease") } },
			{ TEXT("Cunningham"), { TEXT("Cunningham: on"), TEXT("Cunningham: ease") } },
			{ TEXT("Outhaul"), { TEXT("Outhaul: on"), TEXT("Outhaul: ease") } },
			{ TEXT("Backstay"), { TEXT("Backstay: on"), TEXT("Backstay: ease") } },
			{ TEXT("Throttle"), { TEXT("Engine: ahead"), TEXT("Engine: astern") } },
			{ TEXT("ThrottleSplit"), { TEXT("Twin engines: pivot to starboard"), TEXT("Twin engines: pivot to port") } },
			{ TEXT("WingOnWing"), { TEXT("Wing-on-wing"), TEXT("") } }, { TEXT("BackJib"), { TEXT("Back the jib"), TEXT("") } },
			{ TEXT("DockLines"), { TEXT("Dock lines"), TEXT("") } }, { TEXT("Spinnaker"), { TEXT("Spinnaker up / down"), TEXT("") } },
			{ TEXT("Reef"), { TEXT("Reef"), TEXT("") } }, { TEXT("Board"), { TEXT("Board up / down"), TEXT("") } },
			{ TEXT("Righting"), { TEXT("Right a capsized boat"), TEXT("") } }, { TEXT("EngineNeutral"), { TEXT("Engine to neutral"), TEXT("") } },
			{ TEXT("ToggleLearning"), { TEXT("Learning mode"), TEXT("") } }, { TEXT("ToggleDifficulty"), { TEXT("Difficulty"), TEXT("") } },
			{ TEXT("ToggleHud"), { TEXT("Instruments"), TEXT("") } }, { TEXT("ResetBoat"), { TEXT("Reset the boat"), TEXT("") } },
			{ TEXT("Chart"), { TEXT("Chart"), TEXT("") } }, { TEXT("Bearing"), { TEXT("Take a bearing"), TEXT("") } },
			{ TEXT("Gps"), { TEXT("GPS on the chart"), TEXT("") } }, { TEXT("ClearPlot"), { TEXT("Clear the plot"), TEXT("") } },
			{ TEXT("Logbook"), { TEXT("Ship's log"), TEXT("") } }, { TEXT("Replay"), { TEXT("Watch your last run"), TEXT("") } },
			{ TEXT("Photo"), { TEXT("Photo mode"), TEXT("") } }, { TEXT("PhotoShot"), { TEXT("Take a photo / choose"), TEXT("") } },
			{ TEXT("CockpitView"), { TEXT("Cockpit view (the helm's eyes)"), TEXT("") } },
			{ TEXT("ControlsCard"), { TEXT("Controls card"), TEXT("") } }, { TEXT("Menu"), { TEXT("Settings"), TEXT("") } },
		};
		if (const TPair<FString, FString>* N = Names.Find(Action.ToString())) return bNegative && !N->Value.IsEmpty() ? N->Value : N->Key;
		return Action.ToString();
	}
}

void ASailboatPawn::BuildKeyRows()
{
	KeyRows.Reset();
	// One row per command and direction, showing its first keyboard key (mouse and gamepad stay as they are).
	for (const FSailingKeyBinding& B : GetDefault<USailingInputSettings>()->GetBindings())
	{
		if (B.Key.IsGamepadKey() || B.Key.IsMouseButton() || B.Key.IsAxis1D() || B.Key.IsAxis2D()) continue;
		if (B.Action.ToString().StartsWith(TEXT("Menu")) && B.Action != TEXT("Menu")) continue; // arrow keys stay arrows
		const bool bNeg = B.Scale < 0.f;
		if (KeyRows.ContainsByPredicate([&](const FKeyRow& R) { return R.Action == B.Action && R.bNegative == bNeg; })) continue;
		FKeyRow Row;
		Row.Action = B.Action;
		Row.bNegative = bNeg;
		Row.Label = CommandLabel(B.Action, bNeg);
		Row.Key = B.Key;
		KeyRows.Add(Row);
	}
}

void ASailboatPawn::PollKeyCapture()
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC || !bCapturingKey || GFrameCounter <= CaptureFrame + 1) return;
	if (PC->WasInputKeyJustPressed(EKeys::Escape))
	{
		bCapturingKey = false;
		KeysMessage = TEXT("Cancelled");
		return;
	}
	if (PC->WasInputKeyJustPressed(EKeys::BackSpace))
	{
		// Restore this command's default key.
		bCapturingKey = false;
		const FKeyRow& Row = KeyRows[KeysIndex];
		for (const FSailingKeyBinding& B : GetDefault<USailingInputSettings>()->GetDefaults())
		{
			if (B.Action == Row.Action && (B.Scale < 0.f) == Row.bNegative && !B.Key.IsGamepadKey() && !B.Key.IsMouseButton() && !B.Key.IsAxis1D() && !B.Key.IsAxis2D())
			{
				AssignKey(KeysIndex, B.Key);
				break;
			}
		}
		return;
	}
	TArray<FKey> All;
	EKeys::GetAllKeys(All);
	for (const FKey& K : All)
	{
		if (K.IsGamepadKey() || K.IsMouseButton() || K.IsAxis1D() || K.IsAxis2D() || K.IsTouch() || K == EKeys::Escape || K == EKeys::BackSpace) continue;
		if (K.IsModifierKey()) continue;
		if (PC->WasInputKeyJustPressed(K))
		{
			bCapturingKey = false;
			AssignKey(KeysIndex, K);
			return;
		}
	}
}

void ASailboatPawn::AssignKey(int32 Row, const FKey& Key)
{
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	if (Settings->Bindings.Num() == 0) Settings->Bindings = Settings->GetDefaults();
	FKeyRow& Target = KeyRows[Row];
	const FKey Old = Target.Key;
	// If another command had this key, it takes this one's old key (a swap, so nothing is left without a key).
	FString Swapped;
	for (FSailingKeyBinding& B : Settings->Bindings)
	{
		if (B.Key == Key && !(B.Action == Target.Action && (B.Scale < 0.f) == Target.bNegative))
		{
			B.Key = Old;
			Swapped = CommandLabel(B.Action, B.Scale < 0.f);
		}
	}
	for (FSailingKeyBinding& B : Settings->Bindings)
	{
		if (B.Action == Target.Action && (B.Scale < 0.f) == Target.bNegative && B.Key == Old) { B.Key = Key; break; }
	}
	Settings->SaveConfig();
	RebuildMappings();
	BuildKeyRows();
	KeysMessage = Swapped.IsEmpty() ? FString::Printf(TEXT("%s: %s"), *Target.Label, *Key.GetDisplayName().ToString())
		: FString::Printf(TEXT("%s: %s (swapped: %s now %s)"), *CommandLabel(Target.Action, Target.bNegative), *Key.GetDisplayName().ToString(), *Swapped, *Old.GetDisplayName().ToString());
}

bool ASailboatPawn::Rebind(FName Action, bool bNegative, const FKey& Key)
{
	BuildKeyRows();
	const int32 Row = KeyRows.IndexOfByPredicate([&](const FKeyRow& R) { return R.Action == Action && R.bNegative == bNegative; });
	if (Row == INDEX_NONE) return false;
	AssignKey(Row, Key);
	return true;
}

void ASailboatPawn::RebuildMappings()
{
	// The same actions (bound to the same handlers), mapped to the new keys.
	UInputMappingContext* Context = NewObject<UInputMappingContext>(this, TEXT("IMC_Sailboat_Rebound"));
	for (const FSailingKeyBinding& Binding : GetDefault<USailingInputSettings>()->GetBindings())
	{
		const TObjectPtr<UInputAction>* Action = Actions.Find(Binding.Action);
		if (!Action || !*Action) continue;
		FEnhancedActionKeyMapping& Mapping = Context->MapKey(*Action, Binding.Key);
		if (Binding.Scale < 0.f) Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(Context));
		if (FMath::Abs(Binding.Scale) != 1.f)
		{
			UInputModifierScalar* Scalar = NewObject<UInputModifierScalar>(Context);
			Scalar->Scalar = FVector(FMath::Abs(Binding.Scale));
			Mapping.Modifiers.Add(Scalar);
		}
	}
	MappingContext = Context;
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->ClearAllMappings();
			Subsystem->AddMappingContext(MappingContext, 0);
		}
	}
}

void ASailboatPawn::BeginRun(const FString& Label)
{
	// The run that just ended becomes the one to replay (if there was anything to it).
	if (Recording.Duration() > 20.0) LastRun = Recording;
	Recording.Begin(int32(Boat.GetConfig().Type), Label, Boat.GetState().Time);
}

ASailboatPawn* ASailboatPawn::EnsureGhost()
{
	if (GhostBoat && GhostBoat->GetBoatModel().GetConfig().Type == EBoatType(LastRun.BoatType)) return GhostBoat;
	if (GhostBoat) GhostBoat->Destroy();
	GhostBoat = GetWorld()->SpawnActorDeferred<ASailboatPawn>(ASailboatPawn::StaticClass(), GetActorTransform(), nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!GhostBoat) return nullptr;
	GhostBoat->bTrafficBoat = true;
	GhostBoat->bGhost = true;
	GhostBoat->AutoPossessPlayer = EAutoReceiveInput::Disabled;
	GhostBoat->AutoPossessAI = EAutoPossessAI::Disabled;
	GhostBoat->FinishSpawning(GetActorTransform());
	GhostBoat->InitTraffic(LastRun.BoatType, 0.0, 0.0, 0.0);
	GhostBoat->ApplyGhostMaterial();
	return GhostBoat;
}

void ASailboatPawn::ApplyGhostMaterial()
{
	UMaterialInterface* Ghost = GhostMaterial;
	if (!Ghost) return;
	TInlineComponentArray<UMeshComponent*> Meshes(this);
	for (UMeshComponent* M : Meshes)
	{
		M->SetCastShadow(false);
		for (int32 I = 0; I < FMath::Max(M->GetNumMaterials(), 4); ++I) M->SetMaterial(I, Ghost);
	}
	for (UStaticMeshComponent* L : NavLights) if (L) L->SetVisibility(false);
}

void ASailboatPawn::SetGhostFrame(const FReplayFrame& Frame)
{
	FReplay::Apply(Frame, Boat);
	ApplyStateToTransform();
}

void ASailboatPawn::AddCameraOrbit(const FVector2D& Delta, float ZoomDelta)
{
	CameraYaw = FMath::UnwindDegrees(CameraYaw + Delta.X);
	CameraPitch = FMath::Clamp(CameraPitch + Delta.Y, -85.f, 20.f);
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	if (ZoomDelta != 0.f)
	{
		CameraDistance = FMath::Clamp(CameraDistance - ZoomDelta * 150.f, 400.f, 8000.f);
		CameraBoom->TargetArmLength = CameraDistance;
	}
}

void ASailboatPawn::UpdateGhost(float DeltaSeconds)
{
	if (bWatching)
	{
		WatchTime = FMath::Min(WatchTime + DeltaSeconds * WatchSpeed, LastRun.Duration());
	}
	const bool bShow = bWatching || (bGhostOn && !LastRun.IsEmpty());
	if (!bShow)
	{
		if (GhostBoat) GhostBoat->SetActorHiddenInGame(true);
		return;
	}
	// The ghost sails her run in step with yours (from the start of each), or at the replay's own time.
	const double T = bWatching ? WatchTime : Boat.GetState().Time - Recording.StartTime;
	FReplayFrame Frame;
	ASailboatPawn* G = EnsureGhost();
	if (!G) return;
	if (LastRun.Sample(T, Frame))
	{
		G->SetGhostFrame(Frame);
		G->SetActorHiddenInGame(false);
	}
	else
	{
		G->SetActorHiddenInGame(true);
	}
}

void ASailboatPawn::SetWatching(bool bOn)
{
	bWatching = bOn;
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (bOn)
	{
		bPhoto = false;
		WatchTime = 0.0;
		WatchSpeed = 1.f;
		UpdateGhost(0.f);
		if (PC && GhostBoat) PC->SetViewTargetWithBlend(GhostBoat, 0.5f);
		SetActorHiddenInGame(true); // the replay alone
	}
	else
	{
		if (PC) PC->SetViewTargetWithBlend(this, 0.5f);
		SetActorHiddenInGame(false);
		if (GhostBoat && !bGhostOn) GhostBoat->SetActorHiddenInGame(true);
	}
}

void ASailboatPawn::SetCockpitView(bool bOn)
{
	bCockpit = bOn;
	CockpitAccel = CockpitHead = FVector::ZeroVector;
	CockpitPrevVel = FVector(Boat.GetState().Velocity.X, Boat.GetState().Velocity.Y, Boat.GetState().Velocity.Z);
	CockpitRoll = 0.f;
	// The head is placed in the world each frame, free of the chase camera's arm and its lag.
	Camera->SetUsingAbsoluteLocation(bOn);
	Camera->SetUsingAbsoluteRotation(bOn);
	if (bOn) { CameraPitch = -8.f; CameraYaw = 0.f; }
	else
	{
		if (Crew.Num() > 0 && Crew.Last()) Crew.Last()->SetVisibility(true, true);
		Camera->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator::ZeroRotator);
		Camera->SetFieldOfView(90.f);
		CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	}
	StatusMessage = bOn ? TEXT("Cockpit view: you are at the helm. Look around with the mouse; press \\ for the chase camera") : TEXT("Chase camera");
	StatusUntil = Boat.GetState().Time + 3.0;
}

void ASailboatPawn::UpdateCockpitCamera(float DeltaSeconds)
{
	// The helm's head: on the windward side of the cockpit, about 0.8 m above the seat (or the rail when hiking).
	const FBoatConfig& C = Boat.GetConfig();
	const FBoatState& S = Boat.GetState();
	const int32 N = FMath::Max(C.CrewCount, 1);
	const double X = C.CrewCG.X + 0.55 * (0.5 * (N - 1) - (N - 1));
	const FHullShape& H = C.Hulls[0];
	const double Rail = C.bMultihull ? FMath::Abs(C.Hulls.back().CenterY) + 0.2 : H.DeckHalfBeam(X);
	const double Sheer = C.bMultihull ? H.SheerZ + 0.1 : H.SheerHeight(X);
	const float Side = S.CrewOffset != 0.0 ? float(FMath::Sign(S.CrewOffset)) : float(S.WindwardSide);
	const FVector Eye = FVector(X, Side * FMath::Max(Rail - 0.3, 0.25), Sheer + 0.85) * CmPerMeter;

	// Accelerations felt at the head (the boat's, low-passed over 0.3 s): surging forward pushes the head back, a wave
	// lifting the boat sinks it a little; plus a head-bob the neck lets through. A few centimetres at most.
	const float Dt = FMath::Max(DeltaSeconds, 1e-3f);
	const FVector Vel(S.Velocity.X, S.Velocity.Y, S.Velocity.Z);
	const FVector Acc = (Vel - CockpitPrevVel) / Dt;
	CockpitPrevVel = Vel;
	CockpitAccel += (Acc - CockpitAccel) * FMath::Clamp(Dt / 0.3f, 0.f, 1.f);
	const FVector AccBoat = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(CockpitAccel);
	const FVector Target = (-AccBoat * 1.2f).GetClampedToMaxSize(10.f); // cm per m/s^2, at most 10 cm
	CockpitHead += (Target - CockpitHead) * FMath::Clamp(Dt / 0.15f, 0.f, 1.f);

	// The head stays nearly upright as the boat heels: it leans a third of the heel, at most 8 degrees, so the
	// horizon tilts the way it does to a sailor (the heel lesson) without the instruments sliding off.
	const float Heel = float(FMath::RadiansToDegrees(Boat.GetTelemetry().Heel));
	CockpitRoll += (FMath::Clamp(Heel * 0.33f, -8.f, 8.f) - CockpitRoll) * FMath::Clamp(Dt / 0.4f, 0.f, 1.f);
	const FTransform BoatXf = BoatRoot->GetComponentTransform();
	const FVector World = BoatXf.TransformPosition(Eye + CockpitHead);
	const float Yaw = float(FMath::RadiansToDegrees(Boat.GetTelemetry().Heading)) + (bDemo ? 0.f : CameraYaw);
	// You are the helm: the helm's own figure is not drawn from inside it.
	if (Crew.Num() > 0 && Crew.Last()) Crew.Last()->SetVisibility(false, true);
	const float Pitch = FMath::Clamp(CameraPitch, -45.f, 30.f) + 0.3f * float(FMath::RadiansToDegrees(Boat.GetTelemetry().Pitch));
	Camera->SetWorldLocationAndRotation(World, FRotator(Pitch, Yaw, -CockpitRoll * Side));
	Camera->SetFieldOfView(80.f);
}

void ASailboatPawn::UpdatePhotoLens()
{
	// Photo mode is a camera: focus on the boat at f/2.8 on a full-frame sensor (the background softens with the lens),
	// and the lens profile from Visual V1 (barrel distortion, vignetting and fringing, M_LensDistortion).
	FPostProcessSettings& PP = Camera->PostProcessSettings;
	PP.bOverride_DepthOfFieldFocalDistance = PP.bOverride_DepthOfFieldFstop = PP.bOverride_DepthOfFieldSensorWidth = true;
	PP.DepthOfFieldFocalDistance = float(FVector::Dist(Camera->GetComponentLocation(), BoatRoot->GetComponentLocation()));
	PP.DepthOfFieldFstop = 2.8f;
	PP.DepthOfFieldSensorWidth = 36.f;
	if (LensDistortionAsset && !PP.WeightedBlendables.Array.ContainsByPredicate([&](const FWeightedBlendable& B) { return B.Object == LensDistortionAsset; }))
	{
		PP.AddBlendable(LensDistortionAsset, 1.f);
	}
}

void ASailboatPawn::SetPhoto(bool bOn)
{
	bPhoto = bOn;
	if (bOn)
	{
		if (bWatching) SetWatching(false);
		PhotoHintUntil = FPlatformTime::Seconds() + 4.0;
	}
	else
	{
		// Back to the sailing camera: no depth of field, no lens profile.
		FPostProcessSettings& PP = Camera->PostProcessSettings;
		PP.bOverride_DepthOfFieldFocalDistance = PP.bOverride_DepthOfFieldFstop = PP.bOverride_DepthOfFieldSensorWidth = false;
		if (LensDistortionAsset) PP.RemoveBlendable(LensDistortionAsset);
		Camera->SetFieldOfView(90.f);
		CameraPitch = FMath::Clamp(CameraPitch, -75.f, 5.f);
		CameraDistance = FMath::Clamp(CameraDistance, 400.f, 4000.f);
		CameraBoom->TargetArmLength = CameraDistance;
		CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	}
}

void ASailboatPawn::TakePhoto()
{
	const FString Name = FString::Printf(TEXT("Sailing %s.png"), *FDateTime::Now().ToString(TEXT("%Y-%m-%d %H%M%S")));
	const FString Path = FPaths::ProjectSavedDir() / TEXT("Photos") / Name;
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
	FScreenshotRequest::RequestScreenshot(Path, false, false);
	StatusMessage = FString::Printf(TEXT("Photo saved: %s"), *Name);
	StatusUntil = Boat.GetState().Time + 3.0;
	PhotoHintUntil = FPlatformTime::Seconds() + 2.5;
	UE_LOG(LogSailing, Display, TEXT("Photo saved to %s"), *Path);
}

void ASailboatPawn::AddLogEvent(const FString& Remarks)
{
	if (bLogStarted) Logbook.Add(MakeLogEntry(TEXT("Event"), Remarks));
}

void ASailboatPawn::UpdateLogbook(float DeltaSeconds)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || Boat.GetState().Time < 1.0) return;
	const FBoatTelemetry& T = Boat.GetTelemetry();
	if (!bLogStarted)
	{
		bLogStarted = true;
		FLaunchSpot Spot;
		const FString From = GM->GetLaunchSpot(Spot) ? Spot.Name : FString(TEXT("open water"));
		Logbook.Begin(ASailingGameMode::WorldDisplayName(USailingSettings::Get()->World), UTF8_TO_TCHAR(Boat.GetConfig().Name), GM->GetUnixTime(), FString());
		Logbook.Add(MakeLogEntry(TEXT("Event"), FString::Printf(TEXT("Underway from %s in the %hs; %s"), *From, Boat.GetConfig().Name,
			*FString(WeatherPresetName(GM->GetWeather().GetPreset())).ToLower())));
		// Watches on the half hour of the local clock.
		NextWatchUnix = FMath::CeilToDouble(GM->GetUnixTime() / 1800.0) * 1800.0;
		PassageIndex = GM->GetLake().Passage.Num() > 0 ? 0 : -1;
	}
	LogNm += FMath::Max(0.0, T.SpeedThroughWater) * DeltaSeconds / SailingNav::MetersPerNauticalMile;
	if (GM->GetUnixTime() >= NextWatchUnix)
	{
		Logbook.Add(MakeLogEntry(TEXT("Watch"), FString()));
		NextWatchUnix += 1800.0;
	}
	// Things worth writing down as they happen.
	if (T.bAground && !bWasAground) AddLogEvent(FString::Printf(TEXT("Aground in %.1f ft of water"), (T.DepthUnderKeel + Boat.GetConfig().Draft) / 0.3048));
	if (T.bCapsized && !bWasCapsized) AddLogEvent(TEXT("Capsized"));
	if (T.bVesselContact && !bWasTouching) AddLogEvent(TEXT("Contact with another vessel"));
	const bool bDrillDone = DrillRunner.IsComplete();
	if (bDrillDone && !bWasDrillComplete) AddLogEvent(FString::Printf(TEXT("Drill complete: %s"), DrillName(DrillRunner.GetDrill())));
	bWasAground = T.bAground;
	bWasCapsized = T.bCapsized;
	bWasTouching = T.bVesselContact;
	bWasDrillComplete = bDrillDone;
	// The passage plan: mark each waypoint off as she comes within 0.2 nm of it.
	const TArray<TPair<FString, FVector2D>>& Plan = GM->GetLake().Passage;
	if (PassageIndex >= 0 && PassageIndex < Plan.Num() && FVector2D::Distance(GetMapPosition(), Plan[PassageIndex].Value) < 370.0)
	{
		AddLogEvent(FString::Printf(TEXT("Passed %s"), *Plan[PassageIndex].Key));
		++PassageIndex;
		if (PassageIndex == Plan.Num()) AddLogEvent(FString::Printf(TEXT("Passage complete: %.1f nm by the log"), LogNm));
	}
}

void ASailboatPawn::UpdateNavLights()
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const bool bDark = GM && GM->IsDark();
	const bool bMotoring = FMath::Abs(Controls.Throttle) > 0.02 && !Boat.GetConfig().Engines.empty();
	// Rule 25: sidelights and sternlight under sail; Rule 23: add the masthead (steaming) light under power. Each shows
	// only over its arc (Rule 21): sidelights from right ahead to 22.5 degrees abaft the beam on their own side, the
	// sternlight over the 135 degrees astern, the masthead light over the 225 degrees forward.
	double Rel = 0.0, Dist = 0.0;
	if (const APlayerCameraManager* Cam = GetWorld()->GetFirstPlayerController() ? GetWorld()->GetFirstPlayerController()->PlayerCameraManager.Get() : nullptr)
	{
		const FVector D = Cam->GetCameraLocation() - GetActorLocation();
		Rel = FMath::UnwindDegrees(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X)) - FMath::RadiansToDegrees(Boat.GetTelemetry().Heading));
		Dist = D.Size() / CmPerMeter;
	}
	const bool bArc[4] = { Rel <= 2.0 && Rel >= -112.5, Rel >= -2.0 && Rel <= 112.5, FMath::Abs(Rel) >= 112.5, FMath::Abs(Rel) <= 112.5 };
	// Seen as a point at any distance: a few centimeters close to, growing with range so it stays a couple of pixels.
	const float Size = FMath::Max(6.f, float(Dist) * 0.25f);
	for (int32 I = 0; I < NavLights.Num(); ++I)
	{
		if (!NavLights[I]) continue;
		const bool bOn = bDark && (I < 3 || bMotoring) && bArc[FMath::Min(I, 3)];
		NavLights[I]->SetVisibility(bOn);
		if (bOn) NavLights[I]->SetRelativeScale3D(FVector(Size / 100.f));
	}
}

void ASailboatPawn::StartDrill(ESailingDrill Drill)
{
	if (Drill != ESailingDrill::None) BeginRun(FString(DrillName(Drill)));
	ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (Drill == ESailingDrill::None)
	{
		DrillRunner.Stop();
		return;
	}
	if (GM && GM->GetLake().IsLoaded() && (Drill == ESailingDrill::LeaveTheDock || Drill == ESailingDrill::ReturnAndDock))
	{
		// Find the home club's main dock (the largest outline near the origin) and its westmost face.
		const FLakeDock* Main = nullptr;
		for (const FLakeDock& D : GM->GetLake().Docks)
		{
			if (D.bClosed && D.Points[0].Size() < 600.0 && (!Main || D.Points.Num() > Main->Points.Num())) Main = &D;
		}
		const double Time = Boat.GetState().Time;
		FVector2D Berth;
		double BerthHeading = 0.0;
		const double WindFromRad = GM->GetWeatherState().Wind.FromDegrees * kDegToRad;
		const FMarina& Marina = GM->GetLake().Marina;
		if (Drill == ESailingDrill::LeaveTheDock && Boat.GetConfig().Type == EBoatType::J22 && Marina.HomeSlip != INDEX_NONE)
		{
			// The J/22 starts in its own slip at the club (Visual V6), bow in, tied to the fingers.
			const FMarinaSlip& Home = Marina.Slips[Marina.HomeSlip];
			Boat.Reset(Home.Center.X, Home.Center.Y, Home.HeadingDeg * kDegToRad, 0.0);
			Boat.GetMutableState().Time = Time;
			Boat.GetMooringLines() = FindDockLines(Boat, GM->GetLake().Obstacles);
			bSailsStowed = true;   // Graphics G6: covered and furled until she casts off
		}
		else if (Drill == ESailingDrill::LeaveTheDock && FindBerth(GM->GetLake().Terrain, GM->GetLake().Obstacles, FVector2D::ZeroVector, 600.0, WindFromRad, Berth, BerthHeading, Boat.GetConfig()))
		{
			Boat.Reset(Berth.X, Berth.Y, BerthHeading, 0.0);
			Boat.GetMutableState().Time = Time;
			Boat.GetMooringLines() = FindDockLines(Boat, GM->GetLake().Obstacles);
			bSailsStowed = true;
		}
		else if (Drill == ESailingDrill::ReturnAndDock && GM->GetLake().LaunchSpots.Num() > 1)
		{
			const FLaunchSpot& Spot = GM->GetLake().LaunchSpots[1];
			const double Heading = Main ? FMath::Atan2(Main->Points[0].Y - Spot.Y, Main->Points[0].X - Spot.X) : 0.0;
			Boat.Reset(Spot.X, Spot.Y, Heading, 2.0 * kKnot);
			Boat.GetMutableState().Time = Time;
			Boat.GetMooringLines().clear();
		}
		Controls = FBoatControls();
		Controls.MainSheet = Controls.JibSheet = 0.6;
		if (!bTrafficBoat && FParse::Param(FCommandLine::Get(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker();
		ApplyStateToTransform();
	}
	MaxContactKnots = 0.0;
	const double WindFrom = GM ? GM->GetWeatherState().Wind.FromDegrees * kDegToRad : 0.0;
	DrillRunner.Start(Drill, Boat, WindFrom);
	if (!bTrafficBoat) ++DrillSerial;
	bMenuOpen = false;
}

void ASailboatPawn::UpdateLearning()
{
	// Graphics G7: the learning tips' events (Content/Learning/learning-tips.json), in learning mode only.
	if (!USailingSettings::Get()->bLearningMode) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	FLearningFrame F;
	F.Time = Boat.GetState().Time;
	F.TwaDeg = FMath::RadiansToDegrees(T.TrueWindAngle);
	F.Knots = T.SpeedThroughWater / kKnot;
	F.TwsKnots = T.TrueWindSpeed / kKnot;
	F.HeelLeewardDeg = FMath::RadiansToDegrees(T.Heel) * Boat.GetState().WindwardSide;
	F.HelmForce = T.HelmForce;
	F.DepthUnderKeel = T.DepthUnderKeel;
	F.Tiller = Controls.Tiller;
	F.MainSheet = Controls.MainSheet;
	F.JibSheet = Controls.JibSheet;
	F.bInIrons = T.bInIrons;
	F.bAground = T.bAground;
	F.bCollision = T.bCollision;
	F.bVesselContact = T.bVesselContact;
	F.bBackJib = Controls.bBackJib;
	F.bTiedUp = IsTiedUp();
	F.bMotoring = FMath::Abs(Controls.Throttle) > 0.02 && !Boat.GetConfig().Engines.empty();
	auto Count = [](const FSailStripState* Strips, int32 N, ESailFlow A, ESailFlow B) { int32 K = 0; for (int32 I = 0; I < N; ++I) K += Strips[I].Flow == A || Strips[I].Flow == B; return K; };
	F.JibLuff = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Luffing, ESailFlow::Backed);
	F.JibStall = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Stalled, ESailFlow::Stalled);
	F.MainLuff = Count(T.MainStrips, T.NumMainStrips, ESailFlow::Luffing, ESailFlow::Backed);
	F.MainStall = Count(T.MainStrips, T.NumMainStrips, ESailFlow::Stalled, ESailFlow::Stalled);
	F.Drill = DrillRunner.GetDrill();
	F.bDrillActive = DrillRunner.IsActive();
	F.bDrillComplete = DrillRunner.IsComplete();
	F.DrillStep = DrillRunner.GetStep();
	const FVector2D Here(Boat.OriginPosition().X, Boat.OriginPosition().Y);
	if (F.bDrillActive && DrillRunner.GetMarks().IsValidIndex(DrillRunner.GetNextMark())) F.MarkDistance = FVector2D::Distance(Here, DrillRunner.GetMarks()[DrillRunner.GetNextMark()]);
	if (F.bDrillActive && DrillRunner.HasDummy()) F.DummyDistance = FVector2D::Distance(Here, DrillRunner.GetDummy());
	// The nearest dock face within 200 m, twice a second (the coast has thousands of segments).
	if (GM && F.Time >= NextDockScan)
	{
		NextDockScan = F.Time + 0.5;
		NearestDock = -1.0;
		double Best = 200.0;
		for (const FObstacleSegment& S : GM->GetLake().Obstacles)
		{
			if (S.Top > 1.5) continue;
			const FVector2D A(S.AX, S.AY), B(S.BX, S.BY);
			if (FMath::Min(FVector2D::Distance(Here, A), FVector2D::Distance(Here, B)) - FVector2D::Distance(A, B) > Best) continue;
			const double D = FMath::PointDistToSegment(FVector(Here, 0.0), FVector(A, 0.0), FVector(B, 0.0)) - S.Radius;
			if (D < Best) { Best = D; NearestDock = FMath::Max(0.0, D); }
		}
	}
	F.DockDistance = NearestDock;
	if (const ATrafficManager* TM = ATrafficManager::Find(GetWorld()))
	{
		const FRulesCoach::FAdvice& A = TM->GetCoach().GetAdvice();
		F.bAdvice = A.bActive;
		F.bGiveWay = A.bGiveWay;
		F.bStandOn = A.bStandOn;
		F.bRisk = A.bRisk;
		F.Encounter = A.Encounter;
		F.PlayerStatus = A.PlayerStatus;
		F.OtherStatus = A.OtherStatus;
		F.PlayerTack = A.PlayerTack;
		F.OtherTack = A.OtherTack;
		F.Cpa = A.Cpa;
		F.Tcpa = A.Tcpa;
		const std::vector<FTrafficEvent>& Events = TM->GetSim().Events();
		for (size_t I = FMath::Min(LearningTrafficEvents, Events.size()); I < Events.size(); ++I)
			F.bFiveBlasts |= Events[I].Type == FTrafficEvent::Signal && Events[I].Sound == ESoundSignal::FiveShort;
		LearningTrafficEvents = Events.size();
		// A big vessel at speed close by: her wake is coming.
		for (const FTrafficVessel& V : TM->GetSim().GetVessels())
		{
			if (V.IsSail() || V.Length() < 15.0) continue;
			const FVesselSnapshot S = V.Snapshot();
			if (S.Speed() > 8.0 * kKnot && FVector2D::Distance(Here, FVector2D(S.X, S.Y)) < 250.0) F.bBigWakeNear = true;
		}
	}
	if (GM)
	{
		const FWeatherState& W = GM->GetWeatherState();
		F.Storm = W.Storm;
		F.WindFromDeg = W.Wind.FromDegrees;
		F.bTidal = GM->GetLake().IsTidal();
	}
	if (const USailSessionSubsystem* Session = USailSessionSubsystem::Get(this); Session && Session->bHasActive) F.AirTempF = Session->Active.Conditions.AirTempF;
	Learning.Update(F, FLearningContent::Get());
}

void ASailboatPawn::UpdateDrillVisuals()
{
	if (MarkMeshes.Num() == 0)
	{
		UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
		UStaticMesh* Sphere = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
		auto Make = [&](UStaticMesh* Mesh, const FLinearColor& Color, const FVector& Scale)
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetStaticMesh(Mesh);
			C->SetUsingAbsoluteLocation(true);
			C->SetUsingAbsoluteRotation(true);
			C->SetUsingAbsoluteScale(true);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->SetWorldScale3D(Scale);
			C->SetupAttachment(RootComponent);
			C->RegisterComponent();
			UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShapeMaterial, this);
			Mid->SetVectorParameterValue(TEXT("Color"), Color);
			C->SetMaterial(0, Mid);
			C->SetVisibility(false);
			return C;
		};
		for (int32 I = 0; I < 3; ++I) MarkMeshes.Add(Make(Cylinder, FLinearColor(1.f, 0.35f, 0.02f), FVector(1.2f, 1.2f, 2.0f)));
		DummyMesh = Make(Sphere, FLinearColor(1.f, 0.85f, 0.05f), FVector(0.6f));
	}
	const TArray<FVector2D>& Marks = DrillRunner.GetMarks();
	for (int32 I = 0; I < MarkMeshes.Num(); ++I)
	{
		const bool bShow = DrillRunner.IsActive() && I < Marks.Num() && I >= DrillRunner.GetNextMark();
		MarkMeshes[I]->SetVisibility(bShow);
		if (bShow) MarkMeshes[I]->SetWorldLocation(FVector(Marks[I].X * CmPerMeter, Marks[I].Y * CmPerMeter, WaterSurfaceZ + 60.f));
	}
	const bool bDummy = DrillRunner.IsActive() && DrillRunner.HasDummy();
	DummyMesh->SetVisibility(bDummy);
	if (bDummy) DummyMesh->SetWorldLocation(FVector(DrillRunner.GetDummy().X * CmPerMeter, DrillRunner.GetDummy().Y * CmPerMeter, WaterSurfaceZ + 10.f));
}

void ASailboatPawn::StartSampleLayer()
{
	// A recorded sample (Audio/Samples/<Cue>.wav, imported by scripts/import_audio.py as /Game/Audio/Samples/S_<Cue>)
	// plays in place of that synth voice, looping, its level driven by the same physics as the voice it replaces.
	SampleCues.SetNum(int32(ESailingCue::Count));
	uint32 Mask = 0;
	for (int32 K = 0; K < int32(ESailingCue::Count); ++K)
	{
		const FString Name = SailingCueName(ESailingCue(K));
		USoundBase* Wave = LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/Samples/S_%s.S_%s"), *Name, *Name));
		if (!Wave || bTrafficBoat) continue;
		UAudioComponent* A = NewObject<UAudioComponent>(this);
		A->SetupAttachment(BoatRoot);
		A->bAllowSpatialization = false;
		A->bAutoActivate = false;
		A->SetSound(Wave);
		A->SetVolumeMultiplier(0.f);
		A->RegisterComponent();
		A->Play();
		SampleCues[K] = A;
		Mask |= 1u << K;
	}
	// Graphics G7: the sample pack (Inputs/audio, /Game/Audio/Pack) for the cues no single recording replaces.
	if (!bTrafficBoat)
	{
		const TConstArrayView<SailingSound::FPackLoop> Loops = SailingSound::PackLoops();
		for (int32 I = 0; I < Loops.Num(); ++I)
		{
			if (SampleCues[int32(Loops[I].Cue)]) continue;
			USoundBase* Wave = SailingSound::LoadPack(Loops[I].Asset);
			if (!Wave) continue;
			UAudioComponent* A = NewObject<UAudioComponent>(this);
			A->SetupAttachment(BoatRoot);
			A->bAllowSpatialization = false;
			A->bAutoActivate = false;
			A->SetSound(Wave);
			A->SetVolumeMultiplier(0.f);
			A->RegisterComponent();
			A->Play();
			PackLoopComps.Add(A);
			PackLoopDefs.Add(I);
			Mask |= 1u << uint32(Loops[I].Cue);
		}
		for (uint8 K = 0; K < uint8(SailingSound::EPackShot::Count); ++K)
		{
			for (const FString& Asset : SailingSound::PackShots(SailingSound::EPackShot(K)))
			{
				if (USoundBase* Wave = SailingSound::LoadPack(Asset)) { PackShotSounds.Add(Wave); PackShotKinds.Add(K); }
			}
		}
		if (PackShotKinds.Contains(uint8(SailingSound::EPackShot::HalyardSlap)) && !SampleCues[int32(ESailingCue::HalyardSlap)]) Mask |= 1u << uint32(ESailingCue::HalyardSlap);
		if (PackLoopComps.Num()) UE_LOG(LogSailing, Display, TEXT("Sound: sample pack, %d loops and %d one-shots"), PackLoopComps.Num(), PackShotSounds.Num());
	}
	if (Synth) Synth->Params.SampledMask = Mask;
	if (Mask) UE_LOG(LogSailing, Display, TEXT("Sound: %d recorded samples in place of synth voices"), FMath::CountBits(Mask));
}

void ASailboatPawn::UpdateSound(float DeltaSeconds)
{
	if (!Synth)
	{
		return;
	}
	const FBoatTelemetry& T = Boat.GetTelemetry();
	FSailingSoundParams& P = Synth->Params;
	P.ApparentWind = float(T.ApparentWindSpeed);
	int32 Luffing = 0, Streaming = 0;
	for (int32 I = 0; I < T.NumMainStrips; ++I) { Luffing += T.MainStrips[I].Flow == ESailFlow::Luffing || T.MainStrips[I].Flow == ESailFlow::Backed; Streaming += T.MainStrips[I].Flow == ESailFlow::Attached; }
	for (int32 I = 0; I < T.NumJibStrips; ++I) { Luffing += T.JibStrips[I].Flow == ESailFlow::Luffing || T.JibStrips[I].Flow == ESailFlow::Backed; Streaming += T.JibStrips[I].Flow == ESailFlow::Attached; }
	const float Strips = float(FMath::Max(T.NumMainStrips + T.NumJibStrips, 1));
	P.Luff = Luffing / Strips;
	P.Telltales = 0.3f + 0.7f * Streaming / Strips;
	P.BoatSpeed = float(T.BoatSpeed);
	P.HullSpeedRatio = float(T.BoatSpeed / (1.34 * std::sqrt(Boat.GetConfig().WaterlineLength / kFoot) * kKnot));
	// Bow slamming: the boat pitching quickly while making way.
	P.BowSlam = FMath::Clamp(float(FMath::Abs(Boat.GetState().AngularVelocity.Y)) * 3.f * FMath::Clamp(float(T.BoatSpeed) / 2.5f, 0.f, 1.f), 0.f, 1.f);
	const float Dt = FMath::Max(DeltaSeconds, 1e-3f);
	P.TrimRate = FMath::Clamp(float(-((Controls.MainSheet - PrevMainSheet) + (Controls.JibSheet - PrevJibSheet)) / Dt) * 2.f, -1.f, 1.f);
	PrevMainSheet = Controls.MainSheet;
	PrevJibSheet = Controls.JibSheet;
	P.Volume = USailingSettings::Get()->Volume;

	float Rain = 0.f, Thunder = 0.f, Crack = 0.f;
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		Rain = float(GM->GetWeatherState().Rain);
	}
	if (TActorIterator<ASailingEnvironment> It(GetWorld()); It)
	{
		for (const ASailingEnvironment::FThunder& Th : It->GetActiveThunder())
		{
			// Rolling envelope: quick rise, long irregular decay.
			const float Env = FMath::Clamp(Th.Age / 0.15f, 0.f, 1.f) * FMath::Exp(-Th.Age / (0.35f * Th.Duration)) * (0.7f + 0.3f * FMath::Sin(Th.Age * 7.f + Th.Duration));
			Thunder = FMath::Max(Thunder, Th.Loudness * Env);
			if (Th.Loudness > 0.6f && Th.Age < 0.25f) Crack = FMath::Max(Crack, Th.Loudness * (1.f - Th.Age / 0.25f));
		}
	}
	P.Rain = Rain;
	P.Thunder = Thunder;
	P.ThunderCrack = Crack;

	// Visual V7: the wind's gusts and shelter at the boat, at rest in a slip, and a squall coming across the water.
	float Squall = 0.f;
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		const Vec3 O = Boat.OriginPosition();
		const double Now = Boat.GetState().Time;
		const FWindField& Wind = GM->GetWind();
		P.GustRatio = float(Wind.GustFactorAt(Vec3(O.X, O.Y, 10.0), Now));
		const double Mean = FMath::Max(Wind.MeanSpeedAtHeight(10.0), 0.5);
		P.WindShadow = FMath::Clamp(float(1.0 - Wind.VelocityAt(Vec3(O.X, O.Y, 10.0), Now).LengthXY() / (Mean * Wind.GustFactorAt(Vec3(O.X, O.Y, 10.0), Now))), 0.f, 1.f);
		const FGustFront& Front = Wind.GetFront();
		if (Front.bActive)
		{
			const double D = Front.DistanceAhead(O.X, O.Y, GM->GetSimTime());
			Squall = D > 0.0 ? FMath::Clamp(float(1.0 - D / 1500.0), 0.f, 1.f) : FMath::Clamp(float(1.0 + D / 250.0), 0.f, 1.f);
		}
	}
	P.Moored = FMath::Clamp(1.f - float(T.BoatSpeed) / 0.4f, 0.f, 1.f);
	P.RainDeck = Rain;
	P.RainWater = Rain;
	P.Squall = Squall;
	// The sample layer follows the same levels as the voices it replaces.
	if (SampleCues.Num() == int32(ESailingCue::Count))
	{
		const float Aws = float(T.ApparentWindSpeed) * (1.f - 0.55f * P.WindShadow.load());
		const float Levels[] = {
			FMath::Pow(FMath::Clamp(Aws / 12.f, 0.f, 1.5f), 1.5f),                                                    // Wind
			FMath::Clamp((P.GustRatio.load() - 1.f) * 2.5f, 0.f, 1.f) * FMath::Clamp(Aws / 7.f, 0.f, 1.5f),            // GustRumble
			P.Luff.load() * FMath::Clamp(Aws / 8.f, 0.f, 2.f),                                                         // SailFlog
			P.Telltales.load() * FMath::Clamp(Aws / 8.f, 0.f, 1.5f) * 0.3f,                                            // Telltales
			FMath::Pow(FMath::Clamp(float(T.BoatSpeed) / 3.f, 0.f, 1.5f), 1.5f),                                       // BowWave
			FMath::Max(P.Moored.load() * 0.5f, P.BowSlam.load()),                                                      // HullSlap
			FMath::Clamp(P.TrimRate.load(), 0.f, 1.f),                                                                 // Winch
			FMath::Clamp(-P.TrimRate.load(), 0.f, 1.f),                                                                // SheetBlock
			P.Moored.load() * FMath::Clamp(Aws / 8.f, 0.f, 1.f),                                                       // HalyardSlap
			Rain, Rain, Squall * Squall, Thunder };                                                                    // RainDeck, RainWater, SquallHiss, Thunder
		for (int32 K = 0; K < int32(ESailingCue::Count); ++K)
		{
			if (SampleCues[K]) SampleCues[K]->SetVolumeMultiplier(Levels[K] * P.Volume.load());
		}
		UpdatePackSound(P, Aws, Levels);
	}
}

void ASailboatPawn::PlayPackShot(uint8 Kind, float Volume)
{
	TArray<int32> Choices;
	for (int32 I = 0; I < PackShotKinds.Num(); ++I) if (PackShotKinds[I] == Kind) Choices.Add(I);
	if (Choices.Num() == 0 || Volume <= 0.01f) return;
	UGameplayStatics::PlaySound2D(this, PackShotSounds[Choices[FMath::RandRange(0, Choices.Num() - 1)]], Volume, FMath::FRandRange(0.95f, 1.05f));
}

void ASailboatPawn::UpdatePackSound(const FSailingSoundParams& P, float Aws, const float* CueLevels)
{
	// Graphics G7: each pack loop is one band of its cue: the cue's level (as the synth voice it replaces) times the
	// band's crossfade weight over the parameter manifest.json names for it.
	using namespace SailingSound;
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const float Vol = P.Volume.load();
	const float Luff = P.Luff.load(), Speed = P.BoatSpeed.load(), Trim = P.TrimRate.load(), Slam = P.BowSlam.load(), Moored = P.Moored.load();
	const float Tied = IsTiedUp() ? 1.f : 0.f;
	const float Chop = FMath::Clamp((float(T.TrueWindSpeed) - 5.f) / 5.f, 0.f, 1.f);
	float Wind[3], Flog[3], Wash[4], Winch[2];
	static const float WindC[] = { 3.f, 7.f, 11.f }, FlogC[] = { 0.25f, 0.55f, 0.85f }, WashC[] = { 0.5f, 1.5f, 2.6f, 3.6f }, WinchC[] = { 0.2f, 0.7f };
	Crossfade(Aws, WindC, 3, Wind);
	Crossfade(Luff, FlogC, 3, Flog);
	if (Aws < 7.f) { Flog[1] = FMath::Sqrt(FMath::Square(Flog[1]) + FMath::Square(Flog[2])); Flog[2] = 0.f; }   // a strong flog needs a breeze
	Crossfade(Speed, WashC, 4, Wash);
	Wash[3] = FMath::Max(Wash[3], FMath::Clamp((P.HullSpeedRatio.load() - 0.9f) * 5.f, 0.f, 1.f));
	Crossfade(Trim, WinchC, 2, Winch);
	float Lap[3] = { (1.f - Chop) * (1.f - Tied), Tied * (1.f - 0.5f * Chop), FMath::Max(Chop * Moored, Slam) };
	const float LapSum = FMath::Max(Lap[0] + Lap[1] + Lap[2], 1e-3f);
	for (float& L : Lap) L /= LapSum;
	const TConstArrayView<FPackLoop> Loops = PackLoops();
	for (int32 I = 0; I < PackLoopComps.Num(); ++I)
	{
		const FPackLoop& L = Loops[PackLoopDefs[I]];
		const int32 B = L.Band;
		float W = 1.f;
		switch (L.Cue)
		{
		case ESailingCue::Wind: W = Wind[B]; break;
		case ESailingCue::SailFlog: W = Flog[B]; break;
		case ESailingCue::BowWave: W = Wash[B]; break;
		case ESailingCue::HullSlap: W = Lap[B]; break;
		case ESailingCue::Winch: W = Winch[B]; break;
		default: break;
		}
		PackLoopComps[I]->SetVolumeMultiplier(CueLevels[int32(L.Cue)] * W * Vol);
	}
	if (PackShotSounds.Num() == 0) return;
	const double Now = GetWorld()->GetTimeSeconds();
	// The halyard on the mast, at rest or head to wind in a breeze.
	const float Slap = FMath::Max(Moored, T.bInIrons ? 1.f : 0.f) * FMath::Clamp(Aws / 8.f, 0.f, 1.f);
	if (Slap > 0.05f && Now >= NextHalyardShot)
	{
		PlayPackShot(uint8(EPackShot::HalyardSlap), Slap * 0.8f * Vol);
		NextHalyardShot = Now + FMath::FRandRange(0.7, 3.0) / FMath::Max(Slap, 0.3f);
	}
	// A sail filling with a snap as a tack or jibe completes (luff from over 0.6 to under 0.2).
	if (Luff > 0.6f) LuffHighAt = Now;
	if (Luff < 0.2f && Now - LuffHighAt < 1.5 && LuffHighAt > 0.0)
	{
		PlayPackShot(uint8(EPackShot::SailFill), FMath::Clamp(Aws / 8.f, 0.2f, 1.f) * Vol);
		LuffHighAt = -100.0;
	}
	// Winch clicks for small trims; a sheet running out through its block when easing starts.
	if (Trim > 0.03f && Trim < 0.3f && Now >= NextWinchClick)
	{
		PlayPackShot(uint8(EPackShot::WinchClick), 0.6f * Vol);
		NextWinchClick = Now + 0.14;
	}
	if (Trim < -0.3f && PrevTrimRate >= -0.3f) PlayPackShot(uint8(Trim < -0.6f ? EPackShot::SheetEaseFast : EPackShot::SheetEaseSlow), 0.7f * Vol);
	PrevTrimRate = Trim;
	// In the slip: the lines creak and the fenders squeak as she surges.
	if (Tied > 0.f && Now >= NextDockShot)
	{
		const float Surge = FMath::Clamp(float(Boat.GetState().Velocity.Length()) * 4.f + Chop * 0.5f + Aws / 20.f, 0.f, 1.f);
		if (NextDockShot > 0.0) PlayPackShot(uint8(FMath::RandBool() ? EPackShot::DockCreak : EPackShot::FenderSqueak), (0.3f + 0.5f * Surge) * Vol);
		NextDockShot = Now + FMath::FRandRange(2.5, 8.0) / (0.4f + Surge);
	}
}

void ASailboatPawn::ApplyStateToTransform()
{
	const Vec3 Origin = Boat.OriginPosition();
	const Quat& Q = Boat.GetState().Orientation;
	SetActorLocationAndRotation(FVector(Origin.X * CmPerMeter, Origin.Y * CmPerMeter, Origin.Z * CmPerMeter + WaterSurfaceZ), FQuat(Q.X, Q.Y, Q.Z, Q.W));
}

void ASailboatPawn::UpdateRigVisuals(float DeltaSeconds)
{
	VisualTime += DeltaSeconds;
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();

	// Graphics G6: tied up in her slip, a keelboat's sails are stowed (the berthed dress), the boom on the centreline.
	const bool bStowed = bSailsStowed && StowedDress && IsTiedUp();
	if (bStowed != bStowedShown)
	{
		bStowedShown = bStowed;
		StowedDress->SetVisibility(bStowed);
		MainSail->SetVisibility(!bStowed);
		JibSail->SetVisibility(!bStowed && Boat.GetConfig().HasJib());
		if (TelltaleRibbons) TelltaleRibbons->SetVisibility(!bStowed);
		if (ModelMast) ModelMast->SetVisibility(!bStowed);   // the dress carries its own (straight) mast and standing rig
		if (RigLines) RigLines->SetVisibility(!bStowed);
		if (TravelerCar) TravelerCar->SetVisibility(!bStowed);
	}
	// Boom along -X turned by yaw psi points at (-cos psi, -sin psi); the sail chord is (-cos a, side sin a).
	BoomPivot->SetRelativeRotation(FRotator(0.f, bStowed ? 0.f : -FMath::RadiansToDegrees(S.BoomAngle), 0.f));
	for (USceneComponent* Pivot : RudderPivots) Pivot->SetRelativeRotation(FRotator(0.f, -FMath::RadiansToDegrees(S.RudderAngle), 0.f));
	// The fly points into the apparent wind (where it comes from).
	MastheadFly->SetRelativeRotation(FRotator(0.f, FMath::RadiansToDegrees(T.ApparentWindAngle), 0.f));

	const FBoatConfig& Cfg = Boat.GetConfig();
	UpdateCrewFigures(DeltaSeconds);

	if (ModelHull)
	{
		UpdateModelRig(DeltaSeconds);
	}
	if (bStowed)
	{
		SpinSail->SetVisibility(false);
		if (ModelHull) UpdateBoatWetness(DeltaSeconds);
		return;
	}
	// A reef changes the main's planform: rebuild its cloth.
	const double MainHead = Cfg.Main.NumStrips > 0 ? Cfg.Main.Strips[Cfg.Main.NumStrips - 1].ZTop : -1.0;
	if (MainHead != ClothMainHeadZ)
	{
		MainCloth.Init(Cfg.Main, ESailKind::Main);
		ClothMainHeadZ = MainHead;
		MainSail->ClearAllMeshSections();
	}
	UpdateSailCloth(MainSail, MainCloth, Cfg.Main, ESailKind::Main, T.MainStrips, S.MainSide, DeltaSeconds);
	if (Cfg.HasJib())
	{
		UpdateSailCloth(JibSail, JibCloth, Cfg.Jib, ESailKind::Jib, T.JibStrips, S.JibSide, DeltaSeconds);
		JibClewCm = JibCloth.PointAt(1.f, 0.f); // where the jib sheets lead from
	}
	SpinSail->SetVisibility(T.NumSpinStrips > 0);
	if (T.NumSpinStrips > 0) UpdateSailCloth(SpinSail, SpinCloth, Cfg.Spinnaker, ESailKind::Spinnaker, T.SpinStrips, S.SpinSide, DeltaSeconds);
	UpdateTelltaleRibbons();
	if (ModelHull)
	{
		UpdateBoatWetness(DeltaSeconds);
	}
}

void ASailboatPawn::BuildSailMesh(UProceduralMeshComponent* Mesh, const FSailGeometry& Geo, const FSailStripState* Strips, int32 Side, bool bMain)
{
	const int32 N = Geo.NumStrips;
	const int32 Rows = N + 1;
	const int32 Cols = 10;

	// Shape at each row (strip boundary): interpolate the strips on either side.
	struct FRow { double Z, LuffX, Chord, Angle, Camber, Luff; };
	TArray<FRow, TInlineAllocator<8>> RowData;
	const double LuffSlope = N > 1 ? (Geo.Strips[N - 1].LuffX - Geo.Strips[0].LuffX) / (0.5 * (Geo.Strips[N - 1].ZBottom + Geo.Strips[N - 1].ZTop) - 0.5 * (Geo.Strips[0].ZBottom + Geo.Strips[0].ZTop)) : 0.0;
	const double LuffZ0 = 0.5 * (Geo.Strips[0].ZBottom + Geo.Strips[0].ZTop);
	for (int32 R = 0; R < Rows; ++R)
	{
		const int32 A = FMath::Clamp(R - 1, 0, N - 1);
		const int32 B = FMath::Clamp(R, 0, N - 1);
		FRow Row;
		Row.Z = R < N ? Geo.Strips[R].ZBottom : Geo.Strips[N - 1].ZTop;
		Row.LuffX = Geo.Strips[0].LuffX + LuffSlope * (Row.Z - LuffZ0);
		if (R == 0) Row.Chord = Geo.Strips[0].Chord * 1.15;
		else if (R == N) Row.Chord = FMath::Max(0.08, Geo.Strips[N - 1].Chord * 0.55);
		else Row.Chord = 0.5 * (Geo.Strips[A].Chord + Geo.Strips[B].Chord);
		Row.Angle = 0.5 * (Strips[A].AngleFromCenterline + Strips[B].AngleFromCenterline) * Side;
		Row.Camber = 0.5 * (Strips[A].Camber + Strips[B].Camber);
		auto Flutter = [](const FSailStripState& St) { return St.Flow == ESailFlow::Luffing || St.Flow == ESailFlow::Backed ? 1.0 : 0.0; };
		Row.Luff = 0.5 * (Flutter(Strips[A]) + Flutter(Strips[B]));
		// A backed sail bulges to windward.
		if (Strips[A].Flow == ESailFlow::Backed && Strips[B].Flow == ESailFlow::Backed)
		{
			Row.Camber = -Row.Camber;
		}
		RowData.Add(Row);
	}

	TArray<FVector> Verts;
	Verts.SetNumUninitialized(Rows * Cols * 2);
	for (int32 R = 0; R < Rows; ++R)
	{
		const FRow& Row = RowData[R];
		const Vec3 Chord = SailChordDir(Row.Angle, Side);
		const Vec3 Leeward = Vec3(Chord.Y, -Chord.X, 0.0) * Side;
		for (int32 C = 0; C < Cols; ++C)
		{
			const double U = double(C) / (Cols - 1);
			double Depth = 4.0 * Row.Camber * Row.Chord * U * (1.0 - U) * (1.0 + 0.3 * (1.0 - 2.0 * U)); // draft a little forward
			// Luffing: the front of the sail ripples and flogs.
			Depth += Row.Luff * 0.07 * Row.Chord * FMath::Sin(VisualTime * 24.0 + U * 9.0 + R * 1.3) * FMath::Sqrt(1.0 - U);
			const Vec3 P = Vec3(Row.LuffX, 0.0, Row.Z) + Chord * (U * Row.Chord) + Leeward * Depth;
			Verts[R * Cols + C] = ToCm(P);
		}
	}
	if (!bMain) JibClewCm = Verts[Cols - 1]; // the foot's leech end: where the jib sheets lead from
	// Back face: same positions, separate vertices so it can carry the opposite normal.
	for (int32 I = 0; I < Rows * Cols; ++I)
	{
		Verts[Rows * Cols + I] = Verts[I];
	}

	TArray<FVector> Normals;
	Normals.SetNumUninitialized(Verts.Num());
	for (int32 R = 0; R < Rows; ++R)
	{
		for (int32 C = 0; C < Cols; ++C)
		{
			const FVector DU = Verts[R * Cols + FMath::Min(C + 1, Cols - 1)] - Verts[R * Cols + FMath::Max(C - 1, 0)];
			const FVector DV = Verts[FMath::Min(R + 1, Rows - 1) * Cols + C] - Verts[FMath::Max(R - 1, 0) * Cols + C];
			const FVector Nrm = FVector::CrossProduct(DU, DV).GetSafeNormal();
			Normals[R * Cols + C] = Nrm;
			Normals[Rows * Cols + R * Cols + C] = -Nrm;
		}
	}

	const bool bCreate = Mesh->GetNumSections() == 0;
	if (bCreate)
	{
		TArray<int32> Tris;
		for (int32 R = 0; R < Rows - 1; ++R)
		{
			for (int32 C = 0; C < Cols - 1; ++C)
			{
				const int32 V0 = R * Cols + C, V1 = V0 + 1, V2 = V0 + Cols, V3 = V2 + 1;
				Tris.Append({ V0, V2, V1, V1, V2, V3 });
				const int32 O = Rows * Cols;
				Tris.Append({ O + V0, O + V1, O + V2, O + V1, O + V3, O + V2 });
			}
		}
		TArray<FVector2D> UV;
		UV.SetNumZeroed(Verts.Num());
		Mesh->CreateMeshSection_LinearColor(0, Verts, Tris, Normals, UV, {}, {}, false);
	}
	else
	{
		Mesh->UpdateMeshSection_LinearColor(0, Verts, Normals, {}, {}, {});
	}
}

void ASailboatPawn::UpdateTelltales()
{
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FBoatConfig& Cfg = Boat.GetConfig();

	auto Place = [](UStaticMeshComponent* Tell, const Vec3& Attach, const FVector& Dir, float LengthCm)
	{
		const FVector D = Dir.GetSafeNormal();
		Tell->SetRelativeLocation(ToCm(Attach) + D * (LengthCm * 0.5f));
		Tell->SetRelativeRotation(D.Rotation());
	};

	// Jib luff telltales, windward (index 2k) and leeward (2k+1... colored by side) at three heights.
	for (int32 K = 0; K < 3 && Cfg.HasJib(); ++K)
	{
		const FSailStripState& St = T.JibStrips[K];
		const FSailStripGeometry& G = Cfg.Jib.Strips[K];
		const double Angle = St.AngleFromCenterline * S.JibSide;
		const Vec3 Chord = SailChordDir(Angle, S.JibSide);
		const Vec3 Leeward = Vec3(Chord.Y, -Chord.X, 0.0) * S.JibSide;
		const Vec3 Base = Vec3(G.LuffX, 0.0, 0.5 * (G.ZBottom + G.ZTop)) + Chord * 0.25;
		const FVector Aft(Chord.X, Chord.Y, 0.0);
		const float Flick = FMath::Sin(VisualTime * 30.f + K * 2.f);

		// Windward ribbon lifts and flutters when you pinch (angle of attack near the luff angle).
		const bool bWindwardLifting = St.Flow == ESailFlow::Luffing || St.Flow == ESailFlow::Backed || St.AlphaN < St.LuffAlpha + 3.0 * kDegToRad;
		const FVector WindwardDir = bWindwardLifting ? Aft * 0.4f + FVector(0, 0, 0.9f + 0.3f * Flick) : Aft + FVector(0, 0, 0.05f * Flick);
		// Leeward ribbon stalls (droops and twirls) when over-trimmed.
		const bool bLeewardStalled = St.Flow == ESailFlow::Stalled;
		const FVector LeewardDir = bLeewardStalled ? Aft * 0.3f + FVector(0, 0, -0.9f) + FVector(Leeward.X, Leeward.Y, 0) * (0.4f * Flick) : Aft + FVector(0, 0, 0.05f * Flick);

		// Index 2k = port side ribbon, 2k+1 = starboard side; which is windward depends on the jib's side.
		const Vec3 PortAttach = Base + Vec3(0, -0.02, 0);
		const Vec3 StbdAttach = Base + Vec3(0, 0.02, 0);
		const bool bJibOnStarboard = S.JibSide > 0; // wind from port: port ribbon is windward
		Place(JibTelltales[2 * K], PortAttach, bJibOnStarboard ? WindwardDir : LeewardDir, 18.f);
		Place(JibTelltales[2 * K + 1], StbdAttach, bJibOnStarboard ? LeewardDir : WindwardDir, 18.f);
	}

	// Main leech telltales at the leech of the upper three strips: stream aft when the flow leaves the leech cleanly.
	for (int32 K = 0; K < 3; ++K)
	{
		const int32 StripIndex = K + 1;
		const FSailStripState& St = T.MainStrips[StripIndex];
		const FSailStripGeometry& G = Cfg.Main.Strips[StripIndex];
		const double Angle = St.AngleFromCenterline * S.MainSide;
		const Vec3 Chord = SailChordDir(Angle, S.MainSide);
		const Vec3 Leeward = Vec3(Chord.Y, -Chord.X, 0.0) * S.MainSide;
		const Vec3 Leech = Vec3(G.LuffX, 0.0, 0.5 * (G.ZBottom + G.ZTop)) + Chord * G.Chord;
		const float Flick = FMath::Sin(VisualTime * 26.f + K * 1.7f);
		const FVector Aft(Chord.X, Chord.Y, 0.0);
		const FVector Dir = St.Flow == ESailFlow::Stalled
			? FVector(Leeward.X, Leeward.Y, 0) * 0.9f + Aft * 0.2f + FVector(0, 0, 0.3f * Flick) // curls behind the leech
			: (St.Flow == ESailFlow::Luffing ? Aft + FVector(0, 0, 0.5f * Flick) : Aft + FVector(0, 0, 0.05f * Flick));
		Place(LeechTelltales[K], Leech, Dir, 22.f);
	}
}

void ASailboatPawn::ApplyHeldInputs(float DeltaSeconds)
{
	const bool bSimple = USailingSettings::Get()->UseSimpleControls();
	auto Held = [this, bSimple](FName Action)
	{
		if (bMenuOpen || (bSimple && IsCrewHandled(Action))) return 0.f;
		const float* V = HeldAxes.Find(Action);
		return V ? *V : 0.f;
	};
	auto Adjust = [&](double& Value, FName Action, double Rate, double Lo, double Hi)
	{
		const float H = Held(Action);
		if (H != 0.f)
		{
			Value = FMath::Clamp(Value + H * Rate * DeltaSeconds, Lo, Hi);
			LastManualTrimTime = Boat.GetState().Time;
		}
	};
	Adjust(Controls.MainSheet, NAME_MainSheet, 0.35, 0.0, 1.0);
	// With the spinnaker up the jib-sheet keys trim the spinnaker sheet (the jib is in its shadow anyway).
	Adjust(Controls.bSpinnaker ? Controls.SpinSheet : Controls.JibSheet, NAME_JibSheet, 0.35, 0.0, 1.0);
	// Engine: throttle and (twin engines) the split, held to change; 0 is neutral.
	if (!Boat.GetConfig().Engines.empty())
	{
		const float Throttle = Held(TEXT("Throttle"));
		if (Throttle != 0.f) Controls.Throttle = FMath::Clamp(Controls.Throttle + Throttle * 0.5 * DeltaSeconds, -1.0, 1.0);
		const float Split = Held(TEXT("ThrottleSplit"));
		if (Boat.GetConfig().Engines.size() >= 2 && Split != 0.f) Controls.ThrottleSplit = FMath::Clamp(Controls.ThrottleSplit + Split * 0.8 * DeltaSeconds, -1.0, 1.0);
	}
	Adjust(Controls.Traveler, NAME_Traveler, 0.8, -1.0, 1.0);
	// (Hike is yours in both layouts.)
	Adjust(Controls.Hike, NAME_Hike, 0.8, -1.0, 1.0);
	Adjust(Controls.Vang, NAME_Vang, 0.5, 0.0, 1.0);
	Adjust(Controls.Cunningham, NAME_Cunningham, 0.5, 0.0, 1.0);
	Adjust(Controls.Outhaul, NAME_Outhaul, 0.5, 0.0, 1.0);
	Adjust(Controls.Backstay, NAME_Backstay, 0.5, 0.0, 1.0);

	// Tiller: follows the stick or keys, with a short ramp so tapping a key gives a small correction.
	Controls.Tiller = FMath::FInterpConstantTo(Controls.Tiller, Held(NAME_Tiller), DeltaSeconds, 2.5f);
}

void ASailboatPawn::OnAxis(const FInputActionValue& Value, FName Action)
{
	HeldAxes.FindOrAdd(Action) = Value.Get<float>();
}

void ASailboatPawn::OnAxisReleased(const FInputActionValue& Value, FName Action)
{
	HeldAxes.FindOrAdd(Action) = 0.f;
}

void ASailboatPawn::OnLook(const FInputActionValue& Value)
{
	// Ignore the camera in scripted runs, and clamp single events: capturing the mouse at launch can deliver one huge jump.
	float BenchSeconds = 0.f;
	if (bDemo || FParse::Value(FCommandLine::Get(), TEXT("SailingBench="), BenchSeconds))
	{
		return;
	}
	const FVector2D Delta = Value.Get<FVector2D>().ClampAxes(-10.0, 10.0);
	if (bWatching && GhostBoat)
	{
		GhostBoat->AddCameraOrbit(Delta, 0.f);
		return;
	}
	if (bPhoto)
	{
		// Photo mode: look from anywhere, below the boom to straight down.
		CameraYaw = FMath::UnwindDegrees(CameraYaw + Delta.X);
		CameraPitch = FMath::Clamp(CameraPitch + Delta.Y, -89.f, 35.f);
		CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
		return;
	}
	if (bChartOpen)
	{
		// The crosshair stays in the middle; the chart slides under it (mouse right = look east, up = north).
		ChartCenter += FVector2D(Delta.Y, Delta.X) * ChartMetersPerPixel * 4.0;
		return;
	}
	CameraYaw = FMath::UnwindDegrees(CameraYaw + Delta.X);
	CameraPitch = FMath::Clamp(CameraPitch + Delta.Y, -75.f, 5.f);
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
}

void ASailboatPawn::OnZoom(const FInputActionValue& Value)
{
	if (bChartOpen)
	{
		ChartMetersPerPixel = FMath::Clamp(ChartMetersPerPixel * FMath::Pow(0.8, double(Value.Get<float>())), 0.5, 60.0);
		return;
	}
	if (bWatching && GhostBoat)
	{
		GhostBoat->AddCameraOrbit(FVector2D::ZeroVector, Value.Get<float>());
		return;
	}
	if (bPhoto)
	{
		CameraDistance = FMath::Clamp(CameraDistance - Value.Get<float>() * 200.f, 150.f, 30000.f);
		CameraBoom->TargetArmLength = CameraDistance;
		return;
	}
	CameraDistance = FMath::Clamp(CameraDistance - Value.Get<float>() * 120.f, 400.f, 4000.f);
	CameraBoom->TargetArmLength = CameraDistance;
}

void ASailboatPawn::OnButton(const FInputActionValue& Value, FName Action)
{
	USailingSettings* Settings = USailingSettings::Get();
	if (bKeysOpen)
	{
		if (bCapturingKey) return; // the next key pressed is taken in Tick
		if (Action == TEXT("Menu")) { bKeysOpen = false; bMenuOpen = true; }
		else if (Action == TEXT("MenuUp") && KeyRows.Num()) KeysIndex = (KeysIndex + KeyRows.Num() - 1) % KeyRows.Num();
		else if (Action == TEXT("MenuDown") && KeyRows.Num()) KeysIndex = (KeysIndex + 1) % KeyRows.Num();
		else if (Action == TEXT("PhotoShot"))
		{
			bCapturingKey = true;
			CaptureFrame = GFrameCounter; // the Enter that started it is not the new key
			KeysMessage = FString::Printf(TEXT("Press the new key for \"%s\" (Escape cancels)"), *KeyRows[KeysIndex].Label);
		}
		return;
	}
	if (Action == TEXT("Photo"))
	{
		SetPhoto(!bPhoto);
		return;
	}
	if (Action == TEXT("CockpitView") && !bPhoto && !bWatching)
	{
		SetCockpitView(!bCockpit);
		return;
	}
	if (Action == TEXT("Replay"))
	{
		if (LastRun.IsEmpty() && !bWatching)
		{
			StatusMessage = TEXT("Nothing to replay yet: a run is kept when you reset, start a drill or start a race");
			StatusUntil = Boat.GetState().Time + 4.0;
			return;
		}
		SetWatching(!bWatching);
		return;
	}
	if (bPhoto)
	{
		if (Action == TEXT("PhotoShot")) TakePhoto();
		return;
	}
	if (bWatching)
	{
		// Scrub ten seconds at a time; play slower or faster.
		if (Action == TEXT("MenuLeft")) WatchTime = FMath::Max(0.0, WatchTime - 10.0);
		else if (Action == TEXT("MenuRight")) WatchTime = FMath::Min(LastRun.Duration(), WatchTime + 10.0);
		else if (Action == TEXT("MenuUp")) WatchSpeed = FMath::Min(WatchSpeed * 2.f, 16.f);
		else if (Action == TEXT("MenuDown")) WatchSpeed = FMath::Max(WatchSpeed * 0.5f, 0.25f);
		return;
	}
	if (Action == TEXT("Menu"))
	{
		// Graphics G4: Tab opens Pause (the old settings list stays for the runs that start without the front end).
		if (APlayerController* PC = Cast<APlayerController>(GetController()))
		{
			if (ASailingHUD* Hud = PC->GetHUD<ASailingHUD>(); Hud && Hud->UsesFrontEnd() && !bTrafficBoat)
			{
				bMenuOpen = false;
				Hud->OpenPause();
				return;
			}
		}
		bMenuOpen = !bMenuOpen;
		bControlsCard = false;
		return;
	}
	if (Action == TEXT("ControlsCard"))
	{
		bControlsCard = !bControlsCard;
		bMenuOpen = false;
		return;
	}
	if (bMenuOpen)
	{
		if (Action == TEXT("MenuUp")) MenuIndex = (MenuIndex + RowCount - 1) % RowCount;
		else if (Action == TEXT("MenuDown")) MenuIndex = (MenuIndex + 1) % RowCount;
		else if (Action == TEXT("MenuLeft")) ChangeMenuValue(-1);
		else if (Action == TEXT("MenuRight")) ChangeMenuValue(1);
		return;
	}
	if (Action.ToString().StartsWith(TEXT("Menu")))
	{
		return;
	}
	if (Action == TEXT("WingOnWing"))
	{
		Controls.bWingOnWing = !Controls.bWingOnWing;
	}
	else if (Action == TEXT("ToggleLearning"))
	{
		Settings->bLearningMode = !Settings->bLearningMode;
		Settings->Save();
	}
	else if (Action == TEXT("ToggleDifficulty"))
	{
		Settings->Difficulty = Settings->Difficulty == ESailingDifficulty::Easy ? ESailingDifficulty::Realistic : ESailingDifficulty::Easy;
		Settings->Save();
		ApplyDifficulty();
		if (ASailingGameMode* GameMode = GetWorld()->GetAuthGameMode<ASailingGameMode>())
		{
			GameMode->ApplyDifficultyToWind();
		}
	}
	else if (Action == TEXT("ToggleHud"))
	{
		// Graphics G4: H cycles the HUD: full, minimal (cluster, compass, drill, toasts), off (toasts only).
		Settings->bShowHud = true;
		SSailHud::Mode = (SSailHud::Mode + 1) % 3;
		Settings->Save();
	}
	else if (Action == TEXT("ResetBoat"))
	{
		ResetBoat();
	}
	else if (Action == TEXT("DockLines"))
	{
		ToggleDockLines();
	}
	else if (Action == TEXT("Spinnaker"))
	{
		const FBoatConfig& C = Boat.GetConfig();
		if (!C.HasSpinnaker())
		{
			StatusMessage = FString::Printf(TEXT("The %hs carries no spinnaker"), C.Name);
		}
		else
		{
			Controls.bSpinnaker = !Controls.bSpinnaker;
			Controls.SpinSheet = 0.5;
			const TCHAR* Kind = C.bAsymmetricSpinnaker ? TEXT("Gennaker") : TEXT("Spinnaker");
			StatusMessage = FString::Printf(TEXT("%s %s"), Kind, Controls.bSpinnaker ? TEXT("up: Q/E trims its sheet") : TEXT("down"));
		}
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("Reef"))
	{
		const int32 Max = int32(Boat.GetConfig().ReefLuffFraction.size());
		Controls.Reef = Max == 0 ? 0 : (Controls.Reef + 1) % (Max + 1);
		StatusMessage = Max == 0 ? FString::Printf(TEXT("The %hs has no reef points"), Boat.GetConfig().Name)
			: (Controls.Reef == 0 ? FString(TEXT("Reefs shaken out: full main")) : FString::Printf(TEXT("Reef %d in"), Controls.Reef));
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("Board"))
	{
		if (!Boat.GetConfig().HasBoard())
		{
			StatusMessage = TEXT("Fixed keel: nothing to raise");
		}
		else
		{
			Controls.Board = Controls.Board > 0.5 ? 0.25 : 1.0;
			StatusMessage = Controls.Board > 0.5 ? TEXT("Board down") : TEXT("Board up (less drag downwind, more leeway upwind)");
		}
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("Righting"))
	{
		Controls.bRighting = !Controls.bRighting;
		StatusMessage = Boat.GetConfig().RightingLever <= 0.0 ? TEXT("This boat cannot be righted by her crew: reset with R")
			: (Controls.bRighting ? TEXT("Crew on the board (or the righting line): let the sheets go") : TEXT("Crew back aboard"));
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("EngineNeutral"))
	{
		Controls.Throttle = 0.0;
		Controls.ThrottleSplit = 0.0;
		StatusMessage = Boat.GetConfig().Engines.empty() ? TEXT("No engine: sail her in") : TEXT("Engine in neutral");
		StatusUntil = Boat.GetState().Time + 2.0;
	}
	else if (Action == TEXT("Chart"))
	{
		const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
		if (!GM || GM->GetChart().Triangles.Num() == 0)
		{
			StatusMessage = TEXT("No chart for this area (charts are for the coast: choose Galveston Bay in Tab settings)");
			StatusUntil = Boat.GetState().Time + 3.0;
			return;
		}
		SetChartOpen(!bChartOpen);
		// Open on the boat if the GPS is on, else on the navigator's best position (the DR).
		if (bChartOpen) ChartCenter = bShowGps ? GetMapPosition() : Plot.Dr;
	}
	else if (Action == TEXT("Bearing"))
	{
		TakeBearing();
	}
	else if (Action == TEXT("Logbook"))
	{
		bLogOpen = !bLogOpen;
	}
	else if (Action == TEXT("Gps"))
	{
		bShowGps = !bShowGps;
		StatusMessage = bShowGps ? TEXT("GPS on: the chart shows where you are") : TEXT("GPS off: navigate by bearings (U) and dead reckoning");
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("ClearPlot"))
	{
		Plot.Start(GetMapPosition(), Boat.GetState().Time);
		StatusMessage = TEXT("Plot cleared: dead reckoning from here");
		StatusUntil = Boat.GetState().Time + 3.0;
	}
	else if (Action == TEXT("BackJib"))
	{
		Controls.bBackJib = !Controls.bBackJib;
		StatusMessage = Controls.bBackJib ? TEXT("Jib held aback (to windward)") : TEXT("Jib released");
		StatusUntil = Boat.GetState().Time + 2.5;
	}
}

bool ASailboatPawn::ToggleDockLines()
{
	std::vector<FMooringLine>& Lines = Boat.GetMooringLines();
	const double Now = Boat.GetState().Time;
	if (!Lines.empty())
	{
		Lines.clear();
		// Graphics G6: the crew hoists the sails and takes the cover off as the lines come in.
		StatusMessage = bSailsStowed && StowedDress ? TEXT("Lines cast off, sails up") : TEXT("Lines cast off");
		bSailsStowed = false;
		StatusUntil = Now + 3.0;
		return true;
	}
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsLoaded())
	{
		return false;
	}
	if (Boat.GetTelemetry().BoatSpeed > 1.5 * kKnot)
	{
		StatusMessage = TEXT("Too fast to get a line ashore: slow below 1.5 kn");
		StatusUntil = Now + 3.0;
		return false;
	}
	Lines = FindDockLines(Boat, GM->GetLake().Obstacles);
	if (Lines.empty())
	{
		StatusMessage = TEXT("No dock within reach of two cleats: come alongside first");
		StatusUntil = Now + 3.0;
		return false;
	}
	StatusMessage = FString::Printf(TEXT("Tied up with %d lines"), int32(Lines.size()));
	StatusUntil = Now + 3.0;
	return true;
}

TArray<TPair<FString, FString>> ASailboatPawn::GetMenuRows() const
{
	const USailingSettings* S = USailingSettings::Get();
	auto OnOff = [](bool b) { return FString(b ? TEXT("On") : TEXT("Off")); };
	TArray<TPair<FString, FString>> Rows;
	Rows.Add({ TEXT("Sailing area (restarts)"), FString(ASailingGameMode::WorldDisplayName(S->World)) });
	Rows.Add({ TEXT("Boat"), FString(BoatTypeName(EBoatType(FMath::Clamp(S->BoatType, 0, int32(EBoatType::Count) - 1)))) });
	Rows.Add({ TEXT("Drill (Left/Right starts it)"), FString(DrillName(MenuDrill)) });
	FString RaceState = TEXT("None (Right starts one)");
	if (const ATrafficManager* TM = ATrafficManager::Find(GetWorld()))
	{
		if (const FRaceRunner* R = TM->GetRace()) RaceState = R->IsOver() ? FString(TEXT("Finished (Left ends it)")) : FString(TEXT("Racing (Left ends it)"));
	}
	Rows.Add({ TEXT("Race against the fleet"), RaceState });
	Rows.Add({ TEXT("Ghost of your last run"), LastRun.IsEmpty() ? FString(TEXT("(sail a run first)")) : (bGhostOn ? FString::Printf(TEXT("On: %s"), *LastRun.Label) : FString(TEXT("Off"))) });
	const int32 Traffic = FMath::Clamp(USailingSettings::Get()->TrafficLevel, 0, 2);
	Rows.Add({ TEXT("Traffic"), Traffic == 0 ? TEXT("None") : (Traffic == 1 ? TEXT("Light") : TEXT("Busy")) });
	FString Launch = TEXT("Open water");
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		const TArray<FLaunchSpot>& Spots = GM->GetLake().LaunchSpots;
		if (Spots.Num() > 0) Launch = Spots[FMath::Clamp(S->LaunchSpot, 0, Spots.Num() - 1)].Name;
	}
	Rows.Add({ TEXT("Launch spot"), Launch });
	FString Level = TEXT("Full pool");
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		const FLakeData& L = GM->GetLake();
		if (L.IsTidal())
		{
			Rows.Add({ TEXT("Water level"), FString::Printf(TEXT("Tidal: %+.1f ft above chart datum now"), GM->GetTideHeight() / 0.3048) });
			Level.Reset();
		}
		else Level = S->bGaugeLakeLevel ? FString::Printf(TEXT("Gauge %s: %.1f ft (%.1f ft low)"), *L.LevelDate, L.LevelFeet, L.PoolFeet - L.LevelFeet)
			: FString::Printf(TEXT("Full pool: %.1f ft"), L.PoolFeet);
		if (S->bGaugeLakeLevel != (L.Terrain.GetLevelBelowPool() > 0.0)) Level += TEXT(" (next start)");
	}
	if (!Level.IsEmpty()) Rows.Add({ TEXT("Lake level"), Level });
	Rows.Add({ TEXT("Weather"), FString(WeatherPresetName(EWeatherPreset(S->WeatherPreset))) });
	Rows.Add({ TEXT("Start time"), FString::Printf(TEXT("%02d:%02d"), int32(S->StartHour), int32(FMath::Fmod(S->StartHour, 1.f) * 60.f)) });
	Rows.Add({ TEXT("Weather seed"), FString::FromInt(S->WeatherSeed) });
	Rows.Add({ TEXT("Difficulty"), S->Difficulty == ESailingDifficulty::Easy ? TEXT("Easy") : TEXT("Realistic") });
	Rows.Add({ TEXT("Controls"), S->Difficulty == ESailingDifficulty::Easy ? TEXT("Simple (always on Easy)") : (S->ControlLayout == ESailingControlLayout::Simple ? TEXT("Simple") : TEXT("Full")) });
	Rows.Add({ TEXT("Trim assist"), OnOff(S->bTrimAssist) });
	Rows.Add({ TEXT("Learning mode"), OnOff(S->bLearningMode) });
	Rows.Add({ TEXT("Graphics quality"), S->Quality == ESailingQuality::Low ? TEXT("Low") : (S->Quality == ESailingQuality::Medium ? TEXT("Medium")
		: (S->Quality == ESailingQuality::High ? TEXT("High") : TEXT("Ultra (desktop GPU)"))) });
	Rows.Add({ TEXT("Volume"), FString::Printf(TEXT("%d%%"), FMath::RoundToInt(S->Volume * 100.f)) });
	Rows.Add({ TEXT("Keys"), TEXT("Right: change your keys") });
	return Rows;
}

void ASailboatPawn::ChangeMenuValue(int32 Direction)
{
	USailingSettings* S = USailingSettings::Get();
	ASailingGameMode* GameMode = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	switch (MenuIndex)
	{
	case RowWorld:
		S->World = (S->World + 3 + Direction) % 3;
		S->LaunchSpot = 0;
		S->Save();
		UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this)));
		break;
	case RowRace:
		if (ATrafficManager* TM = ATrafficManager::Find(GetWorld()))
		{
			if (Direction > 0 && !TM->IsRacing()) TM->StartRace(5, 300.0);
			else if (Direction < 0) TM->EndRace();
		}
		break;
	case RowKeys:
		if (Direction > 0)
		{
			BuildKeyRows();
			bKeysOpen = true;
			bMenuOpen = false;
			KeysIndex = 0;
			KeysMessage = TEXT("Up / Down choose, Enter then press the new key, Backspace restores the default, Tab closes");
		}
		break;
	case RowGhost:
		bGhostOn = !bGhostOn && !LastRun.IsEmpty();
		if (!bGhostOn && GhostBoat) GhostBoat->SetActorHiddenInGame(true);
		break;
	case RowTraffic:
		S->TrafficLevel = (S->TrafficLevel + 3 + Direction) % 3;
		S->Save();
		break;
	case RowBoat:
		S->BoatType = (S->BoatType + int32(EBoatType::Count) + Direction) % int32(EBoatType::Count);
		SetBoat(S->BoatType);
		break;
	case RowDrill:
		MenuDrill = ESailingDrill((int32(MenuDrill) + int32(ESailingDrill::Count) + Direction) % int32(ESailingDrill::Count));
		StartDrill(MenuDrill);
		break;
	case RowLaunch:
		if (GameMode && GameMode->GetLake().LaunchSpots.Num() > 0)
		{
			const int32 N = GameMode->GetLake().LaunchSpots.Num();
			S->LaunchSpot = (S->LaunchSpot + N + Direction) % N;
			ResetBoat();
		}
		break;
	case RowLakeLevel:
		S->bGaugeLakeLevel = !S->bGaugeLakeLevel;
		break;
	case RowWeather:
		S->WeatherPreset = ESailingWeather((int32(S->WeatherPreset) + int32(EWeatherPreset::Count) + Direction) % int32(EWeatherPreset::Count));
		if (GameMode) GameMode->ApplyWeatherSettings();
		break;
	case RowHour:
		S->StartHour = FMath::Fmod(S->StartHour + Direction + 24.f, 24.f); // round the clock: night sailing too
		if (GameMode) GameMode->ApplyWeatherSettings();
		break;
	case RowSeed:
		S->WeatherSeed = FMath::Max(1, S->WeatherSeed + Direction);
		if (GameMode) GameMode->ApplyWeatherSettings();
		break;
	case RowDifficulty:
		S->Difficulty = S->Difficulty == ESailingDifficulty::Easy ? ESailingDifficulty::Realistic : ESailingDifficulty::Easy;
		ApplyDifficulty();
		if (GameMode) GameMode->ApplyDifficultyToWind();
		break;
	case RowControls:
		S->ControlLayout = S->ControlLayout == ESailingControlLayout::Simple ? ESailingControlLayout::Full : ESailingControlLayout::Simple;
		break;
	case RowTrimAssist:
		S->bTrimAssist = !S->bTrimAssist;
		break;
	case RowLearning:
		S->bLearningMode = !S->bLearningMode;
		break;
	case RowQuality:
		S->Quality = ESailingQuality((int32(S->Quality) + 4 + Direction) % 4);
		if (GameMode) GameMode->ApplyQualitySettings();
		break;
	case RowVolume:
		S->Volume = FMath::Clamp(S->Volume + 0.1f * Direction, 0.f, 1.f);
		break;
	default:
		break;
	}
	S->Save();
}

void ASailboatPawn::CreateInput()
{
	if (MappingContext)
	{
		return;
	}

	// Actions and the mapping context are built from USailingInputSettings (Input.ini), so keys can be rebound
	// without editing assets.
	MappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Sailboat"));
	for (const FSailingKeyBinding& Binding : GetDefault<USailingInputSettings>()->GetBindings())
	{
		TObjectPtr<UInputAction>& Action = Actions.FindOrAdd(Binding.Action);
		if (!Action)
		{
			Action = NewObject<UInputAction>(this, *FString::Printf(TEXT("IA_%s"), *Binding.Action.ToString()));
			Action->ValueType = Binding.Action == NAME_Look ? EInputActionValueType::Axis2D
				: (IsButtonAction(Binding.Action) ? EInputActionValueType::Boolean : EInputActionValueType::Axis1D);
		}
		FEnhancedActionKeyMapping& Mapping = MappingContext->MapKey(Action, Binding.Key);
		if (Binding.Scale < 0.f)
		{
			Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(MappingContext));
		}
		if (FMath::Abs(Binding.Scale) != 1.f)
		{
			UInputModifierScalar* Scalar = NewObject<UInputModifierScalar>(MappingContext);
			Scalar->Scalar = FVector(FMath::Abs(Binding.Scale));
			Mapping.Modifiers.Add(Scalar);
		}
	}
}

void ASailboatPawn::PawnClientRestart()
{
	Super::PawnClientRestart();
	CreateInput();

	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->ClearAllMappings();
			Subsystem->AddMappingContext(MappingContext, 0);
		}
	}
}

void ASailboatPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	CreateInput();

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogSailing, Warning, TEXT("SailboatPawn expects an EnhancedInputComponent; check DefaultInput.ini."));
		return;
	}
	for (const TPair<FName, TObjectPtr<UInputAction>>& Pair : Actions)
	{
		const FName Name = Pair.Key;
		UInputAction* Action = Pair.Value;
		if (Name == NAME_Look)
		{
			Input->BindAction(Action, ETriggerEvent::Triggered, this, &ASailboatPawn::OnLook);
		}
		else if (Name == NAME_Zoom)
		{
			Input->BindAction(Action, ETriggerEvent::Triggered, this, &ASailboatPawn::OnZoom);
		}
		else if (IsButtonAction(Name))
		{
			Input->BindAction(Action, ETriggerEvent::Started, this, &ASailboatPawn::OnButton, Name);
		}
		else
		{
			Input->BindAction(Action, ETriggerEvent::Triggered, this, &ASailboatPawn::OnAxis, Name);
			Input->BindAction(Action, ETriggerEvent::Completed, this, &ASailboatPawn::OnAxisReleased, Name);
		}
	}
}

void ASailboatPawn::SetupCapture()
{
	if (CapturePreset == ECapturePreset::None || bTrafficBoat) return;
	const FCapturePresetInfo& Info = CapturePresetInfo(CapturePreset);
	FParse::Value(FCommandLine::Get(), TEXT("SailingCaptureBearing="), CaptureBearing);
	FParse::Value(FCommandLine::Get(), TEXT("SailingEV="), CaptureEV);
	if (!FParse::Value(FCommandLine::Get(), TEXT("SailingShot="), CaptureName)) CaptureName = TEXT("capture");

	Camera->SetActive(false);
	CaptureCamera->SetActive(true);
	CaptureCamera->SetFieldOfView(Info.HFovDeg);
	CaptureCamera->bConstrainAspectRatio = false;
	if (Info.bOnboard)
	{
		FVector Location;
		FRotator Rotation;
		OnboardCameraMount(CapturePreset, Boat.GetConfig(), 0.f, Location, Rotation);
		CaptureCamera->SetUsingAbsoluteLocation(false);
		CaptureCamera->SetUsingAbsoluteRotation(false);
		CaptureCamera->SetRelativeLocationAndRotation(Location, Rotation);
	}
	else
	{
		// A chase boat, drone or tripod does not heel with the boat: place and aim it in the world every frame.
		CaptureCamera->SetUsingAbsoluteLocation(true);
		CaptureCamera->SetUsingAbsoluteRotation(true);
	}

	// A still that can be compared: exposure locked, no motion blur, no depth of field.
	FPostProcessSettings& PP = CaptureCamera->PostProcessSettings;
	CaptureCamera->PostProcessBlendWeight = 1.f;
	PP.bOverride_MotionBlurAmount = true;
	PP.MotionBlurAmount = 0.f;
	if (!FMath::IsNaN(CaptureEV))
	{
		PP.bOverride_AutoExposureMinBrightness = PP.bOverride_AutoExposureMaxBrightness = PP.bOverride_AutoExposureBias = true;
		PP.AutoExposureMinBrightness = PP.AutoExposureMaxBrightness = CaptureEV;
		PP.AutoExposureBias = 0.f;
		bExposureFrozen = true;
	}
	if (IConsoleVariable* Dof = IConsoleManager::Get().FindConsoleVariable(TEXT("r.DepthOfFieldQuality"))) Dof->Set(0, ECVF_SetByCode);
	if (Info.bBarrel && LensDistortionAsset)
	{
		LensDistortionMaterial = LensDistortionAsset;
		PP.AddBlendable(LensDistortionMaterial, 1.f);
	}

	const FString Dir = FPaths::ProjectSavedDir() / TEXT("Bench");
	CaptureTelemetry.Open(Dir / (CaptureName + TEXT(".telemetry.csv")));
	UE_LOG(LogTemp, Display, TEXT("Reference capture: %s, %.0f deg, %s"), Info.Name, Info.HFovDeg,
		FMath::IsNaN(CaptureEV) ? TEXT("auto exposure frozen at 2.5 s") : *FString::Printf(TEXT("EV100 %.1f"), CaptureEV));
}

void ASailboatPawn::UpdateCapture(float DeltaSeconds)
{
	CaptureElapsed += DeltaSeconds;
	const FCapturePresetInfo& Info = CapturePresetInfo(CapturePreset);
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();

	if (CapturePreset == ECapturePreset::HelmEye)
	{
		// The helmsman sits to windward and crosses over a couple of seconds after each tack.
		const float WantSide = T.TrueWindAngle >= 0.0 ? 1.f : -1.f;
		HelmSide = FMath::FInterpTo(HelmSide, WantSide, DeltaSeconds, 1.5f);
		FVector Location;
		FRotator Rotation;
		OnboardCameraMount(CapturePreset, Boat.GetConfig(), FMath::Sign(HelmSide), Location, Rotation);
		Location.Y *= FMath::Abs(HelmSide);
		CaptureCamera->SetRelativeLocationAndRotation(Location, Rotation);
		// We are the helmsman: hide the crew figures beside us (the camera is in one's head and the simple figures
		// would fill a phone's frame); those further forward stay in view, as in the reference clips.
		if (CapturePreset == ECapturePreset::HelmEye)
		{
			for (UPrimitiveComponent* Figure : Crew)
			{
				if (Figure) Figure->SetVisibility(FVector::Dist(Figure->GetComponentLocation(), CaptureCamera->GetComponentLocation()) > 2.2f * CmPerMeter);
			}
		}
	}
	if (!Info.bOnboard)
	{
		if (FMath::IsNaN(CaptureBearing) && CaptureElapsed > 0.2)
		{
			// Stand to leeward by default, where the sails show their faces (+ = starboard).
			CaptureBearing = FMath::IsNaN(Info.DefaultBearingDeg) ? (T.TrueWindAngle >= 0.0 ? -90.f : 90.f) : Info.DefaultBearingDeg;
		}
		// -SailingCaptureAbsolute: the bearing is a compass bearing from the boat (a shore tripod set up where the scene's
		// reference stood, e.g. looking into an approaching storm), fixed when the stand is set.
		if (!FMath::IsNaN(CaptureBearing) && !bCaptureBearingResolved && FParse::Param(FCommandLine::Get(), TEXT("SailingCaptureAbsolute")))
		{
			CaptureBearing = FMath::UnwindDegrees(CaptureBearing - float(FMath::RadiansToDegrees(T.Heading)));
		}
		bCaptureBearingResolved = true;
		const float Bearing = FMath::IsNaN(CaptureBearing) ? -90.f : CaptureBearing;
		const Vec3 O = Boat.OriginPosition();
		const FVector Origin(O.X * CmPerMeter, O.Y * CmPerMeter, 0.0);
		const float Heading = float(FMath::RadiansToDegrees(T.Heading));
		FVector Location;
		FRotator Rotation;
		WorldCameraPose(CapturePreset, Origin, Heading, Bearing, float(Boat.GetConfig().MastheadZ), WaterSurfaceZ, Location, Rotation);
		if (CapturePreset == ECapturePreset::ShoreTele)
		{
			// A tripod: it stays where it was set up and only pans.
			if (!bShoreStandSet && !FMath::IsNaN(CaptureBearing)) { ShoreStand = Location; bShoreStandSet = true; }
			if (bShoreStandSet)
			{
				const FVector Aim(Origin.X, Origin.Y, WaterSurfaceZ + 0.33f * float(Boat.GetConfig().MastheadZ) * CmPerMeter);
				Location = ShoreStand;
				Rotation = (Aim - ShoreStand).Rotation();
			}
		}
		// Measuring the sky: -SailingCamWorld=<north m>,<east m>,<up m>,<heading deg>,<pitch deg> fixes the camera in the
		// world, relative to the boat's start (the weather's origin).
		FString CamWorld;
		if (FParse::Value(FCommandLine::Get(), TEXT("SailingCamWorld="), CamWorld, false))
		{
			TArray<FString> P;
			CamWorld.ParseIntoArray(P, TEXT(","));
			if (P.Num() >= 5)
			{
				Location = StartLocation + FVector(FCString::Atof(*P[0]), FCString::Atof(*P[1]), FCString::Atof(*P[2])) * CmPerMeter;
				Location.Z = WaterSurfaceZ + FCString::Atof(*P[2]) * CmPerMeter;
				Rotation = FRotator(FCString::Atof(*P[4]), FCString::Atof(*P[3]), 0.f);
			}
		}
		// -SailingCamVessel=<kind>[,<distance m>,<bearing deg from her bow>]: frame the nearest traffic vessel of that kind
		// (ETrafficKind: 1 runabout, 2 trawler, 3 tug and tow, 4 ship, 5 committee boat) from the water, for the vessel models.
		FString CamVessel;
		if (FParse::Value(FCommandLine::Get(), TEXT("SailingCamVessel="), CamVessel, false))
		{
			TArray<FString> P;
			CamVessel.ParseIntoArray(P, TEXT(","));
			const int32 Want = P.Num() > 0 ? FCString::Atoi(*P[0]) : 3;
			const APowerVesselActor* Best = nullptr;
			for (TActorIterator<APowerVesselActor> It(GetWorld()); It; ++It)
			{
				if (int32(It->GetKind()) != Want) continue;
				if (!Best || FVector::Dist(It->GetActorLocation(), Origin) < FVector::Dist(Best->GetActorLocation(), Origin)) Best = *It;
			}
			if (Best)
			{
				const float Dist = P.Num() > 1 ? FCString::Atof(*P[1]) : 120.f;
				const float Brg = P.Num() > 2 ? FCString::Atof(*P[2]) : 50.f;
				const FRotator Dir(0.f, Best->GetActorRotation().Yaw + Brg, 0.f);
				Location = Best->GetActorLocation() + Dir.Vector() * Dist * CmPerMeter;
				Location.Z = WaterSurfaceZ + 2.0 * CmPerMeter;
				Rotation = (Best->GetActorLocation() + FVector(0, 0, 3.0 * CmPerMeter) - Location).Rotation();
			}
		}
		CaptureCamera->SetWorldLocationAndRotation(Location, Rotation);
	}

	// Auto exposure settles in the first seconds; then it is held so the stills compare.
	if (!bExposureFrozen && CaptureElapsed > 2.5)
	{
		FPostProcessSettings& PP = CaptureCamera->PostProcessSettings;
		PP.bOverride_AutoExposureSpeedUp = PP.bOverride_AutoExposureSpeedDown = true;
		PP.AutoExposureSpeedUp = PP.AutoExposureSpeedDown = 0.0001f;
		bExposureFrozen = true;
	}

	const Vec3 O = Boat.OriginPosition();
	const double Wave = GM ? GM->GetWaves().Height(O.X, O.Y, Boat.GetState().Time) : 0.0;
	CaptureTelemetry.Add(FCaptureTelemetryRow::FromBoat(CaptureElapsed, Boat, Controls, Wave));

	if (CaptureElapsed - CaptureSettingsWritten >= 1.0)
	{
		WriteCaptureSettings();
		CaptureSettingsWritten = CaptureElapsed;
	}
}

void ASailboatPawn::WriteCaptureSettings() const
{
	const FCapturePresetInfo& Info = CapturePresetInfo(CapturePreset);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FVector L = CaptureCamera->GetComponentLocation();
	const FRotator R = CaptureCamera->GetComponentRotation();
	double SunElevation = 0.0, SunAzimuth = 0.0;
	FString Area, Date;
	double Latitude = 0.0, Longitude = 0.0, Hour = 0.0, Gust = 0.0;
	if (GM)
	{
		ASailingEnvironment::SunPosition(GM->GetWeatherState().HourOfDay, GM->GetDayOfYear(), GM->GetLake().Latitude, GM->GetLake().Longitude, GM->GetUtcOffsetHours(), SunElevation, SunAzimuth);
		Area = ASailingGameMode::WorldDisplayName(USailingSettings::Get()->World);
		Latitude = GM->GetLake().Latitude;
		Longitude = GM->GetLake().Longitude;
		Hour = GM->GetWeatherState().HourOfDay;
		Gust = GM->GetWind().GetParams().GustIntensity;
		Date = FDateTime::FromUnixTimestamp(int64(GM->GetUnixTime() + GM->GetUtcOffsetHours() * 3600.0)).ToString(TEXT("%Y-%m-%d"));
	}
	const FString Json = FString::Printf(
		TEXT("{\n  \"preset\": \"%s\",\n  \"hfov_deg\": %.1f,\n  \"barrel_distortion\": %s,\n  \"exposure\": \"%s\",\n")
		TEXT("  \"camera_m\": [%.2f, %.2f, %.2f],\n  \"camera_pitch_yaw_roll_deg\": [%.1f, %.1f, %.1f],\n  \"bearing_off_bow_deg\": %.0f,\n")
		TEXT("  \"area\": \"%s\",\n  \"latitude\": %.4f,\n  \"longitude\": %.4f,\n  \"date\": \"%s\",\n  \"clock_hour\": %.2f,\n")
		TEXT("  \"sun_elevation_deg\": %.1f,\n  \"sun_azimuth_deg\": %.1f,\n")
		TEXT("  \"true_wind_kn\": %.1f,\n  \"true_wind_from_deg\": %.0f,\n  \"gust_intensity\": %.2f,\n")
		TEXT("  \"boat\": \"%hs\",\n  \"reef\": %d,\n  \"spinnaker\": %s,\n  \"crew_kg\": %.0f,\n  \"seconds_into_capture\": %.1f\n}\n"),
		Info.Name, Info.HFovDeg, Info.bBarrel ? TEXT("true") : TEXT("false"),
		FMath::IsNaN(CaptureEV) ? TEXT("auto, frozen at 2.5 s") : *FString::Printf(TEXT("EV100 %.1f"), CaptureEV),
		L.X / CmPerMeter, L.Y / CmPerMeter, L.Z / CmPerMeter, R.Pitch, R.Yaw, R.Roll, FMath::IsNaN(CaptureBearing) ? 0.f : CaptureBearing,
		*Area, Latitude, Longitude, *Date, Hour, SunElevation, SunAzimuth, // SunPosition works in degrees
		T.TrueWindSpeed / kKnot, FMath::Fmod(FMath::RadiansToDegrees(T.Heading + T.TrueWindAngle) + 720.0, 360.0), Gust,
		Boat.GetConfig().Name, Controls.Reef, Controls.bSpinnaker ? TEXT("true") : TEXT("false"), Boat.GetConfig().CrewMass, CaptureElapsed);
	FFileHelper::SaveStringToFile(Json, *(FPaths::ProjectSavedDir() / TEXT("Bench") / (CaptureName + TEXT(".camera.json"))));
}

bool ASailboatPawn::LoadMetaCrew()
{
	if (MetaCrewRigs.Num() == NumMetaHumanRoles) return true;
	TArray<TObjectPtr<USkeletalMesh>> Meshes;
	TArray<FCrewRig> Rigs;
	for (int32 R = 0; R < NumMetaHumanRoles; ++R)
	{
		USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
		if (!LoadMetaHumanCrew(R, Body, Face, Outfit)) return false;
		Meshes.Append({ Body, Face, Outfit });
		BuildCrewRig(Body, Rigs.AddDefaulted_GetRef());
	}
	CrewPFDMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Crew/Gear/SM_CrewPFD.SM_CrewPFD"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	CrewCapMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Crew/Gear/SM_CrewCap.SM_CrewCap"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	MetaCrewMeshes = Meshes;
	MetaCrewRigs = MoveTemp(Rigs);
	return true;
}

UPoseableMeshComponent* ASailboatPawn::AddMetaHumanFigure(int32 CrewRole, int32 Index)
{
	USkeletalMesh* BodyMesh = MetaCrewMeshes[3 * CrewRole];
	const FCrewRig& Rig = MetaCrewRigs[CrewRole];
	UPoseableMeshComponent* Body = NewObject<UPoseableMeshComponent>(this);
	Body->SetupAttachment(BoatRoot);
	Body->SetSkinnedAssetAndUpdate(BodyMesh);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->RegisterComponent();
	BoatParts.Add(Body);
	// The face and the clothes follow the body's bones (the face's own joints rest: no expressions).
	USkeletalMeshComponent* FacePart = nullptr;
	for (int32 K = 1; K <= 2; ++K)
	{
		if (!MetaCrewMeshes[3 * CrewRole + K]) continue;
		USkeletalMeshComponent* Part = NewObject<USkeletalMeshComponent>(this);
		if (K == 1) FacePart = Part;
		Part->SetupAttachment(Body);
		Part->SetSkeletalMesh(MetaCrewMeshes[3 * CrewRole + K]);
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Part->RegisterComponent();
		Part->SetLeaderPoseComponent(Body);
		Part->SetDisablePostProcessBlueprint(true); // the face's RigLogic post-process would run for a resting face
		if (K == 2)
		{
			// The default garment comes white; sailing tops and shorts of each sailor's own colours.
			static const FLinearColor Shirts[] = { FLinearColor(0.02f, 0.04f, 0.12f), FLinearColor(0.35f, 0.36f, 0.38f), FLinearColor(0.18f, 0.02f, 0.02f), FLinearColor(0.03f, 0.12f, 0.16f) };
			static const FLinearColor Shorts[] = { FLinearColor(0.25f, 0.2f, 0.12f), FLinearColor(0.02f, 0.03f, 0.08f), FLinearColor(0.1f, 0.1f, 0.1f) };
			for (int32 M = 0; M < Part->GetNumMaterials(); ++M)
			{
				const UMaterialInterface* Base = Part->GetMaterial(M);
				const bool bShirt = Base && Base->GetName().Contains(TEXT("Shirt"));
				const FLinearColor Col = bShirt ? Shirts[CrewRole % UE_ARRAY_COUNT(Shirts)] : Shorts[CrewRole % UE_ARRAY_COUNT(Shorts)];
				// Graphics G3: the shorts in scanned cotton twill (M_CrewFabric), where it has been built.
				// Loaded each time (not cached in a static: a level reload collects it and the pointer would dangle).
				UMaterialInterface* ShortsCloth = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Crew/Fabric/MI_Crew_Shorts.MI_Crew_Shorts"), nullptr, LOAD_NoWarn | LOAD_Quiet);
				if (!bShirt && ShortsCloth)
				{
					UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ShortsCloth, this);
					Mid->SetVectorParameterValue(TEXT("Color"), Col);
					Part->SetMaterial(M, Mid);
					continue;
				}
				if (UMaterialInstanceDynamic* Mid = Part->CreateDynamicMaterialInstance(M))
				{
					for (const TCHAR* Param : { TEXT("diffuse_color_1"), TEXT("diffuse_color_2"), TEXT("B_diffuse_color_1"), TEXT("C_color") }) Mid->SetVectorParameterValue(Param, Col);
				}
			}
		}
		BoatParts.Add(Part);
		// Graphics G3: the scripted polo (scripts/make-crew-clothes.sh) over the shorts, in place of the default T-shirt:
		// the outfit's shirt sections are hidden on every LOD and the polo follows the body like the rest.
		if (K == 2 && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoPolo")))
		{
			const FString R = MetaHumanRoleName(CrewRole);
			USkeletalMesh* PoloMesh = LoadObject<USkeletalMesh>(nullptr, *FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Clothing/SKM_%s_Polo.SKM_%s_Polo"), *R, *R, *R), nullptr, LOAD_NoWarn | LOAD_Quiet);
			const FSkeletalMeshRenderData* Render = Part->GetSkeletalMeshAsset() ? Part->GetSkeletalMeshAsset()->GetResourceForRendering() : nullptr;
			if (PoloMesh && Render)
			{
				for (int32 L = 0; L < Render->LODRenderData.Num(); ++L)
				{
					const TArray<FSkelMeshRenderSection>& Sections = Render->LODRenderData[L].RenderSections;
					for (int32 S = 0; S < Sections.Num(); ++S)
					{
						const UMaterialInterface* Mat = Part->GetMaterial(Sections[S].MaterialIndex);
						if (Mat && Mat->GetName().Contains(TEXT("Shirt"))) Part->ShowMaterialSection(Sections[S].MaterialIndex, S, false, L);
					}
				}
				USkeletalMeshComponent* Polo = NewObject<USkeletalMeshComponent>(this);
				Polo->SetupAttachment(Body);
				Polo->SetSkeletalMesh(PoloMesh);
				Polo->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				Polo->RegisterComponent();
				Polo->SetLeaderPoseComponent(Body);
				static const FLinearColor Polos[] = { FLinearColor(0.02f, 0.05f, 0.16f), FLinearColor(0.75f, 0.74f, 0.70f), FLinearColor(0.20f, 0.02f, 0.02f), FLinearColor(0.03f, 0.14f, 0.18f) };
				const FLinearColor Col = Polos[CrewRole % UE_ARRAY_COUNT(Polos)];
				for (int32 M = 0; M < Polo->GetNumMaterials(); ++M)
				{
					if (M == Polo->GetMaterialIndex(TEXT("Button"))) continue;
					if (UMaterialInstanceDynamic* Mid = Polo->CreateDynamicMaterialInstance(M)) Mid->SetVectorParameterValue(TEXT("Color"), M == Polo->GetMaterialIndex(TEXT("Rib")) ? Col * 0.92f : Col);
				}
				BoatParts.Add(Polo);
			}
		}
	}
	// Graphics G3: deck shoes (scripts/make-crew-clothes.sh, built round each sailor's feet and skinned from them).
	if (!FParse::Param(FCommandLine::Get(), TEXT("SailingNoPolo")))
	{
		const FString R = MetaHumanRoleName(CrewRole);
		if (USkeletalMesh* ShoeMesh = LoadObject<USkeletalMesh>(nullptr, *FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Clothing/SKM_%s_Shoes.SKM_%s_Shoes"), *R, *R, *R), nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			USkeletalMeshComponent* Shoes = NewObject<USkeletalMeshComponent>(this);
			Shoes->SetupAttachment(Body);
			Shoes->SetSkeletalMesh(ShoeMesh);
			Shoes->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Shoes->RegisterComponent();
			Shoes->SetLeaderPoseComponent(Body);
			static const FLinearColor Leather[] = { FLinearColor(0.28f, 0.14f, 0.06f), FLinearColor(0.12f, 0.07f, 0.04f), FLinearColor(0.35f, 0.24f, 0.14f) };
			const int32 Upper = Shoes->GetMaterialIndex(TEXT("Upper"));
			if (Upper >= 0)
				if (UMaterialInstanceDynamic* Mid = Shoes->CreateDynamicMaterialInstance(Upper)) Mid->SetVectorParameterValue(TEXT("Color"), Leather[CrewRole % UE_ARRAY_COUNT(Leather)]);
			BoatParts.Add(Shoes);
		}
	}
	// Graphics G3: hair, brows and beard on the face. Strands on High and Ultra; the groom's cards on Medium.
	if (FacePart && !FParse::Param(FCommandLine::Get(), TEXT("SailingNoGrooms")))
	{
		const bool bStrands = USailingSettings::Get()->Quality >= ESailingQuality::High;
		TArray<TPair<UGroomAsset*, UGroomBindingAsset*>> Grooms;
		LoadMetaHumanGrooms(CrewRole, Grooms);
		for (const TPair<UGroomAsset*, UGroomBindingAsset*>& G : Grooms)
		{
			// Under a cap the scalp hair would poke through its crown: only brows, beard and moustache.
			if (CrewRole != 0 && CrewCapMesh && G.Key->GetName().StartsWith(TEXT("Hair_"))) continue;
#if PLATFORM_MAC
			// The Mac draws cards (no strand geometry on its SM5 platform), 1.5 ms of GPU on High for the whole crew: the hair
			// and beard carry the look; brows and moustache cards are left off (their LOD 2+ has no cards built, so a forced LOD only hides the hair).
			const bool bMacCards = true;
#else
			const bool bMacCards = false;
#endif
			if (bMacCards && (G.Key->GetName().StartsWith(TEXT("Eyebrows_")) || G.Key->GetName().StartsWith(TEXT("Mustache_")))) continue;
			UGroomComponent* Hair = NewObject<UGroomComponent>(this);
			Hair->SetupAttachment(FacePart);
			Hair->SetUseCards(!bStrands);
			Hair->SetGroomAsset(G.Key, G.Value);
			Hair->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Hair->RegisterComponent();
			BoatParts.Add(Hair);
		}
	}
	// The life jacket over the shirt, the cap over the head, each scaled to this skeleton and carried by the
	// chest and head bones: placed on the T-posed rest, relative to the bone's rest.
	const auto At = [&](const TCHAR* Bone) { return Rig.Rest(BodyMesh, Bone).GetLocation(); };
	const FVector Fwd = Rig.Frame.RotateVector(FVector::ForwardVector);
	const float Span = float(FVector::Dist(At(TEXT("upperarm_l")), At(TEXT("upperarm_r"))));
	const float Waist = float(At(TEXT("spine_01")).Z) + 3.f; // the hem at the navel, clear of the shorts' waistband
	const float Top = float(At(TEXT("neck_01")).Z) + 1.f;   // Graphics G6: up to the collarbones (the vest's shoulders)
	// Graphics G6: the sailing school's royal blue vests (Bean's lesson photos), one older and faded.
	static const FLinearColor Foam[] = { FLinearColor(0.012f, 0.075f, 0.52f), FLinearColor(0.014f, 0.09f, 0.48f), FLinearColor(0.03f, 0.10f, 0.38f) };
	// Graphics G6: the life jacket tailored over this sailor's polo (Tools/blender/build_vest.py) and skinned like it, so it
	// wraps the body as it sits; the rigid one below where it has not been built (or with -SailingNoPolo).
	const FString VestRole = MetaHumanRoleName(CrewRole);
	USkeletalMesh* VestMesh = FParse::Param(FCommandLine::Get(), TEXT("SailingNoPolo")) ? nullptr
		: LoadObject<USkeletalMesh>(nullptr, *FString::Printf(TEXT("/Game/Crew/MetaHumans/%s/Clothing/SKM_%s_Vest.SKM_%s_Vest"), *VestRole, *VestRole, *VestRole), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (VestMesh)
	{
		USkeletalMeshComponent* Vest = NewObject<USkeletalMeshComponent>(this);
		Vest->SetupAttachment(Body);
		Vest->SetSkeletalMesh(VestMesh);
		Vest->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Vest->RegisterComponent();
		Vest->SetLeaderPoseComponent(Body);
		const int32 Shell = Vest->GetMaterialIndex(TEXT("PFD"));
		if (UMaterialInstanceDynamic* Mid = Shell >= 0 ? Vest->CreateDynamicMaterialInstance(Shell) : nullptr) Mid->SetVectorParameterValue(TEXT("Color"), Foam[(CrewRole + Index / NumMetaHumanRoles) % UE_ARRAY_COUNT(Foam)]);
		BoatParts.Add(Vest);
	}
	else if (CrewPFDMesh && Span > 10.f && Top > Waist)
	{
		const FVector Chest = At(TEXT("spine_03"));
		// Over the shirt (mesh X is depth, Y width): the torso plus foam, centred a little ahead of the spine joints.
		// Graphics G6: deeper and centred further back, so it wraps the polo's back and sides (ahead of the spine it left the
		// polo showing through behind).
		const FTransform Place(Rig.Frame, FVector(Chest.X, Chest.Y, Waist) + Fwd * (0.06f * Span), FVector(0.0158f * Span, 0.0128f * Span, 0.0092f * (Top - Waist + 2.f)));
		UStaticMeshComponent* Pfd = NewObject<UStaticMeshComponent>(this);
		Pfd->SetStaticMesh(CrewPFDMesh);
		Pfd->SetupAttachment(Body, TEXT("spine_04"));
		Pfd->SetRelativeTransform(Place.GetRelativeTransform(Rig.Rest(BodyMesh, TEXT("spine_04"))));
		Pfd->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Pfd->RegisterComponent();
		if (UMaterialInstanceDynamic* Mid = Pfd->CreateDynamicMaterialInstance(0)) Mid->SetVectorParameterValue(TEXT("Color"), Foam[(CrewRole + Index / NumMetaHumanRoles) % UE_ARRAY_COUNT(Foam)]);
		BoatParts.Add(Pfd);
	}
	// The helm goes bare-headed (his hair and the trimmer's and bow's caps: crews are mixed).
	if (CrewCapMesh && CrewRole != 0)
	{
		// On the head: the scalp groom is left off under it (see the grooms above).
		const FVector Head = At(TEXT("head")) + FVector(0.f, 0.f, 11.0f) + Fwd * 0.8f;
		const FTransform Place(Rig.Frame, Head, FVector(0.106f, 0.105f, 0.076f));
		UStaticMeshComponent* Cap = NewObject<UStaticMeshComponent>(this);
		Cap->SetStaticMesh(CrewCapMesh);
		Cap->SetupAttachment(Body, TEXT("head"));
		Cap->SetRelativeTransform(Place.GetRelativeTransform(Rig.Rest(BodyMesh, TEXT("head"))));
		Cap->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Cap->RegisterComponent();
		static const FLinearColor Caps[] = { FLinearColor(0.8f, 0.8f, 0.78f), FLinearColor(0.02f, 0.04f, 0.12f), FLinearColor(0.35f, 0.3f, 0.2f) };
		if (UMaterialInstanceDynamic* Mid = Cap->CreateDynamicMaterialInstance(0)) Mid->SetVectorParameterValue(TEXT("Color"), Caps[CrewRole % UE_ARRAY_COUNT(Caps)]);
		BoatParts.Add(Cap);
	}
	return Body;
}
