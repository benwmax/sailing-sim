// Visual V3: the sails as cloth and the telltales as ribbons (the cloth itself is SailCloth.cpp).
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "SailingSettings.h"
#include "ProceduralMeshComponent.h"
#include "BenchRunner.h"
#include "Async/ParallelFor.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/PlayerController.h"

using namespace Sailing;

double ASailboatPawn::ClothCpuSeconds = 0.0;

namespace
{
	/**
	 * docs/sail-shadow-steps/: the sails are drawn on a grid three times finer than the cloth's (FSailCloth::Rows x Cols,
	 * about 30 cm a cell on a J/22's spinnaker). Each of the cloth's cells is a flat facet, so a shadow grazing the curved
	 * sail (its own far half, the main's on the spinnaker) fell on whole facets: an edge in steps along the grid, which no
	 * shadow resolution changes (the shadow terminator). The positions between the cloth's are Catmull-Rom (the surface
	 * curves between them; bilinear points would stay on the old facets), the normals, tangents and UVs bilinear. The cloth,
	 * its telltales and its clew stay on the cloth's own grid.
	 */
	constexpr int32 SailRenderSub = 3;
	constexpr int32 SailRenderRows = (FSailCloth::Rows - 1) * SailRenderSub + 1;
	constexpr int32 SailRenderCols = (FSailCloth::Cols - 1) * SailRenderSub + 1;

	template <typename T> T CatmullRom(const T& P0, const T& P1, const T& P2, const T& P3, float t)
	{
		const float t2 = t * t, t3 = t2 * t;
		return (P1 * 2.f + (P2 - P0) * t + (P0 * 2.f - P1 * 5.f + P2 * 4.f - P3) * t2 + (P1 * 3.f - P0 - P2 * 3.f + P3) * t3) * 0.5f;
	}

	/** Where on the cloth's grid a render vertex falls: the cell (R, C) and the fractions in it. */
	void SailRenderCell(int32 Rr, int32 Rc, int32& R, int32& C, float& Tr, float& Tc)
	{
		R = FMath::Min(Rr / SailRenderSub, FSailCloth::Rows - 2);
		C = FMath::Min(Rc / SailRenderSub, FSailCloth::Cols - 2);
		Tr = float(Rr - R * SailRenderSub) / SailRenderSub;
		Tc = float(Rc - C * SailRenderSub) / SailRenderSub;
	}

	template <typename T> T SailBilinear(const TArray<T>& G, int32 R, int32 C, float Tr, float Tc)
	{
		auto At = [&](int32 Ri, int32 Ci) -> const T& { return G[Ri * FSailCloth::Cols + Ci]; };
		return (At(R, C) * (1.f - Tc) + At(R, C + 1) * Tc) * (1.f - Tr) + (At(R + 1, C) * (1.f - Tc) + At(R + 1, C + 1) * Tc) * Tr;
	}

	FVector SailCubic(const TArray<FVector>& G, int32 R, int32 C, float Tr, float Tc)
	{
		auto At = [&](int32 Ri, int32 Ci) -> const FVector&
		{
			return G[FMath::Clamp(Ri, 0, FSailCloth::Rows - 1) * FSailCloth::Cols + FMath::Clamp(Ci, 0, FSailCloth::Cols - 1)];
		};
		FVector Row[4];
		for (int32 K = 0; K < 4; ++K)
		{
			const int32 Ri = R - 1 + K;
			Row[K] = CatmullRom(At(Ri, C - 1), At(Ri, C), At(Ri, C + 1), At(Ri, C + 2), Tc);
		}
		return CatmullRom(Row[0], Row[1], Row[2], Row[3], Tr);
	}

	template <typename T> void RefineSailUV(const TArray<T>& G, TArray<T>& Out);

