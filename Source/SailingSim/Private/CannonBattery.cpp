#include "CannonBattery.h"
#include "BenchRunner.h"
#include "SailboatPawn.h"
#include "SailingFrame.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "VisualPipeline.h"
#include "WaterSurface.h"
#include "Waves.h"
#include "Wind.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "UObject/UObjectIterator.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

double ACannonBattery::CpuSeconds = 0.0;
int32 ACannonBattery::PuffsAlive = 0;

namespace CannonFx
{
	/** The guns' parts as the model names them (export: /Game/Boats/Frigate/Guns/SM_Frigate_<Name>). */
	const TCHAR* const PartNames[] = { TEXT("Gun24_Barrel"), TEXT("Gun24_Carriage"), TEXT("Gun24_Quoin"), TEXT("Gun24_TruckFore"),
		TEXT("Gun24_TruckHind"), TEXT("Carr32_Barrel"), TEXT("Carr32_Bed"), TEXT("Carr32_Slide"), TEXT("Lid") };

	// The long 24's trucks in its carriage's frame (m: guns.json long24.trucks) and its quoin (quoin.z_m; x at level).
	const FVector TruckOrigins[4] = { FVector(0.1016, 0.47904, 0.2413), FVector(0.1016, -0.47904, 0.2413),
		FVector(-1.016, 0.51644, 0.2159), FVector(-1.016, -0.51644, 0.2159) };
	constexpr double QuoinX = -1.32673, QuoinZ = 0.50106;

	/** The smoke's sprite budget by tier, the flash lights' pool. */
	int32 SmokeBudgetFor(ESailingQuality Q)
	{
		return Q == ESailingQuality::Low ? 256 : Q == ESailingQuality::Medium ? 768 : Q == ESailingQuality::High ? 1536 : 3072;
	}
	int32 LightPoolFor(ESailingQuality Q)
	{
		return Q == ESailingQuality::Low ? 1 : Q == ESailingQuality::Medium ? 2 : Q == ESailingQuality::High ? 4 : 6;
	}
	constexpr int32 kFlashPool = 512;   // flame, bloom and spark quads

