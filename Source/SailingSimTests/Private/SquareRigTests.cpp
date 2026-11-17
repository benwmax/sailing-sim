#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "SquareRig.h"
#include "Wind.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// docs/frigate-physics/: square sails hung from yards (SquareRig.h), the frigate Commonwealth's rig. These hold the
// sail's coefficients, the bracing and the model's forces on one square sail set on the J/22's hull (the frigate's own
// config comes with her boat type).
namespace SquareRigTestsLocal
{
	constexpr EAutomationTestFlags SquareFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FBoatConfig OneSquareSail()
	{
		FBoatConfig C;
		FSquareRig& R = C.Square;
		R.NumMasts = 1;
		R.MastX[0] = C.MastX;
		FSquareSailDef Course;
		Course.Kind = ESquareSailKind::Course;
		Course.Mast = 0;
		Course.PivotX = C.MastX;
		Course.ForeOffset = 0.1;
		Course.FootZ = 1.5;
		Course.HeadZ = 6.0;
		Course.HeadWidth = Course.FootWidth = 3.0;
		Course.Area = 13.5;
		Course.BraceLimitDeg = 40.0;
		Course.ReefAreaFraction = { 0.75 };
		R.Sails.push_back(Course);
		FSquareSailDef Topsail = Course;
		Topsail.Kind = ESquareSailKind::Topsail;
		Topsail.FootZ = 6.0;
		Topsail.HeadZ = 8.0;
		Topsail.Area = 5.0;
		Topsail.BraceLimitDeg = 30.0;
		Topsail.BraceOffsetDeg = 4.0;
		R.Sails.push_back(Topsail);
		return C;
	}

	/** One step in a 12 kn wind from north with the boat stopped on a heading, the yards already where the brace puts
	 *  them and the sails as set; the course's force in the boat's frame. */
	Vec3 CourseForce(FBoatModel& Boat, double HeadingDeg, double Brace, ESailSet Set)
	{
		const FBoatConfig& C = Boat.GetConfig();
		FWindParams P;
		P.SpeedKnots = 12.0;
		P.FromDegrees = 0.0;
		const FWindField Wind(P);
		Boat.Reset(0.0, 0.0, HeadingDeg * kDegToRad, 0.0);
		FBoatControls Controls;
		Controls.bMainDown = Controls.bJibDown = true;
		Controls.Brace[0] = Brace;
		for (int I = 0; I < int(C.Square.Sails.size()); ++I)
		{
			Controls.SquareSet[I] = Set;
			Boat.GetMutableState().YardAngle[I] = YardAngleFor(C.Square, I, Brace);
			Boat.GetMutableState().SquareOut[I] = Set == ESailSet::Set ? 1.0 : 0.0;
		}
		Boat.Step(PhysicsDt, Controls, Wind);
		return Boat.GetTelemetry().NumSquareSails > 0 ? Boat.GetTelemetry().SquareStrips[0].Force : Vec3();
	}
}

/** A square sail's lift and drag: lift grows to the stall, the sail shakes with the wind along its yard, and square to the
 *  wind it is a bluff plate (drag only). */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSquareSailCoefficientsTest, "SailingSim.Physics.SquareSailCoefficients", SquareRigTestsLocal::SquareFlags)
bool FSailingSquareSailCoefficientsTest::RunTest(const FString&)
{
	const FSquareRig Rig;
	const double Stall = SquareStallAlpha(Rig);
	AddInfo(FString::Printf(TEXT("Stall at %.1f deg"), Stall * kRadToDeg));
	TestTrue(TEXT("A deep square sail stalls between 15 and 30 deg"), Stall > 15.0 * kDegToRad && Stall < 30.0 * kDegToRad);
	double Last = -1.0, CL = 0.0, CD = 0.0;
	ESailFlow Flow;
	for (double Deg = Rig.LuffDeg + 1.0; Deg <= Stall * kRadToDeg; Deg += 1.0)
	{
		SquareSailCoefficients(Rig, Deg * kDegToRad, CL, CD, Flow);
		TestTrue(*FString::Printf(TEXT("Lift grows toward the stall (%.0f deg)"), Deg), CL > Last);
		Last = CL;
	}
	SquareSailCoefficients(Rig, Stall, CL, CD, Flow);
	TestTrue(TEXT("Its greatest lift 0.75 + 4 x camber"), FMath::IsNearlyEqual(CL, 0.75 + 4.0 * Rig.Camber, 0.01));
	TestTrue(TEXT("... attached"), Flow == ESailFlow::Attached);
	SquareSailCoefficients(Rig, 0.0, CL, CD, Flow);
	TestTrue(TEXT("Wind along the yard: no lift, it shakes"), FMath::Abs(CL) < 1e-9 && Flow == ESailFlow::Luffing);
	SquareSailCoefficients(Rig, 0.5 * kPi, CL, CD, Flow);
	TestTrue(TEXT("Square to the wind: no lift"), FMath::Abs(CL) < 1e-6);
	TestTrue(TEXT("... and the bluff plate's drag"), FMath::IsNearlyEqual(CD, Rig.RunningCD, 1e-6));
	SquareSailCoefficients(Rig, 50.0 * kDegToRad, CL, CD, Flow);
	TestTrue(TEXT("Past the stall it is stalled"), Flow == ESailFlow::Stalled);
	TestTrue(TEXT("... and its drag at least the plate's"), CD >= Rig.RunningCD * FMath::Square(FMath::Sin(50.0 * kDegToRad)) - 1e-9);
	return true;
}

