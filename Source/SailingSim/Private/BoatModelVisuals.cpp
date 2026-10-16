// Visual V2: the modelled boats (the J/22 first). The pawn's other visuals live in SailboatPawn.cpp.
//
// A class with a model (Tools/blender/build_<boat>.py, imported by scripts/make-boat-models.sh) shows its hull, mast,
// boom and rudder meshes instead of the procedural hull and shapes. The standing and running rigging is drawn here
// every frame from the meshes' sockets, with sag from the physics: a loaded sheet or the windward shroud runs straight,
// an eased or lazy sheet droops, the leeward shroud goes slack in a breeze. The mast bends with the backstay and the
// wind (its material's world position offset; the rig points on it follow the same curve), the traveler car moves
// with the trim, and the hull's wet line and the deck's wetness come from the waves, spray and rain (MPC_Boat).
#include "SailboatPawn.h"
#include "BenchRunner.h"
#include "CrewAnimInstance.h"
#include "CrewMotion.h"
#include "EngineUtils.h"
#include "TrafficManager.h"
#include "Race.h"
#include "Traffic.h"
#include "UnrealClient.h"
#include "Misc/Paths.h"
#include "Components/SkeletalMeshComponent.h"
#include "BoatLivery.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "ProceduralMeshComponent.h"
#include "CrewPose.h"

using namespace Sailing;

namespace
{
	constexpr int32 kLineSides = 8;
	constexpr int32 kLineSegments = 10;

	/** Boat detail pass: which colourway a rope wears, the row of T_RopeColourways (Inputs/rope/colourways.json order).
	 *  M_RigRope reads it from the vertex colour's red channel; wires use kLookPlain for a smooth tube (the tiller
	 *  extension) and 0 for 1x19 strand. */
	namespace RopeLook
	{
		constexpr uint8 Mainsheet = 0;      // white with red flecks (TX 7295 EC, Bean's lesson photos)
		constexpr uint8 JibPort = 1;        // red with white flecks
		constexpr uint8 JibStbd = 2;        // green with white flecks
		constexpr uint8 Vang = 5;           // blue/white mix
		constexpr uint8 Plain = 255;
	}

	/** One drawn line: from A to B (boat frame, cm), its radius, its slack (extra length as a fraction) and its look. */
	struct FRigLine
	{
		FVector A, B;
		float RadiusCm;
		float Slack;
		uint8 Look = 0;
	};

	/** Mid-span sag of a line of length L with a small extra length fraction e: a parabola with e = 8/3 (s/L)^2. */
	float SagFor(float LengthCm, float Slack)
	{
		return LengthCm * FMath::Sqrt(FMath::Max(Slack, 0.f) * 3.f / 8.f);
	}

	/** The tube's streams. UV0: U = arc length over one lay of the cover (5 diameters for braid, 11 for 1x19 wire), V once
	 *  round, with a seam column so V runs 0..1; the tangent runs along the line (the braid's normal map is in that frame);
	 *  the vertex colour's red is the look (RopeLook). */
	struct FTubeStreams
	{
		TArray<FVector> Verts, Normals;
		TArray<FVector2D> UV0;
		TArray<FLinearColor> Colors;
		TArray<FProcMeshTangent> Tangents;
		TArray<int32> Tris;
	};

	void AppendTube(const FRigLine& L, const FVector& Down, float LayDiameters, FTubeStreams& Out, bool bTris)
	{
		const FVector D = L.B - L.A;
		const float Len = D.Size();
		const FVector Dir = Len > 1e-3f ? D / Len : FVector::UpVector;
		// Sag across the line, in the plane of the line and gravity.
		FVector Sag = Down - FVector::DotProduct(Down, Dir) * Dir;
		Sag = Sag.GetSafeNormal() * SagFor(Len, L.Slack);
		const FVector Ref = FMath::Abs(Dir.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector;
		const FVector U = FVector::CrossProduct(Dir, Ref).GetSafeNormal();
		const FVector W = FVector::CrossProduct(Dir, U);
		const int32 Base = Out.Verts.Num();
		const float Lay = FMath::Max(LayDiameters * 2.f * L.RadiusCm, 0.01f);
		const FLinearColor Look(float(L.Look) / 255.f, 0.f, 0.f, 1.f);
		float Arc = 0.f;
		FVector Prev = L.A;
		for (int32 I = 0; I <= kLineSegments; ++I)
		{
			const float T = float(I) / kLineSegments;
			const FVector C = L.A + D * T + Sag * (4.f * T * (1.f - T));
			Arc += FVector::Dist(C, Prev);
			Prev = C;
			// Along the sagged curve: the parabola's derivative.
			const FVector Along = (D + Sag * (4.f - 8.f * T)).GetSafeNormal();
			for (int32 K = 0; K <= kLineSides; ++K)
			{
				const float A = 2.f * PI * K / kLineSides;
				const FVector N = U * FMath::Cos(A) + W * FMath::Sin(A);
				Out.Verts.Add(C + N * L.RadiusCm);
				Out.Normals.Add(N);
				Out.UV0.Add(FVector2D(Arc / Lay, float(K) / kLineSides));
				Out.Colors.Add(Look);
				Out.Tangents.Add(FProcMeshTangent(Along, false));
			}
		}
		if (!bTris) return;
		constexpr int32 Ring = kLineSides + 1;
		for (int32 I = 0; I < kLineSegments; ++I)
		{
			for (int32 K = 0; K < kLineSides; ++K)
			{
				const int32 A0 = Base + I * Ring + K, A1 = A0 + 1;
				const int32 B0 = A0 + Ring, B1 = A1 + Ring;
				Out.Tris.Append({ A0, B0, B1, A0, B1, A1 });
			}
		}
	}
}

ASailboatPawn::FBoatModelMeshes ASailboatPawn::ModelMeshesFor(EBoatType Type) const
{
	FBoatModelMeshes M;
	// Boats 10: -SailingJ22Hero draws the script-built hero J/22 (Inputs/j22-hero, imported to /Game/Boats/J22Hero by
	// scripts/import_j22_hero.py) in the J/22's place, with the same sockets, for side-by-side stills.
	if (Type == EBoatType::J22 && FParse::Param(FCommandLine::Get(), TEXT("SailingJ22Hero")))
	{
		auto LoadHero = [](const TCHAR* Part) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/J22Hero/SM_J22H_%s.SM_J22H_%s"), Part, Part)); };
		M.Hull = LoadHero(TEXT("Hull"));
		M.Mast = LoadHero(TEXT("Mast"));
		M.Boom = LoadHero(TEXT("Boom"));
		M.Rudder = LoadHero(TEXT("Rudder"));
		// Boat detail pass: the cabin below decks (optional: older imports have none).
		M.Interior = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, TEXT("/Game/Boats/J22Hero/SM_J22H_Interior.SM_J22H_Interior"), nullptr, LOAD_NoWarn | LOAD_Quiet));
		if (M.Hull && M.Mast && M.Boom && M.Rudder) return M;
		M = FBoatModelMeshes();
	}
	if (Type == EBoatType::J22 && J22HullMesh && J22MastMesh && J22BoomMesh && J22RudderMesh)
	{
		M.Hull = J22HullMesh;
		M.Mast = J22MastMesh;
		M.Boom = J22BoomMesh;
		M.Rudder = J22RudderMesh;
		return M;
	}
	// Visual V7: the other seven from Tools/blender/build_fleet.py (scripts/make-boat-models.sh), loaded by class.
	static const TCHAR* BoatTags[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"), TEXT("Corsair880"), TEXT("Lagoon42") };
	if (int32(Type) <= 0 || int32(Type) >= int32(UE_ARRAY_COUNT(BoatTags)) || FParse::Param(FCommandLine::Get(), TEXT("SailingProceduralBoats"))) return M;
	const TCHAR* Tag = BoatTags[int32(Type)];
	auto Load = [Tag](const TCHAR* Part) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/%s/SM_%s_%s.SM_%s_%s"), Tag, Tag, Part, Tag, Part)); };
	M.Hull = Load(TEXT("Hull"));
	M.Mast = Load(TEXT("Mast"));
	M.Boom = Load(TEXT("Boom"));
	M.Rudder = Load(TEXT("Rudder"));
	if (!M.Hull || !M.Mast || !M.Boom || !M.Rudder) M = FBoatModelMeshes();
	return M;
}

