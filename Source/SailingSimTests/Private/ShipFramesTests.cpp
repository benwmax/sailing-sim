#include "Misc/AutomationTest.h"
#include "ShipFrames.h"

#include <cmath>

#if WITH_DEV_AUTOMATION_TESTS

/**
 * A ship's moving parts (docs/ship-frames/): the frigate's table (her frames, the tiller ropes' poses by the helm's
 * degree); the helm from the rudder and the wheel's turns; the tiller's swing, the rope parts following it (blended
 * between the table's degrees, the runs stretched along their own length); the cabin doors swinging aft for a walker and
 * closing after him; the pose over them all.
 */
namespace ShipFramesTestsLocal
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	bool Near(const Sailing::Vec3& A, const Sailing::Vec3& B, double Tol) { return (A - B).Length() <= Tol; }
	bool Unit(const Sailing::Vec3& A) { return std::fabs(A.Length() - 1.0) < 1e-4; }
	/** The motion moves nothing (within Tol) at and about P. */
	bool Still(const Sailing::FRigMotion& M, const Sailing::Vec3& P, double Tol)
	{
		return Near(M.Apply(P), P, Tol) && Near(M.Apply(P + Sailing::Vec3(1, 0, 0)), P + Sailing::Vec3(1, 0, 0), Tol)
			&& Near(M.Apply(P + Sailing::Vec3(0, 1, 0)), P + Sailing::Vec3(0, 1, 0), Tol) && Near(M.Apply(P + Sailing::Vec3(0, 0, 1)), P + Sailing::Vec3(0, 0, 1), Tol);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipFramesTableTest, "SailingSim.ShipFrames.Table", ShipFramesTestsLocal::TestFlags)
