// Walking a ship (docs/ship-walk/): the On deck view. The walker (Sailing::FShipWalker) lives in the ship's frame on the
// baked walk map; this file loads the map, feeds the walker the player's keys and the felt gravity, puts the camera at
// his eye, lets her helmsman hold the course while you walk, and streams the decks below as you go down to them.
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "CannonBattery.h"
#include "SailingSettings.h"
#include "SailingBindings.h"
#include "BenchRunner.h"
#include "UI/SailUIStyle.h"
#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/StreamableManager.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "InputTriggers.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace ShipWalkGame
{
	/** Seconds a deck below stays loaded after nobody wants it (a walker stepping back and forth at a ladder). */
	constexpr double DeckUnloadDelay = 10.0;
	/** The share of her heel and pitch the eye leans with (a sailor's head stays nearly upright: the cockpit's third). */
	constexpr double EyeLean = 0.33;

	/** A file name from a boat's name: letters and digits only ("Commonwealth"). */
	FString FileStem(const FString& Name)
	{
		FString Out;
		for (TCHAR C : Name) if (FChar::IsAlnum(C)) Out.AppendChar(C);
		return Out;
	}

	/** The folder her exported meshes are in, by her walk map's name (docs/ship-walk/: the export's paths). */
	FString ModelFolder(const FString& Ship)
	{
		if (Ship == TEXT("Commonwealth")) return TEXT("Frigate");
		return Ship;
	}

	/** A deck's mesh: /Game/Boats/<Folder>/Decks/SM_<Folder>_<GunDeck|BerthDeck|Orlop|Hold>; none for the spar deck (the
	 *  outside model is it) or where the asset isn't in the project yet. */
	FSoftObjectPath DeckMeshPath(const FString& Ship, const std::string& Deck)
	{
		const FString Name = UTF8_TO_TCHAR(Deck.c_str());
		FString Part;
		if (Name == TEXT("Gun") || Name == TEXT("Berth")) Part = Name + TEXT("Deck");
		else if (Name == TEXT("Orlop") || Name == TEXT("Hold")) Part = Name;
		else return FSoftObjectPath();
		const FString Folder = ModelFolder(Ship);
		const FString Asset = FString::Printf(TEXT("SM_%s_%s"), *Folder, *Part);
		const FString Package = FString::Printf(TEXT("/Game/Boats/%s/Decks/%s"), *Folder, *Asset);
		if (!FPackageName::DoesPackageExist(Package)) return FSoftObjectPath();
		return FSoftObjectPath(Package + TEXT(".") + Asset);
	}

	/** "gun deck", "orlop": a deck as the prompt names it. */
	FString DeckLabel(const std::string& Deck)
	{
		const FString Name = UTF8_TO_TCHAR(Deck.c_str());
		if (Name == TEXT("Orlop") || Name == TEXT("Hold")) return Name.ToLower();
		return Name.ToLower() + TEXT(" deck");
	}
}

void ASailboatPawn::ClearDeckMeshes()
{
	for (UStaticMeshComponent* Mesh : DeckMeshes) if (Mesh) Mesh->DestroyComponent();
	for (TSharedPtr<FStreamableHandle>& Load : DeckLoads) if (Load.IsValid()) Load->ReleaseHandle();
	DeckMeshes.Reset();
	DeckLoads.Reset();
	DeckUnwantedSince.Reset();
	DeckMeshPaths.Reset();
}

