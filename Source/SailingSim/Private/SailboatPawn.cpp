#include "SailboatPawn.h"
#include "CrewOutfit.h"
#include "SailingFrame.h"
#include "BenchRunner.h"
#include "PerfScopes.h"
#include "SailingHUD.h"
#include "UI/SailHud.h"
#include "SailSession.h"
#include "SailSave.h"
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
#include "SailingBindings.h"
#include "InputModifiers.h"
#include "InputTriggers.h"
#include "FreeCamera.h"
#include "Engine/AssetManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Kismet/GameplayStatics.h"
#include "ProceduralMeshComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Materials/MaterialParameterCollection.h"
#include "CrewAnimInstance.h"
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
			|| Action == TEXT("CockpitView") || Action == TEXT("CrewAction") || Action == TEXT("TravellerDump") || Action == TEXT("Station")
			|| Action == TEXT("PhotoRollReset") || Action == TEXT("PhotoToBoat") || Action == TEXT("PhotoOrbit") || Action == TEXT("PhotoHideUI");
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
	if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingCrewKg="), CrewKg) && CrewKg > 0.f)
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
	CrewClothMids.Reset();
	ModelHull = ModelMast = ModelBoom = ModelRudder = TravelerCar = nullptr;
	MastMaterial = nullptr;
	RigLines->ClearAllMeshSections();
	bRigLinesBuilt = false;
	RigLineKeys[0].Reset();
	RigLineKeys[1].Reset();
	// Graphics G3: the livery (BoatLivery.h). The player's (and its ghost's) is the class's most common scheme as a club
	// boat; each AI boat draws its own. -SailingLiverySeed=<n> picks one (stills).
	{
		uint32 Seed = bTrafficBoat && !bGhost ? GetUniqueID() * 7919u + 1u : 0u;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingLiverySeed="), Seed);
		Livery = SampleBoatLivery(int32(Boat.GetConfig().Type), Seed);
		CrewSeed = Seed;
	}
	const FBoatModelMeshes Model = ModelMeshesFor(Boat.GetConfig().Type);
	bModelTravelerBridge = Model.bTravelerBridge;
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
	// pc/sunfish-fidelity: a Sunfish carries no masthead fly (class photos); her halyard cap is the model's. pc/ilca-fidelity:
	// nor does an ILCA, whose sail's sleeve goes over the masthead.
	MastheadFly->SetVisibility(C.Type != EBoatType::Sunfish && C.Type != EBoatType::ILCA7, true);

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

	// Outboards hang on the transom (inboards and saildrives are out of sight); a model that carries its own draws none
	// (round 12: the grey box read as a placeholder).
	for (const FEngineDef& E : C.Engines)
	{
		if (E.Position.X < Main.SternX + 0.2 && !(ModelHull && Model.bOwnOutboard))
		{
			AddBoatPart(CubeMesh, ToCm(E.Position.X - 0.1, E.Position.Y, E.Position.Z + 0.55), FVector(0.3, 0.25, 1.1) * CmPerMeter, Grey);
		}
	}

	// Crew (Visual V3): posed sailors (CrewPose.h), in the boat's crew colours (CrewOutfit.h).
	CrewFigures.Reset();
	CrewConfig.Reset(); // a copy of this config for the crew's animation (NewCrewBody)
	CrewGrooms.Reset();
	// Visual V7: MetaHumans on the player's boat on Medium and High when they are built (scripts/make-metahumans.sh);
	// the helm is the last figure, the trimmer the one before, the rest work the bow. -SailingBlenderCrew opts out.
	const bool bMeta = !bTrafficBoat && USailingSettings::Get()->Quality != ESailingQuality::Low
		&& !FParse::Param(SailingArgs::Dev(), TEXT("SailingBlenderCrew")) && LoadMetaCrew();
	for (int32 I = 0; I < C.CrewCount && bMeta; ++I)
	{
		const int32 CrewRole = CrewMetaHumanRole(C.CrewCount, I);
		if (USkeletalMeshComponent* Figure = AddMetaHumanFigure(CrewRole, I))
		{
			Crew.Add(Figure);
			CrewFigures.AddDefaulted_GetRef().Rig = CrewRole;
		}
	}
	for (int32 I = 0; I < C.CrewCount && SailorMesh && !bMeta; ++I)
	{
		USkeletalMeshComponent* Figure = NewCrewBody(SailorMesh, -1);
		for (const TPair<FName, TObjectPtr<UMaterialInterface>>& M : CrewMaterials) Figure->SetMaterialByName(M.Key, M.Value);
		// pc/crew-colours: the top in the crew's light polo colour and the life jacket bright (CrewOutfit.h), as the MetaHumans.
		const FCrewOutfit Outfit = SampleCrewOutfit(CrewSeed, I);
		const int32 JacketSlot = Figure->GetMaterialIndex(TEXT("Jacket"));
		if (JacketSlot >= 0)
		{
			if (UMaterialInstanceDynamic* Mid = Figure->CreateDynamicMaterialInstance(JacketSlot)) Mid->SetVectorParameterValue(TEXT("Color"), Outfit.Polo);
		}
		const int32 PfdSlot = Figure->GetMaterialIndex(TEXT("PFD"));
		if (PfdSlot >= 0)
		{
			if (UMaterialInstanceDynamic* Mid = Figure->CreateDynamicMaterialInstance(PfdSlot)) Mid->SetVectorParameterValue(TEXT("Color"), Outfit.Vest);
		}
		BoatParts.Add(Figure);
		Crew.Add(Figure);
		CrewFigures.AddDefaulted();
	}
	// Crew C5: falls (Physics Control on the MetaHumans; Ultra, or -SailingCrewFalls=1).
	SetupCrewFalls();

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
	// tri-radial cruising and racing multihull mains with full battens, the ILCA's three short battens; the maxi's black
	// membrane main with six full battens (Layout 4: fibre paths from the corners, a few wide panels).
	// Sails look (docs/sails-look): each class's cloth width (the crosscut panels, the Sunfish's and Hobie's colour bands)
	// and whether its jib carries a clear window (the club keelboats').
	struct FSailLayout { float Layout, Battens, Full, PanelWidth = 0.9f, JibWindow = 0.f; };
	auto LayoutFor = [](EBoatType T) -> FSailLayout
	{
		switch (T)
		{
		case EBoatType::Sunfish: return { 1.f, 0.f, 0.f, 0.42f };
		case EBoatType::ILCA7: return { 0.f, 3.f, 0.f, 0.72f };
		case EBoatType::Hobie16: return { 2.f, 7.f, 1.f, 0.85f };
		case EBoatType::Corsair880: return { 3.f, 5.f, 1.f, 0.9f };
		case EBoatType::Lagoon42: return { 3.f, 5.f, 1.f, 1.0f };
		case EBoatType::Catalina22: return { 0.f, 4.f, 0.f, 0.9f, 1.f };
		case EBoatType::Catalina30: return { 0.f, 4.f, 0.f, 1.0f, 1.f };
		case EBoatType::Maxi: return { 4.f, 6.f, 1.f, 3.4f };
		default: return { 0.f, 4.f, 0.f, 0.9f, 1.f };    // the J/22
		}
	};
	// The leech's forward travel per metre of height (the crosscut seams meet it at right angles), from the sail's strips.
	auto LeechLean = [](const Sailing::FSailGeometry& G) -> float
	{
		if (G.NumStrips < 2) return 0.25f;
		const Sailing::FSailStripGeometry& A = G.Strips[0];
		const Sailing::FSailStripGeometry& B = G.Strips[G.NumStrips - 1];
		const double Dz = 0.5 * (B.ZBottom + B.ZTop) - 0.5 * (A.ZBottom + A.ZTop);
		const double Dx = (B.LuffX - B.Chord) - (A.LuffX - A.Chord);
		return Dz > 0.1 ? float(FMath::Clamp(Dx / Dz, 0.0, 1.2)) : 0.25f;
	};
	const FSailLayout Lay = LayoutFor(C.Type);
	// Boat fidelity 4: M_SailCloth's sailmaker's detail (seams held on screen, stitching, tabling, corner patches, pocket
	// ends) on High and Ultra; Medium and Low keep the plain path. -SailingNoSailDetail compares.
	static SailingArgs::FCachedFlag NoSailDetailArg(TEXT("SailingNoSailDetail"));
	const float SailDetail = USailingSettings::Get()->Quality >= ESailingQuality::High && !NoSailDetailArg.Get() ? 1.f : 0.f;
	if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(MainSail->GetMaterial(0)))
	{
		Mid->SetScalarParameterValue(TEXT("Detail"), SailDetail);
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
		Mid->SetScalarParameterValue(TEXT("Fade"), Livery.SailFade);   // fleet hero: the coloured cloth's sun fade
		Mid->SetScalarParameterValue(TEXT("LeechLean"), LeechLean(C.Main));
		Mid->SetScalarParameterValue(TEXT("PanelWidth"), Lay.PanelWidth);
		Mid->SetScalarParameterValue(TEXT("Window"), 0.f);
	}
	// Graphics G8 (round 8, the race start: "drab colors"): a club race fleet isn't all white Dacron. Keelboats sailing as
	// traffic with a race wear profile, and a third of the rest, carry laminate sails: smoky grey, grey Mylar or tan aramid
	// (light enough that the dark sail numbers still read). The player's boat keeps the club's Dacron.
	FLinearColor SailColor = Lay.Layout == 4.f ? FLinearColor(0.035f, 0.036f, 0.04f) : FLinearColor(0.70f, 0.68f, 0.63f);
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
		Mid->SetScalarParameterValue(TEXT("Detail"), SailDetail);
		// The jibs match their mains' colours (no battens).
		Mid->SetScalarParameterValue(TEXT("Layout"), Lay.Layout >= 2.f ? Lay.Layout : 0.f);
		Mid->SetScalarParameterValue(TEXT("Height"), C.Jib.NumStrips > 0 ? float(C.Jib.Strips[C.Jib.NumStrips - 1].ZTop - C.Jib.Strips[0].ZBottom) : 1.f);
		Mid->SetScalarParameterValue(TEXT("Fade"), Livery.SailFade);
		Mid->SetScalarParameterValue(TEXT("LeechLean"), LeechLean(C.Jib));
		Mid->SetScalarParameterValue(TEXT("PanelWidth"), Lay.PanelWidth);
		Mid->SetScalarParameterValue(TEXT("Window"), Lay.JibWindow);
	}
	// Realism audit 7: the spinnaker's own cloth (M_SailCloth Layout 5: horizontal panels, a radial head) and the
	// sailmaker's detail; it had kept the material's defaults, a main's crosscut lines on red nylon.
	if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(SpinSail->GetMaterial(0)))
	{
		Mid->SetScalarParameterValue(TEXT("Detail"), SailDetail);
		Mid->SetScalarParameterValue(TEXT("Layout"), 5.f);
		Mid->SetScalarParameterValue(TEXT("Marks"), 0.f);
		Mid->SetScalarParameterValue(TEXT("Battens"), 0.f);
		Mid->SetScalarParameterValue(TEXT("Height"), C.Spinnaker.NumStrips > 0 ? float(C.Spinnaker.Strips[C.Spinnaker.NumStrips - 1].ZTop - C.Spinnaker.Strips[0].ZBottom) : 1.f);
		Mid->SetScalarParameterValue(TEXT("PanelWidth"), 1.0f);
		Mid->SetScalarParameterValue(TEXT("LeechLean"), 0.f);
		Mid->SetScalarParameterValue(TEXT("Window"), 0.f);
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
	SailingPerf::KeepDynamicMeshesOutOfRayTracing(this);
}

const FWindField& ASailboatPawn::GetWind() const
{
	if (const ASailingGameMode* GameMode = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr)
	{
		return GameMode->GetWind();
	}
	return FallbackWind;
}