bool FShipFramesTableTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace ShipFramesTestsLocal;
	const FShipFramesData* DataP = ShipFramesFor("Commonwealth");
	TestNotNull(TEXT("the frigate has moving parts"), DataP);
	TestNull(TEXT("a J/22 has none"), ShipFramesFor("J/22"));
	TestNull(TEXT("no name, none"), ShipFramesFor(nullptr));
	if (!DataP) return false;
	const FShipFramesData& D = *DataP;
	TestEqual(TEXT("twelve frames"), D.NumFrames, 12);
	TestEqual(TEXT("a pose per whole degree of helm"), D.NumPoses, 71);
	TestEqual(TEXT("hard over 35 deg"), D.HardOverDeg, 35.0);
	TestTrue(TEXT("two and a half turns of the wheel to hard over"), std::fabs(D.WheelTurnsHardOver - 2.5) < 0.05);
	TestEqual(TEXT("a door opens square"), D.DoorOpenDeg, 90.0);
	TestEqual(TEXT("no such frame"), D.FrameNamed("Bowsprit"), -1);

	int32 Ropes = 0, Doors = 0, Below = 0;
	bool bRopeSeen[kRopeParts] = {};
	for (int32 K = 0; K < D.NumFrames; ++K)
	{
		const FShipFrame& F = D.Frames[K];
		TestTrue(FString::Printf(TEXT("frame %d is named"), K), F.Name && *F.Name);
		TestEqual(FString::Printf(TEXT("frame %s is found by name"), UTF8_TO_TCHAR(F.Name)), D.FrameNamed(F.Name), K);
		TestTrue(FString::Printf(TEXT("frame %s has unit axes"), UTF8_TO_TCHAR(F.Name)), Unit(F.X) && Unit(F.Y) && Unit(F.Z));
		TestTrue(FString::Printf(TEXT("frame %s is right-handed"), UTF8_TO_TCHAR(F.Name)), Near(F.X.Cross(F.Y), F.Z, 1e-3));
		TestTrue(FString::Printf(TEXT("frame %s is aboard"), UTF8_TO_TCHAR(F.Name)), F.Origin.X > -30.0 && F.Origin.X < 30.0 && std::fabs(F.Origin.Y) < 7.0 && F.Origin.Z > 1.0 && F.Origin.Z < 7.0);
		if (F.Kind == EShipFrameKind::Rope)
		{
			++Ropes;
			TestTrue(FString::Printf(TEXT("rope part %s has its column once"), UTF8_TO_TCHAR(F.Name)), F.Rope >= 0 && F.Rope < kRopeParts && !bRopeSeen[F.Rope]);
			if (F.Rope >= 0 && F.Rope < kRopeParts) bRopeSeen[F.Rope] = true;
		}
		else
		{
			TestEqual(FString::Printf(TEXT("%s is no rope part"), UTF8_TO_TCHAR(F.Name)), F.Rope, -1);
		}
		if (F.Kind == EShipFrameKind::Door)
		{
			++Doors;
			TestTrue(FString::Printf(TEXT("door %s swings one way"), UTF8_TO_TCHAR(F.Name)), std::fabs(std::fabs(F.Sign) - 1.0) < 1e-9);
		}
		else
		{
			TestEqual(FString::Printf(TEXT("%s has no swing sign"), UTF8_TO_TCHAR(F.Name)), F.Sign, 0.0);
		}
		if (F.bBelow) ++Below;
	}
	TestEqual(TEXT("six rope parts"), Ropes, 6);
	TestEqual(TEXT("two cabin doors"), Doors, 2);
	TestEqual(TEXT("the gun deck's parts: tiller, six rope parts, two doors, the capstan head"), Below, 10);
	TestTrue(TEXT("the wheel is on the quarterdeck"), D.FrameNamed("Wheel") >= 0 && !D.Frames[D.FrameNamed("Wheel")].bBelow && D.Frames[D.FrameNamed("Wheel")].Kind == EShipFrameKind::Wheel);
	TestTrue(TEXT("the tiller is below"), D.FrameNamed("Tiller") >= 0 && D.Frames[D.FrameNamed("Tiller")].bBelow && D.Frames[D.FrameNamed("Tiller")].Kind == EShipFrameKind::Tiller);
	TestTrue(TEXT("the tiller lies under the great cabin's beams, aft"), D.Frames[D.FrameNamed("Tiller")].Origin.X < -25.0 && D.Frames[D.FrameNamed("Tiller")].Origin.Z > 3.5);
	TestTrue(TEXT("a capstan on each deck"), D.FrameNamed("Capstan") >= 0 && D.FrameNamed("GunCapstan") >= 0
		&& D.Frames[D.FrameNamed("Capstan")].Origin.Z > D.Frames[D.FrameNamed("GunCapstan")].Origin.Z);

	// The poses: by helm degree ascending, a whole degree apart, the middle row the rest.
	int32 Mid = -1;
	for (int32 K = 0; K < D.NumPoses; ++K)
	{
		if (K > 0) TestTrue(FString::Printf(TEXT("pose %d a degree after the last"), K), std::fabs(D.Poses[K].HelmDeg - D.Poses[K - 1].HelmDeg - 1.0) < 1e-9);
		if (D.Poses[K].HelmDeg == 0.0) Mid = K;
		for (int32 R = 0; R < kRopeParts; ++R)
		{
			const FRopePosePart& P = D.Poses[K].Part[R];
			const Vec3 X(P.R[0][0], P.R[1][0], P.R[2][0]), Y(P.R[0][1], P.R[1][1], P.R[2][1]), Z(P.R[0][2], P.R[1][2], P.R[2][2]);
			if (!(Unit(X) && Unit(Y) && Unit(Z) && Near(X.Cross(Y), Z, 1e-3) && P.ScaleX > 0.0))
			{
				AddError(FString::Printf(TEXT("pose %d part %d is not a proper frame"), K, R));
				return false;
			}
		}
	}
	TestTrue(TEXT("the first row is hard over to port, the last to starboard"), D.NumPoses > 0 && D.Poses[0].HelmDeg == -D.HardOverDeg && D.Poses[D.NumPoses - 1].HelmDeg == D.HardOverDeg);
	TestTrue(TEXT("a row with the helm amidships"), Mid >= 0);
	for (int32 K = 0; K < D.NumFrames; ++K)
	{
		const FShipFrame& F = D.Frames[K];
		if (F.Kind != EShipFrameKind::Rope) continue;
		const FRigMotion M = RopePartMotion(D, F, 0.0);
		TestTrue(FString::Printf(TEXT("%s rests in the amidships row"), UTF8_TO_TCHAR(F.Name)), Still(M, F.Origin, 1e-3));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipFramesHelmTest, "SailingSim.ShipFrames.Helm", ShipFramesTestsLocal::TestFlags)
