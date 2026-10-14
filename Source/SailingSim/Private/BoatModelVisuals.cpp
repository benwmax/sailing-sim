// Visual V2: the modelled boats (the J/22 first). The pawn's other visuals live in SailboatPawn.cpp.
//
// A class with a model (Tools/blender/build_<boat>.py, imported by scripts/make-boat-models.sh) shows its hull, mast,
// boom and rudder meshes instead of the procedural hull and shapes. The standing and running rigging is drawn here
// every frame from the meshes' sockets, with sag from the physics: a loaded sheet or the windward shroud runs straight,
// an eased or lazy sheet droops, the leeward shroud goes slack in a breeze. The mast bends with the backstay and the
// wind (its material's world position offset; the rig points on it follow the same curve), the traveler car moves
// with the trim, and the hull's wet line and the deck's wetness come from the waves, spray and rain (MPC_Boat).
#include "SailboatPawn.h"
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
#include "Components/PoseableMeshComponent.h"
#include "CrewPose.h"

using namespace Sailing;

namespace
{
	constexpr int32 kLineSides = 6;
	constexpr int32 kLineSegments = 10;

	/** One drawn line: from A to B (boat frame, cm), its radius, and its slack (extra length as a fraction). */
	struct FRigLine
	{
		FVector A, B;
		float RadiusCm;
		float Slack;
	};

	/** Mid-span sag of a line of length L with a small extra length fraction e: a parabola with e = 8/3 (s/L)^2. */
	float SagFor(float LengthCm, float Slack)
	{
		return LengthCm * FMath::Sqrt(FMath::Max(Slack, 0.f) * 3.f / 8.f);
	}

	void AppendTube(const FRigLine& L, const FVector& Down, TArray<FVector>& Verts, TArray<FVector>& Normals, TArray<int32>* Tris)
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
		const int32 Base = Verts.Num();
		for (int32 I = 0; I <= kLineSegments; ++I)
		{
			const float T = float(I) / kLineSegments;
			const FVector C = L.A + D * T + Sag * (4.f * T * (1.f - T));
			for (int32 K = 0; K < kLineSides; ++K)
			{
				const float A = 2.f * PI * K / kLineSides;
				const FVector N = U * FMath::Cos(A) + W * FMath::Sin(A);
				Verts.Add(C + N * L.RadiusCm);
				Normals.Add(N);
			}
		}
		if (!Tris) return;
		for (int32 I = 0; I < kLineSegments; ++I)
		{
			for (int32 K = 0; K < kLineSides; ++K)
			{
				const int32 A0 = Base + I * kLineSides + K, A1 = Base + I * kLineSides + (K + 1) % kLineSides;
				const int32 B0 = A0 + kLineSides, B1 = A1 + kLineSides;
				Tris->Append({ A0, B0, B1, A0, B1, A1 });
			}
		}
	}
}

