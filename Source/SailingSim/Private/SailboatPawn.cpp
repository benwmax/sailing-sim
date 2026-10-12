#include "SailboatPawn.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "WaterSurface.h"
#include "SailingAudio.h"
#include "SailingEnvironment.h"
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
#include "ProceduralMeshComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"

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
			|| Action == TEXT("Spinnaker") || Action == TEXT("Reef") || Action == TEXT("Board") || Action == TEXT("Righting") || Action == TEXT("EngineNeutral");
	}

	/** Controls the crew handles in the Simple layout. */
	bool IsCrewHandled(FName Action)
	{
		return Action == NAME_Traveler || Action == NAME_Vang || Action == NAME_Cunningham || Action == NAME_Outhaul || Action == NAME_Backstay;
	}

	enum EMenuRow { RowBoat, RowDrill, RowLaunch, RowLakeLevel, RowWeather, RowHour, RowSeed, RowDifficulty, RowControls, RowTrimAssist, RowLearning, RowQuality, RowVolume, RowCount };

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
	Boat = FBoatModel(FBoatConfig::Make(BoatType));
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
	switch (C.Type)
	{
	case EBoatType::J22: HullColor = FLinearColor(0.75f, 0.06f, 0.06f); break;      // the lesson boat stays red
	case EBoatType::Sunfish: HullColor = FLinearColor(0.95f, 0.72f, 0.10f); break;
	case EBoatType::Catalina30: HullColor = FLinearColor(0.08f, 0.13f, 0.30f); break;
	case EBoatType::Hobie16: HullColor = FLinearColor(0.10f, 0.45f, 0.75f); break;
	default: break;
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
	BuildHullMesh();

	const FBoatConfig& C = Boat.GetConfig();
	const FHullShape& Main = C.Hulls[0];
	const FLinearColor Dark(0.05f, 0.05f, 0.06f), Spar(0.55f, 0.56f, 0.58f), Wood(0.45f, 0.28f, 0.12f), Grey(0.25f, 0.25f, 0.27f), White(0.92f, 0.92f, 0.9f);
	const double DeckZ = C.bMultihull ? Main.SheerZ : Main.SheerHeight(C.MastX);

	// Keels, boards and rudders (a slender cat hull's own lift has no part to show).
	for (const FFoilDef& F : C.Foils)
	{
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
	MastheadFly->SetRelativeLocation(ToCm(C.MastX, 0.0, C.MastheadZ + 0.08));

	// Deck structure: a cabin on the keelboats; beams and trampolines on the cats; akas and nets on the trimaran.
	const double Loa = C.LengthOverall;
	switch (C.Type)
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

	// Crew.
	for (int32 I = 0; I < C.CrewCount; ++I)
	{
		Crew.Add(AddBoatPart(CylinderMesh, FVector::ZeroVector, FVector(40.f, 40.f, 110.f), FLinearColor(0.95f, 0.75f, 0.10f)));
	}

	// Telltales on the jib only when there is one.
	for (UStaticMeshComponent* T : JibTelltales) T->SetVisibility(C.HasJib());
	JibSail->SetVisibility(C.HasJib());
	if (C.HasJib()) JibSail->ClearAllMeshSections();
	MainSail->ClearAllMeshSections();
	SpinSail->ClearAllMeshSections();
	SpinSail->SetVisibility(false);
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
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
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
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingTWA="), StartTwa))
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
	UMaterialInterface* SailMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Sail.M_Sail"));
	for (UProceduralMeshComponent* Sail : { MainSail.Get(), JibSail.Get(), SpinSail.Get() })
	{
		UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(SailMaterial ? SailMaterial : ShapeMaterial.Get(), this);
		// The spinnaker in the classic red, white and blue; working sails in white Dacron.
		Mid->SetVectorParameterValue(TEXT("Color"), Sail == SpinSail ? FLinearColor(0.85f, 0.12f, 0.12f) : FLinearColor(0.96f, 0.95f, 0.92f));
		Sail->SetMaterial(0, Mid);
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

	bDemo = FParse::Param(FCommandLine::Get(), TEXT("SailingDemo"));
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
	FString DrillArg;
	if (FParse::Value(FCommandLine::Get(), TEXT("SailingDrill="), DrillArg))
	{
		for (int32 I = 1; I < int32(ESailingDrill::Count); ++I)
		{
			if (DrillArg.Equals(FString(DrillName(ESailingDrill(I))).Replace(TEXT(" "), TEXT("")), ESearchCase::IgnoreCase))
			{
				MenuDrill = ESailingDrill(I);
				StartDrill(MenuDrill);
			}
		}
	}
	if (FParse::Param(FCommandLine::Get(), TEXT("SailingMenu"))) bMenuOpen = true; // screenshots of the settings menu
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
	TrimAssist.Reset();
	KeyboardTiller = 0.f;
	ApplyStateToTransform();
}

void ASailboatPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
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
	const int32 Steps = Stepper.Advance(DeltaSeconds);
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

	if (Water)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const Vec3 O = Boat.OriginPosition();
		Water->SetBoatForWake(FVector2D(O.X, O.Y), T.Heading, T.BoatSpeed, T.Heel);
	}
	UpdateSound(DeltaSeconds);

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
	}
	UpdateDrillVisuals();
}

