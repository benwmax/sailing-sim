#pragma once

#include "FixedStepper.h"

#include <cstdint>

namespace Sailing
{
	/**
	 * The world's clock (online readiness, rule 3): weather, tides, waves, traffic and every boat run on it, and no boat
	 * owns it. It advances in whole physics steps, so its time is always a whole number of PhysicsDt past its base and
	 * every boat that steps until it reaches the clock lands on the same instant. (Before, the clock was the player's
	 * boat's physics time, which a second player or a boat held by the front end would have split.)
	 */
	class FWorldClock
	{
	public:
		/** Adds frame time; returns the whole steps it moved (capped per frame like a boat's stepper). */
		int Advance(double FrameDt)
		{
			const int N = Stepper.Advance(FrameDt);
			Steps += N;
			return N;
		}

		/** Seconds since the session started (or since SetTime). */
		double GetTime() const { return Base + double(Steps) * Stepper.GetStepDt(); }
		int64_t GetSteps() const { return Steps; }
		double GetStepDt() const { return Stepper.GetStepDt(); }

		/** Puts the clock at a time (a test, or a session that resumes at a saved time). */
		void SetTime(double Seconds)
		{
			Base = Seconds;
			Steps = 0;
		}

	private:
		FFixedStepper Stepper;
		double Base = 0.0;
		int64_t Steps = 0;
	};
}