	bool ParseSide(const FString& S, Sailing::ECannonSide& Out)
	{
		if (S.StartsWith(TEXT("p"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonSide::Port; return true; }
		if (S.StartsWith(TEXT("s"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonSide::Starboard; return true; }
		if (S.StartsWith(TEXT("b"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonSide::Both; return true; }
		return false;
	}
	bool ParseMode(const FString& S, Sailing::ECannonFireMode& Out)
	{
		if (S.StartsWith(TEXT("b"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonFireMode::Broadside; return true; }
		if (S.StartsWith(TEXT("r"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonFireMode::Ripple; return true; }
		if (S.StartsWith(TEXT("a"), ESearchCase::IgnoreCase)) { Out = Sailing::ECannonFireMode::AtWill; return true; }
		return false;
	}
	bool ParseOrder(const FString& S, Sailing::ECannonOrder& Out)
	{
		static const TPair<const TCHAR*, Sailing::ECannonOrder> Names[] = { { TEXT("CastLoose"), Sailing::ECannonOrder::CastLoose },
			{ TEXT("Load"), Sailing::ECannonOrder::Load }, { TEXT("RunOut"), Sailing::ECannonOrder::RunOut }, { TEXT("Fire"), Sailing::ECannonOrder::Fire },
			{ TEXT("CeaseFire"), Sailing::ECannonOrder::CeaseFire }, { TEXT("Secure"), Sailing::ECannonOrder::Secure } };
		for (const auto& N : Names) if (S.Equals(N.Key, ESearchCase::IgnoreCase)) { Out = N.Value; return true; }
		return false;
	}

	/** The smoke's world in the game: the wind field and the waves, each cached on a coarse grid for the frame. */
	class FGameCannonWorld : public Sailing::ICannonWorld
	{
	public:
		const Sailing::FWindField* Wind = nullptr;
		const Sailing::FWaveField* Waves = nullptr;
		mutable TMap<FIntVector, Sailing::Vec3> WindCells;
		mutable TMap<FIntPoint, double> WaterCells;
		static constexpr double WindCellM = 20.0;
		static constexpr double WaterCellM = 8.0;

		Sailing::Vec3 WindAt(const Sailing::Vec3& P, double Time) const override
		{
			if (!Wind) return Sailing::Vec3();
			const FIntVector C(FMath::FloorToInt(P.X / WindCellM), FMath::FloorToInt(P.Y / WindCellM), FMath::Clamp(FMath::FloorToInt(P.Z / 10.0), 0, 8));
			if (const Sailing::Vec3* Found = WindCells.Find(C)) return *Found;
			const Sailing::Vec3 V = Wind->VelocityAt(Sailing::Vec3((C.X + 0.5) * WindCellM, (C.Y + 0.5) * WindCellM, FMath::Max(2.0, (C.Z + 0.5) * 10.0)), Time);
			WindCells.Add(C, V);
			return V;
		}
		double WaterZ(double X, double Y, double Time) const override
		{
			if (!Waves) return 0.0;
			const FIntPoint C(FMath::FloorToInt(X / WaterCellM), FMath::FloorToInt(Y / WaterCellM));
			if (const double* Found = WaterCells.Find(C)) return *Found;
			const double H = Waves->Height((C.X + 0.5) * WaterCellM, (C.Y + 0.5) * WaterCellM, Time);
			WaterCells.Add(C, H);
			return H;
		}
		void NewFrame() { WindCells.Reset(); WaterCells.Reset(); }
	};

	FTransform FrameOf(const Sailing::Vec3& O, const Sailing::Vec3& X, const Sailing::Vec3& Y, const Sailing::Vec3& Z)
	{
		const FMatrix M(FVector(X.X, X.Y, X.Z), FVector(Y.X, Y.Y, Y.Z), FVector(Z.X, Z.Y, Z.Z), FVector(O.X, O.Y, O.Z) * CmPerMeter);
		FTransform T(M);
		T.NormalizeRotation();
		return T;
	}

	ACannonBattery* FirstBattery(UWorld* World)
	{
		if (!World) return nullptr;
		TActorIterator<ACannonBattery> It(World);
		return It ? *It : nullptr;
	}
}

ACannonBattery::ACannonBattery()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;   // after the ship has moved this frame
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	RootComponent = Root;
}

ACannonBattery* ACannonBattery::SpawnBattery(USceneComponent* ShipRoot)
{
	if (!ShipRoot || !ShipRoot->GetWorld()) return nullptr;
	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ACannonBattery* B = ShipRoot->GetWorld()->SpawnActor<ACannonBattery>(ShipRoot->GetComponentLocation(), ShipRoot->GetComponentRotation(), Spawn);
	if (B) B->AttachToComponent(ShipRoot, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
	return B;
}

ACannonBattery* ACannonBattery::SpawnStageIfAsked(UWorld* World)
{
	if (!World) return nullptr;
	const TCHAR* Cmd = SailingArgs::Dev();
	if (!FParse::Param(Cmd, TEXT("SailingCannonStage")) && !FCString::Strifind(Cmd, TEXT("-SailingCannonStage="))) return nullptr;
	// Off the player's boat: <forward m>,<right m>,<heading deg relative to hers> (default 60 m to starboard, the same heading).
	double Fwd = 0.0, Right = 60.0, Heading = 0.0;
	FString Spec;
	if (FParse::Value(Cmd, TEXT("SailingCannonStage="), Spec, false))
	{
		TArray<FString> P;
		Spec.ParseIntoArray(P, TEXT(","));
		if (P.Num() > 0) Fwd = FCString::Atod(*P[0]);
		if (P.Num() > 1) Right = FCString::Atod(*P[1]);
		if (P.Num() > 2) Heading = FCString::Atod(*P[2]);
	}
	FVector At = FVector::ZeroVector;
	FRotator Rot = FRotator::ZeroRotator;
	if (APawn* Player = UGameplayStatics::GetPlayerPawn(World, 0))
	{
		Rot = FRotator(0.0, Player->GetActorRotation().Yaw, 0.0);
		At = Player->GetActorLocation() + Rot.RotateVector(FVector(Fwd, Right, 0.0) * CmPerMeter);
	}
	for (TActorIterator<AWaterSurface> It(World); It; ++It) At.Z = It->GetActorLocation().Z;   // the model's origin is at her waterline
	Rot.Yaw += Heading;
	FActorSpawnParameters Spawn;
	Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ACannonBattery* B = World->SpawnActor<ACannonBattery>(At, Rot, Spawn);
	if (B)
	{
		// It keeps station off the player's boat (her pawn may not exist yet at StartPlay: FollowStage places it each frame).
		B->bStage = true;
		B->StageOffsetCm = FVector(Fwd, Right, 0.0) * CmPerMeter;
		B->StageHeadingDeg = Heading;
	}
	SAIL_LOG(Display, TEXT("Cannon stage %.0f m ahead, %.0f m to starboard, heading %+.0f"), Fwd, Right, Heading);
	return B;
}

void ACannonBattery::FollowStage()
{
	const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Player) return;
	const FRotator Yaw(0.0, Player->GetActorRotation().Yaw, 0.0);
	FVector At = Player->GetActorLocation() + Yaw.RotateVector(StageOffsetCm);
	At.Z = WaterZ0;
	SetActorLocationAndRotation(At, FRotator(0.0, Yaw.Yaw + StageHeadingDeg, 0.0));
}

void ACannonBattery::InitParams()
{
	Params = Sailing::FCannonParams();
	FString Unknown;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingCannonFx="), CommandLineTuning, false))
	{
		const int32 N = ApplyTuning(CommandLineTuning, &Unknown);
		SAIL_LOG(Display, TEXT("Cannon fx: %d from the command line%s%s"), N, Unknown.IsEmpty() ? TEXT("") : TEXT(", unknown: "), *Unknown);
	}
}

int32 ACannonBattery::ApplyTuning(const FString& Text, FString* OutUnknown)
{
	std::string Unknown;
	const int32 N = Params.ApplyOverrides(std::string(TCHAR_TO_UTF8(*Text)), &Unknown);
	if (OutUnknown) *OutUnknown = FString(UTF8_TO_TCHAR(Unknown.c_str()));
	Battery.SetParams(Params);
	Smoke.SetParams(Params);
	PushLook();
	return N;
}

void ACannonBattery::PushLook()
{
	// The look's knobs (docs/cannon-fire/tuning.md) as the materials' parameters; M_Spray standing in has none of them.
	// Luminances are real (cd/m^2): the scene's exposure runs SceneEVOffset stops under the real EV (VisualPipeline.cpp).
	const double ToScene = FMath::Pow(2.0, -SceneEVOffset());
	if (SmokeMID)
	{
		SmokeMID->SetScalarParameterValue(TEXT("GlowNits"), float(Params.SmokeGlowNits * ToScene));
		SmokeMID->SetScalarParameterValue(TEXT("Albedo"), float(Params.SmokeAlbedo));
		SmokeMID->SetScalarParameterValue(TEXT("ForwardScatter"), float(Params.SmokeForwardScatter));
		SmokeMID->SetScalarParameterValue(TEXT("EdgeSoftness"), float(Params.SmokeEdgeSoftness));
		SmokeMID->SetScalarParameterValue(TEXT("CoreGain"), float(Params.SmokeCoreGain));
		SmokeMID->SetScalarParameterValue(TEXT("DepthFadeCm"), float(Params.SmokeDepthFadeM * CmPerMeter));
	}
	if (FlashMID)
	{
		FlashMID->SetScalarParameterValue(TEXT("FlameNits"), float(Params.FlameNits * ToScene));
		FlashMID->SetScalarParameterValue(TEXT("SparkNits"), float(Params.SparkNits * ToScene));
	}
}

double ACannonBattery::SimNow() const
{
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	return GM ? GM->GetSimTime() : (GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0);
}

void ACannonBattery::BeginPlay()
{
	Super::BeginPlay();
	const ESailingQuality Q = USailingSettings::Get()->Quality;
	InitParams();
	Battery.SetParams(Params);
	Battery.Init(Sailing::FrigateCannonMounts(), 1);
	Smoke.SetParams(Params);
	Smoke.SetBudget(CannonFx::SmokeBudgetFor(Q));
	Smoke.Reseed(7);
	const TCHAR* Cmd = SailingArgs::Dev();
	bNoSmoke = FParse::Param(Cmd, TEXT("SailingNoCannonSmoke"));
	bNoLights = FParse::Param(Cmd, TEXT("SailingNoCannonLights"));
	bDebug = FParse::Param(Cmd, TEXT("SailingDebugCannons"));
	for (TActorIterator<AWaterSurface> It(GetWorld()); It; ++It) WaterZ0 = It->GetActorLocation().Z;
	BuildGunVisuals();
	// Bench and stills: -SailingBroadside=<s after the start>[,side[,mode]], -SailingBroadsideEvery=<s>.
	FString Spec;
	if (FParse::Value(Cmd, TEXT("SailingBroadside="), Spec, false))
	{
		TArray<FString> P;
		Spec.ParseIntoArray(P, TEXT(","));
		NextBroadside = SimNow() + (P.Num() > 0 ? FCString::Atod(*P[0]) : 3.0);
		if (P.Num() > 1) CannonFx::ParseSide(P[1], BenchSide);
		if (P.Num() > 2) CannonFx::ParseMode(P[2], BenchMode);
		FParse::Value(Cmd, TEXT("SailingBroadsideEvery="), BroadsideEvery);
		// Run out and ready from the start, so the bench measures the guns as they stand.
		MakeReady(BenchSide);
	}
	SAIL_LOG(Display, TEXT("Cannon battery: %d guns, smoke budget %d, %d flash lights%s"), Battery.Num(), Smoke.GetBudget(),
		bNoLights ? 0 : CannonFx::LightPoolFor(Q), bStage ? TEXT(" (stage)") : TEXT(""));
}

ACannonBattery::FPartMesh ACannonBattery::LoadPart(const TCHAR* Name, EPart Part) const
{
	FPartMesh Out;
	const FString Path = FString::Printf(TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_%s.SM_Frigate_%s"), Name, Name);
	Out.Mesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet));
	if (Out.Mesh) return Out;
	// Stand-ins until the PC imports her guns: the engine's 1 m cylinder (along Z, centred) and cube (centred).
	static const TCHAR* Cylinder = TEXT("/Engine/BasicShapes/Cylinder.Cylinder");
	static const TCHAR* Cube = TEXT("/Engine/BasicShapes/Cube.Cube");
	Out.bStandIn = true;
	const FRotator ZToX(-90.0, 0.0, 0.0), ZToY(0.0, 0.0, -90.0);
	auto Box = [](const FVector& CentreM, const FVector& SizeM) { return FTransform(FQuat::Identity, CentreM * CmPerMeter, SizeM); };
	switch (Part)
	{
	case LongBarrel: Out.Fix = FTransform(ZToX, FVector(0.2, 0.0, 0.0) * CmPerMeter, FVector(0.42, 0.42, 2.9)); break;
	case CarrBarrel: Out.Fix = FTransform(ZToX, FVector(0.53, 0.0, 0.24) * CmPerMeter, FVector(0.42, 0.42, 1.3)); break;
	case TruckFore: Out.Fix = FTransform(ZToY, FVector::ZeroVector, FVector(0.483, 0.483, 0.12)); break;
	case TruckHind: Out.Fix = FTransform(ZToY, FVector::ZeroVector, FVector(0.432, 0.432, 0.12)); break;
	case LongCarriage: Out.Fix = Box(FVector(-0.45, 0.0, 0.45), FVector(1.6, 1.0, 0.55)); break;
	case LongQuoin: Out.Fix = Box(FVector(0.0, 0.0, 0.0), FVector(0.5, 0.33, 0.08)); break;
	case CarrBed: Out.Fix = Box(FVector(0.35, 0.0, 0.12), FVector(1.3, 0.6, 0.24)); break;
	case CarrSlide: Out.Fix = Box(FVector(-0.5, 0.0, 0.22), FVector(2.2, 0.7, 0.43)); break;
	case Lid: Out.Fix = Box(FVector(0.0, 0.42, 0.045), FVector(0.85, 0.84, 0.09)); break;
	default: break;
	}
	const bool bCyl = Part == LongBarrel || Part == CarrBarrel || Part == TruckFore || Part == TruckHind;
	Out.Mesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, bCyl ? Cylinder : Cube, nullptr, LOAD_NoWarn | LOAD_Quiet));
	return Out;
}

FTransform ACannonBattery::PortFrame(const Sailing::FGun& G, double X, double Z) const
{
	const Sailing::FCannonMount& M = G.Mount;
	return CannonFx::FrameOf(M.Origin + M.AxisX * X + M.AxisZ * Z, M.AxisX, M.AxisY, M.AxisZ);
}

void ACannonBattery::BuildGunVisuals()
{
	Parts.SetNum(PartCount);
	PartISMs.SetNum(PartCount);
	for (int32 P = 0; P < PartCount; ++P)
	{
		Parts[P] = LoadPart(CannonFx::PartNames[P], EPart(P));
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this);
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->SetupAttachment(Root);
		ISM->SetStaticMesh(Parts[P].Mesh);
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetCanEverAffectNavigation(false);
		ISM->RegisterComponent();
		PartISMs[P] = ISM;
	}
	// The lids' own meshes (SM_Frigate_Lid_NN_S): one ISM per lid would be many; each is its own component instead.
	Draw.SetNum(Battery.Num());
	Gear.SetNum(Battery.Num());
	Lids.SetNum(Battery.Num());
	// The housed guns' tompions and lead aprons (shared meshes, placed by gundeck.json's copies), drawn until cast loose.
	CoverISMs.SetNum(2);
	for (int32 C = 0; C < 2; ++C)
	{
		const TCHAR* CoverPath = C == 0 ? TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_Gun24_Tompion.SM_Frigate_Gun24_Tompion") : TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_Gun24_Apron.SM_Frigate_Gun24_Apron");
		UStaticMesh* CoverMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, CoverPath, nullptr, LOAD_NoWarn | LOAD_Quiet));
		if (!CoverMesh) continue;
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this);
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->SetupAttachment(Root);
		ISM->SetStaticMesh(CoverMesh);
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetCanEverAffectNavigation(false);
		ISM->RegisterComponent();
		CoverISMs[C] = ISM;
	}
	GearMeshes.SetNum(Battery.Num() * 3);
	for (int32 I = 0; I < Battery.Num(); ++I)
	{
		const Sailing::FGun& G = Battery.Guns()[size_t(I)];
		FGunDraw& D = Draw[I];
		const bool bLong = G.Mount.Kind == Sailing::ECannonKind::Long24;
		const FTransform Id = FTransform::Identity;
		if (bLong)
		{
			D.Barrel = PartISMs[LongBarrel]->AddInstance(Id);
			D.Carriage = PartISMs[LongCarriage]->AddInstance(Id);
			D.Quoin = PartISMs[LongQuoin]->AddInstance(Id);
			for (int32 T = 0; T < 4; ++T) D.Trucks[T] = PartISMs[T < 2 ? TruckFore : TruckHind]->AddInstance(Id);
			if (G.Mount.bHinge)
			{
				// The lid's own mesh (pivoted on its hinge: guns.json lid_frame), or the shared stand-in.
				const FString LidName = FString::Printf(TEXT("Lid_%02d_%s"), G.Mount.Port, G.Mount.Side == Sailing::ECannonSide::Port ? TEXT("P") : TEXT("S"));
				const FString LidPath = FString::Printf(TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_%s.SM_Frigate_%s"), *LidName, *LidName);
				if (UStaticMesh* LidMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *LidPath, nullptr, LOAD_NoWarn | LOAD_Quiet)))
				{
					UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
					C->SetMobility(EComponentMobility::Movable);
					C->SetupAttachment(Root);
					C->SetStaticMesh(LidMesh);
					C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					C->RegisterComponent();
					Lids[I] = C;
				}
				else
				{
					D.Lid = PartISMs[Lid]->AddInstance(Id);
				}
			}
			for (int32 C = 0; C < 2; ++C)
				if ((G.Mount.HousedCovers & (1 << C)) && CoverISMs[C]) D.Covers[C] = CoverISMs[C]->AddInstance(Id);
		}
		else
		{
			D.Barrel = PartISMs[CarrBarrel]->AddInstance(Id);
			D.Bed = PartISMs[CarrBed]->AddInstance(Id);
			D.Slide = PartISMs[CarrSlide]->AddInstance(Id);
		}
		// Gear by pose and the gun's irons, in its port's frame.
		const FString GunId(UTF8_TO_TCHAR(G.Mount.Id));
		const FString Gun = FString::Printf(TEXT("%s_%s"), bLong ? TEXT("Gun24") : TEXT("Carr32"), *GunId);
		const TCHAR* Poses[3] = { bLong ? TEXT("GearHoused") : TEXT("GearRunOut"), bLong ? TEXT("GearRunIn") : TEXT("GearRecoil"), TEXT("GearRunOut") };
		for (int32 K = 0; K < 3; ++K)
		{
			const FString Path = FString::Printf(TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_%s_%s.SM_Frigate_%s_%s"), *Gun, Poses[K], *Gun, Poses[K]);
			GearMeshes[I * 3 + K] = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet));
		}
		const FTransform Port = PortFrame(G, 0.0, 0.0);
		if (GearMeshes[I * 3])
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Movable);
			C->SetupAttachment(Root);
			C->SetRelativeTransform(Port);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->RegisterComponent();
			Gear[I] = C;
		}
		const FString IronsPath = FString::Printf(TEXT("/Game/Boats/Frigate/Guns/SM_Frigate_%s_Irons.SM_Frigate_%s_Irons"), *Gun, *Gun);
		if (UStaticMesh* Irons = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, *IronsPath, nullptr, LOAD_NoWarn | LOAD_Quiet)))
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Movable);
			C->SetupAttachment(Root);
			C->SetStaticMesh(Irons);
			C->SetRelativeTransform(Port);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->RegisterComponent();
		}
	}
	// The smoke and the flame: quads (the engine's 1 m plane) in the render's world, hidden ones parked at zero scale.
	QuadMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"), nullptr, LOAD_NoWarn | LOAD_Quiet));
	SmokeMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_CannonSmoke.M_CannonSmoke"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	FlashMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_CannonFlash.M_CannonFlash"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	// Until the effects script has made them (docs/cannon-fire/), M_Spray's mist stands in for both.
	UMaterialInterface* Spray = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Spray.M_Spray"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (SmokeMaterial) SmokeMID = UMaterialInstanceDynamic::Create(SmokeMaterial, this);
	if (FlashMaterial) FlashMID = UMaterialInstanceDynamic::Create(FlashMaterial, this);
	PushLook();
	if (!SmokeMaterial) SmokeMaterial = Spray;
	if (!FlashMaterial) FlashMaterial = Spray;
	const FVector Here = GetActorLocation();
	auto MakeQuads = [&](const TCHAR* Name, UMaterialInterface* Mat, int32 Count, int32 Floats)
	{
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this, Name);
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->SetupAttachment(Root);
		ISM->SetUsingAbsoluteLocation(true);
		ISM->SetUsingAbsoluteRotation(true);
		ISM->SetUsingAbsoluteScale(true);
		ISM->SetStaticMesh(QuadMesh);
		if (Mat) ISM->SetMaterial(0, Mat);
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetCastShadow(false);
		ISM->SetCanEverAffectNavigation(false);
		ISM->bAffectDistanceFieldLighting = false;
		ISM->NumCustomDataFloats = Floats;
		ISM->RegisterComponent();
		TArray<FTransform> Hidden;
		Hidden.Init(FTransform(FQuat::Identity, Here, FVector::ZeroVector), Count);
		ISM->AddInstances(Hidden, false, true);
		return ISM;
	};
	SmokePool = Smoke.GetBudget();
	FlashPool = CannonFx::kFlashPool;
	SmokeISM = MakeQuads(TEXT("CannonSmoke"), SmokeMID ? static_cast<UMaterialInterface*>(SmokeMID.Get()) : SmokeMaterial.Get(), SmokePool, 5);
	FlashISM = MakeQuads(TEXT("CannonFlash"), FlashMID ? static_cast<UMaterialInterface*>(FlashMID.Get()) : FlashMaterial.Get(), FlashPool, 4);
	const int32 NLights = bNoLights ? 0 : CannonFx::LightPoolFor(USailingSettings::Get()->Quality);
	for (int32 I = 0; I < NLights; ++I)
	{
		UPointLightComponent* L = NewObject<UPointLightComponent>(this);
		L->SetMobility(EComponentMobility::Movable);
		L->SetupAttachment(Root);
		L->SetUsingAbsoluteLocation(true);
		L->SetIntensityUnits(ELightUnits::Candelas);
		L->SetLightColor(FLinearColor(1.0f, 0.62f, 0.32f));   // black powder's flame, about 2,000 K
		L->SetCastShadows(false);
		L->SetSourceRadius(float(0.5 * CmPerMeter));
		L->SetVisibility(false);
		L->RegisterComponent();
		Lights.Add(L);
	}
	bBuilt = true;
	UpdateGunVisuals(true);
}

