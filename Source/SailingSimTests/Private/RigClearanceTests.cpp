#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "CrewPose.h"
#include "SailboatPawn.h"
#include "SailCloth.h"
#include "WaterSurface.h"
#include "SailingSim.h"
#include "ProceduralMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/WorldSettings.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags RigClearanceFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** Flesh radius (cm) by bone name, as SailingSim.Visual.CrewHullClearance has it; -1 for bones not checked. */
	double FleshCm(const FString& Bone)
	{
		const FString B = Bone.ToLower();
		if (B.Contains(TEXT("twist")) || B.Contains(TEXT("corr")) || B.Contains(TEXT("ik_")) || B.Contains(TEXT("root"))) return -1.0;
		if (B.Contains(TEXT("bck")) || B.Contains(TEXT("_in")) || B.Contains(TEXT("_out")) || B.Contains(TEXT("_fwd")) || B.Contains(TEXT("knee"))) return -1.0;
		if (B.Contains(TEXT("tricep")) || B.Contains(TEXT("bicep")) || B.Contains(TEXT("latissimus")) || B.Contains(TEXT("pec")) || B.Contains(TEXT("scap"))) return -1.0;
		if (B.StartsWith(TEXT("pelvis")) || B.StartsWith(TEXT("spine"))) return 10.0;
		if (B.StartsWith(TEXT("neck"))) return 5.0;
		if (B == TEXT("head")) return 9.0;
		if (B.StartsWith(TEXT("thigh"))) return 7.0;
		if (B.StartsWith(TEXT("calf"))) return 4.5;
		if (B.StartsWith(TEXT("clavicle"))) return 5.0;
		if (B.StartsWith(TEXT("upperarm"))) return 4.5;
		if (B.StartsWith(TEXT("lowerarm"))) return 3.5;
		return -1.0;
	}

	/** A point on the line as drawn (its rings' centreline, sagged and draped over the boat). */
	FVector LinePoint(const ASailboatPawn::FRigLineSample& L, double U)
	{
		if (L.Points.Num() < 2) return FMath::Lerp(L.A, L.B, U);
		const double F = FMath::Clamp(U, 0.0, 1.0) * (L.Points.Num() - 1);
		const int32 I = FMath::Min(int32(F), L.Points.Num() - 2);
		return FMath::Lerp(L.Points[I], L.Points[I + 1], F - I);
	}

	/** Segment against triangle (Moller-Trumbore): the hit's fraction along P0->P1, or -1. */
	double SegmentHitsTriangle(const FVector& P0, const FVector& P1, const FVector& V0, const FVector& V1, const FVector& V2)
	{
		const FVector D = P1 - P0, E1 = V1 - V0, E2 = V2 - V0;
		const FVector H = FVector::CrossProduct(D, E2);
		const double A = FVector::DotProduct(E1, H);
		if (FMath::Abs(A) < 1e-9) return -1.0;
		const double F = 1.0 / A;
		const FVector S = P0 - V0;
		const double U = F * FVector::DotProduct(S, H);
		if (U < 0.0 || U > 1.0) return -1.0;
		const FVector Q = FVector::CrossProduct(S, E1);
		const double V = F * FVector::DotProduct(D, Q);
		if (V < 0.0 || U + V > 1.0) return -1.0;
		const double T = F * FVector::DotProduct(E2, Q);
		return T >= 0.0 && T <= 1.0 ? T : -1.0;
	}

	/** How deep a point (boat frame, cm) is inside the solid boat: the shortest way out along the six axes, up to 30 cm. */
	double DepthInBoat(const Sailing::FBoatConfig& Cfg, double HullDepth, const FVector& P, bool bBridge)
	{
		if (!CrewInsideBoat(Cfg, HullDepth, P / Sailing::CmPerMeter, bBridge)) return 0.0;
		double Best = 30.0;
		for (const FVector& Dir : { FVector(0, 0, 1), FVector(0, 0, -1), FVector(0, 1, 0), FVector(0, -1, 0), FVector(1, 0, 0), FVector(-1, 0, 0) })
		{
			for (double S = 0.5; S < Best; S += 0.5)
			{
				if (!CrewInsideBoat(Cfg, HullDepth, (P + Dir * S) / Sailing::CmPerMeter, bBridge)) { Best = S; break; }
			}
		}
		return Best;
	}
}