void ASailboatPawn::LoadWalkMap()
{
	if (bTrafficBoat || bGhost)
	{
		return;
	}
	// -SailingWalkMap=<name> puts a map on any boat (the tests); otherwise her own, by her name or her type's.
	TArray<FString> Candidates;
	FString Forced;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingWalkMap="), Forced) && !Forced.IsEmpty()) Candidates.Add(ShipWalkGame::FileStem(Forced));
	else
	{
		Candidates.Add(ShipWalkGame::FileStem(UTF8_TO_TCHAR(Boat.GetConfig().Name)));
		Candidates.AddUnique(ShipWalkGame::FileStem(UTF8_TO_TCHAR(Sailing::BoatTypeName(Boat.GetConfig().Type))));
	}
	for (const FString& Name : Candidates)
	{
		if (Name.IsEmpty()) continue;
		if (Name == WalkMapName && WalkMap.IsLoaded()) return;   // the same ship again (a rebuild of her visuals)
		const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Ships") / (Name + TEXT(".walk"));
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent)) continue;
		Sailing::FWalkMap Map;
		std::string Error;
		if (!Map.Parse(Bytes.GetData(), size_t(Bytes.Num()), &Error))
		{
			SAIL_LOG(Warning, TEXT("Walk map %s refused: %hs"), *Path, Error.c_str());
			continue;
		}
		ClearDeckMeshes();
		WalkMap = MoveTemp(Map);
		WalkMapName = Name;
		const int32 N = int32(WalkMap.Decks.size());
		for (int32 K = 0; K < N; ++K) DeckMeshPaths.Add(ShipWalkGame::DeckMeshPath(Name, WalkMap.Decks[K].Name));
		DeckMeshes.SetNum(N);
		DeckLoads.SetNum(N);
		DeckUnwantedSince.Init(-1.0, N);
		SAIL_LOG(Log, TEXT("Walk map %s: %d decks, %d ladders, %d spots"), *Name, N, int32(WalkMap.Links.size()), int32(WalkMap.Spots.size()));
		PlaceWalkerAtHelm();
		return;
	}
	// No map for this boat: off the decks (a swap from the ship to a dinghy while walking).
	const bool bWasWalking = bWalking;
	ClearDeckMeshes();
	WalkMap = Sailing::FWalkMap();
	WalkMapName.Reset();
	bWalking = false;
	bShipHelmsman = false;
	ShipOrders.Close();
	if (bWasWalking) ApplyMappingContexts();
}

void ASailboatPawn::PlaceWalkerAtHelm()
{
	if (!CanWalk()) return;
	if (const Sailing::FWalkSpot* Helm = WalkMap.SpotNamed("Helm"))
	{
		if (Walker.Reset(WalkMap, Helm->Deck, Helm->X, Helm->Y, Helm->YawDeg)) return;
	}
	// A map without the spot: on the top deck a fifth of her length forward of her stern, facing forward.
	const Sailing::FHullShape& H = Boat.GetConfig().Hulls[0];
	Walker.Reset(WalkMap, 0, H.SternX + 0.2 * (H.BowX - H.SternX), 0.0, 0.0);
}

void ASailboatPawn::SetWalking(bool bOn, bool bAnnounce)
{
	if (bOn && (!CanWalk() || bTrafficBoat || bGhost)) return;
	if (bOn == bWalking) return;
	if (bOn && !bCockpit) SetCockpitView(true, false);
	bWalking = bOn;
	for (const FName Axis : { FName(TEXT("WalkForward")), FName(TEXT("WalkRight")), FName(TEXT("WalkRun")), FName(TEXT("WalkCrouch")) }) HeldAxes.FindOrAdd(Axis) = 0.f;
	WalkLook = FVector2D::ZeroVector;
	bWalkUsePending = false;
	if (bOn)
	{
		// From the wheel: you set off the way you were looking; her helmsman takes her at the wind angle she had.
		const Sailing::Vec3 Feet = Walker.GetFeet();
		Walker.Reset(WalkMap, Walker.GetDeck(), Feet.X, Feet.Y, Walker.GetYawDeg() + CameraYaw);
		if (!bShipHelmsman) ShipHelmsmanTakes();
	}
	else
	{
		// Back at the wheel, you steer.
		bShipHelmsman = false;
		PlaceWalkerAtHelm();
		CameraYaw = 0.f;
		CameraPitch = -8.f;
	}
	ApplyMappingContexts();
	if (!bAnnounce || SailUI::UiMode() == SailUI::EUiMode::Off) return;
	const bool bPad = SailUI::UsingGamepad();
	if (bOn)
	{
		StatusMessage = SailUI::UiMode() == SailUI::EUiMode::Helpful
			? FString::Printf(TEXT("On deck: %s to walk, %s for a ladder, %s back to the wheel. The helmsman holds her %.0f degrees off the wind"),
				*SailingBindings::Label(TEXT("WalkForward"), false, bPad), *SailingBindings::Label(TEXT("WalkUse"), false, bPad),
				*SailingBindings::Label(TEXT("WalkToHelm"), false, bPad), FMath::Abs(WalkPilot.TargetTWADeg))
			: FString(TEXT("On deck"));
	}
	else
	{
		StatusMessage = TEXT("At the wheel");
	}
	StatusUntil = Boat.GetState().Time + (SailUI::UiMode() == SailUI::EUiMode::Helpful ? 6.0 : 2.0);
}

