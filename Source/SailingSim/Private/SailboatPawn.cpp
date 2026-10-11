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
			|| Action == TEXT("ToggleHud") || Action == TEXT("ResetBoat") || Action == TEXT("Menu") || Action == TEXT("ControlsCard")
			|| Action == TEXT("MenuUp") || Action == TEXT("MenuDown") || Action == TEXT("MenuLeft") || Action == TEXT("MenuRight");
	}

	/** Controls the crew handles in the Simple layout. */
	bool IsCrewHandled(FName Action)
	{
		return Action == NAME_Traveler || Action == NAME_Vang || Action == NAME_Cunningham || Action == NAME_Outhaul || Action == NAME_Backstay;
	}

	enum EMenuRow { RowWeather, RowHour, RowSeed, RowDifficulty, RowControls, RowTrimAssist, RowLearning, RowQuality, RowVolume, RowCount };

	constexpr double kTrimAssistIdleSeconds = 4.0;
}

ASailboatPawn::ASailboatPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	BoatRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoatRoot"));
	RootComponent = BoatRoot;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BasicMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	UStaticMesh* Cube = CubeMesh.Object;
	UStaticMesh* Cylinder = CylinderMesh.Object;
	ShapeMaterial = BasicMaterial.Object;

	// Hull and rig, sized from J/22 class figures. Origin is the design waterline, midships of the waterline.
	Hull = AddPart(TEXT("Hull"), Cube, FVector(-63.f, 0.f, 15.f), FVector(559.f, 244.f, 90.f));
	AddPart(TEXT("Bow"), Cube, FVector(216.f, 0.f, 15.f), FVector(180.f, 180.f, 90.f), FRotator(0.f, 45.f, 0.f));
	AddPart(TEXT("Cockpit"), Cube, FVector(-190.f, 0.f, 58.f), FVector(220.f, 150.f, 6.f));
	AddPart(TEXT("Keel"), Cube, FVector(45.f, 0.f, -73.f), FVector(90.f, 14.f, 86.f));
	AddPart(TEXT("Mast"), Cylinder, FVector(100.f, 0.f, 492.f), FVector(10.f, 10.f, 865.f));
	AddPart(TEXT("Forestay"), Cylinder, FVector(222.f, 0.f, 460.f), FVector(1.5f, 1.5f, 785.f), FRotator(-16.f, 0.f, 0.f));

	RudderPivot = CreateDefaultSubobject<USceneComponent>(TEXT("RudderPivot"));
	RudderPivot->SetupAttachment(BoatRoot);
	RudderPivot->SetRelativeLocation(FVector(-330.f, 0.f, 0.f));
	AddPart(TEXT("Rudder"), Cube, FVector(-18.f, 0.f, -40.f), FVector(36.f, 5.f, 100.f), FRotator::ZeroRotator, RudderPivot);
	AddPart(TEXT("Tiller"), Cube, FVector(55.f, 0.f, 62.f), FVector(110.f, 4.f, 4.f), FRotator::ZeroRotator, RudderPivot);

	BoomPivot = CreateDefaultSubobject<USceneComponent>(TEXT("BoomPivot"));
	BoomPivot->SetupAttachment(BoatRoot);
	BoomPivot->SetRelativeLocation(FVector(95.f, 0.f, 145.f));
	AddPart(TEXT("Boom"), Cylinder, FVector(-150.f, 0.f, 0.f), FVector(8.f, 8.f, 300.f), FRotator(90.f, 0.f, 0.f), BoomPivot);

	MastheadFly = CreateDefaultSubobject<USceneComponent>(TEXT("MastheadFly"));
	MastheadFly->SetupAttachment(BoatRoot);
	MastheadFly->SetRelativeLocation(FVector(100.f, 0.f, 935.f));
	AddPart(TEXT("FlyArrow"), Cube, FVector(18.f, 0.f, 0.f), FVector(45.f, 2.5f, 2.5f), FRotator::ZeroRotator, MastheadFly);
	AddPart(TEXT("FlyVane"), Cube, FVector(-8.f, 0.f, 0.f), FVector(12.f, 1.f, 10.f), FRotator::ZeroRotator, MastheadFly);

	for (int32 I = 0; I < 3; ++I)
	{
		Crew.Add(AddPart(*FString::Printf(TEXT("Crew%d"), I), Cylinder, FVector(-90.f - 55.f * I, 30.f, 115.f), FVector(40.f, 40.f, 110.f)));
	}

	MainSail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MainSail"));
	MainSail->SetupAttachment(BoatRoot);
	MainSail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	JibSail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("JibSail"));
	JibSail->SetupAttachment(BoatRoot);
	JibSail->SetCollisionEnabled(ECollisionEnabled::NoCollision);

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
		if (PartName == TEXT("Hull") || PartName == TEXT("Bow")) Color = FLinearColor(0.75f, 0.06f, 0.06f);
		else if (PartName == TEXT("Keel") || PartName == TEXT("Rudder")) Color = FLinearColor(0.05f, 0.05f, 0.06f);
		else if (PartName == TEXT("Mast") || PartName == TEXT("Boom") || PartName == TEXT("Forestay")) Color = FLinearColor(0.55f, 0.56f, 0.58f);
		else if (PartName == TEXT("Tiller")) Color = FLinearColor(0.45f, 0.28f, 0.12f);
		else if (PartName.StartsWith(TEXT("Crew"))) Color = FLinearColor(0.95f, 0.75f, 0.10f);
		else if (PartName == TEXT("FlyArrow") || PartName == TEXT("FlyVane")) Color = FLinearColor(0.02f, 0.02f, 0.02f);
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
	for (UProceduralMeshComponent* Sail : { MainSail.Get(), JibSail.Get() })
	{
		UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(SailMaterial ? SailMaterial : ShapeMaterial.Get(), this);
		Mid->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.96f, 0.95f, 0.92f));
		Sail->SetMaterial(0, Mid);
	}

	ApplyDifficulty();
	ResetBoat();

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
		CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
	}
}

