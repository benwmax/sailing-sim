// A ship's rig on the model (docs/ship-rig/): her yards brace and hoist, the spanker's boom and gaff swing, and each sail
// shows set, clewed up or furled as the physics has them. The logic is Sailing::FShipRigPose (ShipRig.h); this file finds
// the model's parts (or loads them), and puts each frame's pose on them.
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
		if (Found.Contains(Pair.Key)) continue;
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