/**
 * The sheets and rig lines against the boat, the crew and the sails (Bean's clipping list, job 3): every boat of the fleet
 * held on both tacks close-hauled, reaching and running, in a light and a fresh breeze, the autopilot steering and the
 * trim assist trimming. Each drawn line (UpdateModelRig, recorded by HoldForTests) is sampled along its sagged curve and
 * checked against the solid boat (CrewInsideBoat: hull, deck, cabin trunk, cockpit), the lifelines (the boats that carry
 * them), the crew's flesh (bone segments with CrewHullClearance's radii) and the sails' cloth (passing through a
 * triangle); the shrouds and spreaders against the sails. Within a few centimetres of a line's ends (its fittings, a hand
 * holding it, the clew) it is not checked.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualRigClearanceTest, "SailingSim.Visual.RigClearance", RigClearanceFlags)
bool FVisualRigClearanceTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingRigClearanceWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, 0.f), FRotator::ZeroRotator);
	ASailboatPawn* Pawn = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("Boat spawns"), Pawn))
	{
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
		return false;
	}
	auto Tick = [&](int32 Frames)
	{
		for (int32 F = 0; F < Frames; ++F)
		{
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 30.f);
		}
	};

	struct FCase { double Twa, Knots; const TCHAR* Name; };
	const FCase Cases[] = {
		{ 45.0, 7.0, TEXT("close-hauled, starboard tack, light") }, { -45.0, 7.0, TEXT("close-hauled, port tack, light") },
		{ 45.0, 16.0, TEXT("close-hauled, starboard tack, fresh") }, { -45.0, 16.0, TEXT("close-hauled, port tack, fresh") },
		{ 95.0, 12.0, TEXT("reaching, starboard tack") }, { -95.0, 12.0, TEXT("reaching, port tack") },
		{ 160.0, 12.0, TEXT("running, starboard gybe") }, { -160.0, 12.0, TEXT("running, port gybe") } };

	TMap<FString, int32> Found;   // "boat: what" -> samples
	TMap<FString, FString> Where; // the first of each
	int32 Checked = 0;
	auto Note = [&](const FString& Key, const FString& Detail)
	{
		int32& N = Found.FindOrAdd(Key);
		if (N++ == 0) Where.Add(Key, Detail);
	};
	// What fails (the rest is listed: lines lying on a surface or pressed under a limb within a couple of centimetres, the
	// main's cloth wrapping the mast at its luff):
	//  - a shroud led across the boat to the other side's spreader (the Corsair's floats were swapped),
	//  - a rope more than 10 cm into the solid boat away from its fittings (a sheet through a cabin trunk or coachroof),
	//  - a wire through the jib's cloth away from its luff and head, in 3 samples or more (8 cases x 4 samples),
	//  - the mainsheet's tackle through a sailor (eased square it swept the helm's back: the crew sit to windward running).
	TMap<FString, int32> Fails;

	for (int32 Type = 0; Type < int32(EBoatType::Count); ++Type)
	{
		Pawn->SetBoat(Type);
		Tick(2);
		const FBoatConfig& Cfg = Pawn->GetBoatModel().GetConfig();
		const double HullDepth = Pawn->GetBoatModel().HullDepth();
		const bool bBridge = Pawn->HasModelTravelerBridge();
		const FString BoatName = ANSI_TO_TCHAR(BoatTypeName(Cfg.Type));
		const bool bLifelines = CrewHasLifelines(Cfg);
		for (const FCase& C : Cases)
		{
			Pawn->HoldForTests(C.Twa, C.Knots);
			Tick(8 * 30);
			for (int32 Sample = 0; Sample < 4; ++Sample)
			{
				Tick(15);
				const FTransform Root = Pawn->BoatRoot->GetComponentTransform();
				const FBoatTelemetry& Tel = Pawn->GetBoatModel().GetTelemetry();
				const FString CaseState = FString::Printf(TEXT("%s (heel %.0f, TWA %.0f, boom %.0f)"), C.Name, FMath::RadiansToDegrees(Tel.Heel), FMath::RadiansToDegrees(Tel.TrueWindAngle), FMath::RadiansToDegrees(Pawn->GetBoatModel().GetState().BoomAngle));

				// The crew's flesh: bone segments in the boat frame.
				struct FBoneSeg { FVector A, B; double R; FString Name; int32 Crew; };
				TArray<FBoneSeg> Bones;
				TArray<FVector> Hands;
				const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew = Pawn->GetCrewMeshes();
				for (int32 I = 0; I < Crew.Num(); ++I)
				{
					const USkeletalMeshComponent* M = Crew[I];
					if (!M || !M->IsVisible() || !M->GetSkeletalMeshAsset()) continue;
					const FReferenceSkeleton& Ref = M->GetSkeletalMeshAsset()->GetRefSkeleton();
					for (int32 B = 1; B < Ref.GetNum(); ++B)
					{
						const FString Bone = Ref.GetBoneName(B).ToString();
						if (Bone == TEXT("hand_l") || Bone == TEXT("hand_r")) Hands.Add(Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(B), EBoneSpaces::WorldSpace)));
						const double R = FleshCm(Bone);
						const int32 Parent = Ref.GetParentIndex(B);
						if (R < 0.0 || Parent < 0 || FleshCm(Ref.GetBoneName(Parent).ToString()) < 0.0) continue;
						Bones.Add({ Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(Parent), EBoneSpaces::WorldSpace)),
							Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(B), EBoneSpaces::WorldSpace)), R, Bone, I });
					}
				}
				// The sails' cloth: triangles in the boat frame.
				struct FSailTris { TArray<FVector> V; TArray<uint32> I; const TCHAR* Name; };
				TArray<FSailTris> Sails;
				for (int32 K = 0; K < 3; ++K)
				{
					UProceduralMeshComponent* Mesh = const_cast<UProceduralMeshComponent*>(Pawn->GetSailMesh(K));
					if (!Mesh || !Mesh->IsVisible() || Mesh->GetNumSections() == 0) continue;
					const FProcMeshSection* Sec = Mesh->GetProcMeshSection(0);
					if (!Sec || !Sec->bSectionVisible || Sec->ProcIndexBuffer.Num() < 3) continue;
					FSailTris& S = Sails.AddDefaulted_GetRef();
					S.Name = K == 0 ? TEXT("main") : K == 1 ? TEXT("jib") : TEXT("spinnaker");
					const FTransform ToRoot = Mesh->GetComponentTransform().GetRelativeTransform(Root);
					for (const FProcMeshVertex& V : Sec->ProcVertexBuffer) S.V.Add(ToRoot.TransformPosition(V.Position));
					S.I = Sec->ProcIndexBuffer;
				}

				for (const ASailboatPawn::FRigLineSample& L : Pawn->GetRigLineSamples())
				{
					const FString What = L.Name;
					const FString State = FString::Printf(TEXT("%s; the line (%.0f, %.0f, %.0f) to (%.0f, %.0f, %.0f)"), *CaseState, L.A.X, L.A.Y, L.A.Z, L.B.X, L.B.Y, L.B.Z);
					const double Len = FVector::Dist(L.A, L.B);
					if (Len < 5.0) continue;
					const bool bSpreader = What == TEXT("spreader");
					if (What.Contains(TEXT("shroud")) && L.A.Y * L.B.Y < 0.0 && FMath::Min(FMath::Abs(L.A.Y), FMath::Abs(L.B.Y)) > 20.0)
					{
						Fails.FindOrAdd(FString::Printf(TEXT("%s: %s led across the boat, (%.0f, %.0f, %.0f) to (%.0f, %.0f, %.0f)"), *BoatName, *What,
							L.A.X, L.A.Y, L.A.Z, L.B.X, L.B.Y, L.B.Z))++;
					}
					const bool bHeld = What.Contains(TEXT("tail")) || What == TEXT("tiller extension") || What == TEXT("trapeze wire");
					constexpr int32 NumU = 24;
					// The line against the boat, the lifelines and the crew.
					for (int32 K = 1; K < NumU && !bSpreader; ++K)
					{
						const double U = double(K) / NumU;
						const FVector P = LinePoint(L, U);
						const double FromEnd = FMath::Min(U, 1.0 - U) * Len;
						if (FromEnd < FMath::Max(6.0, 4.0 * L.RadiusCm)) continue;
						++Checked;
						const double Depth = DepthInBoat(Cfg, HullDepth, P, bBridge);
						if (Depth > L.RadiusCm + 1.5)
						{
							Note(FString::Printf(TEXT("%s: %s inside the boat"), *BoatName, *What),
								FString::Printf(TEXT("%.1f cm deep at (%.0f, %.0f, %.0f) cm, %s"), Depth, P.X, P.Y, P.Z, *State));
							// Sails and sheets: the sheets are draped over the boat now (spans included); none goes through it.
							if (What.Contains(TEXT("sheet")))
							{
								const FString Key = FString::Printf(TEXT("%s: %s through the boat"), *BoatName, *What);
								if (!Fails.Contains(Key)) Where.Add(Key, FString::Printf(TEXT("%.1f cm at (%.0f, %.0f, %.0f) cm, %s"), Depth, P.X, P.Y, P.Z, *State));
								Fails.FindOrAdd(Key)++;
							}
							if (Depth > 10.0 && FromEnd > 40.0)
							{
								const FString Key = FString::Printf(TEXT("%s: %s more than 10 cm into the boat"), *BoatName, *What);
								if (!Fails.Contains(Key)) Where.Add(Key, FString::Printf(TEXT("%.0f cm at (%.0f, %.0f, %.0f) cm, %s"), Depth, P.X, P.Y, P.Z, *CaseState));
								Fails.FindOrAdd(Key)++;
							}
						}
						if (bLifelines)
						{
							const double Y = FMath::Abs(P.Y - Cfg.Hulls[0].CenterY * CmPerMeter);
							const double Fence = (Cfg.Hulls[0].DeckHalfBeam(P.X / CmPerMeter) - 0.05) * CmPerMeter;
							const double Deck = CrewFloorZ(Cfg, P.X / CmPerMeter, FMath::Sign(P.Y) * (Fence - 5.0) / CmPerMeter, bBridge) * CmPerMeter;
							const double Hgt = Cfg.Hulls[0].SheerZ < 0.9 ? 60.0 : 68.0;
							for (const double Wire : { 0.5 * Hgt, Hgt })
							{
								if (Deck > -1e6 && FMath::Abs(Y - Fence) < 1.0 + L.RadiusCm && FMath::Abs(P.Z - (Deck + Wire)) < 1.0 + L.RadiusCm)
								{
									Note(FString::Printf(TEXT("%s: %s through a lifeline"), *BoatName, *What),
										FString::Printf(TEXT("at (%.0f, %.0f, %.0f) cm, %s"), P.X, P.Y, P.Z, *State));
									const FString Key = FString::Printf(TEXT("%s: %s through a lifeline"), *BoatName, *What);
									if (!Fails.Contains(Key)) Where.Add(Key, FString::Printf(TEXT("at (%.0f, %.0f, %.0f) cm, %s"), P.X, P.Y, P.Z, *State));
									Fails.FindOrAdd(Key)++;
								}
							}
						}
						// Near a hand that holds it, the line is in the fist.
						bool bInHand = false;
						for (const FVector& H : Hands) bInHand |= bHeld && FVector::Dist(H, P) < 25.0;
						for (const FBoneSeg& B : Bones)
						{
							if (bInHand && B.Name.StartsWith(TEXT("lowerarm"))) continue;
							if (What == TEXT("trapeze wire") && FromEnd < 40.0 && U > 0.5) continue; // the hook at the harness
							const FVector Closest = FMath::ClosestPointOnSegment(P, B.A, B.B);
							const double Gap = FVector::Dist(Closest, P) - B.R - L.RadiusCm;
							if (Gap < -2.0)
							{
								Note(FString::Printf(TEXT("%s: %s through crew %d's %s"), *BoatName, *What, B.Crew, *B.Name),
									FString::Printf(TEXT("%.1f cm into the flesh at (%.0f, %.0f, %.0f) cm, %s"), -Gap, P.X, P.Y, P.Z, *State));
								// Every sheet lies on the crew's legs and arms now, not through them (the tiller extension, rigid in
								// the helm's hand, is the crew pose's to keep clear).
								if (What.Contains(TEXT("sheet")))
								{
									const FString Key = FString::Printf(TEXT("%s: the %s through the crew"), *BoatName, *What);
									if (!Fails.Contains(Key)) Where.Add(Key, FString::Printf(TEXT("crew %d's %s, %.1f cm, %s"), B.Crew, *B.Name, -Gap, *State));
									Fails.FindOrAdd(Key)++;
								}
							}
						}
					}
					// The line through the sails' cloth (not where it meets the sail: the clew, the sheet's end on it).
					for (const FSailTris& S : Sails)
					{
						const bool bSheetOf = (What.Contains(TEXT("jib")) && FCString::Strcmp(S.Name, TEXT("jib")) == 0)
							|| (What.Contains(TEXT("mainsheet")) && FCString::Strcmp(S.Name, TEXT("main")) == 0)
							|| (What == TEXT("forestay") && FCString::Strcmp(S.Name, TEXT("jib")) == 0);
						for (int32 K = 0; K < NumU; ++K)
						{
							const double U0 = double(K) / NumU, U1 = double(K + 1) / NumU;
							const FVector P0 = LinePoint(L, U0), P1 = LinePoint(L, U1);
							bool bHit = false;
							for (int32 T = 0; T + 2 < S.I.Num() && !bHit; T += 3)
							{
								const double H = SegmentHitsTriangle(P0, P1, S.V[S.I[T]], S.V[S.I[T + 1]], S.V[S.I[T + 2]]);
								if (H < 0.0) continue;
								const double U = FMath::Lerp(U0, U1, H);
								const double FromEnd = FMath::Min(U, 1.0 - U) * Len;
								// (a wire's last 12 cm at the mast or the deck: the sail meets the spar there, FSailCloth::KeepClear)
								if (FromEnd < (bSheetOf ? 25.0 : L.Sag.IsZero() || What.Contains(TEXT("shroud")) || What == TEXT("trapeze wire") ? 12.0 : 4.0)) continue;
								if (bSheetOf && What == TEXT("forestay")) continue; // the jib's luff is on the forestay
								bHit = true;
								const FVector P = FMath::Lerp(P0, P1, H);
								const int32 Row = int32(S.I[T]) / FSailCloth::Cols, Col = int32(S.I[T]) % FSailCloth::Cols;
								Note(FString::Printf(TEXT("%s: %s through the %s"), *BoatName, *What, S.Name),
									FString::Printf(TEXT("at (%.0f, %.0f, %.0f) cm (cloth row %d, column %d), %s"), P.X, P.Y, P.Z, Row, Col, *State));
								// (The jib's: a running main eased onto its shrouds and spreaders is turned in only a sheet's few degrees,
								// FSailCloth::KeepClear, and where its belly presses on a wire near the mast the wire still shows through:
								// listed, not failed.)
								if (FCString::Strcmp(S.Name, TEXT("jib")) == 0 && Col >= 4 && Row < FSailCloth::Rows - 5)
								{
									const FString Key = FString::Printf(TEXT("%s: %s through the %s's cloth"), *BoatName, *What, S.Name);
									if (!Fails.Contains(Key)) Where.Add(Key, FString::Printf(TEXT("at (%.0f, %.0f, %.0f) cm, row %d, column %d, %s"), P.X, P.Y, P.Z, Row, Col, *State));
									Fails.FindOrAdd(Key)++;
								}
							}
							if (bHit) break;
						}
					}
				}
			}
		}
	}
	Found.KeySort([](const FString& A, const FString& B) { return A < B; });
	for (const TPair<FString, int32>& F : Found)
	{
		AddInfo(FString::Printf(TEXT("%s: %d samples; first %s"), *F.Key, F.Value, *Where[F.Key]));
	}
	AddInfo(FString::Printf(TEXT("%d line points checked; %d kinds of clip"), Checked, Found.Num()));
	for (const TPair<FString, int32>& F : Fails)
	{
		if (F.Key.EndsWith(TEXT("'s cloth")) && F.Value < 3) continue;
		AddError(FString::Printf(TEXT("%s (%d samples)%s"), *F.Key, F.Value, Where.Contains(F.Key) ? *(TEXT("; first ") + Where[F.Key]) : TEXT("")));
	}

	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

/**
 * The J/22's trimmer tails the jib sheet in light air on both tacks (the PC, Ultra, on main 9bbf9a30: after the crew were
 * spaced apart the trimmer sat out of reach of the leeward self-tailer and both hands went to the knees). 4 kn, close
 * reaching at 50 degrees each way, the autopilot and trim assist sailing her: in every sample the working sheet's tail is
 * in the trimmer's hand.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualTrimmerTailsJibTest, "SailingSim.Visual.TrimmerTailsJib", RigClearanceFlags)
bool FVisualTrimmerTailsJibTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingTrimmerWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, 0.f), FRotator::ZeroRotator);
	ASailboatPawn* Pawn = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (TestNotNull(TEXT("Boat spawns"), Pawn))
	{
		Pawn->SetBoat(int32(Sailing::EBoatType::J22));
		for (const double Twa : { 50.0, -50.0 })
		{
			Pawn->HoldForTests(Twa, 4.0);
			int32 Held = 0;
			for (int32 Frame = 0; Frame < 10 * 30; ++Frame)
			{
				++GFrameCounter;
				World->Tick(LEVELTICK_All, 1.f / 30.f);
				if (Frame >= 6 * 30 && Frame % 15 == 0) Held += Pawn->IsJibTailHeld() ? 1 : 0;
			}
			TestEqual(FString::Printf(TEXT("Light air, TWA %.0f: the trimmer holds the jib tail (samples of 8)"), Twa), Held, 8);
		}
	}
	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

/**
 * The running lines' audit (the sheets' job): every boat's sheets, their tails and the vang, on the eight points of sail
 * RigClearance holds and through a tack and a gybe (sampled every third of a second while the autopilot turns her), against
 * the solid boat (hull, deck, cabin trunk, cockpit: CrewInsideBoat), the lifelines, the crew's flesh, the standing rig
 * (shrouds, stays, spreaders, the trapeze wire) and the mast. Within a few centimetres of a line's ends (its block, the
 * clew, a hand holding it) it is not checked. Everything found is listed; what fails:
 *  - a sheet more than 10 cm into the solid boat away from its fittings,
 *  - a sheet through a wire or the mast (closer than their radii, by more than 1 cm) away from both its ends,
 *  - a sheet more than 4 cm into a sailor away from a hand holding it and off the deck (a line on the deck or the cockpit
 *    floor under a sailor is sat or lain on: the maxi's crew on a lazy sheet),
 * each in more than 2 samples of a boat.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSheetClearanceTest, "SailingSim.Visual.SheetClearance", RigClearanceFlags)
bool FVisualSheetClearanceTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingSheetClearanceWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	World->SpawnActor<AWaterSurface>(FVector(0.f, 0.f, 0.f), FRotator::ZeroRotator);
	ASailboatPawn* Pawn = World->SpawnActor<ASailboatPawn>(FVector(1000.f, 0.f, 0.f), FRotator(0.f, 90.f, 0.f));
	if (!TestNotNull(TEXT("Boat spawns"), Pawn))
	{
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
		return false;
	}
	auto Tick = [&](int32 Frames)
	{
		for (int32 F = 0; F < Frames; ++F)
		{
			++GFrameCounter;
			World->Tick(LEVELTICK_All, 1.f / 30.f);
		}
	};
	auto IsRunning = [](const FString& What) { return What.Contains(TEXT("sheet")) || What == TEXT("vang"); };

	TMap<FString, int32> Found, Fails;
	TMap<FString, FString> Where;
	int32 Checked = 0;
	auto Note = [&](TMap<FString, int32>& Map, const FString& Key, const FString& Detail)
	{
		int32& N = Map.FindOrAdd(Key);
		if (N++ == 0 && !Where.Contains(Key)) Where.Add(Key, Detail);
	};

	for (int32 Type = 0; Type < int32(EBoatType::Count); ++Type)
	{
		Pawn->SetBoat(Type);
		Tick(2);
		const FBoatConfig& Cfg = Pawn->GetBoatModel().GetConfig();
		const double HullDepth = Pawn->GetBoatModel().HullDepth();
		const bool bBridge = Pawn->HasModelTravelerBridge();
		const bool bLifelines = CrewHasLifelines(Cfg);
		const FString BoatName = ANSI_TO_TCHAR(BoatTypeName(Cfg.Type));

		auto Check = [&](const FString& State)
		{
			const FTransform Root = Pawn->BoatRoot->GetComponentTransform();
			struct FBoneSeg { FVector A, B; double R; FString Name; int32 Crew; };
			TArray<FBoneSeg> Bones;
			TArray<FVector> Hands;
			const TArray<TObjectPtr<USkeletalMeshComponent>>& Crew = Pawn->GetCrewMeshes();
			for (int32 I = 0; I < Crew.Num(); ++I)
			{
				const USkeletalMeshComponent* M = Crew[I];
				if (!M || !M->IsVisible() || !M->GetSkeletalMeshAsset()) continue;
				const FReferenceSkeleton& Ref = M->GetSkeletalMeshAsset()->GetRefSkeleton();
				for (int32 B = 1; B < Ref.GetNum(); ++B)
				{
					const FString Bone = Ref.GetBoneName(B).ToString();
					if (Bone == TEXT("hand_l") || Bone == TEXT("hand_r")) Hands.Add(Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(B), EBoneSpaces::WorldSpace)));
					const double R = FleshCm(Bone);
					const int32 Parent = Ref.GetParentIndex(B);
					if (R < 0.0 || Parent < 0 || FleshCm(Ref.GetBoneName(Parent).ToString()) < 0.0) continue;
					Bones.Add({ Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(Parent), EBoneSpaces::WorldSpace)),
						Root.InverseTransformPosition(M->GetBoneLocation(Ref.GetBoneName(B), EBoneSpaces::WorldSpace)), R, Bone, I });
				}
			}
			// The standing rig the sheets mustn't pass through, and the mast (its foot at the deck to its head).
			struct FWire { FVector A, B; double R; FString Name; };
			TArray<FWire> Wires;
			for (const ASailboatPawn::FRigLineSample& L : Pawn->GetRigLineSamples())
			{
				const FString What = L.Name;
				if (!IsRunning(What) && What != TEXT("tiller extension")) Wires.Add({ L.A, L.B, L.RadiusCm, What });
			}
			Wires.Add({ FVector(Cfg.MastX, 0.0, Cfg.Hulls[0].SheerZ) * CmPerMeter, FVector(Cfg.MastX, 0.0, Cfg.MastheadZ) * CmPerMeter, 0.5 * Cfg.MastDiameter * CmPerMeter, TEXT("mast") });
			for (const ASailboatPawn::FRigLineSample& L : Pawn->GetRigLineSamples())
			{
				const FString What = L.Name;
				if (!IsRunning(What)) continue;
				const double Len = FVector::Dist(L.A, L.B);
				if (Len < 5.0) continue;
				const bool bHeld = What.Contains(TEXT("tail"));
				const FString At = FString::Printf(TEXT("%s; the line (%.0f, %.0f, %.0f) to (%.0f, %.0f, %.0f)"), *State, L.A.X, L.A.Y, L.A.Z, L.B.X, L.B.Y, L.B.Z);
				constexpr int32 NumU = 32;
				for (int32 K = 1; K < NumU; ++K)
				{
					const double U = double(K) / NumU;
					const FVector P = LinePoint(L, U);
					const double FromEnd = FMath::Min(U, 1.0 - U) * Len;
					if (FromEnd < FMath::Max(6.0, 4.0 * L.RadiusCm)) continue;
					++Checked;
					const double Depth = DepthInBoat(Cfg, HullDepth, P, bBridge);
					if (Depth > L.RadiusCm + 1.5)
					{
						Note(Found, FString::Printf(TEXT("%s: %s inside the boat"), *BoatName, *What), FString::Printf(TEXT("%.1f cm deep at (%.0f, %.0f, %.0f), %s"), Depth, P.X, P.Y, P.Z, *At));
						if (Depth > 10.0 && FromEnd > 40.0) Note(Fails, FString::Printf(TEXT("%s: %s more than 10 cm into the boat"), *BoatName, *What), FString::Printf(TEXT("%.0f cm at (%.0f, %.0f, %.0f), %s"), Depth, P.X, P.Y, P.Z, *At));
					}
					if (bLifelines)
					{
						const double Y = FMath::Abs(P.Y - Cfg.Hulls[0].CenterY * CmPerMeter);
						const double Fence = (Cfg.Hulls[0].DeckHalfBeam(P.X / CmPerMeter) - 0.05) * CmPerMeter;
						const double Deck = CrewFloorZ(Cfg, P.X / CmPerMeter, FMath::Sign(P.Y) * (Fence - 5.0) / CmPerMeter, bBridge) * CmPerMeter;
						const double Hgt = Cfg.Hulls[0].SheerZ < 0.9 ? 60.0 : 68.0;
						for (const double Wire : { 0.5 * Hgt, Hgt })
						{
							if (Deck > -1e6 && FMath::Abs(Y - Fence) < 1.0 + L.RadiusCm && FMath::Abs(P.Z - (Deck + Wire)) < 1.0 + L.RadiusCm)
							{
								Note(Found, FString::Printf(TEXT("%s: %s through a lifeline"), *BoatName, *What), FString::Printf(TEXT("at (%.0f, %.0f, %.0f), %s"), P.X, P.Y, P.Z, *At));
							}
						}
					}
					for (const FWire& W : Wires)
					{
						if (What == TEXT("vang") && W.Name == TEXT("mast")) continue; // its foot is on the mast
						const FVector C = FMath::ClosestPointOnSegment(P, W.A, W.B);
						const double Gap = FVector::Dist(C, P) - W.R - L.RadiusCm;
						const double WireEnd = FMath::Min(FVector::Dist(C, W.A), FVector::Dist(C, W.B));
						if (Gap < -1.0 && WireEnd > 8.0)
						{
							Note(Found, FString::Printf(TEXT("%s: %s through the %s"), *BoatName, *What, *W.Name), FString::Printf(TEXT("%.1f cm at (%.0f, %.0f, %.0f), %s"), -Gap, P.X, P.Y, P.Z, *At));
							if (FromEnd > 20.0) Note(Fails, FString::Printf(TEXT("%s: %s through the %s"), *BoatName, *What, *W.Name), FString::Printf(TEXT("%.1f cm at (%.0f, %.0f, %.0f), %s"), -Gap, P.X, P.Y, P.Z, *At));
						}
					}
					bool bInHand = false;
					for (const FVector& H : Hands) bInHand |= bHeld && FVector::Dist(H, P) < 25.0;
					// (A line lying on the deck or the cockpit floor under a sailor is sat or lain on: listed, not failed.)
					const bool bOnFloor = CrewInsideBoat(Cfg, HullDepth, (P - FVector(0.0, 0.0, L.RadiusCm + 4.0)) / CmPerMeter, bBridge);
					for (const FBoneSeg& B : Bones)
					{
						if (bInHand && B.Name.StartsWith(TEXT("lowerarm"))) continue;
						const FVector C = FMath::ClosestPointOnSegment(P, B.A, B.B);
						const double Gap = FVector::Dist(C, P) - B.R - L.RadiusCm;
						if (Gap < -2.0)
						{
							Note(Found, FString::Printf(TEXT("%s: %s through crew %d's %s"), *BoatName, *What, B.Crew, *B.Name), FString::Printf(TEXT("%.1f cm at (%.0f, %.0f, %.0f), %s"), -Gap, P.X, P.Y, P.Z, *At));
							if (Gap < -4.0 && !bInHand && !bOnFloor) Note(Fails, FString::Printf(TEXT("%s: %s through the crew"), *BoatName, *What), FString::Printf(TEXT("crew %d's %s, %.1f cm, %s"), B.Crew, *B.Name, -Gap, *At));
						}
					}
				}
			}
		};

		struct FCase { double Twa, Knots; const TCHAR* Name; };
		const FCase Cases[] = {
			{ 45.0, 7.0, TEXT("close-hauled, starboard tack, light") }, { -45.0, 7.0, TEXT("close-hauled, port tack, light") },
			{ 45.0, 16.0, TEXT("close-hauled, starboard tack, fresh") }, { -45.0, 16.0, TEXT("close-hauled, port tack, fresh") },
			{ 95.0, 12.0, TEXT("reaching, starboard tack") }, { -95.0, 12.0, TEXT("reaching, port tack") },
			{ 160.0, 12.0, TEXT("running, starboard gybe") }, { -160.0, 12.0, TEXT("running, port gybe") } };
		for (const FCase& C : Cases)
		{
			Pawn->HoldForTests(C.Twa, C.Knots);
			Tick(8 * 30);
			for (int32 Sample = 0; Sample < 3; ++Sample)
			{
				Tick(15);
				const FBoatTelemetry& Tel = Pawn->GetBoatModel().GetTelemetry();
				Check(FString::Printf(TEXT("%s (heel %.0f, TWA %.0f)"), C.Name, FMath::RadiansToDegrees(Tel.Heel), FMath::RadiansToDegrees(Tel.TrueWindAngle)));
			}
		}
		// Through a tack and a gybe: on the first heading 8 s, then the autopilot takes her to the other, sampled for 12 s.
		struct FTurn { double From, To; const TCHAR* Name; };
		for (const FTurn& T : { FTurn{ 45.0, -45.0, TEXT("tacking") }, FTurn{ 150.0, -150.0, TEXT("gybing") } })
		{
			Pawn->HoldForTests(T.From, 12.0);
			Tick(8 * 30);
			Pawn->RetargetForTests(T.To);
			for (int32 Sample = 0; Sample < 36; ++Sample)
			{
				Tick(10);
				const FBoatTelemetry& Tel = Pawn->GetBoatModel().GetTelemetry();
				Check(FString::Printf(TEXT("%s, %.1f s in (heel %.0f, TWA %.0f, boom %.0f)"), T.Name, (Sample + 1) / 3.0, FMath::RadiansToDegrees(Tel.Heel),
					FMath::RadiansToDegrees(Tel.TrueWindAngle), FMath::RadiansToDegrees(Pawn->GetBoatModel().GetState().BoomAngle)));
			}
		}
	}
	Found.KeySort([](const FString& A, const FString& B) { return A < B; });
	for (const TPair<FString, int32>& F : Found) AddInfo(FString::Printf(TEXT("%s: %d samples; first %s"), *F.Key, F.Value, *Where[F.Key]));
	AddInfo(FString::Printf(TEXT("%d sheet points checked; %d kinds of contact"), Checked, Found.Num()));
	for (const TPair<FString, int32>& F : Fails)
	{
		if (F.Value <= 2) continue;
		AddError(FString::Printf(TEXT("%s (%d samples); first %s"), *F.Key, F.Value, Where.Contains(F.Key) ? *Where[F.Key] : TEXT("")));
	}

	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