ASailboatPawn::FBoatModelMeshes ASailboatPawn::ModelMeshesFor(EBoatType Type) const
{
	FBoatModelMeshes M;
	if (Type == EBoatType::J22 && J22HullMesh && J22MastMesh && J22BoomMesh && J22RudderMesh)
	{
		M.Hull = J22HullMesh;
		M.Mast = J22MastMesh;
		M.Boom = J22BoomMesh;
		M.Rudder = J22RudderMesh;
		return M;
	}
	// Visual V7: the other seven from Tools/blender/build_fleet.py (scripts/make-boat-models.sh), loaded by class.
	static const TCHAR* Tags[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"), TEXT("Corsair880"), TEXT("Lagoon42") };
	if (int32(Type) <= 0 || int32(Type) >= int32(UE_ARRAY_COUNT(Tags)) || FParse::Param(FCommandLine::Get(), TEXT("SailingProceduralBoats"))) return M;
	const TCHAR* Tag = Tags[int32(Type)];
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
				: Name == TEXT("Antifouling") ? &L.Bottom : Name == TEXT("Bootstripe") ? &L.Boot : Name == TEXT("CoveStripe") ? &L.Cove : nullptr;
			if (Col) Mid->SetVectorParameterValue(TEXT("Color"), *Col);
		}
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
			const FVector Lead = RigPoint(ModelHull, *FString::Printf(TEXT("JibLead_%s"), Tag));
			const FVector Winch = RigPoint(ModelHull, *FString::Printf(TEXT("JibWinch_%s"), Tag));
			if (bWorking)
			{
				Ropes.Add({ JibClewCm, Lead, 0.45f, FMath::Lerp(0.02f, 0.0005f, Loaded) + 0.004f * float(Controls.JibSheet) * (1.f - Loaded) });
			}
			else
			{
				const FVector Via = RigPoint(ModelHull, TEXT("LazySheetVia"));
				Ropes.Add({ JibClewCm, Via, 0.45f, 0.03f });
				Ropes.Add({ Via, Lead, 0.45f, 0.05f });
			}
			Ropes.Add({ Lead, Winch, 0.45f, bWorking ? 0.f : 0.02f });
		}
	}

	// Graphics G6: the lines in the crew's hands. The working jib sheet's tail runs from its self-tailer to the trimmer's
	// nearer hand; the tiller extension from the tiller's end to the helm's nearer hand (no extension in the rudder model).
	auto HandNear = [this](int32 I, const FVector& To) -> TOptional<FVector>
	{
		if (!Crew.IsValidIndex(I) || !Crew[I] || !Crew[I]->IsVisible()) return {};
		const FTransform& Root = BoatRoot->GetComponentTransform();
		const FVector L = Root.InverseTransformPosition(Crew[I]->GetBoneLocationByName(TEXT("hand_l"), EBoneSpaces::WorldSpace));
		const FVector R = Root.InverseTransformPosition(Crew[I]->GetBoneLocationByName(TEXT("hand_r"), EBoneSpaces::WorldSpace));
		return FVector::DistSquared(L, To) < FVector::DistSquared(R, To) ? L : R;
	};
	const int32 NumCrew = Crew.Num();
	if (Boat.GetConfig().HasJib() && NumCrew >= 2 && Has(ModelHull, TEXT("JibTailer_S")))
	{
		// (Always drawn, so the rig mesh keeps its vertex count: with no hand in reach, down onto the seat.)
		const FVector Tailer = RigPoint(ModelHull, S.JibSide > 0 ? TEXT("JibTailer_S") : TEXT("JibTailer_P"));
		const TOptional<FVector> Hand = HandNear(NumCrew - 2, Tailer);
		const FVector Tail = Hand && FVector::Dist(*Hand, Tailer) < 160.f ? *Hand : Tailer + FVector(-30.f, (S.JibSide > 0 ? -1.f : 1.f) * 12.f, -16.f);
		Ropes.Add({ Tailer, Tail, 0.45f, 0.03f });
	}
	if (ModelRudder && Has(ModelRudder, TEXT("TillerEnd")))
	{
		const FVector End = RigPoint(ModelRudder, TEXT("TillerEnd"));
		const TOptional<FVector> Hand = NumCrew >= 1 ? HandNear(NumCrew - 1, End) : TOptional<FVector>();
		// In the helm's hand, else lying back along the tiller.
		const FVector Grip = Hand && FVector::Dist(*Hand, End) < 140.f ? *Hand
			: End + (RigPoint(ModelRudder, TEXT("RudderStock")) - End).GetSafeNormal() * 85.f + FVector(0.f, 3.5f, -2.f);
		Wires.Add({ End + FVector(0.f, 0.f, 4.5f), Grip, 1.1f, 0.f });
	}

	// Mainsheet: a 4:1 tackle between the boom bail and the traveler car; taut when the main is drawing.
	const FVector BoomBlock = RigPoint(ModelBoom, TEXT("Boom_Mainsheet"));
	const float MainSlack = FMath::Lerp(0.015f, 0.f, Loaded);
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
			Ropes.Add({ VangBoom + Off, VangMast + Off, 0.3f, 0.02f * (1.f - float(Controls.Vang)) });
		}
	}

	// Gravity in the boat frame (the boat heels and pitches).
	const FVector Down = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
	for (int32 Section = 0; Section < 2; ++Section)
	{
		const TArray<FRigLine>& Lines = Section == 0 ? Wires : Ropes;
		TArray<FVector> Verts, Normals;
		TArray<int32> Tris;
		for (const FRigLine& L : Lines)
		{
			AppendTube(L, Down, Verts, Normals, bRigLinesBuilt ? nullptr : &Tris);
		}
		if (!bRigLinesBuilt)
		{
			RigLines->CreateMeshSection_LinearColor(Section, Verts, Tris, Normals, {}, {}, {}, false);
			RigLines->SetMaterial(Section, Section == 0 ? WireMaterial.Get() : RopeMaterial.Get());
		}
		else
		{
			RigLines->UpdateMeshSection_LinearColor(Section, Verts, Normals, {}, {}, {});
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
	const double Hs = GM->GetWaves().SignificantHeight();
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
	// Visual V3: each sailor's stance and place from the physics crew model (CrewPose.h), blended over a fraction of a
	// second so a tack or a hike reads as movement, not a cut.
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FBoatConfig& Cfg = Boat.GetConfig();
	const FHullShape& Hull = Cfg.Hulls[0];
	const int32 N = Crew.Num();
	const double Rate = DeltaSeconds > 1e-4f ? (S.CrewOffset - PrevCrewOffset) / DeltaSeconds : 0.0;
	PrevCrewOffset = S.CrewOffset;
	const bool bDinghy = Cfg.Type == EBoatType::Sunfish || Cfg.Type == EBoatType::ILCA7 || Cfg.Type == EBoatType::Hobie16;
	const float Side = S.CrewOffset != 0.0 ? float(FMath::Sign(S.CrewOffset)) : float(S.WindwardSide);
	const double Out = FMath::Abs(S.CrewOffset);
	const float Blend = 1.f - FMath::Exp(-DeltaSeconds * 7.f);
	for (int32 I = 0; I < N && I < CrewFigures.Num(); ++I)
	{
		const double X = Cfg.CrewCG.X + 0.55 * (0.5 * (N - 1) - I);
		const double Rail = Cfg.bMultihull ? FMath::Abs(Cfg.Hulls.back().CenterY) + 0.2 : Hull.DeckHalfBeam(X);
		const double Sheer = Cfg.bMultihull ? Hull.SheerZ + 0.1 : Hull.SheerHeight(X);
		const bool bHelm = I == N - 1;
		FCrewPoseParams P;
		P.Side = Side;
		P.Hike = float(FMath::Clamp((Out - Cfg.CrewSitOut * 0.8) / FMath::Max(Cfg.CrewHikeOut, 0.1), 0.0, 1.0));
		FVector Pelvis;
		float Roll = 0.f;
		if (T.bCapsized && Controls.bRighting)
		{
			P.Stance = ECrewStance::Righting;
			Pelvis = FVector(X, S.CrewOffset, Sheer + 0.45 + S.CrewOffsetZ);
		}
		else if (Cfg.bTrapeze && !bHelm && Out > Rail)
		{
			// On the wire: feet on the rail, body out over the water.
			P.Stance = ECrewStance::Trapeze;
			Pelvis = FVector(X, Side * (Rail + 0.8), Sheer + 0.35);
			Roll = 72.f * Side;
		}
		else if (FMath::Abs(Rate) > 0.6)
		{
			P.Stance = ECrewStance::Crossing;
			P.Side = -float(FMath::Sign(Rate)); // facing the side they are heading for
			Pelvis = FVector(X, S.CrewOffset, Sheer + (bDinghy ? 0.25 : 0.05));
		}
		else if (bDinghy)
		{
			P.Stance = ECrewStance::DinghyHike;
			Pelvis = FVector(X, Side * (Rail - 0.04), Sheer + 0.06);
		}
		else if (bHelm)
		{
			P.Stance = ECrewStance::Helm;
			Pelvis = FVector(X, Side * FMath::Max(Rail - 0.18, 0.3), Sheer + 0.07);
		}
		else if (Out > 0.55 * Rail)
		{
			P.Stance = ECrewStance::RailHike;
			Pelvis = FVector(X, Side * (Rail - 0.02), Sheer + 0.07);
		}
		else
		{
			// Light air or downwind: on the cockpit seat (to leeward if the crew model put them there).
			P.Stance = ECrewStance::Cockpit;
			Pelvis = FVector(X, Side * FMath::Clamp(Out, 0.35, FMath::Max(Rail - 0.45, 0.35)), Sheer - 0.10);
		}
		TMap<FName, FQuat> Target;
		CrewJointRotations(P, Target);
		FCrewFigure& F = CrewFigures[I];
		const FCrewRig* Rig = MetaCrewRigs.IsValidIndex(F.Rig) ? &MetaCrewRigs[F.Rig] : nullptr;
		const float Yaw = CrewFacingYaw(P);
		// The sailor's pelvis is 93 cm above the feet; a MetaHuman's is where its skeleton has it, turned with the figure.
		const FVector Location = Rig ? Pelvis * CmPerMeter - (FQuat(FRotator(0.f, Yaw, Roll)) * Rig->Frame.Inverse()).RotateVector(Rig->Pelvis)
			: Pelvis * CmPerMeter - FVector(0.f, 0.f, 93.f);
		if (!F.bStarted)
		{
			F.Joints = Target;
			F.Location = Location;
			F.Yaw = Yaw;
			F.Roll = Roll;
			F.bStarted = true;
		}
		else
		{
			for (TPair<FName, FQuat>& J : F.Joints) J.Value = FQuat::Slerp(J.Value, Target.Contains(J.Key) ? Target[J.Key] : FQuat::Identity, Blend);
			for (const TPair<FName, FQuat>& J : Target) if (!F.Joints.Contains(J.Key)) F.Joints.Add(J.Key, FQuat::Slerp(FQuat::Identity, J.Value, Blend));
			F.Location = FMath::Lerp(F.Location, Location, Blend);
			F.Yaw = F.Yaw + FMath::FindDeltaAngleDegrees(F.Yaw, Yaw) * Blend;
			F.Roll = FMath::Lerp(F.Roll, Roll, Blend);
		}
		const FQuat Facing(FRotator(0.f, F.Yaw, 0.f) + FRotator(0.f, 0.f, F.Roll));
		Crew[I]->SetRelativeLocationAndRotation(F.Location, Rig ? Facing * Rig->Frame.Inverse() : Facing);
		ApplyCrewPose(Crew[I], F.Joints, Rig);
	}
}