void ASailboatPawn::HoldForTests(double TwaDeg, double WindKnots)
{
	FWindParams Params;
	Params.SpeedKnots = WindKnots;
	FallbackWind.SetParams(Params);
	bDemo = true;
	bDemoTacks = false;
	CrudeTackAt = -1.0;
	DemoPilot.TargetTWADeg = TwaDeg;
	DemoPilot.MaxTiller = 0.8;
	// The held states are the rig's own trim, as the polars sail them (docs/trimmer-hands/).
	TrimAssist.Settings.bHands = false;
	bRecordRigLines = true;
	// On the point of sail from the start, with way on (as -SailingTWA's start does).
	const Vec3 O = Boat.OriginPosition();
	Boat.Reset(O.X, O.Y, FMath::DegreesToRadians(Params.FromDegrees - TwaDeg), 4.0 * kKnot);
}

FString ASailboatPawn::EasyRunJson() const
{
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const double Twa = T.TrueWindAngle * kRadToDeg;
	const bool bTacked = CrudeTackSign != 0 && Twa * CrudeTackSign < -FEasyAssists::kRealisticNoGoDeg && T.ForwardSpeed > 1.5 * kKnot;
	return FString::Printf(TEXT("\"easy\":%s,\"heel_cap_deg\":%.1f,\"max_heel_deg\":%.1f,\"crude_tack\":%s,\"tacked\":%s,\"final_twa_deg\":%.1f,\"final_kn\":%.2f"),
		EasyAssists.bEnabled ? TEXT("true") : TEXT("false"), EasyAssists.HeelCapDegFor(Boat.GetConfig()), RunMaxHeelDeg, CrudeTackSign != 0 ? TEXT("true") : TEXT("false"),
		bTacked ? TEXT("true") : TEXT("false"), Twa, T.ForwardSpeed / kKnot);
}

bool ASailboatPawn::IsTrimAssistActive() const
{
	// Easy mode: always on, back a few seconds after the player's own trim.
	if (EasyAssists.bEnabled) return Boat.GetState().Time - LastManualTrimTime > EasyAssists.TrimIdleSeconds;
	return USailingSettings::Get()->bTrimAssist && Boat.GetState().Time - LastManualTrimTime > kTrimAssistIdleSeconds;
}

void ASailboatPawn::EndPlay(const EEndPlayReason::Type Reason)
{
	// Career 1: the session's time on the world clock (the boat's physics time) and the logbook's counts (rule 3).
	if (!bTrafficBoat && !bGhost && bLogStarted && !IsCaptureMode())
	{
		SailCareer::RecordSession(Boat.GetState().Time, Logbook.GetEntries().Num(), LogNm);
	}
	Super::EndPlay(Reason);
}