Sailing::Vec3 ASailboatPawn::FeltGravityShip() const
{
	// The world's gravity in her frame, less her acceleration where the walker stands (the crew's felt gravity, C1).
	const Sailing::FBoatState& S = Boat.GetState();
	const Sailing::FBoatTelemetry& T = Boat.GetTelemetry();
	const Sailing::Vec3 G = S.Orientation.Unrotate(Sailing::Vec3(0.0, 0.0, -Sailing::kGravity));
	const Sailing::Vec3 R = Walker.GetFeet() - Boat.GetCenterOfGravity();
	const Sailing::Vec3& W = S.AngularVelocity;
	const Sailing::Vec3 A = T.AccelBody + T.AngularAccelBody.Cross(R) + W.Cross(W.Cross(R));
	return G - A;
}

void ASailboatPawn::UpdateWalk(float DeltaSeconds)
{
	if (!bWalking)
	{
		// The Helm view: you stand at the wheel (the walker waits there), the look is the cockpit's.
		WalkLook = FVector2D::ZeroVector;
		return;
	}
	Sailing::FWalkInput In;
	if (!bMenuOpen && !bPhoto)
	{
		In.Forward = FMath::Clamp(HeldAxes.FindRef(TEXT("WalkForward")), -1.f, 1.f);
		In.Right = FMath::Clamp(HeldAxes.FindRef(TEXT("WalkRight")), -1.f, 1.f);
		In.bRun = HeldAxes.FindRef(TEXT("WalkRun")) > 0.5f;
		In.bCrouch = HeldAxes.FindRef(TEXT("WalkCrouch")) > 0.5f;
		In.LookYawDeg = WalkLook.X;
		In.LookPitchDeg = WalkLook.Y;
		In.bUse = bWalkUsePending;
	}
	WalkLook = FVector2D::ZeroVector;
	bWalkUsePending = false;
	Walker.Step(WalkMap, In, FeltGravityShip(), bPhoto ? 0.0 : double(DeltaSeconds));

	// The ladder's prompt on the status line while one is in reach (Settings > Interface: none when Off).
	const FString Prompt = GetWalkPrompt();
	if (!Prompt.IsEmpty())
	{
		StatusMessage = Prompt;
		StatusUntil = Boat.GetState().Time + 0.3;
	}
	WalkPromptShown = Prompt;
}

FString ASailboatPawn::GetWalkPrompt() const
{
	if (!bWalking || SailUI::UiMode() == SailUI::EUiMode::Off) return FString();
	const int32 K = Walker.LinkInReach(WalkMap);
	if (K < 0) return FString();
	const Sailing::FWalkLink& L = WalkMap.Links[K];
	const bool bDown = L.Upper == Walker.GetDeck();
	const FString Key = SailingBindings::Label(TEXT("WalkUse"), false, SailUI::UsingGamepad());
	if (SailUI::UiMode() == SailUI::EUiMode::Natural) return FString::Printf(TEXT("%s: ladder %s"), *Key, bDown ? TEXT("down") : TEXT("up"));
	return FString::Printf(TEXT("%s: take the ladder %s to the %s"), *Key, bDown ? TEXT("down") : TEXT("up"),
		*ShipWalkGame::DeckLabel(WalkMap.Decks[bDown ? L.Lower : L.Upper].Name));
}

