// Visual V2: the modelled boats (the J/22 first). The pawn's other visuals live in SailboatPawn.cpp.
//
// A class with a model (Tools/blender/build_<boat>.py, imported by scripts/make-boat-models.sh) shows its hull, mast,
// boom and rudder meshes instead of the procedural hull and shapes. The standing and running rigging is drawn here
// every frame from the meshes' sockets, with sag from the physics: a loaded sheet or the windward shroud runs straight,
// an eased or lazy sheet droops, the leeward shroud goes slack in a breeze. The mast bends with the backstay and the
// wind (its material's world position offset; the rig points on it follow the same curve), the traveler car moves
// with the trim, and the hull's wet line and the deck's wetness come from the waves, spray and rain (MPC_Boat).
#include "SailboatPawn.h"
#include "SailingFrame.h"
#include "Components/InstancedStaticMeshComponent.h"
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
#include "BoatPacks.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "ProceduralMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
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
		const TCHAR* Name = TEXT(""); // what the line is (the rig clearance test's reports): set by Label after each group
		// Rig clearance: how far each ring of the tube is lifted to lie over the boat instead of through it (a lazy sheet
		// over the cabin top, a sheet led up to a coachroof winch): DrapeOverBoat.
		float Lift[kLineSegments + 1] = {};
	};

	FVector LinePoint(const FRigLine& L, const FVector& Sag, int32 I)
	{
		const float T = float(I) / kLineSegments;
		return L.A + (L.B - L.A) * T + Sag * (4.f * T * (1.f - T)) + FVector(0.f, 0.f, L.Lift[I]);
	}

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

	/** The mid-span sag of a line: across it, in the plane of the line and gravity. */
	FVector SagOf(const FRigLine& L, const FVector& Down)
	{
		const FVector D = L.B - L.A;
		const float Len = D.Size();
		const FVector Dir = Len > 1e-3f ? D / Len : FVector::UpVector;
		const FVector Sag = Down - FVector::DotProduct(Down, Dir) * Dir;
		return Sag.GetSafeNormal() * SagFor(Len, L.Slack);
	}

	/** pc/rig-lines: the camera for the on-screen minimum width (boat frame), or off. */
	struct FLineWidening
	{
		FVector Eye = FVector::ZeroVector;
		float PxAngle = 0.f;   // radians per pixel across the view
		bool bOn = false;
	};

	/** pc/rig-lines (docs/rig-lines): a ring's drawn radius, at least kMinLinePx across at its own distance from the camera.
	 *  It steps by a quarter at a time (Exponent counts the steps), so a moving camera changes a line only now and then. */
	constexpr float kMinLinePx = 1.2f;
	float RingRadius(float RadiusCm, const FVector& C, const FLineWidening& W, int32* Exponent = nullptr)
	{
		const float MinR = W.bOn ? 0.5f * kMinLinePx * W.PxAngle * float(FVector::Dist(W.Eye, C)) : 0.f;
		if (MinR <= RadiusCm || RadiusCm <= 0.f) return RadiusCm;
		const float Steps = FMath::CeilToFloat(FMath::Loge(MinR / RadiusCm) / FMath::Loge(1.25f));
		if (Exponent) *Exponent += int32(Steps);
		return RadiusCm * FMath::Pow(1.25f, Steps);
	}

	/** Round the tube: the ring's cosines and sines, worked out once. */
	struct FRingTable
	{
		float Cos[kLineSides + 1], Sin[kLineSides + 1];
		FRingTable()
		{
			for (int32 K = 0; K <= kLineSides; ++K)
			{
				Cos[K] = FMath::Cos(2.f * PI * K / kLineSides);
				Sin[K] = FMath::Sin(2.f * PI * K / kLineSides);
			}
		}
	};

	void AppendTube(const FRigLine& L, const FVector& Sag, float LayDiameters, const FLineWidening& Widen, FTubeStreams& Out, bool bTris)
	{
		static const FRingTable Ring;
		const FVector D = L.B - L.A;
		const float Len = D.Size();
		const FVector Dir = Len > 1e-3f ? D / Len : FVector::UpVector;
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
			const FVector C = LinePoint(L, Sag, I);
			Arc += FVector::Dist(C, Prev);
			Prev = C;
			// Along the sagged curve: the parabola's derivative (and the drape's, between its neighbours).
			const FVector Along = (D + Sag * (4.f - 8.f * T)).GetSafeNormal()
				+ FVector(0.f, 0.f, (L.Lift[FMath::Min(I + 1, kLineSegments)] - L.Lift[FMath::Max(I - 1, 0)]) / FMath::Max(2.f * Len / kLineSegments, 1.f));
			const FProcMeshTangent Tangent(Along.GetSafeNormal(), false);
			const float UArc = Arc / Lay;
			const float R = RingRadius(L.RadiusCm, C, Widen);
			for (int32 K = 0; K <= kLineSides; ++K)
			{
				const FVector N = U * Ring.Cos[K] + W * Ring.Sin[K];
				Out.Verts.Add(C + N * R);
				Out.Normals.Add(N);
				Out.UV0.Add(FVector2D(UArc, float(K) / kLineSides));
				if (bTris) Out.Colors.Add(Look); // the look never changes: sent once, at build (an update skips an empty stream)
				Out.Tangents.Add(Tangent);
			}
		}
		if (!bTris) return;
		constexpr int32 RingVerts = kLineSides + 1;
		for (int32 I = 0; I < kLineSegments; ++I)
		{
			for (int32 K = 0; K < kLineSides; ++K)
			{
				const int32 A0 = Base + I * RingVerts + K, A1 = A0 + 1;
				const int32 B0 = A0 + RingVerts, B1 = A1 + RingVerts;
				Out.Tris.Append({ A0, B0, B1, A0, B1, A1 });
			}
		}
	}

	/** Boat fidelity 4: a rope along a polyline (a coiled tail), Catmull-Rom smoothed (two steps per span), its rings carried
	 *  along by parallel transport so the braid doesn't twist; the same streams as AppendTube (U over 5 diameters). */
	void AppendPolyTube(const TArray<FVector>& P, float RadiusCm, uint8 Look, FTubeStreams& Out)
	{
		static const FRingTable Ring;
		if (P.Num() < 2) return;
		TArray<FVector> C;
		for (int32 I = 0; I + 1 < P.Num(); ++I)
		{
			const FVector P0 = P[FMath::Max(I - 1, 0)], P1 = P[I], P2 = P[I + 1], P3 = P[FMath::Min(I + 2, P.Num() - 1)];
			for (int32 S = 0; S < 2; ++S)
			{
				const float T = S * 0.5f, T2 = T * T, T3 = T2 * T;
				C.Add(0.5f * (2.f * P1 + (P2 - P0) * T + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * T2 + (3.f * P1 - P0 - 3.f * P2 + P3) * T3));
			}
		}
		C.Add(P.Last());
		const int32 Base = Out.Verts.Num();
		const float Lay = 5.f * 2.f * RadiusCm;
		const FLinearColor Col(float(Look) / 255.f, 0.f, 0.f, 1.f);
		FVector Along = (C[1] - C[0]).GetSafeNormal();
		FVector U = FVector::CrossProduct(Along, FMath::Abs(Along.Z) < 0.9f ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
		float Arc = 0.f;
		for (int32 I = 0; I < C.Num(); ++I)
		{
			const FVector NewAlong = (C[FMath::Min(I + 1, C.Num() - 1)] - C[FMath::Max(I - 1, 0)]).GetSafeNormal();
			U = (U - FVector::DotProduct(U, NewAlong) * NewAlong).GetSafeNormal();   // parallel transport
			Along = NewAlong;
			const FVector W = FVector::CrossProduct(Along, U);
			if (I > 0) Arc += FVector::Dist(C[I], C[I - 1]);
			const FProcMeshTangent Tangent(Along, false);
			for (int32 K = 0; K <= kLineSides; ++K)
			{
				const FVector N = U * Ring.Cos[K] + W * Ring.Sin[K];
				Out.Verts.Add(C[I] + N * RadiusCm);
				Out.Normals.Add(N);
				Out.UV0.Add(FVector2D(Arc / Lay, float(K) / kLineSides));
				Out.Colors.Add(Col);
				Out.Tangents.Add(Tangent);
			}
		}
		constexpr int32 RingVerts = kLineSides + 1;
		for (int32 I = 0; I + 1 < C.Num(); ++I)
		{
			for (int32 K = 0; K < kLineSides; ++K)
			{
				const int32 A0 = Base + I * RingVerts + K, A1 = A0 + 1;
				const int32 B0 = A0 + RingVerts, B1 = A1 + RingVerts;
				Out.Tris.Append({ A0, B0, B1, A0, B1, A1 });
			}
		}
	}

#include "J22CoilData.inl"
}