void ASailboatPawn::BeginPlay()
{
	Super::BeginPlay();

	// Boat detail pass: braided rope and 1x19 wire for the live rig lines (scripts/import_boat_detail.py), when imported;
	// otherwise the flat MI_Boat_Rope / MI_Boat_Stainless stay. -SailingFlatRope compares.
	if (!FParse::Param(SailingArgs::Dev(), TEXT("SailingFlatRope")))
	{
		if (UMaterialInterface* R = Cast<UMaterialInterface>(StaticLoadObject(UMaterialInterface::StaticClass(), nullptr, TEXT("/Game/Boats/Rope/M_RigRope.M_RigRope"), nullptr, LOAD_NoWarn | LOAD_Quiet)))
		{
			RopeMaterial = R;
		}
		if (UMaterialInterface* W = Cast<UMaterialInterface>(StaticLoadObject(UMaterialInterface::StaticClass(), nullptr, TEXT("/Game/Boats/Rope/M_RigWire.M_RigWire"), nullptr, LOAD_NoWarn | LOAD_Quiet)))
		{
			WireMaterial = W;
		}
	}

	if (TActorIterator<AWaterSurface> It(GetWorld()); It)
	{
		Water = *It;
		WaterSurfaceZ = It->GetSurfaceZ();
	}
	StartLocation = SailingFrame::ToMapCm(GetWorld(), GetActorLocation());
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
	if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingTWA="), StartTwa))
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
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingBoat="), BoatArg))
	{
		// -SailingBoat=Hobie (the first letters of a fleet boat's name, any case; J22 is the J/22), for this run only.
		const int32 Match = USailingSettings::MatchBoatName(BoatArg);
		if (Match >= 0) USailingSettings::Get()->BoatType = Match;
		else UE_LOG(LogSailing, Warning, TEXT("-SailingBoat=%s matches no boat; sailing the %s"), *BoatArg, UTF8_TO_TCHAR(BoatTypeName(EBoatType(USailingSettings::Get()->BoatType))));
	}
	SetBoat(USailingSettings::Get()->BoatType);
	// -SailingHideBoat (stills): the player's boat and crew hidden, so the water's hull clip shows (docs/boat-water-clip/).
	static SailingArgs::FCachedFlag HideBoatArg(TEXT("SailingHideBoat"));
	if (HideBoatArg.Get()) SetActorHiddenInGame(true);

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

	bDemo = FParse::Param(SailingArgs::Dev(), TEXT("SailingDemo"));
	if (!bTrafficBoat && FParse::Param(SailingArgs::Dev(), TEXT("SailingCockpit"))) SetCockpitView(true);
	float HoldTwa = 0.f;
	if (bDemo)
	{
		bDemoTacks = !FParse::Value(SailingArgs::Dev(), TEXT("SailingHoldTWA="), HoldTwa);
		// Reset has not stepped the physics yet, so work out the starting tack from the wind and heading.
		const Vec3 W = GetWind().VelocityAt(Vec3(StartLocation.X / CmPerMeter, StartLocation.Y / CmPerMeter, 10.0), Boat.GetState().Time);
		DemoFirstSign = WrapAngle(std::atan2(-W.Y, -W.X) - FMath::DegreesToRadians(StartYaw)) >= 0.0 ? 1.0 : -1.0;
		DemoPilot.TargetTWADeg = bDemoTacks ? 45.0 * DemoFirstSign : HoldTwa * DemoFirstSign;
		DemoPilot.MaxTiller = 0.8;
		CameraYaw = bDemoTacks ? 150.f : 210.f;
		CameraPitch = -14.f;
		float CrudeAt = -1.f;
		if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingCrudeTackAt="), CrudeAt)) CrudeTackAt = CrudeAt;
	}
	if (!bTrafficBoat)
	{
		float PhotoSeconds = -1.f;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingPhoto="), PhotoSeconds)) PhotoAt = PhotoSeconds;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingPhotoCam="), PhotoCamArg, false);
	}
	// Benchmarks and screenshots: camera angle (degrees) and distance (meters), and a drill to start in.
	FParse::Value(SailingArgs::Dev(), TEXT("SailingCamYaw="), CameraYaw);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingCamPitch="), CameraPitch);
	float CamMeters = 0.f;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCamDist="), CamMeters))
	{
		CameraDistance = CamMeters * CmPerMeter;
		CameraBoom->TargetArmLength = CameraDistance;
	}
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	// Clean stills outside the capture mode (the blind tests' marina views): no HUD, no on-screen engine messages.
	if (!bTrafficBoat && FParse::Param(SailingArgs::Dev(), TEXT("SailingNoHud")))
	{
		USailingSettings::Get()->bShowHud = false;
		GAreScreenMessagesEnabled = false;
	}
	// Stills of the boat's details (crew, fittings): -SailingCamTarget=<forward>,<starboard>,<up> m in the boat frame is
	// what the camera turns about, instead of 3 m over the hull's origin.
	FString CamTarget;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCamTarget="), CamTarget, false))
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
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCapture="), CaptureArg))
	{
		CapturePreset = ParseCapturePreset(CaptureArg);
		SetupCapture();
		GAreScreenMessagesEnabled = false; // engine warnings (VSM overflow) would be burned into the still
	}
	FString DrillArg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingDrill="), DrillArg))
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
	if (FParse::Param(SailingArgs::Dev(), TEXT("SailingMenu"))) bMenuOpen = true; // screenshots of the settings menu
	if (FParse::Param(SailingArgs::Dev(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker(); // start with it up
}

void ASailboatPawn::ApplyDifficulty()
{
	// Easy mode is one switch (USailingSettings::IsEasy); what it does is the sim's (EasyAssists.h). Never on traffic boats
	// or the ghost: they sail as the boats are.
	const bool bEasy = !bTrafficBoat && !bGhost && USailingSettings::Get()->IsEasy();
	EasyAssists = FEasyAssists::For(Boat.GetConfig(), bEasy);
	EasyAssists.ApplyTo(Boat.GetMutableConfig(), Boat.TotalMass());
	EasyAssists.ApplyTo(TrimAssist.Settings);
	EasyHelm.Reset();
	// Prologue step 3: a scene's assisted limits (the maxi never capsizes or broaches in the mistral); never in normal
	// sailing, on traffic boats or the ghost.
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	FSceneLimits::For(!bTrafficBoat && !bGhost && GM && GM->GetScene()).ApplyTo(Boat.GetMutableConfig());
}

void ASailboatPawn::ResetBoat()
{
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		FLaunchSpot Spot;
		if (GM->GetLaunchSpot(Spot) && !FParse::Param(SailingArgs::Dev(), TEXT("SailingKeepStart")))
		{
			StartLocation = FVector(Spot.X, Spot.Y, 0.0) * CmPerMeter;
			StartYaw = Spot.HeadingDeg;
		}
	}
	float StartTwa = 0.f;
	const bool bTwaArg = FParse::Value(SailingArgs::Dev(), TEXT("SailingTWA="), StartTwa);
	if (bTwaArg)
	{
		StartYaw = GetWind().GetParams().FromDegrees - StartTwa; // recordings and benchmarks start on a set point of sail
	}
	// Prologue step 1: (re)start on the scene's checkpoint pose, the point of sail and speed the step starts from; a reset
	// while the scene runs takes it back to that checkpoint.
	double ResetSpeedKnots = StartSpeedKnots;
	if (ASailingGameMode* SceneGM = GetWorld()->GetAuthGameMode<ASailingGameMode>(); SceneGM && SceneGM->GetScene() && !bTrafficBoat && !bGhost)
	{
		double PoseTwa = 0.0, PoseKnots = 0.0;
		if (SceneGM->RestartScene(PoseTwa, PoseKnots) && !bTwaArg)
		{
			StartYaw = GetWind().GetParams().FromDegrees - PoseTwa;
			ResetSpeedKnots = PoseKnots;
		}
	}
	Boat.GetMooringLines().clear();
	// Soaks: -SailingMooring parks the player's boat on a buoy 12 m upwind of the start, head to wind with the sails up,
	// so the camera stays put (docs/budget/mac-soak-parked-2026-10-17.md).
	const bool bMooring = !bTrafficBoat && !bShowroomPose && FParse::Param(SailingArgs::Dev(), TEXT("SailingMooring"));
	if (bMooring) StartYaw = GetWind().GetParams().FromDegrees;
	if (bShowroomPose && !bTrafficBoat)
	{
		// The showroom (a boat swapped in, or moved off the slip): on its spot and heading.
		StartLocation = FVector(ShowroomSpot.X, ShowroomSpot.Y, 0.0) * CmPerMeter;
		StartYaw = ShowroomYaw;
	}
	// Keep the clock running through a reset: the weather, wind and waves all run on it.
	const double Time = Boat.GetState().Time;
	Boat.Reset(StartLocation.X / CmPerMeter, StartLocation.Y / CmPerMeter, FMath::DegreesToRadians(StartYaw), bMooring ? 0.0 : ResetSpeedKnots * kKnot);
	Boat.GetMutableState().Time = Time;
	if (bMooring)
	{
		const double Heading = FMath::DegreesToRadians(StartYaw);
		const double BowX = 0.45 * Boat.GetConfig().LengthOverall;
		FMooringLine Line;
		Line.BodyPoint = Vec3(BowX, 0.0, 0.5);
		Line.Anchor = Vec3(StartLocation.X / CmPerMeter + (BowX + 12.0) * FMath::Cos(Heading), StartLocation.Y / CmPerMeter + (BowX + 12.0) * FMath::Sin(Heading), 0.0);
		Line.Length = 12.0;
		Boat.GetMooringLines().push_back(Line);
	}
	Controls = FBoatControls();
	Controls.MainSheet = 0.45;
	Controls.JibSheet = 0.45;
	// -SailingSpinnaker: start with it up, whenever the boat is (re)started.
	if (!bTrafficBoat && FParse::Param(SailingArgs::Dev(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker();
	int32 ReefArg = 0;
	// A scene starts (and restarts) with its own sails: the maxi's gale reefs in the prologue.
	if (const ASailingGameMode* ReefGM = GetWorld()->GetAuthGameMode<ASailingGameMode>(); ReefGM && !bTrafficBoat && !bGhost && ReefGM->GetScene())
	{
		Controls.Reef = FMath::Clamp(ReefGM->GetSceneReefs(), 0, int32(Boat.GetConfig().ReefLuffFraction.size()));
	}
	if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingReef="), ReefArg))
	{
		Controls.Reef = FMath::Clamp(ReefArg, 0, int32(Boat.GetConfig().ReefLuffFraction.size()));
	}
	TrimAssist.Reset();
	// Prologue step 2: the crew start again from the reset boat (the scene's checkpoint moves the player as it re-enters).
	if (Stations.IsActive()) Stations.Reset(Boat, Controls, Stations.GetStation());
	KeyboardTiller = 0.f;
	// The sails start again from their shape too: cloth carried over a reset (a new spot, a new tack) can blow out.
	MainCloth.Reset();
	JibCloth.Reset();
	SpinCloth.Reset();
	ApplyStateToTransform();
	Plot.Start(GetMapPosition(), Time); // the departure is a known position
	if (!bTrafficBoat) BeginRun(TEXT("Sail"));
}

void ASailboatPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bKeysOpen) PollKeyCapture();
	if (PhotoAt >= 0.0 && !bTrafficBoat && !bPhoto && Boat.GetState().Time >= PhotoAt)
	{
		PhotoAt = -1.0;
		SetPhoto(true);
		TArray<FString> V;
		PhotoCamArg.ParseIntoArray(V, TEXT(","));
		if (FreeCam && V.Num() >= 3)
		{
			const FRotator Heading(0.f, GetActorRotation().Yaw, 0.f);
			const FVector At = GetActorLocation() + Heading.RotateVector(FVector(FCString::Atod(*V[0]), FCString::Atod(*V[1]), FCString::Atod(*V[2])) * 100.0);
			const FRotator Look = V.Num() >= 5 ? FRotator(FCString::Atof(*V[4]), Heading.Yaw + FCString::Atof(*V[3]), 0.f) : (CameraBoom->GetComponentLocation() - At).Rotation();
			FreeCam->PlaceAt(At, Look);
			if (APlayerController* PC = Cast<APlayerController>(GetController())) PC->SetViewTarget(FreeCam);
			UE_LOG(LogSailing, Display, TEXT("Photo camera at %.0f m from the boat, %.1f m up"), FreeCam->GetLeashDistanceM(),
				SailingFrame::ToMapCm(GetWorld(), FreeCam->GetActorLocation()).Z / 100.0);
		}
	}
	if (!bTrafficBoat && (bWatching || bPhoto))
	{
		// The boat holds still (photo mode holds the world clock too: ASailingGameMode::SetWorldHeld); only the replay
		// and the cameras move.
		if (bPhoto && FreeCam)
		{
			FFreeCameraInput In;
			In.Move = FVector2D(HeldAxes.FindRef(TEXT("PhotoRight")), HeldAxes.FindRef(TEXT("PhotoForward")));
			In.Vertical = HeldAxes.FindRef(TEXT("PhotoUpDown"));
			In.Roll = HeldAxes.FindRef(TEXT("PhotoRoll"));
			In.bBoost = HeldAxes.FindRef(TEXT("PhotoBoost")) > 0.5f;
			In.bSlow = HeldAxes.FindRef(TEXT("PhotoSlow")) > 0.5f;
			FreeCam->Update(DeltaSeconds, In);
			// The lens: [ and ] (the twin-engine pivot keys) zoom in and out.
			UCameraComponent* Lens = FreeCam->GetCamera();
			const float Zoom = HeldAxes.FindRef(TEXT("ThrottleSplit"));
			if (Zoom != 0.f) Lens->SetFieldOfView(FMath::Clamp(Lens->FieldOfView - Zoom * 30.f * DeltaSeconds, 10.f, 110.f));
			UpdatePhotoLens();
		}
		UpdateGhost(DeltaSeconds);
		return;
	}
	if (bTrafficBoat)
	{
		// The traffic simulation sails her; draw where she is, her rig and sails, and her lights.
		ApplyStateToTransform();
		// Held for photo mode, her sails hold their shape with her.
		const ASailingGameMode* HeldGM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
		if (!HeldGM || !HeldGM->IsWorldHeld()) UpdateRigVisuals(DeltaSeconds);
		UpdateNavLights();
		return;
	}
	// Settings > Field of view: the chase camera follows the row as it changes (photo mode keeps its lens, the capture
	// presets theirs, the cockpit sets its own each frame).
	if (!bCockpit && !IsCaptureMode() && Camera && Camera->FieldOfView != USailingSettings::Get()->ChaseFov()) Camera->SetFieldOfView(USailingSettings::Get()->ChaseFov());
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
		if (CrudeTackAt >= 0.0 && T >= CrudeTackAt)
		{
			// A beginner's tack: the tiller hard over toward the boom (bow toward the wind), then let go.
			if (CrudeTackSign == 0) CrudeTackSign = Boat.GetTelemetry().TrueWindAngle >= 0.0 ? 1 : -1;
			Controls.Tiller = T < CrudeTackAt + 4.0 ? double(CrudeTackSign) : 0.0;
		}
		if (T > 5.0) RunMaxHeelDeg = FMath::Max(RunMaxHeelDeg, FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg);
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
		if (ShowroomStage != EShowroomStage::None && !bTrafficBoat)
		{
			// The showroom: she sails through the water while the water carries her back, so she stays on her spot (the
			// current is minus her speed through it, plus a slow pull onto the spot).
			const Vec3 ThroughWater = Boat.GetState().Velocity - Boat.GetWaterCurrent();
			const Vec3 Pull((ShowroomSpot.X - O.X) * 0.3, (ShowroomSpot.Y - O.Y) * 0.3, 0.0);
			Boat.SetWaterCurrent(Pull - ThroughWater);
		}
		else
		{
			Boat.SetWaterCurrent(GameMode->GetCurrentAt(O.X, O.Y));
		}
	}
	// Online readiness (rule 3): the boat steps until it reaches the world clock, so every boat (and a second player's)
	// is on the same instant. Graphics G4: the front end and the loading screen hold the boat where it is while the world
	// keeps moving: its time is carried along with the clock instead. A boat more than a second off the clock (spawned,
	// reset or held) joins it where it is. Without a game mode (a bare test world) the boat keeps its own steps.
	int32 Steps = 0;
	if (ASailingGameMode* ClockMode = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		ClockMode->AdvanceClock(DeltaSeconds);
		const double Behind = ClockMode->GetSimTime() - Boat.GetState().Time;
		const bool bStill = bHeldByUI && !bTrafficBoat && ShowroomStage == EShowroomStage::None;
		if (bStill || FMath::Abs(Behind) > 1.0) Boat.GetMutableState().Time = ClockMode->GetSimTime();
		else Steps = FMath::Clamp(FMath::RoundToInt32(Behind / Stepper.GetStepDt()), 0, 12);
	}
	else if (!(bHeldByUI && !bTrafficBoat && ShowroomStage == EShowroomStage::None))
	{
		Steps = Stepper.Advance(DeltaSeconds);
	}
	if (ShowroomStage != EShowroomStage::None && !bTrafficBoat)
	{
		// The showroom's helm holds a close reach on her side, whatever the wind does.
		ShowroomPilot.TargetTWADeg = 70.0 * ShowroomSide;
		Controls.Tiller = ShowroomPilot.Update(Boat);
	}
	// Stowed in her slip (covered and furled, as drawn), the sails give no force (docs/dock-look/).
	Controls.bSailsDown = bSailsStowed && StowedDress && IsTiedUp();
	// Perf 1: the steps run on a task when they can (BoatPhysicsTask.h); the join tick (TG_PostPhysics) does the rest.
	FBoatStepJob Job;
	Job.Boat = &Boat;
	Job.Controls = &Controls;
	Job.Trim = &TrimAssist;
	Job.Wind = &Wind;
	Job.Waves = Waves;
	Job.Steps = Steps;
	Job.StepDt = Stepper.GetStepDt();
	Job.bTrimAssist = EasyAssists.bEnabled || USailingSettings::Get()->bTrimAssist; // IsTrimAssistActive, step by step
	Job.LastManualTrimTime = LastManualTrimTime;
	if (ShowroomStage != EShowroomStage::None && !bTrafficBoat)
	{
		Job.bTrimAssist = true; // the showroom trims her sails (the player's hands are on the menus)
		Job.LastManualTrimTime = -1e9;
	}
	Job.TrimIdleSeconds = EasyAssists.bEnabled ? EasyAssists.TrimIdleSeconds : kTrimAssistIdleSeconds;
	Job.bSimple = bSimple;
	Job.Easy = &EasyAssists;
	Job.EasyHelm = &EasyHelm;
	UpdateStations(Job.StationInput);
	if (Stations.IsActive())
	{
		Job.Stations = &Stations;
		if (Steps > 0) { GrindTaps = 0; bTravellerDumpPressed = false; } // handed to this frame's steps
	}
	{
		SAILING_PERF_SCOPE(BoatPhysics);
		if (PhysicsTask.Start(this, PhysicsJoinTick, Job)) return;
	}
	TickAfterPhysics(DeltaSeconds);
}

void ASailboatPawn::RegisterActorTickFunctions(bool bRegister)
{
	Super::RegisterActorTickFunctions(bRegister);
	FBoatPhysicsTask::RegisterJoin(this, PhysicsJoinTick, bRegister);
}

void ASailboatPawn::TickAfterPhysics(float DeltaSeconds)
{
	if (PhysicsTask.IsPending()) { SAILING_PERF_SCOPE(BoatPhysics); PhysicsTask.Wait(); }
	const ASailingGameMode* GameMode = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!bTrafficBoat && !bGhost) UpdateRun(DeltaSeconds);
	ApplyStateToTransform();
	UpdateRigVisuals(DeltaSeconds);
	if (IsCaptureMode() && !bTrafficBoat) { SAILING_PERF_SCOPE(BoatCapture); UpdateCapture(DeltaSeconds); }

	if (Water)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const Vec3 O = Boat.OriginPosition();
		Water->SetBoatForWake(FVector2D(O.X, O.Y), T.Heading, T.BoatSpeed, T.Heel);
	}
	{ SAILING_PERF_SCOPE(BoatSound); UpdateSound(DeltaSeconds); }
	if (bCockpit) UpdateCockpitCamera(DeltaSeconds);
	SAILING_PERF_SCOPE(BoatLearning); // the rest of the tick

	// Drills: follow the boat and the crew's actions.
	const FBoatTelemetry& Tel = Boat.GetTelemetry();
	if (Tel.bCollision) MaxContactKnots = FMath::Max(MaxContactKnots, Tel.BoatSpeed / kKnot);
	if (DrillRunner.IsActive())
	{
		FDrillContext Ctx;
		Ctx.bTiedUp = IsTiedUp();
		Ctx.bBackJib = Controls.bBackJib;
		Ctx.MaxContactSpeed = MaxContactKnots;
		DrillCollisions += Tel.bCollision && !bDrillTouching;
		bDrillEasy |= EasyAssists.bEnabled;
		bDrillTouching = Tel.bCollision;
		DrillRunner.Update(Boat, Ctx, DeltaSeconds);
		// Graphics G4: a passed drill is remembered for the front end ("6 drills, N passed").
		if (DrillRunner.IsComplete() && !bTrafficBoat && !bGhost)
		{
			USailSessionSave* Save = USailSessionSave::Get();
			const int32 Index = int32(DrillRunner.GetDrill()) - 1;
			if (Index >= 0 && !Save->DrillsPassed.Contains(Index)) Save->DrillsPassed.Add(Index);
			// Career 1: the lesson's medal, from the runner and what the boat counted (rule 8), then the save.
			if (!bDrillGraded)
			{
				bDrillGraded = true;
				CareerAward = SailCareer::RecordRun(MakeCareerRun(DrillRunner, MaxContactKnots, DrillCollisions, DrillInfractions,
					FSailSave::WorldId(USailingSettings::Get()->World), FSailSave::BoatId(int32(Boat.GetConfig().Type)), bDrillEasy));
				if (CareerAward.IsValid()) AddLogEvent(FString::Printf(TEXT("Lesson: %s, %s medal (%d:%02d)"), DrillName(DrillRunner.GetDrill()),
					*FCareerContent::MedalName(CareerAward.Medal), int32(CareerAward.Seconds) / 60, int32(CareerAward.Seconds) % 60));
			}
			Save->Commit();
		}
	}
	// Prologue step 1: the scripted scene follows this boat (the game mode owns it and judges it on the sim clock). The
	// crew-action button answers the call that asks for an action; step 2: the station merge reports the station and the
	// controls the player worked (UpdateStations).
	if (!bTrafficBoat && !bGhost)
	{
		if (ASailingGameMode* SceneGM = GetWorld()->GetAuthGameMode<ASailingGameMode>(); SceneGM && SceneGM->GetScene())
		{
			const Sailing::FScriptedScene& Scene = *SceneGM->GetScene();
			Sailing::FSceneInput In;
			In.Controls = Controls;
			In.Station = Stations.IsActive() ? Sailing::CrewStationName(Stations.GetStation()) : "helm";
			In.Worked = Stations.TakeWorked();
			const Sailing::FSceneStep* Step = Scene.GetStep();
			if (bCrewActionPressed && Step && Scene.GetPhase() == Sailing::FScriptedScene::EPhase::Calling && Step->Expect.Type == Sailing::ESceneExpect::Action)
			{
				In.Actions.push_back(Step->Expect.Action);
			}
			bCrewActionPressed = false;
			SceneGM->UpdateScene(Boat, In);
		}
	}
	UpdateDrillVisuals();
	if (!bTrafficBoat && !bGhost) UpdateLearning();

	// Screenshots and the gate: -SailingChart=<m per pixel> opens the chart, -SailingPlotFix takes three bearings.
	if (!bChartArgsApplied && Boat.GetState().Time > 2.0 && GameMode)
	{
		bChartArgsApplied = true;
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingPlotFix")))
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
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingChart="), ChartZoom) && GameMode->GetChart().IsLoaded())
		{
			SetChartOpen(true);
			ChartMetersPerPixel = ChartZoom;
			ChartCenter = GetMapPosition();
		}
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingNoGps"))) bShowGps = false;
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingLogOpen"))) bLogOpen = true;
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingKeys"))) { BuildKeyRows(); bKeysOpen = true; KeysMessage = TEXT("Up / Down choose, Enter then press the new key, Backspace restores the default, Tab closes"); }
	}

	// Scripted debrief checks: -SailingGhostAt=<s> resets then sails beside the ghost of the run so far;
	// -SailingWatchAt=<s> starts watching it. Dock stills (docs/dock-look/): -SailingCastOffAt=<s>[,<throttle>] casts off at
	// that sim time and holds the outboard there (-1 full astern .. 1 ahead; -0.4 by default, backing out of the slip).
	{
		static float GhostAt = -1.f, WatchAt = -1.f, CastOffAt = -1.f, CastOffThrottle = -0.4f;
		static bool bCastOff = false;
		static SailingArgs::FOnce Parsed;
		if (Parsed.Take())
		{
			GhostAt = WatchAt = CastOffAt = -1.f;
			CastOffThrottle = -0.4f;
			bCastOff = false;
			FParse::Value(SailingArgs::Dev(), TEXT("SailingGhostAt="), GhostAt);
			FParse::Value(SailingArgs::Dev(), TEXT("SailingWatchAt="), WatchAt);
			FString CastOffArg, AtStr, ThrottleStr;
			if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCastOffAt="), CastOffArg, false))
			{
				if (!CastOffArg.Split(TEXT(","), &AtStr, &ThrottleStr)) AtStr = CastOffArg;
				CastOffAt = FCString::Atof(*AtStr);
				if (!ThrottleStr.IsEmpty()) CastOffThrottle = FMath::Clamp(FCString::Atof(*ThrottleStr), -1.f, 1.f);
			}
		}
		if (CastOffAt > 0.f && Boat.GetState().Time >= CastOffAt)
		{
			CastOffAt = -1.f;
			if (IsTiedUp()) ToggleDockLines();
			bCastOff = true;
		}
		if (bCastOff) Controls.Throttle = CastOffThrottle;
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
		// The bake's own transverse Mercator, inverted (docs/geo-anchor): the logbook's position is the chart's.
		const Sailing::FLatLon Geo = SailingNav::LatLonAt(GM->GetLake().Anchor, P);
		E.Latitude = Geo.LatDeg;
		E.Longitude = Geo.LonDeg;
		E.HeadingMagnetic = SailingNav::TrueToMagnetic(GetHeadingTrueDeg(), GM->GetLake().VariationDeg);
		E.WindFromDeg = SailingNav::NormalizeDeg(GM->GetWeatherState().Wind.FromDegrees);
		E.WindKnots = T.TrueWindSpeed / kKnot;
		E.SeaMeters = GM->GetWaves().SignificantHeightAt(Boat.OriginPosition().X, Boat.OriginPosition().Y);
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
			{ TEXT("PhotoForward"), { TEXT("Photo: fly forward"), TEXT("Photo: fly back") } },
			{ TEXT("PhotoRight"), { TEXT("Photo: fly right"), TEXT("Photo: fly left") } },
			{ TEXT("PhotoUpDown"), { TEXT("Photo: fly up"), TEXT("Photo: fly down") } },
			{ TEXT("PhotoRoll"), { TEXT("Photo: tilt right"), TEXT("Photo: tilt left") } }, { TEXT("PhotoRollReset"), { TEXT("Photo: level the camera"), TEXT("") } },
			{ TEXT("PhotoBoost"), { TEXT("Photo: fast (hold)"), TEXT("") } }, { TEXT("PhotoSlow"), { TEXT("Photo: slow (hold)"), TEXT("") } },
			{ TEXT("PhotoSpeed"), { TEXT("Photo: faster"), TEXT("Photo: slower") } }, { TEXT("PhotoToBoat"), { TEXT("Photo: back to the boat"), TEXT("") } },
			{ TEXT("PhotoOrbit"), { TEXT("Photo: orbit the boat / fly"), TEXT("") } }, { TEXT("PhotoHideUI"), { TEXT("Photo: hide the hints"), TEXT("") } },
			{ TEXT("CockpitView"), { TEXT("Cockpit view (the helm's eyes)"), TEXT("") } },
			{ TEXT("ControlsCard"), { TEXT("Controls card"), TEXT("") } }, { TEXT("Menu"), { TEXT("Settings"), TEXT("") } },
			{ TEXT("CrewAction"), { TEXT("Crew station: answer the captain"), TEXT("") } }, { TEXT("Grind"), { TEXT("Crew station: grind the jib winch"), TEXT("") } },
			{ TEXT("TravellerDump"), { TEXT("Crew station: dump the traveller"), TEXT("") } }, { TEXT("Station"), { TEXT("Crew station: move to the next"), TEXT("") } },
		};
		if (const TPair<FString, FString>* N = Names.Find(Action.ToString())) return bNegative && !N->Value.IsEmpty() ? N->Value : N->Key;
		return Action.ToString();
	}
}