void ASailboatPawn::UpdateWalkCamera(float DeltaSeconds)
{
	if (!Camera || !BoatRoot) return;
	// The eye in her frame (metres) to the world through her transform; the head leans a third of her heel and pitch, as
	// the cockpit's does, and turns on its own: the walker's look on deck, the cockpit's at the wheel.
	const Sailing::Vec3 Eye = Walker.GetEye();
	const FTransform BoatXf = BoatRoot->GetComponentTransform();
	const FVector World = BoatXf.TransformPosition(FVector(Eye.X, Eye.Y, Eye.Z) * Sailing::CmPerMeter);
	const FRotator Hull = BoatXf.Rotator();
	const FRotator Leaned(Hull.Pitch * ShipWalkGame::EyeLean, Hull.Yaw, Hull.Roll * ShipWalkGame::EyeLean);
	const FRotator Look = bWalking
		? FRotator(float(Walker.GetPitchDeg()), float(Walker.GetYawDeg()), 0.f)
		: FRotator(FMath::Clamp(CameraPitch, -75.f, 30.f), float(Walker.GetYawDeg()) + (bDemo ? 0.f : CameraYaw), 0.f);
	Camera->SetWorldLocationAndRotation(World, (FQuat(Leaned) * FQuat(Look)).Rotator());
	Camera->SetFieldOfView(USailingSettings::Get()->ChaseFov() - 10.f);   // as aboard any boat: 10 deg narrower
}

uint32 ASailboatPawn::GetDecksShown() const
{
	uint32 Shown = 0;
	for (int32 K = 0; K < DeckMeshes.Num() && K < 32; ++K) if (DeckMeshes[K] && DeckMeshes[K]->GetStaticMesh()) Shown |= 1u << K;
	return Shown;
}

void ASailboatPawn::UpdateDeckStreaming()
{
	const int32 N = DeckMeshPaths.Num();
	if (!CanWalk() || N == 0 || DeckMeshes.Num() != N || DeckLoads.Num() != N || DeckUnwantedSince.Num() != N) return;
	// Aboard (at the wheel or walking): the decks the walker wants (his, a ladder's other end, what shows through the
	// hatches). Outside: what her top deck shows (the gun deck through the open waist).
	const uint32 Want = bCockpit ? Walker.DecksWanted(WalkMap) : WalkMap.Decks[0].AlsoLoad;
	const double Now = FPlatformTime::Seconds();
	for (int32 K = 0; K < N && K < 32; ++K)
	{
		if (DeckMeshPaths[K].IsNull()) continue;
		if (Want & (1u << K))
		{
			DeckUnwantedSince[K] = -1.0;
			if (DeckMeshes[K]) continue;
			if (!DeckLoads[K].IsValid()) DeckLoads[K] = UAssetManager::GetStreamableManager().RequestAsyncLoad(DeckMeshPaths[K]);
			if (!DeckLoads[K].IsValid() || !DeckLoads[K]->HasLoadCompleted()) continue;
			UStaticMesh* Mesh = Cast<UStaticMesh>(DeckLoads[K]->GetLoadedAsset());
			if (!Mesh)
			{
				SAIL_LOG(Warning, TEXT("Deck mesh %s did not load"), *DeckMeshPaths[K].ToString());
				DeckMeshPaths[K].Reset();
				continue;
			}
			// In her frame like the outside model's parts (BoatRoot, no offset), drawn and shadowed, no collision.
			UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
			Part->SetupAttachment(BoatRoot.Get());
			Part->SetStaticMesh(Mesh);
			Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Part->SetCanEverAffectNavigation(false);
			Part->RegisterComponent();
			DeckMeshes[K] = Part;
		}
		else if (DeckMeshes[K] || DeckLoads[K].IsValid())
		{
			if (DeckUnwantedSince[K] < 0.0) DeckUnwantedSince[K] = Now;
			else if (Now - DeckUnwantedSince[K] > ShipWalkGame::DeckUnloadDelay)
			{
				if (DeckMeshes[K]) DeckMeshes[K]->DestroyComponent();
				DeckMeshes[K] = nullptr;
				if (DeckLoads[K].IsValid()) DeckLoads[K]->ReleaseHandle();
				DeckLoads[K].Reset();
				DeckUnwantedSince[K] = -1.0;
			}
		}
	}
}