void ACannonBattery::UpdateGunVisuals(bool bAll)
{
	bool bDirty[PartCount] = { false };
	const Sailing::FCannonKindSpec& LongK = Battery.Spec(Sailing::ECannonKind::Long24);
	const Sailing::FCannonKindSpec& CarrK = Battery.Spec(Sailing::ECannonKind::Carronade32);
	for (int32 I = 0; I < Battery.Num(); ++I)
	{
		const Sailing::FGun& G = Battery.Guns()[size_t(I)];
		FGunDraw& D = Draw[I];
		const bool bMoved = bAll || FMath::Abs(G.X - D.LastX) > 1e-4 || FMath::Abs(G.ElevationDeg - D.LastElev) > 1e-3
			|| FMath::Abs(G.LidDeg - D.LastLid) > 1e-2 || FMath::Abs(G.TruckTurn - D.LastTurn) > 1e-3;
		// The tompion and apron while housed (they come out when she's cast loose).
		const int32 Shown = G.State == Sailing::EGunState::Housed ? 1 : 0;
		if (Shown != D.CoversShown)
		{
			D.CoversShown = Shown;
			const Sailing::FCannonMount& M = G.Mount;
			for (int32 C = 0; C < 2; ++C)
			{
				if (D.Covers[C] < 0) continue;
				const FMatrix CM(FVector(M.CoverX[C].X, M.CoverX[C].Y, M.CoverX[C].Z), FVector(M.CoverY[C].X, M.CoverY[C].Y, M.CoverY[C].Z),
					FVector(M.CoverZ[C].X, M.CoverZ[C].Y, M.CoverZ[C].Z), FVector(M.CoverOrigin[C].X, M.CoverOrigin[C].Y, M.CoverOrigin[C].Z) * CmPerMeter);
				FTransform CT(CM);
				if (!Shown) CT.SetScale3D(FVector::ZeroVector);
				CoverISMs[C]->UpdateInstanceTransform(D.Covers[C], CT, false, true, true);
			}
		}
		if (!bMoved) continue;
		D.LastX = G.X;
		D.LastElev = G.ElevationDeg;
		D.LastLid = G.LidDeg;
		D.LastTurn = G.TruckTurn;
		auto Put = [&](EPart P, int32 Index, const FTransform& Xf)
		{
			if (Index < 0) return;
			PartISMs[P]->UpdateInstanceTransform(Index, Parts[P].Fix * Xf, false, false, true);
			bDirty[P] = true;
		};
		if (G.Mount.Kind == Sailing::ECannonKind::Long24)
		{
			const FTransform Carriage = PortFrame(G, G.X, LongK.CarriageZ);
			Put(LongCarriage, D.Carriage, Carriage);
			Put(LongBarrel, D.Barrel, FTransform(FRotator(G.ElevationDeg, 0.0, 0.0), FVector(LongK.BarrelPivot.X, LongK.BarrelPivot.Y, LongK.BarrelPivot.Z) * CmPerMeter) * Carriage);
			// The quoin: under the breech at level, drawn back as the breech comes down on the bed (housed: out).
			const double QuoinBack = FMath::Clamp(G.ElevationDeg / G.Mount.HousedElevationDeg, 0.0, 1.0) * 0.35;
			Put(LongQuoin, D.Quoin, FTransform(FVector(CannonFx::QuoinX - QuoinBack, 0.0, CannonFx::QuoinZ) * CmPerMeter) * Carriage);
			for (int32 T = 0; T < 4; ++T)
			{
				// The trucks roll as she moves (the hind ones turn faster: smaller).
				const double R = T < 2 ? LongK.TruckRadiusFore : LongK.TruckRadiusHind;
				const double Turn = -FMath::RadiansToDegrees(G.TruckTurn * LongK.TruckRadiusFore / R);
				Put(T < 2 ? TruckFore : TruckHind, D.Trucks[T], FTransform(FRotator(Turn, 0.0, 0.0), CannonFx::TruckOrigins[T] * CmPerMeter) * Carriage);
			}
			if (G.Mount.bHinge)
			{
				// Opened by a turn about the hinge's +x (roll: y toward z, guns.json's sense).
				const Sailing::FCannonMount& M = G.Mount;
				const FTransform Hinge = FTransform(FRotator(0.0, 0.0, G.LidDeg)) * CannonFx::FrameOf(M.HingeOrigin, M.HingeX, M.HingeY, M.HingeZ);
				if (Lids.IsValidIndex(I) && Lids[I]) Lids[I]->SetRelativeTransform(Hinge);
				else Put(Lid, D.Lid, Hinge);
			}
		}
		else
		{
			Put(CarrSlide, D.Slide, PortFrame(G, G.Mount.SlideX, 0.0));
			const FTransform Bed = PortFrame(G, G.X, CarrK.CarriageZ);
			Put(CarrBed, D.Bed, Bed);
			Put(CarrBarrel, D.Barrel, FTransform(FRotator(G.ElevationDeg, 0.0, 0.0), FVector(CarrK.BarrelPivot.X, CarrK.BarrelPivot.Y, CarrK.BarrelPivot.Z) * CmPerMeter) * Bed);
		}
		// The gear for the pose nearest: housed against the sill, run out, or run in (recoiled) for loading.
		if (Gear.IsValidIndex(I) && Gear[I])
		{
			const bool bLong = G.Mount.Kind == Sailing::ECannonKind::Long24;
			const double Mid = 0.5 * (G.Mount.RunInX + G.Mount.RunOutX);
			const int32 Pose = bLong && G.ElevationDeg > 0.5 * G.Mount.HousedElevationDeg ? 0 : (G.X > Mid ? 2 : 1);
			if (Pose != D.GearPose && GearMeshes[I * 3 + Pose])
			{
				Gear[I]->SetStaticMesh(GearMeshes[I * 3 + Pose]);
				D.GearPose = Pose;
			}
		}
	}
	for (int32 P = 0; P < PartCount; ++P) if (bDirty[P]) PartISMs[P]->MarkRenderStateDirty();
}

