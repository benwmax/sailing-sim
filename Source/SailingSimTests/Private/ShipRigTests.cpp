#include "Misc/AutomationTest.h"
#include "ShipRig.h"

#include <cmath>

#if WITH_DEV_AUTOMATION_TESTS

/**
 * The ship's rig on the model (docs/ship-rig/): the frigate's table of moving spars and sails; a spar's motion (turned
 * the model's way, eased forward, lowered along its mast); the pose from the physics (yards at the physics' angles within
 * the rigging's limits, a topsail clewed up then its yard lowered and the sail furled, fore-and-aft sails mirrored on the
 * starboard tack, the spanker's boom and gaff with the main boom).
 */
namespace ShipRigTestsLocal
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double DegRad = 3.14159265358979323846 / 180.0;

	bool Near(const Sailing::Vec3& A, const Sailing::Vec3& B, double Tol) { return (A - B).Length() <= Tol; }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipRigTableTest, "SailingSim.ShipRig.Table", ShipRigTestsLocal::TestFlags)
bool FShipRigTableTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FShipRigData* RigP = ShipRigFor("Commonwealth");
	TestNotNull(TEXT("the frigate has a rig"), RigP);
	TestNull(TEXT("a J/22 has none"), ShipRigFor("J/22"));
	if (!RigP) return false;
	const FShipRigData& Rig = *RigP;
	TestEqual(TEXT("fifteen moving spars"), Rig.NumSpars, 15);
	TestEqual(TEXT("twenty sails"), Rig.NumSails, 20);
	int32 SquareSeen = 0;
	for (int32 K = 0; K < Rig.NumSails; ++K)
	{
		const FRigSail& S = Rig.Sails[K];
		TestTrue(FString::Printf(TEXT("sail %d has its objects"), K), *S.Set && *S.Clewed && *S.Furled);
		TestTrue(FString::Printf(TEXT("sail %d rides on a spar or the ship"), K), S.Spar >= -1 && S.Spar < Rig.NumSpars);
		if (S.Kind == ERigSailKind::Square)
		{
			TestTrue(FString::Printf(TEXT("square sail %d in the physics' order"), K), S.Square == K && S.Spar >= 0 && *S.Head);
			TestEqual(FString::Printf(TEXT("square sail %d's yard turns with it"), K), Rig.Spars[S.Spar].Square, S.Square);
			++SquareSeen;
		}
		else
		{
			TestTrue(FString::Printf(TEXT("fore-and-aft sail %d mirrors on the starboard tack"), K), S.bMirror && S.Square == -1);
		}
	}
	TestEqual(TEXT("eleven square sails"), SquareSeen, 11);
	const int32 Crossjack = Rig.SparNamed("Yard_Crossjack");
	TestTrue(TEXT("the crossjack braces with the mizzen topsail"), Crossjack >= 0 && Rig.Spars[Crossjack].Square == Rig.SailNamed("mizzen_topsail"));
	TestTrue(TEXT("the spanker rides the gaff"), Rig.Sails[Rig.SailNamed("spanker")].Spar == Rig.SparNamed("SpankerGaff"));
	const int32 Sprit = Rig.SparNamed("Yard_Spritsail");
	TestTrue(TEXT("the spritsail yard stays put"), Sprit >= 0 && Rig.Spars[Sprit].Drive == ERigSparDrive::Fixed);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipRigMotionTest, "SailingSim.ShipRig.Motion", ShipRigTestsLocal::TestFlags)