ASailboatPawn::FBoatModelMeshes ASailboatPawn::ModelMeshesFor(EBoatType Type) const
{
	FBoatModelMeshes M;
	// Boats 10: the script-built hero J/22 (Inputs/j22-hero, imported to /Game/Boats/J22Hero by scripts/import_j22_hero.py)
	// in the J/22's place, with the same sockets. Since round 12 it is the player's boat (the blind test caught the older
	// model's lifelines, grey box outboard and flat surfaces); AI boats and the ghost keep the light model and their
	// liveries. -SailingClassicJ22 compares with the older model; -SailingJ22Hero puts the hero on AI boats too.
	const bool bHero = Type == EBoatType::J22 && !FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicJ22"))
		&& ((!bTrafficBoat && !bGhost) || FParse::Param(SailingArgs::Dev(), TEXT("SailingJ22Hero")));
	if (bHero)
	{
		auto LoadHero = [](const TCHAR* Part) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/J22Hero/SM_J22H_%s.SM_J22H_%s"), Part, Part)); };
		M.Hull = LoadHero(TEXT("Hull"));
		M.Mast = LoadHero(TEXT("Mast"));
		M.Boom = LoadHero(TEXT("Boom"));
		M.Rudder = LoadHero(TEXT("Rudder"));
		// Boat detail pass: the cabin below decks (optional: older imports have none).
		M.Interior = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, TEXT("/Game/Boats/J22Hero/SM_J22H_Interior.SM_J22H_Interior"), nullptr, LOAD_NoWarn | LOAD_Quiet));
		// and its glass: the smoked portlights and fore hatch over the cabin, and the bilge water (translucent, M_J22HeroGlass).
		M.Glass = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, TEXT("/Game/Boats/J22Hero/SM_J22H_Glass.SM_J22H_Glass"), nullptr, LOAD_NoWarn | LOAD_Quiet));
		M.bOwnOutboard = true; // on its bracket on the port quarter (build_j22_hero.py)
		M.bTravelerBridge = false; // its traveler track lies on the cockpit sole
		if (M.Hull && M.Mast && M.Boom && M.Rudder) return M;
		M = FBoatModelMeshes();
	}
	if (Type == EBoatType::J22 && J22HullMesh && J22MastMesh && J22BoomMesh && J22RudderMesh)
	{
		M.Hull = J22HullMesh;
		M.Mast = J22MastMesh;
		M.Boom = J22BoomMesh;
		M.Rudder = J22RudderMesh;
		M.bOwnOutboard = J22HullMesh->FindSocket(TEXT("Outboard")) != nullptr; // build_j22.py draws one since round 12
		return M;
	}
	// Visual V7: the other seven from Tools/blender/build_fleet.py (scripts/make-boat-models.sh), loaded by class. The
	// prologue's maxi is the PC's hero model (Tools/boats/maxi/build_maxi.py, imported by import_boats.py `maxi`) on every
	// boat: her deck gear is in the hull, the traveller lies on the cockpit floor, the diesel is inboard and her canted twin
	// rudders are one blade, mirrored on the starboard stock.
	static const TCHAR* BoatTags[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"), TEXT("Corsair880"), TEXT("Lagoon42"), TEXT("Maxi") };
	if (int32(Type) <= 0 || int32(Type) >= int32(UE_ARRAY_COUNT(BoatTags)) || FParse::Param(SailingArgs::Dev(), TEXT("SailingProceduralBoats"))) return M;
	const TCHAR* Tag = BoatTags[int32(Type)];
	auto Load = [Tag](const TCHAR* Part) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/%s/SM_%s_%s.SM_%s_%s"), Tag, Tag, Part, Tag, Part)); };
	M.Hull = Load(TEXT("Hull"));
	M.Mast = Load(TEXT("Mast"));
	M.Boom = Load(TEXT("Boom"));
	M.Rudder = Load(TEXT("Rudder"));
	if (!M.Hull || !M.Mast || !M.Boom || !M.Rudder) return FBoatModelMeshes();
	if (Type == EBoatType::Maxi)
	{
		M.bOwnOutboard = true;
		M.bTravelerBridge = false;
		M.bMirrorTwinRudder = true;
	}
	return M;
}