FVector ACannonBattery::ShipToWorld(const Sailing::Vec3& P) const
{
	return Root->GetComponentTransform().TransformPosition(FVector(P.X, P.Y, P.Z) * CmPerMeter);
}

FVector ACannonBattery::ShipDirToWorld(const Sailing::Vec3& D) const
{
	return Root->GetComponentTransform().TransformVectorNoScale(FVector(D.X, D.Y, D.Z));
}

Sailing::Vec3 ACannonBattery::WorldToSmoke(const FVector& W) const
{
	// (As AWaterSurface's spray: world = SailingFrame::ToWorld(map) + the water actor's height.)
	const FVector M = SailingFrame::ToMapCm(GetWorld(), W);
	return Sailing::Vec3(M.X / CmPerMeter, M.Y / CmPerMeter, (M.Z - WaterZ0) / CmPerMeter);
}

FVector ACannonBattery::SmokeToWorld(const Sailing::Vec3& P) const
{
	return SailingFrame::ToWorld(GetWorld(), P.X, P.Y, P.Z) + FVector(0.0, 0.0, WaterZ0);
}

void ACannonBattery::MakeReady(Sailing::ECannonSide Side)
{
	Battery.MakeReady(Side);
	if (bBuilt) UpdateGunVisuals(true);
}