bool FShipFramesHelmTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace ShipFramesTestsLocal;
	const FShipFramesData& D = CommonwealthFrames();

	// The physics' rudder (+ the bow to starboard) is the tiller the other way: + helm takes the tiller to starboard, her head to port.
	TestTrue(TEXT("rudder +0.3 rad is helm -17.2 deg"), std::fabs(TillerHelmDeg(D, 0.3) + 17.19) < 0.02);
	TestEqual(TEXT("amidships"), TillerHelmDeg(D, 0.0), 0.0);
	TestEqual(TEXT("held at hard over"), TillerHelmDeg(D, -1.0), D.HardOverDeg);
	TestEqual(TEXT("held at hard over the other way"), TillerHelmDeg(D, 1.0), -D.HardOverDeg);
	TestTrue(TEXT("two and a half turns at hard over"), std::fabs(WheelTurns(D, D.HardOverDeg) - D.WheelTurnsHardOver) < 1e-9);
	TestTrue(TEXT("the wheel's turns have the helm's sign"), WheelTurns(D, -10.0) < 0.0 && std::fabs(WheelTurns(D, -10.0) * 3.5 + D.WheelTurnsHardOver) < 1e-9);
	FShipFramesData NoWheel = D;
	NoWheel.HardOverDeg = 0.0;
	TestEqual(TEXT("no swing, no turns"), WheelTurns(NoWheel, 10.0), 0.0);

	// The tiller turns about its own Z through the rudder head: the head stays, the end goes to starboard with + helm.
	const FShipFrame& T = D.Frames[D.FrameNamed("Tiller")];
	const Vec3 End = T.Origin + T.X * 4.6;   // about where the ropes' eye rides
	const FRigMotion Turn = FrameTurn(T, 20.0);
	TestTrue(TEXT("the rudder head stays put"), Near(Turn.Apply(T.Origin), T.Origin, 1e-9));
	const Vec3 End20 = Turn.Apply(End);
	TestTrue(TEXT("+ helm takes the tiller's end to starboard"), End20.Y > 1.4 && End20.Y < 1.7);
	TestTrue(TEXT("by 20 deg"), std::fabs(std::acos(FMath::Clamp((End20 - T.Origin).Dot(End - T.Origin) / ((End - T.Origin).Length() * (End20 - T.Origin).Length()), -1.0, 1.0)) * kRadToDeg - 20.0) < 1e-6);
	TestTrue(TEXT("a turn is rigid"), std::fabs(Turn.Determinant() - 1.0) < 1e-9);
	TestTrue(TEXT("no swing, no motion"), Still(FrameTurn(T, 0.0), End, 1e-12));
	TestTrue(TEXT("the other way to port"), FrameTurn(T, -20.0).Apply(End).Y < -1.4);

	// The wheel turns about its axle (its X): its hub stays and, with + helm, its top goes to port.
	const FShipFrame& W = D.Frames[D.FrameNamed("Wheel")];
	const FRigMotion Spin = FrameTurn(W, 360.0 * WheelTurns(D, 17.2), 0);
	TestTrue(TEXT("the hub stays put"), Near(Spin.Apply(W.Origin), W.Origin, 1e-9));
	const Vec3 Top = Spin.Apply(W.Origin + Vec3(0.0, 0.0, 0.8));
	TestTrue(TEXT("the top of the wheel goes to port with + helm"), Top.Y < -0.5 && std::fabs(Top.X - W.Origin.X) < 1e-9);
	TestTrue(TEXT("still 0.8 m from the hub"), std::fabs((Top - W.Origin).Length() - 0.8) < 1e-9);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipFramesRopesTest, "SailingSim.ShipFrames.Ropes", ShipFramesTestsLocal::TestFlags)
