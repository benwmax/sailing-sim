// Walking a ship (docs/ship-walk/): the On deck view. The walker (Sailing::FShipWalker) lives in the ship's frame on the
// baked walk map; this file loads the map, feeds the walker the player's keys and the felt gravity, puts the camera at
// his eye, lets her helmsman hold the course while you walk, and streams the decks below as you go down to them.
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "CannonBattery.h"
#include "ShipOutside.h"
#include "SailingSettings.h"
#include "SailingBindings.h"
#include "BenchRunner.h"
#include "UI/SailUIStyle.h"
#include "Camera/CameraComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
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

#include <cmath>

namespace ShipWalkGame
{
	/** Seconds a deck below stays loaded after nobody wants it (a walker stepping back and forth at a ladder). */
	constexpr double DeckUnloadDelay = 10.0;
	/** A cabin lamp: a shaded 25 W bulb of the 1930s (about 250 lm), warm, its light carrying across a cabin. */
	constexpr float LampLumens = 250.f;
	constexpr float LampKelvin = 2700.f;
	constexpr float LampReachCm = 450.f;
	/** Seconds for the eye to come to a cabin from the deck (and back). */
	constexpr float BelowAdaptSeconds = 2.5f;
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

	/** A deck's mesh: /Game/Boats/<Folder>/Decks/SM_<Folder>_<GunDeck|BerthDeck|Orlop|Hold|Below> (a yacht's cabins are
	 *  one deck, "Below": Bluebonnet's); none for the top deck (the outside model is it) or where the asset isn't in the
	 *  project yet. */
	FSoftObjectPath DeckMeshPath(const FString& Ship, const std::string& Deck)
	{
		const FString Name = UTF8_TO_TCHAR(Deck.c_str());
		FString Part;
		if (Name == TEXT("Gun") || Name == TEXT("Berth")) Part = Name + TEXT("Deck");
		else if (Name == TEXT("Orlop") || Name == TEXT("Hold") || Name == TEXT("Below")) Part = Name;
		else return FSoftObjectPath();
		const FString Folder = ModelFolder(Ship);
		const FString Asset = FString::Printf(TEXT("SM_%s_%s"), *Folder, *Part);
		const FString Package = FString::Printf(TEXT("/Game/Boats/%s/Decks/%s"), *Folder, *Asset);
		if (!FPackageName::DoesPackageExist(Package)) return FSoftObjectPath();
		return FSoftObjectPath(Package + TEXT(".") + Asset);
	}

	/** "gun deck", "orlop", "cabins": a deck as the prompt names it (Bluebonnet's are "Deck", "Cockpit" and "Below"). */
	FString DeckLabel(const std::string& Deck)
	{
		const FString Name = UTF8_TO_TCHAR(Deck.c_str());
		if (Name == TEXT("Orlop") || Name == TEXT("Hold") || Name == TEXT("Deck") || Name == TEXT("Cockpit")) return Name.ToLower();
		if (Name == TEXT("Below")) return TEXT("cabins");
		return Name.ToLower() + TEXT(" deck");
	}
}

