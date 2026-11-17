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

		/**
		 * The instant to draw (feedback #26, docs/render-clock/): the clock less the part of a step the frame has not
		 * stepped yet, so the drawn world moves by each frame's own length. GetTime() moves in whole steps: at 60 fps,
		 * with frame times scattered a millisecond or two about 16.7 ms, one frame in seven to four moves the world 8.3
		 * or 25 ms instead of 16.7, and fine water shows it as a stutter. Always within one step behind GetTime(); boats
		 * are drawn between their last two steps at this instant (ASailboatPawn::ApplyStateToTransform).
		 */
		double GetRenderTime() const
		{
			const double A = Stepper.Alpha();
			const double R = GetTime() - (1.0 - (A < 0.0 ? 0.0 : A > 1.0 ? 1.0 : A)) * Stepper.GetStepDt();
			return R > Base ? R : Base;   // (not before the start: "unset" sentinels below zero stay unset)
		}
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