bool FShipFramesRopesTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace ShipFramesTestsLocal;
	const FShipFramesData& D = CommonwealthFrames();
	const FShipFrame& T = D.Frames[D.FrameNamed("Tiller")];
	const FShipFrame& EyeS = D.Frames[D.FrameNamed("TillerEye_S")];
	const FShipFrame& EyeP = D.Frames[D.FrameNamed("TillerEye_P")];
	const FShipFrame& RunS = D.Frames[D.FrameNamed("TillerRun_S")];
	const FShipFrame& RunP = D.Frames[D.FrameNamed("TillerRun_P")];
	const FShipFrame& WrapS = D.Frames[D.FrameNamed("TillerWrap_S")];

	// The eyes ride the tiller's end: at any helm the eye part sits where the tiller's turn takes it (within the build's 5 cm).
	for (double Helm : { -35.0, -20.0, -7.0, 0.0, 12.0, 20.0, 35.0 })
	{
		const FRigMotion Turn = FrameTurn(T, Helm);
		TestTrue(FString::Printf(TEXT("the starboard eye follows the tiller at helm %.0f"), Helm), Near(RopePartMotion(D, EyeS, Helm).Apply(EyeS.Origin), Turn.Apply(EyeS.Origin), 0.06));
		TestTrue(FString::Printf(TEXT("the port eye follows the tiller at helm %.0f"), Helm), Near(RopePartMotion(D, EyeP, Helm).Apply(EyeP.Origin), Turn.Apply(EyeP.Origin), 0.06));
	}

	// Between two of the table's degrees the pose is blended: 20.5 lies between 20 and 21.
	const Vec3 At20 = RopePartMotion(D, EyeS, 20.0).Apply(EyeS.Origin), At21 = RopePartMotion(D, EyeS, 21.0).Apply(EyeS.Origin);
	const Vec3 Half = RopePartMotion(D, EyeS, 20.5).Apply(EyeS.Origin);
	TestTrue(TEXT("a half degree is half way between the rows"), Near(Half, (At20 + At21) * 0.5, 1e-9));
	TestTrue(TEXT("the rows differ"), !Near(At20, At21, 0.01));
	TestTrue(TEXT("past hard over the last row holds"), Near(RopePartMotion(D, EyeS, 50.0).Apply(EyeS.Origin), RopePartMotion(D, EyeS, 35.0).Apply(EyeS.Origin), 1e-12));

	// A run stretches along its own X (the rope's length), rigid across it: the starboard run pays out as the tiller goes
	// to port, and shortens as it comes to starboard; the port run mirrors it.
	auto Stretch = [](const FRigMotion& M, const FShipFrame& F) { return M.ApplyVector(F.X).Length(); };
	TestTrue(TEXT("amidships the runs are as built"), std::fabs(Stretch(RopePartMotion(D, RunS, 0.0), RunS) - 1.0) < 1e-6);
	const double SPort = Stretch(RopePartMotion(D, RunS, -35.0), RunS), SStbd = Stretch(RopePartMotion(D, RunS, 35.0), RunS);
	TestTrue(TEXT("the starboard run pays out with the tiller to port"), SPort > 1.5 && SPort < 2.2);
	TestTrue(TEXT("and shortens with the tiller to starboard"), SStbd > 0.1 && SStbd < 0.3);
	TestTrue(TEXT("the port run mirrors it"), std::fabs(Stretch(RopePartMotion(D, RunP, 35.0), RunP) - SPort) < 1e-3 && std::fabs(Stretch(RopePartMotion(D, RunP, -35.0), RunP) - SStbd) < 1e-3);
	for (double Helm : { -35.0, 35.0 })
	{
		const FRigMotion M = RopePartMotion(D, RunS, Helm);
		// (the table's axes are rounded to a millionth: the stretch leaks a hundred-thousandth across them)
		TestTrue(FString::Printf(TEXT("rigid across the run at helm %.0f"), Helm), std::fabs(M.ApplyVector(RunS.Y).Length() - 1.0) < 1e-4 && std::fabs(M.ApplyVector(RunS.Z).Length() - 1.0) < 1e-4);
		TestTrue(FString::Printf(TEXT("the stretch is the volume's change at helm %.0f"), Helm), std::fabs(M.Determinant() - Stretch(M, RunS)) < 1e-4);
	}
	// The wrap on the sheave hardly moves; a part not in the table does not move at all.
	TestTrue(TEXT("the wrap stays on its sheave"), Near(RopePartMotion(D, WrapS, 35.0).Apply(WrapS.Origin), WrapS.Origin, 0.1));
	TestTrue(TEXT("the tiller is no rope part"), Still(RopePartMotion(D, T, 35.0), T.Origin, 1e-12));
	FShipFramesData Empty = D;
	Empty.NumPoses = 0;
	TestTrue(TEXT("an empty table moves nothing"), Still(RopePartMotion(Empty, EyeS, 35.0), EyeS.Origin, 1e-12));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipFramesDoorsTest, "SailingSim.ShipFrames.Doors", ShipFramesTestsLocal::TestFlags)
