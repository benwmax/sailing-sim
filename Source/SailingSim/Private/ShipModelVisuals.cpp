// A ship's rig on the model (docs/ship-rig/): her yards brace and hoist, the spanker's boom and gaff swing, and each sail
// shows set, clewed up or furled as the physics has them. The logic is Sailing::FShipRigPose (ShipRig.h); this file finds
// the model's parts (or loads them), and puts each frame's pose on them. Her other moving parts (docs/ship-frames/: the
// tiller and its ropes with the rudder, the wheel with them, the cabin doors for a walker) go the same way below, from
// Sailing::FShipFramesPose (ShipFrames.h).
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "CannonBattery.h"
#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/StreamableManager.h"
#include "Misc/PackageName.h"

namespace ShipRigGame
{
	/** The folder and mesh prefix of a ship's exported model by her config name (the export's paths). */
	FString ModelFolder(const char* ConfigName)
	{
		const FString Name = UTF8_TO_TCHAR(ConfigName ? ConfigName : "");
		if (Name == TEXT("Commonwealth")) return TEXT("Frigate");
		return Name;
	}

	/** The rig object a mesh shows ("SM_Frigate_Yard_Fore" or its "_Light" twin -> "Yard_Fore"), or "". */
	FString ObjectOfMesh(const FString& MeshName, const FString& Folder)
	{
		const FString Prefix = FString::Printf(TEXT("SM_%s_"), *Folder);
		if (!MeshName.StartsWith(Prefix)) return FString();
		FString Object = MeshName.Mid(Prefix.Len());
		Object.RemoveFromEnd(TEXT("_Light"));
		return Object;
	}

	/** A rig motion (metres, ship frame) as an Unreal transform in BoatRoot's frame (cm), after the part's rest. A mirror
	 *  comes out as a negative scale. */
	FTransform Posed(const FTransform& Rest, const Sailing::FRigMotion& Motion)
	{
		FMatrix M = FMatrix::Identity;
		for (int32 I = 0; I < 3; ++I)
		{
			for (int32 J = 0; J < 3; ++J) M.M[J][I] = Motion.M[I][J]; // Unreal's matrices take row vectors
		}
		M.M[3][0] = Motion.T.X * Sailing::CmPerMeter;
		M.M[3][1] = Motion.T.Y * Sailing::CmPerMeter;
		M.M[3][2] = Motion.T.Z * Sailing::CmPerMeter;
		return FTransform(Rest.ToMatrixWithScale() * M);
	}

	bool Shows(const FShipRigPart& Part, const Sailing::FShipRigPose& Pose)
	{
		if (Part.Object <= 1) return true;
		const Sailing::ESailShown Shown = Pose.GetShown(Part.Sail);
		return (Part.Object == 2 && Shown == Sailing::ESailShown::Set) || (Part.Object == 3 && Shown == Sailing::ESailShown::Clewed)
			|| (Part.Object == 4 && Shown == Sailing::ESailShown::Furled);
	}
}

void ASailboatPawn::ClearShipRig()
{
	for (UStaticMeshComponent* Mesh : ShipRigOwnMeshes) if (Mesh) Mesh->DestroyComponent();
	ShipRigOwnMeshes.Reset();
	// Parts that were on the boat already go back to their rest (a rebuild may keep them).
	for (const FShipRigPart& Part : ShipRigParts)
	{
		if (UStaticMeshComponent* Mesh = Part.Mesh.Get())
		{
			Mesh->SetRelativeTransform(Part.Rest);
			Mesh->SetVisibility(true);
		}
	}
	ShipRigParts.Reset();
	ShipRigPending.Reset();
	ShipRigPendingParts.Reset();
	if (ShipRigLoad.IsValid()) ShipRigLoad->CancelHandle();
	ShipRigLoad.Reset();
	ShipRig = nullptr;
	if (ShipBattery)
	{
		ShipBattery->OnGunFired.RemoveAll(this);
		ShipBattery->Destroy();
	}
	ShipBattery = nullptr;
	bShipGunsFiring[0] = bShipGunsFiring[1] = false;
	ShipHandling = Sailing::FShipHandling();   // a new boat starts on no manoeuvre
	ShipHandlingCalled = Sailing::EShipManoeuvreStep::Idle;
	ShipSailPlan = 0;
}