UStaticMeshComponent* ASailboatPawn::AddModelPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& LocationCm)
{
	UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
	Part->SetupAttachment(Parent ? Parent : BoatRoot.Get());
	Part->SetStaticMesh(Mesh);
	Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Part->SetRelativeLocation(LocationCm);
	Part->RegisterComponent();
	BoatParts.Add(Part);
	return Part;
}

void ASailboatPawn::BuildModelVisuals(const FBoatModelMeshes& Model)
{
	ModelHull = AddModelPart(Model.Hull, BoatRoot, FVector::ZeroVector);
	// Graphics G3: this boat's livery and wear (sampled in RebuildBoatVisuals) on each hull slot.
	{
		const FBoatLivery& L = Livery;
		const TArray<FName> Slots = ModelHull->GetMaterialSlotNames();
		for (int32 I = 0; I < Slots.Num(); ++I)
		{
			UMaterialInstanceDynamic* Mid = ModelHull->CreateDynamicMaterialInstance(I);
			if (!Mid) continue;
			Mid->SetVectorParameterValue(TEXT("Wear"), FLinearColor(L.Wear.X, L.Wear.Y, L.Wear.Z, L.Wear.W));
			const FString Name = Slots[I].ToString();
			const FLinearColor* Col = Name == TEXT("Topsides") ? &L.Hull : Name == TEXT("Deck") ? &L.Deck : Name == TEXT("NonSkid") ? &L.NonSkid
				: Name == TEXT("Antifouling") ? &L.Bottom : Name == TEXT("Bootstripe") ? &L.Boot : Name == TEXT("CoveStripe") ? &L.Cove
				: Name == TEXT("Teak") ? (L.bTeak ? &L.Teak : &L.Deck) : nullptr;   // Graphics G6: the toe rails
			if (Col) Mid->SetVectorParameterValue(TEXT("Color"), *Col);
		}
	}
	// Boat detail pass: the cabin interior, same pivot as the hull; only on the player's boat (it shows through the
	// companionway and portlights, never from an AI boat's distance).
	if (Model.Interior && !bTrafficBoat && !bGhost)
	{
		AddModelPart(Model.Interior, BoatRoot, FVector::ZeroVector);
	}
	ModelMast = AddModelPart(Model.Mast, BoatRoot, ModelHull->GetSocketTransform(TEXT("MastStep"), RTS_Component).GetLocation());
	MastBendHeightCm = FMath::Max(Model.Mast->GetBounds().GetBox().Max.Z, 100.f);
	MastMaterial = ModelMast->CreateDynamicMaterialInstance(ModelMast->GetMaterialIndex(TEXT("Aluminium")) >= 0 ? ModelMast->GetMaterialIndex(TEXT("Aluminium")) : 0);
	// The boom hangs on the gooseneck pivot (placed from the physics rig); the rudder turns on its stock.
	ModelBoom = AddModelPart(Model.Boom, BoomPivot, FVector::ZeroVector);
	// Every rudder (the cats have two: RudderPivot, RudderPivot_1) turns on its own stock; the mesh is the same.
	for (int32 K = 0; ; ++K)
	{
		const FName Name = K == 0 ? FName(TEXT("RudderPivot")) : FName(*FString::Printf(TEXT("RudderPivot_%d"), K));
		if (!Model.Hull->FindSocket(Name)) break;
		USceneComponent* Pivot = NewObject<USceneComponent>(this);
		Pivot->SetupAttachment(BoatRoot);
		Pivot->SetRelativeLocation(ModelHull->GetSocketTransform(Name, RTS_Component).GetLocation());
		Pivot->RegisterComponent();
		BoatParts.Add(Pivot);
		RudderPivots.Add(Pivot);
		UStaticMeshComponent* Blade = AddModelPart(Model.Rudder, Pivot, FVector::ZeroVector); // built about its own stock
		if (K == 0) ModelRudder = Blade;
	}
	// Graphics G6: the berthed dress for the player's keelboat tied up in her slip (the marina's neighbours wear the same).
	StowedDress = nullptr;
	bStowedShown = false;
	const EBoatType Type = Boat.GetConfig().Type;
	if (!bTrafficBoat && !bGhost && (Type == EBoatType::J22 || Type == EBoatType::Catalina22 || Type == EBoatType::Catalina30))
	{
		const TCHAR* Tag = Type == EBoatType::J22 ? TEXT("J22") : (Type == EBoatType::Catalina22 ? TEXT("Catalina22") : TEXT("Catalina30"));
		if (UStaticMesh* Dress = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/%s/SM_%s_Berthed.SM_%s_Berthed"), Tag, Tag, Tag)))
		{
			StowedDress = AddModelPart(Dress, BoatRoot, FVector::ZeroVector);
			StowedDress->SetVisibility(false);
		}
	}
	// The traveler car slides along the bar with the trim.
	if (Model.Hull->FindSocket(TEXT("Traveler_C")))
	{
		TravelerCar = AddBoatPart(CubeMesh, ModelHull->GetSocketTransform(TEXT("Traveler_C"), RTS_Component).GetLocation(), FVector(8.f, 7.f, 3.f), FLinearColor(0.02f, 0.02f, 0.02f));
		if (CarMaterial) TravelerCar->SetMaterial(0, CarMaterial);
	}
}

FVector ASailboatPawn::RigPoint(const UStaticMeshComponent* Part, FName Socket) const
{
	FVector P = BoatRoot->GetComponentTransform().InverseTransformPosition(Part->GetSocketLocation(Socket));
	if (Part == ModelMast)
	{
		// The mast bends in its material (M_BoatMast): the same half-sine forward and a little aft at the head.
		const float T = FMath::Clamp(Part->GetSocketTransform(Socket, RTS_Component).GetLocation().Z / MastBendHeightCm, 0.f, 1.f);
		P.X += MastBendCm * (FMath::Sin(PI * T) - 0.35f * T * T);
	}
	return P;
}

void ASailboatPawn::UpdateModelRig(float DeltaSeconds)
{
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const float Aws = float(T.ApparentWindSpeed / 0.514444); // knots
	const float Breeze = FMath::Clamp((Aws - 8.f) / 12.f, 0.f, 1.f);

	// Mast bend: the backstay pulls the middle forward; the breeze adds to it (cm at mid-height).
	MastBendCm = FMath::FInterpTo(MastBendCm, 2.f + 7.f * float(Controls.Backstay) + 4.f * Breeze * Breeze, DeltaSeconds, 2.f);
	if (MastMaterial)
	{
		MastMaterial->SetScalarParameterValue(TEXT("BendCm"), MastBendCm);
		MastMaterial->SetScalarParameterValue(TEXT("BendHeightCm"), MastBendHeightCm);
	}

	// Sockets a class may not have (an unstayed ILCA has no shrouds, the Sunfish no jib): their lines are left out.
	auto Has = [](const UStaticMeshComponent* Part, const TCHAR* Socket) { return Part && Part->DoesSocketExist(Socket); };
	// Traveler car: centered at 0, toward the boom's side when eased down (1 = all the way to leeward).
	FVector Car = RigPoint(ModelBoom, TEXT("Boom_Mainsheet")) - FVector(0.f, 0.f, 60.f);
	if (TravelerCar && Has(ModelHull, TEXT("Traveler_S")))
	{
		const FVector TravC = RigPoint(ModelHull, TEXT("Traveler_C")), TravS = RigPoint(ModelHull, TEXT("Traveler_S"));
		const float BoomSide = S.BoomAngle >= 0.0 ? 1.f : -1.f;
		Car = TravC + (TravS - TravC) * FMath::Clamp(float(Controls.Traveler), -1.f, 1.f) * BoomSide;
		TravelerCar->SetRelativeLocation(Car + FVector(0.f, 0.f, 1.5f));
	}

	// Which side is to leeward: the side the boom (the sails) are on; the windward rig takes the load.
	const bool bLeeStbd = S.BoomAngle >= 0.0;
	const float Loaded = FMath::Clamp((Aws - 3.f) / 5.f, 0.f, 1.f); // below about 3 kn nothing is loaded

	TArray<FRigLine> Wires, Ropes;
	// Standing rigging: forestay, uppers via the spreaders, lowers, backstay (each where the class has it).
	const float WireR = 0.25f * FMath::Clamp(float(Boat.GetConfig().MastheadZ / 8.0), 0.8f, 2.4f);
	if (Has(ModelMast, TEXT("Hounds")))
	{
		const FVector Hounds = RigPoint(ModelMast, TEXT("Hounds"));
		if (Has(ModelHull, TEXT("ForestayTack"))) Wires.Add({ RigPoint(ModelHull, TEXT("ForestayTack")), Hounds, WireR, 0.f });
		for (const TCHAR* Tag : { TEXT("S"), TEXT("P") })
		{
			const bool bStbd = Tag[0] == TEXT('S');
			const bool bLee = bStbd == bLeeStbd;
			if (!Has(ModelHull, *FString::Printf(TEXT("ChainplateUpper_%s"), Tag))) continue;
			// The leeward shrouds go slack in a breeze (the windward ones carry the rig).
			const float Slack = bLee ? 0.0002f + 0.0007f * Breeze * FMath::Clamp(float(FMath::Abs(T.Heel)) / 0.1f, 0.f, 1.f) : 0.f;
			const FVector Upper = RigPoint(ModelHull, *FString::Printf(TEXT("ChainplateUpper_%s"), Tag));
			const FString TipName = FString::Printf(TEXT("SpreaderTip_%s"), Tag);
			if (Has(ModelMast, *TipName))
			{
				const FVector Tip = RigPoint(ModelMast, *TipName);
				Wires.Add({ Upper, Tip, WireR, Slack });
				Wires.Add({ Tip, Hounds, WireR, Slack });
				Wires.Add({ RigPoint(ModelHull, *FString::Printf(TEXT("ChainplateLower_%s"), Tag)), RigPoint(ModelMast, TEXT("LowerTang")), WireR, Slack });
			}
			else
			{
				Wires.Add({ Upper, Hounds, WireR, Slack });
			}
		}
		if (Has(ModelHull, TEXT("BackstayPlate")))
		{
			Wires.Add({ RigPoint(ModelHull, TEXT("BackstayPlate")), RigPoint(ModelMast, TEXT("MastheadAft")), WireR * 0.8f, 0.0008f * (1.f - float(Controls.Backstay)) * (1.f - Loaded) });
		}
	}

	// Jib sheets: the working sheet (leeward) from the clew through its lead to the winch, nearly straight under load;
	// the lazy sheet over the cabin top to the windward lead, drooping.
	if (Boat.GetConfig().HasJib() && Has(ModelHull, TEXT("JibLead_S")))
	{
		for (const TCHAR* Tag : { TEXT("S"), TEXT("P") })
		{
			const bool bWorking = (Tag[0] == TEXT('S')) == (S.JibSide > 0);
			const uint8 Look = Tag[0] == TEXT('S') ? RopeLook::JibStbd : RopeLook::JibPort;
			const FVector Lead = RigPoint(ModelHull, *FString::Printf(TEXT("JibLead_%s"), Tag));
			const FVector Winch = RigPoint(ModelHull, *FString::Printf(TEXT("JibWinch_%s"), Tag));
			if (bWorking)
			{
				Ropes.Add({ JibClewCm, Lead, 0.45f, FMath::Lerp(0.02f, 0.0005f, Loaded) + 0.004f * float(Controls.JibSheet) * (1.f - Loaded), Look });
			}
			else
			{
				const FVector Via = RigPoint(ModelHull, TEXT("LazySheetVia"));
				Ropes.Add({ JibClewCm, Via, 0.45f, 0.03f, Look });
				Ropes.Add({ Via, Lead, 0.45f, 0.05f, Look });
			}
			Ropes.Add({ Lead, Winch, 0.45f, bWorking ? 0.f : 0.02f, Look });
		}
	}

	// Graphics G6: the lines in the crew's hands. The working jib sheet's tail runs from its self-tailer to the trimmer's
	// nearer hand; the tiller extension from the tiller's end to the helm's nearer hand (no extension in the rudder model).
	auto HandNear = [this](int32 I, const FVector& To) -> TOptional<FVector>
	{
		if (!Crew.IsValidIndex(I) || !Crew[I] || !Crew[I]->IsVisible()) return {};
		const FTransform& Root = BoatRoot->GetComponentTransform();
		const FVector L = Root.InverseTransformPosition(Crew[I]->GetBoneLocation(TEXT("hand_l"), EBoneSpaces::WorldSpace));
		const FVector R = Root.InverseTransformPosition(Crew[I]->GetBoneLocation(TEXT("hand_r"), EBoneSpaces::WorldSpace));
		return FVector::DistSquared(L, To) < FVector::DistSquared(R, To) ? L : R;
	};
	const int32 NumCrew = Crew.Num();
	if (Boat.GetConfig().HasJib() && NumCrew >= 2 && Has(ModelHull, TEXT("JibTailer_S")))
	{
		// (Always drawn, so the rig mesh keeps its vertex count: with no hand in reach, down onto the seat.)
		const FVector Tailer = RigPoint(ModelHull, S.JibSide > 0 ? TEXT("JibTailer_S") : TEXT("JibTailer_P"));
		const TOptional<FVector> Hand = JibGripCm ? JibGripCm : HandNear(NumCrew - 2, Tailer);
		const FVector Tail = Hand && FVector::Dist(*Hand, Tailer) < 160.f ? *Hand : Tailer + FVector(-30.f, (S.JibSide > 0 ? -1.f : 1.f) * 12.f, -16.f);
		Ropes.Add({ Tailer, Tail, 0.45f, 0.03f, S.JibSide > 0 ? RopeLook::JibStbd : RopeLook::JibPort });
	}
	FVector End;
	if (TillerEndCm(End))
	{
		const TOptional<FVector> Hand = HelmGripCm ? HelmGripCm : (NumCrew >= 1 ? HandNear(NumCrew - 1, End) : TOptional<FVector>());
		// In the helm's hand, else lying back along the tiller.
		const FVector Stock = Has(ModelRudder, TEXT("RudderStock")) ? RigPoint(ModelRudder, TEXT("RudderStock"))
			: BoatRoot->GetComponentTransform().InverseTransformPosition(ModelRudder->GetComponentLocation()) + FVector(0.f, 0.f, End.Z);
		FVector Grip = Hand && FVector::Dist(*Hand, End) < 140.f ? *Hand
			: End + (Stock - End).GetSafeNormal() * 85.f + FVector(0.f, 3.5f, -2.f);
		// Round 10: a dinghy's extension runs on a hand's width past the dagger grip.
		const EBoatType Type = Boat.GetConfig().Type;
		if (HelmGripCm && (Type == EBoatType::ILCA7 || Type == EBoatType::Sunfish)) Grip += (Grip - End).GetSafeNormal() * 12.f;
		Wires.Add({ End + FVector(0.f, 0.f, 4.5f), Grip, 1.1f, 0.f, RopeLook::Plain });
	}

	// Mainsheet: a 4:1 tackle between the boom bail and the traveler car; taut when the main is drawing. Graphics G8: its
	// tail from the car to the helm's hand.
	MainsheetCarCm = Car;
	const FVector BoomBlock = RigPoint(ModelBoom, TEXT("Boom_Mainsheet"));
	const float MainSlack = FMath::Lerp(0.015f, 0.f, Loaded);
	// Round 10: the ILCA's sheet leads on from the boom's end block forward under the boom to a block over the front of the
	// cockpit and down to the ratchet block on its floor, and the tail comes up from there to the hand (it had run from the
	// transom to a hand out of reach). Elsewhere the tail comes off the traveler car.
	FCrewCockpitWell Well;
	if (Boat.GetConfig().Type == EBoatType::ILCA7 && CrewCockpitWell(Boat.GetConfig(), Well))
	{
		const FVector Ratchet = FVector(Well.X1 - 0.12, 0.0, Well.SoleZ + 0.07) * CmPerMeter;
		const FVector SheetLocal = ModelBoom->GetSocketTransform(TEXT("Boom_Mainsheet"), RTS_Component).GetLocation();
		const double Along = FMath::Clamp((Boat.GetConfig().MainLuffX - Ratchet.X / CmPerMeter) * CmPerMeter / FMath::Max(FMath::Abs(SheetLocal.X), 1.0), 0.1, 1.0);
		const FVector MidBlock = BoatRoot->GetComponentTransform().InverseTransformPosition(ModelBoom->GetComponentTransform().TransformPosition(SheetLocal * Along));
		Ropes.Add({ BoomBlock, MidBlock, 0.4f, 0.f });
		Ropes.Add({ MidBlock, Ratchet, 0.4f, MainSlack });
		Ropes.Add({ Ratchet, MainGripCm ? *MainGripCm : Ratchet + FVector(-30.f, 8.f, -4.f), 0.4f, MainGripCm ? 0.01f : 0.03f });
	}
	else
	{
		// (Always drawn, so the rig mesh keeps its vertex count: with no hand on it, a short tail onto the cockpit sole.)
		Ropes.Add({ Car + FVector(0.f, 0.f, 3.f), MainGripCm ? *MainGripCm : Car + FVector(-28.f, 6.f, -6.f), 0.4f, MainGripCm ? 0.01f : 0.04f });
	}
	for (int32 K = 0; K < 4; ++K)
	{
		const FVector Off(0.f, (K - 1.5f) * 1.2f, 0.f);
		Ropes.Add({ BoomBlock + Off, Car + FVector(0.f, 0.f, 3.f) + Off, 0.35f, MainSlack });
	}
	// Vang: a 3:1 tackle from the boom to the mast base, slack when eased off.
	if (Has(ModelBoom, TEXT("Boom_Vang")))
	{
		const FVector VangBoom = RigPoint(ModelBoom, TEXT("Boom_Vang")), VangMast = RigPoint(ModelMast, TEXT("MastBase"));
		for (int32 K = 0; K < 3; ++K)
		{
			const FVector Off(0.f, (K - 1.f) * 1.0f, 0.f);
			Ropes.Add({ VangBoom + Off, VangMast + Off, 0.3f, 0.02f * (1.f - float(Controls.Vang)), RopeLook::Vang });
		}
	}

	// Gravity in the boat frame (the boat heels and pitches).
	const FVector Down = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
	for (int32 Section = 0; Section < 2; ++Section)
	{
		const TArray<FRigLine>& Lines = Section == 0 ? Wires : Ropes;
		FTubeStreams Out;
		for (const FRigLine& L : Lines)
		{
			AppendTube(L, Down, Section == 0 ? 11.f : 5.f, Out, !bRigLinesBuilt);
		}
		if (!bRigLinesBuilt)
		{
			RigLines->CreateMeshSection_LinearColor(Section, Out.Verts, Out.Tris, Out.Normals, Out.UV0, Out.Colors, Out.Tangents, false);
			RigLines->SetMaterial(Section, Section == 0 ? WireMaterial.Get() : RopeMaterial.Get());
		}
		else
		{
			RigLines->UpdateMeshSection_LinearColor(Section, Out.Verts, Out.Normals, Out.UV0, Out.Colors, Out.Tangents);
		}
	}
	bRigLinesBuilt = true;
}

void ASailboatPawn::UpdateBoatWetness(float DeltaSeconds)
{
	// The material parameters are shared by every boat in view; the player's boat sets them.
	if (bTrafficBoat || !BoatParameters) return;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const Vec3 O = Boat.OriginPosition();
	// The hull is wet up to the highest recent water around it and dries back down at about 3 cm a minute.
	const double WaterHere = WaterSurfaceZ + GM->GetWaves().Height(O.X, O.Y, S.Time) * CmPerMeter;
	WetLineZ = FMath::Max(WetLineZ - DeltaSeconds * 0.05, WaterHere);
	const double Hs = GM->GetWaves().SignificantHeightAt(O.X, O.Y);
	const float Knots = float(T.SpeedThroughWater / 0.514444);
	// Splash band: the bow wave and the chop climb the topsides with speed and sea.
	const float Band = 4.f + float(Hs) * 45.f + FMath::Clamp(Knots - 3.f, 0.f, 6.f) * 2.5f;
	// Deck: rain soaks it within a minute; spray comes aboard upwind in a sea; it dries in about five minutes.
	const float Rain = float(GM->GetWeatherState().Rain);
	const float Spray = FMath::Clamp(float(Hs - 0.3) * 2.f, 0.f, 1.f) * FMath::Clamp((Knots - 3.f) / 3.f, 0.f, 1.f) * FMath::Clamp(float(FMath::Abs(T.Heel)) / 0.25f, 0.f, 1.f);
	DeckWetness = FMath::Clamp(DeckWetness + DeltaSeconds * (Rain * 0.03f + Spray * 0.01f - 0.0035f), 0.f, 1.f);
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("WaterZ"), float(WetLineZ));
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("WetBand"), Band);
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("DeckWet"), DeckWetness);
}

