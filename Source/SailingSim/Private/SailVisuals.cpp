// Visual V3: the sails as cloth and the telltales as ribbons (the cloth itself is SailCloth.cpp).
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "SailingSettings.h"
#include "ProceduralMeshComponent.h"

using namespace Sailing;

double ASailboatPawn::ClothCpuSeconds = 0.0;

void ASailboatPawn::UpdateSailCloth(UProceduralMeshComponent* Mesh, FSailCloth& Cloth, const FSailGeometry& Geo, ESailKind Kind,
	const FSailStripState* Strips, int32 Side, float DeltaSeconds)
{
	if (!Cloth.IsValid()) return;
	FSailClothDrive Drive;
	Drive.DeltaSeconds = DeltaSeconds;
	Drive.Time = VisualTime;
	Drive.ApparentWindKnots = float(Boat.GetTelemetry().ApparentWindSpeed / kKnot);
	Drive.Cunningham = float(Controls.Cunningham);
	Drive.GravityBody = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
	// Low draws the physics shape directly; Medium and High run the cloth (and traffic boats in the distance don't).
	Drive.bSimulate = USailingSettings::Get()->Quality != ESailingQuality::Low && !bTrafficBoat;
	const double Start = FPlatformTime::Seconds();
	Cloth.Step(Strips, Side, Drive);
	ClothCpuSeconds += FPlatformTime::Seconds() - Start;

	TArray<FVector> Normals;
	Cloth.ComputeNormals(Normals);
	TArray<FProcMeshTangent> Tangents;
	Cloth.ComputeTangents(Tangents);
	if (Mesh->GetNumSections() == 0)
	{
		TArray<int32> Tris;
		Cloth.Triangles(Tris);
		Mesh->CreateMeshSection(0, Cloth.Positions(), Tris, Normals, Cloth.UV0(), Cloth.UV1(), Cloth.UV2(), TArray<FVector2D>(),
			TArray<FColor>(), Tangents, false);
	}
	else
	{
		// Perf 1 fix 3: the section is updated in place (same topology); the UVs never change after it was made, so only
		// positions, normals and tangents go across.
		Mesh->UpdateMeshSection(0, Cloth.Positions(), Normals, TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FColor>(), Tangents);
	}
}