UStaticMeshComponent* ASailboatPawn::AddModelPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& LocationCm)
{
	UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
	Part->SetupAttachment(Parent ? Parent : BoatRoot.Get());
	Part->SetStaticMesh(Mesh);
	Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Part->SetRelativeLocation(LocationCm);
	// Measuring: -SailingNoBoatDF keeps the boats' parts out of the distance-field lighting (moving meshes re-mark it).
	static SailingArgs::FCachedFlag NoBoatDFArg(TEXT("SailingNoBoatDF"));
	if (NoBoatDFArg.Get()) Part->bAffectDistanceFieldLighting = false;
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
		// Boat fidelity 1 stills: -SailingBoatAge=<years>[,<care 0..1>] ages this boat's hull slots as E1 ages a berthed one.
		FString AgeArg;
		const bool bAge = !bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingBoatAge="), AgeArg, false);
		FString AgeStr, CareStr;
		if (bAge && !AgeArg.Split(TEXT(","), &AgeStr, &CareStr)) { AgeStr = AgeArg; CareStr = TEXT("0.5"); }
		// -SailingDeckWet=<0..1> starts the deck that wet (it dries over about five minutes: UpdateBoatWetness).
		float StartWet = 0.f;
		if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingDeckWet="), StartWet)) DeckWetness = FMath::Clamp(StartWet, 0.f, 1.f);
		// Rain deck stills: -SailingPuddle=<0..1> starts the deck's puddles that full.
		float StartPuddle = 0.f;
		if (!bTrafficBoat && FParse::Value(SailingArgs::Dev(), TEXT("SailingPuddle="), StartPuddle)) PuddleLevel = FMath::Clamp(StartPuddle, 0.f, 1.f);
		const TArray<FName> Slots = ModelHull->GetMaterialSlotNames();
		for (int32 I = 0; I < Slots.Num(); ++I)
		{
			UMaterialInstanceDynamic* Mid = ModelHull->CreateDynamicMaterialInstance(I);
			if (!Mid) continue;
			Mid->SetVectorParameterValue(TEXT("Wear"), FLinearColor(L.Wear.X, L.Wear.Y, L.Wear.Z, L.Wear.W));
			if (bAge)
			{
				Mid->SetScalarParameterValue(TEXT("Age"), FCString::Atof(*AgeStr));
				Mid->SetScalarParameterValue(TEXT("Care"), FCString::Atof(*CareStr));
			}
			auto LiveryFor = [&L](const FString& Name) -> const FLinearColor*
			{
				return Name == TEXT("Topsides") ? &L.Hull : Name == TEXT("Deck") ? &L.Deck : Name == TEXT("NonSkid") ? &L.NonSkid
					: Name == TEXT("Antifouling") ? &L.Bottom : Name == TEXT("Bootstripe") ? &L.Boot : Name == TEXT("CoveStripe") ? &L.Cove
					: Name == TEXT("Teak") ? (L.bTeak ? &L.Teak : &L.Deck) : nullptr;   // Graphics G6: the toe rails
			};
			// pc/boat-slots: a pack (BoatPacks.h) takes each of its entries' livery colours.
			const TConstArrayView<const TCHAR*> Packed = SailingBoatPacks::Entries(Slots[I]);
			for (int32 K = 0; K < Packed.Num(); ++K)
			{
				if (const FLinearColor* Col = LiveryFor(Packed[K])) Mid->SetVectorParameterValue(SailingBoatPacks::ColourParam(K), *Col);
			}
			if (const FLinearColor* Col = Packed.Num() ? nullptr : LiveryFor(Slots[I].ToString())) Mid->SetVectorParameterValue(TEXT("Color"), *Col);
		}
	}
	// Boat detail pass: the cabin interior, same pivot as the hull; only on the player's boat (it shows through the
	// companionway and portlights, never from an AI boat's distance).
	if (Model.Interior && !bTrafficBoat && !bGhost)
	{
		AddModelPart(Model.Interior, BoatRoot, FVector::ZeroVector);
		// Without the glass the portlights are open holes that show the lit cabin. It casts no shadow: the panes are
		// smoked, not opaque, and the interior's own shading already darkens the cabin.
		if (Model.Glass)
		{
			UStaticMeshComponent* GlassPart = AddModelPart(Model.Glass, BoatRoot, FVector::ZeroVector);
			GlassPart->SetCastShadow(false);
		}
	}
	ModelMast = AddModelPart(Model.Mast, BoatRoot, ModelHull->GetSocketTransform(TEXT("MastStep"), RTS_Component).GetLocation());
	MastBendHeightCm = FMath::Max(Model.Mast->GetBounds().GetBox().Max.Z, 100.f);
	MastMaterial = ModelMast->CreateDynamicMaterialInstance(ModelMast->GetMaterialIndex(TEXT("Aluminium")) >= 0 ? ModelMast->GetMaterialIndex(TEXT("Aluminium")) : 0);
	// The boom hangs on the gooseneck pivot (placed from the physics rig); the rudder turns on its stock.
	ModelBoom = AddModelPart(Model.Boom, BoomPivot, FVector::ZeroVector);
	// pc/j22-detail: painted spars where the livery has them (the player's J/22: white, as on Bean's club boats).
	PaintSpars(ModelMast, Livery);
	PaintSpars(ModelBoom, Livery);
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
		if (K > 0 && Model.bMirrorTwinRudder) Blade->SetRelativeScale3D(FVector(1.f, -1.f, 1.f)); // canted outboard each side
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
	// Rig lines pacing (the PC's Ultra bench had the rig lines at 0.9 ms of boat_visuals' 2.0, most of it AI boats'): an AI
	// boat's rig is rebuilt every frame within 30 m of the camera, every 2nd to 150 m, 4th to 600 m, 8th beyond, and every
	// 15th while it is off screen, staggered by boat. Between rebuilds the lines stay drawn where they were, in the boat's
	// frame (the mesh keeps its vertex count). The player's boat is rebuilt every frame.
	if (bTrafficBoat && bRigLinesBuilt)
	{
		int32 Every = 15;
		if (ModelHull && ModelHull->WasRecentlyRendered(0.25f))
		{
			const APlayerController* PC = GetWorld()->GetFirstPlayerController();
			const double Dist = PC && PC->PlayerCameraManager ? FVector::Dist(PC->PlayerCameraManager->GetCameraLocation(), GetActorLocation()) / CmPerMeter : 0.0;
			Every = Dist < 30.0 ? 1 : Dist < 150.0 ? 2 : Dist < 600.0 ? 4 : 8;
		}
		RigPendingSeconds += DeltaSeconds;
		if ((GFrameCounter + GetUniqueID()) % uint64(Every) != 0 && GFrameCounter - RigBuiltFrame < uint64(Every)) return;
		DeltaSeconds = RigPendingSeconds;
	}
	RigPendingSeconds = 0.f;
	RigBuiltFrame = GFrameCounter;
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
		// By the angle the physics gives the boom (TravelerRangeDeg about the gooseneck), not by the track's length: the
		// J/22's track spans the cockpit seat to seat, 3 m aft of the gooseneck, and full travel along it would have led
		// the sheet well outboard of the boom.
		const double Arm = FMath::Abs(TravC.X - BoomPivot->GetRelativeLocation().X);
		const double Out = Arm * FMath::Tan(FMath::DegreesToRadians(FMath::Clamp(Controls.Traveler, -1.0, 1.0) * Boat.GetConfig().TravelerRangeDeg));
		const FVector Along = TravS - TravC;
		const double Half = Along.Size();
		Car = TravC + Along.GetSafeNormal() * FMath::Clamp(Out, -Half, Half) * BoomSide;
		TravelerCar->SetRelativeLocation(Car + FVector(0.f, 0.f, 1.5f));
	}

	// Which side is to leeward: the side the boom (the sails) are on; the windward rig takes the load.
	const bool bLeeStbd = S.BoomAngle >= 0.0;
	const float Loaded = FMath::Clamp((Aws - 3.f) / 5.f, 0.f, 1.f); // below about 3 kn nothing is loaded

	TArray<FRigLine> Wires, Ropes;
	auto Label = [](TArray<FRigLine>& Lines, const TCHAR* Name) { for (FRigLine& L : Lines) if (!*L.Name) L.Name = Name; };
	// Standing rigging: forestay, uppers via the spreaders, lowers, backstay (each where the class has it).
	const float WireR = 0.25f * FMath::Clamp(float(Boat.GetConfig().MastheadZ / 8.0), 0.8f, 2.4f);
	if (Has(ModelMast, TEXT("Hounds")))
	{
		const FVector Hounds = RigPoint(ModelMast, TEXT("Hounds"));
		if (Has(ModelHull, TEXT("ForestayTack"))) Wires.Add({ RigPoint(ModelHull, TEXT("ForestayTack")), Hounds, WireR, 0.f });
		Label(Wires, TEXT("forestay"));
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
				Label(Wires, TEXT("upper shroud"));
				Wires.Add({ RigPoint(ModelHull, *FString::Printf(TEXT("ChainplateLower_%s"), Tag)), RigPoint(ModelMast, TEXT("LowerTang")), WireR, Slack });
				Label(Wires, TEXT("lower shroud"));
			}
			else
			{
				Wires.Add({ Upper, Hounds, WireR, Slack });
				Label(Wires, TEXT("shroud"));
			}
		}
		if (Has(ModelHull, TEXT("BackstayPlate")))
		{
			Wires.Add({ RigPoint(ModelHull, TEXT("BackstayPlate")), RigPoint(ModelMast, TEXT("MastheadAft")), WireR * 0.8f, 0.0008f * (1.f - float(Controls.Backstay)) * (1.f - Loaded) });
			Label(Wires, TEXT("backstay"));
		}
		// The clipping audit (the Hobie's crew out on the trapeze hung from nothing): the trapeze wire from the hounds to the
		// harness of each crew member out beyond the rail, taut. In on the boat it hangs on its shock cord, which the
		// mast model draws (build_fleet.py), so this one shrinks to a stub at the hounds (always drawn: the rig mesh keeps
		// its vertex count).
		if (Boat.GetConfig().bTrapeze && ModelHull && ModelHull->GetStaticMesh())
		{
			const double RailCm = 0.85 * ModelHull->GetStaticMesh()->GetBounds().BoxExtent.Y;
			const FTransform& Root = BoatRoot->GetComponentTransform();
			for (int32 I = 0; I + 1 < Crew.Num(); ++I)   // the last is the helm, who sits in on the tiller
			{
				FVector Harness = Hounds - FVector(0.f, 0.f, 1.f);
				// (Only on the wire: sitting out on the hull, beyond the rail too, the wire ran a metre aft and down to their seat,
				// across the eased main: docs/hobie-downwind/.)
				const bool bOnWire = CrewFigures.IsValidIndex(I) && CrewFigures[I].Stance == ECrewStance::Trapeze;
				if (bOnWire && Crew[I] && Crew[I]->IsVisible())
				{
					const FVector Pelvis = Root.InverseTransformPosition(Crew[I]->GetBoneLocation(TEXT("pelvis"), EBoneSpaces::WorldSpace));
					// The hook at the front of the harness: a hand's width up and forward of the hips, toward the mast.
					if (FMath::Abs(Pelvis.Y) > RailCm) Harness = Pelvis + FVector(8.f, 0.f, 10.f);
				}
				// Drawn thicker than the 3 mm wire (with its ring and handle it reads as a cord): at the real size it vanished from the
				// chase camera.
				Wires.Add({ Hounds, Harness, FMath::Max(WireR * 2.4f, 0.6f), 0.f });
				Label(Wires, TEXT("trapeze wire"));
			}
		}
	}

	// Jib sheets: the working sheet (leeward) from the clew through its lead to the winch, nearly straight under load;
	// the lazy sheet over the cabin top to the windward lead, drooping.
	// A self-tacking jib (the Lagoon's) has one sheet, from the clew down to its car on the track and aft to the leeward
	// winch: the second set of lines lies on it (the rig mesh keeps its vertex count).
	if (Boat.GetConfig().HasJib() && Has(ModelHull, TEXT("JibLead_S")))
	{
		const bool bSelfTacker = Boat.GetConfig().Type == EBoatType::Lagoon42;
		for (const TCHAR* Tag : { TEXT("S"), TEXT("P") })
		{
			const bool bWorking = bSelfTacker || (Tag[0] == TEXT('S')) == (S.JibSide > 0);
			const TCHAR* Side = bSelfTacker ? (S.JibSide > 0 ? TEXT("S") : TEXT("P")) : Tag;
			const uint8 Look = Side[0] == TEXT('S') ? RopeLook::JibStbd : RopeLook::JibPort;
			const FVector Lead = RigPoint(ModelHull, *FString::Printf(TEXT("JibLead_%s"), Side));
			const FVector Winch = RigPoint(ModelHull, *FString::Printf(TEXT("JibWinch_%s"), Side));
			if (bWorking)
			{
				Ropes.Add({ JibClewCm, Lead, 0.45f, FMath::Lerp(0.02f, 0.0005f, Loaded) + 0.004f * float(Controls.JibSheet) * (1.f - Loaded), Look });
			}
			else
			{
				FVector Via = RigPoint(ModelHull, TEXT("LazySheetVia"));
				// (Over the cabin top forward of the mast only while the clew is forward of it too: an overlapping genoa's clew,
				// aft of the mast through a tack, took the sheet forward round the via and back through the mast,
				// SailingSim.Visual.SheetClearance. Then it crosses over the cabin top aft of the mast, at the via's height on the
				// centreline level with the clew, still in two pieces.)
				if (JibClewCm.X < Via.X) Via = FVector(JibClewCm.X, 0.f, Via.Z);
				Ropes.Add({ JibClewCm, Via, 0.45f, 0.03f, Look });
				Ropes.Add({ Via, Lead, 0.45f, 0.05f, Look });
			}
			Ropes.Add({ Lead, Winch, 0.45f, bWorking ? 0.f : 0.02f, Look });
			Label(Ropes, bWorking ? TEXT("jib sheet") : TEXT("lazy jib sheet"));
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
		// (Always drawn, so the rig mesh keeps its vertex count: with no hand in reach, down onto where the model lays it,
		// JibTailRest (the hero's cabin top, forward and inboard of its winch), else onto the seat behind the winch.)
		const FVector Tailer = RigPoint(ModelHull, S.JibSide > 0 ? TEXT("JibTailer_S") : TEXT("JibTailer_P"));
		// (Only into a hand that holds it: led to the nearer hand resting on a knee it ran through the thigh.)
		const TOptional<FVector> Hand = JibGripCm;
		const TCHAR* Rest = S.JibSide > 0 ? TEXT("JibTailRest_S") : TEXT("JibTailRest_P");
		const FVector Tail = Hand && FVector::Dist(*Hand, Tailer) < 160.f ? *Hand
			: Has(ModelHull, Rest) ? RigPoint(ModelHull, Rest) : Tailer + FVector(-30.f, (S.JibSide > 0 ? -1.f : 1.f) * 12.f, -16.f);
		Ropes.Add({ Tailer, Tail, 0.45f, 0.03f, S.JibSide > 0 ? RopeLook::JibStbd : RopeLook::JibPort });
		Label(Ropes, TEXT("jib sheet tail"));
	}
	FVector End;
	// (A wheel boat's TillerEnd is a point on the wheel's rim: no extension there.)
	if (TillerEndCm(End) && Boat.GetConfig().WheelHardOverSeconds <= 0.0)
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
		Label(Wires, TEXT("tiller extension"));
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
	else if (Boat.GetConfig().Type == EBoatType::Sunfish && CrewCockpitWell(Boat.GetConfig(), Well))
	{
		// Rig clearance: the Sunfish's sheet runs from the bridle up to the boom's end block, forward along the boom to a block
		// over the cockpit and down to the hand (its tail ran from the bridle along the deck under the sailor's hips).
		const FVector SheetLocal = ModelBoom->GetSocketTransform(TEXT("Boom_Mainsheet"), RTS_Component).GetLocation();
		const double Over = Well.X1 * CmPerMeter;
		const double Along = FMath::Clamp((Boat.GetConfig().MainLuffX * CmPerMeter - Over) / FMath::Max(FMath::Abs(SheetLocal.X), 1.0), 0.1, 1.0);
		const FVector MidBlock = BoatRoot->GetComponentTransform().InverseTransformPosition(ModelBoom->GetComponentTransform().TransformPosition(SheetLocal * Along));
		Ropes.Add({ BoomBlock, MidBlock, 0.4f, 0.f });
		Ropes.Add({ MidBlock, MainGripCm ? *MainGripCm : MidBlock + FVector(-10.f, 0.f, -45.f), 0.4f, MainGripCm ? 0.01f : 0.05f });
	}
	else
	{
		// (Always drawn, so the rig mesh keeps its vertex count: with no hand on it, a short tail onto the cockpit sole.)
		Ropes.Add({ Car + FVector(0.f, 0.f, 3.f), MainGripCm ? *MainGripCm : Car + FVector(-28.f, 6.f, -6.f), 0.4f, MainGripCm ? 0.01f : 0.04f });
	}
	Label(Ropes, TEXT("mainsheet tail"));
	// Bean's J/22 feedback 1: where the lower block stands on the car (the hero's fiddle, MainsheetBlock), the tackle
	// ends at its sheave, carried with the car.
	FVector LowBlock = Car + FVector(0.f, 0.f, 3.f);
	if (Has(ModelHull, TEXT("MainsheetBlock")) && Has(ModelHull, TEXT("Traveler_C")))
	{
		LowBlock = Car + RigPoint(ModelHull, TEXT("MainsheetBlock")) - RigPoint(ModelHull, TEXT("Traveler_C"));
	}
	for (int32 K = 0; K < 4; ++K)
	{
		const FVector Off(0.f, (K - 1.5f) * 1.2f, 0.f);
		Ropes.Add({ BoomBlock + Off, LowBlock + Off, 0.35f, MainSlack });
	}
	Label(Ropes, TEXT("mainsheet"));
	// Vang: a 3:1 tackle from the boom to the mast base, slack when eased off.
	if (Has(ModelBoom, TEXT("Boom_Vang")))
	{
		const FVector VangBoom = RigPoint(ModelBoom, TEXT("Boom_Vang")), VangMast = RigPoint(ModelMast, TEXT("MastBase"));
		for (int32 K = 0; K < 3; ++K)
		{
			const FVector Off(0.f, (K - 1.f) * 1.0f, 0.f);
			Ropes.Add({ VangBoom + Off, VangMast + Off, 0.3f, 0.02f * (1.f - float(Controls.Vang)), RopeLook::Vang });
		}
		Label(Ropes, TEXT("vang"));
	}

	// Rig clearance: the ropes lie over the boat, not through it. Where a sheet's curve passes inside the solid boat
	// (CrewInsideBoat: deck, cabin trunk, coachroof), its rings are lifted onto the surface: the lazy sheet draped over the
	// cabin top, a sheet led from its lead up over the roof's edge to the winch, a running mainsheet over the coaming. (The
	// vang hangs in the air between its blocks.)
	{
		const FBoatConfig& Cfg = Boat.GetConfig();
		const double HullDepth = Boat.HullDepth();
		const FVector DownD = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
		// Sails and sheets: the crew's legs and trunk (boat frame, cm, with RigClearance's flesh radii), so a sheet or tail
		// lies over a sailor's thigh instead of through it (the Catalina 22's lazy sheet, the J/22's mainsheet tail).
		struct FFlesh { FVector A, B; float R; FVector Hand = FVector(1e9); };
		TArray<FFlesh, TInlineAllocator<24>> Flesh;
		{
			const FTransform& Root = BoatRoot->GetComponentTransform();
			static const FName Pelvis(TEXT("pelvis")), Spine3(TEXT("spine_03")), Spine5(TEXT("spine_05"));
			static const FName Thigh[2] = { FName(TEXT("thigh_l")), FName(TEXT("thigh_r")) }, Calf[2] = { FName(TEXT("calf_l")), FName(TEXT("calf_r")) },
				Foot[2] = { FName(TEXT("foot_l")), FName(TEXT("foot_r")) };
			static const FName UpperArm[2] = { FName(TEXT("upperarm_l")), FName(TEXT("upperarm_r")) }, LowerArm[2] = { FName(TEXT("lowerarm_l")), FName(TEXT("lowerarm_r")) },
				HandBone[2] = { FName(TEXT("hand_l")), FName(TEXT("hand_r")) };
			for (const TObjectPtr<USkeletalMeshComponent>& M : Crew)
			{
				if (!M || !M->IsVisible() || M->GetBoneIndex(Pelvis) == INDEX_NONE) continue;
				auto At = [&](const FName& Bone) { return Root.InverseTransformPosition(M->GetBoneLocation(Bone, EBoneSpaces::WorldSpace)); };
				const FName& Chest = M->GetBoneIndex(Spine5) != INDEX_NONE ? Spine5 : Spine3;
				if (M->GetBoneIndex(Chest) != INDEX_NONE) Flesh.Add({ At(Pelvis), At(Chest), 10.f });
				for (int32 Sd = 0; Sd < 2; ++Sd)
				{
					if (M->GetBoneIndex(Thigh[Sd]) == INDEX_NONE || M->GetBoneIndex(Calf[Sd]) == INDEX_NONE || M->GetBoneIndex(Foot[Sd]) == INDEX_NONE) continue;
					Flesh.Add({ At(Thigh[Sd]), At(Calf[Sd]), 7.f });
					Flesh.Add({ At(Calf[Sd]), At(Foot[Sd]), 4.5f });
				}
				// The arms too (a lazy sheet lifted over a knee met the forearm resting on it), except for a line held in
				// that hand.
				for (int32 Sd = 0; Sd < 2; ++Sd)
				{
					if (M->GetBoneIndex(UpperArm[Sd]) == INDEX_NONE || M->GetBoneIndex(LowerArm[Sd]) == INDEX_NONE || M->GetBoneIndex(HandBone[Sd]) == INDEX_NONE) continue;
					const FVector Hand = At(HandBone[Sd]);
					Flesh.Add({ At(UpperArm[Sd]), At(LowerArm[Sd]), 4.5f, Hand });
					Flesh.Add({ At(LowerArm[Sd]), Hand, 3.5f, Hand });
				}
			}
		}
		// The lifelines (build_fleet.py lifelines(), as RigClearance has them): two wires at half and full height over the
		// deck at the stanchions, a hull's half beam less 5 cm out.
		const bool bLifelines = CrewHasLifelines(Cfg);
		const double LifelineHgt = Cfg.Hulls[0].SheerZ < 0.9 ? 60.0 : 68.0;
		for (FRigLine& L : Ropes)
		{
			const FString What = L.Name;
			if (What == TEXT("vang")) continue;
			const FVector Sag = SagOf(L, DownD);
			auto HeldBy = [&L](const FFlesh& F) { return FVector::DistSquared(F.Hand, L.A) < 625.0 || FVector::DistSquared(F.Hand, L.B) < 625.0; };
			// The flesh this line could touch (within its sag, the most a drape lifts and a hand's width of its chord), and
			// whether it reaches the lifelines at all: the checks below run for every ring and span.
			TArray<const FFlesh*, TInlineAllocator<24>> NearFlesh;
			const float Reach = Sag.Size() + 60.f + L.RadiusCm;
			for (const FFlesh& F : Flesh)
			{
				if (F.Hand.X < 1e8 && HeldBy(F)) continue;
				const FVector Fm = 0.5f * (F.A + F.B);
				if (FVector::Dist(FMath::ClosestPointOnSegment(Fm, L.A, L.B), Fm) < Reach + F.R + 0.5f * FVector::Dist(F.A, F.B)) NearFlesh.Add(&F);
			}
			const double Beam0 = Cfg.Hulls[0].MaxHalfBeam * CmPerMeter, CY = Cfg.Hulls[0].CenterY * CmPerMeter;
			const bool bReachesLifelines = bLifelines && FMath::Max(FMath::Abs(L.A.Y - CY), FMath::Abs(L.B.Y - CY)) + FMath::Abs(Sag.Y) > Beam0 * 0.5;
			// Is a point in the boat, a sailor's flesh or a lifeline wire?
			auto Blocked = [&](const FVector& C) -> bool
			{
				if (CrewInsideBoat(Cfg, HullDepth, C / CmPerMeter, bModelTravelerBridge)) return true;
				for (const FFlesh* F : NearFlesh)
				{
					if (FVector::DistSquared(FMath::ClosestPointOnSegment(C, F->A, F->B), C) < FMath::Square(F->R + L.RadiusCm)) return true;
				}
				if (bReachesLifelines)
				{
					const double Fence = (Cfg.Hulls[0].DeckHalfBeam(C.X / CmPerMeter) - 0.05) * CmPerMeter;
					if (FMath::Abs(FMath::Abs(C.Y - Cfg.Hulls[0].CenterY * CmPerMeter) - Fence) < 1.0 + L.RadiusCm)
					{
						const double Deck = CrewFloorZ(Cfg, C.X / CmPerMeter, FMath::Sign(C.Y) * (Fence - 5.0) / CmPerMeter, bModelTravelerBridge) * CmPerMeter;
						for (const double Wire : { 0.5 * LifelineHgt, LifelineHgt })
						{
							if (Deck > -1e6 && FMath::Abs(C.Z - (Deck + Wire)) < 1.0 + L.RadiusCm) return true;
						}
					}
				}
				return false;
			};
			// How far up a point must go to be out of the boat (a coachroof is up to a metre and a half over the deck), off a
			// sailor's leg or over a lifeline.
			auto Under = [&](const FVector& C) -> float
			{
				if (!Blocked(C)) return 0.f;
				float Up = 2.f;
				while (Up < 150.f && Blocked(C + FVector(0.f, 0.f, Up))) Up += 2.f;
				return Up < 150.f ? Up + L.RadiusCm : 0.f;
			};
			// Each ring takes the most any point within half a span of it needs, so the spans between the rings clear the edge
			// they are lifted over too (a lazy sheet over the cabin top's corner, a sheet up over a coachroof's front).
			for (int32 I = 1; I < kLineSegments; ++I)
			{
				for (const float Off : { -0.5f, -0.25f, 0.f, 0.25f, 0.5f })
				{
					const float U = FMath::Clamp((I + Off) / kLineSegments, 0.f, 1.f);
					L.Lift[I] = FMath::Max(L.Lift[I], Under(L.A + (L.B - L.A) * U + Sag * (4.f * U * (1.f - U))));
				}
			}
			// Sails and sheets: then the drawn spans themselves. A span between a ring lifted onto a cabin top and the next
			// one down on the side deck cut the roof's corner (the lazy sheets of five boats 2-3 cm inside their trunks, the
			// J/22's working sheet 9.5 cm, in SailingSim.Visual.RigClearance): each span is checked at its quarters, and a
			// point still inside lifts the span's free rings (an end at its fitting stays) until it clears.
			for (int32 Pass = 0; Pass < 6; ++Pass)
			{
				bool bLifted = false;
				for (int32 I = 0; I < kLineSegments; ++I)
				{
					const FVector P0 = LinePoint(L, Sag, I), P1 = LinePoint(L, Sag, I + 1);
					// Only a span that can cut something: one next to a lifted ring (a corner), or near a sailor, or across
					// a lifeline's plane (below). The rest are where the first pass left them.
					bool bNear = L.Lift[I] > 0.f || L.Lift[I + 1] > 0.f;
					const FVector Mid = 0.5f * (P0 + P1);
					const float Half = 0.5f * FVector::Dist(P0, P1);
					for (int32 F = 0; F < NearFlesh.Num() && !bNear; ++F)
					{
						bNear = FVector::Dist(FMath::ClosestPointOnSegment(Mid, NearFlesh[F]->A, NearFlesh[F]->B), Mid) < Half + NearFlesh[F]->R + L.RadiusCm;
					}
					// Its eighths, and where it crosses a lifeline's plane (the wires are 3 cm thick: a span can step over
					// one between two checks).
					TArray<float, TInlineAllocator<10>> Checks;
					double Cross = -1.0;
					if (bReachesLifelines)
					{
						// Each end against the fence where it is (the beam narrows aft).
						const double Y0 = FMath::Abs(P0.Y - CY) - (Cfg.Hulls[0].DeckHalfBeam(P0.X / CmPerMeter) - 0.05) * CmPerMeter;
						const double Y1 = FMath::Abs(P1.Y - CY) - (Cfg.Hulls[0].DeckHalfBeam(P1.X / CmPerMeter) - 0.05) * CmPerMeter;
						if (Y0 * Y1 < 0.0) { Cross = FMath::Clamp(Y0 / (Y0 - Y1), 0.02, 0.98); bNear = true; }
					}
					if (bNear) Checks = { 0.125f, 0.25f, 0.375f, 0.5f, 0.625f, 0.75f, 0.875f };
					if (Cross > 0.0) Checks.Add(float(Cross));
					for (const float Q : Checks)
					{
						const float Need = Under(FMath::Lerp(P0, P1, Q));
						if (Need <= 0.f) continue;
						// Both free ends of the span go up by what the point needs; next to an end held at its fitting, the
						// free one goes up enough to raise the point that much.
						const bool bFree0 = I > 0, bFree1 = I + 1 < kLineSegments;
						if (bFree0 && bFree1) { L.Lift[I] += Need; L.Lift[I + 1] += Need; }
						else if (bFree1) L.Lift[I + 1] += Need / Q;
						else if (bFree0) L.Lift[I] += Need / (1.f - Q);
						bLifted = true;
						break;
					}
				}
				if (!bLifted) break;
			}
		}
	}

	// Rig clearance: the wires the sails can't pass through (FSailCloth::KeepClear): the shrouds, the spreaders (the mast
	// model draws them: from the mast at the tip's height out to the tip) and a trapeze wire.
	SailObstacles.Reset();
	for (const FRigLine& L : Wires)
	{
		const FString What = L.Name;
		if (!What.Contains(TEXT("shroud")) && What != TEXT("trapeze wire")) continue;
		// Along its sag (a leeward shroud goes slack in a breeze and bows out): four straight pieces.
		const FVector Sag = SagOf(L, BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f)));
		auto At = [&](float T) { return L.A + (L.B - L.A) * T + Sag * (4.f * T * (1.f - T)); };
		for (int32 K = 0; K < 4; ++K) SailObstacles.Add({ At(K / 4.f), At((K + 1) / 4.f), L.RadiusCm, K == 0 ? 12.f : 0.f, K == 3 ? 12.f : 0.f });
	}
	const int32 NumWireObstacles = SailObstacles.Num();
	// pc/hobie-jib-shroud: FSailCloth keeps a jib outside the wires it meets, an overlapping genoa's way. The Hobie 16's jib
	// sheets to cars on her trampoline, well inside her shrouds (class photos): pushed outward it lay through the leeward
	// shroud. Her jib keeps clear of nothing; its own shape stays inside them.
	bJibInsideShrouds = Boat.GetConfig().Type == EBoatType::Hobie16;
	JibSailObstacles.Reset();
	if (Has(ModelMast, TEXT("SpreaderTip_S")) && Has(ModelMast, TEXT("MastBase")) && Has(ModelMast, TEXT("Hounds")))
	{
		const FVector Base = RigPoint(ModelMast, TEXT("MastBase")), Head = RigPoint(ModelMast, TEXT("Hounds"));
		for (const TCHAR* Tip : { TEXT("SpreaderTip_S"), TEXT("SpreaderTip_P") })
		{
			const FVector P = RigPoint(ModelMast, Tip);
			const FVector Root = FMath::Lerp(Base, Head, FMath::Clamp((P.Z - Base.Z) / FMath::Max(Head.Z - Base.Z, 1.0), 0.0, 1.0));
			SailObstacles.Add({ Root, P, 1.5f });
		}
	}
	if (bRecordRigLines)
	{
		// For the rig clearance test: each line as built (before the on-screen minimum width), named by what it is.
		const FVector DownRec = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
		RigLineSamples.Reset();
		for (const TArray<FRigLine>* Lines : { &Wires, &Ropes })
		{
			for (const FRigLine& L : *Lines)
			{
				FRigLineSample& Rec = RigLineSamples.Add_GetRef({ L.A, L.B, SagOf(L, DownRec), L.RadiusCm, L.Name });
				for (int32 I = 0; I <= kLineSegments; ++I) Rec.Points.Add(LinePoint(L, Rec.Sag, I));
			}
		}
		for (int32 K = NumWireObstacles; K < SailObstacles.Num(); ++K)
		{
			FRigLineSample& Rec = RigLineSamples.Add_GetRef({ SailObstacles[K].A, SailObstacles[K].B, FVector::ZeroVector, SailObstacles[K].RadiusCm, TEXT("spreader") });
			Rec.Points = { Rec.A, Rec.B };
		}
	}

	// pc/rig-lines (docs/rig-lines): each ring of a line is drawn at least kMinLinePx (1.2 px) across at its own distance
	// from the camera (RingRadius), so every row of a far shroud lands on a pixel centre and it stays an unbroken line under
	// TSR/TAA. Boat fidelity 4 widened a whole line to 0.8 px at its middle's distance: the far end fell under it and broke
	// up, the near end drew fat. (#312 did this in the materials by world position offset; docs/gelcoat-rt moved it back
	// here: WPO cost the Mac's base pass half a millisecond at helm eye.) The braid keeps its true scale. -SailingNoMinLineWidth.
	static SailingArgs::FCachedFlag NoMinWidthArg(TEXT("SailingNoMinLineWidth"));
	FLineWidening Widen;
	const APlayerController* ViewPC = GetWorld()->GetFirstPlayerController();
	if (!NoMinWidthArg.Get() && ViewPC && ViewPC->PlayerCameraManager && GEngine && GEngine->GameViewport)
	{
		FVector2D ViewSize;
		GEngine->GameViewport->GetViewportSize(ViewSize);
		Widen.PxAngle = 2.f * FMath::Tan(FMath::DegreesToRadians(ViewPC->PlayerCameraManager->GetFOVAngle() * 0.5f)) / FMath::Max(ViewSize.X, 1.0);
		Widen.Eye = BoatRoot->GetComponentTransform().InverseTransformPosition(ViewPC->PlayerCameraManager->GetCameraLocation());
		Widen.bOn = true;
	}

	// Gravity in the boat frame (the boat heels and pitches).
	const FVector Down = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
	for (int32 Section = 0; Section < 2; ++Section)
	{
		const TArray<FRigLine>& Lines = Section == 0 ? Wires : Ropes;
		// A section none of whose lines moved more than half a millimetre (ends, sag or radius) since its last upload, and none of
		// whose rings stepped its on-screen widening, is left as it is: the standing rig at rest, a sheet made fast.
		TArray<FVector> Keys;
		Keys.Reserve(Lines.Num() * 5);
		for (const FRigLine& L : Lines)
		{
			const FVector Sag = SagOf(L, Down);
			int32 Steps = 0;
			for (int32 I = 0; I <= kLineSegments; ++I) RingRadius(L.RadiusCm, LinePoint(L, Sag, I), Widen, &Steps);
			Keys.Append({ L.A, L.B, Sag, FVector(L.RadiusCm, L.Lift[kLineSegments / 2], L.Lift[kLineSegments / 4] + L.Lift[3 * kLineSegments / 4]),
				FVector(float(Steps), 0.f, 0.f) });
		}
		TArray<FVector>& Last = RigLineKeys[Section];
		bool bMoved = !bRigLinesBuilt || Last.Num() != Keys.Num();
		for (int32 K = 0; !bMoved && K < Keys.Num(); ++K) bMoved = FVector::DistSquared(Keys[K], Last[K]) > 0.05f * 0.05f;
		if (!bMoved) continue;
		Last = MoveTemp(Keys);
		FTubeStreams Out;
		// Reserved up front, and no colours after the build: the per-frame update converted every vertex's linear colour
		// to sRGB and doubled the rig lines' game-thread time (0.65 -> 1.4 ms on the PC).
		const int32 NumVerts = Lines.Num() * (kLineSegments + 1) * (kLineSides + 1);
		Out.Verts.Reserve(NumVerts); Out.Normals.Reserve(NumVerts); Out.UV0.Reserve(NumVerts); Out.Tangents.Reserve(NumVerts);
		if (!bRigLinesBuilt) Out.Colors.Reserve(NumVerts);
		for (int32 K = 0; K < Lines.Num(); ++K)
		{
			AppendTube(Lines[K], Last[5 * K + 2], Section == 0 ? 11.f : 5.f, Widen, Out, !bRigLinesBuilt);
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
	// Boat fidelity 4: the hero J/22's coiled tails (J22CoilData.inl), lying where bake_j22_hero.py baked their shadows into
	// the deck: built once into their own section (they never move in the boat frame). -SailingNoCoils leaves them out.
	static SailingArgs::FCachedFlag NoCoilsArg(TEXT("SailingNoCoils"));
	if (!bRigLinesBuilt && !bTrafficBoat && !bGhost && !NoCoilsArg.Get() && ModelHull && ModelHull->GetStaticMesh()
		&& ModelHull->GetStaticMesh()->GetName() == TEXT("SM_J22H_Hull"))
	{
		FTubeStreams Out;
		TArray<FVector> Pts;
		for (const FJ22Coil& Coil : GJ22Coils)
		{
			Pts.Reset();
			for (int32 I = 0; I < Coil.Count; ++I)
			{
				const float* Q = GJ22CoilPoints[Coil.First + I];
				Pts.Add(FVector(Q[0], Q[1], Q[2]));
			}
			AppendPolyTube(Pts, Coil.RadiusCm, Coil.Look, Out);
		}
		RigLines->CreateMeshSection_LinearColor(2, Out.Verts, Out.Tris, Out.Normals, Out.UV0, Out.Colors, Out.Tangents, false);
		RigLines->SetMaterial(2, RopeMaterial.Get());
	}
	bRigLinesBuilt = true;
}

void ASailboatPawn::UpdateDrips(float DeltaSeconds)
{
	// Rain deck (docs/rain-deck): drips. While the boat is wet (the deck's wetness: rain and spray) and slow, water gathers on
	// the boom's underside and the sheer and drops off: a few drips a second, falling under gravity, the boom's onto the
	// cockpit, the sheer's into the sea. Drawn as M_Spray quads (smooth, Grain 0) on an instanced plane, stretched along
	// their fall. Player's boat, High and Ultra. -SailingNoDrips.
	constexpr int32 kPool = 48;
	static SailingArgs::FCachedFlag NoDripsArg(TEXT("SailingNoDrips"));
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	const float Speed = float(Boat.GetTelemetry().SpeedThroughWater);
	const bool bOn = !NoDripsArg.Get() && USailingSettings::Get()->Quality >= ESailingQuality::High && Boat.GetConfig().Hulls.size() > 0;
	if (!bOn && !Drips) return;
	if (!Drips)
	{
		UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
		UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Spray.M_Spray"), nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (!Plane || !Mat) return;
		Drips = NewObject<UInstancedStaticMeshComponent>(this);
		Drips->SetupAttachment(GetRootComponent());
		Drips->SetMobility(EComponentMobility::Movable);
		Drips->SetUsingAbsoluteLocation(true);
		Drips->SetUsingAbsoluteRotation(true);
		Drips->SetUsingAbsoluteScale(true);
		Drips->SetWorldTransform(FTransform::Identity);
		Drips->SetStaticMesh(Plane);
		Drips->SetMaterial(0, Mat);
		Drips->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Drips->SetCastShadow(false);
		Drips->bAffectDistanceFieldLighting = false;
		Drips->NumCustomDataFloats = 3;   // M_Spray: opacity, grain, seed
		Drips->RegisterComponent();
		TArray<FTransform> Hidden;
		Hidden.Init(FTransform(FQuat::Identity, GetActorLocation(), FVector::ZeroVector), kPool);
		Drips->AddInstances(Hidden, false, true);
	}
	// Spawn: the rate follows the wetness, and eases off under way (past 3.5 m/s the water runs aft instead of dripping).
	const float Wet = FMath::Max(DeckWetness, 0.5f * FMath::Clamp(float(GetWorld()->GetAuthGameMode<ASailingGameMode>() ? GetWorld()->GetAuthGameMode<ASailingGameMode>()->GetWeatherState().Rain : 0.0), 0.f, 1.f));
	const float Rate = bOn ? 10.f * FMath::Clamp((Wet - 0.1f) / 0.5f, 0.f, 1.f) * FMath::Clamp((3.5f - Speed) / 2.f, 0.f, 1.f) : 0.f;
	DripClock += Rate * Dt;
	const FHullShape& Hull = Boat.GetConfig().Hulls[0];
	while (DripClock >= 1.f && DripList.Num() < kPool)
	{
		DripClock -= 1.f;
		FDrip D;
		D.Seed = FMath::FRand();
		D.V = FVector::ZeroVector;
		if (ModelBoom && ModelBoom->GetStaticMesh() && FMath::FRand() < 0.5f)
		{
			// Along the boom's underside, its own frame (the boom swings and lifts with the sheet).
			const FBox B = ModelBoom->GetStaticMesh()->GetBoundingBox();
			const FVector Local(FMath::Lerp(B.Min.X, B.Max.X, FMath::FRandRange(0.1f, 0.95f)), FMath::FRandRange(-0.3f, 0.3f) * B.GetExtent().Y, B.Min.Z);
			D.P = ModelBoom->GetComponentTransform().TransformPosition(Local);
			D.KillZ = float(D.P.Z - 95.f);                                       // the cockpit sole, about
		}
		else
		{
			// Off the sheer, either side, into the sea.
			const double X = FMath::Lerp(Hull.SternX, Hull.BowX, double(FMath::FRandRange(0.1f, 0.85f)));
			const double S = FMath::FRand() < 0.5f ? -1.0 : 1.0;
			const Vec3 W = Boat.BodyToWorld(Vec3(X, Hull.CenterY + S * (Hull.DeckHalfBeam(X) + 0.01), Hull.SheerHeight(X)));
			D.P = SailingFrame::ToWorld(GetWorld(), W.X, W.Y, 0.0);
			D.P.Z = WaterSurfaceZ + W.Z * CmPerMeter;
			D.KillZ = float(WaterSurfaceZ - 20.0);
		}
		DripList.Add(D);
	}
	if (DripClock >= 1.f) DripClock = 0.f;
	// Fall, and draw: each drip a 15 mm smooth quad facing the camera, stretched along its fall by the exposure.
	const APlayerController* PC = GetWorld()->GetFirstPlayerController();
	const FVector Cam = PC && PC->PlayerCameraManager ? PC->PlayerCameraManager->GetCameraLocation() : GetActorLocation();
	TArray<FTransform> Xf;
	Xf.SetNumUninitialized(kPool);
	float Data[3];
	for (int32 I = DripList.Num() - 1; I >= 0; --I)
	{
		FDrip& D = DripList[I];
		D.V.Z -= 981.f * Dt;
		D.P += D.V * Dt;
		if (D.P.Z < D.KillZ) DripList.RemoveAtSwap(I);
	}
	for (int32 I = 0; I < kPool; ++I)
	{
		if (I < DripList.Num())
		{
			const FDrip& D = DripList[I];
			const FVector N = (Cam - D.P).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
			FVector Across = D.V - FVector::DotProduct(D.V, N) * N;
			const float Smear = float(Across.Size()) / CmPerMeter;              // m/s across the view
			if (Smear < 1e-3f) Across = FVector::CrossProduct(N, FVector::UpVector);
			const FVector X = Across.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
			const FQuat Q = FMatrix(X, FVector::CrossProduct(N, X), N, FVector::ZeroVector).ToQuat();
			const float Size = 0.015f;   // (M_Spray's smooth profile: about an 8 mm drop; 6 mm quads were a pixel from the cockpit)
			Xf[I] = FTransform(Q, D.P, FVector(Size + Smear / 40.f, Size, 1.f));
			Data[0] = 1.f;
			Data[1] = 0.f;
			Data[2] = D.Seed;
			Drips->SetCustomData(I, MakeArrayView(Data, 3), false);
		}
		else
		{
			Xf[I] = FTransform(FQuat::Identity, GetActorLocation(), FVector::ZeroVector);
		}
	}
	Drips->BatchUpdateInstancesTransforms(0, Xf, true, true, true);
}

void ASailboatPawn::UpdateBowWave(float DeltaSeconds)
{
	// Spray hull (docs/spray-hull): the bow wave's curl. Past 1.5 m/s a sheet of water piles against each side of the bow and
	// falls away outward and aft along the Kelvin wedge (19.5 degrees): highest a little aft of the stem, about a third of
	// the speed head (V^2 / 2g), scaled with the hull, a lip that thickens at speed. Built every frame in world space on the
	// waves' surface (the boat heels and pitches through it), as a strip per side: 10 stations along the bow by 6 across.
	// Not on Low; AI boats only within 120 m of the camera. M_BowWave: translucent water, its foam lip. -SailingNoBowWave.
	constexpr int32 NS = 10, NU = 6;
	static SailingArgs::FCachedFlag NoBowWaveArg(TEXT("SailingNoBowWave"));
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const float Speed = float(T.SpeedThroughWater);
	bool bShow = GM && !bGhost && !NoBowWaveArg.Get() && USailingSettings::Get()->Quality > ESailingQuality::Low && Speed > 1.5f
		&& !Boat.GetConfig().Hulls.empty();
	if (bShow && bTrafficBoat)
	{
		const APlayerController* PC = GetWorld()->GetFirstPlayerController();
		bShow = PC && PC->PlayerCameraManager && FVector::Dist(PC->PlayerCameraManager->GetCameraLocation(), GetActorLocation()) < 12000.0;
	}
	if (!bShow)
	{
		if (BowWave) BowWave->SetVisibility(false);
		return;
	}
	if (!BowWave)
	{
		BowWave = NewObject<UProceduralMeshComponent>(this);
		BowWave->SetupAttachment(GetRootComponent());
		BowWave->SetUsingAbsoluteLocation(true);
		BowWave->SetUsingAbsoluteRotation(true);
		BowWave->SetUsingAbsoluteScale(true);
		BowWave->SetWorldTransform(FTransform::Identity);
		BowWave->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		BowWave->SetCastShadow(false);
		BowWave->bAffectDistanceFieldLighting = false;
		BowWave->RegisterComponent();
		if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BowWave.M_BowWave"), nullptr, LOAD_NoWarn | LOAD_Quiet)) BowWave->SetMaterial(0, M);
	}
	BowWave->SetVisibility(true);
	const FHullShape& Hull = Boat.GetConfig().Hulls[0];
	const FWaveField& Waves = GM->GetWaves();
	const double Time = Boat.GetState().Time;
	const float Scale = FMath::Clamp(float(Hull.MaxHalfBeam) / 1.2f, 0.5f, 1.5f);
	const float Head = FMath::Min(0.4f * Speed * Speed / (2.f * 9.81f), 0.5f) * Scale;    // m, at the crest (bow-curl-crest: 0.25 read as a wet film at 17 kn)
	const float Fade = FMath::Clamp((Speed - 1.5f) / 1.5f, 0.f, 1.f);
	const float Lip = FMath::Clamp((Speed - 2.f) / 2.5f, 0.f, 1.f);
	// pc/ultra-spray (docs/ultra-spray): M_BowWave's close-up streaks and flecks, on Ultra (vertex colour blue; -SailingNoUltraSpray compares).
	static SailingArgs::FCachedFlag NoUltraSprayArg(TEXT("SailingNoUltraSpray"));
	const float Fine = USailingSettings::Get()->Quality == ESailingQuality::Ultra && !NoUltraSprayArg.Get() ? 1.f : 0.f;
	TArray<FVector> V;
	TArray<FVector2D> UV;
	TArray<FLinearColor> Col;
	TArray<int32> Tris;
	V.Reserve(2 * NS * NU); UV.Reserve(2 * NS * NU); Col.Reserve(2 * NS * NU);
	// From where the bow meets the water (BowX is the stem's top: raked bows overhang it; the spray peels from 0.55-0.8 of it).
	const double X0 = Hull.BowX * 0.8, X1 = Hull.BowX * 0.45;
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const double S = Side == 0 ? 1.0 : -1.0;
		const int32 Base = V.Num();
		for (int32 I = 0; I < NS; ++I)
		{
			const float Tt = float(I) / (NS - 1);
			const double X = FMath::Lerp(X0, X1, double(Tt));
			const double Aft = X0 - X;                                         // m aft of the stem
			const float Rise = FMath::Sin(0.5f * PI * FMath::Min(Tt / 0.15f, 1.f)) * FMath::Exp(-2.6f * FMath::Max(Tt - 0.12f, 0.f));
			const float H = Head * Rise;
			// The root: where this station's side meets the sea as she heels and pitches now (heeled, the lee waterline lies
			// well outboard of the upright half-beam: rooted there the sheet lay on her topsides). The side is taken as a wall
			// at the deck's half-beam; along it the world height is linear in body z, so one step solves for the sea.
			const double YHull = Hull.CenterY + S * FMath::Max(Hull.DeckHalfBeam(X), 0.02);
			const Vec3 Z0 = Boat.BodyToWorld(Vec3(X, YHull, 0.0)), Z1 = Boat.BodyToWorld(Vec3(X, YHull, 1.0));
			const double Sea0 = Waves.Height(Z0.X, Z0.Y, Time);
			const double Zb = FMath::Abs(Z1.Z - Z0.Z) > 1e-3 ? FMath::Clamp((Sea0 - Z0.Z) / (Z1.Z - Z0.Z), -1.5, 1.5) : 0.0;
			const Vec3 Root = Boat.BodyToWorld(Vec3(X, YHull, Zb));
			const Vec3 Off = Boat.BodyToWorld(Vec3(X, YHull + S, Zb));
			FVector2D Out(Off.X - Root.X, Off.Y - Root.Y);
			Out = Out.GetSafeNormal();
			const double Width = 0.12 * Scale + 0.36 * Aft;                    // out to the Kelvin wedge
			for (int32 J = 0; J < NU; ++J)
			{
				const float U = float(J) / (NU - 1);
				// Across: highest at the hull, a shoulder (the lip, curling outward at speed), then down to the sea; 4 cm off
				// her skin.
				const float Profile = FMath::Pow(1.f - U, 1.3f) + Lip * 0.35f * FMath::Sin(PI * FMath::Min(U / 0.45f, 1.f)) * (1.f - U);
				const double Reach = 0.04 + U * Width + 0.04 * Lip * FMath::Sin(PI * U);
				const double WX = Root.X + Out.X * Reach, WY = Root.Y + Out.Y * Reach;
				const double Sea = Waves.Height(WX, WY, Time);
				FVector P = SailingFrame::ToWorld(GetWorld(), WX, WY, 0.0);
				P.Z = WaterSurfaceZ + (Sea + double(H * Profile) + 0.01) * CmPerMeter;
				V.Add(P);
				UV.Add(FVector2D(U, Tt));
				// Fades: in from the stem, out aft, into the sea at the outer edge (the material) and softly at the root.
				const float Ends = FMath::SmoothStep(0.f, 0.18f, Tt) * (1.f - Tt * Tt);
				Col.Add(FLinearColor(Lip, Rise, Fine, Fade * Ends * FMath::SmoothStep(0.f, 0.2f, U + 0.05f)));
			}
		}
		for (int32 I = 0; I + 1 < NS; ++I)
		{
			for (int32 J = 0; J + 1 < NU; ++J)
			{
				const int32 A = Base + I * NU + J, B = A + 1, C = A + NU, D = C + 1;
				if (Side == 0) Tris.Append({ A, C, D, A, D, B }); else Tris.Append({ A, D, C, A, B, D });
			}
		}
	}
	// Normals from the grid (facing up), tangents along the bow.
	TArray<FVector> N;
	TArray<FProcMeshTangent> Tan;
	N.SetNum(V.Num());
	Tan.SetNum(V.Num());
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const int32 Base = Side * NS * NU;
		for (int32 I = 0; I < NS; ++I)
		{
			for (int32 J = 0; J < NU; ++J)
			{
				const int32 K = Base + I * NU + J;
				const FVector Dt = V[Base + FMath::Min(I + 1, NS - 1) * NU + J] - V[Base + FMath::Max(I - 1, 0) * NU + J];
				const FVector Du = V[Base + I * NU + FMath::Min(J + 1, NU - 1)] - V[Base + I * NU + FMath::Max(J - 1, 0)];
				FVector Nk = FVector::CrossProduct(Dt, Du).GetSafeNormal();
				if (Nk.Z < 0.0) Nk = -Nk;
				N[K] = Nk.IsNearlyZero() ? FVector::UpVector : Nk;
				Tan[K] = FProcMeshTangent(Dt.GetSafeNormal(), false);
			}
		}
	}
	if (BowWave->GetNumSections() == 0)
	{
		BowWave->CreateMeshSection_LinearColor(0, V, Tris, N, UV, Col, Tan, false);
	}
	else
	{
		BowWave->UpdateMeshSection_LinearColor(0, V, N, UV, Col, Tan);
	}
}

