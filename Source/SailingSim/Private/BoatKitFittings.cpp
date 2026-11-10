// Hardware fit wave 2 (docs/hardware-fit/README.md): the boat kit's moving fittings on the pawn. Wave 1 put the deck
// hardware in the hero J/22's model (Inputs/j22-hero/j22_kitfit.py); these follow the sails and the wind, so the game
// draws them: the masthead fly's vane on the apparent wind, the jib's piston hanks on the cloth's luff and the jib
// halyard's snap shackle at the head. Each waits for its SM_Kit_ mesh (scripts/import_hardware_kit.py); without it the
// boat looks as before.

#include "SailboatPawn.h"
#include "CourseMarks.h"
#include "KitFittings.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"

using Sailing::EBoatType;
using Sailing::FBoatConfig;

namespace
{
	/** The kit's mesh, or its light copy (AI boats and the ghost: the hero copy is Nanite, the light one is a quarter). */
	UStaticMesh* KitFitMesh(const TCHAR* Part, bool bLight)
	{
		return CourseMarks::Load(bLight ? *FString::Printf(TEXT("%s_Light"), Part) : Part);
	}

	FVector KitFitSocketCm(const UStaticMesh* Mesh, FName Socket, const FVector& Fallback)
	{
		const UStaticMeshSocket* S = Mesh ? Mesh->FindSocket(Socket) : nullptr;
		return S ? S->RelativeLocation : Fallback;
	}
}

void ASailboatPawn::BuildKitFittings()
{
	// Components from the last boat went with BoatParts.
	FlyKitMount = FlyKitVane = JibHeadShackle = nullptr;
	JibHanks.Reset();
	const FBoatConfig& C = Boat.GetConfig();
	const bool bLight = bTrafficBoat || bGhost;
	auto Add = [this](UStaticMesh* Mesh, USceneComponent* Parent) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
		Part->SetupAttachment(Parent ? Parent : BoatRoot.Get());
		Part->SetStaticMesh(Mesh);
		Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Part->SetCanEverAffectNavigation(false);
		Part->bCastDynamicShadow = !bTrafficBoat;   // a few centimetres of plastic: no shadow from AI boats
		Part->bAffectDistanceFieldLighting = false;
		Part->RegisterComponent();
		BoatParts.Add(Part);
		return Part;
	};

	// Masthead fly: the kit's vane on the turning MastheadFly, the boxes hidden. The hero J/22 carries the fixed half
	// (MastheadFlyMount) on its masthead and a FlyPivot socket; other boats get the mount from here.
	const bool bFly = C.Type != EBoatType::Sunfish && C.Type != EBoatType::ILCA7;
	UStaticMesh* Vane = bFly ? KitFitMesh(TEXT("MastheadFlyVane"), bLight) : nullptr;
	const bool bMastMount = ModelMast && ModelMast->DoesSocketExist(TEXT("FlyPivot"));
	UStaticMesh* Mount = Vane && !bMastMount ? KitFitMesh(TEXT("MastheadFlyMount"), bLight) : nullptr;
	if (Vane && (Mount || bMastMount))
	{
		for (UStaticMeshComponent* Box : FlyBoxes) if (Box) Box->SetVisibility(false);
		FlyKitVane = Add(Vane, MastheadFly);
		if (Mount)
		{
			FlyKitMount = Add(Mount, nullptr);
		}
		if (bTrafficBoat)
		{
			FlyKitVane->SetCullDistance(40000.f);
			if (FlyKitMount) FlyKitMount->SetCullDistance(40000.f);
		}
	}
	else
	{
		for (UStaticMeshComponent* Box : FlyBoxes) if (Box) Box->SetVisibility(bFly);
	}

	// Jib hanks and the halyard's snap shackle: the J/22's hank-on jib (the fleet's other jibs are on furlers or bolt ropes).
	if (C.Type == EBoatType::J22 && C.HasJib())
	{
		if (UStaticMesh* Hank = KitFitMesh(TEXT("JibHank"), bLight))
		{
			for (int32 I = 0; I < KitFittings::NumJibHanks; ++I) JibHanks.Add(Add(Hank, nullptr));
		}
		if (UStaticMesh* Shackle = KitFitMesh(TEXT("SnapShackle"), bLight))
		{
			JibHeadShackle = Add(Shackle, nullptr);
		}
		// An AI boat's hanks and shackle (a few centimetres each) are drawn only within 50 m, its fly within 400 m.
		if (bTrafficBoat)
		{
			for (UStaticMeshComponent* Hank : JibHanks) Hank->SetCullDistance(5000.f);
			if (JibHeadShackle) JibHeadShackle->SetCullDistance(5000.f);
		}
	}
	UpdateKitFittings();
}