namespace ShipRigGame
{
	/** The package of an exported part, looked for in the folder its table says first, then the other: the gun deck's
	 *  parts are exported with the decks below (Decks/), the rest with the outside model (Outside/). "" when neither has it. */
	FString PartPackage(const FString& Folder, const FString& Asset, bool bBelow)
	{
		const TCHAR* Order[2] = { bBelow ? TEXT("Decks") : TEXT("Outside"), bBelow ? TEXT("Outside") : TEXT("Decks") };
		for (const TCHAR* Sub : Order)
		{
			const FString Package = FString::Printf(TEXT("/Game/Boats/%s/%s/%s"), *Folder, Sub, *Asset);
			if (FPackageName::DoesPackageExist(Package)) return Package;
		}
		return FString();
	}

	/** A frame as built (its origin and axes in the ship frame, metres) as a transform in BoatRoot's frame (cm). */
	FTransform FrameRest(const Sailing::FShipFrame& F)
	{
		FMatrix M = FMatrix::Identity;   // row vectors: row I is the image of axis I
		M.M[0][0] = F.X.X; M.M[0][1] = F.X.Y; M.M[0][2] = F.X.Z;
		M.M[1][0] = F.Y.X; M.M[1][1] = F.Y.Y; M.M[1][2] = F.Y.Z;
		M.M[2][0] = F.Z.X; M.M[2][1] = F.Z.Y; M.M[2][2] = F.Z.Z;
		M.M[3][0] = F.Origin.X * Sailing::CmPerMeter;
		M.M[3][1] = F.Origin.Y * Sailing::CmPerMeter;
		M.M[3][2] = F.Origin.Z * Sailing::CmPerMeter;
		return FTransform(M);
	}
}

void ASailboatPawn::ClearShipFrames()
{
	for (UStaticMeshComponent* Mesh : ShipFrameOwnMeshes) if (Mesh) Mesh->DestroyComponent();
	ShipFrameOwnMeshes.Reset();
	for (const FShipFramePart& Part : ShipFrameParts)
	{
		if (UStaticMeshComponent* Mesh = Part.Mesh.Get())
		{
			Mesh->SetRelativeTransform(Part.Rest);
			Mesh->SetVisibility(true);
		}
	}
	ShipFrameParts.Reset();
	ShipFramesPending.Reset();
	ShipFramesPendingParts.Reset();
	if (ShipFramesLoad.IsValid()) ShipFramesLoad->CancelHandle();
	ShipFramesLoad.Reset();
	ShipFrames = nullptr;
}

void ASailboatPawn::BindShipFrames()
{
	ClearShipFrames();
	ShipFrames = Sailing::ShipFramesFor(Boat.GetConfig().Name);
	if (!ShipFrames || !BoatRoot) return;
	ShipFramesPose.Reset(*ShipFrames);
	const FString Folder = ShipRigGame::ModelFolder(Boat.GetConfig().Name);

	// The parts already on the boat (the outside model's, straight under BoatRoot in her frame)...
	TSet<FString> Found;
	TArray<USceneComponent*> RootParts;
	BoatRoot->GetChildrenComponents(false, RootParts);
	for (USceneComponent* Child : RootParts)
	{
		UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Child);
		if (!Mesh || !Mesh->GetStaticMesh()) continue;
		const FString Object = ShipRigGame::ObjectOfMesh(Mesh->GetStaticMesh()->GetName(), Folder);
		const int32 Frame = Object.IsEmpty() ? -1 : ShipFrames->FrameNamed(TCHAR_TO_UTF8(*Object));
		if (Frame < 0) continue;
		FShipFramePart Part;
		Part.Mesh = Mesh;
		Part.Rest = Mesh->GetRelativeTransform();
		Part.Applied = Part.Rest;
		Part.Frame = Frame;
		Part.bBelow = ShipFrames->Frames[Frame].bBelow;
		Mesh->SetMobility(EComponentMobility::Movable);
		ShipFrameParts.Add(Part);
		Found.Add(Object);
	}

	// ...and the rest from the export, where it is in the project (each part alone at its own pivot in her frame).
	for (int32 K = 0; K < ShipFrames->NumFrames; ++K)
	{
		const Sailing::FShipFrame& F = ShipFrames->Frames[K];
		const FString Name = UTF8_TO_TCHAR(F.Name);
		if (Found.Contains(Name) || ShipOutsideOwns(Name)) continue;   // the outside model's part: found once it is loaded
		const FString Asset = FString::Printf(TEXT("SM_%s_%s"), *Folder, *Name);
		const FString Package = ShipRigGame::PartPackage(Folder, Asset, F.bBelow);
		if (Package.IsEmpty()) continue;
		FShipFramePart Part;
		Part.Frame = K;
		Part.bBelow = F.bBelow;
		ShipFramesPending.Add(FSoftObjectPath(Package + TEXT(".") + Asset));
		ShipFramesPendingParts.Add(Part);
	}
	if (ShipFramesPending.Num() > 0) ShipFramesLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(ShipFramesPending);
	SAIL_LOG(Log, TEXT("Ship frames %s: %d parts on the model, %d to load, %d not in the project"), UTF8_TO_TCHAR(Boat.GetConfig().Name),
		ShipFrameParts.Num(), ShipFramesPending.Num(), ShipFrames->NumFrames - ShipFrameParts.Num() - ShipFramesPending.Num());
}