void ASailboatPawn::StartDrill(ESailingDrill Drill)
{
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
		if (Drill == ESailingDrill::LeaveTheDock && FindBerth(GM->GetLake().Terrain, GM->GetLake().Obstacles, FVector2D::ZeroVector, 600.0, WindFromRad, Berth, BerthHeading, Boat.GetConfig()))
		{
			Boat.Reset(Berth.X, Berth.Y, BerthHeading, 0.0);
			Boat.GetMutableState().Time = Time;
			Boat.GetMooringLines() = FindDockLines(Boat, GM->GetLake().Obstacles);
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
		ApplyStateToTransform();
	}
	MaxContactKnots = 0.0;
	const double WindFrom = GM ? GM->GetWeatherState().Wind.FromDegrees * kDegToRad : 0.0;
	DrillRunner.Start(Drill, Boat, WindFrom);
	bMenuOpen = false;
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

	// Boom along -X turned by yaw psi points at (-cos psi, -sin psi); the sail chord is (-cos a, side sin a).
	BoomPivot->SetRelativeRotation(FRotator(0.f, -FMath::RadiansToDegrees(S.BoomAngle), 0.f));
	for (USceneComponent* Pivot : RudderPivots) Pivot->SetRelativeRotation(FRotator(0.f, -FMath::RadiansToDegrees(S.RudderAngle), 0.f));
	// The fly points into the apparent wind (where it comes from).
	MastheadFly->SetRelativeRotation(FRotator(0.f, FMath::RadiansToDegrees(T.ApparentWindAngle), 0.f));

	// Crew: along the cockpit at the windward rail, leaning out to hike; flat out on the wire on a trapeze;
	// standing on the board (or leaning back on the righting line) when righting a capsized boat.
	const FBoatConfig& Cfg = Boat.GetConfig();
	const FHullShape& MainHull = Cfg.Hulls[0];
	const double Sit = Cfg.bMultihull ? MainHull.SheerZ + 0.1 : MainHull.SheerHeight(Cfg.CrewCG.X);
	for (int32 I = 0; I < Crew.Num(); ++I)
	{
		const double X = Cfg.CrewCG.X + 0.55 * (0.5 * (Crew.Num() - 1) - I);
		const double Out = FMath::Abs(S.CrewOffset);
		const double Rail = Cfg.bMultihull ? FMath::Abs(Cfg.Hulls.back().CenterY) + 0.2 : 0.5 * Cfg.Beam;
		const bool bOnWire = Cfg.bTrapeze && Out > Rail;
		float Lean = FMath::Clamp(float(Out - 0.6 * Rail) / 0.5f, 0.f, 1.f) * 35.f;
		double Z = Sit + 0.45 + S.CrewOffsetZ;
		if (bOnWire)
		{
			Lean = 75.f; // feet on the rail, body out over the water
			Z = Sit + 0.75;
		}
		Crew[I]->SetRelativeLocation(ToCm(X, S.CrewOffset, Z));
		Crew[I]->SetRelativeRotation(FRotator(0.f, 0.f, Lean * FMath::Sign(S.CrewOffset)));
	}

	BuildSailMesh(MainSail, Cfg.Main, T.MainStrips, S.MainSide, true);
	if (Cfg.HasJib()) BuildSailMesh(JibSail, Cfg.Jib, T.JibStrips, S.JibSide, false);
	SpinSail->SetVisibility(T.NumSpinStrips > 0);
	if (T.NumSpinStrips > 0) BuildSailMesh(SpinSail, Cfg.Spinnaker, T.SpinStrips, S.SpinSide, false);
	UpdateTelltales();
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
	CameraYaw = FMath::UnwindDegrees(CameraYaw + Delta.X);
	CameraPitch = FMath::Clamp(CameraPitch + Delta.Y, -75.f, 5.f);
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
}