bool ASailboatPawn::OnWalkButton(FName Action)
{
	if (Action == TEXT("WalkUse"))
	{
		bWalkUsePending = true;
		return true;
	}
	if (Action == TEXT("WalkToHelm"))
	{
		SetWalking(false);
		return true;
	}
	return false;
}

UInputMappingContext* ASailboatPawn::BuildWalkContext(UObject* Outer, FName Name, const TArray<FSailingKeyBinding>& Bindings,
	const TMap<FName, TObjectPtr<UInputAction>>& InActions)
{
	// The walking keys alone (SailingBindings::InWalkContext), above the boat's context while you walk: the menu, the
	// view, the look and the controls card stay the boat context's.
	return BuildLayerContext(Outer, Name, Bindings, InActions, &SailingBindings::InWalkContext);
}

UInputMappingContext* ASailboatPawn::BuildLayerContext(UObject* Outer, FName Name, const TArray<FSailingKeyBinding>& Bindings,
	const TMap<FName, TObjectPtr<UInputAction>>& InActions, bool (*InLayer)(const FSailingKeyBinding&))
{
	UInputMappingContext* Context = NewObject<UInputMappingContext>(Outer, MakeUniqueObjectName(Outer, UInputMappingContext::StaticClass(), Name));
	for (const FSailingKeyBinding& Binding : Bindings)
	{
		if (!InLayer || !InLayer(Binding)) continue;
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
		if (SailingBindings::IsPadAxis(Binding.Key))
		{
			// The stick's rest is not quite zero: a small dead zone, so the walker stands still with the stick let go.
			UInputModifierDeadZone* Dead = NewObject<UInputModifierDeadZone>(Context);
			Dead->LowerThreshold = 0.15f;
			Dead->UpperThreshold = 1.f;
			Dead->Type = EDeadZoneType::Axial;
			Mapping.Modifiers.Insert(Dead, 0);
		}
		const bool bButton = Binding.Action == TEXT("WalkUse") || Binding.Action == TEXT("WalkToHelm") || Binding.Action == TEXT("ShipOrders")
			|| SailingBindings::IsOrdersAction(Binding.Action);
		if (bButton) Mapping.Triggers.Add(NewObject<UInputTriggerPressed>(Context));
	}
	return Context;
}

// ---- a ship's orders (docs/ship-orders/) ------------------------------------------------------------------------------

void ASailboatPawn::ShipHelmsmanTakes()
{
	bShipHelmsman = true;
	WalkPilot = Sailing::FAutopilot();
	WalkPilot.TargetTWADeg = Boat.GetTelemetry().TrueWindAngle * Sailing::kRadToDeg;
}

Sailing::FShipOrderContext ASailboatPawn::GetShipOrderContext() const
{
	Sailing::FShipOrderContext C;
	// The square rig's sail plans are carried out (ApplySailPlan) and the guns by her battery; tacking, wearing and heaving
	// to join with the crew's manoeuvres (FShipHandling): until then their orders show, with the reason they can't yet.
	C.bSquareRig = Boat.GetConfig().HasSquareRig();
	C.bManoeuvres = false;
	C.bHasGuns = ShipBattery != nullptr;
	if (ShipBattery)
	{
		C.Guns[0] = Sailing::GunsReadyFor(ShipBattery->GetSideStatus(Sailing::ECannonSide::Port));
		C.Guns[1] = Sailing::GunsReadyFor(ShipBattery->GetSideStatus(Sailing::ECannonSide::Starboard));
		C.bFiring[0] = bShipGunsFiring[0];
		C.bFiring[1] = bShipGunsFiring[1];
	}
	C.bHelmsman = bShipHelmsman;
	C.TrueWindAngleDeg = bShipHelmsman ? WalkPilot.TargetTWADeg : Boat.GetTelemetry().TrueWindAngle * Sailing::kRadToDeg;
	return C;
}

