#include "SailboatPawn.h"
#include "SailingSim.h"
#include "FlatWater.h"
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
#include "UObject/ConstructorHelpers.h"

ASailboatPawn::ASailboatPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	// Physics runs before the camera and rendering read the transform.
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	BoatRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoatRoot"));
	RootComponent = BoatRoot;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Cube = CubeMesh.Object;
	UStaticMesh* Cylinder = CylinderMesh.Object;

	// J/22 placeholder, sized from class figures (LOA 6.86 m, beam 2.44 m, draft 1.16 m).
	// Origin is the design waterline at midships. The bow is a box turned 45 degrees.
	Hull = AddPart(TEXT("Hull"), Cube, FVector(-63.f, 0.f, 15.f), FVector(559.f, 244.f, 90.f));
	AddPart(TEXT("Bow"), Cube, FVector(216.f, 0.f, 15.f), FVector(180.f, 180.f, 90.f), FRotator(0.f, 45.f, 0.f));
	AddPart(TEXT("Keel"), Cube, FVector(20.f, 0.f, -73.f), FVector(90.f, 14.f, 86.f));
	AddPart(TEXT("Rudder"), Cube, FVector(-335.f, 0.f, -45.f), FVector(30.f, 5.f, 80.f));
	AddPart(TEXT("Mast"), Cylinder, FVector(70.f, 0.f, 510.f), FVector(10.f, 10.f, 900.f));
	AddPart(TEXT("Boom"), Cylinder, FVector(-95.f, 0.f, 120.f), FVector(8.f, 8.f, 330.f), FRotator(90.f, 0.f, 0.f));
	AddPart(TEXT("Mainsail"), Cube, FVector(-90.f, 0.f, 470.f), FVector(300.f, 2.f, 680.f));

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(BoatRoot);
	CameraBoom->TargetArmLength = 1600.f;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, 250.f);
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

UStaticMeshComponent* ASailboatPawn::AddPart(FName Name, UStaticMesh* Mesh, const FVector& LocationCm, const FVector& SizeCm, const FRotator& Rotation)
{
	UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
	Part->SetupAttachment(BoatRoot);
	Part->SetStaticMesh(Mesh);
	Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Part->SetRelativeLocation(LocationCm);
	Part->SetRelativeRotation(Rotation);
	// Engine basic shapes are 100 cm across.
	Part->SetRelativeScale3D(SizeCm / 100.f);
	return Part;
}

void ASailboatPawn::BeginPlay()
{
	Super::BeginPlay();

	if (TActorIterator<AFlatWater> It(GetWorld()); It)
	{
		WaterSurfaceZMeters = It->GetSurfaceZ() / Sailing::CmPerMeter;
	}

	const FVector Start = GetActorLocation() / Sailing::CmPerMeter;
	Physics.State = Sailing::FBoatState();
	Physics.State.X = Start.X;
	Physics.State.Y = Start.Y;
	Physics.State.Z = WaterSurfaceZMeters + InitialDropMeters;
	Physics.State.Heading = FMath::DegreesToRadians(GetActorRotation().Yaw);
	ApplyStateToTransform();

	// Simple colors so the placeholder reads at a glance.
	TInlineComponentArray<UStaticMeshComponent*> Parts(this);
	for (UStaticMeshComponent* Part : Parts)
	{
		const FString PartName = Part->GetName();
		FLinearColor Color = FLinearColor(0.85f, 0.86f, 0.88f);
		if (PartName == TEXT("Keel") || PartName == TEXT("Rudder")) Color = FLinearColor(0.05f, 0.05f, 0.06f);
		else if (PartName == TEXT("Mast") || PartName == TEXT("Boom")) Color = FLinearColor(0.55f, 0.56f, 0.58f);
		else if (PartName == TEXT("Mainsail")) Color = FLinearColor(0.95f, 0.94f, 0.90f);
		else if (PartName == TEXT("Hull")) Color = FLinearColor(0.75f, 0.06f, 0.06f);
		if (UMaterialInstanceDynamic* Mid = Part->CreateAndSetMaterialInstanceDynamic(0))
		{
			Mid->SetVectorParameterValue(TEXT("Color"), Color);
		}
	}
}

void ASailboatPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const int32 Steps = Stepper.Advance(DeltaSeconds);
	for (int32 i = 0; i < Steps; ++i)
	{
		Physics.Step(Stepper.GetStepDt(), Controls, WaterSurfaceZMeters);
	}
	ApplyStateToTransform();
}

void ASailboatPawn::ApplyStateToTransform()
{
	const Sailing::FBoatState& S = Physics.State;
	const FVector Location(S.X, S.Y, S.Z);
	const FRotator Rotation(FMath::RadiansToDegrees(S.Pitch), FMath::RadiansToDegrees(S.Heading), FMath::RadiansToDegrees(S.Heel));
	SetActorLocationAndRotation(Location * Sailing::CmPerMeter, Rotation);
}

void ASailboatPawn::OnLook(const FInputActionValue& Value)
{
	const FVector2D Delta = Value.Get<FVector2D>();
	CameraYaw = FMath::UnwindDegrees(CameraYaw + Delta.X);
	CameraPitch = FMath::Clamp(CameraPitch + Delta.Y, -70.f, 10.f);
	CameraBoom->SetRelativeRotation(FRotator(CameraPitch, CameraYaw, 0.f));
}

void ASailboatPawn::CreateInput()
{
	if (MappingContext)
	{
		return;
	}

	// Input assets are built in code for Phase 0 so the repo has no binary input assets to keep in sync.
	MappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Sailboat"));

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};
	auto Map = [this](UInputAction* Action, FKey Key, bool bNegate = false, float Scale = 1.f)
	{
		FEnhancedActionKeyMapping& Mapping = MappingContext->MapKey(Action, Key);
		if (bNegate)
		{
			Mapping.Modifiers.Add(NewObject<UInputModifierNegate>(MappingContext));
		}
		if (Scale != 1.f)
		{
			UInputModifierScalar* Scalar = NewObject<UInputModifierScalar>(MappingContext);
			Scalar->Scalar = FVector(Scale);
			Mapping.Modifiers.Add(Scalar);
		}
	};

	SteerAction = MakeAction(TEXT("IA_Steer"), EInputActionValueType::Axis1D);
	Map(SteerAction, EKeys::D);
	Map(SteerAction, EKeys::Right);
	Map(SteerAction, EKeys::A, true);
	Map(SteerAction, EKeys::Left, true);
	Map(SteerAction, EKeys::Gamepad_LeftX);

	ThrottleAction = MakeAction(TEXT("IA_Throttle"), EInputActionValueType::Axis1D);
	Map(ThrottleAction, EKeys::W);
	Map(ThrottleAction, EKeys::Up);
	Map(ThrottleAction, EKeys::S, true);
	Map(ThrottleAction, EKeys::Down, true);
	Map(ThrottleAction, EKeys::Gamepad_RightTriggerAxis);
	Map(ThrottleAction, EKeys::Gamepad_LeftTriggerAxis, true);

	LookAction = MakeAction(TEXT("IA_Look"), EInputActionValueType::Axis2D);
	Map(LookAction, EKeys::Mouse2D, false, 0.5f);
	Map(LookAction, EKeys::Gamepad_Right2D, false, 2.0f);
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

	if (UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		Input->BindAction(SteerAction, ETriggerEvent::Triggered, this, &ASailboatPawn::OnSteer);
		Input->BindAction(SteerAction, ETriggerEvent::Completed, this, &ASailboatPawn::OnSteerReleased);
		Input->BindAction(ThrottleAction, ETriggerEvent::Triggered, this, &ASailboatPawn::OnThrottle);
		Input->BindAction(ThrottleAction, ETriggerEvent::Completed, this, &ASailboatPawn::OnThrottleReleased);
		Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &ASailboatPawn::OnLook);
	}
	else
	{
		UE_LOG(LogSailing, Warning, TEXT("SailboatPawn expects an EnhancedInputComponent; check DefaultInput.ini."));
	}
}