void ASailboatPawn::UpdateShipFrames(float DeltaSeconds)
{
	if (!ShipFrames) return;
	using namespace Sailing;

	// The loaded parts, in her frame like the outside model's (BoatRoot, no offset), drawn and shadowed, no collision.
	if (ShipFramesLoad.IsValid() && ShipFramesLoad->HasLoadCompleted())
	{
		for (int32 K = 0; K < ShipFramesPending.Num() && K < ShipFramesPendingParts.Num(); ++K)
		{
			UStaticMesh* Asset = Cast<UStaticMesh>(ShipFramesPending[K].ResolveObject());
			if (!Asset)
			{
				SAIL_LOG(Warning, TEXT("Ship frame mesh %s did not load"), *ShipFramesPending[K].ToString());
				continue;
			}
			UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this);
			Mesh->SetupAttachment(BoatRoot.Get());
			Mesh->SetMobility(EComponentMobility::Movable);
			Mesh->SetStaticMesh(Asset);
			Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Mesh->SetCanEverAffectNavigation(false);
			Mesh->RegisterComponent();
			ShipFrameOwnMeshes.Add(Mesh);
			FShipFramePart Part = ShipFramesPendingParts[K];
			Part.Mesh = Mesh;
			// The export puts each moving part at its own pivot, its frame's origin and axes (like the gun-port lids), so it
			// rests at its frame; one exported in the ship frame instead (its bounds about the frame's origin, not its own)
			// rests at the identity, and a rope run's stretch along its own X is then only approximate.
			const Sailing::FShipFrame& F = ShipFrames->Frames[Part.Frame];
			const FVector Origin = FVector(F.Origin.X, F.Origin.Y, F.Origin.Z) * Sailing::CmPerMeter;
			const FVector Centre = Asset->GetBoundingBox().GetCenter();
			const bool bAtPivot = FVector::DistSquared(Centre, Origin) >= Centre.SizeSquared();
			Part.Rest = bAtPivot ? ShipRigGame::FrameRest(F) : FTransform::Identity;
			if (!bAtPivot) SAIL_LOG(Log, TEXT("Ship frame part %s is exported in the ship frame, not at its pivot"), UTF8_TO_TCHAR(F.Name));
			Part.Applied = Part.Rest;
			Mesh->SetRelativeTransform(Part.Rest);
			ShipFrameParts.Add(Part);
		}
		ShipFramesPending.Reset();
		ShipFramesPendingParts.Reset();
		ShipFramesLoad.Reset();
	}

	// The helm from the physics' rudder; the doors for the walker's feet (nobody near them when nobody walks her decks).
	const Vec3 Feet = Walker.GetFeet();
	ShipFramesPose.Update(*ShipFrames, Boat.GetState().RudderAngle, bWalking ? &Feet : nullptr, DeltaSeconds);

	// The gun deck's parts show with its mesh (the tiller under the great cabin's beams, its ropes, the doors): outside her
	// nothing sees them, and they would float in her hull when the deck is not loaded.
	const int32 Gun = WalkMap.DeckNamed("Gun");
	const bool bGunDeck = Gun >= 0 && Gun < DeckMeshes.Num() && DeckMeshes[Gun] && DeckMeshes[Gun]->GetStaticMesh();

	// Each part at its rest moved by its frame's motion, moved only when its transform changes (still parts keep their
	// cached shadows).
	for (FShipFramePart& Part : ShipFrameParts)
	{
		UStaticMeshComponent* Mesh = Part.Mesh.Get();
		if (!Mesh) continue;
		const bool bShow = !Part.bBelow || bGunDeck;
		if (Mesh->IsVisible() != bShow) Mesh->SetVisibility(bShow);
		if (!bShow) continue;
		const FTransform Want = ShipRigGame::Posed(Part.Rest, ShipFramesPose.Motion(*ShipFrames, Part.Frame));
		if (Want.GetTranslation().Equals(Part.Applied.GetTranslation(), 0.05) && Want.GetRotation().Equals(Part.Applied.GetRotation(), 1e-5)
			&& Want.GetScale3D().Equals(Part.Applied.GetScale3D(), 1e-4)) continue;
		Mesh->SetRelativeTransform(Want);
		Part.Applied = Want;
	}
}