bool ASailboatPawn::OnOrdersButton(FName Action)
{
	if (Action == TEXT("ShipOrders"))
	{
		ShipOrders.Toggle();
		ApplyMappingContexts();
		return true;
	}
	if (!ShipOrders.IsOpen() || !SailingBindings::IsOrdersAction(Action)) return false;
	if (Action == TEXT("OrdersUp")) ShipOrders.MoveRow(-1);
	else if (Action == TEXT("OrdersDown")) ShipOrders.MoveRow(1);
	else if (Action == TEXT("OrdersLeft")) ShipOrders.MoveGroup(-1);
	else if (Action == TEXT("OrdersRight")) ShipOrders.MoveGroup(1);
	else if (Action == TEXT("OrdersClose"))
	{
		ShipOrders.Close();
		ApplyMappingContexts();
	}
	else if (Action == TEXT("OrdersSelect"))
	{
		Sailing::FIssuedOrder Order;
		if (ShipOrders.Select(GetShipOrderContext(), Boat.GetState().Time, Order)) GiveShipOrder(Order);
	}
	return true;
}

void ASailboatPawn::GiveShipOrder(const Sailing::FIssuedOrder& Order)
{
	using Sailing::EShipOrder;
	switch (Order.Order)
	{
	case EShipOrder::TakeHelm:
		ShipHelmsmanTakes();
		break;
	case EShipOrder::MyHelm:
		// You take the wheel: from on deck that is the walk back to it.
		if (bWalking) SetWalking(false, false);
		bShipHelmsman = false;
		break;
	case EShipOrder::LuffPoint:
	case EShipOrder::BearAwayPoint:
		WalkPilot.TargetTWADeg = Sailing::HelmTargetAfter(Order.Order, WalkPilot.TargetTWADeg, GetShipOrderContext());
		break;
	case EShipOrder::MakeSail:
	case EShipOrder::FightingSail:
	case EShipOrder::ShortenSail:
	case EShipOrder::FurlAll:
		// The crew set, clew up or furl each sail at their pace (the physics' SquareOut, the model's ShipRigPose).
		Sailing::ApplySailPlan(Order.Order, Boat.GetConfig(), Controls);
		break;
	case EShipOrder::CastLoose:
	case EShipOrder::Load:
	case EShipOrder::RunOut:
	case EShipOrder::Fire:
	case EShipOrder::CeaseFire:
	case EShipOrder::Secure:
		if (ShipBattery)
		{
			// The guns' crews do the drill at their pace; a fire order keeps them firing (reload, run out, fire) until
			// cease fire or secure.
			ShipBattery->Order(Sailing::CannonOrderFor(Order.Order), Sailing::CannonSideFor(Order.Side));
			const bool bSide[2] = { Order.Side != Sailing::EOrderSide::Starboard, Order.Side != Sailing::EOrderSide::Port };
			for (int32 K = 0; K < 2; ++K)
			{
				if (!bSide[K]) continue;
				if (Order.Order == EShipOrder::Fire) bShipGunsFiring[K] = true;
				else if (Order.Order == EShipOrder::CeaseFire || Order.Order == EShipOrder::Secure) bShipGunsFiring[K] = false;
			}
		}
		break;
	default:
		// (manoeuvres: refused by GetShipOrderContext until they are wired)
		break;
	}
	// The captain's call, in every HUD mode: it is what you said.
	const Sailing::FShipOrderInfo& Info = Sailing::ShipOrderInfo(Order.Order);
	FString Call = UTF8_TO_TCHAR(Info.Call);
	if (Info.bSided && Order.Side != Sailing::EOrderSide::Both) Call = FString(UTF8_TO_TCHAR(Sailing::OrderSideName(Order.Side))) + TEXT(" side: ") + Call;
	StatusMessage = TEXT("Captain: ") + Call;
	StatusUntil = Boat.GetState().Time + 4.0;
}