	/**
	 * Ultra audit item 5: the wrinkles (FSailWrinkles) on the render grid, each vertex moved along its normal, and the
	 * normals taken again from the wrinkled surface so the light catches them.
	 */
	void WrinkleSail(const FSailCloth& Cloth, const FSailWrinkles& W, TArray<FVector>& Pos, TArray<FVector>& Normals)
	{
		if (!W.bOn) return;
		TArray<FVector4f>& Grid = Cloth.WrinkleGrid;
		if (Grid.Num() != SailRenderRows * SailRenderCols)
		{
			TArray<FVector2D> UV;
			RefineSailUV(Cloth.UV0(), UV);
			Grid.SetNumUninitialized(UV.Num());
			for (int32 Rr = 0; Rr < SailRenderRows; ++Rr)
			{
				for (int32 Rc = 0; Rc < SailRenderCols; ++Rc)
				{
					// The cell here: its steps along the chord and up the sail.
					const FVector2D& U0 = UV[Rr * SailRenderCols + Rc];
					const double Du = 0.5 * (FVector2D::Distance(U0, UV[Rr * SailRenderCols + FMath::Min(Rc + 1, SailRenderCols - 1)]) + FVector2D::Distance(U0, UV[Rr * SailRenderCols + FMath::Max(Rc - 1, 0)]));
					const double Dv = 0.5 * (FVector2D::Distance(U0, UV[FMath::Min(Rr + 1, SailRenderRows - 1) * SailRenderCols + Rc]) + FVector2D::Distance(U0, UV[FMath::Max(Rr - 1, 0) * SailRenderCols + Rc]));
					Grid[Rr * SailRenderCols + Rc] = FVector4f(float(U0.X), float(U0.Y), float(Du), float(Dv));
				}
			}
		}
		bool bAny = false;
		TBitArray<> Moved(false, Pos.Num());
		const TArray<FVector> SmoothPos = Pos;
		for (int32 I = 0; I < Grid.Num(); ++I)
		{
			const FVector4f& G = Grid[I];
			const float Cm = SailWrinkleCm(W, FVector2D(G.X, G.Y), G.Z, G.W);
			if (Cm == 0.f) continue;
			Pos[I] += Normals[I] * Cm;
			Moved[I] = true;
			bAny = true;
		}
		if (!bAny) return;
		// The wrinkles' own turn of the normal (the wrinkled surface's against the same surface unwrinkled, both by central
		// differences) added to the cloth's normals: no seam where the wrinkles end.
		auto FdNormal = [](const TArray<FVector>& P, int32 Rr, int32 Rc)
		{
			const FVector Du = P[Rr * SailRenderCols + FMath::Min(Rc + 1, SailRenderCols - 1)] - P[Rr * SailRenderCols + FMath::Max(Rc - 1, 0)];
			const FVector Dv = P[FMath::Min(Rr + 1, SailRenderRows - 1) * SailRenderCols + Rc] - P[FMath::Max(Rr - 1, 0) * SailRenderCols + Rc];
			return FVector::CrossProduct(Du, Dv).GetSafeNormal();
		};
		for (int32 Rr = 0; Rr < SailRenderRows; ++Rr)
		{
			for (int32 Rc = 0; Rc < SailRenderCols; ++Rc)
			{
				const int32 I = Rr * SailRenderCols + Rc;
				bool bNear = false;
				for (int32 Dr = -1; Dr <= 1 && !bNear; ++Dr)
					for (int32 Dc = -1; Dc <= 1 && !bNear; ++Dc)
						bNear = Moved[FMath::Clamp(Rr + Dr, 0, SailRenderRows - 1) * SailRenderCols + FMath::Clamp(Rc + Dc, 0, SailRenderCols - 1)];
				if (!bNear) continue;
				FVector Nw = FdNormal(Pos, Rr, Rc), Ns = FdNormal(SmoothPos, Rr, Rc);
				if (Nw.IsNearlyZero() || Ns.IsNearlyZero()) continue;
				if (FVector::DotProduct(Ns, Normals[I]) < 0.f) { Nw = -Nw; Ns = -Ns; }
				Normals[I] = (Normals[I] + (Nw - Ns)).GetSafeNormal();
			}
		}
	}

	void RefineSail(const FSailCloth& Cloth, const TArray<FVector>& Normals, const TArray<FProcMeshTangent>& Tangents,
		TArray<FVector>& OutPos, TArray<FVector>& OutNormals, TArray<FProcMeshTangent>& OutTangents)
	{
		const int32 N = SailRenderRows * SailRenderCols;
		OutPos.SetNumUninitialized(N);
		OutNormals.SetNumUninitialized(N);
		OutTangents.SetNumUninitialized(N);
		const TArray<FVector>& P = Cloth.Positions();
		TArray<FVector> TanX;
		TanX.SetNumUninitialized(Tangents.Num());
		for (int32 I = 0; I < Tangents.Num(); ++I) TanX[I] = Tangents[I].TangentX;
		for (int32 Rr = 0; Rr < SailRenderRows; ++Rr)
		{
			for (int32 Rc = 0; Rc < SailRenderCols; ++Rc)
			{
				int32 R, C;
				float Tr, Tc;
				SailRenderCell(Rr, Rc, R, C, Tr, Tc);
				const int32 I = Rr * SailRenderCols + Rc;
				OutPos[I] = SailCubic(P, R, C, Tr, Tc);
				OutNormals[I] = SailBilinear(Normals, R, C, Tr, Tc).GetSafeNormal();
				OutTangents[I] = FProcMeshTangent(SailBilinear(TanX, R, C, Tr, Tc).GetSafeNormal(), Tangents[R * FSailCloth::Cols + C].bFlipTangentY);
			}
		}
	}

