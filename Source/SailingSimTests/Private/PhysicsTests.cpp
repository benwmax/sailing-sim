#include "Misc/AutomationTest.h"
#include "BoatPhysicsStub.h"
#include "FixedStepper.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags PhysicsTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	void RunSeconds(FBoatPhysicsStub& Boat, double Seconds, const FBoatControls& Controls = FBoatControls())
	{
		const int32 Steps = FMath::RoundToInt(Seconds * PhysicsHz);
		for (int32 i = 0; i < Steps; ++i)
		{
			Boat.Step(PhysicsDt, Controls);
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFixedStepperTest, "SailingSim.Physics.FixedStepRate", PhysicsTestFlags)
bool FSailingFixedStepperTest::RunTest(const FString& Parameters)
{
	FFixedStepper Stepper;
	TestEqual(TEXT("Step rate is 120 Hz"), Stepper.GetStepDt(), 1.0 / 120.0);

	int32 Total = 0;
	for (int32 i = 0; i < 60; ++i)
	{
		Total += Stepper.Advance(1.0 / 60.0);
	}
	TestEqual(TEXT("One second at 60 fps runs 120 steps"), Total, 120);

	Total = 0;
	for (int32 i = 0; i < 144; ++i)
	{
		Total += Stepper.Advance(1.0 / 144.0);
	}
	TestTrue(TEXT("One second at 144 fps runs 119 to 120 steps"), Total >= 119 && Total <= 120);

	FFixedStepper Hitch;
	TestEqual(TEXT("A 2 s hitch is capped at 12 steps"), Hitch.Advance(2.0), 12);
	TestTrue(TEXT("Hitch time is dropped, not carried"), Hitch.Alpha() < 1.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFrameRateIndependenceTest, "SailingSim.Physics.FrameRateIndependent", PhysicsTestFlags)
bool FSailingFrameRateIndependenceTest::RunTest(const FString& Parameters)
{
	// The same 4 seconds of input at 30 fps and at 120 fps must give identical boat states.
	auto Simulate = [](double Fps)
	{
		FBoatPhysicsStub Boat;
		Boat.State.Z = 0.3;
		FFixedStepper Stepper;
		FBoatControls Controls;
		Controls.Throttle = 1.0;
		Controls.Rudder = 0.5;
		const int32 Frames = FMath::RoundToInt(4.0 * Fps);
		for (int32 f = 0; f < Frames; ++f)
		{
			const int32 Steps = Stepper.Advance(1.0 / Fps);
			for (int32 s = 0; s < Steps; ++s)
			{
				Boat.Step(PhysicsDt, Controls);
			}
		}
		return Boat.State;
	};

	const FBoatState A = Simulate(30.0);
	const FBoatState B = Simulate(120.0);
	TestEqual(TEXT("X matches"), A.X, B.X, 1e-9);
	TestEqual(TEXT("Y matches"), A.Y, B.Y, 1e-9);
	TestEqual(TEXT("Heading matches"), A.Heading, B.Heading, 1e-9);
	TestEqual(TEXT("Heel matches"), A.Heel, B.Heel, 1e-9);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFloatTest, "SailingSim.Physics.FloatsAtWaterline", PhysicsTestFlags)
bool FSailingFloatTest::RunTest(const FString& Parameters)
{
	FBoatPhysicsStub Boat;
	Boat.State.Z = 0.25; // dropped 25 cm above the waterline
	RunSeconds(Boat, 10.0);
	TestEqual(TEXT("Settles at the waterline (within 1 mm)"), Boat.State.Z, 0.0, 0.001);
	TestEqual(TEXT("Heave motion has died out"), Boat.State.HeaveRate, 0.0, 0.001);

	// Heave period for a J/22-sized waterplane is under a second.
	TestTrue(TEXT("Heave period is plausible (0.5 to 1.5 s)"), Boat.HeavePeriod() > 0.5 && Boat.HeavePeriod() < 1.5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHeelTest, "SailingSim.Physics.RightsFromHeel", PhysicsTestFlags)
bool FSailingHeelTest::RunTest(const FString& Parameters)
{
	FBoatPhysicsStub Boat;
	Boat.State.Heel = FMath::DegreesToRadians(20.0);
	RunSeconds(Boat, 0.5);
	TestTrue(TEXT("Righting moment rolls the boat back toward upright"), Boat.State.Heel < FMath::DegreesToRadians(20.0));
	RunSeconds(Boat, 20.0);
	TestEqual(TEXT("Comes back upright (within 0.1 degree)"), FMath::RadiansToDegrees(Boat.State.Heel), 0.0, 0.1);
	TestTrue(TEXT("Roll period is plausible for a 22 ft keelboat (1.5 to 4 s)"), Boat.RollPeriod() > 1.5 && Boat.RollPeriod() < 4.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSteeringTest, "SailingSim.Physics.SteeringStub", PhysicsTestFlags)
bool FSailingSteeringTest::RunTest(const FString& Parameters)
{
	FBoatControls Controls;
	Controls.Throttle = 1.0;

	FBoatPhysicsStub Straight;
	RunSeconds(Straight, 20.0, Controls);
	TestTrue(TEXT("Motor moves the boat forward"), Straight.State.X > 10.0);
	TestEqual(TEXT("No rudder means no turn"), Straight.State.Heading, 0.0, 1e-9);
	const double SpeedKnots = Straight.State.Surge / MetersPerSecondPerKnot;
	TestTrue(TEXT("Placeholder motor stays below hull speed"), SpeedKnots < HullSpeedKnots(Straight.GetParams().WaterlineLength));

	FBoatPhysicsStub Turning;
	Controls.Rudder = 1.0;
	RunSeconds(Turning, 3.0, Controls);
	TestTrue(TEXT("Right rudder turns to starboard"), Turning.State.Heading > 0.0);
	TestTrue(TEXT("Turning heels the boat outward (to port, negative heel)"), Turning.State.Heel < 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHullSpeedTest, "SailingSim.Physics.HullSpeedRule", PhysicsTestFlags)
bool FSailingHullSpeedTest::RunTest(const FString& Parameters)
{
	// J/22 LWL 19 ft: 1.34 * sqrt(19) = 5.84 knots.
	TestEqual(TEXT("J/22 hull speed"), HullSpeedKnots(19.0 * MetersPerFoot), 5.84, 0.01);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