void ACannonBattery::Order(Sailing::ECannonOrder InOrder, Sailing::ECannonSide Side)
{
	Battery.Order(InOrder, Side, SimNow());
	if (bDebug) SAIL_LOG(Display, TEXT("Cannon order %d to side %d"), int32(InOrder), int32(Side));
}

void ACannonBattery::SetFireMode(Sailing::ECannonFireMode Mode)
{
	Battery.SetFireMode(Mode);
}

void ACannonBattery::RunBenchArgs(double Now)
{
	if (NextBroadside < 0.0 || Now < NextBroadside) return;
	MakeReady(BenchSide);
	Battery.SetFireMode(BenchMode);
	Battery.Order(Sailing::ECannonOrder::Fire, BenchSide, Now);
	SAIL_LOG(Display, TEXT("Cannon bench: fire at %.2f s"), Now);
	NextBroadside = BroadsideEvery > 0.0 ? Now + BroadsideEvery : -1.0;
}

void ACannonBattery::PollTuningFile(float DeltaSeconds)
{
#if !UE_BUILD_SHIPPING
	TuneCheckT -= DeltaSeconds;
	if (TuneCheckT > 0.0) return;
	TuneCheckT = 1.0;
	const FString Path = FPaths::ProjectSavedDir() / TEXT("CannonFx.txt");
	const FDateTime Stamp = IFileManager::Get().GetTimeStamp(*Path);
	if (Stamp == FDateTime::MinValue() || Stamp == TuneStamp) return;
	TuneStamp = Stamp;
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path)) return;
	// The file over the command line's over the defaults, each time it changes.
	Params = Sailing::FCannonParams();
	if (!CommandLineTuning.IsEmpty()) ApplyTuning(CommandLineTuning);
	FString Unknown;
	const int32 N = ApplyTuning(Text, &Unknown);
	SAIL_LOG(Display, TEXT("Cannon fx: %d from %s%s%s"), N, *Path, Unknown.IsEmpty() ? TEXT("") : TEXT(", unknown: "), *Unknown);
