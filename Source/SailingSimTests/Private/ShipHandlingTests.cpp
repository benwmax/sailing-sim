#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "ShipHandling.h"
#include "SquareRig.h"
#include "Wind.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// docs/frigate-physics/: a square-rigged ship's manoeuvres by orders (ShipHandling.h). These hold the orders each step
// gives on the controls, on a three-masted square rig set on the J/22's hull (the frigate's own trials, tack, wear and
// heave to in her config, come with her boat type: Tools/shipkit/frigate/trial/trial.sh --manoeuvre meanwhile).
namespace ShipHandlingTestsLocal
{
	constexpr EAutomationTestFlags ShipFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FBoatConfig ThreeMasts()
	{
		FBoatConfig C;
		FSquareRig& R = C.Square;
		R.NumMasts = 3;
		const double X[3] = { C.MastX + 1.5, C.MastX, C.MastX - 2.0 };
		for (int M = 0; M < 3; ++M)
		{
			R.MastX[M] = X[M];
			FSquareSailDef Course;
			Course.Kind = ESquareSailKind::Course;
			Course.Mast = M;
			Course.PivotX = X[M];
			Course.ForeOffset = 0.1;
			Course.FootZ = 1.5;
			Course.HeadZ = 4.0;
			Course.HeadWidth = Course.FootWidth = 2.0;
			Course.Area = 5.0;
			Course.BraceLimitDeg = 40.0;
			R.Sails.push_back(Course);
			FSquareSailDef Topsail = Course;
			Topsail.Kind = ESquareSailKind::Topsail;
			Topsail.FootZ = 4.0;
			Topsail.HeadZ = 6.0;
			Topsail.Area = 3.5;
			R.Sails.push_back(Topsail);
		}
		return C;
	}