void ASailboatPawn::BindShipRig()
{
	ClearShipRig();
	ShipRig = Sailing::ShipRigFor(Boat.GetConfig().Name);
	if (!ShipRig || !BoatRoot) return;
	ShipRigPose.Reset(*ShipRig);
	// Her guns, housed (the player's ship: the battery's drill, smoke and lights are not for AI ships or the ghost).
	if (!bTrafficBoat && !bGhost)
	{
		ShipBattery = ACannonBattery::SpawnBattery(BoatRoot.Get());
		if (ShipBattery) ShipBattery->OnGunFired.AddUObject(this, &ASailboatPawn::OnShipGunFired);
	}
	const FString Folder = ShipRigGame::ModelFolder(Boat.GetConfig().Name);

	// Every object the rig moves: each spar, and each sail's head and states.
	TMap<FString, FShipRigPart> Wanted;
	for (int32 K = 0; K < ShipRig->NumSpars; ++K)
	{
		FShipRigPart Part;
		Part.Spar = K;
		Part.Object = 0;
		Wanted.Add(UTF8_TO_TCHAR(ShipRig->Spars[K].Name), Part);
	}
	for (int32 K = 0; K < ShipRig->NumSails; ++K)
	{
		const Sailing::FRigSail& S = ShipRig->Sails[K];
		const char* Objects[4] = { S.Head, S.Set, S.Clewed, S.Furled };
		for (int32 O = 0; O < 4; ++O)
		{
			if (!Objects[O] || !*Objects[O]) continue;
			FShipRigPart Part;
			Part.Spar = S.Spar;
			Part.Sail = K;
			Part.Object = uint8(O + 1);
			Wanted.Add(UTF8_TO_TCHAR(Objects[O]), Part);
		}
	}

	// The model's parts already on the boat (her outside meshes, straight under BoatRoot in her frame).
	TSet<FString> Found;
	TArray<USceneComponent*> RootParts;
	BoatRoot->GetChildrenComponents(false, RootParts);
	for (USceneComponent* Child : RootParts)
	{
		UStaticMeshComponent* Mesh = Cast<UStaticMeshComponent>(Child);
		if (!Mesh || !Mesh->GetStaticMesh()) continue;
		const FString Object = ShipRigGame::ObjectOfMesh(Mesh->GetStaticMesh()->GetName(), Folder);
		const FShipRigPart* Want = Object.IsEmpty() ? nullptr : Wanted.Find(Object);
		if (!Want) continue;
		FShipRigPart Part = *Want;
		Part.Mesh = Mesh;
		Part.Rest = Mesh->GetRelativeTransform();
		Part.Applied = Part.Rest;
		Mesh->SetMobility(EComponentMobility::Movable);
		ShipRigParts.Add(Part);
		Found.Add(Object);
	}

	// The rest from the export, where it is in the project.
	for (const TPair<FString, FShipRigPart>& Pair : Wanted)
	{
		if (Found.Contains(Pair.Key) || ShipOutsideOwns(Pair.Key)) continue;   // the outside model's part: found once it is loaded
		const FString Asset = FString::Printf(TEXT("SM_%s_%s"), *Folder, *Pair.Key);
		const FString Package = FString::Printf(TEXT("/Game/Boats/%s/Outside/%s"), *Folder, *Asset);
		if (!FPackageName::DoesPackageExist(Package)) continue;
		ShipRigPending.Add(FSoftObjectPath(Package + TEXT(".") + Asset));
		ShipRigPendingParts.Add(Pair.Value);
	}
	if (ShipRigPending.Num() > 0) ShipRigLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(ShipRigPending);
	SAIL_LOG(Log, TEXT("Ship rig %s: %d parts on the model, %d to load, %d not in the project"), UTF8_TO_TCHAR(Boat.GetConfig().Name),
		ShipRigParts.Num(), ShipRigPending.Num(), Wanted.Num() - ShipRigParts.Num() - ShipRigPending.Num());
}