	template <typename T> void RefineSailUV(const TArray<T>& G, TArray<T>& Out)
	{
		Out.SetNumUninitialized(SailRenderRows * SailRenderCols);
		for (int32 Rr = 0; Rr < SailRenderRows; ++Rr)
		{
			for (int32 Rc = 0; Rc < SailRenderCols; ++Rc)
			{
				int32 R, C;
				float Tr, Tc;
				SailRenderCell(Rr, Rc, R, C, Tr, Tc);
				Out[Rr * SailRenderCols + Rc] = SailBilinear(G, R, C, Tr, Tc);
			}
		}
	}

	/** FSailCloth::Triangles' winding on the render grid (its front face to starboard: M_SailCloth's TwoSidedSign). */
	void SailRenderTriangles(TArray<int32>& Out)
	{
		Out.Reset();
		for (int32 R = 0; R < SailRenderRows - 1; ++R)
		{
			for (int32 C = 0; C < SailRenderCols - 1; ++C)
			{
				const int32 A = R * SailRenderCols + C, B = A + 1, D = A + SailRenderCols, E = D + 1;
				Out.Append({ A, D, B, B, D, E });
			}
		}
	}
}

void ASailboatPawn::UpdateSailCloth(UProceduralMeshComponent* Mesh, FSailCloth& Cloth, const FSailGeometry& Geo, ESailKind Kind,
	const FSailStripState* Strips, int32 Side, float DeltaSeconds)
{
	const FSailUpdate One{ Mesh, &Cloth, Strips, Side };
	UpdateSailCloths(MakeArrayView(&One, 1), DeltaSeconds);
}