	/** She sails close-hauled on the starboard tack for a few seconds (the telemetry filled), then hands over. */
	void Underway(FBoatModel& Boat, const FWindField& Wind, double TwaDeg)
	{
		Boat.Reset(0.0, 0.0, -TwaDeg * kDegToRad, 2.0);
		FBoatControls Controls;
		Controls.bMainDown = Controls.bJibDown = true;
		for (int M = 0; M < kMaxMasts; ++M) Controls.Brace[M] = TwaDeg > 0.0 ? 1.0 : -1.0;
		for (int I = 0; I < int(2.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, Controls, Wind);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShipTackOrdersTest, "SailingSim.Physics.ShipTackOrders", ShipHandlingTestsLocal::ShipFlags)
bool FSailingShipTackOrdersTest::RunTest(const FString&)
{
	using namespace ShipHandlingTestsLocal;
	const FBoatConfig C = ThreeMasts();
	FBoatModel Boat(C);
	FWindParams P;
	P.SpeedKnots = 12.0;
	P.FromDegrees = 0.0;
	const FWindField Wind(P);
	Underway(Boat, Wind, 65.0);

	FShipHandling H;
	TestFalse(TEXT("idle before an order"), H.IsActive());
	FBoatControls Controls;
	TestFalse(TEXT("idle: the caller keeps the helm"), H.Update(Boat, Controls, PhysicsDt));

	const double HelmBefore = Boat.GetState().RudderAngle / (C.MaxRudderAngleDeg * kDegToRad);
	H.Start(EShipManoeuvre::Tack, Boat);
	TestTrue(TEXT("tacking"), H.IsActive());
	TestTrue(TEXT("helm's a-lee first"), H.Step() == EShipManoeuvreStep::HelmsALee);
	TestEqual(TEXT("she ends on the port tack"), H.NewSide(), -1.0);
	TestEqual(TEXT("close-hauled on the port tack after"), H.CourseAfterDeg(), -H.Settings.CloseHauledDeg);

	// Helm's a-lee: the wheel goes over toward the wind (bow to starboard, the wind from starboard) at the wheel's pace,
	// the headsheets fly, the spanker is hauled amidships and every yard stays braced for the old tack.
	for (int M = 0; M < kMaxMasts; ++M) Controls.Brace[M] = 0.3;
	TestTrue(TEXT("holds the helm"), H.Update(Boat, Controls, 0.5));
	TestTrue(TEXT("helm a-lee"), Controls.Tiller > 0.0);
	TestTrue(TEXT("a wheel's pace (a tiller: a second hard over)"), Controls.Tiller <= HelmBefore + 0.5 + 1e-9);
	TestEqual(TEXT("headsheets let fly"), Controls.JibSheet, 1.0);
	TestEqual(TEXT("spanker amidships"), Controls.MainSheet, 0.0);
	for (int M = 0; M < 3; ++M) TestEqual(TEXT("yards held for the old tack"), Controls.Brace[M], 1.0);
	for (int I = 0; I < 4; ++I) H.Update(Boat, Controls, 0.5);
	TestEqual(TEXT("hard a-lee"), Controls.Tiller, 1.0);

	// Head to wind: mainsail haul swings the main and mizzen yards for the new tack, the fore yards stay aback.
	Boat.Reset(0.0, 0.0, -8.0 * kDegToRad, 0.5);
	for (int I = 0; I < 4; ++I) Boat.Step(PhysicsDt, Controls, Wind);
	H.Update(Boat, Controls, PhysicsDt);
	TestTrue(TEXT("mainsail haul near the wind"), H.Step() == EShipManoeuvreStep::MainsailHaul);
	H.Update(Boat, Controls, PhysicsDt);
	TestEqual(TEXT("fore yards held aback"), Controls.Brace[0], 1.0);
	TestEqual(TEXT("main yards round"), Controls.Brace[1], -H.Settings.MainHaulBrace);
	TestEqual(TEXT("mizzen yards round"), Controls.Brace[2], -H.Settings.MainHaulBrace);

	// Well past the wind on the new side: let go and haul swings the fore yards; the courses come down again.
	Boat.Reset(0.0, 0.0, 40.0 * kDegToRad, 0.5);
	for (int I = 0; I < 4; ++I) Boat.Step(PhysicsDt, Controls, Wind);
	H.Update(Boat, Controls, PhysicsDt);
	TestTrue(TEXT("let go and haul past the wind"), H.Step() == EShipManoeuvreStep::LetGoAndHaul);
	H.Update(Boat, Controls, PhysicsDt);
	TestTrue(TEXT("fore yards round for the new tack"), Controls.Brace[0] < 0.0);
	for (int I = 0; I < int(C.Square.Sails.size()); ++I)
		TestTrue(TEXT("tacks and sheets hauled down again"), Controls.SquareSet[I] == ESailSet::Set);
	TestEqual(TEXT("step names for the orders panel"), FString(UTF8_TO_TCHAR(FShipHandling::StepName(H.Step()))), FString(TEXT("Let go and haul")));

	// An order cancelled after "rise tacks and sheets": the courses set again and the spanker no longer brailed.
	Underway(Boat, Wind, 65.0);
	FShipHandling Cancel;
	FBoatControls K;
	Cancel.Start(EShipManoeuvre::Tack, Boat);
	Boat.Reset(0.0, 0.0, -30.0 * kDegToRad, 1.0);
	Boat.Step(PhysicsDt, K, Wind);
	Cancel.Update(Boat, K, PhysicsDt);
	bool bAnyClewed = false;
	for (int I = 0; I < int(C.Square.Sails.size()); ++I) bAnyClewed |= K.SquareSet[I] == ESailSet::Clewed;
	TestTrue(TEXT("courses clewed up near the wind"), bAnyClewed);
	Cancel.Start(EShipManoeuvre::Tack, Boat); // re-issued: the held set must stay the one from before the first rise
	Cancel.Update(Boat, K, PhysicsDt);
	K.bMainDown = true;
	Cancel.Start(EShipManoeuvre::None, Boat);
	TestFalse(TEXT("cancelled: the caller keeps the helm"), Cancel.Update(Boat, K, PhysicsDt));
	for (int I = 0; I < int(C.Square.Sails.size()); ++I) TestTrue(TEXT("cancelled: courses set again"), K.SquareSet[I] == ESailSet::Set);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShipMissedStaysTest, "SailingSim.Physics.ShipMissedStays", ShipHandlingTestsLocal::ShipFlags)
bool FSailingShipMissedStaysTest::RunTest(const FString&)
{
	using namespace ShipHandlingTestsLocal;
	const FBoatConfig C = ThreeMasts();
	FBoatModel Boat(C);
	FWindParams P;
	P.SpeedKnots = 12.0;
	P.FromDegrees = 0.0;
	const FWindField Wind(P);
	Underway(Boat, Wind, 65.0);
	FShipHandling H;
	H.Start(EShipManoeuvre::Tack, Boat);
	FBoatControls Controls;
	// She never comes up past 40 degrees (held there): after MissedStaysSeconds the order is to wear.
	const int Steps = int((H.Settings.MissedStaysSeconds + 1.0) / 0.5);
	for (int I = 0; I < Steps; ++I)
	{
		Boat.Reset(0.0, 0.0, -40.0 * kDegToRad, 1.0);
		Boat.Step(PhysicsDt, Controls, Wind);
		H.Update(Boat, Controls, 0.5);
	}
	TestTrue(TEXT("missed stays: wearing"), H.Manoeuvre() == EShipManoeuvre::Wear);
	// The helm comes up from hard a-lee at the wheel's pace.
	for (int I = 0; I < 6; ++I)
	{
		Boat.Reset(0.0, 0.0, -40.0 * kDegToRad, 1.0);
		Boat.Step(PhysicsDt, Controls, Wind);
		H.Update(Boat, Controls, 0.5);
	}
	TestTrue(TEXT("the wear's first order"), H.Step() == EShipManoeuvreStep::MissedStays || H.Step() == EShipManoeuvreStep::BearAway);
	TestTrue(TEXT("the spanker brailed up to wear"), Controls.bMainDown);
	TestTrue(TEXT("helm up: bearing away (bow to port, the wind from starboard)"), Controls.Tiller < 0.0);
	TestEqual(TEXT("still bound for the port tack"), H.NewSide(), -1.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShipHeaveToTest, "SailingSim.Physics.ShipHeaveTo", ShipHandlingTestsLocal::ShipFlags)
bool FSailingShipHeaveToTest::RunTest(const FString&)
{
	using namespace ShipHandlingTestsLocal;
	const FBoatConfig C = ThreeMasts();
	FBoatModel Boat(C);
	FWindParams P;
	P.SpeedKnots = 12.0;
	P.FromDegrees = 0.0;
	const FWindField Wind(P);
	Underway(Boat, Wind, -65.0);
	FShipHandling H;
	H.Start(EShipManoeuvre::HeaveTo, Boat);
	TestTrue(TEXT("hove to"), H.Step() == EShipManoeuvreStep::HoveTo);
	FBoatControls Controls;
	TestTrue(TEXT("holds the helm hove to"), H.Update(Boat, Controls, PhysicsDt));
	// On the port tack: the fore and mizzen yards braced up for it, the main yards braced for the other tack (aback).
	TestEqual(TEXT("fore full"), Controls.Brace[0], -1.0);
	TestEqual(TEXT("main aback"), Controls.Brace[1], H.Settings.HoveToBraceShare);
	TestEqual(TEXT("mizzen full"), Controls.Brace[2], -1.0);
	TestTrue(TEXT("lying to until told otherwise"), H.IsActive());
	H.Start(EShipManoeuvre::None, Boat);
	TestFalse(TEXT("None ends it"), H.IsActive());
	return true;
}

#endif