void ASailboatPawn::BuildKeyRows()
{
	KeyRows.Reset();
	// One row per command and direction, showing its first keyboard key and its gamepad button (or the stick or
	// trigger that drives it: those stay on their axes). Mouse axes are not rows.
	const TArray<FSailingKeyBinding>& Bindings = GetDefault<USailingInputSettings>()->GetBindings();
	for (const FSailingKeyBinding& B : Bindings)
	{
		if (!SailingBindings::IsKeyboardKey(B.Key)) continue;
		if (!SailingBindings::IsRowAction(B.Action)) continue; // arrow keys stay arrows
		const bool bNeg = B.Scale < 0.f;
		if (KeyRows.ContainsByPredicate([&](const FKeyRow& R) { return R.Action == B.Action && R.bNegative == bNeg; })) continue;
		FKeyRow Row;
		Row.Action = B.Action;
		Row.bNegative = bNeg;
		Row.Label = CommandLabel(B.Action, bNeg);
		Row.Key = B.Key;
		Row.PadKey = SailingBindings::Find(Bindings, B.Action, bNeg, SailingBindings::EColumn::Gamepad);
		Row.PadAxis = SailingBindings::FindPadAxis(Bindings, B.Action, bNeg);
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

bool ASailboatPawn::AssignKey(int32 Row, const FKey& Key)
{
	if (!KeyRows.IsValidIndex(Row)) return false;
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	if (Settings->Bindings.Num() == 0) Settings->Bindings = Settings->GetDefaults();
	const FKeyRow Target = KeyRows[Row];
	const FString KeyName = SailingBindings::KeyLabel(Key);
	// The keyboard key or gamepad button (the column follows the key). If another command had it, it takes this one's
	// old key (a swap, so nothing is left without a key): SailingBindings::Assign, the same rule for both columns.
	const SailingBindings::FAssignResult R = SailingBindings::Assign(Settings->Bindings, Target.Action, Target.bNegative, Key);
	if (R.bRefused)
	{
		KeysMessage = FString::Printf(TEXT("%s stays on %s: it is the only way to pause from the controller"), *KeyName, *CommandLabel(R.OtherAction, false));
		return false;
	}
	if (!R.bChanged)
	{
		if (R.Old == Key) KeysMessage = FString::Printf(TEXT("%s: %s"), *Target.Label, *KeyName);
		else KeysMessage = SailingBindings::IsPadAxis(Key) ? FString(TEXT("Sticks and triggers stay on their axes")) : FString::Printf(TEXT("%s can't be bound here"), *KeyName);
		return false;
	}
	if (!USailingSettings::IgnoresSavedChoices()) Settings->SaveConfig();
	RebuildMappings();
	BuildKeyRows();
	const FString Other = CommandLabel(R.OtherAction, R.bOtherNegative);
	KeysMessage = !R.bSwapped ? FString::Printf(TEXT("%s: %s"), *Target.Label, *KeyName)
		: R.Old.IsValid() ? FString::Printf(TEXT("%s: %s (swapped: %s now %s)"), *Target.Label, *KeyName, *Other, *SailingBindings::KeyLabel(R.Old))
		: FString::Printf(TEXT("%s: %s (%s has no button now)"), *Target.Label, *KeyName, *Other);
	return true;
}

void ASailboatPawn::ResetKeys()
{
	USailingInputSettings* Settings = GetMutableDefault<USailingInputSettings>();
	Settings->Bindings = Settings->GetDefaults();
	if (!USailingSettings::IgnoresSavedChoices()) Settings->SaveConfig();
	RebuildMappings();
	BuildKeyRows();
	KeysMessage = TEXT("Keys and buttons back to the defaults");
}

bool ASailboatPawn::Rebind(FName Action, bool bNegative, const FKey& Key)
{
	BuildKeyRows();
	const int32 Row = KeyRows.IndexOfByPredicate([&](const FKeyRow& R) { return R.Action == Action && R.bNegative == bNegative; });
	if (Row == INDEX_NONE) return false;
	return AssignKey(Row, Key);
}

// Bean's playtest (Oct 20): Esc opens the pause menu, as in most games (and the front end's Back closes it again). It is
// fixed, not one of the rebindable rows: a saved Input.ini keeps it, and the Controls screen's key capture still takes Esc
// as Cancel. Tab (the rebindable key) keeps working; the editor's play-in-editor stops on Esc before the game sees it.
void ASailboatPawn::MapFixedKeys(UInputMappingContext* Context, const TMap<FName, TObjectPtr<UInputAction>>& InActions)
{
	if (const TObjectPtr<UInputAction>* Menu = InActions.Find(TEXT("Menu")); Context && Menu && *Menu)
	{
		Context->MapKey(*Menu, EKeys::Escape).Triggers.Add(NewObject<UInputTriggerPressed>(Context));
	}
}

void ASailboatPawn::MakeActions(UObject* Outer, const TArray<FSailingKeyBinding>& Bindings, TMap<FName, TObjectPtr<UInputAction>>& InOutActions)
{
	for (const FSailingKeyBinding& Binding : Bindings)
	{
		TObjectPtr<UInputAction>& Action = InOutActions.FindOrAdd(Binding.Action);
		if (Action) continue;
		Action = NewObject<UInputAction>(Outer, *FString::Printf(TEXT("IA_%s"), *Binding.Action.ToString()));
		Action->ValueType = Binding.Action == NAME_Look ? EInputActionValueType::Axis2D
			: (IsButtonAction(Binding.Action) ? EInputActionValueType::Boolean : EInputActionValueType::Axis1D);
	}
}

UInputMappingContext* ASailboatPawn::BuildContext(UObject* Outer, FName Name, const TArray<FSailingKeyBinding>& Bindings,
	const TMap<FName, TObjectPtr<UInputAction>>& InActions, bool bPhotoContext)
{
	// A rebind builds new contexts while the old ones are still mapped: each gets a name of its own.
	UInputMappingContext* Context = NewObject<UInputMappingContext>(Outer, MakeUniqueObjectName(Outer, UInputMappingContext::StaticClass(), Name));
	// Photo mode's pad toggle is a half-second hold of its button (View): the controls card (and, in photo mode, the
	// orbit toggle) keep that button's tap. Every other button fires once, on the press.
	TSet<FKey> HoldKeys;
	for (const FSailingKeyBinding& B : Bindings) if (B.Action == TEXT("Photo") && B.Key.IsGamepadKey()) HoldKeys.Add(B.Key);
	for (const FSailingKeyBinding& Binding : Bindings)
	{
		if (!(bPhotoContext ? SailingBindings::InPhotoContext(Binding) : SailingBindings::InBoatContext(Binding))) continue;
		const TObjectPtr<UInputAction>* Action = InActions.Find(Binding.Action);
		if (!Action || !*Action) continue;
		FEnhancedActionKeyMapping& Mapping = Context->MapKey(*Action, Binding.Key);
		if (Binding.Scale < 0.f) Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(Context));
		if (FMath::Abs(Binding.Scale) != 1.f)
		{
			UInputModifierScalar* Scalar = NewObject<UInputModifierScalar>(Context);
			Scalar->Scalar = FVector(FMath::Abs(Binding.Scale));
			Mapping.Modifiers.Add(Scalar);
		}
		if (!IsButtonAction(Binding.Action)) continue;
		if (HoldKeys.Contains(Binding.Key) && Binding.Action == TEXT("Photo"))
		{
			UInputTriggerHold* Hold = NewObject<UInputTriggerHold>(Context);
			Hold->HoldTimeThreshold = 0.5f;
			Hold->bIsOneShot = true;
			Mapping.Triggers.Add(Hold);
		}
		else if (HoldKeys.Contains(Binding.Key))
		{
			UInputTriggerTap* Tap = NewObject<UInputTriggerTap>(Context);
			Tap->TapReleaseTimeThreshold = 0.5f;
			Mapping.Triggers.Add(Tap);
		}
		else
		{
			Mapping.Triggers.Add(NewObject<UInputTriggerPressed>(Context));
		}
	}
	if (!bPhotoContext) MapFixedKeys(Context, InActions);
	return Context;
}

void ASailboatPawn::ApplyMappingContexts()
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	UEnhancedInputLocalPlayerSubsystem* Subsystem = PC ? ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()) : nullptr;
	if (!Subsystem || !MappingContext) return;
	Subsystem->ClearAllMappings();
	Subsystem->AddMappingContext(MappingContext, 0);
	if (bPhoto && PhotoContext) Subsystem->AddMappingContext(PhotoContext, PhotoContextPriority);
}