void ASailboatPawn::UpdateSailCloths(TArrayView<const FSailUpdate> Sails, float DeltaSeconds)
{
	// docs/sail-parallel/: each sail's cloth step, normals, tangents and render grid touch only its own FSailCloth and the
	// inputs read here, so the sails run on the task graph side by side; only the meshes' updates stay on the game thread.
	// Run one after another on the game thread they cost about 1.2 ms a frame on the Mac (main, jib and spinnaker).
	FSailClothDrive Drive;
	Drive.DeltaSeconds = DeltaSeconds;
	Drive.Time = VisualTime;
	Drive.ApparentWindKnots = float(Boat.GetTelemetry().ApparentWindSpeed / kKnot);
	Drive.Cunningham = float(Controls.Cunningham);
	Drive.GravityBody = BoatRoot->GetComponentTransform().InverseTransformVectorNoScale(FVector(0.f, 0.f, -1.f));
	// Low draws the physics shape directly; Medium and High run the cloth (and traffic boats in the distance don't).
	Drive.bSimulate = USailingSettings::Get()->Quality != ESailingQuality::Low && !bTrafficBoat;
	// Drawn on the finer render grid (above); -SailingClassicSailGrid draws the cloth's own grid (compare).
	static SailingArgs::FCachedFlag ClassicGridArg(TEXT("SailingClassicSailGrid"));
	const bool bClassicGrid = ClassicGridArg.Get();
	// Ultra audit item 5: -SailingNoSailWrinkles draws the sails smooth (compare).
	static SailingArgs::FCachedFlag NoWrinklesArg(TEXT("SailingNoSailWrinkles"));
	// (High and Ultra: millimetre wrinkles are lost at Medium's resolution, and the frame there is the tightest.)
	const bool bNoWrinkles = NoWrinklesArg.Get() || USailingSettings::Get()->Quality < ESailingQuality::High;
	struct FWork { TArray<FVector> Normals, RPos, RNormals; TArray<FProcMeshTangent> Tangents, RTangents; };
	TArray<FWork, TInlineAllocator<3>> Work;
	Work.SetNum(Sails.Num());
	for (const FSailUpdate& U : Sails)
	{
		if (U.Cloth->IsValid()) U.Cloth->SetObstacles(bJibInsideShrouds && U.Cloth->GetKind() == ESailKind::Jib ? JibSailObstacles : SailObstacles);
	}
	const double Start = FPlatformTime::Seconds();
	ParallelFor(Sails.Num(), [&](int32 K)
	{
		const FSailUpdate& U = Sails[K];
		FSailCloth& Cloth = *U.Cloth;
		if (!Cloth.IsValid()) return;
		FWork& W = Work[K];
		Cloth.Step(U.Strips, U.Side, Drive);
		Cloth.ComputeNormals(W.Normals);
		Cloth.ComputeTangents(W.Tangents);
		if (!bClassicGrid)
		{
			RefineSail(Cloth, W.Normals, W.Tangents, W.RPos, W.RNormals, W.RTangents);
			if (!bNoWrinkles) WrinkleSail(Cloth, SailWrinklesFor(Cloth, U.Strips, Drive), W.RPos, W.RNormals);
		}
	});
	ClothCpuSeconds += FPlatformTime::Seconds() - Start;
	for (int32 K = 0; K < Sails.Num(); ++K)
	{
		UProceduralMeshComponent* Mesh = Sails[K].Mesh;
		const FSailCloth& Cloth = *Sails[K].Cloth;
		if (!Cloth.IsValid()) continue;
		FWork& W = Work[K];
		if (bClassicGrid)
		{
			if (Mesh->GetNumSections() == 0)
			{
				TArray<int32> Tris;
				Cloth.Triangles(Tris);
				Mesh->CreateMeshSection(0, Cloth.Positions(), Tris, W.Normals, Cloth.UV0(), Cloth.UV1(), Cloth.UV2(), TArray<FVector2D>(), TArray<FColor>(), W.Tangents, false);
			}
			else
			{
				Mesh->UpdateMeshSection(0, Cloth.Positions(), W.Normals, TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FColor>(), W.Tangents);
			}
			continue;
		}
		if (Mesh->GetNumSections() == 0)
		{
			TArray<int32> Tris;
			SailRenderTriangles(Tris);
			TArray<FVector2D> UV0, UV1, UV2;
			RefineSailUV(Cloth.UV0(), UV0);
			RefineSailUV(Cloth.UV1(), UV1);
			RefineSailUV(Cloth.UV2(), UV2);
			Mesh->CreateMeshSection(0, W.RPos, Tris, W.RNormals, UV0, UV1, UV2, TArray<FVector2D>(), TArray<FColor>(), W.RTangents, false);
		}
		else
		{
			// Perf 1 fix 3: the section is updated in place (same topology); the UVs never change after it was made, so only
			// positions, normals and tangents go across.
			Mesh->UpdateMeshSection(0, W.RPos, W.RNormals, TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FVector2D>(), TArray<FColor>(), W.RTangents);
		}
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
	// pc/cloud-mast-specks (docs/mast-specks): each ribbon is turned to face the camera about its length and kept at least
	// kMinTelltalePx across, as the rig lines are (docs/rig-lines). A 1.2 cm ribbon seen edge-on, or from the cockpit at the
	// leech 7 m away, fell under a pixel and broke into the dark-red specks along the mast's edge (Ultra audit follow-up).
	constexpr float kMinTelltalePx = 1.2f;
	FVector Eye = FVector::ZeroVector;
	float PxAngle = 0.f;
	const APlayerController* ViewPC = GetWorld()->GetFirstPlayerController();
	if (ViewPC && ViewPC->PlayerCameraManager && GEngine && GEngine->GameViewport)
	{
		FVector2D ViewSize;
		GEngine->GameViewport->GetViewportSize(ViewSize);
		PxAngle = 2.f * FMath::Tan(FMath::DegreesToRadians(ViewPC->PlayerCameraManager->GetFOVAngle() * 0.5f)) / FMath::Max(ViewSize.X, 1.0);
		Eye = BoatRoot->GetComponentTransform().InverseTransformPosition(ViewPC->PlayerCameraManager->GetCameraLocation());
	}
	TArray<FVector> Verts, Normals;
	TArray<FColor> Colors;
	TArray<int32> Tris;
	constexpr int32 Segs = 6;
	for (const FRibbon& R : Ribbons)
	{
		const FVector Flat = FVector::CrossProduct(R.Dir, R.Side).GetSafeNormal();
		const int32 Base = Verts.Num();
		for (int32 I = 0; I <= Segs; ++I)
		{
			const float S01 = float(I) / Segs;
			const FVector C = R.Root + R.Dir * (R.LengthCm * S01) + R.Side * (R.Wave * S01 * FMath::Sin(VisualTime * 22.f - S01 * 6.f + R.LengthCm));
			FVector Across = Flat * 0.6f;
			if (PxAngle > 0.f)
			{
				const FVector Facing = FVector::CrossProduct(R.Dir, C - Eye).GetSafeNormal();
				Across = (Facing.IsNearlyZero() ? Flat : Facing) * FMath::Max(0.6f, 0.5f * kMinTelltalePx * PxAngle * float(FVector::Dist(Eye, C)));
			}
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