#endif
}

void ACannonBattery::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bBuilt) return;
	const double Start = FPlatformTime::Seconds();
	if (bStage) FollowStage();
	const double Now = SimNow();
	const double Dt = LastNow < 0.0 ? 0.0 : FMath::Clamp(Now - LastNow, 0.0, 0.1);
	LastNow = Now;
	PollTuningFile(DeltaSeconds);
	RunBenchArgs(Now);
	// Gravity as the ship feels it (her heel and trim; her own accelerations are small beside it).
	const FTransform& ShipXf = Root->GetComponentTransform();
	const FVector GShip = ShipXf.InverseTransformVectorNoScale(FVector(0.0, 0.0, -9.81));
	// Her velocity (the smoke starts with the muzzle's), from how far she moved.
	const FVector ShipWorld = ShipXf.GetLocation();
	FVector ShipVel = FVector::ZeroVector;
	if (bHaveLastShip && Dt > 0.0) ShipVel = (ShipWorld - LastShipWorld) / CmPerMeter / Dt;
	if (ShipVel.Size() > 30.0) ShipVel = FVector::ZeroVector;   // a re-centre or a teleport, not her speed
	LastShipWorld = ShipWorld;
	bHaveLastShip = true;
	if (Dt > 0.0)
	{
		Battery.Step({ Dt, Now, Sailing::Vec3(GShip.X, GShip.Y, GShip.Z) });
		const Sailing::FCannonKindSpec* Specs[2] = { &Battery.Spec(Sailing::ECannonKind::Long24), &Battery.Spec(Sailing::ECannonKind::Carronade32) };
		for (const Sailing::FCannonShot& S : Battery.Shots())
		{
			const Sailing::FGun& G = Battery.Guns()[size_t(S.Gun)];
			const Sailing::FCannonKindSpec& K = *Specs[G.Mount.Kind == Sailing::ECannonKind::Long24 ? 0 : 1];
			const FVector MuzzleW = ShipToWorld(S.MuzzleShip);
			const FVector BoreW = ShipDirToWorld(S.BoreShip);
			const FVector VentW = ShipToWorld(G.BarrelToShip(K.Vent, K));
			if (!bNoSmoke)
			{
				Smoke.EmitShot(WorldToSmoke(MuzzleW), Sailing::Vec3(BoreW.X, BoreW.Y, BoreW.Z), WorldToSmoke(VentW), Sailing::Vec3(ShipVel.X, ShipVel.Y, ShipVel.Z),
					S.ChargeKg, S.bMisfire, Now, G.Mount.Kind == Sailing::ECannonKind::Long24);
			}
			FCannonFiredEvent E;
			E.Gun = S.Gun;
			E.Kind = G.Mount.Kind;
			E.Side = G.Mount.Side;
			E.MuzzleWorld = MuzzleW;
			E.BoreWorld = BoreW;
			E.ChargeKg = S.ChargeKg;
			E.ImpulseNs = S.ImpulseNs;
			E.bMisfire = S.bMisfire;
			OnGunFired.Broadcast(E);
			if (bDebug) SAIL_LOG(Display, TEXT("Cannon %hs %s at %.2f s"), G.Mount.Id, S.bMisfire ? TEXT("flashed in the pan") : TEXT("fired"), Now);
		}
		CannonFx::FGameCannonWorld SmokeWorld;
		if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
		{
			SmokeWorld.Wind = &GM->GetWind();
			SmokeWorld.Waves = &GM->GetWaves();
		}
		Smoke.Step(Dt, Now, SmokeWorld);
	}
	UpdateGunVisuals(false);
	const APlayerCameraManager* CamMgr = UGameplayStatics::GetPlayerCameraManager(this, 0);
	const FVector Cam = CamMgr ? CamMgr->GetCameraLocation() : GetActorLocation();
	UpdateSmokeVisuals(Cam);
	UpdateFlashVisuals(Cam, Now);
	UpdateLights(Now);
	PuffsAlive = int32(Smoke.Puffs().size());
	CpuSeconds += FPlatformTime::Seconds() - Start;
}

FVector ACannonBattery::SunDirection()
{
	// Toward the sun (the atmosphere's light 0), looked up once a second; straight up without one.
	const double T = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (T >= SunCheckT)
	{
		SunCheckT = T + 1.0;
		SunToward = FVector::UpVector;
		for (TObjectIterator<UDirectionalLightComponent> It; It; ++It)
		{
			if (It->GetWorld() != GetWorld() || !It->IsUsedAsAtmosphereSunLight() || It->GetAtmosphereSunLightIndex() != 0) continue;
			SunToward = -It->GetForwardVector();
			break;
		}
	}
	return SunToward;
}