/** Bracing: each mast's yards swing together, the upper ones squarer by their offset and held to their own limit; the
 *  trimmer's brace meets the wind at the angle it asks for, and squares the yards before the wind. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSquareBracingTest, "SailingSim.Physics.SquareBracing", SquareRigTestsLocal::SquareFlags)
bool FSailingSquareBracingTest::RunTest(const FString&)
{
	const FBoatConfig C = SquareRigTestsLocal::OneSquareSail();
	const FSquareRig& R = C.Square;
	TestEqual(TEXT("The course is the mast's lowest sail"), R.LowestOn(0), 0);
	TestTrue(TEXT("Sharp up: the course at its limit"), FMath::IsNearlyEqual(YardAngleFor(R, 0, 1.0) * kRadToDeg, 40.0, 1e-9));
	TestTrue(TEXT("... the topsail at its own, tighter limit"), FMath::IsNearlyEqual(YardAngleFor(R, 1, 1.0) * kRadToDeg, 30.0, 1e-9));
	TestTrue(TEXT("Half braced: the topsail squarer by its offset"), FMath::IsNearlyEqual(YardAngleFor(R, 1, 0.5) * kRadToDeg, 16.0, 1e-9));
	TestTrue(TEXT("... on either tack"), FMath::IsNearlyEqual(YardAngleFor(R, 1, -0.5) * kRadToDeg, -16.0, 1e-9));
	TestTrue(TEXT("Nearly square: never past square the other way"), FMath::IsNearlyEqual(YardAngleFor(R, 1, 0.05), 0.0, 1e-12));
	TestTrue(TEXT("The brace held to -1..1"), FMath::IsNearlyEqual(YardAngleFor(R, 0, 3.0), YardAngleFor(R, 0, 1.0), 1e-12));
	for (const double Awa : { 70.0, 90.0, 105.0, -80.0 })
	{
		const double B = BraceForAlpha(R, 0, Awa * kDegToRad, 20.0);
		const double Psi = YardAngleFor(R, 0, B) * kRadToDeg;
		const double Alpha = FMath::Abs(Awa) + Psi * FMath::Sign(Awa) - 90.0;
		TestTrue(*FString::Printf(TEXT("AWA %.0f: braced to 20 deg of attack or its limit (%.1f)"), Awa, Alpha),
			FMath::IsNearlyEqual(Alpha, 20.0, 1e-6) || FMath::IsNearlyEqual(FMath::Abs(Psi), 40.0, 1e-6));
		TestTrue(*FString::Printf(TEXT("AWA %.0f: braced up for the side the wind is on"), Awa), B * Awa > 0.0);
	}
	TestTrue(TEXT("Before the wind the yards are square"), FMath::IsNearlyEqual(BraceForAlpha(R, 0, kPi, 20.0), 0.0, 1e-12));
	TestTrue(TEXT("... and with the wind abaft the beam past the angle asked (never braced the wrong way)"),
		FMath::IsNearlyEqual(BraceForAlpha(R, 0, 120.0 * kDegToRad, 20.0), 0.0, 1e-12));
	return true;
}

/** The model's forces on a square sail: before the wind it drives her ahead; braced up on a reach it drives and heels
 *  her to leeward; braced for the other tack it is aback and drives her astern; clewed up it is only windage. A boat
 *  with no square rig has none. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSquareRigForcesTest, "SailingSim.Physics.SquareRigForces", SquareRigTestsLocal::SquareFlags)
bool FSailingSquareRigForcesTest::RunTest(const FString&)
{
	using namespace SquareRigTestsLocal;
	const FBoatConfig C = OneSquareSail();
	{
		const FBoatConfig J22;
		FBoatModel Plain(J22);
		CourseForce(Plain, 90.0, 0.0, ESailSet::Set);
		TestFalse(TEXT("The J/22 has no square rig"), J22.HasSquareRig());
		TestEqual(TEXT("... and no square sails in her telemetry"), Plain.GetTelemetry().NumSquareSails, 0);
	}
	FBoatModel Boat(C);
	const Vec3 Run = CourseForce(Boat, 180.0, 0.0, ESailSet::Set);
	AddInfo(FString::Printf(TEXT("Running: %.0f N ahead, %.0f N across"), Run.X, Run.Y));
	TestTrue(TEXT("Running: the course drives her ahead"), Run.X > 50.0);
	TestTrue(TEXT("... square to her, without side force"), FMath::Abs(Run.Y) < 0.05 * Run.X);

	// The wind 60 deg on the starboard bow (TWA = wind from - heading).
	const double B = BraceForAlpha(C.Square, 0, 60.0 * kDegToRad, 15.0);
	const Vec3 Reach = CourseForce(Boat, -60.0, B, ESailSet::Set);
	AddInfo(FString::Printf(TEXT("Braced up, wind 60 deg on the bow: %.0f N ahead, %.0f N across"), Reach.X, Reach.Y));
	TestTrue(TEXT("Braced up: braced for a starboard wind"), B > 0.0);
	TestTrue(TEXT("... the course drives her ahead"), Reach.X > 0.0);
	TestTrue(TEXT("... and pushes her to leeward (port)"), Reach.Y < 0.0);

	{
		// Braced up, a course set sharper than its yard (its tack hauled forward) meets the wind at more angle and drives more.
		FBoatConfig Sharp = C;
		Sharp.Square.Sails[0].SetsPastYardDeg = 8.0;
		FBoatModel SharpBoat(Sharp);
		const Vec3 Sharper = CourseForce(SharpBoat, -60.0, 1.0, ESailSet::Set);
		const Vec3 AtYard = CourseForce(Boat, -60.0, 1.0, ESailSet::Set);
		AddInfo(FString::Printf(TEXT("Sharp up, wind 60 deg on the bow: %.0f N ahead on the yard, %.0f N set 8 deg past it"), AtYard.X, Sharper.X));
		TestTrue(TEXT("A course set past its yard drives more close-hauled"), Sharper.X > AtYard.X);
		const double B2 = BraceForAlpha(Sharp.Square, 0, 70.0 * kDegToRad, 15.0);
		const double Working = YardAngleFor(Sharp.Square, 0, B2) * kRadToDeg * (1.0 + 8.0 / 40.0);
		TestTrue(TEXT("... and the trimmer braces its working chord, not its yard, to the angle asked"), FMath::IsNearlyEqual(70.0 + Working - 90.0, 15.0, 1e-6));
	}
	const Vec3 Backed = CourseForce(Boat, -60.0, -1.0, ESailSet::Set);
	AddInfo(FString::Printf(TEXT("Braced for the other tack: %.0f N ahead"), Backed.X));
	TestTrue(TEXT("Braced the wrong way the course is aback and drives her astern"), Backed.X < 0.0);
	TestTrue(TEXT("... and says so"), Boat.GetTelemetry().SquareStrips[0].Flow == ESailFlow::Backed);

	const Vec3 Clewed = CourseForce(Boat, 180.0, 0.0, ESailSet::Clewed);
	TestTrue(TEXT("Clewed up it is a tenth of the set sail's force or less"), Clewed.Length() < 0.1 * Run.Length());
	return true;
}

/** The trimmer braces a square rig's yards: braced up for the side the wind is on, square before it. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSquareTrimTest, "SailingSim.Physics.SquareTrim", SquareRigTestsLocal::SquareFlags)
bool FSailingSquareTrimTest::RunTest(const FString&)
{
	using namespace SquareRigTestsLocal;
	const FBoatConfig C = OneSquareSail();
	for (const double Heading : { -70.0, 70.0, 180.0 })
	{
		FBoatModel Boat(C);
		CourseForce(Boat, Heading, 0.0, ESailSet::Set);
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FBoatControls Controls;
		const FBoatControls Out = Trim.Update(Boat, Controls, PhysicsDt);
		const double Twa = -Heading;
		AddInfo(FString::Printf(TEXT("TWA %.0f: brace %.2f"), Twa, Out.Brace[0]));
		if (FMath::Abs(Twa) > 170.0) TestTrue(TEXT("Before the wind: square"), FMath::Abs(Out.Brace[0]) < 0.05);
		else TestTrue(*FString::Printf(TEXT("TWA %.0f: braced up for the side the wind is on"), Twa), Out.Brace[0] * Twa > 0.0);
	}
	return true;
}

#endif