bool FShipFramesDoorsTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace ShipFramesTestsLocal;
	const FShipFramesData& D = CommonwealthFrames();
	const FShipFrame& DoorS = D.Frames[D.FrameNamed("CabinDoor_S")];
	const FShipFrame& DoorP = D.Frames[D.FrameNamed("CabinDoor_P")];

	// Each leaf hangs from its hinge beside the centreline and swings aft into the cabin, square to the wall when open.
	for (const FShipFrame* Door : { &DoorS, &DoorP })
	{
		const Vec3 Edge = Door->Origin + Door->X * 0.65;   // the leaf's free edge, 0.65 m from the hinge
		TestTrue(FString::Printf(TEXT("%s's leaf runs toward the centreline"), UTF8_TO_TCHAR(Door->Name)), std::fabs(Edge.Y) < std::fabs(Door->Origin.Y) && std::fabs(Edge.X - Door->Origin.X) < 1e-6);
		const Vec3 Open = FrameTurn(*Door, Door->Sign * D.DoorOpenDeg).Apply(Edge);
		TestTrue(FString::Printf(TEXT("%s swings aft"), UTF8_TO_TCHAR(Door->Name)), Open.X < Door->Origin.X - 0.6 && std::fabs(Open.Y - Door->Origin.Y) < 1e-6 && std::fabs(Open.Z - Edge.Z) < 1e-9);
		const Vec3 Wrong = FrameTurn(*Door, -Door->Sign * D.DoorOpenDeg).Apply(Edge);
		TestTrue(FString::Printf(TEXT("the other way would be through the wall, forward"), UTF8_TO_TCHAR(Door->Name)), Wrong.X > Door->Origin.X + 0.6);
	}
	TestTrue(TEXT("the doors swing opposite ways about their own Z"), DoorS.Sign == -DoorP.Sign);

	// A walker near a door's hinge on its deck wants it open; one on the deck above or well away does not.
	const Vec3 Deck(DoorS.Origin.X - 0.8, 0.2, 1.86);
	TestTrue(TEXT("a walker in the doorway"), ShipDoorNear(DoorS, Deck, FShipFramesPose::DoorNearM));
	TestTrue(TEXT("and the other door's too"), ShipDoorNear(DoorP, Deck, FShipFramesPose::DoorNearM));
	TestFalse(TEXT("not from the quarterdeck over it"), ShipDoorNear(DoorS, Deck + Vec3(0.0, 0.0, 2.3), FShipFramesPose::DoorNearM));
	TestFalse(TEXT("not from the berth deck under it"), ShipDoorNear(DoorS, Deck - Vec3(0.0, 0.0, 2.1), FShipFramesPose::DoorNearM));
	TestFalse(TEXT("not from the galley forward"), ShipDoorNear(DoorS, Vec3(-15.0, 0.0, 1.86), FShipFramesPose::DoorNearM));

	// The pose: the doors swing open in a second for him, stay open two seconds after he has gone, then swing shut.
	FShipFramesPose Pose;
	Pose.Reset(D);
	const int32 PortDoor = 0, StbdDoor = 1;   // in the frames' order (CabinDoor_P first)
	TestEqual(TEXT("shut at rest"), Pose.GetDoorOpen(PortDoor), 0.0);
	TestEqual(TEXT("no such door"), Pose.GetDoorOpen(7), 0.0);
	const double Dt = 1.0 / 60.0;
	for (int32 K = 0; K < 30; ++K) Pose.Update(D, 0.0, nullptr, Dt);
	TestEqual(TEXT("nobody walks her decks: shut"), Pose.GetDoorOpen(StbdDoor), 0.0);
	for (int32 K = 0; K < 30; ++K) Pose.Update(D, 0.0, &Deck, Dt);
	const double HalfWay = Pose.GetDoorOpen(StbdDoor);
	TestTrue(TEXT("half open after half a second"), HalfWay > 0.4 && HalfWay < 0.6);
	for (int32 K = 0; K < 45; ++K) Pose.Update(D, 0.0, &Deck, Dt);
	TestTrue(TEXT("open after a second and a quarter"), Pose.GetDoorOpen(StbdDoor) > 0.999);
	TestTrue(TEXT("both doors"), Pose.GetDoorOpen(PortDoor) > 0.999);
	// Its motion: the leaf swung aft, eased into its stop; open all the way it is the full turn.
	const Vec3 Edge = DoorS.Origin + DoorS.X * 0.65;
	TestTrue(TEXT("the open leaf is swung aft"), Near(Pose.Motion(D, D.FrameNamed("CabinDoor_S")).Apply(Edge), FrameTurn(DoorS, DoorS.Sign * D.DoorOpenDeg).Apply(Edge), 1e-4));
	for (int32 K = 0; K < 90; ++K) Pose.Update(D, 0.0, nullptr, Dt);
	TestTrue(TEXT("still open a second and a half after he has gone"), Pose.GetDoorOpen(StbdDoor) > 0.999);
	for (int32 K = 0; K < 60; ++K) Pose.Update(D, 0.0, nullptr, Dt);
	const double Closing = Pose.GetDoorOpen(StbdDoor);
	TestTrue(TEXT("closing after two and a half"), Closing > 0.3 && Closing < 0.7);
	const Vec3 PartWay = Pose.Motion(D, D.FrameNamed("CabinDoor_S")).Apply(Edge);
	TestTrue(TEXT("part way the leaf is between shut and open"), PartWay.X < Edge.X - 0.1 && PartWay.X > DoorS.Origin.X - 0.6);
	for (int32 K = 0; K < 70; ++K) Pose.Update(D, 0.0, nullptr, Dt);
	TestTrue(TEXT("shut again by three and a quarter"), Pose.GetDoorOpen(StbdDoor) < 1e-9);
	TestTrue(TEXT("a shut door is at its rest"), Still(Pose.Motion(D, D.FrameNamed("CabinDoor_S")), Edge, 1e-12));
	// He comes back: the door is on its way open at once (no wait), and a walker at one door does not open the other far away.
	Pose.Update(D, 0.0, &Deck, Dt);
	TestTrue(TEXT("opening again for him"), Pose.GetDoorOpen(StbdDoor) > 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipFramesPoseTest, "SailingSim.ShipFrames.Pose", ShipFramesTestsLocal::TestFlags)