void ASailboatPawn::ClearDeckMeshes()
{
	for (UStaticMeshComponent* Mesh : DeckMeshes) if (Mesh) Mesh->DestroyComponent();
	for (UPointLightComponent* Lamp : DeckLamps) if (Lamp) Lamp->DestroyComponent();
	DeckLamps.Reset();
	DeckLampDecks.Reset();
	for (UInstancedStaticMeshComponent* Copies : DeckCopies) if (Copies) Copies->DestroyComponent();
	DeckCopies.Reset();
	DeckCopyDecks.Reset();
	DeckCopyPaths.Reset();
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
		// Her placed copies' meshes by deck (the frigate's berth deck), loaded with the deck's mesh.
		DeckCopyPaths.SetNum(N);
		if (const ShipOutside::FDeckTable* Table = ShipOutside::DecksFor(Boat.GetConfig().Name))
		{
			for (const ShipOutside::FDeckCopy& C : Table->Copies)
			{
				const int32 K = WalkMap.DeckNamed(TCHAR_TO_UTF8(*C.Deck));
				if (K >= 0 && K < N && !DeckMeshPaths[K].IsNull()) DeckCopyPaths[K].AddUnique(FSoftObjectPath(C.Asset));
			}
		}
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
		// Abaft the wheel where the ship has one (FWalkMap::HelmAbaftWheelAxle): Commonwealth's first walk bake stood the
		// helmsman 0.7 m abaft the axle, with his eye inside the after wheel. The baked spot where that cell is no floor.
		double X = Helm->X;
		if (ShipFrames)
		{
			for (int32 K = 0; K < ShipFrames->NumFrames; ++K)
			{
				const Sailing::FShipFrame& F = ShipFrames->Frames[K];
				if (F.Kind == Sailing::EShipFrameKind::Wheel) { X = Sailing::FWalkMap::HelmStandX(Helm->X, F.Origin.X); break; }
			}
		}
		if (X != Helm->X && Walker.Reset(WalkMap, Helm->Deck, X, Helm->Y, Helm->YawDeg)) return;
		if (Walker.Reset(WalkMap, Helm->Deck, Helm->X, Helm->Y, Helm->YawDeg)) return;
	}
	// A map without the spot: on the top deck a fifth of her length forward of her stern, facing forward.
	const Sailing::FHullShape& H = Boat.GetConfig().Hulls[0];
	Walker.Reset(WalkMap, 0, H.SternX + 0.2 * (H.BowX - H.SternX), 0.0, 0.0);
}