void ASailboatPawn::UpdateShipRig(float DeltaSeconds)
{
	if (!ShipRig) return;
	using namespace Sailing;

	// The loaded parts, in her frame like the outside model's (BoatRoot, no offset), drawn and shadowed, no collision.
	if (ShipRigLoad.IsValid() && ShipRigLoad->HasLoadCompleted())
	{
		for (int32 K = 0; K < ShipRigPending.Num() && K < ShipRigPendingParts.Num(); ++K)
		{
			UStaticMesh* Asset = Cast<UStaticMesh>(ShipRigPending[K].ResolveObject());
			if (!Asset)
			{
				SAIL_LOG(Warning, TEXT("Ship rig mesh %s did not load"), *ShipRigPending[K].ToString());
				continue;
			}
			UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this);
			Mesh->SetupAttachment(BoatRoot.Get());
			Mesh->SetMobility(EComponentMobility::Movable);
			Mesh->SetStaticMesh(Asset);
			Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Mesh->SetCanEverAffectNavigation(false);
			Mesh->RegisterComponent();
			ShipRigOwnMeshes.Add(Mesh);
			FShipRigPart Part = ShipRigPendingParts[K];
			Part.Mesh = Mesh;
			Part.Rest = FTransform::Identity;
			Part.Applied = Part.Rest;
			ShipRigParts.Add(Part);
		}
		ShipRigPending.Reset();
		ShipRigPendingParts.Reset();
		ShipRigLoad.Reset();
	}

	// The physics' rig: each yard's angle and how much of each sail is out, the boom, the fore-and-aft sails.
	const FBoatState& S = Boat.GetState();
	FShipRigInput In;
	const int32 NumSquare = FMath::Min3(int32(Boat.GetConfig().Square.Sails.size()), int32(kMaxSquareSails), int32(kMaxRigSquare));
	for (int32 K = 0; K < NumSquare; ++K)
	{
		In.YardAngle[K] = S.YardAngle[K];
		In.SquareOut[K] = S.SquareOut[K];
		In.bSquareFurl[K] = Controls.SquareSet[K] == ESailSet::Furled;
	}
	In.BoomAngle = S.BoomAngle;
	In.MainOut = S.MainOut;
	In.JibOut = S.JibOut;
	In.StaysailOut = S.StaysailOut;
	In.MainSide = S.MainSide;
	In.JibSide = S.JibSide;
	In.StaysailSide = S.StaysailSide;
	ShipRigPose.Update(*ShipRig, In, DeltaSeconds);

	// Each part at its rest moved by its spar (a sail after its mirror); only a sail's shown state drawn. A part is moved
	// only when its transform changes, so still spars keep their cached shadows.
	for (FShipRigPart& Part : ShipRigParts)
	{
		UStaticMeshComponent* Mesh = Part.Mesh.Get();
		if (!Mesh) continue;
		const bool bShow = ShipRigGame::Shows(Part, ShipRigPose);
		if (Mesh->IsVisible() != bShow) Mesh->SetVisibility(bShow);
		if (!bShow) continue;
		const FRigMotion Motion = Part.Object == 0 || Part.Object == 1 ? ShipRigPose.SparMotion(*ShipRig, Part.Spar) : ShipRigPose.SailMotion(*ShipRig, Part.Sail);
		const FTransform Want = ShipRigGame::Posed(Part.Rest, Motion);
		if (Want.GetTranslation().Equals(Part.Applied.GetTranslation(), 0.05) && Want.GetRotation().Equals(Part.Applied.GetRotation(), 1e-5)
			&& Want.GetScale3D().Equals(Part.Applied.GetScale3D(), 1e-4)) continue;
		Mesh->SetRelativeTransform(Want);
		Part.Applied = Want;
	}
}

void ASailboatPawn::OnShipGunFired(const FCannonFiredEvent& Event)
{
	// A gun's report through the deck: a kick of the camera's buffet (Settings > Camera shake), as hard as a slam for a gun
	// fired beside the camera, fading past about 15 m. A flash in the pan shakes nothing.
	if (Event.bMisfire || Event.ImpulseNs <= 0.0) return;
	const FVector Eye = Camera ? Camera->GetComponentLocation() : GetActorLocation();
	const double DistanceM = FVector::Dist(Eye, Event.MuzzleWorld) / Sailing::CmPerMeter;
	const double Kick = FMath::Clamp(Event.ImpulseNs / 8000.0, 0.2, 1.0) * FMath::Clamp(15.0 / FMath::Max(DistanceM, 15.0), 0.0, 1.0);
	CameraBuffet.Kick(Kick);
}