FString ASailboatPawn::GetOrdersPanelText(int32 Part) const
{
	using namespace Sailing;
	if (!ShipOrders.IsOpen()) return FString();
	const EShipOrderGroup Group = ShipOrders.GetGroup();
	if (Part == 0)
	{
		// The tabs, the open one in brackets.
		FString Tabs = TEXT("ORDERS  ");
		for (int32 G = 0; G < int32(EShipOrderGroup::Count); ++G)
		{
			const FString Name = UTF8_TO_TCHAR(ShipOrderGroupName(EShipOrderGroup(G)));
			Tabs += EShipOrderGroup(G) == Group ? FString::Printf(TEXT("  [%s]"), *Name.ToUpper()) : FString::Printf(TEXT("  %s"), *Name.ToUpper());
		}
		return Tabs;
	}
	const FShipOrderContext Context = GetShipOrderContext();
	if (Part == 1)
	{
		// The rows: the chosen one marked; one that can't be ordered now in parentheses.
		TArray<FString> Lines;
		for (int32 R = 0; R < ShipOrders.NumRows(Group); ++R)
		{
			const FString Mark = R == ShipOrders.GetRow() ? TEXT("> ") : TEXT("   ");
			EShipOrder Order = EShipOrder::MakeSail;
			if (ShipOrders.IsSideRow(Group, R)) Lines.Add(Mark + TEXT("Side: ") + UTF8_TO_TCHAR(OrderSideName(ShipOrders.GetSide())));
			else if (ShipOrders.RowOrder(Group, R, Order))
			{
				const FString Label = UTF8_TO_TCHAR(ShipOrderInfo(Order).Label);
				const bool bBlocked = ShipOrderBlocked(Order, ShipOrderInfo(Order).bSided ? ShipOrders.GetSide() : EOrderSide::Both, Context) != nullptr;
				Lines.Add(Mark + (bBlocked ? TEXT("(") + Label + TEXT(")") : Label));
			}
		}
		return FString::Join(Lines, TEXT("\n"));
	}
	// The line under the rows: why the last order wasn't given, or why this one can't be, then (Helpful) what it does and
	// the keys.
	TArray<FString> Lines;
	if (!ShipOrders.GetRefusal().empty()) Lines.Add(UTF8_TO_TCHAR(ShipOrders.GetRefusal().c_str()));
	EShipOrder Order = EShipOrder::MakeSail;
	const bool bOrderRow = ShipOrders.RowOrder(Group, ShipOrders.GetRow(), Order);
	if (bOrderRow && ShipOrders.GetRefusal().empty())
	{
		if (const char* Why = ShipOrderBlocked(Order, ShipOrderInfo(Order).bSided ? ShipOrders.GetSide() : EOrderSide::Both, Context)) Lines.Add(UTF8_TO_TCHAR(Why));
	}
	if (SailUI::UiMode() == SailUI::EUiMode::Helpful)
	{
		if (bOrderRow) Lines.Add(UTF8_TO_TCHAR(ShipOrderInfo(Order).Explain));
		else Lines.Add(TEXT("Which side's guns the orders go to"));
		const bool bPad = SailUI::UsingGamepad();
		Lines.Add(FString::Printf(TEXT("%s/%s choose   %s/%s tabs   %s order   %s close"),
			*SailingBindings::Label(TEXT("OrdersUp"), false, bPad), *SailingBindings::Label(TEXT("OrdersDown"), false, bPad),
			*SailingBindings::Label(TEXT("OrdersLeft"), false, bPad), *SailingBindings::Label(TEXT("OrdersRight"), false, bPad),
			*SailingBindings::Label(TEXT("OrdersSelect"), false, bPad), *SailingBindings::Label(TEXT("OrdersClose"), false, bPad)));
	}
	return FString::Join(Lines, TEXT("\n"));
}