void ASailboatPawn::RebuildMappings()
{
	// The same actions (bound to the same handlers), mapped to the new keys.
	const TArray<FSailingKeyBinding>& Bindings = GetDefault<USailingInputSettings>()->GetBindings();
	MappingContext = BuildContext(this, TEXT("IMC_Sailboat_Rebound"), Bindings, Actions, false);
	PhotoContext = BuildContext(this, TEXT("IMC_Photo_Rebound"), Bindings, Actions, true);
	ApplyMappingContexts();
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
		if (bPhoto) SetPhoto(false);
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
		if (Crew.Num() > 0 && Crew.Last())
		{
			Crew.Last()->SetVisibility(true, true);
			Crew.Last()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPose;
		}
		Camera->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator::ZeroRotator);
		Camera->SetFieldOfView(USailingSettings::Get()->ChaseFov());
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
	FVector Eye = FVector(X, Side * FMath::Max(Rail - 0.3, 0.25), Sheer + 0.85) * CmPerMeter;
	// Better, the helm's own head where the crew model put it (the eyes about 10 cm ahead of the head bone and 8 cm above
	// it): the guess above sat inside the trimmer on the wheel boats and the Hobie (docs/cockpit-eye/).
	USkeletalMeshComponent* Helm = Crew.Num() > 0 ? Crew.Last().Get() : nullptr;
	if (Helm && Helm->GetBoneIndex(TEXT("head")) != INDEX_NONE)
	{
		Eye = BoatRoot->GetComponentTransform().InverseTransformPositionNoScale(Helm->GetBoneLocation(TEXT("head"))) + FVector(10.f, 0.f, 8.f);
	}

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
	// You are the helm: the helm's own figure is not drawn from inside it, but still posed (its head is the eye).
	if (Helm)
	{
		Helm->SetVisibility(false, true);
		Helm->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	}
	const float Pitch = FMath::Clamp(CameraPitch, -45.f, 30.f) + 0.3f * float(FMath::RadiansToDegrees(Boat.GetTelemetry().Pitch));
	Camera->SetWorldLocationAndRotation(World, FRotator(Pitch, Yaw, -CockpitRoll * Side));
	Camera->SetFieldOfView(USailingSettings::Get()->ChaseFov() - 10.f);   // Settings > Field of view, 10 deg narrower aboard
}

void ASailboatPawn::UpdatePhotoLens()
{
	// Photo mode is a camera: focus on the boat at f/2.8 on a full-frame sensor (the background softens with the lens),
	// and the lens profile from Visual V1 (barrel distortion, vignetting and fringing, M_LensDistortion).
	if (!FreeCam) return;
	UCameraComponent* Lens = FreeCam->GetCamera();
	FPostProcessSettings& PP = Lens->PostProcessSettings;
	PP.bOverride_DepthOfFieldFocalDistance = PP.bOverride_DepthOfFieldFstop = PP.bOverride_DepthOfFieldSensorWidth = true;
	PP.DepthOfFieldFocalDistance = float(FVector::Dist(Lens->GetComponentLocation(), BoatRoot->GetComponentLocation()));
	PP.DepthOfFieldFstop = 2.8f;
	PP.DepthOfFieldSensorWidth = 36.f;
	if (LensDistortionAsset && !PP.WeightedBlendables.Array.ContainsByPredicate([&](const FWeightedBlendable& B) { return B.Object == LensDistortionAsset; }))
	{
		PP.AddBlendable(LensDistortionAsset, 1.f);
	}
}

void ASailboatPawn::SetPhoto(bool bOn)
{
	if (bOn == bPhoto) return;
	if (bOn && bWatching) SetWatching(false);
	bPhoto = bOn;
	APlayerController* PC = Cast<APlayerController>(GetController());
	// Online readiness rule 9: the hold is the game mode's single switch, so the traffic, the weather, the tide and the
	// water's time stop with the boat (before, only the boat stopped: it returns early from Tick in photo mode).
	if (ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>()) GM->SetWorldHeld(bOn);
	HeldAxes.Reset(); // the two contexts' keys overlap: nothing held carries across
	if (bOn)
	{
		// docs/photo-freefly/: a free camera (AFreeCamera) where the chase camera is, the same lens and grade; the view
		// blends over to it, so it opens without a jump. Its leash and orbit are about the boat.
		if (EnsureFreeCamera())
		{
			FreeCam->Limits = FFreeCameraLimits();
			FreeCam->SetAnchor(this, CameraBoom->GetComponentLocation() - GetActorLocation());
			FreeCam->SetMode(EFreeCameraMode::Fly);
			FreeCam->SnapTo(Camera->GetComponentLocation(), Camera->GetComponentRotation());
			UCameraComponent* Lens = FreeCam->GetCamera();
			Lens->PostProcessSettings = Camera->PostProcessSettings;
			Lens->PostProcessBlendWeight = Camera->PostProcessBlendWeight;
			Lens->SetFieldOfView(Camera->FieldOfView);
			UpdatePhotoLens();
			if (PC) PC->SetViewTargetWithBlend(FreeCam, 0.3f);
		}
		PhotoHintUntil = FPlatformTime::Seconds() + 5.0;
		PhotoReadoutUntil = PhotoHintUntil;
	}
	else if (PC)
	{
		// Back on the chase camera (untouched while flying), the boat where she was.
		PC->SetViewTargetWithBlend(this, 0.3f);
	}
	ApplyMappingContexts();
}

AFreeCamera* ASailboatPawn::EnsureFreeCamera()
{
	if (!FreeCam)
	{
		FActorSpawnParameters Params;
		Params.ObjectFlags |= RF_Transient;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		FreeCam = GetWorld()->SpawnActor<AFreeCamera>(Camera->GetComponentLocation(), Camera->GetComponentRotation(), Params);
	}
	return FreeCam;
}

void ASailboatPawn::SetShowroomStage(EShowroomStage Stage, bool bRelocate)
{
	if (bTrafficBoat || bGhost) return;
	const EShowroomStage Prev = ShowroomStage;
	if (Stage == Prev)
	{
		return;
	}
	ShowroomStage = Stage;
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (Stage == EShowroomStage::None)
	{
		// Back on the chase camera, the boat held still where she is.
		bShowroomPose = false;
		if (PC && FreeCam && PC->GetViewTarget() == FreeCam) PC->SetViewTargetWithBlend(this, 0.6f, VTBlend_EaseInOut, 2.f);
		return;
	}
	if (Prev == EShowroomStage::None)
	{
		// Her spot: where she is, or (in the front end) open water near it when she is in her slip or close to the shore.
		const Vec3 O = Boat.OriginPosition();
		ShowroomSpot = FVector2D(O.X, O.Y);
		const double Twa = Boat.GetTelemetry().TrueWindAngle;
		ShowroomSide = Twa < 0.0 ? -1.0 : 1.0;
		ShowroomYaw = float(GetActorRotation().Yaw);
		const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
		if (bRelocate && GM && GM->GetLake().IsLoaded())
		{
			const Sailing::FLakeTerrain& Terrain = GM->GetLake().Terrain;
			const FVector2D Open = SailShowroom::FindOpenWater([&Terrain](double X, double Y) { return Terrain.HeightAt(X, Y); }, O.X, O.Y);
			if (IsTiedUp() || !Open.Equals(ShowroomSpot, 0.5))
			{
				ShowroomSpot = Open;
				ShowroomYaw = float(GetWind().GetParams().FromDegrees - 70.0 * ShowroomSide);
				bShowroomPose = true;
				ResetBoat();
				UE_LOG(LogSailing, Display, TEXT("Showroom: moved to open water at (%.0f, %.0f)"), ShowroomSpot.X, ShowroomSpot.Y);
			}
		}
		ShowroomPilot = Sailing::FAutopilot();
		ShowroomPilot.MaxTiller = 0.6;
		if (EnsureFreeCamera())
		{
			FreeCam->Limits = FFreeCameraLimits();
			FreeCam->Limits.WaterClearM = 0.5; // the showroom's floor: half a metre over the waves
			FreeCam->GetCamera()->PostProcessSettings = Camera->PostProcessSettings;
			FreeCam->GetCamera()->SetFieldOfView(Camera->FieldOfView);
			FreeCam->SnapTo(Camera->GetComponentLocation(), Camera->GetComponentRotation());
			ApplyShowroomFraming(false);
			if (PC) PC->SetViewTargetWithBlend(FreeCam, 0.6f, VTBlend_EaseInOut, 2.f);
		}
		return;
	}
	ApplyShowroomFraming(false);
}

