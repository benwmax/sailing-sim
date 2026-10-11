#pragma once

#include "SailingPhysicsApi.h"

namespace Sailing
{
	/** Physics step rate. Every boat is stepped at this rate regardless of frame rate. */
	constexpr double PhysicsHz = 120.0;
	constexpr double PhysicsDt = 1.0 / PhysicsHz;

	/**
	 * Fixed-timestep accumulator. Frame time goes in, a whole number of fixed steps comes out,
	 * so the boat behaves the same at 30 fps on a phone and 144 fps on a desktop.
	 */
	class SAILINGPHYSICS_API FFixedStepper
	{
	public:
		explicit FFixedStepper(double InStepDt = PhysicsDt, int InMaxStepsPerFrame = 12)
			: StepDt(InStepDt), MaxStepsPerFrame(InMaxStepsPerFrame) {}

		/** Adds frame time and returns how many fixed steps to run now. Drops time past MaxStepsPerFrame (a hitch). */
		int Advance(double FrameDt);

		/** Fraction of a step left in the accumulator, for render interpolation. */
		double Alpha() const { return Accumulator / StepDt; }

		double GetStepDt() const { return StepDt; }

	private:
		double StepDt;
		int MaxStepsPerFrame;
		double Accumulator = 0.0;
	};
}