void ASailboatPawn::UpdateBoatWetness(float DeltaSeconds)
{
	UpdateBowWave(DeltaSeconds);
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
	// Spray hull (docs/spray-hull): the bow wave and slams throw water up the topsides, the same tests AWaterSurface::
	// UpdateSpray throws its spray by (the bow wave past 2 m/s, a slam when the water closes on the bow faster than
	// 0.45 m/s); the side stays wet above the line for half a minute or so after them.
	{
		const FHullShape& Hull = Boat.GetConfig().Hulls[0];
		const Vec3 B = Boat.BodyToWorld(Vec3(0.85 * Hull.BowX, 0.0, 0.0));
		const FVector BowNow(B.X, B.Y, B.Z);
		float Throw = 0.f;
		if (bHasLastBow && DeltaSeconds > 1e-4f)
		{
			const FVector BowV = (BowNow - LastBowM) / DeltaSeconds;
			double H, Vz, Sx, Sy;
			GM->GetWaves().Sample(B.X, B.Y, S.Time, H, Vz, Sx, Sy);
			const double Closing = Vz - BowV.Z, Speed = FVector2D(BowV.X, BowV.Y).Size();
			if (Speed > 2.0) Throw += 0.04f * float(Speed - 2.0) * DeltaSeconds;
			if (BowNow.Z <= H + 0.15 && Closing > 0.45 && Speed > 1.5)
				Throw += 0.8f * float(FMath::Min(Closing, 2.5) - 0.45) * FMath::Min(float(Speed) / 3.f, 1.5f) * DeltaSeconds;
		}
		LastBowM = BowNow;
		bHasLastBow = true;
		SprayWetness = FMath::Clamp(SprayWetness + Throw - DeltaSeconds / 40.f, 0.f, 1.f);
	}
	// Splash band: the bow wave and the chop climb the topsides with speed and sea, and spray after them.
	const float Band = 4.f + float(Hs) * 45.f + FMath::Clamp(Knots - 3.f, 0.f, 6.f) * 2.5f + 25.f * SprayWetness;
	// Deck: rain soaks it within a minute; spray comes aboard upwind in a sea; it dries in about five minutes.
	const float Rain = float(GM->GetWeatherState().Rain);
	const float Spray = FMath::Clamp(float(Hs - 0.3) * 2.f, 0.f, 1.f) * FMath::Clamp((Knots - 3.f) / 3.f, 0.f, 1.f) * FMath::Clamp(float(FMath::Abs(T.Heel)) / 0.25f, 0.f, 1.f);
	DeckWetness = FMath::Clamp(DeckWetness + DeltaSeconds * (Rain * 0.03f + Spray * 0.01f - 0.0035f), 0.f, 1.f);
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("WaterZ"), float(WetLineZ));
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("WetBand"), Band);
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("DeckWet"), DeckWetness);
	// Rain deck (docs/rain-deck): the deck's low spots fill with rain (full in about ten minutes of steady rain), drain and
	// dry in about fifteen once it stops; heel spills them. The rain itself rings the puddles and the wet deck (Rain).
	{
		const float Heel = FMath::Clamp(float(FMath::Abs(T.Heel)) / 0.3f, 0.f, 1.f);
		PuddleLevel = FMath::Clamp(PuddleLevel + DeltaSeconds * (Rain * 0.0017f - 0.0011f - 0.01f * Heel * PuddleLevel), 0.f, 1.f);
		UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("Rain"), Rain);
		UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("Puddle"), PuddleLevel);
		UpdateDrips(DeltaSeconds);
	}
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("SprayWet"), SprayWetness);
	// Boat fidelity 1: M_BoatSurface's close-up detail maps on High and Ultra (docs/boat-fidelity-1); -SailingNoBoatDetail compares.
	static SailingArgs::FCachedFlag NoBoatDetailArg(TEXT("SailingNoBoatDetail"));
	const bool bDetail = USailingSettings::Get()->Quality >= ESailingQuality::High && !NoBoatDetailArg.Get();
	UKismetMaterialLibrary::SetScalarParameterValue(this, BoatParameters, TEXT("Detail"), bDetail ? 1.f : 0.f);
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
	// Ultra audit item 7: the polo's loose cloth (M_CrewFabric's flutter and lag) gets the apparent wind, the air's own
	// motion past the boat (it comes from the apparent wind angle, + from starboard), and the boat's acceleration, both in
	// the world.
	if (CrewClothMids.Num() > 0)
	{
		const FVector WindBody = -FVector(FMath::Cos(T.ApparentWindAngle), FMath::Sin(T.ApparentWindAngle), 0.0) * T.ApparentWindSpeed;
		const FVector WindWS = RootTM.TransformVectorNoScale(WindBody), AccelWS = RootTM.TransformVectorNoScale(Motion.Accel);
		for (UMaterialInstanceDynamic* Mid : CrewClothMids)
		{
			if (!Mid) continue;
			Mid->SetVectorParameterValue(TEXT("WindWS"), FLinearColor(WindWS.X, WindWS.Y, WindWS.Z, 0.f));
			Mid->SetVectorParameterValue(TEXT("AccelWS"), FLinearColor(AccelWS.X, AccelWS.Y, AccelWS.Z, 0.f));
		}
	}
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
		// docs/crew-tack/: each sailor's crossing on a tack or gybe, scripted against the boom.
		Place.Crossing = I < CrewFigures.Num() ? &CrewFigures[I].Crossing : nullptr;
		Place.Dt = DeltaSeconds;
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
		// (From: where the held line comes from, so it runs across the palm; zero for none.)
		auto Hold = [&](int32 Hand, const FVector& At, TOptional<FVector>& Grip, const FVector& From)
		{
			if (FVector::Dist(At, Shoulder[Hand]) > Reach * 1.05) return false;
			Hands.Mode[Hand] = FCrewHands::EMode::Reach;
			Hands.Target[Hand] = CompTM.InverseTransformPosition(At);
			Hands.Grip[Hand] = 0.85f;
			if (!From.IsZero()) Hands.Along[Hand] = CompTM.InverseTransformVectorNoScale((At - From).GetSafeNormal());
			Grip = At;
			return true;
		};
		// Crew C1: how hard each line pulls (the arms take it): the helm force at the tiller, the sails' load on the sheets.
		const float HelmLoad = float(FMath::Clamp(FMath::Abs(T.HelmForce) / 120.0, 0.0, 1.0));
		const float SheetLoad = float(FMath::Clamp(FMath::Sqrt(FMath::Square(T.DriveForce) + FMath::Square(T.HeelingForce)) / 2500.0, 0.0, 1.0));
		const bool bSeated = P.Stance == ECrewStance::Helm || P.Stance == ECrewStance::DinghyHike || P.Stance == ECrewStance::Cockpit
			|| P.Stance == ECrewStance::RailHike;
		// (Crossing on a tack, the helm keeps the extension and the mainsheet: docs/crew-tack/.)
		if ((bSeated || (Pl.bScripted && bHelm)) && !bTrafficBoat)
		{
			const int32 Aft = Shoulder[0].X < Shoulder[1].X ? 0 : 1;
			const FVector Toward = FRotator(0.f, F.Yaw, 0.f).Vector();
			if (bHelm && bTiller && Cfg.WheelHardOverSeconds > 0.0)
			{
				// The maxi: the aft hand on the wheel's rim (TillerEnd), where it can reach it.
				if (Hold(Aft, TillerEnd, HelmGripCm, FVector::ZeroVector)) Tension[Aft] = HelmLoad;
			}
			else if (bHelm && bTiller && P.Stance == ECrewStance::DinghyHike)
			{
				// Round 10: a dinghy sailor holds the extension across the body, the aft hand in front of the chest (the dagger
				// grip), and the mainsheet coming up from its ratchet block in the forward hand just ahead of it (the ILCA's
				// hands had been held out to the sides: the hip-height grip and the keelboat's traveler car were out of reach).
				const FVector Chest = 0.5 * (Shoulder[0] + Shoulder[1]);
				// (A hand's width apart along the boat: together they read as folded arms.)
				if (Hold(Aft, Chest + Toward * 28.0 + FVector(-16.0, 0.0, -36.0), HelmGripCm, TillerEnd)) Tension[Aft] = HelmLoad;
				if (Hold(1 - Aft, Chest + Toward * 32.0 + FVector(18.0, 0.0, -24.0), MainGripCm, FVector::ZeroVector)) Tension[1 - Aft] = 0.6f * SheetLoad;
			}
			else if (bHelm && bTiller)
			{
				// The extension (about 90 cm) from the tiller's end up to the aft hand, held low beside the hip.
				const FVector ToShoulder = Shoulder[Aft] + FVector(0.f, 0.f, -32.f) - TillerEnd;
				const double Len = FMath::Min(90.0, ToShoulder.Size() - 25.0);
				if (Len > 20.0 && Hold(Aft, TillerEnd + ToShoulder.GetSafeNormal() * Len, HelmGripCm, TillerEnd)) Tension[Aft] = HelmLoad;
				// The mainsheet's tail from its block on the car, held out in front at lap height.
				if (!MainsheetCarCm.IsZero())
				{
					const int32 Fwd = 1 - Aft;
					const FVector At = Shoulder[Fwd] + (MainsheetCarCm - Shoulder[Fwd]).GetSafeNormal() * 8.0 + Toward * 30.0 + FVector(0.f, 0.f, -36.f);
					if (Hold(Fwd, At, MainGripCm, MainsheetCarCm)) Tension[Fwd] = 0.6f * SheetLoad;
				}
			}
			else if (bHelm && Cfg.Type == EBoatType::Catalina30)
			{
				// docs/cockpit-eye/: both hands on her wheel's rim on their side (build_fleet.py: the hub 0.95 m over the sole at
				// x -3.45, the rim 0.42 m across and 12 cm aft of it), the inboard hand 50 deg off the top, the outboard 110.
				TOptional<FVector> Rim;
				const double Hub = CrewFloorZ(Cfg, -3.45, 0.0) + 0.95;
				const double WheelSide = FMath::Sign(Shoulder[0].Y + Shoulder[1].Y);
				for (int32 Hand = 0; Hand < 2; ++Hand)
				{
					const bool bInboard = FMath::Abs(Shoulder[Hand].Y) < FMath::Abs(Shoulder[1 - Hand].Y);
					const double A = FMath::DegreesToRadians(bInboard ? 50.0 : 110.0);
					const FVector At = FVector(-3.57, WheelSide * 0.42 * FMath::Sin(A), Hub + 0.42 * FMath::Cos(A)) * CmPerMeter;
					if (Hold(Hand, At, Rim, FVector::ZeroVector)) Tension[Hand] = 0.5f * HelmLoad;
				}
			}
			else if (!bHelm && bJibTail && I == N - 2)
			{
				// The trimmer: the working sheet's tail a forearm's length off its self-tailer.
				const int32 Near = FVector::DistSquared(Shoulder[0], Tailer) < FVector::DistSquared(Shoulder[1], Tailer) ? 0 : 1;
				const FVector ToShoulder = Shoulder[Near] - Tailer;
				if (Hold(Near, Tailer + ToShoulder.GetSafeNormal() * FMath::Clamp(ToShoulder.Size() - 40.0, 25.0, 55.0), JibGripCm, Tailer)) Tension[Near] = 0.4f * SheetLoad;
			}
			for (int32 Hand = 0; Hand < 2; ++Hand)
			{
				// (A dinghy sailor's free hand stays out for balance; on the Hobie, whose twin tillers have no socket to hold, both
				// hands were free and, leaning back, the stance's arms pointed overhead at the sail: docs/crew-light-air/.)
				if (Hands.Mode[Hand] == FCrewHands::EMode::Free && (P.Stance != ECrewStance::DinghyHike || Cfg.bMultihull)) Hands.Mode[Hand] = FCrewHands::EMode::Knee;
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
		In.bReact = !FParse::Param(SailingArgs::Dev(), TEXT("SailingCrewStill"));
		In.bClips = !FParse::Param(SailingArgs::Dev(), TEXT("SailingNoCrewClips"));
		In.bTravelerBridge = bModelTravelerBridge;
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
		// docs/crew-tack/: crossing, a hand on the coaming (the old side's, then the new side's) and the feet stepping.
		if (Pl.bScripted && Pl.HoldSide >= 0 && In.Attach.bValid)
		{
			const FVector At = Pl.bHoldCabin ? In.Attach.HandholdCabin[Pl.HoldSide] : In.Attach.HandholdCoaming[Pl.HoldSide];
			const int32 H = Pl.HoldHand;
			if (FVector::Dist(At, Shoulder[H]) < Reach * 1.05)
			{
				In.Hands.Mode[H] = FCrewHands::EMode::Reach;
				In.Hands.Target[H] = CompTM.InverseTransformPosition(At);
				In.Hands.Grip[H] = 0.85f;
				In.Hands.Along[H] = CompTM.InverseTransformVectorNoScale(FVector::ForwardVector);
			}
		}
		In.FootAnchor[0] = Pl.FootAnchor[0] * CmPerMeter;
		In.FootAnchor[1] = Pl.FootAnchor[1] * CmPerMeter;
		In.FootWeight = Pl.FootWeight;
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
		// (docs/crew-tack/: or at a sim time, -SailingShotAtSim=<s>, for a strip of stills through a demo tack.)
		double ShotAt = -1.0;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingShotAtSim="), ShotAt);
		const bool bShotNow = ShotAt >= 0.0 ? S.Time >= ShotAt : Pl.Duck > 0.8f && F.TransitionS > 0.9f;
		if (!CrewShotTaken.Taken() && bHelm && !bTrafficBoat && bShotNow && FParse::Value(SailingArgs::Dev(), TEXT("SailingShotCrew="), CrewShot))
		{
			CrewShotTaken.Take();
			FScreenshotRequest::RequestScreenshot(FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / FString::Printf(TEXT("Bench/%s.png"), *CrewShot)), false, false);
		}
		static double LastDebug = 0.0;
		if (FParse::Param(SailingArgs::Dev(), TEXT("SailingDebugCrew")) && S.Time - LastDebug > 1.0 && !bTrafficBoat)
		{
			if (I == N - 1) LastDebug = S.Time;
			const FCrewMotionReport& Rep = Anim->GetReport();
			FCrewCockpitWell DebugWell;
			const bool bDebugWell = CrewCockpitWell(Cfg, DebugWell);
			UE_LOG(LogTemp, Log, TEXT("Crew %d pelvis %s m over floor %.2f (well %.2f..%.2f)"), I, *Pl.Pelvis.ToString(), CrewFloorZ(Cfg, Pl.Pelvis.X, Pl.Pelvis.Y),
				bDebugWell ? DebugWell.X0 : 0.0, bDebugWell ? DebugWell.X1 : 0.0);
			UE_LOG(LogTemp, Log, TEXT("Crew %d stance %d duck %.2f: modes %d %d, felt %s, tip %.2f%s, head %.1f deg, clip %s %.2f; accel %s omega %s alpha %s"), I, int32(P.Stance), Pl.Duck,
				int32(Hands.Mode[0]), int32(Hands.Mode[1]), *Rep.Felt.ToString(), Rep.TipRatio, Rep.bBracing ? TEXT(" bracing") : TEXT(""), Rep.HeadTiltDeg,
				Rep.Clip >= 0 ? CrewClips::Info(Rep.Clip).Label : TEXT("-"), Rep.ClipWeight,
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