void ASailboatPawn::ApplyShowroomFraming(bool bKeepYaw)
{
	if (!FreeCam || ShowroomStage == EShowroomStage::None) return;
	// Inputs/ui-showroom/brief.md section 3: the showroom orbits the rig at 0.4 of its height from about 2.4 lengths (9 to
	// 40 m, zoom 0.6x to 1.6x), 3 to 35 deg above the water, from the starboard quarter, turning slowly when left alone;
	// the weather framing stands off about 4 lengths, higher, with the boat to the right of the panel and more sky.
	const FBoatConfig& C = Boat.GetConfig();
	FreeCam->SetAnchor(this, FVector(0.f, 0.f, float(C.MastheadZ) * 0.4f * CmPerMeter));
	const float Heading = float(GetActorRotation().Yaw);
	FFreeCameraOrbit O;
	O.EaseSeconds = 0.6f;
	if (ShowroomStage == EShowroomStage::Boat)
	{
		const float D = FMath::Clamp(float(C.LengthOverall) * 2.4f, 9.f, 40.f) * CmPerMeter;
		O.DistanceCm = D;
		O.MinDistanceCm = 0.6f * D;
		O.MaxDistanceCm = 1.6f * D;
		O.PitchDeg = -12.f;
		O.MinPitchDeg = -35.f;
		O.MaxPitchDeg = -3.f;
		O.YawDeg = Heading + 135.f + 180.f; // the camera on her starboard quarter, looking at her
		O.SpinDegPerSec = 6.f;
		O.SpinIdleSeconds = 4.f;
	}
	else
	{
		const float D = FMath::Clamp(float(C.LengthOverall) * 4.f, 20.f, 90.f) * CmPerMeter;
		O.DistanceCm = D;
		O.MinDistanceCm = 0.7f * D;
		O.MaxDistanceCm = 1.5f * D;
		O.PitchDeg = -4.f;
		O.MinPitchDeg = -20.f;
		O.MaxPitchDeg = 10.f;
		O.YawDeg = Heading + 120.f + 180.f;
		O.LateralOffsetCm = -0.3f * D; // the pivot left of the view: the boat sits right of the panel
		O.UpOffsetCm = 0.12f * D;      // and the sky takes more of the frame
	}
	if (bKeepYaw && FreeCam->GetMode() == EFreeCameraMode::Orbit) O.YawDeg = float(FreeCam->GetActorRotation().Yaw);
	FreeCam->SetOrbit(O);
}

void ASailboatPawn::ShowBoat(int32 Type)
{
	Type = FMath::Clamp(Type, 0, int32(EBoatType::Count) - 1);
	if (ShowroomLoad.IsValid() && ShowroomLoadType == Type) return;
	if (ShowroomLoad.IsValid()) { ShowroomLoad->CancelHandle(); ShowroomLoad.Reset(); }
	if (Type == GetBoatTypeIndex()) return;
	ShowroomLoadType = Type;
	ShowroomLoadStart = FPlatformTime::Seconds();
	// Inputs/ui-showroom/brief.md section 5: her meshes load off the game thread, then she is built in place.
	const TArray<FSoftObjectPath> Paths = ModelAssetPaths(EBoatType(Type));
	if (Paths.Num() > 0) ShowroomLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(Paths, FStreamableDelegate::CreateUObject(this, &ASailboatPawn::FinishShowroomSwap));
	if (!ShowroomLoad.IsValid() || ShowroomLoad->HasLoadCompleted()) FinishShowroomSwap();
}

void ASailboatPawn::FinishShowroomSwap()
{
	if (ShowroomLoadType < 0) return;
	const int32 Type = ShowroomLoadType;
	ShowroomLoadType = -1;
	const double Loaded = FPlatformTime::Seconds();
	// In place: where she is now, on her heading (or the showroom's spot when she is on a stage).
	if (!bShowroomPose)
	{
		const Vec3 O = Boat.OriginPosition();
		ShowroomSpot = FVector2D(O.X, O.Y);
		ShowroomYaw = float(GetActorRotation().Yaw);
	}
	const bool bWasPose = bShowroomPose;
	bShowroomPose = true;
	SetBoat(Type);
	bShowroomPose = bWasPose && ShowroomStage != EShowroomStage::None;
	const double Built = FPlatformTime::Seconds();
	// The shown boat's meshes stay resident; the one before is let go.
	ShowroomResident = ShowroomLoad;
	ShowroomLoad.Reset();
	ApplyShowroomFraming(true);
	UE_LOG(LogSailing, Display, TEXT("Showroom swap %hs: load %.0f ms, build %.0f ms"), Boat.GetConfig().Name,
		(Loaded - ShowroomLoadStart) * 1000.0, (Built - Loaded) * 1000.0);
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
		if (!bTrafficBoat && FParse::Param(SailingArgs::Dev(), TEXT("SailingSpinnaker"))) Controls.bSpinnaker = Boat.GetConfig().HasSpinnaker();
		ApplyStateToTransform();
	}
	MaxContactKnots = 0.0;
	DrillCollisions = DrillInfractions = 0;
	bDrillTouching = bDrillGraded = false;
	bDrillEasy = EasyAssists.bEnabled;
	CareerAward = FCareerProgress::FAward();
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
		// A squall line in a gale (the mistral's) is no thunderstorm: no storm or lightning tips (the scene's captain
		// has the squall).
		F.Storm = W.bSquall ? EStormPhase::None : W.Storm;
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
		if (bShow) MarkMeshes[I]->SetWorldLocation(SailingFrame::ToWorld(GetWorld(), Marks[I].X, Marks[I].Y, 0.0) + FVector(0.0, 0.0, WaterSurfaceZ + 60.f));
	}
	const bool bDummy = DrillRunner.IsActive() && DrillRunner.HasDummy();
	DummyMesh->SetVisibility(bDummy);
	if (bDummy) DummyMesh->SetWorldLocation(SailingFrame::ToWorld(GetWorld(), DrillRunner.GetDummy().X, DrillRunner.GetDummy().Y, 0.0) + FVector(0.0, 0.0, WaterSurfaceZ + 10.f));
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

void ASailboatPawn::UpdateRun(float DeltaSeconds)
{
	// World streaming, measuring (docs/world-streaming): -SailingRun=<m/s>,<bearing deg>[,<turn after m>] slides the world
	// under the boat: she sails as she would (her velocity, and so the water and the apparent wind, are her own) while her
	// position runs on along the bearing, out and back every <turn after> metres. The streaming bench and soak cross tiles
	// and re-centres in seconds this way. She leaves the terrain and its obstacles behind (no grounding on the way).
	static uint32 Gen = MAX_uint32;
	static double Speed = 0.0, Bearing = 0.0, TurnAfter = 0.0;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		Speed = 0.0;
		FString Arg;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingRun="), Arg, false))
		{
			TArray<FString> P;
			Arg.ParseIntoArray(P, TEXT(","));
			Speed = P.Num() > 0 ? FCString::Atod(*P[0]) : 0.0;
			Bearing = P.Num() > 1 ? FCString::Atod(*P[1]) : 0.0;
			TurnAfter = P.Num() > 2 ? FCString::Atod(*P[2]) : 0.0;
		}
	}
	if (Speed <= 0.0 || DeltaSeconds <= 0.f) return;
	if (!bRunning)
	{
		bRunning = true;
		Boat.SetTerrain(nullptr);
		Boat.SetObstacles(nullptr);
	}
	const double Step = Speed * DeltaSeconds;
	RunTravelled += Step;
	if (TurnAfter > 0.0 && RunTravelled >= TurnAfter) { RunTravelled = 0.0; RunSign = -RunSign; }
	const double A = FMath::DegreesToRadians(Bearing);
	FBoatState& S = Boat.GetMutableState();
	S.Position.X += RunSign * Step * FMath::Cos(A);
	S.Position.Y += RunSign * Step * FMath::Sin(A);
}

void ASailboatPawn::ApplyStateToTransform()
{
	const Vec3 Origin = Boat.OriginPosition();
	const Quat& Q = Boat.GetState().Orientation;
	// World streaming: the physics is in the map frame (doubles), the actor in the render frame (SailingFrame.h).
	SetActorLocationAndRotation(SailingFrame::ToWorld(GetWorld(), Origin.X, Origin.Y, Origin.Z) + FVector(0.0, 0.0, WaterSurfaceZ), FQuat(Q.X, Q.Y, Q.Z, Q.W));
}