void ASailboatPawn::ApplyWalkAt()
{
	// Stills of her decks below (docs/ship-walk/): -SailingWalkAt=Below,-2,0,0 stands you in Bluebonnet's saloon facing
	// forward. Once, a second into the sail (after the start's resets).
	if (bWalkAtDone || !CanWalk() || Boat.GetState().Time < 1.0) return;
	bWalkAtDone = true;
	FString At;
	if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingWalkAt="), At, false) || At.IsEmpty()) return;
	TArray<FString> Parts;
	At.ParseIntoArray(Parts, TEXT(","));
	const int32 Deck = Parts.Num() >= 3 ? WalkMap.DeckNamed(TCHAR_TO_UTF8(*Parts[0])) : -1;
	if (Deck < 0)
	{
		SAIL_LOG(Warning, TEXT("-SailingWalkAt=%s: want <deck>,<x>,<y>[,<yaw>] with a deck of %s's map"), *At, *WalkMapName);
		return;
	}
	const double X = FCString::Atod(*Parts[1]), Y = FCString::Atod(*Parts[2]);
	const double Yaw = Parts.Num() >= 4 ? FCString::Atod(*Parts[3]) : 0.0;
	SetWalking(true, false);
	if (!bWalking || !Walker.Reset(WalkMap, Deck, X, Y, Yaw))
	{
		SAIL_LOG(Warning, TEXT("-SailingWalkAt=%s: nowhere to stand there"), *At);
		return;
	}
	SAIL_LOG(Log, TEXT("-SailingWalkAt: walking on %s at (%.2f, %.2f) facing %.0f"), *Parts[0], X, Y, Yaw);
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
		// Back at the wheel, you steer (a yacht's helm view starts its steadied eye again where the helm's head is).
		bShipHelmsman = false;
		PlaceWalkerAtHelm();
		CameraYaw = 0.f;
		CameraPitch = -8.f;
		CockpitEye.bStarted = false;
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
	const TCHAR* Way = L.Kind == Sailing::EWalkLink::Steps ? TEXT("steps") : TEXT("ladder");   // (Bluebonnet's companion stairs, her cockpit's step)
	if (SailUI::UiMode() == SailUI::EUiMode::Natural) return FString::Printf(TEXT("%s: %s %s"), *Key, Way, bDown ? TEXT("down") : TEXT("up"));
	return FString::Printf(TEXT("%s: take the %s %s to the %s"), *Key, Way, bDown ? TEXT("down") : TEXT("up"),
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
	// Aboard (walking, or at a ship's wheel): the decks the walker wants (his, a ladder's other end, what shows through
	// the hatches). Outside, or in a yacht's own helm view: what her top deck shows (the frigate's gun deck through the
	// open waist; nothing of Bluebonnet's cabins, which load only once you set off about her deck).
	const uint32 Want = (bWalking || (bCockpit && HelmOnWalkMap())) ? Walker.DecksWanted(WalkMap) : WalkMap.Decks[0].AlsoLoad;
	const double Now = FPlatformTime::Seconds();
	for (int32 K = 0; K < N && K < 32; ++K)
	{
		if (DeckMeshPaths[K].IsNull()) continue;
		if (Want & (1u << K))
		{
			DeckUnwantedSince[K] = -1.0;
			if (DeckMeshes[K]) continue;
			if (!DeckLoads[K].IsValid())
			{
				TArray<FSoftObjectPath> Wanted = DeckCopyPaths.IsValidIndex(K) ? DeckCopyPaths[K] : TArray<FSoftObjectPath>();
				Wanted.Insert(DeckMeshPaths[K], 0);
				DeckLoads[K] = UAssetManager::GetStreamableManager().RequestAsyncLoad(Wanted);
			}
			if (!DeckLoads[K].IsValid() || !DeckLoads[K]->HasLoadCompleted()) continue;
			UStaticMesh* Mesh = Cast<UStaticMesh>(DeckMeshPaths[K].ResolveObject());
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
			SetDeckCopies(K, true);
			SetDeckLamps(K, true);
		}
		else if (DeckMeshes[K] || DeckLoads[K].IsValid())
		{
			if (DeckUnwantedSince[K] < 0.0) DeckUnwantedSince[K] = Now;
			else if (Now - DeckUnwantedSince[K] > ShipWalkGame::DeckUnloadDelay)
			{
				if (DeckMeshes[K]) DeckMeshes[K]->DestroyComponent();
				DeckMeshes[K] = nullptr;
				SetDeckCopies(K, false);
				SetDeckLamps(K, false);
				if (DeckLoads[K].IsValid()) DeckLoads[K]->ReleaseHandle();
				DeckLoads[K].Reset();
				DeckUnwantedSince[K] = -1.0;
			}
		}
	}
}

void ASailboatPawn::SetDeckLamps(int32 Deck, bool bOn)
{
	for (int32 I = DeckLamps.Num() - 1; I >= 0; --I)
	{
		if (DeckLampDecks[I] != Deck) continue;
		if (DeckLamps[I]) DeckLamps[I]->DestroyComponent();
		DeckLamps.RemoveAt(I);
		DeckLampDecks.RemoveAt(I);
	}
	if (!bOn || !BoatRoot) return;
	// Her cabin lamps (Bluebonnet's brass lamps, lit as in the renders): in her frame at each bulb, shadowed so a lamp
	// lights its own cabin and not the next one through the bulkhead.
	for (const Sailing::FWalkSpot& S : WalkMap.Spots)
	{
		if (S.Deck != Deck || S.Name != "Lamp") continue;
		UPointLightComponent* Lamp = NewObject<UPointLightComponent>(this);
		Lamp->SetupAttachment(BoatRoot.Get());
		Lamp->SetRelativeLocation(FVector(S.X, S.Y, S.Z) * Sailing::CmPerMeter);
		Lamp->SetMobility(EComponentMobility::Movable);
		Lamp->IntensityUnits = ELightUnits::Lumens;
		Lamp->Intensity = ShipWalkGame::LampLumens;
		Lamp->bUseTemperature = true;
		Lamp->Temperature = ShipWalkGame::LampKelvin;
		Lamp->AttenuationRadius = ShipWalkGame::LampReachCm;
		Lamp->SourceRadius = 2.f;
		Lamp->SetCastShadows(true);
		Lamp->RegisterComponent();
		DeckLamps.Add(Lamp);
		DeckLampDecks.Add(Deck);
	}
	// Her lanterns from the export (the frigate's `lights`: the gun deck's, the berth deck's, the sick bay's, the orlop's
	// light room), in her frame at each flame with the export's colour, lumens, reach and shadowing.
	const ShipOutside::FDeckTable* Table = ShipOutside::DecksFor(Boat.GetConfig().Name);
	if (!Table || Deck < 0 || Deck >= int32(WalkMap.Decks.size())) return;
	// Unshadowed on every tier and never scattering in fog: lit with the export's shadows through MegaLights they cost
	// 5 ms at 4K on Ultra (Inputs/bench/frigate-decks/ab/). Created lit, and never toggled: a light registered hidden and
	// shown, or shown and hidden, by a range gate each tick hung the PC's GPU at 4K in the virtual shadow maps' culling
	// (DXGI_ERROR_DEVICE_HUNG at the deck's load, both decks, every run: Inputs/bench/frigate-decks/f2b9c3c5/).
	const FString DeckName = UTF8_TO_TCHAR(WalkMap.Decks[Deck].Name.c_str());
	int32 Lanterns = 0;
	for (const ShipOutside::FLantern& Lt : Table->Lanterns)
	{
		if (Lt.Deck != DeckName) continue;
		UPointLightComponent* Lamp = NewObject<UPointLightComponent>(this);
		Lamp->SetupAttachment(BoatRoot.Get());
		Lamp->SetRelativeLocation(Lt.LocationCm);
		Lamp->SetMobility(EComponentMobility::Movable);
		Lamp->IntensityUnits = ELightUnits::Lumens;
		Lamp->Intensity = Lt.Lumens;
		Lamp->bUseTemperature = false;
		Lamp->SetLightColor(Lt.Colour);
		Lamp->AttenuationRadius = Lt.RadiusCm > 0.f ? Lt.RadiusCm : ShipWalkGame::LampReachCm;
		Lamp->SourceRadius = 2.f;
		Lamp->SetCastShadows(false);
		Lamp->VolumetricScatteringIntensity = 0.f;   // no fog scattering below decks: MegaLights shaded it per pixel, 1.2 ms at 4K
		Lamp->RegisterComponent();
		DeckLamps.Add(Lamp);
		DeckLampDecks.Add(Deck);
		++Lanterns;
	}
	int32 Copies = 0;
	for (int32 I = 0; I < DeckCopies.Num(); ++I) if (DeckCopyDecks[I] == Deck && DeckCopies[I]) Copies += DeckCopies[I]->GetInstanceCount();
	if (Lanterns > 0 || Copies > 0) SAIL_LOG(Log, TEXT("Ship decks %s: %d copies, %d lanterns (unshadowed)"), *DeckName, Copies, Lanterns);
}

void ASailboatPawn::SetDeckCopies(int32 Deck, bool bOn)
{
	for (int32 I = DeckCopies.Num() - 1; I >= 0; --I)
	{
		if (DeckCopyDecks[I] != Deck) continue;
		if (DeckCopies[I]) DeckCopies[I]->DestroyComponent();
		DeckCopies.RemoveAt(I);
		DeckCopyDecks.RemoveAt(I);
	}
	if (!bOn || !BoatRoot || Deck < 0 || Deck >= int32(WalkMap.Decks.size())) return;
	const ShipOutside::FDeckTable* Table = ShipOutside::DecksFor(Boat.GetConfig().Name);
	if (!Table) return;
	// The deck's placed copies (the frigate's 406 on the berth deck: hooks, hammocks, messes, chests), one instanced mesh
	// per part in her frame (BoatRoot, no offset), drawn and shadowed, no collision; the parts the frames move (the
	// tiller and its ropes, the doors) are theirs (ShipFrames.h), not copies. Off the distance field: she moves every
	// frame, and an instanced set on a moving actor re-sends its instances to that scene each time (docs/recentre-hitch/).
	const FString DeckName = UTF8_TO_TCHAR(WalkMap.Decks[Deck].Name.c_str());
	TMap<FString, UInstancedStaticMeshComponent*> ByPart;
	for (const ShipOutside::FDeckCopy& C : Table->Copies)
	{
		if (C.Deck != DeckName) continue;
		bool bFramed = false;
		for (int32 K = 0; ShipFrames && K < ShipFrames->NumFrames && !bFramed; ++K) bFramed = C.Part == UTF8_TO_TCHAR(ShipFrames->Frames[K].Name);
		if (bFramed) continue;
		UInstancedStaticMeshComponent* Copies = ByPart.FindRef(C.Part);
		if (!Copies)
		{
			UStaticMesh* Mesh = Cast<UStaticMesh>(FSoftObjectPath(C.Asset).ResolveObject());
			if (!Mesh) continue;   // not in the project, or not loaded with the deck
			Copies = NewObject<UInstancedStaticMeshComponent>(this);
			Copies->SetupAttachment(BoatRoot.Get());
			Copies->SetStaticMesh(Mesh);
			Copies->SetMobility(EComponentMobility::Movable);
			Copies->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Copies->SetCanEverAffectNavigation(false);
			Copies->bAffectDistanceFieldLighting = false;
			Copies->SetUseConservativeBounds(true);
			Copies->RegisterComponent();
			ByPart.Add(C.Part, Copies);
			DeckCopies.Add(Copies);
			DeckCopyDecks.Add(Deck);
		}
		Copies->AddInstance(C.Transform, false);
	}
	// (Counted in SetDeckLamps' "Ship decks" line, with the lanterns.)
}

void ASailboatPawn::UpdateBelowAdapt(float DeltaSeconds)
{
	// Below: walking with a deckhead over the eye (Bluebonnet's cabins, the frigate's decks under the spar deck).
	bool bUnder = false;
	if (bWalking && CanWalk() && Walker.GetDeck() >= 0 && Walker.GetDeck() < int32(WalkMap.Decks.size()))
	{
		const Sailing::Vec3 Eye = Walker.GetEye();
		bUnder = std::isfinite(WalkMap.Decks[Walker.GetDeck()].OverheadAt(Eye.X, Eye.Y));
	}
	BelowAdapt = FMath::FInterpConstantTo(BelowAdapt, bUnder ? 1.f : 0.f, DeltaSeconds, 1.f / ShipWalkGame::BelowAdaptSeconds);
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

void ASailboatPawn::StartShipManoeuvre(Sailing::EShipManoeuvre Manoeuvre)
{
	using namespace Sailing;
	// Her officers work the braces, sails and helm through it (FShipHandling, after the trimmer each physics step); the
	// helmsman stands by at the wheel to take her after it. From the wheel, you hand her to him for it.
	if (!bShipHelmsman) ShipHelmsmanTakes();
	if (Manoeuvre == EShipManoeuvre::None)
	{
		// Filling away: the side she lies on now, a point free of close-hauled until she has way on.
		const double Side = Boat.GetTelemetry().TrueWindAngle >= 0.0 ? 1.0 : -1.0;
		WalkPilot = FAutopilot();
		constexpr double FreeDeg = 11.25;   // a point free of close-hauled
		WalkPilot.TargetTWADeg = Side * (ShipHandling.Settings.CloseHauledDeg + FreeDeg);
	}
	ShipHandling.Start(Manoeuvre, Boat);
	ShipHandlingCalled = EShipManoeuvreStep::Idle;
}

void ASailboatPawn::UpdateShipManoeuvre()
{
	using namespace Sailing;
	if (ShipHandling.Manoeuvre() == EShipManoeuvre::None) return;
	const EShipManoeuvreStep Step = ShipHandling.Step();
	if (Step != ShipHandlingCalled && Step != EShipManoeuvreStep::Idle && Step != EShipManoeuvreStep::Done)
	{
		// The officer of the watch's call at each step (in every HUD mode, like the captain's).
		StatusMessage = FString(TEXT("Officer of the watch: ")) + UTF8_TO_TCHAR(FShipHandling::StepName(Step));
		StatusUntil = Boat.GetState().Time + 5.0;
	}
	ShipHandlingCalled = Step;
	if (Step == EShipManoeuvreStep::Done)
	{
		// Round: her helmsman takes her close-hauled on the new tack (the handling's courses and spanker set again at the
		// next step).
		const double After = ShipHandling.CourseAfterDeg();
		WalkPilot = FAutopilot();
		WalkPilot.TargetTWADeg = After;
		ShipHandling.Start(EShipManoeuvre::None, Boat);
		ShipHandlingCalled = EShipManoeuvreStep::Idle;
	}
}

Sailing::FShipOrderContext ASailboatPawn::GetShipOrderContext() const
{
	Sailing::FShipOrderContext C;
	// The square rig's sail plans are carried out (ApplySailOrder), the guns by her battery, tacking, wearing and heaving to
	// by her officers (FShipHandling).
	C.bSquareRig = Boat.GetConfig().HasSquareRig();
	C.bManoeuvres = C.bSquareRig;
	C.bHoveTo = ShipHandling.Manoeuvre() == Sailing::EShipManoeuvre::HeaveTo && ShipHandling.Step() == Sailing::EShipManoeuvreStep::HoveTo;
	C.bManoeuvring = ShipHandling.IsActive() && !C.bHoveTo;
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
		// The crew set, clew up or furl each sail at their pace (the physics' SquareOut, the model's ShipRigPose). Shorten
		// sail takes her down her officers' ladder a plan at a time (ShipSailPlans.h), and before the wind the spanker is
		// brailed up with the plan.
		Sailing::ApplySailOrder(Order.Order, Boat.GetConfig(), Controls, ShipSailPlan, FMath::Abs(Boat.GetTelemetry().TrueWindAngle) * Sailing::kRadToDeg > 155.0);
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
	case EShipOrder::Tack:
		StartShipManoeuvre(Sailing::EShipManoeuvre::Tack);
		break;
	case EShipOrder::Wear:
		StartShipManoeuvre(Sailing::EShipManoeuvre::Wear);
		break;
	case EShipOrder::HeaveTo:
		StartShipManoeuvre(Sailing::EShipManoeuvre::HeaveTo);
		break;
	case EShipOrder::FillAway:
		// The main yards braced round to draw again; her helmsman takes her off close-hauled on the tack she lies on.
		StartShipManoeuvre(Sailing::EShipManoeuvre::None);
		break;
	default:
		break;
	}
	// The captain's call, in every HUD mode: it is what you said.
	const Sailing::FShipOrderInfo& Info = Sailing::ShipOrderInfo(Order.Order);
	FString Call = UTF8_TO_TCHAR(Info.Call);
	if (Info.bSided && Order.Side != Sailing::EOrderSide::Both) Call = FString(UTF8_TO_TCHAR(Sailing::OrderSideName(Order.Side))) + TEXT(" side: ") + Call;
	// (shortening sail says which plan she is coming down to: "Shorten sail! (double-reefed topsails)")
	if (Order.Order == EShipOrder::ShortenSail && Sailing::SailOrderPlanName(ShipSailPlan)) Call += FString::Printf(TEXT(" (%s)"), UTF8_TO_TCHAR(Sailing::SailOrderPlanName(ShipSailPlan)));
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