void ACannonBattery::UpdateSmokeVisuals(const FVector& Cam)
{
	const std::vector<Sailing::FSmokePuff>& Puffs = Smoke.Puffs();
	const int32 N = FMath::Min(int32(Puffs.size()), SmokePool);
	// Back to front: the translucent quads of one component draw in instance order.
	SmokeOrder.SetNum(N);
	TArray<double> Dist2;
	Dist2.SetNumUninitialized(N);
	TArray<FVector> At;
	At.SetNumUninitialized(N);
	for (int32 I = 0; I < N; ++I)
	{
		SmokeOrder[I] = I;
		At[I] = SmokeToWorld(Puffs[size_t(I)].P);
		Dist2[I] = FVector::DistSquared(At[I], Cam);
	}
	SmokeOrder.Sort([&Dist2](int32 A, int32 B) { return Dist2[A] > Dist2[B]; });
	// The cloud's own shadow: each puff's sunlight through the smoke between it and the sun, marched through a coarse grid
	// of the puffs' mass (a broadside's bank is lit on its sunward face and grey within, not one flat wall).
	const FVector ToSun = SunDirection();
	const double CellM = 4.0;
	TMap<FIntVector, double> CellMass;
	CellMass.Reserve(N);
	auto CellOf = [CellM](const Sailing::Vec3& P) { return FIntVector(FMath::FloorToInt(P.X / CellM), FMath::FloorToInt(P.Y / CellM), FMath::FloorToInt(P.Z / CellM)); };
	for (int32 I = 0; I < N; ++I) CellMass.FindOrAdd(CellOf(Puffs[size_t(I)].P)) += Puffs[size_t(I)].MassKg;
	TArray<float> SunT;
	SunT.SetNumUninitialized(N);
	const double PerCell = Params.SmokeExtinction / (CellM * CellM);   // tau of a cell's mass crossed over one cell length
	for (int32 I = 0; I < N; ++I)
	{
		const Sailing::FSmokePuff& S = Puffs[size_t(I)];
		double Tau = 0.0;
		for (int32 Step = 1; Step <= 10; ++Step)
		{
			const double Along = S.Sigma + Step * CellM;
			const Sailing::Vec3 Q(S.P.X + ToSun.X * Along, S.P.Y + ToSun.Y * Along, S.P.Z + ToSun.Z * Along);
			if (const double* M = CellMass.Find(CellOf(Q))) Tau += *M * PerCell;
		}
		SunT[I] = float(FMath::Exp(-Tau));
	}
	TArray<FTransform> Xf;
	Xf.SetNumUninitialized(SmokePool);
	float Data[5];
	for (int32 K = 0; K < SmokePool; ++K)
	{
		if (K >= N)
		{
			Xf[K] = FTransform(FQuat::Identity, Cam, FVector::ZeroVector);
			continue;
		}
		const int32 I = SmokeOrder[K];
		const Sailing::FSmokePuff& S = Puffs[size_t(I)];
		const FVector W = At[I];
		const FVector ToCam = Cam - W;
		const double DistM = ToCam.Size() / CmPerMeter;
		const FVector Nrm = ToCam.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		// Tilted a little by its seed (and slowly with age) so the puffs' texture doesn't line up; only a little, because the
		// atlas's G is lit from above (T_CannonSmoke's top is the sunward side).
		const double Spin = (S.Seed - 0.5) * 0.7 + 0.1 * FMath::Sin(0.05 * S.Age + 6.0 * S.Seed);
		FVector Side = FVector::CrossProduct(Nrm, FVector::UpVector).GetSafeNormal(UE_SMALL_NUMBER, FVector::RightVector);
		const FVector Up = FVector::CrossProduct(Side, Nrm);
		const FVector X = Side * FMath::Cos(Spin) + Up * FMath::Sin(Spin);
		const FVector Y = FVector::CrossProduct(Nrm, X);
		const FQuat Q = FMatrix(X, Y, Nrm, FVector::ZeroVector).ToQuat();
		// The quad spans +-2.5 sigma (the material's falloff is the Gaussian's); a puff the camera is in fades out rather
		// than covering the screen.
		const double Width = 5.0 * S.Sigma;
		const double NearFade = FMath::SmoothStep(0.3 * S.Sigma, 1.5 * S.Sigma, DistM);
		Xf[K] = FTransform(Q, W, FVector(Width, Width, 1.0));
		Data[0] = float(S.Opacity(Params) * NearFade);
		Data[1] = float(S.Glow);
		Data[2] = S.Seed;
		Data[3] = float(FMath::Exp(-S.Age / 6.0));   // fresh smoke: denser, billowing; old: smooth haze
		Data[4] = SunT[I];
		SmokeISM->SetCustomData(K, MakeArrayView(Data, 5), false);
	}
	SmokeISM->BatchUpdateInstancesTransforms(0, Xf, true, true, true);
}

void ACannonBattery::UpdateFlashVisuals(const FVector& Cam, double Now)
{
	TArray<FTransform> Xf;
	Xf.Init(FTransform(FQuat::Identity, Cam, FVector::ZeroVector), FlashPool);
	TArray<float> Data;
	Data.SetNumZeroed(FlashPool * 4);
	int32 K = 0;
	// An axial quad: along Dir, turned to face the camera as far as it can.
	auto Axial = [&](const FVector& From, const FVector& Dir, double LengthCm, double WidthCm, float Intensity, float Kind, float Seed, float Age)
	{
		if (K >= FlashPool) return;
		const FVector Centre = From + Dir * (0.5 * LengthCm);
		const FVector ToCam = (Cam - Centre).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		FVector Nrm = ToCam - FVector::DotProduct(ToCam, Dir) * Dir;
		Nrm = Nrm.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Y = FVector::CrossProduct(Nrm, Dir);
		Xf[K] = FTransform(FMatrix(Dir, Y, Nrm, FVector::ZeroVector).ToQuat(), Centre, FVector(LengthCm / CmPerMeter, WidthCm / CmPerMeter, 1.0));
		Data[K * 4 + 0] = Intensity; Data[K * 4 + 1] = Kind; Data[K * 4 + 2] = Seed; Data[K * 4 + 3] = Age;
		++K;
	};
	auto Facing = [&](const FVector& At, double SizeCm, float Intensity, float Kind, float Seed, float Age)
	{
		if (K >= FlashPool) return;
		const FVector Nrm = (Cam - At).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector X = FVector::CrossProduct(FVector::UpVector, Nrm).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
		const FVector Y = FVector::CrossProduct(Nrm, X);
		Xf[K] = FTransform(FMatrix(X, Y, Nrm, FVector::ZeroVector).ToQuat(), At, FVector(SizeCm / CmPerMeter, SizeCm / CmPerMeter, 1.0));
		Data[K * 4 + 0] = Intensity; Data[K * 4 + 1] = Kind; Data[K * 4 + 2] = Seed; Data[K * 4 + 3] = Age;
		++K;
	};
	int32 Index = 0;
	for (const Sailing::FCannonFlash& F : Smoke.Flashes())
	{
		const float I = float(F.Intensity(Now));
		const float Age = float(FMath::Clamp((Now - F.Start) / FMath::Max(F.Life, 1e-6), 0.0, 1.0));
		const float Seed = FMath::Frac(float(Index++) * 0.618034f + float(F.Start) * 7.31f);
		if (I <= 0.f) continue;
		const FVector P = SmokeToWorld(F.P);
		const FVector D = FVector(F.Dir.X, F.Dir.Y, F.Dir.Z).GetSafeNormal();
		const double L = F.LengthM * CmPerMeter;
		if (F.bPan)
		{
			// Kind 2: the pan's spurt of flame, up off the lock.
			Axial(P, FVector::UpVector, L, 0.6 * L, I, 2.f, Seed, Age);
			continue;
		}
		// Kind 0: the flame out of the muzzle (its body grows then thins); kind 3: the round bloom at the mouth.
		Axial(P, D, L * (0.6 + 0.4 * Age), 0.5 * L, I, 0.f, Seed, Age);
		Facing(P + D * (0.15 * L), 0.9 * L, I, 3.f, Seed, Age);
	}
	for (const Sailing::FCannonSpark& S : Smoke.Sparks())
	{
		// Kind 1: a burning grain, streaked along its motion over a 30th of a second.
		const FVector P = SmokeToWorld(S.P);
		const FVector V(S.V.X, S.V.Y, S.V.Z);
		const double Streak = FMath::Max(V.Size() * CmPerMeter / 30.0, 8.0);
		const float Life = float(FMath::Clamp(S.Age / FMath::Max(S.Life, 1e-6), 0.0, 1.0));
		Axial(P, V.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector), Streak, 3.0, 1.f - Life, 1.f, 0.f, Life);
	}
	for (int32 I = 0; I < FlashPool; ++I) FlashISM->SetCustomData(I, MakeArrayView(Data.GetData() + I * 4, 4), false);
	FlashISM->BatchUpdateInstancesTransforms(0, Xf, true, true, true);
}