void ASailboatPawn::OnZoom(const FInputActionValue& Value)
{
	CameraDistance = FMath::Clamp(CameraDistance - Value.Get<float>() * 120.f, 400.f, 4000.f);
	CameraBoom->TargetArmLength = CameraDistance;
}

void ASailboatPawn::OnButton(const FInputActionValue& Value, FName Action)
{
	USailingSettings* Settings = USailingSettings::Get();
	if (Action == TEXT("Menu"))
	{
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
		Settings->bShowHud = !Settings->bShowHud;
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
		StatusMessage = TEXT("Lines cast off");
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
	Rows.Add({ TEXT("Boat"), FString(BoatTypeName(EBoatType(FMath::Clamp(S->BoatType, 0, int32(EBoatType::Count) - 1)))) });
	Rows.Add({ TEXT("Drill (Left/Right starts it)"), FString(DrillName(MenuDrill)) });
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
		Level = S->bGaugeLakeLevel ? FString::Printf(TEXT("Gauge %s: %.1f ft (%.1f ft low)"), *L.LevelDate, L.LevelFeet, L.PoolFeet - L.LevelFeet)
			: FString::Printf(TEXT("Full pool: %.1f ft"), L.PoolFeet);
		if (S->bGaugeLakeLevel != (L.Terrain.GetLevelBelowPool() > 0.0)) Level += TEXT(" (next start)");
	}
	Rows.Add({ TEXT("Lake level"), Level });
	Rows.Add({ TEXT("Weather"), FString(WeatherPresetName(EWeatherPreset(S->WeatherPreset))) });
	Rows.Add({ TEXT("Start time"), FString::Printf(TEXT("%02d:%02d"), int32(S->StartHour), int32(FMath::Fmod(S->StartHour, 1.f) * 60.f)) });
	Rows.Add({ TEXT("Weather seed"), FString::FromInt(S->WeatherSeed) });
	Rows.Add({ TEXT("Difficulty"), S->Difficulty == ESailingDifficulty::Easy ? TEXT("Easy") : TEXT("Realistic") });
	Rows.Add({ TEXT("Controls"), S->Difficulty == ESailingDifficulty::Easy ? TEXT("Simple (always on Easy)") : (S->ControlLayout == ESailingControlLayout::Simple ? TEXT("Simple") : TEXT("Full")) });
	Rows.Add({ TEXT("Trim assist"), OnOff(S->bTrimAssist) });
	Rows.Add({ TEXT("Learning mode"), OnOff(S->bLearningMode) });
	Rows.Add({ TEXT("Graphics quality"), S->Quality == ESailingQuality::Low ? TEXT("Low") : (S->Quality == ESailingQuality::Medium ? TEXT("Medium") : TEXT("High")) });
	Rows.Add({ TEXT("Volume"), FString::Printf(TEXT("%d%%"), FMath::RoundToInt(S->Volume * 100.f)) });
	return Rows;
}

void ASailboatPawn::ChangeMenuValue(int32 Direction)
{
	USailingSettings* S = USailingSettings::Get();
	ASailingGameMode* GameMode = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	switch (MenuIndex)
	{
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
		S->StartHour = FMath::Clamp(S->StartHour + Direction, 6.f, 20.f);
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
		S->Quality = ESailingQuality((int32(S->Quality) + 3 + Direction) % 3);
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