void ASailboatPawn::UpdateRigVisuals(float DeltaSeconds)
{
	SAILING_PERF_SCOPE(BoatVisuals);
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
	// (Rig clearance: turned as the main's foot was last frame to keep it off the shrouds, FSailCloth::GetFootTurn.)
	BoomPivot->SetRelativeRotation(FRotator(0.f, bStowed ? 0.f : -FMath::RadiansToDegrees(S.BoomAngle) + FMath::RadiansToDegrees(MainCloth.GetFootTurn()), 0.f));
	for (USceneComponent* Pivot : RudderPivots) Pivot->SetRelativeRotation(FRotator(0.f, -FMath::RadiansToDegrees(S.RudderAngle), 0.f));
	// The fly points into the apparent wind (where it comes from).
	MastheadFly->SetRelativeRotation(FRotator(0.f, FMath::RadiansToDegrees(T.ApparentWindAngle), 0.f));

	const FBoatConfig& Cfg = Boat.GetConfig();
	{ SAILING_PERF_SCOPE(Crew); UpdateCrewFigures(DeltaSeconds); UpdateCrewFalls(DeltaSeconds); UpdateCrewGroomLOD(); }

	if (ModelHull)
	{
		SAILING_PERF_SCOPE(RigLines);
		UpdateModelRig(DeltaSeconds);
	}
	// Probes: -SailingSailsDown with -SailingMooring strikes the player's sails: no cloth stepped or drawn, while the
	// physics, boom and hull ride the mooring as before (docs/budget/perf-sun-setters-2026-10-17.md, the parked VSM lead).
	static SailingArgs::FCachedFlag SailsDownArg(TEXT("SailingSailsDown"));
	const bool bSailsDown = !bTrafficBoat && !Boat.GetMooringLines().empty() && SailsDownArg.Get();
	if (bSailsDown)
	{
		MainSail->SetVisibility(false);
		JibSail->SetVisibility(false);
		if (TelltaleRibbons) TelltaleRibbons->SetVisibility(false);
	}
	if (bStowed || bSailsDown)
	{
		SpinSail->SetVisibility(false);
		if (ModelHull) UpdateBoatWetness(DeltaSeconds);
		return;
	}
	SAILING_PERF_SCOPE_BEGIN(Sails);
	// A reef changes the main's planform: rebuild its cloth.
	const double MainHead = Cfg.Main.NumStrips > 0 ? Cfg.Main.Strips[Cfg.Main.NumStrips - 1].ZTop : -1.0;
	if (MainHead != ClothMainHeadZ)
	{
		MainCloth.Init(Cfg.Main, ESailKind::Main);
		ClothMainHeadZ = MainHead;
		MainSail->ClearAllMeshSections();
	}
	// docs/sail-parallel/: the sails step side by side (UpdateSailCloths).
	TArray<FSailUpdate, TInlineAllocator<3>> SailUpdates;
	SailUpdates.Add({ MainSail, &MainCloth, T.MainStrips, S.MainSide });
	if (Cfg.HasJib()) SailUpdates.Add({ JibSail, &JibCloth, T.JibStrips, S.JibSide });
	SpinSail->SetVisibility(T.NumSpinStrips > 0);
	if (T.NumSpinStrips > 0) SailUpdates.Add({ SpinSail, &SpinCloth, T.SpinStrips, S.SpinSide });
	UpdateSailCloths(SailUpdates, DeltaSeconds);
	if (Cfg.HasJib()) JibClewCm = JibCloth.PointAt(1.f, 0.f); // where the jib sheets lead from
	SAILING_PERF_SCOPE_END(Sails);
	{ SAILING_PERF_SCOPE(Telltales); UpdateTelltaleRibbons(); }
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

void ASailboatPawn::UpdateStations(FStationInput& Out)
{
	// Prologue step 2: crew-station mode while a scene runs (never on traffic boats or the ghost); normal sailing otherwise.
	Out = FStationInput();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FScriptedScene* Scene = GM && !bTrafficBoat && !bGhost ? GM->GetScene() : nullptr;
	if (!Scene)
	{
		if (Stations.IsActive()) Stations.Reset(Boat, Controls, ECrewStation::None);
		return;
	}
	if (!Stations.IsActive())
	{
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		Stations.Reset(Boat, Controls, ECrewStation::JibTrimmer); // a new hand starts on the jib
		SceneStationSerial = 0;
	}
	if (Scene->GetStationSerial() != SceneStationSerial)
	{
		SceneStationSerial = Scene->GetStationSerial();
		Stations.MoveTo(Boat, CrewStationFromName(Scene->GetStation()));
	}
	if (bStationKeyPressed)
	{
		bStationKeyPressed = false;
		Stations.MoveTo(Boat, NextCrewStation(Stations.GetStation()));
	}
	auto Held = [this](FName Action)
	{
		const float* V = bMenuOpen ? nullptr : HeldAxes.Find(Action);
		return V ? double(*V) : 0.0;
	};
	Out.Wheel = Held(NAME_Tiller);
	Out.JibSheet = Held(NAME_JibSheet);
	Out.Grind = Held(TEXT("Grind"));
	Out.GrindTaps = GrindTaps;
	Out.MainSheet = Held(NAME_MainSheet);
	Out.Traveller = Held(NAME_Traveler);
	Out.bTravellerDump = bTravellerDumpPressed;
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
	// Prologue step 2: at a crew station the hands go to the station merge (UpdateStations), not straight to the controls.
	if (Stations.IsActive()) return;
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
	const float V = Value.Get<float>();
	HeldAxes.FindOrAdd(Action) = V;
	if (Action == TEXT("PhotoSpeed") && FreeCam && bPhoto && FMath::Abs(V) > 0.5f && FPlatformTime::Seconds() >= NextPhotoSpeedStep)
	{
		// The wheel (or the D-pad, held) steps the base speed; in orbit, the distance.
		FreeCam->StepSpeed(V > 0.f ? 1 : -1);
		NextPhotoSpeedStep = FPlatformTime::Seconds() + 0.15;
		PhotoReadoutUntil = FPlatformTime::Seconds() + 2.0;
	}
}

void ASailboatPawn::OnAxisReleased(const FInputActionValue& Value, FName Action)
{
	HeldAxes.FindOrAdd(Action) = 0.f;
}

void ASailboatPawn::OnLook(const FInputActionValue& Value)
{
	// Ignore the camera in scripted runs, and clamp single events: capturing the mouse at launch can deliver one huge jump.
	float BenchSeconds = 0.f;
	if (bDemo || FParse::Value(SailingArgs::Dev(), TEXT("SailingBench="), BenchSeconds))
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
		if (FreeCam) FreeCam->AddLook(Delta);
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
	if (bPhoto) return; // the wheel is photo mode's speed (PhotoSpeed, in its own context)
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
		else if (Action == TEXT("Menu")) SetPhoto(false); // Esc (or the pad's Menu) leaves photo mode
		else if (Action == TEXT("PhotoToBoat") && FreeCam) FreeCam->SnapTo(Camera->GetComponentLocation(), Camera->GetComponentRotation());
		else if (Action == TEXT("PhotoOrbit") && FreeCam)
		{
			FreeCam->SetMode(FreeCam->GetMode() == EFreeCameraMode::Orbit ? EFreeCameraMode::Fly : EFreeCameraMode::Orbit);
			PhotoReadoutUntil = FPlatformTime::Seconds() + 2.0;
		}
		else if (Action == TEXT("PhotoRollReset") && FreeCam) FreeCam->ResetRoll();
		else if (Action == TEXT("PhotoHideUI")) bPhotoHideHints = !bPhotoHideHints;
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
	if (Stations.IsActive())
	{
		// Prologue step 2: the station layer's buttons; the crew hold the boat's other commands (their keys are shared).
		if (Action == TEXT("Grind")) { ++GrindTaps; return; }
		if (Action == TEXT("TravellerDump")) { bTravellerDumpPressed = true; return; }
		if (Action == TEXT("Station")) { bStationKeyPressed = true; return; }
		if (Action == TEXT("WingOnWing") || Action == TEXT("ToggleLearning") || Action == TEXT("ToggleDifficulty") || Action == TEXT("DockLines")
			|| Action == TEXT("Spinnaker") || Action == TEXT("Reef") || Action == TEXT("Board") || Action == TEXT("Righting")
			|| Action == TEXT("EngineNeutral") || Action == TEXT("BackJib")) return;
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
	else if (Action == TEXT("CrewAction"))
	{
		bCrewActionPressed = true;   // the scene reads it after this frame's physics (TickAfterPhysics)
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

	// Actions and the mapping contexts are built from USailingInputSettings (Input.ini), so keys can be rebound
	// without editing assets.
	const TArray<FSailingKeyBinding>& Bindings = GetDefault<USailingInputSettings>()->GetBindings();
	MakeActions(this, Bindings, Actions);
	MappingContext = BuildContext(this, TEXT("IMC_Sailboat"), Bindings, Actions, false);
	PhotoContext = BuildContext(this, TEXT("IMC_Photo"), Bindings, Actions, true);
}

void ASailboatPawn::PawnClientRestart()
{
	Super::PawnClientRestart();
	CreateInput();
	ApplyMappingContexts();
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
			// Each mapping's trigger decides when (BuildContext: the press, a hold or a tap).
			Input->BindAction(Action, ETriggerEvent::Triggered, this, &ASailboatPawn::OnButton, Name);
		}
		else
		{
			Input->BindAction(Action, ETriggerEvent::Triggered, this, &ASailboatPawn::OnAxis, Name);
			Input->BindAction(Action, ETriggerEvent::Completed, this, &ASailboatPawn::OnAxisReleased, Name);
			// The grinder is held (an axis) and tapped (each press is half a turn of the handle).
			if (Name == TEXT("Grind")) Input->BindAction(Action, ETriggerEvent::Started, this, &ASailboatPawn::OnButton, Name);
		}
	}
}

void ASailboatPawn::SetupCapture()
{
	if (CapturePreset == ECapturePreset::None || bTrafficBoat) return;
	const FCapturePresetInfo& Info = CapturePresetInfo(CapturePreset);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingCaptureBearing="), CaptureBearing);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingEV="), CaptureEV);
	if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingShot="), CaptureName)) CaptureName = TEXT("capture");

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
		// Better, the helm's own head where the crew model put it, as the cockpit view does (eyes 10 cm ahead of the head
		// bone, 8 cm above): the mount's guess from the crew's centre stood over the hero J/22's companionway, the view
		// forward half filled by the dark cabin below.
		USkeletalMeshComponent* HelmFigure = Crew.Num() > 0 ? Crew.Last().Get() : nullptr;
		if (HelmFigure && HelmFigure->GetBoneIndex(TEXT("head")) != INDEX_NONE)
		{
			// (Hidden below, as the camera is in its head: still posed, so the head bone moves with the helm.)
			HelmFigure->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			Location = BoatRoot->GetComponentTransform().InverseTransformPositionNoScale(HelmFigure->GetBoneLocation(TEXT("head"))) + FVector(10.f, 0.f, 8.f);
		}
		CaptureCamera->SetRelativeLocationAndRotation(Location, Rotation);
		// We are the helmsman: hide the crew figures beside us (the camera is in one's head and the simple figures
		// would fill a phone's frame); those further forward stay in view, as in the reference clips.
		if (CapturePreset == ECapturePreset::HelmEye)
		{
			for (UPrimitiveComponent* Figure : Crew)
			{
				// With the figure's children (face, clothes, gear, hair), as the cockpit view hides the helm: the strand hair
				// round the camera alone cost 1.1 ms of GPU on High (perf-2).
				// The helm's own figure always (the eye is in its head, docs/helm-eye/): its origin is the boat's, so the
				// distance alone left its legs and tiller arm across the view.
				if (Figure) Figure->SetVisibility(Figure != Crew.Last() && FVector::Dist(Figure->GetComponentLocation(), CaptureCamera->GetComponentLocation()) > 2.2f * CmPerMeter, true);
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
		if (!FMath::IsNaN(CaptureBearing) && !bCaptureBearingResolved && FParse::Param(SailingArgs::Dev(), TEXT("SailingCaptureAbsolute")))
		{
			CaptureBearing = FMath::UnwindDegrees(CaptureBearing - float(FMath::RadiansToDegrees(T.Heading)));
		}
		bCaptureBearingResolved = true;
		const float Bearing = FMath::IsNaN(CaptureBearing) ? -90.f : CaptureBearing;
		const Vec3 O = Boat.OriginPosition();
		const FVector Origin = SailingFrame::ToWorld(GetWorld(), O.X, O.Y, 0.0);
		const float Heading = float(FMath::RadiansToDegrees(T.Heading));
		FVector Location;
		FRotator Rotation;
		WorldCameraPose(CapturePreset, Origin, Heading, Bearing, float(Boat.GetConfig().MastheadZ), WaterSurfaceZ, Location, Rotation);
		if (CapturePreset == ECapturePreset::ShoreTele)
		{
			// A tripod: it stays where it was set up and only pans.
			// (Kept in the map frame: a re-centre moves the render frame under it.)
			if (!bShoreStandSet && !FMath::IsNaN(CaptureBearing)) { ShoreStand = SailingFrame::ToMapCm(GetWorld(), Location); bShoreStandSet = true; }
			if (bShoreStandSet)
			{
				const FVector Aim(Origin.X, Origin.Y, WaterSurfaceZ + 0.33f * float(Boat.GetConfig().MastheadZ) * CmPerMeter);
				Location = SailingFrame::FromMapCm(GetWorld(), ShoreStand);
				Rotation = (Aim - Location).Rotation();
			}
		}
		// Measuring the sky: -SailingCamWorld=<north m>,<east m>,<up m>,<heading deg>,<pitch deg> fixes the camera in the
		// world, relative to the boat's start (the weather's origin).
		FString CamWorld;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCamWorld="), CamWorld, false))
		{
			TArray<FString> P;
			CamWorld.ParseIntoArray(P, TEXT(","));
			if (P.Num() >= 5)
			{
				Location = SailingFrame::FromMapCm(GetWorld(), StartLocation) + FVector(FCString::Atof(*P[0]), FCString::Atof(*P[1]), FCString::Atof(*P[2])) * CmPerMeter;
				Location.Z = WaterSurfaceZ + FCString::Atof(*P[2]) * CmPerMeter;
				Rotation = FRotator(FCString::Atof(*P[4]), FCString::Atof(*P[3]), 0.f);
			}
		}
		// -SailingCamVessel=<kind>[,<distance m>,<bearing deg from her bow>]: frame the nearest traffic vessel of that kind
		// (ETrafficKind: 1 runabout, 2 trawler, 3 tug and tow, 4 ship, 5 committee boat) from the water, for the vessel models.
		FString CamVessel;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCamVessel="), CamVessel, false))
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
	const FVector L = SailingFrame::ToMapCm(GetWorld(), CaptureCamera->GetComponentLocation());   // the map frame
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
	float SunThroughCloud = 1.f;
	double MeterEV = 0.0;
	if (TActorIterator<ASailingEnvironment> It(GetWorld()); It)
	{
		SunThroughCloud = It->GetCloudShade();
		MeterEV = It->GetCameraEV();
	}
	const FString Json = FString::Printf(
		TEXT("{\n  \"preset\": \"%s\",\n  \"hfov_deg\": %.1f,\n  \"barrel_distortion\": %s,\n  \"exposure\": \"%s\",\n")
		TEXT("  \"camera_m\": [%.2f, %.2f, %.2f],\n  \"camera_pitch_yaw_roll_deg\": [%.1f, %.1f, %.1f],\n  \"bearing_off_bow_deg\": %.0f,\n")
		TEXT("  \"area\": \"%s\",\n  \"latitude\": %.4f,\n  \"longitude\": %.4f,\n  \"date\": \"%s\",\n  \"clock_hour\": %.2f,\n")
		TEXT("  \"sun_elevation_deg\": %.1f,\n  \"sun_azimuth_deg\": %.1f,\n  \"sun_through_cloud\": %.2f,\n  \"meter_ev100\": %.2f,\n")
		TEXT("  \"true_wind_kn\": %.1f,\n  \"true_wind_from_deg\": %.0f,\n  \"gust_intensity\": %.2f,\n")
		TEXT("  \"boat\": \"%hs\",\n  \"reef\": %d,\n  \"spinnaker\": %s,\n  \"crew_kg\": %.0f,\n  \"seconds_into_capture\": %.1f\n}\n"),
		Info.Name, Info.HFovDeg, Info.bBarrel ? TEXT("true") : TEXT("false"),
		FMath::IsNaN(CaptureEV) ? TEXT("auto, frozen at 2.5 s") : *FString::Printf(TEXT("EV100 %.1f"), CaptureEV),
		L.X / CmPerMeter, L.Y / CmPerMeter, L.Z / CmPerMeter, R.Pitch, R.Yaw, R.Roll, FMath::IsNaN(CaptureBearing) ? 0.f : CaptureBearing,
		*Area, Latitude, Longitude, *Date, Hour, SunElevation, SunAzimuth, SunThroughCloud, MeterEV, // SunPosition works in degrees
		T.TrueWindSpeed / kKnot, FMath::Fmod(FMath::RadiansToDegrees(T.Heading + T.TrueWindAngle) + 720.0, 360.0), Gust,
		Boat.GetConfig().Name, Controls.Reef, Controls.bSpinnaker ? TEXT("true") : TEXT("false"), Boat.GetConfig().CrewMass, CaptureElapsed);
	FFileHelper::SaveStringToFile(Json, *(FPaths::ProjectSavedDir() / TEXT("Bench") / (CaptureName + TEXT(".camera.json"))));
}

void ASailboatPawn::UpdateCrewGroomLOD()
{
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (CrewGrooms.IsEmpty() || !PC || !PC->PlayerCameraManager) return;
	const FVector Eye = PC->PlayerCameraManager->GetCameraLocation();
	for (const TPair<TWeakObjectPtr<UGroomComponent>, int32>& G : CrewGrooms)
	{
		UGroomComponent* Hair = G.Key.Get();
		if (!Hair) continue;
		// Up close the groom picks its own LOD (strands or finer cards); from 6 m it stays on its last cards.
		const double Dist = FVector::Dist(Eye, Hair->Bounds.Origin);
		const int32 Want = Dist > 600.0 ? G.Value : -1;
		if (Hair->GetForcedLOD() != Want) Hair->SetForcedLOD(Want);
		// Perf 1 fix 8: brows, beards and moustaches go past 8 m, the hair past 40 m (a few pixels; each groom drawn
		// costs its card interpolation on the render thread every frame).
		const bool bScalp = Hair->GroomAsset && Hair->GroomAsset->GetName().StartsWith(TEXT("Hair"));
		const bool bHide = Dist > (bScalp ? 4000.0 : 800.0);
		if (Hair->bHiddenInGame != bHide) { Hair->SetHiddenInGame(bHide); Hair->SetComponentTickEnabled(!bHide); }
	}
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

USkeletalMeshComponent* ASailboatPawn::NewCrewBody(USkeletalMesh* Mesh, int32 Rig)
{
	// Crew C1: posed by its own animation node on the animation worker threads (CrewAnimInstance.h).
	if (!CrewConfig) CrewConfig = MakeShared<const FBoatConfig>(Boat.GetConfig());
	USkeletalMeshComponent* Body = NewObject<USkeletalMeshComponent>(this);
	Body->SetupAttachment(BoatRoot);
	Body->SetSkeletalMesh(Mesh);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	Body->SetAnimInstanceClass(UCrewAnimInstance::StaticClass());
	if (bTrafficBoat)
	{
		// AI boats' crew react too, at 15 Hz, and only while someone can see them.
		Body->SetComponentTickInterval(1.f / 15.f);
		Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	}
	Body->PrimaryComponentTick.AddPrerequisite(this, PrimaryActorTick); // the pawn hands it the frame's input first
	Body->RegisterComponent();
	if (UCrewAnimInstance* Anim = Cast<UCrewAnimInstance>(Body->GetAnimInstance()))
	{
		Anim->Setup(MetaCrewRigs.IsValidIndex(Rig) ? MakeShared<const FCrewRig>(MetaCrewRigs[Rig]) : TSharedPtr<const FCrewRig>(), CrewConfig, Boat.HullDepth());
	}
	return Body;
}

USkeletalMeshComponent* ASailboatPawn::AddMetaHumanFigure(int32 CrewRole, int32 Index)
{
	USkeletalMesh* BodyMesh = MetaCrewMeshes[3 * CrewRole];
	const FCrewRig& Rig = MetaCrewRigs[CrewRole];
	USkeletalMeshComponent* Body = NewCrewBody(BodyMesh, CrewRole);
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
		if (K == 2 && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoPolo")))
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
						// Graphics G8: by the asset's own slot material (the component's is a dynamic instance by now, named
						// MaterialInstanceDynamic_N, so a shirt recoloured above was never hidden).
						const TArray<FSkeletalMaterial>& Slots = Part->GetSkeletalMeshAsset()->GetMaterials();
						const int32 M = Sections[S].MaterialIndex;
						const UMaterialInterface* Mat = Slots.IsValidIndex(M) ? Slots[M].MaterialInterface.Get() : nullptr;
						if (Mat && Mat->GetName().Contains(TEXT("Shirt"))) Part->ShowMaterialSection(M, S, false, L);
					}
				}
				USkeletalMeshComponent* Polo = NewObject<USkeletalMeshComponent>(this);
				Polo->SetupAttachment(Body);
				Polo->SetSkeletalMesh(PoloMesh);
				Polo->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				Polo->RegisterComponent();
				Polo->SetLeaderPoseComponent(Body);
				// pc/crew-colours: a light polo (CrewOutfit.h, Bean's "lighter mix"; dark navy and maroon read near-black backlit).
				const FLinearColor Col = SampleCrewOutfit(CrewSeed, Index).Polo;
				for (int32 M = 0; M < Polo->GetNumMaterials(); ++M)
				{
					if (M == Polo->GetMaterialIndex(TEXT("Button"))) continue;
					if (UMaterialInstanceDynamic* Mid = Polo->CreateDynamicMaterialInstance(M))
					{
						Mid->SetVectorParameterValue(TEXT("Color"), M == Polo->GetMaterialIndex(TEXT("Rib")) ? Col * 0.92f : Col);
						// Ultra audit item 7: its hem and cuffs move in the wind (UpdateCrewFigures feeds them).
						static SailingArgs::FCachedFlag StiffClothArg(TEXT("SailingStiffCrewCloth"));
						if (!StiffClothArg.Get()) CrewClothMids.Add(Mid);
					}
				}
				BoatParts.Add(Polo);
			}
		}
	}
	// Graphics G3: deck shoes (scripts/make-crew-clothes.sh, built round each sailor's feet and skinned from them).
	if (!FParse::Param(SailingArgs::Dev(), TEXT("SailingNoPolo")))
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
	if (FacePart && !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoGrooms")))
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
			// Graphics G8: the coarsest LOD that has a card mesh and draws cards (the build made cards for LODs 1 and 3 only:
			// LODs 2 and 4 draw nothing).
			int32 CardsLOD = -1;
			const TArray<FHairGroupsLOD>& Lods = G.Key->GetHairGroupsLOD();
			for (const FHairGroupsCardsSourceDescription& Cards : G.Key->GetHairGroupsCards())
			{
				const int32 L = Cards.LODIndex;
				if (!Cards.ImportedMesh || !Lods.IsValidIndex(Cards.GroupIndex) || !Lods[Cards.GroupIndex].LODs.IsValidIndex(L)) continue;
				const FHairLODSettings& Set = Lods[Cards.GroupIndex].LODs[L];
				if (Set.bVisible && Set.GeometryType == EGroomGeometryType::Cards) CardsLOD = FMath::Max(CardsLOD, L);
			}
			if (CardsLOD >= 0) CrewGrooms.Add({ Hair, CardsLOD });
		}
	}
	// The life jacket over the shirt, the cap over the head, each scaled to this skeleton and carried by the
	// chest and head bones: placed on the T-posed rest, relative to the bone's rest.
	const auto At = [&](const TCHAR* Bone) { return Rig.Rest(BodyMesh, Bone).GetLocation(); };
	const FVector Fwd = Rig.Frame.RotateVector(FVector::ForwardVector);
	const float Span = float(FVector::Dist(At(TEXT("upperarm_l")), At(TEXT("upperarm_r"))));
	const float Waist = float(At(TEXT("spine_01")).Z) + 3.f; // the hem at the navel, clear of the shorts' waistband
	const float Top = float(At(TEXT("neck_01")).Z) + 1.f;   // Graphics G6: up to the collarbones (the vest's shoulders)
	// pc/crew-colours: a bright life jacket, yellow, red or light blue (CrewOutfit.h; Graphics G6's royal blue school vests
	// read near-black backlit).
	const FLinearColor VestColour = SampleCrewOutfit(CrewSeed, Index).Vest;
	// Graphics G6: the life jacket tailored over this sailor's polo (Tools/blender/build_vest.py) and skinned like it, so it
	// wraps the body as it sits; the rigid one below where it has not been built (or with -SailingNoPolo).
	const FString VestRole = MetaHumanRoleName(CrewRole);
	USkeletalMesh* VestMesh = FParse::Param(SailingArgs::Dev(), TEXT("SailingNoPolo")) ? nullptr
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
		if (UMaterialInstanceDynamic* Mid = Shell >= 0 ? Vest->CreateDynamicMaterialInstance(Shell) : nullptr) Mid->SetVectorParameterValue(TEXT("Color"), VestColour);
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
		if (UMaterialInstanceDynamic* Mid = Pfd->CreateDynamicMaterialInstance(0)) Mid->SetVectorParameterValue(TEXT("Color"), VestColour);
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