bool FShipRigMotionTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using ShipRigTestsLocal::Near;
	const FShipRigData& Rig = CommonwealthRig();
	const FRigSpar& Fore = Rig.Spars[Rig.SparNamed("Yard_Fore")];
	const FRigMotion Rest = RigSparMotion(Fore, 1.0, 0.0, 0.0);
	TestTrue(TEXT("at rest nothing moves"), Near(Rest.Apply({ 25.0, 10.0, 19.0 }), { 25.0, 10.0, 19.0 }, 1e-9));
	const FRigMotion Turned = RigSparMotion(Fore, 1.0, 0.0, 30.0);
	const Vec3 Arm = Turned.Apply(Fore.Origin + Vec3(0.0, 10.0, 0.0));
	TestTrue(TEXT("a positive turn swings the starboard arm aft"), Arm.X < Fore.Origin.X - 4.9 && Arm.Y > 8.6);
	TestTrue(TEXT("the yard's pivot stays"), Near(Turned.Apply(Fore.Origin), Fore.Origin, 1e-9));
	TestTrue(TEXT("a turn is rigid"), std::fabs(Turned.Determinant() - 1.0) < 1e-9);
	const FRigMotion Eased = RigSparMotion(Fore, 1.0, 0.5, 0.0);
	TestTrue(TEXT("the ease brings it forward"), Eased.Apply(Fore.Origin).X > Fore.Origin.X + 0.49);

	const FRigSpar& Topsail = Rig.Spars[Rig.SparNamed("Yard_ForeTopsail")];
	const FRigMotion Lowered = RigSparMotion(Topsail, 0.0, 0.0, 0.0);
	TestTrue(TEXT("lowered, the topsail yard comes down its mast"), std::fabs(Lowered.Apply(Topsail.Origin).Z - (Topsail.Origin.Z + Topsail.Axis.Z * Topsail.HoistLowered)) < 1e-6
		&& Topsail.HoistLowered < -9.0);
	double Lo = 0.0, Hi = 0.0;
	RigBraceLimits(Rig, Rig.SparNamed("Yard_ForeTopsail"), 0.0, -1, Lo, Hi);
	const auto& Rows = Topsail.BraceByHoist;
	TestTrue(TEXT("the topsail yard's limits by hoist"), Topsail.NumBraceByHoist == 5 && Rows[2][0] == 0.5 && Rows[3][0] == 0.75);
	TestTrue(TEXT("lowered it braces only a little"), Lo == Rows[0][1] && Hi == Rows[0][2] && Hi < 0.5 * Topsail.BraceHi);
	RigBraceLimits(Rig, Rig.SparNamed("Yard_ForeTopsail"), 0.6, -1, Lo, Hi);
	TestTrue(TEXT("between two hoists, the narrower"), Lo == FMath::Max(Rows[2][1], Rows[3][1]) && Hi == FMath::Min(Rows[2][2], Rows[3][2]));

	const FRigSail& Jib = Rig.Sails[Rig.SailNamed("jib")];
	const FRigMotion Mirror = RigSailMirror(Jib);
	TestTrue(TEXT("a mirror turns the cloth over"), std::fabs(Mirror.Determinant() + 1.0) < 1e-9);
	TestTrue(TEXT("the stay stays"), Near(Mirror.Apply(Jib.MirrorPoint), Jib.MirrorPoint, 1e-9));
	const Vec3 Off = Jib.MirrorPoint + Jib.MirrorNormal * 2.0;
	TestTrue(TEXT("the clew goes to the other side"), Near(Mirror.Apply(Off), Jib.MirrorPoint - Jib.MirrorNormal * 2.0, 1e-9));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipRigPoseTest, "SailingSim.ShipRig.Pose", ShipRigTestsLocal::TestFlags)