void ACannonBattery::UpdateLights(double Now)
{
	if (Lights.Num() == 0) return;
	// The brightest flames get the lights (a broadside's flashes overlap: each light stands for those near it).
	TArray<TPair<double, const Sailing::FCannonFlash*>> Lit;
	for (const Sailing::FCannonFlash& F : Smoke.Flashes())
	{
		const double I = F.Intensity(Now);
		if (I > 0.01 && !F.bPan) Lit.Add({ I, &F });
	}
	Lit.Sort([](const TPair<double, const Sailing::FCannonFlash*>& A, const TPair<double, const Sailing::FCannonFlash*>& B) { return A.Key > B.Key; });
	for (int32 L = 0; L < Lights.Num(); ++L)
	{
		UPointLightComponent* Light = Lights[L];
		if (L >= Lit.Num()) { if (Light->IsVisible()) Light->SetVisibility(false); continue; }
		const Sailing::FCannonFlash& F = *Lit[L].Value;
		const FVector P = SmokeToWorld(F.P + F.Dir * (0.4 * F.LengthM));
		// More flames than lights: the light carries its share of the rest.
		const double Share = double(Lit.Num()) / double(Lights.Num());
		Light->SetWorldLocation(P);
		// (Real candela into the scene's units: exposure runs SceneEVOffset stops under the real EV, as the night lights.)
		Light->SetIntensity(float(Params.FlashLightCd * FMath::Pow(2.0, -SceneEVOffset()) * Lit[L].Key * FMath::Min(Share, 4.0)));
		Light->SetAttenuationRadius(float(Params.FlashLightRadiusM * CmPerMeter));
		if (!Light->IsVisible()) Light->SetVisibility(true);
	}
}

#if !UE_BUILD_SHIPPING
namespace
{
	// sailing.Broadside [port|starboard|both] [broadside|ripple|atwill]: every gun on the side ready at once, then fire.
	FAutoConsoleCommandWithWorldAndArgs CannonBroadsideCmd(TEXT("sailing.Broadside"),
		TEXT("Run out every gun on a side and fire: sailing.Broadside [port|starboard|both] [broadside|ripple|atwill] (docs/cannon-fire/)"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			ACannonBattery* B = CannonFx::FirstBattery(World);
			if (!B) B = ACannonBattery::SpawnStageIfAsked(World);
			if (!B) { SAIL_LOG(Warning, TEXT("sailing.Broadside: no battery (start with -SailingCannonStage, or sail the frigate)")); return; }
			Sailing::ECannonSide Side = Sailing::ECannonSide::Starboard;
			Sailing::ECannonFireMode Mode = Sailing::ECannonFireMode::Broadside;
			if (Args.Num() > 0) CannonFx::ParseSide(Args[0], Side);
			if (Args.Num() > 1) CannonFx::ParseMode(Args[1], Mode);
			B->MakeReady(Side);
			B->SetFireMode(Mode);
			B->Order(Sailing::ECannonOrder::Fire, Side);
		}));

	// sailing.CannonOrder <CastLoose|Load|RunOut|Fire|CeaseFire|Secure> [port|starboard|both]: an order as the panel gives it.
	FAutoConsoleCommandWithWorldAndArgs CannonOrderCmd(TEXT("sailing.CannonOrder"),
		TEXT("Give the guns an order: sailing.CannonOrder <CastLoose|Load|RunOut|Fire|CeaseFire|Secure> [port|starboard|both]"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			ACannonBattery* B = CannonFx::FirstBattery(World);
			Sailing::ECannonOrder O;
			if (!B || Args.Num() < 1 || !CannonFx::ParseOrder(Args[0], O)) { SAIL_LOG(Warning, TEXT("sailing.CannonOrder: no battery, or an unknown order")); return; }
			Sailing::ECannonSide Side = Sailing::ECannonSide::Both;
			if (Args.Num() > 1) CannonFx::ParseSide(Args[1], Side);
			B->Order(O, Side);
		}));

	// sailing.CannonFx [Key Value]: set a tuning knob live, or (no arguments) write every knob to Saved/CannonFx.dump.txt.
	FAutoConsoleCommandWithWorldAndArgs CannonFxCmd(TEXT("sailing.CannonFx"),
		TEXT("Tune the cannon effects: sailing.CannonFx Key Value, or no arguments to dump every knob to Saved/CannonFx.dump.txt"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			ACannonBattery* B = CannonFx::FirstBattery(World);
			if (!B) { SAIL_LOG(Warning, TEXT("sailing.CannonFx: no battery")); return; }
			if (Args.Num() >= 2)
			{
				FString Unknown;
				B->ApplyTuning(Args[0] + TEXT("=") + Args[1], &Unknown);
				if (!Unknown.IsEmpty()) SAIL_LOG(Warning, TEXT("sailing.CannonFx: unknown %s"), *Unknown);
				return;
			}
			const FString Path = FPaths::ProjectSavedDir() / TEXT("CannonFx.dump.txt");
			FFileHelper::SaveStringToFile(B->DumpTuning(), *Path);
			SAIL_LOG(Display, TEXT("Cannon fx written to %s"), *Path);
		}));
}
#endif