void ASailboatPawn::ApplyDifficulty()
{
	const bool bEasy = USailingSettings::Get()->Difficulty == ESailingDifficulty::Easy;
	FBoatConfig& Config = Boat.GetMutableConfig();
	const FBoatConfig Defaults;
	// Easy: the helm holds the tiller rigidly (no weather-helm drift) and the boat rolls less in gusts.
	Config.HelmStiffness = bEasy ? 1.0e5 : Defaults.HelmStiffness;
	Config.ExtraRollDamping = bEasy ? 2500.0 : 0.0;
}

void ASailboatPawn::ResetBoat()
{
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
		CameraYaw = FMath::UnwindDegrees(CameraYaw + 4.f * DeltaSeconds);
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
	RudderPivot->SetRelativeRotation(FRotator(0.f, -FMath::RadiansToDegrees(S.RudderAngle), 0.f));
	// The fly points into the apparent wind (where it comes from).
	MastheadFly->SetRelativeRotation(FRotator(0.f, FMath::RadiansToDegrees(T.ApparentWindAngle), 0.f));

	for (int32 I = 0; I < Crew.Num(); ++I)
	{
		const float Y = S.CrewOffset * CmPerMeter;
		const float Lean = FMath::Clamp((FMath::Abs(S.CrewOffset) - 0.4f) / 0.5f, 0.f, 1.f) * 35.f * FMath::Sign(S.CrewOffset);
		Crew[I]->SetRelativeLocation(FVector(-90.f - 55.f * I, Y, 115.f));
		Crew[I]->SetRelativeRotation(FRotator(0.f, 0.f, Lean));
	}

	BuildSailMesh(MainSail, Boat.GetConfig().Main, T.MainStrips, S.MainSide, true);
	BuildSailMesh(JibSail, Boat.GetConfig().Jib, T.JibStrips, S.JibSide, false);
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
	for (int32 K = 0; K < 3; ++K)
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
	Adjust(Controls.JibSheet, NAME_JibSheet, 0.35, 0.0, 1.0);
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
}

TArray<TPair<FString, FString>> ASailboatPawn::GetMenuRows() const
{
	const USailingSettings* S = USailingSettings::Get();
	auto OnOff = [](bool b) { return FString(b ? TEXT("On") : TEXT("Off")); };
	TArray<TPair<FString, FString>> Rows;
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
