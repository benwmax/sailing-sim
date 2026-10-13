// Visual V2: the modelled boats (the J/22 first). The pawn's other visuals live in SailboatPawn.cpp.
//
// A class with a model (Tools/blender/build_<boat>.py, imported by scripts/make-boat-models.sh) shows its hull, mast,
// boom and rudder meshes instead of the procedural hull and shapes. The standing and running rigging is drawn here
// every frame from the meshes' sockets, with sag from the physics: a loaded sheet or the windward shroud runs straight,
// an eased or lazy sheet droops, the leeward shroud goes slack in a breeze. The mast bends with the backstay and the
// wind (its material's world position offset; the rig points on it follow the same curve), the traveler car moves
// with the trim, and the hull's wet line and the deck's wetness come from the waves, spray and rain (MPC_Boat).
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "ProceduralMeshComponent.h"

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
	// The other seven boats keep their procedural visuals until they are modelled (Visual V7).
	if (Type == EBoatType::J22 && J22HullMesh && J22MastMesh && J22BoomMesh && J22RudderMesh)
	{
		M.Hull = J22HullMesh;
		M.Mast = J22MastMesh;
		M.Boom = J22BoomMesh;
		M.Rudder = J22RudderMesh;
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
	Part->RegisterComponent();
	BoatParts.Add(Part);
	return Part;
}

void ASailboatPawn::BuildModelVisuals(const FBoatModelMeshes& Model)
{
	ModelHull = AddModelPart(Model.Hull, BoatRoot, FVector::ZeroVector);
	ModelMast = AddModelPart(Model.Mast, BoatRoot, ModelHull->GetSocketTransform(TEXT("MastStep"), RTS_Component).GetLocation());
	MastBendHeightCm = FMath::Max(Model.Mast->GetBounds().GetBox().Max.Z, 100.f);
	MastMaterial = ModelMast->CreateDynamicMaterialInstance(ModelMast->GetMaterialIndex(TEXT("Aluminium")) >= 0 ? ModelMast->GetMaterialIndex(TEXT("Aluminium")) : 0);
	// The boom hangs on the gooseneck pivot (placed from the physics rig); the rudder turns on its stock.
	ModelBoom = AddModelPart(Model.Boom, BoomPivot, FVector::ZeroVector);
	USceneComponent* Pivot = NewObject<USceneComponent>(this);
	Pivot->SetupAttachment(BoatRoot);
	Pivot->SetRelativeLocation(ModelHull->GetSocketTransform(TEXT("RudderPivot"), RTS_Component).GetLocation());
	Pivot->RegisterComponent();
	BoatParts.Add(Pivot);
	RudderPivots.Add(Pivot);
	ModelRudder = AddModelPart(Model.Rudder, Pivot, FVector::ZeroVector);
	// The traveler car slides along the bar with the trim.
	TravelerCar = AddBoatPart(CubeMesh, ModelHull->GetSocketTransform(TEXT("Traveler_C"), RTS_Component).GetLocation(), FVector(8.f, 7.f, 3.f), FLinearColor(0.02f, 0.02f, 0.02f));
	if (CarMaterial) TravelerCar->SetMaterial(0, CarMaterial);
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

	// Traveler car: centered at 0, toward the boom's side when eased down (1 = all the way to leeward).
	const FVector TravC = RigPoint(ModelHull, TEXT("Traveler_C")), TravS = RigPoint(ModelHull, TEXT("Traveler_S"));
	const float BoomSide = S.BoomAngle >= 0.0 ? 1.f : -1.f;
	FVector Car = TravC + (TravS - TravC) * FMath::Clamp(float(Controls.Traveler), -1.f, 1.f) * BoomSide;
	TravelerCar->SetRelativeLocation(Car + FVector(0.f, 0.f, 1.5f));

	// Which side is to leeward: the side the boom (the sails) are on; the windward rig takes the load.
	const bool bLeeStbd = S.BoomAngle >= 0.0;
	const float Loaded = FMath::Clamp((Aws - 3.f) / 5.f, 0.f, 1.f); // below about 3 kn nothing is loaded

	TArray<FRigLine> Wires, Ropes;
	// Standing rigging: forestay, uppers via the spreaders, lowers, backstay.
	const FVector Hounds = RigPoint(ModelMast, TEXT("Hounds"));
	Wires.Add({ RigPoint(ModelHull, TEXT("ForestayTack")), Hounds, 0.25f, 0.f });
	for (const TCHAR* Tag : { TEXT("S"), TEXT("P") })
	{
		const bool bStbd = Tag[0] == TEXT('S');
		const bool bLee = bStbd == bLeeStbd;
		// The leeward shrouds go slack in a breeze (the windward ones carry the rig).
		const float Slack = bLee ? 0.0002f + 0.0007f * Breeze * FMath::Clamp(float(FMath::Abs(T.Heel)) / 0.1f, 0.f, 1.f) : 0.f;
		const FVector Tip = RigPoint(ModelMast, *FString::Printf(TEXT("SpreaderTip_%s"), Tag));
		Wires.Add({ RigPoint(ModelHull, *FString::Printf(TEXT("ChainplateUpper_%s"), Tag)), Tip, 0.25f, Slack });
		Wires.Add({ Tip, Hounds, 0.25f, Slack });
		Wires.Add({ RigPoint(ModelHull, *FString::Printf(TEXT("ChainplateLower_%s"), Tag)), RigPoint(ModelMast, TEXT("LowerTang")), 0.25f, Slack });
	}
	Wires.Add({ RigPoint(ModelHull, TEXT("BackstayPlate")), RigPoint(ModelMast, TEXT("MastheadAft")), 0.2f, 0.0008f * (1.f - float(Controls.Backstay)) * (1.f - Loaded) });

	// Jib sheets: the working sheet (leeward) from the clew through its lead to the winch, nearly straight under load;
	// the lazy sheet over the cabin top to the windward lead, drooping.
	if (Boat.GetConfig().HasJib())
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

	// Mainsheet: a 4:1 tackle between the boom bail and the traveler car; taut when the main is drawing.
	const FVector BoomBlock = RigPoint(ModelBoom, TEXT("Boom_Mainsheet"));
	const float MainSlack = FMath::Lerp(0.015f, 0.f, Loaded);
	for (int32 K = 0; K < 4; ++K)
	{
		const FVector Off(0.f, (K - 1.5f) * 1.2f, 0.f);
		Ropes.Add({ BoomBlock + Off, Car + FVector(0.f, 0.f, 3.f) + Off, 0.35f, MainSlack });
	}
	// Vang: a 3:1 tackle from the boom to the mast base, slack when eased off.
	const FVector VangBoom = RigPoint(ModelBoom, TEXT("Boom_Vang")), VangMast = RigPoint(ModelMast, TEXT("MastBase"));
	for (int32 K = 0; K < 3; ++K)
	{
		const FVector Off(0.f, (K - 1.f) * 1.0f, 0.f);
		Ropes.Add({ VangBoom + Off, VangMast + Off, 0.3f, 0.02f * (1.f - float(Controls.Vang)) });
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