void ASailboatPawn::UpdateTelltaleRibbons()
{
	const FBoatState& S = Boat.GetState();
	const FBoatTelemetry& T = Boat.GetTelemetry();
	const FBoatConfig& Cfg = Boat.GetConfig();
	const FVector Up = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector::UpVector);

	struct FRibbon { FVector Root, Dir, Side; float LengthCm; float Wave; FColor Color; };
	TArray<FRibbon> Ribbons;
	auto Add = [&](const FVector& Root, const FVector& Along, const FVector& Out, ETelltaleState State, float Length, float Phase, FColor Color)
	{
		// Streaming: along the cloth, a gentle ripple. Lifting: up and out, spinning. Stalled: droops and twirls on
		// the leeward face. Fluttering: streams but flicks hard.
		const float Flick = FMath::Sin(VisualTime * 26.f + Phase);
		FVector Dir;
		float Wave = 0.6f;
		switch (State)
		{
		case ETelltaleState::Lifting: Dir = Along * 0.35f + Up * 0.8f + Out * (0.35f + 0.25f * Flick); Wave = 2.0f; break;
		case ETelltaleState::Stalled: Dir = Along * 0.2f - Up * 0.85f + Out * (0.3f * Flick); Wave = 1.2f; break;
		case ETelltaleState::Fluttering: Dir = Along + Up * (0.4f * Flick); Wave = 3.0f; break;
		default: Dir = Along + Up * (0.04f * Flick); break;
		}
		Ribbons.Add({ Root, Dir.GetSafeNormal(), Out, Length, Wave, Color });
	};
	// Which face is windward: the side the sail bellies away from.
	auto WindwardOut = [](const FVector& Normal, int32 Side) { return (FVector::DotProduct(Normal, FVector(0.f, Side, 0.f)) > 0.f ? -Normal : Normal); };

	if (Cfg.HasJib() && JibCloth.IsValid())
	{
		// Jib luff telltales at a quarter, half and three-quarters height, a hand's width behind the luff: red to
		// port, green to starboard, as on a real boat.
		for (int32 K = 0; K < 3; ++K)
		{
			const float V = 0.25f * (K + 1);
			const int32 StripIndex = FMath::Clamp(int32(V * T.NumJibStrips), 0, T.NumJibStrips - 1);
			const FSailStripState& St = T.JibStrips[StripIndex];
			const FVector Root = JibCloth.PointAt(0.1f, V), Along = JibCloth.ChordTangentAt(0.1f, V);
			const FVector Windward = WindwardOut(JibCloth.NormalAt(0.1f, V), S.JibSide);
			const bool bPortWindward = Windward.Y < 0.f;
			Add(Root + Windward * 0.6f, Along, Windward, JibTelltaleState(St, true), 18.f, K * 2.f, bPortWindward ? FColor(200, 15, 15) : FColor(15, 160, 30));
			Add(Root - Windward * 0.6f, Along, -Windward, JibTelltaleState(St, false), 18.f, K * 2.f + 1.f, bPortWindward ? FColor(15, 160, 30) : FColor(200, 15, 15));
		}
	}
	if (MainCloth.IsValid())
	{
		// Main leech telltales at the battens: stream aft off the leech, or curl behind it when the main stalls.
		for (int32 K = 0; K < 3; ++K)
		{
			const float V = 0.4f + 0.2f * K;
			const int32 StripIndex = FMath::Clamp(int32(V * T.NumMainStrips), 0, T.NumMainStrips - 1);
			const FSailStripState& St = T.MainStrips[StripIndex];
			const FVector Root = MainCloth.PointAt(1.f, V), Along = MainCloth.ChordTangentAt(0.97f, V);
			const FVector Leeward = -WindwardOut(MainCloth.NormalAt(0.97f, V), S.MainSide);
			const ETelltaleState State = LeechTelltaleState(St);
			Add(Root, State == ETelltaleState::Stalled ? (Leeward * 0.9f + Along * 0.2f) : Along, Leeward, State == ETelltaleState::Stalled ? ETelltaleState::Streaming : State,
				22.f, 7.f + K * 1.7f, FColor(200, 15, 15));
		}
	}

	// Ribbons: 6 segments, 1.2 cm wide, waving across their width direction.
	TArray<FVector> Verts, Normals;
	TArray<FColor> Colors;
	TArray<int32> Tris;
	constexpr int32 Segs = 6;
	for (const FRibbon& R : Ribbons)
	{
		const FVector Across = FVector::CrossProduct(R.Dir, R.Side).GetSafeNormal() * 0.6f;
		const int32 Base = Verts.Num();
		for (int32 I = 0; I <= Segs; ++I)
		{
			const float S01 = float(I) / Segs;
			const FVector C = R.Root + R.Dir * (R.LengthCm * S01) + R.Side * (R.Wave * S01 * FMath::Sin(VisualTime * 22.f - S01 * 6.f + R.LengthCm));
			Verts.Add(C - Across);
			Verts.Add(C + Across);
			Normals.Add(R.Side);
			Normals.Add(R.Side);
			Colors.Add(R.Color);
			Colors.Add(R.Color);
			if (I < Segs && !bTelltalesBuilt)
			{
				const int32 A = Base + 2 * I;
				Tris.Append({ A, A + 2, A + 1, A + 1, A + 2, A + 3 });
			}
		}
	}
	if (Verts.Num() == 0) return;
	if (!bTelltalesBuilt || TelltaleRibbons->GetNumSections() == 0)
	{
		if (Tris.Num() == 0)
		{
			for (int32 K = 0; K < Ribbons.Num(); ++K)
			{
				for (int32 I = 0; I < Segs; ++I)
				{
					const int32 A = K * 2 * (Segs + 1) + 2 * I;
					Tris.Append({ A, A + 2, A + 1, A + 1, A + 2, A + 3 });
				}
			}
		}
		TelltaleRibbons->CreateMeshSection(0, Verts, Tris, Normals, TArray<FVector2D>(), Colors, TArray<FProcMeshTangent>(), false);
		TelltaleRibbons->SetMaterial(0, TelltaleMaterial);
		bTelltalesBuilt = true;
	}
	else
	{
		TelltaleRibbons->UpdateMeshSection(0, Verts, Normals, TArray<FVector2D>(), Colors, TArray<FProcMeshTangent>());
	}
}