void ASailboatPawn::UpdateCrewFigures(float DeltaSeconds)
{
	// Visual V3: each sailor's stance and place from the physics crew model (CrewPose.h). Crew C1: placed here
	// (CrewPlacement, shared with the tests) with a minimum-jerk move on each change of stance; the joints are posed by each
	// sailor's animation node on the animation threads (CrewMotion.h: the stance, the reaction to the boat's motion,
	// breathing, the feet, hands and head). This hands each node its frame.
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FBoatConfig& Cfg = Boat.GetConfig();
	const int32 N = Crew.Num();
	double Rate = DeltaSeconds > 1e-4f ? (S.CrewOffset - PrevCrewOffset) / DeltaSeconds : 0.0;
	PrevCrewOffset = S.CrewOffset;
	// Round 10: a dinghy sailor's figure follows the crew model's offset through a critically damped spring (settled in about
	// 0.6 s). The auto-trim moves them in and out at up to 2.5 m/s with every roll (it holds her flat that way, and capsizes
	// on the heavy-air reach if it is slowed), which on the figure read as a body jerked to and fro across the boat.
	const bool bDinghyCrew = Cfg.Type == EBoatType::Sunfish || Cfg.Type == EBoatType::ILCA7 || Cfg.Type == EBoatType::Hobie16;
	double ShownOffset = S.CrewOffset;
	if (bDinghyCrew)
	{
		if (!bShownCrewOffset || T.bCapsized) { ShownCrewOffset = float(S.CrewOffset); ShownCrewOffsetV = 0.f; bShownCrewOffset = true; }
		CrewSpring(ShownCrewOffset, ShownCrewOffsetV, float(S.CrewOffset), 9.f, DeltaSeconds);
		ShownOffset = ShownCrewOffset;
		Rate = ShownCrewOffsetV;
	}
	const double BoomRate = DeltaSeconds > 1e-4f ? (S.BoomAngle - PrevBoomAngle) / DeltaSeconds : 0.0;
	PrevBoomAngle = S.BoomAngle;
	// Graphics G8: what the hands hold (round 8: open hands in the air read as a mannequin). The helm has the tiller
	// extension in the aft hand and the mainsheet in the other, the trimmer the working jib sheet's tail; the rest rest
	// their hands on their knees.
	HelmGripCm.Reset();
	MainGripCm.Reset();
	JibGripCm.Reset();
	FVector TillerEnd;
	const bool bTiller = TillerEndCm(TillerEnd);
	const bool bJibTail = Cfg.HasJib() && ModelHull && ModelHull->DoesSocketExist(TEXT("JibTailer_S"));
	const FVector Tailer = bJibTail ? RigPoint(ModelHull, S.JibSide > 0 ? TEXT("JibTailer_S") : TEXT("JibTailer_P")) : FVector::ZeroVector;
	const FTransform& RootTM = BoatRoot->GetComponentTransform();
	auto Has = [](const UStaticMeshComponent* Part, const TCHAR* Socket) { return Part && Part->DoesSocketExist(Socket); };

	// Crew C1: the boat's motion (boat frame) for each sailor's felt gravity.
	FCrewBoatMotion Motion;
	Motion.Gravity = RootTM.InverseTransformVectorNoScale(FVector(0.0, 0.0, -9.81));
	Motion.Accel = FVector(T.AccelBody.X, T.AccelBody.Y, T.AccelBody.Z);
	Motion.Omega = FVector(S.AngularVelocity.X, S.AngularVelocity.Y, S.AngularVelocity.Z);
	Motion.Alpha = FVector(T.AngularAccelBody.X, T.AngularAccelBody.Y, T.AngularAccelBody.Z);
	const FVector CG(Boat.GetCenterOfGravity().X, Boat.GetCenterOfGravity().Y, Boat.GetCenterOfGravity().Z);
	// What they look at (boat frame, cm): the jib's luff telltales, the water upwind for the next puff, ahead, and the next
	// mark or another boat close by (the player's crew; looked for once a second).
	const FVector Telltale = Has(ModelHull, TEXT("ForestayTack")) && Has(ModelMast, TEXT("Hounds"))
		? FMath::Lerp(RigPoint(ModelHull, TEXT("ForestayTack")), RigPoint(ModelMast, TEXT("Hounds")), 0.3f) + FVector(-35.f, 0.f, 0.f)
		: FVector(Cfg.MastX * CmPerMeter + 60.0, 0.0, 250.0);
	const FVector Upwind = FVector(FMath::Cos(T.TrueWindAngle), FMath::Sin(T.TrueWindAngle), 0.0) * 3500.0;
	const FVector Ahead(2500.0, 0.0, 80.0);
	if (!bTrafficBoat && S.Time >= NextGazeSearch)
	{
		NextGazeSearch = S.Time + 1.0;
		GazeBoatCm = FVector::ZeroVector;
		double Best = FMath::Square(250.0 * CmPerMeter);
		for (TActorIterator<ASailboatPawn> It(GetWorld()); It; ++It)
		{
			if (*It == this || It->bGhost) continue;
			const double D2 = FVector::DistSquared(It->GetActorLocation(), GetActorLocation());
			if (D2 < Best) { Best = D2; GazeBoatCm = RootTM.InverseTransformPosition(It->GetActorLocation() + FVector(0.0, 0.0, 150.0)); }
		}
		// Racing: the next mark before any boat (map metres are the physics frame's).
		const ATrafficManager* TM = ATrafficManager::Find(GetWorld());
		const FRaceRunner* Race = TM ? TM->GetRace() : nullptr;
		const FRaceEntry* Me = Race ? Race->FindEntry(FTrafficSim::PlayerId) : nullptr;
		if (Me && Me->bStarted && Me->NextMark < int32(Race->Course.Marks.size()))
		{
			const FRaceMark& M = Race->Course.Marks[Me->NextMark];
			const Vec3 O = Boat.OriginPosition();
			GazeBoatCm = RootTM.InverseTransformPosition(RootTM.GetLocation() + FVector(M.X - O.X, M.Y - O.Y, 0.0) * CmPerMeter);
		}
	}
	auto Hash = [](uint32 X) { X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16; return float(X & 0xffffff) / float(0x1000000); };

	for (int32 I = 0; I < N && I < CrewFigures.Num(); ++I)
	{
		FCrewPlaceInput Place;
		Place.Config = &Cfg;
		Place.Index = I;
		Place.CrewOffset = ShownOffset;
		Place.CrewOffsetZ = S.CrewOffsetZ;
		Place.CrewOffsetX = S.CrewOffsetX;
		Place.WindwardSide = S.WindwardSide;
		Place.OffsetRate = Rate;
		Place.bRighting = T.bCapsized && Controls.bRighting;
		Place.BoomAngle = S.BoomAngle;
		Place.BoomRate = BoomRate;
		Place.TrueWindAngle = T.TrueWindAngle;
		Place.TurnRate = S.AngularVelocity.Z;
		FCrewPlacement Pl;
		CrewPlacement(Place, Pl);
		const FCrewPoseParams& P = Pl.Params;
		const bool bHelm = Pl.bHelm;
		FCrewFigure& F = CrewFigures[I];
		const FCrewRig* Rig = MetaCrewRigs.IsValidIndex(F.Rig) ? &MetaCrewRigs[F.Rig] : nullptr;
		// The sailor's pelvis is 93 cm above the feet; a MetaHuman's is where its skeleton has it, turned with the figure.
		const FVector Location = Rig ? Pl.Pelvis * CmPerMeter - (FQuat(FRotator(0.f, Pl.Yaw, Pl.Roll)) * Rig->Frame.Inverse()).RotateVector(Rig->Pelvis)
			: Pl.Pelvis * CmPerMeter - FVector(0.f, 0.f, 93.f);
		if (!F.bStarted)
		{
			F.Location = F.FromLocation = Location;
			F.Yaw = F.FromYaw = Pl.Yaw;
			F.Roll = F.FromRoll = Pl.Roll;
			F.Stance = P.Stance;
			F.TransitionS = 1.f;
			F.bStarted = true;
		}
		else
		{
			// Crew C1: a change of stance moves by minimum jerk over its own time (not a fixed 7/s blend); between changes
			// the figure follows its place (the crew model's own motion is smooth).
			if (P.Stance != F.Stance)
			{
				F.TransitionSeconds = CrewTransitionSeconds(F.Stance, P.Stance);
				F.FromLocation = F.Location;
				F.FromYaw = F.Yaw;
				F.FromRoll = F.Roll;
				F.TransitionS = 0.f;
				F.Stance = P.Stance;
				++F.Transition;
			}
			F.TransitionS = FMath::Min(1.f, F.TransitionS + DeltaSeconds / FMath::Max(F.TransitionSeconds, 0.05f));
			const float W = CrewMinJerk(F.TransitionS);
			F.Location = FMath::Lerp(F.FromLocation, Location, W);
			F.Yaw = F.FromYaw + FMath::FindDeltaAngleDegrees(F.FromYaw, Pl.Yaw) * W;
			F.Roll = FMath::Lerp(F.FromRoll, Pl.Roll, W);
		}
		const FQuat Facing(FRotator(0.f, F.Yaw, 0.f) + FRotator(0.f, 0.f, F.Roll));
		const FQuat CompRot = Rig ? Facing * Rig->Frame.Inverse() : Facing;
		Crew[I]->SetRelativeLocationAndRotation(F.Location, CompRot);

		// The hands: targets in the boat frame from the shoulders as last posed, then into the figure's own frame.
		FCrewHands Hands;
		float Tension[2] = { 0.f, 0.f };
		const FTransform CompTM(CompRot, F.Location);
		const FVector Shoulder[2] = {
			RootTM.InverseTransformPosition(Crew[I]->GetBoneLocation(TEXT("upperarm_l"), EBoneSpaces::WorldSpace)),
			RootTM.InverseTransformPosition(Crew[I]->GetBoneLocation(TEXT("upperarm_r"), EBoneSpaces::WorldSpace)) };
		constexpr double Reach = 60.0; // shoulder to palm, cm
		auto Hold = [&](int32 Hand, const FVector& At, TOptional<FVector>& Grip)
		{
			if (FVector::Dist(At, Shoulder[Hand]) > Reach * 1.05) return false;
			Hands.Mode[Hand] = FCrewHands::EMode::Reach;
			Hands.Target[Hand] = CompTM.InverseTransformPosition(At);
			Hands.Grip[Hand] = 0.85f;
			Grip = At;
			return true;
		};
		// Crew C1: how hard each line pulls (the arms take it): the helm force at the tiller, the sails' load on the sheets.
		const float HelmLoad = float(FMath::Clamp(FMath::Abs(T.HelmForce) / 120.0, 0.0, 1.0));
		const float SheetLoad = float(FMath::Clamp(FMath::Sqrt(FMath::Square(T.DriveForce) + FMath::Square(T.HeelingForce)) / 2500.0, 0.0, 1.0));
		const bool bSeated = P.Stance == ECrewStance::Helm || P.Stance == ECrewStance::DinghyHike || P.Stance == ECrewStance::Cockpit
			|| P.Stance == ECrewStance::RailHike;
		if (bSeated && !bTrafficBoat)
		{
			const int32 Aft = Shoulder[0].X < Shoulder[1].X ? 0 : 1;
			const FVector Toward = FRotator(0.f, F.Yaw, 0.f).Vector();
			if (bHelm && bTiller && P.Stance == ECrewStance::DinghyHike)
			{
				// Round 10: a dinghy sailor holds the extension across the body, the aft hand in front of the chest (the dagger
				// grip), and the mainsheet coming up from its ratchet block in the forward hand just ahead of it (the ILCA's
				// hands had been held out to the sides: the hip-height grip and the keelboat's traveler car were out of reach).
				const FVector Chest = 0.5 * (Shoulder[0] + Shoulder[1]);
				// (A hand's width apart along the boat: together they read as folded arms.)
				if (Hold(Aft, Chest + Toward * 28.0 + FVector(-16.0, 0.0, -36.0), HelmGripCm)) Tension[Aft] = HelmLoad;
				if (Hold(1 - Aft, Chest + Toward * 32.0 + FVector(18.0, 0.0, -24.0), MainGripCm)) Tension[1 - Aft] = 0.6f * SheetLoad;
			}
			else if (bHelm && bTiller)
			{
				// The extension (about 90 cm) from the tiller's end up to the aft hand, held low beside the hip.
				const FVector ToShoulder = Shoulder[Aft] + FVector(0.f, 0.f, -32.f) - TillerEnd;
				const double Len = FMath::Min(90.0, ToShoulder.Size() - 25.0);
				if (Len > 20.0 && Hold(Aft, TillerEnd + ToShoulder.GetSafeNormal() * Len, HelmGripCm)) Tension[Aft] = HelmLoad;
				// The mainsheet's tail from its block on the car, held out in front at lap height.
				if (!MainsheetCarCm.IsZero())
				{
					const int32 Fwd = 1 - Aft;
					const FVector At = Shoulder[Fwd] + (MainsheetCarCm - Shoulder[Fwd]).GetSafeNormal() * 8.0 + Toward * 30.0 + FVector(0.f, 0.f, -36.f);
					if (Hold(Fwd, At, MainGripCm)) Tension[Fwd] = 0.6f * SheetLoad;
				}
			}
			else if (!bHelm && bJibTail && I == N - 2)
			{
				// The trimmer: the working sheet's tail a forearm's length off its self-tailer.
				const int32 Near = FVector::DistSquared(Shoulder[0], Tailer) < FVector::DistSquared(Shoulder[1], Tailer) ? 0 : 1;
				const FVector ToShoulder = Shoulder[Near] - Tailer;
				if (Hold(Near, Tailer + ToShoulder.GetSafeNormal() * FMath::Clamp(ToShoulder.Size() - 40.0, 25.0, 55.0), JibGripCm)) Tension[Near] = 0.4f * SheetLoad;
			}
			for (int32 Hand = 0; Hand < 2; ++Hand)
			{
				if (Hands.Mode[Hand] == FCrewHands::EMode::Free && P.Stance != ECrewStance::DinghyHike) Hands.Mode[Hand] = FCrewHands::EMode::Knee;
			}
		}

		// Crew C1: the frame for this sailor's animation node.
		UCrewAnimInstance* Anim = Cast<UCrewAnimInstance>(Crew[I]->GetAnimInstance());
		if (!Anim) continue;
		FCrewMotionInput In;
		In.Params = P;
		In.Transition = F.Transition;
		In.TransitionSeconds = F.TransitionSeconds;
		In.Duck = Pl.Duck;
		In.ToBoat = CompTM;
		In.Motion = Motion;
		In.SeatFromCG = Pl.Pelvis - CG;
		In.Hands = Hands;
		In.Tension[0] = Tension[0];
		In.Tension[1] = Tension[1];
		In.Time = float(S.Time);
		In.Seed = uint32(I) * 977u + (bTrafficBoat ? GetUniqueID() : 0u);
		In.bReact = !FParse::Param(FCommandLine::Get(), TEXT("SailingCrewStill"));
		// The handholds and braces: the model's sockets (J22H_sockets.json names) where it has them, else from the geometry.
		CrewDerivedAttachPoints(Cfg, Pl.Pelvis.X, In.Attach);
		for (int32 Sd = 0; Sd < 2; ++Sd)
		{
			const TCHAR* Sx = Sd == 0 ? TEXT("_S") : TEXT("_P");
			auto Socket = [&](const TCHAR* Name, FVector& Out) { const FString Full = FString(Name) + Sx; if (Has(ModelHull, *Full)) Out = RigPoint(ModelHull, FName(*Full)); };
			Socket(TEXT("HandholdCabin"), In.Attach.HandholdCabin[Sd]);
			Socket(TEXT("HandholdCoaming"), In.Attach.HandholdCoaming[Sd]);
			Socket(TEXT("Seat"), In.Attach.Seat[Sd]);
			Socket(TEXT("FootBrace"), In.Attach.FootBrace[Sd]);
			Socket(TEXT("SideDeck"), In.Attach.SideDeck[Sd]);
		}
		// Glances of a couple of seconds: the helm and trimmer mostly at the telltales, the bow ahead and upwind.
		const float Slot = FMath::FloorToFloat((float(S.Time) + 1.7f * I) / 2.4f);
		const float R = Hash(In.Seed * 131u + uint32(int32(Slot)));
		const bool bOther = !GazeBoatCm.IsZero();
		if (P.Stance == ECrewStance::Crossing) In.Gaze = Ahead;
		else if (bHelm || I == N - 2) In.Gaze = R < 0.5f ? Telltale : R < 0.72f ? Upwind : R < 0.9f || !bOther ? Ahead : GazeBoatCm;
		else In.Gaze = R < 0.4f ? Ahead : R < 0.75f || !bOther ? Upwind : GazeBoatCm;
		Anim->SetMotionInput(In);
		// Stills of a tack: -SailingShotCrew=<name> saves Saved/Bench/<name>.png once the helm is crouched under the boom.
		static SailingArgs::FOnce CrewShotTaken;
		FString CrewShot;
		if (!CrewShotTaken.Taken() && bHelm && !bTrafficBoat && Pl.Duck > 0.8f && F.TransitionS > 0.9f && FParse::Value(FCommandLine::Get(), TEXT("SailingShotCrew="), CrewShot))
		{
			CrewShotTaken.Take();
			FScreenshotRequest::RequestScreenshot(FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.png"), *CrewShot)), false, false);
		}
		static double LastDebug = 0.0;
		if (FParse::Param(FCommandLine::Get(), TEXT("SailingDebugCrew")) && S.Time - LastDebug > 1.0 && !bTrafficBoat)
		{
			if (I == N - 1) LastDebug = S.Time;
			const FCrewMotionReport& Rep = Anim->GetReport();
			UE_LOG(LogTemp, Log, TEXT("Crew %d stance %d duck %.2f: modes %d %d, felt %s, tip %.2f%s, head %.1f deg; accel %s omega %s alpha %s"), I, int32(P.Stance), Pl.Duck,
				int32(Hands.Mode[0]), int32(Hands.Mode[1]), *Rep.Felt.ToString(), Rep.TipRatio, Rep.bBracing ? TEXT(" bracing") : TEXT(""), Rep.HeadTiltDeg,
				*Motion.Accel.ToString(), *Motion.Omega.ToString(), *Motion.Alpha.ToString());
		}
	}
}

bool ASailboatPawn::TillerEndCm(FVector& Out) const
{
	// Graphics G8: the end of the tiller, where the extension is hinged: a socket on the J/22's rudder; the fleet's tillered
	// boats build theirs from the config (Tools/blender/build_fleet.py: TillerLength forward of the stock, 16 cm over the
	// transom's sheer).
	if (!ModelRudder) return false;
	if (ModelRudder->DoesSocketExist(TEXT("TillerEnd")))
	{
		Out = RigPoint(ModelRudder, TEXT("TillerEnd"));
		return true;
	}
	const FBoatConfig& Cfg = Boat.GetConfig();
	switch (Cfg.Type)
	{
	case EBoatType::Sunfish: case EBoatType::ILCA7: case EBoatType::Catalina22: case EBoatType::Corsair880: break;
	default: return false;
	}
	const FHullShape& Hull = Cfg.Hulls[0];
	const FVector Local(float(Cfg.TillerLength), 0.f, float(Hull.SheerHeight(Hull.SternX) + 0.16));
	Out = BoatRoot->GetComponentTransform().InverseTransformPosition(ModelRudder->GetComponentTransform().TransformPosition(Local * CmPerMeter));
	return true;
}