bool FShipRigPoseTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using ShipRigTestsLocal::DegRad;
	const FShipRigData& Rig = CommonwealthRig();
	const int32 Fore = Rig.SparNamed("Yard_Fore");
	const int32 ForeTop = Rig.SparNamed("Yard_ForeTopsail");
	const int32 ForeTopSail = Rig.SailNamed("fore_topsail");
	FShipRigPose P;
	P.Reset(Rig);
	FShipRigInput In;
	for (int32 K = 0; K < kMaxRigSquare; ++K) In.SquareOut[K] = 1.0;
	In.YardAngle[0] = 20.0 * DegRad;
	P.Update(Rig, In, 0.1);
	TestEqual(TEXT("the yard at the physics' angle, the model's way"), P.GetTurnDeg(Fore), -20.0, 1e-9);
	TestEqual(TEXT("eased forward as it braces"), P.GetEase(Fore), 0.5461, 1e-9);
	In.YardAngle[0] = 50.0 * DegRad;
	P.Update(Rig, In, 0.1);
	TestEqual(TEXT("never through the rigging"), P.GetTurnDeg(Fore), -33.5, 1e-9);
	TestTrue(TEXT("all set"), P.GetShown(0) == ESailShown::Set && P.GetShown(ForeTopSail) == ESailShown::Set);

	// Furl the fore topsail: clewed up, then the yard lowered square, then furled on it.
	In.YardAngle[1] = 25.0 * DegRad;
	In.SquareOut[1] = 0.3;
	In.bSquareFurl[1] = true;
	P.Update(Rig, In, 0.1);
	TestTrue(TEXT("clewing up"), P.GetShown(ForeTopSail) == ESailShown::Clewed && P.GetHoist(ForeTop) == 1.0);
	In.SquareOut[1] = 0.0;
	P.Update(Rig, In, 1.0);
	TestTrue(TEXT("clewed up, the yard comes down"), P.GetShown(ForeTopSail) == ESailShown::Clewed && P.GetHoist(ForeTop) < 1.0);
	for (int32 K = 0; K < 40; ++K) P.Update(Rig, In, 1.0);
	TestTrue(TEXT("lowered and furled"), P.GetHoist(ForeTop) == 0.0 && P.GetShown(ForeTopSail) == ESailShown::Furled);
	TestEqual(TEXT("lowered, braced only to its lowered limit"), P.GetTurnDeg(ForeTop), Rig.Spars[ForeTop].BraceByHoist[0][1], 1e-9);
	In.bSquareFurl[1] = false;
	P.Update(Rig, In, 1.0);
	TestTrue(TEXT("loosed, she hoists it"), P.GetShown(ForeTopSail) == ESailShown::Clewed && P.GetHoist(ForeTop) > 0.0);

	// The headsails, staysails and spanker on the starboard tack; the boom and gaff with the main boom.
	const int32 Jib = Rig.SailNamed("jib");
	const int32 Spanker = Rig.SailNamed("spanker");
	const int32 Boom = Rig.SparNamed("SpankerBoom");
	TestFalse(TEXT("port tack: as modelled"), P.IsMirrored(Jib));
	In.JibSide = -1;
	In.MainSide = -1;
	In.BoomAngle = -0.3;
	P.Update(Rig, In, 0.1);
	TestTrue(TEXT("starboard tack: mirrored"), P.IsMirrored(Jib) && P.IsMirrored(Spanker));
	TestEqual(TEXT("the boom to port"), P.GetTurnDeg(Boom), 0.3 / DegRad, 1e-9);
	const FRigSpar& BoomSpar = Rig.Spars[Boom];
	TestTrue(TEXT("its end goes to port"), P.SparMotion(Rig, Boom).Apply(BoomSpar.Origin - Vec3(10.0, 0.0, 0.0)).Y < -2.0);
	TestTrue(TEXT("the spanker turns over with the gaff"), std::fabs(P.SailMotion(Rig, Spanker).Determinant() + 1.0) < 1e-9);
	In.JibOut = 0.2;
	P.Update(Rig, In, 0.1);
	TestTrue(TEXT("hauling down"), P.GetShown(Jib) == ESailShown::Clewed && !P.IsMirrored(Jib));
	In.JibOut = 0.0;
	P.Update(Rig, In, 0.1);
	TestTrue(TEXT("down"), P.GetShown(Jib) == ESailShown::Furled);
	return true;
}

#endif