void ASailboatPawn::UpdateKitFittings()
{
	// The fly: on the hero's FlyPivot socket (it bends with the mast; the boxes go there too when the kit vane isn't
	// imported), else on a kit mount at the masthead. Tied up with the sails stowed the mast is the dress's: no fly.
	const FBoatConfig& C = Boat.GetConfig();
	if (ModelMast && ModelMast->DoesSocketExist(TEXT("FlyPivot")))
	{
		const FVector Pivot = RigPoint(ModelMast, TEXT("FlyPivot"));
		if (!Pivot.ContainsNaN()) MastheadFly->SetRelativeLocation(Pivot);
	}
	else if (FlyKitMount)
	{
		FVector Top(C.MastX * 100.0, 0.0, C.MastheadZ * 100.0);
		if (ModelMast)
		{
			// M_BoatMast's bend (RigPoint) at the masthead.
			const float T = FMath::Clamp(float(Top.Z - ModelMast->GetRelativeLocation().Z) / MastBendHeightCm, 0.f, 1.f);
			Top.X += MastBendCm * (FMath::Sin(PI * T) - 0.35f * T * T);
		}
		FlyKitMount->SetRelativeLocation(Top);
		MastheadFly->SetRelativeLocation(Top + KitFitSocketCm(FlyKitMount->GetStaticMesh(), TEXT("Pivot"), FVector(0.0, 0.0, 23.0)));
	}
	const bool bMastUp = !ModelMast || ModelMast->IsVisible();
	if (FlyKitVane) FlyKitVane->SetVisibility(bMastUp);
	if (FlyKitMount) FlyKitMount->SetVisibility(bMastUp);

	// The hanks and the head shackle go with the jib (boat frame, cm).
	const bool bJib = JibSail && JibSail->IsVisible() && JibCloth.IsValid();
	if (JibHeadShackle) JibHeadShackle->SetVisibility(bJib);
	for (UStaticMeshComponent* Hank : JibHanks) if (Hank) Hank->SetVisibility(bJib);
	if (!bJib || (JibHanks.Num() == 0 && !JibHeadShackle))
	{
		return;
	}
	// An AI boat's off screen: leave them where they were (the rig lines are paced the same way).
	if (bTrafficBoat && !JibSail->WasRecentlyRendered(0.25f))
	{
		return;
	}
	// A fitting whose frame can't be built this frame (the cloth not yet built for a boat being swapped in, a NaN in the
	// rig: the Mac's RigClearance run on the rebaked hero, Nov 10) is hidden until it can, never handed to the scene
	// component (SetRelativeTransform ensures on an invalid transform).
	auto Place = [](UStaticMeshComponent* Part, const FTransform& X)
	{
		if (KitFittings::Placeable(X))
		{
			Part->SetRelativeTransform(X);
		}
		else
		{
			Part->SetVisibility(false);
		}
	};
	auto Up = [this](float V)
	{
		const float D = 0.02f;
		const float A = FMath::Clamp(V - D, 0.f, 1.f), B = FMath::Clamp(V + D, 0.f, 1.f);
		return (JibCloth.PointAt(0.f, B) - JibCloth.PointAt(0.f, A)).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	};
	if (JibHanks.Num() > 0)
	{
		// Each hank clips onto the forestay wire (the model's ForestayTack to Hounds, as the rig lines draw it) at the height
		// of its point on the cloth's luff, the sail toward that point; a boat without the sockets hangs them on the luff.
		const bool bStay = ModelHull && ModelMast && ModelHull->DoesSocketExist(TEXT("ForestayTack")) && ModelMast->DoesSocketExist(TEXT("Hounds"));
		const FVector Tack = bStay ? RigPoint(ModelHull, TEXT("ForestayTack")) : FVector::ZeroVector;
		const FVector Hounds = bStay ? RigPoint(ModelMast, TEXT("Hounds")) : FVector::ZeroVector;
		const FVector LuffSocket = KitFitSocketCm(JibHanks[0]->GetStaticMesh(), TEXT("Luff"), FVector(-3.41, 0.0, -0.34));
		for (int32 I = 0; I < JibHanks.Num(); ++I)
		{
			const float V = KitFittings::HankV(I, JibHanks.Num());
			const FVector Luff = JibCloth.PointAt(0.f, V);
			Place(JibHanks[I], bStay
				? KitFittings::HankOnStay(Tack, Hounds, Luff)
				: KitFittings::HankTransform(Luff, Up(V), JibCloth.ChordTangentAt(0.f, V), LuffSocket));
		}
	}
	if (JibHeadShackle)
	{
		Place(JibHeadShackle, KitFittings::HeadShackleTransform(JibCloth.PointAt(0.f, 1.f), Up(1.f), JibCloth.ChordTangentAt(0.f, 1.f)));
	}
}