bool FShipFramesPoseTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace ShipFramesTestsLocal;
	const FShipFramesData& D = CommonwealthFrames();
	FShipFramesPose Pose;
	Pose.Reset(D);
	TestEqual(TEXT("amidships at rest"), Pose.GetHelmDeg(), 0.0);
	for (int32 K = 0; K < D.NumFrames; ++K)
	{
		TestTrue(FString::Printf(TEXT("%s rests at rest"), UTF8_TO_TCHAR(D.Frames[K].Name)), Still(Pose.Motion(D, K), D.Frames[K].Origin, 1e-3));
	}

	// Rudder 0.3 rad (the bow to starboard): the helm is -17.2, the tiller to port with its ropes, the wheel's top to starboard.
	Pose.Update(D, 0.3, nullptr, 0.1);
	TestTrue(TEXT("helm from the rudder"), std::fabs(Pose.GetHelmDeg() + 17.19) < 0.02);
	const int32 Tiller = D.FrameNamed("Tiller"), EyeS = D.FrameNamed("TillerEye_S"), Wheel = D.FrameNamed("Wheel");
	const FShipFrame& T = D.Frames[Tiller];
	const Vec3 End = T.Origin + T.X * 4.6;
	const Vec3 EndNow = Pose.Motion(D, Tiller).Apply(End);
	TestTrue(TEXT("the tiller is to port"), EndNow.Y < -1.2 && EndNow.Y > -1.5);
	TestTrue(TEXT("the tiller's motion is its turn by the helm"), Near(EndNow, FrameTurn(T, Pose.GetHelmDeg()).Apply(End), 1e-12));
	TestTrue(TEXT("its rope eye follows"), Near(Pose.Motion(D, EyeS).Apply(D.Frames[EyeS].Origin), Pose.Motion(D, Tiller).Apply(D.Frames[EyeS].Origin), 0.06));
	TestTrue(TEXT("the ropes are the table's pose at this helm"), Near(Pose.Motion(D, EyeS).Apply(D.Frames[EyeS].Origin), RopePartMotion(D, D.Frames[EyeS], Pose.GetHelmDeg()).Apply(D.Frames[EyeS].Origin), 1e-12));
	const Vec3 Top = Pose.Motion(D, Wheel).Apply(D.Frames[Wheel].Origin + Vec3(0.0, 0.0, 0.8));
	TestTrue(TEXT("the wheel's top is to starboard"), Top.Y > 0.5);
	TestTrue(TEXT("the capstans stand"), Still(Pose.Motion(D, D.FrameNamed("Capstan")), D.Frames[D.FrameNamed("Capstan")].Origin, 1e-12)
		&& Still(Pose.Motion(D, D.FrameNamed("GunCapstan")), D.Frames[D.FrameNamed("GunCapstan")].Origin, 1e-12));
	TestTrue(TEXT("the doors are shut with nobody below"), Still(Pose.Motion(D, D.FrameNamed("CabinDoor_P")), D.Frames[D.FrameNamed("CabinDoor_P")].Origin, 1e-12));
	TestTrue(TEXT("no such frame moves nothing"), Still(Pose.Motion(D, -1), Vec3(), 1e-12) && Still(Pose.Motion(D, D.NumFrames), Vec3(), 1e-12));

	// Hard over and past: held at the tiller's swing.
	Pose.Update(D, -2.0, nullptr, 0.1);
	TestEqual(TEXT("held at hard over"), Pose.GetHelmDeg(), D.HardOverDeg);
	const Vec3 EndHard = Pose.Motion(D, Tiller).Apply(End);
	TestTrue(TEXT("the tiller is hard over to starboard"), EndHard.Y > 2.5);
	TestTrue(TEXT("the wheel has made its turns"), std::fabs(WheelTurns(D, Pose.GetHelmDeg()) - D.WheelTurnsHardOver) < 1e-9);
	return true;
}

#endif
